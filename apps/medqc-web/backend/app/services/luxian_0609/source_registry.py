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


SOURCE_REGISTRY_VERSION = "lx0609-source-registry-v34"
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
        query_version="snapshot-provider-bloodtrans_record-v2",
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
    _entry("exam_master", access_mode=_BOUNDED),
    _entry("exam_item_report", access_mode=_BOUNDED),
    _entry("first_course_record", access_mode=_BOUNDED),
    _entry("first_course_record_diagnosis", access_mode=_BOUNDED),
    _entry("handoff_record", access_mode=_BOUNDED),
    _entry("handover_record", access_mode=_BOUNDED),
    _entry(
        "lab_attention_report",
        access_mode=_DERIVED,
        derived_from_source_keys=("labtest_master", "labtest_item_report"),
    ),
    _entry("labtest_item_report", access_mode=_BOUNDED),
    _entry("labtest_master", access_mode=_BOUNDED),
    _entry("pathology_exam_master", access_mode=_BOUNDED),
    _entry("pathology_exam_report", access_mode=_BOUNDED),
    _entry("crisis_value_record", access_mode=_BOUNDED),
    _entry(
        "inpat_drug_order",
        access_mode=_BOUNDED,
        query_version="snapshot-provider-inpat_drug_order-v2",
    ),
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
    _entry(
        "inpat_nondrug_order.rescue_order",
        access_mode=_BOUNDED,
        query_version="snapshot-provider-inpat_nondrug_order.rescue_order-v1",
    ),
    _entry("inpat_nondrug_order.unstable_order", access_mode=_CONTROLLED),
    _entry("admission_record_diagnosis", access_mode=_BOUNDED),
    # 063 的病案首页诊断是内部决策支持来源；客户适用文书仍由规则合同声明，
    # 不把该来源提升为第二个同名客户事实所有者。
    _entry("mr_diagnosis", access_mode=_BOUNDED),
    _entry("surgery_application", access_mode=_BOUNDED),
    _entry("preane_surveil_record", access_mode=_BOUNDED),
    _entry("postane_surveil_record", access_mode=_BOUNDED),
)

_CONTROLLED_FACT_SOURCES_BY_RULE = MappingProxyType(
    {"LX0609-02-01-03": ("inpat_nondrug_order.unstable_order",)}
)

_DECISION_SUPPORT_SOURCES_BY_RULE = MappingProxyType({
    # 003 优先使用 surgery_record 自带时间；缺失时可用开始时间完全匹配的
    # 唯一 anesthesia_record 明确手术结束时间，或唯一 mr_surgery 时间配对；
    # 手术记录为空时，合格 mr_surgery 的结束时间是独立已实施手术事实，
    # 必须以正式评价时点判断24小时窗口是否成熟；其余场景仍用申请与手术类
    # 医嘱共同确认“确无手术”，避免把未同步误判为不适用。
    "LX0609-04-02-01": (
        "evaluation_context.horizon",
        "anesthesia_record",
        "mr_surgery",
        "surgery_application",
        "inpat_nondrug_order",
    ),
    "LX0609-01-01-01": (
        "evaluation_context.horizon",
        "inpat_registration",
        "discharge_record",
    ),
    "LX0609-01-02-01": (
        "admission_record",
        "evaluation_context.horizon",
        "first_course_record",
        "inpat_registration",
    ),
    "LX0609-09-01-01": ("rescue_record", "inpat_nondrug_order.rescue_order"),
    "LX0609-02-01-01": (
        "admission_record",
        "discharge_record",
        "evaluation_context.horizon",
        "inpat_registration",
        "daily_course_record",
    ),
    "LX0609-02-01-02": (
        "admission_record",
        "discharge_record",
        "evaluation_context.horizon",
        "inpat_registration",
    ),
    "LX0609-02-01-03": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_registration",
        "admission_record",
    ),
    "LX0609-02-01-04": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.severity_order",
        "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-02-01-05": (
        "evaluation_context.horizon",
        "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.severity_order",
        "daily_course_record",
        "senior_course_record",
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
    ),
    # 017 仅在灰区语义核对时读取同一快照中的当前就诊事件；
    # 不加入术后病程或治疗过程来源，避免把非相邻病程内容混入复制判定。
    "LX0609-12-01-02": (
        "exam_item_report",
        "labtest_master",
        "labtest_item_report",
        "inpat_drug_order",
        "surgery_record",
        "mr_surgery",
    ),
    "LX0609-09-01-02": ("rescue_record", "inpat_nondrug_order.rescue_order"),
    "LX0609-06-02-01": ("pathology_exam_master", "pathology_exam_report"),
    "LX0609-06-01-01": (
        # 时限未到（在院运行中）与出院终末须区分评价。
        "evaluation_context.horizon", "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.exam_lab_order", "exam_master", "exam_item_report",
        "first_course_record", "daily_course_record", "senior_course_record", "rescue_record",
    ),
    "LX0609-06-01-03": (
        "inpat_nondrug_order.exam_lab_order", "exam_master", "exam_item_report",
    ),
    "LX0609-06-03-02": (
        # 时限未到（在院运行中）与出院终末须区分评价。
        "evaluation_context.horizon", "inpat_registration.discharge_horizon",
        "inpat_nondrug_order.exam_lab_order", "labtest_master", "labtest_item_report",
    ),
    "LX0609-06-01-02": (
        "inpat_nondrug_order.exam_lab_order",
        "exam_master",
        "exam_item_report",
        "daily_course_record",
        "first_course_record",
        "rescue_record",
        "senior_course_record",
        # 入院 24 小时内开立的检查豁免需要入院锚点。
        "inpat_registration",
        "admission_record",
    ),
    "LX0609-06-01-04": (
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
    "LX0609-06-01-05": (
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
    "LX0609-06-03-03": (
        "consultation_record",
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
    "LX0609-06-03-04": (
        "consultation_record",
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
    "LX0609-06-02-03": ("pathology_exam_master", "pathology_exam_report"),
    "LX0609-06-02-02": (
        "pathology_exam_master",
        "pathology_exam_report",
    ),
    # 026 绑定同一请求内的恶性事实、化疗医嘱和对应病程，禁止跨快照补证。
    "LX0609-05-02-01": (
        "admission_record_diagnosis", "diagnosis", "discharge_record_diagnosis",
        "pathology_exam_report", "inpat_registration.discharge_horizon",
        "discharge_record", "inpat_drug_order", "daily_course_record",
    ),
    # 018 仅接受受控第一诊断：主要诊断，或入院/初步诊断中的编号首项。
    "LX0609-01-01-02": ("diagnosis", "admission_record_diagnosis"),
    "LX0609-01-02-02": ("first_course_record_diagnosis",),
    "LX0609-04-01-04": ("presurg_summary", "surgery_record", "senior_course_record"),
    "LX0609-04-01-05": ("presurg_discussion",),
    # 027 需要同一快照内的病历阶段、恶性事实与正式出院记录。
    "LX0609-08-01-04": (
        "diagnosis", "discharge_record_diagnosis", "pathology_exam_report",
        "inpat_registration.discharge_horizon", "discharge_record",
    ),
    # 028 的客户文书范围只有病程，必须额外绑定严格已实施手术事实，
    # 禁止从病程关键词推断当前手术。
    # mr_diagnosis 仅供院方“病种—术式”目录按 ICD 编码确认癌种，不送入模型。
    "LX0609-04-02-03": (
        "surgery_record", "mr_surgery", "pathology_exam_master",
        "pathology_exam_report", "admission_record_diagnosis", "diagnosis",
        "discharge_record_diagnosis", "inpat_registration.discharge_horizon",
        "discharge_record", "mr_diagnosis",
    ),
    "LX0609-04-02-04": ("surgery_record", "mr_surgery", "daily_course_record"),
    "LX0609-05-01-01": (
        "surgery_record", "mr_surgery", "inpat_drug_order", "daily_course_record",
        "senior_course_record", "postsurg_firstcourse_record",
    ),
    "LX0609-11-01-01": ("surgery_record", "mr_surgery", "surgery_inform_consent"),
    # 029 的新增适用触发仅为结构化手术医嘱；严格已实施手术仍由执行器
    # 复用既有 surgery_record/mr_surgery 事实。申请单不参与本次判定。
    "LX0609-04-01-01": ("inpat_nondrug_order",),
    # 030 以结构化手术医嘱触发“有医嘱但无手术记录”，必须在同一快照
    # 绑定命中的医嘱行，不能退回来源级观察引用。
    "LX0609-04-02-02": ("inpat_nondrug_order",),
    # 麻醉同意书、访视和记录单规则都必须先由结构化手术清单确认
    # 本次住院是否实施麻醉以及麻醉方式，才能正确处理局麻例外。
    "LX0609-11-02-01": ("mr_surgery",),
    "LX0609-11-02-02": ("mr_surgery",),
    # 036/037 术后访视时限按手术结束后24小时（院方口径）与评价截止时间核对；
    # 运行病历优先手术记录，病案首页（mr_surgery）往往出院归档后才有，只作回退。
    "LX0609-04-04-01": (
        "mr_surgery",
        "surgery_record",
        "evaluation_context.horizon",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    "LX0609-04-04-02": (
        "mr_surgery",
        "surgery_record",
        "evaluation_context.horizon",
        "preane_surveil_record",
        "postane_surveil_record",
    ),
    # 038 的客户目录历史上误写为 consent_form；麻醉记录单本身是
    # 本规则的权威判定资料，必须在单规则 Evidence Session 中读取。
    "LX0609-04-04-03": ("mr_surgery", "anesthesia_record"),
    # 039 必须同时绑定严格手术事实与急救例外来源，不能只看术前讨论表。
    "LX0609-04-01-02": ("surgery_record", "mr_surgery", "rescue_record"),
    # 020/023 的“复会诊是否执行”可由病程、医嘱、检查检验或手术记录体现。
    # 全部候选必须进入同一 Evidence Session，避免判定使用了材料但 fact refs 未绑定来源。
    "LX0609-03-01-01": (
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
    "LX0609-03-01-04": (
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
    # 术前小结中的“今日急诊/急诊手术”是免除术前 MDT 的受控例外依据，
    # 必须与手术等级一并进入同一证据快照，不能让执行器另行读取旧数据。
    "LX0609-04-01-03": (
        "surgery_record",
        "mr_surgery",
        "presurg_summary",
        "presurg_discussion",
        "consultation_record",
    ),
    # 输血族逐规则绑定来源；044/045/046按开立且未取消的医嘱触发，
    # 专用病程与首页输血信息仅供记录/字段/时序核验，不代替医嘱。
    # 其他规则保留现有事件合同，各文书与收费仍保持独立来源。
    "LX0609-11-03-01": ("bloodtrans_record", "mr_bloodtrans", "consent_form"),
    "LX0609-11-03-02": ("bloodtrans_record", "mr_bloodtrans", "consent_form"),
    "LX0609-07-01-01": (
        "bloodtrans_record",
        "mr_bloodtrans",
        "blood_application",
        "exam_master",
        "labtest_master",
        "labtest_item_report",
        "daily_course_record",
        "senior_course_record",
        "inpat_nondrug_order",
        "inpat_drug_order",
    ),
    "LX0609-07-01-02": ("inpat_nondrug_order", "inpat_drug_order", "bloodtrans_record", "mr_bloodtrans", "blood_application", "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-07-02-01": ("inpat_nondrug_order", "inpat_drug_order", "bloodtrans_record", "mr_bloodtrans", "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-07-02-02": ("inpat_nondrug_order", "inpat_drug_order", "bloodtrans_record", "mr_bloodtrans", "daily_course_record",
        "senior_course_record",
    ),
    "LX0609-07-03-01": (
        "evaluation_context.horizon",
        "bloodtrans_record",
        "mr_bloodtrans",
        "daily_course_record",
        "senior_course_record",
        "inpat_nondrug_order",
        "inpat_drug_order",
    ),
    "LX0609-07-04-01": (
        "bloodtrans_record",
        "mr_bloodtrans",
        "surgery_record",
        "anesthesia_record",
        "postsurg_firstcourse_record",
    ),
    "LX0609-07-04-02": (
        "bloodtrans_record",
        "mr_bloodtrans",
        "blood_application",
        "inpat_nondrug_order",
        "inpat_bill_item",
    ),
    "LX0609-03-02-01": (
        "inpat_registration",
        "admission_record",
        "daily_course_record",
        "diffcase_discussion_record",
    ),
    # 052 需以任务冻结的评价终点判断危急值 6 小时观察窗是否已成熟；053
    # 仅核对有无处置，保持既有来源与口径。
    "LX0609-06-04-01": (
        "evaluation_context.horizon",
        "labtest_master",
        "labtest_item_report",
        "crisis_value_record",
    ),
    "LX0609-06-04-02": (
        "labtest_master",
        "labtest_item_report",
        "crisis_value_record",
    ),
    "LX0609-05-01-02": (
        "first_course_record", "senior_course_record", "consultation_record", "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-05-01-03": (
        "inpat_drug_order", "daily_course_record", "senior_course_record",
        "consultation_record", "labtest_master", "labtest_item_report",
        "evaluation_context.horizon",
    ),
    "LX0609-05-01-04": (
        "daily_course_record", "senior_course_record", "consultation_record",
        "labtest_item_report",
    ),
    "LX0609-05-01-05": (
        "first_course_record", "senior_course_record", "consultation_record", "labtest_master",
        "labtest_item_report",
    ),
    "LX0609-05-01-06": (
        "inpat_drug_order", "senior_course_record", "consultation_record",
    ),
    "LX0609-05-03-01": (
        "exam_master",
        "exam_item_report",
        "surgery_record",
        "inpat_drug_order",
        "inpat_nondrug_order",
        "daily_course_record",
        "senior_course_record",
    ),
    # 063 比较病案首页与出院记录的出院/死亡诊断；mr_diagnosis 仅作为
    # 规则内部决策支持来源，不改变客户适用文书范围。
    "LX0609-08-01-03": ("discharge_record", "mr_diagnosis", "inpat_registration", "death_record"),
    # 用户口径（2026-10-11）：重要住院事件按结构化来源由程序确定，不再读病程。
    "LX0609-08-01-05": ("discharge_record", "surgery_record", "pathology_exam_report", "mr_bloodtrans",
                        "bloodtrans_record", "rescue_record", "transfer_out_record", "transfer_in_record",
                        "crisis_value_record", "inpat_nondrug_order", "discharge_record_diagnosis"),
    "LX0609-04-05-01": ("evaluation_context.horizon", "mr_surgery"),
    "LX0609-04-05-02": ("evaluation_context.horizon", "mr_surgery"),
    "LX0609-04-05-03": ("mr_surgery",),
    # 070 的九项必须属于本次住院、且早于每一笔实际输血；住院登记、输血事件
    # 与检验结果均需进入同一 Evidence Session。
    "LX0609-07-01-03": (
        "inpat_registration",
        "admission_record",
        "mr_bloodtrans",
        "labtest_item_report",
        "daily_course_record",
        "senior_course_record",
        "inpat_nondrug_order",
        "inpat_drug_order",
    ),
    # 第一阶段扩展规则的触发事实不扩张客户文书范围，但必须进入同一
    # Evidence Session。死亡与普通出院规则互相排斥，因此两类权威记录
    # 需要在同一快照内交叉确认适用性。
    "LX0609-09-02-01": (
        "inpat_registration",
        "discharge_record",
        "evaluation_context.horizon",
    ),
    "LX0609-04-02-06": ("inpat_registration", "discharge_record"),
    "LX0609-04-02-08": ("inpat_registration", "discharge_record"),
    "LX0609-08-01-01": (
        "evaluation_context.horizon",
        "inpat_registration",
        "death_record",
    ),
    "LX0609-08-01-02": ("inpat_registration",),
    "LX0609-08-02-01": ("evaluation_context.horizon", "inpat_registration"),
    "LX0609-08-02-02": (
        "evaluation_context.horizon",
        "inpat_registration",
        "death_record",
    ),
    # 优先使用权威经治医师变更事件；部分院端尚未提供独立事件表，允许
    # 明确医嘱或普通病程的受控医师签名时间线作为替代触发。
    "LX0609-10-01-01": (
        "physician_change_event",
        "inpat_nondrug_order",
        "daily_course_record",
    ),
    "LX0609-10-02-01": ("evaluation_context.horizon", "inpat_nondrug_order"),
    "LX0609-10-02-02": ("inpat_nondrug_order",),
    "LX0609-12-02-01": ("diagnosis", "admission_record_diagnosis"),
    # 075：医嘱触发（运行病历）＋病案首页编码触发（终末），操作记录核对病程与手术记录。
    "LX0609-10-03-01": (
        "inpat_nondrug_order", "first_course_record", "daily_course_record",
        "senior_course_record", "postsurg_firstcourse_record", "surgery_record", "mr_surgery",
    ),
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


def resolve_luxian_0609_customer_document_type(source_key: str) -> str | None:
    """将受控来源解析为可对客户展示的已注册文书类型。"""

    normalized = str(source_key or "").strip().lower()
    if not _SOURCE_KEY_PATTERN.fullmatch(normalized):
        return None
    matches = _entries_for_source_key(normalized)
    registry = load_luxian_0609_source_registry()
    exact_matches = tuple(
        entry for entry in matches if entry.document_type == normalized
    )
    if len(exact_matches) == 1:
        if "." not in normalized:
            return normalized
        # 内部受控的 dotted source（如抢救医嘱）只能投影其已注册客户文书根。
        customer_document_type = normalized.split(".", 1)[0]
        return customer_document_type if customer_document_type in registry else None
    if len(matches) != 1:
        return None
    # 唯一登记的物理来源别名沿用原 source_type，避免改变既有证据坐标。
    if normalized in matches[0].source_keys and "." not in normalized:
        return normalized
    return None


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
