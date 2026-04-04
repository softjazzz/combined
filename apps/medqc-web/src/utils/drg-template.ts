/**
 * DRG/DIP 模板导入导出工具
 *
 * 复用现有 xlsx 动态加载模式 (参考 src/utils/export.ts)
 */

import type { CaseRecord, ValidationResult, ValidationError } from '@/types/drg-dataset'
import { TEMPLATE_COLUMNS } from '@/types/drg-dataset'

type XLSXModule = typeof import('xlsx')

let xlsxModulePromise: Promise<XLSXModule> | null = null

function loadXlsxModule() {
  if (!xlsxModulePromise) {
    xlsxModulePromise = import('xlsx')
  }
  return xlsxModulePromise
}

// ==================== 表头映射 ====================

/** 中文表头 → CaseRecord 字段名 */
const HEADER_TO_KEY: Map<string, keyof CaseRecord> = new Map(
  TEMPLATE_COLUMNS.map((col) => [col.header, col.key]),
)

/** 必填字段列表 */
const REQUIRED_FIELDS: Set<keyof CaseRecord> = new Set(
  TEMPLATE_COLUMNS.filter((col) => col.required).map((col) => col.key),
)

// ==================== 解析 ====================

/**
 * 从 File 对象解析 Excel，返回原始行数据
 */
export async function parseDatasetWorkbook(
  file: File,
): Promise<{ headers: string[]; rawRows: Record<string, any>[] }> {
  const XLSX = await loadXlsxModule()
  const buffer = await file.arrayBuffer()
  const workbook = XLSX.read(buffer, { type: 'array' })

  // 优先找"病案明细" Sheet，找不到就用第一个
  const sheetName =
    workbook.SheetNames.find((n) => n.includes('病案明细')) || workbook.SheetNames[0]
  if (!sheetName) throw new Error('Excel 文件中没有找到工作表')

  const sheet = workbook.Sheets[sheetName]
  const rawRows: Record<string, any>[] = XLSX.utils.sheet_to_json(sheet, { defval: '' })

  // 提取表头
  const headers = rawRows.length > 0 ? Object.keys(rawRows[0]) : []

  return { headers, rawRows }
}

/**
 * 将原始行转换为 CaseRecord[]，同时做校验
 */
export function validateCaseRecords(rawRows: Record<string, any>[]): {
  records: CaseRecord[]
  validation: ValidationResult
} {
  const records: CaseRecord[] = []
  const errors: ValidationError[] = []
  const warnings: string[] = []
  const seenIds = new Set<string>()

  for (let i = 0; i < rawRows.length; i++) {
    const raw = rawRows[i]
    const rowNum = i + 2 // Excel 行号（1是表头）
    const mapped = mapRowToRecord(raw)

    // 必填校验
    let hasError = false

    if (!mapped.admission_id || String(mapped.admission_id).trim() === '') {
      errors.push({ row: rowNum, field: '住院号', message: '住院号为空' })
      hasError = true
    }

    if (!mapped.department || String(mapped.department).trim() === '') {
      errors.push({ row: rowNum, field: '出院科室', message: '出院科室为空' })
      hasError = true
    }

    if (!mapped.discharge_date || String(mapped.discharge_date).trim() === '') {
      errors.push({ row: rowNum, field: '出院日期', message: '出院日期为空' })
      hasError = true
    }

    if (typeof mapped.total_cost !== 'number' || isNaN(mapped.total_cost)) {
      errors.push({ row: rowNum, field: '总费用', message: '总费用不是有效数字' })
      hasError = true
    } else if (mapped.total_cost < 0) {
      errors.push({ row: rowNum, field: '总费用', message: '总费用为负数' })
      hasError = true
    }

    if (hasError) continue

    // 重复 admission_id 检测
    const id = String(mapped.admission_id).trim()
    if (seenIds.has(id)) {
      warnings.push(`第 ${rowNum} 行：住院号 "${id}" 重复，将覆盖之前的记录`)
      // 移除之前的记录
      const prevIdx = records.findIndex((r) => r.admission_id === id)
      if (prevIdx >= 0) records.splice(prevIdx, 1)
    }
    seenIds.add(id)

    records.push(mapped)
  }

  return {
    records,
    validation: {
      canImport: records.length > 0,
      validRows: records.length,
      errors,
      warnings,
    },
  }
}

/**
 * 将原始行映射为 CaseRecord
 */
function mapRowToRecord(raw: Record<string, any>): CaseRecord {
  const get = (header: string): any => {
    // 直接用中文表头查
    if (header in raw) return raw[header]
    // 尝试用字段名查（英文模板）
    const key = HEADER_TO_KEY.get(header)
    if (key && key in raw) return raw[key]
    return undefined
  }

  const toStr = (val: any): string => {
    if (val == null || val === '') return ''
    return String(val).trim()
  }

  const toNum = (val: any): number | undefined => {
    if (val == null || val === '') return undefined
    const n = Number(val)
    return isNaN(n) ? undefined : n
  }

  const toFlag = (val: any): 0 | 1 | undefined => {
    if (val == null || val === '') return undefined
    const n = Number(val)
    if (n === 0 || n === 1) return n as 0 | 1
    return undefined
  }

  // 优先按中文表头映射
  const record: CaseRecord = {
    admission_id: toStr(get('住院号') ?? raw['admission_id']),
    patient_name: toStr(get('患者姓名') ?? raw['patient_name'] ?? ''),
    gender: (() => {
      const v = toStr(get('性别') ?? raw['gender'])
      if (v === 'M' || v === '男') return 'M'
      if (v === 'F' || v === '女') return 'F'
      return undefined
    })(),
    age: toNum(get('年龄') ?? raw['age']),
    department: toStr(get('出院科室') ?? raw['department']),
    ward: toStr(get('病区') ?? raw['ward']) || undefined,
    attending_group: toStr(get('主诊医师组') ?? raw['attending_group']) || undefined,
    attending_doctor: toStr(get('主治医师') ?? raw['attending_doctor']) || undefined,
    admission_date: toStr(get('入院日期') ?? raw['admission_date']) || undefined,
    discharge_date: toStr(get('出院日期') ?? raw['discharge_date']),
    los: toNum(get('住院天数') ?? raw['los']),
    standard_los: toNum(get('标准住院日') ?? raw['standard_los']),
    primary_diagnosis_code: toStr(get('主诊断ICD') ?? raw['primary_diagnosis_code']) || undefined,
    primary_diagnosis_name: toStr(get('主诊断名称') ?? raw['primary_diagnosis_name']) || undefined,
    secondary_diagnoses: toStr(get('其他诊断ICD') ?? raw['secondary_diagnoses']) || undefined,
    main_procedure_code: toStr(get('主手术ICD') ?? raw['main_procedure_code']) || undefined,
    main_procedure_name: toStr(get('主手术名称') ?? raw['main_procedure_name']) || undefined,
    total_cost: toNum(get('总费用') ?? raw['total_cost']) ?? 0,
    drug_fee: toNum(get('药品费') ?? raw['drug_fee']),
    material_fee: toNum(get('耗材费') ?? raw['material_fee']),
    exam_fee: toNum(get('检查费') ?? raw['exam_fee']),
    treatment_fee: toNum(get('治疗费') ?? raw['treatment_fee']),
    surgery_fee: toNum(get('手术费') ?? raw['surgery_fee']),
    bed_fee: toNum(get('床位费') ?? raw['bed_fee']),
    nursing_fee: toNum(get('护理费') ?? raw['nursing_fee']),
    other_fee: toNum(get('其他费用') ?? raw['other_fee']),
    drg_code: toStr(get('DRG编码') ?? raw['drg_code']) || undefined,
    drg_name: toStr(get('DRG名称') ?? raw['drg_name']) || undefined,
    dip_code: toStr(get('DIP编码') ?? raw['dip_code']) || undefined,
    dip_name: toStr(get('DIP名称') ?? raw['dip_name']) || undefined,
    weight: toNum(get('权重') ?? raw['weight']),
    baseline_payment: toNum(get('基准支付额') ?? raw['baseline_payment']),
    insurance_payment: toNum(get('医保实际支付') ?? raw['insurance_payment']),
    low_risk_case_flag: toFlag(get('低风险组标志') ?? raw['low_risk_case_flag']),
    low_risk_death_flag: toFlag(get('低风险死亡标志') ?? raw['low_risk_death_flag']),
  }

  return record
}

// ==================== 导出模板 ====================

/**
 * 导出带样例数据的 Excel 模板
 */
export async function exportDatasetTemplate(sampleData: CaseRecord[]) {
  const XLSX = await loadXlsxModule()

  // 构建表头行
  const headers = TEMPLATE_COLUMNS.map((col) => col.header)

  // 构建数据行
  const dataRows = sampleData.map((record) =>
    TEMPLATE_COLUMNS.map((col) => {
      const val = record[col.key]
      if (val == null) return ''
      return val
    }),
  )

  // 创建工作表
  const ws = XLSX.utils.aoa_to_sheet([headers, ...dataRows])

  // 设置列宽
  ws['!cols'] = TEMPLATE_COLUMNS.map((col) => ({
    wch: Math.max(col.header.length * 2 + 2, 12),
  }))

  // 创建工作簿
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '病案明细')

  // 下载
  XLSX.writeFile(wb, `DRG分析数据模板_${new Date().toISOString().slice(0, 10)}.xlsx`)
}
