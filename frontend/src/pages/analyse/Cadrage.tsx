import { useState } from "react";
import { patch } from "../../api";
import { Erreur, useAction } from "../../composants/communs";
import { STATUTS } from "../../libelles";
import type { NiveauGravite } from "../../types";
import type { ContexteAnalyse } from "./Analyse";

export default function Cadrage({ ctx }: { ctx: ContexteAnalyse }) {
  const a = ctx.analyse;
  const [f, setF] = useState({
    titre: a.titre,
    objet: a.objet,
    perimetre: a.perimetre,
    participants: a.participants,
    cycle_strategique_mois: a.cycle_strategique_mois?.toString() ?? "",
    cycle_operationnel_mois: a.cycle_operationnel_mois?.toString() ?? "",
    diagnostic_id: a.diagnostic_id?.toString() ?? "",
  });
  const [echelle, setEchelle] = useState<NiveauGravite[]>(a.echelle_gravite);
  const [enregistre, setEnregistre] = useState(false);
  const action = useAction();
  const champ = (cle: keyof typeof f) => ({
    value: f[cle],
    disabled: !ctx.saisie,
    onChange: (e: { target: { value: string } }) => {
      setF({ ...f, [cle]: e.target.value });
      setEnregistre(false);
    },
  });
  const entier = (v: string) => (v.trim() ? Number(v) : null);

  const enregistrer = () =>
    action.executer(async () => {
      await patch(ctx.url, {
        ...f,
        cycle_strategique_mois: entier(f.cycle_strategique_mois),
        cycle_operationnel_mois: entier(f.cycle_operationnel_mois),
        diagnostic_id: entier(f.diagnostic_id),
        echelle_gravite: echelle.map((n, i) => ({ ...n, niveau: i + 1 })),
      });
      await ctx.recharger();
      setEnregistre(true);
    });

  const modifierNiveau = (i: number, cle: "libelle" | "description", v: string) => {
    setEchelle(echelle.map((n, j) => (j === i ? { ...n, [cle]: v } : n)));
    setEnregistre(false);
  };

  return (
    <div className="grille-2">
      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Cadre de l'étude</h2>
        <label htmlFor="titre">Titre</label>
        <input id="titre" {...champ("titre")} />
        <label htmlFor="objet">Objet de l'étude</label>
        <textarea id="objet" {...champ("objet")} placeholder="Finalité de l'analyse : homologation, conception d'un projet, revue annuelle…" />
        <label htmlFor="perimetre">Périmètre métier et technique</label>
        <textarea id="perimetre" {...champ("perimetre")} />
        <label htmlFor="participants">Participants aux ateliers</label>
        <textarea id="participants" {...champ("participants")} placeholder="Une personne par ligne, avec son rôle." />
        <div className="grille-2" style={{ gap: 12 }}>
          <div>
            <label htmlFor="cs">Cycle stratégique (mois)</label>
            <input id="cs" type="number" min={1} max={120} {...champ("cycle_strategique_mois")} />
          </div>
          <div>
            <label htmlFor="co">Cycle opérationnel (mois)</label>
            <input id="co" type="number" min={1} max={120} {...champ("cycle_operationnel_mois")} />
          </div>
        </div>
        <label htmlFor="diag">Diagnostic de maturité lié</label>
        <select id="diag" {...champ("diagnostic_id")}>
          <option value="">Aucun, analyse autonome</option>
          {a.diagnostics_mission.map((d) => <option key={d.id} value={d.id}>Diagnostic n° {d.id} ({STATUTS[d.statut] ?? d.statut})</option>)}
        </select>
      </div>

      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Échelle de gravité</h2>
        <p className="discret">Du moins grave au plus grave. Elle sert à coter les événements redoutés.</p>
        <table>
          <thead><tr><th>Niveau</th><th>Libellé</th><th>Description</th><th /></tr></thead>
          <tbody>
            {echelle.map((n, i) => (
              <tr key={i}>
                <td className="mono">G{i + 1}</td>
                <td><input aria-label={`Libellé G${i + 1}`} value={n.libelle} disabled={!ctx.saisie} onChange={(e) => modifierNiveau(i, "libelle", e.target.value)} /></td>
                <td><textarea aria-label={`Description G${i + 1}`} value={n.description} disabled={!ctx.saisie} onChange={(e) => modifierNiveau(i, "description", e.target.value)} style={{ minHeight: 40 }} /></td>
                <td>
                  {ctx.saisie && echelle.length > 2 && i === echelle.length - 1 && (
                    <button className="lien danger" onClick={() => setEchelle(echelle.slice(0, -1))}>Retirer</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {ctx.saisie && echelle.length < 9 && (
          <button className="lien" onClick={() => setEchelle([...echelle, { niveau: echelle.length + 1, libelle: "", description: "" }])}>
            Ajouter un niveau
          </button>
        )}
      </div>

      {ctx.saisie && (
        <div>
          <Erreur erreur={action.erreur} />
          <div className="ligne">
            <button className="principal" disabled={action.enCours} onClick={enregistrer}>Enregistrer le cadrage</button>
            {enregistre && <span className="discret">Enregistré.</span>}
          </div>
        </div>
      )}
    </div>
  );
}
