import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { get, post } from "../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../composants/communs";
import { date, ROLES, STATUTS } from "../libelles";
import type { Client, Mission } from "../types";

export default function Missions() {
  const missions = useDonnees(() => get<Mission[]>("/api/missions"), []);
  const [creation, setCreation] = useState(false);

  return (
    <>
      <div className="ligne espace">
        <h1>Missions</h1>
        <button className="principal" onClick={() => setCreation(!creation)}>{creation ? "Annuler" : "Nouvelle mission"}</button>
      </div>
      {creation && <NouvelleMission />}
      <Erreur erreur={missions.erreur} />
      {!missions.donnees ? (
        <Chargement />
      ) : missions.donnees.length === 0 ? (
        <div className="message info">Aucune mission pour le moment. Créez-en une, ou demandez à un responsable de vous ajouter à son équipe.</div>
      ) : (
        <div className="carte">
          <table>
            <thead>
              <tr>
                <th>Mission</th>
                <th>Client</th>
                <th>Mon rôle</th>
                <th>Statut</th>
                <th>Créée le</th>
              </tr>
            </thead>
            <tbody>
              {missions.donnees.map((m) => (
                <tr key={m.id}>
                  <td><Link to={`/missions/${m.id}`}>{m.titre}</Link></td>
                  <td>{m.client.nom}</td>
                  <td>{m.mon_role ? ROLES[m.mon_role] : "—"}</td>
                  <td><Pastille texte={STATUTS[m.statut] ?? m.statut} ton={m.statut === "en_cours" ? "accent" : undefined} /></td>
                  <td>{date(m.cree_le)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function NouvelleMission() {
  const navigate = useNavigate();
  const clients = useDonnees(() => get<Client[]>("/api/clients"), []);
  const [clientId, setClientId] = useState("");
  const [nouveauClient, setNouveauClient] = useState("");
  const [secteur, setSecteur] = useState("");
  const [titre, setTitre] = useState("");
  const [perimetre, setPerimetre] = useState("");
  const { enCours, erreur, executer } = useAction();

  const creer = (e: FormEvent) => {
    e.preventDefault();
    executer(async () => {
      let id = Number(clientId);
      if (clientId === "nouveau") {
        id = (await post<Client>("/api/clients", { nom: nouveauClient, secteur })).id;
      }
      const m = await post<Mission>("/api/missions", { client_id: id, titre, perimetre });
      navigate(`/missions/${m.id}`);
    });
  };

  return (
    <form className="carte" onSubmit={creer}>
      <h2 style={{ marginTop: 0 }}>Nouvelle mission</h2>
      <label htmlFor="client">Client</label>
      <select id="client" required value={clientId} onChange={(e) => setClientId(e.target.value)}>
        <option value="">Choisir…</option>
        {clients.donnees?.map((c) => <option key={c.id} value={c.id}>{c.nom}</option>)}
        <option value="nouveau">+ Nouveau client</option>
      </select>
      {clientId === "nouveau" && (
        <div className="grille-2">
          <div>
            <label htmlFor="nom-client">Nom du client (ou pseudonyme)</label>
            <input id="nom-client" required value={nouveauClient} onChange={(e) => setNouveauClient(e.target.value)} />
          </div>
          <div>
            <label htmlFor="secteur">Secteur</label>
            <input id="secteur" value={secteur} onChange={(e) => setSecteur(e.target.value)} />
          </div>
        </div>
      )}
      <label htmlFor="titre">Titre de la mission</label>
      <input id="titre" required value={titre} onChange={(e) => setTitre(e.target.value)} placeholder="Diagnostic de maturité 2026" />
      <label htmlFor="perimetre">Périmètre</label>
      <textarea id="perimetre" value={perimetre} onChange={(e) => setPerimetre(e.target.value)} placeholder="Entités, sites, systèmes concernés…" />
      <Erreur erreur={erreur} />
      <p style={{ marginTop: 12 }}>
        <button className="principal" disabled={enCours}>Créer la mission</button>
      </p>
      <p className="discret">Vous serez responsable de la mission ; vous pourrez ensuite composer l'équipe.</p>
    </form>
  );
}
