import { Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { FournisseurSession, useSession } from "./session";
import Connexion from "./pages/Connexion";
import Missions from "./pages/Missions";
import MissionPage from "./pages/Mission";
import DiagnosticPage from "./pages/diagnostic/Diagnostic";
import Utilisateurs from "./pages/admin/Utilisateurs";
import Referentiels from "./pages/admin/Referentiels";
import Journal from "./pages/admin/Journal";
import PreQuestionnairePublic from "./pages/PreQuestionnairePublic";
import MonCompte from "./pages/MonCompte";

export default function App() {
  return (
    <FournisseurSession>
      <Routes>
        {/* Page publique du client : aucun compte, accès par lien. */}
        <Route path="/pre-questionnaire/:jeton" element={<PreQuestionnairePublic />} />
        <Route path="*" element={<Application />} />
      </Routes>
    </FournisseurSession>
  );
}

function Application() {
  const { moi, pret, deconnecter } = useSession();
  const lieu = useLocation();
  if (!pret) return null;
  if (!moi) return lieu.pathname === "/connexion" ? <Connexion /> : <Navigate to="/connexion" replace />;

  return (
    <>
      <header className="entete">
        <Link to="/" className="marque">NormaPrep Audit</Link>
        <nav>
          <NavLink to="/missions">Missions</NavLink>
          {moi.est_admin && (
            <>
              <NavLink to="/admin/utilisateurs">Utilisateurs</NavLink>
              <NavLink to="/admin/referentiels">Référentiels</NavLink>
              <NavLink to="/admin/journal">Journal</NavLink>
            </>
          )}
        </nav>
        <NavLink to="/compte" className="discret">{moi.nom}</NavLink>
        <button onClick={deconnecter}>Se déconnecter</button>
      </header>
      <main className="page">
        <Routes>
          <Route path="/" element={<Navigate to="/missions" replace />} />
          <Route path="/connexion" element={<Navigate to="/missions" replace />} />
          <Route path="/missions" element={<Missions />} />
          <Route path="/missions/:id" element={<MissionPage />} />
          <Route path="/diagnostics/:id/*" element={<DiagnosticPage />} />
          <Route path="/compte" element={<MonCompte />} />
          {moi.est_admin && (
            <>
              <Route path="/admin/utilisateurs" element={<Utilisateurs />} />
              <Route path="/admin/referentiels" element={<Referentiels />} />
              <Route path="/admin/journal" element={<Journal />} />
            </>
          )}
          <Route path="*" element={<p>Page introuvable.</p>} />
        </Routes>
      </main>
    </>
  );
}
