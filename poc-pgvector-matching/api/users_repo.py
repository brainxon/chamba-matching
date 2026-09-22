"""Acceso SOLO LECTURA a la DB REAL del backend. En dev-infra: DB `chambai`,
container `chamba-db`, puerto publicado 5434, rol `poc_pgvector_reader`. En
staging/producción: rol `app_reader` (ver ../deploy/ec2-code-deploy-manual.md
y ../deploy/sql/) - GRANT SELECT únicamente sobre curriculum_vitae_versions,
ningún statement de escritura corre nunca contra esta conexión."""

from typing import Optional

import psycopg

from . import config


def list_cvs(limit: int = 20) -> list[dict]:
    """Una fila por usuario (issue #379): `curriculum_vitae_versions` no tiene
    ningún flag de "actual"/"completo" - un mismo user_id puede tener muchas
    filas (una por aplicación/versión, más variantes por `language`). Sin
    deduplicar, el batch calculaba un embedding y un match_results por CADA
    versión/idioma de cada persona, en vez de uno solo representativo. Acá se
    elige, por usuario, la fila con el `cv_text` más largo (proxy de "CV más
    completo" - no existe ningún score de completitud en el schema real), y
    ante empate la más reciente."""
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, version_number, language, preview, text_length, created_at
                FROM (
                    SELECT DISTINCT ON (user_id)
                           id, user_id, version_number, language,
                           left(cv_text, 220) AS preview,
                           length(cv_text) AS text_length,
                           created_at
                    FROM curriculum_vitae_versions
                    ORDER BY user_id, length(cv_text) DESC, created_at DESC
                ) most_complete_per_user
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_cv_text(cv_version_id: int) -> Optional[str]:
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cv_text FROM curriculum_vitae_versions WHERE id = %s",
                (cv_version_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
