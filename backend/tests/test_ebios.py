"""Analyse de risques EBIOS RM, atelier 1 : cadrage, valeurs métier, biens
supports, événements redoutés, socle de sécurité."""

import pytest

from app.contenu.importeur import importer_audit, importer_excel, importer_maturite
from tests.classeur import classeur
from tests.conftest import ANSSI_EXEMPLE, DEMO_MATURITE, Connexion, creer_utilisateur

PROFIL_NIS2 = {"P01": ["energie"], "P02": ["eti"], "P06": ["aucun"], "P14": ["aucune"], "P15": ["non"]}


@pytest.fixture
def env(client, session, admin):
    # Pivot d'exemple (JSON), maturité de démonstration, puis guide complet (Excel) en version active.
    assert importer_audit(session, ANSSI_EXEMPLE).succes
    assert importer_maturite(session, DEMO_MATURITE).succes
    assert importer_excel(session, classeur(), "socle.xlsx")[0].succes
    h = admin.entetes()
    cli = client.post("/api/clients", headers=h, json={"nom": "Client"}).json()
    mission = client.post("/api/missions", headers=h, json={"client_id": cli["id"], "titre": "Mission"}).json()
    a = client.post(f"/api/missions/{mission['id']}/analyses", headers=h, json={"titre": "Analyse 2026"}).json()

    class Env:
        pass

    e = Env()
    e.h, e.mission, e.url = h, mission["id"], f"/api/analyses/{a['id']}"
    return e


def test_cadrage(client, env):
    r = client.patch(
        env.url,
        headers=env.h,
        json={"objet": "Plateforme de facturation", "cycle_strategique_mois": 36, "participants": "DSI, RSSI"},
    )
    a = r.json()
    assert a["objet"] == "Plateforme de facturation" and a["cycle_strategique_mois"] == 36
    assert [n["libelle"] for n in a["echelle_gravite"]] == ["Mineure", "Significative", "Grave", "Critique"]
    r = client.patch(
        env.url, headers=env.h, json={"echelle_gravite": [{"niveau": 1, "libelle": "A"}, {"niveau": 3, "libelle": "B"}]}
    )
    assert r.status_code == 422
    m = client.get(f"/api/missions/{env.mission}", headers=env.h).json()
    assert [x["titre"] for x in m["analyses"]] == ["Analyse 2026"]


def test_valeurs_biens_evenements(client, env):
    vm = client.post(
        f"{env.url}/valeurs-metier", headers=env.h, json={"nom": "Facturer les clients", "nature": "processus"}
    ).json()
    bs = client.post(
        f"{env.url}/biens-supports", headers=env.h, json={"nom": "ERP", "valeurs_metier": [vm["id"], vm["id"]]}
    ).json()
    assert bs["valeurs_metier"] == [vm["id"]]
    er = client.post(
        f"{env.url}/evenements-redoutes",
        headers=env.h,
        json={"valeur_metier_id": vm["id"], "description": "Arrêt de la facturation", "impacts": ["financiers"], "gravite": 3},
    )
    assert er.status_code == 201
    # Gravité hors échelle, impact inconnu : refusés.
    mauvais = {"valeur_metier_id": vm["id"], "description": "x", "impacts": [], "gravite": 5}
    assert client.post(f"{env.url}/evenements-redoutes", headers=env.h, json=mauvais).status_code == 400
    mauvais.update(gravite=2, impacts=["inconnu"])
    assert client.post(f"{env.url}/evenements-redoutes", headers=env.h, json=mauvais).status_code == 422
    # Réduire l'échelle sous une gravité utilisée : refusé.
    r = client.patch(
        env.url, headers=env.h, json={"echelle_gravite": [{"niveau": 1, "libelle": "A"}, {"niveau": 2, "libelle": "B"}]}
    )
    assert r.status_code == 409
    # Supprimer la valeur métier emporte ses événements et ses liens.
    assert client.delete(f"{env.url}/valeurs-metier/{vm['id']}", headers=env.h).status_code == 204
    assert client.get(f"{env.url}/evenements-redoutes", headers=env.h).json() == []
    assert client.get(f"{env.url}/biens-supports", headers=env.h).json()[0]["valeurs_metier"] == []


def ajouter(client, env, code, profil):
    socle = client.get(f"{env.url}/socle", headers=env.h).json()
    ref = next(d for d in socle["disponibles"] if d["code"] == code)
    return client.post(f"{env.url}/socle", headers=env.h, json={"referentiel_id": ref["id"], "profil": profil})


def test_socle_par_mesure_et_profil(client, env):
    assert ajouter(client, env, "ANSSI-HYG", None).status_code == 400  # profil obligatoire
    assert ajouter(client, env, "ANSSI-HYG", "Standard").status_code == 201
    assert ajouter(client, env, "ANSSI-HYG", "Renforcé").status_code == 409  # déjà présent
    [ref] = client.get(f"{env.url}/socle", headers=env.h).json()["referentiels"]
    # Profil Standard : la mesure 42 (renforcé seulement) n'apparaît pas.
    assert [e["code"] for e in ref["elements"]] == ["1", "13", "16", "37"]
    assert ref["referentiel"]["niveau"] == "Exigence" and ref["compte"]["non_evalue"] == 4
    m1 = ref["elements"][0]
    assert m1["groupe"] == "SENSIBILISER ET FORMER" and [d["code"] for d in m1["details"]] == ["1.1", "1.1.1"]

    sid = ref["id"]
    r = client.put(f"{env.url}/socle/{sid}/etats/13", headers=env.h, json={"etat": "partiel", "ecart": "Pas de MFA pour les VPN"})
    assert r.json()["source"] == "saisie"
    assert client.put(f"{env.url}/socle/{sid}/etats/42", headers=env.h, json={"etat": "applique"}).status_code == 404
    assert client.put(f"{env.url}/socle/{sid}/etats/13", headers=env.h, json={"etat": "bof"}).status_code == 422
    ref = client.get(f"{env.url}/socle", headers=env.h).json()["referentiels"][0]
    assert ref["compte"]["partiel"] == 1 and ref["sans_justification"] == 1


def test_socle_propose_et_pre_rempli_depuis_le_diagnostic(client, env):
    d = client.post(f"/api/missions/{env.mission}/diagnostics", headers=env.h).json()
    du = f"/api/diagnostics/{d['id']}"
    client.put(f"{du}/profilage", headers=env.h, json={"reponses": PROFIL_NIS2})
    client.put(f"{du}/reponses/I6-Q01", headers=env.h, json={"niveau": 2})  # sauvegardes → mesure 37

    # Sans diagnostic lié : rien de proposé, pré-remplissage refusé.
    assert client.get(f"{env.url}/socle", headers=env.h).json()["proposes"] == []
    client.patch(env.url, headers=env.h, json={"diagnostic_id": d["id"]})
    [propose] = client.get(f"{env.url}/socle", headers=env.h).json()["proposes"]
    # SOCLE (Standard) et NIS2-EE (Renforcé) appellent ANSSI-HYG : le plus exigeant l'emporte.
    assert (propose["code"], propose["profil"]) == ("ANSSI-HYG", "Renforcé")
    assert set(propose["motifs"]) == {"Socle d'hygiène (guide ANSSI)", "NIS2 : entité essentielle"}

    ajouter(client, env, "ANSSI-HYG", "Standard")
    sid = client.get(f"{env.url}/socle", headers=env.h).json()["referentiels"][0]["id"]
    client.put(f"{env.url}/socle/{sid}/etats/1", headers=env.h, json={"etat": "applique"})
    r = client.post(f"{env.url}/socle/{sid}/pre-remplir", headers=env.h)
    assert r.json() == {"remplis": 1}
    el = {e["code"]: e for e in client.get(f"{env.url}/socle", headers=env.h).json()["referentiels"][0]["elements"]}
    # Niveau 2 sur I6-Q01, seuils 3 / 1 : partiellement appliquée, présumée.
    assert (el["37"]["etat"], el["37"]["source"]) == ("partiel", "maturite")
    assert "I6-Q01 (niveau 2)" in el["37"]["ecart"]
    assert el["1"]["source"] == "saisie"  # la saisie n'est jamais remplacée


def test_diagnostic_d_une_autre_mission_refuse(client, env):
    cli = client.post("/api/clients", headers=env.h, json={"nom": "Autre"}).json()
    autre = client.post("/api/missions", headers=env.h, json={"client_id": cli["id"], "titre": "Autre"}).json()
    d = client.post(f"/api/missions/{autre['id']}/diagnostics", headers=env.h).json()
    assert client.patch(env.url, headers=env.h, json={"diagnostic_id": d["id"]}).status_code == 400


def test_referentiel_client_dans_le_socle(client, env):
    infos = [["Guide hygiène", "PSSI-CLIENT", "2026", "PSSI du client", "Client", "Interne", "Exigence", "Oui"]]
    r = client.post(
        f"/api/missions/{env.mission}/referentiels/televerser",
        headers=env.h,
        files={"fichier": ("pssi.xlsx", classeur(infos=infos), "application/octet-stream")},
    )
    assert r.json()[0]["succes"]
    disponibles = {d["code"]: d for d in client.get(f"{env.url}/socle", headers=env.h).json()["disponibles"]}
    assert disponibles["PSSI-CLIENT"]["client"] is True
    assert ajouter(client, env, "PSSI-CLIENT", "Standard").status_code == 201

    # Une autre mission ne voit pas ce référentiel.
    cli = client.post("/api/clients", headers=env.h, json={"nom": "Autre"}).json()
    autre = client.post("/api/missions", headers=env.h, json={"client_id": cli["id"], "titre": "Autre"}).json()
    a2 = client.post(f"/api/missions/{autre['id']}/analyses", headers=env.h, json={"titre": "A2"}).json()
    codes = [d["code"] for d in client.get(f"/api/analyses/{a2['id']}/socle", headers=env.h).json()["disponibles"]]
    assert "PSSI-CLIENT" not in codes


def test_droits(client, session, env):
    u = creer_utilisateur(session, "rel@exemple.fr")
    client.put(f"/api/missions/{env.mission}/membres", headers=env.h, json={"utilisateur_id": u.id, "role": "relecteur"})
    hr = Connexion(client, "rel@exemple.fr").entetes()
    assert client.get(env.url, headers=hr).status_code == 200
    assert client.post(f"{env.url}/valeurs-metier", headers=hr, json={"nom": "x"}).status_code == 403
    creer_utilisateur(session, "ext@exemple.fr")
    he = Connexion(client, "ext@exemple.fr").entetes()
    assert client.get(env.url, headers=he).status_code == 404


def test_finaliser_puis_rouvrir(client, env):
    assert client.post(f"{env.url}/finaliser", headers=env.h).json()["statut"] == "finalise"
    r = client.patch(env.url, headers=env.h, json={"objet": "x"})
    assert r.status_code == 409
    assert client.post(f"{env.url}/rouvrir", headers=env.h).json()["statut"] == "en_cours"
    assert client.patch(env.url, headers=env.h, json={"objet": "x"}).status_code == 200
