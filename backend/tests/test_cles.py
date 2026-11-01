"""Clés de l'application : génération au premier démarrage, priorité à l'environnement."""

import json
import stat

import pytest
from cryptography.fernet import Fernet

from app import config
from app.securite import ConfigurationInvalide, verifier_configuration


@pytest.fixture
def sans_cles(monkeypatch, tmp_path):
    """Environnement sans clés, fichier de clés dans un dossier temporaire."""
    fichier = tmp_path / "npa" / "cles.json"
    monkeypatch.setenv("NPA_SECRET_KEY", "")
    monkeypatch.setenv("NPA_CLE_CHIFFREMENT", "")
    monkeypatch.setenv("NPA_FICHIER_CLES", str(fichier))
    config.reglages.cache_clear()
    yield fichier
    config.reglages.cache_clear()


def test_generation_au_premier_demarrage(sans_cles):
    with pytest.raises(ConfigurationInvalide, match="laissez-la vide"):
        verifier_configuration()

    message = config.preparer_cles()
    assert "NPA_SECRET_KEY" in message and "NPA_CLE_CHIFFREMENT" in message
    assert stat.S_IMODE(sans_cles.stat().st_mode) == 0o600

    r = config.reglages()
    assert len(r.secret_key) >= 32
    Fernet(r.cle_chiffrement.encode())
    verifier_configuration()


def test_les_cles_ne_changent_plus(sans_cles):
    config.preparer_cles()
    avant = json.loads(sans_cles.read_text())
    assert config.preparer_cles() == "Clés de l'application : en place."
    assert json.loads(sans_cles.read_text()) == avant


def test_l_environnement_a_priorite(sans_cles, monkeypatch):
    config.preparer_cles()
    monkeypatch.setenv("NPA_SECRET_KEY", "cle-fournie-par-env-" + "y" * 20)
    config.reglages.cache_clear()
    assert config.reglages().secret_key.startswith("cle-fournie-par-env-")
    # La clé de chiffrement, absente de l'environnement, vient du fichier.
    assert config.reglages().cle_chiffrement == json.loads(sans_cles.read_text())["cle_chiffrement"]


def test_rien_n_est_genere_si_l_environnement_fournit_tout(monkeypatch, tmp_path):
    fichier = tmp_path / "cles.json"
    monkeypatch.setenv("NPA_FICHIER_CLES", str(fichier))
    assert config.preparer_cles() == "Clés de l'application : en place."
    assert not fichier.exists()


def test_mot_de_passe_de_base_avec_caracteres_speciaux(monkeypatch):
    """Un « % », un « @ » ou un « / » dans NPA_DB_PASSWORD ne cassent plus l'URL."""
    monkeypatch.delenv("NPA_DATABASE_URL", raising=False)
    monkeypatch.setenv("NPA_DB_PASSWORD", "a%2b@c/d:e#f")
    monkeypatch.setenv("NPA_DB_HOTE", "db")
    url = config.url_base(config.Reglages())
    assert (url.password, url.host, url.database) == ("a%2b@c/d:e#f", "db", "npa")
