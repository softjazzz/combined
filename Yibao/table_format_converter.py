#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专门处理医保规则表格格式的PDF转换器
针对您提供的表格格式进行优化
"""

import os
import sys
import logging
from pathlib import Path
import re
import pandas as pd

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/Yibao/table_conversion.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class TableFormatConverter:
    def __init__(self, source_dir: str, output_dir: str):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.venv_path = "/home/ubuntu/Yibao/pdf_converter_venv"
    
    def _extract_and_restructure_tables(self, pdf_path: Path) -> str:
        """提取PDF并重构为清晰的表格格式"""
        try:
            import pdfplumber
            
            markdown_content = []
            markdown_content.append(f"# {pdf_path.stem}\n\n")
            
            with pdfplumber.open(str(pdf_path)) as pdf:
                all_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        all_text += page_text + "\n"
                
                # 解析文本并重构表格
                structured_content = self._parse_medical_insurance_table(all_text)
                markdown_content.append(structured_content)
            
            return ''.join(markdown_content)
            
        except Exception as e:
            logger.error(f"表格重构失败: {e}")
            return ""
    
    def _parse_medical_insurance_table(self, text: str) -> str:
        """解析医保规则表格文本"""
        lines = text.split('\n')
        
        # 查找表格标题
        title_pattern = r'第[一二三四五六七八九十]+批.*规则对应知识点明细'
        title = ""
        for line in lines:
            if re.search(title_pattern, line.strip()):
                title = line.strip()
                break
        
        if not title:
            title = "医保规则对应知识点明细"
        
        markdown_content = [f"## {title}\n\n"]
        
        # 定义表格结构
        table_data = []
        current_row = {}
        
        # 解析文本内容
        序号_pattern = r'^(\d+)\s+'
        项目名称_pattern = r'^[^0-9\s].*(?:术|检查|治疗|切除|修补|成形|吻合|探查|引流|栓塞|移植|根治|扩张|缝合|固定|切开|造瘘|悬吊|结扎|松解|剔除|重建|修复|成型|取石|取出|置入|置放|转流|分流|断流|搭桥|清扫|清除|摘除|切断|复位|矫治|再造|代替|联合|扩大|姑息|全切|部分|局部|经|开腹|腹腔镜|内镜|显微|介入|穿刺|活检|造影|监测|测定|评估|诊断|筛查|随访).*'
        检出逻辑_pattern = r'经同一切口进行的两种及以上不同的手术.*'
        逻辑依据_pattern = r'(胃肠手术组|直肠肛门手术组|经腹直肠手术组|肝胆手术组|膀胱尿道手术组|男性生殖系统手术组|女性生殖系统手术组)'
        项目代码_pattern = r'(\d{15})'
        备注_pattern = r'各省依据国家项目代码.*'
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                i += 1
                continue
            
            # 检查是否是序号行
            序号_match = re.match(序号_pattern, line)
            if 序号_match:
                # 保存之前的行（如果有）
                if current_row:
                    table_data.append(current_row.copy())
                
                # 开始新行
                current_row = {
                    '序号': 序号_match.group(1),
                    '医疗服务项目名称': '',
                    '检出逻辑': '',
                    '逻辑依据（同切口组别名称）': '',
                    '项目代码供参考（国家医保局全国医疗服务项目）': '',
                    '备注': ''
                }
                
                # 提取项目名称（可能在同一行或下一行）
                remaining_text = line[len(序号_match.group(0)):].strip()
                if remaining_text:
                    current_row['医疗服务项目名称'] = remaining_text
            
            # 检查项目名称
            elif re.match(项目名称_pattern, line) and current_row:
                if not current_row['医疗服务项目名称']:
                    current_row['医疗服务项目名称'] = line
                elif '(' in line or '（' in line:
                    # 可能是项目名称的补充说明
                    current_row['医疗服务项目名称'] += ' ' + line
            
            # 检查检出逻辑
            elif re.search(检出逻辑_pattern, line) and current_row:
                current_row['检出逻辑'] = '经同一切口进行的两种及以上不同的手术，第二及以后的手术未按规定折价计收'
            
            # 检查逻辑依据
            elif re.search(逻辑依据_pattern, line) and current_row:
                match = re.search(逻辑依据_pattern, line)
                if match:
                    current_row['逻辑依据（同切口组别名称）'] = match.group(1)
            
            # 检查项目代码
            elif re.search(项目代码_pattern, line) and current_row:
                match = re.search(项目代码_pattern, line)
                if match:
                    current_row['项目代码供参考（国家医保局全国医疗服务项目）'] = match.group(1)
            
            # 检查备注
            elif re.search(备注_pattern, line) and current_row:
                current_row['备注'] = '各省依据国家项目代码，配置规则知识点中各省项目代码'
            
            i += 1
        
        # 添加最后一行
        if current_row:
            table_data.append(current_row)
        
        # 生成Markdown表格
        if table_data:
            df = pd.DataFrame(table_data)
            
            # 确保所有列都存在
            required_columns = [
                '序号',
                '医疗服务项目名称', 
                '检出逻辑',
                '逻辑依据（同切口组别名称）',
                '项目代码供参考（国家医保局全国医疗服务项目）',
                '备注'
            ]
            
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # 重新排序列
            df = df[required_columns]
            
            # 清理数据
            df = df.fillna('')
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip()
            
            # 转换为Markdown表格
            markdown_table = df.to_markdown(index=False, tablefmt='pipe')
            markdown_content.append(markdown_table + "\n\n")
            
            # 添加统计信息
            markdown_content.append(f"**统计信息：**\n")
            markdown_content.append(f"- 总计项目数量：{len(df)} 项\n")
            markdown_content.append(f"- 涉及手术组别：{df['逻辑依据（同切口组别名称）'].nunique()} 个\n\n")
        
        return ''.join(markdown_content)
    
    def convert_single_pdf(self, pdf_path: Path) -> bool:
        """转换单个PDF文件"""
        if not pdf_path.exists() or pdf_path.suffix.lower() != '.pdf':
            logger.error(f"文件不存在或不是PDF格式: {pdf_path}")
            return False
        
        md_filename = pdf_path.stem + '_table_format.md'
        md_path = self.output_dir / md_filename
        
        logger.info(f"开始转换: {pdf_path.name} -> {md_filename}")
        
        try:
            content = self._extract_and_restructure_tables(pdf_path)
            
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
    output_directory = "/home/ubuntu/Yibao/医保规则_table_format"
    
    logger.info("医保规则表格格式转换器")
    logger.info("=" * 50)
    
    converter = TableFormatConverter(source_directory, output_directory)
    converter.convert_all_pdfs()

if __name__ == "__main__":
    main()
