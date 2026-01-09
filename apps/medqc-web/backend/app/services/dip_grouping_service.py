"""
DIP 分组服务

提供泸州市 DIP 入组预测功能
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DIPGrouperService:
    """DIP 分组服务"""
    
    # 简化的 DIP 分组规则（Mock）
    # 真实实现需要对接泸州市 DIP 分组引擎
    DIP_RULES = {
        # 诊断编码前缀 -> DIP 分组
        "I21": {"dip_code": "RC1", "dip_name": "急性心肌梗死", "dip_type": "核心病种"},
        "I10": {"dip_code": "RC2", "dip_name": "高血压病", "dip_type": "核心病种"},
        "I50": {"dip_code": "RC3", "dip_name": "心力衰竭", "dip_type": "核心病种"},
        "I25": {"dip_code": "RC4", "dip_name": "冠状动脉粥样硬化性心脏病", "dip_type": "核心病种"},
        "J18": {"dip_code": "RC5", "dip_name": "社区获得性肺炎", "dip_type": "核心病种"},
        "K35": {"dip_code": "RC6", "dip_name": "急性阑尾炎", "dip_type": "核心病种"},
        "E11": {"dip_code": "RC7", "dip_name": "2型糖尿病", "dip_type": "核心病种"},
        "K80": {"dip_code": "RC8", "dip_name": "胆石症", "dip_type": "核心病种"},
        "N20": {"dip_code": "RC9", "dip_name": "肾结石", "dip_type": "核心病种"},
        "C34": {"dip_code": "RC10", "dip_name": "肺恶性肿瘤", "dip_type": "核心病种"},
    }
    
    # 手术编码 -> DIP 调整
    PROCEDURE_ADJUSTMENTS = {
        "36.06": {"suffix": "-OP1", "name_suffix": "（支架植入）"},
        "36.07": {"suffix": "-OP1", "name_suffix": "（支架植入）"},
        "88.72": {"suffix": "-OP2", "name_suffix": "（造影）"},
        "47.01": {"suffix": "-OP3", "name_suffix": "（腹腔镜手术）"},
    }
    
    async def group_dip(
        self,
        city_name: str,
        pdx_code: str,
        adx_code: str = "",
        proc_code: str = "",
        patient_gender: str = "M",
        patient_age: int = 50,
        los: int = 7,
        total_fee: float = 0
    ) -> Dict[str, Any]:
        """
        执行 DIP 分组
        
        Args:
            city_name: 城市名称（泸州市）
            pdx_code: 主诊断编码
            adx_code: 次要诊断编码
            proc_code: 手术/操作编码
            patient_gender: 性别 (M/F)
            patient_age: 年龄
            los: 住院天数
            total_fee: 总费用
            
        Returns:
            分组结果
        """
        logger.info(f"DIP 分组请求: city={city_name}, pdx={pdx_code}, proc={proc_code}")
        
        # 清洗诊断编码
        clean_pdx = pdx_code.strip().upper().replace(".", "")[:3] if pdx_code else ""
        
        # 查找匹配的 DIP 规则
        dip_result = None
        for prefix, rule in self.DIP_RULES.items():
            if clean_pdx.startswith(prefix.replace(".", "")):
                dip_result = rule.copy()
                break
        
        # 如果没有匹配，使用默认分组
        if not dip_result:
            dip_result = {
                "dip_code": "CORE-综合",
                "dip_name": "综合分组",
                "dip_type": "综合病种"
            }
        
        # 应用手术调整
        if proc_code:
            clean_proc = proc_code.strip()[:5]
            for proc_prefix, adjustment in self.PROCEDURE_ADJUSTMENTS.items():
                if clean_proc.startswith(proc_prefix.replace(".", "")):
                    dip_result["dip_code"] += adjustment["suffix"]
                    dip_result["dip_name"] += adjustment["name_suffix"]
                    break
        
        # 构建分组路径描述
        grouping_path = f"主诊断 {pdx_code} 匹配 {dip_result['dip_type']}"
        if proc_code:
            grouping_path += f" + 手术 {proc_code}"
        
        return {
            "dip_code": dip_result["dip_code"],
            "dip_name": dip_result["dip_name"],
            "dip_type": dip_result["dip_type"],
            "grouping_path": grouping_path,
            "city_name": city_name,
            "pdx_code": pdx_code,
            "proc_code": proc_code,
            "los": los,
            "total_fee": total_fee,
            "success": True
        }
