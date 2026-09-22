"""initial schema - job_postings + cv_embeddings_cache (chamba_jobs_hot, issue #355/#379)

Revision ID: d535640ae0f1
Revises:
Create Date: 2026-09-22
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d535640ae0f1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # chamba_jobs_hot es una base de datos SEPARADA de la DB real de
    # usuarios (cover_letter_db_stg) a propósito — issue #355: si esta
    # fuente scrapeada/de terceros se compromete, no expone datos de
    # usuarios. Por ser una DB dedicada, acá SÍ instalamos pgvector
    # (nunca en la DB real).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE job_postings (
            id            BIGSERIAL PRIMARY KEY,
            source        TEXT NOT NULL,
            title         TEXT NOT NULL,
            company       TEXT,
            url           TEXT,
            description   TEXT NOT NULL,
            embedding     vector(384) NOT NULL,
            embedding_bge vector(1024),
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX job_postings_hnsw_idx "
        "ON job_postings USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX job_postings_bge_hnsw_idx "
        "ON job_postings USING hnsw (embedding_bge vector_cosine_ops)"
    )

    # cv_embeddings_cache — issue #379: vive ACÁ, no en la DB real de
    # usuarios. Solo lo lee/escribe el proceso de batch (matching-batch),
    # que ya corre en esta misma máquina — el backend real nunca lo toca
    # directamente, así que no hace falta que esté disponible cuando la
    # máquina de matching está apagada (a diferencia de match_results,
    # que sí vive en cover_letter_db_stg.matching por eso mismo).
    # embedding como TEXT, no vector(): no se busca por similitud acá
    # (se busca por PK exacta cv_version_id+model), así que no hace
    # falta el tipo ni un índice HNSW para esta tabla.
    op.execute(
        """
        CREATE TABLE cv_embeddings_cache (
            cv_version_id INTEGER NOT NULL,
            model         VARCHAR(50) NOT NULL,
            embedding     TEXT NOT NULL,
            computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (cv_version_id, model)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cv_embeddings_cache")
    op.execute("DROP INDEX IF EXISTS job_postings_bge_hnsw_idx")
    op.execute("DROP INDEX IF EXISTS job_postings_hnsw_idx")
    op.execute("DROP TABLE IF EXISTS job_postings")
    op.execute("DROP EXTENSION IF EXISTS vector")
