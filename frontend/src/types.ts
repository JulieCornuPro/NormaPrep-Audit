// Formes renvoyées par l'API (sous-ensemble utile à l'interface).

export interface Moi {
  id: number;
  email: string;
  nom: string;
  est_admin: boolean;
}

export interface Client {
  id: number;
  nom: string;
  secteur: string;
  notes: string;
}

export interface Membre {
  utilisateur_id: number;
  nom: string;
  email: string;
  role: string;
}

export interface DiagnosticResume {
  id: number;
  statut: string;
  referentiel: string;
  version: string;
  cree_le: string;
  finalise_le: string | null;
}

export interface Mission {
  id: number;
  titre: string;
  perimetre: string;
  statut: string;
  cree_le: string;
  client: Client;
  mon_role: string | null;
  droits: string[];
  membres: Membre[];
  diagnostics: DiagnosticResume[];
  analyses: AnalyseResume[];
}

export interface Synthese {
  id: number;
  mission_id: number;
  mission_titre: string;
  client: string;
  statut: string;
  referentiel: { code: string; version: string; libelle: string };
  droits: string[];
  budget_atelier_minutes: number;
  ouverture_minutes: number;
  profilage_incomplet: string[];
  reglementations_en_attente: string[];
  progression: Progression;
  finalise_le: string | null;
}

export interface Progression {
  retenues: number;
  repondues: number;
  restantes: number;
}

export interface QuestionProfil {
  code: string;
  libelle: string;
  aide: string;
  type: "choix_unique" | "choix_multiple";
  choix: { code: string; libelle: string }[];
  visible: boolean;
}

export interface LigneReglementation {
  code: string;
  libelle: string;
  nature: string;
  description: string;
  echeance: string;
  niveau_calcule: string;
  decision: string;
  origine: string;
  critere: string;
  justification: string;
  decisions_admises: string[];
}

export interface VueProfilage {
  questions: QuestionProfil[];
  reponses: Record<string, string[]>;
  sans_reponse: string[];
  reglementations: LigneReglementation[];
  ajoutables: { code: string; libelle: string }[];
}

export interface ReponseQ {
  niveau: number | null;
  non_applicable: boolean;
  commentaire: string;
  saisi_le: string | null;
  proposition: { niveau: number | null; commentaire: string; le: string } | null;
}

export interface QuestionQ {
  ref: string;
  enonce: string;
  aide: string;
  profondeur: string;
  niveaux: Record<string, string>;
  references: string[];
  type: string;
  duree: number;
  mode: string;
  mode_contenu: string;
  interlocuteurs: string[];
  reponse: ReponseQ;
}

export interface SousThemeQ {
  code: string;
  libelle: string;
  profondeur: string;
  cible: number | null;
  reglementation: string | null;
  questions: QuestionQ[];
}

export interface Questionnaire {
  themes: { code: string; libelle: string; couleur: string; sous_themes: SousThemeQ[] }[];
  progression: Progression;
}

export interface QuestionPlan {
  ref: string;
  enonce: string;
  sous_theme: string;
  sous_theme_libelle: string;
  type: string;
  duree: number;
  interlocuteurs: string[];
}

export interface PlanAteliers {
  budget_minutes: number;
  ouverture_minutes: number;
  ateliers: {
    numero: number;
    interlocuteurs: string[];
    sous_themes: { code: string; libelle: string }[];
    questions: QuestionPlan[];
    duree_minutes: number;
  }[];
  duree_totale_minutes: number;
  depassements: number[];
  hors_atelier: Record<string, QuestionPlan[]>;
  duree_pre_questionnaire_minutes: number;
}

export interface Valeurs {
  score: number | null;
  cible: number | null;
  ecart: number | null;
}

export interface Resultats {
  global: Valeurs;
  themes: (Valeurs & {
    code: string;
    libelle: string;
    couleur: string;
    sous_themes: (Valeurs & {
      code: string;
      libelle: string;
      non_applicable: boolean;
      reglementation: string | null;
      profondeur: string;
      nb_questions: number;
    })[];
  })[];
  progression: Progression;
  recommandations: {
    ref: string;
    sous_theme: string;
    sous_theme_libelle: string;
    question: string | null;
    texte: string;
    seuil: number;
    effort: string;
    quick_win: boolean;
    niveau_constate: number | null;
    ecart_sous_theme: number | null;
    prestation_libelle: string | null;
  }[];
  audits_proposes: {
    code: string;
    libelle: string;
    description: string;
    referentiel_audit: string | null;
    sections: string[];
    sous_themes: string[];
  }[];
  fige: boolean;
}

export interface Lien {
  id: number;
  destinataire: string;
  expire_le: string;
  revoque: boolean;
  actif: boolean;
  cree_le: string;
  derniere_utilisation: string | null;
  jeton?: string;
  chemin?: string;
}

export interface ReferentielResume {
  id: number;
  code: string;
  version: string;
  nature: string;
  libelle: string;
  source: string;
  licence: string;
  actif: boolean;
  importe_le: string;
  avertissements: string[];
  niveaux: string[];
  profils: string[];
  niveau_socle: number;
  mission_id: number | null;
}

export interface NoeudArbre {
  code: string;
  libelle: string;
  niveau: number;
  profils: string[];
  description: string;
  enfants: NoeudArbre[];
}

export interface ResultatImport {
  succes: boolean;
  deja_importe: boolean;
  code: string;
  version: string;
  feuille: string;
  erreurs: string[];
  avertissements: string[];
  stats: Record<string, number>;
}

export interface AnalyseResume {
  id: number;
  titre: string;
  statut: string;
  cree_le: string;
}

export interface NiveauGravite {
  niveau: number;
  libelle: string;
  description: string;
}

export interface Analyse {
  id: number;
  mission_id: number;
  mission_titre: string;
  client: string;
  titre: string;
  statut: string;
  objet: string;
  perimetre: string;
  participants: string;
  cycle_strategique_mois: number | null;
  cycle_operationnel_mois: number | null;
  echelle_gravite: NiveauGravite[];
  diagnostic_id: number | null;
  diagnostics_mission: { id: number; statut: string }[];
  droits: string[];
  compte: Record<string, number>;
  impacts: string[];
}

export interface ValeurMetier {
  id: number;
  nom: string;
  nature: "processus" | "information";
  description: string;
  responsable: string;
}

export interface BienSupport {
  id: number;
  nom: string;
  description: string;
  responsable: string;
  valeurs_metier: number[];
}

export interface EvenementRedoute {
  id: number;
  valeur_metier_id: number;
  description: string;
  impacts: string[];
  gravite: number;
}

export interface ElementSocle {
  code: string;
  libelle: string;
  groupe: string;
  etat: string;
  ecart: string;
  justification: string;
  source: string | null;
  saisi_le: string | null;
  details: { code: string; libelle: string; niveau: number }[];
}

export interface ReferentielSocle {
  id: number;
  referentiel: { id: number; code: string; version: string; libelle: string; client: boolean; profils: string[]; niveau: string };
  profil: string | null;
  motif: string;
  compte: Record<string, number>;
  sans_justification: number;
  elements: ElementSocle[];
}

export interface Socle {
  referentiels: ReferentielSocle[];
  proposes: { referentiel_id: number; code: string; libelle: string; profil: string | null; motifs: string[] }[];
  disponibles: { id: number; code: string; version: string; libelle: string; profils: string[]; client: boolean }[];
}
