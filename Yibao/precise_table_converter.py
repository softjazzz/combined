#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精确的医保规则表格转换器
专门处理您提供的表格格式，确保输出清晰的表格结构
"""

import argparse
import hashlib
import os
import sys
import logging
from pathlib import Path
from typing import Dict, Optional
import re

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


def _configure_logging(log_file: Optional[Path] = None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.insert(0, logging.FileHandler(str(log_file), encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=handlers,
        force=True,
    )

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_safe_md_filename(filename: str) -> bool:
    return bool(
        filename
        and "/" not in filename
        and "\\" not in filename
        and filename not in {".", ".."}
        and filename.endswith(".md")
    )


def _compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest().lower()


class PreciseTableConverter:
    def __init__(
        self,
        source_dir: str,
        output_dir: str,
        manifest_file: Optional[str] = None,
        overwrite: bool = False,
    ):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = Path(manifest_file) if manifest_file else None
        self.overwrite = overwrite

    def _read_manifest_entries(self) -> Dict[str, str]:
        """读取清单中的 `<sha256>\\t<filename>` 映射；旧格式或非法行忽略。"""
        entries: Dict[str, str] = {}
        if self.manifest_file is None or not self.manifest_file.is_file() or self.manifest_file.is_symlink():
            return entries
        try:
            for raw_line in self.manifest_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.rstrip("\r\n")
                if "\t" not in line:
                    continue
                digest, fname = line.split("\t", 1)
                if _SHA256_RE.match(digest) and _is_safe_md_filename(fname):
                    entries[fname] = digest
        except OSError:
            return {}
        return entries

    def _is_unmodified_manifest_entry(self, filename: str, target_path: Path) -> bool:
        """仅当目标文件在清单中登记且当前 SHA-256 与登记摘要一致时，才确认归属本工具且未人工修改。"""
        if self.manifest_file is None or not _is_safe_md_filename(filename):
            return False
        if not target_path.is_file() or target_path.is_symlink():
            return False
        recorded = self._read_manifest_entries().get(filename)
        if not recorded:
            return False
        try:
            return _compute_sha256(target_path) == recorded
        except OSError:
            return False

    def _record_generated_file(self, filename: str, digest: str) -> None:
        """将本次成功生成的 Markdown 文件及其 SHA-256 摘要登记到清单，供安全清理核对。"""
        if self.manifest_file is None:
            return
        if not _is_safe_md_filename(filename) or not _SHA256_RE.match(digest):
            return
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        entries = self._read_manifest_entries()
        entries[filename] = digest
        tmp_manifest = self.manifest_file.parent / f".{self.manifest_file.name}.tmp.{os.getpid()}"
        with open(tmp_manifest, "w", encoding="utf-8", newline="\n") as mf:
            for fname, sha in entries.items():
                mf.write(f"{sha}\t{fname}\n")
        os.replace(tmp_manifest, self.manifest_file)
    
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

        if (md_path.exists() or md_path.is_symlink()) and not self.overwrite:
            if not self._is_unmodified_manifest_entry(md_filename, md_path):
                logger.warning(f"⚠ 跳过已存在且归属无法确认或已被修改的目标文件: {md_path}")
                return False

        logger.info(f"开始转换: {pdf_path.name} -> {md_filename}")
        
        tmp_path = self.output_dir / f".{md_filename}.tmp.{os.getpid()}"
        try:
            content = self._extract_clean_tables(pdf_path)
            
            if content:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                digest = _compute_sha256(tmp_path)
                os.replace(tmp_path, md_path)
                self._record_generated_file(md_filename, digest)
                logger.info(f"✓ 转换成功: {pdf_path.name}")
                return True
            else:
                logger.error(f"✗ 转换失败: {pdf_path.name}")
                return False
                
        except Exception as e:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
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
    parser = argparse.ArgumentParser(description="精确医保规则表格转换器")
    parser.add_argument(
        "--source-dir",
        default=os.environ.get("PDF_SOURCE_DIR", str(BASE_DIR / "医保规则")),
        help="PDF 源目录",
    )
    parser.add_argument(
        "--output-dir",
        default=os.environ.get("PDF_PRECISE_OUTPUT_DIR", str(BASE_DIR / "医保规则_precise")),
        help="Markdown 输出目录",
    )
    parser.add_argument(
        "--log-file",
        default=os.environ.get("PDF_LOG_FILE", str(BASE_DIR / "precise_conversion.log")),
        help="日志文件路径",
    )
    parser.add_argument(
        "--manifest-file",
        default=None,
        help="记录本次成功生成的 Markdown 文件及摘要的清单路径",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="允许覆盖已存在且归属无法确认的目标文件（默认跳过保护）",
    )
    args = parser.parse_args()
    _configure_logging(Path(args.log_file) if args.log_file else None)

    logger.info("精确医保规则表格转换器")
    logger.info("=" * 50)

    converter = PreciseTableConverter(
        args.source_dir,
        args.output_dir,
        manifest_file=args.manifest_file,
        overwrite=args.overwrite,
    )
    converter.convert_all_pdfs()

if __name__ == "__main__":
    main()
