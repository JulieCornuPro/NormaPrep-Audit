# Format du contenu

Le contenu (référentiels) vit dans le dossier `content/`, monté en lecture
seule dans le conteneur sous `/content`. Il est importé par un administrateur
(API ou commande `npa`). Deux familles de référentiels coexistent :

| Famille | Forme | Exemple livré |
|---|---|---|
| Référentiel de **maturité** | un dossier au format NormaPrep | `content/maturite/demo/` |
| Référentiel d'**audit** | un **classeur Excel** chargé depuis l'interface (recommandé) | — |
| | ou un fichier JSON Section > Exigence > Contrôle | `content/referentiels/anssi-hygiene-exemple.json` |

Les référentiels d'audit servent aux socles de sécurité EBIOS RM et aux
audits. Ils vivent dans la **bibliothèque** (chargés par un administrateur,
visibles partout) ou sont **propres à un client** (chargés par le responsable
de la mission, visibles dans cette mission seulement ; un même code peut
exister dans la bibliothèque et chez un client).

## Règles communes

- **Codes stables** : lettres, chiffres, `-`, `_`, `.` et `/` uniquement. Ils
  identifient un élément d'une version à l'autre et servent aux
  correspondances.
- **Tout ou rien** : à la moindre erreur, l'import est refusé et rien n'est
  écrit. Le rapport donne chaque erreur avec son fichier et son emplacement
  (`fichier › chemin — message`). Les avertissements ne bloquent pas.
- **Versions figées** : chaque import crée une version complète et
  immuable. Réimporter le même contenu sous la même version ne fait rien ; un
  contenu différent sous une version déjà importée est refusé : il faut
  changer la `version`. La dernière version importée devient la **version
  active** de son code ; les anciennes restent consultables. (Différence avec
  NormaPrep, qui mettait à jour le référentiel en place.)
- **Ordre d'import** : une correspondance ou une prestation qui cite un autre
  référentiel est vérifiée contre la version active de celui-ci. Importez
  d'abord le référentiel pivot (ANSSI), puis ceux qui s'y rattachent.
- Encodage UTF-8.

## Référentiel de maturité (format NormaPrep)

Le format de NormaPrep Diagnostic est accepté **tel quel** (voir son
`FORMAT.md` : `_referentiel.json`, `_profilage.json`, `_reglementations.json`,
`_prestations.json`, un fichier par sous-thème dans des sous-dossiers). Les
règles de validation et les messages sont les mêmes.

Ajouts, tous facultatifs :

### `_referentiel.json`

| Champ | Règle |
|---|---|
| `code` | Code du référentiel, 50 caractères max. Défaut : `NORMAPREP-MATURITE` |
| `source`, `licence` | Textes libres, affichés avec le référentiel |

### Question (fichier de sous-thème)

| Champ | Valeurs | Défaut | Rôle |
|---|---|---|---|
| `type` | `niveaux`, `fermee`, `demonstration`, `ouverte` | `niveaux` | Fixe la durée par défaut de la question |
| `duree` | minutes, > 0 et ≤ 120 | durée du type | Estimation propre à la question |
| `mode` | `atelier`, `pre_questionnaire`, `revue_documentaire`, `import` | `atelier` | Où la réponse est recueillie |
| `interlocuteurs` | liste parmi `direction`, `rssi`, `dsi`, `administrateurs`, `developpement`, `dpo`, `achats`, `metier` | vide | Regroupement des ateliers |
| `correspondances` | voir ci-dessous | vide | Lien vers un référentiel d'audit |

Les six `niveaux` restent obligatoires quel que soit le `type`.

### Réglementation (`_reglementations.json`)

| Champ | Règle |
|---|---|
| `referentiel` | Code d'un référentiel d'audit de la bibliothèque : proposé dans le socle EBIOS RM quand la réglementation est retenue. Absent en base : avertissement |
| `profil` | Profil de ce référentiel à appliquer (ex. `Renforcé`). Le plus exigeant l'emporte si plusieurs réglementations appellent le même référentiel |

```json
{ "code": "NIS2-EE", "libelle": "NIS 2 — entité essentielle",
  "referentiel": "ANSSI-HYG", "profil": "Renforcé" }
```

### Prestation (`_prestations.json`)

| Champ | Règle |
|---|---|
| `referentiel_audit` | Code d'un référentiel d'audit (version active en base) : le type d'audit proposé |
| `sections` | Codes de sections de ce référentiel, à inclure dans l'audit proposé. Exige `referentiel_audit` |

```json
{ "code": "AUDIT-ANSSI", "libelle": "Audit de conformité au guide d'hygiène ANSSI",
  "referentiel_audit": "ANSSI-HYG", "sections": ["S09"] }
```

## Référentiel d'audit : classeur Excel

Format du brouillon « Socle de sécurité ». Chargement : **Administration ›
Référentiels** (bibliothèque), carte **Référentiels du client** d'une mission,
ou `npa importer-excel classeur.xlsx`. « Vérifier » (`--simulation`) valide
sans rien écrire. Taille maximale : 15 Mo.

**Feuille « Infos »** (obligatoire) : une ligne par feuille à importer. Les
feuilles qui n'y figurent pas sont ignorées : on peut garder dans le même
classeur des référentiels en cours de rédaction.

| Colonne | Obligatoire | Règle |
|---|---|---|
| Feuille | oui | Nom exact de la feuille |
| Code | oui | Code du référentiel, ex. `ANSSI-HYG` |
| Version | oui | Changer de version pour importer un contenu modifié |
| Libellé | oui | |
| Source, Licence | non | Licence absente : avertissement |
| Niveau socle | non | Nom du niveau évalué dans le socle EBIOS RM (ex. `Exigence`). Défaut : le deuxième niveau |
| Profils cumulatifs | non | `Oui` : un élément applicable à un profil l'est aussi aux suivants (Standard → Renforcé) ; une incohérence est corrigée avec un avertissement |

**Feuille d'un référentiel** : une ligne d'en-têtes, puis une ligne par
élément.

| Colonnes | Contenu |
|---|---|
| Niveaux, de gauche à droite (ex. Section, Exigence, Contrôle, Contrôle détaillé) | `code - libellé` (tiret entouré d'espaces, au moins après), ou `-` / vide si le niveau est absent. Le nombre de niveaux est libre |
| Profils, en fin de ligne (ex. Standard, Renforcé) | `Oui` / `Non`. Une colonne qui ne contient que Oui/Non est un profil |
| Facultatives, reconnues par leur en-tête | Interlocuteurs, Méthode, Preuves attendues, Vérification, Valeur attendue, Recommandation, Description |

Chaque ligne décrit l'élément le plus profond qu'elle renseigne ; ses parents
sont dans les colonnes de gauche. Un parent répété sur plusieurs lignes garde
le même libellé. Une mesure sans contrôle est admise (c'est alors une
exigence). Les codes sont uniques dans toute la feuille.

| Section | Exigence | Contrôle | Standard | Renforcé |
|---|---|---|---|---|
| 1 - Sensibiliser et former | 1.1 - Former les équipes opérationnelles | - | Oui | Oui |
| 1 - Sensibiliser et former | 1.1 - Former les équipes opérationnelles | 1.1.1 - Plan de formation à jour | Oui | Oui |
| 10 - Pour aller plus loin | 42 - Mener des audits réguliers | - | Non | Oui |

Erreurs fréquentes : cellule sans tiret (`7.A Cloisonnement` au lieu de
`7.A - Cloisonnement`), code en double, même code avec deux libellés.

## Référentiel d'audit : fichier JSON

Un fichier JSON par référentiel (et par version), importé depuis le dossier
`content/`. Il est converti dans la même arborescence que l'Excel (niveaux
Section, Exigence, Contrôle).

```json
{
  "code": "ANSSI-HYG",
  "version": "2017.1",
  "libelle": "Guide d'hygiène informatique de l'ANSSI",
  "source": "ANSSI, 2017",
  "licence": "Licence Ouverte / Open Licence (Etalab)",
  "niveaux": ["standard", "renforce"],
  "sections": [
    { "code": "S09", "libelle": "Superviser, auditer, réagir",
      "exigences": [
        { "code": "37", "libelle": "Définir et appliquer une politique de sauvegarde des composants critiques",
          "controles": [
            { "code": "37.a",
              "intitule": "Une politique de sauvegarde écrite définit le périmètre et la fréquence",
              "niveau": "standard",
              "methode": "revue_documentaire",
              "preuves_attendues": ["Politique de sauvegarde"] }
          ] }
      ] }
  ]
}
```

| Élément | Champ | Obligatoire | Règle |
|---|---|---|---|
| Référentiel | `code` | oui | 50 caractères max |
| | `version` | oui | 30 caractères max |
| | `libelle` | oui | |
| | `source`, `licence` | non | Licence absente : avertissement |
| | `niveaux` | non | Profils d'applicabilité (ex. `Standard`, `Renforcé`), cumulatifs : un contrôle de niveau `Standard` vaut aussi pour `Renforcé` |
| Section | `code`, `libelle` | oui | |
| | `description`, `exigences` | non | |
| Exigence | `code`, `libelle` | oui | Une exigence sans contrôle est admise (référentiel pivot décrit par mesures) |
| | `description`, `controles` | non | |
| Contrôle | `code`, `intitule` | oui | |
| | `methode` | oui | `entretien`, `revue_documentaire`, `observation`, `commande` |
| | `niveau` | non | Parmi `niveaux` s'il est défini (ex. CIS `L1`/`L2`) |
| | `verification`, `valeur_attendue` | non | Pour l'évaluation automatique après import de collecte |
| | `preuves_attendues` | non | Liste de textes |
| | `recommandation`, `description` | non | |
| | `poids` | non | > 0, 1 par défaut |
| | `correspondances` | non | Vers un **autre** référentiel, sans seuils |

Les codes de section, d'exigence et de contrôle partagent le même espace :
ils sont **uniques dans tout le référentiel**. Une correspondance peut ainsi
viser une exigence (une mesure ANSSI) aussi bien qu'un contrôle (un point
CIS).

## Correspondances

```json
"correspondances": [
  { "referentiel": "ANSSI-HYG", "code": "37", "seuil_applique": 3, "seuil_partiel": 1 }
]
```

| Champ | Règle |
|---|---|
| `referentiel` | Code d'un référentiel d'audit dont une version est active en base |
| `code` | Code d'une exigence ou d'un contrôle de cette version |
| `seuil_applique`, `seuil_partiel` | Questions de maturité seulement, entiers de 1 à 5, `seuil_partiel` ≤ `seuil_applique` |

**Seuils** (décision : un seuil par correspondance). Ils servent à présumer
l'état de la cible à partir du niveau de maturité constaté, pour pré-remplir
le socle de sécurité :

- niveau ≥ `seuil_applique` → appliquée ;
- niveau ≥ `seuil_partiel` → partiellement appliquée ;
- sinon → non appliquée.

Seuils absents : règle par défaut de l'outil (appliquée à partir de 3,
partielle à partir de 1). Dans tous les cas, ce n'est qu'un pré-remplissage :
l'auditeur confirme chaque mesure.

## Couverture

`npa couverture ANSSI-HYG` (ou `GET /api/contenu/couverture/ANSSI-HYG`)
liste, pour chaque exigence du pivot, les questions et contrôles qui y sont
reliés parmi les versions actives, et les exigences non couvertes.

## À venir

- Benchmarks CIS convertis de PDF en Excel, et sorties des scripts de
  collecte : jalon 4.
