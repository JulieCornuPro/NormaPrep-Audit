"""API : connexion en deux étapes, comptes, contenu, journal."""

from tests.conftest import MOT_DE_PASSE, Connexion, creer_utilisateur


def test_sante(client):
    assert client.get("/api/sante").json() == {"statut": "ok"}


def test_enrolement_puis_connexion(client, admin):
    r = client.post("/api/auth/connexion", json={"email": "admin@exemple.fr", "mot_de_passe": MOT_DE_PASSE})
    etape = r.json()
    assert etape["etape"] == "enrolement"
    assert etape["uri_totp"].startswith("otpauth://totp/")
    admin.secret = etape["secret"]

    # Pas de jeton d'accès sans TOTP.
    assert client.get("/api/auth/moi", headers={"Authorization": f"Bearer {etape['jeton']}"}).status_code == 401

    r = client.post("/api/auth/totp", json={"jeton": etape["jeton"], "code": admin.code()})
    assert r.status_code == 200
    jeton = r.json()["jeton_acces"]
    moi = client.get("/api/auth/moi", headers={"Authorization": f"Bearer {jeton}"}).json()
    assert moi["email"] == "admin@exemple.fr" and moi["est_admin"]

    # Connexion suivante : TOTP déjà actif, plus de secret renvoyé.
    r = client.post("/api/auth/connexion", json={"email": "admin@exemple.fr", "mot_de_passe": MOT_DE_PASSE})
    assert r.json()["etape"] == "totp" and r.json()["secret"] is None


def test_code_totp_non_rejouable(client, admin):
    admin.jeton()
    code_deja_utilise = admin.dernier_code
    r = client.post("/api/auth/connexion", json={"email": "admin@exemple.fr", "mot_de_passe": MOT_DE_PASSE})
    r = client.post("/api/auth/totp", json={"jeton": r.json()["jeton"], "code": code_deja_utilise})
    assert r.status_code == 401


def test_blocage_apres_echecs(client, admin):
    for _ in range(5):
        r = client.post("/api/auth/connexion", json={"email": "admin@exemple.fr", "mot_de_passe": "mauvais"})
        assert r.status_code == 401
    # Bloqué : même le bon mot de passe est refusé, avec le même message.
    r = client.post("/api/auth/connexion", json={"email": "admin@exemple.fr", "mot_de_passe": MOT_DE_PASSE})
    assert r.status_code == 401
    assert r.json()["detail"] == "Identifiants invalides, ou compte temporairement bloqué."


def test_email_inconnu(client, base):
    r = client.post("/api/auth/connexion", json={"email": "personne@exemple.fr", "mot_de_passe": "x"})
    assert r.status_code == 401


def test_changement_de_mot_de_passe_invalide_les_jetons(client, admin):
    entetes = admin.entetes()
    r = client.post("/api/auth/mot-de-passe", headers=entetes, json={"actuel": MOT_DE_PASSE, "nouveau": "court"})
    assert r.status_code == 400
    r = client.post(
        "/api/auth/mot-de-passe", headers=entetes, json={"actuel": MOT_DE_PASSE, "nouveau": "un autre mot de passe solide"}
    )
    assert r.status_code == 204
    assert client.get("/api/auth/moi", headers=entetes).status_code == 401


def test_gestion_des_comptes(client, admin, session):
    entetes = admin.entetes()
    r = client.post(
        "/api/utilisateurs",
        headers=entetes,
        json={"email": "Consultant@Exemple.fr", "nom": "Consultante", "mot_de_passe": MOT_DE_PASSE},
    )
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    assert r.json()["email"] == "consultant@exemple.fr"

    # Doublon refusé, insensible à la casse.
    r = client.post(
        "/api/utilisateurs", headers=entetes, json={"email": "consultant@exemple.fr", "nom": "x", "mot_de_passe": MOT_DE_PASSE}
    )
    assert r.status_code == 409

    consultant = Connexion(client, "consultant@exemple.fr")
    entetes_c = consultant.entetes()
    assert client.get("/api/utilisateurs", headers=entetes_c).status_code == 403

    # Désactivation : le jeton du consultant ne vaut plus rien.
    r = client.patch(f"/api/utilisateurs/{cid}", headers=entetes, json={"actif": False})
    assert r.status_code == 200 and r.json()["actif"] is False
    assert client.get("/api/auth/moi", headers=entetes_c).status_code == 401

    # Un administrateur ne peut pas se retirer ses propres droits.
    moi = client.get("/api/auth/moi", headers=entetes).json()
    assert client.patch(f"/api/utilisateurs/{moi['id']}", headers=entetes, json={"est_admin": False}).status_code == 400


def test_reinitialisation_totp(client, admin, session):
    entetes = admin.entetes()
    u = creer_utilisateur(session, "c@exemple.fr")
    c = Connexion(client, "c@exemple.fr")
    c.jeton()
    r = client.post(f"/api/utilisateurs/{u.id}/reinitialiser-totp", headers=entetes)
    assert r.json()["totp_actif"] is False
    r = client.post("/api/auth/connexion", json={"email": "c@exemple.fr", "mot_de_passe": MOT_DE_PASSE})
    assert r.json()["etape"] == "enrolement" and r.json()["secret"] != c.secret


def test_import_et_consultation_du_contenu(client, admin):
    entetes = admin.entetes()
    dispo = client.get("/api/contenu/disponibles", headers=entetes).json()
    assert {"nature": "maturite", "chemin": "maturite/demo"} in dispo
    assert {"nature": "audit", "chemin": "referentiels/anssi-hygiene-exemple.json"} in dispo

    r = client.post(
        "/api/contenu/import", headers=entetes, json={"nature": "audit", "chemin": "referentiels/anssi-hygiene-exemple.json"}
    )
    assert r.json()["succes"], r.json()
    r = client.post("/api/contenu/import", headers=entetes, json={"nature": "maturite", "chemin": "maturite/demo"})
    assert r.json()["succes"], r.json()

    refs = client.get("/api/contenu/referentiels", headers=entetes).json()
    assert {(x["code"], x["version"]) for x in refs} == {("ANSSI-HYG", "exemple-0.1"), ("NORMAPREP-MATURITE", "demo-0.2")}

    anssi = client.get("/api/contenu/referentiels/ANSSI-HYG", headers=entetes).json()
    assert [s["code"] for s in anssi["sections"]][:2] == ["S01", "S02"]

    mat = client.get("/api/contenu/referentiels/NORMAPREP-MATURITE", headers=entetes).json()
    i6 = next(st for t in mat["themes"] for st in t["sous_themes"] if st["code"] == "I6")
    assert i6["questions"][0]["correspondances"][0]["code"] == "37"

    cov = client.get("/api/contenu/couverture/ANSSI-HYG", headers=entetes).json()
    assert cov["nb_couvertes"] == 1

    journal = client.get("/api/journal?action=contenu_importe", headers=entetes).json()
    assert len(journal) == 2


def test_import_hors_du_dossier_de_contenu(client, admin):
    entetes = admin.entetes()
    r = client.post("/api/contenu/import", headers=entetes, json={"nature": "audit", "chemin": "../backend/pyproject.toml"})
    assert r.status_code == 400


def test_import_reserve_aux_admins(client, session):
    creer_utilisateur(session, "c@exemple.fr")
    entetes = Connexion(client, "c@exemple.fr").entetes()
    r = client.post("/api/contenu/import", headers=entetes, json={"nature": "maturite", "chemin": "maturite/demo"})
    assert r.status_code == 403
    assert client.get("/api/contenu/referentiels", headers=entetes).status_code == 200
