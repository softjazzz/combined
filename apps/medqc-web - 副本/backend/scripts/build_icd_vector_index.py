from __future__ import annotations

import argparse
import json
import os
import pickle
import re
from pathlib import Path
from typing import Dict, List

import numpy as np
import requests
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    import faiss  # type: ignore
except Exception:
    faiss = None  # type: ignore[assignment]

try:
    import hnswlib  # type: ignore
except Exception:
    hnswlib = None  # type: ignore[assignment]


ABBR_MAP = {
    "冠脉": "冠状动脉",
    "支架置入": "支架植入",
    "PCI": "经皮冠状动脉介入",
    "CABG": "冠状动脉旁路移植",
}


def normalize(text: str) -> str:
    t = str(text or "").strip()
    t = t.replace("（", "(").replace("）", ")")
    t = re.sub(r"\s+", "", t)
    for k, v in ABBR_MAP.items():
        t = t.replace(k, v)
    return t


def l2_normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


def embed_texts_siliconflow(
    texts: List[str],
    model: str,
    endpoint: str,
    api_key: str,
    timeout: int,
    batch_size: int,
) -> np.ndarray:
    all_vectors: List[List[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "input": batch, "encoding_format": "float"},
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get("data") or []
        # API returns list with index
        data_sorted = sorted(data, key=lambda x: int(x.get("index", 0)))
        for item in data_sorted:
            emb = item.get("embedding")
            if not isinstance(emb, list):
                raise RuntimeError("invalid embedding payload from siliconflow")
            all_vectors.append(emb)
        print(f"embedded {min(i + batch_size, len(texts))}/{len(texts)}")
    return l2_normalize(np.array(all_vectors, dtype=np.float32))


def build_tfidf(docs: List[Dict[str, str]], out_dir: Path) -> None:
    corpus = [f"{d['name']} {d['norm']}" for d in docs]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    matrix = vectorizer.fit_transform(corpus)
    with (out_dir / "icd10_vectorizer.pkl").open("wb") as f:
        pickle.dump(vectorizer, f)
    with (out_dir / "icd10_matrix.pkl").open("wb") as f:
        pickle.dump(matrix, f)


def build_faiss(vectors: np.ndarray, out_dir: Path) -> bool:
    if faiss is None:
        print("faiss not installed, skip ANN index and use brute-force vectors")
        return False
    dim = int(vectors.shape[1])
    index = faiss.IndexFlatIP(dim)
    index.add(vectors.astype(np.float32))
    faiss.write_index(index, str(out_dir / "icd10.faiss"))
    return True


def build_hnsw(vectors: np.ndarray, out_dir: Path) -> bool:
    if hnswlib is None:
        print("hnswlib not installed, skip ANN index and use brute-force vectors")
        return False
    dim = int(vectors.shape[1])
    index = hnswlib.Index(space="cosine", dim=dim)
    index.init_index(max_elements=vectors.shape[0], ef_construction=200, M=16)
    index.add_items(vectors, np.arange(vectors.shape[0]))
    index.set_ef(64)
    index.save_index(str(out_dir / "icd10_hnsw.bin"))
    return True


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Build local ICD semantic index artifacts.")
    parser.add_argument("--icd-json", default="data/icd10_clinical_diagnoses.json")
    parser.add_argument("--out-dir", default="data/vector")
    parser.add_argument(
        "--engine",
        choices=["tfidf", "faiss", "hnsw"],
        default=os.getenv("ICD_SEMANTIC_BACKEND", "tfidf"),
    )
    parser.add_argument("--model", default=os.getenv("ICD_SEMANTIC_EMBED_MODEL", "BAAI/bge-m3"))
    parser.add_argument("--endpoint", default=os.getenv("ICD_SEMANTIC_API_ENDPOINT", "https://api.siliconflow.cn/v1/embeddings"))
    parser.add_argument("--api-key", default=os.getenv("ICD_SEMANTIC_API_KEY") or os.getenv("SILICONFLOW_API_KEY"))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--limit", type=int, default=0, help="Optional max docs for smoke build")
    args = parser.parse_args()

    icd_path = Path(args.icd_json)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = json.loads(icd_path.read_text(encoding="utf-8"))
    docs: List[Dict[str, str]] = []
    for row in rows:
        code = str(row.get("code") or "").strip()
        name = str(row.get("name") or "").strip()
        if not code or not name:
            continue
        docs.append({"code": code, "name": name, "norm": normalize(name)})
        if args.limit and len(docs) >= args.limit:
            break

    meta = {"count": len(docs), "docs": docs, "engine": args.engine}

    if args.engine == "tfidf":
        build_tfidf(docs, out_dir)
    else:
        if not args.api_key:
            raise RuntimeError("api key missing: set ICD_SEMANTIC_API_KEY or SILICONFLOW_API_KEY")
        corpus = [f"{d['name']} {d['norm']}" for d in docs]
        vectors = embed_texts_siliconflow(
            corpus,
            model=args.model,
            endpoint=args.endpoint,
            api_key=args.api_key,
            timeout=args.timeout,
            batch_size=max(1, args.batch_size),
        )
        np.save(out_dir / "icd10_vectors.npy", vectors)
        meta["dim"] = int(vectors.shape[1])
        meta["embed_model"] = args.model
        if args.engine == "faiss":
            ok = build_faiss(vectors, out_dir)
            if not ok:
                meta["engine"] = "bruteforce"
        else:
            ok = build_hnsw(vectors, out_dir)
            if not ok:
                meta["engine"] = "bruteforce"

    (out_dir / "icd10_meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"built engine={args.engine} docs={len(docs)} -> {out_dir}")


if __name__ == "__main__":
    main()
