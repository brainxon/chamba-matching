"""Backfill de embedding_bge para job_postings que todavía no lo tienen
(issue #378) - necesario para que batch_refresh/knn_match_bge encuentre
matches: seed_jobs_from_recent.py solo calcula el embedding por hashing
(rápido, sin descargar el modelo) para el smoke test primario, nunca BGE.
Sin este backfill, knn_match_bge() (WHERE embedding_bge IS NOT NULL)
siempre devuelve 0 matches y match_results queda vacío aunque el batch
"termine bien".

Mismo texto combinado que usa seed_jobs_from_recent.py para el embedding
por hashing (title+company+description), así los dos embeddings del
mismo job_posting representan el mismo contenido.

Uso:
  python -m api.backfill_job_bge
"""

from __future__ import annotations

import logging
import time

from . import embeddings_bge, jobs_repo

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)


def backfill() -> None:
    t0 = time.perf_counter()
    jobs = jobs_repo.list_jobs_missing_bge()
    log.info("job_postings sin embedding_bge: %d", len(jobs))
    for i, job in enumerate(jobs, start=1):
        text_for_embedding = f"{job['title']}\n{job['company'] or ''}\n{job['description']}"
        vec, _ = embeddings_bge.embed_text(text_for_embedding)
        embedding_literal = embeddings_bge.to_pgvector_literal(vec)
        jobs_repo.set_job_bge_embedding(job["id"], embedding_literal)
        if i % 50 == 0 or i == len(jobs):
            log.info("(%d/%d) backfill BGE listo", i, len(jobs))
    log.info("backfill terminado en %.1fs", time.perf_counter() - t0)


if __name__ == "__main__":
    backfill()
