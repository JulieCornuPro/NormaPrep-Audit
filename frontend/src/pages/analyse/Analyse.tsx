import { Link, Navigate, NavLink, Route, Routes, useParams } from "react-router-dom";
import { get, post } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { STATUTS } from "../../libelles";
import type { Analyse } from "../../types";
import Cadrage from "./Cadrage";
import Valeurs from "./Valeurs";
import Evenements from "./Evenements";
import SoclePage from "./Socle";

export interface ContexteAnalyse {
  analyse: Analyse;
  url: string;
  saisie: boolean;
  recharger: () => Promise<void>;
}

// Analyse de risques EBIOS RM. Jalon 3 : atelier 1 (cadrage et socle de sécurité).
export default function AnalysePage() {
  const { id } = useParams();
  const donnees = useDonnees(() => get<Analyse>(`/api/analyses/${id}`), [id]);
  const action = useAction();
  const a = donnees.donnees;

  if (donnees.erreur) return <Erreur erreur={donnees.erreur} />;
  if (!a) return <Chargement />;

  const finalise = a.statut === "finalise";
  const ctx: ContexteAnalyse = {
    analyse: a,
    url: `/api/analyses/${a.id}`,
    saisie: a.droits.includes("saisie") && !finalise,
    recharger: donnees.recharger,
  };
  const base = `/analyses/${a.id}`;
  const c = a.compte;

  return (
    <>
      <p className="fil">
        <Link to="/missions">Missions</Link> › <Link to={`/missions/${a.mission_id}`}>{a.mission_titre}</Link> ›{" "}
        <span className="courant">{a.titre}</span>
      </p>
      <div className="ligne espace">
        <div>
          <h1>EBIOS RM · {a.client}</h1>
          <p className="discret">
            {a.titre} · atelier 1, cadrage et socle de sécurité
            {a.diagnostic_id ? ` · liée au diagnostic n° ${a.diagnostic_id}` : " · analyse autonome"}
          </p>
        </div>
        <div className="ligne">
          <Pastille texte={STATUTS[a.statut] ?? a.statut} ton={finalise ? "ok" : "accent"} />
          {a.droits.includes("gestion") && (
            <button
              className={finalise ? "" : "principal"}
              disabled={action.enCours}
              onClick={() =>
                action.executer(async () => {
                  await post(`${ctx.url}/${finalise ? "rouvrir" : "finaliser"}`);
                  await donnees.recharger();
                })
              }
            >
              {finalise ? "Rouvrir" : "Finaliser"}
            </button>
          )}
        </div>
      </div>
      <Erreur erreur={action.erreur} />

      <nav className="onglets">
        <NavLink to={`${base}/cadrage`}>1. Cadrage</NavLink>
        <NavLink to={`${base}/valeurs`}>2. Valeurs métier et biens supports ({c.valeurs_metier} / {c.biens_supports})</NavLink>
        <NavLink to={`${base}/evenements`}>3. Événements redoutés ({c.evenements_redoutes})</NavLink>
        <NavLink to={`${base}/socle`}>4. Socle de sécurité ({c.referentiels_socle})</NavLink>
      </nav>

      <Routes>
        <Route index element={<Navigate to={`${base}/cadrage`} replace />} />
        <Route path="cadrage" element={<Cadrage ctx={ctx} />} />
        <Route path="valeurs" element={<Valeurs ctx={ctx} />} />
        <Route path="evenements" element={<Evenements ctx={ctx} />} />
        <Route path="socle" element={<SoclePage ctx={ctx} />} />
      </Routes>
    </>
  );
}
