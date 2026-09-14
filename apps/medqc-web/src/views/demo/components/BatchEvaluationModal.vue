<template>
  <a-modal
    v-model:open="isVisible"
    :title="`质控规则测试 · ${rule?.rule_id || rule?.rule_code || ''}`"
    width="900px"
    :footer="null"
    :destroy-on-close="true"
    class="rule-test-modal"
    @cancel="handleClose"
  >
    <div
      v-if="rule"
      class="rule-test-container"
    >
      <!-- 规则信息展示区 -->
      <a-card
        title="规则信息"
        :bordered="true"
        class="rule-info-card"
      >
        <a-row :gutter="[16, 12]">
          <a-col :span="12">
            <div class="info-item">
              <span class="info-label">规则名称</span>
              <span class="info-value">{{ rule.name }}</span>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="info-item centered">
              <span class="info-label">缺陷级别</span>
              <span :class="['status-pill', `status-pill--${getDefectTone(rule.defect_level)}`]">
                <component
                  :is="statusToneIcons[getDefectTone(rule.defect_level)]"
                  class="status-pill__icon"
                />
                <span class="status-pill__text">{{ getDefectLevelText(rule.defect_level) }}</span>
              </span>
            </div>
          </a-col>
          <a-col :span="6">
            <div class="info-item centered">
              <span class="info-label">复杂度</span>
              <span :class="['status-pill', `status-pill--${getComplexityTone(rule.complexity)}`]">
                <component
                  :is="statusToneIcons[getComplexityTone(rule.complexity)]"
                  class="status-pill__icon"
                />
                <span class="status-pill__text">{{ rule.complexity }}</span>
              </span>
            </div>
          </a-col>
          <a-col :span="24">
            <div class="info-item">
              <span class="info-label">适用文书</span>
              <a-space
                :size="4"
                wrap
              >
                <a-tag
                  v-for="(doc, idx) in rule.applicable_documents"
                  :key="idx"
                  color="geekblue"
                  class="doc-tag"
                >
                  {{ getDocTypeZh(doc) }}
                </a-tag>
              </a-space>
            </div>
          </a-col>
          <a-col :span="24">
            <div class="info-item">
              <span class="info-label">规则描述</span>
              <p class="info-description">
                {{ rule.description }}
              </p>
            </div>
          </a-col>
        </a-row>
      </a-card>

      <!-- 病历输入区 -->
      <a-card
        title="病历文本"
        :bordered="true"
        class="medical-text-card"
      >
        <template #extra>
          <a-radio-group
            v-model:value="exampleType"
            button-style="solid"
            size="small"
            class="example-type-selector"
          >
            <a-radio-button
              value="negative"
              class="negative-btn"
            >
              <CloseCircleOutlined class="radio-icon" />
              <span>反例</span>
            </a-radio-button>
            <a-radio-button
              value="positive"
              class="positive-btn"
            >
              <CheckCircleOutlined class="radio-icon" />
              <span>正例</span>
            </a-radio-button>
          </a-radio-group>
        </template>

        <div class="medical-input-container">
          <a-alert
            :message="
              exampleType === 'negative'
                ? '当前示例：不符合规则要求的病历（用于测试规则识别能力）'
                : '当前示例：符合规则要求的病历（用于测试误报率）'
            "
            :type="exampleType === 'negative' ? 'warning' : 'success'"
            show-icon
            :banner="true"
            style="margin-bottom: 12px; border-radius: 8px"
          />

          <!-- 示例说明折叠面板 -->
          <a-collapse
            v-model:active-key="showExampleInfo"
            class="example-info-collapse"
            style="margin-bottom: 12px"
          >
            <a-collapse-panel
              key="1"
              class="example-info-panel"
            >
              <template #header>
                <div class="panel-header">
                  <InfoCircleOutlined style="margin-right: 8px" />
                  <span class="panel-title">示例说明</span>
                  <span class="panel-subtitle">（仅供参考，不会提交给 LLM）</span>
                </div>
              </template>

              <div class="example-info-content">
                <div class="info-section info-section--analysis">
                  <div class="section-title">
                    <SearchOutlined
                      v-if="exampleType === 'negative'"
                      class="section-title__icon"
                    />
                    <HighlightOutlined
                      v-else
                      class="section-title__icon"
                    />
                    <span>质控分析</span>
                  </div>
                  <div class="section-content">
                    <div class="analysis-summary">
                      <div class="analysis-summary__title">
                        {{ exampleType === 'negative' ? '❌ 核心缺陷' : '✅ 质控要点' }}
                      </div>
                      <div class="focus-point-item">
                        <span class="point-index">1.</span>
                        <span class="point-text">{{
                          exampleType === 'negative'
                            ? '所有检查项目均未写出具体检查结果，未记录任何具体检查数值'
                            : '所有检查项目均有具体结果记录'
                        }}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </a-collapse-panel>
          </a-collapse>

          <a-textarea
            v-model:value="medicalText"
            placeholder="请输入或粘贴病历文本片段（500-2000字）"
            :rows="10"
            :maxlength="2000"
            show-count
            class="medical-textarea"
          />

          <div class="action-bar">
            <span class="hint-text">
              <BulbOutlined class="hint-icon" />
              提示：可以修改示例文本或输入自己的病历
            </span>
            <a-button
              type="primary"
              :loading="testing"
              class="test-btn"
              @click="executeTest"
            >
              <template #icon>
                <ThunderboltOutlined />
              </template>
              开始测试
            </a-button>
          </div>

          <!-- AI调用加载遮罩 -->
          <div
            v-if="showAILoadingMask"
            class="ai-loading-mask"
          >
            <div class="ai-loading-content">
              <a-spin size="large" />
              <div class="ai-loading-text">
                正在调用大模型，请稍候...
              </div>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 结果展示区 -->
      <div
        v-if="testResult"
        class="result-card"
      >
        <div class="card-header">
          <h3 class="card-title">
            测试结果
          </h3>
        </div>
        <div class="card-body">
          <div
            class="result-status"
            :class="testResult.compliant ? 'result-status--success' : 'result-status--warning'"
          >
            <div class="status-icon">
              <CheckCircleFilled
                v-if="testResult.compliant"
                class="status-icon__graphic"
                style="color: #52c41a"
              />
              <ExclamationCircleFilled
                v-else
                class="status-icon__graphic"
                style="color: #faad14"
              />
            </div>
            <div class="status-text">
              <h4>{{ testResult.compliant ? '符合规则要求' : '不符合规则要求' }}</h4>
              <a-progress
                class="result-progress"
                :percent="Math.round(testResult.confidence * 100)"
                :stroke-color="testResult.compliant ? '#52C41A' : '#FAAD14'"
                :show-info="false"
              />
              <p class="confidence-text">
                置信度 {{ (testResult.confidence * 100).toFixed(1) }}%
              </p>
            </div>
          </div>

          <div class="result-details">
            <div class="detail-item">
              <div class="detail-label">
                <FileTextOutlined />
                发现的问题
              </div>
              <div class="detail-content structured-findings">
                <template v-if="parsedFindings.items.length > 0">
                  <p
                    v-if="parsedFindings.summary"
                    class="findings-summary"
                  >
                    {{ parsedFindings.summary }}
                  </p>
                  <div class="findings-list">
                    <div
                      v-for="(item, index) in parsedFindings.items"
                      :key="index"
                      class="findings-item"
                    >
                      <div class="findings-item-header">
                        <span class="findings-item-number">{{ index + 1 }}</span>
                        <strong>{{ item.title }}</strong>
                      </div>
                      <div
                        v-if="item.content"
                        class="findings-item-content"
                      >
                        {{ item.content }}
                      </div>
                    </div>
                  </div>
                </template>
                <template v-else>
                  <p v-if="testResult.compliant">
                    未发现明显问题。
                  </p>
                  <template v-else>
                    <p
                      v-if="parsedFindings.fallback"
                      class="findings-fallback"
                    >
                      {{ parsedFindings.fallback }}
                    </p>
                    <p v-else>
                      {{ testResult.evidence || '未发现明显问题。' }}
                    </p>
                  </template>
                </template>
              </div>
            </div>

            <div class="detail-item">
              <div class="detail-label">
                <CodeOutlined />
                证据引用
              </div>
              <div class="detail-content evidence-box">
                <pre class="evidence-text">{{ testResult.reasoning }}</pre>
              </div>
            </div>

            <div
              v-if="testResult.suggestion"
              class="detail-item"
            >
              <div class="detail-label">
                <BulbOutlined />
                改进建议
              </div>
              <div class="detail-content suggestion-box">
                <div class="suggestion-text">
                  {{ testResult.suggestion }}
                </div>
              </div>
            </div>
          </div>

          <div class="result-actions">
            <a-space :size="8">
              <a-button
                class="secondary-btn"
                @click="testResult = null"
              >
                清除结果
              </a-button>
              <a-button
                type="primary"
                class="feedback-btn"
                @click="provideFeedback"
              >
                提供反馈
              </a-button>
              <a-button
                type="primary"
                :loading="testing"
                class="primary-btn"
                @click="executeTest"
              >
                重新测试
              </a-button>
            </a-space>
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  CloseCircleOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  SearchOutlined,
  HighlightOutlined,
  BulbOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  CodeOutlined,
  CheckCircleFilled,
  ExclamationCircleFilled,
  CloseCircleFilled,
  InfoCircleFilled,
} from '@ant-design/icons-vue'
import type { QCRule, EvaluationResult } from '@/types/demo'
import type { QCRuleCaseExample } from '@/data/qcRuleCases'

interface Props {
  visible: boolean
  rule: QCRule | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  feedback: [result: EvaluationResult]
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

type StatusTone = 'success' | 'warning' | 'error' | 'info'

const statusToneIcons: Record<StatusTone, any> = {
  success: CheckCircleFilled,
  warning: ExclamationCircleFilled,
  error: CloseCircleFilled,
  info: InfoCircleFilled,
}

const qcRuleCaseMapRef = ref<Record<string, any>>({})
const customRuleCaseMapRef = ref<Record<string, any>>({})
const buildCaseTextRef = ref<
  ((example: QCRuleCaseExample, options?: Record<string, unknown>) => string) | null
>(null)
const extractHintsRef = ref<((example: QCRuleCaseExample) => string[]) | null>(null)
const extractFocusPointsRef = ref<((example: QCRuleCaseExample) => string[]) | null>(null)
let caseDataPromise: Promise<void> | null = null

const ensureCaseDataLoaded = async () => {
  if (!caseDataPromise) {
    caseDataPromise = Promise.all([
      import('@/data/qcRuleCases'),
      import('@/data/customRuleCases'),
    ]).then(([qcRuleCasesModule, customRuleCasesModule]) => {
      qcRuleCaseMapRef.value = qcRuleCasesModule.qcRuleCaseMap
      customRuleCaseMapRef.value = customRuleCasesModule.customRuleCaseMap
      buildCaseTextRef.value = qcRuleCasesModule.buildCaseText
      extractHintsRef.value = qcRuleCasesModule.extractHints
      extractFocusPointsRef.value = qcRuleCasesModule.extractFocusPoints
    })
  }

  return caseDataPromise
}

// 文书类别映射
const CANONICAL_LABEL_ZH: Record<string, string> = {
  admission_record: '入院记录',
  progress_note: '病程记录',
  course_record: '病程记录',
  discharge_record: '出院记录',
  operation_record: '手术相关记录',
  examination_report: '辅助检查',
  consent_form: '知情同意书',
}

const ALIAS_TO_CANONICAL: Record<string, string> = {
  手术记录: 'operation_record',
  检查记录: 'examination_report',
  检验检查: 'examination_report',
  输血记录: 'progress_note',
  治疗记录: 'progress_note',
  医嘱记录: 'progress_note',
  medical_order: 'progress_note',
  出院医嘱: 'progress_note',
  输血同意书: 'consent_form',
}

const mapDocTypeToCanonical = (raw: string | undefined | null): string | null => {
  const s = String(raw || '').trim()
  if (!s) return null
  if (s in CANONICAL_LABEL_ZH) return s
  if (s in ALIAS_TO_CANONICAL) return ALIAS_TO_CANONICAL[s]
  const key = s.toLowerCase()
  if (key === 'emergency') return null
  if (key === 'operation' || key === 'operation_record') return 'operation_record'
  if (key === 'examination' || key === 'examination_report') return 'examination_report'
  if (key === 'admission' || key === 'admission_record') return 'admission_record'
  if (key === 'progress' || key === 'progress_note' || key === 'course_record')
    return 'progress_note'
  if (key === 'discharge' || key === 'discharge_record') return 'discharge_record'
  if (key === 'consent' || key === 'consent_form') return 'consent_form'
  return null
}

const getDocTypeZh = (value: string | undefined | null) => {
  const code = mapDocTypeToCanonical(value)
  return code ? CANONICAL_LABEL_ZH[code] : value || ''
}

// 将字符串中的 \\n 统一转换为真实换行，便于在文本框中展示
const normalizeExampleText = (text: string): string => {
  if (!text) return ''
  return text.replace(/\\n/g, '\n')
}

// 获取当前规则的示例病历文本（优先使用后端规则配置，其次使用前端内置示例）
const getExampleMedicalText = (rule: QCRule, type: 'positive' | 'negative'): string => {
  // 1. 优先使用后端规则配置中的示例（跟规则一起维护）
  const rawField: any = type === 'positive' ? rule.positive_example : rule.negative_example
  if (rawField) {
    if (typeof rawField === 'string') {
      if (rawField.trim()) {
        return normalizeExampleText(rawField)
      }
    } else if (
      typeof rawField === 'object' &&
      rawField.content &&
      String(rawField.content).trim()
    ) {
      return normalizeExampleText(String(rawField.content))
    }
  }

  // 2. 回退到前端内置示例（旧方案），避免短期内打断已有使用
  const ruleId = rule.rule_id
  let ruleCase = ruleId ? customRuleCaseMapRef.value[ruleId] : undefined
  if (!ruleCase && ruleId) {
    ruleCase = qcRuleCaseMapRef.value[ruleId]
  }
  if (ruleCase && buildCaseTextRef.value) {
    const example = type === 'positive' ? ruleCase.positive : ruleCase.negative
    const built = buildCaseTextRef.value(example, {
      includeHints: false,
      includeFocusPoints: false,
      includeTitle: false,
      includeAnalysis: false,
    })
    return normalizeExampleText(built)
  }

  // 3. 若前后端都未提供示例，提示用户手动输入
  return type === 'negative'
    ? '该规则暂无不合规示例病历，请手动输入用于测试规则识别能力的文本。'
    : '该规则暂无合规示例病历，请手动输入用于测试误报率的文本。'
}

// 获取当前规则的案例示例
const currentCaseExample = computed<QCRuleCaseExample | null>(() => {
  if (!props.rule) return null

  const ruleId = props.rule.rule_id
  if (!ruleId) return null

  // 优先从泸县33条规则库查找
  let ruleCase = customRuleCaseMapRef.value[ruleId]

  // 如果没找到，从四川省规则库查找
  if (!ruleCase) {
    ruleCase = qcRuleCaseMapRef.value[ruleId]
  }

  if (!ruleCase) return null

  // 根据示例类型返回对应的正例或反例
  return exampleType.value === 'positive' ? ruleCase.positive : ruleCase.negative
})

// 提取当前示例的提示信息
const currentHints = computed<string[]>(() => {
  if (!currentCaseExample.value || !extractHintsRef.value) return []
  return extractHintsRef.value(currentCaseExample.value)
})

// 提取当前示例的质控关注点
const currentFocusPoints = computed<string[]>(() => {
  if (!currentCaseExample.value || !extractFocusPointsRef.value) return []
  return extractFocusPointsRef.value(currentCaseExample.value)
})

// 状态
const exampleType = ref<'negative' | 'positive'>('negative')
const showExampleInfo = ref<string[]>([])
const medicalText = ref('')
const testing = ref(false)
const testResult = ref<EvaluationResult | null>(null)
const showAILoadingMask = ref(false)

// 默认示例文本
const defaultNegativeText = `入院记录：患者主诉胃痛3天，既往有慢性胃炎病史。

入院查体：
血常规：已检查
生化全套：已检查
胃镜：已检查

诊断：慢性胃炎急性发作`

const defaultPositiveText = `入院记录：患者主诉胃痛3天，既往有慢性胃炎病史。

入院查体：
血常规：WBC 8.5×10^9/L，RBC 4.2×10^12/L，Hb 135g/L，PLT 220×10^9/L
生化全套：ALT 35U/L，AST 28U/L，Cr 75μmol/L，Glu 5.2mmol/L
胃镜：胃窦部黏膜充血水肿，见散在糜烂灶

诊断：慢性胃炎急性发作`

// 监听示例类型切换或规则变化，自动加载对应的案例文本
watch(
  [exampleType, () => props.rule],
  async () => {
    await ensureCaseDataLoaded()
    const rule = props.rule

    // 1. 优先使用后端规则对象里自带的 positive_example / negative_example
    if (rule) {
      const textFromRule = getExampleMedicalText(rule, exampleType.value)
      if (textFromRule && textFromRule.trim()) {
        medicalText.value = textFromRule
        return
      }
    }

    // 2. 若规则中未配置示例，则回退到前端内置案例（与另一个质控评估页面保持一致）
    if (currentCaseExample.value && buildCaseTextRef.value) {
      medicalText.value = buildCaseTextRef.value(currentCaseExample.value, {
        includeHints: false,
        includeFocusPoints: false,
        includeTitle: false,
        includeAnalysis: false,
      })
      return
    }

    // 3. 最终兜底：使用简单默认示例
    medicalText.value = exampleType.value === 'negative' ? defaultNegativeText : defaultPositiveText
  },
  { immediate: true },
)

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      void ensureCaseDataLoaded()
    }
  },
  { immediate: true },
)

// 结构化解析"发现的问题"
interface ParsedFindings {
  summary: string
  items: Array<{ title: string; content: string }>
  fallback: string
}

const parsedFindings = computed<ParsedFindings>(() => {
  if (!testResult.value || !testResult.value.evidence) {
    return { summary: '', items: [], fallback: '' }
  }

  const text = testResult.value.evidence
  const rawLines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  const dedupedLines: string[] = []
  const seenLines = new Set<string>()
  for (const line of rawLines) {
    if (!seenLines.has(line)) {
      seenLines.add(line)
      dedupedLines.push(line)
    }
  }

  // 尝试识别结构化的条目（如数字开头的列表）
  const items: Array<{ title: string; content: string }> = []
  let summary = ''

  // 如果第一行是总结性的句子（不以数字开头）
  const lines = [...dedupedLines]
  if (lines.length > 0 && !lines[0].match(/^[\d一二三四五六①②③④⑤⑥⑦⑧⑨⑩][.、]/)) {
    summary = lines[0]
    lines.shift()
  }

  // 解析每一行为条目
  for (const line of lines) {
    const match = line.match(/^([\d一二三四五六①②③④⑤⑥⑦⑧⑨⑩][.、])\s*(.*)$/)
    if (match) {
      // 匹配到编号列表
      const content = match[2]
      // 进一步分解标题和内容
      const colonIndex = content.indexOf('：')
      if (colonIndex > 0) {
        items.push({
          title: content.substring(0, colonIndex),
          content: content.substring(colonIndex + 1).trim(),
        })
      } else {
        items.push({
          title: content,
          content: '',
        })
      }
    }
  }

  // 计算fallback时，确保不重复summary的内容
  let fallback = lines.length > 0 ? lines.join('\n') : ''

  // 如果summary存在，且fallback中包含summary，则从fallback中移除
  if (summary && fallback.includes(summary)) {
    fallback = fallback.replace(summary, '').trim()
  }

  return { summary, items, fallback }
})

// 辅助函数
const getDefectTone = (level: string | undefined): StatusTone => {
  const map: Record<string, StatusTone> = {
    严重缺陷: 'error',
    critical: 'error',
    一般缺陷: 'warning',
    major: 'warning',
    轻微缺陷: 'success',
    minor: 'success',
  }
  return (level && map[level]) || 'warning'
}

const getComplexityTone = (complexity: string | undefined): StatusTone => {
  const map: Record<string, StatusTone> = {
    高复杂度: 'error',
    中复杂度: 'warning',
    低复杂度: 'success',
  }
  return (complexity && map[complexity]) || 'info'
}

const getDefectLevelText = (level: string | undefined) => {
  const textMap: Record<string, string> = {
    critical: '严重缺陷',
    major: '一般缺陷',
    minor: '轻微缺陷',
  }
  return (level && textMap[level]) || level || ''
}

// 执行测试
const executeTest = async () => {
  if (!props.rule) return

  if (!medicalText.value || medicalText.value.length < 50) {
    message.warning('请输入至少50字的病历文本')
    return
  }

  testing.value = true
  testResult.value = null
  showAILoadingMask.value = true // 显示 AI 加载遮罩

  try {
    const response = await fetch('/api/v1/qc/sichuan/test-rule', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        rule_id: props.rule.rule_id,
        medical_text: medicalText.value,
      }),
    })

    const result = await response.json()

    if (result.success) {
      // 字段映射：后端返回 is_compliant，前端需要 compliant
      const data = result.data
      testResult.value = {
        rule_id: data.rule_id,
        rule_code: data.rule_id, // 后端只返回 rule_id
        rule_name: data.rule_name,
        document_name: '测试病历',
        compliant: data.is_compliant, // 字段映射
        confidence: data.confidence,
        evidence: data.findings, // 发现的问题
        reasoning: data.evidence, // 证据引用
        suggestion: data.suggestion,
        execution_time: data.execution_time,
        medical_text: medicalText.value, // 保存病历原文
      }
      message.success('测试完成')
    } else {
      message.error(result.message || '测试失败')
    }
  } catch (error) {
    console.error('测试失败:', error)
    message.error('测试失败，请检查网络连接')
  } finally {
    testing.value = false
    showAILoadingMask.value = false // 隐藏 AI 加载遮罩
  }
}

// 提供反馈
const provideFeedback = () => {
  if (testResult.value) {
    emit('feedback', testResult.value)
  }
}

// 关闭弹窗
const handleClose = () => {
  isVisible.value = false
  testResult.value = null
  medicalText.value = defaultNegativeText
  exampleType.value = 'negative'
}
</script>

<style scoped lang="less">
.rule-test-modal {
  .rule-test-container {
    .rule-info-card,
    .medical-text-card,
    .result-card {
      margin-bottom: 20px;
      border: 1px solid #d9d9d9 !important;
      border-radius: 8px !important;
      box-shadow: 0 2px 12px rgba(0, 0, 0, 0.12) !important;
      transition: all 0.3s ease;
      overflow: hidden;

      &:hover {
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15) !important;
        transform: translateY(-2px);
        border-color: #2b6cf6 !important;
      }

      :deep(.ant-card-head) {
        background: linear-gradient(to bottom, #fafafa, #f5f5f5);
        font-weight: 600;
        border-bottom: 2px solid #e8e8e8;
        padding: 16px 24px;
        font-size: 16px;
      }

      :deep(.ant-card-head-title) {
        color: #262626;
        font-weight: 600;
      }

      :deep(.ant-card-body) {
        padding: 24px;
        background-color: #ffffff;
      }
    }

    .info-item {
      &.centered {
        text-align: center;
      }

      .info-label {
        display: block;
        font-size: 15px;
        font-weight: 600;
        color: rgba(0, 0, 0, 0.85);
        margin-bottom: 8px;
      }

      .info-value {
        font-size: 14px;
        font-weight: 500;
        color: rgba(0, 0, 0, 0.85);
      }

      .info-description {
        margin: 8px 0 0 0;
        color: rgba(0, 0, 0, 0.65);
        line-height: 1.6;
      }
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      padding: 4px 12px;
      border-radius: 12px;
      font-size: 13px;
      font-weight: 500;

      &--success {
        background: #f6ffed;
        color: #52c41a;
      }

      &--warning {
        background: #fff7e6;
        color: #faad14;
      }

      &--error {
        background: #fff2f0;
        color: #ff4d4f;
      }

      &--info {
        background: #e6f7ff;
        color: #2b6cf6;
      }

      &__icon {
        margin-right: 4px;
        font-size: 14px;
      }
    }

    .doc-tag {
      margin: 2px;
    }

    .medical-input-container {
      position: relative;

      .example-type-selector {
        display: inline-flex;
        background: #f5f7fb;
        padding: 4px;
        border-radius: 24px;
        gap: 4px;

        :deep(.ant-radio-button-wrapper) {
          border-radius: 20px;
          border: 1px solid transparent;
          padding: 4px 14px;
          font-size: 12px;
          height: 32px;
          line-height: 22px;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          color: #595959;
          background: transparent;
          transition: all 0.2s;

          &:not(.ant-radio-button-wrapper-checked) {
            background: transparent !important;
            border-color: transparent !important;
          }

          &.negative-btn.ant-radio-button-wrapper-checked {
            background: #fff1f0 !important;
            border-color: rgba(245, 34, 45, 0.3) !important;
            color: #cf1322 !important;
          }

          &.positive-btn.ant-radio-button-wrapper-checked {
            background: #e8f8e5 !important;
            border-color: rgba(82, 196, 26, 0.3) !important;
            color: #389e0d !important;
          }
        }

        .radio-icon {
          font-size: 14px;
        }
      }

      .example-info-collapse {
        :deep(.ant-collapse-header) {
          padding: 8px 12px;
          background: #fafafa;
        }

        .panel-header {
          display: flex;
          align-items: center;
          font-size: 13px;

          .panel-title {
            font-weight: 500;
          }

          .panel-subtitle {
            margin-left: 8px;
            color: rgba(0, 0, 0, 0.45);
            font-size: 12px;
          }
        }

        .example-info-content {
          .info-section {
            padding: 12px;
            border-radius: 4px;

            &--analysis {
              background: #f0f5ff;
            }

            .section-title {
              display: flex;
              align-items: center;
              font-weight: 500;
              margin-bottom: 12px;
              color: rgba(0, 0, 0, 0.85);

              &__icon {
                margin-right: 6px;
                color: #2b6cf6;
              }
            }

            .section-content {
              .analysis-summary {
                &__title {
                  font-weight: 500;
                  margin-bottom: 8px;
                  color: rgba(0, 0, 0, 0.85);
                }

                .focus-point-item {
                  display: flex;
                  margin-bottom: 6px;
                  line-height: 1.6;

                  .point-index {
                    color: #2b6cf6;
                    font-weight: 500;
                    margin-right: 6px;
                  }

                  .point-text {
                    flex: 1;
                    color: rgba(0, 0, 0, 0.65);
                  }
                }
              }
            }
          }
        }
      }

      .medical-textarea {
        font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        font-size: 13px;
        line-height: 1.6;
      }

      .action-bar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 12px;

        .hint-text {
          color: #595959;
          font-size: 14px;
          font-weight: 500;

          .hint-icon {
            margin-right: 4px;
            color: #faad14;
          }
        }

        .test-btn {
          font-weight: 500;
        }
      }

      .ai-loading-mask {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 100;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 255, 255, 0.3);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border-radius: 12px;
        animation: fadeIn 0.3s ease;

        .ai-loading-content {
          text-align: center;

          .ai-loading-text {
            margin-top: 16px;
            font-size: 14px;
            color: rgba(0, 0, 0, 0.65);
          }
        }
      }

      @keyframes fadeIn {
        from {
          opacity: 0;
        }
        to {
          opacity: 1;
        }
      }
    }

    .result-card {
      background: #fff;
      border: 1px solid #f0f0f0;
      border-radius: 8px;
      overflow: hidden;

      .card-header {
        padding: 16px;
        background: #fafafa;
        border-bottom: 1px solid #f0f0f0;

        .card-title {
          margin: 0;
          font-size: 16px;
          font-weight: 500;
        }
      }

      .card-body {
        padding: 16px;

        .result-status {
          display: flex;
          align-items: center;
          padding: 20px;
          border-radius: 8px;
          margin-bottom: 16px;

          &--success {
            background: #f6ffed;
          }

          &--warning {
            background: #fff7e6;
          }

          .status-icon {
            margin-right: 16px;

            &__graphic {
              font-size: 48px;
            }
          }

          .status-text {
            flex: 1;

            h4 {
              margin: 0 0 12px 0;
              font-size: 18px;
            }

            .result-progress {
              margin-bottom: 8px;
            }

            .confidence-text {
              margin: 0;
              font-size: 13px;
              color: rgba(0, 0, 0, 0.65);
            }
          }
        }

        .result-details {
          .detail-item {
            margin-bottom: 16px;

            .detail-label {
              display: flex;
              align-items: center;
              font-weight: 500;
              margin-bottom: 8px;
              color: rgba(0, 0, 0, 0.85);

              :deep(.anticon) {
                margin-right: 6px;
                color: #2b6cf6;
              }
            }

            .detail-content {
              padding: 12px;
              background: #fafafa;
              border-radius: 4px;
              color: rgba(0, 0, 0, 0.65);
              line-height: 1.6;

              &.structured-findings {
                .findings-summary {
                  margin: 0 0 12px 0;
                  font-weight: 500;
                  color: rgba(0, 0, 0, 0.85);
                }

                .findings-list {
                  .findings-item {
                    margin-bottom: 12px;

                    &:last-child {
                      margin-bottom: 0;
                    }

                    .findings-item-header {
                      display: flex;
                      align-items: baseline;
                      gap: 8px;
                      margin-bottom: 4px;

                      .findings-item-number {
                        flex-shrink: 0;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        background: #2b6cf6;
                        color: white;
                        font-size: 12px;
                        font-weight: 600;
                      }

                      strong {
                        color: rgba(0, 0, 0, 0.85);
                        font-weight: 500;
                      }
                    }

                    .findings-item-content {
                      padding-left: 28px;
                      color: rgba(0, 0, 0, 0.65);
                      font-size: 14px;
                      line-height: 1.6;
                    }
                  }
                }

                .findings-fallback {
                  margin: 0;
                  white-space: pre-wrap;
                  line-height: 1.6;
                }
              }

              &.evidence-box {
                background: #f5f5f5;

                .evidence-text {
                  margin: 0;
                  white-space: pre-wrap;
                  font-family: 'Monaco', 'Menlo', monospace;
                  font-size: 14px;
                  line-height: 1.6;
                }
              }

              &.suggestion-box {
                background: #fff7e6;

                .suggestion-text {
                  margin: 0;
                  white-space: pre-wrap;
                  line-height: 1.8;
                  color: rgba(0, 0, 0, 0.85);
                  font-size: 14px;
                }
              }
            }
          }
        }

        .result-actions {
          text-align: right;
          padding-top: 16px;
          border-top: 1px solid #f0f0f0;

          .feedback-btn {
            background: linear-gradient(135deg, #fa8c16 0%, #ff7a45 100%);
            border-color: #fa8c16;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(250, 140, 22, 0.3);

            &:hover {
              background: linear-gradient(135deg, #ff9c2e 0%, #ff8a5b 100%);
              border-color: #ff9c2e;
              box-shadow: 0 4px 12px rgba(250, 140, 22, 0.4);
              transform: translateY(-1px);
            }
          }
        }
      }
    }
  }
}
</style>
