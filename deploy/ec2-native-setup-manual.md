# Manual — Instalación nativa en la EC2 (Postgres + Python, sin Docker)

**Reemplaza la parte de Docker de `ec2-code-deploy-manual.md`** para la EC2 de
ingesta/matching: en vez de `db` (container Postgres) + `job-fetch`/`matching-batch`/
`seed-jobs` corriendo en containers, todo corre nativo en la máquina — mismo criterio que
ya usa la EC2 del backend real (Postgres nativo, no containerizado, confirmado
2026-09-22). `docker-compose.yml` sigue existiendo en el repo y sigue sirviendo para
**desarrollo local** (`docker compose up db job-fetch`), pero ya no es lo que se instala
en la EC2 real.

Sigue después del paso 3 de `ec2-code-deploy-manual.md` (código ya clonado vía `git
clone` en `${APP_DIR}`) — reemplaza los pasos 3 (armar `.env` + `docker compose
up`) en adelante.

## 0. Variables

```bash
# Misma convención que ya usa la EC2 del backend real
# (/home/ubuntu/apps/backend/stg/chamba-ai-backend-fastapi):
export APP_DIR="/home/ubuntu/apps/matching/stg/chamba-matching"

export JOBS_DB_NAME="chamba_jobs_hot"
export JOBS_DB_USER="jobs_ingest"        # rol propio de esta DB, no "poc_app" (ese es solo el default de dev-infra local)
export JOBS_DB_PASSWORD="REEMPLAZAR"     # elegir una password real, guardarla
export PGVECTOR_VERSION="18"             # ajustar a la versión de Postgres que se instale (ver paso 1)
```

## 1. Instalar PostgreSQL + pgvector (repo oficial de PGDG, no el de Ubuntu)

El repo de Ubuntu suele traer una versión de Postgres más vieja y no siempre el paquete
de pgvector correspondiente — usar el repo oficial de PostgreSQL asegura que ambos
paquetes (`postgresql-18` y `postgresql-18-pgvector`) existan y coincidan en versión:

```bash
sudo apt-get update
sudo apt-get install -y curl ca-certificates gnupg
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc
sudo sh -c 'echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
  https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
  > /etc/apt/sources.list.d/pgdg.list'
sudo apt-get update

sudo apt-get install -y "postgresql-${PGVECTOR_VERSION}" "postgresql-${PGVECTOR_VERSION}-pgvector"

sudo systemctl enable --now postgresql
sudo systemctl status postgresql --no-pager
```

## 2. Crear el rol y la base de datos

```bash
sudo -u postgres psql <<EOF
CREATE ROLE ${JOBS_DB_USER} WITH LOGIN PASSWORD '${JOBS_DB_PASSWORD}';
CREATE DATABASE ${JOBS_DB_NAME} OWNER ${JOBS_DB_USER};
EOF
```

`CREATE EXTENSION vector` la corre la migración de Alembic del paso 6 (necesita ser dueño
de la DB, que ya lo es).

**Habilitar conexión por password** (por default `pg_hba.conf` puede estar en modo
`peer`/`trust` solo para sockets locales) — confirmar que exista una línea tipo:

```
# /etc/postgresql/18/main/pg_hba.conf
host    chamba_jobs_hot    jobs_ingest    127.0.0.1/32    scram-sha-256
```

Si no está, agregarla y `sudo systemctl reload postgresql`.

## 3. Python — dos venvs separados (no uno solo)

`matching-batch`/`seed-jobs` necesitan `torch`+`FlagEmbedding` (pesado, ~2.3GB con el
modelo); `job-fetch` necesita `trafilatura`/`beautifulsoup4` (liviano, nada que ver). Un
venv por servicio evita que uno le pese al otro y mantiene la misma separación que ya
tenían como containers distintos:

```bash
sudo apt-get install -y python3-venv python3-pip

cd ${APP_DIR}/poc-pgvector-matching
python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
pip install --no-cache-dir -r requirements-api.txt
deactivate

cd ${APP_DIR}/poc-job-posting-fetch
python3 -m venv venv
source venv/bin/activate
pip install --no-cache-dir -r requirements.txt
deactivate
```

## 4. `.env` para `poc-pgvector-matching` (variables de entorno, no Docker)

```bash
cd ${APP_DIR}/poc-pgvector-matching
cat > .env <<EOF
JOBS_DB_HOST=localhost
JOBS_DB_PORT=5432
JOBS_DB_USER=${JOBS_DB_USER}
JOBS_DB_PASSWORD=${JOBS_DB_PASSWORD}
JOBS_DB_NAME=${JOBS_DB_NAME}
EOF
chmod 600 .env
```

Las demás variables (`BACKEND_DB_*`, `MATCHING_DB_*`) siguen viniendo de SSM Parameter
Store — ver `04-fetch-secrets-and-start.sh` (adaptado en el paso 6 de acá abajo para no
depender de `docker compose`).

## 5. Correr la migración de Alembic (crea `job_postings` + `cv_embeddings_cache` + pgvector)

```bash
cd ${APP_DIR}/poc-pgvector-matching
source venv/bin/activate
set -a; source .env; set +a
alembic upgrade head
deactivate
```

Verificar:
```bash
sudo -u postgres psql -d ${JOBS_DB_NAME} -c "\dx"
sudo -u postgres psql -d ${JOBS_DB_NAME} -c "\dt"
```
Debería aparecer la extensión `vector` y las tablas `job_postings`, `cv_embeddings_cache`.

## 6. `job-fetch` como servicio systemd (tiene que quedar siempre corriendo)

```bash
sudo tee /etc/systemd/system/chamba-job-fetch.service > /dev/null <<EOF
[Unit]
Description=chamba-matching job-fetch (issue #229/#355)
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=${APP_DIR}/poc-job-posting-fetch
ExecStart=${APP_DIR}/poc-job-posting-fetch/venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8002
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now chamba-job-fetch
sudo systemctl status chamba-job-fetch --no-pager
```

## 7. `matching-batch` / `seed-jobs` — puntuales, sin `docker compose run`

Estos NO quedan como servicio — corren una vez y terminan (batch diario / siembra
puntual), igual que antes. `run-daily-refresh.sh` y el `command` de `seed-jobs` en
`docker-compose.yml` hoy asumen `docker compose --profile ... run --rm ...` — hay que
adaptarlos para invocar el venv directo:

```bash
cd ${APP_DIR}/poc-pgvector-matching
source venv/bin/activate
set -a; source .env; set -a  # + BACKEND_DB_*/MATCHING_DB_* (ver .env completo del paso 4 de ec2-code-deploy-manual.md)
python -m api.seed_jobs_from_recent      # siembra puntual (embedding_bge queda NULL a propósito, ver siguiente paso)
python -m api.backfill_job_bge           # issue #378 - SIEMPRE después del seed, si no match_results queda vacío
python -m api.batch_refresh              # batch diario (o con un cv_version_id como argumento)
deactivate
```

✅ `run-daily-refresh.sh` ya está reescrito para este flujo nativo (issue #378) — corre
`backfill_job_bge` + `batch_refresh` con el venv directo, sin Docker, y de paso incluye una
limpieza defensiva de disco al inicio (ver esa nota en el propio script). El handler de la
Lambda (`aws-services-manual.md` paso 8) no necesita cambios: sigue disparando el mismo
path (`/home/ubuntu/deploy/run-daily-refresh.sh`, symlink), el script se encarga de todo
internamente.

## 8. Verificación final

```bash
curl -s http://localhost:8002/docs -o /dev/null -w "job-fetch: %{http_code}\n"
sudo -u postgres psql -d ${JOBS_DB_NAME} -c "SELECT count(*) FROM job_postings;"
```

## Qué queda igual del manual anterior

- El acceso a `cover_letter_db_stg` (backend real) sigue siendo el mismo — `BACKEND_DB_*`,
  `MATCHING_DB_*` desde SSM Parameter Store, sin cambios.
- Los roles `app_reader`/`matching_service` en `cover_letter_db_stg` no cambian.
- `match_results` sigue viviendo en `cover_letter_db_stg.matching` (ver issue #379) — lo
  único que se movió es `cv_embeddings_cache`, que ahora vive en `chamba_jobs_hot` (esta
  máquina), junto a `job_postings`.
