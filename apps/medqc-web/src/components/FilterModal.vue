<template>
  <a-modal
    :visible="props.visible"
    title="筛选条件设置"
    width="800px"
    @ok="handleConfirm"
    @cancel="handleCancel"
  >
    <div class="filter-modal-content">
      <a-form
        :model="formData"
        :label-col="{ span: 6 }"
        :wrapper-col="{ span: 18 }"
      >
        <!-- 缺陷状态筛选 -->
        <a-form-item label="缺陷状态">
          <a-checkbox-group v-model:value="formData.defectStatus">
            <a-checkbox value="pending">待整改</a-checkbox>
            <a-checkbox value="urged">已催办</a-checkbox>
            <a-checkbox value="rectified">已整改</a-checkbox>
            <a-checkbox value="appealed">已申诉</a-checkbox>
          </a-checkbox-group>
        </a-form-item>

        <!-- 审核状态筛选 -->
        <a-form-item label="审核状态">
          <a-checkbox-group v-model:value="formData.auditStatus">
            <a-checkbox value="pending">待审核</a-checkbox>
            <a-checkbox value="reviewing">审核中</a-checkbox>
            <a-checkbox value="passed">已通过</a-checkbox>
            <a-checkbox value="questioned">存疑</a-checkbox>
          </a-checkbox-group>
        </a-form-item>

        <!-- 科室筛选 -->
        <a-form-item label="科室">
          <a-select
            v-model:value="formData.department"
            mode="multiple"
            placeholder="选择科室"
            :options="departmentOptions"
            style="width: 100%"
          />
        </a-form-item>

        <!-- 医生筛选 -->
        <a-form-item label="医生">
          <a-select
            v-model:value="formData.doctor"
            mode="multiple"
            placeholder="选择医生"
            :options="doctorOptions"
            style="width: 100%"
            show-search
            :filter-option="filterOption"
          />
        </a-form-item>

        <!-- 优先级筛选 -->
        <a-form-item label="优先级">
          <a-checkbox-group v-model:value="formData.priority">
            <a-checkbox value="high">高</a-checkbox>
            <a-checkbox value="medium">中</a-checkbox>
            <a-checkbox value="low">低</a-checkbox>
          </a-checkbox-group>
        </a-form-item>

        <!-- 评分范围 -->
        <a-form-item label="评分范围">
          <a-slider
            v-model:value="formData.scoreRange"
            range
            :min="0"
            :max="100"
            :marks="{ 0: '0', 60: '60', 80: '80', 100: '100' }"
          />
        </a-form-item>

        <!-- 缺陷数量范围 -->
        <a-form-item label="缺陷数量">
          <a-input-number
            v-model:value="formData.defectCountMin"
            placeholder="最小值"
            :min="0"
            style="width: 45%"
          />
          <span style="margin: 0 8px">-</span>
          <a-input-number
            v-model:value="formData.defectCountMax"
            placeholder="最大值"
            :min="0"
            style="width: 45%"
          />
        </a-form-item>

        <!-- 时间范围 -->
        <a-form-item label="时间范围">
          <a-range-picker
            v-model:value="formData.timeRange"
            style="width: 100%"
            :placeholder="['开始时间', '结束时间']"
          />
        </a-form-item>

        <!-- 是否催办 -->
        <a-form-item label="催办状态">
          <a-radio-group v-model:value="formData.isUrgent">
            <a-radio :value="undefined">全部</a-radio>
            <a-radio :value="true">已催办</a-radio>
            <a-radio :value="false">未催办</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>

      <!-- 保存为模板 -->
      <div class="template-section mt-4 pt-4 border-t border-gray-200">
        <a-checkbox v-model:checked="saveAsTemplate">
          保存为筛选模板
        </a-checkbox>
        <a-input
          v-if="saveAsTemplate"
          v-model:value="templateName"
          placeholder="输入模板名称"
          class="mt-2"
          style="width: 300px"
        />
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

interface Props {
  visible: boolean
  currentConditions?: Record<string, unknown>
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', conditions: unknown, templateName?: string): void
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  currentConditions: () => ({})
})

const emit = defineEmits<Emits>()

// 表单数据
const formData = reactive({ defectStatus: [],
  auditStatus: [],
  department: [],
  doctor: [],
  priority:  [],
  scoreRange: [0, 100],
  defectCountMin: undefined,
  defectCountMax: undefined,
  timeRange: undefined,
  isUrgent: undefined
})

// 模板相关
const saveAsTemplate = ref(false)
const templateName = ref('')

// 选项数据
const departmentOptions = [
  { label: '内科', value: 'internal' },
  { label: '外科', value: 'surgery' },
  { label: '儿科', value: 'pediatrics' },
  { label: '妇产科', value: 'obstetrics' },
  { label: '急诊科', value: 'emergency' },
  { label: '骨科', value: 'orthopedics' },
  { label: '神经科', value: 'neurology' },
  { label: '心内科', value: 'cardiology' }
]

const doctorOptions = [
  { label: '张医生', value: 'doctor1' },
  { label: '李医生', value: 'doctor2' },
  { label: '王医生', value: 'doctor3' },
  { label: '刘医生', value: 'doctor4' },
  { label: '陈医生', value: 'doctor5' },
  { label: '杨医生', value: 'doctor6' }
]

// 搜索过滤
const filterOption = (input: string, option: { label: string }) => {
  return option.label.toLowerCase().indexOf(input.toLowerCase()) >= 0
}

// 监听visible变化，初始化表单数据
watch(() => props.visible, (newVal: unknown) => {
  if (newVal) {
    // 初始化表单数据
    Object.assign(formData, props.currentConditions)
  }
})

// 确认
const handleConfirm = () => {
  // 验证模板名称
  if (saveAsTemplate.value && !templateName.value.trim()) {
    message.error('请输入模板名称')
    return
  }

  // 构建筛选条件
  const conditions = { ...formData }
  
  // 清理空值
  Object.keys(conditions).forEach(key => {
    const value = conditions[key as keyof typeof conditions]
    if (Array.isArray(value) && value.length === 0) {
      delete conditions[key as keyof typeof conditions]
    } else if (value === undefined || value === null || value === '') {
      delete conditions[key as keyof typeof conditions]
    }
  })

  emit('confirm', conditions, saveAsTemplate.value ? templateName.value : undefined)
  emit('update:visible', false)
  
  // 重置模板相关状态
  saveAsTemplate.value = false
  templateName.value = ''
}

// 取消
const handleCancel = () => {
  emit('update:visible', false)
  saveAsTemplate.value = false
  templateName.value = ''
}

// 重置
const handleReset = () => { Object.assign(formData, {
    defectStatus: [],
    auditStatus: [],
    department: [],
    doctor: [],
    priority:  [],
    scoreRange: [0, 100],
    defectCountMin: undefined,
    defectCountMax: undefined,
    timeRange: undefined,
    isUrgent: undefined
  })
}
</script>

<style scoped>
.filter-modal-content {
  max-height: 60vh;
  overflow-y: auto;
}

.template-section {
  background-color: #f8f9fa;
  padding: 16px;
  border-radius: 6px;
}

:deep(.ant-slider-mark-text) {
  font-size: 12px;
}

:deep(.ant-checkbox-group) {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

:deep(.ant-checkbox-wrapper) {
  margin-right: 0;
}
</style>
