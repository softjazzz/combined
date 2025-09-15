<template>
  <BasicLayout>
    <div class="p-6 md:p-8 bg-gradient-to-b from-white via-sky-50/30 to-teal-50/10 min-h-screen">
      <h3 class="flex items-center gap-2 text-2xl font-bold tracking-tight text-slate-800 mb-6">
        <span class="inline-block w-2.5 h-2.5 rounded-full bg-teal-500"></span>
        医师开方质控模拟（重构版）
      </h3>
      <a-row :gutter="12">
        <!-- 左侧：患者/就诊信息 -->
        <a-col :xs="24" :md="8">
          <a-card title="患者与就诊信息" size="small" :loading="evaluating" class="card-elevated">
            <a-form layout="vertical">
              <a-form-item label="载入测试病历">
                <a-select
                  v-model:value="selectedSample"
                  :options="samples"
                  :loading="samplesLoading"
                  allow-clear
                  placeholder="选择示例病历"
                  @change="onSelectSample"
                />
              </a-form-item>

              <!-- 显示当前选中的测试病历信息 -->
              <div v-if="selectedRecord" class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div class="text-sm font-medium text-blue-800 mb-2">当前测试病历信息</div>
                <div class="text-xs text-blue-600 space-y-1">
                  <div><span class="font-medium">患者:</span> {{ selectedRecord.patient.name }} ({{ selectedRecord.patient.age }}岁, {{ selectedRecord.patient.gender }})</div>
                  <div><span class="font-medium">医保:</span> {{ selectedRecord.patient.insurance_type }} ({{ selectedRecord.patient.insurance_number }})</div>
                  <div><span class="font-medium">科室:</span> {{ selectedRecord.visit.department }} - {{ selectedRecord.visit.visit_type }}</div>
                  <div><span class="font-medium">诊断:</span> {{ selectedRecord.diagnoses[0]?.diagnosis_name || '无' }}</div>
                  <div><span class="font-medium">测试场景:</span> {{ selectedRecord.test_scenario.name }}</div>
                  <div><span class="font-medium">预期结果:</span>
                    <a-tag :color="selectedRecord.test_scenario.expected_result === 'block' ? 'red' : selectedRecord.test_scenario.expected_result === 'warn' ? 'orange' : 'green'">
                      {{ selectedRecord.test_scenario.expected_result }}
                    </a-tag>
                  </div>
                </div>
              </div>

              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item label="年龄">
                    <a-input-number v-model:value="form.patient.age" :min="0" style="width:100%" @change="onFormChanged" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="性别">
                    <a-select v-model:value="form.patient.gender" :options="genderOptions" @change="onFormChanged" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item label="医保类型">
                    <a-select v-model:value="form.patient.insurance_type" :options="insuranceOptions" allow-clear @change="onFormChanged" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="科室">
                    <a-select v-model:value="form.visit.department" :options="departmentOptions" allow-clear show-search @change="onFormChanged" />
                  </a-form-item>
                </a-col>
              </a-row>
              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item label="就诊方式">
                    <a-select v-model:value="form.visit.type" :options="visitTypeOptions" @change="onFormChanged" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="就诊ID">
                    <a-input v-model:value="form.visit.id" placeholder="V_DEMO_001" @change="onFormChanged" />
                  </a-form-item>
                </a-col>
              </a-row>
            </a-form>
          </a-card>
        </a-col>

        <!-- 中间：医嘱录入 -->
        <a-col :xs="24" :md="10">
          <a-card title="医嘱录入（多药）" size="small" class="card-elevated">
            <a-form layout="vertical">
              <a-row :gutter="8">
                <a-col :span="12">
                  <a-form-item label="主诊断编码">
                    <a-input v-model:value="form.diagnosis.main.code" placeholder="如 D001" @change="onFormChanged" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="次要诊断编码">
                    <a-select v-model:value="form.diagnosis.secondary" mode="tags" :token-separators="[',',' ']" placeholder="输入并回车添加" @change="onFormChanged" />
                  </a-form-item>
                </a-col>
              </a-row>

              <a-divider>用药明细</a-divider>

              <div v-for="(ord, idx) in form.orders" :key="idx" class="mb-3">
                <a-row :gutter="8" align="middle">
                  <a-col :span="10">
                    <a-form-item :label="`药品名称 #${idx+1}`">
                      <a-select
                        v-model:value="ord.drug.name"
                        placeholder="请选择药品名称"
                        show-search
                        :filter-option="filterDrugOption"
                        @change="onDrugNameChange(idx, $event)"
                        allow-clear
                      >
                        <a-select-option
                          v-for="drug in drugOptions"
                          :key="drug.code"
                          :value="drug.name"
                          :title="drug.description"
                        >
                          <div>
                            <div>{{ drug.name }}</div>
                            <div class="text-xs text-gray-500">{{ drug.category }}</div>
                          </div>
                        </a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="4">
                    <a-form-item label="剂量">
                      <a-input-number v-model:value="ord.dose" :min="0" style="width:100%" @change="onFormChanged" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="4">
                    <a-form-item label="频次">
                      <a-input v-model:value="ord.frequency" placeholder="qd/bid/tid" @change="onFormChanged" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="4">
                    <a-form-item label="用法">
                      <a-input v-model:value="ord.route" placeholder="po/iv" @change="onFormChanged" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="2" class="text-right">
                    <a-button danger @click="removeOrder(idx)" :disabled="form.orders.length<=1" class="btn-danger-soft">删除</a-button>
                  </a-col>
                </a-row>
              </div>

              <a-space>
                <a-button @click="addOrder" class="btn-soft">新增药品</a-button>
                <a-button type="primary" :loading="evaluating" @click="evaluateNow" class="btn-primary-soft">实时评估</a-button>
                <a-button @click="reset" class="btn-soft">重置</a-button>
              </a-space>
            </a-form>
          </a-card>
        </a-col>

        <!-- 右侧：质控结果 -->
        <a-col :xs="24" :md="6">
          <a-card title="质控结果" size="small" class="card-elevated sticky-card">
            <a-tabs v-model:activeKey="rightTab" class="custom-tabs">
              <a-tab-pane key="results" tab="结果">
                <div class="mb-2">
                  <a-tag :color="severityColor(overall.severity)" :class="['chip', severityTone(overall.severity)]">{{ overall.severity || 'info' }}</a-tag>
                  <span class="text-gray-500 ml-2" v-if="overall.time">{{ overall.time.toFixed(0) }} ms</span>
                </div>
                <a-alert v-if="overall.severity==='info' && !hits.length" message="未发现问题，可继续" type="info" show-icon />
                <a-list v-else :data-source="hits" bordered>
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <div class="w-full">
                        <a-space size="small">
                          <a-tag :color="severityColor(item.severity)" :class="['chip', severityTone(item.severity)]">{{ item.severity }}</a-tag>
                          <a-tag class="chip chip-neutral">{{ item._orderIndex != null ? `#${item._orderIndex+1} ${item._drug || ''}` : '单药' }}</a-tag>
                          <a-tag v-if="item.rule_code" class="chip chip-neutral font-mono">{{ item.rule_code }}</a-tag>
                        </a-space>
                        <div class="mt-1 text-sm font-medium text-slate-800">{{ ruleTitle(item) }}</div>
                        <div v-if="Array.isArray(item.messages) && item.messages.length" class="mt-2">
                          <a-alert v-for="(m,i) in ruleMessages(item)" :key="i" :message="m" :type="item.severity==='block'?'error': item.severity==='warn'?'warning':'info'" show-icon class="mb-2" />
                        </div>
                      </div>
                    </a-list-item>
                  </template>
                </a-list>

                <div v-if="overall.severity==='warn' && hits.length" class="mt-3">
                  <a-alert type="warning" message="存在警告，医生可确认忽略后继续" show-icon />
                  <a-form layout="vertical" class="mt-2">
                    <a-row :gutter="8">
                      <a-col :span="12">
                        <a-form-item label="忽略理由">
                          <a-select v-model:value="ignore.reason" :options="ignoreReasons" placeholder="选择忽略理由" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="备注">
                          <a-input v-model:value="ignore.note" placeholder="可选：补充说明" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                    <a-button type="primary" danger :disabled="!ignore.reason" @click="confirmIgnore" class="btn-danger-soft">确认忽略本次风险</a-button>
                  </a-form>
                </div>

                <a-divider />
                <div>
                  <div class="text-xs text-gray-500 mb-1">上下文快照</div>
                  <pre class="json-pre bg-slate-50 border border-slate-200 rounded-lg p-3 text-xs leading-relaxed">{{ pretty(form) }}</pre>
                </div>
              </a-tab-pane>
              <a-tab-pane key="logs" tab="操作日志">
                <a-space style="margin-bottom:8px">
                  <a-button size="small" @click="clearLogs">清空日志</a-button>
                </a-space>

                <a-list :data-source="logs" bordered class="timeline">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <div class="w-full">
                        <a-space>
                          <span class="font-mono text-xs text-gray-500">{{ item.time }}</span>
                          <a-tag v-if="item.type==='ignore'" color="gold">忽略</a-tag>
                          <a-tag v-else color="blue">评估</a-tag>
                          <a-tag v-if="item.severity" :color="severityColor(item.severity)">{{ item.severity }}</a-tag>
                        </a-space>
                        <div v-if="item.message" class="mt-1 text-gray-700 text-sm">{{ item.message }}</div>
                      </div>
                    </a-list-item>
                  </template>
                </a-list>
              </a-tab-pane>
            </a-tabs>
          </a-card>
        </a-col>
      </a-row>
    </div>
  </BasicLayout>
</template>

<script setup lang="ts">
import BasicLayout from '@/layouts/BasicLayout.vue'
import { ref, watch, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import ApiService from '@/services/apiService'
import { DEPARTMENTS, INSURANCE_TYPES } from '@/types/medical-records'
import testMedicalRecordsService, { type SampleOption, type YibaoTestRecord } from '@/services/testMedicalRecordsService'
import { DRUG_MAPPING, getDrugCodeByName, getDrugNameByCode, type DrugInfo } from '@/data/drugMapping'

const genderOptions = [ { label: '男', value: 'M' }, { label: '女', value: 'F' }, { label: '未知', value: 'U' } ]
const visitTypeOptions = [ { label: '门诊', value: 'OUTPATIENT' }, { label: '住院', value: 'INPATIENT' } ]
const insuranceOptions = INSURANCE_TYPES
const departmentOptions = DEPARTMENTS.map(d => ({ label: d, value: d }))
const drugOptions = ref<DrugInfo[]>(DRUG_MAPPING)

const form = ref<any>({
  patient: { age: 18, gender: 'F', insurance_type: 'basic' },
  visit: { type: 'OUTPATIENT', id: 'V_DEMO_001', department: '' },
  diagnosis: { main: { code: '' }, secondary: [] as string[] },
  orders: [
    { drug: { name: '住院专用药品', code: 'DEMO_DRUG_INPATIENT' }, dose: null, frequency: '', route: '' }
  ]
})

const evaluating = ref(false)
const overall = ref<{ severity: 'info'|'warn'|'block'|''; time?: number }>({ severity: '' })
const hits = ref<Array<{ severity: string; rule_code: string; rule_name: string; messages: string[]; _orderIndex?: number; _drug?: string }>>([])

function severityColor(s?: string) { if (s==='block') return 'red'; if (s==='warn') return 'orange'; if (s==='info') return 'blue'; return 'default' }
function severityTone(s?: string){
  if (s === 'block') return 'bg-rose-50 text-rose-700 border border-rose-200';
  if (s === 'warn')  return 'bg-amber-50 text-amber-700 border border-amber-200';
  return 'bg-sky-50 text-sky-700 border border-sky-200';
}

function isCodeLike(s?: string): boolean {
  if (!s) return true
  const t = String(s).trim()
  // 纯大写字母/数字/下划线，且长度较长，视为编码
  return /^[A-Z0-9_\-]{6,}$/.test(t)
}
function ruleTitle(item: any): string {
  const name = (item?.rule_name || '').trim()
  if (name && !isCodeLike(name)) return name
  const msg = Array.isArray(item?.messages) && item.messages[0] ? String(item.messages[0]).trim() : ''
  return msg || (item?.rule_code || '')
}
function ruleMessages(item: any): string[] {
  const title = ruleTitle(item)
  const arr = Array.isArray(item?.messages) ? item.messages : []
  return arr.filter((m: any) => String(m).trim() !== title)
}


function pretty(v:any){ try{return JSON.stringify(v,null,2)}catch{return String(v)} }

function debounce<T extends (...args:any[])=>any>(fn:T, wait=300){ let t:any; return (...args:any[])=>{ clearTimeout(t); t=setTimeout(()=>fn(...args), wait) } }

const evaluateDebounced = debounce(evaluateNow, 300)
function onFormChanged(){ evaluateDebounced() }

let abortCtrl: AbortController | null = null
function maxSeverity(a: string, b: string){ if (a==='block'||b==='block') return 'block'; if (a==='warn'||b==='warn') return 'warn'; return 'info' }

async function evaluateNow(){
  if (abortCtrl) { abortCtrl.abort() }
  abortCtrl = new AbortController()
  evaluating.value = true
  try{
    const base = { patient: form.value.patient, visit: form.value.visit, diagnosis: form.value.diagnosis }
    const orders = Array.isArray(form.value.orders) ? form.value.orders : []

    // 确保所有订单都有正确的药品编码
    const processedOrders = orders.map((order: any) => {
      const processedOrder = { ...order }
      // 如果有药品名称但没有编码，尝试获取编码
      if (order.drug?.name && !order.drug?.code) {
        const drugCode = getDrugCodeByName(order.drug.name)
        if (drugCode) {
          processedOrder.drug = { ...order.drug, code: drugCode }
        }
      }
      return processedOrder
    })

    if (processedOrders.length <= 1){
      const order = processedOrders[0] || { drug: { code: '' }, dose: null, frequency: '', route: '' }
      const payload = { event_type: 'order.drug.submit', context: { ...base, order } }
      const res = await ApiService.post('/api/engine/evaluate', payload, { signal: abortCtrl.signal })
      const decision = res?.decision || 'pass'
      overall.value.severity = decision === 'block' ? 'block' : decision === 'warn' ? 'warn' : 'info'
      overall.value.time = res?.execution_time_ms || 0
      hits.value = Array.isArray(res?.hits) ? res.hits.map((h:any)=>({
        severity: h.severity, rule_code: h.rule_code, rule_name: h.rule_name, messages: h.messages || [],
        _orderIndex: 0, _drug: order?.drug?.code
      })) : []
    } else {
      const contexts = processedOrders.map((order:any)=>({ ...base, order }))
      const res = await ApiService.post('/api/engine/batch-evaluate', { event_type: 'order.drug.submit', contexts }, { signal: abortCtrl.signal })
      let sev: 'info'|'warn'|'block' = 'info'
      if (Array.isArray(res?.results)){
        res.results.forEach((r:any)=>{ const d = r?.decision; sev = maxSeverity(sev, d==='block'?'block': d==='warn'?'warn':'info') })
      }
      overall.value.severity = sev
      overall.value.time = res?.total_execution_time_ms || 0
      hits.value = Array.isArray(res?.results) ? res.results.flatMap((r:any, idx:number)=>
        (Array.isArray(r.hits)? r.hits: []).map((h:any)=>({
          severity: h.severity, rule_code: h.rule_code, rule_name: h.rule_name, messages: h.messages || [],
          _orderIndex: idx, _drug: processedOrders[idx]?.drug?.code
        }))
      ) : []
    }
  }catch(e:any){
    if (e?.name !== 'CanceledError' && e?.message !== 'canceled') {
      message.error(e?.message || '评估失败')
    }

  }finally{ evaluating.value = false }
}


const rightTab = ref<'results'|'logs'>('results')

// 忽略交互与日志
const ignoreReasons = [
  { label: '临床必要性', value: 'clinical_necessity' },
  { label: '已与患者沟通', value: 'communicated' },
  { label: '其他', value: 'other' }
]
const ignore = ref<{ reason?: string; note?: string }>({})
const logs = ref<Array<{ time: string; type: 'evaluate'|'ignore'; severity?: string; message?: string }>>([])
function addLog(entry: { type: 'evaluate'|'ignore'; severity?: string; message?: string }){
  logs.value.unshift({ time: new Date().toLocaleString(), ...entry })
}
function confirmIgnore(){
  addLog({ type: 'ignore', severity: overall.value.severity || 'info', message: `理由：${ignore.value.reason || ''}；备注：${ignore.value.note || ''}` })
  message.success('已记录忽略理由，模拟继续开立')
  ignore.value = {}
}
function clearLogs(){ logs.value = [] }

// 测试病历样例载入 - 使用Yibao项目的50条测试病历数据
const samples = ref<SampleOption[]>([])
const samplesLoading = ref(false)

// 加载测试病历选项
const loadSampleOptions = async () => {
  samplesLoading.value = true
  try {
    const options = await testMedicalRecordsService.getSampleOptions()
    // 添加原有的示例数据作为备选
    const originalSamples = [
      { label: '样例A：门诊 + 住院药', value: 's1', record: null },
      { label: '样例B：儿科门诊 + 常规药', value: 's2', record: null }
    ]
    samples.value = [...originalSamples, ...options]
  } catch (error) {
    console.error('加载测试病历选项失败:', error)
    message.error('加载测试病历选项失败')
  } finally {
    samplesLoading.value = false
  }
}

const sampleDataByKey: Record<string, any> = {
  s1: {
    patient: { age: 45, gender: 'F', insurance_type: 'basic' },
    visit: { type: 'OUTPATIENT', id: 'V_S1', department: '内科' },
    diagnosis: { main: { code: 'D001' }, secondary: ['D002'] },
    orders: [ { drug: { code: 'DEMO_DRUG_INPATIENT' }, dose: 1, frequency: 'qd', route: 'po' } ]
  },
  s2: {
    patient: { age: 10, gender: 'M', insurance_type: 'basic' },
    visit: { type: 'OUTPATIENT', id: 'V_S2', department: '儿科' },
    diagnosis: { main: { code: 'J06.9' }, secondary: [] },
    orders: [ { drug: { code: 'ABC001' }, dose: 1, frequency: 'bid', route: 'po' } ]
  }
}
const selectedSample = ref<string | null>(null)
const selectedRecord = ref<YibaoTestRecord | null>(null)

async function onSelectSample(v: string){
  // 首先检查是否是原有的示例数据
  const originalData = sampleDataByKey[v]
  if (originalData) {
    form.value = JSON.parse(JSON.stringify(originalData))
    selectedRecord.value = null
    overall.value = { severity: '' }
    hits.value = []
    evaluateDebounced()
    return
  }

  try {
    // 处理测试病历数据
    const record = await testMedicalRecordsService.getRecordById(v)
    if (!record) {
      message.error('未找到对应的测试病历数据')
      return
    }

    // 转换数据格式
    const convertedData = testMedicalRecordsService.convertToFormData(record)
    form.value = JSON.parse(JSON.stringify(convertedData))
    selectedRecord.value = record
    overall.value = { severity: '' }
    hits.value = []

    // 显示加载成功的消息
    message.success(`已加载测试病历：${record.patient.name} - ${record.test_scenario.name}`)

    evaluateDebounced()
  } catch (error) {
    console.error('转换测试病历数据失败:', error)
    message.error('加载测试病历数据失败')
  }
}

function reset(){
  form.value = {
    patient: { age: 18, gender: 'F', insurance_type: 'basic' },
    visit: { type: 'OUTPATIENT', id: 'V_DEMO_001', department: '' },
    diagnosis: { main: { code: '' }, secondary: [] },
    orders: [ { drug: { code: 'DEMO_DRUG_INPATIENT' }, dose: null, frequency: '', route: '' } ]
  }
  overall.value = { severity: '' }
  hits.value = []
}

// 药品名称变化处理
function onDrugNameChange(orderIndex: number, drugName: string) {
  if (!Array.isArray(form.value.orders)) return

  const order = form.value.orders[orderIndex]
  if (!order) return

  // 根据药品名称获取对应的编码
  const drugCode = getDrugCodeByName(drugName)

  order.drug.name = drugName
  order.drug.code = drugCode || ''

  onFormChanged()
}

// 药品选项过滤
function filterDrugOption(input: string, option: any) {
  const drugName = option.value || ''
  const drugInfo = DRUG_MAPPING.find(d => d.name === drugName)

  if (!input) return true

  const searchText = input.toLowerCase()
  return (
    drugName.toLowerCase().includes(searchText) ||
    drugInfo?.category.toLowerCase().includes(searchText) ||
    drugInfo?.description?.toLowerCase().includes(searchText)
  )
}

function addOrder(){
  if (!Array.isArray(form.value.orders)) form.value.orders = []
  form.value.orders.push({ drug: { name: '', code: '' }, dose: null, frequency: '', route: '' })
}
function removeOrder(index: number){
  if (!Array.isArray(form.value.orders)) return
  form.value.orders.splice(index, 1)
  evaluateDebounced()
}

// 初始化时评估一次 + 深度监听
watch(form, () => evaluateDebounced(), { deep: true, immediate: true })

// 组件挂载时加载测试病历选项
onMounted(() => {
  loadSampleOptions()
})
</script>

<style scoped>
.json-pre { white-space: pre-wrap; word-break: break-all; max-height: 220px; overflow: auto; }

/* Cards */
.card-elevated { @apply rounded-xl border border-slate-200 bg-white/90 shadow-sm hover:shadow-md transition-shadow; }
.card-elevated :deep(.ant-card-head) { @apply bg-gradient-to-r from-sky-50 to-teal-50/20 border-b border-slate-200 rounded-t-xl; }
.sticky-card { position: sticky; top: 1.5rem; }

/* Tabs accent */
.custom-tabs :deep(.ant-tabs-ink-bar) { @apply bg-teal-500; }
.custom-tabs :deep(.ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn) { @apply text-teal-600; }
.custom-tabs :deep(.ant-tabs-tab:hover .ant-tabs-tab-btn) { @apply text-teal-600; }

/* Form labels and controls */
:deep(.ant-form-item-label > label) { @apply text-slate-600 text-[13px] font-medium; }
:deep(.ant-input), :deep(.ant-select-selector), :deep(.ant-input-number), :deep(.ant-input-number-input), :deep(.ant-picker) { @apply rounded-lg; }
:deep(.ant-input), :deep(.ant-input-number), :deep(.ant-input-number-input) { @apply border-slate-300; }
:deep(.ant-input:hover), :deep(.ant-select-selector:hover), :deep(.ant-input-number:hover) { @apply border-sky-400; }
:deep(.ant-input:focus), :deep(.ant-input-focused .ant-select-selector), :deep(.ant-select-focused .ant-select-selector), :deep(.ant-input-number-focused) { @apply border-sky-500 ring-2 ring-sky-100; }

/* Buttons */
.btn-soft { @apply !rounded-lg !h-9 !px-4 shadow-sm hover:shadow-md; }
.btn-primary-soft { @apply !rounded-lg !h-9 !px-4 shadow-sm hover:shadow-md bg-teal-600 hover:bg-teal-700 border-none; }
.btn-danger-soft { @apply !rounded-lg !h-9 !px-4 shadow-sm hover:shadow-md; }

/* Chips */
.chip { @apply !rounded-md !px-2 !py-0.5 !text-xs; }
.chip-neutral { @apply bg-slate-50 text-slate-600 border border-slate-200; }

/* Timeline style for logs */
.timeline :deep(.ant-list-items) { @apply relative; }
.timeline :deep(.ant-list-item) { @apply relative pl-6 border-none; }
.timeline :deep(.ant-list-item)::before { content: ''; @apply absolute left-[9px] top-0 bottom-0 border-l border-slate-200; }
.timeline :deep(.ant-list-item)::after { content: ''; @apply absolute left-1 top-2 w-2 h-2 rounded-full bg-teal-500; }
</style>
