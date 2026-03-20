<template>
  <div class="record-detail">
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <!-- 左侧：基本信息和内容 -->
      <div class="xl:col-span-2 space-y-6">
        <!-- 患者基本信息卡片 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <UserOutlined class="text-cyan-400" />
              患者信息
            </h3>
            <a-tag :color="getRecordTypeColor(record.record_type)">
              {{ getRecordTypeLabel(record.record_type) }}
            </a-tag>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div class="space-y-3">
              <div class="flex items-center gap-3">
                <div class="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-bold text-lg">
                  {{ record.patient_name.charAt(0) }}
                </div>
                <div>
                  <div class="font-semibold text-slate-100 text-lg">{{ record.patient_name }}</div>
                  <div class="text-sm text-slate-400">患者姓名</div>
                </div>
              </div>

              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center">
                  <CalendarOutlined class="text-slate-400" />
                </div>
                <div>
                  <div class="font-medium text-slate-200">{{ record.patient_age }} 岁</div>
                  <div class="text-sm text-slate-400">年龄</div>
                </div>
              </div>

              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center">
                  <TeamOutlined class="text-slate-400" />
                </div>
                <div>
                  <div class="font-medium text-slate-200">{{ getGenderLabel(record.patient_gender) }}</div>
                  <div class="text-sm text-slate-400">性别</div>
                </div>
              </div>
            </div>

            <div class="space-y-3">
              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center">
                  <BankOutlined class="text-slate-400" />
                </div>
                <div>
                  <div class="font-medium text-slate-200">{{ record.department }}</div>
                  <div class="text-sm text-slate-400">科室</div>
                </div>
              </div>

              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center">
                  <ClockCircleOutlined class="text-slate-400" />
                </div>
                <div>
                  <div class="font-medium text-slate-200">
                    {{ formatDate(record.admission_date) }}
                  </div>
                  <div class="text-sm text-slate-400">入院时间</div>
                </div>
              </div>

              <div class="flex items-center gap-3">
                <div class="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center">
                  <div 
                    class="w-3 h-3 rounded-full"
                    :class="getStatusDotClass(record.status)"
                  ></div>
                </div>
                <div>
                  <div class="font-medium text-slate-200">{{ getStatusLabel(record.status) }}</div>
                  <div class="text-sm text-slate-400">记录状态</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 记录内容卡片 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <FileTextOutlined class="text-cyan-400" />
              病案内容
            </h3>
            <div class="flex items-center gap-2">
              <a-button 
                size="small"
                @click="copyContent"
                class="bg-slate-700/50 border-slate-600/50 text-slate-300"
              >
                <CopyOutlined />
                复制
              </a-button>
              <a-button 
                size="small"
                @click="toggleFullscreen"
                class="bg-slate-700/50 border-slate-600/50 text-slate-300"
              >
                <ExpandOutlined v-if="!isFullscreen" />
                <CompressOutlined v-else />
                {{ isFullscreen ? '退出' : '全屏' }}
              </a-button>
            </div>
          </div>

          <div 
            class="relative"
            :class="{ 'fixed inset-0 z-50 bg-slate-900 p-6': isFullscreen }"
          >
            <div 
              v-if="isFullscreen"
              class="absolute top-4 right-4 z-10"
            >
              <a-button 
                size="large"
                @click="toggleFullscreen"
                class="bg-slate-800/80 border-slate-600/50 text-slate-300"
              >
                <CompressOutlined />
                退出全屏
              </a-button>
            </div>

            <div 
              class="bg-slate-900/50 rounded-lg p-4 border border-slate-600/30 max-h-96 overflow-y-auto text-slate-200 leading-relaxed"
              :class="{ 'max-h-none h-full': isFullscreen }"
            >
              <pre class="whitespace-pre-wrap font-mono text-sm">{{ record.content }}</pre>
            </div>
          </div>
        </div>

        <!-- 附件信息 -->
        <div 
          v-if="record.file_url" 
          class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6"
        >
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <PaperClipOutlined class="text-cyan-400" />
            附件信息
          </h3>

          <div class="flex items-center justify-between p-4 rounded-lg bg-slate-700/30 border border-slate-600/30">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
                <FileOutlined class="text-blue-400" />
              </div>
              <div>
                <div class="font-medium text-slate-200">{{ record.file_name || '病案文件' }}</div>
                <div class="text-sm text-slate-400">
                  {{ formatFileSize(record.file_size) }} · 
                  {{ formatDate(record.created_at) }}
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2">
              <a-button 
                size="small"
                @click="previewFile"
                class="bg-blue-500/20 border-blue-400/30 text-blue-300"
              >
                <EyeOutlined />
                预览
              </a-button>
              <a-button 
                size="small"
                @click="downloadFile"
                class="bg-emerald-500/20 border-emerald-400/30 text-emerald-300"
              >
                <DownloadOutlined />
                下载
              </a-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：质控信息和操作 -->
      <div class="space-y-6">
        <!-- 质控评分卡片 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <TrophyOutlined class="text-cyan-400" />
            质控评分
          </h3>

          <div v-if="record.qc_score !== null" class="text-center">
            <!-- 评分圆环 -->
            <div class="relative inline-flex items-center justify-center w-24 h-24 mb-4">
              <svg class="w-24 h-24 transform -rotate-90" viewBox="0 0 100 100">
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  stroke="currentColor"
                  stroke-width="8"
                  fill="none"
                  class="text-slate-700"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="40"
                  stroke="currentColor"
                  stroke-width="8"
                  fill="none"
                  :stroke-dasharray="`${(record.qc_score / 100) * 251.2} 251.2`"
                  :class="getScoreCircleColor(record.qc_score)"
                  class="transition-all duration-1000 ease-out"
                />
              </svg>
              <div class="absolute inset-0 flex items-center justify-center">
                <div class="text-center">
                  <div 
                    class="text-2xl font-bold"
                    :class="getScoreColor(record.qc_score)"
                  >
                    {{ record.qc_score }}
                  </div>
                  <div class="text-xs text-slate-400">分</div>
                </div>
              </div>
            </div>

            <!-- 等级标签 -->
            <div class="mb-4">
              <a-tag 
                :color="getGradeColor(record.qc_grade)" 
                size="large"
                class="px-4 py-1 text-sm font-semibold"
              >
                {{ record.qc_grade }}级质控
              </a-tag>
            </div>

            <!-- 评分说明 -->
            <div class="text-sm text-slate-400 space-y-1">
              <div>{{ getScoreDescription(record.qc_score) }}</div>
              <div class="text-xs">
                评分时间：{{ formatDate(record.updated_at) }}
              </div>
            </div>
          </div>

          <div v-else class="text-center py-8">
            <div class="w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-3">
              <QuestionCircleOutlined class="text-slate-400 text-2xl" />
            </div>
            <div class="text-slate-400 mb-4">暂未进行质控评分</div>
            <a-button 
              type="primary"
              @click="$emit('analyze-record', record)"
              :loading="analyzing"
              class="bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 border-none"
            >
              <ThunderboltOutlined />
              开始分析
            </a-button>
          </div>
        </div>

        <!-- 操作按钮组 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <SettingOutlined class="text-cyan-400" />
            操作
          </h3>

          <div class="space-y-3">
            <a-button
              block
              size="large"
              @click="$emit('edit-record', record)"
              class="bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30"
            >
              <EditOutlined />
              查看详情
            </a-button>

            <a-button 
              block 
              size="large"
              @click="$emit('duplicate-record', record)"
              class="bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30"
            >
              <CopyOutlined />
              复制记录
            </a-button>

            <a-button 
              block 
              size="large"
              @click="exportRecord"
              class="bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30"
            >
              <ExportOutlined />
              导出记录
            </a-button>

            <a-divider class="border-slate-600/30" />

            <a-button 
              block 
              size="large"
              danger
              @click="$emit('delete-record', record)"
              class="bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30"
            >
              <DeleteOutlined />
              删除记录
            </a-button>
          </div>
        </div>

        <!-- 记录历史 -->
        <div class="rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6">
          <h3 class="text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4">
            <HistoryOutlined class="text-cyan-400" />
            操作历史
          </h3>

          <div class="space-y-3">
            <div class="flex items-center gap-3 p-3 rounded-lg bg-slate-700/30">
              <div class="w-2 h-2 rounded-full bg-emerald-400"></div>
              <div class="flex-1">
                <div class="text-sm text-slate-200">记录创建</div>
                <div class="text-xs text-slate-400">{{ formatDate(record.created_at) }}</div>
              </div>
            </div>

            <div v-if="record.updated_at !== record.created_at" class="flex items-center gap-3 p-3 rounded-lg bg-slate-700/30">
              <div class="w-2 h-2 rounded-full bg-blue-400"></div>
              <div class="flex-1">
                <div class="text-sm text-slate-200">记录更新</div>
                <div class="text-xs text-slate-400">{{ formatDate(record.updated_at) }}</div>
              </div>
            </div>

            <div v-if="record.qc_score" class="flex items-center gap-3 p-3 rounded-lg bg-slate-700/30">
              <div class="w-2 h-2 rounded-full bg-amber-400"></div>
              <div class="flex-1">
                <div class="text-sm text-slate-200">质控分析完成</div>
                <div class="text-xs text-slate-400">评分：{{ record.qc_score }}分</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  UserOutlined,
  CalendarOutlined,
  TeamOutlined,
  BankOutlined,
  ClockCircleOutlined,
  FileTextOutlined,
  CopyOutlined,
  ExpandOutlined,
  CompressOutlined,
  PaperClipOutlined,
  FileOutlined,
  EyeOutlined,
  DownloadOutlined,
  TrophyOutlined,
  QuestionCircleOutlined,
  ThunderboltOutlined,
  SettingOutlined,
  EditOutlined,
  ExportOutlined,
  DeleteOutlined,
  HistoryOutlined
} from '@ant-design/icons-vue'
import type { MedicalRecord } from '@/types'

type RecordDetailModel = MedicalRecord & {
  record_type?: string
  patient_gender?: string
  admission_date?: string
  file_url?: string
  file_name?: string
  qc_grade?: string
}

// Props
interface Props {
  record: RecordDetailModel
  analyzing?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  analyzing: false
})

// Emits
const emit = defineEmits<{
  'edit-record': [record: RecordDetailModel]
  'duplicate-record': [record: RecordDetailModel]
  'delete-record': [record: RecordDetailModel]
  'analyze-record': [record: RecordDetailModel]
}>()

// 状态
const isFullscreen = ref(false)

// 切换全屏
const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

// 复制内容
const copyContent = async () => {
  try {
    await navigator.clipboard.writeText(props.record.content)
    message.success('内容已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

// 预览文件
const previewFile = () => {
  if (props.record.file_url) {
    window.open(props.record.file_url, '_blank')
  }
}

// 下载文件
const downloadFile = () => {
  if (props.record.file_url) {
    const link = document.createElement('a')
    link.href = props.record.file_url
    link.download = props.record.file_name || '病案文件'
    link.click()
  }
}

// 导出记录
const exportRecord = () => {
  message.info('导出功能开发中...')
}

// 获取记录类型颜色
const getRecordTypeColor = (type?: string) => {
  const colors = {
    inpatient: 'blue',
    outpatient: 'green',
    emergency: 'red'
  }
  return colors[type as keyof typeof colors] || 'default'
}

// 获取记录类型标签
const getRecordTypeLabel = (type?: string) => {
  const labels = {
    inpatient: '住院记录',
    outpatient: '门诊记录',
    emergency: '急诊记录'
  }
  return labels[type as keyof typeof labels] || type
}

// 获取性别标签
const getGenderLabel = (gender?: string) => {
  const labels = {
    M: '男性',
    F: '女性',
    U: '未知'
  }
  return labels[gender as keyof typeof labels] || gender
}

// 获取状态标签
const getStatusLabel = (status?: string) => {
  const labels = {
    pending: '待处理',
    analyzing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[status as keyof typeof labels] || status
}

// 获取状态点样式
const getStatusDotClass = (status?: string) => {
  const classes = {
    pending: 'bg-amber-400',
    analyzing: 'bg-blue-400 animate-pulse',
    completed: 'bg-emerald-400',
    failed: 'bg-red-400'
  }
  return classes[status as keyof typeof classes] || 'bg-gray-400'
}

// 获取评分颜色
const getScoreColor = (score: number) => {
  if (score >= 90) return 'text-emerald-400'
  if (score >= 80) return 'text-blue-400'
  if (score >= 70) return 'text-amber-400'
  return 'text-red-400'
}

// 获取评分圆环颜色
const getScoreCircleColor = (score: number) => {
  if (score >= 90) return 'text-emerald-400'
  if (score >= 80) return 'text-blue-400'
  if (score >= 70) return 'text-amber-400'
  return 'text-red-400'
}

// 获取等级颜色
const getGradeColor = (grade: string) => {
  const colors = {
    A: 'green',
    B: 'blue',
    C: 'orange'
  }
  return colors[grade as keyof typeof colors] || 'default'
}

// 获取评分描述
const getScoreDescription = (score: number) => {
  if (score >= 90) return '优秀 - 病案质量很高，符合所有质控标准'
  if (score >= 80) return '良好 - 病案质量较好，存在少量问题'
  if (score >= 70) return '合格 - 病案质量一般，需要改进'
  return '不合格 - 病案质量较差，存在严重问题'
}

// 格式化日期
const formatDate = (dateString: string) => {
  try {
    return new Date(dateString).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return dateString
  }
}

// 格式化文件大小
const formatFileSize = (bytes?: number) => {
  if (!bytes) return '未知大小'
  
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`
}
</script>

<style scoped>
/* 全屏样式 */
.fixed.inset-0 {
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(8px);
}

/* 滚动条样式 */
.overflow-y-auto::-webkit-scrollbar {
  width: 6px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: rgba(71, 85, 105, 0.2);
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.4);
  border-radius: 3px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.6);
}

/* 评分圆环动画 */
circle {
  transition: stroke-dasharray 1s ease-out;
}

/* 卡片悬浮效果 */
.rounded-xl {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.rounded-xl:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
}

/* 按钮动画 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 响应式设计 */
@media (max-width: 1280px) {
  .xl\\:col-span-2 {
    grid-column: span 1;
  }
}

@media (max-width: 768px) {
  .grid-cols-1.md\\:grid-cols-2 {
    grid-template-columns: 1fr;
  }
  
  .p-6 {
    padding: 1rem;
  }
}
</style>
