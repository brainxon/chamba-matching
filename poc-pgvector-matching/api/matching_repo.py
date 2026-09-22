"""Acceso al cache de embeddings de CV y a los resultados de matching
(issue #355/#379) — en DOS bases de datos distintas a propósito:

- `cv_embeddings_cache` vive en `chamba_jobs_hot` (esta misma máquina, sin
  extensión pgvector real hace falta acá porque no se busca por
  similitud, solo por PK exacta). Solo la usa este mismo proceso de
  batch — el backend real nunca la toca, así que no hace falta que esté
  disponible cuando esta máquina está apagada.
- `match_results` vive en la MISMA base de datos real del backend
  (cover_letter_db_stg, esquema `matching`), NO en chamba_jobs_hot, para
  que el backend real la pueda seguir sirviendo sin importar si esta
  máquina de matching está prendida o no. Rol dedicado
  (`matching_service`) con permisos SOLO sobre el esquema `matching` -
  nunca sobre `public`, donde viven los datos reales de usuarios. Ver
  ../deploy/sql/001-create-matching-service-role.sql.
"""

from typing import Optional

import psycopg

from . import config


def get_cached_embedding(cv_version_id: int, model: str) -> Optional[str]:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT embedding FROM cv_embeddings_cache "
                "WHERE cv_version_id = %s AND model = %s",
                (cv_version_id, model),
            )
            row = cur.fetchone()
            return row[0] if row else None


def cache_embedding(cv_version_id: int, model: str, embedding_literal: str) -> None:
    with psycopg.connect(config.jobs_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cv_embeddings_cache (cv_version_id, model, embedding)
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
