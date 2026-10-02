"""V3.6 40-42 隔离库正式 API 验收；默认只预检，不生成任务或最终结果。"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import httpx

TARGET_DATABASE = "medqc_v36_validation_20260924"
IDENTITY = ("institute_id", "patient_id", "visit_id")
BUCKETS = {"critical", "difficult", "critical_and_difficult", "ordinary"}
GROUPS = {
    "department": "department",
    "record_type": "bucket",
    "qc_physician": "qc_physician",
    "qc_reviewer": "reviewer_id",
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def identity(row):
    result = tuple(row.get(key) for key in IDENTITY)
    require(all(isinstance(value, str) and value.strip() for value in result), "病例三坐标无效")
    return result


class Runner:
    def __init__(self, manifest, base_url, execute):
        self.manifest = manifest
        self.execute = execute
        self.tasks = []
        self.checks = []
        self.cases = {identity(row): row for row in manifest["cases"]}
        self.people = manifest["assignees"]
        token_env = manifest.get("creator_token_env", "MEDQC_TASK_ACCEPTANCE_TOKEN")
        token = os.environ.get(token_env)
        require(token, f"缺少 {token_env} 环境变量")
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
            follow_redirects=False,
        )

    @staticmethod
    def token_env(person):
        return person.get("token_env") or "MEDQC_TASK_ASSIGNEE_TOKEN_" + re.sub(r"[^A-Za-z0-9]", "_", person["user_id"]).upper()

    def request(self, method, path, payload=None, expected=200, token=None):
        require(method == "GET" or self.execute, "只读预检禁止写请求")
        headers = {"Authorization": f"Bearer {token}"} if token else None
        response = self.client.request(method, path, json=payload, headers=headers)
        require(response.status_code == expected, f"{method} {path}: HTTP {response.status_code}, expected {expected}")
        if expected != 200:
            return None
        body = response.json()
        require(body.get("success") is True, f"{method} {path}: 回执 success 非 true")
        return body["data"]

    def preflight(self):
        options = self.request("GET", "/api/v1/tasks/assignee-options")
        if isinstance(options, dict):
            options = options.get("items", [])
        ids = {row.get("user_id", row.get("id")) for row in options}
        require(all(row["user_id"] in ids for row in self.people), "manifest 受领人不在正式有效质控员目录")
        for row in self.cases.values():
            require(row.get("bucket") in BUCKETS, "缺少可信类型桶预期")
            require(row.get("qc_physician") and row.get("reviewer_id"), "缺少质控医师签名或正式审核 reviewer_id；不能伪造事实")
        self.checks.append("readonly_assignee_preflight")

    def payload(self, name, method="all", parameters=None, assignment="by_ratio"):
        value = copy.deepcopy(self.manifest["base_task"])
        value.update(task_name=f"{self.manifest['batch_prefix']}-{name}", task_type="one_time",
                     sampling_method=method, assign_method=assignment)
        value.setdefault("sampling_config", {}).update(parameters or {})
        if assignment == "by_original_reviewer":
            value["assignee_config"] = {"fallback": "reject"}
        return value

    def create(self, payload):
        data = self.request("POST", "/api/v1/tasks", payload)
        require(data.get("id") and data.get("rule_set_version"), "创建未返回 task id 或冻结版本")
        self.tasks.append(data["id"])
        print(json.dumps({"created_task": data["id"], "task_name": payload["task_name"]}, ensure_ascii=False))
        return data["id"]

    def detail(self, task_id, token=None, tab="created"):
        data = self.request("GET", f"/api/v1/tasks/{task_id}?tab={tab}", token=token)
        require(data.get("id") == task_id and isinstance(data.get("records"), list), "任务详情身份或记录信封错误")
        return data

    def sample(self, task_id, expected_cases, method="all"):
        self.request("POST", f"/api/v1/tasks/{task_id}/sample")
        data = self.detail(task_id)
        rows = data["records"]
        keys = [identity(row) for row in rows]
        require(len(keys) == len(set(keys)), "抽样出现重复三坐标")
        require(set(keys).issubset(expected_cases), "抽样超出 manifest 候选集合")
        require(data["total_records"] == len(rows), "任务总数与关联记录数不符")
        if method == "all":
            require(set(keys) == set(expected_cases), "全量或指定集合不完整")
        elif method == "count":
            require(len(rows) == min(2, len(expected_cases)), "总数抽样数量不符")
        else:
            group = GROUPS[method.rsplit("_", 1)[0]]
            wanted = Counter((key[0], self.cases[key][group]) for key in expected_cases)
            actual = Counter((key[0], self.cases[key][group]) for key in keys)
            require(actual == Counter({key: 1 for key in wanted}), "分组定额或比例上限结果不符")
        for row in rows:
            snapshot = row.get("record_type_snapshot")
            if isinstance(snapshot, str):
                snapshot = json.loads(snapshot)
            require(isinstance(snapshot, dict) and snapshot.get("bucket") == self.cases[identity(row)]["bucket"], "类型冻结快照不符")
        before = {(row["id"], identity(row)) for row in rows}
        self.request("POST", f"/api/v1/tasks/{task_id}/sample")
        require(before == {(row["id"], identity(row)) for row in self.detail(task_id)["records"]}, "重复抽样未原样重放")
        return rows

    def assign(self, task_id, method, rows, *, check_negative=True):
        people = [{key: value for key, value in person.items()
                   if key in {"user_id", "user_name", "department", "record_types"}}
                  for person in self.people]
        payload = {"method": method, "assignees": people}
        if method == "by_original_reviewer":
            payload["fallback"] = "reject"
        if method == "by_record_type" and check_negative:
            bad = copy.deepcopy(payload)
            for person in bad["assignees"]:
                person["record_types"] = ["critical"]
            self.request("POST", f"/api/v1/tasks/{task_id}/assign", bad, expected=409)
            require(all(row.get("assignee_id") is None for row in self.detail(task_id)["records"]), "拒绝分配后存在部分写入")
        result = self.request("POST", f"/api/v1/tasks/{task_id}/assign", payload)
        require(result["total_assigned"] == len(rows), "分配计数不符")
        data = self.detail(task_id)
        people_by_id = {person["user_id"]: person for person in self.people}
        for row in data["records"]:
            require(row.get("assignee_id") in people_by_id, "分配到未选定人员")
            person = people_by_id[row["assignee_id"]]
            case = self.cases[identity(row)]
            if method == "by_department":
                require(person["department"] == case["department"], "科室分配归属不符")
            elif method == "by_original_reviewer":
                require(person["user_id"] == case["reviewer_id"], "原质控员分配未采用正式最近审核人")
            elif method == "by_record_type":
                require(case["bucket"] in person["record_types"], "类型分配超出受领桶")
        repeat = self.request("POST", f"/api/v1/tasks/{task_id}/assign", payload)
        require(repeat.get("idempotent") is True, "重复分配不幂等")
        for person in self.people:
            env_key = self.token_env(person)
            token = os.environ.get(env_key)
            require(token, f"缺少受领回读 token 环境变量 {env_key}")
            expected = {row["id"] for row in data["records"] if row["assignee_id"] == person["user_id"]}
            if expected:
                received = self.detail(task_id, token=token, tab="received")
                require({row["id"] for row in received["records"]} == expected, "受领视图范围不符")
        self.checks.append(method)

    def run(self):
        self.preflight()
        if not self.execute:
            return
        require(self.manifest.get("source_sync_ready") is True,
                "尚未确认正式任务同步将远端合成源投影至本地 CDM")
        require(self.manifest.get("reviewer_facts_ready") is True,
                "reviewer_id 仅为预期；尚未确认正式生产者和受领审核事实")
        for person in self.people:
            env_key = self.token_env(person)
            require(os.environ.get(env_key), f"写入前缺少 {env_key}")
        methods = ["all", "count"] + [f"{group}_{mode}" for group in GROUPS for mode in ("count", "ratio")]
        for method in methods:
            params = {"total": 2} if method == "count" else {"total": 1} if method.endswith("_count") else {"percentage": 50, "max_per_group": 1} if method.endswith("_ratio") else {}
            task_id = self.create(self.payload(method, method, params))
            self.sample(task_id, set(self.cases), method)
            self.checks.append(method)
        for method in ("by_ratio", "by_department", "by_original_reviewer", "by_record_type"):
            task_id = self.create(self.payload(method, assignment=method))
            self.assign(task_id, method, self.sample(task_id, set(self.cases)))
        batch_tasks = []
        for index in range(2):
            task_id = self.create(self.payload(f"batch-type-{index}", assignment="by_record_type"))
            rows = self.sample(task_id, set(self.cases))
            batch_tasks.append((task_id, rows))
        batch = self.request("POST", "/api/v1/tasks/batch-assign", {
            "tasks": [{"task_id": task_id, "method": "by_record_type"} for task_id, _ in batch_tasks],
            "assignees": [{key: value for key, value in person.items()
                           if key in {"user_id", "user_name", "department", "record_types"}}
                          for person in self.people],
        })
        require(batch.get("success_count") == 2 and batch.get("failed_count") == 0
                and {item["task_id"] for item in batch.get("items", []) if item.get("success")} == {task_id for task_id, _ in batch_tasks},
                "批量类型分配回执不完整")
        for task_id, rows in batch_tasks:
            # 同策略单条回放只应返回幂等结果，并核对正式受领视图。
            self.assign(task_id, "by_record_type", rows, check_negative=False)
        self.checks.append("batch_by_record_type")
        specified = self.payload("specified")
        selected = list(self.cases)[:2]
        specified["record_refs"] = [dict(zip(IDENTITY, key)) for key in selected]
        self.sample(self.create(specified), set(selected))
        invalid = copy.deepcopy(specified)
        invalid["task_name"] += "-invalid-count"
        invalid.update(sampling_method="count")
        invalid["sampling_config"]["total"] = 1
        self.request("POST", "/api/v1/tasks", invalid, expected=422)
        self.checks.append("specified_set_and_reject_secondary_sampling")
        for scenario in self.manifest.get("scenarios", []):
            payload = copy.deepcopy(scenario["payload"])
            payload["task_name"] = f"{self.manifest['batch_prefix']}-{scenario['name']}"
            expected_status = scenario.get("expected_status", 200)
            if expected_status != 200:
                self.request("POST", "/api/v1/tasks", payload, expected=expected_status)
            else:
                selected = {identity(row) for row in scenario["expected_cases"]}
                self.sample(self.create(payload), selected, scenario.get("method", "all"))
            self.checks.append(scenario["name"])

    def review_bootstrap(self, artifacts):
        """只消费正式任务/受领运行引用；审核 Envelope 从当前 GET 返回读取。"""
        require(self.execute, "正式审核需要显式 --execute")
        require(self.manifest.get("source_sync_ready") is True, "正式同步尚未确认")
        seen = set()
        for task in artifacts["tasks"]:
            task_id = task["task_id"]
            run_number = task["run_number"]
            require(type(run_number) is int and run_number > 0 and task.get("job_id"), "正式运行引用缺失")
            owners = {self.cases[identity(row)]["reviewer_id"] for row in task["records"]}
            require(len(owners) == 1, "审核bootstrap任务存在多个预期受领人")
            person = next((row for row in self.people if row["user_id"] in owners), None)
            require(person is not None, "预期受领人不在本批manifest")
            token = os.environ.get(self.token_env(person))
            require(token, "缺少正式受领人token")
            live = self.detail(task_id, token=token, tab="received")
            wanted = {row["id"]: identity(row) for row in task["records"]}
            require({row["id"]: identity(row) for row in live["records"]} == wanted,
                    "正式受领详情与artifacts病例集合不同")
            self.request("PUT", f"/api/v1/tasks/{task_id}", {"status": "in_progress"}, token=token)
            for record_id, case_key in wanted.items():
                require(case_key not in seen, "审核前置病例重复")
                self.request("POST", f"/api/v1/tasks/{task_id}/records/{record_id}/start", token=token)
                path = f"/api/v1/tasks/{task_id}/records/{record_id}/review"
                view = self.request("GET", f"{path}?run_number={run_number}", token=token)
                result = view.get("result") or {}
                require(result.get("job_id") == task["job_id"] and result.get("envelope_id"),
                        "正式审核GET未返回匹配的job与Envelope")
                if not view.get("current"):
                    require(view.get("can_submit") is True, "当前结果不能提交正式审核")
                    request_id = str(uuid5(NAMESPACE_URL, f"{self.manifest['batch_prefix']}|{task_id}|{record_id}|{result['envelope_id']}"))
                    self.request("POST", path, {"run_number": run_number, "decision": "approved",
                                 "request_id": request_id, "envelope_id": result["envelope_id"]}, token=token)
                saved = self.request("GET", f"{path}?run_number={run_number}", token=token)
                current = saved.get("current") or {}
                require(saved.get("state") == "approved" and current.get("reviewer_id") == person["user_id"]
                        and current.get("envelope_id") == result["envelope_id"], "正式审核回读身份或结果对象不符")
                seen.add(case_key)
                print(json.dumps({"reviewed_task_record": record_id, "review_id": current.get("id")}, ensure_ascii=False))
        require(seen == set(self.cases), "八例正式审核前置未完整覆盖")
        self.checks.append("formal_assigned_record_reviews")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--execute", action="store_true", help="显式执行本批任务写入；不清理")
    parser.add_argument("--review-artifacts", type=Path, help="仅审核正式受领运行前置，不启动抽样矩阵")
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    require(parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment,
            "只允许本地 HTTP API，不接受凭据 URL")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    require(manifest.get("database") == TARGET_DATABASE, "manifest 非授权隔离库")
    require(re.fullmatch(r"[A-Za-z0-9_-]{3,80}", manifest.get("batch_prefix", "")), "批次前缀无效")
    require(8 <= len(manifest.get("cases", [])) <= 12, "需要 8-12 条合成源预期")
    require(len({identity(row) for row in manifest["cases"]}) == len(manifest["cases"]), "manifest 病例重复")
    require(manifest.get("assignees"), "缺少受领人")
    runner = Runner(manifest, args.base_url, args.execute)
    try:
        if args.review_artifacts:
            runner.preflight()
            runner.review_bootstrap(json.loads(args.review_artifacts.read_text(encoding="utf-8")))
        else:
            runner.run()
        print(json.dumps({"mode": "execute" if args.execute else "readonly_preflight",
                          "checks": runner.checks, "created_tasks": runner.tasks}, ensure_ascii=False))
    finally:
        runner.client.close()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, httpx.HTTPError, ValueError, KeyError) as exc:
        # 不打印 HTTP body、manifest 或带凭据的异常详情。
        print(json.dumps({"failed": type(exc).__name__, "reason": str(exc) if isinstance(exc, RuntimeError) else "输入或请求失败，请检查本地安全回执"}, ensure_ascii=False))
        raise SystemExit(1) from None
