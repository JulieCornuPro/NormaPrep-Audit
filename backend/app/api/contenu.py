"""Référentiels : consultation, import, couverture."""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AdminDep, SessionDep, UtilisateurDep
from app.config import reglages
from app.contenu.couverture import couverture
from app.contenu.importeur import importer_audit, importer_maturite
from app.models import (
    NATURE_AUDIT,
    Controle,
    Correspondance,
    Exigence,
    Prestation,
    Question,
    QuestionProfil,
    Referentiel,
    Reglementation,
    Section,
    SousTheme,
    Theme,
)

router = APIRouter(prefix="/api/contenu", tags=["Contenu"])


class ReferentielSortie(BaseModel):
    id: int
    code: str
    version: str
    nature: str
    libelle: str
    source: str
    licence: str
    actif: bool
    importe_le: datetime
    empreinte: str
    avertissements: list[str]


class DemandeImport(BaseModel):
    nature: Literal["maturite", "audit"]
    chemin: str
    remplacer: bool = False
    simulation: bool = False


class ResultatImportSortie(BaseModel):
    succes: bool
    deja_importe: bool
    code: str
    version: str
    referentiel_id: int | None
    erreurs: list[str]
    avertissements: list[str]
    stats: dict[str, int]


class ContenuDisponible(BaseModel):
    nature: Literal["maturite", "audit"]
    chemin: str


# ---------------------------------------------------------------------------


@router.get("/referentiels", response_model=list[ReferentielSortie])
def lister(u: UtilisateurDep, s: SessionDep, toutes_versions: bool = False) -> list[ReferentielSortie]:
    req = select(Referentiel).order_by(Referentiel.code, Referentiel.importe_le.desc())
    if not toutes_versions:
        req = req.where(Referentiel.actif.is_(True))
    return [ReferentielSortie.model_validate(r, from_attributes=True) for r in s.scalars(req)]


@router.get("/referentiels/{code}")
def detail(code: str, u: UtilisateurDep, s: SessionDep, version: str | None = None) -> dict[str, Any]:
    """Contenu complet d'une version (la version active par défaut)."""
    req = select(Referentiel).where(Referentiel.code == code)
    req = req.where(Referentiel.version == version) if version else req.where(Referentiel.actif.is_(True))
    ref = s.scalar(req)
    if ref is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Référentiel introuvable.")
    entete = ReferentielSortie.model_validate(ref, from_attributes=True).model_dump()
    corr = _correspondances_par_source(s, ref.id)
    if ref.nature == NATURE_AUDIT:
        return {**entete, "sections": _arbre_audit(s, ref.id, corr)}
    return {**entete, **_contenu_maturite(s, ref.id, corr)}


@router.get("/disponibles", response_model=list[ContenuDisponible])
def disponibles(admin: AdminDep) -> list[ContenuDisponible]:
    """Contenus présents dans le dossier de contenu, prêts à importer."""
    racine = reglages().dossier_contenu
    trouves: list[ContenuDisponible] = []
    if not racine.is_dir():
        return trouves
    for f in sorted(racine.rglob("_referentiel.json")):
        trouves.append(ContenuDisponible(nature="maturite", chemin=str(f.parent.relative_to(racine))))
    dossiers_maturite = {f.parent for f in racine.rglob("_referentiel.json")}
    for f in sorted(racine.rglob("*.json")):
        if f.name.startswith(("_", ".")) or any(p in dossiers_maturite for p in f.parents):
            continue
        trouves.append(ContenuDisponible(nature="audit", chemin=str(f.relative_to(racine))))
    return trouves


@router.post("/import", response_model=ResultatImportSortie)
def importer(demande: DemandeImport, admin: AdminDep, s: SessionDep) -> ResultatImportSortie:
    chemin = _chemin_sur(demande.chemin)
    fonction = importer_maturite if demande.nature == "maturite" else importer_audit
    res = fonction(s, chemin, utilisateur_id=admin.id, remplacer=demande.remplacer, simulation=demande.simulation)
    return ResultatImportSortie(**asdict(res))


@router.get("/couverture/{code}")
def couverture_pivot(code: str, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    resultat = couverture(s, code)
    if resultat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune version active de ce référentiel d'audit.")
    return resultat


# ---------------------------------------------------------------------------


def _chemin_sur(relatif: str) -> Path:
    """Chemin sous le dossier de contenu, sans possibilité d'en sortir."""
    racine = reglages().dossier_contenu.resolve()
    chemin = (racine / relatif).resolve()
    if not chemin.is_relative_to(racine):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le chemin doit rester dans le dossier de contenu.")
    if not chemin.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"« {relatif} » introuvable dans le dossier de contenu.")
    return chemin


def _correspondances_par_source(s: Session, referentiel_id: int) -> dict[str, list[dict[str, Any]]]:
    resultat: dict[str, list[dict[str, Any]]] = {}
    for c in s.scalars(select(Correspondance).where(Correspondance.referentiel_id == referentiel_id)):
        resultat.setdefault(c.source_code, []).append(
            {
                "referentiel": c.cible_referentiel,
                "code": c.cible_code,
                "seuil_applique": c.seuil_applique,
                "seuil_partiel": c.seuil_partiel,
            }
        )
    return resultat


def _arbre_audit(s: Session, referentiel_id: int, corr: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    sections = s.scalars(select(Section).where(Section.referentiel_id == referentiel_id).order_by(Section.ordre)).all()
    exigences = s.scalars(select(Exigence).where(Exigence.referentiel_id == referentiel_id).order_by(Exigence.ordre)).all()
    controles = s.scalars(select(Controle).where(Controle.referentiel_id == referentiel_id).order_by(Controle.ordre)).all()
    par_exigence: dict[int, list[dict[str, Any]]] = {}
    for c in controles:
        par_exigence.setdefault(c.exigence_id, []).append(
            {
                "code": c.code,
                "intitule": c.intitule,
                "description": c.description,
                "niveau": c.niveau,
                "methode": c.methode,
                "verification": c.verification,
                "valeur_attendue": c.valeur_attendue,
                "preuves_attendues": c.preuves_attendues,
                "recommandation": c.recommandation,
                "poids": c.poids,
                "correspondances": corr.get(c.code, []),
            }
        )
    par_section: dict[int, list[dict[str, Any]]] = {}
    for e in exigences:
        par_section.setdefault(e.section_id, []).append(
            {"code": e.code, "libelle": e.libelle, "description": e.description, "controles": par_exigence.get(e.id, [])}
        )
    return [
        {"code": sec.code, "libelle": sec.libelle, "description": sec.description, "exigences": par_section.get(sec.id, [])}
        for sec in sections
    ]


def _contenu_maturite(s: Session, referentiel_id: int, corr: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    themes = s.scalars(select(Theme).where(Theme.referentiel_id == referentiel_id).order_by(Theme.ordre)).all()
    sous_themes = s.scalars(
        select(SousTheme).where(SousTheme.referentiel_id == referentiel_id).order_by(SousTheme.ordre, SousTheme.code)
    ).all()
    questions = s.scalars(select(Question).where(Question.referentiel_id == referentiel_id).order_by(Question.ordre)).all()
    par_st: dict[int, list[dict[str, Any]]] = {}
    for q in questions:
        par_st.setdefault(q.sous_theme_id, []).append(
            {
                "ref": q.ref,
                "enonce": q.enonce,
                "aide": q.aide,
                "profondeur": q.profondeur,
                "poids": q.poids,
                "references": q.references,
                "niveaux": q.niveaux,
                "type": q.type_question,
                "duree": q.duree_estimee,
                "mode": q.mode,
                "interlocuteurs": q.interlocuteurs,
                "correspondances": corr.get(q.ref, []),
            }
        )
    st_par_theme: dict[int, list[dict[str, Any]]] = {}
    for st in sous_themes:
        st_par_theme.setdefault(st.theme_id, []).append(
            {
                "code": st.code,
                "libelle": st.libelle,
                "description": st.description,
                "poids": st.poids,
                "questions": par_st.get(st.id, []),
            }
        )
    return {
        "themes": [
            {
                "code": t.code,
                "libelle": t.libelle,
                "couleur": t.couleur,
                "poids": t.poids,
                "sous_themes": st_par_theme.get(t.id, []),
            }
            for t in themes
        ],
        "prestations": [
            {"code": p.code, "libelle": p.libelle, "referentiel_audit": p.referentiel_audit, "sections": p.sections}
            for p in s.scalars(select(Prestation).where(Prestation.referentiel_id == referentiel_id).order_by(Prestation.code))
        ],
        "reglementations": [
            {"code": r.code, "libelle": r.libelle, "nature": r.nature, "exigences": r.exigences}
            for r in s.scalars(
                select(Reglementation).where(Reglementation.referentiel_id == referentiel_id).order_by(Reglementation.ordre)
            )
        ],
        "profilage": [
            {"code": q.code, "libelle": q.libelle, "type": q.type, "choix": q.choix, "condition": q.condition}
            for q in s.scalars(
                select(QuestionProfil).where(QuestionProfil.referentiel_id == referentiel_id).order_by(QuestionProfil.ordre)
            )
        ],
    }
