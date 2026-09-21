-- Comparación de modelos de embeddings (issue #355, ver report.md):
-- columna extra para el embedding real de BGE-M3 (1024 dims), al lado del
-- embedding por hashing ya existente en `embedding` (384 dims). Ambos
-- conviven en la misma fila para poder comparar matching lado a lado.

\c chamba_jobs_hot

ALTER TABLE job_postings ADD COLUMN IF NOT EXISTS embedding_bge vector(1024);

CREATE INDEX IF NOT EXISTS job_postings_bge_hnsw_idx
    ON job_postings USING hnsw (embedding_bge vector_cosine_ops);
