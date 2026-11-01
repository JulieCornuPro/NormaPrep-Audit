"""Couverture d'un référentiel pivot (cahier des charges, CNT-05).

Pour chaque exigence et chaque contrôle de la version active du pivot : les
éléments qui y sont reliés, parmi les versions actives des autres
référentiels. Une exigence est couverte si elle-même ou l'un de ses contrôles
reçoit au moins une correspondance.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import NATURE_AUDIT, Correspondance, Exigence, Referentiel, Section


def couverture(session: Session, code_pivot: str) -> dict[str, Any] | None:
    pivot = session.scalar(
        select(Referentiel)
        .where(Referentiel.code == code_pivot, Referentiel.actif.is_(True), Referentiel.nature == NATURE_AUDIT)
        .options(selectinload(Referentiel.sections).selectinload(Section.exigences).selectinload(Exigence.controles))
    )
    if pivot is None:
        return None

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
                "seuil_applique": corr.seuil_applique,
                "seuil_partiel": corr.seuil_partiel,
            }
        )

    sections = []
    nb_exigences = nb_couvertes = 0
    for s in pivot.sections:
        exigences = []
        for e in s.exigences:
            controles = [{"code": c.code, "intitule": c.intitule, "sources": sources.get(c.code, [])} for c in e.controles]
            directes = sources.get(e.code, [])
            couverte = bool(directes) or any(c["sources"] for c in controles)
            nb_exigences += 1
            nb_couvertes += couverte
            exigences.append(
                {"code": e.code, "libelle": e.libelle, "couverte": couverte, "sources": directes, "controles": controles}
            )
        sections.append({"code": s.code, "libelle": s.libelle, "exigences": exigences})

    return {
        "referentiel": pivot.code,
        "version": pivot.version,
        "nb_exigences": nb_exigences,
        "nb_couvertes": nb_couvertes,
        "non_couvertes": [e["code"] for s in sections for e in s["exigences"] if not e["couverte"]],
        "sections": sections,
    }
