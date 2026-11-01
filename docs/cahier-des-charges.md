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
| Budget d'un atelier | 2 heures |
| Qualification (PASSI, ISO 17020) | Non visée pour le moment |

## Jalons

1. **Socle** — Docker, comptes et TOTP, import des référentiels,
   correspondances ANSSI, journal d'audit. *Livré (voir README).*
2. **Maturité** — profilage, plan d'ateliers automatique, pré-questionnaire,
   scores et écarts.
3. **Audits** — socle EBIOS RM, conformité ANSSI, pré-remplissage, preuves et
   constats.
4. **Rapports** — modèles DOCX et PDF, scripts de collecte, premier benchmark
   CIS, circuit de validation.
