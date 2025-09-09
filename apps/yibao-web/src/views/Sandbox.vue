<template>
  <BasicLayout>
    <div class="min-h-screen bg-gray-50 p-4 lg:p-6">
      <!-- 页面头部 -->
      <div class="bg-white rounded-xl shadow-sm border border-gray-200 p-6 mb-6">
        <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div class="flex-1">
            <div class="flex items-center space-x-3 mb-2">
              <div class="p-2 bg-purple-100 rounded-lg">
                <ExperimentOutlined class="text-xl text-purple-600" />
              </div>
              <h1 class="text-2xl lg:text-3xl font-bold text-gray-900">
                规则测试沙箱
              </h1>
            </div>
            <p class="text-gray-600 text-sm lg:text-base">
              在安全的测试环境中验证规则配置的正确性和有效性
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <a-button @click="clearTest" class="flex items-center space-x-2">
              <template #icon><ClearOutlined /></template>
              <span>清空</span>
            </a-button>
            <a-button @click="loadTemplate" class="flex items-center space-x-2">
              <template #icon><FileTextOutlined /></template>
              <span>加载模板</span>
            </a-button>
            <a-button
              type="primary"
              @click="runTest"
              :loading="testing"
              class="flex items-center space-x-2 bg-purple-600 hover:bg-purple-700"
            >
              <template #icon><PlayCircleOutlined /></template>
              <span>运行测试</span>
            </a-button>
          </div>
        </div>
      </div>

      <div class="sandbox-content">
        <a-row :gutter="24">
          <!-- 左侧：规则选择和测试数据 -->
          <a-col :span="12">
            <!-- 规则选择 -->
            <a-card title="选择测试规则" class="test-card">
              <a-select
                v-model:value="selectedRuleId"
                placeholder="选择要测试的规则"
                style="width: 100%"
                show-search
                :filter-option="filterRuleOption"
                @change="onRuleChange"
              >
                <a-select-option
                  v-for="rule in rules"
                  :key="rule.id"
                  :value="rule.id"
                >
                  <div class="rule-option">
                    <span class="rule-code">{{ rule.code }}</span>
                    <span class="rule-name">{{ rule.name }}</span>
                    <a-tag :color="getSeverityColor(rule.severity)" size="small">
                      {{ getSeverityLabel(rule.severity) }}
                    </a-tag>
                  </div>
                </a-select-option>
              </a-select>

              <div v-if="selectedRule" class="rule-info">
                <a-descriptions :column="1" size="small">
                  <a-descriptions-item label="规则类型">
                    {{ getTypeLabel(selectedRule.rule_type) }}
                  </a-descriptions-item>
                  <a-descriptions-item label="规则描述">
                    {{ selectedRule.description || '无描述' }}
                  </a-descriptions-item>
                </a-descriptions>
              </div>
            </a-card>

            <!-- 测试数据输入 -->
            <a-card title="测试数据" class="test-card">
              <a-tabs v-model:activeKey="activeTab">
                <a-tab-pane key="patient" tab="患者信息">
                  <a-form layout="vertical">
                    <a-row :gutter="16">
                      <a-col :span="12">
                        <a-form-item label="患者年龄">
                          <a-input-number
                            v-model:value="testData.patient.age"
                            :min="0"
                            :max="150"
                            style="width: 100%"
                          />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="患者性别">
                          <a-select v-model:value="testData.patient.gender" style="width: 100%">
                            <a-select-option value="male">男</a-select-option>
                            <a-select-option value="female">女</a-select-option>
                          </a-select>
                        </a-form-item>
                      </a-col>
                    </a-row>
                    <a-form-item label="患者ID">
                      <a-input v-model:value="testData.patient.id" placeholder="输入患者ID" />
                    </a-form-item>
                  </a-form>
                </a-tab-pane>

                <a-tab-pane key="visit" tab="就诊信息">
                  <a-form layout="vertical">
                    <a-form-item label="就诊类型">
                      <a-select v-model:value="testData.visit.type" style="width: 100%">
                        <a-select-option value="OUTPATIENT">门诊</a-select-option>
                        <a-select-option value="INPATIENT">住院</a-select-option>
                        <a-select-option value="EMERGENCY">急诊</a-select-option>
                      </a-select>
                    </a-form-item>
                    <a-form-item label="科室">
                      <a-input v-model:value="testData.visit.department" placeholder="输入科室名称" />
                    </a-form-item>
                    <a-form-item label="医院级别">
                      <a-select v-model:value="testData.visit.hospital_level" style="width: 100%">
                        <a-select-option value="1">一级医院</a-select-option>
                        <a-select-option value="2">二级医院</a-select-option>
                        <a-select-option value="3">三级医院</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-form>
                </a-tab-pane>

                <a-tab-pane key="order" tab="医嘱信息">
                  <a-form layout="vertical">
                    <a-form-item label="药品编码">
                      <a-input v-model:value="testData.order.drug_code" placeholder="输入药品编码" />
                    </a-form-item>
                    <a-form-item label="药品名称">
                      <a-input v-model:value="testData.order.drug_name" placeholder="输入药品名称" />
                    </a-form-item>
                    <a-form-item label="用药天数">
                      <a-input-number
                        v-model:value="testData.order.duration_days"
                        :min="1"
                        style="width: 100%"
                      />
                    </a-form-item>
                  </a-form>
                </a-tab-pane>
              </a-tabs>
            </a-card>
          </a-col>

          <!-- 右侧：测试结果 -->
          <a-col :span="12">
            <a-card title="测试结果" class="result-card">
              <div v-if="!testResult && !testing" class="no-result">
                <a-empty description="请选择规则并运行测试" />
              </div>

              <div v-if="testing" class="testing-state">
                <a-spin size="large">
                  <div class="testing-text">正在执行规则测试...</div>
                </a-spin>
              </div>

              <div v-if="testResult" class="test-result">
                <div class="result-header">
                  <a-tag
                    :color="testResult.matched ? getSeverityColor(testResult.severity) : 'default'"
                    class="result-tag"
                  >
                    {{ testResult.matched ? '规则命中' : '规则未命中' }}
                  </a-tag>
                  <span class="execution-time">执行时间: {{ testResult.execution_time }}ms</span>
                </div>

                <div class="result-content">
                  <a-descriptions :column="1" bordered size="small">
                    <a-descriptions-item label="匹配结果">
                      <a-tag :color="testResult.matched ? 'success' : 'default'">
                        {{ testResult.matched ? '匹配' : '不匹配' }}
                      </a-tag>
                    </a-descriptions-item>
                    <a-descriptions-item label="严重级别" v-if="testResult.matched">
                      <a-tag :color="getSeverityColor(testResult.severity)">
                        {{ getSeverityLabel(testResult.severity) }}
                      </a-tag>
                    </a-descriptions-item>
                    <a-descriptions-item label="动作类型" v-if="testResult.matched">
                      <a-tag :color="getActionTypeColor(testResult.action_type)">
                        {{ getActionTypeLabel(testResult.action_type) }}
                      </a-tag>
                    </a-descriptions-item>
                    <a-descriptions-item label="提示消息" v-if="testResult.matched">
                      <div class="message-text">{{ testResult.message }}</div>
                    </a-descriptions-item>
                  </a-descriptions>
                </div>

                <div class="result-details" v-if="testResult.details">
                  <a-divider>执行详情</a-divider>
                  <div class="condition-results">
                    <h4>条件匹配结果:</h4>
                    <div
                      v-for="(matched, index) in testResult.details.conditions_matched"
                      :key="index"
                      class="condition-item"
                    >
                      <a-tag :color="matched ? 'success' : 'error'" size="small">
                        条件 {{ index + 1 }}: {{ matched ? '匹配' : '不匹配' }}
                      </a-tag>
                    </div>
                  </div>
                </div>
              </div>
            </a-card>
          </a-col>
        </a-row>
      </div>
    </div>
  </BasicLayout>
</template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref, onMounted, computed } from 'vue'
import { message } from 'ant-design-vue'
import { supabase } from '@/lib/supabase'
import { rulesService } from '@/services/rulesService'
import type { Rule, RuleTestRequest, RuleTestResult } from '@/types/rules'
import {
  ExperimentOutlined, ClearOutlined, FileTextOutlined, PlayCircleOutlined
} from '@ant-design/icons-vue'

// 响应式数据
const rules = ref<Rule[]>([])
const selectedRuleId = ref<number>()
const selectedRule = computed(() => rules.value.find(r => r.id === selectedRuleId.value))
const testing = ref(false)
const testResult = ref<RuleTestResult>()
const activeTab = ref('patient')

// 测试数据
const testData = ref({
  patient: {
    id: 'P001',
    age: 25,
    gender: 'male'
  },
  visit: {
    type: 'OUTPATIENT',
    department: '内科',
    hospital_level: '3'
  },
  order: {
    drug_code: 'DRUG001',
    drug_name: '阿司匹林',
    duration_days: 7
  }
})

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

const getActionTypeColor = (actionType: string) => {
  const colorMap: Record<string, string> = {
    'intercept': 'red',
    'warn': 'orange',
    'notify': 'blue'
  }
  return colorMap[actionType] || 'default'
}

const getActionTypeLabel = (actionType: string) => {
  const labelMap: Record<string, string> = {
    'intercept': '拦截',
    'warn': '警告',
    'notify': '通知'
  }
  return labelMap[actionType] || actionType
}

const filterRuleOption = (input: string, option: any) => {
  const rule = rules.value.find(r => r.id === option.value)
  if (!rule) return false
  return rule.code.toLowerCase().includes(input.toLowerCase()) ||
         rule.name.toLowerCase().includes(input.toLowerCase())
}

// 事件处理
const onRuleChange = (ruleId: number) => {
  testResult.value = undefined
}

const clearTest = () => {
  selectedRuleId.value = undefined
  testResult.value = undefined
  testData.value = {
    patient: { id: 'P001', age: 25, gender: 'male' },
    visit: { type: 'OUTPATIENT', department: '内科', hospital_level: '3' },
    order: { drug_code: 'DRUG001', drug_name: '阿司匹林', duration_days: 7 }
  }
}

const loadTemplate = () => {
  // 加载测试模板
  testData.value = {
    patient: { id: 'P002', age: 65, gender: 'female' },
    visit: { type: 'INPATIENT', department: '心内科', hospital_level: '3' },
    order: { drug_code: 'ASPIRIN_100MG', drug_name: '阿司匹林肠溶片', duration_days: 30 }
  }
  message.success('已加载测试模板')
}

const runTest = async () => {
  if (!selectedRuleId.value) {
    message.error('请先选择要测试的规则')
    return
  }

  testing.value = true
  testResult.value = undefined

  try {
    const request: RuleTestRequest = {
      rule_id: selectedRuleId.value,
      test_data: testData.value
    }

    const result = await rulesService.testRule(request)
    testResult.value = result

    message.success('测试完成')
  } catch (error: any) {
    message.error(`测试失败: ${error.message}`)
  } finally {
    testing.value = false
  }
}

// 数据加载
const loadRules = async () => {
  try {
    const response = await rulesService.getRules({ pageSize: 100 })
    rules.value = response.data.filter(rule => rule.enabled)
  } catch (error) {
    console.error('加载规则失败:', error)
    message.error('加载规则失败')
  }
}

onMounted(() => {
  loadRules()
})
</script>
