#!/usr/bin/env bash
# Issue #355/#378 — corrida del refresh diario de matching, NATIVO (sin
# Docker - ver ec2-native-setup-manual.md). Reemplaza la versión anterior
# basada en `docker compose run --rm matching-batch`.
#
# Disparado por la Lambda/EventBridge después de prender la EC2 (ver
# aws-services-manual.md paso 8), o manualmente. Procesa TODOS los CVs
# reales existentes (uno por usuario, el más completo - ver
# api/users_repo.py), escribe en matching.match_results (DB real), y
# termina - la propia EC2 se apaga sola después (shutdown -h now, fuera
# de este script).
#
# Limpieza al inicio (issue #378): esta EC2 se apaga/prende sola todos
# los días, y el `user-data` original (que instala Docker, ya sin uso
# real acá) se re-ejecuta en cada boot - vuelve a comerse ~4.5GB de disco
# cada vez si no se saca. Mientras no se corrija eso de raíz (sacar la
# instalación de Docker del user-data de la instancia), esta limpieza
# defensiva evita que el disco (15GB) se llene antes de que el batch
# pueda correr.
#
# Uso:
#   ./run-daily-refresh.sh                    # todos los usuarios (cron/Lambda diario)
#   ./run-daily-refresh.sh <cv_version_id>    # un solo usuario (registro nuevo, on-demand)

set -euo pipefail

APP_DIR="${APP_DIR:-$HOME/apps/matching/stg/chamba-matching}"
STACK_DIR="$APP_DIR/poc-pgvector-matching"
LOG_FILE="${LOG_FILE:-$HOME/.logs/matching-batch.log}"

mkdir -p "$(dirname "$LOG_FILE")"
cd "$STACK_DIR"

{
  echo "=== $(date -u +%FT%TZ) — inicio ==="

  echo "--- limpieza de disco (issue #378) ---"
  if command -v docker >/dev/null 2>&1; then
    echo "docker reapareció (user-data se re-ejecutó en el boot) - purgando"
    sudo apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || true
    sudo rm -rf /var/lib/docker /var/lib/containerd
  fi
  sudo apt-get autoremove -y || true
  sudo apt-get clean || true
  sudo journalctl --vacuum-time=3d || true
  df -h / || true

  source venv/bin/activate
  set -a; source .env; set +a

  echo "--- backfill embedding_bge de job_postings nuevos (issue #378) ---"
  python -m api.backfill_job_bge

  echo "--- matching ---"
  if [ -n "${1:-}" ]; then
    python -m api.batch_refresh "$1"
  else
    python -m api.batch_refresh
  fi
  deactivate

  echo "=== $(date -u +%FT%TZ) — fin ==="
} >> "$LOG_FILE" 2>&1
