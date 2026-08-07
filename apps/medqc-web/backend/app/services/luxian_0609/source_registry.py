"""LX0609 规则文书需求到受控来源的版本化注册表。

注册表区分物理来源、派生父来源和执行器别名。它声明 snapshot provider
必须遵守的读取能力，绝不把当前 bundle 投影等同于来源完整。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from types import MappingProxyType
import re
from typing import Mapping

from .evidence_snapshot import SourceCompleteness
from .rule_contracts import load_luxian_0609_rule_contracts


SOURCE_REGISTRY_VERSION = "lx0609-source-registry-v19"
EXACT_VISIT_BINDING_FIELDS = ("institute_id", "patient_id", "visit_id")
_SOURCE_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


class SourceAccessMode(str, Enum):
    BOUNDED_SOURCE_V1 = "bounded_source_v1"
    CONTROLLED_FACT_V1 = "controlled_fact_v1"
    LEGACY_PROJECTION_V1 = "legacy_projection_v1"
    DERIVED_PROJECTION_V1 = "derived_projection_v1"


class CompletenessAttestationPolicy(str, Enum):
    EXACT_PREDICATE_V1 = "exact_predicate_v1"
    UNPROVEN_ONLY = "unproven_only"
    PROVIDER_LIMIT_PLUS_ONE_V1 = "provider_limit_plus_one_v1"


@dataclass(frozen=True)
class SourceRegistryEntry:
    document_type: str
    physical_source_keys: tuple[str, ...]
    derived_from_source_keys: tuple[str, ...]
    projection_aliases: tuple[str, ...]
    query_version: str
    binding_fields: tuple[str, ...]
    access_mode: SourceAccessMode
    completeness_attestation_policy: CompletenessAttestationPolicy
    default_completeness: SourceCompleteness

    @property
    def source_keys(self) -> tuple[str, ...]:
        """受控读取键视图；明确排除执行器 projection aliases。"""

        return self.physical_source_keys or self.derived_from_source_keys

    @property
    def complete_capable(self) -> bool:
        """只有 provider 的受控完整性协议可声明 COMPLETE/TRUNCATED。"""

        return (
            self.completeness_attestation_policy
            in (
                CompletenessAttestationPolicy.EXACT_PREDICATE_V1,
                CompletenessAttestationPolicy.PROVIDER_LIMIT_PLUS_ONE_V1,
            )
        )

    def __post_init__(self) -> None:
        if not isinstance(self.document_type, str) or not _SOURCE_KEY_PATTERN.fullmatch(
            self.document_type
        ):
            raise ValueError("invalid document_type")
        registered_keys = (*self.physical_source_keys, *self.derived_from_source_keys)
        if not registered_keys or any(
            not isinstance(item, str) or not _SOURCE_KEY_PATTERN.fullmatch(item)
            for item in registered_keys
        ):
            raise ValueError("invalid registered source keys")
        if len(registered_keys) != len(set(registered_keys)):
            raise ValueError("duplicate source_key in registry entry")
        if any(
            not isinstance(item, str) or not _SOURCE_KEY_PATTERN.fullmatch(item)
            for item in self.projection_aliases
        ):
            raise ValueError("invalid projection aliases")
        if not isinstance(self.query_version, str) or not self.query_version.strip():
            raise ValueError("invalid query_version")
        if self.binding_fields != EXACT_VISIT_BINDING_FIELDS:
            raise ValueError("source registry requires exact three-coordinate binding")
        if not isinstance(self.access_mode, SourceAccessMode):
            raise TypeError("access_mode must be SourceAccessMode")
        if not isinstance(self.completeness_attestation_policy, CompletenessAttestationPolicy):
            raise TypeError("invalid completeness attestation policy")
        if (
            self.completeness_attestation_policy
            is CompletenessAttestationPolicy.PROVIDER_LIMIT_PLUS_ONE_V1
            and self.access_mode is not SourceAccessMode.BOUNDED_SOURCE_V1
        ):
            raise ValueError("only bounded source may use limit-plus-one attestation")
        if (
            self.completeness_attestation_policy
            is CompletenessAttestationPolicy.EXACT_PREDICATE_V1
            and self.access_mode is not SourceAccessMode.CONTROLLED_FACT_V1
        ):
            raise ValueError("only controlled fact may use exact predicate attestation")
        if self.default_completeness is not SourceCompleteness.UNPROVEN:
            raise ValueError("registry cannot predeclare source completeness")


def _entry(
    document_type: str,
    *physical_source_keys: str,
    access_mode: SourceAccessMode = SourceAccessMode.LEGACY_PROJECTION_V1,
    derived_from_source_keys: tuple[str, ...] = (),
    projection_aliases: tuple[str, ...] = (),
    query_version: str = "",
) -> SourceRegistryEntry:
    completeness_policy = (
        CompletenessAttestationPolicy.PROVIDER_LIMIT_PLUS_ONE_V1
        if access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
        else (
            CompletenessAttestationPolicy.EXACT_PREDICATE_V1
            if access_mode is SourceAccessMode.CONTROLLED_FACT_V1
            else CompletenessAttestationPolicy.UNPROVEN_ONLY
        )
    )
    return SourceRegistryEntry(
        document_type=document_type,
        physical_source_keys=(
            tuple(physical_source_keys)
            if physical_source_keys
            else (() if derived_from_source_keys else (document_type,))
        ),
        derived_from_source_keys=derived_from_source_keys,
        projection_aliases=projection_aliases,
        query_version=query_version
        or (
            f"snapshot-provider-{document_type}-v1"
            if access_mode is SourceAccessMode.BOUNDED_SOURCE_V1
            else (
                f"controlled-fact-{document_type}-v1"
                if access_mode is SourceAccessMode.CONTROLLED_FACT_V1
                else f"{access_mode.value}-{document_type}"
            )
        ),
        binding_fields=EXACT_VISIT_BINDING_FIELDS,
        access_mode=access_mode,
        completeness_attestation_policy=completeness_policy,
        default_completeness=SourceCompleteness.UNPROVEN,
    )


_BOUNDED = SourceAccessMode.BOUNDED_SOURCE_V1
_CONTROLLED = SourceAccessMode.CONTROLLED_FACT_V1
_DERIVED = SourceAccessMode.DERIVED_PROJECTION_V1

_REGISTRY_ENTRIES = (
    _entry("admission_record", access_mode=_BOUNDED),
    _entry("anesthesia_record", access_mode=_BOUNDED),
    _entry(
        "bloodtrans_record",
        "bloodtrans_record",
        "mr_bloodtrans",
        access_mode=_BOUNDED,
    ),
    _entry(
        "consent_form",
        "consent_form",
        "surgery_inform_consent",
        access_mode=_BOUNDED,
        projection_aliases=(
            "anesthesia_consent",
            "anesthesia_consent_form",
            "blood_transfusion_consent",
        ),
    ),
    _entry("consultation_record", access_mode=_BOUNDED),
    _entry("daily_course_record", access_mode=_BOUNDED),
    _entry("death_discussion", access_mode=_BOUNDED),
    _entry("death_record", access_mode=_BOUNDED),
    _entry("diagnosis", access_mode=_BOUNDED),
    _entry("diffcase_discussion_record", access_mode=_BOUNDED),
    _entry("discharge_record", access_mode=_BOUNDED),
    _entry("discharge_record_diagnosis", access_mode=_BOUNDED),
    _entry(
        "exam_attention_report",
        access_mode=_DERIVED,
        derived_from_source_keys=("exam_master", "exam_item_report"),
    ),
    _entry("exam_item_report", access_mode=_BOUNDED),
    _entry("first_course_record", access_mode=_BOUNDED),
    _entry("handoff_record", access_mode=_BOUNDED),
    _entry("handover_record", access_mode=_BOUNDED),
    _entry(
        "lab_attention_report",
        access_mode=_DERIVED,
        derived_from_source_keys=("labtest_master", "labtest_item_report"),
    ),
    _entry("labtest_item_report", access_mode=_BOUNDED),
    _entry("labtest_master", access_mode=_BOUNDED),
    _entry("crisis_value_record", access_mode=_BOUNDED),
    _entry("inpat_drug_order", access_mode=_BOUNDED),
    _entry("inpat_nondrug_order", access_mode=_BOUNDED),
    _entry(
        "medical_order",
        access_mode=_DERIVED,
        derived_from_source_keys=("inpat_nondrug_order", "inpat_drug_order"),
    ),
    _entry("postsurg_firstcourse_record", access_mode=_BOUNDED),
    _entry("presurg_discussion", access_mode=_BOUNDED),
    _entry("presurg_summary", access_mode=_BOUNDED),
    _entry("rescue_record", access_mode=_BOUNDED),
    _entry("senior_course_record", access_mode=_BOUNDED),
    _entry(
        "surgery_record",
        "surgery_record",
        "mr_surgery",
        access_mode=_BOUNDED,
        query_version="snapshot-provider-surgery_record-v2",
    ),
    _entry("surgery_risk_assessment"),
    _entry("surgery_safecheck_record", access_mode=_BOUNDED),
    _entry("transfer_in_record", access_mode=_BOUNDED),
    _entry("transfer_out_record", access_mode=_BOUNDED),
)

_INTERNAL_SOURCE_ENTRIES = (
    # 第一阶段扩展规则在目录整体切换前先作为内部受控来源注册。
    # 输血记录、申请与收费是三个不同的资料合同，不能继续把收费行合并到
    # bloodtrans_record 后再由规则猜测来源。
    _entry("blood_application", access_mode=_BOUNDED),
    _entry("inpat_bill_item", access_mode=_BOUNDED),
    _entry("physician_change_event", access_mode=_BOUNDED),
    _entry("evaluation_context.horizon", access_mode=_BOUNDED),
    _entry("inpat_registration", access_mode=_BOUNDED),
    _entry("inpat_registration.discharge_horizon", access_mode=_BOUNDED),
    _entry(
        "inpat_nondrug_order.severity_order",
        access_mode=_BOUNDED,
        query_version="snapshot-provider-inpat_nondrug_order.severity_order-v2",
    ),
    _entry(
        "inpat_nondrug_order.exam_lab_order",
        access_mode=_BOUNDED,
        query_version="snapshot-provider-inpat_nondrug_order.exam_lab_order-v1",
    ),
    _entry("inpat_nondrug_order.unstable_order", access_mode=_CONTROLLED),
    _entry("pathology_exam_master", access_mode=_BOUNDED),
    _entry("pathology_exam_report", access_mode=_BOUNDED),
    _entry("admission_record_diagnosis", access_mode=_BOUNDED),
    _entry("exam_master", access_mode=_BOUNDED),
    _entry("surgery_application", access_mode=_BOUNDED),
    _entry("preane_surveil_record", access_mode=_BOUNDED),
    _entry("postane_surveil_record", access_mode=_BOUNDED),
)

_CONTROLLED_FACT_SOURCES_BY_RULE = MappingProxyType(
    {"LX0609-007": ("inpat_nondrug_order.unstable_order",)}
)

_DECISION_SUPPORT_SOURCES_BY_RULE = MappingProxyType({
    # 003 优先使用 surgery_record 自带时间，缺失时仅允许唯一 mr_surgery 时间配对；
    # 手术记录为空时，用申请与手术类医嘱共同确认“确无手术”，避免把未同步误判为不适用。
    "LX0609-003": ("mr_surgery", "surgery_application", "inpat_nondrug_order"),
    "LX0609-001": ("inpat_registration", "discharge_record"),
    "LX0609-002": (
        "admission_record",
        "first_course_record",
        "inpat_registration",
    ),
    "LX0609-004": ("rescue_record",),
    "LX0609-005": (
        "admission_record",
        "discharge_record",
        "inpat_registration",
        "daily_course_record",
    ),
    "LX0609-006": (
        "admission_record",
        "discharge_record",
        "inpat_registration",
    ),
    "LX0609-008": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.severity_order",
        "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-009": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.severity_order",
        "daily_course_record",
        "senior_course_record",
    ),
    # 017 仅在灰区语义核对时读取同一快照中的当前就诊事件；
    # 不加入术后病程或治疗过程来源，避免把非相邻病程内容混入复制判定。
    "LX0609-017": (
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "inpat_drug_order",
        "surgery_record",
        "mr_surgery",
    ),
    "LX0609-010": (
        "inpat_nondrug_order.exam_lab_order",
        "exam_master",
        "exam_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    ),
    "LX0609-011": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.exam_lab_order",
        "exam_master",
        "exam_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    ),
    "LX0609-012": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.exam_lab_order",
        "exam_master",
        "exam_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    ),
    "LX0609-014": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.exam_lab_order",
        "labtest_master",
        "labtest_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    ),
    "LX0609-015": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.exam_lab_order",
        "labtest_master",
        "labtest_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
    ),
    # 病理/肿瘤规则的适用触发来源也必须参与 RuleDecision 引用绑定。
    "LX0609-013": ("pathology_exam_master", "pathology_exam_report"),
    "LX0609-019": ("pathology_exam_master", "pathology_exam_report"),
    # 026 的旧客户文书范围没有结构化诊断，RuleDecision 只允许同一快照
    # 中受控诊断代码决定恶性肿瘤适用性；化疗事实仍缺失时保守 DG。
    "LX0609-026": ("diagnosis",),
    # 018 仅接受受控第一诊断：主要诊断，或入院/初步诊断中的编号首项。
    "LX0609-018": ("diagnosis", "admission_record_diagnosis"),
    # 027 需要同一快照内的恶性诊断与出院记录，不能只绑定触发诊断。
    "LX0609-027": ("diagnosis", "discharge_record"),
    # 028 的客户文书范围只有病程，必须额外绑定严格已实施手术事实，
    # 禁止从病程关键词推断当前手术。
    "LX0609-024": (
        "surgery_record", "mr_surgery", "pathology_exam_master",
        "pathology_exam_report", "diagnosis",
    ),
    "LX0609-025": ("surgery_record", "mr_surgery", "daily_course_record"),
    "LX0609-028": (
        "surgery_record", "mr_surgery", "inpat_drug_order", "daily_course_record",
    ),
    "LX0609-033": ("surgery_record", "mr_surgery", "surgery_inform_consent"),
    # 麻醉同意书、访视和记录单规则都必须先由结构化手术清单确认
    # 本次住院是否实施麻醉以及麻醉方式，才能正确处理局麻例外。
    "LX0609-034": ("mr_surgery",),
    "LX0609-035": ("mr_surgery",),
    "LX0609-036": (
        "mr_surgery",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    "LX0609-037": (
        "mr_surgery",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    "LX0609-038": ("mr_surgery",),
    # 039 必须同时绑定严格手术事实与急救例外来源，不能只看术前讨论表。
    "LX0609-039": ("surgery_record", "mr_surgery", "rescue_record"),
    # 020/023 的“复会诊是否执行”可由病程、医嘱、检查检验或手术记录体现。
    # 全部候选必须进入同一 Evidence Session，避免判定使用了材料但 fact refs 未绑定来源。
    "LX0609-020": (
        "evaluation_context.horizon",
        "inpat_registration",
        "inpat_registration.discharge_horizon",
        "daily_course_record",
        "senior_course_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "surgery_record",
    ),
    "LX0609-023": (
        "evaluation_context.horizon",
        "inpat_registration",
        "inpat_registration.discharge_horizon",
        "daily_course_record",
        "senior_course_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "exam_master",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "surgery_record",
    ),
    # 040 先由结构化手术等级确认四级手术，再核对同次就诊会诊记录。
    "LX0609-040": ("mr_surgery", "consultation_record"),
    # 输血规则的客户文书范围并非都含输血记录；统一决策仍必须先绑定
    # mr_bloodtrans/bloodtrans_record 这一实际输血锚点。申请、同意书、检验和
    # 围术期文书均保持独立来源，禁止再借用输血记录或收费行伪装。
    "LX0609-041": ("bloodtrans_record", "mr_bloodtrans", "consent_form"),
    "LX0609-042": ("bloodtrans_record", "mr_bloodtrans", "consent_form"),
    "LX0609-043": (
        "bloodtrans_record",
        "mr_bloodtrans",
        "blood_application",
        "exam_master",
        "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-044": ("bloodtrans_record", "mr_bloodtrans", "blood_application", "daily_course_record"),
    "LX0609-045": ("bloodtrans_record", "mr_bloodtrans", "daily_course_record"),
    "LX0609-046": ("bloodtrans_record", "mr_bloodtrans", "daily_course_record"),
    "LX0609-047": ("bloodtrans_record", "mr_bloodtrans", "daily_course_record"),
    "LX0609-048": (
        "bloodtrans_record",
        "mr_bloodtrans",
        "surgery_record",
        "anesthesia_record",
        "postsurg_firstcourse_record",
    ),
    "LX0609-049": (
        "bloodtrans_record",
        "mr_bloodtrans",
        "blood_application",
        "inpat_nondrug_order",
        "inpat_bill_item",
    ),
    "LX0609-050": (
        "inpat_registration",
        "admission_record",
        "daily_course_record",
        "diffcase_discussion_record",
    ),
    "LX0609-052": (
        "labtest_master",
        "labtest_item_report",
        "crisis_value_record",
    ),
    "LX0609-053": (
        "labtest_master",
        "labtest_item_report",
        "crisis_value_record",
    ),
    "LX0609-054": (
        "senior_course_record", "consultation_record", "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-055": (
        "senior_course_record", "consultation_record", "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-056": (
        "daily_course_record", "senior_course_record", "consultation_record",
        "labtest_item_report",
    ),
    "LX0609-057": (
        "senior_course_record", "consultation_record", "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-058": (
        "daily_course_record", "senior_course_record", "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-059": (
        "senior_course_record", "consultation_record", "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-063": ("discharge_record",),
    "LX0609-064": ("mr_surgery",),
    "LX0609-065": ("mr_surgery",),
    "LX0609-066": ("mr_surgery",),
    # 070 的九项必须属于本次住院、且早于每一笔实际输血；住院登记、输血事件
    # 与检验结果均需进入同一 Evidence Session。
    "LX0609-070": (
        "inpat_registration",
        "mr_bloodtrans",
        "labtest_item_report",
    ),
    # 第一阶段扩展规则的触发事实不扩张客户文书范围，但必须进入同一
    # Evidence Session，供适用性、时限和关联判定绑定。
    "LX0609-051": ("inpat_registration",),
    "LX0609-060": ("inpat_registration",),
    "LX0609-061": ("inpat_registration",),
    "LX0609-062": ("inpat_registration",),
    "LX0609-067": ("inpat_registration",),
    "LX0609-068": ("inpat_registration",),
    # 优先使用权威经治医师变更事件；部分院端尚未提供独立事件表，允许
    # 明确的“经治医师变更/交接班”医嘱作为受控替代触发。
    "LX0609-071": ("physician_change_event", "inpat_nondrug_order"),
    "LX0609-072": ("inpat_nondrug_order",),
    "LX0609-073": ("inpat_nondrug_order",),
    "LX0609-074": ("diagnosis",),
})


@lru_cache(maxsize=1)
def load_luxian_0609_source_registry() -> Mapping[str, SourceRegistryEntry]:
    entries = {entry.document_type: entry for entry in _REGISTRY_ENTRIES}
    if len(entries) != len(_REGISTRY_ENTRIES):
        raise ValueError("duplicate document_type in LX0609 source registry")
    declared_documents = {
        document_type
        for contract in load_luxian_0609_rule_contracts()
        for document_type in contract.applicable_documents
    }
    if set(entries) != declared_documents:
        raise ValueError("LX0609 source registry drift")
    return MappingProxyType(entries)


def resolve_luxian_0609_rule_sources(
    selected_rule_ids: tuple[str, ...],
) -> dict[str, tuple[SourceRegistryEntry, ...]]:
    contracts = {item.rule_id: item for item in load_luxian_0609_rule_contracts()}
    registry = load_luxian_0609_source_registry()
    if len(selected_rule_ids) != len(set(selected_rule_ids)):
        raise ValueError("duplicate LX0609 rule id")
    resolved: dict[str, tuple[SourceRegistryEntry, ...]] = {}
    for raw_rule_id in selected_rule_ids:
        rule_id = str(raw_rule_id or "").strip().upper()
        contract = contracts.get(rule_id)
        if contract is None:
            raise ValueError("unknown LX0609 rule id")
        resolved[rule_id] = tuple(registry[item] for item in contract.applicable_documents)
    return resolved


def _entries_for_source_key(source_key: str) -> tuple[SourceRegistryEntry, ...]:
    normalized = str(source_key or "").strip().lower()
    if not normalized or not _SOURCE_KEY_PATTERN.fullmatch(normalized):
        return ()
    return tuple(
        entry
        for entry in (
            *load_luxian_0609_source_registry().values(),
            *_INTERNAL_SOURCE_ENTRIES,
        )
        if normalized == entry.document_type or normalized in entry.source_keys
    )


def resolve_luxian_0609_controlled_fact_source_keys(
    selected_rule_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """解析所选规则的内部受控事实查询；不得扩展客户文书范围。"""

    if len(selected_rule_ids) != len(set(selected_rule_ids)):
        raise ValueError("duplicate LX0609 rule id")
    contracts = {item.rule_id for item in load_luxian_0609_rule_contracts()}
    normalized = tuple(str(item or "").strip().upper() for item in selected_rule_ids)
    if any(item not in contracts for item in normalized):
        raise ValueError("unknown LX0609 rule id")
    return tuple(
        sorted(
            {
                source_key
                for rule_id in normalized
                for source_key in _CONTROLLED_FACT_SOURCES_BY_RULE.get(rule_id, ())
            }
        )
    )


def resolve_luxian_0609_decision_support_source_keys(
    selected_rule_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """解析规则裁决所需、但不改变客户适用文书范围的内部来源。"""

    if len(selected_rule_ids) != len(set(selected_rule_ids)):
        raise ValueError("duplicate LX0609 rule id")
    contracts = {item.rule_id for item in load_luxian_0609_rule_contracts()}
    normalized = tuple(str(item or "").strip().upper() for item in selected_rule_ids)
    if any(item not in contracts for item in normalized):
        raise ValueError("unknown LX0609 rule id")
    return tuple(
        sorted(
            {
                source_key
                for rule_id in normalized
                for source_key in _DECISION_SUPPORT_SOURCES_BY_RULE.get(rule_id, ())
            }
        )
    )


def is_registered_luxian_0609_source_key(source_key: str) -> bool:
    return bool(_entries_for_source_key(source_key))


def resolve_luxian_0609_physical_source_entry(
    source_key: str,
) -> SourceRegistryEntry:
    """解析唯一物理来源；projection alias 和派生键不能伪装成可查询表。"""

    normalized = str(source_key or "").strip().lower()
    matches = tuple(
        entry
        for entry in (
            *load_luxian_0609_source_registry().values(),
            *_INTERNAL_SOURCE_ENTRIES,
        )
        if normalized in entry.physical_source_keys
    )
    if len(matches) != 1:
        raise ValueError("LX0609 physical source is not uniquely registered")
    return matches[0]


def source_key_accepts_query_version(source_key: str, query_version: str) -> bool:
    version = str(query_version or "").strip()
    return any(version == entry.query_version for entry in _entries_for_source_key(source_key))


def source_key_supports_proven_completeness(source_key: str, query_version: str) -> bool:
    """只有版本匹配的 limit+1 provider 结果可声明 COMPLETE/TRUNCATED。"""

    version = str(query_version or "").strip()
    return any(
        entry.complete_capable and version == entry.query_version
        for entry in _entries_for_source_key(source_key)
    )
