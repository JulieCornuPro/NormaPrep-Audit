import { useState } from "react";
import { get, put } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { interlocuteurs, minutes, MODES } from "../../libelles";
import type { PlanAteliers, QuestionPlan } from "../../types";
import type { ContexteDiagnostic } from "./Diagnostic";

export default function Ateliers({ ctx }: { ctx: ContexteDiagnostic }) {
  const plan = useDonnees(() => get<PlanAteliers>(`${ctx.url}/ateliers`), [ctx.url]);
  const [budget, setBudget] = useState(ctx.synthese.budget_atelier_minutes);
  const [ouverture, setOuverture] = useState(ctx.synthese.ouverture_minutes);
  const action = useAction();

  if (plan.erreur) return <Erreur erreur={plan.erreur} />;
  if (!plan.donnees) return <Chargement />;
  const p = plan.donnees;

  const changerMode = (q: QuestionPlan, mode: string) =>
    action.executer(async () => {
      await put(`${ctx.url}/questions/${q.ref}/mode`, { mode });
      await plan.recharger();
    });

  const enregistrerParametres = () =>
    action.executer(async () => {
      await put(`${ctx.url}/parametres`, { budget_atelier_minutes: budget, ouverture_minutes: ouverture });
      await ctx.rechargerSynthese();
      await plan.recharger();
    });

  const hors = Object.entries(p.hors_atelier).filter(([, qs]) => qs.length);

  return (
    <>
      <div className="carte">
        <div className="ligne espace">
          <div>
            <strong>{p.ateliers.length} entretien(s)</strong> · {minutes(p.duree_totale_minutes)} au total
            {p.hors_atelier.pre_questionnaire?.length > 0 && <> · pré-questionnaire : {minutes(p.duree_pre_questionnaire_minutes)} côté client</>}
          </div>
          {ctx.saisie && (
            <div className="ligne">
              <label className="choix">Budget&nbsp;<input type="number" min={30} max={480} value={budget} onChange={(e) => setBudget(Number(e.target.value))} style={{ width: 80 }} />&nbsp;min</label>
              <label className="choix">dont ouverture&nbsp;<input type="number" min={0} max={60} value={ouverture} onChange={(e) => setOuverture(Number(e.target.value))} style={{ width: 70 }} />&nbsp;min</label>
              <button disabled={action.enCours} onClick={enregistrerParametres}>Appliquer</button>
            </div>
          )}
        </div>
        <p className="discret">
          Entretiens regroupés par interlocuteurs puis par sous-thème, sans dépasser le budget. Les durées sont des estimations par type de question, à
          calibrer.
        </p>
        {p.depassements.length > 0 && (
          <div className="message alerte">Entretien(s) {p.depassements.join(", ")} : une question dépasse seule le budget.</div>
        )}
        <Erreur erreur={action.erreur} />
      </div>

      {p.ateliers.length === 0 && <div className="message info">Aucune question en entretien. Renseignez le profilage, ou ramenez des questions en entretien.</div>}

      {p.ateliers.map((a) => (
        <div key={a.numero} className="carte">
          <div className="ligne espace">
            <h2 style={{ margin: 0 }}>Entretien {a.numero} · {interlocuteurs(a.interlocuteurs)}</h2>
            <Pastille texte={minutes(a.duree_minutes)} ton={a.duree_minutes > p.budget_minutes ? "danger" : "accent"} />
          </div>
          <p className="discret">{a.sous_themes.map((s) => s.libelle).join(" · ")}</p>
          <ListeQuestions questions={a.questions} saisie={ctx.saisie} actuel="atelier" changer={changerMode} />
        </div>
      ))}

      {hors.map(([mode, qs]) => (
        <div key={mode} className="carte">
          <h2 style={{ marginTop: 0 }}>{MODES[mode] ?? mode} · {qs.length} question(s)</h2>
          <ListeQuestions questions={qs} saisie={ctx.saisie} actuel={mode} changer={changerMode} />
        </div>
      ))}
    </>
  );
}

function ListeQuestions({
  questions,
  saisie,
  actuel,
  changer,
}: {
  questions: QuestionPlan[];
  saisie: boolean;
  actuel: string;
  changer: (q: QuestionPlan, mode: string) => void;
}) {
  return (
    <table>
      <tbody>
        {questions.map((q) => (
          <tr key={q.ref}>
            <td style={{ width: 90 }} className="discret">{q.ref}</td>
            <td>{q.enonce}<br /><span className="discret">{q.sous_theme_libelle}</span></td>
            <td className="nombre" style={{ width: 70 }}>{q.duree} min</td>
            <td style={{ width: 190 }}>
              {saisie ? (
                <select value={actuel} onChange={(e) => changer(q, e.target.value)} aria-label={`Mode de recueil de ${q.ref}`}>
                  {Object.entries(MODES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              ) : (
                MODES[actuel]
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
