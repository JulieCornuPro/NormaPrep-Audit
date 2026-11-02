"""Analyse de risques EBIOS RM — atelier 1 : cadrage, valeurs métier, biens
supports, événements redoutés, socle de sécurité."""

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api import acces
from app.api.deps import SessionDep, UtilisateurDep, adresse_ip
from app.contenu import arbre
from app.ebios import socle
from app.journal import journaliser
from app.models import (
    ETATS_SOCLE,
    NATURE_AUDIT,
    AnalyseRisques,
    BienSupport,
    Diagnostic,
    EtatSocle,
    EvenementRedoute,
    LienValeurBien,
    Referentiel,
    SocleReferentiel,
    ValeurMetier,
)

router = APIRouter(prefix="/api", tags=["Analyse de risques EBIOS RM"])

IMPACTS = ("missions", "humains", "materiels", "gouvernance", "financiers", "juridiques", "image", "environnementaux")


# ---- schémas ------------------------------------------------------------------


class Creation(BaseModel):
    titre: str = Field(min_length=1, max_length=300)
    diagnostic_id: int | None = None


class Niveau(BaseModel):
    niveau: int = Field(ge=1, le=9)
    libelle: str = Field(min_length=1, max_length=100)
    description: str = ""


class Cadrage(BaseModel):
    titre: str | None = Field(default=None, min_length=1, max_length=300)
    objet: str | None = None
    perimetre: str | None = None
    participants: str | None = None
    cycle_strategique_mois: int | None = Field(default=None, ge=1, le=120)
    cycle_operationnel_mois: int | None = Field(default=None, ge=1, le=120)
    echelle_gravite: list[Niveau] | None = None
    diagnostic_id: int | None = None

    @field_validator("echelle_gravite")
    @classmethod
    def echelle_continue(cls, v: list[Niveau] | None) -> list[Niveau] | None:
        if v is not None and [n.niveau for n in v] != list(range(1, len(v) + 1)):
            raise ValueError("L'échelle de gravité doit être numérotée 1, 2, 3… sans trou.")
        return v


class ValeurEntree(BaseModel):
    nom: str = Field(min_length=1, max_length=300)
    nature: Literal["processus", "information"] = "processus"
    description: str = ""
    responsable: str = Field(default="", max_length=200)


class BienEntree(BaseModel):
    nom: str = Field(min_length=1, max_length=300)
    description: str = ""
    responsable: str = Field(default="", max_length=200)
    valeurs_metier: list[int] = []


class EvenementEntree(BaseModel):
    valeur_metier_id: int
    description: str = Field(min_length=1)
    impacts: list[str] = []
    gravite: int = Field(ge=1, le=9)

    @field_validator("impacts")
    @classmethod
    def impacts_connus(cls, v: list[str]) -> list[str]:
        inconnus = [i for i in v if i not in IMPACTS]
        if inconnus:
            raise ValueError(f"Impacts inconnus : {', '.join(inconnus)}.")
        return v


class AjoutSocle(BaseModel):
    referentiel_id: int
    profil: str | None = None
    motif: str = ""


class EtatEntree(BaseModel):
    etat: str
    ecart: str = Field(default="", max_length=5000)
    justification: str = Field(default="", max_length=5000)

    @field_validator("etat")
    @classmethod
    def etat_connu(cls, v: str) -> str:
        if v not in ETATS_SOCLE:
            raise ValueError(f"État inconnu (admis : {', '.join(ETATS_SOCLE)}).")
        return v


# ---- outils -------------------------------------------------------------------


def _verifier_diagnostic(s: Session, analyse_mission: int, diagnostic_id: int | None) -> None:
    if diagnostic_id is None:
        return
    d = s.get(Diagnostic, diagnostic_id)
    if d is None or d.mission_id != analyse_mission:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Le diagnostic lié doit appartenir à la même mission.")


def _valeur(s: Session, a: AnalyseRisques, vid: int) -> ValeurMetier:
    v = s.get(ValeurMetier, vid)
    if v is None or v.analyse_id != a.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Valeur métier introuvable.")
    return v


def _sortie_valeur(v: ValeurMetier) -> dict[str, Any]:
    return {"id": v.id, "nom": v.nom, "nature": v.nature, "description": v.description, "responsable": v.responsable}


def _sortie_bien(s: Session, b: BienSupport) -> dict[str, Any]:
    liens = s.scalars(select(LienValeurBien.valeur_metier_id).where(LienValeurBien.bien_support_id == b.id)).all()
    return {"id": b.id, "nom": b.nom, "description": b.description, "responsable": b.responsable, "valeurs_metier": list(liens)}


def _sortie_evenement(e: EvenementRedoute) -> dict[str, Any]:
    return {
        "id": e.id,
        "valeur_metier_id": e.valeur_metier_id,
        "description": e.description,
        "impacts": e.impacts,
        "gravite": e.gravite,
    }


def _socle(s: Session, a: AnalyseRisques, sid: int) -> SocleReferentiel:
    sr = s.get(SocleReferentiel, sid)
    if sr is None or sr.analyse_id != a.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Référentiel absent du socle.")
    return sr


def _journal(s: Session, u: Any, action: str, a: AnalyseRisques, request: Request, details: dict[str, Any] | None = None) -> None:
    journaliser(
        s, action, utilisateur_id=u.id, objet_type="analyse", objet_id=a.id, details=details, adresse_ip=adresse_ip(request)
    )


# ---- analyse et cadrage --------------------------------------------------------


@router.post("/missions/{mission_id}/analyses", status_code=status.HTTP_201_CREATED)
def creer(mission_id: int, donnees: Creation, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    m = acces.mission(s, u, mission_id, acces.SAISIE)
    _verifier_diagnostic(s, m.id, donnees.diagnostic_id)
    a = AnalyseRisques(mission_id=m.id, titre=donnees.titre.strip(), diagnostic_id=donnees.diagnostic_id, cree_par=u.id)
    s.add(a)
    s.flush()
    _journal(s, u, "analyse_creee", a, request)
    s.commit()
    return {"id": a.id}


@router.get("/analyses/{analyse_id}")
def synthese(analyse_id: int, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id)
    compte = lambda modele: len(s.scalars(select(modele.id).where(modele.analyse_id == a.id)).all())  # noqa: E731
    return {
        "id": a.id,
        "mission_id": a.mission_id,
        "mission_titre": a.mission.titre,
        "client": a.mission.client.nom,
        "titre": a.titre,
        "statut": a.statut,
        "objet": a.objet,
        "perimetre": a.perimetre,
        "participants": a.participants,
        "cycle_strategique_mois": a.cycle_strategique_mois,
        "cycle_operationnel_mois": a.cycle_operationnel_mois,
        "echelle_gravite": a.echelle_gravite,
        "diagnostic_id": a.diagnostic_id,
        "diagnostics_mission": [
            {"id": d.id, "statut": d.statut}
            for d in s.scalars(select(Diagnostic).where(Diagnostic.mission_id == a.mission_id).order_by(Diagnostic.id))
        ],
        "droits": sorted(acces.droits(s, u, a.mission_id)),
        "compte": {
            "valeurs_metier": compte(ValeurMetier),
            "biens_supports": compte(BienSupport),
            "evenements_redoutes": compte(EvenementRedoute),
            "referentiels_socle": compte(SocleReferentiel),
        },
        "impacts": list(IMPACTS),
    }


@router.patch("/analyses/{analyse_id}")
def cadrer(analyse_id: int, donnees: Cadrage, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    champs = donnees.model_dump(exclude_unset=True)
    if "diagnostic_id" in champs:
        _verifier_diagnostic(s, a.mission_id, champs["diagnostic_id"])
    if "echelle_gravite" in champs and champs["echelle_gravite"] is not None:
        maximum = len(champs["echelle_gravite"])
        trop = s.scalars(
            select(EvenementRedoute.id).where(EvenementRedoute.analyse_id == a.id, EvenementRedoute.gravite > maximum)
        ).first()
        if trop:
            raise HTTPException(
                status.HTTP_409_CONFLICT, "Des événements redoutés utilisent une gravité supérieure au nouveau maximum."
            )
    for cle, valeur in champs.items():
        setattr(a, cle, valeur.strip() if cle == "titre" and isinstance(valeur, str) else valeur)
    _journal(s, u, "analyse_cadrage", a, request, {"champs": sorted(champs)})
    s.commit()
    return synthese(analyse_id, u, s)


# ---- valeurs métier ----------------------------------------------------------


@router.get("/analyses/{analyse_id}/valeurs-metier")
def lister_valeurs(analyse_id: int, u: UtilisateurDep, s: SessionDep) -> list[dict[str, Any]]:
    a = acces.analyse(s, u, analyse_id)
    req = select(ValeurMetier).where(ValeurMetier.analyse_id == a.id).order_by(ValeurMetier.ordre, ValeurMetier.id)
    return [_sortie_valeur(v) for v in s.scalars(req)]


@router.post("/analyses/{analyse_id}/valeurs-metier", status_code=status.HTTP_201_CREATED)
def creer_valeur(analyse_id: int, donnees: ValeurEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    v = ValeurMetier(analyse_id=a.id, **donnees.model_dump())
    s.add(v)
    s.commit()
    return _sortie_valeur(v)


@router.put("/analyses/{analyse_id}/valeurs-metier/{vid}")
def modifier_valeur(analyse_id: int, vid: int, donnees: ValeurEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    v = _valeur(s, a, vid)
    for cle, valeur in donnees.model_dump().items():
        setattr(v, cle, valeur)
    s.commit()
    return _sortie_valeur(v)


@router.delete("/analyses/{analyse_id}/valeurs-metier/{vid}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_valeur(analyse_id: int, vid: int, u: UtilisateurDep, s: SessionDep) -> None:
    """Supprime aussi ses événements redoutés et ses liens aux biens supports."""
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    s.delete(_valeur(s, a, vid))
    s.commit()


# ---- biens supports -----------------------------------------------------------


def _lier(s: Session, a: AnalyseRisques, b: BienSupport, valeurs: list[int]) -> None:
    for vid in valeurs:
        _valeur(s, a, vid)
    s.execute(delete(LienValeurBien).where(LienValeurBien.bien_support_id == b.id))
    for vid in dict.fromkeys(valeurs):
        s.add(LienValeurBien(valeur_metier_id=vid, bien_support_id=b.id))


@router.get("/analyses/{analyse_id}/biens-supports")
def lister_biens(analyse_id: int, u: UtilisateurDep, s: SessionDep) -> list[dict[str, Any]]:
    a = acces.analyse(s, u, analyse_id)
    req = select(BienSupport).where(BienSupport.analyse_id == a.id).order_by(BienSupport.ordre, BienSupport.id)
    return [_sortie_bien(s, b) for b in s.scalars(req)]


@router.post("/analyses/{analyse_id}/biens-supports", status_code=status.HTTP_201_CREATED)
def creer_bien(analyse_id: int, donnees: BienEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    b = BienSupport(analyse_id=a.id, nom=donnees.nom, description=donnees.description, responsable=donnees.responsable)
    s.add(b)
    s.flush()
    _lier(s, a, b, donnees.valeurs_metier)
    s.commit()
    return _sortie_bien(s, b)


@router.put("/analyses/{analyse_id}/biens-supports/{bid}")
def modifier_bien(analyse_id: int, bid: int, donnees: BienEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    b = s.get(BienSupport, bid)
    if b is None or b.analyse_id != a.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bien support introuvable.")
    b.nom, b.description, b.responsable = donnees.nom, donnees.description, donnees.responsable
    _lier(s, a, b, donnees.valeurs_metier)
    s.commit()
    return _sortie_bien(s, b)


@router.delete("/analyses/{analyse_id}/biens-supports/{bid}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_bien(analyse_id: int, bid: int, u: UtilisateurDep, s: SessionDep) -> None:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    b = s.get(BienSupport, bid)
    if b is None or b.analyse_id != a.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Bien support introuvable.")
    s.delete(b)
    s.commit()


# ---- événements redoutés --------------------------------------------------------


def _verifier_evenement(s: Session, a: AnalyseRisques, donnees: EvenementEntree) -> None:
    _valeur(s, a, donnees.valeur_metier_id)
    if donnees.gravite > len(a.echelle_gravite):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"La gravité va de 1 à {len(a.echelle_gravite)} dans cette analyse.")


@router.get("/analyses/{analyse_id}/evenements-redoutes")
def lister_evenements(analyse_id: int, u: UtilisateurDep, s: SessionDep) -> list[dict[str, Any]]:
    a = acces.analyse(s, u, analyse_id)
    req = (
        select(EvenementRedoute)
        .where(EvenementRedoute.analyse_id == a.id)
        .order_by(EvenementRedoute.gravite.desc(), EvenementRedoute.id)
    )
    return [_sortie_evenement(e) for e in s.scalars(req)]


@router.post("/analyses/{analyse_id}/evenements-redoutes", status_code=status.HTTP_201_CREATED)
def creer_evenement(analyse_id: int, donnees: EvenementEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    _verifier_evenement(s, a, donnees)
    e = EvenementRedoute(analyse_id=a.id, **donnees.model_dump())
    s.add(e)
    s.commit()
    return _sortie_evenement(e)


@router.put("/analyses/{analyse_id}/evenements-redoutes/{eid}")
def modifier_evenement(analyse_id: int, eid: int, donnees: EvenementEntree, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    e = s.get(EvenementRedoute, eid)
    if e is None or e.analyse_id != a.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Événement redouté introuvable.")
    _verifier_evenement(s, a, donnees)
    for cle, valeur in donnees.model_dump().items():
        setattr(e, cle, valeur)
    s.commit()
    return _sortie_evenement(e)


@router.delete("/analyses/{analyse_id}/evenements-redoutes/{eid}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_evenement(analyse_id: int, eid: int, u: UtilisateurDep, s: SessionDep) -> None:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    e = s.get(EvenementRedoute, eid)
    if e is None or e.analyse_id != a.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Événement redouté introuvable.")
    s.delete(e)
    s.commit()


# ---- socle de sécurité ----------------------------------------------------------


@router.get("/analyses/{analyse_id}/socle")
def lire_socle(analyse_id: int, u: UtilisateurDep, s: SessionDep) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id)
    disponibles = s.scalars(
        select(Referentiel)
        .where(
            Referentiel.nature == NATURE_AUDIT,
            Referentiel.actif.is_(True),
            (Referentiel.mission_id.is_(None)) | (Referentiel.mission_id == a.mission_id),
        )
        .order_by(Referentiel.mission_id.is_not(None), Referentiel.code)
    ).all()
    return {
        **socle.vue(s, a),
        "disponibles": [
            {
                "id": r.id,
                "code": r.code,
                "version": r.version,
                "libelle": r.libelle,
                "profils": r.profils,
                "client": r.mission_id is not None,
            }
            for r in disponibles
        ],
    }


@router.post("/analyses/{analyse_id}/socle", status_code=status.HTTP_201_CREATED)
def ajouter_au_socle(analyse_id: int, donnees: AjoutSocle, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    ref = s.get(Referentiel, donnees.referentiel_id)
    if ref is None or ref.nature != NATURE_AUDIT or ref.mission_id not in (None, a.mission_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Référentiel introuvable.")
    if ref.profils and donnees.profil not in ref.profils:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Choisissez un profil : {', '.join(ref.profils)}.")
    if not ref.profils and donnees.profil:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ce référentiel n'a pas de profils.")
    deja = s.scalar(
        select(SocleReferentiel).join(Referentiel).where(SocleReferentiel.analyse_id == a.id, Referentiel.code == ref.code)
    )
    if deja is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce référentiel est déjà dans le socle.")
    sr = SocleReferentiel(analyse_id=a.id, referentiel_id=ref.id, profil=donnees.profil, motif=donnees.motif.strip())
    s.add(sr)
    s.flush()
    _journal(s, u, "socle_referentiel_ajoute", a, request, {"referentiel": f"{ref.code}@{ref.version}", "profil": donnees.profil})
    s.commit()
    return {"id": sr.id}


@router.delete("/analyses/{analyse_id}/socle/{sid}", status_code=status.HTTP_204_NO_CONTENT)
def retirer_du_socle(analyse_id: int, sid: int, u: UtilisateurDep, s: SessionDep, request: Request) -> None:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    sr = _socle(s, a, sid)
    _journal(s, u, "socle_referentiel_retire", a, request, {"referentiel": sr.referentiel.code})
    s.delete(sr)
    s.commit()


@router.put("/analyses/{analyse_id}/socle/{sid}/etats/{code}")
def renseigner_etat(
    analyse_id: int, sid: int, code: str, donnees: EtatEntree, u: UtilisateurDep, s: SessionDep
) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    sr = _socle(s, a, sid)
    elements = {n.code for n in arbre.charger(s, sr.referentiel).au_niveau(sr.referentiel.niveau_socle, sr.profil)}
    if code not in elements:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élément absent du socle pour ce profil.")
    e = s.scalar(select(EtatSocle).where(EtatSocle.socle_referentiel_id == sr.id, EtatSocle.noeud_code == code))
    if e is None:
        e = EtatSocle(socle_referentiel_id=sr.id, noeud_code=code)
        s.add(e)
    e.etat, e.ecart, e.justification = donnees.etat, donnees.ecart, donnees.justification
    e.source = "saisie"
    e.saisi_par = u.id
    e.saisi_le = datetime.now(UTC)
    s.commit()
    return {
        "code": code,
        "etat": e.etat,
        "ecart": e.ecart,
        "justification": e.justification,
        "source": e.source,
        "saisi_le": e.saisi_le,
    }


@router.post("/analyses/{analyse_id}/socle/{sid}/pre-remplir")
def pre_remplir(analyse_id: int, sid: int, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, int]:
    a = acces.analyse(s, u, analyse_id, acces.SAISIE)
    if a.diagnostic_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Liez d'abord un diagnostic de maturité à l'analyse (cadrage).")
    sr = _socle(s, a, sid)
    n = socle.pre_remplir(s, a, sr, u.id)
    _journal(s, u, "socle_pre_rempli", a, request, {"referentiel": sr.referentiel.code, "elements": n})
    s.commit()
    return {"remplis": n}


@router.post("/analyses/{analyse_id}/finaliser")
def finaliser(analyse_id: int, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.GESTION)
    a.statut = "finalise"
    _journal(s, u, "analyse_finalisee", a, request)
    s.commit()
    return synthese(analyse_id, u, s)


@router.post("/analyses/{analyse_id}/rouvrir")
def rouvrir(analyse_id: int, u: UtilisateurDep, s: SessionDep, request: Request) -> dict[str, Any]:
    a = acces.analyse(s, u, analyse_id, acces.GESTION)
    a.statut = "en_cours"
    _journal(s, u, "analyse_rouverte", a, request)
    s.commit()
    return synthese(analyse_id, u, s)
