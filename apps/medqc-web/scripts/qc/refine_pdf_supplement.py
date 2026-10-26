"""细化已有 PDF 私有预览；离线排重和保存位置建议，无数据库或模型入口。"""

from __future__ import annotations

import argparse
import collections
import csv
import difflib
import hashlib
import html
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from preview_pdf_supplement import CONTENT_FIELDS, DATED_LINE, compact, originals


PUNCTUATION = str.maketrans("，：；（）【】", ",:;()[]")
SIGN_LABEL = re.compile(r"(?<![一-鿿A-Za-z])(?:医生|医师)签名\s*[:：]")
SIGN_NAME = re.compile(r"[一-鿿A-Za-z·]{2,8}")
DAILY_TITLES = re.compile(
    r"输血前评估(?:记录)?|输血后(?:疗效)?(?:评估|评价)(?:记录)?|"
    r"危急值(?:处理|处置)?记录|日常病程记录[（(].*[）)]|"
    r"(?:PPI(?:药物)?|抗生素)使用记录|特殊情况记录"
)


def normalize(text: str) -> str:
    text = html.unescape(str(text or ""))
    text = re.sub(r"</?(?:p|br|div|span|font|b|strong|table|tr|td)(?:\s[^>]*)?/?>", "", text, flags=re.I)
    return compact(text).translate(PUNCTUATION)


def pdf_body(document: dict[str, Any]) -> str:
    """只移除明确的标题时间行；原文另外完整保留。"""
    lines = str(document["content"]).splitlines()
    if lines and compact(lines[0]) == compact(document["title"]):
        lines.pop(0)
    if lines:
        match = DATED_LINE.fullmatch(lines[0])
        if match and compact(match["title"]) in ("", compact(document["title"])):
            lines.pop(0)
    return "\n".join(lines)


def core(text: str) -> str:
    labels = list(SIGN_LABEL.finditer(text))
    # 多个签名栏可能意味着复合文书或边界错误，不能只截前半段认定相同。
    body = text[:labels[0].start()] if len(labels) == 1 else text
    return normalize(body).lstrip(":")


def signatures(text: str) -> tuple[str, ...]:
    labels = list(SIGN_LABEL.finditer(str(text)))
    if len(labels) != 1:
        return ()
    tail = text[labels[0].end():].strip()
    # PDF 末尾可能另有明确日期栏；日期单独保留，绝不充当记录时间。
    tail = re.split(r"(?:\n\s*)?(?:日期|签署时间)\s*[:：]", tail, maxsplit=1)[0]
    names = tuple(dict.fromkeys(re.split(r"[\s/、，,;；]+", tail.strip().rstrip("。.;；"))))
    return names if names and all(SIGN_NAME.fullmatch(name) for name in names) else ()


def row_bodies(row: dict[str, Any]) -> list[str]:
    body = str(row.get("record_content") or "")
    sections = [str(row.get(key) or "") for key in CONTENT_FIELDS if key != "record_content"]
    json_parts = originals(row.get("v2_schema"))
    # 小字段单独命中只证明该字段相同，不证明整份文书相同。
    return list(dict.fromkeys(value for value in (body, "\n".join(sections), "\n".join(json_parts)) if len(core(value)) >= 30))


def grams(text: str) -> set[str]:
    return {text[index:index+5] for index in range(max(0, len(text)-4))}


def indexed_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row=row, variants=[dict(body=body, core=core(body), grams=grams(core(body))) for body in row_bodies(row)]) for row in rows]


def minute(value: Any) -> str | None:
    if not value:
        return None
    try:
        clock = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if clock.tzinfo is None:
            return None
        from datetime import timedelta, timezone
        return clock.astimezone(timezone(timedelta(hours=8))).isoformat(timespec="minutes")
    except ValueError:
        return None


def storage_proposal(document: dict[str, Any]) -> tuple[str | None, str]:
    table = document.get("table")
    title = compact(document["title"])
    if table == "bloodtrans_assessment_record" or DAILY_TITLES.fullmatch(title):
        return "daily_course_record", "course_with_original_title"
    if table:
        return table, "existing_document_type"
    # 不把“请会诊执行”仅凭标题当已完成会诊，也不把操作记录当手术记录。
    return None, "unresolved_type"


def match_document(document: dict[str, Any], index: list[dict[str, Any]]) -> dict[str, Any]:
    body = pdf_body(document)
    text = core(body)
    tokens = grams(text)
    matches = []
    for item in index:
        best = None
        for variant in item["variants"]:
            old = variant["core"]
            if old == text:
                evidence, score = "exact_clinical_body", 1.0
            else:
                common = len(tokens & variant["grams"])
                shorter = min(len(tokens), len(variant["grams"]))
                coverage = common / max(shorter, 1)
                if coverage < .7:
                    continue
                ratio = difflib.SequenceMatcher(None, text, old, autojunk=False).ratio()
                if min(len(old), len(text)) >= 60 and (old in text or text in old):
                    evidence, score = "body_containment", max(ratio, .9)
                elif ratio >= .82:
                    evidence, score = "similar_body_requires_review", ratio
                else:
                    continue
            candidate = dict(evidence=evidence, score=round(score, 6), body=variant["body"], core=old)
            if best is None or candidate["score"] > best["score"]:
                best = candidate
        if best:
            row = item["row"]
            matches.append(dict(best, row=row, table=row["_table"], document_id=row.get("document_id")))
    matches.sort(key=lambda item: item["score"], reverse=True)
    public_matches = [{key:item[key] for key in ("table", "document_id", "score", "evidence")} for item in matches[:5]]
    table, mapping = storage_proposal(document)
    result = dict(proposed_table=table, mapping_basis=mapping, matches=public_matches,
                  action="held", reason="no_reliable_match", differences=[], write_approved=False)
    if matches:
        best = matches[0]
        # 含有同样复制内容的多份旧记录不得任取一份；时间只能用于展示，不能破除内容歧义。
        unique = len(matches) == 1 or best["score"] - matches[1]["score"] >= .06
        if not unique or (best["evidence"] == "similar_body_requires_review" and best["score"] < .96):
            result["reason"] = "ambiguous_or_approximate_match"
            return result
        row = best["row"]
        result.update(proposed_table=best["table"], mapping_basis="unique_existing_content_owner")
        old_time = row.get("record_time") or row.get("record_datetime")
        pdf_time = document.get("record_time")
        changes = []
        result["time_comparison_basis"] = "offset_aware_minute"
        if pdf_time and not old_time:
            changes.append("record_time_missing_in_database")
        elif pdf_time and old_time:
            if minute(old_time) is None:
                # CDM 某些列为 timestamp without time zone；只核对钟面值，不编造时区。
                result["time_comparison_basis"] = "database_unzoned_wall_clock_only"
                if str(old_time).replace(" ", "T")[:16] != pdf_time[:16]:
                    changes.append("record_time_timezone_unverified")
            elif minute(pdf_time) != minute(old_time):
                changes.append("record_time_conflict")
        elif old_time and not pdf_time:
            changes.append("pdf_record_time_missing_keep_existing")
        if best["core"] != text:
            changes.append("body_version_difference")
        old_signs = signatures(str(row.get("record_content") or ""))
        structured = str(row.get("physician_sign") or "").strip()
        if structured:
            old_signs = tuple(re.split(r"[\s/、，,;；]+", structured))
        new_signs = signatures(body)
        if new_signs and not old_signs:
            changes.append("explicit_signatures_missing_in_database")
        elif old_signs and new_signs and set(old_signs) != set(new_signs):
            changes.append("signature_conflict")
        result["differences"] = changes
        if any(key in changes for key in ("record_time_conflict", "record_time_timezone_unverified", "body_version_difference", "signature_conflict")):
            result.update(action="version_review", reason="existing_document_keep_both_versions_no_duplicate_insert")
        elif changes:
            result.update(action="supplement_candidate", reason="existing_document_missing_metadata")
        else:
            # 此处只确认对照用的正文一致，不声称整份 PDF / 全字段完全相同。
            result.update(action="same_body", reason="same_clinical_body_no_new_document")
        return result
    # 旧预览的弱匹配仍是阻止新增的证据；细化算法未命中不等于已证明不存在。
    if document.get("matches"):
        result["reason"] = "prior_match_needs_review"
    elif not document.get("record_time"):
        result["reason"] = "record_time_unavailable"
    elif not table:
        result["reason"] = "document_type_unresolved"
    elif len(text) < 30:
        result["reason"] = "too_little_clinical_content"
    else:
        result.update(action="new_candidate", reason="no_content_match_not_yet_write_ready")
    return result


def additional_identity(payload: dict[str, Any], archive: Path | None) -> dict[str, dict[str, Any]]:
    """只核对原姓名匹配项的页首明确编号，不用正文任意数字作身份证据。"""
    if archive is None:
        return {}
    import fitz

    proofs = {}
    with zipfile.ZipFile(archive) as bundle:
        entries = [entry for entry in bundle.infolist() if not entry.is_dir()]
        if len(entries) != len(payload["files"]):
            raise ValueError("archive_inventory_count_changed")
        for file, entry in zip(payload["files"], entries):
            if file["identity_basis"] == "name_and_identifier":
                continue
            data = bundle.read(entry)
            if hashlib.sha256(data).hexdigest() != file["source_sha256"]:
                raise ValueError("archive_source_hash_changed")
            with fitz.open(stream=data, filetype="pdf") as pdf:
                first_page = pdf[0].get_text(sort=True)
            header = re.search(r"(?P<label>住院号|病案号)\s*[:：]\s*(?P<identifier>[^\n]+)", first_page)
            same_row = header and any(
                str(row.get("name") or "").strip() and
                compact(str(row["name"])) in compact(first_page) and
                header["identifier"].strip() == str(row.get("mr_no") or "").strip()
                for row in payload["existing_documents"][file["sample"]]
            )
            proofs[file["file_id"]] = dict(
                verified=bool(same_row), source_sha256=file["source_sha256"],
                basis="pdf_name_and_explicit_header_number_match_same_case_row",
                pdf_header_label=header["label"] if header else None, matched_local_field="mr_no",
            )
    return proofs


def run(source: Path, output: Path, archive: Path | None = None) -> dict[str, Any]:
    if ".tmp" not in output.resolve().parts or not output.name.endswith("-private"):
        raise ValueError("output_must_be_tmp_private_directory")
    payload = json.loads(source.read_text(encoding="utf-8"))
    identity_proofs = additional_identity(payload, archive)
    indexes = {sample:indexed_rows(rows) for sample, rows in payload["existing_documents"].items()}
    documents = []
    for file in payload["files"]:
        for doc in file["documents"]:
            verdict = match_document(doc, indexes[file["sample"]])
            if file["identity_basis"] != "name_and_identifier" and not identity_proofs.get(file["file_id"], {}).get("verified"):
                verdict.update(action="held", reason="identity_not_cross_checked")
            documents.append(dict(doc, refinement=verdict))
    # 同包内重复也单独列出，不把它们当作多份新增。
    fingerprints: dict[tuple[str, str, str | None], list[str]] = collections.defaultdict(list)
    for doc in documents:
        digest = hashlib.sha256(core(pdf_body(doc)).encode()).hexdigest()
        fingerprints[(doc["sample"], digest, doc.get("record_time"))].append(doc["candidate_id"])
    repeated = [ids for ids in fingerprints.values() if len(ids)>1]
    repeated_ids = {candidate for ids in repeated for candidate in ids}
    for doc in documents:
        if doc["candidate_id"] in repeated_ids:
            doc["refinement"].update(action="held", reason="duplicate_within_pdf_package")
    rows = []
    for case in payload["cases"]:
        docs = [doc for doc in documents if doc["sample"] == case["sample"]]
        rows.append(dict(sample=case["sample"], candidates=len(docs),
                         actions=dict(collections.Counter(d["refinement"]["action"] for d in docs))))
    summary = dict(candidates=len(documents), cases=rows,
                   actions=dict(collections.Counter(d["refinement"]["action"] for d in documents)),
                   held_reasons=dict(collections.Counter(d["refinement"]["reason"] for d in documents if d["refinement"]["action"] == "held")),
                   differences=dict(collections.Counter(key for d in documents for key in d["refinement"]["differences"])),
                   within_package_duplicate_groups=len(repeated), write_approved=False,
                   additional_identity_verified=sum(proof["verified"] for proof in identity_proofs.values()),
                   database_writes=0, model_calls=0, qc_runs=0)
    output.mkdir(parents=True, exist_ok=True)
    (output/"refined-private.json").write_text(json.dumps(dict(documents=documents, summary=summary, identity_proofs=identity_proofs), ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (output/"refined-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    with (output/"逐条建议-private.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["样本", "来源文件号", "起页", "末页", "候选ID", "原题名", "PDF记录时间", "建议保存表", "分类", "原因", "字段差异", "对应旧文书候选"])
        for doc in documents:
            verdict = doc["refinement"]
            writer.writerow([doc["sample"], doc["source_file_id"], doc["page_start"], doc["page_end"],
                             doc["candidate_id"], doc["title"], doc.get("record_time"), verdict["proposed_table"],
                             verdict["action"], verdict["reason"], ";".join(verdict["differences"]),
                             json.dumps(verdict["matches"], ensure_ascii=False)])
    md = ["# PDF 补全逐例方案（只读细化）", "", "此表是补入建议，不是执行计划或已完成导入。相似正文不自动覆盖，未匹配也不等于源库缺失。", "",
          "|样本|片段|同正文，无需新增|已有文书补字段候选|对应候选有版本差异|新增候选|保留待核对|", "|---|---:|---:|---:|---:|---:|---:|"]
    for row in rows:
        a = row["actions"]
        md.append(f"|{row['sample']}|{row['candidates']}|{a.get('same_body',0)}|{a.get('supplement_candidate',0)}|{a.get('version_review',0)}|{a.get('new_candidate',0)}|{a.get('held',0)}|")
    md += ["", "## 保存与读取建议", "", "- 输血前评估、输血后评价：保留原题名和正文，建议保存为独立日常病程；现有输血规则已读取日常病程。不能放入输血记录表，以免产生虚假的输血事件。",
           "- 危急值处置和用药说明：作为原题名的病程文书，不生成新的检验危急值事件或医嘱。",
           "- 请会诊执行记录：有唯一强正文对应时沿用原文书 owner；没有对应时保持待定，不仅凭标题认定为已完成会诊。",
           "- 操作、入出 ICU 及泛名‘记录’：无可靠对应时保留原片段，暂不冒充手术、转科或普通病程。",
           "- 记录时间只来自明确标题或记录时间栏；提交、签署和出院时间均不替代。分钟精度不补秒。双人签名保留两人，不认定先后角色。",
           "- CDM中不带时区的时间只比较钟面值并标记比较依据，不擅自解释成UTC或制造八小时差；钟面不一致继续待核实，不认定已确认的时间冲突。",
           "- 既有正文相同而 PDF 提供了缺失时间/签名时，列为补字段候选；正文或非空字段不一致则保留两个来源，不能自动拼接或覆盖。",
           "", "## 导入前仍需完成", "", "新集必须复制成独立材料版本并完成关联重映射，不能只复制样本列表后修改原1022。当前未创建新集、未修改数据库、未刷新Bundle、未调用模型或质控。",
           "私有逐片段文件另含来源文件号、页码、候选ID和旧文书编号；本汇总不含患者或医生姓名。"]
    md += ["", "## 尚未解除的保留项", ""]
    for reason, count in summary["held_reasons"].items():
        md.append(f"- `{reason}`：{count}项。")
    missing_clocks = [f"{doc['sample']}（{doc['title']}，{doc['source_file_id']}）" for doc in documents if not doc.get("record_time")]
    md += ["", "PDF未提取到明确记录时间的文书："+"、".join(missing_clocks)+"。已有日期保留，签署/出院日期不能代替。",
           "", "`same_body`只表示对照正文相同；`version_review`包括相似正文对应候选，仍需选择活动版本，不能直接当作已确认的缺失或错误。新增候选也不等于已证明源库缺文书。"]
    (output/"逐例补入方案.md").write_text("\n".join(md)+"\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    summary = run(args.source, args.output, args.archive)
    print(json.dumps({key:value for key,value in summary.items() if key != "cases"}, ensure_ascii=True))
