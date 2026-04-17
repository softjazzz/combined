export type ReportTemplateType = 'qc_summary' | 'performance' | 'trend' | 'comparison'
export type ReportStatus = 'pending' | 'generating' | 'completed' | 'failed'

export interface ReportTemplate {
  id: string
  template_name: string
  description: string
  template_type: ReportTemplateType
  enabled: boolean
}

export interface ReportGeneratePayload {
  period_start: string
  period_end: string
  filters?: Record<string, string | number | boolean>
  output_format?: 'pdf' | 'excel' | 'word'
}

export interface ReportInstance {
  id: string
  report_name: string
  template_id: string
  status: ReportStatus
  progress: number
  created_at: string
  output_format: 'pdf' | 'excel' | 'word'
}

const defaultTemplates: ReportTemplate[] = [
  {
    id: 'tpl-qc-summary',
    template_name: '质控概览报表',
    description: '输出指定周期内的质控总览和重点缺陷分布。',
    template_type: 'qc_summary',
    enabled: true,
  },
  {
    id: 'tpl-performance',
    template_name: '科室绩效报表',
    description: '按科室维度统计质控绩效与变化趋势。',
    template_type: 'performance',
    enabled: true,
  },
  {
    id: 'tpl-trend',
    template_name: '质量趋势报表',
    description: '展示评分、缺陷、处理时效等趋势变化。',
    template_type: 'trend',
    enabled: true,
  },
  {
    id: 'tpl-comparison',
    template_name: '科室对比报表',
    description: '对比多科室质控质量与执行效率差异。',
    template_type: 'comparison',
    enabled: true,
  },
]

const reportStore: ReportInstance[] = []

function makeReportName(template: ReportTemplate, payload: ReportGeneratePayload): string {
  return `${template.template_name}（${payload.period_start}~${payload.period_end}）`
}

function newReportId(): string {
  return `report-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export const reportEngine = {
  async getReportTemplates(): Promise<ReportTemplate[]> {
    return defaultTemplates.filter((item) => item.enabled)
  },

  async getReportInstances(options?: {
    limit?: number
    status?: ReportStatus
  }): Promise<ReportInstance[]> {
    const limit = options?.limit && options.limit > 0 ? options.limit : reportStore.length
    const filtered = options?.status
      ? reportStore.filter((item) => item.status === options.status)
      : reportStore
    return filtered.slice(0, limit)
  },

  async generateReport(
    templateId: string,
    payload: ReportGeneratePayload,
  ): Promise<ReportInstance> {
    const template = defaultTemplates.find((item) => item.id === templateId)
    if (!template) {
      throw new Error('未找到对应报表模板')
    }

    const instance: ReportInstance = {
      id: newReportId(),
      report_name: makeReportName(template, payload),
      template_id: templateId,
      status: 'completed',
      progress: 100,
      created_at: new Date().toISOString(),
      output_format: payload.output_format ?? 'pdf',
    }

    reportStore.unshift(instance)
    return instance
  },

  async deleteReportInstance(reportId: string): Promise<boolean> {
    const index = reportStore.findIndex((item) => item.id === reportId)
    if (index < 0) {
      return false
    }
    reportStore.splice(index, 1)
    return true
  },
}
