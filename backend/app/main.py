"""Application FastAPI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import auth, contenu, journal, utilisateurs
from app.securite import verifier_configuration


@asynccontextmanager
async def cycle_de_vie(app: FastAPI):
    verifier_configuration()
    yield


app = FastAPI(
    title="NormaPrep Audit",
    version="0.1.0",
    description="Plateforme d'audit : diagnostic de maturité, audits et rapports.",
    lifespan=cycle_de_vie,
)

app.include_router(auth.router)
app.include_router(utilisateurs.router)
app.include_router(contenu.router)
app.include_router(journal.router)


@app.get("/api/sante", tags=["Exploitation"])
def sante() -> dict[str, str]:
    return {"statut": "ok"}
