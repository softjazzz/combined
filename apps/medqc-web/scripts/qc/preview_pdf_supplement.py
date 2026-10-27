"""本地 PDF 文书补充只读预览；无写库、模型、OCR 或 apply 入口。"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


# 时间只取明确的文书标题行；病史中的日期和签署日期不是记录时间。
STAMP = r"20\d{2}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?"
DATED_LINE = re.compile(rf"^\s*(?P<time>{STAMP})(?P<title>.*?)\s*$")
TITLES = (
    (r"术后首次病程(?:记录)?", "postsurg_firstcourse_record"),
    (r"首次病程(?:记录)?", "first_course_record"),
    (r".*(?:主任|主治|上级|副主任)医师.*查房(?:记录)?", "senior_course_record"),
    (r".*查房记录", "senior_course_record"),
    (r"日常病程(?:记录)?|病程记录", "daily_course_record"),
    (r".*会诊(?:记录|意见)?", "consultation_record"),
    (r"输血(?:治疗)?记录", "bloodtrans_record"),
    (r"输血前评估(?:记录)?|输血后(?:疗效)?(?:评估|评价)(?:记录)?", "bloodtrans_assessment_record"),
    (r"抢救记录", "rescue_record"),
    (r"转入记录", "transfer_in_record"),
    (r"转出记录", "transfer_out_record"),
    (r"交班记录", "handoff_record"),
    (r"接班记录", "handover_record"),
    (r"术前小结", "presurg_summary"),
    (r"术前讨论(?:记录)?", "presurg_discussion"),
    (r".*手术记录", "surgery_record"),
    (r"疑难病例讨论(?:记录)?", "diffcase_discussion_record"),
    (r"死亡病例讨论(?:记录)?", "death_discussion"),
    (r"阶段小结", "summary_record"),
    (r".*沟通(?:记录)?|谈话记录", "docpat_commu_record"),
    (r"死亡记录", "death_record"),
    (r"出院记录", "discharge_record"),
)
CONTENT_FIELDS = (
    "record_content", "case_characteristic", "diagnosis_discussion", "checkup",
    "assist_exam", "diagnose_based_on", "differential_diagnosis", "treatment_plan",
    "admission_condition", "positive_assist_exam", "treatment_course",
    "discharge_condition", "discharge_order", "death_reason", "surgery_process",
)
CASE_KEY = ("institute_id", "patient_id", "visit_id")


@dataclasses.dataclass
class Line:
    page: int
    text: str


def compact(value: str) -> str:
    # 不删除标点，避免把剂量、符号差异误认成完全相同。
    return re.sub(r"\s+", "", value)


def document_type(title: str) -> str | None:
    title = compact(title)
    if len(title) > 35 or re.search(r"[，。；：:!?！？]", title):
        return None
    return next((table for pattern, table in TITLES if re.fullmatch(pattern, title)), None)


def parse_time(value: str) -> str | None:
    value = value.replace("年", "-").replace("月", "-").replace("日", " ")
    value = re.sub(r"\s+", " ", value.strip()).replace("/", "-")
    fmt = "%Y-%m-%d %H:%M:%S" if value.count(":") == 2 else "%Y-%m-%d %H:%M"
    try:
        return datetime.strptime(value, fmt).isoformat(timespec="seconds" if value.count(":") == 2 else "minutes") + "+08:00"
    except ValueError:
        return None


def explicit_record_time(lines: list[Line]) -> dict[str, Any]:
    """终末 PDF 只取明确“记录时间”标签；多个不同值不擅自选取。"""
    found = []
    chinese_stamp = r"20\d{2}年\d{1,2}月\d{1,2}日\s*\d{1,2}:\d{2}(?::\d{2})?"
    pattern = re.compile(rf"记录时间\s*[:：]\s*(?P<time>{STAMP}|{chinese_stamp})")
    for line in lines:
        for match in pattern.finditer(line.text):
            stamp = parse_time(match["time"])
            if stamp:
                found.append(dict(value=stamp, page=line.page, source="explicit_record_time_label"))
    distinct = {item["value"] for item in found}
    return dict(value=found[0]["value"] if len(distinct)==1 else None,
                evidence=found, conflict=len(distinct)>1)


def segment_course(lines: list[Line]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """保留未知短标题为单独待核对片段，避免吞并进前一份文书。"""
    anchors: list[tuple[int, str, str | None, str | None]] = []
    issues = []
    for index, line in enumerate(lines):
        match = DATED_LINE.fullmatch(line.text)
        if not match:
            continue
        title = match["title"].strip()
        start = index
        if not title and index and document_type(lines[index - 1].text):
            start = index - 1
            title = lines[index - 1].text.strip()
        table = document_type(title)
        # 较长正文日期不是边界。未知的简短标题仍独立保留，等待确认。
        if table is None and (not title or len(compact(title)) > 24 or re.search(r"[，。；：:!?！？]", title)):
            continue
        timestamp = parse_time(match["time"])
        if timestamp is None:
            issues.append(dict(page=line.page, reason="invalid_heading_time"))
        anchors.append((start, title, table, timestamp))
    if not anchors:
        return [], [dict(reason="no_reliable_document_boundaries")]
    documents = []
    for number, (start, title, table, timestamp) in enumerate(anchors):
        end = anchors[number + 1][0] if number + 1 < len(anchors) else len(lines)
        chunk = lines[start:end]
        body = "\n".join(line.text for line in chunk)
        documents.append(dict(sequence=number+1, table=table, title=title, record_time=timestamp,
                              time_precision="second" if timestamp and len(timestamp) > 22 else "minute",
                              page_start=chunk[0].page, page_end=chunk[-1].page,
                              content=body, content_sha256=hashlib.sha256(body.encode()).hexdigest(),
                              boundary_review_required=table is None or timestamp is None))
    # 开头页眉由提取器移除；其他前导文字必须作为未归属内容留在私有材料。
    prefix = "\n".join(line.text for line in lines[:anchors[0][0]])
    if compact(prefix):
        issues.append(dict(reason="unassigned_prefix", content=prefix))
    return documents, issues


def originals(value: Any) -> list[str]:
    """仅取 original_text，JSON 元数据不当作正文。"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return []
    if isinstance(value, dict):
        result = [value["original_text"]] if isinstance(value.get("original_text"), str) else []
        for key, child in value.items():
            if key != "original_text":
                result.extend(originals(child))
        return result
    if isinstance(value, list):
        return [text for child in value for text in originals(child)]
    return []


def body_variants(row: dict[str, Any]) -> list[str]:
    variants = [compact(str(row.get(field) or "")) for field in CONTENT_FIELDS]
    variants.extend(compact(text) for text in originals(row.get("v2_schema")))
    return list(dict.fromkeys(text for text in variants if len(text) >= 20))


def clinical_body(value: str) -> str:
    # 签名本身不能作为认定同一文书的证据；源正文仍完整保存。
    return compact(re.split(r"(?:医生|医师)签名\s*[:：]", value)[0])


def comparison(document: dict[str, Any], existing: list[dict[str, Any]]) -> dict[str, Any]:
    if document.get("boundary_review_required") or not document.get("table"):
        return dict(action="review", reason="document_type_or_boundary_uncertain", matches=[])
    text = compact(document["content"])
    core = clinical_body(document["content"])
    matches = []
    for row in existing:
        evidence = None
        for variant in body_variants(row):
            if variant == text:
                evidence = "exact_content"
                break
            # 旧正文可含少量页首标题差异；包含仅用作匹配候选，不直接认定新增或覆盖。
            if len(variant) >= 60 and (variant in text or text in variant):
                evidence = "content_containment"
                break
            body = clinical_body(variant)
            if len(body) >= 90 and len(core) >= 90:
                anchors = [body[p:p+30] for p in (0, len(body)//2, max(0,len(body)-30))]
                if sum(anchor in core for anchor in anchors) >= 2:
                    evidence = "multiple_content_anchors"
                    break
        # 时间只提示可能重复，不能据此认定为同一文书。
        if not evidence and row["_table"] == document["table"]:
            clock = str(row.get("record_time") or row.get("record_datetime") or "").replace(" ", "T")
            if document.get("record_time") and clock[:16] == document["record_time"][:16]:
                evidence = "same_record_minute_only"
        if evidence:
            matches.append(dict(table=row["_table"], document_id=row.get("document_id"), evidence=evidence,
                                record_time=row.get("record_time"), submit_datetime=row.get("submit_datetime")))
    if len(matches) == 1 and matches[0]["evidence"] == "exact_content":
        return dict(action="duplicate", reason="exact_content", matches=matches)
    if matches:
        return dict(action="review", reason="existing_document_candidate_compare_content_and_time", matches=matches)
    if not document.get("record_time"):
        return dict(action="review", reason="record_time_unavailable", matches=[])
    return dict(action="new_candidate", reason="no_existing_content_match_not_write_approved", matches=[])


def read_page_lines(page: Any) -> list[Line]:
    # 先识别多项身份标签所在的固定页眉，不按固定高度裁掉临床正文。
    raw = []
    for block in page.get_text("dict", sort=True)["blocks"]:
        for line in block.get("lines", []):
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text:
                raw.append((line["bbox"], text))
    headers = [(bbox, text) for bbox,text in raw if bbox[1] < 110 and
               re.search(r"(?:姓名|住院号|病案号|科室)\s*[:：]", text)]
    labels = {label for _,text in headers for label in ("姓名","住院号","病案号","科室") if label in text}
    cutoff = max(bbox[3] for bbox,_ in headers) + 1 if len(labels) >= 2 else -1
    return [Line(page.number + 1, text) for bbox,text in raw if bbox[1] >= cutoff and
            not (bbox[1] > page.rect.height - 60 and re.fullmatch(r"(?:第\s*)?[（(]?\s*\d+\s*[）)]?\s*(?:页|/\s*\d+)?", text))]


def read_baseline(connection: Any, pool_name: str) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    from psycopg2 import sql

    connection.set_session(isolation_level="REPEATABLE READ", readonly=True, autocommit=False)
    with connection.cursor() as cur:
        cur.execute("SET LOCAL statement_timeout='15s'")
        cur.execute("SHOW transaction_read_only")
        assert cur.fetchone()[0] == "on"
        cur.execute("SELECT id FROM qc.manual_problem_sample_pools WHERE name=%s", (pool_name,))
        pools = cur.fetchall()
        if len(pools) != 1:
            raise ValueError("source_pool_not_unique")
        cur.execute("SELECT matched_institute_id,matched_patient_id,matched_visit_id,raw_payload_json FROM qc.manual_problem_sample_pool_items WHERE pool_id=%s ORDER BY row_no", (pools[0][0],))
        cases = []
        for institute, patient, visit, raw in cur.fetchall():
            raw = json.loads(raw) if isinstance(raw, str) else raw
            alias = raw.get("sample")
            if not re.fullmatch(r"C\d{2}", str(alias)) or not all((institute,patient,visit)):
                raise ValueError("invalid_canonical_sample_identity")
            cases.append(dict(sample=alias, institute_id=institute, patient_id=patient, visit_id=visit))
        if (len(cases) != 27 or {case['sample'] for case in cases} != {f'C{i:02}' for i in range(1,28)}
                or len({tuple(case[key] for key in CASE_KEY) for case in cases}) != 27):
            raise ValueError("source_cohort_not_27_distinct_samples")
        cur.execute("SELECT table_name,array_agg(column_name::text) FROM information_schema.columns WHERE table_schema='cdm' GROUP BY table_name")
        tables = {name: cols for name, cols in cur.fetchall() if set(CASE_KEY) <= set(cols)}
        relevant = {table for _, table in TITLES}
        docs = {case["sample"]: [] for case in cases}
        counts: dict[str, Any] = {}
        for table in sorted(tables):
            count_rows = {}
            # 也覆盖麻醉、申请、同意及操作等已有正文，不能仅因不在标题映射中就漏掉排重。
            is_doc = table in relevant or "record_content" in tables[table]
            for case in cases:
                where = sql.SQL(" AND ").join(sql.SQL("{}=%s").format(sql.Identifier(key)) for key in CASE_KEY)
                if is_doc:
                    query = sql.SQL("SELECT to_jsonb(t) FROM {}.{} t WHERE ").format(sql.Identifier("cdm"),sql.Identifier(table)) + where
                    cur.execute(query, tuple(case[key] for key in CASE_KEY))
                    records = [dict(row[0], _table=table) for row in cur.fetchall()]
                    docs[case["sample"]].extend(records)
                    count_rows[case["sample"]] = len(records)
                else:
                    query = sql.SQL("SELECT count(*) FROM {}.{} WHERE ").format(sql.Identifier("cdm"),sql.Identifier(table)) + where
                    cur.execute(query, tuple(case[key] for key in CASE_KEY))
                    count_rows[case["sample"]] = cur.fetchone()[0]
            counts[table] = count_rows
        cur.execute("SELECT current_timestamp")
        snapshot = str(cur.fetchone()[0])
    return cases, docs, dict(snapshot=snapshot, schema="cdm", tables=counts, read_only=True)


def run(args: argparse.Namespace) -> dict[str, Any]:
    import fitz
    import psycopg2
    from dotenv import dotenv_values

    output = Path(args.output).resolve()
    if not output.name.endswith("-private") or ".tmp" not in output.parts:
        raise ValueError("output_must_be_tmp_private_directory")
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
    if not isinstance(manifest, list):
        raise ValueError("inventory_format_invalid")
    env = dotenv_values(args.env_file)
    conn = psycopg2.connect(env["DATABASE_URL"], connect_timeout=5,
                            options="-cdefault_transaction_read_only=on")
    try:
        cases, existing, baseline = read_baseline(conn, args.source_pool)
        allowed = {case["sample"] for case in cases}
        parsed_files, proposed = [], []
        with zipfile.ZipFile(args.archive) as archive:
            entries = [entry for entry in archive.infolist() if not entry.is_dir()]
            if len(entries) != len(manifest):
                raise ValueError("inventory_file_count_changed")
            for entry, original in zip(entries, manifest):
                data = archive.read(entry)
                if hashlib.sha256(data).hexdigest() != original["sha256"]:
                    raise ValueError("inventory_pdf_hash_changed")
                aliases = original.get("samples", [])
                if len(aliases) != 1 or aliases[0] not in allowed:
                    raise ValueError("inventory_identity_unresolved")
                sample = aliases[0]
                pdf = fitz.open(stream=data, filetype="pdf")
                pages = [read_page_lines(page) for page in pdf]
                lines = [line for page in pages for line in page]
                if original["kind"] == "病程记录":
                    documents, issues = segment_course(lines)
                else:
                    terminal_clock = explicit_record_time(lines)
                    documents = [dict(sequence=1,table="death_record" if original["kind"] == "死亡记录" else "discharge_record",
                                      title=original["kind"], record_time=terminal_clock["value"],
                                      time_evidence=terminal_clock["evidence"],time_precision=None,
                                      page_start=1,page_end=len(pdf),content="\n".join(line.text for line in lines),
                                      boundary_review_required=terminal_clock["conflict"])]
                    issues = []
                item = dict(file_id=original["file_id"],sample=sample,pages=len(pdf),
                            source_sha256=original["sha256"],identity_basis=original["match_basis"],
                            issues=issues,documents=documents, raw_lines=[dataclasses.asdict(line) for line in lines])
                for document in documents:
                    document["candidate_id"] = hashlib.sha256((original["sha256"]+":"+str(document["sequence"])).encode()).hexdigest()[:24]
                    document["source_file_id"] = original["file_id"]
                    document["sample"] = sample
                    verdict = comparison(document, existing[sample])
                    if document.get("table") and document["table"] not in baseline["tables"]:
                        verdict = dict(action="review",reason="target_table_not_present_mapping_required",matches=verdict["matches"])
                    if original["match_basis"] != "name_and_identifier":
                        verdict = dict(action="review",reason="identity_not_cross_checked",matches=verdict["matches"])
                    document.update(verdict)
                    proposed.append(document)
                parsed_files.append(item)
                pdf.close()
        private = dict(files=parsed_files,baseline=baseline,existing_documents=existing,cases=cases,
                       source_pool=args.source_pool,target_pool=args.target_pool,
                       clone_required=True,write_approved=False)
        (output/"preview-private.json").write_text(json.dumps(private,ensure_ascii=False,indent=2,default=str)+"\n",encoding="utf-8")
        rows = []
        for case in cases:
            sample = case["sample"]
            ds = [doc for doc in proposed if doc["sample"]==sample]
            fs = [file for file in parsed_files if file["sample"]==sample]
            rows.append(dict(sample=sample,pdfs=len(fs),pages=sum(f["pages"] for f in fs),
                             baseline_documents=len(existing[sample]),candidate_documents=len(ds),
                             actions=dict(collections.Counter(d["action"] for d in ds)),
                             types=dict(collections.Counter(d["table"] or "unclassified" for d in ds)),
                             parsing_issues=len([issue for file in fs for issue in file["issues"]])))
        summary = dict(source_pool=args.source_pool,target_pool=args.target_pool,cases=rows,
                       pdfs=len(parsed_files),pages=sum(f["pages"] for f in parsed_files),
                       candidates=len(proposed),actions=dict(collections.Counter(d["action"] for d in proposed)),
                       case_coordinate_tables=len(baseline["tables"]),clone_inventory_complete=False,
                       reasons=dict(collections.Counter(d["reason"] for d in proposed)),
                       parsing_issues=dict(collections.Counter(i["reason"] for f in parsed_files for i in f["issues"])),
                       complete=True,write_approved=False,
                       database_writes=0,model_calls=0,qc_runs=0)
        (output/"preview-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        md = ["# PDF 补全只读预览", "", "所有新增或对应关系均为候选，尚未获准写入。原始正文和原编号仅保存在同目录 private 文件中。", "", "|样本|PDF|页数|现库文书|PDF候选|新增候选|重复|待核对|解析提示|", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for row in rows:
            md.append(f"|{row['sample']}|{row['pdfs']}|{row['pages']}|{row['baseline_documents']}|{row['candidate_documents']}|{row['actions'].get('new_candidate',0)}|{row['actions'].get('duplicate',0)}|{row['actions'].get('review',0)}|{row['parsing_issues']}|")
        md += ["", "待核对包含正文/时间对应、未知标题、目标表映射缺失及身份未交叉确认，不等于全部存在冲突。", "新增候选表示尚未检出正文匹配，不是已证明源库缺文书。", "只读表盘点目前覆盖带完整三坐标的78张表；患者级表和关系重映射仍须在复制实现前补验，不宣称已具备完整复制能力。", "本轮不创建样本集、不刷新 Bundle、不运行模型或质控。"]
        (output/"补入预览.md").write_text("\n".join(md)+"\n",encoding="utf-8")
        return summary
    finally:
        conn.rollback()
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("archive", "inventory", "env-file", "output"):
        parser.add_argument("--"+flag, required=True)
    parser.add_argument("--source-pool", default="1022")
    parser.add_argument("--target-pool", default="1026-PDF补全")
    args = parser.parse_args()
    try:
        summary = run(args)
        print(json.dumps({key:value for key,value in summary.items() if key!="cases"},ensure_ascii=True))
    except Exception as exc:
        # 数据库错误消息和文件名可能包含凭据或患者身份，不输出原始异常。
        print(json.dumps(dict(event="preview_failed",error_type=type(exc).__name__,database_writes=0,model_calls=0)))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
