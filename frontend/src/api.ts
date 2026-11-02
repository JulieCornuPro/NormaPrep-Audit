// Accès à l'API. Le jeton d'accès vit dans sessionStorage : il disparaît à la
// fermeture de l'onglet, et expire de toute façon côté serveur.

const CLE_JETON = "npa.jeton";

export class ErreurApi extends Error {
  constructor(
    public statut: number,
    public messages: string[],
  ) {
    super(messages.join(" "));
  }
}

export function jeton(): string | null {
  try {
    return sessionStorage.getItem(CLE_JETON);
  } catch {
    return null;
  }
}

export function definirJeton(valeur: string | null): void {
  try {
    if (valeur) sessionStorage.setItem(CLE_JETON, valeur);
    else sessionStorage.removeItem(CLE_JETON);
  } catch {
    /* stockage indisponible : la session ne survivra pas au rechargement */
  }
}

let surDeconnexion: () => void = () => {};
export function quandDeconnecte(fn: () => void): void {
  surDeconnexion = fn;
}

function messages(corps: unknown, statut: number): string[] {
  const detail = (corps as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return [detail];
  if (Array.isArray(detail)) {
    return detail.map((d) => (typeof d === "string" ? d : (d as { msg?: string }).msg ?? JSON.stringify(d)));
  }
  return [`Erreur ${statut}.`];
}

export async function api<T = unknown>(chemin: string, options: { methode?: string; corps?: unknown; public?: boolean } = {}): Promise<T> {
  const entetes: Record<string, string> = {};
  if (options.corps !== undefined) entetes["Content-Type"] = "application/json";
  const j = jeton();
  if (j && !options.public) entetes["Authorization"] = `Bearer ${j}`;

  const reponse = await fetch(chemin, {
    method: options.methode ?? (options.corps === undefined ? "GET" : "POST"),
    headers: entetes,
    body: options.corps === undefined ? undefined : JSON.stringify(options.corps),
  });
  const texte = await reponse.text();
  const corps = texte ? JSON.parse(texte) : null;
  if (!reponse.ok) {
    if (reponse.status === 401 && !options.public && j) {
      definirJeton(null);
      surDeconnexion();
    }
    throw new ErreurApi(reponse.status, messages(corps, reponse.status));
  }
  return corps as T;
}

export const get = <T,>(chemin: string) => api<T>(chemin);
export const post = <T,>(chemin: string, corps: unknown = {}) => api<T>(chemin, { methode: "POST", corps });
export const put = <T,>(chemin: string, corps: unknown) => api<T>(chemin, { methode: "PUT", corps });
export const patch = <T,>(chemin: string, corps: unknown) => api<T>(chemin, { methode: "PATCH", corps });
export const del = <T,>(chemin: string) => api<T>(chemin, { methode: "DELETE" });

/** Envoie un fichier (formulaire multipart) avec des champs simples. */
export async function televerser<T>(chemin: string, fichier: File, champs: Record<string, string | boolean> = {}): Promise<T> {
  const formulaire = new FormData();
  formulaire.append("fichier", fichier);
  for (const [cle, valeur] of Object.entries(champs)) formulaire.append(cle, String(valeur));
  const entetes: Record<string, string> = {};
  const j = jeton();
  if (j) entetes["Authorization"] = `Bearer ${j}`;
  const reponse = await fetch(chemin, { method: "POST", headers: entetes, body: formulaire });
  const texte = await reponse.text();
  const corps = texte ? JSON.parse(texte) : null;
  if (!reponse.ok) {
    if (reponse.status === 401 && j) {
      definirJeton(null);
      surDeconnexion();
    }
    throw new ErreurApi(reponse.status, messages(corps, reponse.status));
  }
  return corps as T;
}
