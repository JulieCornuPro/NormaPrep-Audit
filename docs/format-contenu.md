# Format du contenu

Le contenu (référentiels) vit dans le dossier `content/`, monté en lecture
seule dans le conteneur sous `/content`. Il est importé par un administrateur
(API ou commande `npa`). Deux familles de référentiels coexistent :

| Famille | Forme | Exemple livré |
|---|---|---|
| Référentiel de **maturité** | un dossier au format NormaPrep | `content/maturite/demo/` |
| Référentiel d'**audit** | un fichier JSON Section > Exigence > Contrôle | `content/referentiels/anssi-hygiene-exemple.json` |

## Règles communes

- **Codes stables** : lettres, chiffres, `-`, `_` et `.` uniquement. Ils
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

### Prestation (`_prestations.json`)

| Champ | Règle |
|---|---|
| `referentiel_audit` | Code d'un référentiel d'audit (version active en base) : le type d'audit proposé |
| `sections` | Codes de sections de ce référentiel, à inclure dans l'audit proposé. Exige `referentiel_audit` |

```json
{ "code": "AUDIT-ANSSI", "libelle": "Audit de conformité au guide d'hygiène ANSSI",
  "referentiel_audit": "ANSSI-HYG", "sections": ["S09"] }
```

## Référentiel d'audit

Un fichier JSON par référentiel (et par version).

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
| | `niveaux` | non | Si présent, liste des valeurs admises pour `niveau` des contrôles |
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

- Import des benchmarks CIS depuis Excel (convertis de leurs PDF) : jalon 4.
- Référentiel ANSSI complet (42 mesures) : l'exemple livré n'en contient que
  5, avec des intitulés à vérifier sur le guide officiel.
