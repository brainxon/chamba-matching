#!/usr/bin/env bash
# Issue #355 — arma el .env real de la EC2 nueva leyendo las credenciales
# desde SSM Parameter Store (SecureString) y levanta el stack.
#
# Por qué desde Parameter Store y no como argumento/variable de entorno
# pasada a mano: si el password viaja dentro de un comando de
# `ssm send-command`, queda visible en texto plano en el historial de
# `ssm:GetCommandInvocation` / CloudTrail. Acá el valor solo existe en
# memoria de este proceso y en el archivo .env final (permisos 600).
#
# Requiere en el rol de instancia de esta EC2 (${PROJECT_NAME}-ec2-role):
#   ssm:GetParameter sobre arn:aws:ssm:<region>:<account>:parameter/${PROJECT_NAME}/*
# (ver ec2-code-deploy-manual.md paso 4)
#
# Uso (normalmente disparado por ssm send-command, ver ec2-code-deploy-manual.md paso 6):
#   PROJECT_NAME=chamba-matching AWS_REGION=eu-central-1 ./04-fetch-secrets-and-start.sh

set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:?falta PROJECT_NAME}"
AWS_REGION="${AWS_REGION:?falta AWS_REGION}"
STACK_DIR="${STACK_DIR:-$HOME/poc-pgvector-matching}"

if [ ! -d "$STACK_DIR" ]; then
  echo "No encuentro $STACK_DIR — el zip no se descomprimió todavía." >&2
  exit 1
fi

fetch() {
  aws ssm get-parameter --region "$AWS_REGION" --with-decryption \
    --name "/${PROJECT_NAME}/$1" --query 'Parameter.Value' --output text
}

echo "== Armando .env desde SSM Parameter Store =="
umask 077
cat > "$STACK_DIR/.env" <<EOF
JOBS_DB_PASSWORD=$(fetch JOBS_DB_PASSWORD)
BACKEND_DB_HOST=$(fetch BACKEND_DB_HOST)
BACKEND_DB_PORT=5432
BACKEND_DB_USER=$(fetch BACKEND_DB_USER)
BACKEND_DB_PASSWORD=$(fetch BACKEND_DB_PASSWORD)
BACKEND_DB_NAME=$(fetch BACKEND_DB_NAME)
MATCHING_DB_PASSWORD=$(fetch MATCHING_DB_PASSWORD)
MATCHING_DB_NAME=$(fetch BACKEND_DB_NAME)
EOF
chmod 600 "$STACK_DIR/.env"
echo ".env armado en $STACK_DIR/.env (600, no se imprime el contenido)"

echo "== Levantando el stack =="
DEPLOY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$DEPLOY_DIR/02-start-stack.sh" "$STACK_DIR"
