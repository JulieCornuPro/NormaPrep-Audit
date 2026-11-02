import type { CSSProperties } from "react";
import { get } from "../../api";
import { Chargement, Erreur, Pastille, useDonnees } from "../../composants/communs";
import Radar from "../../composants/Radar";
import { couleurTheme, EFFORTS, nombre } from "../../libelles";
import type { Resultats } from "../../types";
import type { ContexteDiagnostic } from "./Diagnostic";

const tonEcart = (e: number | null) => (e === null ? undefined : e > 1 ? "danger" : e > 0 ? "alerte" : "ok");

export default function ResultatsPage({ ctx }: { ctx: ContexteDiagnostic }) {
  const r = useDonnees(() => get<Resultats>(`${ctx.url}/resultats`), [ctx.url]);
  if (r.erreur) return <Erreur erreur={r.erreur} />;
  if (!r.donnees) return <Chargement />;
  const res = r.donnees;
  const axes = res.themes.flatMap((t) => t.sous_themes.filter((s) => s.score !== null).map((s) => ({ ...s, couleur: couleurTheme(t.couleur) })));

  return (
    <>
      {!res.fige && res.progression.restantes > 0 && (
        <div className="message info">Résultats provisoires : {res.progression.restantes} question(s) sans réponse.</div>
      )}
      {res.fige && <div className="message ok">Résultats figés à la finalisation du diagnostic.</div>}

      <div className="grille-2">
        <div className="carte">
          <h2 style={{ marginTop: 0 }}>Synthèse</h2>
          <table>
            <thead>
              <tr><th /><th className="nombre">Constaté</th><th className="nombre">Cible</th><th className="nombre">Écart</th></tr>
            </thead>
            <tbody>
              {res.themes.map((t) => (
                <tr key={t.code}>
                  <td><span className="pastille-theme" style={{ "--couleur-theme": couleurTheme(t.couleur) } as CSSProperties} />{t.libelle}</td>
                  <td className="nombre">{nombre(t.score)}</td>
                  <td className="nombre">{nombre(t.cible)}</td>
                  <td className="nombre">{t.ecart !== null ? <Pastille texte={nombre(t.ecart)} ton={tonEcart(t.ecart)} /> : "—"}</td>
                </tr>
              ))}
              <tr>
                <td><strong>Global</strong></td>
                <td className="nombre"><strong>{nombre(res.global.score)}</strong></td>
                <td className="nombre"><strong>{nombre(res.global.cible)}</strong></td>
                <td className="nombre">{res.global.ecart !== null ? <Pastille texte={nombre(res.global.ecart)} ton={tonEcart(res.global.ecart)} /> : "—"}</td>
              </tr>
            </tbody>
          </table>
          <p className="discret">Écart = cible − constaté : positif, la maturité est en dessous de la cible.</p>
        </div>
        <div className="carte">
          <h2 style={{ marginTop: 0 }}>Maturité par sous-thème</h2>
          <Radar axes={axes} />
        </div>
      </div>

      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Détail par sous-thème</h2>
        <table>
          <thead>
            <tr><th>Sous-thème</th><th className="nombre">Constaté</th><th className="nombre">Cible</th><th className="nombre">Écart</th><th>Cible fixée par</th></tr>
          </thead>
          <tbody>
            {res.themes.flatMap((t) =>
              t.sous_themes.map((s) => (
                <tr key={s.code}>
                  <td><span className="pastille-theme" style={{ "--couleur-theme": couleurTheme(t.couleur) } as CSSProperties} />{s.code} · {s.libelle}</td>
                  <td className="nombre">{s.non_applicable ? "N/A" : nombre(s.score)}</td>
                  <td className="nombre">{nombre(s.cible)}</td>
                  <td className="nombre">{s.ecart !== null ? <Pastille texte={nombre(s.ecart)} ton={tonEcart(s.ecart)} /> : "—"}</td>
                  <td className="discret">{s.reglementation ?? "—"}</td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>

      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Recommandations ({res.recommandations.length})</h2>
        {res.recommandations.length === 0 ? (
          <p className="discret">Aucune recommandation déclenchée.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Recommandation</th><th>Sous-thème</th><th>Effort</th><th>Prestation</th></tr>
            </thead>
            <tbody>
              {res.recommandations.map((x) => (
                <tr key={x.ref}>
                  <td>{x.texte} {x.quick_win && <Pastille texte="Quick win" ton="ok" />}</td>
                  <td className="discret">{x.sous_theme_libelle}<br />constaté {nombre(x.niveau_constate)}, seuil {x.seuil}</td>
                  <td>{EFFORTS[x.effort] ?? x.effort}</td>
                  <td>{x.prestation_libelle ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {res.audits_proposes.length > 0 && (
        <div className="carte">
          <h2 style={{ marginTop: 0 }}>Audits proposés</h2>
          <p className="discret">Prestations appelées par les recommandations ; elles seront lancées en un clic au jalon 3.</p>
          <ul>
            {res.audits_proposes.map((a) => (
              <li key={a.code}>
                <strong>{a.libelle}</strong>
                {a.referentiel_audit && <> — référentiel {a.referentiel_audit}{a.sections.length ? `, sections ${a.sections.join(", ")}` : ""}</>}
                <span className="discret"> (sous-thèmes {a.sous_themes.join(", ")})</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
