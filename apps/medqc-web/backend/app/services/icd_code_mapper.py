"""
ICD 编码映射服务

将国临版 ICD-10 编码转换为医保版编码
用于 DRG/DIP 入组时调用远程 API
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional, Tuple
from zipfile import ZipFile

logger = logging.getLogger(__name__)


class ICDCodeMapper:
    """ICD 编码映射器 - 国临版 <-> 医保版"""
    
    # Excel 文件路径
    MAPPING_FILE = Path(__file__).parent.parent.parent.parent.parent.parent / "DRG" / "20250924更新-疾病诊断编码映射表（国临2.0 2022汇总版对应医保版2.0）.xlsx"
    
    _instance: Optional["ICDCodeMapper"] = None
    _initialized: bool = False
    
    def __new__(cls) -> "ICDCodeMapper":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # 国临 -> 医保 映射
        self._guolin_to_yibao: Dict[str, Tuple[str, str]] = {}
        # 医保 -> 国临 映射
        self._yibao_to_guolin: Dict[str, Tuple[str, str]] = {}
        
        self._load_mapping()
        self._initialized = True
    
    def _load_mapping(self) -> None:
        """从 xlsx 文件加载映射表"""
        if not self.MAPPING_FILE.exists():
            logger.warning(f"映射文件不存在: {self.MAPPING_FILE}")
            return
        
        try:
            logger.info(f"正在加载 ICD 编码映射表: {self.MAPPING_FILE}")
            
            with ZipFile(self.MAPPING_FILE) as z:
                # 读取 shared strings
                ns = {'ns': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                ss_xml = z.read('xl/sharedStrings.xml')
                ss_root = ET.fromstring(ss_xml)
                strings = []
                for si in ss_root.findall('.//ns:si', ns):
                    t = si.find('.//ns:t', ns)
                    strings.append((t.text or '').strip() if t is not None else '')
                
                # 读取 sheet1
                sheet_xml = z.read('xl/worksheets/sheet1.xml')
                sheet_root = ET.fromstring(sheet_xml)
                rows = sheet_root.findall('.//ns:row', ns)
                
                # 跳过表头，处理数据行
                for row in rows[1:]:
                    cells = row.findall('.//ns:c', ns)
                    if len(cells) < 4:
                        continue
                    
                    row_data = []
                    for c in cells[:4]:
                        v = c.find('ns:v', ns)
                        t = c.get('t')
                        if v is not None and t == 's':
                            row_data.append(strings[int(v.text)])
                        elif v is not None:
                            row_data.append(v.text)
                        else:
                            row_data.append('')
                    
                    if len(row_data) >= 4:
                        guolin_code = row_data[0].strip()
                        guolin_name = row_data[1].strip()
                        yibao_code = row_data[2].strip()
                        yibao_name = row_data[3].strip()
                        
                        if guolin_code and yibao_code:
                            self._guolin_to_yibao[guolin_code] = (yibao_code, yibao_name)
                            # 反向映射（取第一个）
                            if yibao_code not in self._yibao_to_guolin:
                                self._yibao_to_guolin[yibao_code] = (guolin_code, guolin_name)
            
            logger.info(f"ICD 编码映射表加载完成: {len(self._guolin_to_yibao)} 条记录")
            
        except Exception as e:
            logger.error(f"加载 ICD 编码映射表失败: {e}")
    
    def map_to_yibao(self, guolin_code: str) -> Tuple[str, str]:
        """
        将国临版编码转换为医保版编码
        
        Args:
            guolin_code: 国临版 ICD-10 编码
            
        Returns:
            (医保版编码, 医保版名称) - 如果找不到映射则返回原编码
        """
        if not guolin_code:
            return ("", "")
        
        code = guolin_code.strip()
        
        # 直接匹配
        if code in self._guolin_to_yibao:
            return self._guolin_to_yibao[code]
        
        # 尝试模糊匹配 - 去掉 x00 后缀
        if 'x' in code.lower():
            base_code = code.split('x')[0]
            for k, v in self._guolin_to_yibao.items():
                if k.startswith(base_code):
                    return v
        
        # 找不到映射，返回原编码
        logger.debug(f"未找到编码映射: {guolin_code}")
        return (code, "")
    
    def map_to_guolin(self, yibao_code: str) -> Tuple[str, str]:
        """
        将医保版编码转换为国临版编码
        
        Args:
            yibao_code: 医保版 ICD-10 编码
            
        Returns:
            (国临版编码, 国临版名称)
        """
        if not yibao_code:
            return ("", "")
        
        code = yibao_code.strip()
        
        if code in self._yibao_to_guolin:
            return self._yibao_to_guolin[code]
        
        return (code, "")
    
    def map_codes_list(self, codes: list) -> list:
        """
        批量转换编码列表
        
        Args:
            codes: 国临版编码列表
            
        Returns:
            医保版编码列表
        """
        return [self.map_to_yibao(code)[0] for code in codes]
    
    @property
    def mapping_count(self) -> int:
        """返回映射表记录数"""
        return len(self._guolin_to_yibao)


# 单例访问
_mapper: Optional[ICDCodeMapper] = None


def get_icd_mapper() -> ICDCodeMapper:
    """获取 ICD 编码映射器单例"""
    global _mapper
    if _mapper is None:
        _mapper = ICDCodeMapper()
    return _mapper
