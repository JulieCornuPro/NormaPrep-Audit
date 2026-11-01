"""Connexion en deux étapes : mot de passe, puis code TOTP.

Au premier passage, l'utilisateur n'a pas encore de TOTP : la première étape
renvoie le secret et l'URI à scanner dans une application d'authentification,
et la seconde étape active le TOTP en vérifiant un premier code.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.deps import SessionDep, UtilisateurDep, adresse_ip
from app.config import reglages
from app.journal import journaliser
from app.models import Utilisateur
from app.securite import (
    HACHE_FACTICE,
    USAGE_ACCES,
    USAGE_TOTP,
    chiffrer,
    dechiffrer,
    doit_rehacher,
    emettre_jeton,
    hacher_mot_de_passe,
    lire_jeton,
    nouveau_secret_totp,
    uri_totp,
    verifier_mot_de_passe,
    verifier_totp,
)

router = APIRouter(prefix="/api/auth", tags=["Authentification"])

MESSAGE_REFUS = "Identifiants invalides, ou compte temporairement bloqué."


class Connexion(BaseModel):
    email: str
    mot_de_passe: str


class EtapeTotp(BaseModel):
    etape: Literal["totp", "enrolement"]
    jeton: str
    # Présents à l'enrôlement seulement.
    secret: str | None = None
    uri_totp: str | None = None


class CodeTotp(BaseModel):
    jeton: str
    code: str


class JetonAcces(BaseModel):
    jeton_acces: str
    expire_dans_minutes: int


class Moi(BaseModel):
    id: int
    email: str
    nom: str
    est_admin: bool


class ChangementMotDePasse(BaseModel):
    actuel: str
    nouveau: str


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _bloque(u: Utilisateur) -> bool:
    return u.bloque_jusqu_a is not None and u.bloque_jusqu_a > _maintenant()


def _echec(s: SessionDep, u: Utilisateur, ip: str | None, etape: str) -> None:
    """Compte un échec ; bloque le compte au-delà du seuil. Validé tout de suite."""
    r = reglages()
    u.echecs_connexion += 1
    journaliser(s, "connexion_echouee", utilisateur_id=u.id, details={"etape": etape}, adresse_ip=ip)
    if u.echecs_connexion >= r.echecs_avant_blocage:
        u.bloque_jusqu_a = _maintenant() + timedelta(minutes=r.duree_blocage_minutes)
        u.echecs_connexion = 0
        journaliser(s, "compte_bloque", utilisateur_id=u.id, details={"minutes": r.duree_blocage_minutes}, adresse_ip=ip)
    s.commit()


@router.post("/connexion", response_model=EtapeTotp)
def connexion(donnees: Connexion, s: SessionDep, request: Request) -> EtapeTotp:
    ip = adresse_ip(request)
    u = s.scalar(select(Utilisateur).where(func.lower(Utilisateur.email) == donnees.email.strip().lower()))
    if u is None:
        verifier_mot_de_passe(HACHE_FACTICE, donnees.mot_de_passe)  # durée de réponse constante
        journaliser(s, "connexion_echouee", details={"etape": "mot_de_passe", "email_inconnu": True}, adresse_ip=ip)
        s.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MESSAGE_REFUS)
    if not u.actif or _bloque(u):
        journaliser(
            s, "connexion_refusee", utilisateur_id=u.id, details={"motif": "inactif" if not u.actif else "bloque"}, adresse_ip=ip
        )
        s.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MESSAGE_REFUS)
    if not verifier_mot_de_passe(u.mot_de_passe_hash, donnees.mot_de_passe):
        _echec(s, u, ip, "mot_de_passe")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, MESSAGE_REFUS)

    if doit_rehacher(u.mot_de_passe_hash):
        u.mot_de_passe_hash = hacher_mot_de_passe(donnees.mot_de_passe)

    jeton = emettre_jeton(u.id, USAGE_TOTP, u.version_jeton, reglages().duree_jeton_intermediaire_minutes)
    if u.totp_actif:
        s.commit()
        return EtapeTotp(etape="totp", jeton=jeton)

    # Enrôlement : le secret est conservé jusqu'à la première vérification réussie.
    if u.totp_secret_chiffre is None:
        u.totp_secret_chiffre = chiffrer(nouveau_secret_totp())
    s.commit()
    secret = dechiffrer(u.totp_secret_chiffre)
    return EtapeTotp(etape="enrolement", jeton=jeton, secret=secret, uri_totp=uri_totp(secret, u.email))


@router.post("/totp", response_model=JetonAcces)
def totp(donnees: CodeTotp, s: SessionDep, request: Request) -> JetonAcces:
    ip = adresse_ip(request)
    refus = HTTPException(status.HTTP_401_UNAUTHORIZED, MESSAGE_REFUS)
    charge = lire_jeton(donnees.jeton, USAGE_TOTP)
    if charge is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session de connexion expirée : recommencez.")
    u = s.get(Utilisateur, int(charge["sub"]))
    if u is None or not u.actif or u.version_jeton != charge["ver"] or u.totp_secret_chiffre is None or _bloque(u):
        raise refus

    pas = verifier_totp(dechiffrer(u.totp_secret_chiffre), donnees.code, u.totp_dernier_pas)
    if pas is None:
        _echec(s, u, ip, "totp")
        raise refus

    u.totp_dernier_pas = pas
    if not u.totp_actif:
        u.totp_actif = True
        journaliser(s, "totp_active", utilisateur_id=u.id, adresse_ip=ip)
    u.echecs_connexion = 0
    u.derniere_connexion = _maintenant()
    journaliser(s, "connexion_reussie", utilisateur_id=u.id, adresse_ip=ip)
    s.commit()

    minutes = reglages().duree_jeton_acces_minutes
    return JetonAcces(jeton_acces=emettre_jeton(u.id, USAGE_ACCES, u.version_jeton, minutes), expire_dans_minutes=minutes)


@router.get("/moi", response_model=Moi)
def moi(u: UtilisateurDep) -> Moi:
    return Moi(id=u.id, email=u.email, nom=u.nom, est_admin=u.est_admin)


@router.post("/mot-de-passe", status_code=status.HTTP_204_NO_CONTENT)
def changer_mot_de_passe(donnees: ChangementMotDePasse, u: UtilisateurDep, s: SessionDep, request: Request) -> None:
    if not verifier_mot_de_passe(u.mot_de_passe_hash, donnees.actuel):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mot de passe actuel incorrect.")
    verifier_robustesse(donnees.nouveau)
    u.mot_de_passe_hash = hacher_mot_de_passe(donnees.nouveau)
    u.version_jeton += 1  # déconnecte les autres sessions
    journaliser(
        s, "mot_de_passe_modifie", utilisateur_id=u.id, objet_type="utilisateur", objet_id=u.id, adresse_ip=adresse_ip(request)
    )
    s.commit()


def verifier_robustesse(mot_de_passe: str) -> None:
    minimum = reglages().longueur_min_mot_de_passe
    if len(mot_de_passe) < minimum:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Le mot de passe doit contenir au moins {minimum} caractères.")
