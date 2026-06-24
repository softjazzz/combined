"""
申诉管理服务
Appeal Service
"""
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime

try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.schemas.appeal import (
    AppealCreate, AppealUpdate, AppealReview, AppealResponse,
    AppealListResponse, AppealFilters, AppealStats,
    AppealStatus, AppealType
)
from app.services.database import db_service


class AppealService:
    """申诉管理服务"""

    async def create_appeal(
        self,
        appeal_data: AppealCreate,
        user_id: str,
        user_name: str,
        department_id: Optional[str] = None
    ) -> Optional[AppealResponse]:
        """创建申诉"""
        try:
            if not db_service._available():
                logger.warning("Database not available")
                return None

            data = {
                'id': str(uuid4()),
                'qc_result_id': appeal_data.qc_result_id,
                'defect_id': appeal_data.defect_id,
                'record_id': appeal_data.record_id,
                'appellant_id': user_id,
                'appellant_name': user_name,
                'department_id': department_id,
                'appeal_reason': appeal_data.appeal_reason,
                'appeal_type': appeal_data.appeal_type.value,
                'evidence_urls': appeal_data.evidence_urls or [],
                'status': AppealStatus.PENDING.value,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            response = db_service.client.table('appeals') \
                .insert(data) \
                .execute()

            if response.data and len(response.data) > 0:
                # 记录操作日志
                await self._log_action(
                    appeal_id=response.data[0]['id'],
                    action='created',
                    operator_id=user_id,
                    operator_name=user_name,
                    comment=f"创建申诉: {appeal_data.appeal_reason[:50]}"
                )
                return AppealResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"创建申诉失败: {str(e)}")
            return None

    async def get_appeal(self, appeal_id: str) -> Optional[AppealResponse]:
        """获取申诉详情"""
        try:
            if not db_service._available():
                return None

            response = db_service.client.table('appeals') \
                .select('*') \
                .eq('id', appeal_id) \
                .execute()

            if response.data and len(response.data) > 0:
                return AppealResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"获取申诉详情失败: {str(e)}")
            return None

    async def list_appeals(
        self,
        filters: AppealFilters
    ) -> AppealListResponse:
        """查询申诉列表"""
        try:
            if not db_service._available():
                return AppealListResponse(items=[], total=0)

            query = db_service.client.table('appeals').select('*', count='exact')

            # 应用筛选条件
            if filters.status:
                query = query.eq('status', filters.status.value)
            if filters.appeal_type:
                query = query.eq('appeal_type', filters.appeal_type.value)
            if filters.appellant_id:
                query = query.eq('appellant_id', filters.appellant_id)
            if filters.department_id:
                query = query.eq('department_id', filters.department_id)
            if filters.start_date:
                query = query.gte('created_at', filters.start_date.isoformat())
            if filters.end_date:
                query = query.lte('created_at', filters.end_date.isoformat())

            # 分页
            offset = (filters.page - 1) * filters.page_size
            response = query.order('created_at', desc=True) \
                .range(offset, offset + filters.page_size - 1) \
                .execute()

            items = [AppealResponse(**item) for item in (response.data or [])]
            total = response.count if hasattr(response, 'count') else len(items)

            return AppealListResponse(
                items=items,
                total=total,
                page=filters.page,
                page_size=filters.page_size,
                has_more=total > offset + len(items)
            )

        except Exception as e:
            logger.error(f"查询申诉列表失败: {str(e)}")
            return AppealListResponse(items=[], total=0)

    async def review_appeal(
        self,
        appeal_id: str,
        review: AppealReview,
        reviewer_id: str,
        reviewer_name: str
    ) -> Optional[AppealResponse]:
        """审核申诉"""
        try:
            if not db_service._available():
                return None

            # 更新申诉状态
            new_status = AppealStatus.APPROVED if review.decision == 'approve' else AppealStatus.REJECTED
            data = {
                'status': new_status.value,
                'reviewer_id': reviewer_id,
                'reviewer_name': reviewer_name,
                'review_comment': review.comment,
                'reviewed_at': datetime.utcnow().isoformat()
            }

            response = db_service.client.table('appeals') \
                .update(data) \
                .eq('id', appeal_id) \
                .execute()

            if response.data and len(response.data) > 0:
                # 记录操作日志
                await self._log_action(
                    appeal_id=appeal_id,
                    action='reviewed',
                    operator_id=reviewer_id,
                    operator_name=reviewer_name,
                    comment=f"{review.decision}: {review.comment}"
                )
                
                return AppealResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"审核申诉失败: {str(e)}")
            return None

    async def withdraw_appeal(
        self,
        appeal_id: str,
        user_id: str,
        user_name: str
    ) -> Optional[AppealResponse]:
        """撤销申诉"""
        try:
            if not db_service._available():
                return None

            # 验证是否为申诉人
            appeal = await self.get_appeal(appeal_id)
            if not appeal or appeal.appellant_id != user_id:
                logger.warning(f"用户 {user_id} 无权撤销申诉 {appeal_id}")
                return None

            # 只能撤销待审核的申诉
            if appeal.status != AppealStatus.PENDING:
                logger.warning(f"申诉 {appeal_id} 状态为 {appeal.status}，无法撤销")
                return None

            response = db_service.client.table('appeals') \
                .update({'status': AppealStatus.WITHDRAWN.value}) \
                .eq('id', appeal_id) \
                .execute()

            if response.data and len(response.data) > 0:
                # 记录操作日志
                await self._log_action(
                    appeal_id=appeal_id,
                    action='withdrawn',
                    operator_id=user_id,
                    operator_name=user_name,
                    comment="申诉人主动撤销"
                )
                return AppealResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"撤销申诉失败: {str(e)}")
            return None

    async def update_appeal(
        self,
        appeal_id: str,
        updates: AppealUpdate,
        user_id: str
    ) -> Optional[AppealResponse]:
        """更新申诉（仅申诉人可更新待审核的申诉）"""
        try:
            if not db_service._available():
                return None

            # 验证权限和状态
            appeal = await self.get_appeal(appeal_id)
            if not appeal or appeal.appellant_id != user_id:
                return None
            if appeal.status != AppealStatus.PENDING:
                return None

            # 构建更新数据
            update_data = {}
            if updates.appeal_reason:
                update_data['appeal_reason'] = updates.appeal_reason
            if updates.appeal_type:
                update_data['appeal_type'] = updates.appeal_type.value
            if updates.evidence_urls is not None:
                update_data['evidence_urls'] = updates.evidence_urls

            if not update_data:
                return appeal

            response = db_service.client.table('appeals') \
                .update(update_data) \
                .eq('id', appeal_id) \
                .execute()

            if response.data and len(response.data) > 0:
                return AppealResponse(**response.data[0])
            return None

        except Exception as e:
            logger.error(f"更新申诉失败: {str(e)}")
            return None

    async def get_appeal_statistics(
        self,
        department_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> AppealStats:
        """获取申诉统计"""
        try:
            if not db_service._available():
                return AppealStats()

            query = db_service.client.table('appeals').select('*')

            if department_id:
                query = query.eq('department_id', department_id)
            if start_date:
                query = query.gte('created_at', start_date.isoformat())
            if end_date:
                query = query.lte('created_at', end_date.isoformat())

            response = query.execute()
            appeals = response.data or []

            stats = AppealStats()
            stats.total_count = len(appeals)
            stats.pending_count = sum(1 for a in appeals if a['status'] == 'pending')
            stats.approved_count = sum(1 for a in appeals if a['status'] == 'approved')
            stats.rejected_count = sum(1 for a in appeals if a['status'] == 'rejected')
            stats.withdrawn_count = sum(1 for a in appeals if a['status'] == 'withdrawn')

            # 计算通过率
            reviewed_count = stats.approved_count + stats.rejected_count
            if reviewed_count > 0:
                stats.approval_rate = stats.approved_count / reviewed_count

            # 计算平均审核时间
            review_times = []
            for a in appeals:
                if a.get('reviewed_at') and a.get('created_at'):
                    created = datetime.fromisoformat(a['created_at'].replace('Z', '+00:00'))
                    reviewed = datetime.fromisoformat(a['reviewed_at'].replace('Z', '+00:00'))
                    hours = (reviewed - created).total_seconds() / 3600
                    review_times.append(hours)

            if review_times:
                stats.avg_review_time_hours = sum(review_times) / len(review_times)

            return stats

        except Exception as e:
            logger.error(f"获取申诉统计失败: {str(e)}")
            return AppealStats()

    async def _log_action(
        self,
        appeal_id: str,
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
                'appeal_id': appeal_id,
                'action': action,
                'operator_id': operator_id,
                'operator_name': operator_name,
                'comment': comment,
                'created_at': datetime.utcnow().isoformat()
            }

            db_service.client.table('appeal_logs').insert(data).execute()

        except Exception as e:
            logger.error(f"记录申诉日志失败: {str(e)}")


# 全局申诉服务实例
appeal_service = AppealService()
