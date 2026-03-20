from __future__ import annotations

import json
import logging
import os
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import requests

from ..core.settings import get_settings


logger = logging.getLogger(__name__)

try:
    import faiss  # type: ignore

    _FAISS_OK = True
except Exception:
    faiss = None  # type: ignore[assignment]
    _FAISS_OK = False

try:
    import hnswlib  # type: ignore

    _HNSW_OK = True
except Exception:
    hnswlib = None  # type: ignore[assignment]
    _HNSW_OK = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    _SKLEARN_OK = True
except Exception:
    TfidfVectorizer = None  # type: ignore[assignment]
    cosine_similarity = None  # type: ignore[assignment]
    _SKLEARN_OK = False


ABBR_MAP = {
    "冠脉": "冠状动脉",
    "支架置入": "支架植入",
    "PCI": "经皮冠状动脉介入",
    "CABG": "冠状动脉旁路移植",
}


def _normalize_text(text: str) -> str:
    out = str(text or "").strip()
    if not out:
        return ""
    out = out.replace("（", "(").replace("）", ")")
    out = re.sub(r"\s+", "", out)
    for k, v in ABBR_MAP.items():
        out = out.replace(k, v)
    return out


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


@dataclass
class _IcdDoc:
    code: str
    name: str
    normalized: str


class IcdSemanticRetrievalService:
    """
    ICD semantic retrieval with pluggable backend:
    - tfidf: local sklearn TF-IDF (P0 fallback)
    - hnsw/faiss: embedding + ANN (M3)
    """

    def __init__(self) -> None:
        self._ready = False
        self._backend: str = "tfidf"

        # TF-IDF path
        self._docs_clinical: List[_IcdDoc] = []
        self._docs_insurance: List[_IcdDoc] = []
        self._vectorizer_clinical: Any = None
        self._vectorizer_insurance: Any = None
        self._matrix_clinical: Any = None
        self._matrix_insurance: Any = None

        # Embedding path
        self._meta_docs: List[Dict[str, Any]] = []
        self._embed_matrix: Optional[np.ndarray] = None
        self._faiss_index: Any = None
        self._hnsw_index: Any = None

    def _select_backend(self) -> str:
        settings = get_settings()
        configured = str(settings.ICD_SEMANTIC_BACKEND or "tfidf").strip().lower()
        if configured == "auto":
            if _FAISS_OK:
                return "faiss"
            if _HNSW_OK:
                return "hnsw"
            return "tfidf"
        if configured in {"faiss", "hnsw", "tfidf"}:
            return configured
        return "tfidf"

    def _build_tfidf_index(self) -> None:
        if not _SKLEARN_OK:
            logger.warning("ICD semantic retrieval tfidf unavailable: sklearn not installed")
            return

        from ..routers import icd_search as icd_mod

        icd_mod._load_data()
        clinical = icd_mod._icd10_clinical_data or []
        insurance = icd_mod._icd10_data or []

        def to_docs(rows: List[Dict[str, Any]]) -> List[_IcdDoc]:
            docs: List[_IcdDoc] = []
            for row in rows:
                code = str(row.get("code") or "").strip()
                name = str(row.get("name") or "").strip()
                if not code or not name:
                    continue
                docs.append(_IcdDoc(code=code, name=name, normalized=_normalize_text(name)))
            return docs

        self._docs_clinical = to_docs(clinical)
        self._docs_insurance = to_docs(insurance)

        def fit(docs: List[_IcdDoc]) -> Tuple[Any, Any]:
            if not docs:
                return None, None
            corpus = [f"{d.name} {d.normalized}" for d in docs]
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
            mat = vec.fit_transform(corpus)
            return vec, mat

        self._vectorizer_clinical, self._matrix_clinical = fit(self._docs_clinical)
        self._vectorizer_insurance, self._matrix_insurance = fit(self._docs_insurance)
        logger.info(
            "ICD semantic tfidf ready: clinical=%d insurance=%d",
            len(self._docs_clinical),
            len(self._docs_insurance),
        )

    def _load_embedding_index(self) -> bool:
        settings = get_settings()
        index_dir = Path(settings.ICD_SEMANTIC_INDEX_DIR)
        meta_path = index_dir / "icd10_meta.json"
        vec_path = index_dir / "icd10_vectors.npy"
        faiss_path = index_dir / "icd10.faiss"
        hnsw_path = index_dir / "icd10_hnsw.bin"

        if not meta_path.exists():
            logger.warning("ICD semantic embedding meta missing: %s", meta_path)
            return False

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self._meta_docs = list(meta.get("docs") or [])
        except Exception:
            logger.exception("Failed to load ICD semantic meta")
            return False

        if vec_path.exists():
            try:
                self._embed_matrix = np.load(vec_path).astype(np.float32)
            except Exception:
                logger.exception("Failed to load ICD semantic vectors: %s", vec_path)
                self._embed_matrix = None

        if self._backend == "faiss" and _FAISS_OK and faiss_path.exists():
            try:
                self._faiss_index = faiss.read_index(str(faiss_path))
                logger.info("ICD semantic faiss index loaded: %s", faiss_path)
                return True
            except Exception:
                logger.exception("Failed to load faiss index")
                self._faiss_index = None

        if self._backend == "hnsw" and _HNSW_OK and hnsw_path.exists():
            try:
                dim = int(meta.get("dim") or 0)
                if dim <= 0 and self._embed_matrix is not None:
                    dim = int(self._embed_matrix.shape[1])
                idx = hnswlib.Index(space="cosine", dim=dim)
                idx.load_index(str(hnsw_path))
                self._hnsw_index = idx
                logger.info("ICD semantic hnsw index loaded: %s", hnsw_path)
                return True
            except Exception:
                logger.exception("Failed to load hnsw index")
                self._hnsw_index = None

        if self._embed_matrix is not None and self._meta_docs:
            logger.info("ICD semantic embedding brute-force ready: rows=%d", len(self._meta_docs))
            return True
        return False

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        self._backend = self._select_backend()
        if self._backend in {"faiss", "hnsw"}:
            ok = self._load_embedding_index()
            if ok:
                self._ready = True
                return
            logger.warning("ICD semantic %s not ready, fallback to tfidf", self._backend)
            self._backend = "tfidf"
        self._build_tfidf_index()
        self._ready = True

    def _embed_query(self, query: str) -> Optional[np.ndarray]:
        settings = get_settings()
        api_key = (
            settings.ICD_SEMANTIC_API_KEY
            or os.getenv("SILICONFLOW_API_KEY")
            or settings.LLM_API_KEY
        )
        endpoint = str(settings.ICD_SEMANTIC_API_ENDPOINT or "https://api.siliconflow.cn/v1/embeddings")
        model = str(settings.ICD_SEMANTIC_EMBED_MODEL or "BAAI/bge-m3")
        timeout = int(getattr(settings, "ICD_SEMANTIC_TIMEOUT_SECONDS", 30))
        if not api_key:
            logger.warning("ICD semantic embedding skipped: API key not configured")
            return None

        try:
            resp = requests.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "input": query,
                    "encoding_format": "float",
                },
                timeout=timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") or []
            if not data:
                return None
            emb = data[0].get("embedding")
            if not isinstance(emb, list) or not emb:
                return None
            vec = np.array([emb], dtype=np.float32)
            return _l2_normalize(vec)
        except Exception:
            logger.exception("ICD semantic embedding request failed")
            return None

    def _search_embedding(self, query: str, top_k: int, min_score: float) -> List[Dict[str, Any]]:
        qv = self._embed_query(query)
        if qv is None or not self._meta_docs:
            return []

        # faiss ANN
        if self._faiss_index is not None:
            scores, indices = self._faiss_index.search(qv.astype(np.float32), max(1, top_k))
            out: List[Dict[str, Any]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0 or idx >= len(self._meta_docs):
                    continue
                s = float(score)
                if s < min_score:
                    continue
                doc = self._meta_docs[int(idx)]
                out.append({"code": doc["code"], "name": doc["name"], "score": s, "source": "semantic"})
            return out

        # hnsw ANN
        if self._hnsw_index is not None:
            labels, distances = self._hnsw_index.knn_query(qv[0], k=max(1, top_k))
            out = []
            for idx, dist in zip(labels[0], distances[0]):
                if idx < 0 or idx >= len(self._meta_docs):
                    continue
                # cosine space in hnswlib returns distance = 1 - cosine_similarity
                s = float(1.0 - dist)
                if s < min_score:
                    continue
                doc = self._meta_docs[int(idx)]
                out.append({"code": doc["code"], "name": doc["name"], "score": s, "source": "semantic"})
            return out

        # brute-force fallback on stored vectors
        if self._embed_matrix is None:
            return []
        sims = (self._embed_matrix @ qv[0]).astype(np.float32)
        idx_sorted = np.argsort(sims)[::-1]
        out = []
        for idx in idx_sorted[: max(1, top_k)]:
            s = float(sims[int(idx)])
            if s < min_score:
                continue
            doc = self._meta_docs[int(idx)]
            out.append({"code": doc["code"], "name": doc["name"], "score": s, "source": "semantic"})
        return out

    def _search_tfidf(self, query: str, prefer_insurance: bool, top_k: int, min_score: float) -> List[Dict[str, Any]]:
        if not _SKLEARN_OK:
            return []
        q = str(query or "").strip()
        if not q:
            return []
        qn = _normalize_text(q)
        docs = self._docs_insurance if prefer_insurance else self._docs_clinical
        vec = self._vectorizer_insurance if prefer_insurance else self._vectorizer_clinical
        mat = self._matrix_insurance if prefer_insurance else self._matrix_clinical
        if not docs or vec is None or mat is None:
            return []

        qv = vec.transform([f"{q} {qn}"])
        sims = cosine_similarity(qv, mat)[0]
        idx_sorted = sims.argsort()[::-1]

        out: List[Dict[str, Any]] = []
        for idx in idx_sorted:
            score = float(sims[int(idx)])
            if score < min_score:
                continue
            doc = docs[int(idx)]
            out.append({"code": doc.code, "name": doc.name, "score": score, "source": "semantic"})
            if len(out) >= max(1, top_k):
                break
        return out

    def search_diagnosis(
        self,
        query: str,
        prefer_insurance: bool = False,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        self._ensure_ready()
        if self._backend in {"faiss", "hnsw"}:
            out = self._search_embedding(_normalize_text(query), top_k=top_k, min_score=min_score)
            if out:
                return out
            # no hard failure: fallback tfidf if embedding/index not ready
            return self._search_tfidf(query, prefer_insurance=prefer_insurance, top_k=top_k, min_score=min_score)
        return self._search_tfidf(query, prefer_insurance=prefer_insurance, top_k=top_k, min_score=min_score)


_semantic_service: Optional[IcdSemanticRetrievalService] = None


def get_icd_semantic_retrieval_service() -> IcdSemanticRetrievalService:
    global _semantic_service
    if _semantic_service is None:
        _semantic_service = IcdSemanticRetrievalService()
    return _semantic_service
