// Libellés affichés pour les codes de l'API.

export const ROLES: Record<string, string> = {
  admin: "Administrateur",
  responsable: "Responsable",
  consultant: "Consultant",
  relecteur: "Relecteur",
};

export const INTERLOCUTEURS: Record<string, string> = {
  direction: "Direction",
  rssi: "RSSI",
  dsi: "DSI",
  administrateurs: "Administrateurs",
  developpement: "Développement",
  dpo: "DPO",
  achats: "Achats",
  metier: "Métiers",
};

export const MODES: Record<string, string> = {
  atelier: "En atelier",
  pre_questionnaire: "Pré-questionnaire",
  revue_documentaire: "Revue documentaire",
  import: "Import",
};

export const NIVEAUX_REGLEMENTATION: Record<string, string> = {
  obligatoire: "Obligatoire",
  a_verifier: "À vérifier",
  recommande: "Recommandé",
};

export const DECISIONS: Record<string, string> = {
  retenue: "Retenue",
  ecartee: "Écartée",
  en_attente: "En attente",
};

export const PROFONDEURS: Record<string, string> = {
  essentiel: "Essentiel",
  standard: "Standard",
  renforce: "Renforcé",
};

export const EFFORTS: Record<string, string> = { faible: "Faible", moyen: "Moyen", eleve: "Élevé" };

export const STATUTS: Record<string, string> = {
  en_cours: "En cours",
  finalise: "Finalisé",
  terminee: "Terminée",
};

export const interlocuteurs = (codes: string[]) => (codes.length ? codes.map((c) => INTERLOCUTEURS[c] ?? c).join(", ") : "Non attribué");

export const date = (iso: string | null | undefined) => (iso ? new Date(iso).toLocaleDateString("fr-FR") : "—");
export const dateHeure = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—";
export const nombre = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toLocaleString("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }));
export const minutes = (m: number) => {
  const h = Math.floor(m / 60);
  const r = Math.round(m % 60);
  return h ? `${h} h ${r.toString().padStart(2, "0")}` : `${r} min`;
};

// Couleur d'un grand thème : le référentiel donne un jeton CSS (« --carto-amber »)
// ou une couleur hexadécimale. Tout autre valeur est ignorée.
export const couleurTheme = (couleur: string | null | undefined): string => {
  if (couleur && /^--[a-z0-9-]+$/i.test(couleur)) return `var(${couleur})`;
  if (couleur && /^#[0-9a-f]{3,8}$/i.test(couleur)) return couleur;
  return "var(--accent)";
};
