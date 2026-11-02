"""Import de référentiels depuis un classeur Excel.

Format (celui du brouillon « Socle de sécurité ») :

- une feuille **Infos** liste les feuilles à importer, une ligne par
  référentiel : Feuille, Code, Version, Libellé, Source, Licence, et en
  option « Niveau socle » (nom de la colonne évaluée dans le socle EBIOS RM,
  par défaut la deuxième) et « Profils cumulatifs » (Oui : un élément
  applicable à un profil l'est aussi aux suivants, ex. Standard → Renforcé).
  Les feuilles absentes d'Infos sont ignorées (référentiels en cours) ;
- chaque feuille listée : une ligne d'en-têtes, puis une ligne par élément.
  * colonnes de niveaux, dans l'ordre (Section, Exigence, Contrôle…) : cellule
    « code - libellé », ou « - » / vide si le niveau est absent ;
  * colonnes de profils, en fin de ligne : Oui / Non ;
  * colonnes facultatives reconnues par leur en-tête : Interlocuteurs, Méthode,
    Preuves attendues, Vérification, Valeur attendue, Recommandation,
    Description.

Chaque ligne décrit l'élément le plus profond qu'elle renseigne ; ses parents
sont les éléments des colonnes précédentes. Un élément répété sur plusieurs
lignes (parent de plusieurs contrôles) doit garder le même libellé.
"""

import hashlib
import io
import json
import re
import unicodedata
from typing import Any

import openpyxl

from app.contenu.outils import METHODES, Rapport

FEUILLE_INFOS = "infos"
OUI, NON = "oui", "non"
CODE_MAX = 60
TAILLE_MAX_OCTETS = 15 * 1024 * 1024

# « 1.1 - Libellé », « OS-1 - Libellé », « 2.B.2-EI/EE.1- Libellé » (espace manquant toléré).
MOTIF_CELLULE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_./-]*?)\s*[-–]\s+(.+?)\s*$", re.S)
MOTIF_CODE = re.compile(r"^[A-Za-z0-9_./-]+$")

COLONNES_FACULTATIVES = {
    "interlocuteurs": "interlocuteurs",
    "interlocuteur": "interlocuteurs",
    "methode": "methode",
    "preuves attendues": "preuves_attendues",
    "preuve attendue": "preuves_attendues",
    "verification": "verification",
    "valeur attendue": "valeur_attendue",
    "recommandation": "recommandation",
    "description": "description",
}


def _norme(texte: Any) -> str:
    """Minuscules, sans accents ni espaces superflus : pour comparer des en-têtes."""
    t = unicodedata.normalize("NFKD", str(texte or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _texte(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _absent(v: Any) -> bool:
    return _texte(v) in ("", "-", "–")


def lire(contenu: bytes, nom_fichier: str = "classeur.xlsx") -> list[tuple[str, Rapport, dict[str, Any] | None]]:
    """Analyse un classeur. Renvoie, pour chaque feuille listée dans Infos :
    (nom de la feuille, rapport, modèle ou None si invalide). Une erreur
    générale (classeur illisible, Infos absente) renvoie une seule entrée."""
    general = Rapport()
    if len(contenu) > TAILLE_MAX_OCTETS:
        general.erreur(nom_fichier, f"Fichier trop volumineux (maximum {TAILLE_MAX_OCTETS // 1024 // 1024} Mo).")
        return [(nom_fichier, general, None)]
    try:
        classeur = openpyxl.load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    except Exception as e:  # format invalide, zip corrompu…
        general.erreur(nom_fichier, f"Classeur Excel illisible ({type(e).__name__}).")
        return [(nom_fichier, general, None)]

    feuilles = {_norme(ws.title): ws for ws in classeur.worksheets}
    if FEUILLE_INFOS not in feuilles:
        general.erreur(
            nom_fichier, "Feuille « Infos » manquante : elle liste les feuilles à importer (voir docs/format-contenu.md)."
        )
        return [(nom_fichier, general, None)]

    entrees = _lire_infos(feuilles[FEUILLE_INFOS], general)
    if not general.valide:
        return [("Infos", general, None)]
    if not entrees:
        general.erreur("Infos", "Aucune feuille à importer : ajoutez une ligne par référentiel.")
        return [("Infos", general, None)]

    resultats = []
    for e in entrees:
        rapport = Rapport()
        ws = feuilles.get(_norme(e["feuille"]))
        if ws is None:
            rapport.erreur("Infos", f"Feuille « {e['feuille']} » introuvable dans le classeur.")
            resultats.append((e["feuille"], rapport, None))
            continue
        modele = _lire_feuille(ws, e, rapport)
        resultats.append((ws.title, rapport, modele if rapport.valide else None))
    classeur.close()
    return resultats


# ---------------------------------------------------------------------------


def _lire_infos(ws: Any, r: Rapport) -> list[dict[str, Any]]:
    lignes = [list(x) for x in ws.iter_rows(values_only=True)]
    if not lignes:
        return []
    entetes = [_norme(c) for c in lignes[0]]
    attendus = {"feuille": None, "code": None, "version": None, "libelle": None, "source": None, "licence": None,
                "niveau socle": None, "profils cumulatifs": None}  # fmt: skip
    for i, h in enumerate(entetes):
        if h in attendus and attendus[h] is None:
            attendus[h] = i
    for obligatoire in ("feuille", "code", "version", "libelle"):
        if attendus[obligatoire] is None:
            r.erreur("Infos", f"Colonne « {obligatoire.capitalize()} » manquante.")
    if not r.valide:
        return []

    def val(ligne: list[Any], cle: str) -> str:
        i = attendus[cle]
        return _texte(ligne[i]) if i is not None and i < len(ligne) else ""

    entrees, vues = [], set()
    for n, ligne in enumerate(lignes[1:], start=2):
        if not any(_texte(c) for c in ligne):
            continue
        ou = f"Infos › ligne {n}"
        e = {k: val(ligne, k) for k in attendus}
        if not e["feuille"]:
            r.erreur(ou, "Nom de feuille manquant.")
            continue
        if not MOTIF_CODE.match(e["code"]) or len(e["code"]) > 50:
            r.erreur(ou, f"Code « {e['code']} » invalide : lettres, chiffres, « - », « _ », « . », « / », 50 caractères au plus.")
        if not e["version"] or len(e["version"]) > 30:
            r.erreur(ou, "Version obligatoire, 30 caractères au plus.")
        if not e["libelle"]:
            r.erreur(ou, "Libellé obligatoire.")
        if e["code"] in vues:
            r.erreur(ou, f"Code « {e['code']} » listé deux fois.")
        vues.add(e["code"])
        e["cumulatifs"] = _norme(e["profils cumulatifs"]) == OUI
        entrees.append(e)
    return entrees


def _lire_feuille(ws: Any, infos: dict[str, Any], r: Rapport) -> dict[str, Any]:
    f = ws.title
    lignes = [list(x) for x in ws.iter_rows(values_only=True)]
    lignes = [x for x in lignes if any(_texte(c) for c in x)]
    if len(lignes) < 2:
        r.erreur(f, "Feuille vide : une ligne d'en-têtes puis une ligne par élément.")
        return {}
    entetes = [_texte(c) for c in lignes[0]]
    corps = lignes[1:]

    # Colonnes de profils : uniquement des Oui / Non (ex. Standard, Renforcé ; EI, EE).
    facultatives_noms = {_norme(h) for h in entetes} & set(COLONNES_FACULTATIVES)
    profils_idx: list[int] = []
    for i, h in enumerate(entetes):
        valeurs = {_norme(x[i]) for x in corps if i < len(x) and _texte(x[i])}
        if h and _norme(h) not in facultatives_noms and valeurs and valeurs <= {OUI, NON}:
            profils_idx.append(i)
    facultatives = {i: COLONNES_FACULTATIVES[_norme(h)] for i, h in enumerate(entetes) if _norme(h) in COLONNES_FACULTATIVES}
    niveaux_idx = [i for i, h in enumerate(entetes) if h and i not in profils_idx and i not in facultatives]
    if not niveaux_idx:
        r.erreur(f, "Aucune colonne de niveau (Section, Exigence, Contrôle…).")
        return {}
    niveaux = [entetes[i] for i in niveaux_idx]
    profils = [entetes[i] for i in profils_idx]

    niveau_socle = 1 if len(niveaux) > 1 else 0
    if infos["niveau socle"]:
        trouve = [k for k, h in enumerate(niveaux) if _norme(h) == _norme(infos["niveau socle"])]
        if trouve:
            niveau_socle = trouve[0]
        else:
            r.erreur("Infos", f"{f} : niveau socle « {infos['niveau socle']} » absent des en-têtes ({', '.join(niveaux)}).")

    noeuds: dict[str, dict[str, Any]] = {}
    ordre = 0
    for n, ligne in enumerate(corps, start=2):
        ligne = ligne + [None] * (len(entetes) - len(ligne))
        chemin: list[str] = []
        for k, i in enumerate(niveaux_idx):
            cellule = ligne[i]
            if _absent(cellule):
                continue
            ou = f"{f} › {_colonne(i)}{n}"
            m = MOTIF_CELLULE.match(_texte(cellule))
            if not m:
                r.erreur(ou, f"« {_texte(cellule)[:60]} » : attendu « code - libellé ».")
                chemin = []
                break
            code, libelle = m.group(1), " ".join(m.group(2).split())
            if len(code) > CODE_MAX:
                r.erreur(ou, f"Code « {code} » trop long ({CODE_MAX} caractères au plus).")
                break
            parent = chemin[-1] if chemin else None
            existant = noeuds.get(code)
            if existant is None:
                ordre += 1
                noeuds[code] = {
                    "code": code, "libelle": libelle, "niveau": k, "parent": parent, "ordre": ordre,
                    "profils_ligne": None, "ligne": n, "description": "", "methode": "", "verification": "",
                    "valeur_attendue": "", "preuves_attendues": [], "recommandation": "", "interlocuteurs": [],
                    "poids": 1.0, "correspondances": [],
                }  # fmt: skip
            else:
                if existant["libelle"] != libelle:
                    r.erreur(ou, f"Code « {code} » déjà utilisé ligne {existant['ligne']} avec un autre libellé.")
                if existant["niveau"] != k or existant["parent"] != parent:
                    r.erreur(ou, f"Code « {code} » déjà utilisé ligne {existant['ligne']} à un autre endroit de l'arborescence.")
            chemin.append(code)
        if not chemin:
            if r.valide:
                r.erreur(f"{f} › ligne {n}", "Aucun élément sur cette ligne.")
            continue

        feuille_noeud = noeuds[chemin[-1]]
        if profils:
            valeurs = [_norme(ligne[i]) == OUI for i in profils_idx]
            if infos["cumulatifs"]:
                premier = next((k for k, v in enumerate(valeurs) if v), None)
                if premier is not None and not all(valeurs[premier:]):
                    manque = [profils[k] for k in range(premier, len(profils)) if not valeurs[k]]
                    r.avertir(
                        f"{f} › ligne {n}",
                        f"{chemin[-1]} : applicable en « {profils[premier]} » mais pas en « {', '.join(manque)} » ; "
                        "profils cumulatifs : importé comme applicable aussi en " + ", ".join(manque) + ". Vérifiez la source.",
                    )
                    valeurs = [v or k >= premier for k, v in enumerate(valeurs)]
            feuille_noeud["profils_ligne"] = [p for p, v in zip(profils, valeurs, strict=True) if v]
        for i, champ in facultatives.items():
            v = _texte(ligne[i])
            if not v or v == "-":
                continue
            if champ in ("interlocuteurs", "preuves_attendues"):
                feuille_noeud[champ] = [x.strip() for x in re.split(r"[;,\n]", v) if x.strip()]
            elif champ == "methode":
                m = _norme(v).replace(" ", "_")
                if m not in METHODES:
                    r.erreur(f"{f} › {_colonne(i)}{n}", f"Méthode « {v} » inconnue (admis : {', '.join(METHODES)}).")
                feuille_noeud["methode"] = m
            else:
                feuille_noeud[champ] = v

    # Profils d'un élément : ceux de sa propre ligne, plus ceux de ses descendants.
    enfants: dict[str | None, list[str]] = {}
    for c, nd in noeuds.items():
        enfants.setdefault(nd["parent"], []).append(c)

    def profils_de(code: str) -> set[str]:
        nd = noeuds[code]
        ens = set(nd["profils_ligne"] or [])
        for e in enfants.get(code, []):
            ens |= profils_de(e)
        nd["profils"] = [p for p in profils if p in ens]
        return ens

    for racine in enfants.get(None, []):
        profils_de(racine)

    for nd in noeuds.values():
        if profils and not nd["profils"]:
            r.avertir(f"{f} › ligne {nd['ligne']}", f"{nd['code']} n'est applicable à aucun profil.")
        nd.pop("profils_ligne", None)
        nd.pop("ligne", None)

    modele = {
        "code": infos["code"],
        "version": infos["version"],
        "libelle": infos["libelle"],
        "source": infos["source"],
        "licence": infos["licence"],
        "niveaux": niveaux,
        "profils": profils,
        "niveau_socle": niveau_socle,
        "noeuds": list(noeuds.values()),
    }
    if not infos["licence"]:
        r.avertir("Infos", f"{f} : licence non renseignée ; vérifiez les droits de réutilisation du contenu.")
    modele["empreinte"] = hashlib.sha256(json.dumps(modele, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return modele


def _colonne(i: int) -> str:
    """Indice de colonne (0 = A) en lettres Excel."""
    s = ""
    i += 1
    while i:
        i, reste = divmod(i - 1, 26)
        s = chr(65 + reste) + s
    return s
