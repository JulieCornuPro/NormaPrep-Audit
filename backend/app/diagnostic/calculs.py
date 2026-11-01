"""Questions retenues, scores, écarts et recommandations.

Règles (cadrage NormaPrep, §8) :

1. Question : niveau 0–5 saisi. N/A = exclue de tous les calculs. Une question
   non posée (profondeur insuffisante) n'existe pas pour ce diagnostic.
2. Sous-thème : moyenne des niveaux, pondérée par le poids des questions.
   Toutes N/A → sous-thème N/A.
3. Thème : moyenne des sous-thèmes non N/A, pondérée par leur poids.
4. Global : moyenne des thèmes non N/A, pondérée par leur poids.
5. Cible d'un thème : moyenne des cibles de ses sous-thèmes non N/A ; même
   règle pour la cible globale.
6. Écart = cible − score (positif = en dessous de la cible).
7. Arrondi à une décimale à l'affichage seulement.

Une question retenue sans réponse ne compte pas dans le score : la
progression le signale, et la finalisation l'interdit.
"""

from typing import Any

from app.diagnostic.contenu import RANG_PROFONDEUR, ContenuMaturite, QuestionC
from app.models import Reponse


def questions_retenues(contenu: ContenuMaturite, exigences: dict[str, dict[str, Any]]) -> list[QuestionC]:
    retenues = []
    for th in contenu.themes:
        for st in th.sous_themes:
            requis = RANG_PROFONDEUR[exigences[st.code]["profondeur"]]
            retenues += [q for q in st.questions if RANG_PROFONDEUR[q.profondeur] <= requis]
    return retenues


def _moyenne(valeurs: list[tuple[float, float]]) -> float | None:
    """Moyenne pondérée de (valeur, poids) ; None si vide."""
    total = sum(p for _, p in valeurs)
    return sum(v * p for v, p in valeurs) / total if total else None


def _arrondi(v: float | None) -> float | None:
    return None if v is None else round(v, 1)


def progression(retenues: list[QuestionC], reponses: dict[str, Reponse]) -> dict[str, int]:
    repondues = sum(
        1 for q in retenues if q.ref in reponses and (reponses[q.ref].non_applicable or reponses[q.ref].niveau is not None)
    )
    return {"retenues": len(retenues), "repondues": repondues, "restantes": len(retenues) - repondues}


def resultats(
    contenu: ContenuMaturite,
    exigences: dict[str, dict[str, Any]],
    reponses: dict[str, Reponse],
) -> dict[str, Any]:
    retenues = questions_retenues(contenu, exigences)
    par_st: dict[str, list[QuestionC]] = {}
    for q in retenues:
        par_st.setdefault(q.sous_theme, []).append(q)

    themes_sortie = []
    scores_st: dict[str, float | None] = {}
    valeurs_globales: list[tuple[float, float]] = []
    cibles_globales: list[float] = []

    for th in contenu.themes:
        sts_sortie = []
        valeurs_theme: list[tuple[float, float]] = []
        cibles_theme: list[float] = []
        for st in th.sous_themes:
            qs = par_st.get(st.code, [])
            niveaux = [
                (float(reponses[q.ref].niveau), q.poids)
                for q in qs
                if q.ref in reponses and not reponses[q.ref].non_applicable and reponses[q.ref].niveau is not None
            ]
            toutes_na = bool(qs) and all(q.ref in reponses and reponses[q.ref].non_applicable for q in qs)
            score = None if toutes_na else _moyenne(niveaux)
            scores_st[st.code] = score
            cible = exigences[st.code]["cible"]
            if score is not None:
                valeurs_theme.append((score, st.poids))
                if cible is not None:
                    cibles_theme.append(cible)
            sts_sortie.append(
                {
                    "code": st.code,
                    "libelle": st.libelle,
                    "non_applicable": toutes_na,
                    "score": _arrondi(score),
                    "cible": cible,
                    "ecart": _arrondi(cible - score) if (cible is not None and score is not None) else None,
                    "reglementation": exigences[st.code]["reglementation"],
                    "profondeur": exigences[st.code]["profondeur"],
                    "nb_questions": len(qs),
                }
            )
        score_theme = _moyenne(valeurs_theme)
        cible_theme = sum(cibles_theme) / len(cibles_theme) if cibles_theme else None
        if score_theme is not None:
            valeurs_globales.append((score_theme, th.poids))
            if cible_theme is not None:
                cibles_globales.append(cible_theme)
        themes_sortie.append(
            {
                "code": th.code,
                "libelle": th.libelle,
                "couleur": th.couleur,
                "score": _arrondi(score_theme),
                "cible": _arrondi(cible_theme),
                "ecart": _arrondi(cible_theme - score_theme) if (cible_theme is not None and score_theme is not None) else None,
                "sous_themes": sts_sortie,
            }
        )

    score_global = _moyenne(valeurs_globales)
    cible_globale = sum(cibles_globales) / len(cibles_globales) if cibles_globales else None
    recos = recommandations(contenu, exigences, reponses, retenues, scores_st)

    return {
        "global": {
            "score": _arrondi(score_global),
            "cible": _arrondi(cible_globale),
            "ecart": _arrondi(cible_globale - score_global) if (cible_globale is not None and score_global is not None) else None,
        },
        "themes": themes_sortie,
        "progression": progression(retenues, reponses),
        "recommandations": recos,
        "audits_proposes": audits_proposes(contenu, recos),
    }


def recommandations(
    contenu: ContenuMaturite,
    exigences: dict[str, dict[str, Any]],
    reponses: dict[str, Reponse],
    retenues: list[QuestionC],
    scores_st: dict[str, float | None],
) -> list[dict[str, Any]]:
    """Déclenchées si le niveau constaté (de la question, ou du sous-thème pour
    une recommandation de sous-thème) est inférieur au seuil. Triées par écart
    du sous-thème décroissant, puis quick wins, puis effort croissant."""
    refs_retenues = {q.ref for q in retenues}
    effort = {"faible": 0, "moyen": 1, "eleve": 2}
    declenchees = []
    for r in contenu.recommandations:
        if r["question"]:
            rep = reponses.get(r["question"])
            if r["question"] not in refs_retenues or rep is None or rep.non_applicable or rep.niveau is None:
                continue
            constate: float | None = rep.niveau
        else:
            constate = scores_st.get(r["sous_theme"])
            if constate is None:
                continue
        if constate >= r["seuil"]:
            continue
        cible = exigences[r["sous_theme"]]["cible"]
        score = scores_st.get(r["sous_theme"])
        ecart = (cible - score) if (cible is not None and score is not None) else None
        prestation = contenu.prestations.get(r["prestation"]) if r["prestation"] else None
        declenchees.append(
            {
                **r,
                "sous_theme_libelle": contenu.sous_themes[r["sous_theme"]].libelle,
                "niveau_constate": _arrondi(constate),
                "ecart_sous_theme": _arrondi(ecart),
                "prestation_libelle": prestation["libelle"] if prestation else None,
            }
        )
    declenchees.sort(
        key=lambda r: (
            -(r["ecart_sous_theme"] if r["ecart_sous_theme"] is not None else -99),
            not r["quick_win"],
            effort.get(r["effort"], 3),
            r["ref"],
        )
    )
    return declenchees


def audits_proposes(contenu: ContenuMaturite, recos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prestations appelées par les recommandations déclenchées, avec le
    référentiel d'audit et les sections à inclure."""
    vues: dict[str, dict[str, Any]] = {}
    for r in recos:
        code = r["prestation"]
        if not code or code not in contenu.prestations:
            continue
        p = contenu.prestations[code]
        entree = vues.setdefault(
            code,
            {
                "code": code,
                "libelle": p["libelle"],
                "description": p["description"],
                "referentiel_audit": p["referentiel_audit"],
                "sections": p["sections"],
                "sous_themes": [],
                "recommandations": [],
            },
        )
        if r["sous_theme"] not in entree["sous_themes"]:
            entree["sous_themes"].append(r["sous_theme"])
        entree["recommandations"].append(r["ref"])
    return list(vues.values())
