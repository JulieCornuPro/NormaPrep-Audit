"""Plan d'ateliers automatique (cahier des charges, section 6).

1. Seules les questions retenues (profondeur) sont planifiées.
2. Les questions en mode pré-questionnaire, revue documentaire ou import
   sortent des ateliers et sont listées à part.
3. Les autres sont groupées par interlocuteurs, ordonnées par thème puis
   sous-thème, et découpées en ateliers dont la durée utile tient dans le
   budget (budget moins le temps d'ouverture et de clôture). Un sous-thème
   n'est coupé que s'il ne tient pas seul dans un atelier.

Durée d'une question : sa durée propre si le contenu la fixe, sinon la durée
par défaut de son type.
"""

from typing import Any

from app.diagnostic.contenu import ContenuMaturite, QuestionC

DUREE_PAR_TYPE = {"fermee": 1.0, "niveaux": 3.0, "demonstration": 5.0, "ouverte": 6.0}
SANS_INTERLOCUTEUR = "non_attribue"


def duree(q: QuestionC) -> float:
    return q.duree if q.duree is not None else DUREE_PAR_TYPE.get(q.type, 3.0)


def mode_effectif(q: QuestionC, modes: dict[str, str]) -> str:
    return modes.get(q.ref, q.mode)


def plan(
    contenu: ContenuMaturite,
    retenues: list[QuestionC],
    modes: dict[str, str],
    budget_minutes: int,
    ouverture_minutes: int,
) -> dict[str, Any]:
    utile = max(budget_minutes - ouverture_minutes, 1)
    hors_atelier: dict[str, list[dict[str, Any]]] = {"pre_questionnaire": [], "revue_documentaire": [], "import": []}

    # Groupes d'interlocuteurs, dans l'ordre de première apparition.
    groupes: dict[tuple[str, ...], list[QuestionC]] = {}
    for q in retenues:
        m = mode_effectif(q, modes)
        if m != "atelier":
            hors_atelier.setdefault(m, []).append(_question(q, contenu))
            continue
        cle = tuple(sorted(q.interlocuteurs)) or (SANS_INTERLOCUTEUR,)
        groupes.setdefault(cle, []).append(q)

    ateliers: list[dict[str, Any]] = []
    for interlocuteurs, questions in groupes.items():
        # Blocs par sous-thème, dans l'ordre des questions retenues.
        blocs: dict[str, list[QuestionC]] = {}
        for q in questions:
            blocs.setdefault(q.sous_theme, []).append(q)

        courant: list[QuestionC] = []
        for bloc in blocs.values():
            duree_bloc = sum(duree(q) for q in bloc)
            duree_courant = sum(duree(q) for q in courant)
            if courant and duree_courant + duree_bloc > utile:
                ateliers.append(_atelier(courant, interlocuteurs, contenu, ouverture_minutes))
                courant = []
            if duree_bloc <= utile:
                courant += bloc
                continue
            # Sous-thème trop long pour un seul atelier : découpé question par question.
            for q in bloc:
                if courant and sum(duree(x) for x in courant) + duree(q) > utile:
                    ateliers.append(_atelier(courant, interlocuteurs, contenu, ouverture_minutes))
                    courant = []
                courant.append(q)
        if courant:
            ateliers.append(_atelier(courant, interlocuteurs, contenu, ouverture_minutes))

    for i, a in enumerate(ateliers, start=1):
        a["numero"] = i

    return {
        "budget_minutes": budget_minutes,
        "ouverture_minutes": ouverture_minutes,
        "ateliers": ateliers,
        "duree_totale_minutes": sum(a["duree_minutes"] for a in ateliers),
        "depassements": [a["numero"] for a in ateliers if a["duree_minutes"] > budget_minutes],
        "hors_atelier": hors_atelier,
        "duree_pre_questionnaire_minutes": sum(q["duree"] for q in hors_atelier["pre_questionnaire"]),
    }


def _question(q: QuestionC, contenu: ContenuMaturite) -> dict[str, Any]:
    return {
        "ref": q.ref,
        "enonce": q.enonce,
        "sous_theme": q.sous_theme,
        "sous_theme_libelle": contenu.sous_themes[q.sous_theme].libelle,
        "type": q.type,
        "duree": duree(q),
        "interlocuteurs": q.interlocuteurs,
    }


def _atelier(
    questions: list[QuestionC], interlocuteurs: tuple[str, ...], contenu: ContenuMaturite, ouverture: int
) -> dict[str, Any]:
    sous_themes: list[str] = []
    for q in questions:
        if q.sous_theme not in sous_themes:
            sous_themes.append(q.sous_theme)
    return {
        "interlocuteurs": [i for i in interlocuteurs if i != SANS_INTERLOCUTEUR],
        "sous_themes": [{"code": c, "libelle": contenu.sous_themes[c].libelle} for c in sous_themes],
        "questions": [_question(q, contenu) for q in questions],
        "duree_questions_minutes": sum(duree(q) for q in questions),
        "duree_minutes": round(sum(duree(q) for q in questions) + ouverture),
    }
