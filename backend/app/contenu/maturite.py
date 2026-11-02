"""Validation d'un référentiel de maturité au format NormaPrep.

Port du validateur PHP de NormaPrep Diagnostic (mêmes fichiers, mêmes règles,
mêmes messages), étendu :

- `_referentiel.json` accepte un `code` (défaut : NORMAPREP-MATURITE) ;
- une question accepte les champs de découpage en ateliers (`type`, `duree`,
  `mode`, `interlocuteurs`) et des `correspondances` vers un référentiel
  d'audit (avec seuils de présomption) ;
- une prestation accepte `referentiel_audit` et `sections` (câblage vers un
  type d'audit).

Les références vers d'autres référentiels (correspondances, prestations) sont
vérifiées à l'import, contre la base : voir `importeur.py`.

Le résultat est un modèle normalisé (dictionnaires aux clés fixes) que
l'importeur écrit sans revérifier.
"""

from pathlib import Path
from typing import Any

from app.contenu.outils import (
    INTERLOCUTEURS,
    MODES,
    PROFONDEURS,
    TYPES_QUESTION,
    Rapport,
    empreinte_fichiers,
    lire_json,
)

NIVEAUX_REGLE = ("obligatoire", "a_verifier", "recommande")
NATURES = ("legale", "referentiel")
EFFORTS = ("faible", "moyen", "eleve")
TYPES_PROFIL = ("choix_unique", "choix_multiple")

F_REFERENTIEL = "_referentiel.json"
F_PROFILAGE = "_profilage.json"
F_REGLEMENTATIONS = "_reglementations.json"
F_PRESTATIONS = "_prestations.json"

CODE_PAR_DEFAUT = "NORMAPREP-MATURITE"


def analyser(dossier: Path) -> tuple[Rapport, dict[str, Any] | None]:
    """Lit et valide le dossier. Renvoie le rapport et le modèle (None si invalide)."""
    v = _Validateur(dossier)
    modele = v.executer()
    return v.rapport, (modele if v.rapport.valide else None)


class _Validateur:
    def __init__(self, dossier: Path) -> None:
        self.dossier = dossier
        self.rapport = Rapport()
        self.fichiers: list[str] = []

    # ------------------------------------------------------------------
    def executer(self) -> dict[str, Any]:
        r = self.rapport
        modele: dict[str, Any] = {
            "referentiel": {},
            "themes": {},
            "sous_themes": {},
            "prestations": {},
            "profil": {},
            "reglementations": {},
        }
        if not self.dossier.is_dir():
            r.erreur("dossier", f"Dossier introuvable : {self.dossier}.")
            return modele

        ref = self._lire(F_REFERENTIEL, True)
        pro = self._lire(F_PROFILAGE, True)
        reg = self._lire(F_REGLEMENTATIONS, True)
        pre = self._lire(F_PRESTATIONS, False)

        if ref is not None:
            self._referentiel(ref, modele)
        if pre is not None:
            self._prestations(pre, modele)
        for relatif in self._fichiers_sous_themes():
            contenu = self._lire(relatif, True)
            if contenu is not None:
                self._sous_theme(contenu, relatif, modele)
        if pro is not None:
            self._profilage(pro, modele)
        if reg is not None:
            self._reglementations(reg, modele)

        self._controles_globaux(modele)

        if r.valide:
            modele["referentiel"]["empreinte"] = empreinte_fichiers(self.dossier, self.fichiers)
            modele["referentiel"]["fichiers"] = sorted(self.fichiers)
        return modele

    # ---- fichiers -----------------------------------------------------
    def _lire(self, relatif: str, obligatoire: bool) -> Any:
        chemin = self.dossier / relatif
        if chemin.is_file():
            self.fichiers.append(relatif)
        contenu = lire_json(chemin, relatif, self.rapport, obligatoire)
        if contenu is not None and not isinstance(contenu, dict):
            self.rapport.erreur(relatif, "Le fichier doit contenir un objet JSON.")
            return None
        return contenu

    def _fichiers_sous_themes(self) -> list[str]:
        """Tous les .json des sous-dossiers, hors fichiers et dossiers en « _ » ou « . »."""
        liste = []
        for sous in sorted(self.dossier.iterdir()):
            if not sous.is_dir() or sous.name[0] in "._":
                continue
            for f in sorted(sous.iterdir()):
                if f.is_file() and f.suffix == ".json" and f.name[0] not in "._":
                    liste.append(f"{sous.name}/{f.name}")
        return sorted(liste)

    # ---- référentiel et thèmes ----------------------------------------
    def _referentiel(self, d: dict[str, Any], modele: dict[str, Any]) -> None:
        r, f = self.rapport, F_REFERENTIEL
        version = r.texte(d, "version")
        if not version:
            r.erreur(f, "Champ « version » obligatoire.")
        elif len(version) > 30:
            r.erreur(f, "La version dépasse 30 caractères.")
        code = CODE_PAR_DEFAUT
        if "code" in d:
            code = r.code(d, "code", f, 50) or CODE_PAR_DEFAUT
        modele["referentiel"] = {
            "code": code,
            "version": version,
            "libelle": r.texte(d, "libelle") or "Référentiel de maturité",
            "source": r.texte(d, "source"),
            "licence": r.texte(d, "licence"),
        }

        themes = d.get("themes")
        if not isinstance(themes, list) or not themes:
            r.erreur(f, "Liste « themes » obligatoire et non vide.")
            return
        for i, t in enumerate(themes):
            ou = f"{f} › themes[{i}]"
            c = r.code(t, "code", ou, 10)
            if c is None:
                continue
            if c in modele["themes"]:
                r.erreur(ou, f"Thème « {c} » déclaré deux fois.")
                continue
            modele["themes"][c] = {
                "code": c,
                "libelle": r.texte_obligatoire(t, "libelle", ou),
                "couleur": r.texte(t, "couleur"),
                "ordre": _entier(t.get("ordre"), i + 1),
                "poids": r.poids(t, ou),
            }

    # ---- prestations ----------------------------------------------------
    def _prestations(self, d: dict[str, Any], modele: dict[str, Any]) -> None:
        r, f = self.rapport, F_PRESTATIONS
        liste = d.get("prestations", [])
        if not isinstance(liste, list):
            r.erreur(f, "« prestations » doit être une liste.")
            return
        for i, p in enumerate(liste):
            ou = f"{f} › prestations[{i}]"
            c = r.code(p, "code", ou, 50)
            if c is None:
                continue
            if c in modele["prestations"]:
                r.erreur(ou, f"Prestation « {c} » déclarée deux fois.")
                continue
            ref_audit = None
            if r.texte(p, "referentiel_audit"):
                ref_audit = r.code(p, "referentiel_audit", ou, 50)
            sections = r.liste_textes(p, "sections", ou)
            if sections and not ref_audit:
                r.erreur(ou, "« sections » exige « referentiel_audit ».")
            modele["prestations"][c] = {
                "code": c,
                "libelle": r.texte_obligatoire(p, "libelle", ou),
                "description": r.texte(p, "description"),
                "lien": r.texte(p, "lien"),
                "referentiel_audit": ref_audit,
                "sections": sections,
                "ou": ou,
            }

    # ---- sous-thèmes, questions, recommandations --------------------------
    def _sous_theme(self, d: dict[str, Any], f: str, modele: dict[str, Any]) -> None:
        r = self.rapport
        st = d.get("sous_theme")
        if not isinstance(st, dict):
            r.erreur(f, "Bloc « sous_theme » obligatoire.")
            return
        code = r.code(st, "code", f, 20)
        if code is None:
            return
        if code in modele["sous_themes"]:
            r.erreur(f, f"Sous-thème « {code} » déjà déclaré dans {modele['sous_themes'][code]['fichier']}.")
            return
        theme = r.texte(st, "theme")
        if theme not in modele["themes"]:
            r.erreur(f, f"Thème « {theme} » inconnu (voir {F_REFERENTIEL}).")

        sous_theme: dict[str, Any] = {
            "code": code,
            "theme": theme,
            "libelle": r.texte_obligatoire(st, "libelle", f),
            "description": r.texte(st, "description"),
            "ordre": _entier(st.get("ordre"), 0),
            "poids": r.poids(st, f),
            "fichier": f,
            "questions": {},
            "recommandations": {},
        }

        questions = d.get("questions", [])
        if not isinstance(questions, list):
            r.erreur(f, "« questions » doit être une liste.")
            questions = []
        for i, q in enumerate(questions):
            ou = f"{f} › questions[{i}]"
            ref = r.code(q, "ref", ou, 30)
            if ref is None:
                continue
            ou = f"{f} › {ref}"
            if not ref.startswith(f"{code}-Q"):
                r.erreur(ou, f"La référence doit commencer par « {code}-Q ».")
            if ref in sous_theme["questions"]:
                r.erreur(ou, "Question déclarée deux fois.")
                continue
            sous_theme["questions"][ref] = {
                "ref": ref,
                "enonce": r.texte_obligatoire(q, "enonce", ou),
                "aide": r.texte(q, "aide"),
                "profondeur": r.parmi(q, "profondeur", PROFONDEURS, ou),
                "poids": r.poids(q, ou),
                "references": r.liste_textes(q, "references", ou),
                "ordre": i + 1,
                "niveaux": self._niveaux(q, ou),
                "type_question": r.parmi(q, "type", TYPES_QUESTION, ou, defaut="niveaux"),
                "duree_estimee": self._duree(q, ou),
                "mode": r.parmi(q, "mode", MODES, ou, defaut="atelier"),
                "interlocuteurs": r.liste_parmi(q, "interlocuteurs", INTERLOCUTEURS, ou),
                "correspondances": r.correspondances(q, ou, avec_seuils=True),
            }
            for j, rec in enumerate(r.liste(q, "recommandations", ou)):
                self._recommandation(rec, ref, ref, f"{ou} › recommandations[{j}]", sous_theme)

        if not sous_theme["questions"]:
            r.avertir(f, "Aucune question.")

        for j, rec in enumerate(r.liste(d, "recommandations", f)):
            self._recommandation(rec, code, None, f"{f} › recommandations[{j}]", sous_theme)

        modele["sous_themes"][code] = sous_theme

    def _niveaux(self, q: dict[str, Any], ou: str) -> dict[str, str]:
        r = self.rapport
        niveaux = q.get("niveaux")
        if not isinstance(niveaux, dict):
            r.erreur(ou, "Bloc « niveaux » obligatoire (descriptions des niveaux 0 à 5).")
            return {}
        propres = {}
        for n in range(6):
            v = niveaux.get(str(n))
            texte = str(v).strip() if isinstance(v, (str, int, float)) else ""
            if not texte:
                r.erreur(ou, f"Description du niveau {n} manquante.")
            propres[str(n)] = texte
        for cle in niveaux:
            if cle not in ("0", "1", "2", "3", "4", "5"):
                r.erreur(ou, f"Niveau « {cle} » inattendu : seuls 0 à 5 existent.")
        return propres

    def _duree(self, q: dict[str, Any], ou: str) -> float | None:
        if "duree" not in q:
            return None
        v = q["duree"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 < v <= 120:
            self.rapport.erreur(ou, "« duree » doit être un nombre de minutes, supérieur à 0 et au plus 120.")
            return None
        return float(v)

    def _recommandation(self, rec: Any, prefixe: str, question_ref: str | None, ou: str, sous_theme: dict[str, Any]) -> None:
        r = self.rapport
        if not isinstance(rec, dict):
            r.erreur(ou, "Recommandation mal formée.")
            return
        ref = r.code(rec, "ref", ou, 40)
        if ref is None:
            return
        if not ref.startswith(f"{prefixe}-R"):
            r.erreur(ou, f"La référence « {ref} » doit commencer par « {prefixe}-R ».")
        if ref in sous_theme["recommandations"]:
            r.erreur(ou, f"Recommandation « {ref} » déclarée deux fois.")
            return
        seuil = rec.get("seuil")
        if isinstance(seuil, bool) or not isinstance(seuil, int) or not 1 <= seuil <= 5:
            r.erreur(ou, "« seuil » doit être un entier de 1 à 5 (déclenchée si niveau < seuil).")
            seuil = 0
        sous_theme["recommandations"][ref] = {
            "ref": ref,
            "question": question_ref,
            "texte": r.texte_obligatoire(rec, "texte", ou),
            "seuil": seuil,
            "effort": r.parmi(rec, "effort", EFFORTS, ou),
            "quick_win": bool(rec.get("quick_win")),
            "prestation": r.texte(rec, "prestation"),
            "ou": ou,
        }

    # ---- profilage ------------------------------------------------------
    def _profilage(self, d: dict[str, Any], modele: dict[str, Any]) -> None:
        r, f = self.rapport, F_PROFILAGE
        questions = d.get("questions")
        if not isinstance(questions, list) or not questions:
            r.erreur(f, "Liste « questions » obligatoire et non vide.")
            return
        for i, q in enumerate(questions):
            ou = f"{f} › questions[{i}]"
            code = r.code(q, "code", ou, 20)
            if code is None:
                continue
            ou = f"{f} › {code}"
            if code in modele["profil"]:
                r.erreur(ou, "Question de profilage déclarée deux fois.")
                continue
            choix: dict[str, dict[str, Any]] = {}
            for j, c in enumerate(r.liste(q, "choix", ou)):
                ouc = f"{ou} › choix[{j}]"
                cc = r.code(c, "code", ouc, 59)
                if cc is None:
                    continue
                if cc in choix:
                    r.erreur(ouc, f"Choix « {cc} » déclaré deux fois.")
                    continue
                choix[cc] = {"code": cc, "libelle": r.texte_obligatoire(c, "libelle", ouc)}
            if not choix:
                r.erreur(ou, "Au moins un choix est obligatoire.")
            modele["profil"][code] = {
                "code": code,
                "libelle": r.texte_obligatoire(q, "libelle", ou),
                "aide": r.texte(q, "aide"),
                "type": r.parmi(q, "type", TYPES_PROFIL, ou),
                "condition": q.get("condition"),
                "ordre": i + 1,
                "choix": choix,
            }
        # Conditions d'affichage : vérifiées une fois toutes les questions connues.
        for code, q in modele["profil"].items():
            if q["condition"] is not None:
                self._condition(q["condition"], f"{f} › {code} › condition", modele)

    # ---- réglementations ---------------------------------------------------
    def _reglementations(self, d: dict[str, Any], modele: dict[str, Any]) -> None:
        r, f = self.rapport, F_REGLEMENTATIONS
        liste = d.get("reglementations")
        if not isinstance(liste, list) or not liste:
            r.erreur(f, "Liste « reglementations » obligatoire et non vide.")
            return
        for i, reg in enumerate(liste):
            ou = f"{f} › reglementations[{i}]"
            code = r.code(reg, "code", ou, 30)
            if code is None:
                continue
            ou = f"{f} › {code}"
            if code in modele["reglementations"]:
                r.erreur(ou, "Réglementation déclarée deux fois.")
                continue

            regles: dict[str, dict[str, Any]] = {}
            for j, rg in enumerate(r.liste(reg, "regles", ou)):
                our = f"{ou} › regles[{j}]"
                rr = r.code(rg, "ref", our, 9)
                if rr is None:
                    continue
                complet = f"{code}-{rr}"
                if complet in regles:
                    r.erreur(our, f"Règle « {rr} » déclarée deux fois.")
                    continue
                if "conditions" not in rg:
                    r.erreur(our, "Bloc « conditions » obligatoire.")
                else:
                    self._condition(rg["conditions"], f"{our} › conditions", modele)
                regles[complet] = {
                    "ref": complet,
                    "niveau": r.parmi(rg, "niveau", NIVEAUX_REGLE, our),
                    "conditions": rg.get("conditions"),
                    "critere": r.texte(rg, "critere"),
                    "priorite": _entier(rg.get("priorite"), 0),
                }
            if not regles:
                r.avertir(ou, "Aucune règle : cette réglementation ne sera jamais proposée par le calcul.")

            exigences: dict[str, dict[str, Any]] = {}
            brutes = reg.get("exigences", {})
            if not isinstance(brutes, dict):
                r.erreur(ou, "« exigences » doit être un objet { sous-thème: {profondeur, cible} }.")
                brutes = {}
            for st, e in brutes.items():
                oue = f"{ou} › exigences › {st}"
                if st not in modele["sous_themes"]:
                    r.erreur(oue, f"Sous-thème « {st} » inconnu.")
                    continue
                if not isinstance(e, dict):
                    r.erreur(oue, "Exigence mal formée.")
                    continue
                cible = e.get("cible")
                if isinstance(cible, bool) or not isinstance(cible, (int, float)) or not 0 <= cible <= 5:
                    r.erreur(oue, "« cible » doit être un nombre de 0 à 5.")
                    cible = 0
                exigences[st] = {
                    "profondeur": r.parmi(e, "profondeur", PROFONDEURS, oue),
                    "cible": round(float(cible), 1),
                }

            modele["reglementations"][code] = {
                "code": code,
                "libelle": r.texte_obligatoire(reg, "libelle", ou),
                "nature": r.parmi(reg, "nature", NATURES, ou),
                "description": r.texte(reg, "description"),
                "echeance": r.texte(reg, "echeance"),
                "actions": r.liste_textes(reg, "actions", ou),
                "ordre": i + 1,
                "regles": regles,
                "exigences": exigences,
                # Référentiel du socle de sécurité EBIOS RM appelé (facultatif).
                "referentiel": (r.code(reg, "referentiel", ou, 50) if r.texte(reg, "referentiel") else None),
                "profil": r.texte(reg, "profil") or None,
            }

    def _condition(self, c: Any, ou: str, modele: dict[str, Any]) -> None:
        """Grammaire :
        {"toujours": true} · {"tous": [c, …]} · {"un_parmi": [c, …]} · {"non": c}
        · {"P01": ["energie", "transport"]} (P01 a reçu l'un de ces choix)
        """
        r = self.rapport
        if not isinstance(c, dict) or len(c) != 1:
            r.erreur(ou, "Une condition est un objet à une seule clé.")
            return
        cle, valeur = next(iter(c.items()))
        if cle == "toujours":
            if valeur is not True:
                r.erreur(ou, "« toujours » doit valoir true.")
            return
        if cle in ("tous", "un_parmi"):
            if not isinstance(valeur, list) or not valeur:
                r.erreur(ou, f"« {cle} » attend une liste non vide de conditions.")
                return
            for i, sous in enumerate(valeur):
                self._condition(sous, f"{ou} › {cle}[{i}]", modele)
            return
        if cle == "non":
            self._condition(valeur, f"{ou} › non", modele)
            return
        if cle not in modele["profil"]:
            r.erreur(ou, f"Question de profilage « {cle} » inconnue.")
            return
        if not isinstance(valeur, list) or not valeur:
            r.erreur(ou, f"« {cle} » attend une liste non vide de choix.")
            return
        for choix in valeur:
            if not isinstance(choix, str) or choix not in modele["profil"][cle]["choix"]:
                r.erreur(ou, f"Choix « {choix if isinstance(choix, (str, int, float)) else '?'} » inconnu pour {cle}.")

    # ---- contrôles globaux ----------------------------------------------
    def _controles_globaux(self, modele: dict[str, Any]) -> None:
        r = self.rapport
        vues: dict[str, str] = {}
        for st in modele["sous_themes"].values():
            for ref, rec in st["recommandations"].items():
                if rec["prestation"] and rec["prestation"] not in modele["prestations"]:
                    r.erreur(rec["ou"], f"Prestation « {rec['prestation']} » inconnue (voir {F_PRESTATIONS}).")
                if ref in vues:
                    r.erreur(rec["ou"], f"Référence « {ref} » déjà utilisée dans {vues[ref]}.")
                vues[ref] = st["fichier"]

        for code in modele["themes"]:
            if not any(st["theme"] == code for st in modele["sous_themes"].values()):
                r.avertir(F_REFERENTIEL, f"Le thème « {code} » n'a aucun sous-thème.")

        if modele["reglementations"]:
            for code, st in modele["sous_themes"].items():
                if not any(code in reg["exigences"] for reg in modele["reglementations"].values()):
                    r.avertir(st["fichier"], "Aucune réglementation n'exige ce sous-thème : il n'aura pas de cible.")


def _entier(v: Any, defaut: int) -> int:
    if isinstance(v, bool):
        return defaut
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return defaut
