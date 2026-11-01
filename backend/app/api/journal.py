"""Consultation du journal d'audit (administrateurs)."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import AdminDep, SessionDep
from app.models import EntreeJournal

router = APIRouter(prefix="/api/journal", tags=["Journal"])


class EntreeSortie(BaseModel):
    id: int
    horodatage: datetime
    utilisateur_id: int | None
    action: str
    objet_type: str | None
    objet_id: str | None
    details: dict[str, Any] | None
    adresse_ip: str | None


@router.get("", response_model=list[EntreeSortie])
def lister(
    admin: AdminDep,
    s: SessionDep,
    action: str | None = None,
    utilisateur_id: int | None = None,
    avant_id: int | None = Query(default=None, description="Pagination : entrées d'id inférieur."),
    limite: int = Query(default=100, ge=1, le=500),
) -> list[EntreeSortie]:
    req = select(EntreeJournal).order_by(EntreeJournal.id.desc()).limit(limite)
    if action:
        req = req.where(EntreeJournal.action == action)
    if utilisateur_id is not None:
        req = req.where(EntreeJournal.utilisateur_id == utilisateur_id)
    if avant_id is not None:
        req = req.where(EntreeJournal.id < avant_id)
    return [EntreeSortie.model_validate(e, from_attributes=True) for e in s.scalars(req)]
