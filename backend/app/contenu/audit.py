"""Validation d'un référentiel d'audit (Section > Exigence > Contrôle).

Un référentiel d'audit est un seul fichier JSON :

    {
      "code": "ANSSI-HYG", "version": "2017.1", "libelle": "...",
      "source": "...", "licence": "...",
      "niveaux": ["standard", "renforce"],          # facultatif
      "sections": [
        { "code": "S1", "libelle": "...", "exigences": [
            { "code": "1", "libelle": "...", "controles": [
                { "code": "1.a", "intitule": "...", "methode": "entretien", ... }
            ] }
        ] }
      ]
    }

Les codes de section, d'exigence et de contrôle partagent un même espace : ils
sont uniques dans le référentiel, ce qui permet à une correspondance de viser
indifféremment une exigence (une mesure ANSSI) ou un contrôle (un point CIS).

Format détaillé : docs/format-contenu.md.
"""

from pathlib import Path
from typing import Any

from app.contenu.outils import METHODES, Rapport, empreinte_fichiers, lire_json


def analyser(fichier: Path) -> tuple[Rapport, dict[str, Any] | None]:
    rapport = Rapport()
    nom = fichier.name
    d = lire_json(fichier, nom, rapport)
    if d is None:
        return rapport, None
    if not isinstance(d, dict):
        rapport.erreur(nom, "Le fichier doit contenir un objet JSON.")
        return rapport, None
    modele = _valider(d, nom, rapport)
    if not rapport.valide:
        return rapport, None
    modele["empreinte"] = empreinte_fichiers(fichier.parent, [nom])
    return rapport, modele


def _valider(d: dict[str, Any], f: str, r: Rapport) -> dict[str, Any]:
    code = r.code(d, "code", f, 50)
    version = r.texte(d, "version")
    if not version:
        r.erreur(f, "Champ « version » obligatoire.")
    elif len(version) > 30:
        r.erreur(f, "La version dépasse 30 caractères.")

    niveaux = tuple(r.liste_textes(d, "niveaux", f))

    modele: dict[str, Any] = {
        "code": code or "",
        "version": version,
        "libelle": r.texte_obligatoire(d, "libelle", f),
        "source": r.texte(d, "source"),
        "licence": r.texte(d, "licence"),
        "sections": [],
    }
    if not r.texte(d, "licence"):
        r.avertir(f, "Licence non renseignée : vérifiez les droits de réutilisation du contenu.")

    # Code → emplacement de sa déclaration, pour l'unicité sur tout le référentiel.
    codes: dict[str, str] = {}

    def declarer(c: str, ou: str) -> bool:
        if c in codes:
            r.erreur(ou, f"Code « {c} » déjà utilisé ({codes[c]}).")
            return False
        codes[c] = ou
        return True

    sections = d.get("sections")
    if not isinstance(sections, list) or not sections:
        r.erreur(f, "Liste « sections » obligatoire et non vide.")
        return modele

    nb_controles = 0
    for i, s in enumerate(sections):
        ou = f"{f} › sections[{i}]"
        cs = r.code(s, "code", ou, 50)
        if cs is None:
            continue
        ou = f"{f} › {cs}"
        if not declarer(cs, ou):
            continue
        section = {
            "code": cs,
            "libelle": r.texte_obligatoire(s, "libelle", ou),
            "description": r.texte(s, "description"),
            "ordre": i + 1,
            "exigences": [],
        }
        exigences = r.liste(s, "exigences", ou)
        if not exigences:
            r.avertir(ou, "Section sans exigence.")
        for j, e in enumerate(exigences):
            oue = f"{ou} › exigences[{j}]"
            ce = r.code(e, "code", oue, 50)
            if ce is None:
                continue
            oue = f"{ou} › {ce}"
            if not declarer(ce, oue):
                continue
            exigence = {
                "code": ce,
                "libelle": r.texte_obligatoire(e, "libelle", oue),
                "description": r.texte(e, "description"),
                "ordre": j + 1,
                "controles": [],
            }
            # Une exigence sans contrôle est admise : un référentiel pivot (guide
            # ANSSI) peut n'être décrit qu'au niveau des mesures.
            for k, c in enumerate(r.liste(e, "controles", oue)):
                ouc = f"{oue} › controles[{k}]"
                cc = r.code(c, "code", ouc, 50)
                if cc is None:
                    continue
                ouc = f"{oue} › {cc}"
                if not declarer(cc, ouc):
                    continue
                niveau = r.texte(c, "niveau")
                if niveaux and niveau not in niveaux:
                    r.erreur(ouc, f"« niveau » doit valoir : {', '.join(niveaux)}.")
                exigence["controles"].append(
                    {
                        "code": cc,
                        "intitule": r.texte_obligatoire(c, "intitule", ouc),
                        "description": r.texte(c, "description"),
                        "niveau": niveau,
                        "methode": r.parmi(c, "methode", METHODES, ouc),
                        "verification": r.texte(c, "verification"),
                        "valeur_attendue": r.texte(c, "valeur_attendue"),
                        "preuves_attendues": r.liste_textes(c, "preuves_attendues", ouc),
                        "recommandation": r.texte(c, "recommandation"),
                        "poids": r.poids(c, ouc),
                        "ordre": k + 1,
                        "correspondances": r.correspondances(c, ouc, avec_seuils=False),
                    }
                )
                nb_controles += 1
            section["exigences"].append(exigence)
        modele["sections"].append(section)

    if nb_controles == 0 and r.valide:
        r.avertir(f, "Aucun contrôle : le référentiel ne pourra servir que de pivot (niveau exigence).")

    # Une correspondance ne vise pas le référentiel lui-même.
    for s in modele["sections"]:
        for e in s["exigences"]:
            for c in e["controles"]:
                for corr in c["correspondances"]:
                    if corr["referentiel"] == code:
                        r.erreur(corr["ou"], "Une correspondance doit viser un autre référentiel.")
    return modele
