import { useState } from "react";
import { get } from "../../api";
import { Chargement, Erreur, useDonnees } from "../../composants/communs";
import { dateHeure } from "../../libelles";

interface Entree {
  id: number;
  horodatage: string;
  utilisateur_id: number | null;
  action: string;
  objet_type: string | null;
  objet_id: string | null;
  details: Record<string, unknown> | null;
  adresse_ip: string | null;
}

export default function Journal() {
  const [action, setAction] = useState("");
  const [avant, setAvant] = useState<number | null>(null);
  const url = `/api/journal?limite=100${action ? `&action=${encodeURIComponent(action)}` : ""}${avant ? `&avant_id=${avant}` : ""}`;
  const journal = useDonnees(() => get<Entree[]>(url), [url]);
  const utilisateurs = useDonnees(() => get<{ id: number; nom: string }[]>("/api/annuaire"), []);
  const noms = new Map(utilisateurs.donnees?.map((u) => [u.id, u.nom]));

  return (
    <>
      <h1>Journal d'audit</h1>
      <p className="discret">Chaque action sensible est tracée ; la base refuse toute modification ou suppression de ce journal.</p>
      <div className="ligne" style={{ marginBottom: 12 }}>
        <input placeholder="Filtrer par action (ex. connexion_echouee)" value={action} onChange={(e) => { setAction(e.target.value.trim()); setAvant(null); }} style={{ maxWidth: 360 }} />
        {avant && <button onClick={() => setAvant(null)}>Revenir aux plus récentes</button>}
      </div>
      <Erreur erreur={journal.erreur} />
      {!journal.donnees ? (
        <Chargement />
      ) : (
        <div className="carte">
          <table>
            <thead>
              <tr><th>Date</th><th>Action</th><th>Par</th><th>Objet</th><th>Détails</th></tr>
            </thead>
            <tbody>
              {journal.donnees.map((e) => (
                <tr key={e.id}>
                  <td className="discret" style={{ whiteSpace: "nowrap" }}>{dateHeure(e.horodatage)}</td>
                  <td>{e.action}</td>
                  <td>{e.utilisateur_id ? noms.get(e.utilisateur_id) ?? `n° ${e.utilisateur_id}` : "—"}</td>
                  <td className="discret">{e.objet_type ? `${e.objet_type} ${e.objet_id ?? ""}` : "—"}</td>
                  <td className="discret" style={{ maxWidth: 360, overflowWrap: "anywhere" }}>
                    {e.details ? JSON.stringify(e.details) : ""}{e.adresse_ip ? ` · ${e.adresse_ip}` : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {journal.donnees.length === 100 && (
            <p style={{ marginTop: 12 }}><button onClick={() => setAvant(journal.donnees![journal.donnees!.length - 1].id)}>Entrées plus anciennes</button></p>
          )}
        </div>
      )}
    </>
  );
}
