/**
 * DRG/DIP 模板上传 - 病案明细数据模型
 *
 * 统一数据真源：所有页面（Analysis / FeeMonitoring / PostEvent）
 * 都从这个结构衍生各自需要的聚合视图。
 */

/** 病案明细记录 - 对应 Excel 模板的一行 */
export interface CaseRecord {
  // === 基础信息 ===
  /** 住院号（必填，唯一标识） */
  admission_id: string
  /** 患者姓名（可脱敏） */
  patient_name: string
  /** 性别 */
  gender?: 'M' | 'F'
  /** 年龄 */
  age?: number

  // === 五级层级字段 ===
  /** 出院科室（必填） */
  department: string
  /** 病区 */
  ward?: string
  /** 主诊医师组（统一命名，PostEvent 侧映射为 chief_group） */
  attending_group?: string
  /** 主治医师 */
  attending_doctor?: string

  // === 时间信息 ===
  /** 入院日期 */
  admission_date?: string
  /** 出院日期（必填） */
  discharge_date: string
  /** 住院天数 */
  los?: number
  /** 标准住院日（需要模板显式提供，否则时间消耗指数不可计算） */
  standard_los?: number

  // === 诊断与手术 ===
  /** 主诊断 ICD 编码 */
  primary_diagnosis_code?: string
  /** 主诊断名称 */
  primary_diagnosis_name?: string
  /** 其他诊断 ICD（英文分号 ; 分隔） */
  secondary_diagnoses?: string
  /** 主手术 ICD 编码 */
  main_procedure_code?: string
  /** 主手术名称 */
  main_procedure_name?: string

  // === 费用拆分 ===
  /** 总费用（必填） */
  total_cost: number
  /** 药品费 */
  drug_fee?: number
  /** 耗材费 */
  material_fee?: number
  /** 检查费 */
  exam_fee?: number
  /** 治疗费 */
  treatment_fee?: number
  /** 手术费 */
  surgery_fee?: number
  /** 床位费 */
  bed_fee?: number
  /** 护理费 */
  nursing_fee?: number
  /** 其他费用 */
  other_fee?: number

  // === DRG/DIP 分组结果 ===
  /** DRG 编码 */
  drg_code?: string
  /** DRG 名称 */
  drg_name?: string
  /** DIP 编码 */
  dip_code?: string
  /** DIP 名称 */
  dip_name?: string
  /** 权重 (RW) */
  weight?: number
  /** 基准支付额 */
  baseline_payment?: number
  /** 医保实际支付 */
  insurance_payment?: number
  /** DIP 分值（地区特有，等价于 DRG 的 RW 权重） */
  dip_score?: number

  // === 质量标志 ===
  /** 低风险组标志（0=否, 1=是）；需要模板显式提供 */
  low_risk_case_flag?: 0 | 1
  /** 低风险死亡标志（0=否, 1=是）；需要模板显式提供 */
  low_risk_death_flag?: 0 | 1
  /** 未入组原因 */
  ungrouped_reason?: string
}

/** 数据集元信息 */
export interface DatasetMeta {
  /** 数据集名称 */
  name: string
  /** 上传时间 ISO */
  uploadedAt: string
  /** 病案总数 */
  recordCount: number
  /** 有效病案数（通过校验） */
  validCount: number
  /** 跳过行数 */
  skippedCount: number
  /** 日期范围 [最早出院日, 最晚出院日] */
  dateRange: [string, string]
  /** 涉及科室列表 */
  departments: string[]
  /** 涉及 DRG 组数 */
  drgGroupCount: number
}

/** 模板校验结果 */
export interface ValidationResult {
  /** 是否可以导入（有有效数据） */
  canImport: boolean
  /** 有效行数 */
  validRows: number
  /** 跳过行数及原因 */
  errors: ValidationError[]
  /** 警告（不影响导入） */
  warnings: string[]
}

/** 单行校验错误 */
export interface ValidationError {
  /** Excel 行号（从2开始，1是表头） */
  row: number
  /** 错误字段 */
  field: string
  /** 错误原因 */
  message: string
}

/**
 * Excel 模板列定义
 * key: CaseRecord 字段名
 * header: Excel 表头中文名
 * required: 是否必填
 */
export interface TemplateColumn {
  key: keyof CaseRecord
  header: string
  required: boolean
}

/** 模板列配置（定义 Excel 的列顺序和表头） */
export const TEMPLATE_COLUMNS: TemplateColumn[] = [
  { key: 'admission_id', header: '住院号', required: true },
  { key: 'patient_name', header: '患者姓名', required: false },
  { key: 'gender', header: '性别', required: false },
  { key: 'age', header: '年龄', required: false },
  { key: 'department', header: '出院科室', required: true },
  { key: 'ward', header: '病区', required: false },
  { key: 'attending_group', header: '主诊医师组', required: false },
  { key: 'attending_doctor', header: '主治医师', required: false },
  { key: 'admission_date', header: '入院日期', required: false },
  { key: 'discharge_date', header: '出院日期', required: true },
  { key: 'los', header: '住院天数', required: false },
  { key: 'standard_los', header: '标准住院日', required: false },
  { key: 'primary_diagnosis_code', header: '主诊断ICD', required: false },
  { key: 'primary_diagnosis_name', header: '主诊断名称', required: false },
  { key: 'secondary_diagnoses', header: '其他诊断ICD', required: false },
  { key: 'main_procedure_code', header: '主手术ICD', required: false },
  { key: 'main_procedure_name', header: '主手术名称', required: false },
  { key: 'total_cost', header: '总费用', required: true },
  { key: 'drug_fee', header: '药品费', required: false },
  { key: 'material_fee', header: '耗材费', required: false },
  { key: 'exam_fee', header: '检查费', required: false },
  { key: 'treatment_fee', header: '治疗费', required: false },
  { key: 'surgery_fee', header: '手术费', required: false },
  { key: 'bed_fee', header: '床位费', required: false },
  { key: 'nursing_fee', header: '护理费', required: false },
  { key: 'other_fee', header: '其他费用', required: false },
  { key: 'dip_code', header: 'DIP编码', required: false },
  { key: 'dip_name', header: 'DIP名称', required: false },
  { key: 'dip_score', header: 'DIP分值', required: false },
  { key: 'drg_code', header: 'DRG编码', required: false },
  { key: 'drg_name', header: 'DRG名称', required: false },
  { key: 'weight', header: '权重', required: false },
  { key: 'baseline_payment', header: '基准支付额', required: false },
  { key: 'insurance_payment', header: '医保实际支付', required: false },
  { key: 'low_risk_case_flag', header: '低风险组标志', required: false },
  { key: 'low_risk_death_flag', header: '低风险死亡标志', required: false },
]
