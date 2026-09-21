# Deploy — Issue #355 (Ingesta de Hot Jobs + Matching)

Scripts para llevar `../poc-pgvector-matching/` (repo `brainxon/chamba-matching`) a una
**EC2 Ubuntu 26.04 LTS nueva** (la máquina de ingesta/matching — **no** la EC2 que ya
corre el backend real), más el SQL que hay que correr **en la EC2 que ya existe hoy**
para que el backend real pueda leer los resultados del matching.

Ver `deployment-cost-proposal.md` (en el workspace principal,
`.issues/355-pgvector-matching-poc/deployment-cost-proposal.md` — no está en este repo,
que es solo el código de deploy) para el diseño completo: por qué es así, comparativa de
costos, decisiones de producto pendientes. Esto es la implementación de esa propuesta.

## Dos máquinas, dos scripts distintos

| Máquina | Qué corre acá | Script |
|---|---|---|
| **EC2 nueva** (ingesta/matching) | `db` (pgvector) + `job-fetch` quedan encendidos; `matching-batch` corre puntual por cron | `01-`, `02-`, `03-`, `run-daily-refresh.sh` |
| **EC2 actual** (la que ya corre el backend real) | Nada nuevo corriendo — solo se le agrega un esquema (`matching`) con 2 tablas a su Postgres ya existente | migración de Alembic + `sql/001-create-matching-service-role.sql` |

## Orden de ejecución

### 1. En la EC2 actual (la que ya existe)

**1a. Esquema y tablas — vía migración de Alembic, no un script suelto** (mismo criterio que el resto del schema real: trazabilidad, `alembic downgrade` si esto no prospera, una sola fuente de verdad). La migración vive en `chamba-ai-backend-fastapi/migrations/versions/c1b99bc64346_add_matching_schema.py` (a mergear a `develop` vía PR, como cualquier otro cambio de schema):

```bash
cd chamba-ai-backend-fastapi
git checkout develop && git pull origin develop
git checkout -b 355-matching-schema
# agregar migrations/versions/c1b99bc64346_add_matching_schema.py
alembic upgrade head
```

**1b. El rol `matching_service`** — el rol ya existe en staging real (`cover_letter_db_stg`,
creado a mano el 2026-09-21), así que en ese entorno solo falta correr los `GRANT` del
script (el bloque de `CREATE ROLE` es un no-op ahí). En un entorno nuevo, este mismo
script crea el rol Y aplica los `GRANT`, **DESPUÉS de que la migración de Alembic ya
corrió** (un password no debería vivir en una migración versionada en git):

```bash
docker exec -i chamba-db psql -U chamba_app -d cover_letter_db_stg < sql/001-create-matching-service-role.sql
```

⚠️ Si es un entorno nuevo (el rol todavía no existe): editar el script y cambiar la
password placeholder (`CAMBIAR_ESTA_PASSWORD`) por una real antes de correrlo. Guardarla —
hace falta para el `.env` del paso 4. Si el rol ya existe (como en staging hoy, con la
password compartida `P4ssw0rd!` — ver nota en el script sobre rotarla), este paso es
irrelevante.

Verificar que quedó bien aislado (el rol nuevo no debe poder tocar `public`):
```bash
docker exec chamba-db psql -U matching_service -d cover_letter_db_stg -c "SELECT count(*) FROM matching.match_results;"        # debe funcionar
docker exec chamba-db psql -U matching_service -d cover_letter_db_stg -c "SELECT count(*) FROM public.curriculum_vitae_versions;"  # debe fallar: permission denied
```

### 2. En la EC2 nueva

`aws-services-manual.md` decidió acceso **solo por SSM** (sin puerto 22 abierto), así que
no hay `scp`/`ssh` directo. El procedimiento real, paso a paso, vive en
**[`ec2-code-deploy-manual.md`](./ec2-code-deploy-manual.md)**: un comando SSM en la EC2
hace `git clone` de este mismo repo (`brainxon/chamba-matching`, público — sin token) y
SSM Parameter Store (SecureString) provee las credenciales, todo corrido desde CloudShell
igual que el manual anterior.

`01-setup-ec2-ubuntu22.sh` tampoco hace falta correrlo a mano: el `user-data` de
`aws-services-manual.md` (paso 6) ya instala Docker automáticamente al crear la EC2. Ese
script queda solo como referencia, o por si alguna vez se monta este stack en una EC2 por
fuera de este flujo (con SSH habilitado).

### 3. Probar el refresh manualmente antes de confiar en el cron

```bash
~/deploy/run-daily-refresh.sh              # todos los usuarios
~/deploy/run-daily-refresh.sh 4            # un solo cv_version_id (caso "usuario nuevo")
tail -f ~/.logs/matching-batch.log
```

## Disparo on-demand ("usuario nuevo", pendiente de resolver)

El script soporta correr para un solo `cv_version_id` (`run-daily-refresh.sh <id>`), pero
**todavía falta decidir cómo el backend real dispara esto remotamente** cuando alguien se
registra a mitad del día — con Fargate esto es una llamada directa a `RunTask` (ver
`deployment-cost-proposal.md` §2); con una EC2 fija como esta, hace falta un mecanismo propio
(ej. un endpoint HTTP mínimo que reciba el `cv_version_id` y dispare `docker compose run` por
detrás, o un trigger vía SSH). No implementado todavía — queda como próximo paso si se
confirma esta EC2 en vez de Fargate como la opción final.

## Archivos

```
deploy/
├── README.md                          ← este archivo
├── aws-services-manual.md              ← crea EC2 + Lambda + EventBridge desde CloudShell (recomendado)
├── ec2-code-deploy-manual.md           ← sube el código a la EC2 nueva y levanta el stack (sigue a aws-services-manual.md)
├── .env.example                       ← referencia de qué variables completa 04-fetch-secrets-and-start.sh
├── 01-setup-ec2-ubuntu22.sh            ← ya NO hace falta correrlo — el user-data del manual AWS instala Docker solo; queda como referencia
├── 02-start-stack.sh                   ← levanta db + job-fetch (EC2 nueva) — invocado por 04-fetch-secrets-and-start.sh
├── 03-install-daily-cron.sh            ← ALTERNATIVA a Lambda+EventBridge: cron instalado en la propia EC2 (no usar los dos a la vez — usamos Lambda+EventBridge)
├── 04-fetch-secrets-and-start.sh       ← arma el .env desde SSM Parameter Store y levanta el stack (ver ec2-code-deploy-manual.md)
├── run-daily-refresh.sh                ← lo que dispara el cron local O la Lambda (vía SSM), según cuál de las dos uses
└── sql/
    ├── 001-create-matching-service-role.sql  ← correr en la EC2 ACTUAL, DESPUÉS de la migración de Alembic
    └── 002-grant-recent-job-postings-read.sql  ← correr en la EC2 ACTUAL, antes del seed (ver ec2-code-deploy-manual.md paso 8)
```

**Seed inicial de datos (smoke test primario)**: `poc-pgvector-matching/api/seed_jobs_from_recent.py`
(servicio `seed-jobs`, profile `seed` en `docker-compose.yml`) carga `job_postings` con
datos reales que ya existen en `recent_job_postings` — evita depender de `job-fetch`
scrapeando de a una URL para el primer test end-to-end. Ver `ec2-code-deploy-manual.md`
paso 5.

El esquema/tablas (`CREATE SCHEMA matching`, `cv_embeddings_cache`, `match_results`) NO está en esta carpeta —
vive como migración de Alembic en `chamba-ai-backend-fastapi/migrations/versions/c1b99bc64346_add_matching_schema.py`.

**Dos formas de programar el refresh diario — usar una, no ambas**: `03-install-daily-cron.sh` (cron
dentro de la propia EC2, simple pero la instancia queda prendida todo el tiempo) o
`aws-services-manual.md` (Lambda + EventBridge Scheduler prenden/apagan la EC2 solo cuando hace
falta — es la opción que decidimos usar, ver `deployment-cost-proposal.md`).
