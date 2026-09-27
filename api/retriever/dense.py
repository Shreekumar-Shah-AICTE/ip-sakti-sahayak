"""The Retriever, dense half: optional multilingual embeddings over The Library.

Why optional: the keyless BM25 path must start and answer with nothing but the stdlib.
Dense retrieval needs numpy + fastembed + a ~220 MB model download, any of which can be
missing on a judge's laptop or in airplane mode. So every failure here degrades to
"dense unavailable, reason X" and The Retriever carries on with BM25 alone.

The index is precomputed (`python -m api.retriever.dense build` -> corpus/index/) and is
only used if its ids and corpus_version match chunks.jsonl exactly: a stale index would
silently point at the wrong text, which is worse than no index.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INDEX_DIR = ROOT / "corpus" / "index"
MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DENSE_TOP_N = 50  # dense candidates handed to RRF (inside the filtered id set)


class Dense:
    """Loaded lazily; `ready` is False until embeddings and the encoder both load."""

    def __init__(self, chunks: list[dict], index_dir: Path = INDEX_DIR):
        self.chunks = chunks
        self.index_dir = index_dir
        self.ready = False
        self.reason = "not loaded"
        self.matrix = None
        self._encoder = None
        self._lock = threading.Lock()
        self._tried = False

    def load(self) -> bool:
        with self._lock:
            if self._tried:
                return self.ready
            self._tried = True
            if os.environ.get("SAHAYAK_DENSE", "1") == "0":
                self.reason = "disabled by SAHAYAK_DENSE=0"
                return False
            try:
                import numpy as np

                meta = json.loads((self.index_dir / "ids.json").read_text(encoding="utf-8"))
                matrix = np.load(self.index_dir / "embeddings.npy")
            except Exception as exc:  # missing numpy, missing/corrupt index
                self.reason = f"no dense index ({type(exc).__name__})"
                return False
            ids = [c["chunk_id"] for c in self.chunks]
            version = self.chunks[0]["corpus_version"] if self.chunks else ""
            if meta.get("ids") != ids or meta.get("corpus_version") != version:
                self.reason = "dense index is stale (ids/corpus_version mismatch) - rebuild it"
                return False
            if matrix.shape[0] != len(ids):
                self.reason = "dense index row count mismatch"
                return False
            try:
                from fastembed import TextEmbedding

                self._encoder = TextEmbedding(meta.get("model", MODEL))
            except Exception as exc:  # fastembed absent, or model not cached and offline
                self.reason = f"encoder unavailable ({type(exc).__name__})"
                return False
            self.matrix = matrix
            self.ready = True
            self.reason = "ready"
            return True

    def warm_up(self) -> threading.Thread:
        """Load in the background so API cold start is not slowed by model loading."""
        t = threading.Thread(target=self.load, daemon=True, name="dense-warm-up")
        t.start()
        return t

    def encode(self, text: str):
        import numpy as np

        v = np.asarray(next(iter(self._encoder.embed([text]))), dtype=np.float32)
        return v / (np.linalg.norm(v) or 1.0)

    def rank(self, query: str, ids: list[int], n: int = DENSE_TOP_N) -> list[tuple[int, float]]:
        """Top-n (chunk index, cosine) among the already-filtered ids."""
        if not self.ready or not ids:
            return []
        import numpy as np

        sims = self.matrix[ids] @ self.encode(query)
        top = np.argsort(-sims)[:n]
        return [(ids[j], float(sims[j])) for j in top]


def build(chunks_path: Path, index_dir: Path = INDEX_DIR) -> tuple[int, int]:
    """Embed every chunk (section + text) and write embeddings.npy + ids.json."""
    import numpy as np
    from fastembed import TextEmbedding

    chunks = [json.loads(line) for line in chunks_path.open(encoding="utf-8") if line.strip()]
    enc = TextEmbedding(MODEL)
    mat = np.array(
        list(enc.embed([f"{c.get('section', '')} {c['text']}" for c in chunks], batch_size=32)),
        dtype=np.float32,
    )
    mat /= np.linalg.norm(mat, axis=1, keepdims=True)
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "embeddings.npy", mat)
    meta = {
        "model": MODEL,
        "corpus_version": chunks[0]["corpus_version"],
        "ids": [c["chunk_id"] for c in chunks],
    }
    (index_dir / "ids.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    return mat.shape


if __name__ == "__main__" and sys.argv[1:] == ["build"]:
    from api.retriever import CHUNKS_PATH

    print("dense index", build(CHUNKS_PATH))
