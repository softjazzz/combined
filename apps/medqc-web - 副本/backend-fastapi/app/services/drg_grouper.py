"""
OpenDRG 分组引擎封装
提供 DRG 分组功能
"""

from typing import Dict, Any, List, Optional, Tuple
try:
    from loguru import logger
except Exception:
    import logging

    logger = logging.getLogger(__name__)

from app.config import settings


class DRGGrouperService:
    """DRG 分组器服务"""

    def __init__(self):
        """初始化 DRG 分组器"""
        self.region = settings.OPENDRG_DEFAULT_REGION
        self.base_payment = settings.OPENDRG_BASE_PAYMENT

        # TODO: 集成真实的 OpenDRG 引擎
        # try:
        #     from opendrg import DRGGrouper
        #     self.grouper = DRGGrouper(region=self.region)
        #     logger.info(f"OpenDRG 引擎初始化成功，地区：{self.region}")
        # except ImportError:
        #     logger.warning("OpenDRG 未安装，使用模拟分组")
        #     self.grouper = None

        self.grouper = None  # 当前使用模拟模式

        # except Exception as e:
        #     logger.error(f"DRG 分组失败: {str(e)}")
        #     raise

    async def group(
        self,
        primary_diagnosis: str,
        secondary_diagnoses: List[str],
        procedures: List[str],
        patient_age: int,
        patient_gender: str,
        total_hospital_days: Optional[int] = None,
        discharge_status: Optional[str] = None
    ) -> Dict[str, Any]:
        """DRG 分组"""
        try:
            # 1. 如果配置为远程模式，使用 medchat.fun API
            if settings.DRG_API_MODE == "remote":
                return await self._call_remote_grouping_api(
                    primary_diagnosis,
                    secondary_diagnoses,
                    procedures,
                    patient_age,
                    patient_gender,
                    total_hospital_days
                )

            # 2. 如果配置了本地 OpenDRG 引擎
            if self.grouper:
                # TODO: 调用真实的 OpenDRG 引擎
                pass

            # 3. 默认使用模拟分组（开发阶段）
            logger.info(f"模拟 DRG 分组: 主诊断={primary_diagnosis}")
            return self._mock_group(
                primary_diagnosis,
                secondary_diagnoses,
                procedures,
                patient_age,
                patient_gender,
                total_hospital_days
            )

        except Exception as e:
            logger.error(f"DRG 分组失败: {str(e)}")
            # 出错时降级到模拟分组
            logger.warning("降级到模拟分组模式")
            return self._mock_group(
                primary_diagnosis,
                secondary_diagnoses,
                procedures,
                patient_age,
                patient_gender,
                total_hospital_days
            )

    async def _call_remote_grouping_api(
        self,
        primary_diagnosis: str,
        secondary_diagnoses: List[str],
        procedures: List[str],
        age: int,
        gender: str,
        los: Optional[int]
    ) -> Dict[str, Any]:
        """调用远程 DRG 分组 API"""
        import httpx
        
        url = settings.DRG_API_URL
        # 构造 Payload，参考外部 API 规范
        payload = {
            "city_name": "四川省", # 默认使用四川规则
            "pdx_code": primary_diagnosis,
            "adx_code": ",".join(secondary_diagnoses),
            "proc_code": ",".join(procedures),
            "patient_gender": gender,
            "patient_age": age,
            "los": los or 7,
            # 默认参数
            "birth_weight": 0,
            "fee_per_point": 60,
            "high_ratio_limit": 3,
            "icu": 0,
            "low_ratio_limit": 0.5,
            "rate": 1,
            "settlement_source": "none",
            "total_fee": 0
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MedQC-Backend/1.0",
             # 注意：实际生产环境可能需要 Cookie 或 Authorization，这里暂且使用公开访问模式
             # "Referer": "https://medchat.fun/medgroup",
             # "Origin": "https://medchat.fun"
        }

        logger.info(f"调用远程分组 API: {url} | PDX={primary_diagnosis}")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            
            if resp.status_code != 200:
                raise Exception(f"External API Error: {resp.status_code} - {resp.text[:100]}")
            
            data = resp.json()
            if not data.get("success"):
                raise Exception(f"External API Failed: {data.get('message', 'Unknown error')}")

            # 解析结果
            result_item = data.get("result", [{}])[0]
            grouping_path = data.get("grouping_path", {})
            
            # 映射到内部数据结构
            drg_code = result_item.get("DRGCode", "0000")
            drg_name = result_item.get("DRGName", "未入组")
            weight = float(result_item.get("RW", 0))
            
            # 计算支付金额 (简单估算)
            baseline_payment = round(settings.OPENDRG_BASE_PAYMENT * weight, 2)
            
            return {
                'adrg_code': result_item.get("ADRGCode", "00"),
                'adrg_name': result_item.get("ADRGName", "-"),
                'drg_code': drg_code,
                'drg_name': drg_name,
                'weight': weight,
                'baseline_payment': baseline_payment,
                'expected_los': {'min': 5, 'max': 14}, # 外部 API 未返回 LOS 范围，暂用默认
                'confidence': 1.0, # 外部 API 视为 100% 可信
                'risk_level': 'medium', # 简化处理
                'grouping_logic': f"远程分组: {grouping_path.get('final_outcome', 'Success')}"
            }

    def _mock_group(
        self,
        primary_diagnosis: str,
        secondary_diagnoses: List[str],
        procedures: List[str],
        patient_age: int,
        patient_gender: str,
        total_hospital_days: Optional[int]
    ) -> Dict[str, Any]:
        """
        模拟 DRG 分组（开发阶段使用）
        根据主诊断和并发症数量进行简单分组
        """
        # 根据主诊断确定 ADRG
        adrg_code, adrg_name = self._get_adrg_by_diagnosis(primary_diagnosis)

        # 根据并发症数量确定 DRG
        has_complications = len(secondary_diagnoses) >= 2
        has_major_complications = any(
            diag in ['E11.901', 'I50.001', 'J96.001']
            for diag in secondary_diagnoses
        )

        # 确定 DRG 编码
        if has_major_complications:
            drg_code = f"{adrg_code}9"  # 伴严重并发症
            drg_name = f"{adrg_name}伴严重合并症"
            weight_multiplier = 1.5
        elif has_complications:
            drg_code = f"{adrg_code}5"  # 伴并发症
            drg_name = f"{adrg_name}伴合并症"
            weight_multiplier = 1.2
        else:
            drg_code = f"{adrg_code}1"  # 无并发症
            drg_name = adrg_name
            weight_multiplier = 1.0

        # 计算权重（基础权重 * 并发症系数）
        base_weight = self._get_base_weight(adrg_code)
        weight = round(base_weight * weight_multiplier, 4)

        # 计算基准支付金额
        baseline_payment = round(self.base_payment * weight, 2)

        # 预期住院日
        expected_los = self._get_expected_los(adrg_code, has_complications)

        # 风险等级评估
        risk_level = self._assess_risk_level(
            patient_age,
            has_major_complications,
            total_hospital_days,
            expected_los
        )

        # 分组逻辑说明
        logic_parts = [f"主诊断：{primary_diagnosis} → ADRG {adrg_code}"]
        if has_major_complications:
            logic_parts.append("存在严重并发症 → 权重增加50%")
        elif has_complications:
            logic_parts.append("存在并发症 → 权重增加20%")
        grouping_logic = "；".join(logic_parts)

        return {
            'adrg_code': adrg_code,
            'adrg_name': adrg_name,
            'drg_code': drg_code,
            'drg_name': drg_name,
            'weight': weight,
            'baseline_payment': baseline_payment,
            'expected_los': expected_los,
            'confidence': 0.85 if has_major_complications else 0.92,
            'risk_level': risk_level,
            'grouping_logic': grouping_logic
        }

    def _get_adrg_by_diagnosis(self, diagnosis_code: str) -> Tuple[str, str]:
        """根据主诊断确定 ADRG"""
        # 简化的 ADRG 映射表
        adrg_mapping = {
            'I21': ('FB1', '急性心肌梗死'),
            'I20': ('FB2', '不稳定型心绞痛'),
            'I10': ('FD1', '高血压'),
            'I50': ('FD2', '心力衰竭'),
            'J18': ('RB1', '肺炎'),
            'J44': ('RB2', '慢性阻塞性肺疾病'),
            'J96': ('RB3', '呼吸衰竭'),
            'E11': ('KB1', '2型糖尿病'),
            'E10': ('KB2', '1型糖尿病'),
            'N18': ('LB1', '慢性肾脏病'),
            'K80': ('HB1', '胆石病'),
        }

        # 提取诊断前3位
        prefix = diagnosis_code[:3]
        if prefix in adrg_mapping:
            return adrg_mapping[prefix]

        # 默认 ADRG
        return ('ZZ9', '其他诊断')

    def _get_base_weight(self, adrg_code: str) -> float:
        """获取 ADRG 基础权重"""
        # 简化的权重表
        weights = {
            'FB1': 2.1000,  # 急性心肌梗死
            'FB2': 1.2000,  # 不稳定型心绞痛
            'FD1': 0.8000,  # 高血压
            'FD2': 1.5000,  # 心力衰竭
            'RB1': 1.0000,  # 肺炎
            'RB2': 1.1000,  # COPD
            'RB3': 2.5000,  # 呼吸衰竭
            'KB1': 0.9000,  # 2型糖尿病
            'KB2': 1.2000,  # 1型糖尿病
            'LB1': 1.8000,  # 慢性肾脏病
            'HB1': 1.3000,  # 胆石病
        }
        return weights.get(adrg_code, 1.0)

    def _get_expected_los(self, adrg_code: str, has_complications: bool) -> Dict[str, int]:
        """获取预期住院日"""
        # 简化的住院日范围
        base_los = {
            'FB1': {'min': 10, 'max': 15},
            'FB2': {'min': 5, 'max': 10},
            'RB1': {'min': 7, 'max': 12},
            'KB1': {'min': 5, 'max': 10},
        }

        los = base_los.get(adrg_code, {'min': 7, 'max': 14})

        # 有并发症时延长住院日
        if has_complications:
            los['min'] += 3
            los['max'] += 5

        return los

    def _assess_risk_level(
        self,
        age: int,
        has_major_complications: bool,
        actual_los: Optional[int],
        expected_los: Dict[str, int]
    ) -> str:
        """评估风险等级"""
        risk_score = 0

        # 年龄因素
        if age >= 80:
            risk_score += 2
        elif age >= 65:
            risk_score += 1

        # 并发症因素
        if has_major_complications:
            risk_score += 2

        # 住院日因素
        if actual_los and actual_los > expected_los['max']:
            risk_score += 1

        # 风险等级判定
        if risk_score >= 4:
            return 'high'
        elif risk_score >= 2:
            return 'medium'
        else:
            return 'low'

    async def calculate_cost_variance(
        self,
        baseline_payment: float,
        actual_cost: float
    ) -> Dict[str, Any]:
        """
        计算费用差异分析

        Args:
            baseline_payment: DRG 基准支付金额
            actual_cost: 实际费用

        Returns:
            费用分析结果
        """
        profit_margin = baseline_payment - actual_cost
        cost_rate = (actual_cost / baseline_payment) * 100 if baseline_payment > 0 else 0

        # 判定盈亏状态
        if profit_margin > 0:
            status = 'profit'
            message = f"盈余 {profit_margin:.2f} 元"
        elif profit_margin < 0:
            status = 'loss'
            message = f"亏损 {abs(profit_margin):.2f} 元"
        else:
            status = 'break_even'
            message = "收支平衡"

        # 费用消耗率
        if cost_rate > 120:
            alert_level = 'critical'
        elif cost_rate > 100:
            alert_level = 'warning'
        else:
            alert_level = 'normal'

        return {
            'baseline_payment': baseline_payment,
            'actual_cost': actual_cost,
            'profit_margin': profit_margin,
            'cost_rate': round(cost_rate, 2),
            'status': status,
            'alert_level': alert_level,
            'message': message
        }

    async def lookup_code_info(self, code: str, city: str = "四川省") -> Dict[str, Any]:
        """
        查询编码详细信息（ADRG/MDC 映射）
        调用外部 API: find-info-by-code
        """
        import httpx
        try:
            url = settings.CODE_INFO_API_URL
            payload = {
                "code": code,
                "city_name": city
            }
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "MedQC-Backend/1.0"
            }
            
            logger.info(f"查询编码信息: {code}, url={url}")

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                
                if resp.status_code != 200:
                    logger.error(f"External API Error: {resp.status_code}")
                    return {"code": code, "adrg_codes": [], "mdc_codes": []}
                
                data = resp.json()
                if not data.get("success"):
                     logger.warning(f"External API Failed: {data}")
                     return {"code": code, "adrg_codes": [], "mdc_codes": []}

                result = data.get("data", {})
                return {
                    "code": result.get("code", code),
                    "adrg_codes": result.get("adrg_codes", []),
                    "mdc_codes": result.get("mdc_codes", [])
                }
        except Exception as e:
            logger.error(f"查询编码信息失败: {str(e)}")
            return {"code": code, "adrg_codes": [], "mdc_codes": []}


# 全局 DRG 分组器实例
drg_grouper = DRGGrouperService()
