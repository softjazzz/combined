<template>
  <a-modal
    :visible="props.visible"
    title="列设置"
    width="600px"
    @ok="handleConfirm"
    @cancel="handleCancel"
  >
    <div class="column-settings-content">
      <div class="mb-4">
        <a-alert
          message="拖拽调整列顺序，勾选控制列显示"
          type="info"
          show-icon
          class="mb-4"
        />
      </div>

      <div class="column-list">
        <div
          v-for="(column, index) in columnList"
          :key="column.key"
          class="column-item"
          :class="{ 'column-item-disabled': !column.visible }"
        >
          <div class="column-item-content">
            <!-- 拖拽手柄 -->
            <div class="drag-handle">
              <HolderOutlined />
            </div>

            <!-- 列显示控制 -->
            <a-checkbox
              v-model:checked="column.visible"
              :disabled="column.fixed"
            >
              {{ column.title }}
            </a-checkbox>

            <!-- 列宽设置 -->
            <div class="column-width-setting">
              <span class="width-label">宽度:</span>
              <a-input-number
                v-model:value="column.width"
                :min="80"
                :max="500"
                :step="10"
                size="small"
                style="width: 80px"
              />
              <span class="width-unit">px</span>
            </div>

            <!-- 固定列设置 -->
            <div class="column-fixed-setting">
              <a-select
                v-model:value="column.fixed"
                size="small"
                style="width: 80px"
                :disabled="column.key === 'action'"
              >
                <a-select-option :value="false">不固定</a-select-option>
                <a-select-option value="left">左固定</a-select-option>
                <a-select-option value="right">右固定</a-select-option>
              </a-select>
            </div>

            <!-- 排序设置 -->
            <div class="column-sort-setting" v-if="column.sortable !== false">
              <a-checkbox
                v-model:checked="column.sorter"
                size="small"
              >
                排序
              </a-checkbox>
            </div>
          </div>
        </div>
      </div>

      <!-- 预设方案 -->
      <div class="preset-schemes mt-6 pt-4 border-t border-gray-200">
        <h4 class="mb-3">预设方案</h4>
        <div class="scheme-buttons">
          <a-button size="small" @click="applyScheme('default')">
            默认方案
          </a-button>
          <a-button size="small" @click="applyScheme('compact')">
            紧凑方案
          </a-button>
          <a-button size="small" @click="applyScheme('detailed')">
            详细方案
          </a-button>
        </div>
      </div>

      <!-- 保存方案 -->
      <div class="save-scheme mt-4">
        <a-input
          v-model:value="schemeName"
          placeholder="输入方案名称"
          style="width: 200px"
        />
        <a-button
          type="primary"
          size="small"
          @click="saveScheme"
          :disabled="!schemeName.trim()"
          class="ml-2"
        >
          保存方案
        </a-button>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-between">
        <div>
          <a-button @click="handleReset">重置</a-button>
        </div>
        <div>
          <a-button @click="handleCancel">取消</a-button>
          <a-button type="primary" @click="handleConfirm">确定</a-button>
        </div>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed } from 'vue'
import { message } from 'ant-design-vue'
import { HolderOutlined } from '@ant-design/icons-vue'

interface ColumnConfig {
  key: string
  title: string
  width: number
  visible: boolean
  fixed: boolean | 'left' | 'right'
  sorter: boolean
  sortable?: boolean
}

interface Props {
  visible: boolean
  columns[]
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', columns: ColumnConfig[]): void
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  columns: () => []
})

const emit = defineEmits<Emits>()

// 列配置列表
const columnList = ref<ColumnConfig[]>([])
const schemeName = ref('')

// 监听visible变化，初始化列配置
watch(() => props.visible, (newVal) => {
  if (newVal) {
    initColumnList()
  }
})

// 初始化列配置
const initColumnList = () => {
  columnList.value = props.columns.map(col => ({
    key: col.key || col.dataIndex,
    title: col.title,
    width: col.width || 120,
    visible: true,
    fixed: col.fixed || false,
    sorter: !!col.sorter,
    sortable: col.sortable !== false
  }))
}

// 应用预设方案
const applyScheme = (scheme: string) => {
  switch (scheme) {
    case 'default':
      columnList.value.forEach(col => {
        col.visible = true
        col.width = getDefaultWidth(col.key)
        col.fixed = col.key === 'action' ? 'right' : false
      })
      break
    case 'compact':
      columnList.value.forEach(col => {
        col.visible = isCompactColumn(col.key)
        col.width = Math.max(80, (col.width || 120) * 0.8)
        col.fixed = col.key === 'action' ? 'right' : false
      })
      break
    case 'detailed':
      columnList.value.forEach(col => {
        col.visible = true
        col.width = Math.min(200, (col.width || 120) * 1.2)
        col.fixed = ['registrationNo', 'action'].includes(col.key) ? 
          (col.key === 'registrationNo' ? 'left' : 'right') : false
      })
      break
  }
  message.success(`已应用${scheme === 'default' ? '默认' : scheme === 'compact' ? '紧凑' : '详细'}方案`)
}

// 获取默认宽度
const getDefaultWidth = (key: string) => {
  const widthMap: Record<string, number> = {
    registrationNo: 120,
    serialNo: 120,
    caseNo: 120,
    patientName: 100,
    department: 100,
    doctor: 100,
    auditStatus: 100,
    score: 80,
    scoringStandard: 120,
    defectCount: 80,
    createTime: 150,
    action: 150
  }
  return widthMap[key] || 120
}

// 判断是否为紧凑模式显示的列
const isCompactColumn = (key: string) => {
  const compactColumns = [
    'registrationNo', 'patientName', 'department', 
    'auditStatus', 'score', 'defectCount', 'action'
  ]
  return compactColumns.includes(key)
}

// 保存方案
const saveScheme = () => {
  if (!schemeName.value.trim()) {
    message.error('请输入方案名称')
    return
  }
  
  // 这里可以保存到本地存储或发送到服务器
  const scheme = {
    name: schemeName.value,
    columns: [...columnList.value]
  }
  
  // 模拟保存
  localStorage.setItem(`column-scheme-${schemeName.value}`, JSON.stringify(scheme))
  message.success(`方案"${schemeName.value}"保存成功`)
  schemeName.value = ''
}

// 确认
const handleConfirm = () => {
  emit('confirm', [...columnList.value])
  emit('update:visible', false)
}

// 取消
const handleCancel = () => {
  emit('update:visible', false)
}

// 重置
const handleReset = () => {
  initColumnList()
  message.success('已重置为默认配置')
}
</script>

<style scoped>
.column-settings-content {
  max-height: 60vh;
  overflow-y: auto;
}

.column-list {
  border: 1px solid #d9d9d9;
  border-radius: 6px;
}

.column-item {
  border-bottom: 1px solid #f0f0f0;
  transition: all 0.3s;
}

.column-item:last-child {
  border-bottom: none;
}

.column-item:hover {
  background-color: #f5f5f5;
}

.column-item-disabled {
  opacity: 0.6;
  background-color: #fafafa;
}

.column-item-content {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  gap: 16px;
}

.drag-handle {
  cursor: move;
  color: #999;
  font-size: 14px;
}

.column-width-setting {
  display: flex;
  align-items: center;
  gap: 4px;
}

.width-label {
  font-size: 12px;
  color: #666;
}

.width-unit {
  font-size: 12px;
  color: #999;
}

.column-fixed-setting {
  display: flex;
  align-items: center;
}

.column-sort-setting {
  display: flex;
  align-items: center;
}

.preset-schemes {
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 6px;
}

.scheme-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.save-scheme {
  display: flex;
  align-items: center;
}

:deep(.ant-checkbox-wrapper) {
  flex: 1;
  min-width: 120px;
}
</style>
