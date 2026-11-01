"""Application FastAPI : l'API sous /api, l'interface web compilée ailleurs."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import auth, contenu, diagnostics, journal, missions, utilisateurs
from app.config import reglages
from app.securite import verifier_configuration


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    verifier_configuration()
    yield


app = FastAPI(
    title="NormaPrep Audit",
    version="0.2.0",
    description="Plateforme d'audit : diagnostic de maturité, audits et rapports.",
    lifespan=cycle_de_vie,
)

for module in (auth, utilisateurs, missions, diagnostics, contenu, journal):
    app.include_router(module.router)
app.include_router(diagnostics.public)


@app.get("/api/sante", tags=["Exploitation"])
def sante() -> dict[str, str]:
    return {"statut": "ok"}


@app.get("/api/{chemin:path}", include_in_schema=False)
def api_inconnue(chemin: str) -> None:
    raise HTTPException(404, "Route d'API inconnue.")


# ---- interface web (application monopage) ------------------------------------

_interface: Path = reglages().dossier_interface
if (_interface / "index.html").is_file():
    app.mount("/assets", StaticFiles(directory=_interface / "assets"), name="assets")

    @app.get("/{chemin:path}", include_in_schema=False)
    def interface(chemin: str) -> FileResponse:
        """Fichiers de l'interface ; toute autre adresse renvoie index.html,
        que l'application monopage route elle-même."""
        fichier = (_interface / chemin).resolve()
        if chemin and fichier.is_file() and fichier.is_relative_to(_interface.resolve()):
            return FileResponse(fichier)
        return FileResponse(_interface / "index.html", headers={"Cache-Control": "no-cache"})
