# Manual — Configurar la EC2 nueva: clonar el código y levantar el stack (Issue #355)

**Continúa donde terminó `aws-services-manual.md`.** Esa EC2 ya existe, ya tiene Docker
instalado (vía `user-data` en el momento de crearla) y SSM la ve — pero todavía no tiene
el código adentro. Esto cubre eso: clonar `brainxon/chamba-matching`, armar el `.env`
real, levantar `db`+`job-fetch`, sembrar `job_postings` con datos reales desde
`recent_job_postings` (smoke test primario, sin depender del scraping), y probar el
refresh manual antes de confiar en la Lambda/EventBridge.

Comandos para correr **desde AWS CloudShell**, en orden.

## Por qué esto no es un `scp` simple

El manual anterior decidió acceso **solo por SSM** para la EC2 nueva (sin key pair, sin
puerto 22 abierto) — `scp`/`ssh` directo no funciona contra esta config. El código vive en
su propio repo de GitHub, **`brainxon/chamba-matching`** (público) — un comando SSM en la
EC2 hace `git clone` directo. Nada de S3 como puente, nada de token: al ser público, un
`git clone` de solo lectura no necesita credenciales.

## Por qué las passwords no van en el comando SSM

Si `BACKEND_DB_PASSWORD`/`MATCHING_DB_PASSWORD` viajaran en texto plano dentro de un
`ssm send-command`, quedan visibles en el historial de `ssm:GetCommandInvocation` (y en
CloudTrail, si el account tiene data events activados). Se guardan antes como
**SecureString en SSM Parameter Store**, y un script ya incluido en el repo
(`deploy/04-fetch-secrets-and-start.sh`) las lee y arma el `.env` directamente en la EC2 —
el valor nunca aparece en un comando ni en un log.

---

## 0. Variables

```bash
export AWS_REGION="eu-central-1"
export PROJECT_NAME="chamba-matching"
export GIT_REPO="https://github.com/brainxon/chamba-matching.git"

# El instance-id de la EC2 nueva (la que devolvió el paso 7 de aws-services-manual.md).
# Si no lo tenés a mano, la Lambda ya lo tiene guardado:
export INSTANCE_ID=$(aws lambda get-function-configuration --region "$AWS_REGION" \
  --function-name "${PROJECT_NAME}-daily-refresh" \
  --query 'Environment.Variables.INSTANCE_ID' --output text)

export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Instance: $INSTANCE_ID"
```

## 1. Permiso del rol de la EC2 para leer los parámetros SSM (necesita `iam:PutRolePolicy` → lo corre el admin)

```bash
cat > /tmp/ec2-ssm-read-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": "ssm:GetParameter", "Resource": "arn:aws:ssm:${AWS_REGION}:${ACCOUNT_ID}:parameter/${PROJECT_NAME}/*"}
  ]
}
EOF

aws iam put-role-policy --role-name "${PROJECT_NAME}-ec2-role" \
  --policy-name "${PROJECT_NAME}-ec2-ssm-read" \
  --policy-document file:///tmp/ec2-ssm-read-policy.json
```

Nota: esto amplía el rol `${PROJECT_NAME}-ec2-role` creado en el paso 4 de
`aws-services-manual.md` — no crea un rol nuevo, solo agrega una política inline más. No
hace falta ningún permiso de S3 (el repo es público).

## 2. Guardar las credenciales reales como SecureString

Completar con los valores reales antes de correr. En staging real, el rol de solo
lectura es `app_reader` y la DB se llama `cover_letter_db_stg` — **no** `poc_pgvector_reader`/
`chambai`, que son solo los defaults de dev-infra que trae `docker-compose.yml` (ver
`.env.example`). La password de `matching_writer` es la que se definió al correr
`sql/001-create-matching-writer-role.sql` en la EC2 actual (README.md paso 1b).
`JOBS_DB_PASSWORD` es una password nueva, a elección, para el Postgres local
(`chamba_jobs_hot`) de esta misma EC2 — no existe todavía, la estás inventando acá.

```bash
aws ssm put-parameter --region "$AWS_REGION" --type SecureString --overwrite \
  --name "/${PROJECT_NAME}/JOBS_DB_PASSWORD" --value "REEMPLAZAR"

aws ssm put-parameter --region "$AWS_REGION" --type SecureString --overwrite \
  --name "/${PROJECT_NAME}/BACKEND_DB_HOST" --value "REEMPLAZAR"

aws ssm put-parameter --region "$AWS_REGION" --type SecureString --overwrite \
  --name "/${PROJECT_NAME}/BACKEND_DB_USER" --value "app_reader"

aws ssm put-parameter --region "$AWS_REGION" --type SecureString --overwrite \
  --name "/${PROJECT_NAME}/BACKEND_DB_PASSWORD" --value "REEMPLAZAR"

aws ssm put-parameter --region "$AWS_REGION" --type SecureString --overwrite \
  --name "/${PROJECT_NAME}/BACKEND_DB_NAME" --value "cover_letter_db_stg"

aws ssm put-parameter --region "$AWS_REGION" --type SecureString --overwrite \
  --name "/${PROJECT_NAME}/MATCHING_DB_PASSWORD" --value "REEMPLAZAR"
```

(`MATCHING_DB_NAME` no lleva parámetro propio — `04-fetch-secrets-and-start.sh` reusa
`BACKEND_DB_NAME`, porque el esquema `matching` vive en la misma DB real, nunca en una
distinta.)

⚠️ Estos comandos quedan en el `history` de la shell de CloudShell con la password en
texto plano — es el mismo trade-off que ya vimos con `run-instances` y compañía. Si te
preocupa, corré `history -c` después, o hacé este paso desde tu Mac con AWS CLI
configurado en vez de CloudShell.

## 3. Clonar el código + armar el `.env` + levantar el stack (todo vía SSM)

```bash
cat > /tmp/ssm-deploy-command.json <<EOF
{
  "commands": [
    "rm -rf /home/ubuntu/chamba-matching",
    "sudo -u ubuntu git clone --depth 1 ${GIT_REPO} /home/ubuntu/chamba-matching",
    "ln -sfn /home/ubuntu/chamba-matching/poc-pgvector-matching /home/ubuntu/poc-pgvector-matching",
    "ln -sfn /home/ubuntu/chamba-matching/poc-job-posting-fetch /home/ubuntu/poc-job-posting-fetch",
    "ln -sfn /home/ubuntu/chamba-matching/deploy /home/ubuntu/deploy",
    "chmod +x /home/ubuntu/deploy/*.sh",
    "sudo -u ubuntu env PROJECT_NAME=${PROJECT_NAME} AWS_REGION=${AWS_REGION} bash /home/ubuntu/deploy/04-fetch-secrets-and-start.sh"
  ]
}
EOF

export DEPLOY_COMMAND_ID=$(aws ssm send-command --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "Issue #355 - clone inicial de codigo" \
  --parameters file:///tmp/ssm-deploy-command.json \
  --query 'Command.CommandId' --output text)

echo "Command: $DEPLOY_COMMAND_ID"
```

Los tres symlinks (`~/poc-pgvector-matching`, `~/poc-job-posting-fetch`, `~/deploy`)
existen por dos razones: (1) la Lambda tiene hardcodeado
`/home/ubuntu/deploy/run-daily-refresh.sh` (ver `aws-services-manual.md` paso 8) y sigue
funcionando así sin tocarla; (2) `docker-compose.yml` referencia `job-fetch` con
`context: ../poc-job-posting-fetch` — **probado localmente**: `docker compose` resuelve
esa ruta relativa contra la ruta *lógica* del symlink (`~/poc-pgvector-matching/..` →
`~/`), no contra la física (`~/chamba-matching/`), así que sin el symlink de
`poc-job-posting-fetch` al lado el build fallaría buscando `~/poc-job-posting-fetch`. El
contenido real vive en `~/chamba-matching/` (el repo clonado completo).

`02-start-stack.sh` (llamado al final de `04-fetch-secrets-and-start.sh`) solo levanta
`db` + `job-fetch` — `matching-batch` y `seed-jobs` quedan apagados, se disparan puntuales
(pasos 5 y 6).

## 4. Ver el resultado del deploy

```bash
aws ssm wait command-executed --region "$AWS_REGION" \
  --command-id "$DEPLOY_COMMAND_ID" --instance-id "$INSTANCE_ID" || true

aws ssm get-command-invocation --region "$AWS_REGION" \
  --command-id "$DEPLOY_COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query '[Status,StandardOutputContent,StandardErrorContent]' --output text
```

Buscar en el output: `docker compose ps` debería listar `db` y `job-fetch` como `running`.
Si `Status` no es `Success`, el `StandardErrorContent` va a decir en qué paso falló
(`git clone`, o el `docker compose up` en sí).

## 5. Sembrar `job_postings` con datos reales de `recent_job_postings` (smoke test primario)

Para un primer test end-to-end no hace falta esperar a que `job-fetch` scrapee URLs de a
una: `recent_job_postings` (DB real, feature de "recent jobs" existente, aislada por
diseño — sin FKs, ver `chamba-ai-backend-fastapi/domain/models/recent_job.py:26`) ya
tiene datos reales. `api/seed_jobs_from_recent.py` los lee (solo lectura) y los inserta en
`job_postings` (`chamba_jobs_hot`, esta EC2 nueva) con embedding por hashing — no BGE, así
que no descarga ningún modelo y corre en segundos.

**Antes**: correr el GRANT de `deploy/sql/002-grant-recent-job-postings-read.sql` contra
la DB real — el rol `app_reader` hoy solo tiene `SELECT` sobre `curriculum_vitae_versions`,
no sobre `recent_job_postings` todavía. Mismo criterio que `sql/001-...`: no lo corro yo,
lo corrés vos o el admin, directamente en la EC2 actual (la del backend):

```bash
docker exec -i chamba-db psql -U chamba_app -d cover_letter_db_stg < deploy/sql/002-grant-recent-job-postings-read.sql
```

(ajustar container/usuario/DB si el real de producción difiere del de `dev-infra`)

Con el GRANT ya aplicado, disparar la siembra vía SSM:

```bash
cat > /tmp/ssm-seed-jobs.json <<'EOF'
{"commands": ["cd /home/ubuntu/poc-pgvector-matching && sudo -u ubuntu docker compose --profile seed run --rm seed-jobs"]}
EOF

export SEED_COMMAND_ID=$(aws ssm send-command --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "Issue #355 - seed inicial de job_postings desde recent_job_postings" \
  --parameters file:///tmp/ssm-seed-jobs.json \
  --query 'Command.CommandId' --output text)

aws ssm wait command-executed --region "$AWS_REGION" \
  --command-id "$SEED_COMMAND_ID" --instance-id "$INSTANCE_ID" || true

aws ssm get-command-invocation --region "$AWS_REGION" \
  --command-id "$SEED_COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query '[Status,StandardOutputContent,StandardErrorContent]' --output text
```

Buscar en el output: `listo: N insertados, ...`. Si `Status` no es `Success` y el error es
`permission denied for table recent_job_postings`, el GRANT de arriba no corrió (o corrió
contra el rol/DB equivocado — confirmar `app_reader` / `cover_letter_db_stg`, no los
defaults de dev). Correr de nuevo es seguro — el script es idempotente por `url`, no
duplica filas ya insertadas.

## 6. Probar el refresh manual ANTES de confiar en la Lambda/cron

Esto es lo mismo que va a disparar la Lambda todos los días — probarlo una vez a mano
para no descubrir un error recién en la primera corrida automática de madrugada:

```bash
cat > /tmp/ssm-test-refresh.json <<'EOF'
{"commands": ["sudo -u ubuntu /home/ubuntu/deploy/run-daily-refresh.sh"]}
EOF

export TEST_COMMAND_ID=$(aws ssm send-command --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --comment "Issue #355 - test manual de run-daily-refresh" \
  --parameters file:///tmp/ssm-test-refresh.json \
  --query 'Command.CommandId' --output text)

aws ssm wait command-executed --region "$AWS_REGION" \
  --command-id "$TEST_COMMAND_ID" --instance-id "$INSTANCE_ID" || true

aws ssm get-command-invocation --region "$AWS_REGION" \
  --command-id "$TEST_COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query '[Status,StandardOutputContent,StandardErrorContent]' --output text
```

Esto descarga el modelo BGE-M3 la primera vez (puede tardar varios minutos) — corridas
siguientes son más rápidas porque el modelo queda cacheado en el volumen del container.
El log completo queda en la EC2 en `~/.logs/matching-batch.log` (accesible después vía
`aws ssm start-session --target "$INSTANCE_ID"` si tenés el Session Manager plugin
instalado localmente, o repitiendo el patrón de `send-command` con `cat` sobre ese archivo).

## 7. Confirmar que el resultado llegó a la DB real

Desde la EC2 **actual** (la del backend, no esta nueva), con el rol `matching_writer`:

```bash
docker exec chamba-db psql -U matching_writer -d cover_letter_db_stg \
  -c "SELECT count(*) FROM matching.match_results;"
```

Debería devolver un número mayor a 0 después del paso 6.

---

## Verificación final

```bash
cat > /tmp/ssm-check-stack.json <<'EOF'
{"commands": ["sudo -u ubuntu docker compose -f /home/ubuntu/poc-pgvector-matching/docker-compose.yml ps"]}
EOF

export CHECK_COMMAND_ID=$(aws ssm send-command --region "$AWS_REGION" \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters file:///tmp/ssm-check-stack.json \
  --query 'Command.CommandId' --output text)

aws ssm wait command-executed --region "$AWS_REGION" \
  --command-id "$CHECK_COMMAND_ID" --instance-id "$INSTANCE_ID" || true

aws ssm get-command-invocation --region "$AWS_REGION" \
  --command-id "$CHECK_COMMAND_ID" --instance-id "$INSTANCE_ID" \
  --query 'StandardOutputContent' --output text
```

Esperado: `db` y `job-fetch` en estado `running`/`Up`, `matching-batch` no listado (solo
corre puntual, `docker compose ps` no lo muestra entre corridas).

## Resumen de lo creado en este manual

| Recurso | Nombre |
|---|---|
| Política inline agregada al rol EC2 existente | `${PROJECT_NAME}-ec2-ssm-read` |
| Parámetros SecureString | `/${PROJECT_NAME}/JOBS_DB_PASSWORD`, `/${PROJECT_NAME}/BACKEND_DB_HOST`, `/${PROJECT_NAME}/BACKEND_DB_USER`, `/${PROJECT_NAME}/BACKEND_DB_PASSWORD`, `/${PROJECT_NAME}/BACKEND_DB_NAME`, `/${PROJECT_NAME}/MATCHING_DB_PASSWORD` |
| GRANT agregado al rol de solo lectura (DB real) | `SELECT` sobre `public.recent_job_postings` para `app_reader` |
| Código en la EC2 nueva | `/home/ubuntu/chamba-matching/` (repo clonado) + symlinks `~/poc-pgvector-matching`, `~/poc-job-posting-fetch`, `~/deploy` |
| Datos sembrados | `job_postings` (`chamba_jobs_hot`, EC2 nueva) desde `recent_job_postings` (DB real) |

## Redeploy (si cambia el código)

Repetir el paso 3 — el `rm -rf` + `git clone --depth 1` trae la versión más reciente de
`main` de `brainxon/chamba-matching` y `04-fetch-secrets-and-start.sh` vuelve a correr
`docker compose up -d --build`, así que toma el código nuevo. No hace falta recrear la
política ni los parámetros SSM si no cambiaron. El paso 5 (siembra) se puede repetir
cuando quieras — es idempotente, solo agrega lo que sea nuevo en `recent_job_postings`.

## Pendiente (fuera de alcance de este manual)

- El disparo on-demand para usuario nuevo — sigue confirmado fuera de alcance (ver `README.md`).
- Rotar las passwords guardadas en Parameter Store si alguna vez quedaron expuestas en
  chat o en el `history` de CloudShell (ver nota del paso 2).
- Reemplazar el seed desde `recent_job_postings` por el pipeline real de scraping
  (`job-fetch`) una vez que esto deje de ser un smoke test — `recent_job_postings` es un
  dataset de terceros (Stapply/ats-scrapers) con su propia política de retención/limpieza
  (ver `chamba-ai-backend-fastapi/domain/models/recent_job.py`), no pensado como fuente
  permanente de `job_postings`.
- `pg_hba.conf`/`postgresql.conf` en la EC2 **actual** (backend real) — el Postgres ahí
  solo escucha en `127.0.0.1` hoy; sin ese cambio, `BACKEND_DB_HOST` desde la EC2 nueva
  no va a poder conectar aunque el security group ya esté abierto (paso 3 de
  `aws-services-manual.md`). Confirmado explícitamente como tarea aparte, más adelante.
- Automatizar el redeploy con un trigger (hoy es: volver a correr el paso 3 a mano cada
  vez que cambia el código) — no es prioridad mientras esto siga siendo un PoC/piloto.
