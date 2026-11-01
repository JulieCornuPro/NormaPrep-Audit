import { useCallback, useEffect, useState } from "react";
import { ErreurApi } from "../api";

export function Erreur({ erreur }: { erreur: unknown }) {
  if (!erreur) return null;
  const messages = erreur instanceof ErreurApi ? erreur.messages : [String(erreur)];
  return (
    <div className="message erreur" role="alert">
      {messages.length === 1 ? messages[0] : <ul>{messages.map((m) => <li key={m}>{m}</li>)}</ul>}
    </div>
  );
}

export function Chargement() {
  return <p className="discret">Chargement…</p>;
}

/** Charge une donnée et la recharge à la demande. */
export function useDonnees<T>(charger: () => Promise<T>, deps: unknown[]) {
  const [donnees, setDonnees] = useState<T | null>(null);
  const [erreur, setErreur] = useState<unknown>(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const recharger = useCallback(() => {
    setErreur(null);
    return charger().then(setDonnees, setErreur);
  }, deps);
  useEffect(() => {
    recharger();
  }, [recharger]);
  return { donnees, erreur, recharger, setDonnees };
}

/** Exécute une action et garde son erreur pour l'afficher. */
export function useAction() {
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState<unknown>(null);
  const executer = async <T,>(fn: () => Promise<T>): Promise<T | undefined> => {
    setEnCours(true);
    setErreur(null);
    try {
      return await fn();
    } catch (e) {
      setErreur(e);
      return undefined;
    } finally {
      setEnCours(false);
    }
  };
  return { enCours, erreur, executer, setErreur };
}

export function Pastille({ texte, ton }: { texte: string; ton?: "ok" | "alerte" | "danger" | "accent" }) {
  return <span className={`pastille ${ton ?? ""}`}>{texte}</span>;
}
