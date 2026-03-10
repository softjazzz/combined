<template>
  <div class="frontpage-panel">
    <a-button type="primary" block :loading="generating" @click="emit('generate')" style="margin-bottom: 16px">
      <ThunderboltOutlined />
      AI 生成病案首页
    </a-button>

    <template v-if="fields.length > 0">
      <!-- 进度指示 -->
      <div class="fp-progress">
        <span>填充率</span>
        <a-progress :percent="fillRate" :stroke-color="fillRate >= 90 ? '#52c41a' : '#faad14'" size="small" />
      </div>

      <!-- 基本信息 -->
      <div ref="basicSectionRef" class="fp-section" :class="{ 'fp-section--focus': focusTarget === 'basic' }">
        <div class="fp-section-title">基本信息</div>
        <div class="fp-grid">
          <div v-for="f in basicFields" :key="f.label" class="fp-field">
            <label>{{ f.label }}</label>
            <div class="fp-field-value">
              <a-input v-model:value="f.value" size="small" />
              <a-tooltip v-if="f.confidence < 1" :title="`AI 置信度 ${(f.confidence * 100).toFixed(0)}%`">
                <span class="confidence-dot" :class="confidenceClass(f.confidence)"></span>
              </a-tooltip>
            </div>
          </div>
        </div>
      </div>

      <!-- 住院信息 -->
      <div ref="admissionSectionRef" class="fp-section" :class="{ 'fp-section--focus': focusTarget === 'admission' }">
        <div class="fp-section-title">住院信息</div>
        <div class="fp-grid">
          <div v-for="f in admissionFields" :key="f.label" class="fp-field">
            <label>{{ f.label }}</label>
            <div class="fp-field-value">
              <a-input v-model:value="f.value" size="small" />
              <a-tooltip v-if="f.confidence < 1" :title="`AI 置信度 ${(f.confidence * 100).toFixed(0)}%`">
                <span class="confidence-dot" :class="confidenceClass(f.confidence)"></span>
              </a-tooltip>
            </div>
          </div>
        </div>
      </div>

      <!-- 诊断信息 -->
      <div ref="diagnosisSectionRef" class="fp-section" :class="{ 'fp-section--focus': focusTarget === 'diagnosis' }">
        <div class="fp-section-title">
          诊断信息
          <a-tag color="processing" size="small">AI 提取</a-tag>
        </div>
        <div class="diag-list">
          <div v-for="(diag, idx) in diagnosisFields" :key="idx" class="diag-item">
            <div class="diag-header">
              <a-tag v-if="idx === 0" color="red" size="small">主诊断</a-tag>
              <a-tag v-else color="default" size="small">其他诊断 {{ idx }}</a-tag>
              <span class="confidence-badge" :class="confidenceClass(diag.confidence)">
                {{ (diag.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="diag-row">
              <a-input v-model:value="diag.name" placeholder="诊断名称" size="small" style="flex: 2" />
              <a-input v-model:value="diag.code" placeholder="ICD-10 编码" size="small" style="flex: 1" />
            </div>
          </div>
          <a-button type="dashed" size="small" block @click="addDiagnosis" style="margin-top: 8px">
            + 添加诊断
          </a-button>
        </div>
      </div>

      <!-- 手术/操作 -->
      <div ref="procedureSectionRef" class="fp-section" :class="{ 'fp-section--focus': focusTarget === 'procedure' }">
        <div class="fp-section-title">
          手术/操作
          <a-tag color="processing" size="small">AI 提取</a-tag>
        </div>
        <div class="diag-list">
          <div v-for="(proc, idx) in procedureFields" :key="idx" class="diag-item">
            <div class="diag-header">
              <a-tag v-if="idx === 0" color="blue" size="small">主手术</a-tag>
              <a-tag v-else color="default" size="small">其他操作 {{ idx }}</a-tag>
              <span class="confidence-badge" :class="confidenceClass(proc.confidence)">
                {{ (proc.confidence * 100).toFixed(0) }}%
              </span>
            </div>
            <div class="diag-row">
              <a-input v-model:value="proc.name" placeholder="手术/操作名称" size="small" style="flex: 2" />
              <a-input v-model:value="proc.code" placeholder="ICD-9-CM-3" size="small" style="flex: 1" />
            </div>
          </div>
          <a-button type="dashed" size="small" block @click="addProcedure" style="margin-top: 8px">
            + 添加手术/操作
          </a-button>
        </div>
      </div>

      <!-- 底部操作 -->
      <div class="fp-actions">
        <a-button size="small" @click="emit('export', 'health')">
          <DownloadOutlined />
          卫健委格式
        </a-button>
        <a-button size="small" @click="emit('export', 'insurance')">
          <DownloadOutlined />
          医保格式
        </a-button>
        <a-button size="small" @click="emit('export', 'settlement')">
          <DownloadOutlined />
          结算清单
        </a-button>
        <a-button type="primary" size="small" @click="emit('save')">
          <SaveOutlined />
          保存首页
        </a-button>
      </div>
    </template>

    <div v-else-if="!generating" class="fp-empty">
      <FileTextOutlined style="font-size: 32px; color: #d9d9d9" />
      <p>点击上方按钮，AI 将自动提取病历信息生成首页</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  ThunderboltOutlined,
  FileTextOutlined,
  DownloadOutlined,
  SaveOutlined,
} from '@ant-design/icons-vue'
import type { FrontPageField } from './mockData'

const props = defineProps<{
  fields: FrontPageField[]
  generating: boolean
  focusTarget?: 'basic' | 'admission' | 'diagnosis' | 'procedure' | ''
}>()

const emit = defineEmits<{
  generate: []
  save: []
  export: [format: 'health' | 'insurance' | 'settlement']
  'draft-change': [payload: { diagnoses: DiagItem[]; procedures: DiagItem[] }]
}>()

// 诊断和手术列表（可编辑）
interface DiagItem { name: string; code: string; confidence: number }
const diagnosisFields = ref<DiagItem[]>([])
const procedureFields = ref<DiagItem[]>([])
const basicSectionRef = ref<HTMLElement | null>(null)
const admissionSectionRef = ref<HTMLElement | null>(null)
const diagnosisSectionRef = ref<HTMLElement | null>(null)
const procedureSectionRef = ref<HTMLElement | null>(null)

// 将 fields 按类别分组
const basicFields = computed(() =>
  props.fields.filter(f => ['医疗机构名称', '患者姓名', '性别', '年龄', '住院号'].includes(f.label))
)
const admissionFields = computed(() =>
  props.fields.filter(f => ['入院日期', '出院日期', '住院天数', '入院科室', '床号'].includes(f.label))
)

// 填充率
const fillRate = computed(() => {
  if (props.fields.length === 0) return 0
  const filled = props.fields.filter(f => f.value && f.value !== '–').length
  return Math.round((filled / props.fields.length) * 100)
})

// 从 fields 中提取诊断和手术
watch(() => props.fields, (newFields) => {
  // 1. 如果新数据为空数组（例如触发了重新生成），则重置本地列表
  if (newFields.length === 0) {
    diagnosisFields.value = []
    procedureFields.value = []
    return
  }

  const mainDiag = newFields.find(f => f.label === '主要诊断')
  const mainDiagCode = newFields.find(f => f.label === '主要诊断编码')
  const mainProc = newFields.find(f => f.label === '主要手术')
  const mainProcCode = newFields.find(f => f.label === '主要手术编码')

  if (diagnosisFields.value.length === 0) {
    diagnosisFields.value.push({ name: '', code: '', confidence: 0.5 })
  }
  diagnosisFields.value[0].name = mainDiag?.value || diagnosisFields.value[0].name || ''
  diagnosisFields.value[0].code = mainDiagCode?.value || diagnosisFields.value[0].code || ''
  diagnosisFields.value[0].confidence = mainDiag?.confidence || diagnosisFields.value[0].confidence || 0.5

  if (mainProc && mainProc.value !== '无' && mainProc.value !== '–') {
    if (procedureFields.value.length === 0) {
      procedureFields.value.push({ name: '', code: '', confidence: 0.5 })
    }
    procedureFields.value[0].name = mainProc.value || procedureFields.value[0].name || ''
    procedureFields.value[0].code = mainProcCode?.value || procedureFields.value[0].code || ''
    procedureFields.value[0].confidence = mainProc?.confidence || procedureFields.value[0].confidence || 0.5
  }
}, { immediate: true, deep: true })

watch(
  [diagnosisFields, procedureFields],
  () => {
    emit('draft-change', {
      diagnoses: diagnosisFields.value.map(item => ({ ...item })),
      procedures: procedureFields.value.map(item => ({ ...item })),
    })
  },
  { deep: true },
)

function addDiagnosis() {
  diagnosisFields.value.push({ name: '', code: '', confidence: 0 })
}

function addProcedure() {
  procedureFields.value.push({ name: '', code: '', confidence: 0 })
}

function confidenceClass(c: number) {
  return c >= 0.9 ? 'high' : c >= 0.7 ? 'mid' : 'low'
}

watch(
  () => props.focusTarget,
  async (target) => {
    if (!target) return
    await nextTick()
    const map = {
      basic: basicSectionRef.value,
      admission: admissionSectionRef.value,
      diagnosis: diagnosisSectionRef.value,
      procedure: procedureSectionRef.value,
    }
    map[target]?.scrollIntoView({
      behavior: 'smooth',
      block: 'start',
      inline: 'nearest',
    })
  },
)
</script>

<style scoped>
.fp-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  font-size: 12px;
  color: #888;
}

.fp-progress .ant-progress {
  flex: 1;
}

.fp-section {
  margin-bottom: 16px;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.fp-section--focus {
  border-color: #60a5fa;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
}

.fp-section-title {
  padding: 8px 12px;
  background: #fafafa;
  font-weight: 600;
  font-size: 13px;
  color: #1a1a1a;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  gap: 8px;
}

.fp-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 12px;
}

.fp-field label {
  display: block;
  font-size: 11px;
  color: #888;
  margin-bottom: 2px;
}

.fp-field-value {
  display: flex;
  align-items: center;
  gap: 4px;
}

.confidence-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.confidence-dot.high { background: #52c41a; }
.confidence-dot.mid { background: #faad14; }
.confidence-dot.low { background: #ff4d4f; }

.confidence-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  font-weight: 500;
}

.confidence-badge.high { background: #f6ffed; color: #52c41a; }
.confidence-badge.mid { background: #fffbe6; color: #faad14; }
.confidence-badge.low { background: #fff2f0; color: #ff4d4f; }

.diag-list {
  padding: 12px;
}

.diag-item {
  margin-bottom: 8px;
  padding: 8px;
  background: #fafafa;
  border-radius: 6px;
}

.diag-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.diag-row {
  display: flex;
  gap: 8px;
}

.fp-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.fp-empty {
  text-align: center;
  padding: 40px 20px;
  color: #999;
}

.fp-empty p {
  margin-top: 12px;
  font-size: 13px;
}
</style>
