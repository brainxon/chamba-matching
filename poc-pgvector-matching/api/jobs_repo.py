"""Acceso a la DB NUEVA (chamba_jobs_hot, container `db` de este PoC) -
separada de la DB real del backend (ver users_repo.py). Esto es lo que
materializa la decisión de arquitectura del issue #355 (tarea 5)."""

from typing import Optional

import psycopg

from . import config

TABLE = "job_postings"


def _row_to_dict(cur, row) -> dict:
    cols = [d.name for d in cur.description]
    return dict(zip(cols, row))


def insert_job(source: str, title: str, company: Optional[str], url: Optional[str],
                description: str, embedding_literal: str) -> dict:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {TABLE} (source, title, company, url, description, embedding)
                VALUES (%s, %s, %s, %s, %s, %s::vector)
                RETURNING id, source, title, company, url, description, created_at
                """,
                (source, title, company, url, description, embedding_literal),
            )
            row = _row_to_dict(cur, cur.fetchone())
        conn.commit()
    return row


def url_exists(url: str) -> bool:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT 1 FROM {TABLE} WHERE url = %s LIMIT 1", (url,))
            return cur.fetchone() is not None


def list_jobs(limit: int = 50) -> list[dict]:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, source, title, company, url, description, created_at "
                f"FROM {TABLE} ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
            return [_row_to_dict(cur, r) for r in cur.fetchall()]


def knn_match(embedding_literal: str, top_k: int = 5) -> list[dict]:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, source, title, company, url, description,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM {TABLE}
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (embedding_literal, embedding_literal, top_k),
            )
            return [_row_to_dict(cur, r) for r in cur.fetchall()]


def list_jobs_missing_bge() -> list[dict]:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, description FROM {TABLE} WHERE embedding_bge IS NULL"
            )
            return [_row_to_dict(cur, r) for r in cur.fetchall()]


def set_job_bge_embedding(job_id: int, embedding_literal: str) -> None:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE {TABLE} SET embedding_bge = %s::vector WHERE id = %s",
                (embedding_literal, job_id),
            )
        conn.commit()


def knn_match_bge(embedding_literal: str, top_k: int = 5) -> list[dict]:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, source, title, company, url, description,
                       1 - (embedding_bge <=> %s::vector) AS similarity
                FROM {TABLE}
                WHERE embedding_bge IS NOT NULL
                ORDER BY embedding_bge <=> %s::vector
                LIMIT %s
                """,
                (embedding_literal, embedding_literal, top_k),
            )
            return [_row_to_dict(cur, r) for r in cur.fetchall()]
