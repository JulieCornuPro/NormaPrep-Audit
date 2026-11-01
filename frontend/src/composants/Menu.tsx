import { useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { useSession } from "../session";
import { appliquerTheme, themeMemorise, THEMES, type Theme } from "../theme";

// Icônes au trait, dans l'esprit de NormaPrep.
const icones: Record<string, ReactNode> = {
  missions: <path d="M4 5h16v14H4zM4 9h16M9 5V3h6v2" />,
  utilisateurs: (
    <>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M16 4.5a3.5 3.5 0 0 1 0 7M18 14c2.2.6 3.5 2.8 3.5 6" />
    </>
  ),
  referentiels: <path d="M5 3h11l3 3v15H5zM9 8h7M9 12h7M9 16h5" />,
  journal: <path d="M12 7v5l3 2M3 12a9 9 0 1 0 3-6.7M3 4v4h4" />,
  sortie: <path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10" />,
};

const Icone = ({ nom }: { nom: string }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">{icones[nom]}</svg>
);

function initiales(nom: string): string {
  return nom
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((m) => m[0]!.toUpperCase())
    .join("");
}

export function ChoixTheme() {
  const [theme, setTheme] = useState<Theme>(themeMemorise());
  return (
    <div className="choix-theme" role="group" aria-label="Thème d'affichage">
      {THEMES.map((t) => (
        <button
          key={t.valeur}
          type="button"
          aria-pressed={theme === t.valeur}
          onClick={() => {
            appliquerTheme(t.valeur);
            setTheme(t.valeur);
          }}
        >
          {t.libelle}
        </button>
      ))}
    </div>
  );
}

export default function Menu() {
  const { moi, deconnecter } = useSession();
  if (!moi) return null;
  return (
    <aside className="menu">
      <Link to="/" className="marque">NormaPrep <span>Audit</span></Link>
      <NavLink to="/compte" className="utilisateur">
        <span className="avatar" aria-hidden="true">{initiales(moi.nom)}</span>
        <span style={{ overflow: "hidden" }}>
          <span className="nom" style={{ display: "block" }}>{moi.nom}</span>
          <span className="role">{moi.est_admin ? "Administrateur" : "Consultant"}</span>
        </span>
      </NavLink>
      <nav aria-label="Navigation principale">
        <span className="groupe">Audit</span>
        <NavLink to="/missions"><Icone nom="missions" />Missions</NavLink>
        {moi.est_admin && (
          <>
            <span className="groupe">Administration</span>
            <NavLink to="/admin/utilisateurs"><Icone nom="utilisateurs" />Utilisateurs</NavLink>
            <NavLink to="/admin/referentiels"><Icone nom="referentiels" />Référentiels</NavLink>
            <NavLink to="/admin/journal"><Icone nom="journal" />Journal</NavLink>
          </>
        )}
      </nav>
      <div className="bas">
        <ChoixTheme />
        <button type="button" onClick={deconnecter}><Icone nom="sortie" />Se déconnecter</button>
      </div>
    </aside>
  );
}
