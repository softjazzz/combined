#!/usr/bin/env python3
"""
PDF文档解析服务
支持多种PDF解析方法：PyMuPDF (fitz)、pdfplumber、自动医疗信息识别
"""

import io
import logging
from typing import Dict, Any, Optional, List
import re
from pathlib import Path

# PDF解析库
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

logger = logging.getLogger(__name__)

class PDFParser:
    """PDF文档解析器"""
    
    def __init__(self):
        self.available_methods = []
        if HAS_PYMUPDF:
            self.available_methods.append('pymupdf')
        if HAS_PDFPLUMBER:
            self.available_methods.append('pdfplumber')
    
    def parse_pdf(self, file_content: bytes, filename: str = "") -> Dict[str, Any]:
        """
        解析PDF文件
        
        Args:
            file_content: PDF文件二进制内容
            filename: 文件名
            
        Returns:
            解析结果字典
        """
        result = {
            "success": False,
            "method": "",
            "pages": 0,
            "content": "",
            "medical_info": {},
            "error": None
        }
        
        try:
            # 优先使用PyMuPDF
            if HAS_PYMUPDF:
                result = self._parse_with_pymupdf(file_content, filename)
                if result["success"]:
                    result["method"] = "PyMuPDF (fitz) - 高性能PDF文本提取"
                    return result
            
            # 备用方案：pdfplumber
            if HAS_PDFPLUMBER:
                result = self._parse_with_pdfplumber(file_content, filename)
                if result["success"]:
                    result["method"] = "pdfplumber - 备用解析方案"
                    return result
            
            # 如果都不可用
            result["error"] = "PDF解析库不可用。请安装 PyMuPDF (fitz) 或 pdfplumber"
            result["method"] = "无可用解析库"
            
        except Exception as e:
            logger.error(f"PDF解析失败: {str(e)}")
            result["error"] = f"PDF解析失败: {str(e)}"
            result["method"] = "解析异常"
        
        return result
    
    def _parse_with_pymupdf(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """使用PyMuPDF解析PDF"""
        try:
            # 从字节流创建PDF文档
            doc = fitz.open(stream=file_content, filetype="pdf")
            
            full_text = ""
            page_count = len(doc)
            
            # 逐页提取文本
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                
                # 尝试多种文本提取方法
                text = ""
                
                # 方法1: 标准文本提取
                text = page.get_text()
                
                # 如果文本为空或主要是乱码，尝试其他方法
                if not text.strip() or self._is_mostly_garbled(text):
                    # 方法2: 使用不同的文本提取选项
                    text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
                
                if not text.strip() or self._is_mostly_garbled(text):
                    # 方法3: 提取文本块
                    blocks = page.get_text("dict")
                    text_parts = []
                    for block in blocks.get("blocks", []):
                        if "lines" in block:
                            for line in block["lines"]:
                                for span in line.get("spans", []):
                                    span_text = span.get("text", "")
                                    if span_text.strip():
                                        text_parts.append(span_text)
                    text = " ".join(text_parts)
                
                if text.strip():
                    full_text += f"\n=== 第{page_num + 1}页 ===\n"
                    full_text += text + "\n"
                else:
                    full_text += f"\n=== 第{page_num + 1}页 ===\n"
                    full_text += "[此页面无法提取文本内容，可能包含图片或特殊格式]\n"
            
            doc.close()
            
            # 清理文本
            cleaned_text = self._clean_text(full_text)
            
            # 如果解析结果主要是乱码，添加提示信息
            if self._is_mostly_garbled(cleaned_text):
                cleaned_text = f"""⚠️ PDF文本提取警告：
此PDF文件的文本内容可能存在以下问题：
1. 中文字体未正确嵌入PDF文件
2. PDF文件是扫描版本，需要OCR识别
3. PDF文件使用了特殊编码格式

原始提取内容：
{cleaned_text}

建议：
- 如果是扫描版PDF，请使用OCR工具先转换为文本
- 如果是电子版PDF，请检查字体嵌入设置
- 可以尝试将PDF转换为Word格式后重新上传"""
            
            # 提取医疗信息
            medical_info = self._extract_medical_info(cleaned_text)
            
            return {
                "success": True,
                "pages": page_count,
                "content": cleaned_text,
                "medical_info": medical_info,
                "error": None
            }
            
        except Exception as e:
            logger.error(f"PyMuPDF解析失败: {str(e)}")
            return {
                "success": False,
                "pages": 0,
                "content": "",
                "medical_info": {},
                "error": f"PyMuPDF解析失败: {str(e)}"
            }
    
    def _is_mostly_garbled(self, text: str) -> bool:
        """检查文本是否主要是乱码"""
        if not text or len(text.strip()) < 10:
            return False
        
        # 计算中文字符、英文字符和数字的比例
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        english_chars = len([c for c in text if c.isalpha() and ord(c) < 128])
        digits = len([c for c in text if c.isdigit()])
        
        total_chars = len([c for c in text if not c.isspace()])
        if total_chars == 0:
            return True
        
        # 对于医疗文档，如果中文字符很少，可能是字体嵌入问题
        chinese_ratio = chinese_chars / total_chars
        
        # 检查是否包含常见的医疗中文词汇
        medical_keywords = ['患者', '病史', '诊断', '治疗', '症状', '检查', '医生', '病历', '入院', '出院']
        has_medical_keywords = any(keyword in text for keyword in medical_keywords)
        
        # 如果中文字符比例很低且没有医疗关键词，可能是乱码
        if chinese_ratio < 0.05 and not has_medical_keywords:
            # 进一步检查：如果主要是数字和少量英文字母，很可能是PDF字体问题
            meaningful_chars = chinese_chars + english_chars + digits
            if meaningful_chars > 0:
                digit_ratio = digits / meaningful_chars
                # 如果数字占比超过70%，很可能是字体嵌入问题导致的乱码
                if digit_ratio > 0.7:
                    return True
        
        return False
    
    def _parse_with_pdfplumber(self, file_content: bytes, filename: str) -> Dict[str, Any]:
        """使用pdfplumber解析PDF"""
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                full_text = ""
                page_count = len(pdf.pages)
                
                # 逐页提取文本
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        full_text += f"\n=== 第{page_num + 1}页 ===\n"
                        full_text += text + "\n"
                
                # 清理文本
                cleaned_text = self._clean_text(full_text)
                
                # 提取医疗信息
                medical_info = self._extract_medical_info(cleaned_text)
                
                return {
                    "success": True,
                    "pages": page_count,
                    "content": cleaned_text,
                    "medical_info": medical_info,
                    "error": None
                }
                
        except Exception as e:
            logger.error(f"pdfplumber解析失败: {str(e)}")
            return {
                "success": False,
                "pages": 0,
                "content": "",
                "medical_info": {},
                "error": f"pdfplumber解析失败: {str(e)}"
            }
    
    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        if not text:
            return ""
        
        # 移除多余的空白字符
        text = re.sub(r'\n\s*\n', '\n\n', text)  # 合并多个换行
        text = re.sub(r' +', ' ', text)  # 合并多个空格
        
        # 移除特殊字符和乱码
        text = re.sub(r'[·•▪▫◦‣⁃]', '', text)  # 移除项目符号
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)  # 移除控制字符
        
        text = text.strip()
        
        return text
    
    def _extract_medical_info(self, text: str) -> Dict[str, Any]:
        """从文本中提取医疗信息"""
        medical_info = {
            "patient_name": None,
            "patient_age": None,
            "patient_gender": None,
            "department": None,
            "diagnosis": [],
            "symptoms": [],
            "vital_signs": {},
            "medications": [],
            "procedures": []
        }
        
        if not text:
            return medical_info
        
        try:
            # 提取患者姓名
            name_patterns = [
                r'患者[：:]\s*([^\s，,。.]{2,4})',
                r'姓名[：:]\s*([^\s，,。.]{2,4})',
                r'病人[：:]\s*([^\s，,。.]{2,4})'
            ]
            for pattern in name_patterns:
                match = re.search(pattern, text)
                if match:
                    medical_info["patient_name"] = match.group(1)
                    break
            
            # 提取年龄
            age_patterns = [
                r'年龄[：:]\s*(\d+)\s*岁',
                r'(\d+)\s*岁',
                r'年龄[：:]\s*(\d+)'
            ]
            for pattern in age_patterns:
                match = re.search(pattern, text)
                if match:
                    medical_info["patient_age"] = int(match.group(1))
                    break
            
            # 提取性别
            gender_patterns = [
                r'性别[：:]\s*(男|女)',
                r'，\s*(男|女)\s*，',
                r'患者.*?(男|女)'
            ]
            for pattern in gender_patterns:
                match = re.search(pattern, text)
                if match:
                    medical_info["patient_gender"] = match.group(1)
                    break
            
            # 提取科室
            dept_patterns = [
                r'科室[：:]\s*([^\s，,。.]+科)',
                r'([^\s，,。.]+科).*?病历',
                r'入院科室[：:]\s*([^\s，,。.]+科)'
            ]
            for pattern in dept_patterns:
                match = re.search(pattern, text)
                if match:
                    medical_info["department"] = match.group(1)
                    break
            
            # 提取诊断
            diagnosis_patterns = [
                r'诊断[：:]\s*([^\n]+)',
                r'初步诊断[：:]\s*([^\n]+)',
                r'临床诊断[：:]\s*([^\n]+)'
            ]
            for pattern in diagnosis_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    diagnoses = re.split(r'[，,；;]', match.strip())
                    medical_info["diagnosis"].extend([d.strip() for d in diagnoses if d.strip()])
            
            # 提取生命体征
            vital_patterns = {
                "temperature": r'体温[：:]\s*(\d+\.?\d*)\s*[℃°C]',
                "pulse": r'脉搏[：:]\s*(\d+)\s*次/分',
                "blood_pressure": r'血压[：:]\s*(\d+/\d+)\s*mmHg',
                "respiratory_rate": r'呼吸[：:]\s*(\d+)\s*次/分'
            }
            for key, pattern in vital_patterns.items():
                match = re.search(pattern, text)
                if match:
                    medical_info["vital_signs"][key] = match.group(1)
            
        except Exception as e:
            logger.warning(f"医疗信息提取失败: {str(e)}")
        
        return medical_info
    
    def get_available_methods(self) -> List[str]:
        """获取可用的解析方法"""
        return self.available_methods.copy()


# 创建全局解析器实例
pdf_parser = PDFParser()

def parse_pdf_file(file_content: bytes, filename: str = "") -> Dict[str, Any]:
    """
    解析PDF文件的便捷函数
    
    Args:
        file_content: PDF文件二进制内容
        filename: 文件名
        
    Returns:
        解析结果字典
    """
    return pdf_parser.parse_pdf(file_content, filename)


if __name__ == "__main__":
    # 测试代码
    print("PDF解析器测试")
    print(f"可用解析方法: {pdf_parser.get_available_methods()}")
    
    # 测试文件路径
    test_file = Path(__file__).parent.parent.parent / "张伟_病程记录.pdf"
    if test_file.exists():
        print(f"测试文件: {test_file}")
        with open(test_file, 'rb') as f:
            content = f.read()
        
        result = parse_pdf_file(content, test_file.name)
        print(f"解析结果: {result['success']}")
        print(f"解析方法: {result['method']}")
        print(f"页数: {result['pages']}")
        print(f"内容长度: {len(result['content'])}")
        if result['medical_info']:
            print(f"医疗信息: {result['medical_info']}")
    else:
        print("测试文件不存在")
