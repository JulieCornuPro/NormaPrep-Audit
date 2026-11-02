"""Import des référentiels depuis Excel (format du brouillon « Socle de sécurité »)."""

from app.contenu import excel
from tests.classeur import INFO_HYG, LIGNES, classeur
from tests.conftest import Connexion, creer_utilisateur


def lire(contenu: bytes):
    return excel.lire(contenu)


def test_lecture_arborescence_et_profils():
    [(feuille, rapport, modele)] = lire(classeur())
    assert feuille == "Guide hygiène" and rapport.erreurs == []
    assert modele["niveaux"] == ["Section", "Exigence", "Contrôle", "Contrôle détaillé"]
    assert modele["profils"] == ["Standard", "Renforcé"]
    assert modele["niveau_socle"] == 1
    n = {x["code"]: x for x in modele["noeuds"]}
    # « 1.1 » est à la fois un contrôle et le parent de « 1.1.1 ».
    assert (n["1.1.1"]["parent"], n["1.1"]["parent"], n["1"]["parent"], n["I"]["parent"]) == ("1.1", "1", "I", None)
    assert n["1.1"]["libelle"] == "Les équipes formées comprennent ..."
    # Mesure sans contrôle : un élément terminal au niveau Exigence.
    assert n["16"]["niveau"] == 1 and not any(x["parent"] == "16" for x in modele["noeuds"])
    # Profils : ceux de la ligne, plus ceux des descendants.
    assert n["1.2"]["profils"] == ["Renforcé"] and n["1"]["profils"] == ["Standard", "Renforcé"]
    assert n["42"]["profils"] == ["Renforcé"]


def test_profils_cumulatifs_corrige_et_signale():
    [(_, rapport, modele)] = lire(classeur())
    assert any("13.1 : applicable en « Standard » mais pas en « Renforcé »" in a for a in rapport.avertissements)
    assert next(x for x in modele["noeuds"] if x["code"] == "13.1")["profils"] == ["Standard", "Renforcé"]


def test_profils_non_cumulatifs():
    [(_, rapport, modele)] = lire(classeur(infos=[INFO_HYG[:7] + ["Non"]]))
    assert not rapport.avertissements or not any("13.1" in a for a in rapport.avertissements)
    assert next(x for x in modele["noeuds"] if x["code"] == "13.1")["profils"] == ["Standard"]


def test_codes_recyf_et_tiret_colle():
    lignes = [
        [
            "I - Gouvernance",
            "2.A.1-EI/EE - Le dirigeant est responsable",
            "2.A.1-EI/EE.1- Le dirigeant est-il responsable ?",
            "-",
            "Oui",
            "Oui",
        ],
    ]
    [(_, rapport, modele)] = lire(classeur(lignes))
    assert rapport.erreurs == []
    assert [x["code"] for x in modele["noeuds"]] == ["I", "2.A.1-EI/EE", "2.A.1-EI/EE.1"]


def test_feuilles_hors_infos_ignorees():
    resultats = lire(classeur(feuilles_en_plus={"ReCyF en cours": [["Section"], ["n'importe quoi"]], "DORA": []}))
    assert [f for f, _, _ in resultats] == ["Guide hygiène"]


def test_erreurs_localisees():
    lignes = LIGNES + [
        ["II - CONNAÎTRE", "4 Identifier les informations sensibles", "-", "-", "Oui", "Oui"],
        ["I - SENSIBILISER ET FORMER", "1 - Autre libellé pour la même mesure", "-", "-", "Oui", "Oui"],
    ]
    [(_, rapport, modele)] = lire(classeur(lignes))
    assert modele is None
    assert any(
        "Guide hygiène › B10 — « 4 Identifier les informations sensibles » : attendu « code - libellé »" in e
        for e in rapport.erreurs
    )
    assert any("B11 — Code « 1 » déjà utilisé ligne 2 avec un autre libellé" in e for e in rapport.erreurs)


def test_infos_obligatoire_et_controlee():
    [(_, rapport, _)] = lire(classeur(avec_infos=False))
    assert any("Feuille « Infos » manquante" in e for e in rapport.erreurs)
    [(_, rapport, _)] = lire(classeur(infos=[["Absente", "X", "1", "X", "", "", "", ""]]))
    assert any("Feuille « Absente » introuvable" in e for e in rapport.erreurs)
    [(_, rapport, _)] = lire(classeur(infos=[INFO_HYG[:6] + ["Mesure", "Oui"]]))
    assert any("niveau socle « Mesure » absent des en-têtes" in e for e in rapport.erreurs)
    [(_, rapport, _)] = lire(b"pas un classeur")
    assert any("Classeur Excel illisible" in e for e in rapport.erreurs)


def test_empreinte_stable():
    a = lire(classeur())[0][2]["empreinte"]
    b = lire(classeur(feuilles_en_plus={"Brouillon": [["x"]]}))[0][2]["empreinte"]
    assert a == b  # une feuille non listée ne change pas le référentiel


# ---- par l'API -----------------------------------------------------------------


def televerser(client, entetes, url, contenu, **champs):
    return client.post(
        url,
        headers=entetes,
        files={"fichier": ("socle.xlsx", contenu, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={k: str(v).lower() for k, v in champs.items()},
    )


def test_televersement_bibliotheque(client, admin, session):
    h = admin.entetes()
    r = televerser(client, h, "/api/contenu/televerser", classeur(), simulation=True)
    assert r.status_code == 200 and r.json()[0]["succes"] and r.json()[0]["stats"] == {}
    r = televerser(client, h, "/api/contenu/televerser", classeur())
    res = r.json()[0]
    assert res["succes"] and res["feuille"] == "Guide hygiène" and res["stats"]["exigence"] == 5
    assert any("13.1" in a for a in res["avertissements"])
    assert televerser(client, h, "/api/contenu/televerser", classeur()).json()[0]["deja_importe"]

    detail = client.get("/api/contenu/referentiels/ANSSI-HYG", headers=h).json()
    assert detail["profils"] == ["Standard", "Renforcé"] and detail["arbre"][0]["enfants"][0]["code"] == "1"

    r = client.post("/api/contenu/televerser", headers=h, files={"fichier": ("socle.csv", b"a;b", "text/csv")})
    assert r.status_code == 400

    creer_utilisateur(session, "c@exemple.fr")
    hc = Connexion(client, "c@exemple.fr").entetes()
    assert televerser(client, hc, "/api/contenu/televerser", classeur()).status_code == 403


def test_referentiel_du_client(client, admin, session):
    h = admin.entetes()
    cli = client.post("/api/clients", headers=h, json={"nom": "Client"}).json()
    m = client.post("/api/missions", headers=h, json={"client_id": cli["id"], "titre": "M"}).json()
    infos = [["Guide hygiène", "PSSI-CLIENT", "2026", "PSSI du client", "Client", "Interne", "Exigence", "Oui"]]
    r = televerser(client, h, f"/api/missions/{m['id']}/referentiels/televerser", classeur(infos=infos))
    assert r.json()[0]["succes"], r.json()

    # Visible dans sa mission, absent de la bibliothèque.
    assert [x["code"] for x in client.get(f"/api/missions/{m['id']}/referentiels", headers=h).json()] == ["PSSI-CLIENT"]
    assert "PSSI-CLIENT" not in [x["code"] for x in client.get("/api/contenu/referentiels", headers=h).json()]

    # Un consultant de la mission ne peut pas charger de référentiel.
    u = creer_utilisateur(session, "c@exemple.fr")
    client.put(f"/api/missions/{m['id']}/membres", headers=h, json={"utilisateur_id": u.id, "role": "consultant"})
    hc = Connexion(client, "c@exemple.fr").entetes()
    assert televerser(client, hc, f"/api/missions/{m['id']}/referentiels/televerser", classeur(infos=infos)).status_code == 403
    assert client.get(f"/api/missions/{m['id']}/referentiels/PSSI-CLIENT", headers=hc).status_code == 200
