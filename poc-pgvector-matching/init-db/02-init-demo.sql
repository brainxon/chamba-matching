-- Demo interactiva (v2 del PoC #355): tabla de "hot jobs" con forma
-- realista (title/company/url/description), modelada sobre la tabla real
-- `recent_job_postings` que ya existe en la DB real del backend (chambai)
-- pero hoy vive junto a los datos de usuarios. Acá vive en su propia DB
-- (chamba_jobs_hot, ya creada por 01-init.sql) — separada de esa DB real.
--
-- Distinta de `job_embeddings` (01-init.sql), que es la tabla usada por el
-- benchmark de carga sintética (scripts/run_all.py) — no se tocan entre sí.

\c chamba_jobs_hot

CREATE TABLE IF NOT EXISTS job_postings (
    id          BIGSERIAL PRIMARY KEY,
    source      TEXT NOT NULL,       -- 'seed' o 'scraped:<platform>'
    title       TEXT NOT NULL,
    company     TEXT,
    url         TEXT,
    description TEXT NOT NULL,
    embedding   vector(384) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS job_postings_hnsw_idx
    ON job_postings USING hnsw (embedding vector_cosine_ops);
