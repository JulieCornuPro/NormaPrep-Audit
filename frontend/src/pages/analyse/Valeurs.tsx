import { useState } from "react";
import { del, get, post, put } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import type { BienSupport, ValeurMetier } from "../../types";
import type { ContexteAnalyse } from "./Analyse";

const VALEUR_VIDE = { nom: "", nature: "processus" as ValeurMetier["nature"], description: "", responsable: "" };
const BIEN_VIDE = { nom: "", description: "", responsable: "", valeurs_metier: [] as number[] };

export default function Valeurs({ ctx }: { ctx: ContexteAnalyse }) {
  const valeurs = useDonnees(() => get<ValeurMetier[]>(`${ctx.url}/valeurs-metier`), [ctx.url]);
  const biens = useDonnees(() => get<BienSupport[]>(`${ctx.url}/biens-supports`), [ctx.url]);
  const action = useAction();
  const [valeur, setValeur] = useState<(typeof VALEUR_VIDE & { id?: number }) | null>(null);
  const [bien, setBien] = useState<(typeof BIEN_VIDE & { id?: number }) | null>(null);

  if (!valeurs.donnees || !biens.donnees) return <><Erreur erreur={valeurs.erreur ?? biens.erreur} /><Chargement /></>;
  const nomValeur = Object.fromEntries(valeurs.donnees.map((v) => [v.id, v.nom]));

  const tout = async () => {
    await Promise.all([valeurs.recharger(), biens.recharger(), ctx.recharger()]);
  };
  const enregistrerValeur = () =>
    action.executer(async () => {
      const { id, ...corps } = valeur!;
      if (id) await put(`${ctx.url}/valeurs-metier/${id}`, corps);
      else await post(`${ctx.url}/valeurs-metier`, corps);
      setValeur(null);
      await tout();
    });
  const enregistrerBien = () =>
    action.executer(async () => {
      const { id, ...corps } = bien!;
      if (id) await put(`${ctx.url}/biens-supports/${id}`, corps);
      else await post(`${ctx.url}/biens-supports`, corps);
      setBien(null);
      await tout();
    });
  const supprimer = (chemin: string, message: string) =>
    window.confirm(message) &&
    action.executer(async () => {
      await del(chemin);
      await tout();
    });

  return (
    <>
      <Erreur erreur={action.erreur} />
      <div className="grille-2">
        <div className="carte">
          <div className="ligne espace">
            <h2 style={{ marginTop: 0 }}>Valeurs métier</h2>
            {ctx.saisie && !valeur && <button onClick={() => setValeur({ ...VALEUR_VIDE })}>Ajouter</button>}
          </div>
          <p className="discret">Processus et informations essentiels à la mission de l'organisation.</p>
          {valeur && (
            <div className="message info">
              <label htmlFor="vm-nom">Nom</label>
              <input id="vm-nom" value={valeur.nom} onChange={(e) => setValeur({ ...valeur, nom: e.target.value })} />
              <label htmlFor="vm-nature">Nature</label>
              <select id="vm-nature" value={valeur.nature} onChange={(e) => setValeur({ ...valeur, nature: e.target.value as ValeurMetier["nature"] })}>
                <option value="processus">Processus</option>
                <option value="information">Information</option>
              </select>
              <label htmlFor="vm-desc">Description</label>
              <textarea id="vm-desc" value={valeur.description} onChange={(e) => setValeur({ ...valeur, description: e.target.value })} />
              <label htmlFor="vm-resp">Responsable</label>
              <input id="vm-resp" value={valeur.responsable} onChange={(e) => setValeur({ ...valeur, responsable: e.target.value })} />
              <div className="ligne" style={{ marginTop: 12 }}>
                <button className="principal" disabled={!valeur.nom.trim() || action.enCours} onClick={enregistrerValeur}>Enregistrer</button>
                <button onClick={() => setValeur(null)}>Annuler</button>
              </div>
            </div>
          )}
          {valeurs.donnees.length === 0 ? (
            <p className="discret">Aucune valeur métier.</p>
          ) : (
            <table>
              <tbody>
                {valeurs.donnees.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <strong>{v.nom}</strong> <Pastille texte={v.nature === "processus" ? "Processus" : "Information"} />
                      {v.description && <><br /><span className="discret">{v.description}</span></>}
                      {v.responsable && <><br /><span className="discret">Responsable : {v.responsable}</span></>}
                    </td>
                    {ctx.saisie && (
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="lien" onClick={() => setValeur({ ...v })}>Modifier</button>{" "}
                        <button
                          className="lien danger"
                          onClick={() => supprimer(`${ctx.url}/valeurs-metier/${v.id}`, `Supprimer « ${v.nom} » et ses événements redoutés ?`)}
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

        <div className="carte">
          <div className="ligne espace">
            <h2 style={{ marginTop: 0 }}>Biens supports</h2>
            {ctx.saisie && !bien && <button onClick={() => setBien({ ...BIEN_VIDE })}>Ajouter</button>}
          </div>
          <p className="discret">Composants du SI sur lesquels reposent les valeurs métier : applications, serveurs, réseaux, prestataires, locaux…</p>
          {bien && (
            <div className="message info">
              <label htmlFor="bs-nom">Nom</label>
              <input id="bs-nom" value={bien.nom} onChange={(e) => setBien({ ...bien, nom: e.target.value })} />
              <label htmlFor="bs-desc">Description</label>
              <textarea id="bs-desc" value={bien.description} onChange={(e) => setBien({ ...bien, description: e.target.value })} />
              <label htmlFor="bs-resp">Responsable</label>
              <input id="bs-resp" value={bien.responsable} onChange={(e) => setBien({ ...bien, responsable: e.target.value })} />
              <label>Valeurs métier supportées</label>
              {valeurs.donnees.length === 0 && <p className="discret">Créez d'abord des valeurs métier.</p>}
              {valeurs.donnees.map((v) => (
                <label key={v.id} style={{ fontWeight: 400, margin: "4px 0" }}>
                  <input
                    type="checkbox"
                    style={{ width: "auto", marginRight: 8 }}
                    checked={bien.valeurs_metier.includes(v.id)}
                    onChange={(e) =>
                      setBien({
                        ...bien,
                        valeurs_metier: e.target.checked ? [...bien.valeurs_metier, v.id] : bien.valeurs_metier.filter((x) => x !== v.id),
                      })
                    }
                  />
                  {v.nom}
                </label>
              ))}
              <div className="ligne" style={{ marginTop: 12 }}>
                <button className="principal" disabled={!bien.nom.trim() || action.enCours} onClick={enregistrerBien}>Enregistrer</button>
                <button onClick={() => setBien(null)}>Annuler</button>
              </div>
            </div>
          )}
          {biens.donnees.length === 0 ? (
            <p className="discret">Aucun bien support.</p>
          ) : (
            <table>
              <tbody>
                {biens.donnees.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <strong>{b.nom}</strong>
                      {b.description && <><br /><span className="discret">{b.description}</span></>}
                      <br />
                      <span className="discret">
                        {b.valeurs_metier.length ? `Supporte : ${b.valeurs_metier.map((x) => nomValeur[x]).join(", ")}` : "Aucune valeur métier liée"}
                      </span>
                    </td>
                    {ctx.saisie && (
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="lien" onClick={() => setBien({ ...b })}>Modifier</button>{" "}
                        <button className="lien danger" onClick={() => supprimer(`${ctx.url}/biens-supports/${b.id}`, `Supprimer « ${b.nom} » ?`)}>
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
      </div>
    </>
  );
}
