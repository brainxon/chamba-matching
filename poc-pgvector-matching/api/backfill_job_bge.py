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


# Bajados de (32, 2048) - issue #378: esa combinación tiró OOM ("Killed",
# sin traceback) en la EC2 real (3.7GB RAM, sin swap). Una descripción de
# trabajo no necesita 2048 tokens como un CV completo, así que bajar
# max_length también reduce el cómputo, no solo la memoria.
CHUNK_SIZE = 8
JOB_MAX_LENGTH = 512


def backfill() -> None:
    t0 = time.perf_counter()
    jobs = jobs_repo.list_jobs_missing_bge()
    log.info("job_postings sin embedding_bge: %d", len(jobs))
    done = 0
    for chunk_start in range(0, len(jobs), CHUNK_SIZE):
        chunk = jobs[chunk_start:chunk_start + CHUNK_SIZE]
        texts = [f"{j['title']}\n{j['company'] or ''}\n{j['description']}" for j in chunk]
        vecs, elapsed = embeddings_bge.embed_texts(texts, batch_size=CHUNK_SIZE, max_length=JOB_MAX_LENGTH)
        for job, vec in zip(chunk, vecs):
            jobs_repo.set_job_bge_embedding(job["id"], embeddings_bge.to_pgvector_literal(vec))
        done += len(chunk)
        log.info("(%d/%d) backfill BGE listo - lote de %d en %.1fs", done, len(jobs), len(chunk), elapsed)
    log.info("backfill terminado en %.1fs", time.perf_counter() - t0)


if __name__ == "__main__":
    backfill()
