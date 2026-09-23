<template>
  <a-drawer
    :open="visible"
    width="980"
    placement="right"
    :destroy-on-close="true"
    :body-style="{ padding: '16px 20px' }"
    class="outpatient-detail-drawer"
    @close="$emit('close')"
  >
    <template #title>
      <div class="flex items-center justify-between gap-3 pr-4">
        <div class="flex items-center gap-3">
          <span class="text-slate-900 font-semibold">门急诊病历质控详情</span>
          <a-tag
            color="blue"
            class="apple-status-tag"
          >
            {{ record?.visit_type || 'outpatient' }}
          </a-tag>
          <span class="text-xs text-slate-500">
            {{ currentIndexDisplay }}
          </span>
        </div>
        <div class="flex items-center gap-2">
          <a-button
            size="small"
            :disabled="!hasPrev"
            @click="emit('navigate-prev')"
          >
            上一条
          </a-button>
          <a-button
            size="small"
            :disabled="!hasNext"
            @click="emit('navigate-next')"
          >
            下一条
          </a-button>
        </div>
      </div>
    </template>

    <div
      class="grid grid-cols-1 gap-4"
      :class="detailData && !loading && !error ? 'lg:grid-cols-[1fr_320px]' : ''"
    >
      <section class="space-y-4">
        <div class="apple-drawer-panel px-4 py-3">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div>
              <p class="text-slate-400">
                病历号
              </p>
              <p class="font-mono text-slate-800">
                {{ displayRecordId }}
              </p>
            </div>
            <div>
              <p class="text-slate-400">
                患者
              </p>
              <p class="text-slate-800">
                {{ record?.patient_name || '-' }}
              </p>
            </div>
            <div>
              <p class="text-slate-400">
                科室
              </p>
              <p class="text-slate-800">
                {{ record?.department || '-' }}
              </p>
            </div>
            <div>
              <p class="text-slate-400">
                状态
              </p>
              <a-tag
                :color="statusColor"
                class="apple-status-tag"
              >
                {{ statusText }}
              </a-tag>
            </div>
          </div>
        </div>

        <a-skeleton
          v-if="loading"
          active
          :paragraph="{ rows: 6 }"
        />
        <div
          v-else-if="error"
          class="apple-drawer-panel p-4"
          role="alert"
          data-testid="outpatient-detail-error"
        >
          <p class="text-slate-800 font-medium">
            {{ error }}
          </p>
          <a-button
            type="primary"
            class="mt-3"
            data-testid="retry-outpatient-detail"
            @click="emit('retry')"
          >
            重试
          </a-button>
        </div>
        <div
          v-else-if="qcLinkUnavailable"
          class="apple-drawer-panel p-4"
          role="status"
          data-testid="outpatient-qc-link-unavailable"
        >
          <p class="text-slate-800 font-medium">
            质控关联待核实
          </p>
          <p class="text-slate-500 text-sm mt-1">
            当前病历文书可查看，缺陷与整改等质控记录暂不可确认。
          </p>
        </div>
        <a-skeleton
          v-else
          :loading="false"
        >
          <a-tabs
            v-if="detailData"
            v-model:active-key="activeTab"
            class="detail-tabs"
          >
            <a-tab-pane
              key="defects"
              :tab="`缺陷(${defects.length})`"
            >
              <div
                v-if="defects.length"
                class="space-y-3"
              >
                <article
                  v-for="(defect, index) in defects"
                  :key="defect.id || `${index}`"
                  class="apple-defect-card p-3"
                >
                  <div class="flex items-center justify-between gap-3">
                    <p class="font-semibold text-slate-800">
                      {{ defect.title || defect.defect_type || '缺陷项' }}
                    </p>
                    <div class="flex items-center gap-2">
                      <a-tag
                        :color="severityColor(defect.severity)"
                        class="apple-status-tag"
                      >
                        {{ defect.severity || 'warning' }}
                      </a-tag>
                      <a-button
                        v-if="defect.id"
                        size="small"
                        type="link"
                        class="!px-1"
                        @click="emit('urge-defect', String(defect.id))"
                      >
                        催办
                      </a-button>
                      <a-button
                        v-if="defect.id"
                        size="small"
                        type="link"
                        class="!px-1"
                        @click="emit('approve-defect', String(defect.id))"
                      >
                        通过
                      </a-button>
                      <a-button
                        v-if="defect.id"
                        size="small"
                        type="link"
                        danger
                        class="!px-1"
                        @click="emit('reject-defect', String(defect.id))"
                      >
                        存疑
                      </a-button>
                      <a-button
                        v-if="defect.id"
                        size="small"
                        type="link"
                        class="!px-1"
                        :disabled="!props.remediationEnabled"
                        @click="emit('assign-remediation', String(defect.id))"
                      >
                        派发整改
                      </a-button>
                    </div>
                  </div>
                  <p class="mt-1 text-sm text-slate-600">
                    {{
                      defect.description ||
                        defect.defect_description ||
                        defect.comment ||
                        '暂无描述'
                    }}
                  </p>
                </article>
              </div>
              <a-empty
                v-else
                description="暂无缺陷记录"
              />
            </a-tab-pane>

            <a-tab-pane
              key="remediation"
              :tab="`整改(${remediation.length})`"
            >
              <a-timeline
                v-if="remediation.length"
                class="px-2"
              >
                <a-timeline-item
                  v-for="(item, index) in remediation"
                  :key="item.id || `${index}`"
                  :color="timelineColor(item.status)"
                >
                  <p class="font-medium text-slate-800">
                    {{ item.status || 'pending' }}
                  </p>
                  <p class="text-sm text-slate-500">
                    {{ item.remediation_requirement || item.comment || '暂无整改说明' }}
                  </p>
                </a-timeline-item>
              </a-timeline>
              <a-empty
                v-else
                description="暂无整改任务"
              />
            </a-tab-pane>

            <a-tab-pane
              key="appeals"
              :tab="`申诉(${appeals.length})`"
            >
              <a-list
                v-if="appeals.length"
                size="small"
                :data-source="appeals"
                :split="false"
                class="space-y-2"
              >
                <template #renderItem="{ item }">
                  <a-list-item class="!px-0">
                    <div
                      class="w-full rounded-xl border border-[rgba(0,0,0,0.08)] bg-[rgba(245,245,247,0.74)] p-3"
                    >
                      <div class="flex items-center justify-between">
                        <span class="font-medium text-slate-800">{{
                          item.status || 'pending'
                        }}</span>
                        <span class="text-xs text-slate-400">{{ item.created_at || '-' }}</span>
                      </div>
                      <p class="text-sm text-slate-600 mt-1">
                        {{ item.reason || item.comment || '暂无申诉说明' }}
                      </p>
                    </div>
                  </a-list-item>
                </template>
              </a-list>
              <a-empty
                v-else
                description="暂无申诉记录"
              />
            </a-tab-pane>

            <a-tab-pane
              key="history"
              :tab="`操作记录(${operationHistory.length})`"
            >
              <a-timeline
                v-if="operationHistory.length"
                class="px-2"
              >
                <a-timeline-item
                  v-for="(item, index) in operationHistory"
                  :key="item.id || `${index}`"
                >
                  <p class="font-medium text-slate-800">
                    {{ item.action || item.operation || '状态更新' }}
                  </p>
                  <p class="text-xs text-slate-500">
                    {{ item.operator_name || item.operator_id || '系统' }} ·
                    {{ item.created_at || '-' }}
                  </p>
                </a-timeline-item>
              </a-timeline>
              <a-empty
                v-else
                description="暂无操作历史"
              />
            </a-tab-pane>
          </a-tabs>
        </a-skeleton>
      </section>

      <aside
        v-if="detailData && !loading && !error"
        class="space-y-3"
      >
        <div class="apple-drawer-panel p-3">
          <h3 class="text-sm font-semibold text-slate-800 mb-2">
            病历文书
          </h3>
          <div
            v-if="rawDocumentPanels.length"
            class="space-y-2"
          >
            <details
              v-for="item in rawDocumentPanels"
              :key="item.key"
              class="rounded border border-[rgba(0,0,0,0.06)] bg-white p-2.5"
              data-testid="outpatient-raw-document"
            >
              <summary class="cursor-pointer text-sm text-slate-800">
                {{ item.title }}
              </summary>
              <pre class="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-slate-700">{{ item.content || '文书暂无正文' }}</pre>
            </details>
          </div>
          <a-empty
            v-else
            description="暂无病历文书"
          />
        </div>
      </aside>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { AdminRecordItem } from '@/api/qcAdmin'

interface DetailDrawerProps {
  visible: boolean
  loading?: boolean
  record: AdminRecordItem | null
  detailData: Record<string, unknown> | null
  error?: string
  remediationEnabled?: boolean
  hasPrev?: boolean
  hasNext?: boolean
  currentIndex?: number
  totalCount?: number
}

const props = withDefaults(defineProps<DetailDrawerProps>(), {
  loading: false,
  error: '',
  remediationEnabled: false,
  hasPrev: false,
  hasNext: false,
  currentIndex: 0,
  totalCount: 0,
})

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'retry'): void
  (event: 'urge-defect', defectId: string): void
  (event: 'approve-defect', defectId: string): void
  (event: 'reject-defect', defectId: string): void
  (event: 'assign-remediation', defectId: string): void
  (event: 'navigate-prev'): void
  (event: 'navigate-next'): void
}>()

const activeTab = ref('defects')

watch(
  () => props.visible,
  (open) => {
    if (open) {
      activeTab.value = 'defects'
    }
  },
)

const payload = computed<Record<string, any>>(() => {
  if (props.detailData && typeof props.detailData === 'object') {
    return props.detailData as Record<string, any>
  }
  return {}
})
const qcLinkUnavailable = computed(
  () => payload.value.qc_data_status === 'unavailable_identity_contract',
)

const defects = computed<any[]>(() => payload.value.defects || [])
const remediation = computed<any[]>(() => payload.value.remediation || [])
const appeals = computed<any[]>(() => payload.value.appeals || [])
const operationHistory = computed<any[]>(() => payload.value.operation_history || [])

const documents = computed<Record<string, any>>(() => {
  const docs = payload.value.documents
  if (docs && typeof docs === 'object') {
    return docs
  }
  return {}
})

const statusText = computed(() => {
  if (props.loading || props.error || !props.detailData) return '质控状态不可用'
  return qcLinkUnavailable.value ? '质控关联待核实' : String(props.record?.status || 'pending')
})
const displayRecordId = computed(() => String(props.record?.record_id || props.record?.id || '-'))
const currentIndexDisplay = computed(() => {
  if (!props.totalCount) {
    return '0/0'
  }
  return `${props.currentIndex || 0}/${props.totalCount}`
})

const statusColor = computed(() => {
  if (props.loading || props.error || !props.detailData || qcLinkUnavailable.value) return 'default'
  const map: Record<string, string> = {
    pending: 'orange',
    reviewing: 'blue',
    approved: 'green',
    rejected: 'red',
    remediated: 'cyan',
    urged: 'gold',
  }
  return map[String(props.record?.status || '')] || 'default'
})

const severityColor = (severity: string | undefined) => {
  const map: Record<string, string> = {
    high: 'red',
    major: 'red',
    medium: 'orange',
    warning: 'orange',
    low: 'blue',
    minor: 'blue',
  }
  return map[String(severity || '').toLowerCase()] || 'default'
}

const timelineColor = (status: string | undefined) => {
  const map: Record<string, string> = {
    pending: 'blue',
    in_progress: 'orange',
    submitted: 'cyan',
    approved: 'green',
    rejected: 'red',
    closed: 'gray',
  }
  return map[String(status || '').toLowerCase()] || 'blue'
}

const rawDocumentPanels = computed(() => {
  const rows = documents.value.raw_documents
  if (!Array.isArray(rows)) return []
  return rows.filter((row): row is Record<string, unknown> => Boolean(row && typeof row === 'object'))
    .map((row, index) => ({
      key: String(row.id || index),
      title: String(row.document_title || row.title || row.document_type || `文书 ${index + 1}`),
      content: String(row.content || ''),
    }))
})
</script>

<style scoped>
:deep(.outpatient-detail-drawer .ant-drawer-content) {
  background: #f5f5f7;
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

:deep(.outpatient-detail-drawer .ant-drawer-header) {
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(18px);
}

:deep(.outpatient-detail-drawer .ant-drawer-body) {
  background: #f5f5f7;
}

.apple-drawer-panel {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 22px rgba(0, 0, 0, 0.045);
  backdrop-filter: blur(18px);
}

.apple-defect-card {
  border: 1px solid rgba(217, 45, 32, 0.16);
  border-radius: 12px;
  background: rgba(255, 247, 246, 0.74);
}

.apple-status-tag {
  border-radius: 999px;
  font-weight: 500;
}

:deep(.detail-tabs .ant-tabs-nav) {
  margin-bottom: 12px;
}

:deep(.detail-tabs .ant-tabs-tab) {
  color: rgba(29, 29, 31, 0.6);
  font-weight: 500;
}

:deep(.detail-tabs .ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn),
:deep(.ant-btn-link) {
  color: #2b6cf6;
}

:deep(.detail-tabs .ant-tabs-ink-bar) {
  background: #2b6cf6;
}

:deep(.ant-btn-primary) {
  border-color: #2b6cf6 !important;
  background: #2b6cf6 !important;
}

:deep(.ant-tag-blue) {
  color: #2b6cf6;
  border-color: rgba(43, 108, 246, 0.16);
  background: rgba(43, 108, 246, 0.08);
}
</style>
