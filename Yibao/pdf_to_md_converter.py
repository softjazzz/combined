#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDF to Markdown Converter Script
将 PDF 文件批量转换为 Markdown 格式

使用方法:
python pdf_to_md_converter.py

依赖安装:
pip install markitdown pymupdf pdfplumber
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional
import subprocess

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/Yibao/conversion.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class PDFToMarkdownConverter:
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查可用的转换工具
        self.available_tools = self._check_available_tools()
        logger.info(f"可用的转换工具: {', '.join(self.available_tools)}")
    
    def _check_available_tools(self) -> List[str]:
        """检查系统中可用的转换工具"""
        tools = []
        
        # 检查 markitdown
        try:
            import markitdown
            tools.append('markitdown')
        except ImportError:
            logger.warning("markitdown 未安装")
        
        # 检查 pymupdf (fitz)
        try:
            import fitz
            tools.append('pymupdf')
        except ImportError:
            logger.warning("pymupdf 未安装")
        
        # 检查 pdfplumber
        try:
            import pdfplumber
            tools.append('pdfplumber')
        except ImportError:
            logger.warning("pdfplumber 未安装")
        
        return tools
    
    def _convert_with_markitdown(self, pdf_path: Path, md_path: Path) -> bool:
        """使用 markitdown 转换 PDF"""
        try:
            from markitdown import MarkItDown
            
            md = MarkItDown()
            result = md.convert(str(pdf_path))
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(result.text_content)
            
            logger.info(f"✓ 使用 markitdown 成功转换: {pdf_path.name}")
            return True
        except Exception as e:
            logger.error(f"✗ markitdown 转换失败 {pdf_path.name}: {e}")
            return False
    
    def _convert_with_pymupdf(self, pdf_path: Path, md_path: Path) -> bool:
        """使用 pymupdf 转换 PDF"""
        try:
            import fitz
            
            doc = fitz.open(str(pdf_path))
            markdown_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                
                if text.strip():
                    markdown_content.append(f"## 第 {page_num + 1} 页\n\n")
                    # 简单的文本格式化
                    lines = text.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line:
                            markdown_content.append(f"{line}\n\n")
            
            doc.close()
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(''.join(markdown_content))
            
            logger.info(f"✓ 使用 pymupdf 成功转换: {pdf_path.name}")
            return True
        except Exception as e:
            logger.error(f"✗ pymupdf 转换失败 {pdf_path.name}: {e}")
            return False
    
    def _convert_with_pdfplumber(self, pdf_path: Path, md_path: Path) -> bool:
        """使用 pdfplumber 转换 PDF"""
        try:
            import pdfplumber
            
            markdown_content = []
            
            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    
                    if text:
                        markdown_content.append(f"## 第 {page_num + 1} 页\n\n")
                        # 简单的文本格式化
                        lines = text.split('\n')
                        for line in lines:
                            line = line.strip()
                            if line:
                                markdown_content.append(f"{line}\n\n")
            
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(''.join(markdown_content))
            
            logger.info(f"✓ 使用 pdfplumber 成功转换: {pdf_path.name}")
            return True
        except Exception as e:
            logger.error(f"✗ pdfplumber 转换失败 {pdf_path.name}: {e}")
            return False
    
    def convert_single_pdf(self, pdf_path: Path) -> bool:
        """转换单个 PDF 文件"""
        if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
            logger.error(f"文件不存在或不是 PDF 格式: {pdf_path}")
            return False
        
        # 生成输出文件名
        md_filename = pdf_path.stem + '.md'
        md_path = self.output_dir / md_filename
        
        logger.info(f"开始转换: {pdf_path.name} -> {md_filename}")
        
        # 按优先级尝试不同的转换工具
        conversion_methods = [
            ('markitdown', self._convert_with_markitdown),
            ('pymupdf', self._convert_with_pymupdf),
            ('pdfplumber', self._convert_with_pdfplumber)
        ]
        
        for tool_name, convert_func in conversion_methods:
            if tool_name in self.available_tools:
                if convert_func(pdf_path, md_path):
                    return True
        
        logger.error(f"所有转换方法都失败了: {pdf_path.name}")
        return False
    
    def convert_all_pdfs(self) -> None:
        """转换目录中的所有 PDF 文件"""
        if not self.source_dir.exists():
            logger.error(f"源目录不存在: {self.source_dir}")
            return
        
        # 查找所有 PDF 文件
        pdf_files = list(self.source_dir.glob('*.pdf'))
        
        if not pdf_files:
            logger.warning(f"在 {self.source_dir} 中没有找到 PDF 文件")
            return
        
        logger.info(f"找到 {len(pdf_files)} 个 PDF 文件")
        
        success_count = 0
        failed_files = []
        
        for pdf_file in pdf_files:
            if self.convert_single_pdf(pdf_file):
                success_count += 1
            else:
                failed_files.append(pdf_file.name)
        
        # 输出转换结果统计
        logger.info(f"\n转换完成!")
        logger.info(f"成功转换: {success_count}/{len(pdf_files)} 个文件")
        
        if failed_files:
            logger.warning(f"转换失败的文件: {', '.join(failed_files)}")
        
        logger.info(f"输出目录: {self.output_dir}")

def install_dependencies():
    """安装必要的依赖包"""
    packages = ['markitdown', 'pymupdf', 'pdfplumber']
    
    # 检查是否在虚拟环境中
    venv_path = "/home/ubuntu/Yibao/pdf_converter_venv"
    
    for package in packages:
        try:
            __import__(package.replace('-', '_'))
            logger.info(f"✓ {package} 已安装")
        except ImportError:
            logger.info(f"正在安装 {package}...")
            try:
                # 尝试使用 --user 标志或虚拟环境
                if os.path.exists(venv_path):
                    pip_cmd = [f"{venv_path}/bin/python", '-m', 'pip', 'install', package]
                else:
                    pip_cmd = [sys.executable, '-m', 'pip', 'install', '--user', package]
                
                subprocess.check_call(pip_cmd)
                logger.info(f"✓ {package} 安装成功")
            except subprocess.CalledProcessError as e:
                logger.warning(f"⚠ {package} 安装失败: {e}")
                logger.info("建议手动创建虚拟环境并安装依赖")

def main():
    """主函数"""
    source_directory = "/home/ubuntu/Yibao/医保规则"
    output_directory = "/home/ubuntu/Yibao/医保规则_md"
    
    logger.info("PDF to Markdown 转换器")
    logger.info("=" * 50)
    
    # 检查并安装依赖
    logger.info("检查依赖包...")
    install_dependencies()
    
    # 创建转换器实例
    converter = PDFToMarkdownConverter(source_directory, output_directory)
    
    # 检查是否有可用的转换工具
    if not converter.available_tools:
        logger.error("没有可用的转换工具，请安装 markitdown、pymupdf 或 pdfplumber")
        return
    
    # 开始转换
    converter.convert_all_pdfs()

if __name__ == "__main__":
    main()
