import { useState, type FormEvent } from "react";
import { get, patch, post } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { dateHeure } from "../../libelles";
import { useSession } from "../../session";

interface Compte {
  id: number;
  email: string;
  nom: string;
  est_admin: boolean;
  actif: boolean;
  totp_actif: boolean;
  bloque_jusqu_a: string | null;
  derniere_connexion: string | null;
}

export default function Utilisateurs() {
  const { moi } = useSession();
  const comptes = useDonnees(() => get<Compte[]>("/api/utilisateurs"), []);
  const action = useAction();
  const [email, setEmail] = useState("");
  const [nom, setNom] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [admin, setAdmin] = useState(false);

  const faire = (fn: () => Promise<unknown>) =>
    action.executer(async () => {
      await fn();
      await comptes.recharger();
    });

  const creer = (e: FormEvent) => {
    e.preventDefault();
    faire(async () => {
      await post("/api/utilisateurs", { email, nom, mot_de_passe: motDePasse, est_admin: admin });
      setEmail("");
      setNom("");
      setMotDePasse("");
      setAdmin(false);
    });
  };

  return (
    <>
      <h1>Utilisateurs</h1>
      <Erreur erreur={action.erreur ?? comptes.erreur} />
      {!comptes.donnees ? (
        <Chargement />
      ) : (
        <div className="carte">
          <table>
            <thead>
              <tr><th>Nom</th><th>Rôle</th><th>État</th><th>Dernière connexion</th><th>Actions</th></tr>
            </thead>
            <tbody>
              {comptes.donnees.map((c) => {
                const bloque = c.bloque_jusqu_a && new Date(c.bloque_jusqu_a) > new Date();
                const soi = c.id === moi?.id;
                return (
                  <tr key={c.id}>
                    <td>{c.nom}<br /><span className="discret">{c.email}</span></td>
                    <td>{c.est_admin ? "Administrateur" : "Utilisateur"}</td>
                    <td className="ligne">
                      {c.actif ? <Pastille texte="Actif" ton="ok" /> : <Pastille texte="Désactivé" />}
                      {!c.totp_actif && <Pastille texte="TOTP à configurer" ton="alerte" />}
                      {bloque && <Pastille texte="Bloqué" ton="danger" />}
                    </td>
                    <td className="discret">{dateHeure(c.derniere_connexion)}</td>
                    <td>
                      <div className="ligne">
                        {!soi && <button className="lien" onClick={() => faire(() => patch(`/api/utilisateurs/${c.id}`, { actif: !c.actif }))}>{c.actif ? "Désactiver" : "Réactiver"}</button>}
                        {!soi && <button className="lien" onClick={() => faire(() => patch(`/api/utilisateurs/${c.id}`, { est_admin: !c.est_admin }))}>{c.est_admin ? "Retirer admin" : "Rendre admin"}</button>}
                        {c.totp_actif && (
                          <button
                            className="lien"
                            onClick={() => confirm(`Réinitialiser le TOTP de ${c.nom} ? Il devra le reconfigurer.`) && faire(() => post(`/api/utilisateurs/${c.id}/reinitialiser-totp`))}
                          >
                            Réinitialiser TOTP
                          </button>
                        )}
                        {bloque && <button className="lien" onClick={() => faire(() => post(`/api/utilisateurs/${c.id}/debloquer`))}>Débloquer</button>}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <form className="carte" onSubmit={creer} style={{ maxWidth: 560 }}>
        <h2 style={{ marginTop: 0 }}>Nouveau compte</h2>
        <label htmlFor="nom">Nom</label>
        <input id="nom" required value={nom} onChange={(e) => setNom(e.target.value)} />
        <label htmlFor="email">Adresse e-mail</label>
        <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <label htmlFor="mdp">Mot de passe initial (12 caractères minimum)</label>
        <input id="mdp" type="password" autoComplete="new-password" minLength={12} required value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />
        <label className="choix"><input type="checkbox" checked={admin} onChange={(e) => setAdmin(e.target.checked)} />Administrateur</label>
        <p className="discret">Transmettez le mot de passe par un autre canal ; la personne configurera son TOTP à la première connexion.</p>
        <button className="principal" disabled={action.enCours}>Créer le compte</button>
      </form>
    </>
  );
}
