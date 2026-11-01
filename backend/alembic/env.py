"""Environnement Alembic : la base est celle des réglages de l'application."""

from logging.config import fileConfig

from alembic import context
from app import models  # noqa: F401  (déclare les tables)
from app.db import Base, moteur

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

cible = Base.metadata


def executer_hors_ligne() -> None:
    context.configure(url=str(moteur().url), target_metadata=cible, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def executer_en_ligne() -> None:
    with moteur().connect() as connexion:
        context.configure(connection=connexion, target_metadata=cible)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    executer_hors_ligne()
else:
    executer_en_ligne()
