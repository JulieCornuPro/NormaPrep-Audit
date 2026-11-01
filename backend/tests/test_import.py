"""Import en base, versions figées, couverture, journal."""

import json
import shutil

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.contenu.couverture import couverture
from app.contenu.importeur import importer_audit, importer_maturite
from app.models import Correspondance, EntreeJournal, Prestation, Question, Referentiel
from tests.conftest import ANSSI_EXEMPLE, DEMO_MATURITE


def compter(session, modele, *criteres) -> int:
    return session.scalar(select(func.count()).select_from(modele).where(*criteres))


def test_maturite_avant_le_pivot_est_refusee(session):
    res = importer_maturite(session, DEMO_MATURITE)
    assert not res.succes
    assert any("« ANSSI-HYG » absent de la base : importez-le avant" in e for e in res.erreurs)
    assert compter(session, Referentiel) == 0
    # Le refus est tracé.
    assert compter(session, EntreeJournal, EntreeJournal.action == "contenu_import_refuse") == 1


def test_import_complet(session):
    res = importer_audit(session, ANSSI_EXEMPLE)
    assert res.succes, res.erreurs
    assert res.stats == {"sections": 10, "exigences": 5, "controles": 4, "correspondances": 0}

    res = importer_maturite(session, DEMO_MATURITE)
    assert res.succes, res.erreurs
    assert res.stats["questions"] == 4
    assert res.stats["correspondances"] == 1

    q = session.scalar(select(Question).where(Question.ref == "I6-Q01"))
    assert q.interlocuteurs == ["dsi", "administrateurs"] and q.duree_estimee == 3
    corr = session.scalar(select(Correspondance).where(Correspondance.source_code == "I6-Q01"))
    assert (corr.cible_referentiel, corr.cible_code, corr.seuil_applique, corr.seuil_partiel) == ("ANSSI-HYG", "37", 3, 1)
    p = session.scalar(select(Prestation).where(Prestation.code == "AUDIT-ANSSI"))
    assert p.referentiel_audit == "ANSSI-HYG" and p.sections == ["S09"]
    assert compter(session, EntreeJournal, EntreeJournal.action == "contenu_importe") == 2


def test_reimport_identique_ne_fait_rien(session):
    importer_audit(session, ANSSI_EXEMPLE)
    res = importer_audit(session, ANSSI_EXEMPLE)
    assert res.succes and res.deja_importe
    assert compter(session, Referentiel) == 1


def test_version_figee(session, tmp_path):
    importer_audit(session, ANSSI_EXEMPLE)
    d = json.loads(ANSSI_EXEMPLE.read_text(encoding="utf-8"))
    d["sections"][0]["libelle"] = "Libellé modifié"
    f = tmp_path / "anssi.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")

    res = importer_audit(session, f)
    assert not res.succes
    assert any("Changez la version" in e for e in res.erreurs)

    # Nouvelle version : elle devient active, l'ancienne reste intacte.
    d["version"] = "exemple-0.2"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    assert importer_audit(session, f).succes
    versions = {r.version: r.actif for r in session.scalars(select(Referentiel))}
    assert versions == {"exemple-0.1": False, "exemple-0.2": True}


def test_remplacement_explicite(session, tmp_path):
    importer_audit(session, ANSSI_EXEMPLE)
    d = json.loads(ANSSI_EXEMPLE.read_text(encoding="utf-8"))
    d["sections"][0]["libelle"] = "Libellé modifié"
    f = tmp_path / "anssi.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    res = importer_audit(session, f, remplacer=True)
    assert res.succes, res.erreurs
    assert compter(session, Referentiel) == 1


def test_simulation_n_ecrit_rien(session):
    res = importer_audit(session, ANSSI_EXEMPLE, simulation=True)
    assert res.succes
    assert compter(session, Referentiel) == 0
    assert compter(session, EntreeJournal) == 0


def test_code_inconnu_dans_le_pivot(session, tmp_path):
    importer_audit(session, ANSSI_EXEMPLE)
    dossier = tmp_path / "demo"
    shutil.copytree(DEMO_MATURITE, dossier)
    f = dossier / "I_infrastructure" / "I6_sauvegardes.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["questions"][0]["correspondances"][0]["code"] = "99"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    res = importer_maturite(session, dossier)
    assert not res.succes
    assert any("Code « 99 » inconnu dans ANSSI-HYG" in e for e in res.erreurs)


def test_section_de_prestation_inconnue(session, tmp_path):
    importer_audit(session, ANSSI_EXEMPLE)
    dossier = tmp_path / "demo"
    shutil.copytree(DEMO_MATURITE, dossier)
    f = dossier / "_prestations.json"
    d = json.loads(f.read_text(encoding="utf-8"))
    d["prestations"][1]["sections"] = ["S99"]
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    res = importer_maturite(session, dossier)
    assert any("Section « S99 » inconnue" in e for e in res.erreurs)


def test_couverture(session):
    importer_audit(session, ANSSI_EXEMPLE)
    importer_maturite(session, DEMO_MATURITE)
    c = couverture(session, "ANSSI-HYG")
    assert c["nb_exigences"] == 5
    assert c["nb_couvertes"] == 1
    assert c["non_couvertes"] == ["1", "4", "7", "34"]
    m37 = next(e for s in c["sections"] for e in s["exigences"] if e["code"] == "37")
    assert m37["sources"][0]["code"] == "I6-Q01"
    assert couverture(session, "INCONNU") is None


def test_journal_inalterable(session):
    importer_audit(session, ANSSI_EXEMPLE)
    for requete in ("UPDATE journal SET action = 'falsifie'", "DELETE FROM journal", "TRUNCATE journal"):
        with pytest.raises(DBAPIError, match="ni modifié ni supprimé"):
            session.execute(text(requete))
        session.rollback()
    assert compter(session, EntreeJournal) == 1
