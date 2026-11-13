"""固定 d7dc325b7 的只读合同闭包；无连接工厂、写入或重判入口。

抽取函数保持源代码；固定投影仅允许两张批准目标表。变更须复核同步合同。
"""
from __future__ import annotations
import base64
import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from types import SimpleNamespace

SOURCE_COMMIT = "d7dc325b7dee82dcc2215b9b68dfbb797f57dea5"
CONTRACT = "daily-material-r2-v3"
SOURCES = ("cache", "clinical")
PostgresSettings = Any
InterfaceSpec = Any
PublishSpec = Any
ClinicalContract = Any

CACHE_COLUMNS = ('institute_id', 'patient_id', 'visit_id', 'visit_type', 'name', 'sex', 'inpat_no', 'mr_no', 'document_id', 'document_title', 'document_status', 'submitter', 'submitter_id', 'submit_datetime', 'record_content', 'last_modifier', 'last_modifier_id', 'last_modified_datetime', 'update_time', 'record_datetime', 'age_year', 'physician_sign', 'physician_sign_datetime')
CLINICAL_COLUMNS = ('institute_id', 'patient_id', 'visit_id', 'document_id', 'document_title', 'record_content', 'record_time', 'submit_time', 'modified_time', 'source_status', 'source_payload')


def _ident(value):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", value):
        raise ValueError("invalid_readonly_identifier")
    return '"' + value + '"'


def resolve_interface(name):
    if name != "web.daily_course_record":
        raise ValueError("unsupported_readonly_projection")
    return SimpleNamespace(publish=SimpleNamespace(schema="cdm", table="daily_course_record", target_columns=CACHE_COLUMNS))


def clinical_contract():
    return SimpleNamespace(spec=SimpleNamespace(publish=SimpleNamespace(schema="sync_material", table="clinical_daily_current", target_columns=CLINICAL_COLUMNS)))



class ErrorKind(str, Enum):
    CONFIGURATION = "configuration_error"
    INTERFACE = "interface_not_registered"
    SOURCE_CONNECT = "source_connect_error"
    SOURCE_QUERY = "source_query_error"
    SCHEMA = "schema_validation_error"
    KEY = "key_validation_error"
    LOCK = "lock_conflict"
    INGEST_CONNECT = "ingest_connect_error"
    INGEST_WRITE = "ingest_write_error"
    PUBLISH_CONTRACT = "publish_contract_error"
    CDM_CONNECT = "cdm_connect_error"
    CDM_WRITE = "cdm_write_error"
    UNEXPECTED = "unexpected_error"


ERROR_KINDS = frozenset(item.value for item in ErrorKind)


class IngestError(Exception):
    """只携带受控类别和静态位置，不携带驱动异常或数据原文。"""

    def __init__(self, kind: ErrorKind | str, location: str) -> None:
        value = kind.value if isinstance(kind, ErrorKind) else kind
        self.kind = value if value in ERROR_KINDS else ErrorKind.UNEXPECTED.value
        self.location = location
        super().__init__(f"{self.kind} at {location}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize(value: Any) -> Any:
    """生成可跨平台比较的 JSON 形态。"""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return {"$type": "float", "text": "NaN"}
        if math.isinf(value):
            return {"$type": "float", "text": "Infinity" if value > 0 else "-Infinity"}
        return value
    if isinstance(value, (bytes, bytearray)):
        return {"$type": "bytes", "b64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, Decimal):
        return {"$type": "decimal", "text": format(value, "f")}
    if isinstance(value, datetime):
        return {"$type": "datetime", "iso": value.isoformat()}
    if isinstance(value, date):
        return {"$type": "date", "iso": value.isoformat()}
    return {"$type": "str", "text": str(value)}


def require(condition: bool, location: str) -> None:
    if not condition:
        raise IngestError(ErrorKind.CONFIGURATION, location)


def independent_database(settings: PostgresSettings, role: str) -> None:
    production = settings.database == "medqc_sync_" + role and settings.port == 5432
    synthetic = (
        bool(re.fullmatch("delivery_" + role + r"_[a-f0-9]{12}", settings.database))
        and settings.port != 5432
    )
    require(
        settings.host == "127.0.0.1" and (production or synthetic),
        "clinical_independent_" + role + "_required",
    )


def digest(value: Any) -> str:
    return sha256_hex(canonical_json(value))


@dataclass(frozen=True)
class CasePolicy:
    """一个批准病例；原机构值不被改写，canonical身份由批准映射单独提供。"""

    canonical_case: tuple[str, str, str]
    native_cases: tuple[tuple[str, str, str, str], ...]
    identity_version: str
    type_version: str
    rule_version: str
    approval_id: str
    # 显式同文书映射，不凭同号或正文自动认定。元素为cache/clinical完整源键JSON。
    links: tuple[tuple[str, str, str], ...] = ()
    # (来源, 源状态原值或None, 已批准语义)，未知状态不可用于等价确认。
    status_rules: tuple[tuple[str, str | None, str], ...] = ()
    shared_document_key_contract: str | None = None
    # 各类型需要比较的额外源字段，必须显式列出；缺列不能默认为相等。
    equivalence_fields: tuple[tuple[str, str], ...] = ()
    # 仅批准字段双方NULL可表示不适用；不能把缺列、空串或单边NULL放行。
    not_applicable_fields: tuple[tuple[str, str, str], ...] = ()
    # 首轮逐文书批准类型，不能以所在表名或unresolved_type自动批准。
    clinical_type_approvals: tuple[tuple[str, str, str], ...] = ()

    def validate(self) -> None:
        require(
            len(self.canonical_case) == 3
            and all(isinstance(v, str) and v.strip() for v in self.canonical_case),
            "material_canonical_identity",
        )
        require(
            bool(self.native_cases) and len(set(self.native_cases)) == len(self.native_cases),
            "material_native_cases",
        )
        require(
            all(
                len(k) == 4 and k[0] in SOURCES and all(isinstance(v, str) and v.strip() for v in k)
                for k in self.native_cases
            ),
            "material_native_identity",
        )
        require(
            all(
                isinstance(v, str) and v.strip()
                for v in (
                    self.identity_version,
                    self.type_version,
                    self.rule_version,
                    self.approval_id,
                )
            ),
            "material_policy_approval",
        )
        require(
            len({(s, v) for s, v, _ in self.status_rules}) == len(self.status_rules),
            "material_status_mapping_ambiguous",
        )
        require(
            all(
                s in SOURCES and isinstance(meaning, str) and meaning.strip()
                for s, _, meaning in self.status_rules
            ),
            "material_status_mapping",
        )
        require(
            self.shared_document_key_contract is None
            or bool(self.shared_document_key_contract.strip()),
            "material_shared_key_contract",
        )
        require(
            len(set(self.equivalence_fields)) == len(self.equivalence_fields)
            and all(a.strip() and b.strip() for a, b in self.equivalence_fields),
            "material_equivalence_fields",
        )
        require(
            len({(a, b) for a, b, _ in self.not_applicable_fields})
            == len(self.not_applicable_fields)
            and all(
                (a, b) in self.equivalence_fields and evidence.strip()
                for a, b, evidence in self.not_applicable_fields
            ),
            "material_not_applicable_contract",
        )
        require(
            len({k for k, _, _ in self.clinical_type_approvals})
            == len(self.clinical_type_approvals),
            "material_type_approval_ambiguous",
        )
        for key, kind, evidence in self.clinical_type_approvals:
            import json

            parts = json.loads(key)
            require(
                isinstance(parts, list)
                and len(parts) == 4
                and ("clinical", *parts[:3]) in self.native_cases
                and kind == "daily_course_record"
                and bool(evidence.strip()),
                "material_type_approval",
            )
        cache_keys, clinical_keys = [], []
        for cache, clinical, evidence in self.links:
            import json

            require(bool(evidence.strip()), "material_link_evidence")
            for source, key in (("cache", cache), ("clinical", clinical)):
                parts = json.loads(key)
                require(
                    isinstance(parts, list)
                    and len(parts) == 4
                    and all(isinstance(v, str) and v.strip() for v in parts),
                    "material_link_key",
                )
                require((source, *parts[:3]) in self.native_cases, "material_link_case")
            cache_keys.append(cache)
            clinical_keys.append(clinical)
        require(
            len(set(cache_keys)) == len(cache_keys)
            and len(set(clinical_keys)) == len(clinical_keys),
            "material_link_cardinality",
        )

    @property
    def case_id(self) -> str:
        return digest(self.canonical_case)

    @property
    def policy_hash(self) -> str:
        self.validate()
        return digest(asdict(self))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CasePolicy:
        d = dict(data)
        for key in (
            "canonical_case",
            "native_cases",
            "links",
            "status_rules",
            "equivalence_fields",
            "not_applicable_fields",
            "clinical_type_approvals",
        ):
            d[key] = tuple(tuple(x) if isinstance(x, (tuple, list)) else x for x in d.get(key, []))
        value = cls(**d)
        value.validate()
        return value


def time_equal(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return False
    a, b = datetime.fromisoformat(left), datetime.fromisoformat(right)
    if (a.tzinfo is None) != (b.tzinfo is None):
        return False  # 禁止给无偏移时刻猜时区。
    return a == b


def confirmation_basis(items: list[dict[str, Any]]) -> dict[str, Any]:
    """按实际确认的材料版本固定证明，不串联每次immediate prior decision_id。"""
    basis = {}
    for item in items:
        if (
            item.get("source_namespace") != "clinical"
            or item.get("state") != "SUPPLEMENT_CONFIRMED"
        ):
            continue
        proof = item.get("confirmation", {})
        require(
            isinstance(proof, dict)
            and isinstance(proof.get("coverage"), dict)
            and isinstance(proof.get("policy_hash"), str)
            and proof.get("proof_hash") == digest(proof["coverage"]),
            "material_confirmation_basis_invalid",
        )
        basis[item["version_id"]] = {
            "policy_hash": proof["policy_hash"],
            "proof_hash": proof["proof_hash"],
            "confirmation_hash": digest(proof),
        }
    return basis


def input_hash(
    policy: CasePolicy,
    versions: list[dict[str, Any]],
    coverage: dict[str, Any],
    confirmations: dict[str, Any] | None = None,
) -> str:
    return digest(
        {
            "decision_contract": CONTRACT,
            "policy": policy.policy_hash,
            "versions": sorted(v["version_id"] for v in versions),
            "coverage": coverage,
            "confirmation_basis": confirmations or {},
        }
    )


def body_relation_hint(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """仅提示关联；不同已知事件时间的同文不合并，未知时间不能证明独立。"""
    a = "".join((left["body"] or "").split())
    b = "".join((right["body"] or "").split())
    if not a or not b:
        return False
    if a != b:
        return a in b or b in a
    x, y = left["record_time"], right["record_time"]
    if x is None or y is None:
        return True
    if (datetime.fromisoformat(x).utcoffset() is None) != (
        datetime.fromisoformat(y).utcoffset() is None
    ):
        return True
    return time_equal(x, y)


def _publish(spec: InterfaceSpec) -> PublishSpec:
    if spec.publish is None:
        raise IngestError(ErrorKind.PUBLISH_CONTRACT, "material_publish_contract_required")
    return spec.publish


def _inputs(q: Any, case_id: str) -> tuple[CasePolicy, list[dict[str, Any]], dict[str, Any]]:
    q.execute(
        "SELECT p.policy_json FROM sync_material.case_policy c "
        "JOIN sync_material.policy_version p ON p.policy_hash=c.policy_hash WHERE c.case_id=%s",
        (case_id,),
    )
    row = q.fetchone()
    require(row is not None, "material_case_policy_missing")
    policy = CasePolicy.from_dict(row[0])
    q.execute(
        "SELECT v.material_json FROM sync_material.case_binding b "
        "JOIN sync_material.document_head h ON h.source_namespace=b.source_namespace "
        "AND h.native_case_hash=b.native_case_hash JOIN sync_material.document_version v "
        "ON v.version_id=h.version_id WHERE b.case_id=%s ORDER BY v.version_id",
        (case_id,),
    )
    versions = [r[0] for r in q.fetchall()]
    q.execute(
        "SELECT source_namespace,coverage_json FROM sync_material.coverage WHERE case_id=%s",
        (case_id,),
    )
    coverage = dict(q.fetchall())
    for source in ("cache", "clinical"):
        coverage.setdefault(
            source, {"state": "UNKNOWN", "scope": "UNCONFIRMED", "observed_at": None}
        )
    return policy, versions, coverage


def _target_current(q: Any, policy: CasePolicy, specs: dict[str, InterfaceSpec]) -> bool:
    """检测通知/轮询尚未跟上：实际目标/回执变化时不能复用旧选择。

    只查同CDM，业务无需连接ingest；不写待办，下一次显式poll会恢复。
    """
    _, versions, _ = _inputs(q, policy.case_id)
    for source, inst, patient, visit in policy.native_cases:
        spec = specs[source]
        columns = _publish(spec).target_columns
        q.execute(
            "SELECT "
            + ",".join(map(_ident, columns))
            + " FROM "
            + _ident(_publish(spec).schema)
            + "."
            + _ident(_publish(spec).table)
            + " WHERE institute_id=%s AND patient_id=%s AND visit_id=%s",
            (inst, patient, visit),
        )
        actual = sorted(
            digest(dict(zip(columns, [normalize(v) for v in row], strict=True)))
            for row in q.fetchall()
        )
        expected = sorted(
            digest(v["target_payload"])
            for v in versions
            if v["source_namespace"] == source and v["native_key"][:3] == [inst, patient, visit]
        )
        if actual != expected:
            return False
    for v in versions:
        r = v["publication"]
        q.execute(
            "SELECT r.generation,r.mapping_hash,r.activation FROM sync_delivery.receipt r "
            "JOIN sync_delivery.contract a ON a.interface_name=r.interface_name "
            "AND a.source_epoch=r.source_epoch AND a.mapping_hash=r.mapping_hash "
            "AND a.activation=r.activation "
            "WHERE r.source_epoch=%s AND r.interface_name=%s AND r.source_key_hash=%s",
            (r["source_epoch"], r["interface"], r["source_key_hash"]),
        )
        if q.fetchone() != (r["generation"], r["mapping_hash"], r["activation"]):
            return False
    return True


def _independent_prior_items(
    q: Any,
    policy: CasePolicy,
    versions: list[dict[str, Any]],
    prior: dict[str, Any],
    specs: dict[str, InterfaceSpec],
) -> list[dict[str, Any]]:
    """待重判不意味着全部可靠事实失效；只保留版本和关系均未受影响的旧选择。"""
    items: list[dict[str, Any]] = json.loads(canonical_json(prior["items"]))
    if prior.get("contract") != CONTRACT or prior["policy_hash"] != policy.policy_hash:
        for item in items:
            item.update(state="PENDING_RECONCILIATION", rule_usable=False)
        return items
    current = {v["record_identity"]: v for v in versions}
    prior_by_id = {v["record_identity"]: v for v in items}
    changed_docs = set()
    changed_versions = set()
    for record in set(current) | set(prior_by_id):
        a, b = current.get(record), prior_by_id.get(record)
        if a is None or b is None or a["version_id"] != b["version_id"]:
            changed = a if a is not None else b
            assert changed is not None
            changed_docs.add(changed["native_key"][-1])
            if b:
                changed_versions.add(b["version_id"])
    for source, inst, patient, visit in policy.native_cases:
        spec = specs[source]
        columns = _publish(spec).target_columns
        q.execute(
            "SELECT "
            + ",".join(map(_ident, columns))
            + " FROM "
            + _ident(_publish(spec).schema)
            + "."
            + _ident(_publish(spec).table)
            + " WHERE institute_id=%s AND patient_id=%s AND visit_id=%s",
            (inst, patient, visit),
        )
        rows = [dict(zip(columns, row, strict=True)) for row in q.fetchall()]
        actual = {
            row["document_id"]: digest({k: normalize(v) for k, v in row.items()}) for row in rows
        }
        expected = {
            v["native_key"][-1]: digest(v["target_payload"])
            for v in versions
            if v["source_namespace"] == source and v["native_key"][:3] == [inst, patient, visit]
        }
        changed_docs.update(
            doc for doc in set(actual) | set(expected) if actual.get(doc) != expected.get(doc)
        )
        old_payloads = {
            i["native_key"][-1]: digest(i["target_payload"])
            for i in items
            if i["source_namespace"] == source and i["native_key"][:3] == [inst, patient, visit]
        }
        for payload in rows:
            if actual[payload["document_id"]] == old_payloads.get(payload["document_id"]):
                continue
            recorded = payload.get("record_datetime" if source == "cache" else "record_time")
            candidate = {
                "body": payload.get("record_content"),
                "record_time": recorded.isoformat() if isinstance(recorded, datetime) else recorded,
            }
            for item in items:
                if item["source_namespace"] != source and body_relation_hint(item, candidate):
                    changed_versions.add(item["version_id"])
    for item in items:
        r = item["publication"]
        q.execute(
            "SELECT r.generation,r.mapping_hash,r.activation FROM sync_delivery.receipt r "
            "JOIN sync_delivery.contract a ON a.interface_name=r.interface_name "
            "AND a.source_epoch=r.source_epoch AND a.mapping_hash=r.mapping_hash "
            "AND a.activation=r.activation "
            "WHERE r.source_epoch=%s AND r.interface_name=%s AND r.source_key_hash=%s",
            (r["source_epoch"], r["interface"], r["source_key_hash"]),
        )
        if q.fetchone() != (r["generation"], r["mapping_hash"], r["activation"]):
            changed_docs.add(item["native_key"][-1])
            changed_versions.add(item["version_id"])
    for item in items:
        if (
            item["native_key"][-1] in changed_docs
            or set(item["related_versions"]) & changed_versions
        ):
            changed_versions.add(item["version_id"])
    for cache_key, clinical_key, _ in policy.links:
        a, b = json.loads(cache_key)[-1], json.loads(clinical_key)[-1]
        if a in changed_docs or b in changed_docs:
            changed_docs.update((a, b))
    for item in items:
        if (
            item["native_key"][-1] in changed_docs
            or item["version_id"] in changed_versions
            or set(item["related_versions"]) & changed_versions
        ):
            item.update(state="PENDING_RECONCILIATION", rule_usable=False)
    return items


def read_manifest_in_transaction(
    cdm: PostgresSettings, connection: Any, case_id: str, clinical_contract: ClinicalContract
) -> dict[str, Any]:
    """复用业务已打开的同一CDM只读RR事务；不提交/回滚/关闭调用者连接。"""
    independent_database(cdm, "cdm")
    with connection.cursor() as q:
        q.execute(
            "SELECT current_database(),current_setting('transaction_read_only'),"
            "current_setting('transaction_isolation')"
        )
        require(
            q.fetchone() == (cdm.database, "on", "repeatable read"),
            "material_capture_transaction_required",
        )
        return _read_manifest(q, case_id, clinical_contract)


def _read_manifest(q: Any, case_id: str, clinical_contract: ClinicalContract) -> dict[str, Any]:
    policy, versions, coverage = _inputs(q, case_id)
    q.execute(
        "SELECT d.decision_id,d.result_json FROM sync_material.selection_head s "
        "JOIN sync_material.decision d ON d.decision_id=s.decision_id WHERE s.case_id=%s",
        (case_id,),
    )
    row = q.fetchone()
    fresh = (
        row is not None
        and row[1].get("contract") == CONTRACT
        and row[1].get("confirmation_basis") == confirmation_basis(row[1]["items"])
        and row[1]["input_hash"]
        == input_hash(policy, versions, coverage, row[1]["confirmation_basis"])
        and _target_current(
            q,
            policy,
            {
                "cache": resolve_interface("web.daily_course_record"),
                "clinical": clinical_contract.spec,
            },
        )
    )
    if fresh:
        result = {"decision_id": row[0], **row[1], "fresh": True}
    else:
        # 旧材料和旧选择可追溯，但不能把旧判定用于新任务确定事实。
        items = (
            _independent_prior_items(
                q,
                policy,
                versions,
                row[1],
                {
                    "cache": resolve_interface("web.daily_course_record"),
                    "clinical": clinical_contract.spec,
                },
            )
            if row
            else []
        )
        result = {
            "fresh": False,
            "state": "PENDING_RECONCILIATION",
            "case_id": case_id,
            "policy_hash": policy.policy_hash,
            "coverage": coverage,
            "prior_decision": {"decision_id": row[0], **row[1]} if row else None,
            "items": items,
            "selection": [i["version_id"] for i in items if i["selected"]],
            "rule_materials": [
                i["version_id"] for i in items if i["selected"] and i["rule_usable"]
            ],
            "can_judge_clinical_absence": False,
        }
    frozen: dict[str, Any] = json.loads(canonical_json(result))
    return frozen


EXTRACTED_SOURCE_SHA256 = {'domain.py:ErrorKind': '2ae1d302f13e47e14d7f0c039aa2ae763c9c13bef350e0928dade16ac1b6bd74', 'domain.py:IngestError': '1264d4e3c547f2262600348f32ac33e6d8761e478cef5972e55de083f526cd0d', 'domain.py:canonical_json': 'cbef3cf5439cdc28ffbe82520b352fc1d6915816c0891957a89a5009cb5fdbd8', 'domain.py:sha256_hex': '353da17f4d8198502350fd523db93a2bddfcaa3e282640443f266f61e95454eb', 'domain.py:normalize': '28818319649598b3c5b9412b3fcddd853df572660b6062613d7b504daf9569e3', 'clinical_daily.py:require': '3312fd2d4ee16aeb47cc1422336099c6e4143acd696f20cd69a4f7aa43395d0c', 'clinical_daily.py:independent_database': '20648a45471236f0e9b2ed9683f3d76560ffc0176e02fce42a617e8f892cd529', 'daily_materials.py:digest': '55e798fcc4fe6a952ae6992dd930f584959353d16c01c4d1d41519639787a9be', 'daily_materials.py:CasePolicy': '09e38a04faf07f1122f30524d424190a919daa071d941537272bf476bf35dbe7', 'daily_materials.py:time_equal': '7b736085219c97d829644d38d3a838fc4d1f10b5e6f73acccf2b5e87ff5fbf6a', 'daily_materials.py:confirmation_basis': '9b2f36a1c541f469b8206ad6598631cf13ad2738cebc63fa352c1e4648c11407', 'daily_materials.py:input_hash': 'a0b7445179a18c2f7f242c6c35d2b94d4431044e7cba911d014bb7c8e59fffc6', 'daily_materials.py:body_relation_hint': '2ffe5f849b42ab98f266448e3cd016c72b224c78d0f58441059db52314a4a0b2', 'daily_reconcile.py:_publish': 'c668e273f493fd58338d5e859e60a677353a3d461ff0e7d1841ee40f7ef181d6', 'daily_reconcile.py:_inputs': '840885a8a061ef4c009d04637e2afcf06929eba88db59cc1a3317c43700525c3', 'daily_reconcile.py:_target_current': '32a6c1d89e1d84d7e5c7955647b15ae10928dbe1255e6e20872f614756c44d6e', 'daily_reconcile.py:_independent_prior_items': '231dff1acdac50183519338da62e7e8865a6b6687fe15d982ab6484bdd806777', 'daily_reconcile.py:read_manifest_in_transaction': '5292dc9e31d17e927bc68a825137dae2c73ead7c8cc49111bc33e1442afa8edc', 'daily_reconcile.py:_read_manifest': 'c59ab6749a3843393f398cd37c59374fc86111ba10408df5bbf1b9566f15bfaf'}
