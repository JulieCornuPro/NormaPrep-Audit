"""Réglages lus dans l'environnement (préfixe NPA_).

Les deux clés de l'application (NPA_SECRET_KEY, NPA_CLE_CHIFFREMENT) peuvent
être fournies par l'environnement. Laissées vides, elles sont générées au
premier démarrage et conservées dans `fichier_cles` (un volume Docker) :
voir `preparer_cles`. L'environnement a toujours priorité sur le fichier.
"""

import json
import os
import secrets
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

CLES = ("secret_key", "cle_chiffrement")


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="NPA_", env_file=".env", extra="ignore")

    # Base de données. Soit une URL complète (NPA_DATABASE_URL), soit ses
    # éléments séparés : c'est le cas sous Docker, où le mot de passe vient de
    # NPA_DB_PASSWORD. L'URL est alors construite ici, caractères spéciaux
    # du mot de passe échappés (un « % » ou un « @ » cassait l'URL).
    database_url: str = ""
    db_hote: str = "localhost"
    db_port: int = 5432
    db_utilisateur: str = "npa"
    db_nom: str = "npa"
    db_password: str = "npa"

    # Signature des jetons d'accès.
    secret_key: str = ""

    # Clé Fernet (base64, 32 octets) qui chiffre les secrets TOTP en base.
    cle_chiffrement: str = ""

    # Fichier des clés générées automatiquement (volume persistant).
    fichier_cles: Path = Path("/var/lib/npa/cles.json")

    # Dossier du contenu (référentiels), monté dans le conteneur.
    dossier_contenu: Path = Path("/content")

    # Interface web compilée, servie par l'API (vide = pas d'interface).
    dossier_interface: Path = Path("/app/interface")

    # Nom affiché dans l'application d'authentification (TOTP).
    emetteur_totp: str = "NormaPrep Audit"

    # Durées.
    duree_jeton_acces_minutes: int = 480
    duree_jeton_intermediaire_minutes: int = 5

    # Protection contre les essais répétés de connexion.
    echecs_avant_blocage: int = 5
    duree_blocage_minutes: int = 15

    longueur_min_mot_de_passe: int = 12


def url_base(r: "Reglages") -> URL | str:
    if r.database_url:
        return r.database_url
    return URL.create(
        "postgresql+psycopg",
        username=r.db_utilisateur,
        password=r.db_password,
        host=r.db_hote,
        port=r.db_port,
        database=r.db_nom,
    )


def _lire_fichier_cles(fichier: Path) -> dict[str, str]:
    if not fichier.is_file():
        return {}
    contenu = json.loads(fichier.read_text(encoding="utf-8"))
    return {k: str(contenu[k]) for k in CLES if contenu.get(k)}


@lru_cache
def reglages() -> Reglages:
    r = Reglages()
    manquantes = [k for k in CLES if not getattr(r, k)]
    if manquantes:
        depuis_fichier = _lire_fichier_cles(r.fichier_cles)
        r = r.model_copy(update={k: depuis_fichier[k] for k in manquantes if k in depuis_fichier})
    return r


def preparer_cles() -> str:
    """Génère les clés absentes de l'environnement et du fichier, et les
    enregistre dans le fichier (droits 600). Ne remplace jamais une clé
    existante. Renvoie un message pour le journal de démarrage."""
    r = Reglages()
    fichier = r.fichier_cles
    existantes = _lire_fichier_cles(fichier)
    a_generer = [k for k in CLES if not getattr(r, k) and k not in existantes]
    if not a_generer:
        return "Clés de l'application : en place."

    nouvelles = dict(existantes)
    if "secret_key" in a_generer:
        nouvelles["secret_key"] = secrets.token_urlsafe(48)
    if "cle_chiffrement" in a_generer:
        nouvelles["cle_chiffrement"] = Fernet.generate_key().decode()

    fichier.parent.mkdir(parents=True, exist_ok=True)
    temporaire = fichier.with_suffix(".tmp")
    descripteur = os.open(temporaire, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descripteur, "w", encoding="utf-8") as f:
        json.dump(nouvelles, f)
    os.replace(temporaire, fichier)
    reglages.cache_clear()
    noms = ", ".join(f"NPA_{k.upper()}" for k in a_generer)
    return f"Clés générées et enregistrées dans {fichier} : {noms}. Sauvegardez ce fichier (npa afficher-cles)."
