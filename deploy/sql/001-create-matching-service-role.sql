-- Issue #355 — correr contra la DB REAL de staging (cover_letter_db_stg),
-- en la EC2 que YA EXISTE hoy, DESPUÉS de que la migración de Alembic
-- (chamba-ai-backend-fastapi/migrations/versions/c1b99bc64346_add_matching_schema.py)
-- ya haya corrido y el esquema `matching` con sus dos tablas exista —
-- si el esquema todavía no existe, los GRANT de abajo van a fallar con
-- "schema matching does not exist".
--
-- El DDL de tablas/esquema NO va acá, vive en esa migración (mismo
-- criterio que el resto del schema real: trazabilidad, alembic
-- downgrade, una sola fuente de verdad). Este script solo agrega los
-- permisos sobre ese esquema al rol de escritura.
--
-- El rol `matching_service` YA EXISTE (creado a mano, 2026-09-21, con
-- CREATE USER matching_service WITH PASSWORD 'P4ssw0rd!') — el bloque
-- DO de abajo es un no-op en ese caso (IF NOT EXISTS), se deja por si
-- este script corre primero en otro entorno.
--
-- ⚠️ La password actual (`P4ssw0rd!`) es débil Y está repetida en
-- `app_reader` (mismo valor para los dos roles) — anula parte del
-- sentido de tener roles separados con privilegios distintos. Rotarla
-- (ALTER ROLE matching_service WITH PASSWORD '...') antes de production
-- real; para seguir probando en staging ahora se puede dejar así.
--
-- Ejecutar:
--   docker exec -i chamba-db psql -U chamba_app -d cover_letter_db_stg < 001-create-matching-service-role.sql
-- (ajustar container/usuario/DB si el real de producción difiere del de dev-infra)

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'matching_service') THEN
        CREATE ROLE matching_service WITH LOGIN PASSWORD 'CAMBIAR_ESTA_PASSWORD';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE cover_letter_db_stg TO matching_service;
GRANT USAGE ON SCHEMA matching TO matching_service;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA matching TO matching_service;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA matching TO matching_service;
ALTER DEFAULT PRIVILEGES IN SCHEMA matching
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO matching_service;
ALTER DEFAULT PRIVILEGES IN SCHEMA matching
    GRANT USAGE ON SEQUENCES TO matching_service;

-- Verificación sugerida (correr después, conectado como matching_service):
--   SELECT count(*) FROM matching.match_results;             -- debe funcionar
--   SELECT count(*) FROM public.curriculum_vitae_versions;   -- debe fallar: permission denied
