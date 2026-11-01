"""Import des référentiels en base.

Principes (repris de NormaPrep et adaptés aux versions figées) :

- **tout ou rien** : validation complète d'abord, puis écriture dans une seule
  transaction ; à la moindre erreur, rien n'est écrit ;
- **une version importée ne change jamais** : réimporter le même contenu sous
  la même version ne fait rien ; un contenu différent sous une version déjà
  importée est refusé (il faut changer la version), sauf remplacement
  explicite d'une version qu'aucun audit n'utilise ;
- la version importée devient la **version active** de son code ;
- les **références externes** (correspondances, prestations câblées vers un
  référentiel d'audit) sont vérifiées contre les versions actives en base :
  importer d'abord le référentiel pivot, puis ceux qui s'y rattachent.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.contenu import audit as validation_audit
from app.contenu import maturite as validation_maturite
from app.contenu.outils import Rapport
from app.journal import journaliser
from app.models import (
    NATURE_AUDIT,
    NATURE_MATURITE,
    Controle,
    Correspondance,
    Exigence,
    Prestation,
    Question,
    QuestionProfil,
    Recommandation,
    Referentiel,
    Reglementation,
    Section,
    SousTheme,
    Theme,
)


@dataclass
class ResultatImport:
    succes: bool = False
    deja_importe: bool = False
    code: str = ""
    version: str = ""
    referentiel_id: int | None = None
    erreurs: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Points d'entrée
# ---------------------------------------------------------------------------


def importer_maturite(
    session: Session,
    dossier: Path,
    *,
    utilisateur_id: int | None = None,
    remplacer: bool = False,
    simulation: bool = False,
) -> ResultatImport:
    rapport, modele = validation_maturite.analyser(dossier)
    return _importer(session, rapport, modele, NATURE_MATURITE, utilisateur_id, remplacer, simulation)


def importer_audit(
    session: Session,
    fichier: Path,
    *,
    utilisateur_id: int | None = None,
    remplacer: bool = False,
    simulation: bool = False,
) -> ResultatImport:
    rapport, modele = validation_audit.analyser(fichier)
    if modele is not None:
        # Même forme d'en-tête que pour la maturité.
        modele = {
            "referentiel": {k: modele[k] for k in ("code", "version", "libelle", "source", "licence", "empreinte")},
            **modele,
        }
    return _importer(session, rapport, modele, NATURE_AUDIT, utilisateur_id, remplacer, simulation)


# ---------------------------------------------------------------------------
# Déroulé commun
# ---------------------------------------------------------------------------


def _importer(
    session: Session,
    rapport: Rapport,
    modele: dict[str, Any] | None,
    nature: str,
    utilisateur_id: int | None,
    remplacer: bool,
    simulation: bool,
) -> ResultatImport:
    res = ResultatImport(erreurs=list(rapport.erreurs), avertissements=list(rapport.avertissements))
    if modele is not None:
        res.code = modele["referentiel"]["code"]
        res.version = modele["referentiel"]["version"]
        _verifier_references_externes(session, modele, nature, rapport)
        res.erreurs = list(rapport.erreurs)

    if res.erreurs or modele is None:
        if not simulation:
            journaliser(
                session,
                "contenu_import_refuse",
                utilisateur_id=utilisateur_id,
                objet_type="referentiel",
                objet_id=f"{res.code}@{res.version}" if res.code else None,
                details={"nature": nature, "erreurs": res.erreurs[:50], "nb_erreurs": len(res.erreurs)},
            )
            session.commit()
        return res

    entete = modele["referentiel"]
    existant = session.scalar(
        select(Referentiel).where(Referentiel.code == entete["code"], Referentiel.version == entete["version"])
    )
    if existant is not None:
        if existant.nature != nature:
            res.erreurs.append(f"{entete['code']} — Ce code est déjà utilisé par un référentiel de nature « {existant.nature} ».")
            return res
        if existant.empreinte == entete["empreinte"]:
            res.succes = True
            res.deja_importe = True
            res.referentiel_id = existant.id
            return res
        if not remplacer:
            res.erreurs.append(
                f"{entete['code']} › version {entete['version']} — Cette version est déjà importée avec un "
                "contenu différent. Changez la version (une version importée ne change jamais)."
            )
            return res

    autre_nature = session.scalar(
        select(Referentiel.nature).where(Referentiel.code == entete["code"], Referentiel.nature != nature).limit(1)
    )
    if autre_nature:
        res.erreurs.append(f"{entete['code']} — Ce code est déjà utilisé par un référentiel de nature « {autre_nature} ».")
        return res

    if simulation:
        res.succes = True
        return res

    # ---- écriture, dans la transaction de la session ----------------------
    try:
        if existant is not None:
            # Remplacement explicite. Quand les audits existeront, une version
            # utilisée par un audit ne pourra pas être remplacée.
            session.delete(existant)
            session.flush()

        ref = Referentiel(
            code=entete["code"],
            version=entete["version"],
            nature=nature,
            libelle=entete["libelle"],
            source=entete.get("source", ""),
            licence=entete.get("licence", ""),
            empreinte=entete["empreinte"],
            importe_par=utilisateur_id,
            avertissements=res.avertissements,
            actif=False,
        )
        session.add(ref)
        session.flush()

        if nature == NATURE_MATURITE:
            res.stats = _ecrire_maturite(session, ref, modele)
        else:
            res.stats = _ecrire_audit(session, ref, modele)

        session.execute(update(Referentiel).where(Referentiel.code == ref.code, Referentiel.id != ref.id).values(actif=False))
        ref.actif = True

        journaliser(
            session,
            "contenu_importe",
            utilisateur_id=utilisateur_id,
            objet_type="referentiel",
            objet_id=f"{ref.code}@{ref.version}",
            details={"nature": nature, "remplacement": existant is not None, "stats": res.stats},
        )
        session.commit()
    except Exception:
        session.rollback()
        raise

    res.succes = True
    res.referentiel_id = ref.id
    return res


# ---------------------------------------------------------------------------
# Références vers d'autres référentiels
# ---------------------------------------------------------------------------


def _codes_actifs(session: Session, code_referentiel: str) -> dict[str, set[str]] | None:
    """Pour la version active d'un référentiel d'audit : codes de sections,
    d'exigences et de contrôles. None si aucune version active."""
    ref = session.scalar(
        select(Referentiel).where(
            Referentiel.code == code_referentiel, Referentiel.actif.is_(True), Referentiel.nature == NATURE_AUDIT
        )
    )
    if ref is None:
        return None
    return {
        "sections": set(session.scalars(select(Section.code).where(Section.referentiel_id == ref.id))),
        "cibles": set(session.scalars(select(Exigence.code).where(Exigence.referentiel_id == ref.id)))
        | set(session.scalars(select(Controle.code).where(Controle.referentiel_id == ref.id))),
    }


def _verifier_references_externes(session: Session, modele: dict[str, Any], nature: str, rapport: Rapport) -> None:
    cache: dict[str, dict[str, set[str]] | None] = {}

    def codes(ref: str) -> dict[str, set[str]] | None:
        if ref not in cache:
            cache[ref] = _codes_actifs(session, ref)
        return cache[ref]

    for corr in _toutes_correspondances(modele, nature):
        cible = codes(corr["referentiel"])
        if cible is None:
            rapport.erreur(
                corr["ou"],
                f"Référentiel « {corr['referentiel']} » absent de la base : importez-le avant celui-ci.",
            )
        elif corr["code"] not in cible["cibles"]:
            rapport.erreur(corr["ou"], f"Code « {corr['code']} » inconnu dans {corr['referentiel']} (version active).")

    if nature == NATURE_MATURITE:
        for p in modele["prestations"].values():
            if not p["referentiel_audit"]:
                continue
            cible = codes(p["referentiel_audit"])
            if cible is None:
                rapport.erreur(
                    p["ou"],
                    f"Référentiel d'audit « {p['referentiel_audit']} » absent de la base : importez-le avant celui-ci.",
                )
                continue
            for s in p["sections"]:
                if s not in cible["sections"]:
                    rapport.erreur(p["ou"], f"Section « {s} » inconnue dans {p['referentiel_audit']} (version active).")


def _toutes_correspondances(modele: dict[str, Any], nature: str) -> list[dict[str, Any]]:
    if nature == NATURE_MATURITE:
        return [c for st in modele["sous_themes"].values() for q in st["questions"].values() for c in q["correspondances"]]
    return [c for s in modele["sections"] for e in s["exigences"] for ctl in e["controles"] for c in ctl["correspondances"]]


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


def _correspondance(ref: Referentiel, source_type: str, source_code: str, c: dict[str, Any]) -> Correspondance:
    return Correspondance(
        referentiel_id=ref.id,
        source_type=source_type,
        source_code=source_code,
        cible_referentiel=c["referentiel"],
        cible_code=c["code"],
        seuil_applique=c["seuil_applique"],
        seuil_partiel=c["seuil_partiel"],
    )


def _ecrire_maturite(session: Session, ref: Referentiel, modele: dict[str, Any]) -> dict[str, int]:
    stats = dict.fromkeys(
        (
            "themes",
            "sous_themes",
            "questions",
            "recommandations",
            "prestations",
            "questions_profil",
            "reglementations",
            "correspondances",
        ),
        0,
    )
    themes: dict[str, Theme] = {}
    for code, t in modele["themes"].items():
        themes[code] = Theme(
            referentiel_id=ref.id, code=code, libelle=t["libelle"], couleur=t["couleur"], ordre=t["ordre"], poids=t["poids"]
        )
        session.add(themes[code])
        stats["themes"] += 1

    for code, p in modele["prestations"].items():
        session.add(
            Prestation(
                referentiel_id=ref.id,
                code=code,
                libelle=p["libelle"],
                description=p["description"],
                lien=p["lien"],
                referentiel_audit=p["referentiel_audit"],
                sections=p["sections"],
            )
        )
        stats["prestations"] += 1
    session.flush()

    for code, st in modele["sous_themes"].items():
        sous_theme = SousTheme(
            referentiel_id=ref.id,
            theme_id=themes[st["theme"]].id,
            code=code,
            libelle=st["libelle"],
            description=st["description"],
            ordre=st["ordre"],
            poids=st["poids"],
        )
        session.add(sous_theme)
        session.flush()
        stats["sous_themes"] += 1

        questions: dict[str, Question] = {}
        for qref, q in st["questions"].items():
            questions[qref] = Question(
                referentiel_id=ref.id,
                sous_theme_id=sous_theme.id,
                ref=qref,
                enonce=q["enonce"],
                aide=q["aide"],
                profondeur=q["profondeur"],
                poids=q["poids"],
                references=q["references"],
                niveaux=q["niveaux"],
                ordre=q["ordre"],
                type_question=q["type_question"],
                duree_estimee=q["duree_estimee"],
                mode=q["mode"],
                interlocuteurs=q["interlocuteurs"],
            )
            session.add(questions[qref])
            stats["questions"] += 1
            for c in q["correspondances"]:
                session.add(_correspondance(ref, "question", qref, c))
                stats["correspondances"] += 1
        session.flush()

        for rref, rec in st["recommandations"].items():
            session.add(
                Recommandation(
                    referentiel_id=ref.id,
                    sous_theme_id=sous_theme.id,
                    question_id=questions[rec["question"]].id if rec["question"] else None,
                    ref=rref,
                    texte=rec["texte"],
                    seuil=rec["seuil"],
                    effort=rec["effort"],
                    quick_win=rec["quick_win"],
                    prestation_code=rec["prestation"] or None,
                )
            )
            stats["recommandations"] += 1

    for code, q in modele["profil"].items():
        session.add(
            QuestionProfil(
                referentiel_id=ref.id,
                code=code,
                libelle=q["libelle"],
                aide=q["aide"],
                type=q["type"],
                condition=q["condition"],
                choix=list(q["choix"].values()),
                ordre=q["ordre"],
            )
        )
        stats["questions_profil"] += 1

    for code, r in modele["reglementations"].items():
        session.add(
            Reglementation(
                referentiel_id=ref.id,
                code=code,
                libelle=r["libelle"],
                nature=r["nature"],
                description=r["description"],
                echeance=r["echeance"],
                actions=r["actions"],
                regles=list(r["regles"].values()),
                exigences=r["exigences"],
                ordre=r["ordre"],
            )
        )
        stats["reglementations"] += 1

    session.flush()
    return stats


def _ecrire_audit(session: Session, ref: Referentiel, modele: dict[str, Any]) -> dict[str, int]:
    stats = {"sections": 0, "exigences": 0, "controles": 0, "correspondances": 0}
    for s in modele["sections"]:
        section = Section(
            referentiel_id=ref.id, code=s["code"], libelle=s["libelle"], description=s["description"], ordre=s["ordre"]
        )
        session.add(section)
        session.flush()
        stats["sections"] += 1
        for e in s["exigences"]:
            exigence = Exigence(
                referentiel_id=ref.id,
                section_id=section.id,
                code=e["code"],
                libelle=e["libelle"],
                description=e["description"],
                ordre=e["ordre"],
            )
            session.add(exigence)
            session.flush()
            stats["exigences"] += 1
            for c in e["controles"]:
                session.add(
                    Controle(
                        referentiel_id=ref.id,
                        exigence_id=exigence.id,
                        code=c["code"],
                        intitule=c["intitule"],
                        description=c["description"],
                        niveau=c["niveau"],
                        methode=c["methode"],
                        verification=c["verification"],
                        valeur_attendue=c["valeur_attendue"],
                        preuves_attendues=c["preuves_attendues"],
                        recommandation=c["recommandation"],
                        poids=c["poids"],
                        ordre=c["ordre"],
                    )
                )
                stats["controles"] += 1
                for corr in c["correspondances"]:
                    session.add(_correspondance(ref, "controle", c["code"], corr))
                    stats["correspondances"] += 1
    session.flush()
    return stats
