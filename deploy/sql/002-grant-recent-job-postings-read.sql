-- Issue #355 — correr contra la DB REAL de staging (cover_letter_db_stg),
-- en la EC2 que YA EXISTE hoy (la del backend real).
--
-- El rol de solo lectura (app_reader en staging; poc_pgvector_reader es
-- su equivalente en dev-infra) se creó originalmente con GRANT SELECT
-- únicamente sobre curriculum_vitae_versions (ver
-- ../../poc-pgvector-matching/README.md "Acceso de solo lectura a la DB
-- real"). Este script agrega el mismo permiso, acotado, sobre
-- recent_job_postings — necesario para api/seed_jobs_from_recent.py
-- (smoke test primario: sembrar chamba_jobs_hot con datos reales que ya
-- existen ahí en vez de esperar a que job-fetch scrapee de a una URL).
--
-- recent_job_postings está diseñada aislada a propósito (sin FKs a
-- ninguna otra tabla, ver
-- chamba-ai-backend-fastapi/domain/models/recent_job.py:26) — leerla no
-- expone ninguna relación con datos de usuarios.
--
-- Ejecutar (ajustar rol/DB si el nombre real difiere):
--   docker exec -i chamba-db psql -U chamba_app -d cover_letter_db_stg < 002-grant-recent-job-postings-read.sql
-- o, si no hay acceso por docker exec, cualquier cliente psql conectado
-- como owner/superuser de cover_letter_db_stg.

GRANT SELECT ON public.recent_job_postings TO app_reader;

-- Verificación sugerida (correr después, conectado como app_reader):
--   SELECT count(*) FROM public.recent_job_postings;                     -- debe funcionar
--   INSERT INTO public.recent_job_postings (global_id, title, company, url, posted_at) VALUES ('x','x','x','x', now());  -- debe fallar: permission denied
