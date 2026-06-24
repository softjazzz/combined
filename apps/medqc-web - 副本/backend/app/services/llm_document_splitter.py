"""
LLM 智能文书切分器

用一次 LLM 调用识别完整病历中的段落边界和文书类型，
替代纯正则切分，兼容任何医院的文书格式。

典型调用成本：~2000 tokens，耗时 3-5 秒。
"""
import json
import logging
import re
from typing import List, Dict, Any, Optional

from .document_segmenter import DocumentSection, classify_section
from .qc_llm_client import SichuanQCLLMClient

logger = logging.getLogger(__name__)

# 所有标准文书类型（与 rule_router.SECTION_TO_RULE_TYPES 对齐）
VALID_SECTION_TYPES = {
    'admission_record', 'first_course_record', 'daily_course_record',
    'senior_course_record', 'rescue_record', 'diffcase_discussion_record',
    'death_discussion', 'handoff_record', 'handover_record',
    'summary_record', 'consultation_record', 'surgery_record',
    'presurg_summary', 'presurg_discussion', 'postsurg_firstcourse_record',
    'surgery_safecheck_record', 'surgery_risk_assessment',
    'anesthesia_record', 'newborn_record', 'bloodtrans_record',
    'nursing_record', 'discharge_record', 'death_record',
    'consent_form', 'exam_item_report', 'labtest_item_report',
    'medical_order', 'transfer_in_record', 'transfer_out_record',
}

# LLM 提示词：让 LLM 识别段落边界
SPLIT_PROMPT = """你是一个医疗病历文档分段专家。请分析以下完整住院病历文本，识别其中包含的所有独立医疗文书段落。

要求：
1. 识别每个文书段落的标题、类型、起始行号和结束行号
2. 行号从 1 开始计数
3. 文书类型必须是以下标准类型之一：
   - admission_record（入院记录）
   - first_course_record（首次病程记录）
   - daily_course_record（日常病程记录、术后病程记录、普通病程记录）
   - senior_course_record（主任/副主任查房记录、上级医师查房记录）
   - surgery_record（手术记录）
   - presurg_discussion（术前讨论记录）
   - presurg_summary（术前小结）
   - postsurg_firstcourse_record（术后首次病程记录）
   - discharge_record（出院记录、出院小结）
   - death_record（死亡记录）
   - death_discussion（死亡讨论）
   - consultation_record（会诊记录）
   - rescue_record（抢救记录）
   - consent_form（知情同意书、谈话记录）
   - anesthesia_record（麻醉记录）
   - nursing_record（护理记录）
   - medical_order（医嘱）
   - summary_record（阶段小结）
   - diffcase_discussion_record（疑难病例讨论）
   - exam_item_report（检查报告）
   - labtest_item_report（检验报告）
4. 跳过非正式文书段落（如费用清单、病案首页基本信息等）
5. 分隔线（如 ====）不属于任何段落内容

请以JSON数组格式返回，每个元素：
{"title": "段落标题", "type": "标准文书类型", "start_line": 起始行号, "end_line": 结束行号}

只返回JSON数组，不要额外文字。"""


async def split_document_by_llm(
    content: str,
    llm_client: Optional[SichuanQCLLMClient] = None,
) -> List[DocumentSection]:
    """
    用 LLM 识别病历段落边界并切分。

    Args:
        content: 完整病历文本
        llm_client: LLM 客户端（可选，默认创建新实例）

    Returns:
        DocumentSection 列表
    """
    if not content or not content.strip():
        return []

    client = llm_client or SichuanQCLLMClient()
    lines = content.split('\n')

    # 构建带行号的文本（让 LLM 能精确定位）
    numbered_text = '\n'.join(f'{i+1}: {line}' for i, line in enumerate(lines))

    # 构建 prompt
    prompt = f"""{SPLIT_PROMPT}

以下是带行号的完整住院病历文本（共 {len(lines)} 行）：

{numbered_text}"""

    logger.info(f"[LLM-Splitter] 开始调用 LLM 切分文档（{len(lines)} 行，{len(content)} 字符）")

    try:
        # 复用已有的 LLM 调用（使用 safe_post_json）
        result = await client.generate(prompt)

        # 提取 LLM 返回内容
        response_text = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )

        if not response_text:
            logger.warning("[LLM-Splitter] LLM 返回空结果，回退到正则切分")
            from .document_segmenter import split_document
            return split_document(content)

        # 解析 JSON
        sections_data = _parse_llm_response(response_text)
        if not sections_data:
            logger.warning("[LLM-Splitter] 解析 LLM JSON 失败，回退到正则切分")
            from .document_segmenter import split_document
            return split_document(content)

        # 转为 DocumentSection 对象
        sections = _build_sections(sections_data, lines)

        logger.info(
            f"[LLM-Splitter] 切分完成: {len(sections)} 个段落 | "
            f"类型: {', '.join(f'{s.section_type}' for s in sections)}"
        )

        return sections

    except Exception as e:
        logger.error(f"[LLM-Splitter] 异常: {e}，回退到正则切分")
        from .document_segmenter import split_document
        return split_document(content)


def _parse_llm_response(text: str) -> Optional[List[Dict[str, Any]]]:
    """解析 LLM 返回的 JSON"""
    # 尝试直接解析
    try:
        data = json.loads(text.strip())
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 中的内容
    m = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1).strip())
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # 尝试找到 JSON 数组
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    logger.warning(f"[LLM-Splitter] 无法解析 JSON: {text[:200]}...")
    return None


def _build_sections(
    sections_data: List[Dict[str, Any]],
    lines: List[str],
) -> List[DocumentSection]:
    """将 LLM 返回的段落信息转为 DocumentSection 对象"""
    sections = []
    total_lines = len(lines)

    for i, item in enumerate(sections_data):
        title = item.get('title', '').strip()
        section_type = item.get('type', '').strip()
        start_line = item.get('start_line', 1)
        end_line = item.get('end_line', total_lines)

        # 校验行号范围
        start_line = max(1, min(start_line, total_lines))
        end_line = max(start_line, min(end_line, total_lines))

        # 校验文书类型
        if section_type not in VALID_SECTION_TYPES:
            # 尝试用正则匹配修正
            corrected = classify_section(title)
            if corrected != 'progress_note':
                section_type = corrected
            else:
                logger.warning(
                    f"[LLM-Splitter] 未知文书类型 '{section_type}'，标题 '{title}'，"
                    f"跳过此段落"
                )
                continue

        # 提取内容（去掉分隔线）
        content_lines = []
        for ln in lines[start_line - 1: end_line]:
            stripped = ln.strip()
            # 跳过纯分隔线
            if re.match(r'^={10,}$', stripped):
                continue
            # 跳过标题行（如 【入院记录】）
            if re.match(r'^【.+?】\s*$', stripped):
                continue
            content_lines.append(ln)

        content = '\n'.join(content_lines).strip()
        if not content:
            continue

        sections.append(DocumentSection(
            section_type=section_type,
            title=title,
            content=content,
            start_line=start_line,
            end_line=end_line,
            timestamp=None,
            char_count=len(content),
        ))

    return sections
