"""Dépendances communes : session, utilisateur connecté, droits."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import session
from app.models import Utilisateur
from app.securite import USAGE_ACCES, lire_jeton

SessionDep = Annotated[Session, Depends(session)]

_bearer = HTTPBearer(auto_error=False)


def utilisateur_connecte(
    s: SessionDep,
    identifiants: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Utilisateur:
    refus = HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.", headers={"WWW-Authenticate": "Bearer"})
    if identifiants is None:
        raise refus
    charge = lire_jeton(identifiants.credentials, USAGE_ACCES)
    if charge is None:
        raise refus
    u = s.get(Utilisateur, int(charge["sub"]))
    if u is None or not u.actif or not u.totp_actif or u.version_jeton != charge["ver"]:
        raise refus
    return u


UtilisateurDep = Annotated[Utilisateur, Depends(utilisateur_connecte)]


def administrateur(u: UtilisateurDep) -> Utilisateur:
    if not u.est_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")
    return u


AdminDep = Annotated[Utilisateur, Depends(administrateur)]


def adresse_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
