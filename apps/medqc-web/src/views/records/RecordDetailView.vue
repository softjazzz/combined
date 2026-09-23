<template>
  <div class="record-detail-page p-6">
    <!-- 顶部导航 -->
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-4">
        <a-button
          :icon="h(ArrowLeftOutlined)"
          @click="goBack"
        >
          返回
        </a-button>
        <h1 class="text-2xl font-bold text-gray-900">
          病案详情
        </h1>
        <a-tag
          v-if="recordId"
          color="blue"
          class="text-xs"
        >
          {{ recordId }}
        </a-tag>
      </div>

      <div class="flex items-center gap-3">
        <a-button @click="() => showQCPanel = !showQCPanel">
          <ExclamationCircleOutlined />
          {{ showQCPanel ? '隐藏质控' : '查看质控' }}
        </a-button>
        <a-button
          type="primary"
          :icon="h(PlayCircleOutlined)"
        >
          开始质控
        </a-button>
      </div>
    </div>

    <!-- 主体内容：左侧 EMR + 右侧质控面板 -->
    <div class="flex gap-6">
      <!-- 左侧：EMR 文书渲染 -->
      <div
        :class="showQCPanel ? 'flex-1' : 'w-full'"
        class="transition-all"
      >
        <EMRViewer
          v-if="recordId"
          ref="emrViewerRef"
          :record-id="recordId"
          :max-height="700"
          @defect-click="handleDefectClick"
          @loaded="handleEMRLoaded"
        />
      </div>

      <!-- 右侧：质控结果面板 -->
      <div
        v-if="showQCPanel"
        class="w-80 flex-shrink-0 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden"
      >
        <div class="px-4 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
          <h3 class="text-sm font-bold text-gray-700">
            <ExclamationCircleOutlined class="mr-1 text-orange-500" />
            质控结果
          </h3>
          <a-tag
            :color="annotationsAvailable ? (qcIssues.length > 0 ? 'red' : 'green') : 'default'"
            size="small"
          >
            {{ annotationsAvailable ? `${qcIssues.length} 个问题` : '标注不可用' }}
          </a-tag>
        </div>

        <div
          v-if="!annotationsAvailable"
          class="p-8 text-center text-gray-500"
          role="status"
        >
          当前无法核对缺陷标注
        </div>
        <div
          v-else-if="qcIssues.length === 0"
          class="p-8 text-center text-gray-400"
        >
          <CheckCircleOutlined class="text-3xl text-green-400 mb-2" />
          <p class="text-sm">
            暂无质控问题
          </p>
        </div>

        <div
          v-else
          class="overflow-y-auto"
          style="max-height: 650px"
        >
          <div
            v-for="(issue, index) in qcIssues"
            :key="issue.defect_id"
            :class="[
              'px-4 py-3 border-b border-gray-100 cursor-pointer transition-colors',
              activeDefectId === issue.defect_id ? 'bg-blue-50 border-l-4 border-l-blue-500' : 'hover:bg-gray-50'
            ]"
            @click="scrollToDefect(issue.defect_id)"
          >
            <div class="flex items-center gap-2 mb-1">
              <span
                :class="[
                  'w-5 h-5 rounded-full text-white text-[10px] flex items-center justify-center font-bold',
                  issue.severity === 'critical' ? 'bg-red-500' :
                  issue.severity === 'error' ? 'bg-orange-500' :
                  issue.severity === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
                ]"
              >
                {{ index + 1 }}
              </span>
              <span class="text-sm font-medium text-gray-700 truncate flex-1">
                {{ issue.rule_name || issue.category }}
              </span>
              <a-tag
                :color="issue.severity === 'critical' ? 'red' : issue.severity === 'error' ? 'orange' : 'gold'"
                size="small"
              >
                {{ severityText(issue.severity) }}
              </a-tag>
            </div>
            <p class="text-xs text-gray-500 line-clamp-2 ml-7">
              {{ issue.description }}
            </p>
            <p
              v-if="issue.suggestion"
              class="text-xs text-blue-500 ml-7 mt-1 line-clamp-1"
            >
              💡 {{ issue.suggestion }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftOutlined,
  PlayCircleOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import EMRViewer from '@/components/qc/EMRViewer.vue'
import type { DefectAnnotation } from '@/composables/useDefectHighlight'

const route = useRoute()
const router = useRouter()

// 从路由获取 recordId
const recordId = route.params.id as string

// 状态
const showQCPanel = ref(true)
const qcIssues = ref<DefectAnnotation[]>([])
const annotationsAvailable = ref(false)
const activeDefectId = ref<string | null>(null)
const emrViewerRef = ref<InstanceType<typeof EMRViewer> | null>(null)

// 返回上一页
const goBack = () => {
  router.go(-1)
}

// 严重级别文本
const severityText = (severity: string) => {
  const map: Record<string, string> = {
    critical: '严重',
    error: '错误',
    warning: '警告',
    info: '提示',
  }
  return map[severity] || severity
}

// EMR 加载完成
const handleEMRLoaded = (data: any) => {
  annotationsAvailable.value = data?.annotations_status === 'available'
  qcIssues.value = annotationsAvailable.value && Array.isArray(data?.defect_annotations)
    ? data.defect_annotations
    : []
}

// 缺陷点击：从 EMRViewer 内部触发
const handleDefectClick = (defectId: string) => {
  activeDefectId.value = defectId
}

// 从右侧面板点击：滚动到文书中的缺陷位置
const scrollToDefect = (defectId: string) => {
  activeDefectId.value = defectId
  emrViewerRef.value?.scrollTo(defectId)
}
</script>

<style scoped>
.record-detail-page {
  min-height: 100vh;
  background: #f8fafc;
}
</style>
