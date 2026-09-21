"""Embeddings determinísticos por hashing (feature hashing / bolsa de
palabras), sin red ni proveedor externo (issue #355: sin AWS, y para esta
demo interactiva, sin OpenAI tampoco - decisión explícita del owner para
no depender de red/cuota durante una demo en vivo).

No son embeddings semánticos de un modelo entrenado: dos textos con
palabras en común (ej. "Python", "FastAPI", "PostgreSQL") caen en los
mismos buckets y su similitud coseno sube - suficiente para que el
matching en la demo se vea razonable, pero no reemplaza una evaluación
real de calidad semántica.
"""

import hashlib
import re

import numpy as np

_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def embed_text(text: str, dim: int) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    for token in _TOKEN_RE.findall((text or "").lower()):
        digest = hashlib.md5(token.encode()).hexdigest()
        idx = int(digest[:8], 16) % dim
        sign = 1.0 if int(digest[8], 16) % 2 == 0 else -1.0
        vec[idx] += sign
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def to_pgvector_literal(vec: np.ndarray) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec.tolist()) + "]"
