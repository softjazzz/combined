<template>
  <div class="grouper-config">
    <a-page-header
      title="分组器配置管理"
      sub-title="6.2.2 分组器本地化适配（真实接口）"
      class="page-header"
      @back="() => $router.back()"
    >
      <template #extra>
        <a-space>
          <a-button
            :loading="refreshing"
            @click="loadAll"
          >
            刷新
          </a-button>
          <a-button
            type="primary"
            :loading="saving"
            @click="handleSave"
          >
            保存草稿
          </a-button>
          <a-button
            type="primary"
            ghost
            :loading="publishing"
            @click="handlePublish"
          >
            发布版本
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <a-row :gutter="16">
        <a-col :span="12">
          <a-card
            title="当前配置草稿"
            size="small"
          >
            <a-form
              :model="config"
              layout="vertical"
            >
              <a-row :gutter="12">
                <a-col :span="12">
                  <a-form-item label="地区版本">
                    <a-select v-model:value="config.region">
                      <a-select-option value="national">
                        国家版
                      </a-select-option>
                      <a-select-option value="sichuan">
                        四川省版
                      </a-select-option>
                      <a-select-option value="luzhou">
                        泸州版
                      </a-select-option>
                      <a-select-option value="chengdu">
                        成都版
                      </a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="分组引擎">
                    <a-select v-model:value="config.engine">
                      <a-select-option value="OpenDRG">
                        OpenDRG
                      </a-select-option>
                      <a-select-option value="DIP">
                        DIP
                      </a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="12">
                <a-col :span="8">
                  <a-form-item label="基准费率">
                    <a-input-number
                      v-model:value="config.baseRate"
                      class="full-width"
                      :min="1000"
                      :max="50000"
                    />
                  </a-form-item>
                </a-col>
                <a-col :span="8">
                  <a-form-item label="医院等级系数">
                    <a-input-number
                      v-model:value="config.hospitalCoefficient"
                      class="full-width"
                      :min="0.5"
                      :max="2"
                      :step="0.01"
                    />
                  </a-form-item>
                </a-col>
                <a-col :span="8">
                  <a-form-item label="区域调整系数">
                    <a-input-number
                      v-model:value="config.regionCoefficient"
                      class="full-width"
                      :min="0.5"
                      :max="2"
                      :step="0.01"
                    />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-row :gutter="12">
                <a-col :span="12">
                  <a-form-item label="低倍率阈值">
                    <a-input-number
                      v-model:value="config.lowRateThreshold"
                      class="full-width"
                      :min="1"
                      :max="20"
                    />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="高倍率阈值">
                    <a-input-number
                      v-model:value="config.highRateThreshold"
                      class="full-width"
                      :min="14"
                      :max="120"
                    />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item label="生效日期">
                <a-date-picker
                  v-model:value="effectiveDateValue"
                  format="YYYY-MM-DD"
                  class="full-width"
                />
              </a-form-item>

              <a-row :gutter="12">
                <a-col :span="12">
                  <a-form-item label="CC/MCC 校验">
                    <a-switch v-model:checked="config.enableCCMCC" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="自动编码建议">
                    <a-switch v-model:checked="config.enableAutoSuggestion" />
                  </a-form-item>
                </a-col>
              </a-row>
            </a-form>
          </a-card>

          <a-card
            title="一致率校验样本（可编辑）"
            size="small"
            class="mt-12"
          >
            <a-space
              direction="vertical"
              class="full-width"
            >
              <a-alert
                type="info"
                show-icon
                message="统计公式：一致率 = 匹配成功样本数 / 有效对照样本数"
              />
              <a-textarea
                v-model:value="consistencySampleText"
                :rows="8"
                placeholder="每行: case_key,hospital_group,insurance_group"
              />
              <a-button
                :loading="checkingConsistency"
                @click="handleRunConsistency"
              >
                运行一致率校验
              </a-button>
            </a-space>
          </a-card>
        </a-col>

        <a-col :span="12">
          <a-card
            title="发布状态"
            size="small"
          >
            <a-descriptions
              size="small"
              :column="1"
            >
              <a-descriptions-item label="当前发布版本">
                {{ current.published_version_id || '-' }}
              </a-descriptions-item>
              <a-descriptions-item label="草稿地区">
                {{ config.region }}
              </a-descriptions-item>
              <a-descriptions-item label="草稿引擎">
                {{ config.engine }}
              </a-descriptions-item>
            </a-descriptions>
          </a-card>

          <a-card
            title="版本列表（可回滚）"
            size="small"
            class="mt-12"
          >
            <a-table
              size="small"
              :data-source="versionItems"
              :pagination="{ pageSize: 5 }"
              :row-key="(item: any) => item.version_id"
            >
              <a-table-column
                key="version_id"
                title="版本ID"
                data-index="version_id"
              />
              <a-table-column
                key="operator"
                title="操作人"
                data-index="operator"
              />
              <a-table-column
                key="operated_at"
                title="时间"
              >
                <template #default="{ record }">
                  {{ formatTime(record.operated_at) }}
                </template>
              </a-table-column>
              <a-table-column
                key="is_published"
                title="状态"
              >
                <template #default="{ record }">
                  <a-tag :color="record.is_published ? 'green' : 'default'">
                    {{ record.is_published ? '生效中' : '历史版本' }}
                  </a-tag>
                </template>
              </a-table-column>
              <a-table-column
                key="actions"
                title="操作"
              >
                <template #default="{ record }">
                  <a-space>
                    <a-button
                      size="small"
                      @click="handleViewVersion(record.version_id)"
                    >
                      查看
                    </a-button>
                    <a-button
                      size="small"
                      :disabled="record.is_published"
                      :loading="rollingBack && rollbackTargetId === record.version_id"
                      @click="handleRollback(record.version_id)"
                    >
                      回滚
                    </a-button>
                  </a-space>
                </template>
              </a-table-column>
            </a-table>
          </a-card>

          <a-card
            title="一致率看板"
            size="small"
            class="mt-12"
          >
            <div class="consistency-block">
              <a-progress
                type="dashboard"
                :percent="consistencyRate"
                :stroke-color="consistencyRate >= 95 ? '#52c41a' : '#faad14'"
                :width="120"
              />
              <div class="consistency-meta">
                <div>目标：≥95%</div>
                <div>有效样本：{{ consistencyReport?.summary?.valid_count ?? 0 }}</div>
                <div>差异样本：{{ consistencyReport?.summary?.difference_count ?? 0 }}</div>
              </div>
            </div>
            <a-button
              type="link"
              @click="detailVisible = true"
            >
              查看差异明细
            </a-button>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <a-modal
      v-model:open="detailVisible"
      title="一致率差异明细"
      :footer="null"
      width="860"
    >
      <a-table
        size="small"
        :data-source="consistencyReport?.differences || []"
        :row-key="(item: any, idx: number) => item.case_key || idx"
      >
        <a-table-column
          key="case_key"
          title="样本键"
          data-index="case_key"
        />
        <a-table-column
          key="hospital_group"
          title="院内入组"
          data-index="hospital_group"
        />
        <a-table-column
          key="insurance_group"
          title="医保入组"
          data-index="insurance_group"
        />
      </a-table>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  getGrouperConfigCurrent,
  getGrouperConfigVersionDetail,
  listGrouperConfigVersions,
  publishGrouperConfig,
  rollbackGrouperConfig,
  runGrouperConsistencyCheck,
  saveGrouperConfigDraft,
} from '@/api/drg'

const saving = ref(false)
const publishing = ref(false)
const rollingBack = ref(false)
const checkingConsistency = ref(false)
const refreshing = ref(false)
const rollbackTargetId = ref('')
const detailVisible = ref(false)

const current = reactive({
  published_version_id: null as string | null,
})

const config = reactive({
  region: 'sichuan',
  engine: 'OpenDRG',
  baseRate: 10000,
  hospitalCoefficient: 1.2,
  regionCoefficient: 1.05,
  effectiveDate: '2024-01-01',
  lowRateThreshold: 3,
  highRateThreshold: 30,
  enableCCMCC: true,
  enableAutoSuggestion: true,
})

const versionItems = ref<any[]>([])
const consistencyReport = ref<any>(null)

const consistencySampleText = ref('LXA001,AB15,AB15\nLXA002,AB23,AB23\nLXA003,AF19,AF20')

const consistencyRate = computed(() =>
  Number(consistencyReport.value?.summary?.consistency_rate || 0),
)

const effectiveDateValue = computed({
  get: () => (config.effectiveDate ? dayjs(config.effectiveDate) : null),
  set: (value) => {
    config.effectiveDate = value ? value.format('YYYY-MM-DD') : ''
  },
})

function currentOperator() {
  return 'workstation-v4'
}

function formatTime(value: string) {
  if (!value) return '-'
  const dt = dayjs(value)
  return dt.isValid() ? dt.format('YYYY-MM-DD HH:mm:ss') : value
}

async function loadCurrentConfig() {
  const data = await getGrouperConfigCurrent()
  Object.assign(config, data.draft || {})
  current.published_version_id = data.published_version_id || null
  consistencyReport.value = data.latest_consistency_report || null
}

async function loadVersions() {
  const data = await listGrouperConfigVersions()
  versionItems.value = data.items || []
}

async function loadAll() {
  refreshing.value = true
  try {
    await Promise.all([loadCurrentConfig(), loadVersions()])
  } finally {
    refreshing.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await saveGrouperConfigDraft({
      config: { ...config },
      operator: currentOperator(),
      change_summary: '更新分组器本地化配置草稿',
    })
    message.success('草稿保存成功')
    await loadCurrentConfig()
  } catch (error) {
    console.error(error)
    message.error('草稿保存失败')
  } finally {
    saving.value = false
  }
}

async function handlePublish() {
  publishing.value = true
  try {
    await publishGrouperConfig({
      operator: currentOperator(),
      change_summary: `发布 ${config.region} ${config.engine} 配置`,
    })
    message.success('配置发布成功')
    await loadAll()
  } catch (error) {
    console.error(error)
    message.error('配置发布失败')
  } finally {
    publishing.value = false
  }
}

async function handleRollback(versionId: string) {
  rollbackTargetId.value = versionId
  rollingBack.value = true
  try {
    await rollbackGrouperConfig({
      version_id: versionId,
      operator: currentOperator(),
      change_summary: `回滚到版本 ${versionId}`,
    })
    message.success('回滚成功')
    await loadAll()
  } catch (error) {
    console.error(error)
    message.error('回滚失败')
  } finally {
    rollingBack.value = false
    rollbackTargetId.value = ''
  }
}

async function handleViewVersion(versionId: string) {
  try {
    const detail = await getGrouperConfigVersionDetail(versionId)
    Modal.info({
      title: `版本详情 ${versionId}`,
      width: 760,
      content: JSON.stringify(detail, null, 2),
    })
  } catch (error) {
    console.error(error)
    message.error('读取版本详情失败')
  }
}

function parseSamples() {
  return consistencySampleText.value
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line, index) => {
      const [caseKey, hospitalGroup, insuranceGroup] = line
        .split(',')
        .map((item) => item?.trim() || '')
      return {
        case_key: caseKey || `line-${index + 1}`,
        hospital_group: hospitalGroup,
        insurance_group: insuranceGroup,
      }
    })
}

async function handleRunConsistency() {
  checkingConsistency.value = true
  try {
    const samples = parseSamples()
    if (samples.length === 0) {
      message.warning('请至少提供一条样本')
      return
    }
    const report = await runGrouperConsistencyCheck({
      operator: currentOperator(),
      version_id: current.published_version_id || undefined,
      samples,
    })
    consistencyReport.value = report
    message.success(`一致率校验完成：${report.summary?.consistency_rate ?? 0}%`)
  } catch (error) {
    console.error(error)
    message.error('一致率校验失败')
  } finally {
    checkingConsistency.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped>
.grouper-config {
  min-height: 100vh;
  background: #f3f6fa;
}

.page-header {
  background: #fff;
}

.content-wrapper {
  padding: 16px;
}

.full-width {
  width: 100%;
}

.mt-12 {
  margin-top: 12px;
}

.consistency-block {
  display: flex;
  align-items: center;
  gap: 16px;
}

.consistency-meta {
  display: grid;
  gap: 6px;
  font-size: 12px;
  color: #334155;
}
</style>
