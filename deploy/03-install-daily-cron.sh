#!/usr/bin/env bash
# Issue #355 — instala el cron del refresh diario en esta EC2.
# Mismo patrón que services/recent_jobs/README.md (chamba-ai-backend-fastapi)
# ya usa para su propio cron de ingesta — cron de sistema, no un scheduler
# en proceso, para no sumar una dependencia de runtime nueva.
#
# Uso: ./03-install-daily-cron.sh [HH:MM en UTC, default 02:00]

set -euo pipefail

TIME="${1:-02:00}"
HOUR="${TIME%%:*}"
MINUTE="${TIME##*:}"

SCRIPT_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run-daily-refresh.sh"
chmod +x "$SCRIPT_PATH"

CRON_LINE="$MINUTE $HOUR * * * $SCRIPT_PATH"

( crontab -l 2>/dev/null | grep -vF "$SCRIPT_PATH" ; echo "$CRON_LINE" ) | crontab -

echo "Instalado: $CRON_LINE"
echo "Verificar con: crontab -l"
