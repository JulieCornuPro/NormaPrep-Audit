import { useState } from "react";
import { del, get, post, put } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { dateHeure, ETATS_SOCLE } from "../../libelles";
import type { ElementSocle, ReferentielSocle, Socle } from "../../types";
import type { ContexteAnalyse } from "./Analyse";

const TONS: Record<string, "ok" | "alerte" | "danger" | "accent" | undefined> = {
  applique: "ok",
  partiel: "alerte",
  non_applique: "danger",
  non_evalue: undefined,
  non_applicable: "accent",
};

export default function SoclePage({ ctx }: { ctx: ContexteAnalyse }) {
  const socle = useDonnees(() => get<Socle>(`${ctx.url}/socle`), [ctx.url]);
  const action = useAction();
  const [choix, setChoix] = useState({ referentiel_id: "", profil: "", motif: "" });

  if (!socle.donnees) return <><Erreur erreur={socle.erreur} /><Chargement /></>;
  const s = socle.donnees;
  const choisi = s.disponibles.find((d) => String(d.id) === choix.referentiel_id);

  const ajouter = (referentiel_id: number, profil: string | null, motif: string) =>
    action.executer(async () => {
      await post(`${ctx.url}/socle`, { referentiel_id, profil: profil || null, motif });
      setChoix({ referentiel_id: "", profil: "", motif: "" });
      await Promise.all([socle.recharger(), ctx.recharger()]);
    });

  return (
    <>
      <Erreur erreur={action.erreur} />
      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Composition du socle</h2>
        <p className="discret">
          Référentiels applicables à l'objet étudié : obligations réglementaires, guides de bonnes pratiques, référentiels du client. Pour chacun, on évalue l'état
          d'application de chaque mesure et on justifie les écarts.
        </p>
        {s.proposes.length > 0 && (
          <div className="message info">
            <strong>Proposés par le diagnostic lié</strong>
            {s.proposes.map((p) => (
              <div key={p.code} className="ligne espace" style={{ marginTop: 6 }}>
                <span>
                  {p.code}{p.profil ? ` (${p.profil})` : ""} · <span className="discret">{p.motifs.join(", ")}</span>
                </span>
                {ctx.saisie && (
                  <button disabled={action.enCours} onClick={() => ajouter(p.referentiel_id, p.profil, `Réglementation retenue : ${p.motifs.join(", ")}`)}>
                    Ajouter
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        {ctx.saisie && (
          <div className="ligne" style={{ flexWrap: "wrap", alignItems: "flex-end" }}>
            <div style={{ flex: 2, minWidth: 220 }}>
              <label htmlFor="sc-ref">Référentiel</label>
              <select id="sc-ref" value={choix.referentiel_id} onChange={(e) => setChoix({ ...choix, referentiel_id: e.target.value, profil: "" })}>
                <option value="">Choisir…</option>
                {s.disponibles.map((d) => (
                  <option key={d.id} value={d.id}>{d.code} {d.version}{d.client ? " (client)" : ""} · {d.libelle}</option>
                ))}
              </select>
            </div>
            {choisi && choisi.profils.length > 0 && (
              <div style={{ flex: 1, minWidth: 140 }}>
                <label htmlFor="sc-profil">Profil</label>
                <select id="sc-profil" value={choix.profil} onChange={(e) => setChoix({ ...choix, profil: e.target.value })}>
                  <option value="">Choisir…</option>
                  {choisi.profils.map((p) => <option key={p}>{p}</option>)}
                </select>
              </div>
            )}
            <div style={{ flex: 2, minWidth: 200 }}>
              <label htmlFor="sc-motif">Motif</label>
              <input id="sc-motif" value={choix.motif} onChange={(e) => setChoix({ ...choix, motif: e.target.value })} placeholder="Exigence contractuelle, politique interne…" />
            </div>
            <button
              className="principal"
              disabled={!choisi || (choisi.profils.length > 0 && !choix.profil) || action.enCours}
              onClick={() => ajouter(choisi!.id, choix.profil, choix.motif)}
            >
              Ajouter au socle
            </button>
          </div>
        )}
        {s.referentiels.length === 0 && <p className="discret">Le socle est vide.</p>}
      </div>

      {s.referentiels.map((r) => (
        <BlocReferentiel key={r.id} ctx={ctx} r={r} recharger={async () => { await Promise.all([socle.recharger(), ctx.recharger()]); }} />
      ))}
    </>
  );
}

function BlocReferentiel({ ctx, r, recharger }: { ctx: ContexteAnalyse; r: ReferentielSocle; recharger: () => Promise<void> }) {
  const action = useAction();
  const [filtre, setFiltre] = useState("");
  const [info, setInfo] = useState("");
  const total = r.elements.length;
  const evalues = total - r.compte.non_evalue;
  const elements = filtre ? r.elements.filter((e) => e.etat === filtre) : r.elements;
  const groupes: [string, ElementSocle[]][] = [];
  for (const e of elements) {
    const dernier = groupes[groupes.length - 1];
    if (dernier && dernier[0] === e.groupe) dernier[1].push(e);
    else groupes.push([e.groupe, [e]]);
  }

  return (
    <div className="carte">
      <div className="ligne espace">
        <div>
          <h2 style={{ margin: 0 }}>
            {r.referentiel.code} {r.referentiel.version}{r.profil ? ` · profil ${r.profil}` : ""}
            {r.referentiel.client && <> <Pastille texte="Client" ton="accent" /></>}
          </h2>
          <p className="discret" style={{ margin: "4px 0 0" }}>
            {r.referentiel.libelle}
            {r.motif && <><br />Motif : {r.motif}</>}
          </p>
        </div>
        {ctx.saisie && (
          <div className="ligne">
            {ctx.analyse.diagnostic_id && (
              <button
                disabled={action.enCours}
                title="Présume l'état des mesures non évaluées à partir des réponses du diagnostic. Ne remplace aucune saisie."
                onClick={() =>
                  action.executer(async () => {
                    const { remplis } = await post<{ remplis: number }>(`${ctx.url}/socle/${r.id}/pre-remplir`);
                    setInfo(remplis ? `${remplis} mesure(s) pré-remplie(s) depuis le diagnostic, à valider.` : "Aucune mesure à pré-remplir (pas de correspondance ou déjà évaluées).");
                    await recharger();
                  })
                }
              >
                Pré-remplir depuis le diagnostic
              </button>
            )}
            <button
              className="lien danger"
              disabled={action.enCours}
              onClick={() =>
                window.confirm(`Retirer ${r.referentiel.code} du socle ? Les évaluations saisies seront perdues.`) &&
                action.executer(async () => {
                  await del(`${ctx.url}/socle/${r.id}`);
                  await recharger();
                })
              }
            >
              Retirer
            </button>
          </div>
        )}
      </div>
      <Erreur erreur={action.erreur} />
      {info && <div className="message ok">{info}</div>}

      <div className="progression" style={{ margin: "14px 0 8px" }} role="progressbar" aria-valuenow={evalues} aria-valuemin={0} aria-valuemax={total}>
        <div style={{ width: `${total ? (100 * evalues) / total : 0}%` }} />
      </div>
      <div className="ligne" style={{ flexWrap: "wrap", gap: 6 }}>
        <span className="discret">{evalues} / {total} évalué(e)s{r.referentiel.niveau ? ` (niveau « ${r.referentiel.niveau} »)` : ""} ·</span>
        <button className={`lien ${filtre === "" ? "" : "discret"}`} onClick={() => setFiltre("")}>Tout</button>
        {Object.entries(ETATS_SOCLE).map(([code, libelle]) => (
          <button key={code} className="lien" onClick={() => setFiltre(filtre === code ? "" : code)} aria-pressed={filtre === code}>
            <Pastille texte={`${libelle} : ${r.compte[code] ?? 0}`} ton={filtre === code || !filtre ? TONS[code] : undefined} />
          </button>
        ))}
      </div>
      {r.sans_justification > 0 && (
        <div className="message alerte">{r.sans_justification} écart(s) sans justification : précisez pourquoi la mesure n'est pas (ou partiellement) appliquée.</div>
      )}

      {groupes.map(([groupe, liste]) => (
        <div key={groupe + liste[0].code}>
          {groupe && <h3 style={{ marginBottom: 4 }}>{groupe}</h3>}
          {liste.map((e) => <LigneSocle key={e.code} ctx={ctx} sid={r.id} e={e} recharger={recharger} />)}
        </div>
      ))}
      {elements.length === 0 && <p className="discret">Aucune mesure dans cet état.</p>}
    </div>
  );
}

function LigneSocle({ ctx, sid, e, recharger }: { ctx: ContexteAnalyse; sid: number; e: ElementSocle; recharger: () => Promise<void> }) {
  const [f, setF] = useState({ etat: e.etat, ecart: e.ecart, justification: e.justification });
  const [ouvert, setOuvert] = useState(false);
  const action = useAction();
  const modifie = f.etat !== e.etat || f.ecart !== e.ecart || f.justification !== e.justification;
  const ecart = f.etat === "partiel" || f.etat === "non_applique";
  const avecTexte = ecart || f.etat === "non_applicable" || f.ecart || f.justification;

  const enregistrer = () =>
    action.executer(async () => {
      await put(`${ctx.url}/socle/${sid}/etats/${encodeURIComponent(e.code)}`, f);
      await recharger();
    });

  return (
    <div className="question" style={{ padding: "10px 0" }}>
      <div className="ligne espace" style={{ alignItems: "flex-start" }}>
        <div style={{ flex: 1 }}>
          <code>{e.code}</code> {e.libelle}
          {e.source === "maturite" && <> <Pastille texte="Présumé, à valider" ton="alerte" /></>}
          {e.details.length > 0 && (
            <button className="lien" style={{ marginLeft: 8 }} onClick={() => setOuvert(!ouvert)} aria-expanded={ouvert}>
              {ouvert ? "Masquer" : `${e.details.length} contrôle(s)`}
            </button>
          )}
        </div>
        <select
          aria-label={`État de ${e.code}`}
          value={f.etat}
          disabled={!ctx.saisie}
          onChange={(ev) => setF({ ...f, etat: ev.target.value })}
          style={{ width: 230 }}
        >
          {Object.entries(ETATS_SOCLE).map(([code, libelle]) => <option key={code} value={code}>{libelle}</option>)}
        </select>
      </div>
      {ouvert && (
        <ul className="discret" style={{ margin: "6px 0" }}>
          {e.details.map((d) => <li key={d.code}><code>{d.code}</code> {d.libelle}</li>)}
        </ul>
      )}
      {avecTexte && (
        <div className="grille-2" style={{ gap: 12, marginTop: 6 }}>
          <textarea
            aria-label={`Écart constaté pour ${e.code}`}
            placeholder="Écart constaté : ce qui n'est pas en place"
            value={f.ecart}
            disabled={!ctx.saisie}
            onChange={(ev) => setF({ ...f, ecart: ev.target.value })}
          />
          <textarea
            aria-label={`Justification pour ${e.code}`}
            placeholder={f.etat === "non_applicable" ? "Pourquoi la mesure ne s'applique pas" : "Justification de l'écart (risque accepté, mesure compensatoire, plan…)"}
            value={f.justification}
            disabled={!ctx.saisie}
            onChange={(ev) => setF({ ...f, justification: ev.target.value })}
          />
        </div>
      )}
      <Erreur erreur={action.erreur} />
      {ctx.saisie && modifie && (
        <div className="ligne" style={{ marginTop: 6 }}>
          <button className="principal" disabled={action.enCours} onClick={enregistrer}>Enregistrer</button>
          <button className="lien" onClick={() => setF({ etat: e.etat, ecart: e.ecart, justification: e.justification })}>Annuler</button>
        </div>
      )}
      {!modifie && e.saisi_le && <span className="discret" style={{ fontSize: 12 }}>Saisi le {dateHeure(e.saisi_le)}</span>}
    </div>
  );
}
