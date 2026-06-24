import os
import json
from collections import defaultdict
from typing import Any, Dict, List

import httpx


def load_env(env_path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


KEYWORD_TO_DOCS: List[tuple[List[str], List[str]]] = [
    (["入院诊断", "入院记录", "入院评估", "首次病程"], ["入院记录", "首次病程记录"]),
    (["出院诊断", "出院记录", "出院医嘱", "出院小结"], ["出院记录", "出院医嘱"]),
    (["病程", "日常病程", "上级查房", "术后病程", "阶段小结", "交接班"], ["病程记录"]),
    (["手术", "术前", "术后", "术中"], ["手术记录", "术前讨论记录", "术后病程记录"]),
    (["麻醉"], ["麻醉记录"]),
    (["会诊"], ["会诊记录"]),
    (["知情同意"], ["知情同意书"]),
    (["医嘱"], ["医嘱单"]),
    (["检验", "检查", "影像", "超声"], ["检验报告", "检查报告"]),
    (["护理评估", "护理记录"], ["护理评估", "护理记录"]),
    (["死亡", "病重", "病危", "抢救"], ["病危（重）通知书", "抢救记录", "死亡记录"]),
    (["转科"], ["转科记录"]),
    (["术前讨论"], ["术前讨论记录"]),
    (["手术安全核查"], ["手术安全核查表"]),
    (["新生儿", "儿科"], ["新生儿记录", "儿科专科记录"]),
]


def infer_docs_by_name(name: str) -> List[str]:
    hits: List[str] = []
    for kws, docs in KEYWORD_TO_DOCS:
        if any(kw in (name or "") for kw in kws):
            hits.extend(docs)
    seen: set[str] = set()
    out: List[str] = []
    for d in hits:
        if d not in seen:
            seen.add(d)
            out.append(d)
    return out or ["通用文书"]


def fetch_rules(url: str, key: str) -> List[Dict[str, Any]]:
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    params = {
        "select": "rule_code,name,applicable_record_types,target_sections",
        "order": "rule_code.asc",
        "limit": "200",
    }
    with httpx.Client(timeout=30) as c:
        r = c.get(f"{url.rstrip('/')}/rest/v1/qc_rules", headers=headers, params=params)
        r.raise_for_status()
        return r.json()  # type: ignore[return-value]


def main() -> None:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    env = load_env(os.path.join(root, ".env"))
    url = env.get("SUPABASE_URL", "").strip()
    key = env.get("SUPABASE_SERVICE_ROLE_KEY") or env.get("SUPABASE_ANON_KEY")
    if not url or not key:
        raise SystemExit("缺少 SUPABASE_URL 或 API KEY")

    rules = fetch_rules(url, key)

    mapping_lines: List[str] = []
    count_by_doc: dict[str, int] = defaultdict(int)

    for r in rules:
        code = (r.get("rule_code") or "").strip()
        name = (r.get("name") or "").strip()
        docs: List[str] = []
        # 优先使用库内已填写字段
        docs = r.get("applicable_documents") or r.get("applicable_record_types") or []
        if not docs:
            docs = infer_docs_by_name(name)
        for d in docs:
            count_by_doc[d] = count_by_doc.get(d, 0) + 1
        mapping_lines.append(f"- {code} {name}: {' / '.join(docs)}")

    # 汇总
    summary_lines = ["\n[按文书类型汇总]"]
    for doc, cnt in sorted(count_by_doc.items(), key=lambda x: (-x[1], x[0])):
        summary_lines.append(f"- {doc}: {cnt}")

    # 输出到 Markdown 文件
    docs_dir = os.path.abspath(os.path.join(root, "docs"))
    os.makedirs(docs_dir, exist_ok=True)
    out_path = os.path.join(docs_dir, "规则-文书类型映射清单.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("## 规则与医疗文书类型映射清单\n\n")
        f.write("\n".join(mapping_lines))
        f.write("\n\n")
        f.write("\n".join(summary_lines))

    # 终端输出摘要
    print(f"生成完成: {out_path}")
    print(summary_lines[0])
    for line in summary_lines[1:6]:  # 只显示前 5 条汇总以便快速查看
        print(line)


if __name__ == "__main__":
    main()


