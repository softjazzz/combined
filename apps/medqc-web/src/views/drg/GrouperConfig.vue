<template>
  <div class="grouper-config">
    <a-page-header
      title="分组器配置管理"
      sub-title="DRG/DIP 分组规则与参数配置"
      class="page-header"
      @back="() => $router.back()"
    >
      <template #extra>
        <a-button
          type="primary"
          :loading="saving"
          @click="handleSave"
        >
          <template #icon>
            <SaveOutlined />
          </template>
          保存配置
        </a-button>
      </template>
    </a-page-header>

    <div class="content-wrapper">
      <a-row :gutter="24">
        <!-- 左侧：配置表单 -->
        <a-col :span="14">
          <!-- 基础配置 -->
          <div class="config-card">
            <div class="card-header">
              <SettingOutlined /> 基础配置
            </div>
            <div class="card-body">
              <a-form
                :model="config"
                layout="vertical"
                class="config-form"
              >
                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-form-item label="地区版本">
                      <a-select
                        v-model:value="config.region"
                        @change="handleRegionChange"
                      >
                        <a-select-option value="national">
                          国家版 (CHS-DRG 1.1)
                        </a-select-option>
                        <a-select-option value="sichuan">
                          四川省版
                        </a-select-option>
                        <a-select-option value="luzhou">
                          泸州市版
                        </a-select-option>
                        <a-select-option value="chengdu">
                          成都市版
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
                          DIP (按病种分值)
                        </a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                </a-row>

                <a-row :gutter="16">
                  <a-col :span="8">
                    <a-form-item label="基准费率 (¥)">
                      <a-input-number
                        v-model:value="config.baseRate"
                        :min="1000"
                        :max="50000"
                        :step="100"
                        class="full-width"
                        :formatter="(value?: string | number) => `¥ ${value ?? ''}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')"
                        :parser="(value?: string) => (value || '').replace(/\¥\s?|(,*)/g, '')"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="医院等级系数">
                      <a-input-number
                        v-model:value="config.hospitalCoefficient"
                        :min="0.5"
                        :max="2.0"
                        :step="0.05"
                        :precision="2"
                        class="full-width"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="8">
                    <a-form-item label="区域调整系数">
                      <a-input-number
                        v-model:value="config.regionCoefficient"
                        :min="0.8"
                        :max="1.5"
                        :step="0.01"
                        :precision="2"
                        class="full-width"
                      />
                    </a-form-item>
                  </a-col>
                </a-row>

                <a-form-item label="生效日期">
                  <a-date-picker
                    v-model:value="config.effectiveDate"
                    format="YYYY-MM-DD"
                    class="full-width"
                  />
                </a-form-item>
              </a-form>
            </div>
          </div>

          <!-- 特殊规则配置 -->
          <div class="config-card">
            <div class="card-header">
              <ThunderboltOutlined /> 特殊病例处理规则
            </div>
            <div class="card-body">
              <a-form layout="vertical">
                <a-form-item>
                  <template #label>
                    <span>低倍率病例阈值</span>
                    <a-tooltip title="住院天数低于该值可能按低倍率结算">
                      <QuestionCircleOutlined class="help-icon" />
                    </a-tooltip>
                  </template>
                  <a-slider
                    v-model:value="config.lowRateThreshold"
                    :min="1"
                    :max="7"
                    :marks="{ 1: '1天', 3: '3天', 5: '5天', 7: '7天' }"
                  />
                </a-form-item>

                <a-form-item>
                  <template #label>
                    <span>高倍率病例阈值</span>
                    <a-tooltip title="住院天数超过该值可能按高倍率结算">
                      <QuestionCircleOutlined class="help-icon" />
                    </a-tooltip>
                  </template>
                  <a-slider
                    v-model:value="config.highRateThreshold"
                    :min="14"
                    :max="60"
                    :marks="{ 14: '14天', 30: '30天', 45: '45天', 60: '60天' }"
                  />
                </a-form-item>

                <a-divider />

                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-form-item label="启用CC/MCC校验">
                      <a-switch v-model:checked="config.enableCCMCC" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="启用自动编码建议">
                      <a-switch v-model:checked="config.enableAutoSuggestion" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-form>
            </div>
          </div>
        </a-col>

        <!-- 右侧：状态与统计 -->
        <a-col :span="10">
          <!-- 当前配置状态 -->
          <div class="status-card">
            <div class="status-header">
              <CheckCircleOutlined class="status-icon success" />
              <span>当前配置状态</span>
            </div>
            <div class="status-body">
              <div class="status-row">
                <span class="label">地区</span>
                <span class="value">{{ regionLabels[config.region] || config.region }}</span>
              </div>
              <div class="status-row">
                <span class="label">版本</span>
                <span class="value">CHS-DRG 1.1</span>
              </div>
              <div class="status-row">
                <span class="label">生效日期</span>
                <span class="value">{{ config.effectiveDate?.format('YYYY-MM-DD') || '-' }}</span>
              </div>
              <div class="status-row">
                <span class="label">计算公式</span>
                <span class="value formula">
                  {{ config.baseRate.toLocaleString() }} × 权重 × {{ config.hospitalCoefficient }} × {{ config.regionCoefficient }}
                </span>
              </div>
            </div>
          </div>

          <!-- DRG组统计 -->
          <div class="stats-card">
            <div class="card-header">
              <BarChartOutlined /> DRG 分组统计
            </div>
            <div class="card-body">
              <a-row :gutter="16">
                <a-col :span="12">
                  <a-statistic
                    title="DRG 组数"
                    :value="drgStats.totalGroups"
                    suffix="组"
                  >
                    <template #prefix>
                      <AppstoreOutlined />
                    </template>
                  </a-statistic>
                </a-col>
                <a-col :span="12">
                  <a-statistic
                    title="权重范围"
                    :value="drgStats.weightRange"
                  >
                    <template #prefix>
                      <LineChartOutlined />
                    </template>
                  </a-statistic>
                </a-col>
              </a-row>
              <a-divider style="margin: 16px 0" />
              <a-row :gutter="16">
                <a-col :span="12">
                  <a-statistic
                    title="ICD-10 编码数"
                    :value="drgStats.icd10Count"
                    suffix="个"
                  />
                </a-col>
                <a-col :span="12">
                  <a-statistic
                    title="ICD-9-CM-3 编码数"
                    :value="drgStats.icd9Count"
                    suffix="个"
                  />
                </a-col>
              </a-row>
            </div>
          </div>

          <!-- 医保一致率 -->
          <div class="consistency-card">
            <div class="card-header">
              <SafetyCertificateOutlined /> 医保一致率监控
            </div>
            <div class="card-body">
              <div class="consistency-progress">
                <a-progress
                  type="dashboard"
                  :percent="consistencyRate"
                  :stroke-color="consistencyRate >= 95 ? '#52c41a' : consistencyRate >= 90 ? '#faad14' : '#ff4d4f'"
                  :width="120"
                >
                  <template #format="percent">
                    <span class="progress-text">{{ percent }}%</span>
                  </template>
                </a-progress>
              </div>
              <div class="consistency-info">
                <div class="info-row">
                  <span>目标一致率</span>
                  <span class="target">≥ 95%</span>
                </div>
                <div class="info-row">
                  <span>上月差异病例</span>
                  <span>{{ differenceCount }} 例</span>
                </div>
              </div>
              <a-button
                type="link"
                block
                class="view-detail-btn"
              >
                <SearchOutlined /> 查看差异明细
              </a-button>
            </div>
          </div>
        </a-col>
      </a-row>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  SaveOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  QuestionCircleOutlined,
  CheckCircleOutlined,
  BarChartOutlined,
  AppstoreOutlined,
  LineChartOutlined,
  SafetyCertificateOutlined,
  SearchOutlined
} from '@ant-design/icons-vue'

// 配置数据
const config = reactive({
  region: 'sichuan',
  engine: 'OpenDRG',
  baseRate: 10000,
  hospitalCoefficient: 1.2,
  regionCoefficient: 1.05,
  effectiveDate: dayjs('2024-01-01'),
  lowRateThreshold: 3,
  highRateThreshold: 30,
  enableCCMCC: true,
  enableAutoSuggestion: true
})

const regionLabels: Record<string, string> = {
  national: '国家版',
  sichuan: '四川省',
  luzhou: '泸州市',
  chengdu: '成都市'
}

// DRG 统计数据 (Mock)
const drgStats = reactive({
  totalGroups: 626,
  weightRange: '0.34 - 8.56',
  icd10Count: 28500,
  icd9Count: 9800
})

// 医保一致率 (Mock)
const consistencyRate = ref(96.5)
const differenceCount = ref(42)

const saving = ref(false)

const handleRegionChange = (value: string) => {
  // 根据地区切换更新统计数据
  message.info(`已切换至 ${regionLabels[value]} 版本`)
  
  // Mock: 更新统计数据
  if (value === 'national') {
    drgStats.totalGroups = 628
    drgStats.weightRange = '0.30 - 9.00'
  } else if (value === 'sichuan') {
    drgStats.totalGroups = 626
    drgStats.weightRange = '0.34 - 8.56'
  }
}

const handleSave = async () => {
  saving.value = true
  try {
    // Mock: 保存配置
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('配置保存成功')
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped lang="scss">
.grouper-config {
  min-height: 100vh;
  background-color: #f1f5f9;
}

.page-header {
  background: #fff;
  padding: 16px 32px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  
  :deep(.ant-page-header-heading-title) {
    font-weight: 700;
    font-size: 18px;
    color: #1e293b;
  }
  
  :deep(.ant-page-header-heading-sub-title) {
    color: #64748b;
    font-size: 13px;
  }
}

.content-wrapper {
  padding: 24px 32px;
}

/* Card Styles */
.config-card, .stats-card, .status-card, .consistency-card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  border: 1px solid #e2e8f0;
  margin-bottom: 16px;
  overflow: hidden;
}

.card-header {
  padding: 14px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-weight: 600;
  font-size: 14px;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 8px;
  
  :deep(.anticon) {
    color: #6366f1;
  }
}

.card-body {
  padding: 20px;
}

/* Form Styles */
.config-form {
  .full-width {
    width: 100%;
  }
  
  :deep(.ant-form-item-label > label) {
    font-weight: 500;
    color: #334155;
  }
}

.help-icon {
  margin-left: 6px;
  color: #94a3b8;
  cursor: help;
}

/* Status Card */
.status-card {
  .status-header {
    padding: 14px 20px;
    background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
    border-bottom: 1px solid #a7f3d0;
    font-weight: 600;
    font-size: 14px;
    color: #065f46;
    display: flex;
    align-items: center;
    gap: 8px;
    
    .status-icon.success {
      color: #10b981;
      font-size: 18px;
    }
  }
  
  .status-body {
    padding: 16px 20px;
  }
  
  .status-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px dashed #f1f5f9;
    
    &:last-child {
      border-bottom: none;
    }
    
    .label {
      color: #64748b;
      font-size: 13px;
    }
    
    .value {
      font-weight: 600;
      color: #0f172a;
      font-size: 13px;
      
      &.formula {
        font-family: 'SF Mono', Monaco, monospace;
        font-size: 12px;
        color: #6366f1;
      }
    }
  }
}

/* Consistency Card */
.consistency-card {
  .consistency-progress {
    display: flex;
    justify-content: center;
    padding: 16px 0;
  }
  
  .progress-text {
    font-size: 24px;
    font-weight: 700;
    color: #0f172a;
  }
  
  .consistency-info {
    .info-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      font-size: 13px;
      color: #64748b;
      
      .target {
        font-weight: 600;
        color: #10b981;
      }
    }
  }
  
  .view-detail-btn {
    margin-top: 12px;
    color: #6366f1;
  }
}
</style>
