import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api";
import { Chargement, Erreur, useAction, useDonnees } from "../composants/communs";
import { date } from "../libelles";

interface QuestionPublique {
  ref: string;
  sous_theme: string;
  enonce: string;
  aide: string;
  niveaux: Record<string, string>;
  niveau: number | null;
  commentaire: string;
}

interface PagePublique {
  mission: string;
  client: string;
  expire_le: string;
  questions: QuestionPublique[];
}

// Page ouverte par le client, sans compte : le jeton du lien fait office d'accès.
export default function PreQuestionnairePublic() {
  const { jeton } = useParams();
  const base = `/api/public/pre-questionnaire/${jeton}`;
  const page = useDonnees(() => api<PagePublique>(base, { public: true }), [base]);

  if (page.erreur) {
    return (
      <div className="page-etroite">
        <h1>Pré-questionnaire</h1>
        <Erreur erreur={page.erreur} />
      </div>
    );
  }
  if (!page.donnees) return <div className="page"><Chargement /></div>;
  const p = page.donnees;

  return (
    <main className="page" style={{ maxWidth: 820 }}>
      <h1>Pré-questionnaire · {p.client}</h1>
      <p className="discret">{p.mission} · lien valable jusqu'au {date(p.expire_le)}</p>
      <div className="message info">
        Pour chaque question, choisissez la description qui correspond le mieux à votre situation et ajoutez un commentaire si besoin. Chaque
        réponse est enregistrée immédiatement ; vous pouvez revenir plus tard avec le même lien. Votre consultant les reprendra avec vous.
      </div>
      {p.questions.length === 0 && <p>Aucune question n'est en attente de réponse.</p>}
      {p.questions.map((q) => <Question key={q.ref} base={base} question={q} />)}
    </main>
  );
}

function Question({ base, question }: { base: string; question: QuestionPublique }) {
  const [niveau, setNiveau] = useState<number | null>(question.niveau);
  const [commentaire, setCommentaire] = useState(question.commentaire);
  const [enregistre, setEnregistre] = useState(false);
  const action = useAction();

  const envoyer = (n: number | null, c: string) =>
    action.executer(async () => {
      await api(`${base}/reponses/${question.ref}`, { methode: "PUT", corps: { niveau: n, commentaire: c }, public: true });
      setEnregistre(true);
    });

  return (
    <div className="carte">
      <p className="discret">{question.sous_theme}</p>
      <h2 style={{ marginTop: 0 }}>{question.enonce}</h2>
      {question.aide && <p className="discret">{question.aide}</p>}
      <div className="niveaux" role="radiogroup" aria-label={question.enonce}>
        {Object.entries(question.niveaux).map(([n, texte]) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={niveau === Number(n)}
            className={`niveau ${niveau === Number(n) ? "choisi" : ""}`}
            onClick={() => {
              setNiveau(Number(n));
              envoyer(Number(n), commentaire);
            }}
          >
            <span className="chiffre">{n}</span>
            <span>{texte}</span>
          </button>
        ))}
      </div>
      <label htmlFor={`c-${question.ref}`}>Commentaire</label>
      <textarea id={`c-${question.ref}`} value={commentaire} onChange={(e) => setCommentaire(e.target.value)} onBlur={() => envoyer(niveau, commentaire)} />
      <Erreur erreur={action.erreur} />
      {enregistre && !action.erreur && <p className="discret">Réponse enregistrée.</p>}
    </div>
  );
}
