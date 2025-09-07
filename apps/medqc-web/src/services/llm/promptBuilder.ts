/**
 * 提示词构建器 - 负责构建各种LLM提示词
 */

import { ParseOptions } from '@/types/medical'

export class PromptBuilder {
  /**
   * 构建医疗文本解析的主提示词（升级版 - 支持层级化分类）
   */
  static buildMedicalParsePrompt(text: string, options: ParseOptions = {}): string {
    const sections: string[] = []

    // 基础指令 - 升级为层级化分类
    sections.push('你是一个专业的医疗信息抽取和文书分类助手。请从以下病历文本中准确抽取结构化信息，并按照层级化分类体系对医疗文书进行精准分类。')
    sections.push('')
    sections.push('## 层级化文书分类体系：')
    sections.push('')
    sections.push('### 一级分类（7个主要类别）：')
    sections.push('1. **入院记录** (admission_record) - 患者入院时的基本信息和病情记录')
    sections.push('2. **病程记录** (progress_note) - 患者住院期间的病情变化和治疗过程记录')
    sections.push('3. **手术记录** (operation_record) - 手术相关的各类记录文书')
    sections.push('4. **护理文书** (nursing_document) - 护理相关的记录和评估文书')
    sections.push('5. **出院记录** (discharge_record) - 患者出院时的总结和后续指导')
    sections.push('6. **检查报告** (examination_report) - 各类检查和化验报告')
    sections.push('7. **医嘱记录** (medical_order) - 医生开具的各类医嘱记录')
    sections.push('')
    sections.push('### 二级分类（具体文书类型）：')
    sections.push('**入院记录类：** admission_record, admission_diagnosis')
    sections.push('**病程记录类：** first_progress_note, daily_progress_note, attending_progress, consultation_record, handover_record, transfer_record, stage_summary')
    sections.push('**手术记录类：** preoperative_summary, preoperative_discussion, operation_record, postoperative_first_note, anesthesia_record')
    sections.push('**护理文书类：** nursing_record, temperature_chart, nursing_plan, nursing_assessment')
    sections.push('**出院记录类：** discharge_record, discharge_summary, death_record')
    sections.push('**检查报告类：** imaging_examination, laboratory_test, pathology_examination, special_examination')
    sections.push('**医嘱记录类：** long_term_order, temporary_order, order_execution')
    sections.push('')
    sections.push('## 分类要求：')
    sections.push('1. 严格按照JSON格式输出')
    sections.push('2. 如果某个字段无法确定，请设置为null')
    sections.push('3. 为每个抽取的字段提供置信度评分(0-100)')
    sections.push('4. **必须**为每个文书同时提供一级分类(category)和二级分类(type)')
    sections.push('5. 为每个文书提供完整的内容和在原文中的位置标识')
    sections.push('6. 保持文档的层次结构和段落完整性')
    sections.push('7. 特别注意识别护理文书和医嘱记录，这两类文书识别准确率需要重点提升')
    sections.push('')
    sections.push('病历文本：')
    sections.push('```')
    sections.push(text)
    sections.push('```')
    sections.push('')

    // 根据选项添加不同的提取要求
    sections.push('请提取以下信息：')

    if (options.extractPatientInfo !== false) {
      sections.push('1. 患者基本信息（重点提取）：')
      sections.push('   - 病历号/住院号：通常在文档开头或页眉中，格式如"住院号：123456"或"病历号：2024001"')
      sections.push('   - 患者姓名：通常在文档开头，格式如"姓名：张三"或"患者张三"或直接出现在病程记录中')
      sections.push('   - 年龄：格式如"年龄：45岁"或"45岁"或"患者张三，男，45岁"')
      sections.push('   - 性别：格式如"性别：男"或"男性"或"患者张三，男，45岁"')
      sections.push('   - 科室：格式如"科室：内科"或"入院科室：心内科"或在页眉中出现')
      sections.push('')
      sections.push('   提取规则：')
      sections.push('   • 优先从文档开头的"患者基本信息"部分提取')
      sections.push('   • 如果开头没有，从病程记录的首句提取，通常格式为"患者姓名，性别，年龄岁，因...入院"')
      sections.push('   • 科室信息可能在页眉、文档标题或入院记录中')
      sections.push('   • 如果找不到明确信息，设置为null，不要猜测')
    }

    if (options.extractDiagnosisInfo !== false) {
      sections.push('2. 诊断信息：')
      sections.push('   - 主要诊断')
      sections.push('   - 次要诊断（如有）')
    }

    if (options.extractSurgeryInfo !== false) {
      sections.push('3. 手术信息：')
      sections.push('   - 主要手术及操作名称')
    }

    if (options.classifyDocuments) {
      sections.push('4. 文书分类和锚点定位：')
      sections.push('   - 识别并分类文档中包含的所有医疗文书类型')
      sections.push('   - 入院记录、病程记录、手术记录、出院记录等')
      sections.push('   - 不要输出文书的全文内容，只需提供标题、类型、短摘要和用于定位全文的开始/结束标记')
      sections.push('   - 提供文书在原文中的开始和结束标记（startMarker/endMarker）')
    }

    // JSON格式要求 - 增强患者信息提取示例
    sections.push('')
    sections.push('请严格按照以下JSON格式返回：')
    sections.push('```json')
    sections.push('{')
    sections.push('  "recordNumber": "2024001",  // 病历号，如果未找到则为null')
    sections.push('  "patientName": "张伟",      // 患者真实姓名，如果未找到则为null')
    sections.push('  "patientAge": 45,          // 年龄数字，如果未找到则为null')
    sections.push('  "patientGender": "男",     // 性别："男"或"女"，如果未找到则为null')
    sections.push('  "department": "内科",      // 科室名称，如果未找到则为null')
    sections.push('  "primaryDiagnosis": "主要诊断",')
    sections.push('  "secondaryDiagnosis": ["次要诊断1", "次要诊断2"],')
    sections.push('  "majorSurgery": "主要手术名称",')
    sections.push('  "documents": [')
    sections.push('    {')
    sections.push('      "id": "文书ID",')
    sections.push('      "category": "一级分类代码（如：progress_note）",')
    sections.push('      "type": "二级分类代码（如：first_progress_note）",')
    sections.push('      "title": "文书完整标题",')
    sections.push('      "content": "文书完整内容（保持原有段落结构）",')
    sections.push('      "confidence": 0.95,')
    sections.push('      "position": {')
    sections.push('        "startMarker": "文书开始的独特文本片段",')
    sections.push('        "endMarker": "文书结尾的独特文本片段",')
    sections.push('        "startIndex": 开始位置索引,')
    sections.push('        "endIndex": 结束位置索引,')
    sections.push('        "fullContent": "文书的完整原文内容"')
    sections.push('      }')
    sections.push('    }')
    sections.push('  ],')
    sections.push('  "confidence": 0.9')
    sections.push('}')
    sections.push('```')

    // 患者信息提取示例
    sections.push('')
    sections.push('患者信息提取示例：')
    sections.push('示例1 - 结构化格式：')
    sections.push('```')
    sections.push('患者基本信息：')
    sections.push('姓名：张伟')
    sections.push('性别：男')
    sections.push('年龄：45岁')
    sections.push('科室：内科')
    sections.push('```')
    sections.push('提取结果：patientName="张伟", patientGender="男", patientAge=45, department="内科"')
    sections.push('')
    sections.push('示例2 - 病程记录格式：')
    sections.push('```')
    sections.push('患者李明，女，32岁，因"胸痛3天"入院。')
    sections.push('```')
    sections.push('提取结果：patientName="李明", patientGender="女", patientAge=32')
    sections.push('')
    sections.push('## 重要注意事项：')
    sections.push('')
    sections.push('### 基本要求：')
    sections.push('- 患者信息是最重要的提取目标，请仔细查找')
    sections.push('- 如果某项信息无法确定，请设置为null（不是"未识别"字符串）')
    sections.push('- confidence字段表示提取信息的置信度（0-100之间的整数）')
    sections.push('- 请确保返回的是有效的JSON格式')
    sections.push('')
    sections.push('### 分类要求：')
    sections.push('- **必须同时提供category和type字段**，category是一级分类，type是二级分类')
    sections.push('- documents数组中的content字段必须包含完整的文书内容，不是摘要')
    sections.push('- 保持原文的段落结构、换行和格式')
    sections.push('- startMarker和endMarker应该是该文书开始和结尾的独特文本片段')
    sections.push('- 标记文本应该足够独特，避免在其他地方重复出现')
    sections.push('- fullContent字段应包含从startMarker到endMarker的完整原文')
    sections.push('')
    sections.push('### 特殊识别要求：')
    sections.push('- **护理文书**：重点识别护理记录、体温单、护理计划等，通过"护理"、"体温"、"生命体征"等关键词识别')
    sections.push('- **医嘱记录**：重点识别长期医嘱、临时医嘱、医嘱执行记录，通过"医嘱"、"用药"、"执行"等关键词识别')
    sections.push('- **检查报告**：区分影像学检查、实验室检查、病理检查和特殊检查')
    sections.push('- **手术记录**：可能没有明确标题，通过"术前诊断"、"手术过程"、"术后处理"等内容识别')
    sections.push('- **查房记录**：区分主治医师、主任医师查房记录，都归类为attending_progress')

    return sections.join('\n')
  }

  /**
   * 构建文档索引提示词（指针模式专用）- 基于原版精准实现
   */
  static buildDocumentIndexPrompt(text: string): string {
    const system = `你是专业的医疗病历结构化助手。你的唯一任务是从文本中识别出所有独立的医疗文书记录，并提取它们的【确切标题】和【时间戳】。

严格要求：
- 仅输出一个JSON数组，不包含任何解释性文字。
- 数组中的每个对象只包含以下字段：
  - title (字符串): 必须是文书中逐字提取的、完整的标题，例如 "首次病程记录" 或 "孙治庆主治医师查房记录"。对于手术记录，如果没有明确标题但包含"记录时间"、"手术日期"、"术前诊断"等特征，请使用"手术记录"作为标题。
  - timestamp (字符串): 如果标题附近有明确的时间戳 (格式 YYYY-MM-DD HH:MM)，请提取。如果没有，则为 null。
- 不要生成ID、类型、摘要、代码片段(snippet)、行号或任何其他字段。
- 忽略所有页眉和页脚信息。
- 特别注意：手术记录可能没有明确的"手术记录"标题，而是直接以"记录时间：YYYY年MM月DD日"开始，这种情况下应识别为手术记录。`

    const example = `输出格式示例：
[
  { "title": "首次病程记录", "timestamp": "2025-03-30 01:08" },
  { "title": "孙治庆主治医师查房记录", "timestamp": "2025-03-30 08:29" },
  { "title": "CT检查记录", "timestamp": "2025-03-30 10:35" },
  { "title": "术后首次病程记录", "timestamp": "2025-03-31 13:09" }
]`

    const user = `请对以下原始病历文本进行索引，只提取 title 和 timestamp：\n\n${text}`

    return `${system}\n\n${example}\n\n${user}`
  }

  /**
   * 构建文档摘要提示词
   */
  static buildSummaryPrompt(text: string, maxLength: number = 200): string {
    return `请为以下医疗文档生成一个简洁的摘要，长度不超过${maxLength}字：

文档内容：
${text}

要求：
1. 突出关键医疗信息
2. 保持专业术语的准确性
3. 简洁明了，便于快速理解
4. 长度控制在${maxLength}字以内

请直接返回摘要内容，不需要额外的格式或说明。`
  }

  /**
   * 构建指针模式提示词（用于精确定位）
   */
  static buildPointerPrompt(text: string, targetInfo: string): string {
    return `请在以下文本中精确定位"${targetInfo}"相关信息的位置：

文本内容：
${text}

请返回JSON格式的结果：
{
  "found": true/false,
  "startIndex": 起始位置,
  "endIndex": 结束位置,
  "matchedText": "匹配的文本内容",
  "confidence": 置信度
}

要求：
- 如果找到相关信息，请提供精确的字符位置
- 如果有多个匹配，请返回最相关的一个
- 置信度范围0-1，表示匹配的准确性`
  }

  /**
   * 构建批量处理提示词
   */
  static buildBatchPrompt(texts: string[], options: ParseOptions = {}): string {
    const sections: string[] = []

    sections.push('你是一个专业的医疗信息批量处理助手。请处理以下多个病历文本，并为每个文本提取关键信息。')
    sections.push('')

    texts.forEach((text: any,  index: any) => {
      sections.push(`=== 文本 ${index + 1} ===`)
      sections.push(text.substring(0, 500) + (text.length > 500 ? '...' : ''))
      sections.push('')
    })

    sections.push('请为每个文本返回JSON格式的结果数组：')
    sections.push('[')
    sections.push('  {')
    sections.push('    "index": 1,')
    sections.push('    "recordNumber": "病历号",')
    sections.push('    "patientName": "患者姓名",')
    sections.push('    "primaryDiagnosis": "主要诊断",')
    sections.push('    "confidence": 0.9')
    sections.push('  },')
    sections.push('  ...')
    sections.push(']')

    return sections.join('\n')
  }

  /**
   * 构建质量检查提示词
   */
  static buildQualityCheckPrompt(extractedData: any): string {
    return `请检查以下提取的医疗信息的质量和完整性：

提取的数据：
${JSON.stringify(extractedData, null, 2)}

请评估：
1. 信息的完整性（是否缺少关键字段）
2. 信息的准确性（是否存在明显错误）
3. 格式的规范性（是否符合医疗记录标准）

请返回JSON格式的质量报告：
{
  "overallScore": 0.85,
  "completeness": 0.9,
  "accuracy": 0.8,
  "format": 0.9,
  "issues": [
    {
      "field": "字段名",
      "issue": "问题描述",
      "severity": "high/medium/low"
    }
  ],
  "suggestions": [
    "改进建议1",
    "改进建议2"
  ]
}`
  }

  /**
   * 构建错误修复提示词
   */
  static buildErrorFixPrompt(originalText: string, errorData: any, errorDescription: string): string {
    return `原始文本中的信息提取出现了错误，请重新分析并修正：

原始文本：
${originalText}

错误的提取结果：
${JSON.stringify(errorData, null, 2)}

错误描述：
${errorDescription}

请重新提取正确的信息，并以JSON格式返回修正后的结果。特别注意避免之前出现的错误。`
  }

  /**
   * 构建多语言支持提示词
   */
  static buildMultiLanguagePrompt(text: string, targetLanguage: string = 'zh'): string {
    const languageMap: Record<string, string> = {
      'zh': '中文',
      'en': 'English',
      'ja': '日本語'
    }

    const language = languageMap[targetLanguage] || '中文'

    return `请将以下医疗文本翻译并提取信息，结果请用${language}返回：

原始文本：
${text}

要求：
1. 保持医疗术语的准确性
2. 适应目标语言的表达习惯
3. 保留重要的数值和日期信息
4. 以JSON格式返回提取的信息`
  }
}
