"""Refresh diario de matching (issue #355, deployment-cost-proposal.md §4).

Pensado para correr 1 vez al día vía cron (ver ../deploy/run-daily-refresh.sh),
NO como parte de la API que sirve requests. Recalcula el matching de TODOS
los usuarios reales contra los hot jobs actuales de chamba_jobs_hot, uno por
persona (el CV más completo de cada quien - ver users_repo.list_cvs, issue
#379), reusando el mismo modelo BGE-M3 ya cargado para todos - por eso
conviene que esto sea un batch y no un proceso por usuario.

El caso "usuario nuevo" (matching inmediato, on-demand) llama a este mismo
módulo pero acotado a un solo cv_version_id - ver refresh_one() / __main__.
"""

from __future__ import annotations

import logging
import sys
import time

from . import embeddings_bge, jobs_repo, matching_repo, users_repo

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MODEL = "bge-m3"
TOP_K = 10


def refresh_one(cv_version_id: int, cv_text: str) -> None:
    cached = matching_repo.get_cached_embedding(cv_version_id, MODEL)
    if cached is not None:
        embedding_literal = cached
    else:
        vec, _ = embeddings_bge.embed_text(cv_text)
        embedding_literal = embeddings_bge.to_pgvector_literal(vec)
        matching_repo.cache_embedding(cv_version_id, MODEL, embedding_literal)

    matches = jobs_repo.knn_match_bge(embedding_literal, top_k=TOP_K)
    matching_repo.replace_match_results(cv_version_id, MODEL, matches)


def refresh_all() -> None:
    """Cron diario: todos los usuarios existentes."""
    t0 = time.perf_counter()
    cvs = users_repo.list_cvs(limit=1_000_000)
    log.info("refrescando matching para %d usuarios reales (1 CV más completo c/u)", len(cvs))
    for i, cv in enumerate(cvs, start=1):
        cv_text = users_repo.get_cv_text(cv["id"])
        if not cv_text:
            continue
        refresh_one(cv["id"], cv_text)
        log.info("(%d/%d) cv_version_id=%s listo", i, len(cvs), cv["id"])
    log.info("refresh diario terminado en %.1fs", time.perf_counter() - t0)


def refresh_single(cv_version_id: int) -> None:
    """Usuario nuevo: on-demand, un solo CV. Disparado por el backend real al registrarse."""
    t0 = time.perf_counter()
    cv_text = users_repo.get_cv_text(cv_version_id)
    if not cv_text:
        log.error("cv_version_id=%s no encontrado en la DB real", cv_version_id)
        sys.exit(1)
    refresh_one(cv_version_id, cv_text)
    log.info("cv_version_id=%s listo en %.1fs", cv_version_id, time.perf_counter() - t0)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        refresh_single(int(sys.argv[1]))
    else:
        refresh_all()
