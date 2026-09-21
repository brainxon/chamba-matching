"""Acceso al esquema `matching` (issue #355) - vive en la MISMA base de
datos real del backend (chambai), no en chamba_jobs_hot, para que
cv_embeddings_cache/match_results sigan disponibles para el backend real
sin importar si la máquina que corre este batch está prendida o no.

Usa un rol dedicado (`matching_service`) con permisos SOLO sobre el
esquema `matching` - nunca sobre `public`, donde viven los datos reales
de usuarios. Ver ../deploy/sql/001-create-matching-service-role.sql.
"""

from typing import Optional

import psycopg

from . import config


def get_cached_embedding(cv_version_id: int, model: str) -> Optional[str]:
    with psycopg.connect(config.matching_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT embedding FROM matching.cv_embeddings_cache "
                "WHERE cv_version_id = %s AND model = %s",
                (cv_version_id, model),
            )
            row = cur.fetchone()
            return row[0] if row else None


def cache_embedding(cv_version_id: int, model: str, embedding_literal: str) -> None:
    with psycopg.connect(config.matching_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO matching.cv_embeddings_cache (cv_version_id, model, embedding)
                VALUES (%s, %s, %s)
                ON CONFLICT (cv_version_id, model)
                DO UPDATE SET embedding = EXCLUDED.embedding, computed_at = now()
                """,
                (cv_version_id, model, embedding_literal),
            )
        conn.commit()


def replace_match_results(cv_version_id: int, model: str, matches: list[dict]) -> None:
    """Sobreescribe el ranking de un CV (borra lo anterior de ese modelo, inserta lo nuevo)."""
    with psycopg.connect(config.matching_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM matching.match_results WHERE cv_version_id = %s AND model = %s",
                (cv_version_id, model),
            )
            for m in matches:
                cur.execute(
                    """
                    INSERT INTO matching.match_results (cv_version_id, job_id, similarity, model)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (cv_version_id, m["id"], m["similarity"], model),
                )
        conn.commit()
