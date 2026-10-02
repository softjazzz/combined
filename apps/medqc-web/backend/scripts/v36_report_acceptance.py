"""V3.6 隔离报表验收：正式 HTTP 生产链；默认只读取已生产的验收产物。"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

DATABASE = "medqc_v36_validation_20260924"
RULE_SET = "luxian_0609_qc_v1"
IDENTITY = ("institute_id", "patient_id", "visit_id")


class AcceptanceFailure(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise AcceptanceFailure(message)


def identity(row):
    return tuple(row.get(key) for key in IDENTITY)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class Probe:
    def __init__(self, manifest, base_url, artifacts, execute=False, timeout=300):
        require(manifest.get("database") == DATABASE, "manifest 必须指定本批隔离库")
        require(manifest.get("synthetic") is True, "manifest 必须声明纯合成来源")
        require(urlparse(base_url).hostname in {"127.0.0.1", "localhost", "::1"}, "仅支持本地隔离服务")
        self.manifest = manifest
        self.path = artifacts
        self.execute = execute
        self.timeout = timeout
        self.http = httpx.Client(base_url=base_url.rstrip("/"), timeout=60, trust_env=False)
        self.state = json.loads(artifacts.read_text(encoding="utf-8")) if artifacts.exists() else {
            "database": DATABASE, "synthetic": True, "tasks": [], "jobs": [], "defects": [], "checks": [],
        }
        require(self.state.get("database") == DATABASE, "产物数据库声明不匹配")
        self.cases = manifest["cases"]
        require(self.cases and len(self.cases) <= 20, "病例集合须为1至20例")
        require(len({identity(case) for case in self.cases}) == len(self.cases), "病例三坐标重复")
        for case in self.cases:
            require(all(identity(case)) and case.get("scene") in {"running", "final"}, "病例身份或场景缺失")
            require(case.get("department") and case.get("doctor"), "病例须有独立验收科室及医生维度")
            require(type(case.get("expected_issue")) is bool, "须显式指定预期问题状态")

    def checkpoint(self):
        save(self.path, self.state)

    def request(self, actor, method, path, *, params=None, body=None, csv_response=False):
        require(method == "GET" or self.execute, "写 API 默认关闭，请明确使用 --execute")
        token = os.environ.get(self.manifest["actors"][actor]["token_env"], "")
        require(token, f"缺少 {actor} 的环境令牌")
        response = self.http.request(method, path, params=params, json=body,
                                     headers={"Authorization": f"Bearer {token}"})
        # 不回显响应正文、查询身份、认证字段或模型日志。
        require(response.status_code == 200, f"{method} {path.split('?')[0]} 返回 HTTP {response.status_code}")
        if csv_response:
            require("text/csv" in response.headers.get("content-type", ""), "导出未返回 CSV")
            require(response.headers.get("cache-control") == "no-store", "导出缓存策略不符")
            reader = csv.reader if csv_response == "sections" else csv.DictReader
            return list(reader(io.StringIO(response.content.decode("utf-8-sig"))))
        payload = response.json()
        require(payload.get("success") is True and "data" in payload, "API 回执信封无效")
        return payload["data"]

    def preflight(self):
        version = self.request("creator", "GET", f"/api/v1/rule-set-versions/{RULE_SET}/{self.manifest['rule_set_version']}")
        resolution = version["resolution"]
        require(resolution["active_rule_ids"] == ["LX0609-001"], "验收冻结版本必须仅启用确定性001")
        require(not resolution["paused_rule_ids"], "验收版本不允许暂停规则混入输出")
        entry = next(row for row in resolution["entries"] if row["rule_id"] == "LX0609-001")
        require(entry.get("core_system_ids") == [self.manifest["core_system_id"]], "冻结核心制度归属不符")

    def publish_version(self):
        require(self.execute, "发布版本需要 --execute")
        require(not self.state["tasks"] and not self.state["jobs"], "已有生产产物不得重新发布版本")
        require(not self.state.get("version_draft"), "已有草稿引用，请人工核对正式发布状态，禁止重建")
        setup = self.manifest["version_setup"]
        base = self.request("creator", "GET", f"/api/v1/rule-set-versions/{RULE_SET}/{setup['base_version']}")
        entries = setup.get("entries")
        if entries is None:
            # 只搬运正式基础目录元数据；状态和归属由本批显式确认的验收合同决定。
            entries = [{**row, "state": "active" if row["rule_id"] == "LX0609-001" else "offline",
                        "core_system_ids": [self.manifest["core_system_id"]] if row["rule_id"] == "LX0609-001" else [],
                        **({"doctor_visible": True} if row["rule_id"] == "LX0609-001" else {})}
                       for row in base["resolution"]["entries"]]
        permitted = {"rule_id", "state", "department_scope_mode", "department_refs", "doctor_visible", "core_system_ids"}
        entries = [{key: value for key, value in row.items() if key in permitted} for row in entries]
        note = "SYN-V36 报表隔离验收：仅001确定性执行，显式核心制度归属"
        draft = self.request("creator", "POST", f"/api/v1/rule-set-versions/{RULE_SET}/draft", body={
            "base_version": setup["base_version"], "entries": entries, "note": note,
        })
        self.state["version_draft"] = {"id": draft["id"], "version_seq": draft["version_seq"]}
        self.checkpoint()
        published = self.request("creator", "POST", f"/api/v1/rule-set-versions/{RULE_SET}/draft/publish", body={
            "version": self.manifest["rule_set_version"], "version_seq": draft["version_seq"], "note": note,
        })
        require(published["version"] == self.manifest["rule_set_version"], "正式发布版本回执不符")
        self.state["published_version"] = published["version"]
        self.checkpoint()

    def wait_sync(self, prefix, job_id, expected_count):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            sync = self.request("creator", "GET", prefix + f"/sync-records/{job_id}")
            if sync["status"] == "completed":
                require(sync["ready_count"] == expected_count and sync["failed_count"] == 0,
                        "正式资料同步未全部就绪")
                return
            require(sync["status"] in {"queued", "running"}, "正式资料同步失败")
            time.sleep(2)
        raise AcceptanceFailure("正式资料同步超时；保留同步作业引用")

    def wait_job(self, actor, job_id):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            job = self.request(actor, "GET", f"/api/v1/qc/sichuan/workspace/batch-jobs/{job_id}")
            status = job.get("status")
            if status == "completed":
                summary = job.get("summary") or {}
                calls = job.get("llm_call_count", summary.get("llm_call_count"))
                tokens = job.get("total_tokens", summary.get("total_tokens"))
                require(type(calls) is int and calls == 0, "不能证明实际 LLM 调用为零")
                require(type(tokens) is int and tokens == 0, "不能证明实际模型 Token 为零")
                return {"job_id": job_id, "llm_call_count": calls, "total_tokens": tokens}
            require(status not in {"failed", "canceled", "cancelled"}, "正式质控执行失败或取消")
            time.sleep(2)
        raise AcceptanceFailure("正式质控保存结果轮询超时；保留产物，禁止重造结果")

    def produce(self):
        require(not self.state["tasks"] and not self.state["jobs"] and not self.state["defects"],
                "产物已存在，请默认只读核验；不重复创建任务")
        running = [case for case in self.cases if case["scene"] == "running"]
        if running:
            task = self.request("creator", "POST", "/api/v1/tasks", body={
                "task_name": f"SYN-V36-REPORT-{uuid4().hex[:12]}", "scene": "running",
                "rule_set_key": RULE_SET, "sampling_method": "all",
                "sampling_config": {"case_scope": "active"},
                "record_refs": [{key: case[key] for key in IDENTITY} for case in running],
            })
            require(task.get("rule_set_version") == self.manifest["rule_set_version"], "任务未冻结指定版本")
            entry = {"task_id": task["id"], "rule_set_version": task["rule_set_version"]}
            self.state["tasks"].append(entry)
            self.checkpoint()
            prefix = f"/api/v1/tasks/{task['id']}"
            sampled = self.request("creator", "POST", prefix + "/sample")
            records = sampled["records"]
            require({identity(row) for row in records} == {identity(case) for case in running}, "保存抽样三坐标不一致")
            entry["records"] = [{key: row[key] for key in (*IDENTITY, "id")} for row in records]
            self.checkpoint()
            staff = self.manifest["actors"]["staff"]
            self.request("creator", "POST", prefix + "/assign", body={
                "method": "by_ratio", "assignees": [{"user_id": staff["id"], "user_name": "合成受领人"}],
            })
            self.request("staff", "PUT", prefix, body={"status": "in_progress"})
            for row in records:
                self.request("staff", "POST", prefix + f"/records/{row['id']}/start")
            sync = self.request("creator", "POST", prefix + "/sync-records")
            entry["sync_job_id"] = sync["job_id"]
            self.checkpoint()
            self.wait_sync(prefix, sync["job_id"], len(records))
            run = self.request("staff", "POST", prefix + "/qc-runs", params={"scope": "assigned"})
            entry.update(run_number=run["run_number"], job_id=run["job_id"])
            self.state["jobs"].append({"job_id": run["job_id"], "actor": "staff", "scene": "running"})
            self.checkpoint()
            entry["usage"] = self.wait_job("staff", run["job_id"])
            for row in records:
                result = self.request("staff", "GET", prefix + f"/qc-runs/{run['run_number']}/records/{row['id']}",
                                      params={"scope": "assigned"})
                require(result.get("result_state") == "available" and result.get("items"), "原运行保存结果不可用")
                expected = next(case for case in running if identity(case) == identity(row))
                require(result.get("job_id") == run["job_id"], "原运行 job 引用错配")
                points = [point for point in result["items"]
                          if (point.get("rule_id") or point.get("rule_code") or point.get("qc_point_id")) == "LX0609-001"]
                require(len(points) == 1, "正式结果缺少唯一001")
                expected_status = "non_compliant" if expected["expected_issue"] else "compliant"
                require(points[0].get("status") == expected_status, "001正式结果状态与源文书时间不一致")
                defect_id = str(uuid4())
                defect = {"id": defect_id, "task_id": task["id"], "task_record_id": row["id"],
                          "run_number": run["run_number"], "root_job_id": run["job_id"],
                          **{key: expected[key] for key in IDENTITY}, "scene": "running"}
                self.state["defects"].append(defect)
                self.checkpoint()
                body = {"defect_id": defect_id, "run_number": run["run_number"],
                        "rule_name": "SYN 人工报表验收缺陷", "description": "合成验收：文书记录需要完善。",
                        "severity": "warning", "suggestion": "合成验收：请补充完整文书记录。"}
                path = prefix + f"/records/{row['id']}/manual-defects"
                first = self.request("staff", "POST", path, body=body)
                replay = self.request("staff", "POST", path, body=body)
                require(first["id"] == replay["id"] and replay.get("idempotent") is True, "人工录入重放未幂等")
                defect["created_at"] = first["created_at"]
                review = self.request("reviewer", "POST", f"/api/v1/manual-defects/{defect_id}/review", body={
                    "decision": "approved", "expected_status": "pending",
                })
                require(review.get("manual_review_status") == "approved", "人工缺陷审核未保存")
                candidates = self.request("reviewer", "GET", "/api/v1/defect-rectifications/candidates", params={
                    **{key: expected[key] for key in IDENTITY}, "expected_job_id": run["job_id"],
                })
                matches = [target for target in candidates["targets"]
                           if target["target_kind"] == "task_manual_defect" and target["target_id"] == defect_id]
                require(len(matches) == 1, "缺少唯一可信人工整改来源")
                defect.update(matches[0])
                defect.pop("label", None)
                self.checkpoint()
        for case in self.cases:
            if case["scene"] != "final":
                continue
            job = self.request("creator", "POST", "/api/v1/qc/sichuan/workspace/batch-jobs", body={
                "rule_set_key": RULE_SET, "scope": "final",
                "record_refs": [{key: case[key] for key in IDENTITY}],
            })
            entry = {"job_id": job["id"], "actor": "creator", "scene": "final", **{key: case[key] for key in IDENTITY}}
            self.state["jobs"].append(entry)
            self.checkpoint()
            entry["usage"] = self.wait_job("creator", job["id"])
            self.checkpoint()

    def verify(self):
        checks = []
        groups = {(case["scene"], case["department"], case["doctor"]) for case in self.cases}
        for scene, department, doctor in sorted(groups):
            cases = [case for case in self.cases if (case["scene"], case["department"], case["doctor"]) == (scene, department, doctor)]
            params = {"scene": scene, "department": department, "doctor": doctor}
            summary = self.request("creator", "GET", "/api/v1/quality-reports/record-quality", params=params)
            page = self.request("creator", "GET", "/api/v1/quality-reports/record-quality/records",
                                params={**params, "page_size": 100})
            require({identity(row) for row in page["items"]} == {identity(case) for case in cases}, "病历报表精确来源集合不一致")
            require(summary["kpis"]["qc_ready_total"] == len(cases), "已质控分母不一致")
            require(summary["kpis"]["auto_defect_total"] == sum(case["expected_issue"] for case in cases), "确定性问题数不一致")
            if scene == "final":
                require(summary["scope"]["archive_status"] == "unverified", "终末报表冒称已核验归档")
            rows = self.request("creator", "GET", "/api/v1/quality-reports/record-quality/export",
                                params={**params, "sheet": "records"}, csv_response=True)
            exported = {(row.get("机构编号"), row.get("患者编号"), row.get("就诊编号")) for row in rows}
            require(exported == {identity(case) for case in cases}, "CSV 与报表病例集合不一致")
            checks.append({"kind": "record_quality", "scene": scene, "records": len(cases), "csv_rows": len(rows),
                           "score_status": summary.get("score_standard", {}).get("status"),
                           "scored_total": summary["kpis"].get("scored_total"),
                           "average_score": summary["kpis"].get("average_score"),
                           "source_status": summary.get("source_status")})
        for institute in sorted({case["institute_id"] for case in self.cases}):
            for scene in sorted({case["scene"] for case in self.cases if case["institute_id"] == institute}):
                cases = [case for case in self.cases if case["institute_id"] == institute and case["scene"] == scene]
                for department in sorted({case["department"] for case in cases}):
                    group = [case for case in cases if case["department"] == department]
                    params = {"scene": scene, "institute_id": institute, "department": department,
                              "system_id": self.manifest["core_system_id"]}
                    report = self.request("creator", "GET", "/api/v1/core-system-reports", params=params)
                    require({identity(row) for row in report["items"]} == {identity(case) for case in group},
                            "制度报表精确病例集合不一致")
                    require(all(row["rule_set_version"] == self.manifest["rule_set_version"] for row in report["items"]),
                            "制度报表未读取本批正式冻结版本")
                    system = next(row for row in report["systems"] if row["id"] == self.manifest["core_system_id"])
                    count, issues = len(group), sum(case["expected_issue"] for case in group)
                    require(system["record_count"] == count and system["problem_records"] == issues, "制度分子分母不一致")
                    require(abs(system["problem_rate"] - issues / count) < 1e-9, "制度问题率不一致")
                    rows = self.request("creator", "GET", "/api/v1/core-system-reports/export", params=params, csv_response="sections")
                    buckets = [row for row in rows if len(row) >= 6 and row[0] == "制度汇总"
                               and row[1] == self.manifest["core_system_id"]]
                    require(len(buckets) == 1 and int(buckets[0][3]) == count and int(buckets[0][4]) == issues,
                            "制度 CSV 分子分母与报表不一致")
                    header = next(index for index, row in enumerate(rows) if row and row[0] == "机构")
                    exported = {tuple(row[:3]) for row in rows[header + 1:]}
                    require(exported == {identity(case) for case in group}, "制度 CSV 与报表病例集合不一致")
                    checks.append({"kind": "core_system", "scene": scene, "records": count, "problems": issues, "csv_rows": len(rows)})
        for task in self.state["tasks"]:
            defects = [row for row in self.state["defects"] if row["task_id"] == task["task_id"]]
            require(defects, "人工生产链未完成")
            dates = [datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
                     .astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() for row in defects]
            params = {"start_date": min(dates), "end_date": max(dates), "task_id": task["task_id"], "scene": "running"}
            report = self.request("creator", "GET", "/api/v1/manual-quality-reports", params={**params, "page_size": 100})
            require(report["timezone"] == "Asia/Shanghai", "人工创建日期时区不符")
            require(report["summary"]["entered"] == len(defects), "重复操作混入人工录入量")
            require({row["id"] for row in report["items"]} == {row["id"] for row in defects}, "人工报表缺陷集合不一致")
            require(all(row["source_verified"] for row in report["items"]), "正式生产链来源核验失败")
            require(report["summary"]["review"]["approved"] == len(defects), "当前审核数量不一致")
            require(sum(report["summary"]["rectification"].values()) == len(defects), "当前整改分列重复或丢失")
            for institute, department in sorted({(row["institute_id"], row["department"]) for row in report["items"]}):
                selected = [row for row in report["items"] if row["institute_id"] == institute and row["department"] == department]
                filtered = self.request("creator", "GET", "/api/v1/manual-quality-reports", params={
                    **params, "institute_id": institute, "department": department,
                    "creator_id": self.manifest["actors"]["staff"]["id"], "page_size": 100,
                })
                require(filtered["summary"]["entered"] == len(selected), "人工机构科室录入人组合筛选不一致")
            rows = self.request("creator", "GET", "/api/v1/manual-quality-reports/export", params=params, csv_response=True)
            require({row["id"] for row in rows} == {row["id"] for row in defects}, "人工 CSV 与查询集合不一致")
            checks.append({"kind": "manual_quality", "entered": len(defects), "rectification": report["summary"]["rectification"], "csv_rows": len(rows)})
        self.state["checks"] = checks
        self.state["status"] = "verified"
        self.state["unverified"] = ["上海跨午夜边界", "未知来源基线", "跨机构越权反例", "浏览器验收"]
        self.checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--execute", action="store_true", help="显式执行已授权的正式写 API")
    parser.add_argument("--publish-version", action="store_true", help="先以正式草稿/发布API生产manifest.version_setup版本")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    probe = None
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
        probe = Probe(manifest, args.base_url, args.artifacts, args.execute, args.timeout)
        if args.publish_version:
            probe.publish_version()
        probe.preflight()
        if args.execute:
            probe.produce()
        else:
            require(probe.state["jobs"], "尚无正式生产产物；默认只读模式未执行任何写 API")
        probe.verify()
        print(json.dumps({"status": "verified", "checks": len(probe.state["checks"]),
                          "unverified": probe.state["unverified"]}, ensure_ascii=False))
        return 0
    except (AcceptanceFailure, httpx.HTTPError, KeyError, ValueError) as exc:
        if probe is not None:
            probe.state["status"] = "incomplete"
            probe.checkpoint()
        # HTTP 异常可能含 URL/参数，仅输出类型；业务断言仅包含固定文案。
        message = str(exc) if isinstance(exc, AcceptanceFailure) else type(exc).__name__
        print(json.dumps({"status": "incomplete", "reason": message}, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if probe is not None:
            probe.http.close()


if __name__ == "__main__":
    raise SystemExit(main())
