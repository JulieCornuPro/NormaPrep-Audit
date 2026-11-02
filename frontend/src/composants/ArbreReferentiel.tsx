import { useState } from "react";
import type { NoeudArbre } from "../types";
import { Pastille } from "./communs";

// Arborescence d'un référentiel : niveaux dépliables, profils d'applicabilité.
export default function ArbreReferentiel({ racines, niveaux, profils }: { racines: NoeudArbre[]; niveaux: string[]; profils: string[] }) {
  return (
    <div>
      {racines.map((n) => <Noeud key={n.code} n={n} niveaux={niveaux} profils={profils} ouvert={false} />)}
    </div>
  );
}

function Noeud({ n, niveaux, profils, ouvert }: { n: NoeudArbre; niveaux: string[]; profils: string[]; ouvert: boolean }) {
  const [deplie, setDeplie] = useState(ouvert);
  const partiel = profils.length > 0 && n.profils.length > 0 && n.profils.length < profils.length;
  return (
    <div style={{ marginLeft: n.niveau ? 18 : 0, borderLeft: n.niveau ? "1px solid var(--bordure)" : "none", paddingLeft: n.niveau ? 10 : 0 }}>
      <div className="ligne" style={{ padding: "4px 0", gap: 8 }}>
        {n.enfants.length > 0 ? (
          <button className="lien" aria-expanded={deplie} onClick={() => setDeplie(!deplie)} style={{ width: 18 }}>
            {deplie ? "−" : "+"}
          </button>
        ) : (
          <span style={{ width: 18 }} />
        )}
        <code>{n.code}</code>
        <span style={{ flex: 1, fontWeight: n.niveau === 0 ? 700 : 500 }}>{n.libelle}</span>
        <span className="discret mono" style={{ fontSize: 12 }}>{niveaux[n.niveau] ?? ""}</span>
        {partiel && n.profils.map((p) => <Pastille key={p} texte={p} ton="accent" />)}
      </div>
      {deplie && n.enfants.map((e) => <Noeud key={e.code} n={e} niveaux={niveaux} profils={profils} ouvert={false} />)}
    </div>
  );
}
