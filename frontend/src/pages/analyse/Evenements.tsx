import { useState } from "react";
import { del, get, post, put } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { IMPACTS } from "../../libelles";
import type { EvenementRedoute, ValeurMetier } from "../../types";
import type { ContexteAnalyse } from "./Analyse";

type Saisie = { id?: number; valeur_metier_id: number; description: string; impacts: string[]; gravite: number };

export default function Evenements({ ctx }: { ctx: ContexteAnalyse }) {
  const valeurs = useDonnees(() => get<ValeurMetier[]>(`${ctx.url}/valeurs-metier`), [ctx.url]);
  const evenements = useDonnees(() => get<EvenementRedoute[]>(`${ctx.url}/evenements-redoutes`), [ctx.url]);
  const action = useAction();
  const [saisie, setSaisie] = useState<Saisie | null>(null);
  const echelle = ctx.analyse.echelle_gravite;
  const max = echelle.length;

  if (!valeurs.donnees || !evenements.donnees) return <><Erreur erreur={valeurs.erreur ?? evenements.erreur} /><Chargement /></>;
  const vs = valeurs.donnees;
  const ton = (g: number) => (g >= max ? "danger" : g >= max - 1 ? "alerte" : undefined);
  const libelleG = (g: number) => `G${g} · ${echelle[g - 1]?.libelle ?? ""}`;

  const tout = () => Promise.all([evenements.recharger(), ctx.recharger()]);
  const enregistrer = () =>
    action.executer(async () => {
      const { id, ...corps } = saisie!;
      if (id) await put(`${ctx.url}/evenements-redoutes/${id}`, corps);
      else await post(`${ctx.url}/evenements-redoutes`, corps);
      setSaisie(null);
      await tout();
    });

  return (
    <div className="carte">
      <div className="ligne espace">
        <h2 style={{ marginTop: 0 }}>Événements redoutés</h2>
        {ctx.saisie && !saisie && vs.length > 0 && (
          <button onClick={() => setSaisie({ valeur_metier_id: vs[0].id, description: "", impacts: [], gravite: 1 })}>Ajouter</button>
        )}
      </div>
      <p className="discret">Pour chaque valeur métier, ce qu'on redoute (atteinte à la disponibilité, l'intégrité, la confidentialité…), ses impacts et sa gravité.</p>
      {vs.length === 0 && <div className="message info">Créez d'abord des valeurs métier (onglet 2).</div>}
      <Erreur erreur={action.erreur} />

      {saisie && (
        <div className="message info">
          <label htmlFor="er-vm">Valeur métier</label>
          <select id="er-vm" value={saisie.valeur_metier_id} onChange={(e) => setSaisie({ ...saisie, valeur_metier_id: Number(e.target.value) })}>
            {vs.map((v) => <option key={v.id} value={v.id}>{v.nom}</option>)}
          </select>
          <label htmlFor="er-desc">Événement redouté</label>
          <textarea id="er-desc" value={saisie.description} onChange={(e) => setSaisie({ ...saisie, description: e.target.value })} placeholder="Indisponibilité du service de paie pendant plus de 48 h" />
          <label>Impacts</label>
          <div className="ligne" style={{ flexWrap: "wrap" }}>
            {Object.entries(IMPACTS).map(([code, libelle]) => (
              <label key={code} style={{ fontWeight: 400, margin: "2px 12px 2px 0" }}>
                <input
                  type="checkbox"
                  style={{ width: "auto", marginRight: 6 }}
                  checked={saisie.impacts.includes(code)}
                  onChange={(e) =>
                    setSaisie({ ...saisie, impacts: e.target.checked ? [...saisie.impacts, code] : saisie.impacts.filter((x) => x !== code) })
                  }
                />
                {libelle}
              </label>
            ))}
          </div>
          <label htmlFor="er-g">Gravité</label>
          <select id="er-g" value={saisie.gravite} onChange={(e) => setSaisie({ ...saisie, gravite: Number(e.target.value) })}>
            {echelle.map((_, i) => <option key={i} value={i + 1}>{libelleG(i + 1)}</option>)}
          </select>
          <div className="ligne" style={{ marginTop: 12 }}>
            <button className="principal" disabled={!saisie.description.trim() || action.enCours} onClick={enregistrer}>Enregistrer</button>
            <button onClick={() => setSaisie(null)}>Annuler</button>
          </div>
        </div>
      )}

      {vs.map((v) => {
        const liste = evenements.donnees!.filter((e) => e.valeur_metier_id === v.id);
        return (
          <div key={v.id} className="question">
            <strong>{v.nom}</strong>
            {liste.length === 0 ? (
              <p className="discret">Aucun événement redouté.</p>
            ) : (
              <table>
                <tbody>
                  {liste.map((e) => (
                    <tr key={e.id}>
                      <td style={{ width: "50%" }}>{e.description}</td>
                      <td className="discret">{e.impacts.map((i) => IMPACTS[i] ?? i).join(", ") || "—"}</td>
                      <td><Pastille texte={libelleG(e.gravite)} ton={ton(e.gravite)} /></td>
                      {ctx.saisie && (
                        <td style={{ whiteSpace: "nowrap" }}>
                          <button className="lien" onClick={() => setSaisie({ ...e })}>Modifier</button>{" "}
                          <button
                            className="lien danger"
                            onClick={() =>
                              window.confirm("Supprimer cet événement redouté ?") &&
                              action.executer(async () => {
                                await del(`${ctx.url}/evenements-redoutes/${e.id}`);
                                await tout();
                              })
                            }
                          >
                            Supprimer
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}
