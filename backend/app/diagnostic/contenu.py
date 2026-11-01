"""Contenu d'une version de référentiel de maturité, chargé en mémoire.

Une version est figée : la charger une fois par requête suffit, et tous les
calculs travaillent sur ces structures simples, sans requête supplémentaire.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Prestation,
    Question,
    QuestionProfil,
    Recommandation,
    Reglementation,
    SousTheme,
    Theme,
)

RANG_PROFONDEUR = {"essentiel": 1, "standard": 2, "renforce": 3}
RANG_NIVEAU = {"recommande": 1, "a_verifier": 2, "obligatoire": 3}


@dataclass
class QuestionC:
    ref: str
    sous_theme: str
    enonce: str
    aide: str
    profondeur: str
    poids: float
    references: list[str]
    niveaux: dict[str, str]
    ordre: int
    type: str
    duree: float | None
    mode: str
    interlocuteurs: list[str]


@dataclass
class SousThemeC:
    code: str
    theme: str
    libelle: str
    ordre: int
    poids: float
    questions: list[QuestionC] = field(default_factory=list)


@dataclass
class ThemeC:
    code: str
    libelle: str
    couleur: str
    ordre: int
    poids: float
    sous_themes: list[SousThemeC] = field(default_factory=list)


@dataclass
class ContenuMaturite:
    themes: list[ThemeC]
    sous_themes: dict[str, SousThemeC]
    questions: dict[str, QuestionC]
    profil: list[dict[str, Any]]  # questions de profilage, dans l'ordre
    reglementations: dict[str, dict[str, Any]]
    recommandations: list[dict[str, Any]]
    prestations: dict[str, dict[str, Any]]


def charger(session: Session, referentiel_id: int) -> ContenuMaturite:
    rid = referentiel_id
    themes_db = session.scalars(select(Theme).where(Theme.referentiel_id == rid).order_by(Theme.ordre, Theme.id)).all()
    themes = [ThemeC(t.code, t.libelle, t.couleur, t.ordre, t.poids) for t in themes_db]
    par_id_theme = {t.id: th for t, th in zip(themes_db, themes, strict=True)}

    sts_db = session.scalars(
        select(SousTheme).where(SousTheme.referentiel_id == rid).order_by(SousTheme.ordre, SousTheme.code)
    ).all()
    sous_themes: dict[str, SousThemeC] = {}
    par_id_st: dict[int, SousThemeC] = {}
    for s in sts_db:
        th = par_id_theme[s.theme_id]
        c = SousThemeC(s.code, th.code, s.libelle, s.ordre, s.poids)
        th.sous_themes.append(c)
        sous_themes[s.code] = c
        par_id_st[s.id] = c

    questions: dict[str, QuestionC] = {}
    par_id_q: dict[int, str] = {}
    for q in session.scalars(select(Question).where(Question.referentiel_id == rid).order_by(Question.ordre, Question.id)):
        st = par_id_st[q.sous_theme_id]
        c = QuestionC(
            q.ref,
            st.code,
            q.enonce,
            q.aide,
            q.profondeur,
            q.poids,
            q.references,
            q.niveaux,
            q.ordre,
            q.type_question,
            q.duree_estimee,
            q.mode,
            q.interlocuteurs,
        )
        st.questions.append(c)
        questions[q.ref] = c
        par_id_q[q.id] = q.ref

    profil = [
        {"code": p.code, "libelle": p.libelle, "aide": p.aide, "type": p.type, "condition": p.condition, "choix": p.choix}
        for p in session.scalars(
            select(QuestionProfil).where(QuestionProfil.referentiel_id == rid).order_by(QuestionProfil.ordre)
        )
    ]
    reglementations = {
        r.code: {
            "code": r.code,
            "libelle": r.libelle,
            "nature": r.nature,
            "description": r.description,
            "echeance": r.echeance,
            "actions": r.actions,
            "regles": r.regles,
            "exigences": r.exigences,
            "ordre": r.ordre,
        }
        for r in session.scalars(
            select(Reglementation).where(Reglementation.referentiel_id == rid).order_by(Reglementation.ordre)
        )
    }
    recommandations = [
        {
            "ref": r.ref,
            "sous_theme": par_id_st[r.sous_theme_id].code,
            "question": par_id_q.get(r.question_id) if r.question_id else None,
            "texte": r.texte,
            "seuil": r.seuil,
            "effort": r.effort,
            "quick_win": r.quick_win,
            "prestation": r.prestation_code,
        }
        for r in session.scalars(select(Recommandation).where(Recommandation.referentiel_id == rid).order_by(Recommandation.ref))
    ]
    prestations = {
        p.code: {
            "code": p.code,
            "libelle": p.libelle,
            "description": p.description,
            "lien": p.lien,
            "referentiel_audit": p.referentiel_audit,
            "sections": p.sections,
        }
        for p in session.scalars(select(Prestation).where(Prestation.referentiel_id == rid))
    }
    return ContenuMaturite(themes, sous_themes, questions, profil, reglementations, recommandations, prestations)
