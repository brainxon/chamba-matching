"""Embeddings reales via BGE-M3 (BAAI, modelo abierto/gratuito, 1024 dims,
multilingüe) - comparación pedida contra el hashing determinístico de
embeddings.py (ver report.md "Comparación de modelos de embeddings").

Corre 100% local dentro del container `api` (CPU, sin GPU) - no llama a
ningún proveedor externo, pero a diferencia del hashing SÍ es un modelo
entrenado real, y por eso pesa (torch + pesos del modelo, ~2.3GB) y tarda
un tiempo real por texto (ver /api/jobs/embed-bge).

Carga perezosa + cacheada (singleton en el módulo): cargar el modelo tarda
varios segundos, no queremos hacerlo en cada request.
"""

import logging
import time

import numpy as np

log = logging.getLogger(__name__)

_model = None
_load_seconds: float | None = None

DIM = 1024


def _get_model():
    global _model, _load_seconds
    if _model is None:
        from FlagEmbedding import BGEM3FlagModel

        t0 = time.perf_counter()
        log.info("loading BGE-M3 (BAAI/bge-m3, CPU, use_fp16=False) - primera vez, puede tardar...")
        _model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
        _load_seconds = time.perf_counter() - t0
        log.info("BGE-M3 cargado en %.2fs", _load_seconds)
    return _model


def embed_text(text: str) -> tuple[np.ndarray, float]:
    """Returns (unit-norm dense vector, seconds spent encoding - excluye la carga del modelo)."""
    model = _get_model()
    t0 = time.perf_counter()
    out = model.encode([text or ""], batch_size=1, max_length=2048)
    vec = np.asarray(out["dense_vecs"][0], dtype=np.float32)
    elapsed = time.perf_counter() - t0
    return vec, elapsed


def embed_texts(texts: list[str], batch_size: int = 32) -> tuple[list[np.ndarray], float]:
    """Igual que embed_text pero para varios textos en una sola llamada -
    en CPU, procesar N textos juntos es mucho más rápido que N llamadas
    individuales (menos overhead por llamada). Usar para backfills/batches
    grandes (ver api/backfill_job_bge.py, issue #378), no para el caso de
    un solo CV on-demand."""
    model = _get_model()
    t0 = time.perf_counter()
    out = model.encode([t or "" for t in texts], batch_size=batch_size, max_length=2048)
    vecs = [np.asarray(v, dtype=np.float32) for v in out["dense_vecs"]]
    elapsed = time.perf_counter() - t0
    return vecs, elapsed


def to_pgvector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec.tolist()) + "]"


def load_seconds() -> float | None:
    return _load_seconds
