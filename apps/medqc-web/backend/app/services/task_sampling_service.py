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
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List

logger = logging.getLogger(__name__)
HOSPITAL_TZ = timezone(timedelta(hours=8))
_OUTPATIENT_PAGE_SIZE = 500
_OUTPATIENT_MAX_DOCUMENTS = 50000


def validate_active_running_date_range(date_range: Any) -> tuple[date | None, date | None, date]:
    """校验显式在院任务的入院日期窗；创建与抽样共用。"""
    if date_range is None:
        date_range = {}
    if not isinstance(date_range, dict):
        raise ValueError("日期范围格式无效")

    def bound(value: Any) -> date | None:
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

    start, end = bound(date_range.get("start")), bound(date_range.get("end"))
    if start and end and start > end:
        raise ValueError("日期范围起始时间不能晚于结束时间")
    today = datetime.now(HOSPITAL_TZ).date()
    if start and start > today:
        raise ValueError("入院开始日期不能晚于在院截止日期")
    if start and (today - start).days > 180:
        raise ValueError("入院日期范围最多 180 天")
    return start, end, today


def validate_scoped_sampling_config(scene: Any, method: Any, config: Any) -> None:
    """校验新场景抽样参数，创建与实际抽样使用同一合同。"""
    if scene not in {"outpatient", "running"}:
        return
    if not isinstance(config, dict):
        raise ValueError("抽样配置格式无效")
    if not isinstance(method, str) or method not in {"all", "count", "percentage"}:
        raise ValueError("无效的抽样方式")
    if method == "count":
        total = config.get("total", 50)
        if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
            raise ValueError("抽样数量必须为正整数")
        if not isinstance(config.get("by_department", False), bool):
            raise ValueError("按科室抽样参数必须为布尔值")
    if method == "percentage":
        percentage = config.get("percentage", 10)
        if isinstance(percentage, bool) or not isinstance(percentage, (int, float)) or not 0 < percentage <= 100:
            raise ValueError("抽样比例必须在 0 到 100 之间")
        if config.get("group_by") not in (None, "department"):
            raise ValueError("场景抽样仅支持按科室分组")


class TaskSamplingService:
    """任务抽样引擎"""

    async def _get_active_running_candidates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """仅为显式在院范围的运行任务生成可信三坐标候选。"""
        import anyio

        from .case_scope_service import CaseScopeService

        start, end, today = validate_active_running_date_range(task.get("date_range"))
        departments = task.get("department_filter")
        if departments is None:
            departments = []
        if not isinstance(departments, list) or any(
            not isinstance(item, str) or not item.strip() for item in departments
        ):
            raise ValueError("科室范围格式无效")
        departments = [item.strip() for item in departments]
        refs = task.get("record_refs")
        if refs is None:
            refs = []
        if not isinstance(refs, list):
            raise ValueError("指定病例三坐标格式无效")

        def identity(item: Any) -> tuple[str, str, str]:
            if not isinstance(item, dict):
                raise ValueError("指定病例三坐标格式无效")
            coordinates = tuple(item.get(key) for key in ("institute_id", "patient_id", "visit_id"))
            if any(not isinstance(value, str) or not value.strip() for value in coordinates):
                raise ValueError("指定病例三坐标不完整")
            return tuple(value.strip() for value in coordinates)

        requested = [identity(ref) for ref in refs]
        if len(requested) != len(set(requested)):
            raise ValueError("指定病例三坐标重复")

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

        validate_scoped_sampling_config(scene, method, config)

        # 场景是任务意图，候选必须由该场景的真实数据源证明。
        if scene == "outpatient":
            if task.get("record_ids"):
                raise ValueError("门急诊任务不能使用旧病历 ID，请提供三坐标")
            candidates = await self._get_outpatient_candidates(task)
        elif scene == "running" and config.get("case_scope") == "active":
            if task.get("record_ids"):
                raise ValueError("运行任务不能使用旧病历 ID，请提供三坐标")
            candidates = await self._get_active_running_candidates(task)
        elif scene is not None:
            raise NotImplementedError("场景抽样暂不可用：尚未接通可验证的病历场景范围")
        else:
            candidates = await self._get_candidate_records(task)

        if not candidates:
            logger.info("任务候选病历为空")
            return []

        if method == "all":
            return candidates
        elif method == "count":
            return self._sample_by_count(candidates, config)
        elif method == "percentage":
            return self._sample_by_percentage(candidates, config)
        else:
            logger.warning(f"未知的抽样方式: {method}，使用全量")
            return candidates

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
