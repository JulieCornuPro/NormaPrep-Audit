"""Profilage réglementaire (port de NPD_Profilage, NormaPrep Diagnostic).

1. Les réponses de profilage déclenchent des règles ; chaque réglementation
   ressort avec le niveau le plus fort de ses règles vérifiées : obligatoire,
   à vérifier ou recommandé.
2. Le consultant arbitre : il tranche les « à vérifier », retient des
   objectifs recommandés, écarte ou ajoute une réglementation (avec
   justification).
3. Les réglementations retenues fixent, par sous-thème, la profondeur du
   questionnaire et la maturité cible (le maximum de chacune).

Quand le profilage change, les décisions prises par le consultant sont
préservées ; celles restées à leur valeur par défaut suivent le calcul.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.diagnostic.contenu import RANG_NIVEAU, RANG_PROFONDEUR, ContenuMaturite
from app.models import Diagnostic, DiagReglementation

DECISIONS = ("retenue", "ecartee", "en_attente")


class ErreurArbitrage(ValueError):
    def __init__(self, erreurs: list[str]) -> None:
        super().__init__("; ".join(erreurs))
        self.erreurs = erreurs


# ---- conditions -------------------------------------------------------------


def evaluer(condition: Any, reponses: dict[str, list[str]]) -> bool:
    if not isinstance(condition, dict) or len(condition) != 1:
        return False
    cle, valeur = next(iter(condition.items()))
    if cle == "toujours":
        return valeur is True
    if cle == "tous":
        return isinstance(valeur, list) and bool(valeur) and all(evaluer(c, reponses) for c in valeur)
    if cle == "un_parmi":
        return isinstance(valeur, list) and any(evaluer(c, reponses) for c in valeur)
    if cle == "non":
        return not evaluer(valeur, reponses)
    # Feuille : la question a reçu au moins un des choix cités.
    return isinstance(valeur, list) and bool(set(reponses.get(cle, [])) & set(valeur))


def nettoyer_reponses(soumises: dict[str, Any], contenu: ContenuMaturite) -> dict[str, list[str]]:
    """Ne garde que les questions affichées (conditions évaluées dans l'ordre)
    et les choix existants ; un seul choix pour une question à choix unique."""
    propres: dict[str, list[str]] = {}
    for q in contenu.profil:
        if q["condition"] is not None and not evaluer(q["condition"], propres):
            continue
        valeurs = soumises.get(q["code"], [])
        if not isinstance(valeurs, list):
            valeurs = [valeurs]
        codes = {c["code"] for c in q["choix"]}
        retenues: list[str] = []
        for v in valeurs:
            if isinstance(v, str) and v in codes and v not in retenues:
                retenues.append(v)
        if q["type"] == "choix_unique":
            retenues = retenues[:1]
        if retenues:
            propres[q["code"]] = retenues
    return propres


def questions_visibles(reponses: dict[str, list[str]], contenu: ContenuMaturite) -> list[str]:
    return [q["code"] for q in contenu.profil if q["condition"] is None or evaluer(q["condition"], reponses)]


def questions_sans_reponse(reponses: dict[str, list[str]], contenu: ContenuMaturite) -> list[str]:
    return [c for c in questions_visibles(reponses, contenu) if not reponses.get(c)]


def calculer(reponses: dict[str, list[str]], contenu: ContenuMaturite) -> dict[str, dict[str, str]]:
    """{code réglementation: {niveau, critere}} pour les réglementations dont
    au moins une règle est vérifiée. À niveau égal, la règle de plus forte
    priorité (puis la première déclarée) garde la main."""
    resultat: dict[str, dict[str, str]] = {}
    for code, reg in contenu.reglementations.items():
        regles = sorted(enumerate(reg["regles"]), key=lambda x: (-int(x[1].get("priorite", 0)), x[0]))
        for _, r in regles:
            if not evaluer(r.get("conditions"), reponses):
                continue
            rang = RANG_NIVEAU.get(r["niveau"], 0)
            actuel = RANG_NIVEAU[resultat[code]["niveau"]] if code in resultat else 0
            if rang > actuel:
                resultat[code] = {"niveau": r["niveau"], "critere": r.get("critere", "")}
    return resultat


# ---- décisions ----------------------------------------------------------------


def decision_par_defaut(niveau: str) -> str:
    return {"obligatoire": "retenue", "a_verifier": "en_attente"}.get(niveau, "ecartee")


def justification_requise(origine: str, niveau: str, decision: str) -> bool:
    if origine == "forcage":
        return decision == "retenue"
    if niveau == "a_verifier":
        return decision != "en_attente"
    if niveau == "obligatoire":
        return decision == "ecartee"
    return False


def decision_du_consultant(ligne: DiagReglementation) -> bool:
    return (
        ligne.origine == "forcage"
        or ligne.decision != decision_par_defaut(ligne.niveau_calcule)
        or bool(ligne.justification.strip())
    )


def lignes(session: Session, diagnostic_id: int) -> list[DiagReglementation]:
    return list(session.scalars(select(DiagReglementation).where(DiagReglementation.diagnostic_id == diagnostic_id)))


def synchroniser(session: Session, diag: Diagnostic, calcul: dict[str, dict[str, str]]) -> None:
    existantes = {ligne.reglementation_code: ligne for ligne in lignes(session, diag.id)}

    for code, c in calcul.items():
        ligne = existantes.get(code)
        if ligne is None:
            session.add(
                DiagReglementation(
                    diagnostic_id=diag.id,
                    reglementation_code=code,
                    niveau_calcule=c["niveau"],
                    decision=decision_par_defaut(c["niveau"]),
                    origine="calcul",
                    critere=c["critere"],
                )
            )
            continue
        # Décision restée par défaut : elle suit le calcul. Sinon elle est gardée.
        decision = ligne.decision if decision_du_consultant(ligne) else decision_par_defaut(c["niveau"])
        ligne.niveau_calcule = c["niveau"]
        ligne.decision = decision
        ligne.origine = "calcul"
        ligne.critere = c["critere"]

    for code, ligne in existantes.items():
        if code in calcul or ligne.origine == "forcage":
            continue
        if ligne.decision == "retenue" and decision_du_consultant(ligne):
            # Retenue par le consultant : on ne la retire pas en silence.
            ligne.origine = "forcage"
            ligne.critere = "Ne ressort plus du profilage ; maintenue jusqu'à décision du consultant."
        else:
            session.delete(ligne)
    session.flush()


def enregistrer_profil(session: Session, diag: Diagnostic, soumises: dict[str, Any], contenu: ContenuMaturite) -> None:
    diag.profil = nettoyer_reponses(soumises, contenu)
    synchroniser(session, diag, calculer(diag.profil, contenu))


def arbitrer(
    session: Session,
    diag: Diagnostic,
    decisions: dict[str, dict[str, str]],
    contenu: ContenuMaturite,
    ajout: str | None = None,
    justification_ajout: str = "",
) -> None:
    """Applique les décisions du consultant. Tout ou rien : ErreurArbitrage
    liste les problèmes et rien n'est modifié."""
    erreurs: list[str] = []
    existantes = {ligne.reglementation_code: ligne for ligne in lignes(session, diag.id)}
    maj: dict[str, tuple[str, str]] = {}

    for code, d in decisions.items():
        ligne = existantes.get(code)
        if ligne is None:
            erreurs.append(f"{code} : réglementation absente de ce diagnostic.")
            continue
        libelle = contenu.reglementations.get(code, {}).get("libelle", code)
        decision = str(d.get("decision", ligne.decision))
        justification = str(d.get("justification", "")).strip()
        admises = DECISIONS if (ligne.origine == "calcul" and ligne.niveau_calcule == "a_verifier") else ("retenue", "ecartee")
        if decision not in admises:
            erreurs.append(f"{libelle} : décision invalide.")
            continue
        if justification_requise(ligne.origine, ligne.niveau_calcule, decision) and not justification:
            erreurs.append(f"{libelle} : une justification est nécessaire pour cette décision.")
            continue
        maj[code] = (decision, justification)

    if ajout:
        if ajout not in contenu.reglementations or ajout in existantes:
            erreurs.append("Réglementation à ajouter introuvable ou déjà présente.")
        elif not justification_ajout.strip():
            erreurs.append(
                f"{contenu.reglementations[ajout]['libelle']} : une justification est nécessaire pour ajouter une réglementation."
            )

    if erreurs:
        raise ErreurArbitrage(erreurs)

    for code, (decision, justification) in maj.items():
        ligne = existantes[code]
        if ligne.origine == "forcage" and decision == "ecartee":
            session.delete(ligne)  # écarter un ajout manuel revient à le retirer
            continue
        ligne.decision = decision
        ligne.justification = justification
    if ajout:
        session.add(
            DiagReglementation(
                diagnostic_id=diag.id,
                reglementation_code=ajout,
                niveau_calcule="recommande",
                decision="retenue",
                origine="forcage",
                critere="Ajoutée par le consultant.",
                justification=justification_ajout.strip(),
            )
        )
    session.flush()


def vue_reglementations(session: Session, diag: Diagnostic, contenu: ContenuMaturite) -> list[dict[str, Any]]:
    """Lignes triées : obligatoires, à vérifier, recommandées, puis ajouts."""

    def rang(ligne: DiagReglementation) -> int:
        return 0 if ligne.origine == "forcage" else RANG_NIVEAU.get(ligne.niveau_calcule, 0)

    resultat = []
    for ligne in sorted(
        lignes(session, diag.id),
        key=lambda x: (-rang(x), contenu.reglementations.get(x.reglementation_code, {}).get("ordre", 0)),
    ):
        reg = contenu.reglementations.get(ligne.reglementation_code, {})
        resultat.append(
            {
                "code": ligne.reglementation_code,
                "libelle": reg.get("libelle", ligne.reglementation_code),
                "nature": reg.get("nature", ""),
                "description": reg.get("description", ""),
                "echeance": reg.get("echeance", ""),
                "niveau_calcule": ligne.niveau_calcule,
                "decision": ligne.decision,
                "origine": ligne.origine,
                "critere": ligne.critere,
                "justification": ligne.justification,
                "decisions_admises": list(DECISIONS)
                if (ligne.origine == "calcul" and ligne.niveau_calcule == "a_verifier")
                else ["retenue", "ecartee"],
            }
        )
    return resultat


def exigences(session: Session, diag: Diagnostic, contenu: ContenuMaturite) -> dict[str, dict[str, Any]]:
    """Par sous-thème : profondeur requise (essentiel par défaut), cible (None
    si aucune réglementation retenue ne l'exige) et réglementation qui la fixe."""
    resultat = {code: {"profondeur": "essentiel", "cible": None, "reglementation": None} for code in contenu.sous_themes}
    retenues = [
        contenu.reglementations[ligne.reglementation_code]
        for ligne in lignes(session, diag.id)
        if ligne.decision == "retenue" and ligne.reglementation_code in contenu.reglementations
    ]
    for reg in sorted(retenues, key=lambda r: r["ordre"]):
        for st, e in reg["exigences"].items():
            if st not in resultat:
                continue
            r = resultat[st]
            if RANG_PROFONDEUR[e["profondeur"]] > RANG_PROFONDEUR[r["profondeur"]]:
                r["profondeur"] = e["profondeur"]
            if r["cible"] is None or float(e["cible"]) > r["cible"]:
                r["cible"] = float(e["cible"])
                r["reglementation"] = reg["libelle"]
    return resultat
