<template>
  <div class="pre-analysis h-full flex flex-col overflow-y-auto custom-scrollbar">
    <!-- Compact Header -->
    <div class="header-bar">
      <div class="header-left">
        <div class="header-icon">
          <ThunderboltOutlined />
        </div>
        <div>
          <h2 class="header-title">事前分析</h2>
          <p class="header-desc">AI 病历智能抽取 → ICD 自动编码 → DRG/DIP 预分组</p>
        </div>
      </div>
      <div class="header-actions">
        <a-select 
          v-model:value="selectedCaseIndex" 
          placeholder="选择测试病历"
          style="width: 180px"
          @change="handleCaseChange"
          size="middle"
        >
          <a-select-option v-for="(tc, idx) in testCases" :key="idx" :value="idx">
            {{ tc.name }}
          </a-select-option>
        </a-select>
        <button 
          @click="handleExtract"
          :disabled="!medicalText || extracting"
          class="extract-btn"
        >
          <LoadingOutlined v-if="extracting" class="animate-spin" />
          <ThunderboltOutlined v-else />
          {{ extracting ? 'AI抽取中...' : 'AI 智能抽取' }}
        </button>
      </div>
    </div>

    <!-- Main Content: 2-column -->
    <div class="main-grid">
      <!-- Left: Medical Record -->
      <div class="panel-card medical-panel">
        <div class="panel-header">
          <svg class="panel-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
          </svg>
          <span class="panel-title">原始病历文本</span>
          <span v-if="hasExtractedData" class="ai-tag">AI 已解析</span>
          <span class="text-counter">{{ medicalText.length }} 字</span>
        </div>
        <!-- 未提取时：可编辑 textarea -->
        <a-textarea
          v-if="!hasExtractedData"
          v-model:value="medicalText"
          placeholder="请输入或粘贴病历文本，或从上方选择测试病历..."
          :rows="20"
          class="medical-textarea"
        />
        <!-- 提取完成后：带 NLP 实体高亮的只读视图 -->
        <div v-else class="medical-highlight-view custom-scrollbar" @dblclick="hasExtractedData && (extractedData = null)">
          <div class="highlight-text" v-html="highlightedMedicalText"></div>
        </div>
      </div>

      <!-- Right: Results -->
      <div class="results-column">
        <!-- Diagnosis & Surgery Row -->
        <div class="coding-row">
          <!-- Diagnosis -->
          <div class="panel-card coding-panel">
            <div class="panel-header">
              <svg class="panel-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>
              </svg>
              <span class="panel-title">提取诊断</span>
              <span v-if="hasExtractedData && mainDiagnosis" class="badge-count">{{ 1 + secondaryDiagnoses.length }}</span>
            </div>
            <div class="coding-list custom-scrollbar">
              <template v-if="hasExtractedData">
                <!-- Main Diagnosis — 高亮主诊断卡片 -->
                <div v-if="mainDiagnosis" class="diag-item diag-main">
                  <div class="diag-left-bar blue"></div>
                  <div class="diag-badge">主</div>
                  <div class="diag-info">
                    <div class="diag-name">{{ mainDiagnosis.text }}</div>
                    <div class="diag-code-chip blue">{{ mainDiagnosis.code || '待编码' }}</div>
                  </div>
                </div>
                <!-- Secondary Diagnoses -->
                <div v-for="(diag, idx) in secondaryDiagnoses" :key="idx" class="diag-item">
                  <div class="diag-num">{{ idx + 2 }}</div>
                  <div class="diag-info">
                    <div class="diag-name">{{ diag.text }}</div>
                    <div class="diag-code-chip muted">{{ diag.code || '-' }}</div>
                  </div>
                </div>
                <div v-if="!mainDiagnosis && secondaryDiagnoses.length === 0" class="empty-state-inline">
                  暂无诊断数据
                </div>
              </template>
              <!-- 优雅空状态 -->
              <div v-else class="empty-state-box">
                <FileTextOutlined class="empty-state-icon" />
                <span>等待 AI 抽取</span>
              </div>
            </div>
          </div>

          <!-- Surgery -->
          <div class="panel-card coding-panel">
            <div class="panel-header">
              <svg class="panel-icon-svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.121 14.121L19 19m-7-7l7-7m-7 7l-2.879 2.879M12 12L9.121 9.121m0 5.758a3 3 0 10-4.243 4.243 3 3 0 004.243-4.243zm0-5.758a3 3 0 10-4.243-4.243 3 3 0 004.243 4.243z"/>
              </svg>
              <span class="panel-title">手术/操作</span>
              <span v-if="hasExtractedData && procedures.length" class="badge-count amber">{{ procedures.length }}</span>
            </div>
            <div class="coding-list custom-scrollbar">
              <template v-if="hasExtractedData">
                <div v-for="(proc, idx) in procedures" :key="idx" :class="['diag-item', idx === 0 ? 'proc-main' : '']">
                  <div v-if="idx === 0" class="diag-left-bar amber"></div>
                  <div :class="idx === 0 ? 'diag-badge amber' : 'diag-num'">{{ idx === 0 ? '主' : idx + 1 }}</div>
                  <div class="diag-info">
                    <div class="diag-name">{{ proc.text }}</div>
                    <div :class="['diag-code-chip', idx === 0 ? 'amber' : 'muted']">{{ proc.code || '-' }}</div>
                  </div>
                </div>
                <div v-if="procedures.length === 0" class="empty-state-box subtle">
                  <ScissorOutlined class="empty-state-icon-sm" />
                  <span>病历中未提取到手术数据</span>
                </div>
              </template>
              <!-- 优雅空状态 -->
              <div v-else class="empty-state-box">
                <ScissorOutlined class="empty-state-icon" />
                <span>等待 AI 抽取</span>
              </div>
            </div>
          </div>
        </div>

        <!-- ===== DRG/DIP 入组预测（重构核心）===== -->
        <div class="panel-card grouping-panel">
          <div class="panel-header">
            <svg class="panel-icon-svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#6366f1" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 16A8 8 0 014 8h16a8 8 0 010 8H4z"/>
              <circle cx="8" cy="12" r="1"/>
              <circle cx="12" cy="12" r="1"/>
              <circle cx="16" cy="12" r="1"/>
            </svg>
            <span class="panel-title-lg">入组预测分析</span>
            <!-- Segmented tabs -->
            <div class="grouping-tabs">
              <button 
                @click="handleDIPGrouping"
                :disabled="grouping || !hasExtractedData"
                :class="['grouping-tab', groupingType === 'DIP' && drgResult ? 'active-dip' : '']"
              >
                <LoadingOutlined v-if="grouping && groupingType === 'DIP'" class="animate-spin" />
                四川省 DIP
              </button>
              <button 
                @click="handleDRGGrouping"
                :disabled="grouping || !hasExtractedData"
                :class="['grouping-tab', groupingType === 'DRG' && drgResult ? 'active-drg' : '']"
              >
                <LoadingOutlined v-if="grouping && groupingType === 'DRG'" class="animate-spin" />
                四川省 DRG
              </button>
            </div>
          </div>

          <!-- Result Display -->
          <div v-if="drgResult" class="grouping-result">
            <!-- 上部：渐变编码卡片 + 财务微型看板 -->
            <div class="result-hero-row">
              <!-- 高级渐变编码卡片 -->
              <div :class="['hero-code-card', groupingType === 'DIP' ? 'emerald' : 'blue']">
                <div class="hero-glow"></div>
                <div class="hero-label">{{ groupingType }} 预测组编码</div>
                <div class="hero-value">{{ drgResult.code }}</div>
                <div class="hero-name">{{ drgResult.name }}</div>
                <div class="hero-tags">
                  <span v-if="drgResult.weight && drgResult.weight !== '--'" class="hero-tag">RW {{ drgResult.weight }}</span>
                  <span v-if="drgResult.matchType" class="hero-tag">{{ drgResult.matchType }}</span>
                </div>
              </div>

              <!-- 财务微型看板 — 3 列 -->
              <div class="finance-grid">
                <div class="finance-card">
                  <div class="finance-label">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v4m0 4h.01"/></svg>
                    预估支付
                  </div>
                  <div :class="['finance-value', drgResult.payment !== '--' ? 'green' : '']">
                    <template v-if="drgResult.payment !== '--'">
                      <span class="finance-unit">¥</span><span>{{ drgResult.payment?.toLocaleString() }}</span>
                    </template>
                    <template v-else><span class="finance-placeholder">--</span></template>
                  </div>
                </div>
                <div class="finance-card">
                  <div class="finance-label">实际费用</div>
                  <div class="finance-value">
                    <span class="finance-unit">¥</span><span>{{ drgResult.actual_cost?.toLocaleString() || '0' }}</span>
                  </div>
                </div>
                <div class="finance-card">
                  <div class="finance-label">预估盈亏</div>
                  <div :class="['finance-value', typeof drgResult.profit === 'number' ? (drgResult.profit >= 0 ? 'green' : 'red') : '']">
                    <template v-if="drgResult.profit !== '--'">
                      <span>{{ drgResult.profit >= 0 ? '+' : '' }}</span><span class="finance-unit">¥</span><span>{{ drgResult.profit?.toLocaleString() }}</span>
                    </template>
                    <template v-else><span class="finance-placeholder">--</span></template>
                  </div>
                </div>
              </div>
            </div>

            <!-- 执行日志 — 代码化风格 -->
            <div v-if="drgResult.messages?.length" class="trace-section">
              <div class="trace-title">入组判定过程 (Execution Trace)</div>
              <div class="trace-list">
                <div v-for="(msg, idx) in drgResult.messages" :key="idx" class="trace-item">
                  <svg class="trace-check" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M9 12l2 2 4-4"/>
                    <circle cx="12" cy="12" r="9"/>
                  </svg>
                  <span v-html="highlightCodes(msg)"></span>
                </div>
              </div>
            </div>
          </div>

          <!-- Empty State -->
          <div v-else class="grouping-empty">
            <div class="grouping-empty-icon">
              <CalculatorOutlined />
            </div>
            <p>{{ hasExtractedData ? '点击上方按钮进行 DRG/DIP 入组预测' : 'AI 抽取完成后自动进行入组预测' }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import { 
  FileSearchOutlined, 
  FileTextOutlined, 
  MedicineBoxOutlined, 
  ScissorOutlined, 
  AppstoreOutlined,
  CalculatorOutlined,
  SyncOutlined,
  LoadingOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue'

// 本地分组引擎
import { performGrouping as localDrgGrouping, getMdcName } from '@/views/drg-grouper/drgGrouper'
import { performDipGrouping as localDipGrouping } from '@/views/drg-grouper/dipGrouper'

// Test cases
const testCases = [
  {
    name: '高血压合并冠心病',
    medical_text: `入院记录

患者张三，男，58岁，因"反复胸闷、心悸3年，加重1周"于2026年1月1日入院。

现病史：患者3年前开始出现胸闷、心悸症状，活动后加重，休息后可缓解。近1周上述症状加重，夜间阵发性呼吸困难，双下肢轻度水肿。

既往史：高血压病史10年，血压最高180/110mmHg，规律服用降压药物。无糖尿病史。

入院诊断：
1. 冠状动脉粥样硬化性心脏病
2. 心功能III级
3. 高血压病3级（极高危）

手术情况：2026年1月3日行冠状动脉造影术+支架植入术。

出院诊断：冠心病、心力衰竭、高血压病3级`
  },
  {
    name: '急性阑尾炎手术',
    medical_text: `入院记录

患者李四，男，32岁，因"转移性右下腹痛6小时"入院。

现病史：6小时前无明显诱因出现脐周疼痛，后转移至右下腹，持续性疼痛，伴恶心、低热。

体格检查：T 37.8℃，右下腹麦氏点压痛、反跳痛阳性。

入院诊断：急性阑尾炎

手术情况：2026年1月2日行腹腔镜阑尾切除术，手术顺利。

出院诊断：急性化脓性阑尾炎`
  },
  {
    name: '肺炎住院治疗',
    medical_text: `入院记录

患者王五，女，65岁，因"咳嗽咳痰伴发热5天"入院。

现病史：5天前受凉后出现咳嗽，咳黄色粘痰，伴发热，体温最高39.2℃。

胸部CT：双下肺感染性病变。

入院诊断：社区获得性肺炎

治疗经过：予头孢曲松抗感染、氨溴索化痰治疗，症状好转。

出院诊断：社区获得性肺炎（双下肺）`
  }
]

// State
const selectedCaseIndex = ref<number | undefined>(undefined)
const medicalText = ref('')
const extracting = ref(false)
const grouping = ref(false)
const extractedData = ref<any>(null)
const drgResult = ref<any>(null)
const admissionId = ref<string | null>(null)
const groupingType = ref<'DIP' | 'DRG'>('DIP')
const codeMappings = ref<Record<string, string>>({})

// Computed
const hasExtractedData = computed(() => !!extractedData.value)

const mainDiagnosis = computed(() => {
  if (!extractedData.value?.diagnoses) return null
  const code = extractedData.value.diagnoses.discharge_main_icd || extractedData.value.diagnoses.admission_main_icd
  const text = extractedData.value.diagnoses.discharge_main_diagnosis_text || extractedData.value.diagnoses.admission_main_diagnosis_text
  const mappedCode = codeMappings.value[code] || ''
  return code || text ? { code, text, mappedCode } : null
})

const secondaryDiagnoses = computed(() => {
  if (!extractedData.value?.diagnoses) return []
  const codes = extractedData.value.diagnoses.discharge_other_icds || extractedData.value.diagnoses.admission_other_icds || []
  const texts = extractedData.value.diagnoses.discharge_other_diagnoses_texts || extractedData.value.diagnoses.admission_other_diagnoses_texts || []
  return texts.map((text: string, i: number) => ({
    code: codes[i] || '',
    text,
    mappedCode: codeMappings.value[codes[i]] || ''
  })).slice(0, 5)
})

const procedures = computed(() => {
  const procs = extractedData.value?.procedures || extractedData.value?.surgeries
  if (!procs) return []
  
  const mainCode = procs.main_procedure_code || procs.major_surgery_icd || ''
  const mainText = procs.main_procedure_text || procs.major_surgery_text || ''
  const otherCodes = procs.other_procedure_codes || procs.other_surgery_icds || []
  const otherTexts = procs.other_procedure_texts || procs.other_surgery_texts || []
  
  const result = []
  if (mainText) {
    result.push({ code: mainCode, text: mainText })
  }
  otherTexts.forEach((text: string, i: number) => {
    result.push({ code: otherCodes[i] || '', text })
  })
  return result.slice(0, 5)
})

/** 收集所有已提取的实体关键词，用于左侧原文高亮 */
const highlightedMedicalText = computed(() => {
  if (!medicalText.value) return ''
  let html = medicalText.value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  // 收集诊断名称（蓝色高亮）
  const diagTerms: string[] = []
  if (mainDiagnosis.value?.text) diagTerms.push(mainDiagnosis.value.text)
  secondaryDiagnoses.value.forEach(d => { if (d.text) diagTerms.push(d.text) })

  // 收集手术名称（紫色高亮）
  const procTerms: string[] = []
  procedures.value.forEach(p => { if (p.text) procTerms.push(p.text) })

  // 按长度降序排列，避免短词覆盖长词
  const allTerms = [
    ...diagTerms.map(t => ({ text: t, type: 'diag' as const })),
    ...procTerms.map(t => ({ text: t, type: 'proc' as const })),
  ].sort((a, b) => b.text.length - a.text.length)

  for (const term of allTerms) {
    const escaped = term.text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const cls = term.type === 'diag' ? 'hl-diag' : 'hl-proc'
    html = html.replace(
      new RegExp(escaped, 'g'),
      `<mark class="${cls}">${term.text}</mark>`
    )
  }

  // 换行转 <br>
  html = html.replace(/\n/g, '<br/>')
  return html
})

/** 高亮执行日志中的编码 */
function highlightCodes(msg: string): string {
  return msg.replace(
    /([A-Z]\d{2}\.\d[\w.]*|\d{2}\.\d[\w.]*)/g,
    '<code class="trace-code">$1</code>'
  ).replace(
    /→/g,
    '<span class="trace-arrow">→</span>'
  )
}

// Methods
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
      body: JSON.stringify({ medical_text: medicalText.value })
    })

    const data = await response.json()
    if (response.ok && data.success && data.data) {
      extractedData.value = data.data
      admissionId.value = data.data.admission_id
      message.success('AI智能抽取完成')
      handleDIPGrouping()
    } else {
      message.error(data.error || data.detail || '抽取失败')
    }
  } catch (error) {
    console.error('Extract error:', error)
    message.error('AI抽取服务暂不可用')
  } finally {
    extracting.value = false
  }
}

const handleDIPGrouping = async () => {
  if (!extractedData.value) {
    message.warning('请先完成AI抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DIP'
  
  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const procedures = extractedData.value.procedures || {}
    const basicInfo = extractedData.value.basic_info || {}
    const costs = extractedData.value.costs || {}
    
    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes = diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = procedures.main_procedure_code || ''
    const otherProcCodes = procedures.other_procedure_codes || []
    
    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const ssList = [mainProcCode, ...otherProcCodes].filter(Boolean)
    
    const dipResult = localDipGrouping({ zdList, ssList })
    
    if (dipResult.status === '分组成功') {
      drgResult.value = {
        code: dipResult.dipCode || '未入组',
        name: dipResult.dipName || '未知病种',
        weight: '--',
        payment: '--',
        actual_cost: costs.total_cost || 0,
        profit: '--',
        matchType: dipResult.matchType || '',
        messages: dipResult.messages
      }
      message.success(`四川省DIP入组成功: ${dipResult.dipCode}`)
    } else {
      drgResult.value = {
        code: '未入组',
        name: '无法匹配病种',
        weight: '--',
        payment: '--',
        actual_cost: costs.total_cost || 0,
        profit: '--',
        messages: dipResult.messages
      }
      message.warning('DIP未能入组')
    }
  } catch (error) {
    console.error('DIP grouping error:', error)
    message.error('DIP本地分组引擎执行失败')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}

const handleDRGGrouping = async () => {
  if (!extractedData.value) {
    message.warning('请先完成AI抽取')
    return
  }

  grouping.value = true
  groupingType.value = 'DRG'
  
  try {
    const diagnoses = extractedData.value.diagnoses || {}
    const procedures = extractedData.value.procedures || {}
    const basicInfo = extractedData.value.basic_info || {}
    const costs = extractedData.value.costs || {}
    
    const primaryDiagCode = diagnoses.discharge_main_icd || diagnoses.admission_main_icd || ''
    const secondaryDiagCodes = diagnoses.discharge_other_icds || diagnoses.admission_other_icds || []
    const mainProcCode = procedures.main_procedure_code || ''
    const otherProcCodes = procedures.other_procedure_codes || []
    
    const zdList = [primaryDiagCode, ...secondaryDiagCodes].filter(Boolean)
    const ssList = [mainProcCode, ...otherProcCodes].filter(Boolean)
    
    const drgGroupResult = await localDrgGrouping({
      gender: (basicInfo.gender === '2' || basicInfo.gender_text === '女') ? '2' : '1',
      age: basicInfo.age_years || 50,
      zdList,
      ssList,
      days: 7,
    })
    
    const actualCost = costs.total_cost || 0
    
    if (drgGroupResult.status === '分组成功' && drgGroupResult.drg) {
      const rw = drgGroupResult.rw || 0
      const baselinePayment = Math.round(rw * 8000 * 100) / 100
      
      drgResult.value = {
        code: drgGroupResult.drg,
        name: drgGroupResult.drgName || `MDC${drgGroupResult.mdc || ''} / ADRG${drgGroupResult.adrg || ''}`,
        weight: rw,
        payment: baselinePayment,
        actual_cost: actualCost,
        profit: Math.round((baselinePayment - actualCost) * 100) / 100,
        messages: drgGroupResult.messages
      }
      message.success(`四川省DRG入组成功: ${drgGroupResult.drg} (RW=${rw})`)
    } else {
      drgResult.value = {
        code: '未入组',
        name: drgGroupResult.adrg ? `ADRG: ${drgGroupResult.adrg}` : '无法入组',
        weight: 0,
        payment: 0,
        actual_cost: actualCost,
        profit: -actualCost,
        messages: drgGroupResult.messages
      }
      message.warning('DRG未能入组')
    }
  } catch (error) {
    console.error('DRG grouping error:', error)
    message.error('DRG本地分组引擎执行失败')
    drgResult.value = null
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
/* ===== Layout ===== */
.pre-analysis { padding: 0 4px; }

.header-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border-radius: 16px;
  padding: 16px 24px; margin-bottom: 16px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.header-left { display: flex; align-items: center; gap: 14px; }
.header-icon {
  width: 42px; height: 42px; border-radius: 12px;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  display: flex; align-items: center; justify-content: center;
  color: #fff; font-size: 20px;
  box-shadow: 0 4px 12px rgba(59,130,246,0.3);
}
.header-title { font-size: 18px; font-weight: 700; color: #1e293b; margin: 0; line-height: 1.3; }
.header-desc { font-size: 12px; color: #94a3b8; margin: 2px 0 0; }
.header-actions { display: flex; align-items: center; gap: 10px; }

.extract-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 20px; border-radius: 10px; border: none;
  background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%);
  color: #fff; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
  box-shadow: 0 4px 12px rgba(59,130,246,0.3);
}
.extract-btn:hover:not(:disabled) { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(59,130,246,0.4); }
.extract-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.main-grid {
  flex: 1; display: grid;
  grid-template-columns: 380px 1fr;
  gap: 16px;
}
@media (max-width: 1024px) { .main-grid { grid-template-columns: 1fr; } }

.results-column { display: flex; flex-direction: column; gap: 16px; }
.coding-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 768px) { .coding-row { grid-template-columns: 1fr; } }

/* ===== Panel Card ===== */
.panel-card {
  background: #fff; border-radius: 14px;
  border: 1px solid rgba(226,232,240,0.8);
  box-shadow: 0 2px 10px rgba(0,0,0,0.02);
  padding: 18px; transition: box-shadow 0.25s;
}
.panel-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.06); }

.panel-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 14px; padding-bottom: 12px;
  border-bottom: 1px solid #f1f5f9;
}
.panel-icon-svg { flex-shrink: 0; }
.panel-title { font-size: 14px; font-weight: 700; color: #1e293b; }
.panel-title-lg { font-size: 16px; font-weight: 800; color: #0f172a; }
.text-counter {
  margin-left: auto; font-size: 11px; color: #94a3b8;
  background: rgba(226,232,240,0.6); padding: 2px 10px; border-radius: 6px;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
}
.ai-tag {
  font-size: 10px; font-weight: 700; color: #6366f1;
  background: rgba(99,102,241,0.08); padding: 2px 8px; border-radius: 5px;
  letter-spacing: 0.3px; border: 1px solid rgba(99,102,241,0.15);
}
.badge-count {
  margin-left: auto; width: 20px; height: 20px; border-radius: 50%;
  font-size: 11px; font-weight: 700; color: #fff;
  background: #3b82f6;
  display: flex; align-items: center; justify-content: center;
}
.badge-count.amber { background: #f59e0b; }

/* ===== Medical Panel ===== */
.medical-panel { display: flex; flex-direction: column; }
.medical-textarea {
  flex: 1; border-radius: 10px !important;
  background: #f8fafc !important; border-color: #e2e8f0 !important;
  resize: none !important; font-size: 14px !important; line-height: 1.8 !important;
  color: #475569 !important;
}

/* AI 实体高亮视图 */
.medical-highlight-view {
  flex: 1; border-radius: 10px;
  background: #f8fafc; border: 1px solid #e2e8f0;
  padding: 12px 16px; overflow-y: auto;
  max-height: 520px; min-height: 300px;
  cursor: default;
}
.highlight-text {
  font-size: 14px; line-height: 1.8; color: #475569;
}
:deep(.hl-diag) {
  background: rgba(59,130,246,0.08); color: #2563eb;
  border-bottom: 2px solid rgba(59,130,246,0.3);
  padding: 0 2px; border-radius: 2px;
  font-weight: 600; cursor: help;
}
:deep(.hl-proc) {
  background: rgba(99,102,241,0.08); color: #4f46e5;
  border-bottom: 2px solid rgba(99,102,241,0.3);
  padding: 0 2px; border-radius: 2px;
  font-weight: 600; cursor: help;
}

/* ===== Coding List ===== */
.coding-list { max-height: 260px; overflow-y: auto; }
.coding-panel { min-height: 200px; }

/* ===== Diagnosis Item — 增加左侧高亮边条 ===== */
.diag-item {
  position: relative;
  display: flex; align-items: flex-start; gap: 10px;
  padding: 10px 12px 10px 16px; border-radius: 10px;
  background: #f8fafc; margin-bottom: 6px;
  border: 1px solid #f1f5f9;
  transition: all 0.15s;
}
.diag-item:hover { background: #f1f5f9; }

.diag-left-bar {
  position: absolute; left: 0; top: 10px;
  width: 3px; height: 20px; border-radius: 0 3px 3px 0;
}
.diag-left-bar.blue { background: #3b82f6; }
.diag-left-bar.amber { background: #f59e0b; }

.diag-item.diag-main {
  background: rgba(59,130,246,0.04);
  border-color: rgba(191,219,254,0.6);
}
.diag-item.proc-main {
  background: rgba(245,158,11,0.04);
  border-color: rgba(253,230,138,0.6);
}

.diag-badge {
  flex-shrink: 0; padding: 2px 8px; border-radius: 5px;
  background: #3b82f6;
  color: #fff; font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px;
  margin-top: 2px;
}
.diag-badge.amber { background: #f59e0b; }

.diag-num {
  flex-shrink: 0; width: 24px; height: 24px; border-radius: 7px;
  background: #e2e8f0; color: #64748b;
  font-size: 11px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.diag-info { flex: 1; min-width: 0; }
.diag-name { font-size: 14px; color: #0f172a; font-weight: 600; line-height: 1.4; }

.diag-code-chip {
  display: inline-block; margin-top: 4px;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  font-size: 11px; font-weight: 600;
  padding: 1px 8px; border-radius: 5px;
}
.diag-code-chip.blue { color: rgba(59,130,246,0.85); background: rgba(59,130,246,0.08); }
.diag-code-chip.amber { color: #d97706; background: rgba(245,158,11,0.08); }
.diag-code-chip.muted { color: #64748b; background: rgba(100,116,139,0.06); }

/* ===== Empty States ===== */
.empty-state-inline {
  text-align: center; padding: 20px 0;
  color: #94a3b8; font-size: 13px;
}
.empty-state-box {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 32px 0; color: #cbd5e1; font-size: 13px; gap: 8px;
  border: 2px dashed #e2e8f0; border-radius: 12px;
  background: rgba(248,250,252,0.5);
}
.empty-state-box.subtle {
  padding: 20px 0; color: #d1d5db;
  border-color: #f1f5f9;
  font-size: 12px; font-weight: 500;
}
.empty-state-icon { font-size: 28px; color: #cbd5e1; }
.empty-state-icon-sm { font-size: 20px; color: #d1d5db; }

/* ===== Grouping Panel ===== */
.grouping-panel {
  flex: 1;
  box-shadow: 0 8px 30px rgba(0,0,0,0.04);
}

/* Segmented tabs */
.grouping-tabs {
  margin-left: auto;
  display: flex; padding: 2px; border-radius: 10px;
  background: rgba(241,245,249,0.8);
  border: 1px solid rgba(226,232,240,0.5);
}
.grouping-tab {
  display: flex; align-items: center; gap: 4px;
  padding: 6px 16px; border-radius: 8px; border: none;
  background: transparent; color: #64748b;
  font-size: 12px; font-weight: 600; cursor: pointer;
  transition: all 0.2s;
}
.grouping-tab:hover:not(:disabled) { color: #1e293b; }
.grouping-tab:disabled { opacity: 0.4; cursor: not-allowed; }
.grouping-tab.active-dip {
  background: #fff; color: #059669;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
.grouping-tab.active-drg {
  background: #fff; color: #3b82f6;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* ===== Result Hero Row ===== */
.grouping-result { display: flex; flex-direction: column; gap: 16px; }

.result-hero-row {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) minmax(300px, 2fr);
  gap: 20px; align-items: stretch;
}
@media (max-width: 900px) { .result-hero-row { grid-template-columns: 1fr; } }

/* ===== Hero Code Card (高级渐变) ===== */
.hero-code-card {
  position: relative; overflow: hidden;
  padding: 24px; border-radius: 18px; color: #fff;
  display: flex; flex-direction: column;
}
.hero-code-card.emerald {
  background: linear-gradient(135deg, #10b981 0%, #0d9488 100%);
  box-shadow: 0 8px 24px rgba(16,185,129,0.25);
}
.hero-code-card.blue {
  background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
  box-shadow: 0 8px 24px rgba(59,130,246,0.25);
}
.hero-glow {
  position: absolute; top: -40px; right: -40px;
  width: 120px; height: 120px;
  background: rgba(255,255,255,0.1);
  border-radius: 50%; filter: blur(30px);
  pointer-events: none;
}
.hero-label {
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 1.5px;
  opacity: 0.7; margin-bottom: 4px;
}
.hero-value {
  font-size: 32px; font-weight: 900;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  letter-spacing: 1px; line-height: 1.2;
}
.hero-name {
  font-size: 13px; font-weight: 500;
  opacity: 0.85; line-height: 1.5;
  margin-top: 4px;
}
.hero-tags { display: flex; gap: 6px; margin-top: auto; padding-top: 12px; flex-wrap: wrap; }
.hero-tag {
  background: rgba(255,255,255,0.18); backdrop-filter: blur(4px);
  padding: 4px 12px; border-radius: 6px;
  font-size: 11px; font-weight: 700;
  border: 1px solid rgba(255,255,255,0.1);
}

/* ===== Finance Grid (微型看板) ===== */
.finance-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
}
.finance-card {
  background: #f8fafc; border: 1px solid #f1f5f9;
  border-radius: 14px; padding: 16px;
  display: flex; flex-direction: column; justify-content: center;
  transition: border-color 0.2s;
}
.finance-card:hover { border-color: #e2e8f0; }
.finance-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 700; color: #94a3b8;
  margin-bottom: 8px;
}
.finance-value {
  font-size: 22px; font-weight: 800; color: #1e293b;
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  line-height: 1;
  display: flex; align-items: baseline;
}
.finance-value.green { color: #059669; }
.finance-value.red { color: #dc2626; }
.finance-unit {
  font-size: 13px; font-weight: 500; color: #94a3b8;
  margin-right: 1px;
}
.finance-placeholder {
  font-size: 22px; font-weight: 800; color: #cbd5e1;
  letter-spacing: 2px;
}

/* ===== Execution Trace (代码化日志) ===== */
.trace-section {
  background: #f8fafc; border-radius: 14px;
  padding: 16px 18px; border: 1px solid #f1f5f9;
}
.trace-title {
  font-size: 11px; font-weight: 700; color: #94a3b8;
  text-transform: uppercase; letter-spacing: 1px;
  margin-bottom: 12px;
}
.trace-list { display: flex; flex-direction: column; gap: 8px; padding-left: 2px; }
.trace-item {
  display: flex; align-items: flex-start; gap: 10px;
  font-size: 12px; font-weight: 500; color: #475569;
  line-height: 1.6;
}
.trace-check { flex-shrink: 0; margin-top: 2px; }

/* 代码高亮 (通过 v-html) */
:deep(.trace-code) {
  font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
  font-size: 11px; font-weight: 600;
  background: rgba(16,185,129,0.06); color: #059669;
  padding: 1px 6px; border-radius: 4px;
  border: 1px solid rgba(16,185,129,0.1);
}
:deep(.trace-arrow) {
  color: #94a3b8; margin: 0 2px;
}

/* ===== Grouping Empty ===== */
.grouping-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px 0; color: #94a3b8; font-size: 13px;
}
.grouping-empty-icon {
  width: 56px; height: 56px; border-radius: 16px;
  background: #f1f5f9; border: 2px dashed #e2e8f0;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; color: #cbd5e1; margin-bottom: 12px;
}
.grouping-empty p { margin-top: 4px; font-weight: 500; }

/* ===== Scrollbar ===== */
.custom-scrollbar::-webkit-scrollbar { width: 4px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }

/* ===== Animation ===== */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
.grouping-result { animation: fadeInUp 0.35s ease-out; }
.diag-item { animation: fadeInUp 0.2s ease-out; }
</style>
