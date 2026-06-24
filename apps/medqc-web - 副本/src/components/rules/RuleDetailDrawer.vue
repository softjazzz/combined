<template>
  <a-drawer
    :open="open"
    width="720"
    :title="null"
    :header-style="{ display: 'none' }"
    class="rule-detail-drawer"
    destroy-on-close
    @close="emit('update:open', false)"
  >
    <div
      v-if="rule"
      class="pb-8"
    >
      <!-- 头部 -->
      <div class="flex items-start justify-between mb-6">
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-2 flex-wrap">
            <a-tag
              color="blue"
              class="text-xs font-mono"
            >
              {{ rule.rule_code }}
            </a-tag>
            <a-tag :color="severityColor">
              {{ severityLabel }}
            </a-tag>
            <a-tag :color="categoryColor">
              {{ categoryLabel }}
            </a-tag>
            <a-tag :color="typeColor">
              {{ typeLabel }}
            </a-tag>
          </div>
          <h2 class="text-lg font-bold text-slate-800 leading-tight">
            {{ rule.name }}
          </h2>
        </div>
        <a-button
          type="text"
          class="text-slate-400 hover:text-slate-600 ml-2 shrink-0"
          @click="emit('update:open', false)"
        >
          <template #icon>
            <CloseOutlined />
          </template>
        </a-button>
      </div>

      <!-- 基本信息 -->
      <section class="mb-6">
        <h3 class="section-title">
          <FileTextOutlined class="mr-2" />
          基本信息
        </h3>
        <div class="info-grid">
          <div class="info-item">
            <span class="info-label">状态</span>
            <span>
              <a-badge :status="rule.is_active ? 'success' : 'default'" />
              {{ rule.is_active ? '已激活' : '已停用' }}
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">扣分</span>
            <span>
              <a-tag
                v-if="rule.max_score === 0"
                color="red"
                size="small"
              >单项否决</a-tag>
              <span v-else>{{ rule.max_score }} 分</span>
            </span>
          </div>
          <div class="info-item">
            <span class="info-label">权重</span>
            <span>{{ rule.weight }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">版本</span>
            <span>{{ rule.version || '1.0' }}</span>
          </div>
          <div
            v-if="documentCategoryLabel"
            class="info-item"
          >
            <span class="info-label">文书类型</span>
            <a-tag :color="documentCategoryColor">
              {{ documentCategoryLabel }}
            </a-tag>
          </div>
          <div class="info-item">
            <span class="info-label">创建时间</span>
            <span>{{ formatDate(rule.created_at) }}</span>
          </div>
          <div class="info-item">
            <span class="info-label">更新时间</span>
            <span>{{ formatDate(rule.updated_at) }}</span>
          </div>
        </div>
      </section>

      <!-- 规则描述 -->
      <section class="mb-6">
        <h3 class="section-title">
          <AlignLeftOutlined class="mr-2" />
          规则描述
        </h3>
        <div class="content-block">
          {{ rule.description || '暂无描述' }}
        </div>
      </section>

      <!-- 检查逻辑 -->
      <section
        v-if="hasCheckLogic"
        class="mb-6"
      >
        <h3 class="section-title">
          <CodeOutlined class="mr-2" />
          检查逻辑
        </h3>
        <div class="code-block">
          <pre class="text-xs leading-relaxed">{{ formattedCheckLogic }}</pre>
        </div>
      </section>

      <!-- Prompt 模板 -->
      <section
        v-if="rule.prompt_template"
        class="mb-6"
      >
        <h3 class="section-title">
          <ThunderboltOutlined class="mr-2" />
          Prompt 模板
          <a-button
            type="text"
            size="small"
            class="ml-auto text-slate-400 hover:text-blue-500"
            @click="copyToClipboard(rule.prompt_template!)"
          >
            <template #icon>
              <CopyOutlined />
            </template>
            复制
          </a-button>
        </h3>
        <div class="code-block prompt-block">
          <pre class="text-xs leading-relaxed whitespace-pre-wrap">{{ truncatedPrompt }}</pre>
          <a-button
            v-if="isPromptTruncated"
            type="link"
            size="small"
            class="mt-2"
            @click="showFullPrompt = !showFullPrompt"
          >
            {{ showFullPrompt ? '收起' : '展开全部' }}（{{ rule.prompt_template!.length }} 字符）
          </a-button>
        </div>
      </section>

      <!-- 正例 / 反例 -->
      <section
        v-if="positiveExample || negativeExample"
        class="mb-6"
      >
        <h3 class="section-title">
          <ExperimentOutlined class="mr-2" />
          正反示例
        </h3>
        <a-tabs
          size="small"
          type="card"
        >
          <a-tab-pane
            v-if="positiveExample"
            key="positive"
          >
            <template #tab>
              <CheckCircleOutlined class="text-green-500 mr-1" />
              合规示例
            </template>
            <div class="example-block example-positive">
              <pre class="text-xs leading-relaxed whitespace-pre-wrap">{{ positiveExample }}</pre>
            </div>
          </a-tab-pane>
          <a-tab-pane
            v-if="negativeExample"
            key="negative"
          >
            <template #tab>
              <CloseCircleOutlined class="text-red-500 mr-1" />
              违规示例
            </template>
            <div class="example-block example-negative">
              <pre class="text-xs leading-relaxed whitespace-pre-wrap">{{ negativeExample }}</pre>
            </div>
          </a-tab-pane>
        </a-tabs>
      </section>

      <!-- 底部操作 -->
      <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
        <a-button @click="emit('edit', rule)">
          <template #icon>
            <EditOutlined />
          </template>
          编辑规则
        </a-button>
        <a-button
          type="primary"
          @click="emit('test', rule)"
        >
          <template #icon>
            <PlayCircleOutlined />
          </template>
          测试规则
        </a-button>
      </div>
    </div>

    <!-- 空状态 -->
    <div
      v-else
      class="flex items-center justify-center h-64"
    >
      <a-empty description="请选择一条规则查看详情" />
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  CloseOutlined,
  FileTextOutlined,
  AlignLeftOutlined,
  CodeOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  ExperimentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  EditOutlined,
  PlayCircleOutlined
} from '@ant-design/icons-vue'
import { DocumentCategoryService } from '@/services/document-category-service'
import type { DocumentCategory } from '@/types/medical'

interface Props {
  open: boolean
  rule: Record<string, any> | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  edit: [rule: Record<string, any>]
  test: [rule: Record<string, any>]
}>()

const showFullPrompt = ref(false)

// 配置映射
const CONFIG = {
  categories: {
    completeness: { label: '完整性', color: 'blue' },
    consistency: { label: '一致性', color: 'green' },
    rationality: { label: '合理性', color: 'orange' },
    timeliness: { label: '及时性', color: 'purple' }
  } as Record<string, { label: string; color: string }>,
  severities: {
    critical: { label: '严重', color: 'red' },
    major: { label: '重要', color: 'orange' },
    minor: { label: '轻微', color: 'blue' }
  } as Record<string, { label: string; color: string }>,
  types: {
    logical: { label: '逻辑规则', color: 'cyan' },
    semantic: { label: '语义规则', color: 'magenta' },
    hybrid: { label: '混合规则', color: 'geekblue' }
  } as Record<string, { label: string; color: string }>
}

const severityLabel = computed(() => CONFIG.severities[props.rule?.severity]?.label || props.rule?.severity || '')
const severityColor = computed(() => CONFIG.severities[props.rule?.severity]?.color || 'default')
const categoryLabel = computed(() => CONFIG.categories[props.rule?.category]?.label || props.rule?.category || '')
const categoryColor = computed(() => CONFIG.categories[props.rule?.category]?.color || 'default')
const typeLabel = computed(() => CONFIG.types[props.rule?.rule_type]?.label || props.rule?.rule_type || '')
const typeColor = computed(() => CONFIG.types[props.rule?.rule_type]?.color || 'default')

const documentCategoryLabel = computed(() => {
  const cat = props.rule?.primary_document_category || props.rule?.resolvedPrimary
  if (!cat) return ''
  try {
    const config = DocumentCategoryService.getDocumentCategoryDisplayConfig(cat as DocumentCategory)
    return config.label !== cat ? config.label : ''
  } catch {
    return ''
  }
})

const documentCategoryColor = computed(() => {
  const cat = props.rule?.primary_document_category || props.rule?.resolvedPrimary
  if (!cat) return undefined
  try {
    const config = DocumentCategoryService.getDocumentCategoryDisplayConfig(cat as DocumentCategory)
    return config.color
  } catch {
    return undefined
  }
})

const hasCheckLogic = computed(() => {
  const cl = props.rule?.check_logic
  return cl && typeof cl === 'object' && Object.keys(cl).length > 0
})

const formattedCheckLogic = computed(() => {
  try {
    return JSON.stringify(props.rule?.check_logic, null, 2)
  } catch {
    return String(props.rule?.check_logic)
  }
})

const PROMPT_TRUNCATE_LENGTH = 500

const isPromptTruncated = computed(() => {
  return (props.rule?.prompt_template?.length || 0) > PROMPT_TRUNCATE_LENGTH
})

const truncatedPrompt = computed(() => {
  const tpl = props.rule?.prompt_template || ''
  if (showFullPrompt.value || tpl.length <= PROMPT_TRUNCATE_LENGTH) return tpl
  return tpl.slice(0, PROMPT_TRUNCATE_LENGTH) + '...'
})

const positiveExample = computed(() => props.rule?.positive_example || props.rule?.check_logic?.positive_example || '')
const negativeExample = computed(() => props.rule?.negative_example || props.rule?.check_logic?.negative_example || '')

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateStr
  }
}

const copyToClipboard = async (text: string) => {
  try {
    await navigator.clipboard.writeText(text)
    message.success('已复制到剪贴板')
  } catch {
    message.error('复制失败')
  }
}
</script>

<style scoped>
.section-title {
  @apply flex items-center text-sm font-semibold text-slate-700 mb-3 pb-2 border-b border-slate-100;
}

.info-grid {
  @apply grid grid-cols-2 gap-x-6 gap-y-3;
}

.info-item {
  @apply flex items-center justify-between text-sm;
}

.info-label {
  @apply text-slate-400 font-medium;
}

.content-block {
  @apply bg-slate-50 rounded-lg p-4 text-sm text-slate-700 leading-relaxed border border-slate-100;
}

.code-block {
  @apply bg-slate-900 rounded-lg p-4 text-slate-200 overflow-auto;
  max-height: 300px;
}

.prompt-block {
  @apply bg-indigo-950;
  max-height: 400px;
}

.example-block {
  @apply rounded-lg p-4 overflow-auto text-slate-700 border;
  max-height: 300px;
}

.example-positive {
  @apply bg-green-50 border-green-200;
}

.example-negative {
  @apply bg-red-50 border-red-200;
}
</style>
