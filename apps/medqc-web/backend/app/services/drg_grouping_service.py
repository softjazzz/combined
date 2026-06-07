"""
DRG/DIP 分组服务 - 调用 medchat.fun 真实 API
"""

from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import httpx
import logging

from .drg_config_store import get_runtime_grouping_config

logger = logging.getLogger(__name__)

# API 配置
DRG_API_URL = "https://medchat.fun/api/drg-grouping"
DIP_API_URL = "https://medchat.fun/api/dip-grouping"
CODE_INFO_API_URL = "https://medchat.fun/api/find-info-by-code"

# 默认基准支付 (四川省)
DEFAULT_BASE_PAYMENT = 8000.0
DRG_WEIGHT_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "drg_weights.json"


@lru_cache(maxsize=1)
def load_drg_weight_dataset() -> Dict[str, Any]:
    with DRG_WEIGHT_DATA_PATH.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    entries = payload.get("entries") or []
    by_code = {
        str(item.get("drgCode") or "").strip().upper(): item
        for item in entries
        if item.get("drgCode")
    }
    return {"meta": payload.get("meta") or {}, "entries": entries, "by_code": by_code}


def lookup_drg_weight(drg_code: str | None) -> Optional[Dict[str, Any]]:
    if not drg_code:
        return None
    return load_drg_weight_dataset()["by_code"].get(drg_code.strip().upper())


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
            primary_diagnosis: 主诊断 ICD-10 编码（国临版）
            secondary_diagnoses: 其他诊断编码列表（国临版）
            procedures: 手术操作编码列表
            patient_age: 年龄
            patient_gender: 性别 (M/F)
            los: 住院天数
            city_name: 城市名称（决定分组规则版本）
            total_fee: 总费用
            
        Returns:
            分组结果（包含原编码和映射后的编码）
        """
        # 导入编码映射服务
        from .icd_code_mapper import get_icd_mapper
        mapper = get_icd_mapper()
        
        # 将国临版编码映射为医保版
        original_pdx = primary_diagnosis
        mapped_pdx, mapped_pdx_name = mapper.map_to_yibao(primary_diagnosis)
        
        # 映射次要诊断
        original_adx = secondary_diagnoses
        mapped_adx = mapper.map_codes_list(secondary_diagnoses) if secondary_diagnoses else []
        
        logger.info(f"编码映射: {original_pdx} -> {mapped_pdx}")
        
        payload = {
            "city_name": city_name,
            "pdx_code": mapped_pdx,  # 使用医保版编码
            "adx_code": ",".join(mapped_adx) if mapped_adx else "",
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
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "Cookie": "acw_tc=ac11000117671024951721484edd9575d3a8bd27e3e385850319c1fd267de8",
            "Referer": "https://medchat.fun/medgroup",
            "Origin": "https://medchat.fun",
        }

        logger.info(f"调用 DRG 分组 API: PDX={primary_diagnosis}, 城市={city_name}")
        runtime_config = get_runtime_grouping_config()

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

                weight_info = lookup_drg_weight(drg_code)
                if weight_info:
                    weight = float(weight_info.get("weight") or weight)
                    drg_name = weight_info.get("drgName") or drg_name

                # 计算支付金额
                baseline_payment = self._calculate_payment(weight, runtime_config)

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
                    "is_low_risk": bool(weight_info.get("isLowRisk")) if weight_info else None,
                    "weight_source": "backend/app/data/drg_weights.json" if weight_info else "remote_response",
                    "config_version_id": runtime_config.get("config_version_id"),
                    "runtime_config": self._public_runtime_config(runtime_config),
                    "cost_ratio": self._cost_ratio(total_fee, baseline_payment),
                    "cost_group": self._cost_group(total_fee, baseline_payment, runtime_config),
                    "raw_response": result_item,
                    # 编码映射信息
                    "original_code": original_pdx,
                    "mapped_code": mapped_pdx,
                    "mapped_code_name": mapped_pdx_name,
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
        runtime_config = get_runtime_grouping_config()
        local_weight = lookup_drg_weight(primary_diagnosis)
        drg_code = local_weight.get("drgCode") if local_weight else "ZZ91"
        drg_name = local_weight.get("drgName") if local_weight else "未入组"
        weight = float(local_weight.get("weight")) if local_weight else 1.0
        baseline_payment = self._calculate_payment(weight, runtime_config)
        return {
            "success": False,
            "adrg_code": "ZZ9",
            "adrg_name": "其他",
            "drg_code": drg_code,
            "drg_name": drg_name,
            "weight": weight,
            "baseline_payment": baseline_payment,
            "expected_los": {"min": 7, "max": 14},
            "confidence": 0.5,
            "risk_level": "unknown",
            "grouping_logic": f"分组失败: {error_msg}",
            "is_low_risk": bool(local_weight.get("isLowRisk")) if local_weight else None,
            "weight_source": "backend/app/data/drg_weights.json" if local_weight else "fallback_default",
            "config_version_id": runtime_config.get("config_version_id"),
            "runtime_config": self._public_runtime_config(runtime_config),
            "cost_ratio": 0,
            "cost_group": "base",
            "error": error_msg
        }

    def _calculate_payment(self, weight: float, runtime_config: Dict[str, Any]) -> float:
        return round(
            float(runtime_config.get("base_rate") or DEFAULT_BASE_PAYMENT)
            * float(weight or 0)
            * float(runtime_config.get("hospital_coefficient") or 1)
            * float(runtime_config.get("region_coefficient") or 1),
            2,
        )

    def _cost_ratio(self, total_fee: float, baseline_payment: float) -> float:
        try:
            return round(float(total_fee or 0) / float(baseline_payment or 0), 4)
        except Exception:
            return 0

    def _cost_group(
        self,
        total_fee: float,
        baseline_payment: float,
        runtime_config: Dict[str, Any],
    ) -> str:
        ratio = self._cost_ratio(total_fee, baseline_payment)
        if baseline_payment <= 0:
            return "base"
        if ratio >= float(runtime_config.get("high_rate_threshold") or 3):
            return "high_cost"
        if ratio <= float(runtime_config.get("low_rate_threshold") or 0.5):
            return "low_cost"
        return "base"

    def _public_runtime_config(self, runtime_config: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "base_rate": runtime_config.get("base_rate"),
            "hospital_coefficient": runtime_config.get("hospital_coefficient"),
            "region_coefficient": runtime_config.get("region_coefficient"),
            "high_rate_threshold": runtime_config.get("high_rate_threshold"),
            "low_rate_threshold": runtime_config.get("low_rate_threshold"),
        }


# 单例
drg_grouping_service = DRGGroupingService()


def get_drg_grouping_service() -> DRGGroupingService:
    return drg_grouping_service
