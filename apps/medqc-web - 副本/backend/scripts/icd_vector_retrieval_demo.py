from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.routers import icd_search


ABBR_MAP = {
    "冠脉": "冠状动脉",
    "支架置入": "支架植入",
    "PCI": "经皮冠状动脉介入",
    "CABG": "冠状动脉旁路移植",
    "糖尿病2型": "2型糖尿病",
}


def normalize_text(text: str) -> str:
    out = str(text or "").strip()
    out = out.replace("（", "(").replace("）", ")")
    out = re.sub(r"\s+", "", out)
    for k, v in ABBR_MAP.items():
        out = out.replace(k, v)
    return out


@dataclass
class IcdDoc:
    code: str
    name: str
    norm: str


class IcdVectorRetriever:
    def __init__(self) -> None:
        icd_search._load_data()
        source = icd_search._icd10_clinical_data or icd_search._icd10_data
        self.docs: List[IcdDoc] = []
        corpus: List[str] = []
        for row in source:
            code = str(row.get("code") or "").strip()
            name = str(row.get("name") or "").strip()
            if not code or not name:
                continue
            norm = normalize_text(name)
            self.docs.append(IcdDoc(code=code, name=name, norm=norm))
            corpus.append(f"{name} {norm}")

        if not corpus:
            raise RuntimeError("ICD corpus is empty.")

        # char n-gram for robust typo/abbreviation-ish retrieval in Chinese clinical text
        self.vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        self.matrix = self.vectorizer.fit_transform(corpus)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[IcdDoc, float]]:
        q = normalize_text(query)
        qv = self.vectorizer.transform([f"{query} {q}"])
        sims = cosine_similarity(qv, self.matrix)[0]
        idx_sorted = sims.argsort()[::-1][:top_k]
        out: List[Tuple[IcdDoc, float]] = []
        for idx in idx_sorted:
            out.append((self.docs[int(idx)], float(sims[int(idx)])))
        return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo ICD vector retrieval (local TF-IDF vectors).")
    parser.add_argument("--query", action="append", help="query text; can be specified multiple times")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    queries = args.query or [
        "冠脉支架植入后状态",
        "冠状动脉支架植入后状态",
        "不稳定型心绞痛",
        "不稳定性心绞痛",
    ]

    retriever = IcdVectorRetriever()
    for q in queries:
        print("=" * 90)
        print(f"QUERY: {q}")
        results = retriever.search(q, top_k=args.top_k)
        for i, (doc, score) in enumerate(results, start=1):
            print(f"{i}. {doc.code:<14} score={score:.4f}  {doc.name}")


if __name__ == "__main__":
    main()

