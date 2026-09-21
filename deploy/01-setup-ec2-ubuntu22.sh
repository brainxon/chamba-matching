#!/usr/bin/env bash
# Issue #355 — bootstrap de una EC2 Ubuntu 22.04 LTS nueva (la de
# ingesta/matching, NO la que ya corre el backend real).
#
# Instala Docker Engine + el plugin de Compose (repo oficial de Docker).
# Correr UNA VEZ, con un usuario que tenga sudo.
#
# Uso:
#   scp -r deploy ubuntu@<host-ec2>:~/
#   ssh ubuntu@<host-ec2> 'bash ~/deploy/01-setup-ec2-ubuntu22.sh'

set -euo pipefail

echo "== Verificando Ubuntu 22.04 =="
if ! grep -q '22.04' /etc/os-release 2>/dev/null; then
  echo "ADVERTENCIA: esto se probó pensado para Ubuntu 22.04 LTS — /etc/os-release no lo confirma. Continuando de todas formas." >&2
fi

echo "== Instalando dependencias =="
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

echo "== Agregando el repo oficial de Docker =="
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "== Instalando Docker Engine + Compose plugin =="
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "== Permitiendo correr docker sin sudo =="
sudo usermod -aG docker "$USER"

echo
echo "Listo. Cerrá sesión y volvé a entrar (o corré 'newgrp docker') para que el grupo tome efecto."
docker --version
docker compose version
