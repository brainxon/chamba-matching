"""Acceso SOLO LECTURA a `recent_job_postings` en la DB REAL del backend
(mismo rol de solo lectura que users_repo.py) — feature existente,
aislada por diseño (sin FKs a ninguna otra tabla, ver
chamba-ai-backend-fastapi/domain/models/recent_job.py). Ningún statement
de escritura corre nunca contra esta conexión.

Requiere que el rol de solo lectura tenga GRANT SELECT sobre esta tabla
además de curriculum_vitae_versions — ver
../deploy/sql/002-grant-recent-job-postings-read.sql (no viene por
default, el rol original solo cubría CVs)."""

import psycopg

from . import config


def list_recent_jobs(limit: int = 500) -> list[dict]:
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, global_id, source, title, company, url, description
                FROM recent_job_postings
                WHERE description IS NOT NULL AND length(trim(description)) > 0
                ORDER BY posted_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
