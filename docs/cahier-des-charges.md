# Cahier des charges

Le cahier des charges est un document partagé, tenu à jour en dehors du
dépôt : <https://claude.ai/artifact/5HZQCazPj3PAfTgbndV8MB>

Il fait référence. Les décisions qui touchent directement le code sont
rappelées ci-dessous.

## Décisions prises

| Sujet | Décision |
|---|---|
| Usage | Interne au cabinet uniquement |
| Hébergement | Conteneur Docker, aucun appel à un service externe |
| IA | Aucune |
| Parcours | Profilage → diagnostic de maturité → socle de sécurité → audits ciblés → rapports |
| Contenu repris | Contenu et logique de NormaPrep Diagnostic, pas le plugin WordPress |
| Format des référentiels d'audit | Section > Exigence > Contrôle, contrôle et question séparés |
| Référentiel pivot | Guide d'hygiène ANSSI |
| Pré-remplissage du socle | Seuil défini par correspondance, règle par défaut sinon |
| Niveau des contrôles (CIS L1/L2, ANSSI standard/renforcé) | Choisi par l'auditeur |
| Benchmarks CIS | Convertis de PDF en Excel, puis importés |
| Budget d'un entretien | 2 heures (réglable par diagnostic) |
| Pré-questionnaire | Lien sans compte, le client propose un niveau, le consultant valide |
| Qualification (PASSI, ISO 17020) | Non visée pour le moment |

## Jalons

1. **Socle** — Docker, comptes et TOTP, import des référentiels,
   correspondances ANSSI, journal d'audit. *Livré.*
2. **Maturité** — interface web, missions et équipes, profilage, plan
   d'entretiens automatique, pré-questionnaire, scores et écarts. *Livré.*
3. **Référentiels et EBIOS RM atelier 1** — chargement des référentiels par
   l'interface (Excel, feuille « Infos »), arborescence libre et profils
   d'applicabilité, bibliothèque et référentiels client ; analyse de risques
   autonome ou liée à un diagnostic : cadrage, valeurs métier, biens supports,
   événements redoutés, socle de sécurité évalué par mesure, pré-remplissage
   depuis la maturité. *Livré.*
4. **Constats, rapports, audit de configuration** — constats et rapports
   communs (DOCX/PDF), benchmarks CIS convertis en Excel, import des sorties
   des scripts de collecte, rapport annoté.
5. **EBIOS RM ateliers 2 à 5** — sources de risque, scénarios stratégiques et
   opérationnels, traitement du risque.
6. **Audit de code, test d'intrusion.**
