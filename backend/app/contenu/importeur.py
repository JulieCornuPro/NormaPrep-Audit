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
from app.contenu import excel as lecture_excel
from app.contenu import maturite as validation_maturite
from app.contenu.outils import Rapport
from app.journal import journaliser
from app.models import (
    NATURE_AUDIT,
    NATURE_MATURITE,
    Correspondance,
    Noeud,
    Prestation,
    Question,
    QuestionProfil,
    Recommandation,
    Referentiel,
    Reglementation,
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
    feuille: str = ""
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


ENTETE_AUDIT = ("code", "version", "libelle", "source", "licence", "empreinte", "niveaux", "profils", "niveau_socle")


def importer_audit(
    session: Session,
    fichier: Path,
    *,
    utilisateur_id: int | None = None,
    remplacer: bool = False,
    simulation: bool = False,
    mission_id: int | None = None,
) -> ResultatImport:
    """Référentiel d'audit au format JSON (Section > Exigence > Contrôle)."""
    rapport, modele = validation_audit.analyser(fichier)
    if modele is not None:
        modele = {"referentiel": {k: modele[k] for k in ENTETE_AUDIT}, **modele}
    return _importer(session, rapport, modele, NATURE_AUDIT, utilisateur_id, remplacer, simulation, mission_id)


def importer_excel(
    session: Session,
    contenu: bytes,
    nom_fichier: str,
    *,
    utilisateur_id: int | None = None,
    remplacer: bool = False,
    simulation: bool = False,
    mission_id: int | None = None,
) -> list[ResultatImport]:
    """Classeur Excel : un référentiel par feuille listée dans « Infos ».
    Chaque feuille est importée indépendamment (une feuille en erreur
    n'empêche pas les autres)."""
    resultats = []
    for feuille, rapport, modele in lecture_excel.lire(contenu, nom_fichier):
        if modele is not None:
            modele = {"referentiel": {k: modele[k] for k in ENTETE_AUDIT}, **modele}
        res = _importer(session, rapport, modele, NATURE_AUDIT, utilisateur_id, remplacer, simulation, mission_id)
        res.feuille = feuille
        resultats.append(res)
    return resultats


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
    mission_id: int | None = None,
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
                details={"nature": nature, "mission_id": mission_id, "erreurs": res.erreurs[:50], "nb_erreurs": len(res.erreurs)},
            )
            session.commit()
        return res

    entete = modele["referentiel"]
    portee = Referentiel.mission_id.is_(None) if mission_id is None else Referentiel.mission_id == mission_id
    existant = session.scalar(
        select(Referentiel).where(Referentiel.code == entete["code"], Referentiel.version == entete["version"], portee)
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
        select(Referentiel.nature).where(Referentiel.code == entete["code"], Referentiel.nature != nature, portee).limit(1)
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
            mission_id=mission_id,
            niveaux=entete.get("niveaux", []),
            profils=entete.get("profils", []),
            niveau_socle=entete.get("niveau_socle", 1),
        )
        session.add(ref)
        session.flush()

        if nature == NATURE_MATURITE:
            res.stats = _ecrire_maturite(session, ref, modele)
        else:
            res.stats = _ecrire_audit(session, ref, modele)

        session.execute(
            update(Referentiel).where(Referentiel.code == ref.code, Referentiel.id != ref.id, portee).values(actif=False)
        )
        ref.actif = True

        journaliser(
            session,
            "contenu_importe",
            utilisateur_id=utilisateur_id,
            objet_type="referentiel",
            objet_id=f"{ref.code}@{ref.version}",
            details={"nature": nature, "mission_id": mission_id, "remplacement": existant is not None, "stats": res.stats},
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


def _codes_actifs(session: Session, code_referentiel: str) -> dict[str, Any] | None:
    """Version active d'un référentiel d'audit de la bibliothèque : ses codes
    d'éléments et ses profils. None si aucune version active."""
    ref = session.scalar(
        select(Referentiel).where(
            Referentiel.code == code_referentiel,
            Referentiel.actif.is_(True),
            Referentiel.nature == NATURE_AUDIT,
            Referentiel.mission_id.is_(None),
        )
    )
    if ref is None:
        return None
    return {"cibles": set(session.scalars(select(Noeud.code).where(Noeud.referentiel_id == ref.id))), "profils": ref.profils}


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
                if s not in cible["cibles"]:
                    rapport.erreur(p["ou"], f"Section « {s} » inconnue dans {p['referentiel_audit']} (version active).")
        # Référentiel du socle appelé par une réglementation : il peut être chargé
        # plus tard, d'où un simple avertissement.
        for reg in modele["reglementations"].values():
            if not reg.get("referentiel"):
                continue
            cible = codes(reg["referentiel"])
            ou = f"_reglementations.json › {reg['code']}"
            if cible is None:
                rapport.avertir(
                    ou,
                    f"Référentiel « {reg['referentiel']} » pas encore chargé : il ne pourra être proposé dans le socle qu'une fois chargé.",
                )
            elif reg.get("profil") and cible["profils"] and reg["profil"] not in cible["profils"]:
                rapport.erreur(
                    ou, f"Profil « {reg['profil']} » inconnu dans {reg['referentiel']} (profils : {', '.join(cible['profils'])})."
                )


def _toutes_correspondances(modele: dict[str, Any], nature: str) -> list[dict[str, Any]]:
    if nature == NATURE_MATURITE:
        return [c for st in modele["sous_themes"].values() for q in st["questions"].values() for c in q["correspondances"]]
    return [c for n in modele["noeuds"] for c in n["correspondances"]]


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
                referentiel_code=r.get("referentiel"),
                referentiel_profil=r.get("profil"),
            )
        )
        stats["reglementations"] += 1

    session.flush()
    return stats


def _ecrire_audit(session: Session, ref: Referentiel, modele: dict[str, Any]) -> dict[str, int]:
    """Nœuds dans l'ordre du modèle (un parent précède toujours ses enfants)."""
    ids: dict[str, int] = {}
    stats = {"noeuds": 0, "correspondances": 0}
    par_niveau: dict[str, int] = {}
    for n in modele["noeuds"]:
        noeud = Noeud(
            referentiel_id=ref.id,
            parent_id=ids[n["parent"]] if n["parent"] else None,
            niveau=n["niveau"],
            ordre=n["ordre"],
            code=n["code"],
            libelle=n["libelle"],
            description=n.get("description", ""),
            profils=n.get("profils", []),
            methode=n.get("methode", ""),
            verification=n.get("verification", ""),
            valeur_attendue=n.get("valeur_attendue", ""),
            preuves_attendues=n.get("preuves_attendues", []),
            recommandation=n.get("recommandation", ""),
            interlocuteurs=n.get("interlocuteurs", []),
            poids=n.get("poids", 1.0),
        )
        session.add(noeud)
        session.flush()
        ids[n["code"]] = noeud.id
        stats["noeuds"] += 1
        nom = (ref.niveaux[n["niveau"]] if n["niveau"] < len(ref.niveaux) else f"niveau {n['niveau']}").lower()
        par_niveau[nom] = par_niveau.get(nom, 0) + 1
        for corr in n.get("correspondances", []):
            session.add(_correspondance(ref, "controle", n["code"], corr))
            stats["correspondances"] += 1
    session.flush()
    return {**par_niveau, **stats}
