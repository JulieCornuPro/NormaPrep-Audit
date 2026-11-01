// Thème d'affichage : sombre (défaut, CARTO), clair, ou auto (suit le système).
// Mémorisé dans le navigateur ; le stockage peut être indisponible (navigation
// privée) : l'application fonctionne alors avec le thème par défaut.

export type Theme = "sombre" | "clair" | "auto";
export const THEMES: { valeur: Theme; libelle: string }[] = [
  { valeur: "sombre", libelle: "Sombre" },
  { valeur: "clair", libelle: "Clair" },
  { valeur: "auto", libelle: "Auto" },
];

const CLE = "npa.theme";

export function themeMemorise(): Theme {
  try {
    const v = localStorage.getItem(CLE);
    if (v === "sombre" || v === "clair" || v === "auto") return v;
  } catch {
    /* stockage indisponible */
  }
  return "sombre";
}

export function appliquerTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(CLE, theme);
  } catch {
    /* stockage indisponible : le choix vaut pour cette page seulement */
  }
}
