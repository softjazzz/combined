"""
Supabase 数据库服务
提供数据库访问的统一接口
"""

from typing import List, Optional, Dict, Any
from supabase import create_client, Client
from loguru import logger
from datetime import datetime

from app.config import settings


class DatabaseService:
    """数据库服务类"""

    def __init__(self):
        """初始化 Supabase 客户端"""
        self.client: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )

    # ============================================
    # 病案首页相关
    # ============================================

    async def get_case_front_page(self, admission_id: str) -> Optional[Dict[str, Any]]:
        """获取病案首页详情"""
        try:
            response = self.client.table('case_front_page') \
                .select('*') \
                .eq('admission_id', admission_id) \
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"获取病案首页失败: {str(e)}")
            return None

    async def get_case_diagnoses(self, front_page_id: int) -> List[Dict[str, Any]]:
        """获取病案首页的次诊断列表"""
        try:
            response = self.client.table('case_front_page_diagnoses') \
                .select('*') \
                .eq('front_page_id', front_page_id) \
                .order('sequence') \
                .execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"获取次诊断失败: {str(e)}")
            return []

    async def get_case_procedures(self, front_page_id: int) -> List[Dict[str, Any]]:
        """获取病案首页的手术操作列表"""
        try:
            response = self.client.table('case_front_page_procedures') \
                .select('*') \
                .eq('front_page_id', front_page_id) \
                .order('sequence') \
                .execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"获取手术操作失败: {str(e)}")
            return []

    # ============================================
    # ICD 编码库相关
    # ============================================

    async def search_icd10_codes(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """搜索 ICD-10 编码"""
        try:
            # 使用 PostgreSQL 全文搜索
            response = self.client.table('icd10_codes') \
                .select('*') \
                .or_(f'code.ilike.%{keyword}%,name.ilike.%{keyword}%') \
                .eq('is_active', True) \
                .limit(limit) \
                .execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"搜索 ICD-10 编码失败: {str(e)}")
            return []

    async def search_icd9_procedures(
        self,
        keyword: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """搜索 ICD-9-CM-3 手术操作编码"""
        try:
            response = self.client.table('icd9_procedures') \
                .select('*') \
                .or_(f'code.ilike.%{keyword}%,name.ilike.%{keyword}%') \
                .eq('is_active', True) \
                .limit(limit) \
                .execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"搜索 ICD-9-CM-3 编码失败: {str(e)}")
            return []

    async def get_icd_code_by_code(
        self,
        code: str,
        category: str = 'diagnosis'
    ) -> Optional[Dict[str, Any]]:
        """根据编码获取 ICD 详情"""
        try:
            table = 'icd10_codes' if category == 'diagnosis' else 'icd9_procedures'
            response = self.client.table(table) \
                .select('*') \
                .eq('code', code) \
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"获取 ICD 编码详情失败: {str(e)}")
            return None

    # ============================================
    # DRG 分组相关
    # ============================================

    async def save_drg_grouping(
        self,
        admission_id: str,
        region: str,
        adrg_code: str,
        adrg_name: str,
        drg_code: str,
        drg_name: str,
        weight: float,
        baseline_payment: float,
        grouping_logic: Optional[str] = None
    ) -> Optional[int]:
        """保存 DRG 分组结果"""
        try:
            # 先将该 admission_id 的旧版本标记为非最新
            self.client.table('drg_groupings') \
                .update({'is_latest': False}) \
                .eq('admission_id', admission_id) \
                .execute()

            # 插入新版本
            data = {
                'admission_id': admission_id,
                'region': region,
                'adrg_code': adrg_code,
                'adrg_name': adrg_name,
                'drg_code': drg_code,
                'drg_name': drg_name,
                'weight': weight,
                'baseline_payment': baseline_payment,
                'grouping_logic': grouping_logic,
                'is_latest': True,
                'version': 1,  # TODO: 实现版本递增逻辑
                'grouped_at': datetime.utcnow().isoformat()
            }

            response = self.client.table('drg_groupings') \
                .insert(data) \
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]['grouping_id']
            return None

        except Exception as e:
            logger.error(f"保存 DRG 分组失败: {str(e)}")
            return None

    async def get_latest_drg_grouping(
        self,
        admission_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取最新的 DRG 分组结果"""
        try:
            response = self.client.table('drg_groupings') \
                .select('*') \
                .eq('admission_id', admission_id) \
                .eq('is_latest', True) \
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"获取最新 DRG 分组失败: {str(e)}")
            return None

    async def get_drg_grouping_history(
        self,
        admission_id: str
    ) -> List[Dict[str, Any]]:
        """获取 DRG 分组历史"""
        try:
            response = self.client.table('drg_groupings') \
                .select('*') \
                .eq('admission_id', admission_id) \
                .order('grouped_at', desc=True) \
                .execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"获取 DRG 分组历史失败: {str(e)}")
            return []

    # ============================================
    # 编码建议相关
    # ============================================

    async def save_coding_suggestion(
        self,
        admission_id: str,
        suggestion_type: str,
        message: str,
        diagnosis_code: Optional[str] = None,
        diagnosis_name: Optional[str] = None,
        evidence: Optional[str] = None,
        severity: str = 'info'
    ) -> Optional[int]:
        """保存编码建议"""
        try:
            data = {
                'admission_id': admission_id,
                'suggestion_type': suggestion_type,
                'diagnosis_code': diagnosis_code,
                'diagnosis_name': diagnosis_name,
                'message': message,
                'evidence': evidence,
                'severity': severity,
                'status': 'pending'
            }

            response = self.client.table('coding_suggestions') \
                .insert(data) \
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]['suggestion_id']
            return None

        except Exception as e:
            logger.error(f"保存编码建议失败: {str(e)}")
            return None

    async def get_coding_suggestions(
        self,
        admission_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取编码建议列表"""
        try:
            query = self.client.table('coding_suggestions') \
                .select('*') \
                .eq('admission_id', admission_id)

            if status:
                query = query.eq('status', status)

            response = query.order('created_at', desc=True).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"获取编码建议失败: {str(e)}")
            return []

    async def update_suggestion_status(
        self,
        suggestion_id: int,
        status: str,
        handled_by: str
    ) -> bool:
        """更新编码建议状态"""
        try:
            response = self.client.table('coding_suggestions') \
                .update({
                    'status': status,
                    'handled_by': handled_by,
                    'handled_at': datetime.utcnow().isoformat()
                }) \
                .eq('suggestion_id', suggestion_id) \
                .execute()

            return response.data is not None

        except Exception as e:
            logger.error(f"更新编码建议状态失败: {str(e)}")
            return False

    # ============================================
    # DRG 预警相关
    # ============================================

    async def save_drg_alert(
        self,
        admission_id: str,
        alert_type: str,
        alert_level: str,
        message: str,
        metric_value: Optional[float] = None,
        threshold_value: Optional[float] = None
    ) -> Optional[int]:
        """保存 DRG 预警"""
        try:
            data = {
                'admission_id': admission_id,
                'alert_type': alert_type,
                'alert_level': alert_level,
                'message': message,
                'metric_value': metric_value,
                'threshold_value': threshold_value,
                'status': 'pending'
            }

            response = self.client.table('drg_alerts') \
                .insert(data) \
                .execute()

            if response.data and len(response.data) > 0:
                return response.data[0]['alert_id']
            return None

        except Exception as e:
            logger.error(f"保存 DRG 预警失败: {str(e)}")
            return None

    async def get_drg_alerts(
        self,
        admission_id: Optional[str] = None,
        alert_level: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取 DRG 预警列表"""
        try:
            query = self.client.table('drg_alerts').select('*')

            if admission_id:
                query = query.eq('admission_id', admission_id)
            if alert_level:
                query = query.eq('alert_level', alert_level)
            if status:
                query = query.eq('status', status)

            response = query.order('triggered_at', desc=True).limit(limit).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"获取 DRG 预警失败: {str(e)}")
            return []


# 全局数据库服务实例
db_service = DatabaseService()
