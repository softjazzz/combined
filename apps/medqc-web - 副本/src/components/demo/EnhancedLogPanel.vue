<template>
  <div class="enhanced-log-panel">
    <!-- 日志面板头部 -->
    <div class="log-header">
      <div class="header-left">
        <FileTextOutlined class="header-icon" />
        <span class="header-title">演示日志</span>
        <a-badge
          :count="filteredLogs.length"
          :overflow-count="999"
        />
      </div>
      <div class="header-right">
        <a-space>
          <a-button
            size="small"
            :disabled="filteredLogs.length === 0"
            @click="handleCopyAll"
          >
            <CopyOutlined />
            复制全部
          </a-button>
          <a-button
            size="small"
            :disabled="filteredLogs.length === 0"
            @click="handleExport"
          >
            <DownloadOutlined />
            导出日志
          </a-button>
          <a-popconfirm
            title="确定要清空所有日志吗？"
            ok-text="确定"
            cancel-text="取消"
            @confirm="handleClear"
          >
            <a-button
              size="small"
              danger
              :disabled="logs.length === 0"
            >
              <DeleteOutlined />
              清空
            </a-button>
          </a-popconfirm>
        </a-space>
      </div>
    </div>

    <!-- 过滤器 -->
    <div class="log-filters">
      <a-input-search
        v-model:value="searchKeyword"
        placeholder="搜索日志内容..."
        allow-clear
        size="small"
        style="width: 300px"
      >
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input-search>

      <a-radio-group
        v-model:value="selectedLevel"
        button-style="solid"
        size="small"
      >
        <a-radio-button value="all">
          全部
        </a-radio-button>
        <a-radio-button value="info">
          信息
        </a-radio-button>
        <a-radio-button value="warning">
          警告
        </a-radio-button>
        <a-radio-button value="error">
          错误
        </a-radio-button>
      </a-radio-group>
    </div>

    <!-- 日志列表 -->
    <div
      ref="logListRef"
      class="log-list"
    >
      <div
        v-for="(log, index) in filteredLogs"
        :key="index"
        class="log-item"
        :class="`log-${log.level}`"
      >
        <div class="log-item-header">
          <div class="log-meta">
            <component
              :is="getLevelIcon(log.level)"
              :class="`level-icon level-${log.level}`"
            />
            <span class="log-timestamp">{{ log.timestamp }}</span>
            <a-tag
              :color="getLevelColor(log.level)"
              size="small"
            >
              {{ getLevelLabel(log.level) }}
            </a-tag>
          </div>
          <div class="log-actions">
            <a-tooltip title="复制此条日志">
              <a-button
                type="text"
                size="small"
                @click="handleCopyLog(log)"
              >
                <CopyOutlined />
              </a-button>
            </a-tooltip>
            <a-tooltip title="展开/折叠">
              <a-button
                v-if="log.message.length > 100"
                type="text"
                size="small"
                @click="toggleLogExpand(index)"
              >
                <DownOutlined v-if="!expandedLogs.has(index)" />
                <UpOutlined v-else />
              </a-button>
            </a-tooltip>
          </div>
        </div>
        <div
          class="log-message"
          :class="{ expanded: expandedLogs.has(index) }"
        >
          {{ log.message }}
        </div>
        <div
          v-if="log.details"
          class="log-details"
        >
          <pre>{{ JSON.stringify(log.details, null, 2) }}</pre>
        </div>
      </div>

      <!-- 空状态 -->
      <a-empty
        v-if="filteredLogs.length === 0"
        description="暂无日志"
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { message, Empty } from 'ant-design-vue'
import {
  FileTextOutlined,
  CopyOutlined,
  DownloadOutlined,
  DeleteOutlined,
  SearchOutlined,
  InfoCircleOutlined,
  WarningOutlined,
  CloseCircleOutlined,
  DownOutlined,
  UpOutlined
} from '@ant-design/icons-vue'

// 日志级别类型
type LogLevel = 'info' | 'warning' | 'error'

// 日志条目接口
export interface LogEntry {
  timestamp: string
  level: LogLevel
  message: string
  details?: any
}

// Props
interface Props {
  logs: LogEntry[]
}

const props = defineProps<Props>()

// Emits
const emit = defineEmits<{
  clear: []
}>()

// 搜索关键词
const searchKeyword = ref('')

// 选中的日志级别
const selectedLevel = ref<'all' | LogLevel>('all')

// 展开的日志索引集合
const expandedLogs = ref(new Set<number>())

// 日志列表引用
const logListRef = ref<HTMLElement>()

// 过滤后的日志
const filteredLogs = computed(() => {
  let result = props.logs

  // 按级别过滤
  if (selectedLevel.value !== 'all') {
    result = result.filter(log => log.level === selectedLevel.value)
  }

  // 按关键词过滤
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    result = result.filter(log =>
      log.message.toLowerCase().includes(keyword) ||
      (log.details && JSON.stringify(log.details).toLowerCase().includes(keyword))
    )
  }

  return result
})

// 获取级别图标
const getLevelIcon = (level: LogLevel) => {
  switch (level) {
    case 'info':
      return InfoCircleOutlined
    case 'warning':
      return WarningOutlined
    case 'error':
      return CloseCircleOutlined
    default:
      return InfoCircleOutlined
  }
}

// 获取级别颜色
const getLevelColor = (level: LogLevel) => {
  switch (level) {
    case 'info':
      return 'blue'
    case 'warning':
      return 'orange'
    case 'error':
      return 'red'
    default:
      return 'default'
  }
}

// 获取级别标签
const getLevelLabel = (level: LogLevel) => {
  switch (level) {
    case 'info':
      return '信息'
    case 'warning':
      return '警告'
    case 'error':
      return '错误'
    default:
      return '未知'
  }
}

// 切换日志展开状态
const toggleLogExpand = (index: number) => {
  if (expandedLogs.value.has(index)) {
    expandedLogs.value.delete(index)
  } else {
    expandedLogs.value.add(index)
  }
}

// 复制单条日志
const handleCopyLog = async (log: LogEntry) => {
  try {
    const text = formatLogEntry(log)
    await navigator.clipboard.writeText(text)
    message.success('日志已复制到剪贴板')
  } catch (error) {
    message.error('复制失败')
  }
}

// 复制全部日志
const handleCopyAll = async () => {
  try {
    const text = filteredLogs.value.map(formatLogEntry).join('\n\n')
    await navigator.clipboard.writeText(text)
    message.success(`已复制 ${filteredLogs.value.length} 条日志到剪贴板`)
  } catch (error) {
    message.error('复制失败')
  }
}

// 导出日志
const handleExport = () => {
  try {
    const exportData = {
      exportTime: new Date().toISOString(),
      totalLogs: filteredLogs.value.length,
      logs: filteredLogs.value
    }

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json'
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `demo-logs-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)

    message.success('日志已导出')
  } catch (error) {
    message.error('导出失败')
  }
}

// 清空日志
const handleClear = () => {
  emit('clear')
  expandedLogs.value.clear()
  message.success('日志已清空')
}

// 格式化日志条目
const formatLogEntry = (log: LogEntry): string => {
  let text = `[${log.timestamp}] [${getLevelLabel(log.level)}] ${log.message}`
  if (log.details) {
    text += `\n详细信息: ${JSON.stringify(log.details, null, 2)}`
  }
  return text
}

// 监听日志变化，自动滚动到底部
watch(() => props.logs.length, async () => {
  await nextTick()
  if (logListRef.value) {
    logListRef.value.scrollTop = logListRef.value.scrollHeight
  }
})
</script>

<style scoped lang="less">
.enhanced-log-panel {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid #f0f0f0;
  background: #fafafa;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  font-size: 18px;
  color: #1890ff;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #262626;
}

.log-filters {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  background: #fff;
}

.log-list {
  max-height: 400px;
  overflow-y: auto;
  padding: 12px;
}

.log-item {
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 6px;
  border-left: 3px solid;
  background: #fafafa;
  transition: all 0.2s;

  &:hover {
    background: #f5f5f5;
  }

  &.log-info {
    border-left-color: #1890ff;
  }

  &.log-warning {
    border-left-color: #faad14;
  }

  &.log-error {
    border-left-color: #f5222d;
  }
}

.log-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.log-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.level-icon {
  font-size: 16px;

  &.level-info {
    color: #1890ff;
  }

  &.level-warning {
    color: #faad14;
  }

  &.level-error {
    color: #f5222d;
  }
}

.log-timestamp {
  font-size: 12px;
  color: #8c8c8c;
  font-family: 'Courier New', monospace;
}

.log-actions {
  display: flex;
  gap: 4px;
}

.log-message {
  font-size: 14px;
  color: #262626;
  line-height: 1.6;
  word-break: break-word;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;

  &.expanded {
    max-height: none;
  }
}

.log-details {
  margin-top: 8px;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #d9d9d9;

  pre {
    margin: 0;
    font-size: 12px;
    color: #595959;
    font-family: 'Courier New', monospace;
    white-space: pre-wrap;
    word-break: break-word;
  }
}
</style>

