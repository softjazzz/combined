<template>
  <BasicLayout>
    <div>
      <h3>实时提醒沙箱</h3>
      <a-row :gutter="12">
        <a-col :span="12">
          <a-card title="Facts（上下文）">
            <a-textarea v-model:value="factsText" rows="10" />
          </a-card>
          <a-card title="表达式（JSON）" style="margin-top:12px;">
            <a-textarea v-model:value="exprText" rows="10" />
          </a-card>
          <a-button type="primary" style="margin-top:12px;" @click="run">运行</a-button>
        </a-col>
        <a-col :span="12">
          <a-card title="结果">
            <div>匹配：{{ matched ? '是' : '否' }}</div>
            <div style="margin-top:8px;">消息：{{ message }}</div>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </BasicLayout>
  </template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref } from 'vue'
import { evalExpression, renderMessage } from '@health-qc/rule-engine'

const factsText = ref(`{ "patient": { "age": 18 }, "order": { "drug_code": "ABC001" } }`)
const exprText = ref(`{ "all": [ { "fact": "patient.age", "op": ">", "value": 14 }, { "fact": "order.drug_code", "op": "in", "value": ["ABC001","ABC002"] } ] }`)
const matched = ref(false)
const message = ref('')

function run() {
  try {
    const facts = JSON.parse(factsText.value || '{}')
    const expr = JSON.parse(exprText.value || '{}')
    matched.value = evalExpression(facts, expr)
    message.value = matched.value ? renderMessage('药品 {order.drug_code} 不适用于年龄 {patient.age}', facts) : ''
  } catch (e: any) {
    matched.value = false
    message.value = e?.message || '解析失败'
  }
}
</script>



