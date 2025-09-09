<template>
  <BasicLayout>
    <div class="p-6 space-y-6">
      <h3 class="text-xl font-semibold">违规与审计</h3>

      <a-card title="违规记录">
        <div class="mb-3 flex gap-2 items-center">
          <a-select v-model:value="vSeverity" placeholder="严重级" allow-clear style="width: 140px">
            <a-select-option value="info">提醒</a-select-option>
            <a-select-option value="warn">警告</a-select-option>
            <a-select-option value="block">拦截</a-select-option>
          </a-select>
          <a-input v-model:value="vRuleCode" placeholder="规则编码 (如 DRUG_AGE_DEMO)" style="width: 220px" />
          <a-input v-model:value="vVisitId" placeholder="就诊ID" style="width: 160px" />
          <a-button type="primary" @click="reloadViolations">查询</a-button>
        </div>
        <a-table :data-source="violations" :columns="violationCols" :pagination="false" rowKey="id" />
        <div class="flex justify-end mt-3">
          <a-pagination :current="vPage" :pageSize="vPageSize" :total="vTotal" @change="onVPage" />
        </div>
      </a-card>

      <a-card title="审计任务">
        <a-table :data-source="audits" :columns="auditCols" :pagination="false" rowKey="id" />
        <div class="flex justify-end mt-3">
          <a-pagination :current="aPage" :pageSize="aPageSize" :total="aTotal" @change="onAPage" />
        </div>
      </a-card>
    </div>
  </BasicLayout>
  </template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref, onMounted } from 'vue'
import { listViolations, listAuditTasks } from '@/services/supabaseSdk'

const violations = ref<any[]>([])
const vPage = ref(1)
const vPageSize = ref(10)
const vTotal = ref(0)
const vSeverity = ref<string | undefined>(undefined)
const vRuleCode = ref<string>('')
const vVisitId = ref<string>('')

const audits = ref<any[]>([])
const aPage = ref(1)
const aPageSize = ref(10)
const aTotal = ref(0)

const violationCols = [
  { title: 'ID', dataIndex: 'id' },
  { title: '就诊ID', dataIndex: 'visit_id' },
  { title: '严重级', dataIndex: 'severity' },
  { title: '时间', dataIndex: 'created_at' }
]

const auditCols = [
  { title: 'ID', dataIndex: 'id' },
  { title: '规则ID', dataIndex: 'rule_id' },
  { title: '状态', dataIndex: 'status' },
  { title: '时间', dataIndex: 'created_at' }
]

async function loadViolations() {
  const { rows, total } = await listViolations({
    page: vPage.value,
    pageSize: vPageSize.value,
    severity: vSeverity.value || undefined,
    ruleCode: vRuleCode.value?.trim() || undefined,
    visitId: vVisitId.value?.trim() || undefined
  })
  violations.value = rows
  vTotal.value = total
}

async function loadAudits() {
  const { rows, total } = await listAuditTasks({ page: aPage.value, pageSize: aPageSize.value })
  audits.value = rows
  aTotal.value = total
}

function onVPage(p: number) { vPage.value = p; loadViolations() }
function reloadViolations() { vPage.value = 1; loadViolations() }
function onAPage(p: number) { aPage.value = p; loadAudits() }

onMounted(() => { loadViolations(); loadAudits() })
</script>



