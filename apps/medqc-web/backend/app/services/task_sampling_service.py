"""
任务抽样引擎服务

功能:
- 全量抽样（取全部匹配病历）
- 总数抽样（随机抽 N 条）
- 百分比抽样（按科室/类型/医生分组后各取 X%）
"""

import random
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class TaskSamplingService:
    """任务抽样引擎"""

    async def sample(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据任务配置执行抽样

        Args:
            task: 任务配置，包含 date_range, department_filter, record_ids,
                  sampling_method, sampling_config

        Returns:
            抽样后的病历列表
        """
        # 场景是任务意图，不能作为病例已满足该场景的证据。
        if task.get("scene") is not None:
            raise NotImplementedError("场景抽样暂不可用：尚未接通可验证的病历场景范围")

        # 1. 获取候选病历池
        candidates = await self._get_candidate_records(task)

        if not candidates:
            logger.warning(f"任务 {task.get('task_name', '')} 没有匹配的候选病历")
            return []

        # 2. 根据抽样方式执行抽样
        method = task.get("sampling_method", "all")
        config = task.get("sampling_config", {})

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
