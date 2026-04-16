import { qcAnalysisEngine } from './qc/analysis-engine'

export interface RunningQCRequest {
  recordId: string
  patientId: string
  content: string
  department: string
  admissionDate: string
  currentDate: string
  doctorId: string
  analysisType: 'real-time' | 'scheduled' | 'triggered'
}

export interface RunningQCIssue {
  qualityPointId: string
  qualityPointName: string
  content: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  deductionScore: number
  department: string
  alertLevel: 'low' | 'medium' | 'high' | 'critical'
  isUrgent: boolean
  requiresImmediateAction: boolean
  suggestion: string
}

export interface RunningQCTimelinessCheck {
  checkType: 'admission_record' | 'progress_note' | 'surgery_record' | 'discharge_record'
  expectedTime: string
  actualTime?: string
  isOverdue: boolean
  overdueHours?: number
  suggestion: string
}

export interface RunningQCResult {
  recordId: string
  patientId: string
  score?: number
  analysisType: 'real-time' | 'scheduled' | 'triggered'
  analysisTime: string
  summary: {
    totalScore: number
    grade: '甲级' | '乙级' | '丙级'
    overallAssessment: string
    riskLevel: 'low' | 'medium' | 'high' | 'critical'
  }
  realTimeIssues: RunningQCIssue[]
  departmentSpecificIssues: Array<{
    qualityPointId: string
    qualityPointName: string
    content: string
    isEffectiveToDoctor: boolean
    suggestion: string
  }>
  timelinessChecks: RunningQCTimelinessCheck[]
  recommendations: string[]
  nextCheckTime: string
}

export type RunningQCResultComponent = RunningQCResult

function clampScore(score: number): number {
  return Math.max(0, Math.min(100, Math.round(score)))
}

function toGrade(score: number): '甲级' | '乙级' | '丙级' {
  if (score >= 90) return '甲级'
  if (score >= 75) return '乙级'
  return '丙级'
}

function toRiskLevel(score: number): 'low' | 'medium' | 'high' | 'critical' {
  if (score >= 90) return 'low'
  if (score >= 75) return 'medium'
  if (score >= 60) return 'high'
  return 'critical'
}

function parseDateTime(value: string): number {
  const time = new Date(value).getTime()
  return Number.isNaN(time) ? Date.now() : time
}

function hoursBetween(start: string, end: string): number {
  const diff = parseDateTime(end) - parseDateTime(start)
  return Math.max(0, Math.round(diff / (60 * 60 * 1000)))
}

function buildRealTimeIssues(
  department: string,
  ruleResults: Array<{
    ruleId: string
    ruleName: string
    hasViolation: boolean
    severity: string
    evidence: string[]
    reasoning: string
    score?: number
  }>,
): RunningQCIssue[] {
  return ruleResults
    .filter((item) => item.hasViolation)
    .map((item) => {
      const severity = item.severity === 'critical' || item.severity === 'major' ? 'high' : 'medium'
      const alertLevel = item.severity === 'critical' ? 'critical' : severity
      return {
        qualityPointId: item.ruleId,
        qualityPointName: item.ruleName,
        content: item.evidence[0] || item.reasoning,
        severity,
        deductionScore: Math.max(1, 100 - (item.score ?? 60)),
        department,
        alertLevel,
        isUrgent: alertLevel === 'critical' || alertLevel === 'high',
        requiresImmediateAction: alertLevel === 'critical',
        suggestion: item.evidence[0] || item.reasoning,
      }
    })
}

function buildDepartmentSpecificIssues(
  department: string,
  issues: RunningQCIssue[],
): RunningQCResult['departmentSpecificIssues'] {
  if (!department) {
    return []
  }

  const firstIssue = issues[0]
  if (!firstIssue) {
    return [{
      qualityPointId: `${department}-qc-001`,
      qualityPointName: `${department}常规关注项`,
      content: `${department}当前未见明显实时缺陷，建议持续关注病历结构完整性。`,
      isEffectiveToDoctor: true,
      suggestion: '保持病程记录、出院记录与医嘱执行的一致性。',
    }]
  }

  return [{
    qualityPointId: firstIssue.qualityPointId,
    qualityPointName: `${department}重点关注 - ${firstIssue.qualityPointName}`,
    content: firstIssue.content,
    isEffectiveToDoctor: true,
    suggestion: firstIssue.suggestion,
  }]
}

function buildTimelinessChecks(request: RunningQCRequest): RunningQCTimelinessCheck[] {
  const admissionTs = parseDateTime(request.admissionDate)
  const currentTs = parseDateTime(request.currentDate)
  const expectedAdmission = new Date(admissionTs + 24 * 60 * 60 * 1000).toISOString()
  const progressExpected = new Date(admissionTs + 48 * 60 * 60 * 1000).toISOString()
  const surgeryExpected = new Date(admissionTs + 72 * 60 * 60 * 1000).toISOString()
  const dischargeExpected = new Date(Math.max(admissionTs, currentTs)).toISOString()

  const admissionOverdue = currentTs > admissionTs + 24 * 60 * 60 * 1000
  const progressOverdue = currentTs > admissionTs + 48 * 60 * 60 * 1000
  const surgeryOverdue = currentTs > admissionTs + 72 * 60 * 60 * 1000
  const dischargeOverdue = currentTs > admissionTs + 96 * 60 * 60 * 1000

  return [
    {
      checkType: 'admission_record',
      expectedTime: expectedAdmission,
      actualTime: request.currentDate,
      isOverdue: admissionOverdue,
      overdueHours: admissionOverdue ? hoursBetween(expectedAdmission, request.currentDate) : 0,
      suggestion: '入院记录请尽量在 24 小时内完成。',
    },
    {
      checkType: 'progress_note',
      expectedTime: progressExpected,
      actualTime: request.currentDate,
      isOverdue: progressOverdue,
      overdueHours: progressOverdue ? hoursBetween(progressExpected, request.currentDate) : 0,
      suggestion: '病程记录建议按病程变化及时更新。',
    },
    {
      checkType: 'surgery_record',
      expectedTime: surgeryExpected,
      actualTime: request.currentDate,
      isOverdue: surgeryOverdue,
      overdueHours: surgeryOverdue ? hoursBetween(surgeryExpected, request.currentDate) : 0,
      suggestion: '如涉及手术，请及时完善手术记录。',
    },
    {
      checkType: 'discharge_record',
      expectedTime: dischargeExpected,
      actualTime: request.currentDate,
      isOverdue: dischargeOverdue,
      overdueHours: dischargeOverdue ? hoursBetween(dischargeExpected, request.currentDate) : 0,
      suggestion: '出院后请及时完成出院记录与总结。',
    },
  ]
}

class RunningQCService {
  async analyzeRunningRecord(request: RunningQCRequest): Promise<RunningQCResult> {
    const result = await qcAnalysisEngine.analyze({
      recordId: request.recordId,
      content: request.content,
      options: {
        priority: 'high',
        includeCache: true,
      },
    })

    const score = clampScore(result.overallScore)
    const realTimeIssues = buildRealTimeIssues(request.department, result.ruleResults)
    const departmentSpecificIssues = buildDepartmentSpecificIssues(request.department, realTimeIssues)
    const timelinessChecks = buildTimelinessChecks(request)

    const recommendations = [...result.suggestions]
    if (realTimeIssues.length > 0) {
      recommendations.unshift('优先修复当前高风险质控问题，再处理一般缺陷。')
    }
    if (timelinessChecks.some((item) => item.isOverdue)) {
      recommendations.push('请重点复核时效性节点，避免超时记录影响质控等级。')
    }

    return {
      recordId: request.recordId,
      patientId: request.patientId,
      score,
      analysisType: request.analysisType,
      analysisTime: request.currentDate,
      summary: {
        totalScore: score,
        grade: toGrade(score),
        overallAssessment:
          realTimeIssues.length > 0
            ? `发现 ${realTimeIssues.length} 个实时质控问题，建议优先处理高风险事项。`
            : '当前记录整体稳定，未发现明显实时质控问题。',
        riskLevel: toRiskLevel(score),
      },
      realTimeIssues,
      departmentSpecificIssues,
      timelinessChecks,
      recommendations: recommendations.length > 0 ? recommendations : ['当前质控结果正常，建议保持现有记录规范。'],
      nextCheckTime: new Date(parseDateTime(request.currentDate) + 12 * 60 * 60 * 1000).toISOString(),
    }
  }

  async healthCheck(): Promise<{ status: string; message: string }> {
    return {
      status: 'healthy',
      message: '运行病历质控服务可用',
    }
  }
}

export const runningQCService = new RunningQCService()
