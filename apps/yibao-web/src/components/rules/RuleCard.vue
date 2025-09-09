<template>
  <a-card
    class="border-0 shadow-md hover:shadow-lg transition-all duration-300 cursor-pointer group"
    :class="{
      'ring-2 ring-blue-500 ring-opacity-50': selected,
      'border-l-4 border-l-green-500 bg-gradient-to-r from-green-50 to-white': rule.enabled,
      'border-l-4 border-l-gray-400 bg-gradient-to-r from-gray-50 to-white opacity-75': !rule.enabled
    }"
    @click="$emit('click', rule)"
  >
    <template #title>
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <a-tag
            :color="getSeverityColor(rule.severity)"
            class="text-xs font-medium"
          >
            {{ getSeverityLabel(rule.severity) }}
          </a-tag>
          <span class="font-mono text-sm font-semibold text-blue-600">{{ rule.code }}</span>
        </div>
        <div class="flex items-center space-x-2">
          <a-switch
            :checked="rule.enabled"
            :loading="toggling"
            @change="handleToggle"
            size="small"
            @click.stop
          />
        </div>
      </div>
    </template>

    <template #extra>
      <a-dropdown @click.stop>
        <a-button
          type="text"
          size="small"
          class="opacity-0 group-hover:opacity-100 transition-opacity duration-200"
        >
          <template #icon><MoreOutlined /></template>
        </a-button>
        <template #overlay>
          <a-menu>
            <a-menu-item @click="$emit('edit', rule)">
              <EditOutlined />
              编辑
            </a-menu-item>
            <a-menu-item @click="$emit('view', rule)">
              <EyeOutlined />
              查看详情
            </a-menu-item>
            <a-menu-item @click="$emit('test', rule)">
              <PlayCircleOutlined />
              测试规则
            </a-menu-item>
            <a-menu-divider />
            <a-menu-item @click="$emit('duplicate', rule)">
              <CopyOutlined />
              复制规则
            </a-menu-item>
            <a-menu-item @click="$emit('export', rule)">
              <ExportOutlined />
              导出规则
            </a-menu-item>
            <a-menu-divider />
            <a-menu-item @click="$emit('delete', rule)" danger>
              <DeleteOutlined />
              删除规则
            </a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </template>

    <div class="space-y-4">
      <div>
        <h3 class="text-lg font-semibold text-gray-800 mb-2 line-clamp-2">{{ rule.name }}</h3>
        <p v-if="rule.description" class="text-sm text-gray-600 line-clamp-2 leading-relaxed">
          {{ rule.description }}
        </p>
      </div>

      <div class="flex flex-wrap gap-2 items-center">
        <a-tag :color="getTypeColor(rule.rule_type)" size="small" class="text-xs">
          {{ getTypeLabel(rule.rule_type) }}
        </a-tag>
        <a-tag :color="getCategoryColor(rule.category_id)" size="small" class="text-xs">
          {{ getCategoryLabel(rule.category_id) }}
        </a-tag>
        <span class="ml-auto text-xs font-medium text-purple-600 bg-purple-100 px-2 py-1 rounded-full">
          v{{ rule.version || 1 }}
        </span>
      </div>

      <div class="grid grid-cols-3 gap-4 py-3 border-t border-b border-gray-100">
        <div class="text-center">
          <div class="flex items-center justify-center space-x-1 text-gray-600">
            <ThunderboltOutlined class="text-xs" />
            <span class="text-xs font-medium">{{ rule.trigger_count || 0 }}</span>
          </div>
          <div class="text-xs text-gray-500 mt-1">触发</div>
        </div>
        <div class="text-center">
          <div class="flex items-center justify-center space-x-1 text-gray-600">
            <FilterOutlined class="text-xs" />
            <span class="text-xs font-medium">{{ rule.condition_count || 0 }}</span>
          </div>
          <div class="text-xs text-gray-500 mt-1">条件</div>
        </div>
        <div class="text-center">
          <div class="flex items-center justify-center space-x-1 text-gray-600">
            <PlayCircleOutlined class="text-xs" />
            <span class="text-xs font-medium">{{ rule.action_count || 0 }}</span>
          </div>
          <div class="text-xs text-gray-500 mt-1">动作</div>
        </div>
      </div>

      <div class="flex items-center justify-between text-xs text-gray-500">
        <div class="flex items-center space-x-1">
          <ClockCircleOutlined />
          <span>{{ formatTime(rule.updated_at) }}</span>
        </div>
        <div v-if="rule.hit_count" class="flex items-center space-x-1 text-orange-600">
          <AimOutlined />
          <span class="font-medium">命中 {{ rule.hit_count }} 次</span>
        </div>
      </div>
    </div>
  </a-card>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import {
  MoreOutlined, EditOutlined, EyeOutlined, PlayCircleOutlined,
  CopyOutlined, ExportOutlined, DeleteOutlined, ThunderboltOutlined,
  FilterOutlined, ClockCircleOutlined, AimOutlined
} from '@ant-design/icons-vue'

interface Rule {
  id: number
  code: string
  name: string
  description?: string
  rule_type: string
  category_id: string
  severity: string
  enabled: boolean
  version: number
  updated_at: string
  trigger_count?: number
  condition_count?: number
  action_count?: number
  hit_count?: number
}

interface Props {
  rule: Rule
  selected?: boolean
}

interface Emits {
  (e: 'click', rule: Rule): void
  (e: 'toggle', rule: Rule, enabled: boolean): void
  (e: 'edit', rule: Rule): void
  (e: 'view', rule: Rule): void
  (e: 'test', rule: Rule): void
  (e: 'duplicate', rule: Rule): void
  (e: 'export', rule: Rule): void
  (e: 'delete', rule: Rule): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const toggling = ref(false)

// 工具方法
const getSeverityColor = (severity: string) => {
  const colorMap: Record<string, string> = {
    'info': 'blue',
    'warn': 'orange',
    'block': 'red'
  }
  return colorMap[severity] || 'default'
}

const getSeverityLabel = (severity: string) => {
  const labelMap: Record<string, string> = {
    'info': '信息',
    'warn': '警告',
    'block': '阻断'
  }
  return labelMap[severity] || severity
}

const getTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    'drug_age': 'blue',
    'drug_gender': 'green',
    'visit_type': 'orange',
    'hospital_level': 'purple',
    'duration': 'cyan',
    'surgery_pricing': 'red'
  }
  return colorMap[type] || 'default'
}

const getTypeLabel = (type: string) => {
  const labelMap: Record<string, string> = {
    'drug_age': '年龄限制',
    'drug_gender': '性别限制',
    'visit_type': '就诊方式',
    'hospital_level': '机构级别',
    'duration': '疗程限制',
    'surgery_pricing': '手术折价'
  }
  return labelMap[type] || type || '未分类'
}

const getCategoryColor = (categoryId: string) => {
  const colorMap: Record<string, string> = {
    'batch_1': 'blue',
    'batch_2': 'green',
    'batch_3': 'orange',
    'batch_4': 'purple',
    'batch_5': 'cyan'
  }
  return colorMap[categoryId] || 'default'
}

const getCategoryLabel = (categoryId: string) => {
  const labelMap: Record<string, string> = {
    'batch_1': '第一批',
    'batch_2': '第二批',
    'batch_3': '第三批',
    'batch_4': '第四批',
    'batch_5': '第五批'
  }
  return labelMap[categoryId] || '未分类'
}

const formatTime = (timeStr: string) => {
  if (!timeStr) return '-'
  const now = new Date()
  const time = new Date(timeStr)
  const diff = now.getTime() - time.getTime()
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  if (days < 30) return `${Math.floor(days / 7)}周前`
  return `${Math.floor(days / 30)}个月前`
}

// 事件处理
const handleToggle = async (enabled: boolean) => {
  toggling.value = true
  try {
    emit('toggle', props.rule, enabled)
  } finally {
    toggling.value = false
  }
}
</script>


