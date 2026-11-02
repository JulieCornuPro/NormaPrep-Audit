import { useState } from "react";
import { get, post } from "../../api";
import { Chargement, Erreur, Pastille, useAction, useDonnees } from "../../composants/communs";
import { dateHeure } from "../../libelles";
import Televersement from "../../composants/Televersement";
import ArbreReferentiel from "../../composants/ArbreReferentiel";
import type { NoeudArbre } from "../../types";

interface Ref {
  id: number;
  code: string;
  version: string;
  nature: string;
  libelle: string;
  actif: boolean;
  importe_le: string;
  avertissements: string[];
  niveaux: string[];
  profils: string[];
}

interface Detail {
  code: string;
  version: string;
  libelle: string;
  source: string;
  licence: string;
  niveaux: string[];
  profils: string[];
  arbre: NoeudArbre[];
}

interface ResultatImport {
  succes: boolean;
  deja_importe: boolean;
  code: string;
  version: string;
  erreurs: string[];
  avertissements: string[];
  stats: Record<string, number>;
}

interface Couverture {
  referentiel: string;
  version: string;
  nb_exigences: number;
  nb_couvertes: number;
  non_couvertes: string[];
}

export default function Referentiels() {
  const refs = useDonnees(() => get<Ref[]>("/api/contenu/referentiels?toutes_versions=true"), []);
  const dispo = useDonnees(() => get<{ nature: string; chemin: string }[]>("/api/contenu/disponibles"), []);
  const [resultat, setResultat] = useState<ResultatImport | null>(null);
  const [couverture, setCouverture] = useState<Couverture | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const action = useAction();

  const importer = (nature: string, chemin: string, simulation: boolean) =>
    action.executer(async () => {
      setResultat(await post<ResultatImport>("/api/contenu/import", { nature, chemin, simulation }));
      await refs.recharger();
    });

  return (
    <>
      <h1>Référentiels</h1>
      <Erreur erreur={action.erreur ?? refs.erreur} />

      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Importés</h2>
        {!refs.donnees ? (
          <Chargement />
        ) : refs.donnees.length === 0 ? (
          <p className="discret">Aucun référentiel. Importez d'abord le référentiel pivot (audit ANSSI), puis le référentiel de maturité.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Code</th><th>Version</th><th>Nature</th><th>Importé le</th><th>État</th><th /></tr>
            </thead>
            <tbody>
              {refs.donnees.map((r) => (
                <tr key={r.id}>
                  <td>{r.code}<br /><span className="discret">{r.libelle}</span></td>
                  <td>{r.version}</td>
                  <td>{r.nature === "audit" ? "Audit" : "Maturité"}</td>
                  <td>{dateHeure(r.importe_le)}</td>
                  <td>{r.actif ? <Pastille texte="Active" ton="ok" /> : <Pastille texte="Ancienne" />}</td>
                  <td>
                    {r.actif && r.nature === "audit" && (
                      <button className="lien" onClick={() => action.executer(async () => setDetail(await get<Detail>(`/api/contenu/referentiels/${r.code}`)))}>
                        Consulter
                      </button>
                    )}{" "}
                    {r.actif && r.nature === "audit" && (
                      <button className="lien" onClick={() => action.executer(async () => setCouverture(await get<Couverture>(`/api/contenu/couverture/${r.code}`)))}>
                        Couverture
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {couverture && (
          <div className="message info">
            {couverture.referentiel} {couverture.version} : {couverture.nb_couvertes} / {couverture.nb_exigences} exigences reliées à au moins une question.
            {couverture.non_couvertes.length > 0 && <> Non couvertes : {couverture.non_couvertes.join(", ")}.</>}
          </div>
        )}
      </div>

      {detail && (
        <div className="carte">
          <div className="ligne espace">
            <h2 style={{ marginTop: 0 }}>{detail.code} {detail.version}</h2>
            <button className="lien" onClick={() => setDetail(null)}>Fermer</button>
          </div>
          <p>{detail.libelle}</p>
          <p className="discret">
            Niveaux : {detail.niveaux.join(" › ") || "—"}
            {detail.profils.length > 0 && <> · profils : {detail.profils.join(", ")}</>}
            {detail.source && <><br />Source : {detail.source}</>}
            {detail.licence && <><br />Licence : {detail.licence}</>}
          </p>
          <ArbreReferentiel racines={detail.arbre} niveaux={detail.niveaux} profils={detail.profils} />
        </div>
      )}

      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Charger un classeur Excel</h2>
        <p className="discret">Référentiels de la bibliothèque, visibles dans toutes les missions. Un référentiel propre à un client se charge depuis sa mission.</p>
        <Televersement url="/api/contenu/televerser" apres={refs.recharger} />
      </div>

      <div className="carte">
        <h2 style={{ marginTop: 0 }}>Dossier de contenu</h2>
        <p className="discret">Fichiers présents dans le dossier <code>content/</code> du serveur. « Vérifier » valide sans rien écrire.</p>
        {dispo.donnees?.map((d) => (
          <div key={d.chemin} className="ligne espace question">
            <span><Pastille texte={d.nature === "audit" ? "Audit" : "Maturité"} /> <code>{d.chemin}</code></span>
            <span className="ligne">
              <button disabled={action.enCours} onClick={() => importer(d.nature, d.chemin, true)}>Vérifier</button>
              <button className="principal" disabled={action.enCours} onClick={() => importer(d.nature, d.chemin, false)}>Importer</button>
            </span>
          </div>
        ))}
        {resultat && (
          <div className={`message ${resultat.succes ? "ok" : "erreur"}`}>
            <strong>
              {resultat.succes
                ? resultat.deja_importe
                  ? `${resultat.code} ${resultat.version} : déjà importé à l'identique.`
                  : `${resultat.code} ${resultat.version} : valide${Object.keys(resultat.stats).length ? " et importé" : ""}.`
                : `Import refusé (${resultat.erreurs.length} erreur(s)) : rien n'a été écrit.`}
            </strong>
            {resultat.erreurs.length > 0 && <ul>{resultat.erreurs.map((e) => <li key={e}>{e}</li>)}</ul>}
            {resultat.avertissements.length > 0 && (
              <details>
                <summary>{resultat.avertissements.length} avertissement(s)</summary>
                <ul>{resultat.avertissements.map((e) => <li key={e}>{e}</li>)}</ul>
              </details>
            )}
          </div>
        )}
      </div>
    </>
  );
}
