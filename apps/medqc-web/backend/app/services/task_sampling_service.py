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
from datetime import date, datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class TaskSamplingService:
    """任务抽样引擎"""

    async def _get_outpatient_candidates(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从门急诊文书按机构、患者、就诊三坐标生成病例候选。"""
        from ..core.supabase_client import async_execute, get_supabase

        def parse_date(value: Any, *, range_bound: bool = False) -> date:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            if isinstance(value, str):
                try:
                    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                        return date.fromisoformat(value)
                    if not range_bound:
                        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                except ValueError:
                    pass
            raise ValueError("门急诊候选日期格式无效")

        date_range = task.get("date_range") or {}
        if not isinstance(date_range, dict):
            raise ValueError("日期范围格式无效")
        start = parse_date(date_range["start"], range_bound=True) if date_range.get("start") is not None else None
        end = parse_date(date_range["end"], range_bound=True) if date_range.get("end") is not None else None
        if start and end and start > end:
            raise ValueError("日期范围起始时间不能晚于结束时间")

        departments = task.get("department_filter") or []
        if not isinstance(departments, list) or any(not isinstance(item, str) or not item.strip() for item in departments):
            raise ValueError("科室范围格式无效")
        department_set = {item.strip() for item in departments}

        refs = task.get("record_refs") or []
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
        try:
            response = await async_execute(
                sb.table("cdm.outpat_record").select(
                    "institute_id,patient_id,visit_id,visit_datetime,dept_name"
                )
            )
            documents = getattr(response, "data", None)
            if documents is None or not isinstance(documents, list):
                raise RuntimeError("候选病历数据源返回无效")
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
        # 场景是任务意图，候选必须由该场景的真实数据源证明。
        scene = task.get("scene")
        if scene == "outpatient":
            if task.get("record_ids"):
                raise ValueError("门急诊任务不能使用旧病历 ID，请提供三坐标")
            candidates = await self._get_outpatient_candidates(task)
        elif scene is not None:
            raise NotImplementedError("场景抽样暂不可用：尚未接通可验证的病历场景范围")
        else:
            candidates = await self._get_candidate_records(task)

        # 2. 根据抽样方式执行抽样
        method = task.get("sampling_method", "all")
        config = task.get("sampling_config") or {}

        if scene == "outpatient":
            if not isinstance(config, dict):
                raise ValueError("抽样配置格式无效")
            if method not in {"all", "count", "percentage"}:
                raise ValueError("无效的抽样方式")
            if method == "count":
                total = config.get("total", 50)
                if isinstance(total, bool) or not isinstance(total, int) or total <= 0:
                    raise ValueError("抽样数量必须为正整数")
            if method == "percentage":
                percentage = config.get("percentage", 10)
                if isinstance(percentage, bool) or not isinstance(percentage, (int, float)) or not 0 < percentage <= 100:
                    raise ValueError("抽样比例必须在 0 到 100 之间")
                if config.get("group_by") not in (None, "department"):
                    raise ValueError("门急诊抽样仅支持按科室分组")

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

        per_group = max(1, total // len(groups))
        remainder = total % len(groups)

        sampled = []
        for i, (group_name, group_records) in enumerate(groups.items()):
            count = per_group + (1 if i < remainder else 0)
            count = min(count, len(group_records))
            sampled.extend(random.sample(group_records, count))

        return sampled[:total]
