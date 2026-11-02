import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import Menu from "./composants/Menu";
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
  const { moi, pret } = useSession();
  const lieu = useLocation();
  if (!pret) return null;
  if (!moi) return lieu.pathname === "/connexion" ? <Connexion /> : <Navigate to="/connexion" replace />;

  return (
    <div className="coquille">
      <Menu />
      <div className="contenu">
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
      </div>
    </div>
  );
}
