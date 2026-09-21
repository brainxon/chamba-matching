"""Semilla inicial de job_postings (chamba_jobs_hot) desde datos reales que
YA existen en recent_job_postings (DB real del backend, solo lectura) -
issue #355.

Pensado para el primer smoke test end-to-end del stack ya desplegado: en
vez de esperar a que job-fetch scrapee URLs una por una, usa datos que ya
están cargados por la feature de "recent jobs" existente (aislada por
diseño, sin FKs - ver
chamba-ai-backend-fastapi/domain/models/recent_job.py:26).

Usa el embedding por hashing (embeddings.py), no BGE-M3 - alcanza para
este smoke test primario y no depende de descargar el modelo (~2.3GB) en
la primera corrida. El backfill de embedding_bge, si hace falta después,
sigue el mismo patrón que ya usa /api/jobs/embed-bge (list_jobs_missing_bge
+ set_job_bge_embedding en jobs_repo.py).

Idempotente por `url`: una fila cuyo url ya existe en job_postings se
saltea (no hay constraint UNIQUE en la tabla - el chequeo es a nivel
aplicación, ver jobs_repo.url_exists), así que correr esto varias veces
no duplica filas.

Uso:
  docker compose --profile seed run --rm seed-jobs
  docker compose --profile seed run --rm seed-jobs python -m api.seed_jobs_from_recent 200
"""

from __future__ import annotations

import logging
import sys

from . import embeddings, jobs_repo, recent_jobs_repo

logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

EMBED_DIM = 384
SOURCE_TAG = "seed:recent_job_postings"


def seed(limit: int = 500) -> None:
    rows = recent_jobs_repo.list_recent_jobs(limit=limit)
    log.info("recent_job_postings: %d filas con descripción no vacía", len(rows))

    inserted = skipped_existing = skipped_no_url = 0
    for row in rows:
        if not row["url"]:
            skipped_no_url += 1
            continue
        if jobs_repo.url_exists(row["url"]):
            skipped_existing += 1
            continue

        text_for_embedding = f"{row['title']}\n{row['company'] or ''}\n{row['description']}"
        vec = embeddings.embed_text(text_for_embedding, EMBED_DIM)
        embedding_literal = embeddings.to_pgvector_literal(vec)

        jobs_repo.insert_job(
            source=SOURCE_TAG,
            title=row["title"],
            company=row["company"],
            url=row["url"],
            description=row["description"],
            embedding_literal=embedding_literal,
        )
        inserted += 1

    log.info(
        "listo: %d insertados, %d ya existían (mismo url), %d sin url (salteados)",
        inserted, skipped_existing, skipped_no_url,
    )


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    seed(limit_arg)
