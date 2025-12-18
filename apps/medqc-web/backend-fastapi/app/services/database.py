"""
Supabase 数据库服务
提供数据库访问的统一接口
"""

from typing import List, Optional, Dict, Any
import os
try:
    from supabase import create_client, Client
except Exception:
    create_client = None
    Client = Any

try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)
from datetime import datetime

from app.config import settings


class DatabaseService:
    """数据库服务类"""

    def __init__(self):
        """初始化 Supabase 客户端"""
        if settings.DEMO_MODE:
            self.client = None
            return
        # 避免在系统配置了 SOCKS 代理（ALL_PROXY/HTTP(S)_PROXY）但未安装 socksio 时启动失败
        # 仅在代理值包含 socks 时忽略环境代理
        for key in [
            'ALL_PROXY', 'all_proxy',
            'HTTP_PROXY', 'http_proxy',
            'HTTPS_PROXY', 'https_proxy'
        ]:
            value = os.environ.get(key)
            if value and 'socks' in value.lower():
                os.environ.pop(key, None)

        if create_client is None or not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            self.client = None
            return

        self.client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )

    def _available(self) -> bool:
        return self.client is not None

    # ============================================
    # 病案首页相关
    # ============================================

    async def list_case_front_pages(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取病案首页列表（包含次诊断/手术，便于前端直接使用）"""
        try:
            if not self._available():
                return []
            response = self.client.table('case_front_page') \
                .select('*') \
                .order('updated_at', desc=True) \
                .limit(limit) \
                .execute()

            records = response.data if response.data else []
            if not records:
                return []

            front_page_ids = [r['front_page_id'] for r in records]

            diag_resp = self.client.table('case_front_page_diagnoses') \
                .select('*') \
                .in_('front_page_id', front_page_ids) \
                .order('sequence') \
                .execute()

            proc_resp = self.client.table('case_front_page_procedures') \
                .select('*') \
                .in_('front_page_id', front_page_ids) \
                .order('sequence') \
                .execute()

            diags = diag_resp.data if diag_resp.data else []
            procs = proc_resp.data if proc_resp.data else []

            diags_by_fp: Dict[int, List[Dict[str, Any]]] = {}
            for d in diags:
                diags_by_fp.setdefault(d['front_page_id'], []).append({
                    'code': d['diagnosis_code'],
                    'name': d['diagnosis_name'],
                    'sequence': d.get('sequence'),
                    'is_complication': d.get('is_complication', False)
                })

            procs_by_fp: Dict[int, List[Dict[str, Any]]] = {}
            for p in procs:
                procs_by_fp.setdefault(p['front_page_id'], []).append({
                    'code': p['procedure_code'],
                    'name': p['procedure_name'],
                    'sequence': p.get('sequence'),
                    'procedure_date': p.get('procedure_date')
                })

            enriched = []
            for r in records:
                fp_id = r['front_page_id']
                enriched.append({
                    **r,
                    'secondary_diagnoses': diags_by_fp.get(fp_id, []),
                    'procedures': procs_by_fp.get(fp_id, [])
                })

            return enriched

        except Exception as e:
            logger.error(f"获取病案首页列表失败: {str(e)}")
            return []

    async def get_case_front_page(self, admission_id: str) -> Optional[Dict[str, Any]]:
        """获取病案首页详情"""
        try:
            if not self._available():
                return None
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

    async def get_case_front_page_detail(self, admission_id: str) -> Optional[Dict[str, Any]]:
        """获取病案首页详情（包含次诊断、手术操作）"""
        try:
            fp = await self.get_case_front_page(admission_id)
            if not fp:
                return None

            front_page_id = fp['front_page_id']
            diagnoses = await self.get_case_diagnoses(front_page_id)
            procedures = await self.get_case_procedures(front_page_id)

            return {
                **fp,
                'secondary_diagnoses': [
                    {
                        'code': d['diagnosis_code'],
                        'name': d['diagnosis_name'],
                        'sequence': d.get('sequence'),
                        'is_complication': d.get('is_complication', False)
                    }
                    for d in diagnoses
                ],
                'procedures': [
                    {
                        'code': p['procedure_code'],
                        'name': p['procedure_name'],
                        'sequence': p.get('sequence'),
                        'procedure_date': p.get('procedure_date')
                    }
                    for p in procedures
                ]
            }

        except Exception as e:
            logger.error(f"获取病案首页详情失败: {str(e)}")
            return None

    async def upsert_case_front_page(self, payload) -> Dict[str, Any]:
        """创建或更新病案首页，并覆盖保存次诊断/手术操作列表"""
        try:
            if not self._available():
                raise Exception('Supabase client not configured')
            # upsert 主表（以 admission_id 唯一）
            fp_data = payload.model_dump(exclude={'secondary_diagnoses', 'procedures'})

            upsert_resp = self.client.table('case_front_page') \
                .upsert(fp_data, on_conflict='admission_id') \
                .execute()

            if not upsert_resp.data or len(upsert_resp.data) == 0:
                raise Exception('case_front_page upsert failed')

            fp = upsert_resp.data[0]
            front_page_id = fp['front_page_id']

            # 覆盖次诊断/手术（简单实现：先删后插）
            self.client.table('case_front_page_diagnoses') \
                .delete() \
                .eq('front_page_id', front_page_id) \
                .execute()

            self.client.table('case_front_page_procedures') \
                .delete() \
                .eq('front_page_id', front_page_id) \
                .execute()

            diag_rows = []
            for idx, d in enumerate(payload.secondary_diagnoses or []):
                diag_rows.append({
                    'front_page_id': front_page_id,
                    'diagnosis_code': d.code,
                    'diagnosis_name': d.name,
                    'sequence': d.sequence if d.sequence is not None else (idx + 1),
                    'is_complication': d.is_complication
                })

            if diag_rows:
                self.client.table('case_front_page_diagnoses').insert(diag_rows).execute()

            proc_rows = []
            for idx, p in enumerate(payload.procedures or []):
                proc_rows.append({
                    'front_page_id': front_page_id,
                    'procedure_code': p.code,
                    'procedure_name': p.name,
                    'procedure_date': p.procedure_date.isoformat() if p.procedure_date else None,
                    'sequence': p.sequence if p.sequence is not None else (idx + 1)
                })

            if proc_rows:
                self.client.table('case_front_page_procedures').insert(proc_rows).execute()

            # 返回完整详情
            detail = await self.get_case_front_page_detail(payload.admission_id)
            if not detail:
                raise Exception('failed to fetch detail after upsert')
            return detail

        except Exception as e:
            logger.error(f"保存病案首页失败: {str(e)}")
            raise

    async def get_case_diagnoses(self, front_page_id: int) -> List[Dict[str, Any]]:
        """获取病案首页的次诊断列表"""
        try:
            if not self._available():
                return []
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
            if not self._available():
                return []
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
            if not self._available():
                return []
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
            if not self._available():
                return []
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
            if not self._available():
                return None
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
            if not self._available():
                return None
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
            if not self._available():
                return None
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
            if not self._available():
                return []
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

    async def list_coding_suggestions(
        self,
        admission_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取编码建议列表（支持不传 admission_id 查询全量）"""
        try:
            if not self._available():
                return []
            query = self.client.table('coding_suggestions').select('*')

            if admission_id:
                query = query.eq('admission_id', admission_id)
            if status:
                query = query.eq('status', status)

            response = query.order('created_at', desc=True).limit(limit).execute()
            return response.data if response.data else []

        except Exception as e:
            logger.error(f"获取编码建议列表失败: {str(e)}")
            return []

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
            if not self._available():
                return None
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
            if not self._available():
                return []
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
            if not self._available():
                return False
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
            if not self._available():
                return None
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
            if not self._available():
                return []
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

    async def update_alert_status(
        self,
        alert_id: int,
        status: str,
        handled_by: str
    ) -> bool:
        """更新 DRG 预警状态"""
        try:
            if not self._available():
                return False
            response = self.client.table('drg_alerts') \
                .update({
                    'status': status,
                    'handled_by': handled_by,
                    'handled_at': datetime.utcnow().isoformat()
                }) \
                .eq('alert_id', alert_id) \
                .execute()

            return response.data is not None

        except Exception as e:
            logger.error(f"更新 DRG 预警状态失败: {str(e)}")
            return False


# 全局数据库服务实例
db_service = DatabaseService()
