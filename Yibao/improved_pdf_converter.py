#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
改进的PDF到Markdown转换器 - 专门处理表格格式
针对医保规则PDF文档优化，保持表格结构清晰
"""

import os
import sys
import logging
from pathlib import Path
import subprocess
import pandas as pd
import re

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/Yibao/improved_conversion.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class ImprovedPDFConverter:
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.venv_path = "/home/ubuntu/Yibao/pdf_converter_venv"
        
    def _extract_tables_with_camelot(self, pdf_path: Path) -> list:
        """使用camelot提取表格"""
        try:
            import camelot
            tables = camelot.read_pdf(str(pdf_path), pages='all', flavor='lattice')
            logger.info(f"使用camelot提取到 {len(tables)} 个表格")
            return tables
        except Exception as e:
            logger.warning(f"camelot提取失败: {e}")
            return []
    
    def _extract_tables_with_tabula(self, pdf_path: Path) -> list:
        """使用tabula-py提取表格"""
        try:
            import tabula
            tables = tabula.read_pdf(str(pdf_path), pages='all', multiple_tables=True)
            logger.info(f"使用tabula提取到 {len(tables)} 个表格")
            return tables
        except Exception as e:
            logger.warning(f"tabula提取失败: {e}")
            return []
    
    def _extract_with_pdfplumber_tables(self, pdf_path: Path) -> str:
        """使用pdfplumber提取表格并格式化为Markdown"""
        try:
            import pdfplumber
            
            markdown_content = []
            markdown_content.append(f"# {pdf_path.stem}\n\n")
            
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    markdown_content.append(f"## 第 {page_num + 1} 页\n\n")
                    
                    # 尝试提取表格
                    tables = page.extract_tables()
                    
                    if tables:
                        for table_num, table in enumerate(tables):
                            if table and len(table) > 0:
                                markdown_content.append(f"### 表格 {table_num + 1}\n\n")
                                
                                # 转换为DataFrame以便更好地处理
                                df = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                                
                                # 清理数据
                                df = df.fillna('')
                                df = df.applymap(lambda x: str(x).strip() if x else '')
                                
                                # 转换为Markdown表格
                                markdown_table = df.to_markdown(index=False, tablefmt='pipe')
                                markdown_content.append(markdown_table + "\n\n")
                    else:
                        # 如果没有表格，提取普通文本
                        text = page.extract_text()
                        if text:
                            # 尝试识别表格模式的文本并格式化
                            formatted_text = self._format_text_as_table(text)
                            markdown_content.append(formatted_text + "\n\n")
            
            return ''.join(markdown_content)
            
        except Exception as e:
            logger.error(f"pdfplumber表格提取失败: {e}")
            return ""
    
    def _format_text_as_table(self, text: str) -> str:
        """尝试将文本格式化为表格"""
        lines = text.split('\n')
        formatted_lines = []
        
        # 检测可能的表格行
        table_lines = []
        current_table = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_table:
                    table_lines.append(current_table)
                    current_table = []
                continue
            
            # 检测是否为表格行（包含多个字段）
            if self._is_table_row(line):
                current_table.append(line)
            else:
                if current_table:
                    table_lines.append(current_table)
                    current_table = []
                formatted_lines.append(line)
        
        if current_table:
            table_lines.append(current_table)
        
        # 处理检测到的表格
        result = []
        for item in formatted_lines:
            if isinstance(item, str):
                result.append(item)
        
        for table in table_lines:
            if len(table) > 1:
                result.append(self._convert_to_markdown_table(table))
        
        return '\n'.join(result)
    
    def _is_table_row(self, line: str) -> bool:
        """判断是否为表格行"""
        # 简单的启发式规则
        # 检查是否包含数字序号、代码等
        patterns = [
            r'^\d+\s+',  # 以数字开头
            r'\d{12,}',  # 包含长数字（如代码）
            r'[\u4e00-\u9fff]+\s+[\u4e00-\u9fff]+\s+[\u4e00-\u9fff]+',  # 多个中文词组
        ]
        
        for pattern in patterns:
            if re.search(pattern, line):
                return True
        return False
    
    def _convert_to_markdown_table(self, table_lines: list) -> str:
        """将文本行转换为Markdown表格"""
        if not table_lines:
            return ""
        
        # 尝试解析表格结构
        rows = []
        for line in table_lines:
            # 简单的字段分割（可能需要根据实际情况调整）
            fields = re.split(r'\s{2,}', line.strip())
            rows.append(fields)
        
        if not rows:
            return ""
        
        # 确定列数
        max_cols = max(len(row) for row in rows)
        
        # 标准化行
        normalized_rows = []
        for row in rows:
            while len(row) < max_cols:
                row.append('')
            normalized_rows.append(row[:max_cols])
        
        # 生成Markdown表格
        if len(normalized_rows) == 1:
            # 只有一行，作为标题
            header = '| ' + ' | '.join(normalized_rows[0]) + ' |'
            separator = '| ' + ' | '.join(['---'] * len(normalized_rows[0])) + ' |'
            return header + '\n' + separator + '\n'
        else:
            # 第一行作为标题
            header = '| ' + ' | '.join(normalized_rows[0]) + ' |'
            separator = '| ' + ' | '.join(['---'] * len(normalized_rows[0])) + ' |'
            
            table_md = [header, separator]
            for row in normalized_rows[1:]:
                table_md.append('| ' + ' | '.join(row) + ' |')
            
            return '\n'.join(table_md) + '\n'
    
    def _install_table_libraries(self):
        """安装表格处理相关的库"""
        libraries = [
            'camelot-py[cv]',
            'tabula-py', 
            'pandas',
            'openpyxl'
        ]
        
        for lib in libraries:
            try:
                subprocess.check_call([
                    f"{self.venv_path}/bin/python", '-m', 'pip', 'install', lib
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info(f"✓ {lib} 安装成功")
            except subprocess.CalledProcessError:
                logger.warning(f"⚠ {lib} 安装失败")
    
    def convert_single_pdf(self, pdf_path: Path) -> bool:
        """转换单个PDF文件"""
        if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
            logger.error(f"文件不存在或不是PDF格式: {pdf_path}")
            return False
        
        md_filename = pdf_path.stem + '_improved.md'
        md_path = self.output_dir / md_filename
        
        logger.info(f"开始转换: {pdf_path.name} -> {md_filename}")
        
        try:
            # 使用改进的pdfplumber方法
            content = self._extract_with_pdfplumber_tables(pdf_path)
            
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
        
        # 安装必要的库
        logger.info("安装表格处理库...")
        self._install_table_libraries()
        
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
    output_directory = "/home/ubuntu/Yibao/医保规则_improved_md"
    
    logger.info("改进的PDF to Markdown 转换器")
    logger.info("=" * 50)
    
    converter = ImprovedPDFConverter(source_directory, output_directory)
    converter.convert_all_pdfs()

if __name__ == "__main__":
    main()
