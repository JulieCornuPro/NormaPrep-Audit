"""Classeur de test au format du brouillon « Socle de sécurité » (synthétique)."""

import io

import openpyxl

ENTETES = ["Section", "Exigence", "Contrôle", "Contrôle détaillé", "Standard", "Renforcé"]
LIGNES = [
    [
        "I - SENSIBILISER ET FORMER",
        "1 - Former les équipes opérationnelles",
        "1.1 - Les équipes formées comprennent ...",
        "-",
        "Oui",
        "Oui",
    ],
    [
        "I - SENSIBILISER ET FORMER",
        "1 - Former les équipes opérationnelles",
        "1.1 - Les équipes formées comprennent ...",
        "1.1.1 - les administrateurs réseau",
        "Oui",
        "Oui",
    ],
    ["I - SENSIBILISER ET FORMER", "1 - Former les équipes opérationnelles", "1.2 - Former chaque année", "-", "Non", "Oui"],
    ["III - AUTHENTIFIER", "13 - Privilégier une authentification forte", "13.1 - Deux facteurs", "-", "Oui", "Non"],
    ["IV - SÉCURISER LES POSTES", "16 - Gestion centralisée des politiques", "-", "-", "Oui", "Oui"],
    [
        "IX - SUPERVISER, AUDITER, RÉAGIR",
        "37 - Politique de sauvegarde des composants critiques",
        "37.1 - Sauvegardes régulières",
        "-",
        "Oui",
        "Oui",
    ],
    [
        "IX - SUPERVISER, AUDITER, RÉAGIR",
        "37 - Politique de sauvegarde des composants critiques",
        "37.2 - Copie hors ligne",
        "-",
        "Oui",
        "Oui",
    ],
    ["X - POUR ALLER PLUS LOIN", "42 - Audits réguliers", "42.1 - Audit annuel", "-", "Non", "Oui"],
]
INFOS = ["Feuille", "Code", "Version", "Libellé", "Source", "Licence", "Niveau socle", "Profils cumulatifs"]
INFO_HYG = ["Guide hygiène", "ANSSI-HYG", "2017.1", "Guide d'hygiène informatique", "ANSSI", "Licence Ouverte", "Exigence", "Oui"]


def classeur(lignes=None, infos=None, feuilles_en_plus=None, avec_infos=True) -> bytes:
    wb = openpyxl.Workbook()
    if avec_infos:
        wi = wb.active
        wi.title = "Infos"
        wi.append(INFOS)
        for ligne in infos if infos is not None else [INFO_HYG]:
            wi.append(ligne)
        ws = wb.create_sheet("Guide hygiène")
    else:
        ws = wb.active
        ws.title = "Guide hygiène"
    ws.append(ENTETES)
    for ligne in lignes if lignes is not None else LIGNES:
        ws.append(ligne)
    for nom, contenu in (feuilles_en_plus or {}).items():
        w = wb.create_sheet(nom)
        for ligne in contenu:
            w.append(ligne)
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
