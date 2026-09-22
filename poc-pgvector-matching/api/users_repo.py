"""Acceso SOLO LECTURA a la DB REAL del backend. En dev-infra: DB `chambai`,
container `chamba-db`, puerto publicado 5434, rol `poc_pgvector_reader`. En
staging/producción: rol `app_reader` (ver ../deploy/ec2-code-deploy-manual.md
y ../deploy/sql/003-grant-user-cv-versions-read.sql) - GRANT SELECT por
COLUMNA (nunca la tabla completa) sobre users/user_cvs/user_cv_versions,
nunca sobre datos personales (nombre, email, etc.). Ningún statement de
escritura corre nunca contra esta conexión.

Fuente del CV (issue #379): el CV BASE vigente de cada usuario, vía el
puntero explícito que mantiene la app real -
`users.current_user_cv_id -> user_cvs.latest_version_id -> user_cv_versions.id`
- NO `curriculum_vitae_versions` (esa tabla guarda outputs *tailored* por
aplicación, sin ningún flag de "actual"; un usuario puede tener muchas
filas ahí y no hay forma de saber cuál usar sin adivinar)."""

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
    """Una fila por usuario, automático: el join por `current_user_cv_id`/
    `latest_version_id` solo puede devolver un user_cv_version por
    persona (son punteros a un solo registro), a diferencia de la vieja
    fuente (curriculum_vitae_versions) que necesitaba deduplicar a mano."""
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ucv2.id, u.id AS user_id, ucv2.version_number, ucv2.language,
                       length(ucv2.cv_json) AS text_length, ucv2.created_at
                FROM users u
                JOIN user_cvs ucv ON u.current_user_cv_id = ucv.id
                JOIN user_cv_versions ucv2 ON ucv.latest_version_id = ucv2.id
                ORDER BY ucv2.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


def get_cv_text(cv_version_id: int) -> Optional[str]:
    """cv_version_id acá es user_cv_versions.id (ver list_cvs, ya NO
    curriculum_vitae_versions.id). Devuelve el contenido aplanado a texto
    plano para el embedding - cv_json es JSON serializado, no texto
    directo."""
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cv_json FROM user_cv_versions WHERE id = %s",
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
