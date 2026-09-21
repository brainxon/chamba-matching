#!/usr/bin/env bash
# Issue #355 — corrida del refresh diario de matching.
#
# Disparado por cron (ver 03-install-daily-cron.sh) o manualmente. Corre
# `matching-batch` como una tarea puntual (`compose run --rm`, no `up -d`)
# — se levanta, carga el modelo BGE-M3, procesa TODOS los CVs reales
# existentes, escribe en matching.match_results (esquema en la DB real),
# y se apaga. No queda nada corriendo (ni pagando CPU) entre corridas.
#
# Uso:
#   ./run-daily-refresh.sh                    # todos los usuarios (cron diario)
#   ./run-daily-refresh.sh <cv_version_id>    # un solo usuario (registro nuevo, on-demand)

set -euo pipefail

STACK_DIR="${STACK_DIR:-$HOME/poc-pgvector-matching}"
LOG_FILE="${LOG_FILE:-$HOME/.logs/matching-batch.log}"

mkdir -p "$(dirname "$LOG_FILE")"
cd "$STACK_DIR"

{
  echo "=== $(date -u +%FT%TZ) — inicio ==="
  if [ -n "${1:-}" ]; then
    docker compose --profile batch run --rm matching-batch python -m api.batch_refresh "$1"
  else
    docker compose --profile batch run --rm matching-batch
  fi
  echo "=== $(date -u +%FT%TZ) — fin ==="
} >> "$LOG_FILE" 2>&1
