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
acá se elige, por usuario, el de mayor % de completitud, entre TODOS sus
idiomas, replicando la MISMA lógica que ya usa el frontend real (ver
`chamba-ai/src/app/utils/root-cv-completeness.util.ts::computeRootCvCompleteness()`),
no persistida en la DB. Probado con `cv_json` más largo primero (commit
anterior) y descartado: idiomas con muchas versiones viejas acumuladas
(ver botón "Limpiar entradas duplicadas" en la UI) pueden tener
`cv_json` más largo por datos duplicados sin representar más contenido
real - eligió el CV en francés al 40% de completitud en vez del español
al 100% para una cuenta real. La versión de cada idioma usada es la de
`version_number` más alto (mismo criterio que usa el backend real para
leer, ver `adapters/persistence/repositories/root_cv.py` - NO confía en
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


def _completeness_score(cv_json_raw: Optional[str]) -> float:
    """Replica computeRootCvCompleteness() del frontend real
    (chamba-ai/src/app/utils/root-cv-completeness.util.ts) - header 40
    (fullName 15/email 15/phone 10), experiencia 30 (todo o nada: ≥1
    entrada con jobTitle+company), educación 20 (todo o nada: ≥1 entrada
    con degree+institution), additionalSkills 10 (alguna de las 4
    subsecciones no vacía). No hay score persistido en la DB, así que se
    recalcula acá con la misma fórmula, no con "cv_json más largo" (issue
    #379 - esa heurística fallaba con idiomas con muchas versiones viejas
    acumuladas y datos duplicados sin limpiar)."""
    if not cv_json_raw:
        return 0.0
    try:
        parsed = json.loads(cv_json_raw)
    except (ValueError, TypeError):
        return 0.0
    root = parsed.get("root_cv", parsed) if isinstance(parsed, dict) else {}
    if not isinstance(root, dict):
        return 0.0

    score = 0.0
    header = root.get("header") or {}
    if isinstance(header, dict):
        if header.get("fullName"):
            score += 15
        if header.get("email"):
            score += 15
        if header.get("phone"):
            score += 10

    experience = root.get("professionalExperience") or []
    if isinstance(experience, list) and any(
        isinstance(e, dict) and e.get("jobTitle") and e.get("company") for e in experience
    ):
        score += 30

    education = root.get("education") or []
    if isinstance(education, list) and any(
        isinstance(e, dict) and e.get("degree") and e.get("institution") for e in education
    ):
        score += 20

    skills = root.get("additionalSkillsAndCompetencies") or {}
    if isinstance(skills, dict) and any(
        skills.get(k) for k in ("languages", "technicalProficiency", "professionalDevelopment", "publicationsAndPatents")
    ):
        score += 10

    return score


def list_cvs(limit: int = 20) -> list[dict]:
    """Una fila por usuario: entre TODOS sus `root_curriculum_vitaes` (uno
    por idioma), el de mayor % de completitud real (_completeness_score),
    no el de `cv_json` más largo. No hace falta tocar `users` para esto -
    `root_curriculum_vitaes.user_id` ya alcanza."""
    with psycopg.connect(config.backend_dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rcvv.id, rcv.user_id, rcv.language, rcvv.version_number,
                       rcvv.cv_json, rcvv.created_at
                FROM root_curriculum_vitaes rcv
                JOIN root_curriculum_vitae_versions rcvv
                    ON rcvv.root_cv_id = rcv.id
                   AND rcvv.version_number = (
                       SELECT MAX(v2.version_number)
                       FROM root_curriculum_vitae_versions v2
                       WHERE v2.root_cv_id = rcv.id
                   )
                """
            )
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

    best_per_user: dict[int, dict] = {}
    for row in rows:
        score = _completeness_score(row["cv_json"])
        current = best_per_user.get(row["user_id"])
        is_better = (
            current is None
            or score > current["_score"]
            or (score == current["_score"] and row["created_at"] > current["created_at"])
        )
        if is_better:
            row["_score"] = score
            best_per_user[row["user_id"]] = row

    result = sorted(best_per_user.values(), key=lambda r: r["created_at"], reverse=True)[:limit]
    for r in result:
        r.pop("cv_json", None)
        r.pop("_score", None)
    return result


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
