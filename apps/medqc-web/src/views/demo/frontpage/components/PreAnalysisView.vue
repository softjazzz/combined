<template>
  <div class="pre-analysis-shell">
    <section class="command-header">
      <div class="header-main">
        <div class="title-block">
          <h1>病历抽取与 DRG / DIP 预判</h1>
          <p>先阅读原始病历，再执行结构化抽取与分组预判，统一在一个中控台完成。</p>
        </div>

        <div class="action-bar">
          <button
            type="button"
            class="btn btn-ghost"
            :disabled="extracting || grouping"
            @click="handleExtract"
          >
            <span class="btn-icon">⚡</span>
            {{ extracting ? '抽取中...' : '开始抽取' }}
          </button>

          <div
            class="segmented"
            role="tablist"
            aria-label="分组类型"
          >
            <button
              type="button"
              class="segmented-item"
              :class="{ active: groupingType === 'DIP' }"
              :disabled="extracting || grouping || !hasExtractedData"
              @click="handleDIPGrouping"
            >
              DIP
            </button>
            <button
              type="button"
              class="segmented-item"
              :class="{ active: groupingType === 'DRG' }"
              :disabled="extracting || grouping || !hasExtractedData"
              @click="handleDRGGrouping"
            >
              DRG
            </button>
          </div>
        </div>
      </div>

      <div
        class="case-strip"
        role="tablist"
        aria-label="病例切换"
      >
        <button
          v-for="(item, index) in testCases"
          :key="item.name"
          type="button"
          class="case-chip"
          :class="{ active: selectedCaseIndex === index }"
          @click="handleCaseChange(index)"
        >
          <span class="case-chip__id">{{ item.admissionId || `病例 ${index + 1}` }}</span>
          <span class="case-chip__name">{{ item.name }}</span>
        </button>

        <div class="active-case">
          <span class="active-case__label">当前病例</span>
          <strong>{{ currentCase.admissionId }}</strong>
          <span>{{ currentCase.name }}</span>
        </div>
      </div>
    </section>

    <section class="status-zone">
      <div
        class="workflow-rail"
        aria-label="工作流"
      >
        <div
          class="workflow-node"
          :class="{ active: !!medicalText }"
        >
          <span class="workflow-node__index">01</span>
          <div>
            <div class="workflow-node__title">
              病历阅读
            </div>
            <div class="workflow-node__desc">
              确认原始文本与临床场景
            </div>
          </div>
        </div>
        <div
          class="workflow-node"
          :class="{ active: hasExtractedData }"
        >
          <span class="workflow-node__index">02</span>
          <div>
            <div class="workflow-node__title">
              结构化抽取
            </div>
            <div class="workflow-node__desc">
              沉淀主诊断、手术与费用字段
            </div>
          </div>
        </div>
        <div
          class="workflow-node"
          :class="{ active: !!drgResult }"
        >
          <span class="workflow-node__index">03</span>
          <div>
            <div class="workflow-node__title">
              分组预判
            </div>
            <div class="workflow-node__desc">
              输出分组结果与费用判断
            </div>
          </div>
        </div>
      </div>

      <div class="snapshot-strip">
        <article class="snapshot-card">
          <span class="snapshot-card__label">文书长度</span>
          <strong>{{ textLength }}</strong>
          <small>字</small>
        </article>
        <article class="snapshot-card">
          <span class="snapshot-card__label">诊断条目</span>
          <strong>{{ diagnosisCount }}</strong>
          <small>条</small>
        </article>
        <article class="snapshot-card">
          <span class="snapshot-card__label">手术条目</span>
          <strong>{{ procedures.length }}</strong>
          <small>条</small>
        </article>
        <article class="snapshot-card snapshot-card--status">
          <span class="snapshot-card__label">当前状态</span>
          <strong>{{ currentStageLabel }}</strong>
        </article>
      </div>
    </section>

    <section class="workspace-grid">
      <article class="surface reader-panel">
        <div class="panel-head panel-head--between">
          <h2>原始病历内容</h2>
          <div class="reading-meta">
            <span>当前病案</span>
            <strong>{{ currentCase.admissionId }}</strong>
            <span>{{ currentCase.name }}</span>
          </div>
        </div>

        <div class="reader-body">
          <div class="reader-scroll">
            <div
              class="medical-text"
              v-html="highlightedMedicalText"
            />
          </div>
        </div>
      </article>

      <aside class="result-column">
        <article class="surface">
          <div class="panel-head panel-head--between">
            <h2>主诊断与手术 / 操作</h2>
            <span class="status-pill">{{ hasExtractedData ? '已同步' : '等待抽取' }}</span>
          </div>

          <div class="summary-list">
            <div class="summary-row">
              <span class="summary-row__label">主诊断</span>
              <strong>{{ hasExtractedData && mainDiagnosis ? mainDiagnosis.text || mainDiagnosis.code || '已抽取' : '等待抽取' }}</strong>
              <span class="summary-row__meta">编码 {{ mainDiagnosis?.code || '--' }}</span>
            </div>
            <div class="summary-row">
              <span class="summary-row__label">手术 / 操作</span>
              <strong>{{ procedures.length ? procedures[0].text || '已抽取' : '等待抽取' }}</strong>
              <span class="summary-row__meta">{{ hasExtractedData ? `${procedures.length} 条` : '0 条' }}</span>
            </div>
          </div>

          <div
            v-if="secondaryDiagnoses.length"
            class="tag-block"
          >
            <span class="tag-block__label">次诊断</span>
            <div class="tag-list">
              <span
                v-for="(item, idx) in secondaryDiagnoses.slice(0, 5)"
                :key="`${item.code || item.text}-${idx}`"
                class="tag-item"
              >
                {{ item.text || item.code || '未命名诊断' }}
              </span>
            </div>
          </div>
        </article>

        <article class="surface">
          <div class="panel-head panel-head--between">
            <h2>DRG / DIP 预判结果</h2>
            <div
              class="segmented segmented--compact"
              role="tablist"
              aria-label="分组类型"
            >
              <button
                type="button"
                class="segmented-item"
                :class="{ active: groupingType === 'DIP' }"
                :disabled="extracting || grouping || !hasExtractedData"
                @click="handleDIPGrouping"
              >
                DIP
              </button>
              <button
                type="button"
                class="segmented-item"
                :class="{ active: groupingType === 'DRG' }"
                :disabled="extracting || grouping || !hasExtractedData"
                @click="handleDRGGrouping"
              >
                DRG
              </button>
            </div>
          </div>

          <div
            v-if="drgResult"
            class="group-result"
          >
            <div class="group-result__top">
              <span class="group-badge">{{ drgResult.groupingType || groupingType }}</span>
              <h3>{{ drgResult.groupName || drgResult.name || '未返回分组' }}</h3>
              <p>{{ drgResult.message || '分组结果已生成，可继续核对费用结构与手术匹配。' }}</p>
            </div>

            <div class="metric-grid">
              <div class="metric-card">
                <span>权重 / 点数</span>
                <strong>{{ drgResult.weight || '--' }}</strong>
              </div>
              <div class="metric-card">
                <span>预估费用</span>
                <strong>{{ drgResult.payment !== '--' ? drgResult.payment?.toLocaleString() : '--' }}</strong>
              </div>
              <div class="metric-card">
                <span>实际费用</span>
                <strong>{{ drgResult.actual_cost !== '--' ? drgResult.actual_cost?.toLocaleString() : '--' }}</strong>
              </div>
              <div class="metric-card">
                <span>盈亏情况</span>
                <strong :class="profitClass">{{ drgResult.profit !== '--' ? drgResult.profit?.toLocaleString() : '--' }}</strong>
              </div>
            </div>
          </div>

          <div
            v-else
            class="empty-state"
          >
            <div class="empty-state__icon">
              DRG
            </div>
            <div class="empty-state__title">
              等待分组结果
            </div>
            <div class="empty-state__desc">
              完成抽取后可生成 DRG / DIP 结果与费用建议。
            </div>
          </div>
        </article>

        <article class="surface">
          <div class="panel-head">
            <h2>分组执行轨迹</h2>
          </div>
          <div
            v-if="drgResult && (drgResult.messages || []).length"
            class="trace-list"
          >
            <div
              v-for="(item, idx) in drgResult.messages || []"
              :key="idx"
              class="trace-item"
            >
              <div class="trace-item__title">
                步骤 {{ idx + 1 }}
              </div>
              <div
                class="trace-item__value"
                v-html="highlightCodes(item)"
              />
            </div>
          </div>
          <div
            v-else
            class="trace-empty"
          >
            暂无轨迹，执行 DRG/DIP 后自动记录。
          </div>
        </article>
      </aside>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import { performGrouping as localDrgGrouping } from '@/views/drg-grouper/drgGrouper'
import { performDipGrouping as localDipGrouping } from '@/views/drg-grouper/dipGrouper'
import { searchICD9Procedures } from '@/data/drg/mock-icd-codes'

const testCases = [
  {
    name: '冠心病合并高血压',
    admissionId: 'ZS-001',
    medical_text: `入院记录

患者张三，男，58岁，因“反复胸闷、胸痛1年，加重3天”入院。
现病史：患者1年前开始出现活动后胸闷、胸痛，休息后可缓解。近1周症状加重，夜间阵发性呼吸困难。
既往史：高血压病史10年，规律服用降压药物，无糖尿病史。
入院诊断：
1. 冠状动脉粥样硬化性心脏病
2. 心功能不全
3. 高血压病3级（极高危组）
手术情况：2026年1月2日行冠状动脉造影术及支架植入术。`,
  },
  {
    name: '急性阑尾炎手术',
    admissionId: 'LS-002',
    medical_text: `入院记录

患者李四，男，32岁，因“转移性右下腹痛6小时”入院。
现病史：6小时前无明显诱因出现脐周疼痛，后转移至右下腹，伴恶心、低热。
体格检查：T 37.8℃，右下腹麦氏点压痛、反跳痛阳性。
入院诊断：急性阑尾炎。
手术情况：2026年2月6日行腹腔镜阑尾切除术，手术顺利。`,
  },
  {
    name: '社区获得性肺炎',
    admissionId: 'WW-003',
    medical_text: `入院记录

患者王五，女，65岁，因“咳嗽咳痰伴发热3天”入院。
现病史：5天前受凉后出现咳嗽、咳黄痰，伴发热，体温最高39.2℃。
胸部CT：双下肺感染性病变。
入院诊断：社区获得性肺炎。
治疗经过：予头孢曲松抗感染、氨溴索化痰治疗，症状好转。`,
  },
]

const selectedCaseIndex = ref(0)
const medicalText = ref(testCases[0].medical_text)
const extracting = ref(false)
const grouping = ref(false)
const extractedData = ref<any>(null)
const drgResult = ref<any>(null)
const admissionId = ref<string | null>(testCases[0].admissionId)
const groupingType = ref<'DIP' | 'DRG'>('DIP')
const codeMappings = ref<Record<string, string>>({})

function isGroupingSuccess(status?: string): boolean {
  if (!status) return false
  return status.includes('成功') || status.toLowerCase().includes('success')
}

const hasExtractedData = computed(() => !!extractedData.value)
const currentCase = computed(() => testCases[selectedCaseIndex.value] || testCases[0])
const textLength = computed(() => (medicalText.value || '').replace(/\s+/g, '').length)

const currentStageLabel = computed(() => {
  if (grouping.value) return '分组中'
  if (drgResult.value) return '预判完成'
  if (extracting.value) return '抽取中'
  if (hasExtractedData.value) return '待分组'
  return '待抽取'
})

const mainDiagnosis = computed(() => {
  const diags = extractedData.value?.diagnoses
  if (!diags) return null
  const code = diags.discharge_main_icd || diags.admission_main_icd || ''
  const text = diags.discharge_main_diagnosis_text || diags.admission_main_diagnosis_text || ''
  return code || text ? { code, text, mappedCode: codeMappings.value[code] || '' } : null
})

const secondaryDiagnoses = computed(() => {
  const diags = extractedData.value?.diagnoses
  if (!diags) return []
  const codes = diags.discharge_other_icds || diags.admission_other_icds || []
  const texts = diags.discharge_other_diagnoses_texts || diags.admission_other_diagnoses_texts || []
  return texts
    .map((text: string, idx: number) => ({
      code: codes[idx] || '',
      text,
      mappedCode: codeMappings.value[codes[idx]] || '',
    }))
    .slice(0, 5)
})

const diagnosisCount = computed(() => (mainDiagnosis.value ? 1 : 0) + secondaryDiagnoses.value.length)

function firstNonEmptyString(...values: unknown[]): string {
  for (const value of values) {
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return ''
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter(Boolean)
}

function extractProcedureTextsFromMedicalText(text: string): string[] {
  if (!text) return []
  const matches = new Set<string>()
  const patterns = [
    /(?:行|施行)([^，。；\n]{2,40}?术)/g,
    /手术(?:情况|经过)?[:：]\s*([^，。；\n]{2,40}?术)/g,
  ]
  for (const pattern of patterns) {
    let match: RegExpExecArray | null = pattern.exec(text)
    while (match) {
      const candidate = (match[1] || '').trim()
      if (candidate && candidate.length <= 40) matches.add(candidate)
      match = pattern.exec(text)
    }
  }
  return Array.from(matches)
}

function inferProcedureCodeFromText(text: string): string {
  const normalized = (text || '').trim()
  if (!normalized) return ''

  // 先走关键词直连，覆盖本项目常见术式
  const keywordRules: Array<{ keywords: string[]; code: string }> = [
    { keywords: ['腹腔镜', '阑尾切除'], code: '47.0100' },
    { keywords: ['阑尾切除'], code: '47.0901' },
    { keywords: ['支架植入'], code: '36.0700' },
    { keywords: ['冠状动脉造影'], code: '88.5500' },
    { keywords: ['经皮冠状动脉介入'], code: '36.0700' },
  ]
  for (const rule of keywordRules) {
    if (rule.keywords.every((kw) => normalized.includes(kw))) return rule.code
  }

  // 再尝试 mock ICD-9 检索
  const candidates = searchICD9Procedures(normalized)
  if (candidates.length > 0) return candidates[0].code

  // 使用手术名称中的关键子串做降级检索
  const compact = normalized.replace(/术|手术|操作|及|与|行|腹腔镜/g, '').trim()
  if (compact.length >= 2) {
    const fallback = searchICD9Procedures(compact)
    if (fallback.length > 0) return fallback[0].code
  }
  return ''
}

function getNormalizedProcedures(data: any, sourceText: string): Array<{ code: string; text: string }> {
  const procs = data?.procedures || data?.surgeries || data?.operation || {}

  const mainCode = firstNonEmptyString(
    procs?.main_procedure_code,
    procs?.major_surgery_icd,
    procs?.major_surgery_code,
    procs?.main_surgery_code,
    procs?.main_operation_code,
  )
  const mainText = firstNonEmptyString(
    procs?.main_procedure_text,
    procs?.main_procedure_name,
    procs?.major_surgery_text,
    procs?.major_surgery_name,
    procs?.main_surgery_text,
    procs?.main_operation_text,
    procs?.main_operation_name,
    procs?.surgery_name,
  )

  const otherCodes = normalizeStringArray(
    procs?.other_procedure_codes
      || procs?.other_surgery_icds
      || procs?.other_surgery_codes
      || procs?.other_operation_codes,
  )
  const otherTexts = normalizeStringArray(
    procs?.other_procedure_texts
      || procs?.other_procedures_texts
      || procs?.other_surgery_texts
      || procs?.other_operation_texts
      || procs?.other_procedure_names,
  )

  const result: Array<{ code: string; text: string }> = []
  if (mainText) result.push({ code: mainCode || inferProcedureCodeFromText(mainText), text: mainText })

  otherTexts.forEach((text, idx) => {
    result.push({ code: otherCodes[idx] || inferProcedureCodeFromText(text), text })
  })

  const otherProcObjects = Array.isArray(procs?.other_procedures) ? procs.other_procedures : []
  otherProcObjects.forEach((item: any) => {
    const text = firstNonEmptyString(item?.text, item?.name, item?.surgery_name, item?.operation_name)
    const code = firstNonEmptyString(item?.code, item?.icd, item?.icd9, item?.surgery_code)
    if (text) result.push({ code: code || inferProcedureCodeFromText(text), text })
  })

  if (!result.length) {
    const fallbackTexts = extractProcedureTextsFromMedicalText(sourceText)
    fallbackTexts.forEach((text) => result.push({ code: inferProcedureCodeFromText(text), text }))
  }

  // 去重，避免字段重复映射导致重复展示
  const dedup = new Map<string, { code: string; text: string }>()
  result.forEach((item) => {
    const key = `${item.code}::${item.text}`
    if (!dedup.has(key)) dedup.set(key, item)
  })
  return Array.from(dedup.values()).slice(0, 5)
}

const procedures = computed(() => getNormalizedProcedures(extractedData.value, medicalText.value))

const profitClass = computed(() => {
  const profit = Number(drgResult.value?.profit)
  if (!Number.isFinite(profit)) return ''
  return profit >= 0 ? 'profit-positive' : 'profit-negative'
})

const highlightedMedicalText = computed(() => {
  if (!medicalText.value) return ''
  let html = medicalText.value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  const diagTerms: string[] = []
  if (mainDiagnosis.value?.text) diagTerms.push(mainDiagnosis.value.text)
  secondaryDiagnoses.value.forEach((item: { text?: string }) => {
    if (item.text) diagTerms.push(item.text)
  })

  const procTerms: string[] = []
  procedures.value.forEach((item: { text?: string }) => {
    if (item.text) procTerms.push(item.text)
  })

  const allTerms = [
    ...diagTerms.map((text) => ({ text, type: 'diag' as const })),
    ...procTerms.map((text) => ({ text, type: 'proc' as const })),
  ].sort((a, b) => b.text.length - a.text.length)

  for (const term of allTerms) {
    const escaped = term.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const cls = term.type === 'diag' ? 'hl-diag' : 'hl-proc'
    html = html.replace(new RegExp(escaped, 'g'), `<mark class="${cls}">${term.text}</mark>`)
  }

  return html.replace(/\n/g, '<br/>')
})

function highlightCodes(msg: string): string {
  return String(msg || '').replace(
    /([A-Z]\d{2}\.\d[\w.]*|\d{2}\.\d[\w.]*)/g,
    '<code class="trace-code">$1</code>',
  )
}

const handleCaseChange = (idx: number) => {
  selectedCaseIndex.value = idx
  medicalText.value = testCases[idx].medical_text
  extractedData.value = null
  drgResult.value = null
  admissionId.value = testCases[idx].admissionId
}

const handleExtract = async () => {
  if (!medicalText.value.trim()) {
    message.warning('请先输入病历文本')
    return
  }

  extracting.value = true
  try {
    const response = await fetch('/api/v1/case-front-page/extract-pre-group', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ medical_text: medicalText.value }),
    })
    const data = await response.json()

    if (response.ok && data.success && data.data) {
      extractedData.value = data.data
      admissionId.value = data.data.admission_id
      message.success('AI 智能抽取完成')
      await handleDIPGrouping()
    } else {
      message.error(data.error || data.detail || '抽取失败')
    }
  } catch (error) {
    console.error('Extract error:', error)
    message.error('AI 抽取服务暂不可用')
  } finally {
    extracting.value = false
  }
}

const handleDIPGrouping = async () => {
  if (!extractedData.value || extracting.value) {
    message.warning('请先完成 AI 抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DIP'

  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const proceduresData = extractedData.value.procedures || extractedData.value.surgeries || {}
    const costs = extractedData.value.costs || {}

    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes = diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = proceduresData.main_procedure_code || ''
    const otherProcCodes = proceduresData.other_procedure_codes || []

    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const fallbackProcCodes = procedures.value.map((item) => item.code).filter(Boolean)
    const ssList = Array.from(new Set([mainProcCode, ...otherProcCodes, ...fallbackProcCodes].filter(Boolean)))

    const dipResult = localDipGrouping({ zdList, ssList })

    if (isGroupingSuccess(dipResult.status)) {
      drgResult.value = {
        code: dipResult.dipCode || '未入组',
        name: dipResult.dipName || '未知病种',
        groupingType: 'DIP',
        weight: '--',
        payment: '--',
        actual_cost: costs.total_cost || 0,
        profit: '--',
        matchType: dipResult.matchType || '',
        messages: dipResult.messages,
      }
      message.success(`四川 DIP 入组成功: ${dipResult.dipCode}`)
    } else {
      drgResult.value = {
        code: '未入组',
        name: '无法匹配病种',
        groupingType: 'DIP',
        weight: '--',
        payment: '--',
        actual_cost: costs.total_cost || 0,
        profit: '--',
        messages: dipResult.messages,
      }
      message.warning('DIP 未能入组')
    }
  } catch (error) {
    console.error('DIP grouping error:', error)
    message.error('DIP 本地分组引擎执行失败')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}

const handleDRGGrouping = async () => {
  if (!extractedData.value || extracting.value) {
    message.warning('请先完成 AI 抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DRG'

  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const proceduresData = extractedData.value.procedures || extractedData.value.surgeries || {}
    const basicInfo = extractedData.value.basic_info || {}
    const costs = extractedData.value.costs || {}

    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes = diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = proceduresData.main_procedure_code || ''
    const otherProcCodes = proceduresData.other_procedure_codes || []

    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const fallbackProcCodes = procedures.value.map((item) => item.code).filter(Boolean)
    const ssList = Array.from(new Set([mainProcCode, ...otherProcCodes, ...fallbackProcCodes].filter(Boolean)))

    const drgGroupResult = await localDrgGrouping({
      gender: basicInfo.gender === '2' || basicInfo.gender_text === '女' ? '2' : '1',
      age: basicInfo.age_years || 50,
      zdList,
      ssList,
      days: 7,
    })

    const actualCost = costs.total_cost || 0

    if (isGroupingSuccess(drgGroupResult.status) && drgGroupResult.drg) {
      const rw = drgGroupResult.rw || 0
      const baselinePayment = Math.round(rw * 8000 * 100) / 100
      drgResult.value = {
        code: drgGroupResult.drg,
        name:
          drgGroupResult.drgName ||
          `MDC ${drgGroupResult.mdc || '--'} / ADRG ${drgGroupResult.adrg || '--'}`,
        groupingType: 'DRG',
        weight: rw,
        payment: baselinePayment,
        actual_cost: actualCost,
        profit: Math.round((baselinePayment - actualCost) * 100) / 100,
        messages: drgGroupResult.messages,
      }
      message.success(`四川 DRG 入组成功: ${drgGroupResult.drg} (RW=${rw})`)
    } else {
      drgResult.value = {
        code: '未入组',
        name: drgGroupResult.adrg ? `ADRG: ${drgGroupResult.adrg}` : '无法入组',
        groupingType: 'DRG',
        weight: 0,
        payment: 0,
        actual_cost: actualCost,
        profit: -actualCost,
        messages: drgGroupResult.messages,
      }
      message.warning('DRG 未能入组')
    }
  } catch (error) {
    console.error('DRG grouping error:', error)
    message.error('DRG 本地分组引擎执行失败')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
.pre-analysis-shell {
  --bg: #f3f6fb;
  --surface: #ffffff;
  --surface-soft: #f8fbff;
  --line: #d8e1ee;
  --text: #15233b;
  --text-muted: #62748f;
  --accent: #1f63f2;
  --accent-soft: #e8f0ff;
  --ok: #15803d;
  --bad: #dc2626;
  height: 100%;
  min-height: 100%;
  padding: 16px;
  background: linear-gradient(180deg, #f6f8fc 0%, var(--bg) 100%);
  color: var(--text);
  overflow-y: auto;
  box-sizing: border-box;
}

.command-header,
.status-zone,
.surface {
  border: 1px solid var(--line);
  border-radius: 16px;
  background: var(--surface);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.03);
}

.command-header {
  padding: 16px;
}

.header-main {
  display: flex;
  justify-content: space-between;
  gap: 14px;
}

.title-block h1 {
  margin: 0;
  font-size: 28px;
  line-height: 1.2;
  letter-spacing: -0.01em;
  font-weight: 900;
}

.title-block p {
  margin: 8px 0 0;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.7;
}

.action-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.btn {
  height: 36px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #bfd0ee;
  background: #fff;
  color: #2b4d8c;
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.btn:disabled,
.segmented-item:disabled,
.case-chip:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-ghost {
  background: var(--surface-soft);
}

.btn-icon {
  width: 16px;
  height: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e7eeff;
}

.segmented {
  display: inline-flex;
  border: 1px solid #bfd0ee;
  border-radius: 10px;
  overflow: hidden;
  background: #fff;
}

.segmented-item {
  height: 36px;
  min-width: 64px;
  border: 0;
  background: transparent;
  color: #315ea8;
  font-size: 13px;
  font-weight: 800;
  padding: 0 12px;
}

.segmented-item.active {
  background: var(--accent);
  color: #fff;
}

.segmented--compact .segmented-item {
  height: 32px;
  min-width: 56px;
}

.case-strip {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) 200px;
  gap: 8px;
}

.case-chip,
.active-case {
  min-height: 68px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  padding: 10px;
}

.case-chip {
  display: grid;
  align-content: center;
  text-align: left;
  gap: 3px;
}

.case-chip.active {
  border-color: #9bb9f3;
  background: var(--accent-soft);
}

.case-chip__id {
  font-size: 11px;
  font-weight: 700;
  color: #4c6ca5;
}

.case-chip__name {
  font-size: 16px;
  font-weight: 800;
  line-height: 1.25;
}

.active-case {
  display: grid;
  align-content: center;
  gap: 2px;
}

.active-case__label {
  font-size: 11px;
  color: var(--accent);
  font-weight: 700;
}

.active-case strong {
  font-size: 18px;
  line-height: 1.2;
}

.active-case span:last-child {
  font-size: 13px;
  color: var(--text-muted);
}

.status-zone {
  margin-top: 12px;
  padding: 14px;
}

.workflow-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.workflow-node {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 70px;
  padding: 10px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
}

.workflow-node.active {
  border-color: #a9c1f2;
  background: #eef5ff;
}

.workflow-node__index {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: #dce7fb;
  color: var(--accent);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
}

.workflow-node__title {
  font-size: 15px;
  font-weight: 800;
}

.workflow-node__desc {
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.snapshot-strip {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.snapshot-card {
  min-height: 72px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  padding: 10px;
}

.snapshot-card__label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
}

.snapshot-card strong {
  display: inline-block;
  margin-top: 6px;
  font-size: 22px;
  font-weight: 900;
  line-height: 1;
}

.snapshot-card small {
  margin-left: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.snapshot-card--status strong {
  color: var(--accent);
}

.workspace-grid {
  margin-top: 12px;
  display: grid;
  grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
  gap: 12px;
}

.surface {
  padding: 14px;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-head--between {
  justify-content: space-between;
}

.panel-head h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
  font-weight: 900;
  letter-spacing: -0.01em;
}

.reader-panel {
  min-height: 640px;
}

.reading-meta {
  height: 32px;
  border-radius: 999px;
  padding: 0 10px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #4f617f;
}

.reading-meta strong {
  color: var(--accent);
  font-size: 13px;
}

.reader-body {
  margin-top: 12px;
  height: calc(100% - 46px);
  border: 1px solid var(--line);
  border-radius: 12px;
  background: #fbfdff;
  overflow: hidden;
}

.reader-scroll {
  height: 100%;
  overflow: auto;
  padding: 14px 16px;
}

.medical-text {
  color: var(--text);
  font-size: 16px;
  line-height: 1.78;
  white-space: pre-wrap;
  word-break: break-word;
}

.medical-text :deep(mark.hl-diag) {
  background: #ffeab2;
  border-radius: 4px;
  padding: 0 2px;
}

.medical-text :deep(mark.hl-proc) {
  background: #d9e8ff;
  border-radius: 4px;
  padding: 0 2px;
}

.result-column {
  display: grid;
  gap: 12px;
  align-content: start;
}

.status-pill {
  height: 26px;
  border-radius: 999px;
  border: 1px solid #bdd0f5;
  background: #edf3ff;
  color: var(--accent);
  padding: 0 9px;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

.summary-list {
  margin-top: 10px;
  display: grid;
  gap: 8px;
}

.summary-row {
  min-height: 52px;
  border-radius: 12px;
  border: 1px solid var(--line);
  background: var(--surface-soft);
  padding: 10px;
  display: grid;
  grid-template-columns: 86px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
}

.summary-row__label {
  color: var(--text-muted);
  font-size: 13px;
}

.summary-row strong {
  font-size: 18px;
  font-weight: 800;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.summary-row__meta {
  font-size: 13px;
  color: var(--accent);
  font-weight: 700;
}

.tag-block {
  margin-top: 8px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface-soft);
  padding: 10px;
}

.tag-block__label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 700;
  margin-bottom: 6px;
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-item {
  height: 24px;
  border-radius: 999px;
  border: 1px solid #c1d6ff;
  background: #ebf3ff;
  color: #2f5ba7;
  font-size: 12px;
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
}

.group-result {
  margin-top: 10px;
  border-radius: 12px;
  border: 1px solid #c2d4f5;
  background: #f5f9ff;
  padding: 10px;
}

.group-result__top h3 {
  margin: 6px 0 0;
  font-size: 20px;
  line-height: 1.2;
  font-weight: 900;
}

.group-result__top p {
  margin: 6px 0 0;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
}

.group-badge {
  height: 22px;
  border-radius: 999px;
  background: #dee9ff;
  color: #2255a9;
  font-size: 12px;
  font-weight: 800;
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
}

.metric-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.metric-card {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #fff;
  padding: 9px 10px;
}

.metric-card span {
  font-size: 12px;
  color: var(--text-muted);
}

.metric-card strong {
  display: block;
  margin-top: 6px;
  font-size: 17px;
  line-height: 1.1;
  font-weight: 900;
}

.profit-positive {
  color: var(--ok);
}

.profit-negative {
  color: var(--bad);
}

.trace-list {
  margin-top: 8px;
  display: grid;
  gap: 8px;
}

.trace-item {
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface-soft);
  padding: 9px 10px;
}

.trace-item__title {
  font-size: 12px;
  color: #3e629f;
  font-weight: 700;
}

.trace-item__value {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.65;
  color: #31445f;
}

.trace-empty {
  margin-top: 10px;
  border: 1px dashed #c2d3ee;
  border-radius: 10px;
  background: #f8fbff;
  color: var(--text-muted);
  font-size: 13px;
  line-height: 1.6;
  padding: 12px;
}

.empty-state {
  margin-top: 10px;
  border: 1px dashed #c2d3ee;
  border-radius: 12px;
  background: #f8fbff;
  min-height: 170px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.empty-state__icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #dce8ff;
  color: #2958b4;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 800;
}

.empty-state__title {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 900;
}

.empty-state__desc {
  margin-top: 5px;
  max-width: 300px;
  color: var(--text-muted);
  font-size: 13px;
}

.medical-text :deep(code.trace-code) {
  background: #edf2ff;
  border-radius: 4px;
  padding: 1px 4px;
  color: #274e96;
}

@media (max-width: 1180px) {
  .header-main {
    flex-direction: column;
  }
  .action-bar {
    align-items: center;
    justify-content: space-between;
  }
  .case-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .active-case {
    grid-column: span 2;
  }
  .snapshot-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .pre-analysis-shell {
    padding: 12px;
  }
  .title-block h1 {
    font-size: 24px;
  }
  .panel-head h2 {
    font-size: 18px;
  }
  .case-strip,
  .workflow-rail,
  .snapshot-strip,
  .metric-grid {
    grid-template-columns: 1fr;
  }
  .active-case {
    grid-column: auto;
  }
  .action-bar {
    flex-wrap: wrap;
  }
  .summary-row {
    grid-template-columns: 1fr;
  }
  .medical-text {
    font-size: 15px;
  }
}
</style>
