<template>
  <div class="scoring-rules-page p-6 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800">
          评分标准配置
        </h1>
        <p class="text-gray-500 text-sm mt-1">
          管理质控扣分规则、最高扣分限制和一票否决项
        </p>
      </div>
      <div class="flex gap-3">
        <a-upload
          :show-upload-list="false"
          accept=".xlsx,.xls"
          :custom-request="handleImport"
        >
          <a-button :loading="importing">
            <UploadOutlined /> 导入 Excel
          </a-button>
        </a-upload>
        <a-button
          :loading="exporting"
          @click="handleExport"
        >
          <DownloadOutlined /> 导出 Excel
        </a-button>
        <a-button
          type="primary"
          @click="openDrawer()"
        >
          <PlusOutlined /> 新增规则
        </a-button>
      </div>
    </div>

    <!-- 分类统计 -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <div
        v-for="(cat, catName) in categoryStats"
        :key="catName"
        :class="[
          'bg-white rounded-xl p-4 border cursor-pointer transition-all',
          activeCategory === catName ? 'border-blue-500 shadow-md' : 'border-gray-100 hover:border-blue-200'
        ]"
        @click="activeCategory = activeCategory === catName ? '' : catName as string"
      >
        <div class="text-sm text-gray-500">
          {{ catName }}
        </div>
        <div class="flex items-end justify-between mt-2">
          <span class="text-2xl font-bold text-gray-800">{{ cat.total }}</span>
          <div class="text-xs">
            <span class="text-green-600">{{ cat.enabled }} 启用</span>
            <span
              v-if="cat.veto_count"
              class="text-red-500 ml-2"
            >{{ cat.veto_count }} 否决</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 规则表格 -->
    <div class="bg-white rounded-xl border border-gray-100 shadow-sm">
      <div class="p-4 border-b flex items-center justify-between">
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="搜索规则名称..."
          style="width: 280px"
          @search="fetchRules"
        />
        <span class="text-sm text-gray-400">共 {{ rules.length }} 条规则</span>
      </div>

      <a-table
        :data-source="filteredRules"
        :columns="columns"
        row-key="id"
        :pagination="{ pageSize: 20, showTotal: (t: number) => `共 ${t} 条` }"
        size="middle"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <div class="font-medium text-gray-800">
              {{ record.name }}
            </div>
            <div
              v-if="record.description"
              class="text-xs text-gray-400 mt-0.5"
            >
              {{ record.description }}
            </div>
          </template>

          <template v-if="column.key === 'category'">
            <a-tag
              :color="categoryColor(record.category)"
              size="small"
            >
              {{ record.category }}
            </a-tag>
          </template>

          <template v-if="column.key === 'deduction'">
            <span
              class="font-bold"
              :class="record.veto ? 'text-red-600' : 'text-orange-600'"
            >
              {{ record.veto ? '一票否决' : `-${record.deduction}分` }}
            </span>
            <div
              v-if="!record.veto && record.max_deduction !== record.deduction"
              class="text-xs text-gray-400"
            >
              最高 -{{ record.max_deduction }}分
            </div>
          </template>

          <template v-if="column.key === 'severity'">
            <a-tag
              :color="severityColor(record.severity)"
              size="small"
            >
              {{ severityLabel(record.severity) }}
            </a-tag>
          </template>

          <template v-if="column.key === 'enabled'">
            <a-switch
              :checked="record.enabled"
              size="small"
              :loading="togglingId === record.id"
              @change="handleToggle(record)"
            />
          </template>

          <template v-if="column.key === 'actions'">
            <a-space>
              <a-button
                type="link"
                size="small"
                @click="openDrawer(record)"
              >
                编辑
              </a-button>
              <a-popconfirm
                title="确定删除此规则？"
                @confirm="handleDelete(record.id)"
              >
                <a-button
                  type="link"
                  size="small"
                  danger
                >
                  删除
                </a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </div>

    <!-- 编辑 Drawer -->
    <a-drawer
      v-model:open="drawerVisible"
      :title="editingRule ? '编辑规则' : '新增规则'"
      :width="480"
      :body-style="{ padding: '24px' }"
      @close="closeDrawer"
    >
      <a-form
        :model="formData"
        layout="vertical"
      >
        <a-form-item
          label="规则名称"
          required
        >
          <a-input
            v-model:value="formData.name"
            placeholder="例如：入院记录24h内完成"
          />
        </a-form-item>

        <a-form-item label="类别">
          <a-select
            v-model:value="formData.category"
            :options="categoryOptions"
          />
        </a-form-item>

        <a-form-item label="说明">
          <a-textarea
            v-model:value="formData.description"
            :rows="2"
            placeholder="规则详细说明"
          />
        </a-form-item>

        <a-form-item label="是否一票否决">
          <a-switch v-model:checked="formData.veto" />
          <span class="ml-2 text-xs text-gray-400">开启后扣分值自动设为100分</span>
        </a-form-item>

        <template v-if="!formData.veto">
          <a-row :gutter="16">
            <a-col :span="12">
              <a-form-item label="单项扣分">
                <a-input-number
                  v-model:value="formData.deduction"
                  :min="0.5"
                  :max="50"
                  :step="0.5"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="最高扣分">
                <a-input-number
                  v-model:value="formData.max_deduction"
                  :min="0.5"
                  :max="100"
                  :step="0.5"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
          </a-row>
        </template>

        <a-form-item label="严重级别">
          <a-radio-group v-model:value="formData.severity">
            <a-radio-button value="info">
              提示
            </a-radio-button>
            <a-radio-button value="warning">
              警告
            </a-radio-button>
            <a-radio-button value="error">
              错误
            </a-radio-button>
            <a-radio-button value="critical">
              严重
            </a-radio-button>
          </a-radio-group>
        </a-form-item>
      </a-form>

      <template #footer>
        <div class="flex justify-end gap-3">
          <a-button @click="closeDrawer">
            取消
          </a-button>
          <a-button
            type="primary"
            :loading="saving"
            @click="handleSave"
          >
            {{ editingRule ? '保存' : '创建' }}
          </a-button>
        </div>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  UploadOutlined,
  DownloadOutlined,
} from '@ant-design/icons-vue'
import axios from 'axios'
import { getAccessToken } from '@/utils/auth-token'

// 从 localStorage 读取 token（与 apiService.ts 的 TokenManager 保持一致）
function getAuthHeader(): Record<string, string> {
  const token = getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ============= 状态 =============
const rules = ref<any[]>([])
const categoryStats = ref<Record<string, any>>({})
const searchKeyword = ref('')
const activeCategory = ref('')
const drawerVisible = ref(false)
const editingRule = ref<any>(null)
const saving = ref(false)
const importing = ref(false)
const exporting = ref(false)
const togglingId = ref<string | null>(null)

const formData = ref({
  name: '',
  category: '形式质控',
  description: '',
  deduction: 2,
  max_deduction: 2,
  veto: false,
  severity: 'warning' as string,
})

// ============= 表格列 =============
const columns = [
  { title: '规则名称', key: 'name', dataIndex: 'name', width: 260 },
  { title: '类别', key: 'category', dataIndex: 'category', width: 100 },
  { title: '扣分', key: 'deduction', dataIndex: 'deduction', width: 120 },
  { title: '级别', key: 'severity', dataIndex: 'severity', width: 80 },
  { title: '启用', key: 'enabled', dataIndex: 'enabled', width: 80 },
  { title: '操作', key: 'actions', width: 120 },
]

const categoryOptions = [
  { value: '形式质控', label: '形式质控' },
  { value: '内涵质控', label: '内涵质控' },
  { value: '编码质控', label: '编码质控' },
  { value: '一票否决', label: '一票否决' },
]

// ============= 计算属性 =============
const filteredRules = computed(() => {
  let result = rules.value
  if (activeCategory.value) {
    result = result.filter(r => r.category === activeCategory.value)
  }
  if (searchKeyword.value) {
    const kw = searchKeyword.value.toLowerCase()
    result = result.filter(r => r.name.toLowerCase().includes(kw))
  }
  return result
})

// ============= 方法 =============
const fetchRules = async () => {
  try {
    const res = await axios.get('/api/v1/scoring-rules', { headers: getAuthHeader() })
    const data = res.data?.data
    if (data) {
      rules.value = data.rules || []
      categoryStats.value = data.categories || {}
    }
  } catch (err) {
    console.error('获取规则失败:', err)
  }
}

const handleToggle = async (record: any) => {
  togglingId.value = record.id
  try {
    await axios.put(`/api/v1/scoring-rules/${record.id}/toggle`, {}, { headers: getAuthHeader() })
    record.enabled = !record.enabled
    message.success(record.enabled ? '已启用' : '已禁用')
  } catch (err) {
    message.error('操作失败')
  } finally {
    togglingId.value = null
  }
}

const handleDelete = async (id: string) => {
  try {
    await axios.delete(`/api/v1/scoring-rules/${id}`, { headers: getAuthHeader() })
    message.success('删除成功')
    await fetchRules()
  } catch (err) {
    message.error('删除失败')
  }
}

const openDrawer = (rule?: any) => {
  editingRule.value = rule || null
  if (rule) {
    formData.value = { ...rule }
  } else {
    formData.value = {
      name: '', category: '形式质控', description: '',
      deduction: 2, max_deduction: 2, veto: false, severity: 'warning',
    }
  }
  drawerVisible.value = true
}

const closeDrawer = () => {
  drawerVisible.value = false
  editingRule.value = null
}

const handleSave = async () => {
  if (!formData.value.name.trim()) {
    message.warning('请输入规则名称')
    return
  }
  saving.value = true
  try {
    const payload = { ...formData.value }
    if (payload.veto) {
      payload.deduction = 100
      payload.max_deduction = 100
      payload.severity = 'critical'
    }

    if (editingRule.value) {
      await axios.put(`/api/v1/scoring-rules/${editingRule.value.id}`, payload, { headers: getAuthHeader() })
      message.success('更新成功')
    } else {
      await axios.post('/api/v1/scoring-rules', payload, { headers: getAuthHeader() })
      message.success('创建成功')
    }
    closeDrawer()
    await fetchRules()
  } catch (err) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleExport = async () => {
  exporting.value = true
  try {
    const res = await axios.get('/api/v1/scoring-rules/export', {
      responseType: 'blob',
      headers: getAuthHeader(),
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `评分标准_${new Date().toISOString().slice(0, 10)}.xlsx`
    a.click()
    URL.revokeObjectURL(url)
    message.success('导出成功')
  } catch (err) {
    message.error('导出失败')
  } finally {
    exporting.value = false
  }
}

const handleImport = async (options: any) => {
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', options.file)
    const res = await axios.post('/api/v1/scoring-rules/import', fd, {
      headers: { 'Content-Type': 'multipart/form-data', ...getAuthHeader() },
    })
    const data = res.data?.data
    message.success(`导入成功: ${data?.imported || 0} 条规则`)
    await fetchRules()
  } catch (err) {
    message.error('导入失败')
  } finally {
    importing.value = false
  }
}

// ============= 辅助 =============
const categoryColor = (cat: string) => ({
  '形式质控': 'blue', '内涵质控': 'purple', '编码质控': 'cyan', '一票否决': 'red',
}[cat] || 'default')

const severityColor = (sev: string) => ({
  critical: 'red', error: 'orange', warning: 'gold', info: 'blue',
}[sev] || 'default')

const severityLabel = (sev: string) => ({
  critical: '严重', error: '错误', warning: '警告', info: '提示',
}[sev] || sev)

// ============= 初始化 =============
onMounted(fetchRules)
</script>
