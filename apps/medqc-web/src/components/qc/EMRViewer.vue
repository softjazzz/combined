<template>
  <div
    ref="viewerRef"
    class="emr-viewer"
  >
    <!-- 文书标签页（仅在没有外部导航时显示） -->
    <div
      v-if="!hideDocTabs && documents.length > 1"
      class="mb-5"
    >
      <div
        class="inline-flex items-center gap-1 bg-gray-100/80 p-1 rounded-xl border border-gray-100/50"
      >
        <button
          v-for="doc in documents"
          :key="doc.id"
          :class="[
            'px-4 py-1.5 text-[13px] font-medium whitespace-nowrap rounded-lg transition-all duration-200',
            activeDocId === doc.id
              ? 'bg-white text-blue-700 shadow-[0_1px_3px_rgba(0,0,0,0.08)]'
              : 'text-gray-500 hover:text-gray-700',
          ]"
          @click="
            activeDocId = doc.id
            loadDocument(doc)
          "
        >
          {{ doc.doc_name || doc.doc_type }}
        </button>
      </div>
    </div>

    <!-- 工具栏已移除：患者/科室信息由外层 Header 展示 -->

    <!-- 加载中 -->
    <div
      v-if="loading"
      class="flex items-center justify-center h-64"
    >
      <a-spin tip="正在加载文书内容..." />
    </div>

    <!-- 文书内容 -->
    <div
      v-else-if="renderedContent"
      ref="contentRef"
      class="emr-content overflow-auto"
      :style="{ maxHeight: maxHeight + 'px' }"
      v-html="renderedContent"
    />

    <!-- 空状态 -->
    <div
      v-else
      class="flex flex-col items-center justify-center h-64 text-gray-400"
    >
      <FileTextOutlined class="text-4xl mb-3" />
      <p>暂无文书内容</p>
      <p class="text-xs">
        请在左侧选择病历
      </p>
    </div>

    <!-- 缺陷列表面板（悬浮） -->
    <div
      v-if="showAnnotationPanel && annotations.length > 0"
      class="annotation-panel fixed bottom-4 right-4 z-50 max-h-[26rem] w-72 overflow-hidden rounded-[18px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(248,250,252,0.98))] shadow-[0_16px_34px_rgba(15,23,42,0.14)] backdrop-blur-xl"
    >
      <div
        class="flex items-center justify-between border-b border-slate-200/80 bg-white/72 px-4 py-3"
      >
        <span class="text-sm font-bold text-slate-700">缺陷标注 ({{ annotations.length }})</span>
        <button
          class="text-slate-400 transition-colors hover:text-slate-600"
          @click="showAnnotationPanel = false"
        >
          ✕
        </button>
      </div>
      <div class="max-h-80 overflow-y-auto divide-y divide-slate-100">
        <div
          v-for="ann in annotations"
          :key="ann.defect_id"
          :class="[
            'px-4 py-3 cursor-pointer transition-colors text-sm',
            activeDefectId === ann.defect_id ? 'bg-blue-50/80' : 'hover:bg-slate-50/80',
          ]"
          @click="handleAnnotationClick(ann)"
        >
          <div class="flex items-center gap-2 mb-1">
            <span
              :class="[
                'w-2 h-2 rounded-full',
                ann.severity === 'critical'
                  ? 'bg-blue-700'
                  : ann.severity === 'error'
                    ? 'bg-blue-600'
                    : ann.severity === 'warning'
                      ? 'bg-blue-500'
                      : 'bg-blue-400',
              ]"
            />
            <span class="font-medium text-slate-700 truncate">{{
              ann.rule_name || ann.category
            }}</span>
          </div>
          <p class="text-slate-500 text-xs line-clamp-2">
            {{ ann.description }}
          </p>
        </div>
      </div>
    </div>

    <!-- 缺陷面板触发按钮 -->
    <button
      v-if="annotations.length > 0 && !showAnnotationPanel"
      class="fixed right-4 bottom-4 z-50 flex h-11 w-11 items-center justify-center rounded-full bg-blue-600 text-white shadow-[0_12px_24px_rgba(37,99,235,0.22)] transition-all hover:scale-105 hover:bg-blue-700"
      @click="showAnnotationPanel = true"
    >
      <span class="text-sm font-bold">{{ annotations.length }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { UserOutlined, ApartmentOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { useDefectHighlight } from '@/composables/useDefectHighlight'
import type { DefectAnnotation } from '@/composables/useDefectHighlight'
import { getAccessToken } from '@/utils/auth-token'

// ============= Props =============
const props = withDefaults(
  defineProps<{
    recordId?: string
    visitId?: string
    patientId?: string
    instituteId?: string
    docType?: string
    maxHeight?: number
    hideDocTabs?: boolean // 外部已有文书导航时，隐藏内部 Tab
  }>(),
  {
    maxHeight: 600,
    hideDocTabs: false,
  },
)

const emit = defineEmits<{
  (e: 'defect-click', defectId: string): void
  (e: 'loaded', data: any): void
  (e: 'error', reason?: string): void
}>()

// ============= 状态 =============
const loading = ref(false)
const rawContent = ref('')
const contentType = ref<'text' | 'html'>('text')
const metadata = ref<Record<string, string>>({})
const annotations = ref<DefectAnnotation[]>([])
const documents = ref<any[]>([])
const activeDocId = ref<string | null>(null)
const showAnnotationPanel = ref(false)

const viewerRef = ref<HTMLElement>()
const contentRef = ref<HTMLElement>()

// 高亮 composable
const { activeDefectId, highlightDefects, scrollToDefect, onDefectClick, bindClickEvents } =
  useDefectHighlight()

const effectiveRecordId = computed(() => props.recordId || props.visitId || '')
const hasTripletContext = computed(() => !!(props.visitId && props.patientId && props.instituteId))

const baseQueryString = computed(() => {
  const params = new URLSearchParams()
  if (props.visitId) params.append('visit_id', props.visitId)
  if (props.patientId) params.append('patient_id', props.patientId)
  if (props.instituteId) params.append('institute_id', props.instituteId)
  return params.toString()
})

// ============= 计算属性 =============
const renderedContent = computed(() => {
  if (!rawContent.value) return ''

  if (contentType.value === 'html') {
    // HTML 内容：直接渲染（后续可加 DOMPurify 净化）
    return rawContent.value
  }

  // 纯文本：注入高亮标记
  return highlightDefects(rawContent.value, annotations.value)
})

// ============= 方法 =============
function buildUrl(path: 'documents' | 'render', extraParams?: Record<string, string>) {
  const baseId = effectiveRecordId.value
  if (!baseId) return ''
  const params = new URLSearchParams(baseQueryString.value)
  Object.entries(extraParams || {}).forEach(([key, value]) => {
    if (value) params.append(key, value)
  })
  const query = params.toString()
  return `/api/v1/emr/${encodeURIComponent(baseId)}/${path}${query ? `?${query}` : ''}`
}

function resetViewerState() {
  rawContent.value = ''
  contentType.value = 'text'
  metadata.value = {}
  annotations.value = []
  documents.value = []
  activeDocId.value = null
}

function getAuthHeaders(): Record<string, string> {
  const token = getAccessToken()

  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }
}

function readEnvelopeMessage(result: unknown, fallbackMessage: string): string {
  if (!result || typeof result !== 'object') return fallbackMessage

  const envelope = result as {
    message?: unknown
    normalized?: {
      message?: unknown
    }
  }

  const normalizedMessage = envelope.normalized?.message
  if (typeof normalizedMessage === 'string' && normalizedMessage.trim()) {
    return normalizedMessage
  }

  if (typeof envelope.message === 'string' && envelope.message.trim()) {
    return envelope.message
  }

  return fallbackMessage
}

async function fetchDocuments() {
  const url = buildUrl('documents')
  if (!url) {
    resetViewerState()
    emit('error', 'missing-identifiers')
    return
  }

  try {
    const response = await fetch(url, {
      headers: getAuthHeaders(),
    })
    const result = await response.json()
    if (response.status === 401 || response.status === 403) {
      emit('error', 'unauthorized')
      return
    }
    if (result?.success !== false) {
      documents.value = result?.data || []
      if (documents.value.length > 0) {
        activeDocId.value = documents.value[0].id
        await loadDocument(documents.value[0])
      } else {
        rawContent.value = ''
        annotations.value = []
        emit('error', 'no-documents')
      }
    } else {
      emit('error', readEnvelopeMessage(result, 'load-documents-failed'))
    }
  } catch (err) {
    console.error('获取文书列表失败:', err)
    emit('error', 'load-documents-failed')
  }
}

async function loadDocument(doc?: any) {
  loading.value = true
  try {
    const extraParams: Record<string, string> = {}
    if (doc?.doc_type) extraParams.doc_type = doc.doc_type
    if (doc?.id) extraParams.doc_id = doc.id
    const url = buildUrl('render', extraParams)
    if (!url) {
      emit('error', 'missing-identifiers')
      return
    }
    const response = await fetch(url, {
      headers: getAuthHeaders(),
    })
    const result = await response.json()
    if (response.status === 401 || response.status === 403) {
      emit('error', 'unauthorized')
      return
    }

    if (result?.success !== false && result?.data) {
      const data = result.data
      rawContent.value = data.content || ''
      contentType.value = data.content_type || 'text'
      metadata.value = data.metadata || {}
      annotations.value = data.defect_annotations || []

      if (rawContent.value) {
        emit('loaded', data)
      } else {
        emit('error', 'empty-content')
      }

      // 绑定高亮点击事件
      nextTick(() => {
        if (contentRef.value) {
          bindClickEvents(contentRef.value)
        }
      })
    } else {
      emit('error', readEnvelopeMessage(result, 'load-document-failed'))
    }
  } catch (err) {
    console.error('加载文书内容失败:', err)
    emit('error', 'load-document-failed')
  } finally {
    loading.value = false
  }
}

function handleAnnotationClick(ann: DefectAnnotation) {
  scrollToDefect(ann.defect_id, contentRef.value)
  emit('defect-click', ann.defect_id)
}

// 对外暴露：供父组件调用
function scrollTo(defectId: string) {
  scrollToDefect(defectId, contentRef.value)
}

defineExpose({ scrollTo, loadDocument })

// ============= 生命周期 =============
onDefectClick((defectId) => {
  emit('defect-click', defectId)
})

watch(
  () => [props.recordId, props.visitId, props.patientId, props.instituteId, props.docType],
  () => {
    if (effectiveRecordId.value || hasTripletContext.value) {
      fetchDocuments()
    } else {
      resetViewerState()
    }
  },
  { immediate: true },
)
</script>

<style scoped>
/* ============ 阅读区外壳 ============ */
.emr-content {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(252, 253, 255, 0.98));
  border-radius: 10px;
  border: 1px solid rgba(226, 232, 240, 0.56);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.025);
  padding: 12px 14px 22px;
  /* 文字排版黄金参数 */
  font-family: 'PingFang SC', 'Microsoft YaHei', 'SimSun', serif;
  font-size: 14px;
  line-height: 1.9;
  color: #475569; /* slate-600：不用纯黑，减少长时间阅读视网膜疲劳 */
  white-space: pre-wrap;
  word-break: break-all;
  /* 人体工学最大宽度，自动居中 */
  max-width: 104ch;
  margin: 0 auto;
}

/* ============ 段落标题（块级视觉锚点） ============ */
.emr-content :deep(.emr-section-title) {
  display: block;
  font-weight: 700;
  color: #1e293b; /* slate-900：比正文深，立刻抓住视线 */
  font-size: 14px;
  margin-top: 1.15em;
  margin-bottom: 0.1em;
  letter-spacing: 0.01em;
}

.emr-content :deep(.emr-section-title:first-child) {
  margin-top: 0;
}

/* ============ 缺陷高亮（虚线下划线，克制） ============ */
.emr-content :deep(.emr-defect) {
  position: relative;
  cursor: help;
  border-bottom: 1.5px dashed;
  padding-bottom: 1px;
  transition:
    background-color 0.15s,
    border-color 0.15s;
}
.emr-content :deep(.emr-defect--critical) {
  background-color: rgba(219, 234, 254, 0.82);
  border-color: #2563eb;
}
.emr-content :deep(.emr-defect--error) {
  background-color: rgba(239, 246, 255, 0.82);
  border-color: #3b82f6;
}
.emr-content :deep(.emr-defect--warning) {
  background-color: rgba(239, 246, 255, 0.62);
  border-color: #60a5fa;
}
.emr-content :deep(.emr-defect--info) {
  background-color: rgba(239, 246, 255, 0.52);
  border-color: #3b82f6;
}
.emr-content :deep(.emr-defect:hover) {
  filter: brightness(0.97);
}

/* ============ Tooltip 卡片（pure CSS hover） ============ */
.emr-content :deep(.emr-defect-tip) {
  display: none;
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 200;
  width: 260px;
  background: #fff;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.12);
  padding: 11px 13px;
  pointer-events: none;
  white-space: normal;
  word-break: break-all;
}
.emr-content :deep(.emr-defect:hover .emr-defect-tip) {
  display: block;
}
.emr-content :deep(.emr-defect-tip__header) {
  display: flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 7px;
  padding-bottom: 7px;
  border-bottom: 1px solid #f1f5f9;
}
.emr-content :deep(.emr-defect-tip__header--critical) {
  color: #1d4ed8;
}
.emr-content :deep(.emr-defect-tip__header--error) {
  color: #2563eb;
}
.emr-content :deep(.emr-defect-tip__header--warning) {
  color: #3b82f6;
}
.emr-content :deep(.emr-defect-tip__header--info) {
  color: #2563eb;
}
.emr-content :deep(.emr-defect-tip__body) {
  font-size: 12.5px;
  line-height: 1.6;
  color: #475569;
}
.emr-content :deep(.emr-defect-tip__suggest) {
  margin-top: 7px;
  padding-top: 7px;
  border-top: 1px solid #f1f5f9;
  font-size: 12px;
  color: #64748b;
  line-height: 1.55;
}

@media (max-width: 960px) {
  .emr-content {
    padding: 12px 14px 18px;
    max-width: none;
  }
}
</style>
