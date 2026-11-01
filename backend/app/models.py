"""Modèle de données.

Trois blocs :

- comptes et journal d'audit ;
- référentiels, importés depuis les fichiers du dossier de contenu. Chaque
  import crée une **version figée** (référentiel + tout son contenu) : une
  version déjà importée n'est jamais modifiée, ce qui garantit qu'un audit
  garde exactement le contenu sur lequel il a été mené. Les codes sont stables
  d'une version à l'autre ;
- correspondances entre référentiels, exprimées par codes (référentiel cible,
  contrôle cible) pour survivre aux changements de version.

Le contenu imbriqué qui n'est jamais interrogé en SQL (niveaux décrits, règles
de profilage, exigences) est stocké en JSON.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# ---------------------------------------------------------------------------
# Comptes et journal
# ---------------------------------------------------------------------------


class Utilisateur(Base):
    __tablename__ = "utilisateur"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    nom: Mapped[str] = mapped_column(String(200))
    mot_de_passe_hash: Mapped[str] = mapped_column(String(255))
    est_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    actif: Mapped[bool] = mapped_column(Boolean, default=True)

    # Secret TOTP chiffré (Fernet). Nul tant que l'enrôlement n'est pas fait.
    totp_secret_chiffre: Mapped[str | None] = mapped_column(Text, default=None)
    totp_actif: Mapped[bool] = mapped_column(Boolean, default=False)
    # Dernier pas de temps TOTP accepté : empêche de rejouer un code.
    totp_dernier_pas: Mapped[int | None] = mapped_column(BigInteger, default=None)

    echecs_connexion: Mapped[int] = mapped_column(Integer, default=0)
    bloque_jusqu_a: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # Incrémenté à chaque changement sensible : invalide les jetons émis avant.
    version_jeton: Mapped[int] = mapped_column(Integer, default=0)

    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    derniere_connexion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class EntreeJournal(Base):
    """Journal d'audit. Une règle en base interdit toute modification ou
    suppression (voir la migration initiale)."""

    __tablename__ = "journal"
    __table_args__ = (Index("ix_journal_action", "action"), Index("ix_journal_utilisateur", "utilisateur_id"))

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    horodatage: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    utilisateur_id: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id"), default=None)
    action: Mapped[str] = mapped_column(String(60))
    objet_type: Mapped[str | None] = mapped_column(String(60), default=None)
    objet_id: Mapped[str | None] = mapped_column(String(120), default=None)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    adresse_ip: Mapped[str | None] = mapped_column(String(45), default=None)


# ---------------------------------------------------------------------------
# Référentiels (versions figées)
# ---------------------------------------------------------------------------

NATURE_MATURITE = "maturite"
NATURE_AUDIT = "audit"


class Referentiel(Base):
    __tablename__ = "referentiel"
    __table_args__ = (UniqueConstraint("code", "version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(30))
    nature: Mapped[str] = mapped_column(String(20))  # maturite | audit
    libelle: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(Text, default="")
    licence: Mapped[str] = mapped_column(Text, default="")
    # La version active d'un code est celle que les nouveaux audits utilisent.
    actif: Mapped[bool] = mapped_column(Boolean, default=False)
    # SHA-256 du contenu importé : un import identique est reconnu.
    empreinte: Mapped[str] = mapped_column(String(64))
    importe_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    importe_par: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id"), default=None)
    avertissements: Mapped[list[str]] = mapped_column(JSON, default=list)

    sections: Mapped[list["Section"]] = relationship(
        back_populates="referentiel", cascade="all, delete-orphan", order_by="Section.ordre"
    )


# ---- Référentiels d'audit : Section > Exigence > Contrôle -----------------


class Section(Base):
    __tablename__ = "section"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    libelle: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    ordre: Mapped[int] = mapped_column(Integer)

    referentiel: Mapped[Referentiel] = relationship(back_populates="sections")
    exigences: Mapped[list["Exigence"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="Exigence.ordre"
    )


class Exigence(Base):
    __tablename__ = "exigence"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    section_id: Mapped[int] = mapped_column(ForeignKey("section.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    libelle: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text, default="")
    ordre: Mapped[int] = mapped_column(Integer)

    section: Mapped[Section] = relationship(back_populates="exigences")
    controles: Mapped[list["Controle"]] = relationship(
        back_populates="exigence", cascade="all, delete-orphan", order_by="Controle.ordre"
    )


class Controle(Base):
    __tablename__ = "controle"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    exigence_id: Mapped[int] = mapped_column(ForeignKey("exigence.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    intitule: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, default="")
    niveau: Mapped[str] = mapped_column(String(30), default="")
    methode: Mapped[str] = mapped_column(String(30))
    verification: Mapped[str] = mapped_column(Text, default="")
    valeur_attendue: Mapped[str] = mapped_column(Text, default="")
    preuves_attendues: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommandation: Mapped[str] = mapped_column(Text, default="")
    poids: Mapped[float] = mapped_column(Float, default=1.0)
    ordre: Mapped[int] = mapped_column(Integer)

    exigence: Mapped[Exigence] = relationship(back_populates="controles")


# ---- Référentiel de maturité (format NormaPrep) ---------------------------


class Theme(Base):
    __tablename__ = "theme"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(10))
    libelle: Mapped[str] = mapped_column(String(200))
    couleur: Mapped[str] = mapped_column(String(60), default="")
    ordre: Mapped[int] = mapped_column(Integer)
    poids: Mapped[float] = mapped_column(Float, default=1.0)


class SousTheme(Base):
    __tablename__ = "sous_theme"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    theme_id: Mapped[int] = mapped_column(ForeignKey("theme.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    libelle: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    ordre: Mapped[int] = mapped_column(Integer)
    poids: Mapped[float] = mapped_column(Float, default=1.0)


class Question(Base):
    __tablename__ = "question"
    __table_args__ = (UniqueConstraint("referentiel_id", "ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    sous_theme_id: Mapped[int] = mapped_column(ForeignKey("sous_theme.id", ondelete="CASCADE"))
    ref: Mapped[str] = mapped_column(String(30))
    enonce: Mapped[str] = mapped_column(Text)
    aide: Mapped[str] = mapped_column(Text, default="")
    profondeur: Mapped[str] = mapped_column(String(20))
    poids: Mapped[float] = mapped_column(Float, default=1.0)
    references: Mapped[list[str]] = mapped_column(JSON, default=list)
    # {"0": "...", ..., "5": "..."}
    niveaux: Mapped[dict[str, str]] = mapped_column(JSON)
    ordre: Mapped[int] = mapped_column(Integer)

    # Découpage en ateliers (cahier des charges, section 6).
    type_question: Mapped[str] = mapped_column(String(20), default="niveaux")
    duree_estimee: Mapped[float | None] = mapped_column(Float, default=None)  # minutes
    mode: Mapped[str] = mapped_column(String(30), default="atelier")
    interlocuteurs: Mapped[list[str]] = mapped_column(JSON, default=list)


class Prestation(Base):
    __tablename__ = "prestation"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    libelle: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    lien: Mapped[str] = mapped_column(Text, default="")
    # Câblage vers un type d'audit : référentiel d'audit et sections proposées.
    referentiel_audit: Mapped[str | None] = mapped_column(String(50), default=None)
    sections: Mapped[list[str]] = mapped_column(JSON, default=list)


class Recommandation(Base):
    __tablename__ = "recommandation"
    __table_args__ = (UniqueConstraint("referentiel_id", "ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    sous_theme_id: Mapped[int] = mapped_column(ForeignKey("sous_theme.id", ondelete="CASCADE"))
    question_id: Mapped[int | None] = mapped_column(ForeignKey("question.id", ondelete="CASCADE"), default=None)
    ref: Mapped[str] = mapped_column(String(40))
    texte: Mapped[str] = mapped_column(Text)
    seuil: Mapped[int] = mapped_column(Integer)
    effort: Mapped[str] = mapped_column(String(10))
    quick_win: Mapped[bool] = mapped_column(Boolean, default=False)
    prestation_code: Mapped[str | None] = mapped_column(String(50), default=None)


class QuestionProfil(Base):
    __tablename__ = "question_profil"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(20))
    libelle: Mapped[str] = mapped_column(Text)
    aide: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(20))
    condition: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    # [{"code": "energie", "libelle": "Énergie"}, ...]
    choix: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    ordre: Mapped[int] = mapped_column(Integer)


class Reglementation(Base):
    __tablename__ = "reglementation"
    __table_args__ = (UniqueConstraint("referentiel_id", "code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(30))
    libelle: Mapped[str] = mapped_column(String(300))
    nature: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="")
    echeance: Mapped[str] = mapped_column(Text, default="")
    actions: Mapped[list[str]] = mapped_column(JSON, default=list)
    # [{"ref": "NIS2-EE-R1", "niveau": ..., "conditions": {...}, "critere": ..., "priorite": 0}]
    regles: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    # {"G3": {"profondeur": "renforce", "cible": 4.0}}
    exigences: Mapped[dict[str, dict[str, Any]]] = mapped_column(JSON, default=dict)
    ordre: Mapped[int] = mapped_column(Integer)


# ---- Correspondances --------------------------------------------------------


class Correspondance(Base):
    """Lien d'un élément d'une version de référentiel (question de maturité ou
    contrôle d'audit) vers une exigence ou un contrôle d'un autre référentiel,
    désigné par codes (les codes d'exigence et de contrôle partagent le même
    espace dans un référentiel). Les seuils servent à présumer l'état de la
    cible à partir d'un niveau de maturité : appliquée si
    niveau >= seuil_applique, partielle si niveau >= seuil_partiel, sinon non
    appliquée. Nuls = règle par défaut de l'outil."""

    __tablename__ = "correspondance"
    __table_args__ = (
        UniqueConstraint("referentiel_id", "source_type", "source_code", "cible_referentiel", "cible_code"),
        Index("ix_correspondance_cible", "cible_referentiel", "cible_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(10))  # question | controle
    source_code: Mapped[str] = mapped_column(String(50))
    cible_referentiel: Mapped[str] = mapped_column(String(50))
    cible_code: Mapped[str] = mapped_column(String(50))
    seuil_applique: Mapped[int | None] = mapped_column(Integer, default=None)
    seuil_partiel: Mapped[int | None] = mapped_column(Integer, default=None)


# ---------------------------------------------------------------------------
# Clients, missions et diagnostics (jalon 2)
# ---------------------------------------------------------------------------

ROLE_RESPONSABLE = "responsable"
ROLE_CONSULTANT = "consultant"
ROLE_RELECTEUR = "relecteur"
ROLES_MISSION = (ROLE_RESPONSABLE, ROLE_CONSULTANT, ROLE_RELECTEUR)


class Client(Base):
    __tablename__ = "client"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Nom réel ou pseudonyme : le cabinet choisit ce qu'il conserve.
    nom: Mapped[str] = mapped_column(String(200))
    secteur: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id"), default=None)


class Mission(Base):
    __tablename__ = "mission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("client.id"))
    titre: Mapped[str] = mapped_column(String(300))
    perimetre: Mapped[str] = mapped_column(Text, default="")
    statut: Mapped[str] = mapped_column(String(20), default="en_cours")  # en_cours | terminee
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id"), default=None)

    client: Mapped[Client] = relationship()
    membres: Mapped[list["MembreMission"]] = relationship(back_populates="mission", cascade="all, delete-orphan")


class MembreMission(Base):
    """Rôle d'un utilisateur sur une mission. Un administrateur voit toutes
    les missions sans en être membre."""

    __tablename__ = "membre_mission"
    __table_args__ = (UniqueConstraint("mission_id", "utilisateur_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("mission.id", ondelete="CASCADE"))
    utilisateur_id: Mapped[int] = mapped_column(ForeignKey("utilisateur.id"))
    role: Mapped[str] = mapped_column(String(20))

    mission: Mapped[Mission] = relationship(back_populates="membres")
    utilisateur: Mapped[Utilisateur] = relationship()


class Diagnostic(Base):
    """Diagnostic de maturité d'une mission, mené sur une version figée du
    référentiel de maturité."""

    __tablename__ = "diagnostic"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("mission.id", ondelete="CASCADE"))
    referentiel_id: Mapped[int] = mapped_column(ForeignKey("referentiel.id"))
    statut: Mapped[str] = mapped_column(String(20), default="en_cours")  # en_cours | finalise
    # Réponses de profilage : {"P01": ["energie"], ...}
    profil: Mapped[dict[str, list[str]]] = mapped_column(JSON, default=dict)
    # Mode de recueil modifié par le consultant : {"G3-Q01": "pre_questionnaire"}
    modes: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    budget_atelier_minutes: Mapped[int] = mapped_column(Integer, default=120)
    ouverture_minutes: Mapped[int] = mapped_column(Integer, default=15)
    # Résultats figés à la finalisation (scores, cibles, recommandations).
    resultats_figes: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id"), default=None)
    finalise_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    mission: Mapped[Mission] = relationship()
    referentiel: Mapped[Referentiel] = relationship()


class DiagReglementation(Base):
    """Réglementation proposée par le profilage ou ajoutée par le consultant,
    avec la décision prise (reprise de NormaPrep)."""

    __tablename__ = "diag_reglementation"
    __table_args__ = (UniqueConstraint("diagnostic_id", "reglementation_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostic.id", ondelete="CASCADE"))
    reglementation_code: Mapped[str] = mapped_column(String(30))
    niveau_calcule: Mapped[str] = mapped_column(String(20))  # obligatoire | a_verifier | recommande
    decision: Mapped[str] = mapped_column(String(20))  # retenue | ecartee | en_attente
    origine: Mapped[str] = mapped_column(String(10))  # calcul | forcage
    critere: Mapped[str] = mapped_column(Text, default="")
    justification: Mapped[str] = mapped_column(Text, default="")


class Reponse(Base):
    """Réponse à une question de maturité. Le niveau retenu est celui du
    consultant ; la proposition du client (pré-questionnaire) est gardée à
    part jusqu'à ce que le consultant la valide."""

    __tablename__ = "reponse"
    __table_args__ = (UniqueConstraint("diagnostic_id", "question_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostic.id", ondelete="CASCADE"))
    question_ref: Mapped[str] = mapped_column(String(30))
    niveau: Mapped[int | None] = mapped_column(Integer, default=None)
    non_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    commentaire: Mapped[str] = mapped_column(Text, default="")
    saisi_par: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id"), default=None)
    saisi_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    niveau_propose: Mapped[int | None] = mapped_column(Integer, default=None)
    commentaire_client: Mapped[str] = mapped_column(Text, default="")
    propose_le: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class LienPreQuestionnaire(Base):
    """Lien envoyé au client pour le pré-questionnaire. Seule l'empreinte
    SHA-256 du jeton est conservée."""

    __tablename__ = "lien_pre_questionnaire"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    diagnostic_id: Mapped[int] = mapped_column(ForeignKey("diagnostic.id", ondelete="CASCADE"))
    empreinte_jeton: Mapped[str] = mapped_column(String(64), unique=True)
    destinataire: Mapped[str] = mapped_column(String(200), default="")
    expire_le: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoque: Mapped[bool] = mapped_column(Boolean, default=False)
    cree_le: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cree_par: Mapped[int | None] = mapped_column(ForeignKey("utilisateur.id"), default=None)
    derniere_utilisation: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
