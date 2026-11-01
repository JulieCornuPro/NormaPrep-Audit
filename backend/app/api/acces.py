"""Droits sur les missions.

| Rôle | Lire | Saisir (profilage, réponses) | Gérer (membres, finaliser) |
|---|---|---|---|
| administrateur | oui | oui | oui |
| responsable | oui | oui | oui |
| consultant | oui | oui | non |
| relecteur | oui | non | non |

Une mission inaccessible répond 404, comme une mission inexistante : on ne
révèle pas son existence.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ROLE_CONSULTANT, ROLE_RESPONSABLE, Diagnostic, MembreMission, Mission, Utilisateur

LECTURE = "lecture"
SAISIE = "saisie"
GESTION = "gestion"

_DROITS = {
    "admin": {LECTURE, SAISIE, GESTION},
    ROLE_RESPONSABLE: {LECTURE, SAISIE, GESTION},
    ROLE_CONSULTANT: {LECTURE, SAISIE},
    "relecteur": {LECTURE},
}


def role(s: Session, u: Utilisateur, mission_id: int) -> str | None:
    if u.est_admin:
        return "admin"
    return s.scalar(
        select(MembreMission.role).where(MembreMission.mission_id == mission_id, MembreMission.utilisateur_id == u.id)
    )


def droits(s: Session, u: Utilisateur, mission_id: int) -> set[str]:
    r = role(s, u, mission_id)
    return _DROITS.get(r, set()) if r else set()


def mission(s: Session, u: Utilisateur, mission_id: int, droit: str = LECTURE) -> Mission:
    m = s.get(Mission, mission_id)
    d = droits(s, u, mission_id) if m else set()
    if m is None or LECTURE not in d:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission introuvable.")
    if droit not in d:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Votre rôle sur cette mission ne permet pas cette action.")
    return m


def diagnostic(s: Session, u: Utilisateur, diagnostic_id: int, droit: str = LECTURE) -> Diagnostic:
    d = s.get(Diagnostic, diagnostic_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Diagnostic introuvable.")
    mission(s, u, d.mission_id, droit)
    if droit == SAISIE and d.statut == "finalise":
        raise HTTPException(status.HTTP_409_CONFLICT, "Diagnostic finalisé : rouvrez-le pour le modifier.")
    return d
