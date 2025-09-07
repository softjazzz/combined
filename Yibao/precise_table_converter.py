#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精确的医保规则表格转换器
专门处理您提供的表格格式，确保输出清晰的表格结构
"""

import os
import sys
import logging
from pathlib import Path
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/Yibao/precise_conversion.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PreciseTableConverter:
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.venv_path = "/home/ubuntu/Yibao/pdf_converter_venv"
    
    def _extract_clean_tables(self, pdf_path: Path) -> str:
        """提取并清理表格数据"""
        try:
            import pdfplumber
            
            with pdfplumber.open(str(pdf_path)) as pdf:
                all_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        all_text += page_text + "\n"
                
                # 根据文件名判断处理方式
                if "手术项目" in pdf_path.name:
                    return self._parse_surgery_table(all_text, pdf_path.stem)
                elif "药品" in pdf_path.name:
                    return self._parse_drug_table(all_text, pdf_path.stem)
                else:
                    return self._parse_general_table(all_text, pdf_path.stem)
            
        except Exception as e:
            logger.error(f"表格提取失败: {e}")
            return ""
    
    def _parse_surgery_table(self, text: str, title: str) -> str:
        """解析手术项目表格"""
        lines = text.split('\n')
        
        markdown_content = [f"# {title}\n\n"]
        
        # 查找表格标题
        for line in lines:
            if "规则对应知识点明细" in line:
                markdown_content.append(f"## {line.strip()}\n\n")
                break
        
        # 定义表格头
        headers = [
            "序号",
            "医疗服务项目名称", 
            "检出逻辑",
            "逻辑依据（同切口组别名称）",
            "项目代码供参考（国家医保局全国医疗服务项目）",
            "备注"
        ]
        
        # 创建表格
        table_rows = []
        current_row = [""] * 6
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # 检测序号行
            序号_match = re.match(r'^(\d+)\s+(.+)', line)
            if 序号_match:
                # 保存之前的行
                if current_row[0]:
                    table_rows.append(current_row[:])
                
                # 开始新行
                current_row = [""] * 6
                current_row[0] = 序号_match.group(1)
                current_row[1] = 序号_match.group(2).strip()
                
            # 检测检出逻辑
            elif "经同一切口进行的两种及以上不同的手术" in line:
                current_row[2] = "经同一切口进行的两种及以上不同的手术，第二及以后的手术未按规定折价计收"
                
            # 检测逻辑依据（手术组）
            elif re.search(r'(胃肠手术组|直肠肛门手术组|经腹直肠手术组|肝胆手术组|膀胱尿道手术组|男性生殖系统手术组|女性生殖系统手术组)', line):
                match = re.search(r'(胃肠手术组|直肠肛门手术组|经腹直肠手术组|肝胆手术组|膀胱尿道手术组|男性生殖系统手术组|女性生殖系统手术组)', line)
                if match:
                    current_row[3] = match.group(1)
            
            # 检测项目代码（15位数字）
            elif re.search(r'\b(\d{15})\b', line):
                match = re.search(r'\b(\d{15})\b', line)
                if match:
                    current_row[4] = match.group(1)
            
            # 检测备注
            elif "各省依据国家项目代码" in line:
                current_row[5] = "各省依据国家项目代码，配置规则知识点中各省项目代码"
            
            i += 1
        
        # 添加最后一行
        if current_row[0]:
            table_rows.append(current_row)
        
        # 生成Markdown表格
        if table_rows:
            # 表头
            header_line = "| " + " | ".join(headers) + " |"
            separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            
            markdown_content.append(header_line + "\n")
            markdown_content.append(separator_line + "\n")
            
            # 数据行
            for row in table_rows:
                # 清理和截断过长的内容
                cleaned_row = []
                for cell in row:
                    cell = str(cell).strip()
                    # 如果内容太长，截断并添加省略号
                    if len(cell) > 50 and cell != row[1]:  # 项目名称可以长一些
                        cell = cell[:47] + "..."
                    cleaned_row.append(cell)
                
                row_line = "| " + " | ".join(cleaned_row) + " |"
                markdown_content.append(row_line + "\n")
            
            markdown_content.append(f"\n**统计信息：**\n")
            markdown_content.append(f"- 总计项目数量：{len(table_rows)} 项\n\n")
        
        return ''.join(markdown_content)
    
    def _parse_drug_table(self, text: str, title: str) -> str:
        """解析药品表格"""
        lines = text.split('\n')
        
        markdown_content = [f"# {title}\n\n"]
        
        # 查找表格标题
        for line in lines:
            if "规则对应知识点明细" in line:
                markdown_content.append(f"## {line.strip()}\n\n")
                break
        
        # 定义表格头
        headers = [
            "序号",
            "药品通用名",
            "检出逻辑", 
            "逻辑依据（2024版国家药品目录备注）",
            "知识点对应",
            "药品代码数量"
        ]
        
        # 创建表格
        table_rows = []
        current_row = [""] * 6
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # 检测序号行
            序号_match = re.match(r'^(\d+)\s+(.+)', line)
            if 序号_match:
                # 保存之前的行
                if current_row[0]:
                    table_rows.append(current_row[:])
                
                # 开始新行
                current_row = [""] * 6
                current_row[0] = 序号_match.group(1)
                remaining = 序号_match.group(2).strip()
                
                # 尝试提取药品名称（通常在序号后面）
                drug_name_match = re.match(r'^([^\s]+(?:\s+[^\s]+)*?)\s+(.+)', remaining)
                if drug_name_match:
                    current_row[1] = drug_name_match.group(1)
                    rest_text = drug_name_match.group(2)
                    
                    # 检查是否包含检出逻辑
                    if "参保人年龄超出" in rest_text or "限" in rest_text:
                        current_row[2] = "参保人年龄超出儿童年龄限制"
                        
                        # 提取限制条件作为逻辑依据
                        limit_match = re.search(r'限[：:]?(.+?)(?:\s+\d+|$)', rest_text)
                        if limit_match:
                            current_row[3] = "限：" + limit_match.group(1).strip()
                else:
                    current_row[1] = remaining
            
            # 检测其他信息
            elif current_row[0] and "限" in line and not current_row[3]:
                current_row[3] = line.strip()
            
            # 检测数字（可能是药品代码数量）
            elif current_row[0] and re.match(r'^\d+$', line):
                current_row[5] = line
            
            i += 1
        
        # 添加最后一行
        if current_row[0]:
            table_rows.append(current_row)
        
        # 生成Markdown表格
        if table_rows:
            # 表头
            header_line = "| " + " | ".join(headers) + " |"
            separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"
            
            markdown_content.append(header_line + "\n")
            markdown_content.append(separator_line + "\n")
            
            # 数据行
            for row in table_rows:
                # 清理内容
                cleaned_row = []
                for cell in row:
                    cell = str(cell).strip()
                    # 如果内容太长，适当截断
                    if len(cell) > 80:
                        cell = cell[:77] + "..."
                    cleaned_row.append(cell)
                
                row_line = "| " + " | ".join(cleaned_row) + " |"
                markdown_content.append(row_line + "\n")
            
            markdown_content.append(f"\n**统计信息：**\n")
            markdown_content.append(f"- 总计药品数量：{len(table_rows)} 项\n\n")
        
        return ''.join(markdown_content)
    
    def _parse_general_table(self, text: str, title: str) -> str:
        """解析通用表格"""
        return self._parse_drug_table(text, title)  # 默认使用药品表格格式
    
    def convert_single_pdf(self, pdf_path: Path) -> bool:
        """转换单个PDF文件"""
        if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
            logger.error(f"文件不存在或不是PDF格式: {pdf_path}")
            return False
        
        md_filename = pdf_path.stem + '_precise.md'
        md_path = self.output_dir / md_filename
        
        logger.info(f"开始转换: {pdf_path.name} -> {md_filename}")
        
        try:
            content = self._extract_clean_tables(pdf_path)
            
            if content:
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"✓ 转换成功: {pdf_path.name}")
                return True
            else:
                logger.error(f"✗ 转换失败: {pdf_path.name}")
                return False
                
        except Exception as e:
            logger.error(f"✗ 转换出错 {pdf_path.name}: {e}")
            return False
    
    def convert_all_pdfs(self):
        """转换所有PDF文件"""
        if not self.source_dir.exists():
            logger.error(f"源目录不存在: {self.source_dir}")
            return
        
        pdf_files = list(self.source_dir.glob('*.pdf'))
        
        if not pdf_files:
            logger.warning(f"在 {self.source_dir} 中没有找到PDF文件")
            return
        
        logger.info(f"找到 {len(pdf_files)} 个PDF文件")
        
        success_count = 0
        failed_files = []
        
        for pdf_file in pdf_files:
            if self.convert_single_pdf(pdf_file):
                success_count += 1
            else:
                failed_files.append(pdf_file.name)
        
        logger.info(f"\n转换完成!")
        logger.info(f"成功转换: {success_count}/{len(pdf_files)} 个文件")
        
        if failed_files:
            logger.warning(f"转换失败的文件: {', '.join(failed_files)}")
        
        logger.info(f"输出目录: {self.output_dir}")

def main():
    """主函数"""
    source_directory = "/home/ubuntu/Yibao/医保规则"
    output_directory = "/home/ubuntu/Yibao/医保规则_precise"
    
    logger.info("精确医保规则表格转换器")
    logger.info("=" * 50)
    
    converter = PreciseTableConverter(source_directory, output_directory)
    converter.convert_all_pdfs()

if __name__ == "__main__":
    main()
