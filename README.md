# NormaPrep Audit

Plateforme d'audit à usage interne : diagnostic de maturité, socle de
sécurité, audits de conformité et de configuration, rapports. Elle reprend le
contenu et la logique de NormaPrep Diagnostic dans un outil autonome livré en
conteneur Docker.

- Cahier des charges : [docs/cahier-des-charges.md](docs/cahier-des-charges.md)
- Format des référentiels : [docs/format-contenu.md](docs/format-contenu.md)

## État : jalon 1 (socle)

| Fonction | État |
|---|---|
| Stack Docker (API + PostgreSQL), migrations automatiques au démarrage | fait |
| Comptes, connexion mot de passe + TOTP obligatoire, blocage après 5 échecs | fait |
| Gestion des comptes par un administrateur | fait |
| Import des référentiels de maturité (format NormaPrep) et d'audit (Section > Exigence > Contrôle) | fait |
| Versions figées des référentiels | fait |
| Correspondances vers le pivot ANSSI, avec seuils ; rapport de couverture | fait |
| Journal d'audit inaltérable (protégé au niveau de la base) | fait |
| Interface web | jalon 2 ; en attendant, l'API se pilote depuis `/docs` |
| Stockage des preuves (MinIO) | jalon 3, avec les preuves |

## Démarrage

Prérequis : Docker et Docker Compose.

1. Créer le fichier `.env` à partir du modèle :

   ```bash
   cp .env.example .env
   ```

2. Dans `.env`, choisir un mot de passe pour la base (`NPA_DB_PASSWORD`),
   puis générer les deux clés et copier les lignes affichées dans `.env` :

   ```bash
   docker compose run --rm --no-deps --entrypoint npa api generer-cles
   ```

3. Lancer la stack (les migrations s'appliquent au démarrage de l'API) :

   ```bash
   docker compose up -d --build
   ```

4. Créer le premier administrateur (le mot de passe est demandé, 12 caractères minimum) :

   ```bash
   docker compose exec api npa creer-admin --email prenom.nom@cabinet.fr --nom "Prénom Nom"
   ```

5. Importer le contenu de démonstration, **pivot ANSSI d'abord** :

   ```bash
   docker compose exec api npa importer-audit /content/referentiels/anssi-hygiene-exemple.json
   ```

   ```bash
   docker compose exec api npa importer-maturite /content/maturite/demo
   ```

### Avec Docker Desktop (Windows ou Mac)

Docker Desktop fournit Docker Compose : les étapes ci-dessus s'appliquent
telles quelles, à taper dans un terminal (PowerShell sous Windows, Terminal
sous Mac) ouvert dans le dossier du dépôt cloné. Docker Desktop doit être
démarré.

Le premier lancement se fait en ligne de commande : Docker Desktop ne sait
pas créer une stack Compose depuis son interface. Ensuite, la stack apparaît
dans l'onglet **Containers** sous le nom `normaprep-audit` ; on peut la
démarrer, l'arrêter et lire les journaux de l'API depuis l'interface. L'onglet
**Exec** du conteneur `api` permet de lancer les commandes `npa` sans
terminal.

L'API écoute sur <http://127.0.0.1:8000> (machine locale uniquement) ; la
documentation interactive est sur <http://127.0.0.1:8000/docs>. En
production, placer un proxy TLS devant.

### Première connexion

1. `POST /api/auth/connexion` avec l'email et le mot de passe. La réponse
   contient `etape: "enrolement"`, un `secret` et une `uri_totp` : ajoutez le
   compte dans une application d'authentification (scan du QR code de
   l'URI, ou saisie du secret).
2. `POST /api/auth/totp` avec le `jeton` reçu et le code à 6 chiffres. La
   réponse contient le `jeton_acces` à présenter en `Authorization: Bearer`.

Les connexions suivantes renvoient directement `etape: "totp"`.

## Commandes d'administration

Dans le conteneur : `docker compose exec api npa <commande>`.

| Commande | Rôle |
|---|---|
| `generer-cles` | Génère `NPA_SECRET_KEY` et `NPA_CLE_CHIFFREMENT` |
| `creer-admin --email … --nom …` | Crée un administrateur |
| `importer-audit <fichier.json>` | Importe un référentiel d'audit |
| `importer-maturite <dossier>` | Importe un référentiel de maturité |
| `couverture <code>` | Couverture d'un référentiel pivot (`--json` pour le détail) |

Les deux commandes d'import acceptent `--simulation` (valide sans écrire) et
`--remplacer` (remplace une version déjà importée, tant qu'aucun audit ne
l'utilise).

## API (jalon 1)

| Route | Accès | Rôle |
|---|---|---|
| `POST /api/auth/connexion`, `POST /api/auth/totp` | public | Connexion en deux étapes |
| `GET /api/auth/moi`, `POST /api/auth/mot-de-passe` | connecté | Compte courant |
| `GET/POST /api/utilisateurs`, `PATCH /api/utilisateurs/{id}` | admin | Comptes |
| `POST /api/utilisateurs/{id}/reinitialiser-totp`, `/debloquer`, `/mot-de-passe` | admin | Assistance |
| `GET /api/contenu/referentiels`, `GET /api/contenu/referentiels/{code}` | connecté | Référentiels |
| `GET /api/contenu/couverture/{code}` | connecté | Couverture d'un pivot |
| `GET /api/contenu/disponibles`, `POST /api/contenu/import` | admin | Import depuis le dossier de contenu |
| `GET /api/journal` | admin | Journal d'audit |

## Sécurité

- Mots de passe hachés en Argon2id ; 12 caractères minimum.
- TOTP obligatoire pour tous les comptes ; secrets chiffrés en base
  (Fernet) ; un code ne peut pas être rejoué.
- Blocage de 15 minutes après 5 échecs ; message d'erreur identique que le
  compte existe ou non.
- Les jetons d'accès (8 h) sont invalidés dès que le mot de passe, les droits
  ou le TOTP changent, ou que le compte est désactivé.
- Journal d'audit : toute modification ou suppression est refusée par la base
  (déclencheurs PostgreSQL).
- Conteneur API en système de fichiers en lecture seule, utilisateur non root,
  port exposé sur `127.0.0.1` uniquement.

**Conservez `NPA_CLE_CHIFFREMENT`** avec vos sauvegardes : sans elle, les
secrets TOTP sont illisibles et chaque compte doit refaire l'enrôlement.

## Développement

```
backend/
  app/
    api/          routes (auth, utilisateurs, contenu, journal)
    contenu/      validation, import et couverture des référentiels
    models.py     modèle de données
    securite.py   mots de passe, TOTP, jetons
    cli.py        commandes npa
  alembic/        migrations
  tests/          tests (PostgreSQL réel)
content/          référentiels (démonstration)
docs/
```

Les tests utilisent une vraie base PostgreSQL ; chaque test repart d'un
schéma vide créé par les migrations.

```bash
cd backend && pip install -e ".[dev]"
```

```bash
NPA_TEST_DATABASE_URL=postgresql+psycopg://npa:npa@localhost:5432/npa_test pytest
```

Style : `ruff check` et `ruff format`.
