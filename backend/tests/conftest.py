"""Tests sur une vraie base PostgreSQL (NPA_TEST_DATABASE_URL).

Chaque test part d'un schéma vide, créé par les migrations Alembic : les
migrations sont donc testées à chaque exécution.
"""

import base64
import os
from pathlib import Path

RACINE_BACKEND = Path(__file__).resolve().parents[1]
RACINE_DEPOT = RACINE_BACKEND.parent

os.environ["NPA_DATABASE_URL"] = os.environ.get("NPA_TEST_DATABASE_URL", "postgresql+psycopg://npa:npa@localhost:5432/npa_test")
os.environ["NPA_SECRET_KEY"] = "cle-de-test-" + "x" * 40
os.environ["NPA_CLE_CHIFFREMENT"] = base64.urlsafe_b64encode(b"cle-de-test-chiffrement-32-octet").decode()
os.environ["NPA_DOSSIER_CONTENU"] = str(RACINE_DEPOT / "content")

import pyotp  # noqa: E402
import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.db import fabrique_sessions, moteur  # noqa: E402
from app.models import Utilisateur  # noqa: E402
from app.securite import hacher_mot_de_passe  # noqa: E402

CONTENU = RACINE_DEPOT / "content"
DEMO_MATURITE = CONTENU / "maturite" / "demo"
ANSSI_EXEMPLE = CONTENU / "referentiels" / "anssi-hygiene-exemple.json"
MOT_DE_PASSE = "un mot de passe solide"


@pytest.fixture
def base():
    """Schéma vide puis migrations jusqu'à la dernière révision."""
    m = moteur()
    m.dispose()
    with m.begin() as c:
        c.execute(text("DROP SCHEMA public CASCADE"))
        c.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(RACINE_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(RACINE_BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    yield m
    m.dispose()


@pytest.fixture
def session(base):
    s = fabrique_sessions()()
    yield s
    s.close()


@pytest.fixture
def client(base):
    from app.main import app

    with TestClient(app) as c:
        yield c


def creer_utilisateur(session, email: str, est_admin: bool = False) -> Utilisateur:
    u = Utilisateur(
        email=email, nom=email.split("@")[0], mot_de_passe_hash=hacher_mot_de_passe(MOT_DE_PASSE), est_admin=est_admin
    )
    session.add(u)
    session.commit()
    return u


class Connexion:
    """Mène la connexion complète d'un utilisateur et garde son secret TOTP."""

    def __init__(self, client: TestClient, email: str) -> None:
        self.client = client
        self.email = email
        self.secret: str | None = None
        self.decalage = 0

    def code(self) -> str:
        import time

        # Chaque connexion utilise le pas suivant : un code ne se rejoue pas.
        code = pyotp.TOTP(self.secret).at(time.time() + 30 * self.decalage)
        self.decalage += 1
        self.dernier_code = code
        return code

    def jeton(self) -> str:
        r = self.client.post("/api/auth/connexion", json={"email": self.email, "mot_de_passe": MOT_DE_PASSE})
        assert r.status_code == 200, r.text
        etape = r.json()
        if etape["etape"] == "enrolement":
            self.secret = etape["secret"]
        r = self.client.post("/api/auth/totp", json={"jeton": etape["jeton"], "code": self.code()})
        assert r.status_code == 200, r.text
        return r.json()["jeton_acces"]

    def entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.jeton()}"}


@pytest.fixture
def admin(client, session):
    creer_utilisateur(session, "admin@exemple.fr", est_admin=True)
    return Connexion(client, "admin@exemple.fr")
