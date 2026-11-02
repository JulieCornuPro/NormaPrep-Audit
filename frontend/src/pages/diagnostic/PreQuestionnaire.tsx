import { useState, type FormEvent } from "react";
import { del, get, post } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { date, dateHeure } from "../../libelles";
import type { Lien, PlanAteliers } from "../../types";
import type { ContexteDiagnostic } from "./Diagnostic";

export default function PreQuestionnaire({ ctx }: { ctx: ContexteDiagnostic }) {
  const liens = useDonnees(() => get<Lien[]>(`${ctx.url}/liens`), [ctx.url]);
  const plan = useDonnees(() => get<PlanAteliers>(`${ctx.url}/ateliers`), [ctx.url]);
  const [destinataire, setDestinataire] = useState("");
  const [jours, setJours] = useState(14);
  const [nouveau, setNouveau] = useState<Lien | null>(null);
  const action = useAction();

  const questions = plan.donnees?.hors_atelier.pre_questionnaire ?? [];
  const adresse = nouveau?.chemin ? `${window.location.origin}${nouveau.chemin}` : "";

  const creer = (e: FormEvent) => {
    e.preventDefault();
    action.executer(async () => {
      setNouveau(await post<Lien>(`${ctx.url}/liens`, { destinataire, jours }));
      setDestinataire("");
      await liens.recharger();
    });
  };

  return (
    <>
      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Questions du pré-questionnaire</h2>
        {!plan.donnees ? (
          <Chargement />
        ) : questions.length === 0 ? (
          <p className="discret">Aucune question en pré-questionnaire. Dans l'onglet « Plan d'entretiens », passez des questions factuelles en mode « Pré-questionnaire ».</p>
        ) : (
          <ul>{questions.map((q) => <li key={q.ref}>{q.ref} · {q.enonce}</li>)}</ul>
        )}
        <p className="discret">Le client propose un niveau et un commentaire ; vous les retrouvez dans le questionnaire, et vous choisissez de les reprendre ou non.</p>
      </div>

      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Liens envoyés au client</h2>
        {ctx.saisie && (
          <form className="ligne" onSubmit={creer}>
            <input placeholder="Destinataire (ex. DSI)" value={destinataire} onChange={(e) => setDestinataire(e.target.value)} style={{ flex: 2 }} aria-label="Destinataire" />
            <label className="choix">Valable&nbsp;<input type="number" min={1} max={60} value={jours} onChange={(e) => setJours(Number(e.target.value))} style={{ width: 70 }} />&nbsp;jours</label>
            <button className="principal" disabled={action.enCours || questions.length === 0}>Créer un lien</button>
          </form>
        )}
        {nouveau && (
          <div className="message ok">
            Lien créé. Copiez-le maintenant : il ne sera plus affiché.
            <div className="ligne" style={{ marginTop: 6 }}>
              <code>{adresse}</code>
              <button type="button" onClick={() => navigator.clipboard?.writeText(adresse)}>Copier</button>
            </div>
          </div>
        )}
        <Erreur erreur={action.erreur ?? liens.erreur} />
        {liens.donnees && liens.donnees.length > 0 && (
          <table style={{ marginTop: 12 }}>
            <thead>
              <tr><th>Destinataire</th><th>Créé le</th><th>Expire le</th><th>Dernière réponse</th><th>État</th><th /></tr>
            </thead>
            <tbody>
              {liens.donnees.map((l) => (
                <tr key={l.id}>
                  <td>{l.destinataire || "—"}</td>
                  <td>{date(l.cree_le)}</td>
                  <td>{date(l.expire_le)}</td>
                  <td>{dateHeure(l.derniere_utilisation)}</td>
                  <td><Pastille texte={l.actif ? "Actif" : l.revoque ? "Révoqué" : "Expiré"} ton={l.actif ? "ok" : undefined} /></td>
                  <td>
                    {l.actif && ctx.saisie && (
                      <button
                        className="lien danger"
                        onClick={() =>
                          action.executer(async () => {
                            await del(`${ctx.url}/liens/${l.id}`);
                            await liens.recharger();
                          })
                        }
                      >
                        Révoquer
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
