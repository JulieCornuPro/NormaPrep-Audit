import { Link, Navigate, NavLink, Route, Routes, useParams } from "react-router-dom";
import { get, post } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { date, STATUTS } from "../../libelles";
import type { Synthese } from "../../types";
import Profilage from "./Profilage";
import Ateliers from "./Ateliers";
import QuestionnairePage from "./Questionnaire";
import PreQuestionnaire from "./PreQuestionnaire";
import ResultatsPage from "./Resultats";

export interface ContexteDiagnostic {
  synthese: Synthese;
  url: string;
  saisie: boolean;
  rechargerSynthese: () => Promise<void>;
}

export default function DiagnosticPage() {
  const { id } = useParams();
  const synthese = useDonnees(() => get<Synthese>(`/api/diagnostics/${id}`), [id]);
  const action = useAction();
  const s = synthese.donnees;

  if (synthese.erreur) return <Erreur erreur={synthese.erreur} />;
  if (!s) return <Chargement />;

  const finalise = s.statut === "finalise";
  const ctx: ContexteDiagnostic = {
    synthese: s,
    url: `/api/diagnostics/${s.id}`,
    saisie: s.droits.includes("saisie") && !finalise,
    rechargerSynthese: synthese.recharger,
  };
  const base = `/diagnostics/${s.id}`;
  const p = s.progression;
  const avancement = p.retenues ? Math.round((100 * p.repondues) / p.retenues) : 0;

  const basculer = () =>
    action.executer(async () => {
      await post(`${ctx.url}/${finalise ? "rouvrir" : "finaliser"}`);
      await synthese.recharger();
    });

  return (
    <>
      <p className="fil">
        <Link to="/missions">Missions</Link> › <Link to={`/missions/${s.mission_id}`}>{s.mission_titre}</Link> ›{" "}
        <span className="courant">Diagnostic n° {s.id}</span>
      </p>
      <div className="ligne espace">
        <div>
          <h1>Diagnostic de maturité · {s.client}</h1>
          <p className="discret">
            Référentiel {s.referentiel.code} {s.referentiel.version}
            {finalise && s.finalise_le ? ` · finalisé le ${date(s.finalise_le)}` : ""}
          </p>
        </div>
        <div className="ligne">
          <Pastille texte={STATUTS[s.statut] ?? s.statut} ton={finalise ? "ok" : "accent"} />
          {s.droits.includes("gestion") && (
            <button className={finalise ? "" : "principal"} disabled={action.enCours} onClick={basculer}>
              {finalise ? "Rouvrir" : "Finaliser"}
            </button>
          )}
        </div>
      </div>
      <Erreur erreur={action.erreur} />

      <div className="carte">
        <div className="ligne espace">
          <span>{p.repondues} / {p.retenues} questions traitées</span>
          <span className="discret">
            {s.profilage_incomplet.length > 0 && `Profilage incomplet (${s.profilage_incomplet.length}) · `}
            {s.reglementations_en_attente.length > 0 && `${s.reglementations_en_attente.length} réglementation(s) à trancher`}
          </span>
        </div>
        <div className="progression" style={{ marginTop: 8 }} role="progressbar" aria-valuenow={avancement} aria-valuemin={0} aria-valuemax={100}>
          <div style={{ width: `${avancement}%` }} />
        </div>
      </div>

      <nav className="onglets">
        <NavLink to={`${base}/profilage`}>1. Profilage</NavLink>
        <NavLink to={`${base}/ateliers`}>2. Plan d'entretiens</NavLink>
        <NavLink to={`${base}/questionnaire`}>3. Questionnaire</NavLink>
        <NavLink to={`${base}/pre-questionnaire`}>Pré-questionnaire</NavLink>
        <NavLink to={`${base}/resultats`}>4. Résultats</NavLink>
      </nav>

      <Routes>
        <Route index element={<Navigate to={`${base}/${s.profilage_incomplet.length ? "profilage" : "questionnaire"}`} replace />} />
        <Route path="profilage" element={<Profilage ctx={ctx} />} />
        <Route path="ateliers" element={<Ateliers ctx={ctx} />} />
        <Route path="questionnaire" element={<QuestionnairePage ctx={ctx} />} />
        <Route path="pre-questionnaire" element={<PreQuestionnaire ctx={ctx} />} />
        <Route path="resultats" element={<ResultatsPage ctx={ctx} />} />
      </Routes>
    </>
  );
}
