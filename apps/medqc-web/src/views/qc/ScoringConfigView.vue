<template>
  <div class="scoring-config-page p-6 max-w-4xl mx-auto">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-slate-800 dark:text-white flex items-center gap-3">
        <SettingOutlined class="text-blue-500" />
        评分阈值配置
      </h1>
      <p class="text-sm text-slate-500 mt-1">
        配置病历质控评分的甲乙丙等级分数线和扣分规则
      </p>
    </div>

    <a-alert
      v-if="isReadonly"
      type="info"
      show-icon
      message="当前为只读模式"
      description="当前账号仅可查看评分阈值配置，需全局系统管理员（admin / sync_admin / super_admin）角色方可修改。"
      class="mb-6"
    />

    <a-spin :spinning="loading">
      <!-- 等级阈值卡片 -->
      <div class="mb-6">
        <h2
          class="text-base font-semibold text-slate-700 dark:text-slate-200 mb-4 flex items-center gap-2"
        >
          <TrophyOutlined />
          等级分数线
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div
            v-for="(config, grade) in formData.grade_thresholds"
            :key="grade"
            class="relative bg-white dark:bg-slate-800 rounded-xl border-2 p-5 shadow-sm transition-all hover:shadow-md"
            :style="{ borderColor: config.color + '40' }"
          >
            <div class="flex items-center justify-between mb-4">
              <span
                class="text-2xl font-black"
                :style="{ color: config.color }"
              >{{
                config.label
              }}</span>
              <a-tag
                :color="config.color"
                class="!m-0"
              >
                {{ config.description }}
              </a-tag>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-sm text-slate-500 whitespace-nowrap">最低分数</span>
              <a-input-number
                v-model:value="config.min_score"
                :min="0"
                :max="100"
                class="flex-1"
                :disabled="isReadonly || grade === '丙'"
              />
            </div>
            <div
              v-if="grade === '丙'"
              class="mt-2 text-xs text-slate-400"
            >
              丙级为低于乙级分数线的所有分数（自动计算）
            </div>
          </div>
        </div>
      </div>

      <!-- 扣分规则 -->
      <div class="mb-6">
        <h2
          class="text-base font-semibold text-slate-700 dark:text-slate-200 mb-4 flex items-center gap-2"
        >
          <AlertOutlined />
          缺陷扣分上限
        </h2>
        <div
          class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden"
        >
          <a-table
            :data-source="deductionTableData"
            :columns="deductionColumns"
            :pagination="false"
            size="middle"
            row-key="key"
          >
            <template #bodyCell="{ column, record }">
              <template v-if="column.dataIndex === 'severity'">
                <a-tag :color="record.color">
                  {{ record.label }}
                </a-tag>
              </template>
              <template v-if="column.dataIndex === 'max_deduction'">
                <a-input-number
                  v-model:value="
                    formData.deduction_rules[record.key as 'critical' | 'major' | 'minor']
                      .max_deduction
                  "
                  :min="0"
                  :max="100"
                  :disabled="isReadonly"
                  size="small"
                  style="width: 100px"
                />
                <span class="ml-1 text-slate-400">分</span>
              </template>
            </template>
          </a-table>
        </div>
      </div>

      <!-- 基础设置 -->
      <div class="mb-6">
        <h2
          class="text-base font-semibold text-slate-700 dark:text-slate-200 mb-4 flex items-center gap-2"
        >
          <ControlOutlined />
          基础设置
        </h2>
        <div
          class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5"
        >
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label class="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-2">基础分值</label>
              <a-input-number
                v-model:value="formData.base_score"
                :min="0"
                :max="200"
                :disabled="isReadonly"
                class="w-full"
              />
              <p class="text-xs text-slate-400 mt-1">
                病历初始分数，缺陷会在此基础上扣分
              </p>
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-600 dark:text-slate-300 mb-2">及格线</label>
              <a-input-number
                v-model:value="formData.pass_score"
                :min="0"
                :max="100"
                :disabled="isReadonly"
                class="w-full"
              />
              <p class="text-xs text-slate-400 mt-1">
                低于此分数的病历将标记为不合格
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 预览区 -->
      <div class="mb-6">
        <h2
          class="text-base font-semibold text-slate-700 dark:text-slate-200 mb-4 flex items-center gap-2"
        >
          <EyeOutlined />
          分数预览
        </h2>
        <div
          class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5"
        >
          <div class="flex items-center gap-4">
            <a-input-number
              v-model:value="previewScore"
              :min="0"
              :max="100"
              placeholder="输入分数"
              style="width: 160px"
              @change="computePreview"
            />
            <span class="text-slate-400">→</span>
            <span
              v-if="previewGrade"
              class="text-lg font-bold"
              :style="{ color: previewColor }"
            >
              {{ previewGrade }}级
            </span>
            <span
              v-if="previewDesc"
              class="text-sm text-slate-500"
            >{{ previewDesc }}</span>
          </div>
        </div>
      </div>

      <!-- 操作栏 -->
      <div class="flex justify-end gap-3">
        <a-button
          data-testid="scoring-config-reset"
          :disabled="isReadonly || loading || saving"
          @click="resetForm"
        >
          <template #icon>
            <UndoOutlined />
          </template>
          重置
        </a-button>
        <a-button
          type="primary"
          data-testid="scoring-config-save"
          :loading="saving"
          :disabled="isReadonly || loading || saving"
          size="large"
          @click="saveConfig"
        >
          <template #icon>
            <SaveOutlined />
          </template>
          保存配置
        </a-button>
      </div>
    </a-spin>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  SettingOutlined,
  TrophyOutlined,
  AlertOutlined,
  ControlOutlined,
  EyeOutlined,
  UndoOutlined,
  SaveOutlined,
} from '@ant-design/icons-vue'
import { apiClient } from '@/services/apiService'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const loading = ref(false)
const saving = ref(false)

const canEditScoringConfig = computed(() => {
  const roles = authStore.userRoles || []
  if (roles.some((role) => ['sync_admin', 'super_admin'].includes(role))) {
    return true
  }
  if (roles.includes('admin')) {
    const instituteId = String(
      (authStore.user as { institute_id?: string | null } | null)?.institute_id ?? '',
    ).trim()
    return !instituteId
  }
  return false
})
const isReadonly = computed(() => !canEditScoringConfig.value)

const formData = reactive({
  grade_thresholds: {
    甲: { min_score: 90, label: '甲级', color: '#52c41a', description: '病历质量优秀' },
    乙: { min_score: 70, label: '乙级', color: '#faad14', description: '病历质量合格' },
    丙: { min_score: 0, label: '丙级', color: '#ff4d4f', description: '病历质量不合格' },
  },
  deduction_rules: {
    critical: { max_deduction: 30, description: '关键缺陷最大扣分' },
    major: { max_deduction: 15, description: '重要缺陷最大扣分' },
    minor: { max_deduction: 5, description: '一般缺陷最大扣分' },
  },
  base_score: 100,
  pass_score: 70,
})

// 预览
const previewScore = ref<number | null>(null)
const previewGrade = ref('')
const previewColor = ref('')
const previewDesc = ref('')

function computePreview() {
  if (previewScore.value == null) return
  const s = previewScore.value
  if (s >= formData.grade_thresholds['甲'].min_score) {
    previewGrade.value = '甲'
    previewColor.value = formData.grade_thresholds['甲'].color
    previewDesc.value = formData.grade_thresholds['甲'].description
  } else if (s >= formData.grade_thresholds['乙'].min_score) {
    previewGrade.value = '乙'
    previewColor.value = formData.grade_thresholds['乙'].color
    previewDesc.value = formData.grade_thresholds['乙'].description
  } else {
    previewGrade.value = '丙'
    previewColor.value = formData.grade_thresholds['丙'].color
    previewDesc.value = formData.grade_thresholds['丙'].description
  }
}

// 扣分表
const deductionColumns = [
  { title: '缺陷等级', dataIndex: 'severity', width: 120 },
  { title: '说明', dataIndex: 'description' },
  { title: '最大扣分', dataIndex: 'max_deduction', width: 180 },
]

const deductionTableData = computed(() => [
  { key: 'critical', label: '关键缺陷', color: 'red', ...formData.deduction_rules.critical },
  { key: 'major', label: '重要缺陷', color: 'orange', ...formData.deduction_rules.major },
  { key: 'minor', label: '一般缺陷', color: 'blue', ...formData.deduction_rules.minor },
])

// 提取后端真实错误信息
function resolveApiErrorMessage(error: any, fallback: string): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail.trim()
  const errMsg = error?.response?.data?.error || error?.response?.data?.message
  if (typeof errMsg === 'string' && errMsg.trim()) return errMsg.trim()
  if (typeof error?.message === 'string' && error.message.trim()) return error.message.trim()
  return fallback
}

// 加载配置
async function loadConfig() {
  loading.value = true
  try {
    const { data: result } = await apiClient.get('/api/v1/scoring-config')
    if (result?.success === false) {
      message.error(result?.error || result?.detail || '加载评分配置失败')
      return
    }
    if (result?.data) {
      Object.assign(formData, result.data)
    }
  } catch (e: any) {
    console.error('加载评分配置失败', e)
    message.error(resolveApiErrorMessage(e, '加载评分配置失败'))
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  if (isReadonly.value || saving.value) return
  saving.value = true
  try {
    const { data: result } = await apiClient.put('/api/v1/scoring-config', formData)
    if (result?.success === false) {
      message.error(result?.error || result?.detail || '保存失败')
      return
    }
    message.success('评分配置保存成功')
  } catch (e: any) {
    message.error(resolveApiErrorMessage(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

function resetForm() {
  if (isReadonly.value || loading.value || saving.value) return
  loadConfig()
  previewScore.value = null
  previewGrade.value = ''
}

onMounted(loadConfig)
</script>
