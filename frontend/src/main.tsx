import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
// Polices du thème CARTO, embarquées (aucun appel à un service externe).
import "@fontsource/rajdhani/latin-400.css";
import "@fontsource/rajdhani/latin-ext-400.css";
import "@fontsource/rajdhani/latin-500.css";
import "@fontsource/rajdhani/latin-ext-500.css";
import "@fontsource/rajdhani/latin-600.css";
import "@fontsource/rajdhani/latin-ext-600.css";
import "@fontsource/rajdhani/latin-700.css";
import "@fontsource/rajdhani/latin-ext-700.css";
import "@fontsource/inconsolata/latin-400.css";
import "@fontsource/inconsolata/latin-600.css";
import "@fontsource/inconsolata/latin-700.css";
import "@fontsource/syncopate/latin-700.css";
import App from "./App";
import { appliquerTheme, themeMemorise } from "./theme";
import "./styles.css";

// Avant le premier rendu : pas de flash de l'autre thème.
appliquerTheme(themeMemorise());

createRoot(document.getElementById("racine")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);
