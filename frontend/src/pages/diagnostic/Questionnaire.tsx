import { useState } from "react";
import { get, put } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { dateHeure, interlocuteurs, MODES, nombre, PROFONDEURS } from "../../libelles";
import type { QuestionQ, Questionnaire, ReponseQ } from "../../types";
import type { ContexteDiagnostic } from "./Diagnostic";

export default function QuestionnairePage({ ctx }: { ctx: ContexteDiagnostic }) {
  const q = useDonnees(() => get<Questionnaire>(`${ctx.url}/questionnaire`), [ctx.url]);
  const [filtre, setFiltre] = useState("toutes");

  if (q.erreur) return <Erreur erreur={q.erreur} />;
  if (!q.donnees) return <Chargement />;
  if (q.donnees.themes.length === 0) return <div className="message info">Aucune question retenue : renseignez d'abord le profilage.</div>;

  const garder = (x: QuestionQ) =>
    filtre === "toutes" ||
    (filtre === "a_traiter" && x.reponse.niveau === null && !x.reponse.non_applicable) ||
    (filtre === "propositions" && x.reponse.proposition !== null);

  return (
    <>
      <div className="ligne" style={{ marginBottom: 12 }}>
        <label className="choix">Afficher&nbsp;
          <select value={filtre} onChange={(e) => setFiltre(e.target.value)} style={{ width: "auto" }}>
            <option value="toutes">Toutes les questions</option>
            <option value="a_traiter">À traiter</option>
            <option value="propositions">Avec une proposition du client</option>
          </select>
        </label>
      </div>
      {q.donnees.themes.map((t) =>
        t.sous_themes.map((st) => {
          const visibles = st.questions.filter(garder);
          if (!visibles.length) return null;
          return (
            <div key={st.code} className="carte">
              <div className="ligne espace">
                <h2 style={{ margin: 0 }}>{t.libelle} › {st.code} {st.libelle}</h2>
                <span className="discret">
                  Profondeur {PROFONDEURS[st.profondeur]} · cible {nombre(st.cible)}{st.reglementation ? ` (${st.reglementation})` : ""}
                </span>
              </div>
              {visibles.map((x) => <Question key={x.ref} ctx={ctx} question={x} apres={() => ctx.rechargerSynthese()} />)}
            </div>
          );
        }),
      )}
    </>
  );
}

function Question({ ctx, question, apres }: { ctx: ContexteDiagnostic; question: QuestionQ; apres: () => void }) {
  const [rep, setRep] = useState<ReponseQ>(question.reponse);
  const [commentaire, setCommentaire] = useState(question.reponse.commentaire);
  const action = useAction();

  const enregistrer = (niveau: number | null, na: boolean, texte = commentaire) =>
    action.executer(async () => {
      setRep(await put<ReponseQ>(`${ctx.url}/reponses/${question.ref}`, { niveau, non_applicable: na, commentaire: texte }));
      apres();
    });

  const prop = rep.proposition;
  return (
    <div className="question">
      <div className="ligne espace">
        <strong>{question.ref} · {question.enonce}</strong>
        <span className="ligne">
          {question.mode !== "atelier" && <Pastille texte={MODES[question.mode]} />}
          <span className="discret">{interlocuteurs(question.interlocuteurs)}</span>
        </span>
      </div>
      {question.aide && <p className="discret">À demander : {question.aide}</p>}
      {prop && (
        <div className="message alerte">
          Proposition du client ({dateHeure(prop.le)}) : niveau {prop.niveau ?? "non précisé"}
          {prop.commentaire && <> — « {prop.commentaire} »</>}
          {ctx.saisie && prop.niveau !== null && rep.niveau !== prop.niveau && (
            <> · <button className="lien" onClick={() => enregistrer(prop.niveau, false)}>Reprendre ce niveau</button></>
          )}
        </div>
      )}
      <div className="niveaux" role="radiogroup" aria-label={`Niveau de ${question.ref}`}>
        {Object.entries(question.niveaux).map(([n, texte]) => {
          const choisi = !rep.non_applicable && rep.niveau === Number(n);
          return (
            <button
              key={n}
              type="button"
              role="radio"
              aria-checked={choisi}
              disabled={!ctx.saisie || action.enCours}
              className={`niveau ${choisi ? "choisi" : ""} ${prop?.niveau === Number(n) ? "propose" : ""}`}
              onClick={() => enregistrer(Number(n), false)}
            >
              <span className="chiffre">{n}</span>
              <span>{texte}</span>
            </button>
          );
        })}
      </div>
      <div className="ligne espace">
        <label className="choix">
          <input type="checkbox" disabled={!ctx.saisie} checked={rep.non_applicable} onChange={(e) => enregistrer(null, e.target.checked)} />
          Non applicable
        </label>
        <span className="discret">{rep.saisi_le ? `Enregistré ${dateHeure(rep.saisi_le)}` : "Pas encore de réponse"}</span>
      </div>
      <textarea
        aria-label={`Commentaire sur ${question.ref}`}
        placeholder="Commentaire, éléments constatés, preuves demandées…"
        disabled={!ctx.saisie}
        value={commentaire}
        onChange={(e) => setCommentaire(e.target.value)}
        onBlur={() => commentaire !== rep.commentaire && enregistrer(rep.non_applicable ? null : rep.niveau, rep.non_applicable)}
      />
      <Erreur erreur={action.erreur} />
    </div>
  );
}
