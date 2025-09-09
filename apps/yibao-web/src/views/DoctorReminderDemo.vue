<template>
  <BasicLayout>
    <div class="p-6 space-y-6">
      <h3 class="text-xl font-semibold">医生端提醒组件 Demo</h3>

      <a-card title="模拟医嘱表单">
        <a-form layout="vertical">
          <a-row :gutter="12">
            <a-col :span="6">
              <a-form-item label="患者年龄">
                <a-input-number v-model:value="form.patient.age" :min="0" style="width: 100%;" />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item label="患者性别">
                <a-select v-model:value="form.patient.gender" :options="genderOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item label="就诊方式">
                <a-select v-model:value="form.visit.type" :options="visitTypeOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="6">
              <a-form-item label="药品编码">
                <a-input v-model:value="form.order.drug_code" placeholder="如 DEMO_DRUG_INPATIENT" />
              </a-form-item>
            </a-col>
          </a-row>
          <a-space>
            <a-button type="primary" :loading="submitting" @click="submitOrder">模拟提交医嘱</a-button>
            <a-button @click="reset">重置</a-button>
          </a-space>
        </a-form>
      </a-card>

      <a-drawer v-model:open="drawerOpen" :title="drawerTitle" :width="520" :maskClosable="false">
        <div class="space-y-3">
          <div>
            <a-tag :color="severityColor(decision.severity)">{{ decision.severity || 'info' }}</a-tag>
          </div>
          <div v-if="Array.isArray(decision.messages) && decision.messages.length">
            <a-alert v-for="(m, i) in decision.messages" :key="i" :message="m" :type="alertType(decision.severity)" show-icon class="mb-2" />
          </div>
          <a-divider>命中详情</a-divider>
          <a-list :data-source="hits" bordered>
            <template #renderItem="{ item }">
              <a-list-item>
                <a-space>
                  <a-tag :color="severityColor(item.severity)">{{ item.severity }}</a-tag>
                  <span class="font-mono text-xs">{{ item.ruleCode }}</span>
                  <span>{{ item.message }}</span>
                </a-space>
              </a-list-item>
            </template>
          </a-list>
          <a-divider>上下文快照</a-divider>
          <pre class="json-pre">{{ pretty(form) }}</pre>

          <template v-if="decision.severity === 'warn'">
            <a-divider>忽略理由（演示）</a-divider>
            <a-select v-model:value="ignore.reason" :options="ignoreReasons" style="width: 100%;" placeholder="请选择忽略理由" />
            <a-textarea v-model:value="ignore.note" :rows="3" placeholder="补充说明（可选）" class="mt-2" />
          </template>

          <div class="flex justify-end gap-2 mt-4">
            <a-button v-if="decision.severity !== 'block'" @click="closeDrawer">知道了</a-button>
            <a-button v-if="decision.severity === 'warn'" type="primary" @click="confirmIgnore">忽略并继续</a-button>
            <a-button v-if="decision.severity === 'block'" type="primary" danger @click="closeDrawer">修改医嘱</a-button>
          </div>
        </div>
      </a-drawer>
    </div>
  </BasicLayout>
</template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref } from 'vue'
import { message } from 'ant-design-vue'
import { functionsPost } from '@/services/functionsClient'

const genderOptions = [
  { label: '男', value: 'M' },
  { label: '女', value: 'F' }
]
const visitTypeOptions = [
  { label: '门诊', value: 'OUTPATIENT' },
  { label: '住院', value: 'INPATIENT' }
]

const form = ref<any>({
  patient: { age: 18, gender: 'F' },
  visit: { type: 'OUTPATIENT', id: 'V_DEMO_001' },
  order: { drug_code: 'DEMO_DRUG_INPATIENT' }
})

const submitting = ref(false)
const drawerOpen = ref(false)
const drawerTitle = ref('医嘱提醒')
const decision = ref<{ severity: 'info' | 'warn' | 'block' | '' ; messages: string[] }>({ severity: '', messages: [] })
const hits = ref<any[]>([])
const ignore = ref<{ reason?: string; note?: string }>({})
const ignoreReasons = [
  { label: '患者病情特殊', value: 'special_condition' },
  { label: '上级医师已同意', value: 'approved_by_senior' },
  { label: '与患者充分沟通', value: 'patient_informed' }
]

function severityColor(s?: string) {
  if (s === 'block') return 'red'
  if (s === 'warn') return 'orange'
  if (s === 'info') return 'blue'
  return 'default'
}
function alertType(s?: string) {
  if (s === 'block') return 'error'
  if (s === 'warn') return 'warning'
  return 'info'
}
function pretty(obj: any) {
  try { return JSON.stringify(obj, null, 2) } catch { return String(obj) }
}

async function submitOrder() {
  submitting.value = true
  try {
    const payload = { event: 'drug_order', context: form.value, record: true }
    const resp = await functionsPost('/evaluate-rule', payload)
    hits.value = Array.isArray(resp?.hits) ? resp.hits : []
    if (!hits.value.length) {
      decision.value = { severity: 'info', messages: ['未发现问题，可继续'] }
    } else {
      // 取最高严重级
      let sev: 'info' | 'warn' | 'block' = 'info'
      hits.value.forEach((h: any) => { if (h.severity === 'block') sev = 'block'; else if (h.severity === 'warn' && sev === 'info') sev = 'warn' })
      const messages = hits.value.map((h: any) => h.message || `${h.severity}:${h.ruleCode}`)
      decision.value = { severity: sev, messages }
    }
    drawerOpen.value = true
    drawerTitle.value = decision.value.severity === 'block' ? '拦截：请修改医嘱' : (decision.value.severity === 'warn' ? '警告：需确认忽略理由' : '提醒')
  } catch (e: any) {
    message.error(e?.message || '评估失败')
  } finally {
    submitting.value = false
  }
}

function reset() {
  form.value = { patient: { age: 18, gender: 'F' }, visit: { type: 'OUTPATIENT', id: 'V_DEMO_001' }, order: { drug_code: 'DEMO_DRUG_INPATIENT' } }
}

function closeDrawer() { drawerOpen.value = false }

async function confirmIgnore() {
  try {
    // 取最近一条违规（实际应由 evaluate-rule 返回记录ID；这里简化：不做ID关联，仅提示成功）
    await functionsPost('/violations?action=ignore', { id: hits.value?.[0]?.violation_id || 0, reason: ignore.value.reason, note: ignore.value.note })
    message.success('已记录忽略理由（演示或最近一条记录）')
  } catch {}
  drawerOpen.value = false
}
const templates = [
  { name: '门诊+住院药演示（应警告/拦截）', data: { patient: { age: 18, gender: 'F' }, visit: { type: 'OUTPATIENT', id: 'V_DEMO_001' }, order: { drug_code: 'DEMO_DRUG_INPATIENT' } } },
  { name: '住院+住院药（通过）', data: { patient: { age: 45, gender: 'M' }, visit: { type: 'INPATIENT', id: 'V_DEMO_002' }, order: { drug_code: 'DEMO_DRUG_INPATIENT' } } },
  { name: '儿童+限制药（应警告）', data: { patient: { age: 10, gender: 'M' }, visit: { type: 'OUTPATIENT', id: 'V_DEMO_003' }, order: { drug_code: 'ABC001' } } }
]

</script>

<style scoped>
.json-pre { white-space: pre-wrap; word-break: break-all; }
</style>



