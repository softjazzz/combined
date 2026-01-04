"""
整改管理服务
Rectification Service
"""
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.schemas.rectification import (
    RectificationTaskCreate, RectificationTaskUpdate,
    TaskAssignment, TaskSubmission, TaskReview,
    RectificationTaskResponse, RectificationTaskListResponse,
    TaskFilters, TaskStats,
    TaskStatus, TaskSeverity, ReviewResult
)
from app.services.database import db_service


class RectificationService:
    """整改管理服务"""

    async def create_task(
        self,
        task_data: RectificationTaskCreate,
        assigner_id: Optional[str] = None,
        assigner_name: Optional[str] = None
    ) -> Optional[RectificationTaskResponse]:
        """创建整改任务"""
        try:
            if not db_service._available():
                logger.warning("Database not available")
                return None

            data = {
                'id': str(uuid4()),
                'qc_result_id': task_data.qc_result_id,
                'defect_id': task_data.defect_id,
                'record_id': task_data.record_id,
                'appeal_id': task_data.appeal_id,
                'task_title': task_data.task_title,
                'task_description': task_data.task_description,
                'defect_type': task_data.defect_type,
                'severity': task_data.severity.value,
                'assignee_id': task_data.assignee_id,
                'assignee_name': task_data.assignee_name,
                'assigner_id': assigner_id,
                'assigner_name': assigner_name,
                'department_id': task_data.department_id,
                'due_date': task_data.due_date.isoformat() if task_data.due_date else None,
                'status': TaskStatus.PENDING.value,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            response = db_service.client.table('rectification_tasks') \
                .insert(data) \
                .execute()

            if response.data and len(response.data) > 0:
                # 记录操作日志
                await self._log_action(
                    task_id=response.data[0]['id'],
                    action='created',
                    operator_id=assigner_id or 'system',
                    operator_name=assigner_name or 'System',
                    comment=f"创建整改任务: {task_data.task_title}"
                )
                return RectificationTaskResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"创建整改任务失败: {str(e)}")
            return None

    async def get_task(self, task_id: str) -> Optional[RectificationTaskResponse]:
        """获取整改任务详情"""
        try:
            if not db_service._available():
                return None

            response = db_service.client.table('rectification_tasks') \
                .select('*') \
                .eq('id', task_id) \
                .execute()

            if response.data and len(response.data) > 0:
                return RectificationTaskResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"获取整改任务详情失败: {str(e)}")
            return None

    async def list_tasks(
        self,
        filters: TaskFilters
    ) -> RectificationTaskListResponse:
        """查询整改任务列表"""
        try:
            if not db_service._available():
                return RectificationTaskListResponse(items=[], total=0)

            query = db_service.client.table('rectification_tasks').select('*', count='exact')

            # 应用筛选条件
            if filters.status:
                query = query.eq('status', filters.status.value)
            if filters.severity:
                query = query.eq('severity', filters.severity.value)
            if filters.assignee_id:
                query = query.eq('assignee_id', filters.assignee_id)
            if filters.assigner_id:
                query = query.eq('assigner_id', filters.assigner_id)
            if filters.department_id:
                query = query.eq('department_id', filters.department_id)
            if filters.start_date:
                query = query.gte('created_at', filters.start_date.isoformat())
            if filters.end_date:
                query = query.lte('created_at', filters.end_date.isoformat())
            
            # 筛选逾期任务
            if filters.overdue_only:
                query = query.lt('due_date', datetime.utcnow().isoformat()) \
                    .in_('status', ['pending', 'in_progress'])

            # 分页
            offset = (filters.page - 1) * filters.page_size
            response = query.order('created_at', desc=True) \
                .range(offset, offset + filters.page_size - 1) \
                .execute()

            items = [RectificationTaskResponse(**item) for item in (response.data or [])]
            total = response.count if hasattr(response, 'count') else len(items)

            return RectificationTaskListResponse(
                items=items,
                total=total,
                page=filters.page,
                page_size=filters.page_size,
                has_more=total > offset + len(items)
            )

        except Exception as e:
            logger.error(f"查询整改任务列表失败: {str(e)}")
            return RectificationTaskListResponse(items=[], total=0)

    async def assign_task(
        self,
        task_id: str,
        assignment: TaskAssignment,
        assigner_id: str,
        assigner_name: str
    ) -> Optional[RectificationTaskResponse]:
        """分配/重新分配整改任务"""
        try:
            if not db_service._available():
                return None

            data = {
                'assignee_id': assignment.assignee_id,
                'assignee_name': assignment.assignee_name,
                'assigner_id': assigner_id,
                'assigner_name': assigner_name,
                'status': TaskStatus.PENDING.value
            }

            response = db_service.client.table('rectification_tasks') \
                .update(data) \
                .eq('id', task_id) \
                .execute()

            if response.data and len(response.data) > 0:
                # 记录操作日志
                await self._log_action(
                    task_id=task_id,
                    action='assigned',
                    operator_id=assigner_id,
                    operator_name=assigner_name,
                    comment=f"分配给: {assignment.assignee_name}. {assignment.comment or ''}"
                )
                return RectificationTaskResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"分配整改任务失败: {str(e)}")
            return None

    async def submit_rectification(
        self,
        task_id: str,
        submission: TaskSubmission,
        user_id: str,
        user_name: str
    ) -> Optional[RectificationTaskResponse]:
        """提交整改"""
        try:
            if not db_service._available():
                return None

            # 验证是否为任务指派人
            task = await self.get_task(task_id)
            if not task or task.assignee_id != user_id:
                logger.warning(f"用户 {user_id} 无权提交整改任务 {task_id}")
                return None

            data = {
                'rectification_content': submission.rectification_content,
                'rectification_files': submission.rectification_files or [],
                'submitted_at': datetime.utcnow().isoformat(),
                'status': TaskStatus.SUBMITTED.value
            }

            response = db_service.client.table('rectification_tasks') \
                .update(data) \
                .eq('id', task_id) \
                .execute()

            if response.data and len(response.data) > 0:
                # 记录操作日志
                await self._log_action(
                    task_id=task_id,
                    action='submitted',
                    operator_id=user_id,
                    operator_name=user_name,
                    comment=f"提交整改: {submission.rectification_content[:50]}"
                )
                return RectificationTaskResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"提交整改失败: {str(e)}")
            return None

    async def review_rectification(
        self,
        task_id: str,
        review: TaskReview,
        reviewer_id: str,
        reviewer_name: str
    ) -> Optional[RectificationTaskResponse]:
        """验收整改"""
        try:
            if not db_service._available():
                return None

            # 验证任务状态
            task = await self.get_task(task_id)
            if not task or task.status != TaskStatus.SUBMITTED:
                logger.warning(f"整改任务 {task_id} 状态不正确，无法验收")
                return None

            new_status = TaskStatus.APPROVED if review.review_result == ReviewResult.PASS else TaskStatus.REJECTED
            data = {
                'status': new_status.value,
                'reviewer_id': reviewer_id,
                'reviewer_name': reviewer_name,
                'review_comment': review.review_comment,
                'review_result': review.review_result.value,
                'reviewed_at': datetime.utcnow().isoformat()
            }

            # 如果验收通过，标记为完成
            if review.review_result == ReviewResult.PASS:
                data['completed_at'] = datetime.utcnow().isoformat()

            response = db_service.client.table('rectification_tasks') \
                .update(data) \
                .eq('id', task_id) \
                .execute()

            if response.data and len(response.data) > 0:
                # 记录操作日志
                await self._log_action(
                    task_id=task_id,
                    action='reviewed',
                    operator_id=reviewer_id,
                    operator_name=reviewer_name,
                    comment=f"{review.review_result.value}: {review.review_comment}"
                )
                return RectificationTaskResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"验收整改失败: {str(e)}")
            return None

    async def update_task(
        self,
        task_id: str,
        updates: RectificationTaskUpdate,
        user_id: str
    ) -> Optional[RectificationTaskResponse]:
        """更新整改任务"""
        try:
            if not db_service._available():
                return None

            # 构建更新数据
            update_data = {}
            if updates.task_title:
                update_data['task_title'] = updates.task_title
            if updates.task_description:
                update_data['task_description'] = updates.task_description
            if updates.severity:
                update_data['severity'] = updates.severity.value
            if updates.due_date:
                update_data['due_date'] = updates.due_date.isoformat()
            if updates.status:
                update_data['status'] = updates.status.value

            if not update_data:
                return await self.get_task(task_id)

            response = db_service.client.table('rectification_tasks') \
                .update(update_data) \
                .eq('id', task_id) \
                .execute()

            if response.data and len(response.data) > 0:
                return RectificationTaskResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"更新整改任务失败: {str(e)}")
            return None

    async def get_task_statistics(
        self,
        department_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> TaskStats:
        """获取整改任务统计"""
        try:
            if not db_service._available():
                return TaskStats()

            query = db_service.client.table('rectification_tasks').select('*')

            if department_id:
                query = query.eq('department_id', department_id)
            if assignee_id:
                query = query.eq('assignee_id', assignee_id)
            if start_date:
                query = query.gte('created_at', start_date.isoformat())
            if end_date:
                query = query.lte('created_at', end_date.isoformat())

            response = query.execute()
            tasks = response.data or []

            stats = TaskStats()
            stats.total_count = len(tasks)
            stats.pending_count = sum(1 for t in tasks if t['status'] == 'pending')
            stats.in_progress_count = sum(1 for t in tasks if t['status'] == 'in_progress')
            stats.submitted_count = sum(1 for t in tasks if t['status'] == 'submitted')
            stats.approved_count = sum(1 for t in tasks if t['status'] == 'approved')
            stats.rejected_count = sum(1 for t in tasks if t['status'] == 'rejected')

            # 计算逾期任务数
            now = datetime.utcnow()
            stats.overdue_count = sum(
                1 for t in tasks
                if t.get('due_date') and
                datetime.fromisoformat(t['due_date'].replace('Z', '+00:00')) < now and
                t['status'] in ['pending', 'in_progress']
            )

            # 计算完成率
            if stats.total_count > 0:
                stats.completion_rate = stats.approved_count / stats.total_count

            # 计算平均完成时间
            completion_times = []
            for t in tasks:
                if t.get('completed_at') and t.get('created_at'):
                    created = datetime.fromisoformat(t['created_at'].replace('Z', '+00:00'))
                    completed = datetime.fromisoformat(t['completed_at'].replace('Z', '+00:00'))
                    hours = (completed - created).total_seconds() / 3600
                    completion_times.append(hours)

            if completion_times:
                stats.avg_completion_time_hours = sum(completion_times) / len(completion_times)

            # 计算按时完成率
            on_time_count = 0
            for t in tasks:
                if t.get('completed_at') and t.get('due_date'):
                    completed = datetime.fromisoformat(t['completed_at'].replace('Z', '+00:00'))
                    due = datetime.fromisoformat(t['due_date'].replace('Z', '+00:00'))
                    if completed <= due:
                        on_time_count += 1

            completed_with_due_date = sum(
                1 for t in tasks
                if t.get('completed_at') and t.get('due_date')
            )
            if completed_with_due_date > 0:
                stats.on_time_rate = on_time_count / completed_with_due_date

            return stats

        except Exception as e:
            logger.error(f"获取整改任务统计失败: {str(e)}")
            return TaskStats()

    async def get_my_tasks(
        self,
        user_id: str,
        status_filter: Optional[TaskStatus] = None
    ) -> List[RectificationTaskResponse]:
        """获取我的整改任务"""
        filters = TaskFilters(
            assignee_id=user_id,
            status=status_filter,
            page_size=100
        )
        result = await self.list_tasks(filters)
        return result.items

    async def _log_action(
        self,
        task_id: str,
        action: str,
        operator_id: str,
        operator_name: str,
        comment: Optional[str] = None
    ):
        """记录操作日志"""
        try:
            if not db_service._available():
                return

            data = {
                'id': str(uuid4()),
                'task_id': task_id,
                'action': action,
                'operator_id': operator_id,
                'operator_name': operator_name,
                'comment': comment,
                'created_at': datetime.utcnow().isoformat()
            }

            db_service.client.table('rectification_logs').insert(data).execute()

        except Exception as e:
            logger.error(f"记录整改日志失败: {str(e)}")


# 全局整改服务实例
rectification_service = RectificationService()
