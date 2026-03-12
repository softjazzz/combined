<template>
  <div class="emr-viewer" ref="viewerRef">
    <!-- 文书标签页 -->
    <div v-if="documents.length > 1" class="doc-tabs flex border-b border-gray-200 mb-4 overflow-x-auto">
      <button
        v-for="doc in documents"
        :key="doc.id"
        @click="activeDocId = doc.id; loadDocument(doc)"
        :class="[
          'px-4 py-2 text-sm font-medium whitespace-nowrap transition-colors border-b-2',
          activeDocId === doc.id
            ? 'border-blue-600 text-blue-600 bg-blue-50/50'
            : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
        ]"
      >
        {{ doc.doc_name || doc.doc_type }}
      </button>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar flex items-center justify-between px-4 py-2 bg-gray-50 rounded-lg border border-gray-200 mb-4">
      <div class="flex items-center gap-3 text-sm text-gray-600">
        <span v-if="metadata.patient_name">
          <UserOutlined /> {{ metadata.patient_name }}
        </span>
        <span v-if="metadata.department" class="text-gray-400">|</span>
        <span v-if="metadata.department">
          <ApartmentOutlined /> {{ metadata.department }}
        </span>
        <span v-if="metadata.doc_type" class="text-gray-400">|</span>
        <span v-if="metadata.doc_type" class="text-blue-600 font-medium">
          {{ metadata.doc_type }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <a-tag v-if="annotations.length > 0" :color="annotations.length > 3 ? 'red' : 'orange'">
          {{ annotations.length }} 个缺陷
        </a-tag>
        <a-tag v-else color="green">无缺陷</a-tag>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="flex items-center justify-center h-64">
      <a-spin tip="正在加载文书内容..." />
    </div>

    <!-- 文书内容 -->
    <div
      v-else-if="renderedContent"
      ref="contentRef"
      class="emr-content prose prose-sm max-w-none p-6 bg-white rounded-xl border border-gray-200 shadow-sm overflow-auto"
      :style="{ maxHeight: maxHeight + 'px' }"
      v-html="renderedContent"
    />

    <!-- 空状态 -->
    <div v-else class="flex flex-col items-center justify-center h-64 text-gray-400">
      <FileTextOutlined class="text-4xl mb-3" />
      <p>暂无文书内容</p>
      <p class="text-xs">请在左侧选择病历</p>
    </div>

    <!-- 缺陷列表面板（悬浮） -->
    <div
      v-if="showAnnotationPanel && annotations.length > 0"
      class="annotation-panel fixed right-4 bottom-4 w-80 max-h-96 bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden z-50"
    >
      <div class="flex items-center justify-between px-4 py-3 bg-gray-50 border-b">
        <span class="text-sm font-bold text-gray-700">缺陷标注 ({{ annotations.length }})</span>
        <button @click="showAnnotationPanel = false" class="text-gray-400 hover:text-gray-600">
          ✕
        </button>
      </div>
      <div class="overflow-y-auto max-h-80 divide-y divide-gray-100">
        <div
          v-for="ann in annotations"
          :key="ann.defect_id"
          :class="[
            'px-4 py-3 cursor-pointer transition-colors text-sm',
            activeDefectId === ann.defect_id ? 'bg-blue-50' : 'hover:bg-gray-50'
          ]"
          @click="handleAnnotationClick(ann)"
        >
          <div class="flex items-center gap-2 mb-1">
            <span
              :class="[
                'w-2 h-2 rounded-full',
                ann.severity === 'critical' ? 'bg-red-500' :
                ann.severity === 'error' ? 'bg-orange-500' :
                ann.severity === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
              ]"
            />
            <span class="font-medium text-gray-700 truncate">{{ ann.rule_name || ann.category }}</span>
          </div>
          <p class="text-gray-500 text-xs line-clamp-2">{{ ann.description }}</p>
        </div>
      </div>
    </div>

    <!-- 缺陷面板触发按钮 -->
    <button
      v-if="annotations.length > 0 && !showAnnotationPanel"
      @click="showAnnotationPanel = true"
      class="fixed right-4 bottom-4 w-12 h-12 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center z-50 transition-transform hover:scale-110"
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

// ============= Props =============
const props = withDefaults(defineProps<{
  recordId?: string
  visitId?: string
  patientId?: string
  instituteId?: string
  docType?: string
  maxHeight?: number
}>(), {
  maxHeight: 600,
})

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
const { activeDefectId, highlightDefects, scrollToDefect, onDefectClick, bindClickEvents } = useDefectHighlight()

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

async function fetchDocuments() {
  const url = buildUrl('documents')
  if (!url) {
    resetViewerState()
    emit('error', 'missing-identifiers')
    return
  }

  try {
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json' },
    })
    const result = await response.json()
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
      emit('error', result?.message || 'load-documents-failed')
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
      headers: { 'Content-Type': 'application/json' },
    })
    const result = await response.json()

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
      emit('error', result?.message || 'load-document-failed')
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
  { immediate: true }
)
</script>

<style scoped>
.emr-content {
  font-family: 'SimSun', 'STSong', serif;
  font-size: 14px;
  line-height: 2;
  white-space: pre-wrap;
  word-break: break-all;
}

.emr-content :deep(.defect-highlight:hover) {
  filter: brightness(0.95);
  outline: 2px solid currentColor;
  outline-offset: 1px;
}
</style>
