-- Issue #355 — correr contra la DB REAL del backend (chambai), en la EC2
-- que YA EXISTE hoy, DESPUÉS de que la migración de Alembic
-- (chamba-ai-backend-fastapi/migrations/versions/c1b99bc64346_add_matching_schema.py)
-- ya haya corrido y el esquema `matching` con sus dos tablas exista.
--
-- Solo crea el rol de escritura — el DDL de tablas/esquema NO va acá,
-- vive en esa migración (mismo criterio que el resto del schema real:
-- trazabilidad, alembic downgrade, una sola fuente de verdad).
--
-- Creación de credenciales deliberadamente FUERA de la migración de
-- Alembic — un password (aunque sea un placeholder) no debería quedar
-- en un archivo versionado en git.
--
-- Ejecutar:
--   docker exec -i chamba-db psql -U chamba_app -d chambai < 001-create-matching-writer-role.sql
-- (ajustar container/usuario/DB si el real de producción difiere del de dev-infra)
--
-- ⚠️ CAMBIAR la password antes de correr en cualquier entorno real.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'matching_writer') THEN
        CREATE ROLE matching_writer WITH LOGIN PASSWORD 'CAMBIAR_ESTA_PASSWORD';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE chambai TO matching_writer;
GRANT USAGE ON SCHEMA matching TO matching_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA matching TO matching_writer;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA matching TO matching_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA matching
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO matching_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA matching
    GRANT USAGE ON SEQUENCES TO matching_writer;

-- Verificación sugerida (correr después, conectado como matching_writer):
--   SELECT count(*) FROM matching.match_results;             -- debe funcionar
--   SELECT count(*) FROM public.curriculum_vitae_versions;   -- debe fallar: permission denied
