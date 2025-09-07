---
title: "Vue 3 + TypeScript 最佳实践"
description: "Vue 3 Composition API和TypeScript的开发规范"
version: "2.0"
category: "frontend"
priority: "high"
type: "manual"
---
# Vue 3 + TypeScript 最佳实践

## 🎯 组件开发规范

### 1. 组件结构标准
```vue
<!-- ✅ 标准组件结构 -->
<template>
  <div class="medical-record-form">
    <!-- 模板内容 -->
  </div>
</template>

<script setup lang="ts">
// 导入依赖
import { ref, computed, onMounted } from 'vue'
import type { MedicalRecord } from '@/types/medical-record'

// 接口定义
interface Props {
  recordId?: string
  readonly?: boolean
}

// Props定义
const props = withDefaults(defineProps<Props>(), {
  readonly: false
})

// Emits定义
const emit = defineEmits<{
  save: [record: MedicalRecord]
  cancel: []
}>()

// 响应式数据
const loading = ref(false)
const formData = ref<Partial<MedicalRecord>>({})

// 计算属性
const isValid = computed(() => {
  return formData.value.patientName && formData.value.diagnosis
})

// 方法定义
const handleSave = async () => {
  // 实现逻辑
}

// 生命周期
onMounted(() => {
  // 初始化逻辑
})
</script>

<style scoped>
.medical-record-form {
  /* 样式定义 */
}
</style>
```

### 2. Composables使用规范
```typescript
// ✅ 正确的Composable定义
// composables/useMedicalRecord.ts
export function useMedicalRecord(recordId?: string) {
  const record = ref<MedicalRecord | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const fetchRecord = async (id: string) => {
    loading.value = true
    error.value = null
    try {
      record.value = await medicalRecordService.getById(id)
    } catch (err) {
      error.value = '获取病历失败'
      console.error(err)
    } finally {
      loading.value = false
    }
  }

  const updateRecord = async (data: Partial<MedicalRecord>) => {
    // 更新逻辑
  }

  // 自动获取数据
  if (recordId) {
    onMounted(() => fetchRecord(recordId))
  }

  return {
    record: readonly(record),
    loading: readonly(loading),
    error: readonly(error),
    fetchRecord,
    updateRecord
  }
}
```

### 3. 类型定义规范
```typescript
// types/medical-record.ts
export interface MedicalRecord {
  id: string
  patientName: string
  patientId: string
  department: Department
  admissionDate: Date
  dischargeDate?: Date
  diagnosis: Diagnosis[]
  status: RecordStatus
  createdAt: Date
  updatedAt: Date
}

export type RecordStatus = 'draft' | 'submitted' | 'reviewed' | 'approved'

export interface Diagnosis {
  code: string
  name: string
  type: 'primary' | 'secondary'
  icd10Code?: string
}
```

### 4. 状态管理规范
```typescript
// stores/medical-record.ts
export const useMedicalRecordStore = defineStore('medicalRecord', () => {
  // 状态
  const records = ref<MedicalRecord[]>([])
  const currentRecord = ref<MedicalRecord | null>(null)
  const loading = ref(false)

  // Getters
  const recordsByDepartment = computed(() => (departmentId: string) => {
    return records.value.filter(r => r.department.id === departmentId)
  })

  // Actions
  const fetchRecords = async (filters?: RecordFilters) => {
    loading.value = true
    try {
      records.value = await medicalRecordService.getList(filters)
    } finally {
      loading.value = false
    }
  }

  return {
    records: readonly(records),
    currentRecord: readonly(currentRecord),
    loading: readonly(loading),
    recordsByDepartment,
    fetchRecords
  }
})
```

## 🔧 开发工具配置

### 1. TypeScript配置
```json
// tsconfig.json关键配置
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noImplicitReturns": true
  }
}
```

### 2. ESLint规则
```json
// .eslintrc.js关键规则
{
  "rules": {
    "@typescript-eslint/no-explicit-any": "error",
    "@typescript-eslint/explicit-function-return-type": "warn",
    "vue/component-name-in-template-casing": ["error", "PascalCase"]
  }
}
```

## 🚨 常见错误避免
1. **避免使用any类型**
2. **避免在template中使用复杂逻辑**
3. **避免直接修改props**
4. **避免在computed中执行副作用**
5. **避免忘记清理副作用(定时器、事件监听器)**

## 📋 代码审查检查点
- [ ] 使用了Composition API
- [ ] 所有变量都有明确类型
- [ ] Props和Emits都有类型定义
- [ ] 使用了适当的响应式API
- [ ] 组件职责单一且清晰