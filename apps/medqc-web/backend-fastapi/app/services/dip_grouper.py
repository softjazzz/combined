"""
DIP 分组服务
"""
from typing import Dict, Any, List, Optional
try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)

from app.config import settings
import httpx

class DIPGrouperService:
    """DIP 分组器服务"""

    def __init__(self):
        pass

    async def group(
        self,
        city_name: str,
        pdx_code: str,
        adx_code: Optional[str],
        proc_code: Optional[str],
        patient_gender: str,
        patient_age: int,
        los: int,
        total_fee: float = 0
    ) -> Dict[str, Any]:
        """
        DIP 分组
        调用外部 API: medchat.fun/api/dip-grouping
        """
        try:
            url = settings.DIP_API_URL
            if not url:
                # Default fallback if not set in config yet
                url = "https://medchat.fun/api/dip-grouping"

            # 构造 Payload
            # 注意：外部 API 要求的字段名可能根据 user request 中的 payload 调整
            payload = {
                "city_name": city_name,
                "pdx_code": pdx_code,
                "adx_code": adx_code or "",
                "proc_code": proc_code or "",
                "patient_gender": patient_gender,
                "patient_age": patient_age,
                "los": los,
                "total_fee": total_fee,
                # 默认/固定参数
                "birth_weight": 0,
                "fee_per_point": 60,
                "high_ratio_limit": 3,
                "icu": 0,
                "low_ratio_limit": 0.5,
                "rate": 1,
                "settlement_source": "none"
            }

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "MedQC-Backend/1.0"
            }

            logger.info(f"调用 DIP 分组 API: {url} | City={city_name} | PDX={pdx_code}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                
                if resp.status_code != 200:
                    raise Exception(f"External API Error: {resp.status_code} - {resp.text[:100]}")
                
                data = resp.json()
                if not data.get("success"):
                     raise Exception(f"External API Failed: {data.get('message', 'Unknown error')}")

                # 解析结果
                # Result is a list, take first item
                result_list = data.get("result", [])
                if not result_list:
                    raise Exception("No grouping result returned")
                
                result_item = result_list[0]
                grouping_path = data.get("grouping_path", {})
                
                # Extract fields
                dip_code = result_item.get("dipcode", "-")
                # dip_name usually comes from catalogue but here we might not have it directly in result_item
                # Looking at sample response: "dip_code": "J18.9-null", "dip_name": "..." is inside reference_grouping sometimes?
                # Wait, the sample response in user prompt:
                # "result": [{"dipcode": "J18.9-null", ...}]
                # "grouping_path": { "dip_info_actual": { "type": "核心内科组" ... } }
                # "reference_grouping": { "pdx_related": [ ... ] }
                
                # We try to find a name if possible, otherwise use type
                dip_name = grouping_path.get("dip_info_actual", {}).get("type", "未知分组")
                dip_type = grouping_path.get("dip_info_actual", {}).get("type", "未知类型")
                
                # Try to matches dip_code in reference_grouping to find a better name?
                # User sample had "dip_name" in "reference_grouping" items.
                
                return {
                    "dip_code": dip_code,
                    "dip_name": dip_name,
                    "dip_type": dip_type,
                    "diag_code": result_item.get("PDX"),
                    "proc_code": result_item.get("PROCs"),
                    "grouping_path": grouping_path.get("final_outcome", "Success")
                }

        except Exception as e:
            logger.error(f"DIP 分组失败: {str(e)}")
            raise e

# 全局 DIP 分组器实例
dip_grouper = DIPGrouperService()
