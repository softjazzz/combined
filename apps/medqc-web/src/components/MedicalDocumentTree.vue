<template>
  <div class="doc-tree glass-card">
    <a-typography-title :level="5" class="mb-3">医疗文书目录</a-typography-title>

    <a-empty v-if="!groupedDocs.size" description="暂无文书" />

    <a-collapse v-else ghost :bordered="false">
      <a-collapse-panel v-for="([cat, items]) in groupedArray" :key="cat" :header="categoryLabel(cat)">
        <a-collapse ghost :bordered="false">
          <a-collapse-panel
            v-for="doc in items"
            :key="doc.id"
          >
            <template #header>
              <div class="doc-item-header">
                <div class="doc-main-info">
                  <span class="doc-title">{{ doc.title || getDocumentTypeLabel(doc.type) }}</span>
                  <span v-if="getDocumentTimestamp(doc)" class="doc-timestamp">
                    <a-icon type="clock-circle" class="mr-1" />
                    {{ formatTimestamp(getDocumentTimestamp(doc)) }}
                  </span>
                </div>
                <div class="doc-meta-info">
                  <a-tag :color="getDocumentTypeColor(doc.type)" class="doc-type-tag">
                    {{ getDocumentTypeLabel(doc.type) }}
                  </a-tag>
                  <span v-if="doc.confidence != null" class="doc-confidence">
                    置信度 {{ Math.round(doc.confidence) }}%
                  </span>
                </div>
                <div class="doc-summary">{{ doc.content }}</div>
              </div>
            </template>
            <div class="doc-full">
              <a-typography-text type="secondary" class="block mb-2">完整内容</a-typography-text>
              <pre class="whitespace-pre-wrap leading-6">{{ getFullContent(doc) }}</pre>
            </div>
          </a-collapse-panel>
        </a-collapse>
      </a-collapse-panel>
    </a-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed, defineProps } from 'vue'
import type { ExtractedDocument, DocumentType, DocumentCategory } from '@/services/llmService'
import {
  getDocumentTypeLabel,
  getDocumentTypeColor,
  DOCUMENT_TYPE_TO_CATEGORY,
  DOCUMENT_CATEGORY_LABELS
} from '@/utils/documentTypeUtils'

const props = defineProps<{
  documents: ExtractedDocument[]
  originalText: string
}>()

const groupedDocs = computed(() => {
  const map = new Map<DocumentCategory, ExtractedDocument[]>()
  if (!props.documents) return map
  for (const d of props.documents) {
    const cat = DOCUMENT_TYPE_TO_CATEGORY[d.type]
    if (!map.has(cat)) map.set(cat, [])
    map.get(cat)!.push(d)
  }
  // 按时间顺序排序（优先）或标题排序（兜底）
  for (const [k, arr] of map) {
    arr.sort((a, b: unknown) => {
      const timeA = getDocumentTimestamp(a)
      const timeB = getDocumentTimestamp(b)

      // 如果都有时间戳，按时间排序
      if (timeA && timeB) {
        return timeA.localeCompare(timeB)
      }

      // 有时间戳的排在前面
      if (timeA && !timeB) return -1
      if (!timeA && timeB) return 1

      // 都没有时间戳，按标题排序
      return (a.title || '').localeCompare(b.title || '', 'zh')
    })
    map.set(k, arr)
  }
  return map
})

const groupedArray = computed(() => Array.from(groupedDocs.value.entries()))

function categoryLabel(cat: DocumentCategory) {
  return DOCUMENT_CATEGORY_LABELS[cat] || String(cat)
}

// 获取文档时间戳
function getDocumentTimestamp(doc: ExtractedDocument): string | null {
  // 优先从标题中提取时间戳（格式：YYYY-MM-DD HH:MM）
  const titleMatch = doc.title?.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/)
  if (titleMatch) {
    return titleMatch[1]
  }

  // 其次使用extractedAt字段
  if (doc.extractedAt) {
    return doc.extractedAt instanceof Date
      ? doc.extractedAt.toISOString()
      : String(doc.extractedAt)
  }

  return null
}

// 格式化时间戳显示
function formatTimestamp(timestamp: string | null): string {
  if (!timestamp) return ''

  try {
    // 如果是YYYY-MM-DD HH:MM格式，直接返回
    if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$/.test(timestamp)) {
      return timestamp
    }

    // 否则解析为Date对象并格式化
    const date = new Date(timestamp)
    if (isNaN(date.getTime())) return timestamp

    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    }).replace(/\//g, '-')
  } catch {
    return timestamp
  }
}


function getFullContent(doc: ExtractedDocument): string {
  // 1) 优先：使用新的 fullContent 字段（来自确定性切片）
  if (doc.position?.fullContent && doc.position.fullContent.trim()) {
    return doc.position.fullContent
  }

  // 2) 次选：按精确的指针切片（startIndex/endIndex）
  const source = props.originalText || ''
  if (source) {
    const si = doc.position?.startIndex
    const ei = doc.position?.endIndex
    if (typeof si === 'number' && typeof ei === 'number' && ei > si && si >= 0 && ei <= source.length) {
      return source.slice(si, ei)
    }
  }

  // 3) 兜底：使用摘要内容
  return doc.content || '暂无内容'
}
</script>

<style scoped>
.glass-card {
  backdrop-filter: blur(8px);
  background: rgba(255,255,255,0.6);
  border: 1px solid rgba(255,255,255,0.3);
  border-radius: 12px;
  padding: 12px 16px;
}

.doc-item-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.doc-main-info {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.doc-title {
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
  flex-shrink: 0;
}

.doc-timestamp {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}

.doc-meta-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.doc-type-tag {
  font-size: 11px;
  margin: 0;
}

.doc-confidence {
  font-size: 11px;
  color: #3b82f6;
  background: #eff6ff;
  padding: 2px 6px;
  border-radius: 3px;
}

.doc-summary {
  font-size: 13px;
  color: #6b7280;
  line-height: 1.4;
  margin-top: 4px;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

pre {
  max-height: 420px;
  overflow: auto;
  font-size: 12px;
  line-height: 1.5;
}

/* 响应式调整 */
@media (max-width: 768px) {
  .doc-main-info {
    flex-direction: column;
    align-items: flex-start;
    gap: 6px;
  }

  .doc-meta-info {
    flex-wrap: wrap;
    gap: 6px;
  }
}
</style>

