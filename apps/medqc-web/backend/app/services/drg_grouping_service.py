"""
DRG/DIP 分组服务 - 调用 medchat.fun 真实 API
"""

from typing import Dict, Any, List, Optional
import httpx
import logging

logger = logging.getLogger(__name__)

# API 配置
DRG_API_URL = "https://medchat.fun/api/drg-grouping"
DIP_API_URL = "https://medchat.fun/api/dip-grouping"
CODE_INFO_API_URL = "https://medchat.fun/api/find-info-by-code"

# 默认基准支付 (四川省)
DEFAULT_BASE_PAYMENT = 8000.0


class DRGGroupingService:
    """DRG 分组服务"""

    async def group_drg(
        self,
        primary_diagnosis: str,
        secondary_diagnoses: List[str],
        procedures: List[str],
        patient_age: int,
        patient_gender: str,
        los: int = 7,
        city_name: str = "四川省",
        total_fee: float = 0
    ) -> Dict[str, Any]:
        """
        调用真实 DRG 分组 API
        
        Args:
            primary_diagnosis: 主诊断 ICD-10 编码
            secondary_diagnoses: 其他诊断编码列表
            procedures: 手术操作编码列表
            patient_age: 年龄
            patient_gender: 性别 (M/F)
            los: 住院天数
            city_name: 城市名称（决定分组规则版本）
            total_fee: 总费用
            
        Returns:
            分组结果
        """
        payload = {
            "city_name": city_name,
            "pdx_code": primary_diagnosis,
            "adx_code": ",".join(secondary_diagnoses) if secondary_diagnoses else "",
            "proc_code": ",".join(procedures) if procedures else "",
            "patient_gender": patient_gender,
            "patient_age": patient_age,
            "los": los,
            "birth_weight": 0,
            "fee_per_point": 60,
            "high_ratio_limit": 3,
            "icu": 0,
            "low_ratio_limit": 0.5,
            "rate": 1,
            "settlement_source": "none",
            "total_fee": total_fee
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MedQC-Backend/1.0",
        }

        logger.info(f"调用 DRG 分组 API: PDX={primary_diagnosis}, 城市={city_name}")

        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                resp = await client.post(DRG_API_URL, json=payload, headers=headers)

                if resp.status_code != 200:
                    logger.error(f"DRG API Error: {resp.status_code} - {resp.text[:200]}")
                    return self._fallback_result(primary_diagnosis, "API 调用失败")

                data = resp.json()
                if not data.get("success"):
                    logger.warning(f"DRG API Failed: {data.get('message', 'Unknown error')}")
                    return self._fallback_result(primary_diagnosis, data.get("message", "分组失败"))

                # 解析结果
                result_item = data.get("result", [{}])[0] if data.get("result") else {}
                grouping_path = data.get("grouping_path", {})

                drg_code = result_item.get("DRGCode", "0000")
                drg_name = result_item.get("DRGName", "未入组")
                adrg_code = result_item.get("ADRGCode", "00")
                adrg_name = result_item.get("ADRGName", "-")
                weight = float(result_item.get("RW", 0))

                # 计算支付金额
                baseline_payment = round(DEFAULT_BASE_PAYMENT * weight, 2)

                return {
                    "success": True,
                    "adrg_code": adrg_code,
                    "adrg_name": adrg_name,
                    "drg_code": drg_code,
                    "drg_name": drg_name,
                    "weight": weight,
                    "baseline_payment": baseline_payment,
                    "expected_los": {"min": 5, "max": 14},
                    "confidence": 1.0,
                    "risk_level": "medium",
                    "grouping_logic": f"远程分组: {grouping_path.get('final_outcome', 'Success')}",
                    "raw_response": result_item
                }

        except Exception as e:
            logger.error(f"DRG 分组异常: {str(e)}")
            return self._fallback_result(primary_diagnosis, str(e))

    async def group_dip(
        self,
        primary_diagnosis: str,
        secondary_diagnoses: List[str],
        procedures: List[str],
        patient_age: int,
        patient_gender: str,
        los: int = 7,
        city_name: str = "四川省",
        total_fee: float = 0
    ) -> Dict[str, Any]:
        """
        调用真实 DIP 分组 API
        """
        payload = {
            "city_name": city_name,
            "pdx_code": primary_diagnosis,
            "adx_code": ",".join(secondary_diagnoses) if secondary_diagnoses else "",
            "proc_code": ",".join(procedures) if procedures else "",
            "patient_gender": patient_gender,
            "patient_age": patient_age,
            "los": los,
            "birth_weight": 0,
            "settlement_source": "none",
            "total_fee": total_fee
        }

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MedQC-Backend/1.0",
        }

        logger.info(f"调用 DIP 分组 API: PDX={primary_diagnosis}, 城市={city_name}")

        try:
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                resp = await client.post(DIP_API_URL, json=payload, headers=headers)

                if resp.status_code != 200:
                    logger.error(f"DIP API Error: {resp.status_code}")
                    return {"success": False, "error": "API 调用失败"}

                data = resp.json()
                if not data.get("success"):
                    return {"success": False, "error": data.get("message", "分组失败")}

                return {
                    "success": True,
                    "data": data.get("result", {}),
                    "grouping_path": data.get("grouping_path", {})
                }

        except Exception as e:
            logger.error(f"DIP 分组异常: {str(e)}")
            return {"success": False, "error": str(e)}

    def _fallback_result(self, primary_diagnosis: str, error_msg: str) -> Dict[str, Any]:
        """降级返回 Mock 结果"""
        return {
            "success": False,
            "adrg_code": "ZZ9",
            "adrg_name": "其他",
            "drg_code": "ZZ91",
            "drg_name": "未入组",
            "weight": 1.0,
            "baseline_payment": DEFAULT_BASE_PAYMENT,
            "expected_los": {"min": 7, "max": 14},
            "confidence": 0.5,
            "risk_level": "unknown",
            "grouping_logic": f"分组失败: {error_msg}",
            "error": error_msg
        }


# 单例
drg_grouping_service = DRGGroupingService()


def get_drg_grouping_service() -> DRGGroupingService:
    return drg_grouping_service
