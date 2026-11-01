import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { definirJeton, get, jeton, quandDeconnecte } from "./api";
import type { Moi } from "./types";

interface Session {
  moi: Moi | null;
  pret: boolean;
  connecter: (jetonAcces: string) => Promise<void>;
  deconnecter: () => void;
}

const Contexte = createContext<Session>({ moi: null, pret: false, connecter: async () => {}, deconnecter: () => {} });

export function FournisseurSession({ children }: { children: ReactNode }) {
  const [moi, setMoi] = useState<Moi | null>(null);
  const [pret, setPret] = useState(false);

  const deconnecter = () => {
    definirJeton(null);
    setMoi(null);
  };

  useEffect(() => {
    quandDeconnecte(() => setMoi(null));
    if (!jeton()) {
      setPret(true);
      return;
    }
    get<Moi>("/api/auth/moi")
      .then(setMoi, () => definirJeton(null))
      .finally(() => setPret(true));
  }, []);

  const connecter = async (jetonAcces: string) => {
    definirJeton(jetonAcces);
    setMoi(await get<Moi>("/api/auth/moi"));
  };

  return <Contexte.Provider value={{ moi, pret, connecter, deconnecter }}>{children}</Contexte.Provider>;
}

export const useSession = () => useContext(Contexte);
