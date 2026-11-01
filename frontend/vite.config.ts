import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En développement, l'API tourne à part (uvicorn ou Docker) : /api lui est relayé.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: "dist", sourcemap: false },
});
