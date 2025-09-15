<template>
  <div class="qc-rules-demo-panel">
    <a-card title="质控规则演示" class="rules-panel">
      <template #extra>
        <a-tooltip title="规则配置">
          <SettingOutlined />
        </a-tooltip>
      </template>

      <!-- 规则库展示 -->
      <div class="rules-section">
        <div class="rules-header">
          <h4>质控规则管理</h4>
          <a-typography-text type="secondary">
            在此选择要应用的质控规则，已选规则将用于病历分析
          </a-typography-text>
        </div>
        <a-tabs v-model:activeKey="activeTab" type="card">
          <a-tab-pane key="selected" :tab="`已选规则 (${selectedRules.length})`" :tab-style="{ fontWeight: selectedRules.length > 0 ? 'bold' : 'normal' }">
            <div v-if="selectedRules.length === 0" class="empty-rules">
              <a-empty description="暂无选择的规则">
                <template #image>
                  <SettingOutlined style="font-size: 48px; color: #d9d9d9;" />
                </template>
                <div style="margin-top: 16px;">
                  <a-typography-text type="secondary">
                    请切换到"可用规则库"标签页选择要应用的规则
                  </a-typography-text>
                  <div style="margin-top: 8px;">
                    <a-button type="link" @click="activeTab = 'available'">
                      去选择规则 →
                    </a-button>
                  </div>
                </div>
              </a-empty>
            </div>
            <div v-else class="rules-list">
              <div class="rules-summary">
                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-statistic
                      title="已选规则数量"
                      :value="selectedRules.length"
                      suffix="条"
                    />
                  </a-col>
                  <a-col :span="12">
                    <a-statistic
                      title="规则覆盖度"
                      :value="Math.round((selectedRules.length / Math.max(availableRules.length, 1)) * 100)"
                      suffix="%"
                    />
                  </a-col>
                </a-row>
                <div style="margin-top: 12px;">
                  <a-space>
                    <a-button size="small" @click="clearAllRules" :disabled="selectedRules.length === 0">
                      清空全部
                    </a-button>
                    <a-button size="small" type="link" @click="activeTab = 'available'">
                      添加更多规则
                    </a-button>
                  </a-space>
                </div>
              </div>
              <div
                v-for="rule in selectedRules"
                :key="rule.id"
                class="rule-item selected-rule-item"
              >
                <div class="rule-header">
                  <span class="rule-name">{{ rule.name || rule.id }}</span>
                  <a-space>
                    <a-tag :color="getSeverityColor(rule.severity || 'medium')">
                      {{ getSeverityText(rule.severity || 'medium') }}
                    </a-tag>
                    <a-tag color="blue">{{ rule.category || '规则' }}</a-tag>
                    <a-button
                      size="small"
                      type="text"
                      danger
                      @click="removeRule(rule)"
                      title="移除此规则"
                    >
                      移除
                    </a-button>
                  </a-space>
                </div>
                <div class="rule-description">{{ rule.description || '暂无描述' }}</div>
                <div class="rule-details">
                  <a-row :gutter="16">
                    <a-col :span="8">
                      <small>权重: {{ rule.weight || 1.0 }}</small>
                    </a-col>
                    <a-col :span="8">
                      <small>类型: {{ rule.ruleType || '未知' }}</small>
                    </a-col>
                    <a-col :span="8">
                      <small>状态: {{ rule.isActive ? '启用' : '禁用' }}</small>
                    </a-col>
                  </a-row>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <a-tab-pane key="available" :tab="`可用规则库 (${availableRules.length})`">
            <div class="available-rules">
              <div class="rules-filter" style="margin-bottom: 16px;">
                <a-row :gutter="8">
                  <a-col :span="8">
                    <a-select
                      v-model:value="categoryFilter"
                      placeholder="按类别筛选"
                      allowClear
                      size="small"
                      style="width: 100%;"
                    >
                      <a-select-option value="completeness">完整性</a-select-option>
                      <a-select-option value="consistency">一致性</a-select-option>
                      <a-select-option value="rationality">合理性</a-select-option>
                    </a-select>
                  </a-col>
                  <a-col :span="8">
                    <a-select
                      v-model:value="severityFilter"
                      placeholder="按严重程度筛选"
                      allowClear
                      size="small"
                      style="width: 100%;"
                    >
                      <a-select-option value="high">严重</a-select-option>
                      <a-select-option value="medium">重要</a-select-option>
                      <a-select-option value="low">轻微</a-select-option>
                    </a-select>
                  </a-col>
                  <a-col :span="8">
                    <a-select
                      v-model:value="statusFilter"
                      placeholder="按状态筛选"
                      allowClear
                      size="small"
                      style="width: 100%;"
                    >
                      <a-select-option value="active">启用</a-select-option>
                      <a-select-option value="inactive">禁用</a-select-option>
                    </a-select>
                  </a-col>
                </a-row>
              </div>
              <a-list
                :data-source="filteredRules"
                :pagination="{ pageSize: 6, size: 'small', showSizeChanger: true, showQuickJumper: true }"
              >
                <template #renderItem="{ item }">
                  <a-list-item>
                    <template #actions>
                      <a-button
                        size="small"
                        type="primary"
                        :disabled="isRuleSelected(item)"
                        @click="addRule(item)"
                      >
                        {{ isRuleSelected(item) ? '已选择' : '选择' }}
                      </a-button>
                    </template>
                    <a-list-item-meta
                      :title="item.name || item.ruleCode || item.id"
                      :description="item.description || '暂无描述'"
                    >
                      <template #avatar>
                        <a-avatar :style="{ backgroundColor: getSeverityColor(item.severity || 'medium') }">
                          {{ getSeverityText((item.severity || 'medium') as any).charAt(0) }}
                        </a-avatar>
                      </template>
                    </a-list-item-meta>
                    <div style="margin-top: 8px;">
                      <a-space>
                        <a-tag size="small" :color="getSeverityColor(item.severity || 'medium')">
                          {{ getSeverityText(item.severity || 'medium') }}
                        </a-tag>
                        <a-tag size="small" color="blue">{{ item.category || '规则' }}</a-tag>
                        <a-tag size="small" color="green" v-if="item.isActive">启用</a-tag>
                        <a-tag size="small" color="red" v-else>禁用</a-tag>
                      </a-space>
                    </div>
                  </a-list-item>
                </template>
              </a-list>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>

      <!-- 测试病历信息 -->
      <div class="record-section">
        <h4>测试病历</h4>
        <div v-if="!testRecord" class="empty-record">
          <a-empty description="暂无选择的测试病历">
            <a-button type="dashed" @click="selectTestRecord">
              选择测试病历
            </a-button>
          </a-empty>
        </div>
        <div v-else class="record-info">
          <a-descriptions :column="2" size="small" bordered>
            <a-descriptions-item label="病历号">{{ testRecord.id }}</a-descriptions-item>
            <a-descriptions-item label="患者姓名">{{ testRecord.patient_name || testRecord.patientName }}</a-descriptions-item>
            <a-descriptions-item label="科室">{{ testRecord.department }}</a-descriptions-item>
            <a-descriptions-item label="入院日期">{{ testRecord.admission_date || testRecord.admissionDate }}</a-descriptions-item>
            <a-descriptions-item label="病历类型" :span="2">{{ testRecord.record_type || testRecord.type }}</a-descriptions-item>
          </a-descriptions>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="actions-section">
        <a-space>
          <a-button
            type="primary"
            :icon="h(PlayCircleOutlined)"
            :disabled="selectedRules.length === 0 || !testRecord"
            @click="handleStartAnalysis"
            size="large"
          >
            开始质控分析
          </a-button>
          <a-button
            :icon="h(SettingOutlined)"
            @click="handleConfigRules"
          >
            配置规则
          </a-button>
        </a-space>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref, h, computed } from 'vue'
import { message } from 'ant-design-vue'
import { SettingOutlined, PlayCircleOutlined } from '@ant-design/icons-vue'
import type { QualityControlRule } from '@/types/quality-control'

// Props
const props = defineProps<{
  selectedRules: any[]
  availableRules: any[]
  testRecord: any
}>()

// Emits
const emit = defineEmits<{
  rulesUpdated: [rules: QualityControlRule[]]
}>()

// 响应式数据
const activeTab = ref('selected')
const categoryFilter = ref<string>()
const severityFilter = ref<string>()
const statusFilter = ref<string>()

// 可用规则由父组件传入（来源：Supabase / 本地回退）
const availableRules = (props.availableRules || []) as any[]

// 计算属性：过滤后的规则
const filteredRules = computed(() => {
  let rules = availableRules

  if (categoryFilter.value) {
    rules = rules.filter(rule => rule.category === categoryFilter.value)
  }

  if (severityFilter.value) {
    rules = rules.filter(rule => rule.severity === severityFilter.value)
  }

  if (statusFilter.value) {
    const isActive = statusFilter.value === 'active'
    rules = rules.filter(rule => rule.isActive === isActive)
  }

  return rules
})

// 工具函数
const getSeverityColor = (severity: string) => {
  switch (severity) {
    case 'high': return 'red'
    case 'medium': return 'orange'
    case 'low': return 'blue'
    default: return 'default'
  }
}

const getSeverityText = (severity: string) => {
  switch (severity) {
    case 'high': return '高'
    case 'medium': return '中'
    case 'low': return '低'
    default: return '未知'
  }
}

// 事件处理
const handleStartAnalysis = () => {
  if (props.selectedRules.length === 0) {
    message.warning('请先选择质控规则')
    return
  }
  if (!props.testRecord) {
    message.warning('请先选择测试病历')
    return
  }
  message.success('开始质控分析...')
  // 触发分析事件
  emit('rulesUpdated', props.selectedRules)
}

const handleConfigRules = () => {
  message.info('规则配置功能开发中...')
}

const addRule = (rule: any) => {
  // 检查是否已经选择
  if (isRuleSelected(rule)) {
    message.warning(`规则 "${rule.name || rule.id}" 已经选择`)
    return
  }

  const updatedRules = [...props.selectedRules, rule]
  emit('rulesUpdated', updatedRules)
  message.success(`已添加规则: ${rule.name || rule.id}`)
}

const removeRule = (rule: any) => {
  const updatedRules = props.selectedRules.filter(r => r.id !== rule.id)
  emit('rulesUpdated', updatedRules)
  message.success(`已移除规则: ${rule.name || rule.id}`)
}

const isRuleSelected = (rule: any) => {
  return props.selectedRules.some(r => r.id === rule.id)
}

const selectTestRecord = () => {
  message.info('测试病历选择功能开发中...')
}

const clearAllRules = () => {
  emit('rulesUpdated', [])
  message.success('已清空所有规则')
}
</script>

<style scoped lang="less">
.qc-rules-demo-panel {
  .rules-panel {
    .rules-section {
      margin-bottom: 24px;

      .rules-header {
        margin-bottom: 16px;

        h4 {
          font-weight: 600;
          margin-bottom: 4px;
          color: #333;
        }
      }

      .empty-rules {
        text-align: center;
        padding: 40px 0;
      }

      .rules-summary {
        margin-bottom: 16px;
        padding: 12px;
        background: #f8f9fa;
        border-radius: 6px;
      }

      .rules-list {
        .rule-item {
          border: 1px solid #f0f0f0;
          border-radius: 6px;
          padding: 12px;
          margin-bottom: 12px;
          transition: all 0.2s ease;

          &:hover {
            border-color: #d9d9d9;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          }

          &.selected-rule-item {
            border-color: #1890ff;
            background: #f6ffed;
          }

          .rule-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 8px;

            .rule-name {
              font-weight: 500;
              color: #333;
            }
          }

          .rule-description {
            color: #666;
            font-size: 14px;
            margin-bottom: 8px;
          }

          .rule-details {
            font-size: 12px;
            color: #999;
          }
        }
      }

      .available-rules {
        .rules-filter {
          padding: 12px;
          background: #fafafa;
          border-radius: 6px;
          margin-bottom: 16px;
        }
      }
    }

    .record-section {
      margin-bottom: 24px;

      h4 {
        font-weight: 600;
        margin-bottom: 16px;
        color: #333;
        font-size: 16px;
      }

      .empty-record {
        text-align: center;
        padding: 24px;
        border: 1px dashed #d9d9d9;
        border-radius: 6px;
        background: #fafafa;
      }

      .record-info {
        border: 1px solid #f0f0f0;
        border-radius: 6px;
        overflow: hidden;
      }
    }

    .actions-section {
      text-align: center;
      padding-top: 20px;
      border-top: 1px solid #f0f0f0;
      margin-top: 24px;

  }
}
}

</style>
