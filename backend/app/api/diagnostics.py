"""Diagnostic de maturité : profilage, réglementations, questionnaire,
plan d'ateliers, pré-questionnaire, résultats."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import acces
from app.api.deps import SessionDep, UtilisateurDep, adresse_ip
from app.diagnostic import ateliers, calculs, profilage
from app.diagnostic.contenu import ContenuMaturite, charger
from app.journal import journaliser
from app.models import Diagnostic, LienPreQuestionnaire, Reponse

router = APIRouter(prefix="/api/diagnostics", tags=["Diagnostic"])
public = APIRouter(prefix="/api/public", tags=["Pré-questionnaire (public)"])

MODES = ("atelier", "pre_questionnaire", "revue_documentaire", "import")


# ---- schémas ------------------------------------------------------------------


class Profil(BaseModel):
    reponses: dict[str, list[str]]


class Decision(BaseModel):
    decision: str
    justification: str = ""


class Arbitrage(BaseModel):
    decisions: dict[str, Decision] = {}
    ajout: str | None = None
    justification_ajout: str = ""


class ReponseEntree(BaseModel):
    niveau: int | None = Field(default=None, ge=0, le=5)
    non_applicable: bool = False
    commentaire: str = Field(default="", max_length=5000)


class ModeEntree(BaseModel):
    mode: str = Field(pattern="^(" + "|".join(MODES) + ")$")


class Parametres(BaseModel):
    budget_atelier_minutes: int = Field(ge=30, le=480)
    ouverture_minutes: int = Field(ge=0, le=60)


class LienEntree(BaseModel):
    destinataire: str = Field(default="", max_length=200)
    jours: int = Field(default=14, ge=1, le=60)


class PropositionClient(BaseModel):
    niveau: int | None = Field(default=None, ge=0, le=5)
    commentaire: str = Field(default="", max_length=5000)


# ---- outils -------------------------------------------------------------------


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _reponses(s: Session, diag: Diagnostic) -> dict[str, Reponse]:
    return {r.question_ref: r for r in s.scalars(select(Reponse).where(Reponse.diagnostic_id == diag.id))}


def _contexte(s: Session, diag: Diagnostic) -> tuple[ContenuMaturite, dict[str, dict[str, Any]]]:
    contenu = charger(s, diag.referentiel_id)
    return contenu, profilage.exigences(s, diag, contenu)


def _reponse_sortie(r: Reponse | None) -> dict[str, Any]:
    if r is None:
        return {"niveau": None, "non_applicable": False, "commentaire": "", "saisi_le": None, "proposition": None}
    proposition = None
    if r.propose_le is not None:
        proposition = {"niveau": r.niveau_propose, "commentaire": r.commentaire_client, "le": r.propose_le}
    return {
        "niveau": r.niveau,
        "non_applicable": r.non_applicable,
        "commentaire": r.commentaire,
        "saisi_le": r.saisi_le,
        "proposition": proposition,
    }


# ---- synthèse -----------------------------------------------------------------


@router.get("/{diagnostic_id}")
def synthese(diagnostic_id: int, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id)
    contenu, exig = _contexte(s, diag)
    retenues = calculs.questions_retenues(contenu, exig)
    lignes = profilage.lignes(s, diag.id)
    return {
        "id": diag.id,
        "mission_id": diag.mission_id,
        "mission_titre": diag.mission.titre,
        "client": diag.mission.client.nom,
        "statut": diag.statut,
        "referentiel": {"code": diag.referentiel.code, "version": diag.referentiel.version, "libelle": diag.referentiel.libelle},
        "droits": sorted(acces.droits(s, u, diag.mission_id)),
        "budget_atelier_minutes": diag.budget_atelier_minutes,
        "ouverture_minutes": diag.ouverture_minutes,
        "profilage_incomplet": profilage.questions_sans_reponse(diag.profil, contenu),
        "reglementations_en_attente": [x.reglementation_code for x in lignes if x.decision == "en_attente"],
        "progression": calculs.progression(retenues, _reponses(s, diag)),
        "cree_le": diag.cree_le,
        "finalise_le": diag.finalise_le,
    }


# ---- profilage et réglementations ---------------------------------------------


def _vue_profilage(s: Session, diag: Diagnostic, contenu: ContenuMaturite) -> dict[str, Any]:
    visibles = set(profilage.questions_visibles(diag.profil, contenu))
    retenues = {x.reglementation_code for x in profilage.lignes(s, diag.id)}
    return {
        "questions": [{**q, "visible": q["code"] in visibles} for q in contenu.profil],
        "reponses": diag.profil,
        "sans_reponse": profilage.questions_sans_reponse(diag.profil, contenu),
        "reglementations": profilage.vue_reglementations(s, diag, contenu),
        "ajoutables": [
            {"code": r["code"], "libelle": r["libelle"]}
            for r in sorted(contenu.reglementations.values(), key=lambda r: r["ordre"])
            if r["code"] not in retenues
        ],
    }


@router.get("/{diagnostic_id}/profilage")
def lire_profilage(diagnostic_id: int, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id)
    return _vue_profilage(s, diag, charger(s, diag.referentiel_id))


@router.put("/{diagnostic_id}/profilage")
def enregistrer_profilage(
    diagnostic_id: int, donnees: Profil, u: UtilisateurDep, s: SessionDep, request: Request
) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id, acces.SAISIE)
    contenu = charger(s, diag.referentiel_id)
    profilage.enregistrer_profil(s, diag, donnees.reponses, contenu)
    journaliser(
        s, "profilage_enregistre", utilisateur_id=u.id, objet_type="diagnostic", objet_id=diag.id, adresse_ip=adresse_ip(request)
    )
    s.commit()
    return _vue_profilage(s, diag, contenu)


@router.put("/{diagnostic_id}/reglementations")
def arbitrer(diagnostic_id: int, donnees: Arbitrage, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id, acces.SAISIE)
    contenu = charger(s, diag.referentiel_id)
    try:
        profilage.arbitrer(
            s,
            diag,
            {k: v.model_dump() for k, v in donnees.decisions.items()},
            contenu,
            donnees.ajout,
            donnees.justification_ajout,
        )
    except profilage.ErreurArbitrage as e:
        s.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, e.erreurs) from e
    journaliser(
        s, "reglementations_arbitrees", utilisateur_id=u.id, objet_type="diagnostic", objet_id=diag.id,
        details=donnees.model_dump(), adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return _vue_profilage(s, diag, contenu)


# ---- questionnaire --------------------------------------------------------------


@router.get("/{diagnostic_id}/questionnaire")
def questionnaire(diagnostic_id: int, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id)
    contenu, exig = _contexte(s, diag)
    retenues = {q.ref for q in calculs.questions_retenues(contenu, exig)}
    reponses = _reponses(s, diag)
    themes = []
    for th in contenu.themes:
        sts = []
        for st in th.sous_themes:
            qs = [
                {
                    "ref": q.ref,
                    "enonce": q.enonce,
                    "aide": q.aide,
                    "profondeur": q.profondeur,
                    "niveaux": q.niveaux,
                    "references": q.references,
                    "type": q.type,
                    "duree": ateliers.duree(q),
                    "mode": ateliers.mode_effectif(q, diag.modes),
                    "mode_contenu": q.mode,
                    "interlocuteurs": q.interlocuteurs,
                    "reponse": _reponse_sortie(reponses.get(q.ref)),
                }
                for q in st.questions
                if q.ref in retenues
            ]
            if qs:
                sts.append({"code": st.code, "libelle": st.libelle, **exig[st.code], "questions": qs})
        if sts:
            themes.append({"code": th.code, "libelle": th.libelle, "couleur": th.couleur, "sous_themes": sts})
    return {"themes": themes, "progression": calculs.progression(calculs.questions_retenues(contenu, exig), reponses)}


@router.put("/{diagnostic_id}/reponses/{ref}")
def repondre(diagnostic_id: int, ref: str, donnees: ReponseEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id, acces.SAISIE)
    contenu, exig = _contexte(s, diag)
    if ref not in {q.ref for q in calculs.questions_retenues(contenu, exig)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question absente de ce diagnostic.")
    r = _reponses(s, diag).get(ref) or Reponse(diagnostic_id=diag.id, question_ref=ref)
    s.add(r)
    r.non_applicable = donnees.non_applicable
    r.niveau = None if donnees.non_applicable else donnees.niveau
    r.commentaire = donnees.commentaire
    r.saisi_par = u.id
    r.saisi_le = _maintenant()
    s.commit()
    return _reponse_sortie(r)


@router.put("/{diagnostic_id}/questions/{ref}/mode")
def changer_mode(diagnostic_id: int, ref: str, donnees: ModeEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    """Déplace une question vers le pré-questionnaire, un atelier, etc."""
    diag = acces.diagnostic(s, u, diagnostic_id, acces.SAISIE)
    contenu = charger(s, diag.referentiel_id)
    if ref not in contenu.questions:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question inconnue.")
    modes = dict(diag.modes)
    if donnees.mode == contenu.questions[ref].mode:
        modes.pop(ref, None)
    else:
        modes[ref] = donnees.mode
    diag.modes = modes
    s.commit()
    return {"ref": ref, "mode": donnees.mode}


# ---- ateliers -------------------------------------------------------------------


@router.get("/{diagnostic_id}/ateliers")
def plan_ateliers(diagnostic_id: int, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id)
    contenu, exig = _contexte(s, diag)
    return ateliers.plan(
        contenu, calculs.questions_retenues(contenu, exig), diag.modes, diag.budget_atelier_minutes, diag.ouverture_minutes
    )


@router.put("/{diagnostic_id}/parametres")
def parametres(diagnostic_id: int, donnees: Parametres, u: UtilisateurDep, s: SessionDep) -> dict[str, int]:
    diag = acces.diagnostic(s, u, diagnostic_id, acces.SAISIE)
    if donnees.ouverture_minutes >= donnees.budget_atelier_minutes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le temps d'ouverture doit être inférieur au budget de l'atelier.")
    diag.budget_atelier_minutes = donnees.budget_atelier_minutes
    diag.ouverture_minutes = donnees.ouverture_minutes
    s.commit()
    return donnees.model_dump()


# ---- résultats et finalisation ------------------------------------------------


@router.get("/{diagnostic_id}/resultats")
def resultats(diagnostic_id: int, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id)
    if diag.statut == "finalise" and diag.resultats_figes is not None:
        return {**diag.resultats_figes, "fige": True}
    contenu, exig = _contexte(s, diag)
    return {**calculs.resultats(contenu, exig, _reponses(s, diag)), "fige": False}


@router.post("/{diagnostic_id}/finaliser")
def finaliser(diagnostic_id: int, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id, acces.GESTION)
    if diag.statut == "finalise":
        raise HTTPException(status.HTTP_409_CONFLICT, "Diagnostic déjà finalisé.")
    contenu, exig = _contexte(s, diag)
    bloquants = []
    if profilage.questions_sans_reponse(diag.profil, contenu):
        bloquants.append("Le profilage n'est pas terminé.")
    if any(x.decision == "en_attente" for x in profilage.lignes(s, diag.id)):
        bloquants.append("Des réglementations « à vérifier » ne sont pas tranchées.")
    res = calculs.resultats(contenu, exig, _reponses(s, diag))
    if res["progression"]["restantes"]:
        bloquants.append(f"{res['progression']['restantes']} question(s) sans réponse (répondez ou marquez N/A).")
    if bloquants:
        raise HTTPException(status.HTTP_409_CONFLICT, bloquants)
    diag.statut = "finalise"
    diag.finalise_le = _maintenant()
    diag.resultats_figes = res
    journaliser(
        s, "diagnostic_finalise", utilisateur_id=u.id, objet_type="diagnostic", objet_id=diag.id, adresse_ip=adresse_ip(request)
    )
    s.commit()
    return {**res, "fige": True}


@router.post("/{diagnostic_id}/rouvrir")
def rouvrir(diagnostic_id: int, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, str]:
    diag = acces.diagnostic(s, u, diagnostic_id, acces.GESTION)
    diag.statut = "en_cours"
    diag.finalise_le = None
    diag.resultats_figes = None
    journaliser(
        s, "diagnostic_rouvert", utilisateur_id=u.id, objet_type="diagnostic", objet_id=diag.id, adresse_ip=adresse_ip(request)
    )
    s.commit()
    return {"statut": diag.statut}


# ---- pré-questionnaire : liens ------------------------------------------------


def _empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


def _lien_sortie(lien: LienPreQuestionnaire) -> dict[str, Any]:
    return {
        "id": lien.id,
        "destinataire": lien.destinataire,
        "expire_le": lien.expire_le,
        "revoque": lien.revoque,
        "actif": not lien.revoque and lien.expire_le > _maintenant(),
        "cree_le": lien.cree_le,
        "derniere_utilisation": lien.derniere_utilisation,
    }


@router.get("/{diagnostic_id}/liens")
def lister_liens(diagnostic_id: int, u: UtilisateurDep, s: SessionDep) -> list[dict[str, Any]]:
    diag = acces.diagnostic(s, u, diagnostic_id)
    req = (
        select(LienPreQuestionnaire).where(LienPreQuestionnaire.diagnostic_id == diag.id).order_by(LienPreQuestionnaire.id.desc())
    )
    return [_lien_sortie(x) for x in s.scalars(req)]


@router.post("/{diagnostic_id}/liens", status_code=status.HTTP_201_CREATED)
def creer_lien(diagnostic_id: int, donnees: LienEntree, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    """Le jeton n'est renvoyé qu'ici : seule son empreinte est conservée."""
    diag = acces.diagnostic(s, u, diagnostic_id, acces.SAISIE)
    jeton = secrets.token_urlsafe(32)
    lien = LienPreQuestionnaire(
        diagnostic_id=diag.id,
        empreinte_jeton=_empreinte(jeton),
        destinataire=donnees.destinataire.strip(),
        expire_le=_maintenant() + timedelta(days=donnees.jours),
        cree_par=u.id,
    )
    s.add(lien)
    s.flush()
    journaliser(
        s, "lien_pre_questionnaire_cree", utilisateur_id=u.id, objet_type="diagnostic", objet_id=diag.id,
        details={"lien_id": lien.id, "jours": donnees.jours, "destinataire": lien.destinataire}, adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return {**_lien_sortie(lien), "jeton": jeton, "chemin": f"/pre-questionnaire/{jeton}"}


@router.delete("/{diagnostic_id}/liens/{lien_id}")
def revoquer_lien(diagnostic_id: int, lien_id: int, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    diag = acces.diagnostic(s, u, diagnostic_id, acces.SAISIE)
    lien = s.get(LienPreQuestionnaire, lien_id)
    if lien is None or lien.diagnostic_id != diag.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lien introuvable.")
    lien.revoque = True
    journaliser(
        s, "lien_pre_questionnaire_revoque", utilisateur_id=u.id, objet_type="diagnostic", objet_id=diag.id,
        details={"lien_id": lien.id}, adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return _lien_sortie(lien)


# ---- pré-questionnaire : accès client (public, par jeton) -----------------------


def _lien_valide(s: Session, jeton: str) -> tuple[LienPreQuestionnaire, Diagnostic]:
    refus = HTTPException(status.HTTP_404_NOT_FOUND, "Ce lien n'est pas valide ou a expiré. Contactez votre consultant.")
    lien = s.scalar(select(LienPreQuestionnaire).where(LienPreQuestionnaire.empreinte_jeton == _empreinte(jeton)))
    if lien is None or lien.revoque or lien.expire_le <= _maintenant():
        raise refus
    diag = s.get(Diagnostic, lien.diagnostic_id)
    if diag is None or diag.statut == "finalise":
        raise refus
    return lien, diag


def _questions_pre(s: Session, diag: Diagnostic) -> list[Any]:
    contenu, exig = _contexte(s, diag)
    return [
        (q, contenu.sous_themes[q.sous_theme].libelle)
        for q in calculs.questions_retenues(contenu, exig)
        if ateliers.mode_effectif(q, diag.modes) == "pre_questionnaire"
    ]


@public.get("/pre-questionnaire/{jeton}")
def pre_questionnaire(jeton: str, s: SessionDep) -> dict[str, Any]:
    lien, diag = _lien_valide(s, jeton)
    reponses = _reponses(s, diag)
    return {
        "mission": diag.mission.titre,
        "client": diag.mission.client.nom,
        "expire_le": lien.expire_le,
        "questions": [
            {
                "ref": q.ref,
                "sous_theme": libelle,
                "enonce": q.enonce,
                "aide": q.aide,
                "niveaux": q.niveaux,
                "niveau": reponses[q.ref].niveau_propose if q.ref in reponses else None,
                "commentaire": reponses[q.ref].commentaire_client if q.ref in reponses else "",
            }
            for q, libelle in _questions_pre(s, diag)
        ],
    }


@public.put("/pre-questionnaire/{jeton}/reponses/{ref}")
def proposer(jeton: str, ref: str, donnees: PropositionClient, s: SessionDep, request: Request) -> dict[str, Any]:
    lien, diag = _lien_valide(s, jeton)
    if ref not in {q.ref for q, _ in _questions_pre(s, diag)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question absente du pré-questionnaire.")
    r = _reponses(s, diag).get(ref) or Reponse(diagnostic_id=diag.id, question_ref=ref)
    s.add(r)
    r.niveau_propose = donnees.niveau
    r.commentaire_client = donnees.commentaire
    r.propose_le = _maintenant()
    lien.derniere_utilisation = r.propose_le
    journaliser(
        s, "pre_questionnaire_reponse", objet_type="diagnostic", objet_id=diag.id,
        details={"lien_id": lien.id, "question": ref}, adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return {"ref": ref, "niveau": r.niveau_propose, "commentaire": r.commentaire_client}
