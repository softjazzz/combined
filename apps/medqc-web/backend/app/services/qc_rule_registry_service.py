from __future__ import annotations

import json
import logging
import uuid
import hashlib
from pathlib import Path
from typing import Any

from sqlalchemy import text

from ..database.connection import SessionLocal

logger = logging.getLogger(__name__)

_PUBLISH_ACTIONS = {"publish", "published", "promote", "stable", "activate"}
_INACTIVE_ACTIONS = {"rollback", "unpublish", "deprecate", "archive", "disable"}
_PREFERRED_STATUSES = {"published", "stable"}

_DEFAULT_RULE_VERSION = "2026.04.p0"
_DEFAULT_PROMPT_VERSION = "default-v1"

_REQUIRED_RULE_FIELDS = (
    "rule_id",
    "name",
    "description",
    "category",
    "complexity",
    "defect_level",
    "applicable_documents",
    "custom_prompt",
    "executor_type",
    "execution_domain",
    "doc_scope",
    "rule_version",
    "prompt_version",
    "cost_class",
)


class QCRuleRegistryService:
    """规则注册表服务：优先读取 PG 治理表，失败时回退 JSON 文件。"""

    def __init__(
        self,
        *,
        session_factory=SessionLocal,
        json_path: str | Path | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._json_path = (
            Path(json_path)
            if json_path is not None
            else Path(__file__).resolve().parent.parent / "data" / "sichuan_rules_146.json"
        )

    def load_active_rules(self) -> tuple[list[dict[str, Any]], str]:
        """加载可用规则，返回 (rules, source)。"""
        pg_rules = self._load_active_rules_from_pg()
        if pg_rules:
            return pg_rules, "pg_governance"

        json_rules = self._load_rules_from_json()
        return json_rules, "json_file"

    def load_rule_by_id(self, rule_id: str) -> tuple[dict[str, Any] | None, str]:
        """按 rule_id 获取规则。"""
        normalized = str(rule_id or "").strip().upper()
        if not normalized:
            rules, source = self.load_active_rules()
            return None, source

        rules, source = self.load_active_rules()
        for rule in rules:
            rid = str(rule.get("rule_id") or "").strip().upper()
            if rid == normalized:
                return rule, source
        return None, source

    def list_publish_history(self, rule_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """查询发布历史（仅 PG 可用时返回数据）。"""
        if self._session_factory is None:
            return []

        rows: list[dict[str, Any]] = []
        session = self._session_factory()
        try:
            params: dict[str, Any] = {"limit": max(1, int(limit or 50))}
            where = ""
            if str(rule_id or "").strip():
                where = "WHERE rule_id = :rule_id"
                params["rule_id"] = str(rule_id).strip()
            sql = text(
                f"""
                SELECT id, rule_id, rule_version_id, action, reason, operator, created_at
                FROM qc.qc_rule_publish_history
                {where}
                ORDER BY created_at DESC
                LIMIT :limit
                """
            )
            rows = [dict(row) for row in session.execute(sql, params).mappings().all()]
        except Exception as exc:
            logger.warning("读取规则发布历史失败: %s", exc, exc_info=True)
            return []
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

        return rows

    def bootstrap_rules_from_json_to_pg(
        self,
        *,
        operator: str = "system",
        mark_published: bool = True,
    ) -> dict[str, int]:
        """
        将 JSON 规则批量导入治理表（幂等增量）。
        - 若同 rule_id 最新版本 checksum 一致：跳过
        - 若不一致：新增 version_no+1，并可写 publish_history
        """
        if self._session_factory is None:
            return {"inserted": 0, "skipped": 0, "published": 0}

        rules = self._load_rules_from_json()
        if not rules:
            return {"inserted": 0, "skipped": 0, "published": 0}

        inserted = 0
        skipped = 0
        published = 0
        session = self._session_factory()
        try:
            for rule in rules:
                rule_id = str(rule.get("rule_id") or "").strip()
                if not rule_id:
                    skipped += 1
                    continue
                payload_json = json.dumps(rule, ensure_ascii=False, separators=(",", ":"))
                checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
                latest_row = (
                    session.execute(
                        text(
                            """
                            SELECT id, version_no, checksum
                            FROM qc.qc_rule_versions
                            WHERE rule_id = :rule_id
                            ORDER BY version_no DESC
                            LIMIT 1
                            """
                        ),
                        {"rule_id": rule_id},
                    )
                    .mappings()
                    .first()
                )
                if latest_row and str(latest_row.get("checksum") or "").strip() == checksum:
                    skipped += 1
                    continue

                latest_ver = int(latest_row.get("version_no") or 0) if latest_row else 0
                version_no = latest_ver + 1
                version_id = str(uuid.uuid4())
                status = "published" if mark_published else "draft"
                session.execute(
                    text(
                        """
                        INSERT INTO qc.qc_rule_versions
                          (id, rule_id, version_no, status, payload_json, checksum, created_by, created_at)
                        VALUES
                          (:id, :rule_id, :version_no, :status, :payload_json, :checksum, :created_by, NOW())
                        """
                    ),
                    {
                        "id": version_id,
                        "rule_id": rule_id,
                        "version_no": version_no,
                        "status": status,
                        "payload_json": payload_json,
                        "checksum": checksum,
                        "created_by": str(operator or "system"),
                    },
                )
                inserted += 1

                if mark_published:
                    session.execute(
                        text(
                            """
                            INSERT INTO qc.qc_rule_publish_history
                              (id, rule_id, rule_version_id, action, reason, operator, created_at)
                            VALUES
                              (:id, :rule_id, :rule_version_id, 'publish', :reason, :operator, NOW())
                            """
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "rule_id": rule_id,
                            "rule_version_id": version_id,
                            "reason": "bootstrap from json source",
                            "operator": str(operator or "system"),
                        },
                    )
                    published += 1

            commit = getattr(session, "commit", None)
            if callable(commit):
                commit()
        except Exception:
            rollback = getattr(session, "rollback", None)
            if callable(rollback):
                rollback()
            raise
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

        return {"inserted": inserted, "skipped": skipped, "published": published}

    def list_rule_versions(self, rule_id: str, limit: int = 20) -> list[dict[str, Any]]:
        if self._session_factory is None:
            return []
        rid = str(rule_id or "").strip()
        if not rid:
            return []
        session = self._session_factory()
        try:
            rows = (
                session.execute(
                    text(
                        """
                        SELECT id, rule_id, version_no, status, checksum, created_by, created_at
                        FROM qc.qc_rule_versions
                        WHERE rule_id = :rule_id
                        ORDER BY version_no DESC
                        LIMIT :limit
                        """
                    ),
                    {"rule_id": rid, "limit": max(1, int(limit or 20))},
                )
                .mappings()
                .all()
            )
            return [dict(row) for row in rows]
        except Exception as exc:
            logger.warning("读取规则版本失败: rule_id=%s err=%s", rid, exc, exc_info=True)
            return []
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

    def publish_rule_version(
        self,
        *,
        rule_id: str,
        version_no: int,
        operator: str = "system",
        reason: str = "manual publish",
    ) -> bool:
        return self._apply_publish_action(
            action="publish",
            rule_id=rule_id,
            version_no=version_no,
            operator=operator,
            reason=reason,
        )

    def rollback_rule_version(
        self,
        *,
        rule_id: str,
        version_no: int,
        operator: str = "system",
        reason: str = "manual rollback",
    ) -> bool:
        return self._apply_publish_action(
            action="rollback",
            rule_id=rule_id,
            version_no=version_no,
            operator=operator,
            reason=reason,
        )

    def update_rule_prompt_version(
        self,
        *,
        rule_id: str,
        custom_prompt: str | None,
        operator: str = "system",
    ) -> bool:
        """
        在治理表为规则追加新版本并发布（仅 PG 可用时生效）。
        """
        if self._session_factory is None:
            return False
        rid = str(rule_id or "").strip()
        if not rid:
            return False
        session = self._session_factory()
        try:
            latest = (
                session.execute(
                    text(
                        """
                        SELECT id, version_no, payload_json, checksum
                        FROM qc.qc_rule_versions
                        WHERE rule_id = :rule_id
                        ORDER BY version_no DESC
                        LIMIT 1
                        """
                    ),
                    {"rule_id": rid},
                )
                .mappings()
                .first()
            )
            if not latest:
                return False
            payload = self._parse_payload(latest.get("payload_json")) or {}
            if custom_prompt is None:
                payload.pop("custom_prompt", None)
                payload["prompt_version"] = "default-v1"
            else:
                payload["custom_prompt"] = str(custom_prompt)
                payload["prompt_version"] = "custom-v1"

            payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            checksum = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            if str(latest.get("checksum") or "").strip() == checksum:
                return True

            version_no = int(latest.get("version_no") or 0) + 1
            version_id = str(uuid.uuid4())
            session.execute(
                text(
                    """
                    INSERT INTO qc.qc_rule_versions
                      (id, rule_id, version_no, status, payload_json, checksum, created_by, created_at)
                    VALUES
                      (:id, :rule_id, :version_no, 'published', :payload_json, :checksum, :created_by, NOW())
                    """
                ),
                {
                    "id": version_id,
                    "rule_id": rid,
                    "version_no": version_no,
                    "payload_json": payload_json,
                    "checksum": checksum,
                    "created_by": str(operator or "system"),
                },
            )
            session.execute(
                text(
                    """
                    INSERT INTO qc.qc_rule_publish_history
                      (id, rule_id, rule_version_id, action, reason, operator, created_at)
                    VALUES
                      (:id, :rule_id, :rule_version_id, 'publish', :reason, :operator, NOW())
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "rule_id": rid,
                    "rule_version_id": version_id,
                    "reason": "prompt update",
                    "operator": str(operator or "system"),
                },
            )
            commit = getattr(session, "commit", None)
            if callable(commit):
                commit()
            return True
        except Exception as exc:
            rollback = getattr(session, "rollback", None)
            if callable(rollback):
                rollback()
            logger.warning("更新规则提示词版本失败: rule_id=%s err=%s", rid, exc, exc_info=True)
            return False
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

    def _load_active_rules_from_pg(self) -> list[dict[str, Any]]:
        if self._session_factory is None:
            return []

        session = self._session_factory()
        try:
            version_rows = [
                dict(row)
                for row in session.execute(
                    text(
                        """
                        SELECT id, rule_id, version_no, status, payload_json, created_at
                        FROM qc.qc_rule_versions
                        """
                    )
                )
                .mappings()
                .all()
            ]
            if not version_rows:
                return []

            publish_rows = [
                dict(row)
                for row in session.execute(
                    text(
                        """
                        SELECT rule_id, rule_version_id, action, created_at
                        FROM qc.qc_rule_publish_history
                        ORDER BY created_at DESC
                        """
                    )
                )
                .mappings()
                .all()
            ]
        except Exception as exc:
            logger.warning("读取 PG 治理规则失败，回退 JSON: %s", exc, exc_info=True)
            return []
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()

        selected_rows = self._pick_active_versions(version_rows, publish_rows)
        rules: list[dict[str, Any]] = []
        for row in selected_rows:
            normalized = self._normalize_rule_payload(
                row.get("payload_json"),
                fallback_rule_id=row.get("rule_id"),
                fallback_version_no=row.get("version_no"),
            )
            if normalized is not None:
                rules.append(normalized)

        return rules

    def _pick_active_versions(
        self,
        version_rows: list[dict[str, Any]],
        publish_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        by_rule: dict[str, list[dict[str, Any]]] = {}
        by_version_id: dict[str, dict[str, Any]] = {}

        for row in version_rows:
            rule_key = str(row.get("rule_id") or "").strip()
            if not rule_key:
                continue
            by_rule.setdefault(rule_key, []).append(row)
            version_id = str(row.get("id") or "").strip()
            if version_id:
                by_version_id[version_id] = row

        publish_choice: dict[str, str | None] = {}
        for row in publish_rows:
            rule_key = str(row.get("rule_id") or "").strip()
            if not rule_key or rule_key in publish_choice:
                continue
            action = str(row.get("action") or "").strip().lower()
            if action in _PUBLISH_ACTIONS:
                publish_choice[rule_key] = str(row.get("rule_version_id") or "").strip() or None
            elif action in _INACTIVE_ACTIONS:
                publish_choice[rule_key] = None

        selected: list[dict[str, Any]] = []
        for rule_key, rows in by_rule.items():
            candidate: dict[str, Any] | None = None

            if rule_key in publish_choice:
                publish_version_id = publish_choice[rule_key]
                if publish_version_id:
                    candidate = by_version_id.get(publish_version_id)
                else:
                    # 最近动作为下线，视为无 active 版本
                    continue

            if candidate is None:
                preferred = [
                    row
                    for row in rows
                    if str(row.get("status") or "").strip().lower() in _PREFERRED_STATUSES
                ]
                if preferred:
                    candidate = max(preferred, key=self._rule_sort_key)

            if candidate is None:
                candidate = max(rows, key=self._rule_sort_key)

            selected.append(candidate)

        selected.sort(key=lambda row: str(row.get("rule_id") or ""))
        return selected

    @staticmethod
    def _rule_sort_key(row: dict[str, Any]) -> tuple[int, str]:
        try:
            version_no = int(row.get("version_no") or 0)
        except Exception:
            version_no = 0
        created_at = str(row.get("created_at") or "")
        return version_no, created_at

    def _load_rules_from_json(self) -> list[dict[str, Any]]:
        try:
            raw = json.loads(self._json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.error("读取 JSON 规则失败: %s", exc, exc_info=True)
            return []

        rules: list[dict[str, Any]] = []
        for item in raw if isinstance(raw, list) else []:
            normalized = self._normalize_rule_payload(item)
            if normalized is not None:
                rules.append(normalized)
        return rules

    def _normalize_rule_payload(
        self,
        payload: Any,
        *,
        fallback_rule_id: Any = None,
        fallback_version_no: Any = None,
    ) -> dict[str, Any] | None:
        parsed = self._parse_payload(payload)
        if parsed is None:
            return None

        normalized: dict[str, Any] = dict(parsed)
        rid = (
            str(normalized.get("rule_id") or "").strip()
            or str(fallback_rule_id or "").strip()
            or str(normalized.get("rule_code") or "").strip()
        )
        if not rid:
            return None

        custom_prompt = str(normalized.get("custom_prompt") or "").strip()
        executor_type = str(normalized.get("executor_type") or "").strip().lower() or "llm"
        rule_version = str(normalized.get("rule_version") or "").strip()
        if not rule_version:
            if fallback_version_no is not None and str(fallback_version_no).strip():
                rule_version = f"v{fallback_version_no}"
            else:
                rule_version = _DEFAULT_RULE_VERSION

        prompt_version = str(normalized.get("prompt_version") or "").strip()
        if not prompt_version:
            prompt_version = "custom-v1" if custom_prompt else _DEFAULT_PROMPT_VERSION

        cost_class = str(normalized.get("cost_class") or "").strip()
        if not cost_class:
            cost_class = "low" if executor_type == "program" else "medium"

        normalized.update(
            {
                "rule_id": rid,
                "name": str(normalized.get("name") or "").strip(),
                "description": str(normalized.get("description") or "").strip(),
                "category": str(normalized.get("category") or "").strip(),
                "complexity": str(normalized.get("complexity") or "").strip(),
                "defect_level": str(normalized.get("defect_level") or "").strip(),
                "applicable_documents": self._normalize_documents(normalized.get("applicable_documents")),
                "custom_prompt": custom_prompt,
                "executor_type": executor_type,
                "execution_domain": str(normalized.get("execution_domain") or "").strip(),
                "doc_scope": str(normalized.get("doc_scope") or "").strip() or "primary",
                "rule_version": rule_version,
                "prompt_version": prompt_version,
                "cost_class": cost_class,
            }
        )

        for required in _REQUIRED_RULE_FIELDS:
            normalized.setdefault(required, "" if required != "applicable_documents" else [])

        return normalized

    @staticmethod
    def _parse_payload(payload: Any) -> dict[str, Any] | None:
        if isinstance(payload, dict):
            return dict(payload)
        if isinstance(payload, str):
            text_payload = payload.strip()
            if not text_payload:
                return None
            try:
                decoded = json.loads(text_payload)
            except Exception:
                logger.warning("规则 payload_json 反序列化失败")
                return None
            if isinstance(decoded, dict):
                return decoded
            return None
        return None

    @staticmethod
    def _normalize_documents(documents: Any) -> list[str]:
        if isinstance(documents, list):
            return [str(item).strip() for item in documents if str(item).strip()]
        if isinstance(documents, str):
            text_value = documents.strip()
            return [text_value] if text_value else []
        return []

    def _apply_publish_action(
        self,
        *,
        action: str,
        rule_id: str,
        version_no: int,
        operator: str,
        reason: str,
    ) -> bool:
        if self._session_factory is None:
            return False
        rid = str(rule_id or "").strip()
        if not rid:
            return False
        session = self._session_factory()
        try:
            target = (
                session.execute(
                    text(
                        """
                        SELECT id
                        FROM qc.qc_rule_versions
                        WHERE rule_id = :rule_id AND version_no = :version_no
                        LIMIT 1
                        """
                    ),
                    {"rule_id": rid, "version_no": int(version_no)},
                )
                .mappings()
                .first()
            )
            if not target:
                return False
            version_id = str(target.get("id") or "")
            session.execute(
                text(
                    """
                    UPDATE qc.qc_rule_versions
                    SET status = 'published'
                    WHERE id = :version_id
                    """
                ),
                {"version_id": version_id},
            )
            session.execute(
                text(
                    """
                    INSERT INTO qc.qc_rule_publish_history
                      (id, rule_id, rule_version_id, action, reason, operator, created_at)
                    VALUES
                      (:id, :rule_id, :rule_version_id, :action, :reason, :operator, NOW())
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "rule_id": rid,
                    "rule_version_id": version_id,
                    "action": str(action),
                    "reason": str(reason or ""),
                    "operator": str(operator or "system"),
                },
            )
            commit = getattr(session, "commit", None)
            if callable(commit):
                commit()
            return True
        except Exception as exc:
            rollback = getattr(session, "rollback", None)
            if callable(rollback):
                rollback()
            logger.warning("规则发布动作失败: action=%s rule_id=%s err=%s", action, rid, exc, exc_info=True)
            return False
        finally:
            close = getattr(session, "close", None)
            if callable(close):
                close()


_default_registry_service = QCRuleRegistryService()


def load_active_rules() -> tuple[list[dict[str, Any]], str]:
    return _default_registry_service.load_active_rules()


def load_rule_by_id(rule_id: str) -> tuple[dict[str, Any] | None, str]:
    return _default_registry_service.load_rule_by_id(rule_id)


def list_publish_history(rule_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    return _default_registry_service.list_publish_history(rule_id=rule_id, limit=limit)
