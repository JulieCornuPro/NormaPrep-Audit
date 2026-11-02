import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { del, get, patch, post, put } from "../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../composants/communs";
import { date, ROLES, STATUTS } from "../libelles";
import type { Mission, NoeudArbre, ReferentielResume } from "../types";
import Televersement from "../composants/Televersement";
import ArbreReferentiel from "../composants/ArbreReferentiel";

export default function MissionPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const mission = useDonnees(() => get<Mission>(`/api/missions/${id}`), [id]);
  const action = useAction();
  const m = mission.donnees;

  if (mission.erreur) return <Erreur erreur={mission.erreur} />;
  if (!m) return <Chargement />;
  const gestion = m.droits.includes("gestion");
  const saisie = m.droits.includes("saisie");

  const nouveauDiagnostic = () =>
    action.executer(async () => {
      const d = await post<{ id: number }>(`/api/missions/${m.id}/diagnostics`);
      navigate(`/diagnostics/${d.id}`);
    });

  return (
    <>
      <p className="fil"><Link to="/missions">Missions</Link> › <span className="courant">{m.client.nom}</span></p>
      <div className="ligne espace">
        <h1>{m.titre}</h1>
        <Pastille texte={STATUTS[m.statut] ?? m.statut} ton={m.statut === "en_cours" ? "accent" : undefined} />
      </div>
      <p className="discret">Client : {m.client.nom}{m.client.secteur ? ` · ${m.client.secteur}` : ""} · créée le {date(m.cree_le)}</p>
      {m.perimetre && <p style={{ whiteSpace: "pre-wrap" }}>{m.perimetre}</p>}
      <Erreur erreur={action.erreur} />

      <div className="grille-2">
        <div className="carte">
          <div className="ligne espace">
            <h2 style={{ marginTop: 0 }}>Diagnostics de maturité</h2>
            {saisie && <button className="principal" disabled={action.enCours} onClick={nouveauDiagnostic}>Nouveau diagnostic</button>}
          </div>
          {m.diagnostics.length === 0 ? (
            <p className="discret">Aucun diagnostic de maturité.</p>
          ) : (
            <table>
              <tbody>
                {m.diagnostics.map((d) => (
                  <tr key={d.id}>
                    <td><Link to={`/diagnostics/${d.id}`}>Diagnostic n° {d.id}</Link></td>
                    <td className="discret">{d.referentiel} {d.version}</td>
                    <td><Pastille texte={STATUTS[d.statut] ?? d.statut} ton={d.statut === "finalise" ? "ok" : "accent"} /></td>
                    <td className="discret">{date(d.cree_le)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <Analyses mission={m} saisie={saisie} />
      </div>

      <div className="grille-2">
        <ReferentielsClient mission={m} gestion={gestion} />
        <Equipe mission={m} gestion={gestion} recharger={mission.recharger} />
      </div>

      {gestion && (
        <p>
          <button
            onClick={() =>
              action.executer(async () => {
                await patch(`/api/missions/${m.id}`, { statut: m.statut === "en_cours" ? "terminee" : "en_cours" });
                await mission.recharger();
              })
            }
          >
            {m.statut === "en_cours" ? "Marquer la mission comme terminée" : "Rouvrir la mission"}
          </button>
        </p>
      )}
    </>
  );
}

function Equipe({ mission, gestion, recharger }: { mission: Mission; gestion: boolean; recharger: () => Promise<void> }) {
  const annuaire = useDonnees(
    () => (gestion ? get<{ id: number; nom: string; email: string }[]>("/api/annuaire") : Promise.resolve([])),
    [gestion],
  );
  const [utilisateur, setUtilisateur] = useState("");
  const [role, setRole] = useState("consultant");
  const { enCours, erreur, executer } = useAction();
  const membres = new Set(mission.membres.map((x) => x.utilisateur_id));

  const definir = (utilisateurId: number, r: string) =>
    executer(async () => {
      await put(`/api/missions/${mission.id}/membres`, { utilisateur_id: utilisateurId, role: r });
      await recharger();
    });

  return (
    <div className="carte">
      <h2 style={{ marginTop: 0 }}>Équipe</h2>
      <Erreur erreur={erreur} />
      <table>
        <tbody>
          {mission.membres.map((x) => (
            <tr key={x.utilisateur_id}>
              <td>{x.nom}<br /><span className="discret">{x.email}</span></td>
              <td>
                {gestion ? (
                  <select value={x.role} disabled={enCours} onChange={(e) => definir(x.utilisateur_id, e.target.value)}>
                    {["responsable", "consultant", "relecteur"].map((r) => <option key={r} value={r}>{ROLES[r]}</option>)}
                  </select>
                ) : (
                  ROLES[x.role]
                )}
              </td>
              {gestion && (
                <td>
                  <button
                    className="lien danger"
                    disabled={enCours}
                    onClick={() =>
                      executer(async () => {
                        await del(`/api/missions/${mission.id}/membres/${x.utilisateur_id}`);
                        await recharger();
                      })
                    }
                  >
                    Retirer
                  </button>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      {gestion && (
        <div className="ligne" style={{ marginTop: 12 }}>
          <select value={utilisateur} onChange={(e) => setUtilisateur(e.target.value)} style={{ flex: 2 }} aria-label="Personne à ajouter">
            <option value="">Ajouter une personne…</option>
            {annuaire.donnees?.filter((a) => !membres.has(a.id)).map((a) => <option key={a.id} value={a.id}>{a.nom}</option>)}
          </select>
          <select value={role} onChange={(e) => setRole(e.target.value)} style={{ flex: 1 }} aria-label="Rôle">
            {["consultant", "relecteur", "responsable"].map((r) => <option key={r} value={r}>{ROLES[r]}</option>)}
          </select>
          <button disabled={!utilisateur || enCours} onClick={() => definir(Number(utilisateur), role).then(() => setUtilisateur(""))}>Ajouter</button>
        </div>
      )}
    </div>
  );
}

function Analyses({ mission, saisie }: { mission: Mission; saisie: boolean }) {
  const navigate = useNavigate();
  const [titre, setTitre] = useState("");
  const [diagnostic, setDiagnostic] = useState("");
  const [ouvert, setOuvert] = useState(false);
  const { enCours, erreur, executer } = useAction();

  const creer = () =>
    executer(async () => {
      const a = await post<{ id: number }>(`/api/missions/${mission.id}/analyses`, {
        titre: titre.trim(),
        diagnostic_id: diagnostic ? Number(diagnostic) : null,
      });
      navigate(`/analyses/${a.id}`);
    });

  return (
    <div className="carte">
      <div className="ligne espace">
        <h2 style={{ marginTop: 0 }}>Analyses de risques EBIOS RM</h2>
        {saisie && !ouvert && <button className="principal" onClick={() => setOuvert(true)}>Nouvelle analyse</button>}
      </div>
      <Erreur erreur={erreur} />
      {ouvert && (
        <div className="message info">
          <label>
            Titre
            <input value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="Analyse de risques du SI de production" />
          </label>
          <label>
            Diagnostic de maturité lié (facultatif)
            <select value={diagnostic} onChange={(e) => setDiagnostic(e.target.value)}>
              <option value="">Aucun, analyse autonome</option>
              {mission.diagnostics.map((d) => <option key={d.id} value={d.id}>Diagnostic n° {d.id} ({STATUTS[d.statut] ?? d.statut})</option>)}
            </select>
          </label>
          <p className="discret">Le diagnostic lié propose les référentiels du socle et pré-remplit leur état d'application.</p>
          <div className="ligne">
            <button className="principal" disabled={!titre.trim() || enCours} onClick={creer}>Créer</button>
            <button onClick={() => setOuvert(false)}>Annuler</button>
          </div>
        </div>
      )}
      {mission.analyses.length === 0 ? (
        !ouvert && <p className="discret">Aucune analyse. Une analyse peut être menée seule ou à la suite d'un diagnostic.</p>
      ) : (
        <table>
          <tbody>
            {mission.analyses.map((a) => (
              <tr key={a.id}>
                <td><Link to={`/analyses/${a.id}`}>{a.titre}</Link></td>
                <td><Pastille texte={STATUTS[a.statut] ?? a.statut} ton={a.statut === "finalise" ? "ok" : "accent"} /></td>
                <td className="discret">{date(a.cree_le)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

interface DetailRef {
  code: string;
  version: string;
  niveaux: string[];
  profils: string[];
  arbre: NoeudArbre[];
}

function ReferentielsClient({ mission, gestion }: { mission: Mission; gestion: boolean }) {
  const url = `/api/missions/${mission.id}/referentiels`;
  const refs = useDonnees(() => get<ReferentielResume[]>(url), [url]);
  const [detail, setDetail] = useState<DetailRef | null>(null);
  const [charger, setCharger] = useState(false);
  const { erreur, executer } = useAction();

  return (
    <div className="carte">
      <div className="ligne espace">
        <h2 style={{ marginTop: 0 }}>Référentiels du client</h2>
        {gestion && !charger && <button onClick={() => setCharger(true)}>Charger un classeur</button>}
      </div>
      <p className="discret">Référentiels propres à ce client (politique interne, exigences d'un donneur d'ordre…), visibles dans cette mission seulement.</p>
      <Erreur erreur={erreur ?? refs.erreur} />
      {!refs.donnees ? (
        <Chargement />
      ) : refs.donnees.length === 0 ? (
        <p className="discret">Aucun référentiel client.</p>
      ) : (
        <table>
          <tbody>
            {refs.donnees.map((r) => (
              <tr key={r.id}>
                <td>{r.code}<br /><span className="discret">{r.libelle}</span></td>
                <td>{r.version}</td>
                <td>{r.actif ? <Pastille texte="Active" ton="ok" /> : <Pastille texte="Ancienne" />}</td>
                <td>
                  {r.actif && (
                    <button className="lien" onClick={() => executer(async () => setDetail(await get<DetailRef>(`${url}/${encodeURIComponent(r.code)}`)))}>
                      Consulter
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {charger && (
        <div style={{ marginTop: 12 }}>
          <Televersement url={`${url}/televerser`} apres={refs.recharger} />
          <button className="lien" onClick={() => setCharger(false)}>Fermer</button>
        </div>
      )}
      {detail && (
        <div style={{ marginTop: 12 }}>
          <div className="ligne espace">
            <strong>{detail.code} {detail.version}</strong>
            <button className="lien" onClick={() => setDetail(null)}>Fermer</button>
          </div>
          <ArbreReferentiel racines={detail.arbre} niveaux={detail.niveaux} profils={detail.profils} />
        </div>
      )}
    </div>
  );
}
