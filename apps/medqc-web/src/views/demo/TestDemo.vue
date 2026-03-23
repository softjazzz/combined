<template>
  <div class="test-demo">
    <h1>组件测试页面</h1>
    
    <a-card title="QCRulesDemoPanel 测试">
      <QCRulesDemoPanel 
        :selected-rules="testRules"
        :available-rules="testRules"
        :test-record="testRecord"
        @rules-updated="handleRulesUpdated"
      />
    </a-card>
    
    <a-card
      title="测试数据"
      style="margin-top: 16px;"
    >
      <pre>{{ JSON.stringify({ testRules, testRecord }, null, 2) }}</pre>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import QCRulesDemoPanel from '@/components/demo/QCRulesDemoPanel.vue'
import type { QualityControlRule } from '@/types/quality-control'

const testRules = ref<QualityControlRule[]>([
  {
    id: 'rule-001',
    pointId: 'point-001',
    conditions: [],
    logicOperator: 'AND',
    createTime: new Date().toISOString(),
    updateTime: new Date().toISOString(),
    name: '病历完整性检查',
    description: '检查病历基本信息完整性',
    category: '完整性',
    severity: 'high',
    weight: 1.0,
    isActive: true
  }
])

const testRecord = ref({
  id: 'MR-2024-001',
  patientName: '张三',
  department: '心内科',
  admissionDate: '2024-01-15',
  type: '住院病历'
})

const handleRulesUpdated = (rules: QualityControlRule[]) => {
  console.log('规则更新:', rules)
  testRules.value = rules
}
</script>

<style scoped>
.test-demo {
  padding: 24px;
}
</style>
