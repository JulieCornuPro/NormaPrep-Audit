"""Réglages lus dans l'environnement (préfixe NPA_)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NPA_", env_file=".env", extra="ignore")

    # Base de données (SQLAlchemy + psycopg 3).
    database_url: str = "postgresql+psycopg://npa:npa@localhost:5432/npa"

    # Signature des jetons d'accès. Obligatoire en production.
    secret_key: str = ""

    # Clé Fernet (base64, 32 octets) qui chiffre les secrets TOTP en base.
    cle_chiffrement: str = ""

    # Dossier du contenu (référentiels), monté dans le conteneur.
    dossier_contenu: Path = Path("/content")

    # Nom affiché dans l'application d'authentification (TOTP).
    emetteur_totp: str = "NormaPrep Audit"

    # Durées.
    duree_jeton_acces_minutes: int = 480
    duree_jeton_intermediaire_minutes: int = 5

    # Protection contre les essais répétés de connexion.
    echecs_avant_blocage: int = 5
    duree_blocage_minutes: int = 15

    longueur_min_mot_de_passe: int = 12


@lru_cache
def reglages() -> Reglages:
    return Reglages()
