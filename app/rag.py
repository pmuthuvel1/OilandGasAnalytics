"""Tiny RAG layer using the Compass embedding model.

Indexes a curated set of project text files (docs, JSON examples, sample CSV)
into an in-memory numpy vector store. Persists the index to
``logs/rag_index.json`` so we don't re-embed on every run.

No external vector-DB dependency: cosine similarity on a (N, D) numpy matrix
is plenty fast for the few hundred chunks we have here.
"""
from __future__ import annotations

import glob
import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .config import get_config

logger = logging.getLogger(__name__)

_DEFAULT_INCLUDES = [
    "*.md",
    "input_examples/*.json",
    "output_examples/*.json",
    "data/*.csv",
    "data/SEAM_I_Well_Log_Delivery/Logs_In_Ascii/Gamma.Well.*",
    "data/SEAM_I_Well_Log_Delivery/Logs_In_Ascii/Density.Well.*",
]
_INDEX_FILE = Path(os.getenv("RAG_INDEX_FILE", "logs/rag_index.json"))
_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
_CHUNK_CHARS = int(os.getenv("RAG_CHUNK_CHARS", "1200"))
_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))
_MAX_CHUNKS_PER_FILE = int(os.getenv("RAG_MAX_CHUNKS_PER_FILE", "20"))
_EMBED_BATCH = int(os.getenv("RAG_EMBED_BATCH", "32"))
_LOCK = threading.Lock()
_STATE: Dict[str, Any] = {"loaded": False, "vectors": None, "chunks": []}


def _includes() -> List[str]:
    raw = os.getenv("RAG_INCLUDE_GLOBS")
    if not raw:
        return _DEFAULT_INCLUDES
    return [g.strip() for g in raw.split(",") if g.strip()]


def _iter_files() -> List[Path]:
    files: List[Path] = []
    for pattern in _includes():
        for path in glob.glob(pattern, recursive=True):
            p = Path(path)
            if p.is_file() and p.stat().st_size < 2_000_000:  # skip very large files
                files.append(p)
    return sorted(set(files))


def _chunk_text(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= _CHUNK_CHARS:
        return [text]
    chunks = []
    start = 0
    step = max(1, _CHUNK_CHARS - _CHUNK_OVERLAP)
    while start < len(text) and len(chunks) < _MAX_CHUNKS_PER_FILE:
        chunks.append(text[start : start + _CHUNK_CHARS])
        start += step
    return chunks


def _hash_corpus(files: List[Path]) -> str:
    h = hashlib.sha256()
    for p in files:
        try:
            stat = p.stat()
            h.update(f"{p}:{stat.st_size}:{int(stat.st_mtime)}\n".encode())
        except OSError:
            continue
    config = get_config()
    h.update((config.COMPASS_EMBEDDING_MODEL or "").encode())
    return h.hexdigest()


def _get_embedding_client():
    config = get_config()
    if not config.llm_enabled:
        return None, None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not available; RAG disabled.")
        return None, None
    kwargs: Dict[str, Any] = {"api_key": config.OPENAI_API_KEY, "timeout": config.OPENAI_REQUEST_TIMEOUT}
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    return OpenAI(**kwargs), config.COMPASS_EMBEDDING_MODEL


def _embed(texts: List[str]) -> Optional[np.ndarray]:
    client, model = _get_embedding_client()
    if client is None or not texts:
        return None
    vectors: List[List[float]] = []
    for i in range(0, len(texts), _EMBED_BATCH):
        batch = texts[i : i + _EMBED_BATCH]
        try:
            resp = client.embeddings.create(model=model, input=batch)
            vectors.extend([d.embedding for d in resp.data])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Embedding batch failed (%s); RAG will be empty.", exc)
            return None
    arr = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def _load_persisted(corpus_hash: str) -> bool:
    if not _INDEX_FILE.exists():
        return False
    try:
        data = json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    if data.get("corpus_hash") != corpus_hash:
        return False
    vectors = np.asarray(data.get("vectors", []), dtype=np.float32)
    chunks = data.get("chunks", [])
    if vectors.size == 0 or not chunks or vectors.shape[0] != len(chunks):
        return False
    _STATE.update({"loaded": True, "vectors": vectors, "chunks": chunks, "corpus_hash": corpus_hash})
    logger.info("RAG index loaded from cache: %d chunks", len(chunks))
    return True


def _persist(corpus_hash: str, vectors: np.ndarray, chunks: List[Dict[str, Any]]) -> None:
    try:
        _INDEX_FILE.write_text(
            json.dumps(
                {
                    "corpus_hash": corpus_hash,
                    "vectors": vectors.tolist(),
                    "chunks": chunks,
                }
            ),
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist RAG index: %s", exc)


def build_index(force: bool = False) -> int:
    """Build (or load) the RAG index. Returns chunk count (0 if disabled)."""
    with _LOCK:
        files = _iter_files()
        corpus_hash = _hash_corpus(files)
        if not force and _STATE.get("loaded") and _STATE.get("corpus_hash") == corpus_hash:
            return len(_STATE["chunks"])
        if not force and _load_persisted(corpus_hash):
            return len(_STATE["chunks"])

        chunks: List[Dict[str, Any]] = []
        texts: List[str] = []
        for path in files:
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            for i, ch in enumerate(_chunk_text(raw)):
                chunks.append({"source": str(path), "chunk_id": i, "text": ch})
                texts.append(ch)

        if not texts:
            _STATE.update({"loaded": True, "vectors": None, "chunks": [], "corpus_hash": corpus_hash})
            return 0

        logger.info("RAG: embedding %d chunks from %d files...", len(texts), len(files))
        vectors = _embed(texts)
        if vectors is None:
            _STATE.update({"loaded": True, "vectors": None, "chunks": [], "corpus_hash": corpus_hash})
            return 0
        _STATE.update({"loaded": True, "vectors": vectors, "chunks": chunks, "corpus_hash": corpus_hash})
        _persist(corpus_hash, vectors, chunks)
        return len(chunks)


def retrieve(query: str, k: int = 4) -> List[Dict[str, Any]]:
    """Return up to ``k`` most relevant chunks for the query (empty if disabled)."""
    if not query or not query.strip():
        return []
    if not _STATE.get("loaded"):
        try:
            build_index()
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG build failed: %s", exc)
            return []
    vectors = _STATE.get("vectors")
    chunks = _STATE.get("chunks") or []
    if vectors is None or not len(chunks):
        return []
    q_vec = _embed([query])
    if q_vec is None:
        return []
    scores = (vectors @ q_vec[0]).astype(float)
    top_idx = np.argsort(-scores)[:k]
    results = []
    for idx in top_idx:
        ch = chunks[int(idx)]
        results.append(
            {
                "source": ch["source"],
                "chunk_id": ch["chunk_id"],
                "score": round(float(scores[int(idx)]), 4),
                "snippet": ch["text"][:600],
            }
        )
    return results


def retrieve_with_retry(
    query: str,
    k: int = 4,
    min_score: float = 0.2,
    min_hits: int = 2,
    broaden_terms: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Retrieve with automatic broadening when results are weak or empty.

    Returns ``{"hits": [...], "attempts": [...], "final_query": str,
    "coverage": "ok"|"weak"|"empty"}`` so the planner can decide whether to
    delegate more research work.
    """
    attempts: List[Dict[str, Any]] = []
    base = (query or "").strip()
    broaden_terms = broaden_terms or [
        "reservoir porosity permeability",
        "seismic amplitude horizon fault",
        "well log lithology gas sand",
        "oil and gas exploration risk",
    ]

    def _coverage(hits: List[Dict[str, Any]]) -> str:
        if not hits:
            return "empty"
        top = hits[0]["score"]
        if len(hits) < min_hits or top < min_score:
            return "weak"
        return "ok"

    final_hits: List[Dict[str, Any]] = []
    final_query = base
    candidates: List[str] = []
    if base:
        candidates.append(base)
    for term in broaden_terms:
        candidates.append((base + " " + term).strip() if base else term)

    for q in candidates:
        try:
            hits = retrieve(q, k=k)
        except Exception as exc:  # noqa: BLE001
            logger.warning("retrieve_with_retry failed for %r: %s", q, exc)
            hits = []
        cov = _coverage(hits)
        attempts.append(
            {
                "query": q,
                "hits": len(hits),
                "top_score": hits[0]["score"] if hits else 0.0,
                "coverage": cov,
            }
        )
        final_hits, final_query = hits, q
        if cov == "ok":
            break

    return {
        "hits": final_hits,
        "attempts": attempts,
        "final_query": final_query,
        "coverage": attempts[-1]["coverage"] if attempts else "empty",
    }


def status() -> Dict[str, Any]:
    return {
        "loaded": bool(_STATE.get("loaded")),
        "chunks": len(_STATE.get("chunks") or []),
        "index_file": str(_INDEX_FILE),
    }

