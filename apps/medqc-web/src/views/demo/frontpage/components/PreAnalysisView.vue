<template>
  <div class="pre-analysis-shell">
    <section class="analysis-command">
      <div class="analysis-command__main">
        <div class="analysis-command__title-row">
          <div>
            <h1>病历抽取与 DRG / DIP 预判</h1>
            <p>
              把原始病历阅读、主诊断校验和分组预判收在同一个工作台里，先看文书，再做结构化判断。
            </p>
          </div>
          <div class="command-status">
            <strong>{{ currentCase.admissionId }}</strong>
            <span>{{ currentCase.name }}</span>
          </div>
        </div>

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
                先确认原始文本和手术场景
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
                沉淀主诊断、手术和费用字段
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
                DRG / DIP 预判
              </div>
              <div class="workflow-node__desc">
                输出分组结果与费用判断
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="analysis-command__side">
        <div
          class="case-switcher"
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
            <span class="case-chip__meta">{{ item.admissionId || `病例 ${index + 1}` }}</span>
            <span class="case-chip__name">{{ item.name }}</span>
          </button>
        </div>
        <div class="toolbar-actions">
          <button
            type="button"
            class="ghost-button"
            :disabled="extracting"
            @click="handleExtract"
          >
            <span class="primary-action__icon">⚡</span>
            <span>{{ extracting ? '抽取中' : '开始抽取' }}</span>
          </button>
          <button
            type="button"
            class="primary-action primary-action--compact"
            :disabled="grouping || !hasExtractedData"
            @click="handleDRGGrouping"
          >
            <span class="primary-action__icon">⚡</span>
            <span>{{ grouping ? '分组中' : 'DRG 分组' }}</span>
          </button>
        </div>
      </div>
    </section>

    <div class="pre-analysis-grid">
      <section class="surface-card surface-card--medical">
        <div class="panel-head panel-head--reading">
          <div>
            <h2>原始病历内容</h2>
          </div>
          <div class="reading-actions">
            <div class="medical-toolbar">
              <span class="medical-toolbar__label">当前病案</span>
              <span class="medical-toolbar__value">{{ currentCase.admissionId }}</span>
              <span class="medical-toolbar__dot" />
              <span class="medical-toolbar__value">{{ currentCase.name }}</span>
            </div>
            <button
              v-if="hasExtractedData"
              type="button"
              class="ghost-button ghost-button--soft"
              @click="extractedData = null"
            >
              清空结构化结果
            </button>
          </div>
        </div>

        <div class="medical-frame">
          <div class="medical-frame__scroll">
            <div
              class="medical-text"
              v-html="highlightedMedicalText"
            />
          </div>
        </div>
      </section>

      <section class="results-column">
        <article class="surface-card surface-card--panel">
          <div class="panel-head panel-head--tight">
            <div>
              <h2>主诊断与手术 / 操作</h2>
            </div>
            <span class="status-pill status-pill--blue">{{
              hasExtractedData ? '已同步' : '等待抽取'
            }}</span>
          </div>

          <div class="console-list">
            <div class="console-row">
              <span class="console-row__label">主诊断</span>
              <strong>{{
                hasExtractedData && mainDiagnosis
                  ? mainDiagnosis.text || mainDiagnosis.code || '已抽取'
                  : '等待抽取'
              }}</strong>
              <span class="console-row__meta">编码 {{ mainDiagnosis?.code || '--' }}</span>
            </div>
            <div class="console-row">
              <span class="console-row__label">手术 / 操作</span>
              <strong>{{ procedures.length ? procedures[0].text || '已抽取' : '等待抽取' }}</strong>
              <span class="console-row__meta">{{
                hasExtractedData ? `${procedures.length} 条` : '0 条'
              }}</span>
            </div>
          </div>
        </article>

        <section class="surface-card surface-card--grouping">
          <div class="panel-head panel-head--tight">
            <div>
              <h2>DRG / DIP 预判结果</h2>
            </div>
            <div class="group-actions">
              <button
                type="button"
                class="ghost-button ghost-button--soft"
                :disabled="grouping || !hasExtractedData"
                @click="handleDIPGrouping"
              >
                DIP
              </button>
              <button
                type="button"
                class="primary-action primary-action--compact"
                :disabled="grouping || !hasExtractedData"
                @click="handleDRGGrouping"
              >
                <span class="primary-action__icon">⚡</span>
                <span>{{ grouping ? '分组中' : 'DRG' }}</span>
              </button>
            </div>
          </div>

          <div
            v-if="drgResult"
            class="group-summary"
          >
            <div class="group-summary__top">
              <div>
                <div class="group-summary__badge">
                  {{ drgResult.groupingType || groupingType }}
                </div>
                <div class="group-summary__name">
                  {{ drgResult.groupName || drgResult.name || '未返回分组' }}
                </div>
              </div>
              <div class="group-summary__meta">
                {{
                  drgResult.message || '分组结果已生成，可继续核对费用结构、手术匹配和主诊断归类。'
                }}
              </div>
            </div>

            <div class="metric-grid metric-grid--grouping">
              <div class="metric-card">
                <span>权重 / 点数</span>
                <strong>{{ drgResult.weight || '--' }}</strong>
              </div>
              <div class="metric-card">
                <span>预估费用</span>
                <strong>{{
                  drgResult.payment !== '--' ? drgResult.payment?.toLocaleString() : '--'
                }}</strong>
              </div>
              <div class="metric-card">
                <span>实际费用</span>
                <strong>{{
                  drgResult.actual_cost !== '--' ? drgResult.actual_cost?.toLocaleString() : '--'
                }}</strong>
              </div>
              <div class="metric-card">
                <span>盈亏情况</span>
                <strong>{{
                  drgResult.profit !== '--' ? drgResult.profit?.toLocaleString() : '--'
                }}</strong>
              </div>
            </div>
          </div>

          <div
            v-if="drgResult"
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
            class="empty-state"
          >
            <div class="empty-state__icon">
              DRG
            </div>
            <div class="empty-state__title">
              等待分组结果
            </div>
            <div class="empty-state__desc">
              完成病历抽取后即可生成 DRG / DIP 结果与费用建议。
            </div>
          </div>
        </section>
      </section>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  CalculatorOutlined,
  CheckCircleOutlined,
  FileTextOutlined,
  LoadingOutlined,
  ScissorOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import { performGrouping as localDrgGrouping } from '@/views/drg-grouper/drgGrouper'
import { performDipGrouping as localDipGrouping } from '@/views/drg-grouper/dipGrouper'

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

const procedures = computed(() => {
  const procs = extractedData.value?.procedures || extractedData.value?.surgeries
  if (!procs) return []

  const mainCode = procs.main_procedure_code || procs.major_surgery_icd || ''
  const mainText = procs.main_procedure_text || procs.major_surgery_text || ''
  const otherCodes = procs.other_procedure_codes || procs.other_surgery_icds || []
  const otherTexts = procs.other_procedure_texts || procs.other_surgery_texts || []

  const result: Array<{ code: string; text: string }> = []
  if (mainText) result.push({ code: mainCode, text: mainText })
  otherTexts.forEach((text: string, idx: number) => {
    result.push({ code: otherCodes[idx] || '', text })
  })
  return result.slice(0, 5)
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
  return msg.replace(
    /([A-Z]\d{2}\.\d[\w.]*|\d{2}\.\d[\w.]*)/g,
    '<code class="trace-code">$1</code>',
  )
}

const handleCaseChange = (idx: number) => {
  medicalText.value = testCases[idx].medical_text
  extractedData.value = null
  drgResult.value = null
  admissionId.value = null
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
  if (!extractedData.value) {
    message.warning('请先完成 AI 抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DIP'

  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const proceduresData = extractedData.value.procedures || {}
    const costs = extractedData.value.costs || {}

    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes =
      diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = proceduresData.main_procedure_code || ''
    const otherProcCodes = proceduresData.other_procedure_codes || []

    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const ssList = [mainProcCode, ...otherProcCodes].filter(Boolean)

    const dipResult = localDipGrouping({ zdList, ssList })

    if (isGroupingSuccess(dipResult.status)) {
      drgResult.value = {
        code: dipResult.dipCode || '未入组',
        name: dipResult.dipName || '未知病种',
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
  if (!extractedData.value) {
    message.warning('请先完成 AI 抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DRG'

  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const proceduresData = extractedData.value.procedures || {}
    const basicInfo = extractedData.value.basic_info || {}
    const costs = extractedData.value.costs || {}

    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes =
      diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = proceduresData.main_procedure_code || ''
    const otherProcCodes = proceduresData.other_procedure_codes || []

    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const ssList = [mainProcCode, ...otherProcCodes].filter(Boolean)

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
  min-height: 100%;
  padding: 18px 20px 22px;
  background:
    radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 26%),
    linear-gradient(180deg, #f6f9ff 0%, #eef4ff 52%, #edf2fb 100%);
  color: #0f172a;
}

.analysis-command {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: 18px;
  padding: 18px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 255, 0.94));
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.05);
}

.analysis-command__main {
  flex: 1;
  min-width: 0;
}
.analysis-command__side {
  display: flex;
  width: min(440px, 42%);
  min-width: 320px;
  flex-direction: column;
  gap: 12px;
}
.analysis-command__title-row {
  margin-top: 10px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
.analysis-command h1 {
  margin: 0;
  font-size: 32px;
  line-height: 1.08;
  font-weight: 900;
  letter-spacing: -0.04em;
}
.analysis-command p {
  margin: 10px 0 0;
  max-width: 760px;
  color: #64748b;
  font-size: 14px;
  line-height: 1.72;
}
.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
}
.eyebrow-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  height: 18px;
  padding: 0 7px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.14);
  color: #1d4ed8;
  font-size: 10px;
  letter-spacing: 0.04em;
}

.command-status {
  display: grid;
  flex-shrink: 0;
  gap: 2px;
  min-width: 168px;
  padding: 12px 14px;
  border-radius: 18px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.92), rgba(255, 255, 255, 0.96));
}
.command-status__label {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2563eb;
}
.command-status strong {
  font-size: 16px;
  line-height: 1.2;
  color: #0f172a;
}
.command-status span:last-child {
  color: #64748b;
  font-size: 13px;
}

.workflow-rail {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 18px;
}
.workflow-node {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 14px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(255, 255, 255, 0.72);
  color: #64748b;
}
.workflow-node.active {
  border-color: rgba(37, 99, 235, 0.18);
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.08), rgba(255, 255, 255, 0.98));
  box-shadow: 0 12px 22px rgba(37, 99, 235, 0.06);
}
.workflow-node__index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 12px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}
.workflow-node__title {
  font-size: 14px;
  font-weight: 800;
  color: #0f172a;
}
.workflow-node__desc {
  margin-top: 1px;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
}

.case-switcher {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.case-chip {
  display: grid;
  gap: 4px;
  min-height: 78px;
  padding: 12px 13px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.94);
  color: #475569;
  text-align: left;
  transition: all 0.18s ease;
}
.case-chip:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.22);
  box-shadow: 0 10px 22px rgba(37, 99, 235, 0.1);
}
.case-chip.active {
  border-color: rgba(37, 99, 235, 0.24);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.94), rgba(255, 255, 255, 0.98));
  color: #1d4ed8;
  box-shadow: inset 0 0 0 1px rgba(37, 99, 235, 0.08);
}
.case-chip__meta {
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  opacity: 0.72;
}
.case-chip__name {
  font-size: 16px;
  line-height: 1.25;
  font-weight: 800;
  color: #0f172a;
}
.toolbar-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.pre-analysis-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(360px, 0.88fr);
  gap: 14px;
  margin-top: 14px;
}
.results-column {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.coding-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
.surface-card {
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 251, 255, 0.96));
  box-shadow: 0 14px 32px rgba(15, 23, 42, 0.04);
}
.surface-card--medical {
  padding: 16px;
  min-height: 720px;
}
.surface-card--small {
  padding: 14px;
  min-height: 154px;
}
.surface-card--grouping {
  padding: 16px;
  min-height: 520px;
}
.surface-card--panel {
  padding: 16px;
}
.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.panel-head--tight,
.panel-head--compact {
  align-items: center;
}
.panel-head--reading {
  align-items: flex-start;
}
.panel-kicker {
  font-size: 12px;
  font-weight: 800;
  color: #2563eb;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.panel-head h2 {
  margin: 4px 0 0;
  font-size: 17px;
  line-height: 1.2;
  font-weight: 800;
  color: #0f172a;
}

.ghost-button,
.primary-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 38px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid rgba(37, 99, 235, 0.14);
  background: rgba(255, 255, 255, 0.94);
  color: #1d4ed8;
  font-size: 13px;
  font-weight: 700;
}
.ghost-button--soft {
  background: rgba(37, 99, 235, 0.05);
}
.primary-action {
  border-color: transparent;
  background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
  color: #fff;
  box-shadow: 0 12px 26px rgba(37, 99, 235, 0.2);
}
.primary-action--compact {
  height: 36px;
  padding: 0 13px;
}
.primary-action__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.16);
  font-size: 12px;
}

.reading-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 10px;
}
.medical-toolbar {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.06);
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}
.medical-toolbar__label {
  color: #2563eb;
  font-weight: 800;
}
.medical-toolbar__value {
  color: #0f172a;
}
.medical-toolbar__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #cbd5e1;
}
.medical-frame {
  margin-top: 14px;
  height: calc(100% - 84px);
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(247, 250, 255, 0.98));
  overflow: hidden;
}
.medical-frame__scroll {
  height: 100%;
  overflow: auto;
  padding: 16px 18px;
}
.medical-text {
  color: #0f172a;
  font-size: 14px;
  line-height: 1.85;
  white-space: pre-wrap;
  word-break: break-word;
}
.medical-text :deep(.highlight-code) {
  background: rgba(37, 99, 235, 0.1);
  color: #1d4ed8;
  padding: 0 2px;
  border-radius: 4px;
}

.console-list {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}
.console-row {
  display: grid;
  grid-template-columns: 82px minmax(0, 1fr) auto;
  gap: 10px;
  align-items: center;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(248, 250, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.1);
}
.console-row__label {
  font-size: 12px;
  color: #64748b;
}
.console-row strong {
  font-size: 14px;
  color: #0f172a;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.console-row__meta {
  font-size: 12px;
  color: #2563eb;
  font-weight: 700;
}

.group-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.group-summary {
  margin-top: 12px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: rgba(248, 251, 255, 0.96);
}
.group-summary__top {
  display: grid;
  gap: 8px;
}
.group-summary__badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  font-size: 12px;
  font-weight: 800;
}
.group-summary__name {
  margin-top: 6px;
  font-size: 17px;
  font-weight: 800;
  color: #0f172a;
}
.group-summary__meta {
  color: #64748b;
  font-size: 13px;
  line-height: 1.6;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.metric-grid--grouping {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.metric-card {
  padding: 12px 13px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.1);
}
.metric-card span {
  display: block;
  font-size: 12px;
  color: #64748b;
}
.metric-card strong {
  display: block;
  margin-top: 8px;
  font-size: 18px;
  line-height: 1;
  color: #0f172a;
}
.trace-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}
.trace-item {
  padding: 12px 13px;
  border-radius: 14px;
  background: rgba(248, 250, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.1);
}
.trace-item__title {
  font-size: 12px;
  font-weight: 800;
  color: #2563eb;
}
.trace-item__value {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.68;
  color: #334155;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 310px;
  margin-top: 12px;
  border-radius: 18px;
  border: 1px dashed rgba(37, 99, 235, 0.18);
  background: rgba(248, 251, 255, 0.8);
  text-align: center;
}
.empty-state__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 18px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.empty-state__title {
  margin-top: 14px;
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
}
.empty-state__desc {
  margin-top: 8px;
  max-width: 320px;
  color: #64748b;
  font-size: 13px;
  line-height: 1.7;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.status-pill--blue {
  background: rgba(37, 99, 235, 0.08);
  color: #2563eb;
  border: 1px solid rgba(37, 99, 235, 0.1);
}

@media (max-width: 1180px) {
  .analysis-command {
    flex-direction: column;
  }
  .analysis-command__side {
    width: 100%;
    min-width: 0;
  }
  .case-switcher {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .analysis-command__title-row {
    flex-direction: column;
  }
  .pre-analysis-grid {
    grid-template-columns: 1fr;
  }
  .surface-card--medical {
    min-height: 580px;
  }
}

@media (max-width: 960px) {
  .pre-analysis-shell {
    padding: 14px;
  }
  .analysis-command {
    padding: 14px;
  }
  .analysis-command h1 {
    font-size: 26px;
  }
  .analysis-command__side {
    align-items: stretch;
  }
  .case-switcher {
    grid-template-columns: 1fr;
  }
  .toolbar-actions {
    flex-wrap: wrap;
  }
  .workflow-rail,
  .coding-grid,
  .metric-grid,
  .metric-grid--grouping {
    grid-template-columns: 1fr;
  }
  .console-row {
    grid-template-columns: 1fr;
  }
  .panel-head--reading,
  .reading-actions {
    align-items: stretch;
  }
}
</style>
