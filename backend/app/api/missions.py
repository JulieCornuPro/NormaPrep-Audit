"""Clients et missions."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api import acces
from app.api.deps import SessionDep, UtilisateurDep, adresse_ip
from app.journal import journaliser
from app.models import (
    NATURE_MATURITE,
    ROLE_RESPONSABLE,
    ROLES_MISSION,
    Client,
    Diagnostic,
    MembreMission,
    Mission,
    Referentiel,
    Utilisateur,
)

router = APIRouter(prefix="/api", tags=["Missions"])


# ---- schémas ------------------------------------------------------------------


class ClientEntree(BaseModel):
    nom: str = Field(min_length=1, max_length=200)
    secteur: str = Field(default="", max_length=200)
    notes: str = ""


class ClientSortie(ClientEntree):
    id: int


class MissionEntree(BaseModel):
    client_id: int
    titre: str = Field(min_length=1, max_length=300)
    perimetre: str = ""


class MissionModification(BaseModel):
    titre: str | None = Field(default=None, min_length=1, max_length=300)
    perimetre: str | None = None
    statut: str | None = Field(default=None, pattern="^(en_cours|terminee)$")


class MembreSortie(BaseModel):
    utilisateur_id: int
    nom: str
    email: str
    role: str


class DiagnosticResume(BaseModel):
    id: int
    statut: str
    referentiel: str
    version: str
    cree_le: datetime
    finalise_le: datetime | None


class MissionSortie(BaseModel):
    id: int
    titre: str
    perimetre: str
    statut: str
    cree_le: datetime
    client: ClientSortie
    mon_role: str | None = None
    droits: list[str] = []
    membres: list[MembreSortie] = []
    diagnostics: list[DiagnosticResume] = []


class Membre(BaseModel):
    utilisateur_id: int
    role: str = Field(pattern="^(" + "|".join(ROLES_MISSION) + ")$")


class Annuaire(BaseModel):
    id: int
    nom: str
    email: str


# ---- clients ------------------------------------------------------------------


@router.get("/clients", response_model=list[ClientSortie], tags=["Clients"])
def lister_clients(u: UtilisateurDep, s: SessionDep) -> list[ClientSortie]:
    return [ClientSortie.model_validate(c, from_attributes=True) for c in s.scalars(select(Client).order_by(Client.nom))]


@router.post("/clients", response_model=ClientSortie, status_code=status.HTTP_201_CREATED, tags=["Clients"])
def creer_client(donnees: ClientEntree, u: UtilisateurDep, s: SessionDep, request: Request) -> ClientSortie:
    c = Client(nom=donnees.nom.strip(), secteur=donnees.secteur.strip(), notes=donnees.notes, cree_par=u.id)
    s.add(c)
    s.flush()
    journaliser(s, "client_cree", utilisateur_id=u.id, objet_type="client", objet_id=c.id, adresse_ip=adresse_ip(request))
    s.commit()
    return ClientSortie.model_validate(c, from_attributes=True)


@router.patch("/clients/{client_id}", response_model=ClientSortie, tags=["Clients"])
def modifier_client(client_id: int, donnees: ClientEntree, u: UtilisateurDep, s: SessionDep, request: Request) -> ClientSortie:
    c = s.get(Client, client_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    c.nom, c.secteur, c.notes = donnees.nom.strip(), donnees.secteur.strip(), donnees.notes
    journaliser(s, "client_modifie", utilisateur_id=u.id, objet_type="client", objet_id=c.id, adresse_ip=adresse_ip(request))
    s.commit()
    return ClientSortie.model_validate(c, from_attributes=True)


@router.get("/annuaire", response_model=list[Annuaire], tags=["Utilisateurs"])
def annuaire(u: UtilisateurDep, s: SessionDep) -> list[Annuaire]:
    """Comptes actifs, pour composer l'équipe d'une mission."""
    return [
        Annuaire(id=x.id, nom=x.nom, email=x.email)
        for x in s.scalars(select(Utilisateur).where(Utilisateur.actif.is_(True)).order_by(Utilisateur.nom))
    ]


# ---- missions -----------------------------------------------------------------


def _sortie(s: SessionDep, u: Utilisateur, m: Mission, detail: bool = False) -> MissionSortie:
    sortie = MissionSortie(
        id=m.id,
        titre=m.titre,
        perimetre=m.perimetre,
        statut=m.statut,
        cree_le=m.cree_le,
        client=ClientSortie.model_validate(m.client, from_attributes=True),
        mon_role=acces.role(s, u, m.id),
        droits=sorted(acces.droits(s, u, m.id)),
    )
    if detail:
        sortie.membres = [
            MembreSortie(utilisateur_id=mm.utilisateur_id, nom=mm.utilisateur.nom, email=mm.utilisateur.email, role=mm.role)
            for mm in sorted(m.membres, key=lambda x: (ROLES_MISSION.index(x.role), x.utilisateur.nom))
        ]
        sortie.diagnostics = [
            DiagnosticResume(
                id=d.id,
                statut=d.statut,
                referentiel=d.referentiel.code,
                version=d.referentiel.version,
                cree_le=d.cree_le,
                finalise_le=d.finalise_le,
            )
            for d in s.scalars(select(Diagnostic).where(Diagnostic.mission_id == m.id).order_by(Diagnostic.id))
        ]
    return sortie


@router.get("/missions", response_model=list[MissionSortie])
def lister_missions(u: UtilisateurDep, s: SessionDep) -> list[MissionSortie]:
    req = select(Mission).order_by(Mission.cree_le.desc())
    if not u.est_admin:
        req = req.join(MembreMission).where(MembreMission.utilisateur_id == u.id)
    return [_sortie(s, u, m) for m in s.scalars(req)]


@router.post("/missions", response_model=MissionSortie, status_code=status.HTTP_201_CREATED)
def creer_mission(donnees: MissionEntree, u: UtilisateurDep, s: SessionDep, request: Request) -> MissionSortie:
    if s.get(Client, donnees.client_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Client introuvable.")
    m = Mission(client_id=donnees.client_id, titre=donnees.titre.strip(), perimetre=donnees.perimetre, cree_par=u.id)
    s.add(m)
    s.flush()
    # Le créateur devient responsable de la mission.
    s.add(MembreMission(mission_id=m.id, utilisateur_id=u.id, role=ROLE_RESPONSABLE))
    journaliser(s, "mission_creee", utilisateur_id=u.id, objet_type="mission", objet_id=m.id, adresse_ip=adresse_ip(request))
    s.commit()
    s.refresh(m)
    return _sortie(s, u, m, detail=True)


@router.get("/missions/{mission_id}", response_model=MissionSortie)
def detail_mission(mission_id: int, u: UtilisateurDep, s: SessionDep) -> MissionSortie:
    return _sortie(s, u, acces.mission(s, u, mission_id), detail=True)


@router.patch("/missions/{mission_id}", response_model=MissionSortie)
def modifier_mission(
    mission_id: int, donnees: MissionModification, u: UtilisateurDep, s: SessionDep, request: Request
) -> MissionSortie:
    m = acces.mission(s, u, mission_id, acces.GESTION)
    changements = donnees.model_dump(exclude_none=True)
    for cle, valeur in changements.items():
        setattr(m, cle, valeur.strip() if cle == "titre" else valeur)
    journaliser(
        s, "mission_modifiee", utilisateur_id=u.id, objet_type="mission", objet_id=m.id,
        details=changements, adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return _sortie(s, u, m, detail=True)


@router.put("/missions/{mission_id}/membres", response_model=MissionSortie)
def definir_membre(mission_id: int, donnees: Membre, u: UtilisateurDep, s: SessionDep, request: Request) -> MissionSortie:
    m = acces.mission(s, u, mission_id, acces.GESTION)
    cible = s.get(Utilisateur, donnees.utilisateur_id)
    if cible is None or not cible.actif:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Utilisateur introuvable.")
    mm = next((x for x in m.membres if x.utilisateur_id == cible.id), None)
    if mm is not None and mm.role == ROLE_RESPONSABLE and donnees.role != ROLE_RESPONSABLE:
        _garder_un_responsable(m, cible.id)
    if mm is None:
        m.membres.append(MembreMission(utilisateur_id=cible.id, role=donnees.role))
    else:
        mm.role = donnees.role
    journaliser(
        s, "membre_defini", utilisateur_id=u.id, objet_type="mission", objet_id=m.id,
        details={"utilisateur_id": cible.id, "role": donnees.role}, adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return _sortie(s, u, m, detail=True)


@router.delete("/missions/{mission_id}/membres/{utilisateur_id}", response_model=MissionSortie)
def retirer_membre(mission_id: int, utilisateur_id: int, u: UtilisateurDep, s: SessionDep, request: Request) -> MissionSortie:
    m = acces.mission(s, u, mission_id, acces.GESTION)
    mm = next((x for x in m.membres if x.utilisateur_id == utilisateur_id), None)
    if mm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ce compte n'est pas membre de la mission.")
    if mm.role == ROLE_RESPONSABLE:
        _garder_un_responsable(m, utilisateur_id)
    m.membres.remove(mm)
    journaliser(
        s, "membre_retire", utilisateur_id=u.id, objet_type="mission", objet_id=m.id,
        details={"utilisateur_id": utilisateur_id}, adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return _sortie(s, u, m, detail=True)


def _garder_un_responsable(m: Mission, partant: int) -> None:
    if not any(x.role == ROLE_RESPONSABLE and x.utilisateur_id != partant for x in m.membres):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Une mission garde au moins un responsable.")


@router.post("/missions/{mission_id}/diagnostics", response_model=DiagnosticResume, status_code=status.HTTP_201_CREATED)
def creer_diagnostic(mission_id: int, u: UtilisateurDep, s: SessionDep, request: Request) -> DiagnosticResume:
    m = acces.mission(s, u, mission_id, acces.SAISIE)
    ref = s.scalar(select(Referentiel).where(Referentiel.nature == NATURE_MATURITE, Referentiel.actif.is_(True)).limit(1))
    if ref is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Aucun référentiel de maturité importé : un administrateur doit en importer un."
        )
    d = Diagnostic(mission_id=m.id, referentiel_id=ref.id, cree_par=u.id)
    s.add(d)
    s.flush()
    journaliser(
        s, "diagnostic_cree", utilisateur_id=u.id, objet_type="diagnostic", objet_id=d.id,
        details={"mission_id": m.id, "referentiel": f"{ref.code}@{ref.version}"}, adresse_ip=adresse_ip(request),
    )  # fmt: skip
    s.commit()
    return DiagnosticResume(
        id=d.id, statut=d.statut, referentiel=ref.code, version=ref.version, cree_le=d.cree_le, finalise_le=None
    )
