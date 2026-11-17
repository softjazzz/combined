"""准备态默认不连接；获准后仅四类材料读取/保存，不创建质控任务。"""
from pathlib import Path
import argparse
import json
import os
import sys
import uuid


KINDS = ("daily_course_record", "presurg_summary", "surgery_record", "postsurg_firstcourse_record")
SOURCE = "cb437e611e802c5117f212c1e9743d2748ec4127"


def load_plan(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("trial_plan_path_invalid")
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("trial_plan_capacity")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("trial_plan_invalid")
    if (value.get("source_commit") != SOURCE or value.get("contract") != "clinical-primary-four-v1"
            or value.get("metadata_revision") != "clinical-primary-real-fields-v2"
            or sorted(value.get("document_types", ())) != sorted(KINDS)):
        raise ValueError("trial_contract_mismatch")
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != 2:
        raise ValueError("trial_requires_two_fixed_cases")
    if not all(isinstance(case, dict) for case in cases) or len({case.get("alias") for case in cases}) != 2:
        raise ValueError("trial_case_alias_invalid")
    if not all(isinstance(value.get(k), str) and value[k].strip()
               for k in ("approved_policy_file", "expected_source_binding")):
        raise ValueError("trial_source_approval_required")
    for case in cases:
        if case.get("alias") not in {"P01", "P02"}:
            raise ValueError("trial_case_alias_invalid")
        if not all(isinstance(case.get(k), str) and case[k].strip() for k in
                   ("institute_id", "patient_id", "visit_id", "expected_policy_hash", "expected_selection_id")):
            raise ValueError("trial_case_approval_required")
        counts = case.get("expected_selected_counts")
        if (not isinstance(counts, dict) or set(counts) != set(KINDS)
                or any(type(n) is not int or not 0 <= n <= 20000 for n in counts.values())
                or sum(counts.values()) == 0):
            raise ValueError("trial_expected_counts_required")
    return value


def execute(plan, output):
    # 此函数只由显式--execute进入；准备态不会导入任何应用/模型配置。
    if plan.get("authorization") != "APPROVED" or not plan.get("approval_reference"):
        raise ValueError("trial_execution_not_approved")
    output = Path(output)
    if not output.is_absolute():
        raise ValueError("trial_output_path_invalid")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    backend = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend))
    os.environ.update(QC_PRIMARY_FOUR_MATERIAL_ENABLED="true", QC_DAILY_MATERIAL_ENABLED="false",
                      QC_CASE_MATERIAL_DIR=str(output / "materials"),
                      QC_PRIMARY_FOUR_POLICY_FILE=plan["approved_policy_file"])
    from app.database import clinical_connection as clinical
    from app.services import clinical_sources, primary_material_readonly as readonly
    from app.services import primary_material_projection as primary, case_material_snapshot as material
    from app.services.luxian_0609 import source_evidence_reader as reader
    from app.services.bundles import assembly
    assert readonly.SOURCE_COMMIT == SOURCE
    source = clinical_sources.ordinary_snapshot()
    if source.get("binding") != plan.get("expected_source_binding"):
        raise ValueError("trial_source_binding_mismatch")
    results = []
    with clinical.selected(source):
        for case in plan["cases"]:
            identity = tuple(case[key] for key in ("institute_id", "patient_id", "visit_id"))
            with primary.live_context(identity):
                state = material.context()
                selection = primary.manifest(identity)
                if selection is None:
                    raise ValueError("trial_candidate_not_deployed")
                if (selection["policy_hash"] != case["expected_policy_hash"]
                        or selection["selection_id"] != case["expected_selection_id"]):
                    raise ValueError("trial_published_selection_mismatch")
                if any(item["selected_version"] is None for item in selection["items"]):
                    raise ValueError("trial_material_held_stop")
                counts = {}
                for kind in KINDS:
                    bundle = assembly._select_records(schema="cdm", table=kind,
                        institute_id=identity[0], patient_id=identity[1], visit_id=identity[2], limit=20000)
                    inputs = reader.read_luxian_0609_snapshot_source_rows(source_key=kind,
                        institute_id=identity[0], patient_id=identity[1], visit_id=identity[2], source_schema="cdm")
                    if inputs.truncated:
                        raise ValueError("trial_input_truncated_stop")
                    if [x["version_id"] for x in bundle] != [x["version_id"] for x in inputs.rows]:
                        raise ValueError("trial_material_version_mismatch")
                    counts[kind] = len(inputs.rows)
                if counts != case["expected_selected_counts"]:
                    raise ValueError("trial_selected_counts_mismatch")
                state["documents"] = {"documents":primary.project_documents(selection),
                                      "primary_material_status":primary.display_scope(selection)}
                captured = {key:value for key,value in state.items() if key not in {"engine", "connection"}}
                captured.update(protocol=material.PROTOCOL, limited_material_trial=True,
                                trial_document_types=list(KINDS))
            # 私有联验目录中的材料副本，不写生产任务/结果表或正式材料任务索引。
            synthetic_index = "material-trial-" + uuid.uuid4().hex
            saved = material.persist(synthetic_index, captured)
            with material.activate(saved):
                if primary.manifest(identity) != selection:
                    raise ValueError("trial_frozen_selection_mismatch")
            results.append({"case_alias":case["alias"], "selection_id":selection["selection_id"],
                            "fingerprint":saved["fingerprint"], "counts":counts})
    report = {"contract":readonly.CONTRACT,"source_commit":SOURCE,"cases":results,
              "model_calls":0,"medical_rule_runs":0,"quality_tasks_created":0,"production_writes":0}
    (output / "trial-summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8",newline="\n")
    return {"ok":True,"case_count":len(results),"model_calls":0,"quality_tasks_created":0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        plan = load_plan(args.plan)
        if not args.execute:
            print(json.dumps({"ok":True,"plan_checked":True,"executed":False,"database_connections":0,
                              "model_calls":0,"case_count":2}))
            return 0
        if not args.output:
            raise ValueError("trial_output_required")
        print(json.dumps(execute(plan,args.output)))
        return 0
    except Exception as error:
        # 未知异常不回显驱动信息、病例键、正文或受保护配置。
        print(json.dumps({"ok":False,"error_type":type(error).__name__,"instruction":"stop; preserve trial artifacts; do not retry"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
