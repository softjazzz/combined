"""
任务抽样引擎服务

功能:
- 全量抽样（取全部匹配病历）
- 总数抽样（随机抽 N 条）
- 百分比抽样（按科室/类型/医生分组后各取 X%）
"""

import random
import logging
import re
import math
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)
HOSPITAL_TZ = timezone(timedelta(hours=8))
_OUTPATIENT_PAGE_SIZE = 500
_OUTPATIENT_MAX_DOCUMENTS = 50000


def _date_bound(value: Any) -> date | None:
    """日期窗边界：只接受 date 或 YYYY-MM-DD 字符串，不接受带时刻的值。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        raise ValueError("日期范围格式无效")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError("日期范围格式无效")


def validate_active_running_date_range(date_range: Any) -> tuple[date | None, date | None, date]:
    """校验显式在院任务的入院日期窗；创建与抽样共用。"""
    if date_range is None:
        date_range = {}
    if not isinstance(date_range, dict):
        raise ValueError("日期范围格式无效")

    start, end = _date_bound(date_range.get("start")), _date_bound(date_range.get("end"))
    if start and end and start > end:
        raise ValueError("日期范围起始时间不能晚于结束时间")
    today = datetime.now(HOSPITAL_TZ).date()
    if start and start > today:
        raise ValueError("入院开始日期不能晚于在院截止日期")
    if start and (today - start).days > 180:
        raise ValueError("入院日期范围最多 180 天")
    return start, end, today


# 终末口径 B（2026-09-30）：终末任务按“期间出院”取候选，不核验是否已归档。
FINAL_CASE_SCOPE = "discharged"
MAX_DISCHARGE_WINDOW_DAYS = 31


def validate_discharged_final_date_range(date_range: Any) -> tuple[date, date]:
    """校验终末（已出院）任务的出院日期窗；创建与抽样共用。

    起止必须同时填写，起不晚于止、止不晚于今天（医院时区），跨度最多 31 天
    （与病例范围服务“期间出院”合同一致，避免创建通过、抽样才失败）。
    """
    if not isinstance(date_range, dict):
        raise ValueError("终末任务必须填写出院日期范围")
    start, end = _date_bound(date_range.get("start")), _date_bound(date_range.get("end"))
    if start is None or end is None:
        raise ValueError("终末任务必须填写出院开始日期和结束日期")
    if start > end:
        raise ValueError("出院开始日期不能晚于结束日期")
    if end > datetime.now(HOSPITAL_TZ).date():
        raise ValueError("出院结束日期不能晚于今天")
    if (end - start).days + 1 > MAX_DISCHARGE_WINDOW_DAYS:
        raise ValueError("出院日期范围最多 31 天")
    return start, end


def validate_scene_case_scope(scene: Any, method: Any, config: Any, date_range: Any) -> None:
    """创建、编辑、模板共用：场景病例范围与日期窗的唯一校验入口。

    显式选择的病例范围才按新合同校验，与实际抽样同一合同：运行=当前在院（入院日期窗），
    终末=已出院（出院日期窗，口径 B），门急诊校验抽样参数。未带 case_scope 的历史运行/终末
    配置保持原兼容行为（创建不校验，抽样时明确不可用），其他 case_scope 取值一律拒绝。
    """
    config = config if isinstance(config, dict) else {}
    validate_task_clinical_doctors(scene, config.get("clinical_doctors"))
    validate_task_score_filter(scene, config.get("score_filter"))
    if config.get("score_filter") is not None:
        from .scoring_service import get_workstation_standard
        get_workstation_standard(scene, config["score_filter"]["standard_id"])
    case_scope = config.get("case_scope")
    if scene == "outpatient":
        validate_scoped_sampling_config(scene, method, config)
    elif scene == "running" and case_scope == "active":
        validate_scoped_sampling_config(scene, method, config)
        validate_active_running_date_range(date_range)
    elif scene == "final" and case_scope == FINAL_CASE_SCOPE:
        validate_scoped_sampling_config(scene, method, config)
        validate_discharged_final_date_range(date_range)
    elif case_scope is not None:
        raise ValueError("病例范围与任务场景不匹配")


def validate_scoped_sampling_config(scene: Any, method: Any, config: Any) -> None:
    """校验新场景抽样参数，创建与实际抽样使用同一合同。"""
    if scene not in {"outpatient", "running", "final"}:
        return
    if not isinstance(config, dict):
        raise ValueError("抽样配置格式无效")
    validate_task_clinical_doctors(scene, config.get("clinical_doctors"))
    validate_task_score_filter(scene, config.get("score_filter"))
    if not isinstance(method, str) or method not in {"all", "count", "percentage", "department_count", "department_ratio"}:
        raise ValueError("无效的抽样方式")
    if method in {"department_count", "department_ratio"}:
        allowed = {"case_scope", "total", "score_filter", "clinical_doctors"} if method == "department_count" else {"case_scope", "percentage", "max_per_group", "score_filter", "clinical_doctors"}
        if set(config) - allowed:
            raise ValueError("科室抽样配置含不支持的字段")
    if method in {"count", "department_count"}:
        total = config.get("total") if method == "department_count" else config.get("total", 50)
        if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            raise ValueError("抽样数量必须为正整数")
        if method == "department_count" and total > 10000:
            raise ValueError("每科室抽样数量不能超过 10000")
        if not isinstance(config.get("by_department", False), bool):
            raise ValueError("按科室抽样参数必须为布尔值")
    if method in {"percentage", "department_ratio"}:
        percentage = config.get("percentage", 10)
        if isinstance(percentage, bool) or not isinstance(percentage, (int, float)) or not 0 < percentage <= 100:
            raise ValueError("抽样比例必须在 0 到 100 之间")
        if config.get("group_by") not in (None, "department"):
            raise ValueError("场景抽样仅支持按科室分组")
        if method == "department_ratio":
            maximum = config.get("max_per_group")
            if isinstance(maximum, bool) or not isinstance(maximum, int) or not 1 <= maximum <= 10000:
                raise ValueError("每科室最多份数必须为 1 到 10000 的整数")


def validate_task_clinical_doctors(scene: Any, value: Any) -> None:
    """临床医生沿用病案首页主治医师签名，机构隔离，不推断账号身份。"""
    if value is None:
        return
    if scene not in {"running", "final"}:
        raise ValueError("临床医生筛选仅支持运行和终末场景")
    if not isinstance(value, list) or not 1 <= len(value) <= 100:
        raise ValueError("临床医生筛选须为 1 到 100 条机构与主治医师引用")
    identities = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"institute_id", "physician_name"} or any(
            not isinstance(item[key], str) or not item[key].strip() or len(item[key]) > 100
            for key in ("institute_id", "physician_name")
        ):
            raise ValueError("临床医生筛选缺少有效机构或主治医师签名")
        identities.append((item["institute_id"].strip(), item["physician_name"].strip()))
    if len(identities) != len(set(identities)):
        raise ValueError("临床医生筛选引用重复")


def validate_task_score_filter(scene: Any, value: Any) -> None:
    """评分条件只引用同场景既有标准，不推断缺失得分。"""
    if value is None:
        return
    if scene not in {"running", "final"}:
        raise ValueError("评分筛选仅支持运行和终末场景")
    if not isinstance(value, dict) or set(value) - {"standard_id", "score_min", "score_max"}:
        raise ValueError("评分筛选配置格式无效")
    if not isinstance(value.get("standard_id"), str) or not value["standard_id"].strip():
        raise ValueError("评分筛选必须选择评分标准")
    for key in ("score_min", "score_max"):
        number = value.get(key)
        if key in value and (isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number)):
            raise ValueError("得分区间必须是有限数值")
    if value.get("score_min") is not None and value.get("score_max") is not None and value["score_min"] > value["score_max"]:
        raise ValueError("最低得分不能高于最高得分")


def validate_specified_case_sampling(method: Any, config: Any, refs: Any) -> None:
    """指定三坐标病例是固定集合，不允许再次随机抽样。"""
    if refs and (method != "all" or set(config or {}) - {"case_scope"}):
        raise ValueError("指定病历不允许二次抽样，请使用全部病历且清空抽样参数")


class TaskSamplingService:
    """任务抽样引擎"""

    @staticmethod
    def _identity(item: Any) -> tuple[str, str, str]:
        if not isinstance(item, dict):
            raise ValueError("指定病例三坐标格式无效")
        coordinates = tuple(item.get(key) for key in ("institute_id", "patient_id", "visit_id"))
        if any(not isinstance(value, str) or not value.strip() for value in coordinates):
            raise ValueError("指定病例三坐标不完整")
        return tuple(value.strip() for value in coordinates)

    @classmethod
    def _scope_inputs(cls, task: Dict[str, Any]) -> tuple[list[str], list[tuple[str, str, str]]]:
        """住院类场景任务共用：科室范围与指定三坐标（去重校验）。"""
        departments = task.get("department_filter")
        if departments is None:
            departments = []
        if not isinstance(departments, list) or any(
            not isinstance(item, str) or not item.strip() for item in departments
        ):
            raise ValueError("科室范围格式无效")
        refs = task.get("record_refs")
        if refs is None:
            refs = []
        if not isinstance(refs, list):
            raise ValueError("指定病例三坐标格式无效")
        requested = [cls._identity(ref) for ref in refs]
        if len(requested) != len(set(requested)):
            raise ValueError("指定病例三坐标重复")
        return [item.strip() for item in departments], requested

    async def _get_active_running_candidates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """仅为显式在院范围的运行任务生成可信三坐标候选。"""
        import anyio

        from .case_scope_service import CaseScopeService

        start, end, today = validate_active_running_date_range(task.get("date_range"))
        departments, requested = self._scope_inputs(task)
        identity = self._identity

        try:
            result = await anyio.to_thread.run_sync(
                lambda: CaseScopeService().resolve_hospitalization_scope(
                    scope_mode="active",
                    as_of_date=today,
                    admission_start_date=start,
                    discharge_start_date=None,
                    discharge_end_date=None,
                    departments=departments,
                )
            )
        except Exception as exc:
            logger.warning("运行任务在院候选查询失败: %s", type(exc).__name__)
            raise RuntimeError("候选病历数据源不可用") from exc
        if result.source_status != "ready":
            raise RuntimeError("候选病历数据源未就绪")
        try:
            if len(result.case_refs) != len(result.selected):
                raise ValueError("三坐标数量不一致")
            candidates = {}
            seen = set()
            for case_ref, row in zip(result.case_refs, result.selected):
                key = identity(row)
                if key != (case_ref.institute_id, case_ref.patient_id, case_ref.visit_id):
                    raise ValueError("三坐标不一致")
                admission = row.get("admission_time")
                if (
                    key in seen
                    or row.get("hospitalization_status") != "active"
                    or not isinstance(admission, datetime)
                    or admission.tzinfo is not None
                    or admission.date() > today
                    or (start and admission.date() < start)
                    or (departments and row.get("department") not in departments)
                ):
                    raise ValueError("在院候选状态或范围无效")
                seen.add(key)
                if end and admission.date() > end:
                    continue
                candidates[key] = {
                    "institute_id": key[0],
                    "patient_id": key[1],
                    "visit_id": key[2],
                    "department": row.get("department"),
                    "admission_date": admission.date().isoformat(),
                }
        except (AttributeError, TypeError, ValueError) as exc:
            raise RuntimeError("运行任务候选病历数据无效") from exc
        if requested and not set(requested).issubset(candidates):
            raise ValueError("指定病历不存在或不属于在院筛选范围")
        if not candidates:
            raise ValueError("在院筛选范围内无候选病历")
        return [candidates[key] for key in requested] if requested else list(candidates.values())

    async def _get_discharged_final_candidates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """终末任务（口径 B：期间出院，未核验归档）从源库住院口径生成可信三坐标候选。"""
        import anyio

        from .case_scope_service import CaseScopeService

        start, end = validate_discharged_final_date_range(task.get("date_range"))
        departments, requested = self._scope_inputs(task)
        today = datetime.now(HOSPITAL_TZ).date()
        try:
            result = await anyio.to_thread.run_sync(
                lambda: CaseScopeService().resolve_hospitalization_scope(
                    scope_mode=FINAL_CASE_SCOPE,
                    as_of_date=today,
                    admission_start_date=None,
                    discharge_start_date=start,
                    discharge_end_date=end,
                    departments=departments,
                )
            )
        except Exception as exc:
            logger.warning("终末任务出院候选查询失败: %s", type(exc).__name__)
            raise RuntimeError("候选病历数据源不可用") from exc
        if result.source_status != "ready":
            raise RuntimeError("候选病历数据源未就绪")
        try:
            if len(result.case_refs) != len(result.selected):
                raise ValueError("三坐标数量不一致")
            candidates: Dict[tuple[str, str, str], Dict[str, Any]] = {}
            for case_ref, row in zip(result.case_refs, result.selected):
                key = self._identity(row)
                if key != (case_ref.institute_id, case_ref.patient_id, case_ref.visit_id):
                    raise ValueError("三坐标不一致")
                discharge = row.get("discharge_time")
                if (
                    key in candidates
                    or row.get("hospitalization_status") != "discharged"
                    or not isinstance(discharge, datetime)
                    or discharge.tzinfo is not None
                    or not start <= discharge.date() <= end
                    or (departments and row.get("department") not in departments)
                ):
                    raise ValueError("出院候选状态或范围无效")
                candidates[key] = {
                    "institute_id": key[0],
                    "patient_id": key[1],
                    "visit_id": key[2],
                    "department": row.get("department"),
                    "discharge_date": discharge.date().isoformat(),
                }
        except (AttributeError, TypeError, ValueError) as exc:
            raise RuntimeError("终末任务候选病历数据无效") from exc
        if requested and not set(requested).issubset(candidates):
            raise ValueError("指定病历不存在或不属于出院筛选范围")
        if not candidates:
            raise ValueError("出院筛选范围内无候选病历")
        return [candidates[key] for key in requested] if requested else list(candidates.values())

    async def _get_outpatient_candidates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从门急诊文书按机构、患者、就诊三坐标生成病例候选。"""
        from ..core.supabase_client import async_execute, get_supabase

        def parse_date(value: Any, *, range_bound: bool = False) -> date:
            if isinstance(value, datetime):
                if range_bound:
                    raise ValueError("日期范围格式无效")
                return value.astimezone(HOSPITAL_TZ).date() if value.tzinfo else value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                try:
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        return date.fromisoformat(value)
                    if not range_bound:
                        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        return parsed.astimezone(HOSPITAL_TZ).date() if parsed.tzinfo else parsed.date()
                except ValueError:
                    pass
            raise ValueError("门急诊候选日期格式无效")

        date_range = task.get("date_range")
        if date_range is None:
            date_range = {}
        if not isinstance(date_range, dict):
            raise ValueError("日期范围格式无效")
        start = parse_date(date_range["start"], range_bound=True) if date_range.get("start") is not None else None
        end = parse_date(date_range["end"], range_bound=True) if date_range.get("end") is not None else None
        if start and end and start > end:
            raise ValueError("日期范围起始时间不能晚于结束时间")

        departments = task.get("department_filter")
        if departments is None:
            departments = []
        if not isinstance(departments, list) or any(not isinstance(item, str) or not item.strip() for item in departments):
            raise ValueError("科室范围格式无效")
        department_set = {item.strip() for item in departments}

        refs = task.get("record_refs")
        if refs is None:
            refs = []
        if not isinstance(refs, list):
            raise ValueError("指定病例三坐标格式无效")

        def identity(item: Dict[str, Any]) -> tuple[str, str, str]:
            if not isinstance(item, dict):
                raise ValueError("指定病例三坐标格式无效")
            coordinates = tuple(item.get(key) for key in ("institute_id", "patient_id", "visit_id"))
            if any(not isinstance(value, str) or not value.strip() for value in coordinates):
                raise ValueError("门急诊病例三坐标不完整")
            return tuple(value.strip() for value in coordinates)

        requested = {identity(ref) for ref in refs}
        if len(requested) != len(refs):
            raise ValueError("指定病例三坐标重复")

        sb = get_supabase()
        if sb is None:
            raise RuntimeError("候选病历数据源不可用")
        documents = []
        offset = 0
        expected_count = None
        seen_documents = set()
        try:
            while True:
                query = sb.table("cdm.outpat_record").select(
                    "institute_id,patient_id,visit_id,document_id,visit_datetime,dept_name",
                    count="exact",
                )
                for column_name in ("institute_id", "patient_id", "visit_id", "document_id"):
                    query = query.order(column_name)
                response = await async_execute(query.range(offset, offset + _OUTPATIENT_PAGE_SIZE - 1))
                page = getattr(response, "data", None)
                count = getattr(response, "count", None)
                if (not isinstance(page, list) or not isinstance(count, int) or isinstance(count, bool)
                    or count < offset + len(page) or len(page) > _OUTPATIENT_PAGE_SIZE):
                    raise RuntimeError("候选病历数据源返回无效")
                if expected_count is not None and count != expected_count:
                    raise RuntimeError("候选病历数据源读取期间发生变化")
                expected_count = count
                if count > _OUTPATIENT_MAX_DOCUMENTS or (not page and offset < count):
                    raise RuntimeError("候选病历数据源读取不完整")
                for document in page:
                    if not isinstance(document, dict):
                        raise RuntimeError("候选病历数据源返回无效")
                    document_id = document.get("document_id")
                    document_key = (*identity(document), document_id)
                    if (not isinstance(document_id, str) or not document_id.strip()
                        or document_key in seen_documents):
                        raise RuntimeError("候选病历文书身份无效")
                    seen_documents.add(document_key)
                documents.extend(page)
                offset += len(page)
                if offset >= count:
                    break
        except Exception as exc:
            logger.warning("门急诊候选查询失败: %s", type(exc).__name__)
            raise RuntimeError("候选病历数据源不可用") from exc

        candidates: Dict[tuple[str, str, str], Dict[str, Any]] = {}
        for document in documents:
            try:
                key = identity(document)
                value = document.get("visit_datetime")
                visit_day = parse_date(value) if value is not None else None
            except ValueError as exc:
                raise RuntimeError("门急诊候选病历数据无效") from exc
            department = document.get("dept_name")
            department = department.strip() if isinstance(department, str) else None
            if start and (visit_day is None or visit_day < start):
                continue
            if end and (visit_day is None or visit_day > end):
                continue
            if department_set and department not in department_set:
                continue
            candidates.setdefault(
                key,
                {
                    "institute_id": key[0],
                    "patient_id": key[1],
                    "visit_id": key[2],
                    "department": department,
                    "visit_datetime": value,
                },
            )

        if requested and not requested.issubset(candidates):
            raise ValueError("指定病历不存在或不属于门急诊筛选范围")
        if requested:
            return [candidates[identity(ref)] for ref in refs]
        return list(candidates.values())

    async def sample(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据任务配置执行抽样

        Args:
            task: 任务配置，包含 date_range, department_filter, record_ids,
                  sampling_method, sampling_config

        Returns:
            抽样后的病历列表
        """
        scene = task.get("scene")
        method = task.get("sampling_method", "all")
        config = task.get("sampling_config")
        if config is None:
            config = {}

        if isinstance(config, dict):
            validate_task_clinical_doctors(scene, config.get("clinical_doctors"))
            validate_task_score_filter(scene, config.get("score_filter"))
        validate_scoped_sampling_config(scene, method, config)
        validate_specified_case_sampling(method, config, task.get("record_refs"))

        # 场景是任务意图，候选必须由该场景的真实数据源证明。
        if scene == "outpatient":
            if task.get("record_ids"):
                raise ValueError("门急诊任务不能使用旧病历 ID，请提供三坐标")
            candidates = await self._get_outpatient_candidates(task)
        elif scene == "running" and config.get("case_scope") == "active":
            if task.get("record_ids"):
                raise ValueError("运行任务不能使用旧病历 ID，请提供三坐标")
            candidates = await self._get_active_running_candidates(task)
        elif scene == "final" and config.get("case_scope") == FINAL_CASE_SCOPE:
            if task.get("record_ids"):
                raise ValueError("终末任务不能使用旧病历 ID，请提供三坐标")
            candidates = await self._get_discharged_final_candidates(task)
        elif scene is not None:
            raise NotImplementedError("场景抽样暂不可用：尚未接通可验证的病历场景范围")
        else:
            candidates = await self._get_candidate_records(task)

        if config.get("clinical_doctors") is not None:
            candidates = await self._filter_clinical_doctor_candidates(candidates, config["clinical_doctors"])
        if config.get("score_filter") is not None:
            candidates = await self._filter_scored_candidates(candidates, scene, config["score_filter"])

        if not candidates:
            logger.info("任务候选病历为空")
            return []

        if method == "all":
            return candidates
        elif method == "count":
            return self._sample_by_count(candidates, config)
        elif method == "percentage":
            return self._sample_by_percentage(candidates, config)
        elif method in {"department_count", "department_ratio"}:
            return self._sample_by_department(candidates, method, config)
        else:
            logger.warning(f"未知的抽样方式: {method}，使用全量")
            return candidates

    async def _filter_clinical_doctor_candidates(
        self, candidates: List[Dict[str, Any]], doctors: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        import anyio
        from ..database.connection import SessionLocal
        from ..database.models.cdm import MedicalRecordFrontpage
        from sqlalchemy import select, tuple_

        identities = {self._identity(row) for row in candidates}
        selected = {(item["institute_id"].strip(), item["physician_name"].strip()) for item in doctors}

        def load():
            matching = set()
            with SessionLocal() as session:
                ordered = sorted(identities)
                for start in range(0, len(ordered), 500):
                    rows = session.execute(select(
                        MedicalRecordFrontpage.institute_id, MedicalRecordFrontpage.patient_id,
                        MedicalRecordFrontpage.visit_id, MedicalRecordFrontpage.attending_physician_sign,
                    ).where(tuple_(
                        MedicalRecordFrontpage.institute_id, MedicalRecordFrontpage.patient_id,
                        MedicalRecordFrontpage.visit_id,
                    ).in_(ordered[start:start + 500]))).all()
                    for institute, patient, visit, physician in rows:
                        if (str(institute).strip(), str(physician or "").strip()) in selected:
                            matching.add((str(institute).strip(), str(patient).strip(), str(visit).strip()))
            return [row for row in candidates if self._identity(row) in matching]

        try:
            return await anyio.to_thread.run_sync(load)
        except Exception as exc:
            logger.warning("临床医生筛选来源不可用 error_type=%s", type(exc).__name__)
            raise RuntimeError("临床医生筛选来源不可用") from None

    async def _filter_scored_candidates(
        self, candidates: List[Dict[str, Any]], scene: str, score_filter: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """对完整真实候选集计分后再抽样，复用病历池的 Canonical 评分 owner。"""
        import anyio
        from ..database.connection import SessionLocal
        from .custom_qc_workspace_service import CustomQCWorkspaceService
        from .scoring_service import get_workstation_standard, score_workstation_page, standard_needs_department
        from .medical_records.query_service import load_scoring_departments

        if len(candidates) > 5000:
            raise ValueError("评分筛选范围超过 5000 例，请缩小范围")

        def load():
            standard = get_workstation_standard(scene, score_filter["standard_id"])
            identities = [self._identity(row) for row in candidates]
            # 任务筛选不能将科室来源故障降级为空命中；在计分 owner 的兼容降级路径外读取。
            departments = (
                load_scoring_departments(identities, session_factory=SessionLocal)
                if standard_needs_department(standard) else {}
            )
            refs = [{key: row[key] for key in ("institute_id", "patient_id", "visit_id")} for row in candidates]
            anchors = CustomQCWorkspaceService().build_luxian_0609_completed_record_result_summaries(
                record_refs=refs, session_factory=SessionLocal,
            )
            states, _ = score_workstation_page(
                {self._identity(row): scene for row in candidates}, anchors,
                session_factory=SessionLocal, standard_loader=lambda _: standard, strict=True,
                department_loader=lambda *_args, **_kwargs: departments,
            )
            matching = []
            for row in candidates:
                state = states.get(self._identity(row)) or {}
                score = state.get("score")
                if state.get("status") != "scored" or isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                    continue
                if score_filter.get("score_min") is not None and score < score_filter["score_min"]:
                    continue
                if score_filter.get("score_max") is not None and score > score_filter["score_max"]:
                    continue
                matching.append(row)
            return matching

        try:
            return await anyio.to_thread.run_sync(load)
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("任务评分筛选不可用 error_type=%s", type(exc).__name__)
            raise RuntimeError("评分暂不可用，无法筛选") from None

    async def _get_candidate_records(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取候选病历池"""
        from ..core.supabase_client import get_supabase, async_execute

        sb = get_supabase()
        if sb is None:
            raise RuntimeError("候选病历数据源不可用")

        # 指定病历必须实际存在，不能在查询失败时构造候选记录。
        record_ids = task.get("record_ids", [])
        if record_ids:
            try:
                resp = await async_execute(
                    sb.table('medical_records')
                    .select('id,patient_name,department,admission_date')
                    .in_('id', record_ids)
                )
                records = list(getattr(resp, 'data', None) or [])
            except Exception as exc:
                logger.warning("从数据库获取指定病历失败", exc_info=True)
                raise RuntimeError("候选病历数据源不可用") from exc
            if set(record_ids) != {record.get("id") for record in records}:
                raise ValueError("指定病历不存在或不可访问，请核对病历范围")
            return records

        # 从数据库按条件查询
        if sb is not None:
            try:
                query = sb.table('medical_records').select(
                    'id,patient_name,department,admission_date,discharge_date,doctor_name'
                )

                # 应用日期范围
                date_range = task.get("date_range", {})
                if date_range:
                    if date_range.get("start"):
                        query = query.gte('admission_date', date_range["start"])
                    if date_range.get("end"):
                        query = query.lte('admission_date', date_range["end"])

                # 应用科室筛选
                dept_filter = task.get("department_filter", [])
                if dept_filter:
                    query = query.in_('department', dept_filter)

                # 限制最大返回
                query = query.limit(10000)
                resp = await async_execute(query)
                return list(getattr(resp, 'data', None) or [])
            except Exception as exc:
                logger.warning("从数据库获取候选病历失败", exc_info=True)
                raise RuntimeError("候选病历数据源不可用") from exc

    def _sample_by_department(self, candidates: List[Dict], method: str, config: Dict[str, Any]) -> List[Dict]:
        """按机构内科室分别抽样；比例沿用向下取整、非空组至少一份的约定。"""
        groups: Dict[tuple[str, str], List[Dict]] = {}
        for candidate in candidates:
            institute, department = candidate.get("institute_id"), candidate.get("department")
            if not isinstance(institute, str) or not institute.strip() or not isinstance(department, str) or not department.strip():
                raise ValueError("科室抽样缺少可信机构或科室归属")
            groups.setdefault((institute, department), []).append(candidate)
        sampled = []
        for records in groups.values():
            count = config["total"] if method == "department_count" else min(
                config["max_per_group"], max(1, int(len(records) * config["percentage"] / 100)),
            )
            sampled.extend(random.sample(records, min(count, len(records))))
        return sampled

    def _sample_by_count(
        self, candidates: List[Dict], config: Dict[str, Any]
    ) -> List[Dict]:
        """按总数抽样"""
        total = config.get("total", 50)
        total = min(total, len(candidates))

        if config.get("by_department", False):
            # 按科室均匀抽样
            return self._stratified_sample(candidates, "department", total)

        return random.sample(candidates, total)

    def _sample_by_percentage(
        self, candidates: List[Dict], config: Dict[str, Any]
    ) -> List[Dict]:
        """按百分比抽样"""
        percentage = config.get("percentage", 10) / 100.0
        group_by = config.get("group_by", None)  # department | doctor_name | type

        if group_by:
            # 分组后各取 X%
            groups: Dict[str, List[Dict]] = {}
            for c in candidates:
                key = c.get(group_by, "未分类")
                groups.setdefault(key, []).append(c)

            sampled = []
            for group_name, group_records in groups.items():
                count = max(1, int(len(group_records) * percentage))
                count = min(count, len(group_records))
                sampled.extend(random.sample(group_records, count))
            return sampled
        else:
            count = max(1, int(len(candidates) * percentage))
            count = min(count, len(candidates))
            return random.sample(candidates, count)

    def _stratified_sample(
        self, candidates: List[Dict], group_key: str, total: int
    ) -> List[Dict]:
        """分层抽样（按指定字段均匀分配）"""
        groups: Dict[str, List[Dict]] = {}
        for c in candidates:
            key = c.get(group_key, "未分类")
            groups.setdefault(key, []).append(c)

        if not groups:
            return []

        target = min(total, len(candidates))
        counts = {group: 0 for group in groups}
        remaining = target
        while remaining:
            eligible = [group for group, records in groups.items() if counts[group] < len(records)]
            quotient, remainder = divmod(remaining, len(eligible))
            if quotient:
                for group in eligible:
                    added = min(quotient, len(groups[group]) - counts[group])
                    counts[group] += added
                    remaining -= added
            if remainder and remaining:
                eligible = [group for group in eligible if counts[group] < len(groups[group])]
                for group in random.sample(eligible, min(remainder, len(eligible))):
                    counts[group] += 1
                    remaining -= 1

        sampled = []
        for group, records in groups.items():
            sampled.extend(random.sample(records, counts[group]))
        return sampled
