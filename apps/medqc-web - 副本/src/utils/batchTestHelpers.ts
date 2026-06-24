/**
 * 批量质控测试辅助工具
 */

/**
 * 预置的入院记录病历文本（用于批量测试）
 * 基于 LX-008 正例的完整入院记录
 */
export const PRESET_ADMISSION_RECORD = `患者信息：张伟，男，44岁，入院科室：呼吸与危重症医学科，病区：呼吸内一科。

主诉：体检发现肺部结节1周。

现病史：患者1周前单位组织体检，行胸部CT发现右肺下叶磨玻璃结节，直径约1.8cm，边界清晰。患者无咳嗽、咳痰、咯血、胸痛、气促等不适。为进一步诊治来我院就诊，门诊完善相关检查后以'右肺占位性病变'收入院。

既往史：既往体健。否认高血压、糖尿病病史。否认肝炎、结核病史。否认手术史、外伤史、输血史。否认食物、药物过敏史。

体格检查：T 36.5℃，P 72次/分，R 18次/分，BP 125/78 mmHg。神志清楚，精神可，自主体位，查体合作。全身皮肤黏膜无黄染，浅表淋巴结未触及肿大。双肺呼吸音清，未闻及干湿啰音。心律齐，各瓣膜听诊区未闻及杂音。腹部平软，无压痛，肝脾肋下未触及。双下肢无水肿。

辅助检查：
1. 血常规：WBC 8.6×10⁹/L，N 72%，Hb 135g/L，PLT 210×10⁹/L
2. 肝功能：ALT 38U/L，AST 42U/L，TBIL 16μmol/L，ALB 41g/L
3. 肾功能：Cr 78μmol/L，BUN 5.2mmol/L
4. 心电图：窦性心律，大致正常心电图
5. 胸部CT平扫（2024-10-25，外院）：右肺下叶见直径约1.8cm磨玻璃结节，边界清晰，无毛刺征，未见明显淋巴结肿大
6. 腹部超声：肝胆胰脾未见明显异常，双肾未见结石及积水
7. 空腹血糖：5.9mmol/L
8. 凝血功能：PT 12.3s，APTT 31.5s，FIB 3.8g/L

入院诊断：右肺占位性病变`

/**
 * 筛选适用于入院记录的质控规则
 * @param rules 所有质控规则
 * @returns 适用于入院记录的质控规则列表
 */
export function filterAdmissionRecordRules(rules: any[]): any[] {
  return rules
    .filter(rule => {
      const applicableDocs = rule.applicable_documents || []
      const id = String(rule.rule_id || rule.rule_code || '').toUpperCase()
      // 仅批量质控 LX 系列规则，暂不包含 LXE 扩展规则
      const isLxSeries = id.startsWith('LX-') && !id.startsWith('LXE-')
      return isLxSeries && (applicableDocs.includes('admission_record') || applicableDocs.includes('入院记录'))
    })
    .sort((a, b) => {
      const idA = String(a.rule_id || '')
      const idB = String(b.rule_id || '')
      return idA.localeCompare(idB, 'zh-Hans-CN', { numeric: true })
    })
}

/**
 * 批量测试结果接口
 */
export interface BatchTestResult {
  ruleId: string
  ruleName: string
  isCompliant: boolean
  status?: 'compliant' | 'non_compliant' | 'not_applicable' | 'uncertain' | 'error'
  findings?: string
  issues: Array<{
    description: string
    evidence?: string
  }>
  applicability?: {
    is_applicable: boolean
    reason?: string
    method?: string
  }
  notApplicable?: boolean
  notApplicableReason?: string
  evidence?: string
  suggestion?: string
  evidenceVerified?: boolean
  confidence: number
  error?: string
  llmRawOutput?: string
  metadata?: Record<string, any>
}

/**
 * 批量测试进度信息
 */
export interface BatchTestProgress {
  total: number
  completed: number
  currentRuleId?: string
  currentRuleName?: string
}

/**
 * 预置的病程记录病历文本（用于批量测试）
 * 基于 LX-011 正例的完整首次病程记录
 */
export const PRESET_COURSE_RECORD = `首次病程记录

病例特点：
1. 患者为中老年男性，58岁；
2. 主诉：反复胸闷、气促3年，加重伴晕厥1天；
3. 现病史：患者3年前无明显诱因出现活动后胸闷、气促，休息后可缓解。近1年来症状逐渐加重，活动耐量明显下降。1天前晨起时突发晕厥，持续约1分钟后自行恢复，伴出汗、心悸。就诊于我院急诊，查心电图示完全性左束支传导阻滞，心肌酶谱升高，为进一步诊治收入我科；
4. 既往史：高血压病史10年，最高血压180/110mmHg，规律服用降压药物，血压控制尚可；2型糖尿病病史5年，口服降糖药治疗，血糖控制一般；
5. 体格检查：T 36.8℃，P 88次/分，R 20次/分，BP 145/90mmHg。神志清楚，精神一般。双肺呼吸音粗，双肺底可闻及少许湿性啰音。心界向左下扩大，心率88次/分，律齐，心尖部可闻及3/6级收缩期吹风样杂音。双下肢轻度水肿；
6. 辅助检查：
   - 心电图：窦性心律，完全性左束支传导阻滞，ST-T改变；
   - 心肌酶谱：肌钙蛋白I 0.85ng/ml（正常<0.04），肌酸激酶同工酶58U/L（正常<25）；
   - 胸片：心影增大，双肺纹理增多，肺淤血征象；
   - 超声心动图：左室扩大（LVEDd 65mm），左室射血分数35%，二尖瓣中度反流；
   - 实验室检查：BNP 1250pg/ml（正常<100），血糖8.5mmol/L，肾功能正常。

初步诊断：
1. 冠心病 急性非ST段抬高型心肌梗死
2. 心功能不全 心功能Ⅲ级（NYHA分级）
3. 高血压病 3级 极高危
4. 2型糖尿病

诊断依据：
1. 中老年男性，有高血压、糖尿病等冠心病危险因素；
2. 反复胸闷、气促3年，加重伴晕厥1天，符合急性冠脉综合征临床表现；
3. 心电图示完全性左束支传导阻滞，ST-T改变；
4. 心肌酶谱明显升高：肌钙蛋白I 0.85ng/ml，肌酸激酶同工酶58U/L；
5. BNP明显升高（1250pg/ml），提示心功能不全；
6. 超声心动图示左室扩大、射血分数降低（35%），二尖瓣反流；
7. 体格检查示心界扩大，双肺底湿啰音，双下肢水肿，符合心功能不全表现。

鉴别诊断：
1. 扩张型心肌病：需进一步完善冠脉造影明确冠脉情况；
2. 肺栓塞：患者胸闷、气促症状明显，但D-二聚体正常，胸片未见明显异常；
3. 主动脉夹层：患者有高血压病史，但无典型撕裂样疼痛，胸片未见纵隔增宽。

诊疗计划：
1. 冠心病监护病房（CCU）监护，心电监护、吸氧；
2. 抗血小板聚集：阿司匹林100mg qd，氯吡格雷75mg qd；
3. 抗凝治疗：低分子肝素钙5000U q12h 皮下注射；
4. 改善心肌代谢：曲美他嗪20mg tid；
5. 强心利尿：呋塞米20mg qd，螺内酯20mg qd；
6. 降压治疗：继续原降压方案；
7. 控制血糖：调整降糖方案；
8. 完善冠脉造影检查，明确冠脉病变情况，必要时行PCI治疗；
9. 监测心肌酶谱、肾功能、电解质等；
10. 一级护理，低盐低脂糖尿病饮食。

医师签名：张医生
日期：2025-10-31`

/**
 * 预置的手术记录病历文本（用于批量测试）
 */
export const PRESET_OPERATION_RECORD = `手术记录

手术日期：2025-10-20  09:30-11:20
术前诊断：急性化脓性阑尾炎
术后诊断：急性化脓性阑尾炎伴局限性腹膜炎
手术名称：腹腔镜阑尾切除术
手术者：李主任医师
第一助手：王医师
第二助手：张医师
器械护士：刘护士
巡回护士：陈护士
麻醉方式：气管插管全身麻醉
麻醉医师：赵医师

手术经过：
患者入室后取平卧位，常规消毒铺巾，麻醉满意后开始手术。于脐下缘作1cm纵行切口，建立气腹，腹腔内压力维持在12-14mmHg。置入腹腔镜探查，见腹腔内少量浑浊渗液约50ml，阑尾肿胀充血，表面有脓性渗出物附着，局部腹膜充血水肿。于右下腹麦氏点及左下腹各作0.5cm穿刺孔，置入操作器械。

分离阑尾周围粘连，显露阑尾根部，结扎阑尾动脉，荷包缝合阑尾根部浆肌层，距阑尾根部约1cm处套扎阑尾，阑尾根部远端予以电凝离断，荷包缝合内翻残端。标本装入标本袋取出送病理检查。吸净腹腔渗液，彻底冲洗腹腔，放置引流管一根至盆腔，引流通畅。再次检查无活动性出血，逐层关闭切口。

术中出血：约30ml
输血：无
输液：乳酸林格液1000ml，0.9%氯化钠注射液500ml
标本：阑尾一条，长约8cm，直径约1.5cm，表面充血水肿，切面见脓性物
术中冰冻病理：（待补充）

术后处理：
1. 禁食水，胃肠减压
2. 抗感染治疗：头孢哌酮舒巴坦3.0g q12h ivgtt + 甲硝唑0.5g q12h ivgtt
3. 补液支持治疗
4. 镇痛治疗：地佐辛5mg im sos
5. 观察生命体征、腹部体征及引流液性状
6. 术后24-48小时拔除引流管

手术者签名：李主任医师
助手签名：王医师  张医师
日期：2025-10-20`

/**
 * 预置的出院记录病历文本（用于批量测试）
 */
export const PRESET_DISCHARGE_SUMMARY = `出院记录

姓名：张三
性别：男
年龄：58岁
住院号：2025100123
入院日期：2025-10-01
出院日期：2025-10-15
出院医嘱下达时间：2025-10-15 10:00
住院天数：14天

病案首页诊断：
1. 冠心病 急性非ST段抬高型心肌梗死
   冠状动脉粥样硬化性心脏病
   经皮冠状动脉介入治疗术后（前降支支架植入术后）
2. 心功能不全 心功能Ⅱ级（NYHA分级）
3. 高血压病 3级 极高危
4. 2型糖尿病
5. 高脂血症

入院诊断：
1. 冠心病 急性非ST段抬高型心肌梗死
2. 心功能不全 心功能Ⅲ级（NYHA分级）
3. 高血压病 3级 极高危
4. 2型糖尿病

出院诊断：
1. 冠心病 急性非ST段抬高型心肌梗死
   冠状动脉粥样硬化性心脏病
   经皮冠状动脉介入治疗术后（前降支支架植入术后）
2. 心功能不全 心功能Ⅱ级（NYHA分级）
3. 高血压病 3级 极高危
4. 2型糖尿病

入院情况：
患者因"反复胸闷、气促3年，加重伴晕厥1天"于2025-10-01入院。入院时神志清楚，精神一般，诉胸闷、气促明显，活动后加重，伴心悸、出汗。查体：T 36.8℃，P 88次/分，R 20次/分，BP 145/90mmHg。双肺底可闻及少许湿性啰音，心界向左下扩大，心尖部可闻及3/6级收缩期吹风样杂音，双下肢轻度水肿。心电图示完全性左束支传导阻滞，心肌酶谱升高，BNP 1250pg/ml，超声心动图示左室扩大、射血分数35%。

诊疗经过：
入院后完善相关检查，明确诊断为急性非ST段抬高型心肌梗死、心功能不全。予以CCU监护，心电监护、吸氧，给予抗血小板聚集、抗凝、改善心肌代谢、强心利尿、降压、控制血糖等治疗。入院第3天行冠状动脉造影检查，示前降支近段95%狭窄，回旋支远段50%狭窄，右冠状动脉未见明显狭窄。行前降支病变处支架植入术（药物洗脱支架1枚，规格3.0×23mm），术后造影示血流通畅，TIMI 3级。术后继续抗血小板、抗凝、强心利尿等治疗。患者病情逐渐好转，胸闷、气促症状明显缓解，双下肢水肿消退，复查心肌酶谱降至正常，BNP下降至450pg/ml，超声心动图复查示左室射血分数改善至45%。病情稳定，今日出院。

出院情况：
患者一般情况良好，无胸闷、气促，活动耐量较前明显改善。查体：T 36.5℃，P 72次/分，R 18次/分，BP 130/80mmHg。神志清楚，精神可，双肺呼吸音清，未闻及干湿啰音，心律齐，心尖部可闻及2/6级收缩期杂音，双下肢无水肿。

出院医嘱：
1. 休息：出院后注意休息，避免剧烈活动，可适当进行康复锻炼
2. 饮食：低盐低脂糖尿病饮食，控制总热量摄入
3. 药物治疗：
   - 阿司匹林肠溶片 100mg qd 口服（餐后服用）
   - 替格瑞洛片 90mg bid 口服（服用至少12个月）
   - 阿托伐他汀钙片 20mg qn 口服
   - 美托洛尔缓释片 47.5mg qd 口服
   - 培哚普利片 4mg qd 口服
   - 螺内酯片 20mg qd 口服
   - 二甲双胍片 0.5g tid 口服
4. 复查：出院后1周、1个月、3个月门诊复查，监测血压、血糖、血脂、肝肾功能、心肌酶谱等
5. 注意事项：
   - 规律服药，不可自行停药或调整剂量
   - 监测血压、血糖，如有异常及时就诊
   - 如出现胸痛、胸闷、气促加重等不适，立即就诊
   - 戒烟限酒，保持心情舒畅
   - 预防感冒，避免感染

出院带药：
阿司匹林肠溶片、替格瑞洛片、阿托伐他汀钙片、美托洛尔缓释片、培哚普利片、螺内酯片、二甲双胍片（各带1个月用量）

医师签名：李医生
完成时间：2025-10-17 14:30`

/**
 * 病历类型配置接口
 */
export interface DocumentTypeConfig {
  key: string                    // 类型标识，如 'admission_record'
  label: string                  // 显示名称，如 '入院记录'
  icon: string                   // 图标标识
  tagColor: string               // 标签颜色
  presetText: string            // 预置病历文本
  ruleCount?: number            // 相关质控点数量（动态计算）
  description?: string          // 类型描述
}

/**
 * 病历类型配置数组
 */
export const DOCUMENT_TYPE_CONFIGS: DocumentTypeConfig[] = [
  {
    key: 'admission_record',
    label: '入院记录',
    icon: 'admission',
    tagColor: 'blue',
    presetText: PRESET_ADMISSION_RECORD,
    description: '患者入院时的完整记录，包含主诉、现病史、既往史、体格检查、辅助检查、入院诊断'
  },
  {
    key: 'course_record',
    label: '病程记录',
    icon: 'course',
    tagColor: 'green',
    presetText: PRESET_COURSE_RECORD,
    description: '住院期间的首次病程记录，包含病例特点、初步诊断、诊断依据、鉴别诊断、诊疗计划'
  },
  {
    key: 'operation_record',
    label: '手术记录',
    icon: 'operation',
    tagColor: 'orange',
    presetText: PRESET_OPERATION_RECORD,
    description: '手术过程的详细记录，包含术前诊断、手术经过、术中情况、术后处理'
  },
  {
    key: 'discharge_summary',
    label: '出院记录',
    icon: 'discharge',
    tagColor: 'purple',
    presetText: PRESET_DISCHARGE_SUMMARY,
    description: '患者出院时的总结记录，包含入出院诊断、诊疗经过、出院情况、出院医嘱'
  }
]

export type RuleSeries = 'lx' | 'lxe' | 'all'

/**
 * 根据病历类型筛选质控规则（通用版本）
 * @param rules 所有质控规则
 * @param documentType 病历类型标识
 * @param series 规则系列：'lx'（默认，仅 LX- 主规则）、'lxe'（仅 LXE- 扩展规则）、'all'（两者都包含）
 * @returns 筛选后的质控规则列表
 */
export function filterRulesByDocumentType(
  rules: any[],
  documentType: string,
  series: RuleSeries = 'lx'
): any[] {
  return rules
    .filter(rule => {
      const applicableDocs = rule.applicable_documents || []
      const id = String(rule.rule_id || rule.rule_code || '').toUpperCase()

      let inSeries = true
      if (series === 'lx') {
        // 批量质控仅包含 LX 主规则，排除 LXE 扩展规则
        inSeries = id.startsWith('LX-') && !id.startsWith('LXE-')
      } else if (series === 'lxe') {
        inSeries = id.startsWith('LXE-')
      } else if (series === 'all') {
        inSeries = id.startsWith('LX-') || id.startsWith('LXE-')
      }
      if (!inSeries) return false

      return applicableDocs.includes(documentType)
    })
    .sort((a, b) => {
      const idA = String(a.rule_id || '')
      const idB = String(b.rule_id || '')
      return idA.localeCompare(idB, 'zh-Hans-CN', { numeric: true })
    })
}

/**
 * 质控规则分组类别配置
 */
export interface RuleCategory {
  key: string
  label: string
  icon: string
  description: string
  order: number
}

/**
 * 质控规则分组类别
 */
export const RULE_CATEGORIES: RuleCategory[] = [
  {
    key: 'basic_info',
    label: '基础信息',
    icon: '📋',
    description: '主诉、现病史、既往史等基础信息规范',
    order: 1
  },
  {
    key: 'auxiliary_exam',
    label: '辅助检查',
    icon: '🔬',
    description: '检验检查结果记录规范',
    order: 2
  },
  {
    key: 'course_record',
    label: '病程记录',
    icon: '📝',
    description: '病程记录与诊疗过程规范',
    order: 3
  },
  {
    key: 'operation',
    label: '手术记录',
    icon: '⚕️',
    description: '手术相关记录规范',
    order: 4
  },
  {
    key: 'discharge',
    label: '出院记录',
    icon: '🏥',
    description: '出院记录与医嘱规范',
    order: 5
  },
  {
    key: 'other',
    label: '其他',
    icon: '📌',
    description: '其他质控要求',
    order: 99
  }
]

/**
 * 根据规则 ID 和名称自动检测规则所属分类
 */
export function detectRuleCategory(rule: any): string {
  const ruleId = String(rule.rule_id || '').toLowerCase()
  const ruleName = String(rule.name || '').toLowerCase()
  const applicableDocs = rule.applicable_documents || []

  // 基于规则 ID 前缀匹配
  if (ruleId.startsWith('lx-001') || ruleId.startsWith('lx-002') || ruleId.startsWith('lx-003') ||
      ruleId.startsWith('lx-004') || ruleId.startsWith('lx-005') || ruleId.startsWith('lx-006') ||
      ruleId.startsWith('lx-007')) {
    return 'basic_info'
  }

  if (ruleId.startsWith('lx-008') || ruleId.startsWith('lx-009') || ruleId.startsWith('lx-010')) {
    return 'auxiliary_exam'
  }

  if (ruleId.startsWith('lx-011') || ruleId.startsWith('lx-012') || ruleId.startsWith('lx-013')) {
    return 'course_record'
  }

  if (ruleId.startsWith('lx-014') || ruleId.startsWith('lx-015') || ruleId.startsWith('lx-016')) {
    return 'operation'
  }

  if (ruleId.startsWith('lx-017') || ruleId.startsWith('lx-018') || ruleId.startsWith('lx-019') ||
      ruleId.startsWith('lx-020')) {
    return 'discharge'
  }

  // 基于规则名称匹配
  if (ruleName.includes('主诉') || ruleName.includes('现病史') || ruleName.includes('既往史') ||
      ruleName.includes('体格检查') || ruleName.includes('入院诊断')) {
    return 'basic_info'
  }

  if (ruleName.includes('辅助检查') || ruleName.includes('检验') || ruleName.includes('检查结果')) {
    return 'auxiliary_exam'
  }

  if (ruleName.includes('病程') || ruleName.includes('诊断依据') || ruleName.includes('鉴别诊断') ||
      ruleName.includes('诊疗计划')) {
    return 'course_record'
  }

  if (ruleName.includes('手术') || ruleName.includes('术前') || ruleName.includes('术后')) {
    return 'operation'
  }

  if (ruleName.includes('出院') || ruleName.includes('出院医嘱') || ruleName.includes('出院诊断')) {
    return 'discharge'
  }

  // 基于适用文档类型匹配
  if (applicableDocs.includes('admission_record') || applicableDocs.includes('入院记录')) {
    return 'basic_info'
  }

  if (applicableDocs.includes('course_record') || applicableDocs.includes('病程记录')) {
    return 'course_record'
  }

  if (applicableDocs.includes('operation_record') || applicableDocs.includes('手术记录')) {
    return 'operation'
  }

  if (applicableDocs.includes('discharge_summary') || applicableDocs.includes('出院记录')) {
    return 'discharge'
  }

  return 'other'
}

/**
 * 对质控规则进行分类
 * @param rules 质控规则列表
 * @returns 分类后的规则 Map，key 为分类标识，value 为规则数组
 */
export function categorizeRules(rules: any[]): Map<string, any[]> {
  const categorizedMap = new Map<string, any[]>()

  // 初始化所有分类
  RULE_CATEGORIES.forEach(category => {
    categorizedMap.set(category.key, [])
  })

  // 对每个规则进行分类
  rules.forEach(rule => {
    const categoryKey = detectRuleCategory(rule)
    const categoryRules = categorizedMap.get(categoryKey) || []
    categoryRules.push(rule)
    categorizedMap.set(categoryKey, categoryRules)
  })

  // 移除空分类
  const result = new Map<string, any[]>()
  categorizedMap.forEach((rules, key) => {
    if (rules.length > 0) {
      result.set(key, rules)
    }
  })

  return result
}

/**
 * 根据搜索文本和筛选条件过滤质控规则
 * @param rules 质控规则列表
 * @param searchText 搜索文本（匹配规则 ID 或规则名称）
 * @param defectLevel 缺陷等级筛选（可选）
 * @param complexity 复杂度筛选（可选）
 * @returns 过滤后的规则列表
 */
export function filterRules(
  rules: any[],
  searchText: string = '',
  defectLevel?: string,
  complexity?: string
): any[] {
  let filtered = [...rules]

  // 搜索文本过滤
  if (searchText.trim()) {
    const searchLower = searchText.toLowerCase().trim()
    filtered = filtered.filter(rule => {
      const ruleId = String(rule.rule_id || '').toLowerCase()
      const ruleName = String(rule.name || '').toLowerCase()
      return ruleId.includes(searchLower) || ruleName.includes(searchLower)
    })
  }

  // 缺陷等级过滤
  if (defectLevel) {
    filtered = filtered.filter(rule => {
      const level = String(rule.defect_level || '').toLowerCase()
      return level === defectLevel.toLowerCase()
    })
  }

  // 复杂度过滤
  if (complexity) {
    filtered = filtered.filter(rule => {
      const comp = String(rule.complexity || '').toLowerCase()
      return comp === complexity.toLowerCase()
    })
  }

  return filtered
}
