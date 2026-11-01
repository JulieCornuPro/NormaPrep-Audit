import { useState, type FormEvent } from "react";
import { post } from "../api";
import { Erreur, useAction } from "../composants/communs";
import { useSession } from "../session";

export default function MonCompte() {
  const { moi, deconnecter } = useSession();
  const [actuel, setActuel] = useState("");
  const [nouveau, setNouveau] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const { enCours, erreur, executer, setErreur } = useAction();

  const envoyer = (e: FormEvent) => {
    e.preventDefault();
    if (nouveau !== confirmation) {
      setErreur(new Error("Les deux saisies du nouveau mot de passe diffèrent."));
      return;
    }
    executer(async () => {
      await post("/api/auth/mot-de-passe", { actuel, nouveau });
      // Les jetons existants sont invalidés : il faut se reconnecter.
      deconnecter();
    });
  };

  return (
    <>
      <h1>Mon compte</h1>
      <p className="discret">{moi?.nom} · {moi?.email}</p>
      <div className="carte" style={{ maxWidth: 480 }}>
        <h2 style={{ marginTop: 0 }}>Changer de mot de passe</h2>
        <form onSubmit={envoyer}>
          <label htmlFor="actuel">Mot de passe actuel</label>
          <input id="actuel" type="password" autoComplete="current-password" required value={actuel} onChange={(e) => setActuel(e.target.value)} />
          <label htmlFor="nouveau">Nouveau mot de passe (12 caractères minimum)</label>
          <input id="nouveau" type="password" autoComplete="new-password" minLength={12} required value={nouveau} onChange={(e) => setNouveau(e.target.value)} />
          <label htmlFor="confirmation">Confirmation</label>
          <input id="confirmation" type="password" autoComplete="new-password" required value={confirmation} onChange={(e) => setConfirmation(e.target.value)} />
          <Erreur erreur={erreur} />
          <p className="discret">Après le changement, vous serez déconnecté de toutes vos sessions.</p>
          <button className="principal" disabled={enCours}>Changer</button>
        </form>
      </div>
    </>
  );
}
