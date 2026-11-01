import { useEffect, useState } from "react";
import { get, put } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { DECISIONS, NIVEAUX_REGLEMENTATION } from "../../libelles";
import type { LigneReglementation, VueProfilage } from "../../types";
import type { ContexteDiagnostic } from "./Diagnostic";

const TON_NIVEAU: Record<string, "danger" | "alerte" | "accent"> = { obligatoire: "danger", a_verifier: "alerte", recommande: "accent" };

export default function Profilage({ ctx }: { ctx: ContexteDiagnostic }) {
  const vue = useDonnees(() => get<VueProfilage>(`${ctx.url}/profilage`), [ctx.url]);
  const [reponses, setReponses] = useState<Record<string, string[]>>({});
  const action = useAction();

  useEffect(() => {
    if (vue.donnees) setReponses(vue.donnees.reponses);
  }, [vue.donnees]);

  if (vue.erreur) return <Erreur erreur={vue.erreur} />;
  if (!vue.donnees) return <Chargement />;
  const v = vue.donnees;

  // Les conditions d'affichage sont évaluées par le serveur ; on enregistre à chaque choix.
  const choisir = (code: string, choix: string, multiple: boolean) => {
    const actuels = reponses[code] ?? [];
    const valeurs = multiple ? (actuels.includes(choix) ? actuels.filter((c) => c !== choix) : [...actuels, choix]) : [choix];
    const nouvelles = { ...reponses, [code]: valeurs };
    setReponses(nouvelles);
    action.executer(async () => {
      vue.setDonnees(await put<VueProfilage>(`${ctx.url}/profilage`, { reponses: nouvelles }));
      await ctx.rechargerSynthese();
    });
  };

  return (
    <div className="grille-2">
      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Profil de l'organisation</h2>
        <p className="discret">Ces réponses déterminent les réglementations applicables, la profondeur du questionnaire et les cibles de maturité. Chaque réponse est enregistrée immédiatement.</p>
        <Erreur erreur={action.erreur} />
        {v.questions.filter((q) => q.visible).map((q) => (
          <fieldset key={q.code} style={{ border: "none", padding: 0, margin: "16px 0 0" }}>
            <legend style={{ fontWeight: 600 }}>
              {q.libelle} {v.sans_reponse.includes(q.code) && <Pastille texte="à renseigner" ton="alerte" />}
            </legend>
            {q.aide && <p className="discret">{q.aide}</p>}
            {q.choix.map((c) => (
              <label key={c.code} className="choix">
                <input
                  type={q.type === "choix_multiple" ? "checkbox" : "radio"}
                  name={q.code}
                  disabled={!ctx.saisie}
                  checked={(reponses[q.code] ?? []).includes(c.code)}
                  onChange={() => choisir(q.code, c.code, q.type === "choix_multiple")}
                />
                {c.libelle}
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      <Reglementations ctx={ctx} vue={v} miseAJour={(nv) => vue.setDonnees(nv)} />
    </div>
  );
}

function Reglementations({ ctx, vue, miseAJour }: { ctx: ContexteDiagnostic; vue: VueProfilage; miseAJour: (v: VueProfilage) => void }) {
  const [brouillons, setBrouillons] = useState<Record<string, { decision: string; justification: string }>>({});
  const [ajout, setAjout] = useState("");
  const [justificationAjout, setJustificationAjout] = useState("");
  const action = useAction();

  // Le profil vient de changer et le serveur a recalculé la liste : on oublie
  // les décisions en cours sur des réglementations qui n'y sont plus, et un
  // ajout prévu qui ressort désormais du calcul (ou n'est plus ajoutable).
  useEffect(() => {
    const admises = new Map(vue.reglementations.map((r) => [r.code, r.decisions_admises]));
    setBrouillons((b) => {
      const gardes = Object.fromEntries(Object.entries(b).filter(([code, d]) => admises.get(code)?.includes(d.decision)));
      return Object.keys(gardes).length === Object.keys(b).length ? b : gardes;
    });
    if (ajout && !vue.ajoutables.some((a) => a.code === ajout)) {
      setAjout("");
      setJustificationAjout("");
    }
  }, [vue, ajout]);

  const valeur = (l: LigneReglementation) => brouillons[l.code] ?? { decision: l.decision, justification: l.justification };
  const modifier = (l: LigneReglementation, champ: "decision" | "justification", v: string) =>
    setBrouillons({ ...brouillons, [l.code]: { ...valeur(l), [champ]: v } });

  const enregistrer = () =>
    action.executer(async () => {
      const corps: Record<string, unknown> = { decisions: brouillons };
      if (ajout) Object.assign(corps, { ajout, justification_ajout: justificationAjout });
      miseAJour(await put<VueProfilage>(`${ctx.url}/reglementations`, corps));
      setBrouillons({});
      setAjout("");
      setJustificationAjout("");
      await ctx.rechargerSynthese();
    });

  const modifie = Object.keys(brouillons).length > 0 || ajout !== "";

  return (
    <div className="carte">
      <h2 style={{ marginTop: 0 }}>Réglementations</h2>
      <p className="discret">Résultat indicatif, qui ne constitue pas un avis juridique. Tranchez les « à vérifier » ; une justification est demandée quand vous vous écartez du calcul.</p>
      {vue.reglementations.length === 0 && <p className="discret">Renseignez le profil pour voir les réglementations applicables.</p>}
      {vue.reglementations.map((l) => (
        <div key={l.code} className="question">
          <div className="ligne espace">
            <strong>{l.libelle}</strong>
            <span className="ligne">
              {l.origine === "forcage" ? <Pastille texte="Ajoutée" /> : <Pastille texte={NIVEAUX_REGLEMENTATION[l.niveau_calcule]} ton={TON_NIVEAU[l.niveau_calcule]} />}
            </span>
          </div>
          {l.critere && <p className="discret">{l.critere}</p>}
          <div className="ligne">
            {l.decisions_admises.map((d) => (
              <label key={d} className="choix">
                <input type="radio" name={`dec-${l.code}`} disabled={!ctx.saisie} checked={valeur(l).decision === d} onChange={() => modifier(l, "decision", d)} />
                {DECISIONS[d]}
              </label>
            ))}
          </div>
          {(valeur(l).justification || brouillons[l.code]) && (
            <input
              aria-label={`Justification pour ${l.libelle}`}
              placeholder="Justification"
              disabled={!ctx.saisie}
              value={valeur(l).justification}
              onChange={(e) => modifier(l, "justification", e.target.value)}
            />
          )}
        </div>
      ))}
      {ctx.saisie && vue.ajoutables.length > 0 && (
        <>
          <h3>Ajouter une réglementation</h3>
          <select value={ajout} onChange={(e) => setAjout(e.target.value)} aria-label="Réglementation à ajouter">
            <option value="">Choisir…</option>
            {vue.ajoutables.map((a) => <option key={a.code} value={a.code}>{a.libelle}</option>)}
          </select>
          {ajout && <input style={{ marginTop: 8 }} placeholder="Justification (obligatoire)" value={justificationAjout} onChange={(e) => setJustificationAjout(e.target.value)} />}
        </>
      )}
      <Erreur erreur={action.erreur} />
      {ctx.saisie && (
        <p className="ligne" style={{ marginTop: 12 }}>
          <button className="principal" disabled={!modifie || action.enCours} onClick={enregistrer}>Enregistrer les décisions</button>
          <span className="discret">{modifie ? "Décisions modifiées, non enregistrées." : "Rien à enregistrer : la liste reflète le profil."}</span>
        </p>
      )}
    </div>
  );
}
