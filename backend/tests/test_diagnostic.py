"""Diagnostic de maturité, de bout en bout par l'API, sur le référentiel de
démonstration.

Rappel du contenu de démonstration :
- SOCLE (toujours obligatoire) : G3, I6, A4 en essentiel, cible 2 ;
- NIS2-EE : obligatoire si secteur énergie/finance et ETI/GE ; à vérifier si
  P15 = « ne sait pas » ; G3 renforcé cible 4, I6 standard cible 3 ;
- ISO27001 : recommandé (toujours) ;
- questions : G3-Q01 (essentiel), G3-Q02 (renforcé), I6-Q01 (essentiel),
  A4-Q01 (standard).
"""

import pytest

from app.contenu.importeur import importer_audit, importer_maturite
from tests.conftest import ANSSI_EXEMPLE, DEMO_MATURITE, MOT_DE_PASSE, Connexion, creer_utilisateur

PROFIL_PME = {"P01": ["autre"], "P02": ["pme"], "P06": ["aucun"], "P14": ["aucune"]}
PROFIL_NIS2 = {"P01": ["energie"], "P02": ["eti"], "P06": ["aucun"], "P14": ["aucune"], "P15": ["non"]}


@pytest.fixture
def env(client, session, admin):
    assert importer_audit(session, ANSSI_EXEMPLE).succes
    assert importer_maturite(session, DEMO_MATURITE).succes
    h = admin.entetes()
    cli = client.post("/api/clients", headers=h, json={"nom": "Client démo", "secteur": "Industrie"}).json()
    mission = client.post("/api/missions", headers=h, json={"client_id": cli["id"], "titre": "Diagnostic 2026"}).json()
    diag = client.post(f"/api/missions/{mission['id']}/diagnostics", headers=h).json()

    class Env:
        pass

    e = Env()
    e.h, e.mission, e.diag = h, mission, diag["id"]
    e.url = f"/api/diagnostics/{diag['id']}"
    return e


def profiler(client, env, profil):
    r = client.put(f"{env.url}/profilage", headers=env.h, json={"reponses": profil})
    assert r.status_code == 200, r.text
    return r.json()


def regs(vue):
    return {r["code"]: (r["niveau_calcule"], r["decision"]) for r in vue["reglementations"]}


def refs(client, env):
    q = client.get(f"{env.url}/questionnaire", headers=env.h).json()
    return [x["ref"] for t in q["themes"] for st in t["sous_themes"] for x in st["questions"]]


def repondre(client, env, ref, niveau=None, na=False):
    r = client.put(f"{env.url}/reponses/{ref}", headers=env.h, json={"niveau": niveau, "non_applicable": na})
    assert r.status_code == 200, r.text


# ---- profilage ----------------------------------------------------------------


def test_profil_pme(client, env):
    vue = profiler(client, env, PROFIL_PME)
    assert regs(vue) == {"SOCLE": ("obligatoire", "retenue"), "ISO27001": ("recommande", "ecartee")}
    # P15 est masquée quand le secteur est « autre ».
    p15 = next(q for q in vue["questions"] if q["code"] == "P15")
    assert p15["visible"] is False and vue["sans_reponse"] == []
    # Profondeur essentielle partout : A4-Q01 (standard) et G3-Q02 (renforcé) ne sont pas posées.
    assert refs(client, env) == ["G3-Q01", "I6-Q01"]


def test_profil_nis2_releve_profondeur_et_cible(client, env):
    vue = profiler(client, env, PROFIL_NIS2)
    assert regs(vue)["NIS2-EE"] == ("obligatoire", "retenue")
    assert refs(client, env) == ["G3-Q01", "G3-Q02", "I6-Q01"]
    q = client.get(f"{env.url}/questionnaire", headers=env.h).json()
    g3 = q["themes"][0]["sous_themes"][0]
    assert (g3["profondeur"], g3["cible"], g3["reglementation"]) == ("renforce", 4.0, "NIS2 : entité essentielle")


def test_choix_invalides_ignores(client, env):
    vue = profiler(client, env, {**PROFIL_PME, "P01": ["autre", "energie"], "PXX": ["?"], "P02": ["inconnu"]})
    assert vue["reponses"]["P01"] == ["autre"]  # choix unique : le premier
    assert "P02" not in vue["reponses"] and "PXX" not in vue["reponses"]
    assert vue["sans_reponse"] == ["P02"]


def test_a_verifier_puis_arbitrage(client, env):
    vue = profiler(client, env, {**PROFIL_PME, "P01": ["services_num"], "P15": ["ne_sait_pas"]})
    assert regs(vue)["NIS2-EE"] == ("a_verifier", "en_attente")
    assert client.get(env.url, headers=env.h).json()["reglementations_en_attente"] == ["NIS2-EE"]

    # Confirmer sans justification : refusé.
    r = client.put(f"{env.url}/reglementations", headers=env.h, json={"decisions": {"NIS2-EE": {"decision": "retenue"}}})
    assert r.status_code == 400 and "justification" in r.json()["detail"][0]

    r = client.put(
        f"{env.url}/reglementations",
        headers=env.h,
        json={"decisions": {"NIS2-EE": {"decision": "retenue", "justification": "Désignée par l'ANSSI en 2025."}}},
    )
    assert regs(r.json())["NIS2-EE"] == ("a_verifier", "retenue")
    assert "G3-Q02" in refs(client, env)


def test_decision_du_consultant_preservee(client, env):
    profiler(client, env, PROFIL_PME)
    r = client.put(f"{env.url}/reglementations", headers=env.h, json={"decisions": {"ISO27001": {"decision": "retenue"}}})
    assert regs(r.json())["ISO27001"] == ("recommande", "retenue")
    # Le profilage change : l'objectif ISO choisi par le consultant reste retenu.
    vue = profiler(client, env, {**PROFIL_PME, "P02": ["tpe"]})
    assert regs(vue)["ISO27001"] == ("recommande", "retenue")
    assert "A4-Q01" in refs(client, env)  # ISO27001 exige A4 en standard


def test_ajout_manuel_d_une_reglementation(client, env):
    profiler(client, env, PROFIL_PME)
    r = client.put(f"{env.url}/reglementations", headers=env.h, json={"ajout": "DORA"})
    assert r.status_code == 400
    r = client.put(
        f"{env.url}/reglementations",
        headers=env.h,
        json={"ajout": "DORA", "justification_ajout": "Exigé par un client bancaire."},
    )
    dora = next(x for x in r.json()["reglementations"] if x["code"] == "DORA")
    assert (dora["origine"], dora["decision"]) == ("forcage", "retenue")
    # Écarter un ajout manuel le retire.
    r = client.put(f"{env.url}/reglementations", headers=env.h, json={"decisions": {"DORA": {"decision": "ecartee"}}})
    assert "DORA" not in regs(r.json())


# ---- résultats ------------------------------------------------------------------


def test_scores_ecarts_et_recommandations(client, env):
    profiler(client, env, PROFIL_PME)
    repondre(client, env, "G3-Q01", 1)
    repondre(client, env, "I6-Q01", 2)
    res = client.get(f"{env.url}/resultats", headers=env.h).json()

    g, i, a = res["themes"]
    assert (g["score"], g["cible"], g["ecart"]) == (1.0, 2.0, 1.0)
    assert (i["score"], i["cible"], i["ecart"]) == (2.0, 2.0, 0.0)
    assert a["score"] is None  # aucune question posée
    assert res["global"] == {"score": 1.5, "cible": 2.0, "ecart": 0.5}

    reco = [r["ref"] for r in res["recommandations"]]
    # G3 (écart 1) avant I6 (écart 0) ; dans G3, la recommandation quick win d'abord.
    assert reco == ["G3-R1", "G3-Q01-R1", "I6-Q01-R1"]
    audits = {a["code"]: a for a in res["audits_proposes"]}
    assert set(audits) == {"EBIOS-RM", "AUDIT-ANSSI"}
    assert (audits["AUDIT-ANSSI"]["referentiel_audit"], audits["AUDIT-ANSSI"]["sections"]) == ("ANSSI-HYG", ["37"])


def test_non_applicable_exclu_des_calculs(client, env):
    profiler(client, env, PROFIL_PME)
    repondre(client, env, "G3-Q01", 3)
    repondre(client, env, "I6-Q01", na=True)
    res = client.get(f"{env.url}/resultats", headers=env.h).json()
    i6 = res["themes"][1]["sous_themes"][0]
    assert i6["non_applicable"] is True and i6["score"] is None
    assert res["global"]["score"] == 3.0
    assert res["progression"] == {"retenues": 2, "repondues": 2, "restantes": 0}


def test_question_non_posee_refusee(client, env):
    profiler(client, env, PROFIL_PME)
    r = client.put(f"{env.url}/reponses/A4-Q01", headers=env.h, json={"niveau": 2})
    assert r.status_code == 404


def test_finalisation(client, env):
    r = client.post(f"{env.url}/finaliser", headers=env.h)
    assert r.status_code == 409 and "profilage" in r.json()["detail"][0]

    profiler(client, env, PROFIL_PME)
    repondre(client, env, "G3-Q01", 2)
    r = client.post(f"{env.url}/finaliser", headers=env.h)
    assert r.status_code == 409 and "1 question(s) sans réponse" in r.json()["detail"][0]

    repondre(client, env, "I6-Q01", 4)
    r = client.post(f"{env.url}/finaliser", headers=env.h)
    assert r.status_code == 200 and r.json()["fige"] is True

    # Figé : plus de saisie, résultats conservés.
    assert client.put(f"{env.url}/reponses/G3-Q01", headers=env.h, json={"niveau": 5}).status_code == 409
    assert client.get(f"{env.url}/resultats", headers=env.h).json()["global"]["score"] == 3.0

    assert client.post(f"{env.url}/rouvrir", headers=env.h).json() == {"statut": "en_cours"}
    repondre(client, env, "G3-Q01", 5)


# ---- ateliers et pré-questionnaire ---------------------------------------------


def test_plan_d_ateliers(client, env):
    profiler(client, env, PROFIL_NIS2)
    p = client.get(f"{env.url}/ateliers", headers=env.h).json()
    # G3 (direction, rssi) et I6 (dsi, administrateurs) : deux ateliers distincts.
    assert [(a["interlocuteurs"], [q["ref"] for q in a["questions"]]) for a in p["ateliers"]] == [
        (["direction", "rssi"], ["G3-Q01", "G3-Q02"]),
        (["administrateurs", "dsi"], ["I6-Q01"]),
    ]
    # G3-Q01 : 3 min (type niveaux), G3-Q02 : 1 min (fermée), + 15 min d'ouverture.
    assert p["ateliers"][0]["duree_minutes"] == 19

    # I6-Q01 part au pré-questionnaire : il ne reste qu'un atelier.
    client.put(f"{env.url}/questions/I6-Q01/mode", headers=env.h, json={"mode": "pre_questionnaire"})
    p = client.get(f"{env.url}/ateliers", headers=env.h).json()
    assert len(p["ateliers"]) == 1
    assert [q["ref"] for q in p["hors_atelier"]["pre_questionnaire"]] == ["I6-Q01"]


def test_decoupage_selon_le_budget(client, env):
    profiler(client, env, PROFIL_NIS2)
    # Budget minimal : 30 min dont 28 d'ouverture → 2 min utiles, G3 (4 min) est coupé.
    client.put(f"{env.url}/parametres", headers=env.h, json={"budget_atelier_minutes": 30, "ouverture_minutes": 28})
    p = client.get(f"{env.url}/ateliers", headers=env.h).json()
    assert [[q["ref"] for q in a["questions"]] for a in p["ateliers"]] == [["G3-Q01"], ["G3-Q02"], ["I6-Q01"]]
    assert p["depassements"] == [1, 3]  # une question de 3 min dépasse seule le budget utile


def test_pre_questionnaire(client, env):
    profiler(client, env, PROFIL_PME)
    client.put(f"{env.url}/questions/I6-Q01/mode", headers=env.h, json={"mode": "pre_questionnaire"})
    lien = client.post(f"{env.url}/liens", headers=env.h, json={"destinataire": "DSI", "jours": 7}).json()
    jeton = lien["jeton"]

    # Accès client, sans compte.
    page = client.get(f"/api/public/pre-questionnaire/{jeton}").json()
    assert page["mission"] == "Diagnostic 2026" and [q["ref"] for q in page["questions"]] == ["I6-Q01"]
    r = client.put(f"/api/public/pre-questionnaire/{jeton}/reponses/I6-Q01", json={"niveau": 3, "commentaire": "NAS + bandes"})
    assert r.status_code == 200
    assert client.put(f"/api/public/pre-questionnaire/{jeton}/reponses/G3-Q01", json={"niveau": 1}).status_code == 404

    # Le consultant voit la proposition, sans qu'elle soit sa réponse.
    q = client.get(f"{env.url}/questionnaire", headers=env.h).json()
    i6 = q["themes"][1]["sous_themes"][0]["questions"][0]["reponse"]
    assert i6["niveau"] is None and i6["proposition"]["niveau"] == 3

    # Lien révoqué : inaccessible ; seul l'empreinte du jeton est en base.
    client.delete(f"{env.url}/liens/{lien['id']}", headers=env.h)
    assert client.get(f"/api/public/pre-questionnaire/{jeton}").status_code == 404
    assert "jeton" not in client.get(f"{env.url}/liens", headers=env.h).json()[0]
    assert client.get("/api/public/pre-questionnaire/jeton-invente").status_code == 404


# ---- droits ---------------------------------------------------------------------


def test_droits_sur_la_mission(client, session, env):
    creer_utilisateur(session, "externe@exemple.fr")
    relectrice = creer_utilisateur(session, "relectrice@exemple.fr")
    h_ext = Connexion(client, "externe@exemple.fr").entetes()
    h_rel = Connexion(client, "relectrice@exemple.fr").entetes()

    # Non-membre : la mission n'existe pas pour lui.
    assert client.get(f"/api/missions/{env.mission['id']}", headers=h_ext).status_code == 404
    assert client.get(env.url, headers=h_ext).status_code == 404
    assert client.get("/api/missions", headers=h_ext).json() == []

    r = client.put(
        f"/api/missions/{env.mission['id']}/membres", headers=env.h, json={"utilisateur_id": relectrice.id, "role": "relecteur"}
    )
    assert r.status_code == 200
    profiler(client, env, PROFIL_PME)
    assert client.get(f"{env.url}/resultats", headers=h_rel).status_code == 200
    assert client.put(f"{env.url}/reponses/G3-Q01", headers=h_rel, json={"niveau": 2}).status_code == 403
    assert client.post(f"{env.url}/finaliser", headers=h_rel).status_code == 403

    # Le dernier responsable ne peut pas partir.
    admin_id = client.get("/api/auth/moi", headers=env.h).json()["id"]
    r = client.delete(f"/api/missions/{env.mission['id']}/membres/{admin_id}", headers=env.h)
    assert r.status_code == 400


def test_qr_code_a_l_enrolement(client, session):
    creer_utilisateur(session, "nouveau@exemple.fr")
    r = client.post("/api/auth/connexion", json={"email": "nouveau@exemple.fr", "mot_de_passe": MOT_DE_PASSE}).json()
    assert r["qr_svg"].startswith("<svg")


def test_messages_quand_le_profil_a_change(client, env):
    """Décision sur une réglementation qui ne ressort plus, ajout d'une
    réglementation que le profil fait désormais ressortir : messages clairs."""
    profiler(client, env, {**PROFIL_PME, "P01": ["finance"]})
    profiler(client, env, PROFIL_NIS2)  # DORA disparaît, NIS2-EE apparaît
    r = client.put(
        f"{env.url}/reglementations",
        headers=env.h,
        json={"decisions": {"DORA": {"decision": "ecartee"}}, "ajout": "NIS2-EE", "justification_ajout": "x"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == [
        "DORA ne ressort plus du profilage (le profil a changé) : rechargez la page.",
        "NIS2 : entité essentielle figure déjà dans la liste (le profil l'a fait ressortir) : inutile de l'ajouter.",
    ]
