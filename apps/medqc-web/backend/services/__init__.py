"""
医疗质控系统后端服务模块
"""

from .pdf_parser import PDFParser, parse_pdf_file

__all__ = ['PDFParser', 'parse_pdf_file']



