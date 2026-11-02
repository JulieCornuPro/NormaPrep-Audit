"""Socle de sécurité (EBIOS RM, atelier 1).

Le socle d'une analyse est la sélection des référentiels applicables
(bibliothèque ou référentiels du client), chacun sur une version figée et avec
un profil. Pour chaque élément du niveau évalué (la mesure, en général), on
renseigne l'état d'application et on justifie les écarts.

Sources de pré-remplissage, l'analyste validant toujours :
- le diagnostic de maturité de la mission : présomption à partir des
  correspondances question → mesure et de leurs seuils (appliquée si
  niveau ≥ seuil_applique, partielle si niveau ≥ seuil_partiel ; par défaut
  3 et 1). Plusieurs questions sur une même mesure : l'état le plus prudent.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contenu import arbre
from app.models import (
    AnalyseRisques,
    Correspondance,
    Diagnostic,
    DiagReglementation,
    EtatSocle,
    Referentiel,
    Reglementation,
    Reponse,
    SocleReferentiel,
)

SEUIL_APPLIQUE_DEFAUT = 3
SEUIL_PARTIEL_DEFAUT = 1
RANG = {"non_applique": 0, "partiel": 1, "applique": 2}
LIBELLES = {
    "applique": "Appliquée",
    "partiel": "Partiellement appliquée",
    "non_applique": "Non appliquée",
    "non_evalue": "Non évaluée",
    "non_applicable": "Non applicable",
}


def vue(session: Session, analyse: AnalyseRisques) -> dict[str, Any]:
    referentiels = []
    lignes = session.scalars(
        select(SocleReferentiel)
        .where(SocleReferentiel.analyse_id == analyse.id)
        .order_by(SocleReferentiel.ordre, SocleReferentiel.id)
    ).all()
    for sr in lignes:
        referentiels.append(_vue_referentiel(session, sr))
    return {"referentiels": referentiels, "proposes": proposes(session, analyse, lignes)}


def _vue_referentiel(session: Session, sr: SocleReferentiel) -> dict[str, Any]:
    ref = sr.referentiel
    a = arbre.charger(session, ref)
    etats = {e.noeud_code: e for e in session.scalars(select(EtatSocle).where(EtatSocle.socle_referentiel_id == sr.id))}
    elements = []
    compte = dict.fromkeys(LIBELLES, 0)
    sans_justification = 0
    for n in a.au_niveau(ref.niveau_socle, sr.profil):
        e = etats.get(n.code)
        etat = e.etat if e else "non_evalue"
        compte[etat] += 1
        if etat in ("partiel", "non_applique") and not (e and e.justification.strip()):
            sans_justification += 1
        groupe = n.ancetre(0)
        elements.append(
            {
                "code": n.code,
                "libelle": n.libelle,
                "groupe": groupe.libelle if groupe and groupe is not n else "",
                "etat": etat,
                "ecart": e.ecart if e else "",
                "justification": e.justification if e else "",
                "source": e.source if e else None,
                "saisi_le": e.saisi_le if e else None,
                "details": [
                    {"code": d.code, "libelle": d.libelle, "niveau": d.niveau} for d in n.descendants() if d.applicable(sr.profil)
                ],
            }
        )
    return {
        "id": sr.id,
        "referentiel": {
            "id": ref.id,
            "code": ref.code,
            "version": ref.version,
            "libelle": ref.libelle,
            "client": ref.mission_id is not None,
            "profils": ref.profils,
            "niveau": ref.niveaux[ref.niveau_socle] if ref.niveau_socle < len(ref.niveaux) else "",
        },
        "profil": sr.profil,
        "motif": sr.motif,
        "compte": compte,
        "sans_justification": sans_justification,
        "elements": elements,
    }


def proposes(session: Session, analyse: AnalyseRisques, lignes: list[SocleReferentiel]) -> list[dict[str, Any]]:
    """Référentiels appelés par les réglementations retenues dans le diagnostic
    lié, pas encore dans le socle."""
    if analyse.diagnostic_id is None:
        return []
    diag = session.get(Diagnostic, analyse.diagnostic_id)
    if diag is None:
        return []
    deja = {sr.referentiel.code for sr in lignes}
    retenues = session.scalars(
        select(DiagReglementation.reglementation_code).where(
            DiagReglementation.diagnostic_id == diag.id, DiagReglementation.decision == "retenue"
        )
    ).all()
    resultat: dict[str, dict[str, Any]] = {}
    for reg in session.scalars(
        select(Reglementation).where(
            Reglementation.referentiel_id == diag.referentiel_id,
            Reglementation.code.in_(retenues),
            Reglementation.referentiel_code.is_not(None),
        )
    ):
        if reg.referentiel_code in deja:
            continue
        ref = session.scalar(
            select(Referentiel).where(
                Referentiel.code == reg.referentiel_code, Referentiel.actif.is_(True), Referentiel.mission_id.is_(None)
            )
        )
        if ref is None:
            continue
        p = resultat.setdefault(
            ref.code,
            {"referentiel_id": ref.id, "code": ref.code, "libelle": ref.libelle, "profil": reg.referentiel_profil, "motifs": []},
        )
        p["motifs"].append(reg.libelle)
        # Profil le plus exigeant demandé (ordre des profils du référentiel).
        if reg.referentiel_profil and ref.profils and reg.referentiel_profil in ref.profils:
            if p["profil"] not in ref.profils or ref.profils.index(reg.referentiel_profil) > ref.profils.index(p["profil"]):
                p["profil"] = reg.referentiel_profil
    return list(resultat.values())


def pre_remplir(session: Session, analyse: AnalyseRisques, sr: SocleReferentiel, utilisateur_id: int) -> int:
    """Présume l'état des éléments non encore évalués à partir du diagnostic
    lié. Ne remplace jamais une saisie. Renvoie le nombre d'éléments remplis."""
    if analyse.diagnostic_id is None:
        return 0
    diag = session.get(Diagnostic, analyse.diagnostic_id)
    if diag is None:
        return 0
    ref = sr.referentiel
    correspondances = session.scalars(
        select(Correspondance).where(
            Correspondance.referentiel_id == diag.referentiel_id,
            Correspondance.source_type == "question",
            Correspondance.cible_referentiel == ref.code,
        )
    ).all()
    if not correspondances:
        return 0
    reponses = {r.question_ref: r for r in session.scalars(select(Reponse).where(Reponse.diagnostic_id == diag.id))}
    a = arbre.charger(session, ref)
    existants = {e.noeud_code: e for e in session.scalars(select(EtatSocle).where(EtatSocle.socle_referentiel_id == sr.id))}
    remplis = 0
    for n in a.au_niveau(ref.niveau_socle, sr.profil):
        e = existants.get(n.code)
        if e is not None and e.etat != "non_evalue":
            continue
        codes = {n.code, *(d.code for d in n.descendants())}
        presomptions = []
        for c in correspondances:
            rep = reponses.get(c.source_code)
            if c.cible_code not in codes or rep is None or rep.non_applicable or rep.niveau is None:
                continue
            seuil_a = c.seuil_applique or SEUIL_APPLIQUE_DEFAUT
            seuil_p = c.seuil_partiel or SEUIL_PARTIEL_DEFAUT
            etat = "applique" if rep.niveau >= seuil_a else "partiel" if rep.niveau >= seuil_p else "non_applique"
            presomptions.append((etat, f"{c.source_code} (niveau {rep.niveau})"))
        if not presomptions:
            continue
        etat = min((p[0] for p in presomptions), key=RANG.__getitem__)
        if e is None:
            e = EtatSocle(socle_referentiel_id=sr.id, noeud_code=n.code)
            session.add(e)
        e.etat = etat
        e.ecart = "Présumé depuis le diagnostic de maturité : " + ", ".join(p[1] for p in presomptions) + ". À valider."
        e.source = "maturite"
        e.saisi_par = utilisateur_id
        e.saisi_le = datetime.now(UTC)
        remplis += 1
    session.flush()
    return remplis
