#!/usr/bin/env bash
# Issue #355 — levanta el stack de ingesta/matching en la EC2 nueva.
#
# Requiere:
#   - El código ya clonado en esta EC2 (ver ../ec2-code-deploy-manual.md —
#     hoy es `git clone` de brainxon/chamba-matching, no rsync/scp).
#   - Un archivo .env en poc-pgvector-matching/ con las credenciales
#     REALES de producción (ver .env.example en esta misma carpeta) —
#     NUNCA usar en producción las passwords de desarrollo que trae
#     docker-compose.yml por defecto (poc_pass, poc_reader_only_355).
#   - sql/001-create-matching-writer-role.sql ya corrido contra la DB real
#     (ver README.md de esta carpeta) — matching_writer debe existir.

set -euo pipefail

STACK_DIR="${1:-$HOME/poc-pgvector-matching}"

if [ ! -d "$STACK_DIR" ]; then
  echo "No encuentro $STACK_DIR — copiá la carpeta poc-pgvector-matching/ primero." >&2
  exit 1
fi

if [ ! -f "$STACK_DIR/.env" ]; then
  echo "Falta $STACK_DIR/.env — copiá .env.example y completá credenciales reales antes de continuar." >&2
  exit 1
fi

cd "$STACK_DIR"

# Solo lo liviano queda encendido: la DB (chamba_jobs_hot, pgvector) y el
# servicio de scraping. El trabajo pesado (matching-batch, el que carga
# BGE-M3) NO se deja corriendo — se dispara puntual por cron/on-demand
# (ver run-daily-refresh.sh), así no se paga el modelo cargado en
# memoria ocioso entre corridas.
echo "== Levantando db + job-fetch (quedan encendidos) =="
docker compose up -d --build db job-fetch

echo "== Estado =="
docker compose ps

echo
echo "matching-batch NO se levanta acá — corre puntual, ver run-daily-refresh.sh"
echo "y 03-install-daily-cron.sh para instalarlo como cron diario."
