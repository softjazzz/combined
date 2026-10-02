"""V3.6 隔离病例正式 HTTP 验收；默认只读，凭据只从进程环境读取。"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit
from uuid import NAMESPACE_URL, uuid5

import httpx

DATABASE = "medqc_v36_validation_20260924"
RECTIFICATIONS = "/api/v1/defect-rectifications"
COMMUNICATIONS = "/api/v1/case-communications"
IDENTITY_KEYS = ("institute_id", "patient_id", "visit_id")
SOURCE_KEYS = (*IDENTITY_KEYS, "scene", "root_job_id", "envelope_id")


class ProbeFailure(RuntimeError):
    """固定脱敏失败，不携带响应正文或认证信息。"""


def require(condition, label):
    if not condition:
        raise ProbeFailure(label)


def emit(step, **facts):
    print(json.dumps({"step": step, **facts}, ensure_ascii=False), flush=True)


def load_manifest(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), "manifest_invalid")
    require(value.get("database") == DATABASE, "isolation_database_mismatch")
    require(
        value.get("synthetic_case") is True, "synthetic_identity_confirmation_required"
    )
    fields = (*SOURCE_KEYS, "target_kind", "target_id", "assignee_id", "batch_prefix")
    require(
        all(isinstance(value.get(key), str) and value[key].strip() for key in fields),
        "manifest_missing_source",
    )
    require(value["scene"] in {"running", "final"}, "unsupported_scene")
    require(
        value["target_kind"] in {"canonical_defect", "task_manual_defect"},
        "unsupported_target",
    )
    require(
        bool(re.fullmatch(r"[A-Za-z0-9_-]{8,80}", value["batch_prefix"])),
        "batch_prefix_invalid",
    )
    require(
        not any("token" in key.lower() or "password" in key.lower() for key in value),
        "credentials_forbidden_in_manifest",
    )
    return value


class Probe:
    def __init__(self, client, manifest, *, execute=False, pause=False):
        self.client, self.manifest = client, manifest
        self.execute, self.pause = execute, pause
        self.identity = {key: manifest[key] for key in IDENTITY_KEYS}
        self.source = {key: manifest[key] for key in SOURCE_KEYS}
        self.batch = manifest["batch_prefix"]
        self.tokens = {
            "qc": os.environ.get("MEDQC_CASE_QC_TOKEN", ""),
            "doctor": os.environ.get("MEDQC_CASE_DOCTOR_TOKEN", ""),
        }
        require(all(self.tokens.values()), "actor_tokens_required_in_environment")

    def call(
        self, step, method, path, *, actor="qc", params=None, body=None, status=200
    ):
        require(method == "GET" or self.execute, "write_not_enabled")
        response = self.client.request(
            method,
            path,
            params=params,
            json=body,
            headers={"Authorization": f"Bearer {self.tokens[actor]}"},
        )
        emit(step, status=response.status_code)
        require(response.status_code == status, f"{step}_unexpected_http_status")
        if status != 200:
            return None
        payload = response.json()
        require(
            isinstance(payload, dict)
            and payload.get("success") is True
            and isinstance(payload.get("data"), dict),
            f"{step}_invalid_envelope",
        )
        return payload["data"]

    def checkpoint(self, stage):
        if self.pause:
            emit(stage, waiting_for="coordinator_synthetic_source_update")
            require(input().strip() == "continue", "checkpoint_not_confirmed")

    def preflight(self):
        candidates = self.call(
            "rectification_candidates",
            "GET",
            f"{RECTIFICATIONS}/candidates",
            params={**self.identity, "expected_job_id": self.source["root_job_id"]},
        )
        require(
            any(
                item.get("id") == self.manifest["assignee_id"]
                for item in candidates.get("doctors", [])
            ),
            "assignee_not_candidate",
        )
        self.target = next(
            (
                item
                for item in candidates.get("targets", [])
                if all(
                    item.get(key) == self.manifest[key]
                    for key in (
                        "target_kind",
                        "target_id",
                        "scene",
                        "root_job_id",
                        "envelope_id",
                    )
                )
            ),
            None,
        )
        require(self.target is not None, "frozen_target_not_candidate")
        source = {
            **self.source,
            "target_kind": self.manifest["target_kind"],
            "target_id": self.manifest["target_id"],
        }
        existing = self.call(
            "target_not_dispatched",
            "GET",
            RECTIFICATIONS,
            params={**source, "page_size": 100},
        )
        require(existing.get("total") == 0, "target_already_dispatched_do_not_repeat")
        old_job = self.manifest.get("old_root_job_id")
        if old_job:
            require(old_job != self.source["root_job_id"], "old_job_equals_current")
            self.call(
                "old_round_candidate_rejected",
                "GET",
                f"{RECTIFICATIONS}/candidates",
                params={**self.identity, "expected_job_id": old_job},
                status=409,
            )
        evidence = self.manifest.get("evidence_document")
        if evidence:
            require(
                isinstance(evidence, dict)
                and all(
                    evidence.get(key)
                    for key in ("execution_domain", "doc_type", "doc_id")
                ),
                "evidence_manifest_invalid",
            )
            visit = quote(self.identity["visit_id"], safe="")
            documents = self.call(
                "saved_document_directory",
                "GET",
                f"/api/v1/emr/{visit}/documents",
                params={**self.identity, "view": "summary"},
            )
            require(bool(documents.get("documents")), "saved_documents_unavailable")
            rendered = self.call(
                "saved_evidence_document",
                "GET",
                f"/api/v1/emr/{visit}/render",
                params={**self.identity, **evidence},
            )
            require(
                not rendered.get("empty_reason") and bool(rendered.get("content")),
                "evidence_document_unavailable",
            )
            emit("evidence_api_ready", browser_highlight_verified=False)
        emit("read_only_preflight_complete", database=DATABASE, batch=self.batch)

    def detail(self):
        return self.call(
            "rectification_detail", "GET", f"{RECTIFICATIONS}/{self.task['id']}"
        )

    def action(self, action, actor="qc", urge=None):
        old = self.task["version"]
        body = {
            "version": old,
            "action": action,
            "comment": f"{self.batch} 合成隔离验收动作 {action}",
        }
        if urge:
            body["urge_event_id"] = urge
        self.task = self.call(
            f"rectification_{action}",
            "POST",
            f"{RECTIFICATIONS}/{self.task['id']}/actions",
            actor=actor,
            body=body,
        )
        require(
            self.task.get("version") == old + 1, "rectification_version_not_incremented"
        )
        expected = {
            "urge": "pending",
            "withdraw_urge": "pending",
            "submit": "submitted",
            "reject": "rejected",
            "approve": "approved",
        }[action]
        require(self.task.get("status") == expected, "rectification_state_mismatch")

    def comparison(self, event_id, step):
        value = self.call(
            step,
            "GET",
            f"{RECTIFICATIONS}/{self.task['id']}/comparison",
            params={"event_id": event_id},
        )
        require(
            value.get("available") is True and bool(value.get("documents")),
            "comparison_snapshot_unavailable",
        )
        return value

    def rectification_chain(self):
        body = {
            **self.source,
            "target_kind": self.manifest["target_kind"],
            "target_id": self.manifest["target_id"],
            "assignee_id": self.manifest["assignee_id"],
            "requirement": f"{self.batch} 合成隔离病例整改验收要求",
        }
        self.task = self.call("rectification_assign", "POST", RECTIFICATIONS, body=body)
        require(
            self.task.get("status") == "pending" and self.task.get("version") == 1,
            "assignment_initial_state_invalid",
        )
        emit("assignment_receipt", task_id=self.task["id"], version=1)
        self.action("urge")
        urged = self.detail()
        event = next(
            (
                row
                for row in urged["events"]
                if row["action"] == "urge" and row.get("can_withdraw")
            ),
            None,
        )
        require(event is not None, "active_urge_event_missing")
        self.action("withdraw_urge", urge=event["id"])
        require(
            not any(row.get("can_withdraw") for row in self.detail()["events"]),
            "withdrawal_not_effective",
        )
        self.checkpoint("before_first_submit")
        self.action("submit", "doctor")
        first_event = next(
            row for row in self.detail()["events"] if row["action"] == "submit"
        )
        first = self.comparison(first_event["id"], "first_submission_comparison")
        self.action("reject")
        self.checkpoint("before_second_submit")
        self.action("submit", "doctor")
        events = self.detail()["events"]
        submissions = [row for row in events if row["action"] == "submit"]
        require(
            len(submissions) == 2 and submissions[0]["id"] != submissions[1]["id"],
            "submission_history_missing",
        )
        second = self.comparison(submissions[1]["id"], "second_submission_comparison")
        require(
            self.comparison(first_event["id"], "first_snapshot_preserved") == first,
            "first_submission_snapshot_overwritten",
        )
        if self.manifest.get("expect_document_changes") is True:
            require(
                any(row["before"] != row["after"] for row in first["documents"]),
                "first_source_change_missing",
            )
            require(
                first["documents"] != second["documents"],
                "second_source_change_missing",
            )
        self.action("approve")
        final = self.detail()
        require(
            [row["action"] for row in final["events"]]
            == [
                "assign",
                "urge",
                "withdraw_urge",
                "submit",
                "reject",
                "submit",
                "approve",
            ],
            "rectification_event_chain_mismatch",
        )
        self.rectification_event_ids = {
            f"rectification_event:{row['id']}" for row in final["events"]
        }
        emit(
            "rectification_chain_complete",
            task_id=self.task["id"],
            events=len(final["events"]),
        )

    def communication_chain(self):
        candidates = self.call(
            "communication_candidates",
            "POST",
            f"{COMMUNICATIONS}/candidates",
            body={
                key: self.source[key]
                for key in (*IDENTITY_KEYS, "scene", "root_job_id")
            },
        )
        require(
            all(
                candidates["source"].get(key) == value
                for key, value in self.source.items()
            ),
            "communication_source_mismatch",
        )
        require(
            any(
                row.get("id") == self.manifest["assignee_id"]
                for row in candidates.get("doctors", [])
            ),
            "communication_doctor_missing",
        )
        notices = []
        for action in ("urge", "opinion"):
            body = {
                **self.source,
                "recipient_id": self.manifest["assignee_id"],
                "action": action,
                "content": f"{self.batch} 合成病例沟通 {action}",
                "request_id": str(uuid5(NAMESPACE_URL, f"{self.batch}:{action}")),
            }
            notice = self.call(
                f"communication_{action}", "POST", COMMUNICATIONS, body=body
            )
            require(
                notice.get("is_read") is False and bool(notice.get("notification_id")),
                "communication_notification_missing",
            )
            notices.append(notice)
        inbox = self.call(
            "doctor_inbox",
            "GET",
            f"{COMMUNICATIONS}/inbox",
            actor="doctor",
            params={"page_size": 100},
        )
        require(
            {row["id"] for row in notices}
            <= {row["id"] for row in inbox.get("items", [])},
            "notification_not_in_inbox",
        )
        for notice in notices:
            path = f"{COMMUNICATIONS}/{notice['id']}"
            self.call("doctor_notice_detail", "GET", path, actor="doctor")
            read = self.call(
                "doctor_notice_read", "POST", f"{path}/read", actor="doctor"
            )
            require(
                read.get("is_read") is True and bool(read.get("read_at")),
                "notification_read_missing",
            )
            require(
                self.call("doctor_read_persisted", "GET", path, actor="doctor").get(
                    "is_read"
                )
                is True,
                "notification_read_not_persisted",
            )
        urge = notices[0]
        withdrawal = self.call(
            "case_urge_withdraw",
            "POST",
            COMMUNICATIONS,
            body={
                **self.source,
                "recipient_id": self.manifest["assignee_id"],
                "action": "withdraw",
                "related_event_id": urge["id"],
                "content": f"{self.batch} 合成病例催办撤回",
                "request_id": str(uuid5(NAMESPACE_URL, f"{self.batch}:withdraw")),
            },
        )
        inbox = self.call(
            "doctor_inbox_after_withdraw",
            "GET",
            f"{COMMUNICATIONS}/inbox",
            actor="doctor",
            params={"page_size": 100},
        )
        require(
            urge["id"] not in {row["id"] for row in inbox.get("items", [])},
            "withdrawn_urge_still_in_inbox",
        )
        self.communication_event_ids = {
            *(f"case_communication:{row['id']}" for row in notices),
            f"case_communication:{withdrawal['id']}",
            *(f"notification_read:{row['notification_id']}" for row in notices),
        }
        emit("communication_chain_complete", messages=len(notices))

    def timeline(self):
        value = self.call(
            "case_operation_timeline",
            "GET",
            "/api/v1/record-operations/case",
            params={**self.identity, "limit": 200},
        )
        ids = {row["id"] for row in value.get("items", [])}
        require(
            self.rectification_event_ids <= ids, "rectification_timeline_events_missing"
        )
        if hasattr(self, "communication_event_ids"):
            require(
                self.communication_event_ids <= ids,
                "communication_timeline_events_missing",
            )
        emit(
            "timeline_verified",
            database=DATABASE,
            batch=self.batch,
            browser_verified=False,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--execute", action="store_true", help="主协调授权后启用正式写接口"
    )
    parser.add_argument(
        "--pause-before-submit",
        action="store_true",
        help="两次提交前等主协调更新合成源，stdin 输入 continue",
    )
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    require(
        url.scheme == "http"
        and url.hostname in {"127.0.0.1", "localhost", "::1"}
        and not url.username
        and not url.password
        and url.path in {"", "/"}
        and not url.query
        and not url.fragment,
        "local_api_url_required",
    )
    manifest = load_manifest(args.manifest)
    # 数据库绑定由主协调预检本地服务；本脚本不读取或打印 DSN、不调用数据库。
    with httpx.Client(
        base_url=args.base_url, timeout=90, follow_redirects=False, trust_env=False
    ) as client:
        probe = Probe(
            client, manifest, execute=args.execute, pause=args.pause_before_submit
        )
        probe.preflight()
        if args.execute:
            probe.rectification_chain()
            probe.timeline()
            probe.communication_chain()
            probe.timeline()
            emit(
                "case_chain_complete",
                database=DATABASE,
                batch=probe.batch,
                browser_verified=False,
            )
        else:
            emit("writes_disabled", next_step="coordinator_authorization_and_execute")


if __name__ == "__main__":
    try:
        main()
    except (
        ProbeFailure,
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
        StopIteration,
        EOFError,
        OSError,
    ) as error:
        emit(
            "failed",
            reason=str(error)
            if isinstance(error, ProbeFailure)
            else type(error).__name__,
        )
        sys.exit(1)
