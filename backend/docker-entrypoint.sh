#!/bin/sh
set -e
cd /app
# Clés : générées au premier démarrage si .env ne les fournit pas.
npa preparer-cles
npa verifier-configuration
npa verifier-base
alembic upgrade head
exec "$@"
