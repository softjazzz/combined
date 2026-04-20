<template>
  <a-drawer
    :open="visible"
    title="病历联审详情"
    placement="right"
    :width="1100"
    class="qc-review-drawer"
    :destroy-on-close="true"
    @close="handleClose"
  >
    <!-- 顶部：病历基本信息 -->
    <div class="bg-slate-50 rounded-xl p-4 mb-4 border border-slate-100">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div
            class="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-sm"
          >
            {{ (record?.patient_name || '').charAt(0) }}
          </div>
          <div>
            <div class="text-base font-bold text-slate-800">
              {{ record?.patient_name || '-' }}
            </div>
            <div class="text-xs text-slate-400">
              病案号：{{ record?.record_id || '-' }}
            </div>
          </div>
        </div>
        <span
          class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border"
          :class="statusClass"
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :class="statusDotClass"
          />
          {{ statusText }}
        </span>
      </div>
      <div class="grid grid-cols-4 gap-4 text-sm">
        <div>
          <span class="text-slate-400">科室</span>
          <div class="font-medium text-slate-700 mt-0.5">
            {{ record?.department || '-' }}
          </div>
        </div>
        <div>
          <span class="text-slate-400">出院日期</span>
          <div class="font-medium text-slate-700 mt-0.5">
            {{ record?.discharge_date || '-' }}
          </div>
        </div>
        <div>
          <span class="text-slate-400">质控得分</span>
          <div
            class="font-medium font-mono mt-0.5"
            :style="{ color: getScoreColor(record?.score) }"
          >
            {{ record?.score ?? '-' }}
          </div>
        </div>
        <div>
          <span class="text-slate-400">缺陷数</span>
          <div class="font-medium text-slate-700 mt-0.5">
            {{ record?.defect_count || 0 }}
          </div>
        </div>
      </div>
    </div>

    <!-- 双栏布局：左侧文书 + 右侧缺陷 -->
    <div
      class="flex gap-4"
      style="height: calc(100vh - 300px)"
    >
      <!-- 左侧：病历文书内容 -->
      <div class="flex-1 bg-white rounded-xl border border-slate-100 overflow-hidden flex flex-col">
        <div class="flex items-center gap-2 px-4 py-3 border-b border-slate-100">
          <a-segmented
            v-model:value="activeDocTab"
            :options="docTabs"
            size="small"
          />
        </div>
        <div class="flex-1 overflow-y-auto p-5">
          <a-spin :spinning="docLoading">
            <div
              v-if="currentDocContent"
              class="doc-content text-sm leading-relaxed text-slate-700"
              v-html="sanitizeHtml(currentDocContent)"
            />
            <div
              v-else
              class="text-center py-12 text-slate-400"
            >
              <FileTextOutlined
                style="font-size: 36px"
                class="mb-3 block"
              />
              <p class="text-sm">
                {{ docLoading ? '加载中...' : '暂无文书内容' }}
              </p>
              <p class="text-xs mt-1 text-slate-300">
                文书数据需从后端病历库获取
              </p>
            </div>
          </a-spin>
        </div>
      </div>

      <!-- 右侧：缺陷列表 -->
      <div class="w-[400px] flex-shrink-0 flex flex-col">
        <div class="flex items-center justify-between mb-3">
          <h3 class="text-sm font-bold text-slate-800">
            质控问题
            <span class="text-xs text-slate-400 font-normal ml-2">共 {{ displayedIssueCount }} 项</span>
          </h3>
          <a-button
            size="small"
            type="text"
            class="text-slate-500"
            @click="loadDefects"
          >
            <ReloadOutlined :spin="defectLoading" />
          </a-button>
        </div>

        <a-spin
          :spinning="defectLoading"
          class="flex-1 overflow-hidden"
        >
          <div
            v-if="displayedIssueCount === 0"
            class="text-center py-8 text-slate-400 text-sm"
          >
            暂无质控问题
          </div>
          <div
            v-else-if="defectList.length > 0"
            class="space-y-3 overflow-y-auto pr-1"
            style="max-height: calc(100vh - 380px)"
          >
            <div
              v-for="defect in defectList"
              :key="defect.id"
              class="bg-white rounded-xl border border-slate-100 p-4 hover:shadow-md transition-all cursor-pointer group"
              :class="{ 'ring-2 ring-blue-200 border-blue-200': selectedDefectId === defect.id }"
              @click="selectedDefectId = defect.id"
            >
              <div class="flex items-start justify-between mb-2">
                <div class="flex items-center gap-2">
                  <span
                    class="w-2 h-2 rounded-full flex-shrink-0"
                    :class="{
                      'bg-rose-500': defect.severity === 'critical' || defect.severity === 'error',
                      'bg-amber-500': defect.severity === 'warning',
                      'bg-blue-500': defect.severity === 'info',
                    }"
                  />
                  <span class="text-sm font-medium text-slate-800">{{ defect.rule_name }}</span>
                </div>
                <span
                  class="text-xs px-2 py-0.5 rounded-md font-medium"
                  :class="{
                    'bg-amber-50 text-amber-600': defect.status === 'pending',
                    'bg-blue-50 text-blue-600': defect.status === 'urged',
                    'bg-emerald-50 text-emerald-600': defect.status === 'approved',
                    'bg-rose-50 text-rose-600': defect.status === 'rejected',
                    'bg-slate-100 text-slate-500': defect.status === 'remediated',
                  }"
                >
                  {{ getDefectStatusText(defect.status) }}
                </span>
              </div>
              <p class="text-xs text-slate-500 mb-2 line-clamp-2">
                {{ defect.description }}
              </p>
              <div class="flex items-center gap-4 text-xs text-slate-400">
                <span>分类：{{ defect.category }}</span>
                <span>位置：{{ defect.location }}</span>
              </div>

              <!-- 操作按钮（选中时显示） -->
              <QCReviewActionBar
                v-if="selectedDefectId === defect.id"
                :defect="defect"
                class="mt-3 pt-3 border-t border-slate-100"
                @action-done="handleActionDone"
              />
            </div>
          </div>
          <div
            v-else
            class="space-y-3 overflow-y-auto pr-1"
            style="max-height: calc(100vh - 380px)"
          >
            <div
              v-for="issue in reviewItemList"
              :key="issue.id"
              class="bg-white rounded-xl border border-slate-100 p-4"
            >
              <div class="flex items-start justify-between gap-3 mb-3">
                <div class="min-w-0">
                  <div class="text-sm font-semibold text-slate-800 break-words">
                    {{ issue.rule_code ? `${issue.rule_code} · ` : ''
                    }}{{ issue.rule_name || '质控规则' }}
                  </div>
                  <div class="flex flex-wrap items-center gap-2 mt-2 text-xs">
                    <span
                      class="px-2 py-0.5 rounded-full border"
                      :class="getReviewStatusClass(issue.status)"
                    >
                      {{ getReviewStatusText(issue.status) }}
                    </span>
                    <span
                      v-if="issue.document_type"
                      class="px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-200"
                    >
                      {{ issue.document_type }}
                    </span>
                    <span
                      v-if="issue.rule_family"
                      class="px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-200"
                    >
                      {{ issue.rule_family }}
                    </span>
                    <span
                      v-if="issue.defect_level"
                      class="px-2 py-0.5 rounded-full bg-slate-50 text-slate-500 border border-slate-200"
                    >
                      {{ issue.defect_level }}
                    </span>
                  </div>
                </div>
                <span
                  v-if="issue.confidence !== null && issue.confidence !== undefined"
                  class="text-xs text-slate-400 font-mono flex-shrink-0"
                >
                  {{ Number(issue.confidence).toFixed(2) }}
                </span>
              </div>

              <div
                v-if="issue.findings"
                class="text-xs text-slate-700 leading-6"
              >
                <span class="text-slate-400">结论：</span>{{ issue.findings }}
              </div>
              <div
                v-if="issue.evidence"
                class="text-xs text-slate-500 leading-6 mt-2"
              >
                <span class="text-slate-400">证据：</span>{{ issue.evidence }}
              </div>
              <div
                v-if="issue.suggestion"
                class="text-xs text-blue-600 leading-6 mt-2"
              >
                <span class="text-slate-400">建议：</span>{{ issue.suggestion }}
              </div>
            </div>
          </div>
        </a-spin>
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ReloadOutlined, FileTextOutlined } from '@ant-design/icons-vue'
import { getDefectList, getRecordDetail, type DefectItem } from '@/api/qcAdmin'
import QCReviewActionBar from './QCReviewActionBar.vue'

interface RecordData {
  id: string
  record_id: string
  patient_name?: string
  department?: string
  discharge_date?: string
  score?: number
  defect_count?: number
  status?: string
}

interface ReviewIssueItem {
  id: string
  source?: string
  job_id?: string
  record_id: string
  visit_id?: string
  patient_name?: string
  rule_code?: string
  rule_name: string
  status: 'non_compliant' | 'uncertain' | 'compliant' | 'not_applicable'
  document_type?: string
  rule_family?: string
  defect_level?: string
  findings?: string
  evidence?: string
  suggestion?: string
  confidence?: number | null
}

const props = defineProps<{
  visible: boolean
  record: RecordData | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'close'): void
  (e: 'refresh'): void
}>()

const defectLoading = ref(false)
const defectList = ref<DefectItem[]>([])
const reviewItemList = ref<ReviewIssueItem[]>([])
const selectedDefectId = ref<string | null>(null)
const docLoading = ref(false)
const recordDetail = ref<Record<string, unknown> | null>(null)
const activeDocTab = ref('admission')

const docTabs = [
  { label: '入院记录', value: 'admission' },
  { label: '出院记录', value: 'discharge' },
  { label: '病程记录', value: 'progress' },
  { label: '手术记录', value: 'surgery' },
]

// 当前文书内容（根据 Tab 切换，兼容多种后端字段名）
const currentDocContent = computed(() => {
  if (!recordDetail.value) return ''
  const d = recordDetail.value
  const docs =
    (d.documents as Record<string, unknown> | undefined) ||
    (d.document_bundle as Record<string, unknown> | undefined) ||
    {}
  const tabMap: Record<string, string> = {
    admission: String(
      d.admissionNote ||
        d.admission_note ||
        d.admission_record ||
        docs.admissionNote ||
        docs.admission_note ||
        '',
    ),
    discharge: String(
      d.dischargeNote ||
        d.discharge_note ||
        d.discharge_record ||
        d.discharge_summary ||
        docs.dischargeNote ||
        docs.discharge_note ||
        '',
    ),
    progress: String(
      d.progressNote ||
        d.progress_note ||
        d.progress_record ||
        d.course_record ||
        docs.progressNote ||
        docs.progress_note ||
        '',
    ),
    surgery: String(
      d.surgeryNote ||
        d.surgery_note ||
        d.surgery_record ||
        d.operation_record ||
        docs.surgeryNote ||
        docs.surgery_note ||
        '',
    ),
  }
  return tabMap[activeDocTab.value] || ''
})

const displayedIssueCount = computed(() =>
  defectList.value.length > 0 ? defectList.value.length : reviewItemList.value.length,
)

/**
 * HTML 净化：移除 script/iframe/事件属性，防止 XSS
 * 生产环境建议替换为 DOMPurify 等专业库
 */
const sanitizeHtml = (html: string): string => {
  if (!html) return ''
  return (
    html
      // 移除 script 标签及内容
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      // 移除 iframe
      .replace(/<iframe[\s\S]*?<\/iframe>/gi, '')
      .replace(/<iframe[^>]*\/>/gi, '')
      // 移除事件属性（on*="...")
      .replace(/\son\w+\s*=\s*["'][^"']*["']/gi, '')
      .replace(/\son\w+\s*=\s*[^\s>]*/gi, '')
      // 移除 javascript: 协议
      .replace(/href\s*=\s*["']javascript:[^"']*["']/gi, 'href="#"')
  )
}

// 状态样式计算
const statusClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved')
    return 'bg-emerald-50 text-emerald-600 border-emerald-100'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-50 text-rose-600 border-rose-100'
  return 'bg-amber-50 text-amber-600 border-amber-100'
})

const statusDotClass = computed(() => {
  const s = props.record?.status
  if (s === 'completed' || s === 'passed' || s === 'approved') return 'bg-emerald-500'
  if (s === 'failed' || s === 'rejected') return 'bg-rose-500'
  return 'bg-amber-500'
})

const statusText = computed(() => {
  const map: Record<string, string> = {
    pending: '待质控',
    urged: '已催办',
    remediated: '已整改',
    approved: '已通过',
    rejected: '已驳回',
    completed: '已通过',
    passed: '已通过',
    failed: '未通过',
  }
  return map[props.record?.status || ''] || props.record?.status || '-'
})

const getScoreColor = (score?: number) => {
  if (!score) return '#94a3b8'
  if (score >= 90) return '#10b981'
  if (score >= 80) return '#3b82f6'
  if (score >= 60) return '#f59e0b'
  return '#f43f5e'
}

const getDefectStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待处理',
    urged: '已催办',
    remediated: '已整改',
    approved: '已通过',
    rejected: '已驳回',
  }
  return map[status] || status
}

const getReviewStatusText = (status: ReviewIssueItem['status']) => {
  const map: Record<ReviewIssueItem['status'], string> = {
    non_compliant: '不合规',
    uncertain: '待复核',
    compliant: '合规',
    not_applicable: '不适用',
  }
  return map[status] || status
}

const getReviewStatusClass = (status: ReviewIssueItem['status']) => {
  const map: Record<ReviewIssueItem['status'], string> = {
    non_compliant: 'bg-rose-50 text-rose-600 border-rose-100',
    uncertain: 'bg-amber-50 text-amber-600 border-amber-100',
    compliant: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    not_applicable: 'bg-slate-100 text-slate-500 border-slate-200',
  }
  return map[status] || map.uncertain
}

// 加载缺陷列表
const loadDefects = async () => {
  if (!props.record?.record_id) return
  defectLoading.value = true
  try {
    const res = await getDefectList({ record_id: props.record.record_id })
    if (res.success && res.data) {
      defectList.value = (res.data as any).items || (res.data as any) || []
    }
  } catch {
    defectList.value = []
  } finally {
    defectLoading.value = false
  }
}

// 加载病历文书详情
const loadRecordDetail = async () => {
  if (!props.record?.record_id) return
  docLoading.value = true
  try {
    const res = await getRecordDetail(props.record.record_id)
    if (res.success && res.data) {
      const detail = res.data as Record<string, unknown>
      recordDetail.value = detail
      const inlineDefects = detail.defects
      if (Array.isArray(inlineDefects)) {
        defectList.value = inlineDefects as DefectItem[]
      }
      const reviewItems = detail.review_items
      if (Array.isArray(reviewItems)) {
        reviewItemList.value = reviewItems as ReviewIssueItem[]
      }
    }
  } catch {
    recordDetail.value = null
    reviewItemList.value = []
  } finally {
    docLoading.value = false
  }
}

// 操作完成后刷新
const handleActionDone = () => {
  loadDefects()
  emit('refresh')
}

const handleClose = () => {
  emit('update:visible', false)
  emit('close')
}

// 打开时自动加载
watch(
  () => props.visible,
  (val) => {
    if (val && props.record) {
      selectedDefectId.value = null
      activeDocTab.value = 'admission'
      recordDetail.value = null
      reviewItemList.value = []
      loadDefects()
      loadRecordDetail()
    }
  },
)
</script>

<style scoped>
.qc-review-drawer :deep(.ant-drawer-body) {
  padding: 20px;
  background: #fafbfc;
}

.doc-content {
  font-size: 14px;
  line-height: 1.9;
  color: #333;
}

.doc-content :deep(h4) {
  color: #1a1a1a;
  font-size: 16px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #3b82f6;
}

.doc-content :deep(b) {
  color: #1a1a1a;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
