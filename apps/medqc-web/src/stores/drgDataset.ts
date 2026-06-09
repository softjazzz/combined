/**
 * DRG 模板数据集 Store
 *
 * 职责：保存上传的病案明细数据，提供聚合查询接口。
 * Store 只保状态和编排，计算逻辑委托给 drg-aggregation.ts。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { CaseRecord, DatasetMeta, ValidationResult } from '@/types/drg-dataset'
import type { AnalysisDimension, AnalysisDataResponse } from '@/types/drg-analysis'
import { buildAnalysisResponse } from '@/utils/drg-aggregation'
import {
  parseDatasetWorkbook,
  validateCaseRecords,
  exportDatasetTemplate,
} from '@/utils/drg-template'
import { buildTemplateCases } from '@/data/drg/template-cases'

export const useDrgDatasetStore = defineStore('drgDataset', () => {
  // ==================== State ====================
  const records = ref<CaseRecord[]>([])
  const meta = ref<DatasetMeta | null>(null)
  const lastValidation = ref<ValidationResult | null>(null)
  const importing = ref(false)

  // ==================== Getters ====================

  /** 是否有上传数据 */
  const hasUploadedData = computed(() => records.value.length > 0)

  /** 数据摘要 */
  const summary = computed(() => {
    if (!hasUploadedData.value) return null
    const r = records.value
    const departments = [...new Set(r.map((c) => c.department))]
    const drgCodes = new Set(
      r.filter((c) => c.drg_code || c.dip_code).map((c) => c.drg_code || c.dip_code || ''),
    )
    return {
      recordCount: r.length,
      departments,
      drgGroupCount: drgCodes.size,
      groupedCount: r.filter((c) => c.drg_code || c.dip_code).length,
      ungroupedCount: r.filter((c) => !c.drg_code && !c.dip_code).length,
    }
  })

  // ==================== Actions ====================

  /**
   * 从 Excel 文件导入数据
   */
  async function importFromExcel(file: File): Promise<{
    success: boolean
    validation: ValidationResult
  }> {
    importing.value = true
    try {
      const { rawRows } = await parseDatasetWorkbook(file)
      const result = validateCaseRecords(rawRows)
      lastValidation.value = result.validation

      if (!result.validation.canImport) {
        return { success: false, validation: result.validation }
      }

      records.value = result.records

      // 计算元信息
      const dates = result.records
        .map((r) => r.discharge_date)
        .filter(Boolean)
        .sort()
      const departments = [...new Set(result.records.map((r) => r.department))]
      const drgCodes = new Set(
        result.records
          .filter((r) => r.drg_code || r.dip_code)
          .map((r) => r.drg_code || r.dip_code || ''),
      )

      meta.value = {
        name: file.name,
        uploadedAt: new Date().toISOString(),
        recordCount: rawRows.length,
        validCount: result.records.length,
        skippedCount: rawRows.length - result.records.length,
        dateRange: [dates[0] || '', dates[dates.length - 1] || ''],
        departments,
        drgGroupCount: drgCodes.size,
      }

      return { success: true, validation: result.validation }
    } finally {
      importing.value = false
    }
  }

  /**
   * 清除数据集，恢复到 Mock 模式
   */
  function clearData() {
    records.value = []
    meta.value = null
    lastValidation.value = null
  }

  /**
   * 获取 AnalysisDataResponse（供 api/drg.ts 调用，替代 Mock）
   */
  function getAnalysisResponse(dimension: AnalysisDimension): AnalysisDataResponse {
    return buildAnalysisResponse(records.value, dimension)
  }

  /**
   * 下载模板（含样例数据）
   */
  async function downloadTemplate() {
    await exportDatasetTemplate(buildTemplateCases())
  }

  return {
    // state
    records,
    meta,
    lastValidation,
    importing,
    // getters
    hasUploadedData,
    summary,
    // actions
    importFromExcel,
    clearData,
    getAnalysisResponse,
    downloadTemplate,
  }
})
