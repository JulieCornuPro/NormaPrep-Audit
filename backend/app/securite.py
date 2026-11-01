"""Mots de passe, TOTP et jetons.

- Mots de passe : Argon2id (argon2-cffi), paramètres par défaut de la
  bibliothèque, rehachés automatiquement s'ils évoluent.
- TOTP : secret généré par pyotp, chiffré en base avec Fernet (clé
  NPA_CLE_CHIFFREMENT). Un code déjà accepté ne peut pas être rejoué.
- Jetons : JWT HS256 signés avec NPA_SECRET_KEY.
  * jeton intermédiaire (5 min), délivré après le mot de passe, qui ne sert
    qu'à présenter le code TOTP ;
  * jeton d'accès (8 h par défaut). Il porte la `version_jeton` de
    l'utilisateur : la changer (mot de passe modifié, compte désactivé,
    TOTP réinitialisé) invalide tous les jetons déjà émis.
"""

import time
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken

from app.config import reglages

_hacheur = PasswordHasher()

USAGE_ACCES = "acces"
USAGE_TOTP = "totp"


class ConfigurationInvalide(RuntimeError):
    pass


def verifier_configuration() -> None:
    """Refuse de démarrer avec des clés absentes ou faibles."""
    r = reglages()
    if len(r.secret_key) < 32:
        raise ConfigurationInvalide("NPA_SECRET_KEY doit contenir au moins 32 caractères.")
    try:
        Fernet(r.cle_chiffrement.encode())
    except (ValueError, TypeError) as e:
        raise ConfigurationInvalide("NPA_CLE_CHIFFREMENT doit être une clé Fernet (générez-la avec : npa generer-cles).") from e


# ---- mots de passe ----------------------------------------------------------


def hacher_mot_de_passe(mot_de_passe: str) -> str:
    return _hacheur.hash(mot_de_passe)


def verifier_mot_de_passe(hache: str, mot_de_passe: str) -> bool:
    try:
        return _hacheur.verify(hache, mot_de_passe)
    except (VerificationError, InvalidHashError):
        return False


def doit_rehacher(hache: str) -> bool:
    return _hacheur.check_needs_rehash(hache)


# Haché factice : vérifié quand l'email est inconnu, pour que la durée de
# réponse ne révèle pas si un compte existe.
HACHE_FACTICE = _hacheur.hash("compte-inexistant-valeur-factice")


# ---- TOTP -------------------------------------------------------------------


def _fernet() -> Fernet:
    return Fernet(reglages().cle_chiffrement.encode())


def nouveau_secret_totp() -> str:
    return pyotp.random_base32()


def chiffrer(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def dechiffrer(secret_chiffre: str) -> str:
    try:
        return _fernet().decrypt(secret_chiffre.encode()).decode()
    except InvalidToken as e:
        raise ConfigurationInvalide("Secret TOTP indéchiffrable : la clé de chiffrement a changé ?") from e


def uri_totp(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=reglages().emetteur_totp)


def verifier_totp(secret: str, code: str, dernier_pas: int | None, maintenant: float | None = None) -> int | None:
    """Vérifie un code (fenêtre ±1 pas de 30 s). Renvoie le pas accepté, ou
    None si le code est faux ou déjà utilisé."""
    code = code.strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return None
    totp = pyotp.TOTP(secret)
    t = time.time() if maintenant is None else maintenant
    pas_actuel = int(t // totp.interval)
    for decalage in (0, -1, 1):
        pas = pas_actuel + decalage
        if totp.at(pas * totp.interval) == code:
            if dernier_pas is not None and pas <= dernier_pas:
                return None  # rejeu
            return pas
    return None


# ---- jetons -----------------------------------------------------------------


def emettre_jeton(utilisateur_id: int, usage: str, version_jeton: int, minutes: int) -> str:
    maintenant = datetime.now(UTC)
    charge = {
        "sub": str(utilisateur_id),
        "usage": usage,
        "ver": version_jeton,
        "iat": maintenant,
        "exp": maintenant + timedelta(minutes=minutes),
    }
    return jwt.encode(charge, reglages().secret_key, algorithm="HS256")


def lire_jeton(jeton: str, usage: str) -> dict[str, Any] | None:
    try:
        charge = jwt.decode(
            jeton, reglages().secret_key, algorithms=["HS256"], options={"require": ["sub", "exp", "usage", "ver"]}
        )
    except jwt.PyJWTError:
        return None
    if charge.get("usage") != usage:
        return None
    return charge
