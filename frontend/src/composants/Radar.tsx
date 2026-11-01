// Radar constaté / cible : un axe par sous-thème, échelle 0 à 5.

import { nombre } from "../libelles";

interface Axe {
  code: string;
  libelle: string;
  score: number | null;
  cible: number | null;
}

const T = 360;
const C = T / 2;
const R = 120;

function point(i: number, n: number, valeur: number): [number, number] {
  const angle = -Math.PI / 2 + (2 * Math.PI * i) / n;
  const r = (R * valeur) / 5;
  return [C + r * Math.cos(angle), C + r * Math.sin(angle)];
}

const trace = (axes: Axe[], cle: "score" | "cible") =>
  axes.map((a, i) => point(i, axes.length, a[cle] ?? 0).map((v) => v.toFixed(1)).join(",")).join(" ");

export default function Radar({ axes }: { axes: Axe[] }) {
  if (axes.length === 0) return <p className="discret">Aucun sous-thème évalué pour le moment.</p>;
  if (axes.length < 3) return <Barres axes={axes} />;
  const n = axes.length;
  return (
    <figure style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${T} ${T}`} role="img" aria-label="Maturité constatée et cible par sous-thème" style={{ width: "100%", maxWidth: 420 }}>
        {[1, 2, 3, 4, 5].map((niveau) => (
          <polygon key={niveau} points={axes.map((_, i) => point(i, n, niveau).join(",")).join(" ")} fill="none" stroke="var(--bordure)" />
        ))}
        {axes.map((a, i) => {
          const [x, y] = point(i, n, 5);
          const [lx, ly] = point(i, n, 5.75);
          return (
            <g key={a.code}>
              <line x1={C} y1={C} x2={x} y2={y} stroke="var(--bordure)" />
              <text x={lx} y={ly} fontSize="11" textAnchor="middle" dominantBaseline="middle" fill="var(--texte-2)">{a.code}</text>
            </g>
          );
        })}
        <polygon points={trace(axes, "cible")} fill="none" stroke="var(--alerte)" strokeWidth="2" strokeDasharray="5 4" />
        <polygon points={trace(axes, "score")} fill="var(--accent)" fillOpacity="0.18" stroke="var(--accent)" strokeWidth="2" />
      </svg>
      <figcaption className="ligne discret">
        <span><span style={{ color: "var(--accent)" }}>■</span> Constaté</span>
        <span><span style={{ color: "var(--alerte)" }}>┅</span> Cible</span>
      </figcaption>
    </figure>
  );
}

// Moins de trois axes : un radar n'a pas de sens, on compare en barres.
function Barres({ axes }: { axes: Axe[] }) {
  return (
    <figure style={{ margin: 0 }}>
      {axes.map((a) => (
        <div key={a.code} style={{ margin: "12px 0" }}>
          <div className="ligne espace">
            <span>{a.code} · {a.libelle}</span>
            <span className="discret">{nombre(a.score)} / cible {nombre(a.cible)}</span>
          </div>
          <div style={{ position: "relative", height: 14, background: "var(--surface-2)", borderRadius: 4 }} aria-hidden="true">
            <div style={{ width: `${((a.score ?? 0) / 5) * 100}%`, height: "100%", background: "var(--accent)", borderRadius: 4 }} />
            {a.cible !== null && (
              <div style={{ position: "absolute", top: -3, bottom: -3, left: `calc(${(a.cible / 5) * 100}% - 1px)`, borderLeft: "2px dashed var(--alerte)" }} />
            )}
          </div>
        </div>
      ))}
      <figcaption className="ligne discret">
        <span><span style={{ color: "var(--accent)" }}>■</span> Constaté (sur 5)</span>
        <span><span style={{ color: "var(--alerte)" }}>┆</span> Cible</span>
      </figcaption>
    </figure>
  );
}
