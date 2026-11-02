"""Couverture d'un référentiel pivot (cahier des charges, CNT-05).

Pour chaque élément du niveau évalué dans le socle (la mesure, en général) de
la version active du pivot : les questions et contrôles d'autres référentiels
qui y sont reliés, parmi les versions actives. Un élément est couvert si
lui-même ou l'un de ses descendants reçoit au moins une correspondance.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contenu import arbre
from app.models import NATURE_AUDIT, Correspondance, Referentiel


def couverture(session: Session, code_pivot: str) -> dict[str, Any] | None:
    pivot = session.scalar(
        select(Referentiel).where(
            Referentiel.code == code_pivot,
            Referentiel.actif.is_(True),
            Referentiel.nature == NATURE_AUDIT,
            Referentiel.mission_id.is_(None),
        )
    )
    if pivot is None:
        return None
    a = arbre.charger(session, pivot)

    lignes = session.execute(
        select(Correspondance, Referentiel.code, Referentiel.version)
        .join(Referentiel, Referentiel.id == Correspondance.referentiel_id)
        .where(Correspondance.cible_referentiel == code_pivot, Referentiel.actif.is_(True))
        .order_by(Referentiel.code, Correspondance.source_code)
    ).all()
    sources: dict[str, list[dict[str, Any]]] = {}
    for corr, ref_code, ref_version in lignes:
        sources.setdefault(corr.cible_code, []).append(
            {
                "referentiel": ref_code,
                "version": ref_version,
                "type": corr.source_type,
                "code": corr.source_code,
                "cible": corr.cible_code,
                "seuil_applique": corr.seuil_applique,
                "seuil_partiel": corr.seuil_partiel,
            }
        )

    elements = []
    for n in a.au_niveau(pivot.niveau_socle):
        trouvees = [s for x in [n, *n.descendants()] for s in sources.get(x.code, [])]
        groupe = n.ancetre(0)
        elements.append(
            {
                "code": n.code,
                "libelle": n.libelle,
                "groupe": groupe.libelle if groupe and groupe is not n else "",
                "couverte": bool(trouvees),
                "sources": trouvees,
            }
        )
    niveau = pivot.niveaux[pivot.niveau_socle] if pivot.niveau_socle < len(pivot.niveaux) else ""
    return {
        "referentiel": pivot.code,
        "version": pivot.version,
        "niveau": niveau,
        "nb_exigences": len(elements),
        "nb_couvertes": sum(e["couverte"] for e in elements),
        "non_couvertes": [e["code"] for e in elements if not e["couverte"]],
        "elements": elements,
    }
