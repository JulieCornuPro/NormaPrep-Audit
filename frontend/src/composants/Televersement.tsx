import { useRef, useState } from "react";
import { televerser } from "../api";
import type { ResultatImport } from "../types";
import { Erreur, useAction } from "./communs";

// Chargement d'un classeur Excel de référentiels : « Vérifier » valide sans
// rien écrire, « Importer » charge les feuilles listées dans « Infos ».
export default function Televersement({ url, apres }: { url: string; apres?: () => void }) {
  const champ = useRef<HTMLInputElement>(null);
  const [fichier, setFichier] = useState<File | null>(null);
  const [resultats, setResultats] = useState<ResultatImport[] | null>(null);
  const [simulation, setSimulation] = useState(false);
  const action = useAction();

  const envoyer = (sim: boolean) =>
    action.executer(async () => {
      setResultats(null);
      const r = await televerser<ResultatImport[]>(url, fichier!, { simulation: sim });
      setSimulation(sim);
      setResultats(r);
      if (!sim) apres?.();
    });

  return (
    <div>
      <div className="ligne">
        <input
          ref={champ}
          type="file"
          accept=".xlsx"
          aria-label="Classeur Excel"
          onChange={(e) => {
            setFichier(e.target.files?.[0] ?? null);
            setResultats(null);
          }}
          style={{ flex: 1, minWidth: 220 }}
        />
        <button disabled={!fichier || action.enCours} onClick={() => envoyer(true)}>Vérifier</button>
        <button className="principal" disabled={!fichier || action.enCours} onClick={() => envoyer(false)}>Importer</button>
      </div>
      <p className="discret">
        Classeur .xlsx : une feuille par référentiel, listées dans la feuille « Infos » (voir docs/format-contenu.md). Les feuilles non listées
        sont ignorées.
      </p>
      <Erreur erreur={action.erreur} />
      {resultats?.map((r, i) => (
        <div key={i} className={`message ${r.succes ? "ok" : "erreur"}`}>
          <strong>
            {r.feuille ? `Feuille « ${r.feuille} » : ` : ""}
            {r.succes
              ? r.deja_importe
                ? `${r.code} ${r.version} déjà importé à l'identique.`
                : simulation
                  ? `${r.code} ${r.version} valide, rien n'a été écrit.`
                  : `${r.code} ${r.version} importé (${Object.entries(r.stats)
                      .filter(([k]) => k !== "noeuds" && k !== "correspondances")
                      .map(([k, v]) => `${v} × ${k}`)
                      .join(", ")}).`
              : `refusé, ${r.erreurs.length} erreur(s) : rien n'a été écrit.`}
          </strong>
          {r.erreurs.length > 0 && <ul>{r.erreurs.slice(0, 30).map((e) => <li key={e}>{e}</li>)}</ul>}
          {r.erreurs.length > 30 && <p className="discret">… et {r.erreurs.length - 30} autre(s).</p>}
          {r.avertissements.length > 0 && (
            <details>
              <summary>{r.avertissements.length} avertissement(s)</summary>
              <ul>{r.avertissements.map((e) => <li key={e}>{e}</li>)}</ul>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
