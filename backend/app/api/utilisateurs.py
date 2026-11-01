"""Gestion des comptes (administrateurs)."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app.api.auth import verifier_robustesse
from app.api.deps import AdminDep, SessionDep, adresse_ip
from app.journal import journaliser
from app.models import Utilisateur
from app.securite import hacher_mot_de_passe

router = APIRouter(prefix="/api/utilisateurs", tags=["Utilisateurs"])


class UtilisateurSortie(BaseModel):
    id: int
    email: str
    nom: str
    est_admin: bool
    actif: bool
    totp_actif: bool
    bloque_jusqu_a: datetime | None
    cree_le: datetime
    derniere_connexion: datetime | None


class CreationUtilisateur(BaseModel):
    email: EmailStr
    nom: str = Field(min_length=1, max_length=200)
    mot_de_passe: str
    est_admin: bool = False


class ModificationUtilisateur(BaseModel):
    nom: str | None = Field(default=None, min_length=1, max_length=200)
    est_admin: bool | None = None
    actif: bool | None = None


class NouveauMotDePasse(BaseModel):
    nouveau: str


def _sortie(u: Utilisateur) -> UtilisateurSortie:
    return UtilisateurSortie.model_validate(u, from_attributes=True)


def _trouver(s: SessionDep, utilisateur_id: int) -> Utilisateur:
    u = s.get(Utilisateur, utilisateur_id)
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    return u


@router.get("", response_model=list[UtilisateurSortie])
def lister(admin: AdminDep, s: SessionDep) -> list[UtilisateurSortie]:
    return [_sortie(u) for u in s.scalars(select(Utilisateur).order_by(Utilisateur.nom))]


@router.post("", response_model=UtilisateurSortie, status_code=status.HTTP_201_CREATED)
def creer(donnees: CreationUtilisateur, admin: AdminDep, s: SessionDep, request: Request) -> UtilisateurSortie:
    email = donnees.email.strip().lower()
    if s.scalar(select(Utilisateur.id).where(func.lower(Utilisateur.email) == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Un compte existe déjà avec cet email.")
    verifier_robustesse(donnees.mot_de_passe)
    u = Utilisateur(
        email=email,
        nom=donnees.nom.strip(),
        mot_de_passe_hash=hacher_mot_de_passe(donnees.mot_de_passe),
        est_admin=donnees.est_admin,
    )
    s.add(u)
    s.flush()
    journaliser(
        s,
        "utilisateur_cree",
        utilisateur_id=admin.id,
        objet_type="utilisateur",
        objet_id=u.id,
        details={"email": email, "est_admin": donnees.est_admin},
        adresse_ip=adresse_ip(request),
    )
    s.commit()
    return _sortie(u)


@router.patch("/{utilisateur_id}", response_model=UtilisateurSortie)
def modifier(
    utilisateur_id: int, donnees: ModificationUtilisateur, admin: AdminDep, s: SessionDep, request: Request
) -> UtilisateurSortie:
    u = _trouver(s, utilisateur_id)
    if u.id == admin.id and (donnees.actif is False or donnees.est_admin is False):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Vous ne pouvez pas retirer vos propres droits ni désactiver votre compte."
        )
    changements = donnees.model_dump(exclude_none=True)
    if donnees.nom is not None:
        u.nom = donnees.nom.strip()
    if donnees.est_admin is not None and donnees.est_admin != u.est_admin:
        u.est_admin = donnees.est_admin
        u.version_jeton += 1
    if donnees.actif is not None and donnees.actif != u.actif:
        u.actif = donnees.actif
        u.version_jeton += 1
    journaliser(
        s,
        "utilisateur_modifie",
        utilisateur_id=admin.id,
        objet_type="utilisateur",
        objet_id=u.id,
        details=changements,
        adresse_ip=adresse_ip(request),
    )
    s.commit()
    return _sortie(u)


@router.post("/{utilisateur_id}/reinitialiser-totp", response_model=UtilisateurSortie)
def reinitialiser_totp(utilisateur_id: int, admin: AdminDep, s: SessionDep, request: Request) -> UtilisateurSortie:
    """L'utilisateur refera l'enrôlement à sa prochaine connexion."""
    u = _trouver(s, utilisateur_id)
    u.totp_secret_chiffre = None
    u.totp_actif = False
    u.totp_dernier_pas = None
    u.version_jeton += 1
    journaliser(
        s, "totp_reinitialise", utilisateur_id=admin.id, objet_type="utilisateur", objet_id=u.id, adresse_ip=adresse_ip(request)
    )
    s.commit()
    return _sortie(u)


@router.post("/{utilisateur_id}/debloquer", response_model=UtilisateurSortie)
def debloquer(utilisateur_id: int, admin: AdminDep, s: SessionDep, request: Request) -> UtilisateurSortie:
    u = _trouver(s, utilisateur_id)
    u.bloque_jusqu_a = None
    u.echecs_connexion = 0
    journaliser(
        s, "compte_debloque", utilisateur_id=admin.id, objet_type="utilisateur", objet_id=u.id, adresse_ip=adresse_ip(request)
    )
    s.commit()
    return _sortie(u)


@router.post("/{utilisateur_id}/mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
def definir_mot_de_passe(
    utilisateur_id: int, donnees: NouveauMotDePasse, admin: AdminDep, s: SessionDep, request: Request
) -> None:
    u = _trouver(s, utilisateur_id)
    verifier_robustesse(donnees.nouveau)
    u.mot_de_passe_hash = hacher_mot_de_passe(donnees.nouveau)
    u.version_jeton += 1
    journaliser(
        s,
        "mot_de_passe_reinitialise",
        utilisateur_id=admin.id,
        objet_type="utilisateur",
        objet_id=u.id,
        adresse_ip=adresse_ip(request),
    )
    s.commit()
