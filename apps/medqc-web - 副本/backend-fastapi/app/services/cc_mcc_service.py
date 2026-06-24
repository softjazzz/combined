"""
CC/MCC 知识库服务
提供 CC (Complication) 和 MCC (Major Complication) 查询功能
"""

import os
from typing import Dict, Optional, Set
from pathlib import Path

try:
    from loguru import logger
except Exception:
    import logging
    logger = logging.getLogger(__name__)


class CCMCCService:
    """CC/MCC 知识库服务"""
    
    def __init__(self, drg_version: str = "CHS_DRG_11"):
        """
        初始化 CC/MCC 服务
        
        Args:
            drg_version: DRG 版本，默认 CHS_DRG_11
        """
        self.drg_version = drg_version
        
        # 存储 CC/MCC 数据
        self.cc_dict: Dict[str, Dict[str, str]] = {}  # {code: {name, exclude_table}}
        self.mcc_dict: Dict[str, Dict[str, str]] = {}  # {code: {name, exclude_table}}
        
        # 快速查询集合
        self.cc_codes: Set[str] = set()
        self.mcc_codes: Set[str] = set()
        
        # 加载数据
        self._load_from_files()
        
        logger.info(
            f"CC/MCC 知识库加载完成: "
            f"CC={len(self.cc_codes)}, MCC={len(self.mcc_codes)}"
        )
    
    def _get_rule_file_path(self, filename: str) -> Path:
        """
        获取规则文件路径
        
        Args:
            filename: 文件名，如 "5_MCC.txt"
            
        Returns:
            文件的绝对路径
        """
        # 获取当前文件所在目录
        current_dir = Path(__file__).parent.parent
        
        # 构建规则文件路径
        rule_path = current_dir / "DRG1118" / "DRG_Rules" / self.drg_version / filename
        
        if not rule_path.exists():
            # 尝试备用路径（如果项目结构不同）
            alt_path = Path("/home/ubuntu/coding/health-qc-monorepo/apps/medqc-web/DRG1118/DRG_Rules") / self.drg_version / filename
            if alt_path.exists():
                return alt_path
            
            logger.warning(f"规则文件不存在: {rule_path}")
            return rule_path
        
        return rule_path
    
    def _parse_rule_file(self, filepath: Path) -> Dict[str, Dict[str, str]]:
        """
        解析规则文件
        
        文件格式示例:
        疾病编码 疾病名称 排除内容
        A01.100 副伤寒甲 表 7-1
        A02.000 沙门菌肠炎 表 7-1
        
        Args:
            filepath: 规则文件路径
            
        Returns:
            {code: {name: str, exclude_table: str}}
        """
        result = {}
        
        if not filepath.exists():
            logger.warning(f"文件不存在: {filepath}")
            return result
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    # 跳过空行和标题行
                    line = line.strip()
                    if not line or line.startswith('疾病编码'):
                        continue
                    
                    # 解析行内容
                    parts = line.split()
                    if len(parts) >= 2:
                        code = parts[0]
                        name = parts[1]
                        exclude_table = ' '.join(parts[2:]) if len(parts) > 2 else ''
                        
                        result[code] = {
                            'name': name,
                            'exclude_table': exclude_table
                        }
            
            logger.info(f"成功解析 {filepath.name}: {len(result)} 条记录")
            
        except Exception as e:
            logger.error(f"解析文件失败 {filepath}: {str(e)}")
        
        return result
    
    def _load_from_files(self):
        """从文件加载 CC/MCC 数据"""
        # 加载 MCC
        mcc_file = self._get_rule_file_path("5_MCC.txt")
        self.mcc_dict = self._parse_rule_file(mcc_file)
        self.mcc_codes = set(self.mcc_dict.keys())
        
        # 加载 CC
        cc_file = self._get_rule_file_path("6_CC.txt")
        self.cc_dict = self._parse_rule_file(cc_file)
        self.cc_codes = set(self.cc_dict.keys())
    
    def is_cc(self, icd_code: str) -> bool:
        """
        判断 ICD 编码是否为 CC
        
        Args:
            icd_code: ICD 编码，如 "N18.3"
            
        Returns:
            是否为 CC
        """
        return icd_code in self.cc_codes
    
    def is_mcc(self, icd_code: str) -> bool:
        """
        判断 ICD 编码是否为 MCC
        
        Args:
            icd_code: ICD 编码，如 "N18.5"
            
        Returns:
            是否为 MCC
        """
        return icd_code in self.mcc_codes
    
    def is_cc_or_mcc(self, icd_code: str) -> bool:
        """
        判断 ICD 编码是否为 CC 或 MCC
        
        Args:
            icd_code: ICD 编码
            
        Returns:
            是否为 CC 或 MCC
        """
        return self.is_cc(icd_code) or self.is_mcc(icd_code)
    
    def get_cc_mcc_info(self, icd_code: str) -> Dict[str, any]:
        """
        获取 ICD 编码的 CC/MCC 信息
        
        Args:
            icd_code: ICD 编码
            
        Returns:
            {
                "code": str,
                "is_cc": bool,
                "is_mcc": bool,
                "name": str | None,
                "exclude_table": str | None,
                "type": "mcc" | "cc" | "none"
            }
        """
        is_mcc = self.is_mcc(icd_code)
        is_cc = self.is_cc(icd_code)
        
        # 确定类型（MCC 优先级高于 CC）
        if is_mcc:
            cc_type = "mcc"
            info = self.mcc_dict.get(icd_code, {})
        elif is_cc:
            cc_type = "cc"
            info = self.cc_dict.get(icd_code, {})
        else:
            cc_type = "none"
            info = {}
        
        return {
            "code": icd_code,
            "is_cc": is_cc,
            "is_mcc": is_mcc,
            "name": info.get('name'),
            "exclude_table": info.get('exclude_table'),
            "type": cc_type
        }
    
    def get_all_cc_codes(self) -> Set[str]:
        """获取所有 CC 编码集合"""
        return self.cc_codes.copy()
    
    def get_all_mcc_codes(self) -> Set[str]:
        """获取所有 MCC 编码集合"""
        return self.mcc_codes.copy()
    
    def get_statistics(self) -> Dict[str, int]:
        """
        获取统计信息
        
        Returns:
            {
                "total_cc": int,
                "total_mcc": int,
                "total": int
            }
        """
        return {
            "total_cc": len(self.cc_codes),
            "total_mcc": len(self.mcc_codes),
            "total": len(self.cc_codes) + len(self.mcc_codes)
        }


# 全局单例
_cc_mcc_service: Optional[CCMCCService] = None


def get_cc_mcc_service() -> CCMCCService:
    """
    获取 CC/MCC 服务单例
    
    Returns:
        CCMCCService 实例
    """
    global _cc_mcc_service
    if _cc_mcc_service is None:
        _cc_mcc_service = CCMCCService()
    return _cc_mcc_service
