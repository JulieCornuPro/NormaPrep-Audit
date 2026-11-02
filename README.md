# NormaPrep Audit

Plateforme d'audit à usage interne : diagnostic de maturité, socle de
sécurité, audits de conformité et de configuration, rapports. Elle reprend le
contenu et la logique de NormaPrep Diagnostic dans un outil autonome livré en
conteneur Docker.

- Cahier des charges : [docs/cahier-des-charges.md](docs/cahier-des-charges.md)
- Format des référentiels : [docs/format-contenu.md](docs/format-contenu.md)

## État : jalons 1 à 3

| Fonction | État |
|---|---|
| Stack Docker (API, interface web, PostgreSQL), clés et migrations automatiques | fait |
| Comptes, connexion mot de passe + TOTP (QR code), blocage après 5 échecs | fait |
| Import des référentiels, versions figées, correspondances ANSSI, couverture | fait |
| Journal d'audit inaltérable | fait |
| Clients, missions, équipe et rôles par mission | fait |
| Diagnostic : profilage réglementaire, arbitrage, profondeur et cibles | fait |
| Plan d'entretiens automatique (budget, interlocuteurs, modes de recueil) | fait |
| Questionnaire à niveaux, pré-questionnaire client par lien | fait |
| Résultats : scores, écarts, radar, recommandations, audits proposés, finalisation | fait |
| Référentiels chargés depuis l'interface (classeur Excel), bibliothèque et référentiels client | fait |
| EBIOS RM atelier 1 : cadrage, valeurs métier, biens supports, événements redoutés, socle de sécurité | fait |
| Constats et rapports communs, audit de configuration (CIS) | jalon 4 |
| EBIOS RM ateliers 2 à 5 | jalon 5 |
| Audit de code, test d'intrusion | jalon 6 |

## Démarrage

Prérequis : Docker et Docker Compose (fournis par Docker Desktop sous
Windows et Mac ; Docker Desktop doit être démarré). Les commandes se tapent
dans un terminal ouvert dans le dossier du dépôt : PowerShell sous Windows,
Terminal sous Mac ou Linux.

### 1. Récupérer le code

```bash
git clone https://github.com/JulieCornuPro/NormaPrep-Audit.git
```

```bash
cd NormaPrep-Audit
```

Déjà cloné : `git checkout main` puis `git pull`.

### 2. Créer le fichier `.env`

`.env` n'est **pas** dans le dépôt (il contient un secret) : chacun le crée
sur sa machine à partir du modèle `.env.example`. Il ne contient qu'une
information obligatoire, le mot de passe de la base de données, à choisir
librement. Les clés de l'application, elles, sont générées automatiquement
au premier démarrage : rien à faire.

Windows (PowerShell) :

```bash
Copy-Item .env.example .env
```

```bash
notepad .env
```

Mac ou Linux :

```bash
cp .env.example .env
```

Dans le fichier, complétez la ligne `NPA_DB_PASSWORD=` avec le mot de passe
choisi, par exemple `NPA_DB_PASSWORD=Une-phrase-longue-2026`, puis
enregistrez. Ne touchez pas aux lignes qui commencent par `#`.

À éviter :

- créer le fichier avec `echo ... > .env` dans PowerShell : il serait écrit
  dans un encodage que Docker ne lit pas ;
- l'enregistrer sous le nom `.env.txt` : dans le Bloc-notes, choisir le type
  « Tous les fichiers » ;
- changer `NPA_DB_PASSWORD` après le premier lancement : la base garde le mot
  de passe de sa création (voir « Repartir de zéro »).

### 3. Lancer l'application

```bash
docker compose up -d --build
```

La première construction prend quelques minutes (elle compile aussi
l'interface). Vérifiez ensuite que l'API tourne : la dernière ligne doit
être `Uvicorn running on http://0.0.0.0:8000`.

```bash
docker compose logs api --tail 10
```

### 4. Créer le premier administrateur

Le mot de passe est demandé ensuite (12 caractères minimum ; rien ne
s'affiche pendant la saisie, c'est normal).

```bash
docker compose exec api npa creer-admin --email prenom.nom@cabinet.fr --nom "Prénom Nom"
```

### 5. Importer le contenu de démonstration, pivot ANSSI d'abord

```bash
docker compose exec api npa importer-audit /content/referentiels/anssi-hygiene-exemple.json
```

```bash
docker compose exec api npa importer-maturite /content/maturite/demo
```

Chaque commande doit se terminer par une ligne « … importé : {…} ».

### 6. Sauvegarder les clés générées

À conserver hors du serveur (gestionnaire de mots de passe, coffre) :

```bash
docker compose exec api npa afficher-cles
```

### 7. Ouvrir l'application

<http://127.0.0.1:8000> (machine locale uniquement). La documentation de
l'API est sur <http://127.0.0.1:8000/docs>. En production, placer un proxy
TLS devant.

### Mettre à jour

```bash
git pull
```

```bash
docker compose up -d --build
```

La base, les comptes et les référentiels sont conservés.

### Repartir de zéro

Efface la base **et** les clés (toutes les données) ; reprenez ensuite à
l'étape 3. Dans l'application d'authentification, supprimez l'ancienne
entrée « NormaPrep Audit » avant de scanner le nouveau QR code.

```bash
docker compose down -v
```

### En cas de problème

L'adresse ne répond pas (connexion refusée) : l'API ne tourne pas. Ces deux
commandes en donnent la raison.

```bash
docker compose ps
```

```bash
docker compose logs api --tail 30
```

| Message (dans le terminal ou les journaux) | Solution |
|---|---|
| `NPA_DB_PASSWORD manquant dans .env` | Créer `.env` (étape 2) |
| `CONFIGURATION INVALIDE : NPA_SECRET_KEY …` | Supprimer la ligne `NPA_SECRET_KEY=…` de `.env` (clé générée automatiquement) |
| `password authentication failed for user "npa"` | Le mot de passe de `.env` a changé : remettre l'ancien, ou repartir de zéro |
| `/bin/sh^M: bad interpreter` | Fichiers convertis par Git sous Windows : supprimer le dossier et cloner à nouveau |

### Avec Docker Desktop (Windows ou Mac)

Le premier lancement se fait en ligne de commande : Docker Desktop ne sait
pas créer une stack Compose depuis son interface. Ensuite, la stack apparaît
dans l'onglet **Containers** sous le nom `normaprep-audit` ; on peut la
démarrer, l'arrêter et lire les journaux de l'API depuis l'interface. L'onglet
**Exec** du conteneur `api` permet de lancer les commandes `npa` sans
terminal.

### Première connexion

Saisissez l'email et le mot de passe de l'administrateur : l'application
affiche un QR code à scanner avec une application d'authentification
(Microsoft Authenticator, Google Authenticator, FreeOTP…), puis demande le
code à 6 chiffres. Les connexions suivantes demandent directement le code.

## Utilisation

L'interface reprend le thème CARTO de NormaPrep. Le choix **Sombre** (par
défaut), **Clair** ou **Auto** (suit le réglage de l'ordinateur) se fait en
bas du menu ; il est mémorisé dans le navigateur. Les polices sont intégrées à
l'application : aucun appel à un service externe.


1. **Missions** : créez une mission (et son client), puis composez l'équipe :
   responsable, consultant, relecteur.
2. **Diagnostic** : depuis la mission, lancez un diagnostic de maturité. Il
   utilise la version active du référentiel, figée pour toute sa durée.
3. **Profilage** : les réponses font ressortir les réglementations
   (obligatoire, à vérifier, recommandé). Tranchez les « à vérifier » ; une
   justification est demandée quand vous vous écartez du calcul. Les
   réglementations retenues fixent la profondeur du questionnaire et les
   cibles.
4. **Plan d'entretiens** : l'outil regroupe les questions par interlocuteurs et
   les découpe en entretiens sous le budget (2 h par défaut). Passez les
   questions factuelles en pré-questionnaire.
5. **Pré-questionnaire** : créez un lien et envoyez-le au client. Il répond
   sans compte ; ses propositions apparaissent dans le questionnaire.
6. **Questionnaire** : un clic sur le niveau observé l'enregistre.
7. **Résultats** : scores, cibles, écarts, recommandations et audits
   proposés. Le responsable finalise : les résultats sont figés.

**Référentiels.** Un administrateur charge les référentiels de la
bibliothèque depuis **Administration › Référentiels** : un classeur Excel, une
feuille par référentiel, listées dans une feuille « Infos » (format :
[docs/format-contenu.md](docs/format-contenu.md)). « Vérifier » contrôle le
classeur sans rien écrire. Le responsable d'une mission peut aussi charger les
référentiels propres au client (politique interne…), visibles dans cette
mission seulement.

**Analyse de risques EBIOS RM** (atelier 1), depuis la mission, seule ou liée
à un diagnostic de maturité :

1. **Cadrage** : objet, périmètre, participants, cycles, échelle de gravité.
2. **Valeurs métier et biens supports**, reliés entre eux.
3. **Événements redoutés** : par valeur métier, impacts et gravité.
4. **Socle de sécurité** : choisissez les référentiels applicables et leur
   profil (ex. guide d'hygiène, Standard). Pour chaque mesure : appliquée,
   partiellement, non appliquée ou non applicable, avec l'écart et sa
   justification. Si l'analyse est liée à un diagnostic, les référentiels
   appelés par les réglementations retenues sont proposés, et « Pré-remplir »
   présume l'état des mesures depuis les réponses (à valider ; une saisie
   n'est jamais écrasée).

| Rôle sur la mission | Lire | Saisir | Gérer l'équipe, finaliser |
|---|---|---|---|
| Responsable | oui | oui | oui |
| Consultant | oui | oui | non |
| Relecteur | oui | non | non |

Un administrateur a tous les droits sur toutes les missions.

## Commandes d'administration

Dans le conteneur : `docker compose exec api npa <commande>`.

| Commande | Rôle |
|---|---|
| `afficher-cles` | Affiche les clés en usage, pour les sauvegarder |
| `generer-cles` | Génère deux clés, pour qui préfère les fournir dans `.env` |
| `creer-admin --email … --nom …` | Crée un administrateur |
| `importer-audit <fichier.json>` | Importe un référentiel d'audit |
| `importer-maturite <dossier>` | Importe un référentiel de maturité |
| `importer-excel <classeur.xlsx>` | Importe les référentiels d'un classeur Excel dans la bibliothèque |
| `couverture <code>` | Couverture d'un référentiel pivot (`--json` pour le détail) |

Les commandes d'import acceptent `--simulation` (valide sans écrire) et
`--remplacer` (remplace une version déjà importée, tant qu'aucun audit ne
l'utilise).

## API

La liste complète et à jour est sur `/docs`. Principales familles :

| Préfixe | Rôle |
|---|---|
| `/api/auth` | Connexion en deux étapes, compte courant |
| `/api/utilisateurs`, `/api/annuaire` | Comptes (admin), annuaire pour composer une équipe |
| `/api/clients`, `/api/missions` | Clients, missions, équipe, création des diagnostics |
| `/api/diagnostics/{id}` | Profilage, réglementations, questionnaire, ateliers, liens, résultats, finalisation |
| `/api/public/pre-questionnaire/{jeton}` | Pré-questionnaire du client, sans compte |
| `/api/contenu` | Référentiels, import, couverture |
| `/api/journal` | Journal d'audit (admin) |

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
- Accès aux missions par rôle ; une mission dont on n'est pas membre répond
  « introuvable ».
- Liens de pré-questionnaire : jeton aléatoire de 256 bits, seule son
  empreinte est conservée ; durée limitée (60 jours au plus), révocables.
- Conteneur API en système de fichiers en lecture seule, utilisateur non root,
  port exposé sur `127.0.0.1` uniquement.

**Conservez les clés** (`npa afficher-cles`) avec vos sauvegardes : sans
`NPA_CLE_CHIFFREMENT`, les secrets TOTP sont illisibles et chaque compte doit
refaire l'enrôlement. Elles vivent dans le volume Docker `cles` : un
`docker compose down -v` les efface, comme la base.

## Développement

```
Dockerfile        image unique : interface compilée + API
backend/
  app/
    api/          routes (auth, utilisateurs, missions, diagnostics, contenu, journal)
    contenu/      validation, import et couverture des référentiels
    diagnostic/   profilage, calculs, plan d'ateliers
    models.py     modèle de données
    securite.py   mots de passe, TOTP, jetons
    cli.py        commandes npa
  alembic/        migrations
  tests/          tests (PostgreSQL réel)
frontend/         interface web (React, TypeScript, Vite)
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

Interface : avec l'API lancée sur le port 8000, `npm run dev` sert
l'interface avec rechargement à chaud (les appels `/api` sont relayés).

```bash
cd frontend && npm ci && npm run dev
```
