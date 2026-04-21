<template>
  <a-modal
    :open="open"
    title="导入质控规则"
    width="720px"
    :footer="null"
    destroy-on-close
    @cancel="emit('update:open', false)"
  >
    <!-- Step 1: 文件上传 -->
    <div
      v-if="step === 'upload'"
      class="py-4"
    >
      <a-upload-dragger
        :before-upload="handleFile"
        :show-upload-list="false"
        accept=".json"
      >
        <p class="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p class="ant-upload-text">
          点击或拖拽 JSON 文件到此处
        </p>
        <p class="ant-upload-hint">
          支持导出的规则 JSON 文件，系统将自动识别字段映射
        </p>
      </a-upload-dragger>
      <a-alert
        class="mt-4"
        type="info"
        show-icon
        message="支持的 JSON 格式"
        description="数组格式 [...] 或包含 rules 字段的对象 { rules: [...] }。每条规则至少需要 rule_code 和 name 字段。"
      />
    </div>

    <!-- Step 2: 预览 & 确认 -->
    <div
      v-else-if="step === 'preview'"
      class="py-2"
    >
      <div class="flex items-center justify-between mb-4">
        <div>
          <h4 class="text-sm font-semibold text-slate-700 m-0">
            检测到 {{ parsedRules.length }} 条规则
          </h4>
          <p class="text-xs text-slate-400 mt-1 m-0">
            {{ fileName }}
          </p>
        </div>
        <a-button
          size="small"
          @click="step = 'upload'"
        >
          重新选择
        </a-button>
      </div>

      <a-table
        :data-source="previewData"
        :columns="previewColumns"
        size="small"
        :pagination="{ pageSize: 5, size: 'small' }"
        :scroll="{ x: 600 }"
        row-key="rule_code"
      />

      <div class="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-100">
        <a-button @click="emit('update:open', false)">
          取消
        </a-button>
        <a-button
          type="primary"
          :loading="importing"
          @click="doImport"
        >
          <template #icon>
            <ImportOutlined />
          </template>
          确认导入 {{ parsedRules.length }} 条规则
        </a-button>
      </div>
    </div>

    <!-- Step 3: 结果 -->
    <div
      v-else-if="step === 'result'"
      class="py-4"
    >
      <a-result
        :status="resultStatus"
        :title="resultTitle"
        :sub-title="resultSubTitle"
      >
        <template #extra>
          <div class="space-y-3">
            <div class="flex items-center justify-center gap-6 text-sm">
              <span class="text-green-600">
                <CheckCircleOutlined class="mr-1" />
                插入 {{ importResult.inserted }} 条
              </span>
              <span class="text-blue-600">
                <SyncOutlined class="mr-1" />
                更新 {{ importResult.updated }} 条
              </span>
              <span
                v-if="importResult.errors > 0"
                class="text-red-500"
              >
                <CloseCircleOutlined class="mr-1" />
                失败 {{ importResult.errors }} 条
              </span>
            </div>
            <a-alert
              v-if="importResult.sample_error"
              type="warning"
              :message="'示例错误: ' + importResult.sample_error"
              class="text-left text-xs"
              show-icon
            />
            <div class="flex gap-3 justify-center mt-4">
              <a-button @click="reset">
                继续导入
              </a-button>
              <a-button
                type="primary"
                @click="handleDone"
              >
                完成
              </a-button>
            </div>
          </div>
        </template>
      </a-result>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  InboxOutlined,
  ImportOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons-vue'
import { resolveApiBaseUrl } from '@/utils/api-helpers'

const API_BASE = resolveApiBaseUrl()

interface Props {
  open: boolean
}

defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  imported: []
}>()

type Step = 'upload' | 'preview' | 'result'

const step = ref<Step>('upload')
const fileName = ref('')
const parsedRules = ref<Record<string, any>[]>([])
const importing = ref(false)
const importResult = ref({
  inserted: 0,
  updated: 0,
  errors: 0,
  sample_error: null as string | null,
})

const previewColumns = [
  { title: '编码', dataIndex: 'rule_code', key: 'rule_code', width: 100, ellipsis: true },
  { title: '名称', dataIndex: 'name', key: 'name', width: 200, ellipsis: true },
  { title: '分类', dataIndex: 'category', key: 'category', width: 80 },
  { title: '严重性', dataIndex: 'severity', key: 'severity', width: 80 },
  { title: '类型', dataIndex: 'rule_type', key: 'rule_type', width: 80 },
]

const previewData = computed(() => {
  return parsedRules.value.map((r) => ({
    rule_code: r.rule_code || r.rule_id || '-',
    name: r.name || r.rule_name || '未命名',
    category: r.category || r.rule_category || '-',
    severity: r.defect_level || r.severity || '-',
    rule_type: r.rule_type || '-',
  }))
})

const resultStatus = computed(() => {
  if (
    importResult.value.errors > 0 &&
    importResult.value.inserted === 0 &&
    importResult.value.updated === 0
  ) {
    return 'error'
  }
  if (importResult.value.errors > 0) return 'warning'
  return 'success'
})

const resultTitle = computed(() => {
  const total = importResult.value.inserted + importResult.value.updated
  if (resultStatus.value === 'error') return '导入失败'
  return `成功导入 ${total} 条规则`
})

const resultSubTitle = computed(() => {
  if (importResult.value.errors > 0) {
    return `${importResult.value.errors} 条规则导入失败，请检查数据格式`
  }
  return '所有规则已成功导入数据库'
})

const handleFile = (file: File) => {
  fileName.value = file.name
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const content = e.target?.result as string
      const parsed = JSON.parse(content)

      // 支持多种格式：数组、{ rules: [...] }、{ data: [...] }
      let rules: any[]
      if (Array.isArray(parsed)) {
        rules = parsed
      } else if (Array.isArray(parsed.rules)) {
        rules = parsed.rules
      } else if (Array.isArray(parsed.data)) {
        rules = parsed.data
      } else {
        message.error('JSON 格式不正确：需要数组或包含 rules/data 字段的对象')
        return
      }

      if (rules.length === 0) {
        message.warning('文件中没有找到规则数据')
        return
      }

      parsedRules.value = rules
      step.value = 'preview'
    } catch {
      message.error('JSON 解析失败，请检查文件格式')
    }
  }
  reader.readAsText(file, 'utf-8')
  return false // 阻止自动上传
}

const doImport = async () => {
  importing.value = true
  try {
    const resp = await fetch(`${API_BASE}/api/v1/semantic-rules/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rules: parsedRules.value }),
    })

    if (!resp.ok) {
      const errText = await resp.text()
      throw new Error(`HTTP ${resp.status}: ${errText}`)
    }

    const result = await resp.json()
    const data = result.data || result

    importResult.value = {
      inserted: data.inserted || 0,
      updated: data.updated || 0,
      errors: data.errors || 0,
      sample_error: data.sample_error || null,
    }

    step.value = 'result'
  } catch (err) {
    message.error(`导入请求失败: ${err instanceof Error ? err.message : '未知错误'}`)
  } finally {
    importing.value = false
  }
}

const reset = () => {
  step.value = 'upload'
  parsedRules.value = []
  fileName.value = ''
}

const handleDone = () => {
  emit('update:open', false)
  emit('imported')
  reset()
}
</script>
