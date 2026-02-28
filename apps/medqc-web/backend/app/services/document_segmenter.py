"""
病历文档段落切割器

纯正则实现，零 LLM 调用。
将一份完整住院病历按时间戳+标题行自动切分为多个段落，
并映射到标准文书类型。
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentSection:
    """切割后的单个病历段落"""
    section_type: str          # 标准文书类型 (如 progress_note, operation_record)
    title: str                 # 段落标题 (如 "主治医师查房记录")
    content: str               # 段落全文
    start_line: int            # 起始行号 (1-indexed)
    end_line: int              # 结束行号 (1-indexed)
    timestamp: Optional[str] = None   # 时间戳 (如 "2025-03-31 08:45")
    char_count: int = 0        # 字符数


# ======================================================================
# 标题关键词 → 标准文书类型 映射表
# 优先级：从上到下，先匹配到的为准
# ======================================================================
SECTION_TYPE_RULES = [
    # 手术/麻醉相关
    (r'手术记录',              'operation_record'),
    (r'术后首次病程',          'operation_record'),      # 术后首程归入手术类
    (r'麻醉',                  'anesthesia_record'),

    # 术前相关 (细粒度类型, 便于精准路由规则)
    (r'术前讨论',              'preop_discussion'),
    (r'术前小结',              'preop_summary'),

    # 入院/出院
    (r'入院记录',              'admission_record'),
    (r'首次病程记录',          'admission_record'),      # 首次病程归入入院类
    (r'出院记录|出院小结',     'discharge_record'),
    (r'死亡记录|死亡讨论',     'discharge_record'),

    # 查房/病程
    (r'主任医师查房|副主任医师查房', 'progress_note'),
    (r'主治医师查房',          'progress_note'),
    (r'查房记录',              'progress_note'),
    (r'日常病程',              'progress_note'),
    (r'阶段小结',              'progress_note'),
    (r'转科记录|交接班',       'progress_note'),
    (r'抢救记录',              'progress_note'),
    (r'病危通知',              'progress_note'),

    # 会诊
    (r'会诊',                  'consultation_record'),

    # 检查/检验
    (r'CT检查|MRI|核磁|影像',  'examination_report'),
    (r'检查记录|检验',         'examination_report'),
    (r'病理',                  'examination_report'),

    # 医嘱
    (r'医嘱|长期医嘱|临时医嘱', 'medical_order'),

    # 知情同意
    (r'知情同意|手术同意|谈话记录', 'consent_form'),

    # 输血
    (r'输血',                  'transfusion_record'),
]

# 段落分隔行的正则模式
# 匹配格式: "2025-03-30 08:29 孙治庆主治医师查房记录"
# 或者: "首次病程记录" (无时间戳)
SECTION_HEADER_PATTERN = re.compile(
    r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(.+)$'  # 有时间戳
)

# 无时间戳但有标题关键词的行
TITLE_ONLY_PATTERN = re.compile(
    r'^(首次病程记录|入院记录|出院记录|手术记录|术前小结|术前讨论记录|'
    r'术后首次病程记录|日常病程记录|查房记录|会诊记录|'
    r'抢救记录|死亡记录|死亡讨论|阶段小结|转科记录|'
    r'麻醉记录|病理报告|知情同意书)\s*$'
)

# 跳过的"噪声"行 (页眉页脚)
NOISE_PATTERN = re.compile(
    r'^(泸县人民医院|病\s*程\s*记\s*录|手\s*术\s*记\s*录|'
    r'科室：|第\(\d+\)页)'
)


def classify_section(title: str) -> str:
    """根据标题关键词判断文书类型"""
    for pattern, section_type in SECTION_TYPE_RULES:
        if re.search(pattern, title):
            return section_type
    return 'progress_note'  # 兜底


def split_document(text: str) -> List[DocumentSection]:
    """
    将完整病历文本切分为段落列表。

    Args:
        text: 完整的病历文本

    Returns:
        DocumentSection 列表，按出现顺序排列
    """
    lines = text.split('\n')
    sections: List[DocumentSection] = []

    current_title = ""
    current_timestamp = None
    current_start = 1
    current_lines: List[str] = []

    def flush_section():
        """将当前累积的行保存为一个段落"""
        nonlocal current_title, current_timestamp, current_start, current_lines

        if not current_lines:
            return

        # 过滤掉纯噪声行
        content_lines = [
            ln for ln in current_lines
            if ln.strip() and not NOISE_PATTERN.match(ln.strip())
        ]

        if not content_lines:
            current_lines = []
            return

        content = '\n'.join(content_lines)
        title = current_title or content_lines[0][:30]
        section_type = classify_section(title)
        end_line = current_start + len(current_lines) - 1

        sections.append(DocumentSection(
            section_type=section_type,
            title=title.strip(),
            content=content.strip(),
            start_line=current_start,
            end_line=end_line,
            timestamp=current_timestamp,
            char_count=len(content),
        ))

        current_lines = []

    for i, raw_line in enumerate(lines):
        line = raw_line.rstrip('\r')
        line_no = i + 1

        # 跳过页眉页脚噪声
        if NOISE_PATTERN.match(line.strip()):
            current_lines.append(line)
            continue

        # 检查是否是段落分隔行 (有时间戳)
        m = SECTION_HEADER_PATTERN.match(line.strip())
        if m:
            flush_section()
            current_timestamp = m.group(1)
            current_title = m.group(2).strip()
            current_start = line_no
            current_lines = [line]
            continue

        # 检查是否是无时间戳的标题行
        m2 = TITLE_ONLY_PATTERN.match(line.strip())
        if m2:
            flush_section()
            current_title = m2.group(1).strip()
            current_timestamp = None
            current_start = line_no
            current_lines = [line]

            # 如果下一行是时间戳，把它也吃进来
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                ts_match = re.match(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s*$', next_line)
                if ts_match:
                    current_timestamp = ts_match.group(1)
            continue

        # 普通内容行
        current_lines.append(line)

    # 最后一个段落
    flush_section()

    logger.info(
        f"病历切割完成: {len(sections)} 个段落, "
        f"类型分布: {_type_summary(sections)}"
    )
    return sections


def _type_summary(sections: List[DocumentSection]) -> str:
    """生成类型分布的简要描述"""
    from collections import Counter
    c = Counter(s.section_type for s in sections)
    return ', '.join(f'{t}:{n}' for t, n in c.most_common())


def merge_small_sections(
    sections: List[DocumentSection],
    min_chars: int = 100
) -> List[DocumentSection]:
    """
    将过短的段落合并到相邻段落。

    Args:
        sections: 原始段落列表
        min_chars: 最小字符数阈值

    Returns:
        合并后的段落列表
    """
    if not sections:
        return sections

    merged: List[DocumentSection] = []
    for sec in sections:
        if sec.char_count < min_chars and merged:
            # 合并到上一个段落
            prev = merged[-1]
            merged[-1] = DocumentSection(
                section_type=prev.section_type,
                title=prev.title,
                content=prev.content + '\n\n' + sec.content,
                start_line=prev.start_line,
                end_line=sec.end_line,
                timestamp=prev.timestamp,
                char_count=prev.char_count + sec.char_count,
            )
        else:
            merged.append(sec)

    return merged
