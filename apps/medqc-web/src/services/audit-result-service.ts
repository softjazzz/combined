// @ts-nocheck
// Temporary compile-safe audit result service.
// Provides the methods currently consumed by audit UI components.

import type {
  AIDefectSuggestion,
  AuditLevel,
  QCAuditResult,
  QCAuditTaskItem,
  QCDefect,
} from '@/types/audit-module'

interface CreateAuditPayload {
  audit_score?: number
  audit_conclusion?: string
  defects?: Array<Partial<QCDefect>>
}

interface ModifyLowerPayload {
  reason?: string
  score?: number
  conclusion?: string
}

class AuditResultService {
  private readonly results = new Map<string, QCAuditResult[]>()

  async getAIDefectSuggestions(
    _taskItem: QCAuditTaskItem,
    _context: { medical_record?: string }
  ): Promise<AIDefectSuggestion[]> {
    return []
  }

  async getAuditResults(taskItemId: string, _includeDefects: boolean = true): Promise<QCAuditResult[]> {
    return [...(this.results.get(taskItemId) || [])]
  }

  async createAuditResult(
    taskItemId: string,
    auditLevel: AuditLevel,
    reviewerId: string,
    payload: CreateAuditPayload
  ): Promise<QCAuditResult> {
    const now = new Date().toISOString()
    const result: QCAuditResult = {
      id: `qar_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      task_item_id: taskItemId,
      audit_level: auditLevel,
      reviewer_id: reviewerId,
      reviewer_name: reviewerId,
      audit_score: Number(payload.audit_score ?? 85),
      audit_conclusion: payload.audit_conclusion || '',
      defects_found: (payload.defects || []).map((d, i) => ({
        id: d.id || `def_${Date.now()}_${i}`,
        audit_result_id: '',
        task_item_id: taskItemId,
        defect_type: String(d.defect_type || '内容缺失'),
        defect_category: String(d.defect_category || '完整性'),
        severity: (d.severity as QCDefect['severity']) || 'minor',
        title: String(d.title || '待确认缺陷'),
        description: String(d.description || ''),
        status: (d.status as QCDefect['status']) || 'open',
        score_deduction: Number(d.score_deduction ?? 0),
        ai_assisted: Boolean(d.ai_assisted ?? false),
        identified_at: now,
        created_at: now,
        updated_at: now,
      })),
      status: 'draft',
      is_final: false,
      created_at: now,
      updated_at: now,
    }

    result.defects_found = result.defects_found.map(def => ({ ...def, audit_result_id: result.id }))

    const list = this.results.get(taskItemId) || []
    const idx = list.findIndex(r => r.audit_level === auditLevel)
    if (idx >= 0) {
      list[idx] = result
    } else {
      list.push(result)
    }
    this.results.set(taskItemId, list)
    return result
  }

  async submitAuditResult(auditResultId: string): Promise<void> {
    this.updateResultById(auditResultId, item => {
      item.status = 'submitted'
      item.submitted_at = new Date().toISOString()
      item.is_final = true
      item.updated_at = new Date().toISOString()
    })
  }

  async modifyLowerLevelResult(
    auditResultId: string,
    modifiedBy: string,
    payload: ModifyLowerPayload
  ): Promise<void> {
    this.updateResultById(auditResultId, item => {
      if (typeof payload.score === 'number') item.audit_score = payload.score
      if (typeof payload.conclusion === 'string') item.audit_conclusion = payload.conclusion
      item.modified_by = modifiedBy
      item.modification_reason = payload.reason || ''
      item.original_score = item.original_score ?? item.audit_score
      item.status = 'modified'
      item.updated_at = new Date().toISOString()
    })
  }

  private updateResultById(id: string, mutator: (item: QCAuditResult) => void): void {
    for (const [taskId, list] of this.results.entries()) {
      const idx = list.findIndex(x => x.id === id)
      if (idx >= 0) {
        const next = { ...list[idx] }
        mutator(next)
        list[idx] = next
        this.results.set(taskId, list)
        return
      }
    }
  }
}

export const auditResultService = new AuditResultService()
export default auditResultService

