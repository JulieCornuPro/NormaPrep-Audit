import { useState, type FormEvent } from "react";
import { api } from "../api";
import { Erreur, useAction } from "../composants/communs";
import { useSession } from "../session";

interface Etape {
  etape: "totp" | "enrolement";
  jeton: string;
  secret: string | null;
  qr_svg: string | null;
}

export default function Connexion() {
  const { connecter } = useSession();
  const [email, setEmail] = useState("");
  const [motDePasse, setMotDePasse] = useState("");
  const [etape, setEtape] = useState<Etape | null>(null);
  const [code, setCode] = useState("");
  const { enCours, erreur, executer, setErreur } = useAction();

  const envoyerIdentifiants = (e: FormEvent) => {
    e.preventDefault();
    executer(async () => {
      setEtape(await api<Etape>("/api/auth/connexion", { methode: "POST", corps: { email, mot_de_passe: motDePasse }, public: true }));
      setMotDePasse("");
    });
  };

  const envoyerCode = (e: FormEvent) => {
    e.preventDefault();
    executer(async () => {
      const r = await api<{ jeton_acces: string }>("/api/auth/totp", {
        methode: "POST",
        corps: { jeton: etape!.jeton, code },
        public: true,
      });
      await connecter(r.jeton_acces);
    });
  };

  return (
    <div className="page-etroite">
      <h1>NormaPrep Audit</h1>
      <div className="carte">
        {!etape && (
          <form onSubmit={envoyerIdentifiants}>
            <label htmlFor="email">Adresse e-mail</label>
            <input id="email" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            <label htmlFor="mdp">Mot de passe</label>
            <input id="mdp" type="password" autoComplete="current-password" required value={motDePasse} onChange={(e) => setMotDePasse(e.target.value)} />
            <Erreur erreur={erreur} />
            <p style={{ marginTop: 16 }}>
              <button className="principal" disabled={enCours}>Continuer</button>
            </p>
          </form>
        )}

        {etape && (
          <form onSubmit={envoyerCode}>
            {etape.etape === "enrolement" ? (
              <>
                <h2 style={{ marginTop: 0 }}>Activer la double authentification</h2>
                <p>Scannez ce QR code avec votre application d'authentification (Microsoft Authenticator, Google Authenticator, FreeOTP…).</p>
                {etape.qr_svg && <div className="qr" dangerouslySetInnerHTML={{ __html: etape.qr_svg }} />}
                <p className="discret">
                  Ou saisissez cette clé à la main : <code>{etape.secret}</code>
                </p>
              </>
            ) : (
              <p>Saisissez le code à 6 chiffres affiché par votre application d'authentification.</p>
            )}
            <label htmlFor="code">Code</label>
            <input
              id="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9 ]{6,7}"
              required
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
            <Erreur erreur={erreur} />
            <p className="ligne" style={{ marginTop: 16 }}>
              <button className="principal" disabled={enCours}>Se connecter</button>
              <button
                type="button"
                className="lien"
                onClick={() => {
                  setEtape(null);
                  setCode("");
                  setErreur(null);
                }}
              >
                Recommencer
              </button>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
