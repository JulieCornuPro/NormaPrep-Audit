"""Validation du contenu, sans base de données."""

import json
import shutil
from pathlib import Path

import pytest

from app.contenu import audit, maturite
from tests.conftest import ANSSI_EXEMPLE, DEMO_MATURITE, RACINE_BACKEND

FIXTURE_NORMAPREP = RACINE_BACKEND / "tests" / "fixtures" / "normaprep-exemple"


@pytest.fixture
def demo(tmp_path: Path) -> Path:
    """Copie modifiable du référentiel de démonstration."""
    cible = tmp_path / "demo"
    shutil.copytree(DEMO_MATURITE, cible)
    return cible


def modifier(chemin: Path, fonction) -> None:
    d = json.loads(chemin.read_text(encoding="utf-8"))
    fonction(d)
    chemin.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def erreurs(dossier: Path) -> list[str]:
    rapport, _ = maturite.analyser(dossier)
    return rapport.erreurs


# ---- maturité ----------------------------------------------------------------


def test_demo_valide():
    rapport, modele = maturite.analyser(DEMO_MATURITE)
    assert rapport.erreurs == []
    assert modele["referentiel"]["code"] == "NORMAPREP-MATURITE"
    assert set(modele["sous_themes"]) == {"G3", "I6", "A4"}
    q = modele["sous_themes"]["I6"]["questions"]["I6-Q01"]
    assert q["interlocuteurs"] == ["dsi", "administrateurs"]
    assert q["correspondances"][0]["referentiel"] == "ANSSI-HYG"
    assert len(modele["referentiel"]["empreinte"]) == 64


def test_format_normaprep_accepte_tel_quel():
    """Le référentiel d'exemple des tests NormaPrep, sans aucun ajout, est valide."""
    rapport, modele = maturite.analyser(FIXTURE_NORMAPREP)
    assert rapport.erreurs == []
    q = modele["sous_themes"]["G3"]["questions"]["G3-Q01"]
    assert q["type_question"] == "niveaux" and q["mode"] == "atelier" and q["correspondances"] == []


def test_empreinte_stable(demo):
    _, m1 = maturite.analyser(DEMO_MATURITE)
    _, m2 = maturite.analyser(demo)
    assert m1["referentiel"]["empreinte"] == m2["referentiel"]["empreinte"]


def test_fichier_obligatoire_manquant(demo):
    (demo / "_profilage.json").unlink()
    assert any("_profilage.json — Fichier manquant" in e for e in erreurs(demo))


def test_json_illisible(demo):
    (demo / "_prestations.json").write_text("{ pas du json", encoding="utf-8")
    assert any("JSON illisible" in e for e in erreurs(demo))


def test_niveau_manquant(demo):
    modifier(demo / "I_infrastructure" / "I6_sauvegardes.json", lambda d: d["questions"][0]["niveaux"].pop("4"))
    assert any("I6-Q01 — Description du niveau 4 manquante" in e for e in erreurs(demo))


def test_theme_inconnu(demo):
    modifier(demo / "A_applicatif" / "A4_secrets.json", lambda d: d["sous_theme"].update(theme="Z"))
    assert any("Thème « Z » inconnu" in e for e in erreurs(demo))


def test_prefixe_de_reference(demo):
    modifier(demo / "A_applicatif" / "A4_secrets.json", lambda d: d["questions"][0].update(ref="X-Q01"))
    assert any("doit commencer par « A4-Q »" in e for e in erreurs(demo))


def test_seuil_de_recommandation(demo):
    def f(d):
        d["questions"][0]["recommandations"][0]["seuil"] = 7

    modifier(demo / "I_infrastructure" / "I6_sauvegardes.json", f)
    assert any("« seuil » doit être un entier de 1 à 5" in e for e in erreurs(demo))


def test_prestation_inconnue(demo):
    def f(d):
        d["questions"][0]["recommandations"][0]["prestation"] = "INCONNUE"

    modifier(demo / "I_infrastructure" / "I6_sauvegardes.json", f)
    assert any("Prestation « INCONNUE » inconnue" in e for e in erreurs(demo))


def test_condition_avec_choix_inconnu(demo):
    def f(d):
        d["reglementations"][0]["regles"][0]["conditions"] = {"P01": ["choix-qui-n-existe-pas"]}

    modifier(demo / "_reglementations.json", f)
    assert any("Choix « choix-qui-n-existe-pas » inconnu pour P01" in e for e in erreurs(demo))


def test_exigence_sur_sous_theme_inconnu(demo):
    modifier(
        demo / "_reglementations.json",
        lambda d: d["reglementations"][0]["exigences"].update(Z9={"profondeur": "standard", "cible": 3}),
    )
    assert any("Sous-thème « Z9 » inconnu" in e for e in erreurs(demo))


def test_champs_d_atelier_controles(demo):
    def f(d):
        q = d["questions"][0]
        q.update(type="libre", mode="telepathie", duree=0, interlocuteurs=["stagiaire"])

    modifier(demo / "I_infrastructure" / "I6_sauvegardes.json", f)
    e = erreurs(demo)
    assert any("« type » doit valoir" in x for x in e)
    assert any("« mode » doit valoir" in x for x in e)
    assert any("« duree » doit être" in x for x in e)
    assert any("« stagiaire » inconnu" in x for x in e)


def test_seuils_de_correspondance(demo):
    def f(d):
        d["questions"][0]["correspondances"] = [
            {"referentiel": "ANSSI-HYG", "code": "37", "seuil_applique": 2, "seuil_partiel": 3},
            {"referentiel": "ANSSI-HYG", "code": "37"},
            {"referentiel": "ANSSI-HYG", "code": "34", "seuil_applique": 9},
        ]

    modifier(demo / "I_infrastructure" / "I6_sauvegardes.json", f)
    e = erreurs(demo)
    assert any("« seuil_partiel » ne peut pas dépasser" in x for x in e)
    assert any("déclarée deux fois" in x for x in e)
    assert any("« seuil_applique » doit être un entier de 1 à 5" in x for x in e)


def test_sections_sans_referentiel_audit(demo):
    modifier(demo / "_prestations.json", lambda d: d["prestations"][1].pop("referentiel_audit"))
    assert any("« sections » exige « referentiel_audit »" in e for e in erreurs(demo))


# ---- référentiel d'audit -----------------------------------------------------


def analyser_audit(tmp_path: Path, fonction=None):
    d = json.loads(ANSSI_EXEMPLE.read_text(encoding="utf-8"))
    if fonction:
        fonction(d)
    f = tmp_path / "ref.json"
    f.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return audit.analyser(f)


def test_exemple_anssi_valide():
    rapport, modele = audit.analyser(ANSSI_EXEMPLE)
    assert rapport.erreurs == []
    assert modele["code"] == "ANSSI-HYG"
    assert len(modele["sections"]) == 10
    s9 = next(s for s in modele["sections"] if s["code"] == "S09")
    assert [c["code"] for c in s9["exigences"][0]["controles"]] == ["37.a", "37.b", "37.c"]


def test_code_unique_entre_niveaux(tmp_path):
    def f(d):
        d["sections"][0]["exigences"][0]["controles"][0]["code"] = "37"

    rapport, _ = analyser_audit(tmp_path, f)
    assert any("Code « 37 » déjà utilisé" in e for e in rapport.erreurs)


def test_methode_et_niveau(tmp_path):
    def f(d):
        c = d["sections"][0]["exigences"][0]["controles"][0]
        c["methode"] = "intuition"
        c["niveau"] = "expert"

    rapport, _ = analyser_audit(tmp_path, f)
    assert any("« methode » doit valoir" in e for e in rapport.erreurs)
    assert any("« niveau » doit valoir : Standard, Renforcé" in e for e in rapport.erreurs)


def test_correspondance_vers_soi_meme(tmp_path):
    def f(d):
        d["sections"][0]["exigences"][0]["controles"][0]["correspondances"] = [{"referentiel": "ANSSI-HYG", "code": "37"}]

    rapport, _ = analyser_audit(tmp_path, f)
    assert any("doit viser un autre référentiel" in e for e in rapport.erreurs)


def test_seuils_interdits_sur_un_controle(tmp_path):
    def f(d):
        d["sections"][0]["exigences"][0]["controles"][0]["correspondances"] = [
            {"referentiel": "ISO27001", "code": "A.6.3", "seuil_applique": 3}
        ]

    rapport, _ = analyser_audit(tmp_path, f)
    assert any("n'a de sens que pour une question de maturité" in e for e in rapport.erreurs)
