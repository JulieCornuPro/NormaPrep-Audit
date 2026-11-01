"""Outils communs aux validateurs.

Les validateurs accumulent les erreurs au lieu de s'arrêter à la première :
l'auteur du contenu reçoit la liste complète, avec le fichier et
l'emplacement de chaque problème (« fichier › chemin — message »).
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MOTIF_CODE = re.compile(r"^[A-Za-z0-9_.-]+$")

PROFONDEURS = ("essentiel", "standard", "renforce")
TYPES_QUESTION = ("niveaux", "fermee", "demonstration", "ouverte")
MODES = ("atelier", "pre_questionnaire", "revue_documentaire", "import")
INTERLOCUTEURS = ("direction", "rssi", "dsi", "administrateurs", "developpement", "dpo", "achats", "metier")
METHODES = ("entretien", "revue_documentaire", "observation", "commande")


@dataclass
class Rapport:
    erreurs: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)

    @property
    def valide(self) -> bool:
        return not self.erreurs

    def erreur(self, ou: str, message: str) -> None:
        self.erreurs.append(f"{ou} — {message}")

    def avertir(self, ou: str, message: str) -> None:
        self.avertissements.append(f"{ou} — {message}")

    # ---- lecture de champs -------------------------------------------------

    @staticmethod
    def texte(d: Any, cle: str) -> str:
        """Texte facultatif, nettoyé des espaces de bord."""
        if isinstance(d, dict):
            v = d.get(cle)
            if isinstance(v, (str, int, float)) and not isinstance(v, bool):
                return str(v).strip()
        return ""

    def texte_obligatoire(self, d: Any, cle: str, ou: str) -> str:
        t = self.texte(d, cle)
        if not t:
            self.erreur(ou, f"Champ « {cle} » obligatoire.")
        return t

    def code(self, d: Any, cle: str, ou: str, maximum: int) -> str | None:
        """Code ou référence : obligatoire, caractères restreints, longueur bornée."""
        if not isinstance(d, dict):
            self.erreur(ou, "Élément mal formé.")
            return None
        c = self.texte(d, cle)
        if not c:
            self.erreur(ou, f"Champ « {cle} » obligatoire.")
            return None
        if not MOTIF_CODE.match(c):
            self.erreur(ou, f"« {c} » : seuls lettres, chiffres, « - », « _ » et « . » sont admis.")
            return None
        if len(c) > maximum:
            self.erreur(ou, f"« {c} » dépasse {maximum} caractères.")
            return None
        return c

    def parmi(self, d: Any, cle: str, admis: tuple[str, ...], ou: str, defaut: str | None = None) -> str:
        v = self.texte(d, cle)
        if not v and defaut is not None:
            return defaut
        if v not in admis:
            self.erreur(ou, f"« {cle} » doit valoir : {', '.join(admis)}.")
        return v

    def poids(self, d: Any, ou: str) -> float:
        """Poids facultatif, strictement positif, 1 par défaut."""
        if not isinstance(d, dict) or "poids" not in d:
            return 1.0
        v = d["poids"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            self.erreur(ou, "« poids » doit être un nombre strictement positif.")
            return 1.0
        return float(v)

    def liste_textes(self, d: Any, cle: str, ou: str) -> list[str]:
        if not isinstance(d, dict) or cle not in d:
            return []
        v = d[cle]
        if not isinstance(v, list):
            self.erreur(ou, f"« {cle} » doit être une liste de textes.")
            return []
        return [str(t).strip() for t in v if isinstance(t, (str, int, float)) and str(t).strip()]

    def liste_parmi(self, d: Any, cle: str, admis: tuple[str, ...], ou: str) -> list[str]:
        valeurs = self.liste_textes(d, cle, ou)
        for v in valeurs:
            if v not in admis:
                self.erreur(ou, f"« {cle} » : « {v} » inconnu (admis : {', '.join(admis)}).")
        return valeurs

    def liste(self, d: Any, cle: str, ou: str) -> list[Any]:
        """Liste facultative (absente = vide)."""
        if not isinstance(d, dict) or cle not in d:
            return []
        v = d[cle]
        if not isinstance(v, list):
            self.erreur(ou, f"« {cle} » doit être une liste.")
            return []
        return v

    def correspondances(self, d: Any, ou: str, avec_seuils: bool) -> list[dict[str, Any]]:
        """Liste « correspondances » d'une question ou d'un contrôle.

        Forme : [{"referentiel": "ANSSI-HYG", "code": "37",
                  "seuil_applique": 3, "seuil_partiel": 1}]
        Les seuils ne concernent que les questions de maturité (0–5).
        """
        resultat: list[dict[str, Any]] = []
        vues: set[tuple[str, str]] = set()
        for i, c in enumerate(self.liste(d, "correspondances", ou)):
            ouc = f"{ou} › correspondances[{i}]"
            ref = self.code(c, "referentiel", ouc, 50)
            code = self.code(c, "code", ouc, 50)
            if ref is None or code is None:
                continue
            if (ref, code) in vues:
                self.erreur(ouc, f"Correspondance vers {ref} › {code} déclarée deux fois.")
                continue
            vues.add((ref, code))
            seuils: dict[str, int | None] = {"seuil_applique": None, "seuil_partiel": None}
            for cle in seuils:
                if cle not in c:
                    continue
                if not avec_seuils:
                    self.erreur(ouc, f"« {cle} » n'a de sens que pour une question de maturité.")
                    continue
                v = c[cle]
                if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
                    self.erreur(ouc, f"« {cle} » doit être un entier de 1 à 5.")
                    continue
                seuils[cle] = v
            a, p = seuils["seuil_applique"], seuils["seuil_partiel"]
            if a is not None and p is not None and p > a:
                self.erreur(ouc, "« seuil_partiel » ne peut pas dépasser « seuil_applique ».")
            resultat.append({"referentiel": ref, "code": code, **seuils, "ou": ouc})
        return resultat


def lire_json(chemin: Path, relatif: str, rapport: Rapport, obligatoire: bool = True) -> Any:
    """Lit un fichier JSON ; None s'il manque ou est illisible (erreur notée)."""
    if not chemin.is_file():
        if obligatoire:
            rapport.erreur(relatif, "Fichier manquant.")
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        rapport.erreur(relatif, "Le fichier doit être encodé en UTF-8.")
    except json.JSONDecodeError as e:
        rapport.erreur(relatif, f"JSON illisible : {e.msg} (ligne {e.lineno}, colonne {e.colno}).")
    return None


def empreinte_fichiers(racine: Path, fichiers: list[str]) -> str:
    """SHA-256 reproductible d'un ensemble de fichiers (chemins relatifs triés)."""
    h = hashlib.sha256()
    for relatif in sorted(fichiers):
        h.update(relatif.encode("utf-8") + b"\0")
        h.update((racine / relatif).read_bytes())
        h.update(b"\0")
    return h.hexdigest()
