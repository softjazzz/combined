import { computed, ref } from 'vue'
import type { DocItem, FrontpageFocusTarget, QCIssueLike } from '../types'
import { normalizeDefect } from '../normalize'

interface LocatePayload {
  target: FrontpageFocusTarget
  issue: QCIssueLike
}

function normalize(input?: string) {
  return (input || '').toLowerCase()
}

function inferDocType(issue: QCIssueLike): string | null {
  const text = `${issue.group || ''} ${issue.description || ''} ${issue.suggestion || ''}`.toLowerCase()
  if (/手术|操作|麻醉|切口|术者/.test(text)) return 'surgery_record'
  if (/出院|首页|出院诊断|出院小结/.test(text)) return 'discharge_record'
  if (/入院|主诉|现病史|体格检查|病情/.test(text)) return 'admission_record'
  return null
}

export function useQcPipeline() {
  const assistIssues = ref<QCIssueLike[]>([])
  const qcRefreshSeed = ref(0)

  const assistBadgeCount = computed(() =>
    assistIssues.value.filter(issue => !issue.dismissed).length,
  )

  function handleAssistIssuesChange(issues: QCIssueLike[]) {
    assistIssues.value = issues
      .map((issue, index) => normalizeDefect(issue, index))
      .filter(issue => !issue.dismissed)
  }

  function touchCodingRefresh() {
    qcRefreshSeed.value += 1
  }

  function inferLocateTarget(issue: QCIssueLike): FrontpageFocusTarget {
    const text = normalize(`${issue.group || ''} ${issue.description || ''} ${issue.suggestion || ''}`)
    if (issue.category === 'coding') {
      if (/手术|操作|麻醉|icd-9|icd9|cm-3|cm3/.test(text)) return 'procedure'
      return 'diagnosis'
    }
    if (issue.category === 'cost') return 'admission'
    if (/手术|操作|麻醉|切口|术者/.test(text)) return 'procedure'
    if (/诊断|icd|病情/.test(text)) return 'diagnosis'
    if (/入院|出院|住院|科室|床号|转科|入院病情/.test(text)) return 'admission'
    return 'basic'
  }

  function buildLocatePayload(issue: QCIssueLike): LocatePayload {
    return {
      target: inferLocateTarget(issue),
      issue,
    }
  }

  function findEvidenceDoc(issue: QCIssueLike, docs: DocItem[]) {
    const preferredType = inferDocType(issue)
    if (preferredType) {
      const hit = docs.find(d => d.type === preferredType && d.has_content && d.content)
      if (hit) return hit
    }
    return docs.find(d => d.has_content && d.content) || null
  }

  function findEvidenceSnippet(issue: QCIssueLike, content: string | null) {
    if (!content) return ''
    const source = content
    const key = (issue.evidence || issue.description || '').trim()
    if (!key) return source.slice(0, 220)
    const index = source.indexOf(key)
    if (index < 0) return source.slice(0, 220)
    const start = Math.max(0, index - 80)
    const end = Math.min(source.length, index + key.length + 80)
    return source.slice(start, end)
  }

  return {
    assistIssues,
    assistBadgeCount,
    qcRefreshSeed,
    handleAssistIssuesChange,
    touchCodingRefresh,
    buildLocatePayload,
    findEvidenceDoc,
    findEvidenceSnippet,
  }
}
