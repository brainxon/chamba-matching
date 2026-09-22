#!/usr/bin/env bash
# Issue #355/#379 — completa el .env real de la EC2 nueva agregando
# BACKEND_DB_*/MATCHING_DB_* leídos desde SSM Parameter Store (SecureString).
#
# Nativo, no Docker (ver ec2-native-setup-manual.md): las JOBS_DB_* ya
# las escribió el paso 4 de ese manual directo en el .env — este script
# solo AGREGA (append) las variables del backend real, nunca sobreescribe
# el archivo entero (si lo hiciera, borraría las JOBS_DB_* ya puestas).
#
# Por qué desde Parameter Store y no como argumento/variable de entorno
# pasada a mano: si el password viaja dentro de un comando de
# `ssm send-command`, queda visible en texto plano en el historial de
# `ssm:GetCommandInvocation` / CloudTrail. Acá el valor solo existe en
# memoria de este proceso y en el archivo .env final (permisos 600).
#
# Requiere en el rol de instancia de esta EC2 (${PROJECT_NAME}-ec2-role):
#   ssm:GetParameter sobre arn:aws:ssm:<region>:<account>:parameter/${PROJECT_NAME}/*
# (ver ec2-code-deploy-manual.md paso 1)
#
# Uso:
#   PROJECT_NAME=chamba-matching AWS_REGION=eu-central-1 ./04-fetch-secrets-and-start.sh

set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:?falta PROJECT_NAME}"
AWS_REGION="${AWS_REGION:?falta AWS_REGION}"
STACK_DIR="${STACK_DIR:-$HOME/poc-pgvector-matching}"
ENV_FILE="$STACK_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "No encuentro $ENV_FILE — corré primero el paso 4 de ec2-native-setup-manual.md (JOBS_DB_*)." >&2
  exit 1
fi

fetch() {
  aws ssm get-parameter --region "$AWS_REGION" --with-decryption \
    --name "/${PROJECT_NAME}/$1" --query 'Parameter.Value' --output text
}

echo "== Agregando BACKEND_DB_*/MATCHING_DB_* al .env existente desde SSM Parameter Store =="
umask 077
BACKEND_HOST_VALUE="$(fetch BACKEND_DB_HOST)"
cat >> "$ENV_FILE" <<EOF
BACKEND_DB_HOST=${BACKEND_HOST_VALUE}
BACKEND_DB_PORT=5432
BACKEND_DB_USER=$(fetch BACKEND_DB_USER)
BACKEND_DB_PASSWORD=$(fetch BACKEND_DB_PASSWORD)
BACKEND_DB_NAME=$(fetch BACKEND_DB_NAME)
MATCHING_DB_HOST=${BACKEND_HOST_VALUE}
MATCHING_DB_PORT=5432
MATCHING_DB_PASSWORD=$(fetch MATCHING_DB_PASSWORD)
MATCHING_DB_NAME=$(fetch BACKEND_DB_NAME)
EOF
chmod 600 "$ENV_FILE"
echo "$ENV_FILE actualizado (600, no se imprime el contenido)"
