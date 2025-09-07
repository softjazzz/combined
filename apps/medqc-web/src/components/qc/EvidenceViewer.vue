<template>
  <div class="evidence-viewer">
    <!-- 佐证依据触发按钮 -->
    <a-button 
      type="link" 
      size="small" 
      @click="showEvidence = !showEvidence"
      class="evidence-trigger"
    >
      <template #icon>
        <EyeOutlined v-if="!showEvidence" />
        <EyeInvisibleOutlined v-else />
      </template>
      {{ showEvidence ? '隐藏佐证依据' : '查看佐证依据' }}
    </a-button>

    <!-- 佐证依据内容 -->
    <a-collapse 
      v-model:activeKey="activeKey" 
      v-if="showEvidence"
      class="evidence-collapse mt-3"
      ghost
    >
      <a-collapse-panel key="evidence" header="📋 佐证依据详情">
        <div class="evidence-content">
          
          <!-- 评估结论摘要 -->
          <div class="evidence-summary mb-4">
            <div class="flex items-center mb-2">
              <component 
                :is="getComplianceIcon()" 
                :style="{ color: getComplianceColor(), fontSize: '16px' }"
                class="mr-2"
              />
              <span class="font-medium text-gray-800">
                评估结论: {{ evidence.is_compliant ? '✅ 合规' : '❌ 不合规' }}
              </span>
              <a-tag 
                :color="getConfidenceColor()" 
                class="ml-2"
              >
                置信度: {{ Math.round(evidence.confidence * 100) }}%
              </a-tag>
            </div>
          </div>

          <!-- 评估发现 -->
          <div class="evidence-findings mb-4">
            <h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center">
              <SearchOutlined class="mr-1" />
              评估发现
            </h4>
            <div class="bg-blue-50 border-l-4 border-blue-400 p-3 rounded-r">
              <p class="text-sm text-gray-700 leading-relaxed">
                {{ evidence.findings || '暂无详细发现说明' }}
              </p>
            </div>
          </div>

          <!-- 支撑证据 -->
          <div class="evidence-support mb-4">
            <h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center">
              <FileTextOutlined class="mr-1" />
              支撑证据
            </h4>
            <div class="evidence-quotes">
              <div 
                v-for="(quote, index) in parsedEvidence" 
                :key="index"
                class="evidence-quote mb-3"
              >
                <div class="quote-header flex items-center justify-between mb-2">
                  <span class="text-xs text-gray-500 font-medium">
                    📍 {{ quote.location || `证据片段 ${index + 1}` }}
                  </span>
                  <a-button 
                    type="link" 
                    size="small" 
                    @click="highlightInOriginal(quote.text)"
                    class="text-xs"
                  >
                    <template #icon><AimOutlined /></template>
                    定位原文
                  </a-button>
                </div>
                <div class="quote-content bg-yellow-50 border border-yellow-200 rounded p-3">
                  <blockquote class="text-sm text-gray-800 italic leading-relaxed">
                    "{{ quote.text }}"
                  </blockquote>
                  <div v-if="quote.explanation" class="quote-explanation mt-2 pt-2 border-t border-yellow-200">
                    <p class="text-xs text-gray-600">
                      <strong>说明:</strong> {{ quote.explanation }}
                    </p>
                  </div>
                </div>
              </div>
              
              <!-- 无证据时的提示 -->
              <div v-if="parsedEvidence.length === 0" class="no-evidence text-center py-4">
                <InboxOutlined class="text-gray-400 text-2xl mb-2" />
                <p class="text-sm text-gray-500">暂无具体支撑证据</p>
              </div>
            </div>
          </div>

          <!-- 评估逻辑说明 -->
          <div class="evidence-reasoning">
            <h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center">
              <BulbOutlined class="mr-1" />
              评估逻辑
            </h4>
            <div class="bg-green-50 border-l-4 border-green-400 p-3 rounded-r">
              <p class="text-sm text-gray-700 leading-relaxed">
                {{ evidence.reasoning || getDefaultReasoning() }}
              </p>
            </div>
          </div>

          <!-- 改进建议 (仅不合规时显示) -->
          <div v-if="!evidence.is_compliant && evidence.suggestions" class="evidence-suggestions mt-4">
            <h4 class="text-sm font-semibold text-gray-700 mb-2 flex items-center">
              <BulbOutlined class="mr-1" />
              改进建议
            </h4>
            <div class="bg-orange-50 border-l-4 border-orange-400 p-3 rounded-r">
              <ul class="text-sm text-gray-700 space-y-1">
                <li v-for="(suggestion, index) in evidence.suggestions" :key="index" class="flex items-start">
                  <span class="text-orange-500 mr-2">•</span>
                  <span>{{ suggestion }}</span>
                </li>
              </ul>
            </div>
          </div>

        </div>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, defineProps, defineEmits } from 'vue'
import {
  EyeOutlined,
  EyeInvisibleOutlined,
  SearchOutlined,
  FileTextOutlined,
  BulbOutlined,
  AimOutlined,
  InboxOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons-vue'

// 组件属性
interface EvidenceData {
  rule_id: string
  rule_name: string
  is_compliant: boolean
  confidence: number
  findings: string
  evidence: string
  reasoning: string
  suggestions?: string[]
  evidence_locations?: string[]
}

const props = defineProps<{
  evidence: EvidenceData
  documentType?: string
}>()

const emit = defineEmits<{
  highlightText: [text: string]
}>()

// 组件状态
const showEvidence = ref(false)
const activeKey = ref(['evidence'])

// 解析证据内容
const parsedEvidence = computed(() => {
  if (!props.evidence.evidence) return []

  try {
    const evidence = props.evidence.evidence
    const evidenceLocations = props.evidence.evidence_locations || []

    // 如果是JSON格式
    if (evidence.startsWith('[') || evidence.startsWith('{')) {
      const parsed = JSON.parse(evidence)
      return Array.isArray(parsed) ? parsed : [parsed]
    }

    // 如果包含分号分隔的多个证据
    if (evidence.includes(';')) {
      const evidenceParts = evidence.split(';').filter(s => s.trim().length > 5)
      return evidenceParts.map((text, index) => ({
        text: text.trim(),
        location: evidenceLocations[index] || `${props.documentType || '病历'}第${index + 1}处`,
        explanation: `此证据${props.evidence.is_compliant ? '支持合规' : '表明不合规'}的判断`
      }))
    }

    // 如果是纯文本，按句号分割
    const sentences = evidence.split(/[。！？]/).filter(s => s.trim().length > 10)
    return sentences.map((text, index) => ({
      text: text.trim(),
      location: evidenceLocations[index] || `${props.documentType || '病历'}第${index + 1}处`,
      explanation: `此证据${props.evidence.is_compliant ? '支持合规' : '表明不合规'}的判断`
    }))

  } catch (error) {
    // 解析失败时返回原始文本
    return [{
      text: props.evidence.evidence,
      location: props.documentType || '病历原文',
      explanation: `此证据${props.evidence.is_compliant ? '支持合规' : '表明不合规'}的判断`
    }]
  }
})

// 获取合规状态图标
const getComplianceIcon = () => {
  return props.evidence.is_compliant ? CheckCircleOutlined : CloseCircleOutlined
}

// 获取合规状态颜色
const getComplianceColor = () => {
  return props.evidence.is_compliant ? '#52c41a' : '#f5222d'
}

// 获取置信度颜色
const getConfidenceColor = () => {
  const confidence = props.evidence.confidence
  if (confidence >= 0.8) return 'green'
  if (confidence >= 0.6) return 'orange'
  return 'red'
}

// 获取默认推理说明
const getDefaultReasoning = () => {
  const compliant = props.evidence.is_compliant
  const ruleName = props.evidence.rule_name
  
  if (compliant) {
    return `根据质控规则"${ruleName}"的要求，通过分析病历内容，发现相关记录完整且符合规范要求，因此评估为合规。`
  } else {
    return `根据质控规则"${ruleName}"的要求，通过分析病历内容，发现存在不符合规范的情况或缺失必要信息，因此评估为不合规。`
  }
}

// 在原文中高亮显示
const highlightInOriginal = (text: string) => {
  emit('highlightText', text)
}
</script>

<style scoped>
.evidence-viewer {
  @apply w-full;
}

.evidence-trigger {
  @apply text-blue-600 hover:text-blue-800 p-0;
}

.evidence-collapse {
  @apply border border-gray-200 rounded-lg bg-white;
}

.evidence-collapse :deep(.ant-collapse-header) {
  @apply bg-gray-50 font-medium;
}

.evidence-collapse :deep(.ant-collapse-content-box) {
  @apply p-4;
}

.evidence-quote {
  @apply transition-all duration-200;
}

.evidence-quote:hover {
  @apply transform scale-[1.01];
}

.quote-content {
  @apply shadow-sm;
}

.quote-content:hover {
  @apply shadow-md;
}

.evidence-summary {
  @apply pb-3 border-b border-gray-200;
}

.no-evidence {
  @apply bg-gray-50 rounded-lg;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .evidence-content {
    @apply text-sm;
  }
  
  .quote-header {
    @apply flex-col items-start space-y-1;
  }
}
</style>
