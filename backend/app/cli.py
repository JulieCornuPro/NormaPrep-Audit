"""Commandes d'administration : `npa <commande>`.

Dans le conteneur : `docker compose exec api npa <commande>`.
"""

import argparse
import getpass
import json
import os
import secrets
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import func, select


def _session():
    from app.db import fabrique_sessions

    return fabrique_sessions()()


def generer_cles(_: argparse.Namespace) -> int:
    print(f"NPA_SECRET_KEY={secrets.token_urlsafe(48)}")
    print(f"NPA_CLE_CHIFFREMENT={Fernet.generate_key().decode()}")
    return 0


def preparer_cles(_: argparse.Namespace) -> int:
    from app.config import preparer_cles as preparer

    print(preparer())
    return 0


def verifier_configuration(_: argparse.Namespace) -> int:
    from app.securite import ConfigurationInvalide
    from app.securite import verifier_configuration as verifier

    try:
        verifier()
    except ConfigurationInvalide as e:
        print(f"\nCONFIGURATION INVALIDE : {e}\n", file=sys.stderr)
        return 1
    return 0


def afficher_cles(_: argparse.Namespace) -> int:
    """Affiche les clés en usage, pour les sauvegarder hors du serveur."""
    from app.config import reglages

    r = reglages()
    print("# À conserver en lieu sûr. Sans NPA_CLE_CHIFFREMENT, les TOTP sont illisibles.")
    print(f"NPA_SECRET_KEY={r.secret_key}")
    print(f"NPA_CLE_CHIFFREMENT={r.cle_chiffrement}")
    return 0


def creer_admin(args: argparse.Namespace) -> int:
    from app.config import reglages
    from app.journal import journaliser
    from app.models import Utilisateur
    from app.securite import hacher_mot_de_passe

    mot_de_passe = os.environ.get("NPA_ADMIN_MOT_DE_PASSE") or getpass.getpass("Mot de passe : ")
    if len(mot_de_passe) < reglages().longueur_min_mot_de_passe:
        print(f"Le mot de passe doit contenir au moins {reglages().longueur_min_mot_de_passe} caractères.", file=sys.stderr)
        return 1
    email = args.email.strip().lower()
    with _session() as s:
        if s.scalar(select(Utilisateur.id).where(func.lower(Utilisateur.email) == email)):
            print("Un compte existe déjà avec cet email.", file=sys.stderr)
            return 1
        u = Utilisateur(email=email, nom=args.nom, mot_de_passe_hash=hacher_mot_de_passe(mot_de_passe), est_admin=True)
        s.add(u)
        s.flush()
        journaliser(
            s,
            "utilisateur_cree",
            objet_type="utilisateur",
            objet_id=u.id,
            details={"email": email, "est_admin": True, "via": "cli"},
        )
        s.commit()
    print(f"Administrateur créé : {email}. Le TOTP sera configuré à la première connexion.")
    return 0


def _afficher_import(res) -> int:
    for e in res.erreurs:
        print(f"ERREUR  {e}")
    for a in res.avertissements:
        print(f"AVERT.  {a}")
    if not res.succes:
        print(f"Import refusé : {len(res.erreurs)} erreur(s). Rien n'a été écrit.")
        return 1
    if res.deja_importe:
        print(f"{res.code} {res.version} : déjà importé à l'identique, rien à faire.")
    else:
        print(f"{res.code} {res.version} importé : {json.dumps(res.stats, ensure_ascii=False)}")
    return 0


def importer(args: argparse.Namespace) -> int:
    from app.contenu.importeur import importer_audit, importer_maturite

    fonction = importer_maturite if args.commande == "importer-maturite" else importer_audit
    with _session() as s:
        res = fonction(s, Path(args.chemin), remplacer=args.remplacer, simulation=args.simulation)
    if args.simulation and res.succes:
        print("Simulation : le contenu est valide, rien n'a été écrit.")
    return _afficher_import(res)


def couverture(args: argparse.Namespace) -> int:
    from app.contenu.couverture import couverture as calculer

    with _session() as s:
        res = calculer(s, args.code)
    if res is None:
        print("Aucune version active de ce référentiel d'audit.", file=sys.stderr)
        return 1
    print(f"{res['referentiel']} {res['version']} : {res['nb_couvertes']}/{res['nb_exigences']} exigences couvertes")
    if res["non_couvertes"]:
        print("Non couvertes : " + ", ".join(res["non_couvertes"]))
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="npa", description="Administration de NormaPrep Audit")
    sous = p.add_subparsers(dest="commande", required=True)

    sous.add_parser("generer-cles", help="Génère NPA_SECRET_KEY et NPA_CLE_CHIFFREMENT").set_defaults(fn=generer_cles)
    sous.add_parser("preparer-cles", help="Génère les clés absentes (lancé au démarrage)").set_defaults(fn=preparer_cles)
    sous.add_parser("verifier-configuration", help="Vérifie les clés (lancé au démarrage)").set_defaults(
        fn=verifier_configuration
    )
    sous.add_parser("afficher-cles", help="Affiche les clés en usage, pour sauvegarde").set_defaults(fn=afficher_cles)

    c = sous.add_parser("creer-admin", help="Crée un compte administrateur")
    c.add_argument("--email", required=True)
    c.add_argument("--nom", required=True)
    c.set_defaults(fn=creer_admin)

    for nom, aide in (
        ("importer-maturite", "Importe un référentiel de maturité (dossier au format NormaPrep)"),
        ("importer-audit", "Importe un référentiel d'audit (fichier JSON)"),
    ):
        c = sous.add_parser(nom, help=aide)
        c.add_argument("chemin")
        c.add_argument(
            "--remplacer", action="store_true", help="Remplace une version déjà importée (si aucun audit ne l'utilise)"
        )
        c.add_argument("--simulation", action="store_true", help="Valide sans rien écrire")
        c.set_defaults(fn=importer)

    c = sous.add_parser("couverture", help="Couverture d'un référentiel pivot")
    c.add_argument("code")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=couverture)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
