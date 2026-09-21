-- PoC issue #355 — aislamiento de arquitectura:
-- "los hot jobs scrapeados van en una base de datos NUEVA y separada de la
--  de usuarios (seguridad: si la DB pública se compromete, cortamos el
--  acceso sin exponer datos de usuarios)"
--
-- Este script corre una sola vez, al crear el volumen de datos del
-- contenedor `db` (docker-entrypoint-initdb.d), y crea DOS bases de datos
-- separadas dentro de la misma instancia de Postgres para simular esa
-- separación a nivel de esquema/conexión. En producción la recomendación
-- (ver report.md) es ir un paso más allá: instancias/redes separadas.

CREATE DATABASE chamba_users;
CREATE DATABASE chamba_jobs_hot;

\c chamba_users
CREATE EXTENSION IF NOT EXISTS vector;

-- Embeddings de CVs de candidatos (datos de usuarios).
CREATE TABLE cv_embeddings (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT NOT NULL,
    source_ref  TEXT NOT NULL,
    embedding   vector(1536) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

\c chamba_jobs_hot
CREATE EXTENSION IF NOT EXISTS vector;

-- Embeddings de job postings scrapeados ("hot jobs"), en su propia DB.
CREATE TABLE job_embeddings (
    id          BIGSERIAL PRIMARY KEY,
    job_ref     TEXT NOT NULL,
    embedding   vector(1536) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
