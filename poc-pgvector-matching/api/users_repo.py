"""Acceso SOLO LECTURA a la DB REAL del backend. En dev-infra: DB `chambai`,
container `chamba-db`, puerto publicado 5434, rol `poc_pgvector_reader`. En
staging/producción: rol `app_reader` (ver ../deploy/ec2-code-deploy-manual.md
y ../deploy/sql/004-grant-root-cv-versions-read.sql) - GRANT SELECT por
COLUMNA (nunca la tabla completa) sobre root_curriculum_vitaes/
root_curriculum_vitae_versions, nunca sobre datos personales. Ningún
statement de escritura corre nunca contra esta conexión.

Fuente del CV (issue #379, corregido tras verificar con una cuenta real -
ver `.issues/355-pgvector-matching-poc/execution-report.md`): la feature
real es "CV Maestro", respaldada por `root_curriculum_vitaes` (una fila
POR IDIOMA por usuario) + `root_curriculum_vitae_versions` (versionado
dentro de cada idioma) - NO `user_cvs`/`user_cv_versions` (esa es una
feature vieja/sin uso real, confirmado: una cuenta real con "CV Maestro"
completo en la UI tenía CERO filas ahí) NI `curriculum_vitae_versions`
(esa son outputs *tailored* por aplicación, sin flag de "actual").

Un usuario puede tener varios `root_curriculum_vitaes` (uno por idioma) -
acá se elige, por usuario, el de mayor contenido (`cv_json` más largo,
entre TODOS sus idiomas) como proxy de "CV más completo" (no existe
ningún % de completitud persistido en la DB - se calcula en el frontend,
ver `chamba-ai/src/app/utils/root-cv-completeness.util.ts`, nunca se
guarda). La versión de cada idioma usada es la de `version_number` más
alto (mismo criterio que usa el backend real para leer, ver
`adapters/persistence/repositories/root_cv.py` - NO confía en
`latest_version_id` para leer, a pesar de que la columna existe)."""

from __future__ import annotations

import json
from typing import Optional

import psycopg

from . import config


def _flatten_json_text(value) -> list[str]:
    """Extrae recursivamente los valores string de un cv_json, sin asumir
    su estructura exacta (evita acoplarse al formato interno del CV del
    backend, que puede cambiar) - issue #379."""
    out: list[str] = []
    if isinstance(value, str):
        if value.strip():
            out.append(value.strip())
    elif isinstance(value, dict):
        for v in value.values():
            out.extend(_flatten_json_text(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_flatten_json_text(v))
    return out


def list_cvs(limit: int = 20) -> list[dict]:
    """Una fila por usuario: entre TODOS sus `root_curriculum_vitaes` (uno
    por idioma), la versión más reciente (`version_number` más alto) del
    idioma con más contenido. No hace falta tocar `users` para esto -
    `root_curriculum_vitaes.user_id` ya alcanza."""
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, language, version_number, text_length, created_at
                FROM (
                    SELECT DISTINCT ON (rcv.user_id)
                           rcvv.id, rcv.user_id, rcv.language, rcvv.version_number,
                           length(rcvv.cv_json) AS text_length, rcvv.created_at
                    FROM root_curriculum_vitaes rcv
                    JOIN root_curriculum_vitae_versions rcvv
                        ON rcvv.root_cv_id = rcv.id
                       AND rcvv.version_number = (
                           SELECT MAX(v2.version_number)
                           FROM root_curriculum_vitae_versions v2
                           WHERE v2.root_cv_id = rcv.id
                       )
                    ORDER BY rcv.user_id, length(rcvv.cv_json) DESC, rcvv.created_at DESC
                ) most_complete_per_user
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_cv_text(cv_version_id: int) -> Optional[str]:
    """cv_version_id acá es root_curriculum_vitae_versions.id (ver
    list_cvs). cv_json tiene la forma {"root_cv": {...}} - se aplana todo
    el árbol igual, sin asumir esa envoltura específica, por si cambia."""
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cv_json FROM root_curriculum_vitae_versions WHERE id = %s",
                (cv_version_id,),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            try:
                parsed = json.loads(row[0])
            except (ValueError, TypeError):
                return row[0]
            pieces = _flatten_json_text(parsed)
            return "\n".join(pieces) if pieces else None
