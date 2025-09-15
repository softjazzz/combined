<template>
  <BasicLayout>
    <div class="min-h-screen bg-gray-50 p-8">
      <!-- 页面标题 -->
      <div class="mb-8">
        <div class="bg-gradient-to-r from-indigo-500 via-purple-600 to-pink-600 text-white p-6 rounded-2xl shadow-lg">
          <div class="flex justify-between items-start">
            <div class="flex items-center gap-4">
              <div class="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center border border-white/20">
                <FileTextOutlined class="text-xl text-white" />
              </div>
              <div>
                <h1 class="text-2xl font-bold">{{ record?.name || '病历详情' }}</h1>
                <p class="text-purple-100">查看测试病历详细信息</p>
              </div>
            </div>
            <div class="flex space-x-3">
              <a-button @click="handleEdit" size="large" class="bg-white/10 border-white/30 text-white hover:bg-white/20">
                <EditOutlined /> 编辑
              </a-button>
              <a-button @click="handleAnalyze" type="primary" size="large" class="bg-white/20 border-white/30 text-white hover:bg-white/30">
                <ThunderboltOutlined /> 分析
              </a-button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="loading" class="text-center py-12">
        <a-spin size="large" />
        <p class="text-gray-500 mt-4">加载中...</p>
      </div>

      <div v-else-if="record" class="grid grid-cols-1 xl:grid-cols-3 gap-8">
        <!-- 主要内容 -->
        <div class="xl:col-span-2 space-y-6">
          <!-- 基本信息 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <UserOutlined class="text-blue-600" />
                患者信息
              </h3>
              <a-tag :color="getStatusColor(record.status)">
                {{ getStatusLabel(record.status) }}
              </a-tag>
            </div>
            
            <div class="grid grid-cols-2 gap-6">
              <div class="space-y-4">
                <div>
                  <label class="text-sm text-gray-500">患者姓名</label>
                  <p class="text-gray-800 font-medium">{{ record.patient_name }}</p>
                </div>
                <div>
                  <label class="text-sm text-gray-500">患者ID</label>
                  <p class="text-gray-800 font-medium">{{ record.patient_id }}</p>
                </div>
                <div>
                  <label class="text-sm text-gray-500">科室</label>
                  <p class="text-gray-800 font-medium">{{ record.department }}</p>
                </div>
                <div>
                  <label class="text-sm text-gray-500">记录类型</label>
                  <p class="text-gray-800 font-medium">{{ record.record_type }}</p>
                </div>
              </div>
              <div class="space-y-4">
                <div>
                  <label class="text-sm text-gray-500">疾病类型</label>
                  <p class="text-gray-800 font-medium">{{ record.disease_type }}</p>
                </div>
                <div>
                  <label class="text-sm text-gray-500">复杂度等级</label>
                  <p class="text-gray-800 font-medium">{{ record.complexity_level }}</p>
                </div>
                <div v-if="record.medical_insurance_type">
                  <label class="text-sm text-gray-500">医保类型</label>
                  <p class="text-gray-800 font-medium">{{ record.medical_insurance_type }}</p>
                </div>
                <div v-if="record.cost_amount">
                  <label class="text-sm text-gray-500">费用金额</label>
                  <p class="text-gray-800 font-medium">¥{{ record.cost_amount.toLocaleString() }}</p>
                </div>
              </div>
            </div>

            <div v-if="record.tags && record.tags.length > 0" class="mt-6">
              <label class="text-sm text-gray-500 block mb-2">标签</label>
              <div class="flex flex-wrap gap-2">
                <a-tag v-for="tag in record.tags" :key="tag" color="blue">{{ tag }}</a-tag>
              </div>
            </div>
          </div>

          <!-- 病历内容 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div class="flex items-center justify-between mb-6">
              <h3 class="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <FileTextOutlined class="text-green-600" />
                病历内容
              </h3>
              <a-button size="small" @click="copyContent">
                <CopyOutlined /> 复制内容
              </a-button>
            </div>
            
            <div class="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <pre class="whitespace-pre-wrap text-gray-800 text-sm leading-relaxed">{{ record.content }}</pre>
            </div>
          </div>

          <!-- 质控结果 -->
          <div v-if="record.qc_score" class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <h3 class="text-lg font-semibold text-gray-800 flex items-center gap-2 mb-6">
              <TrophyOutlined class="text-orange-600" />
              质控结果
            </h3>
            
            <div class="grid grid-cols-3 gap-6">
              <div class="text-center">
                <div class="text-3xl font-bold mb-2" :class="getScoreClass(record.qc_score)">
                  {{ record.qc_score }}分
                </div>
                <p class="text-gray-600 text-sm">质控评分</p>
              </div>
              <div v-if="record.expected_score" class="text-center">
                <div class="text-3xl font-bold text-blue-600 mb-2">{{ record.expected_score }}分</div>
                <p class="text-gray-600 text-sm">预期评分</p>
              </div>
              <div v-if="record.expected_grade" class="text-center">
                <div class="text-3xl font-bold text-purple-600 mb-2">{{ record.expected_grade }}</div>
                <p class="text-gray-600 text-sm">预期等级</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 侧边栏 -->
        <div class="space-y-6">
          <!-- 操作面板 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <h3 class="text-lg font-semibold text-gray-800 mb-4">操作</h3>
            <div class="space-y-3">
              <a-button block size="large" type="primary" @click="openOrderDrawer">
                <ThunderboltOutlined /> 开立医嘱并质控
              </a-button>
              <a-button block size="large" @click="handleEdit">
                <EditOutlined /> 编辑病历
              </a-button>
              <a-button block size="large" @click="handleAnalyze">
                <ThunderboltOutlined /> 质控分析
              </a-button>
              <a-button block size="large" @click="handleDuplicate">
                <CopyOutlined /> 复制病历
              </a-button>
              <a-button block size="large" @click="handleExport">
                <DownloadOutlined /> 导出数据
              </a-button>
              <a-button block size="large" danger @click="handleDelete">
                <DeleteOutlined /> 删除病历
              </a-button>
            </div>
          </div>

          <!-- 风险评估 -->
          <div v-if="record.violation_risk" class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <h3 class="text-lg font-semibold text-gray-800 mb-4">风险评估</h3>
            <div class="text-center">
              <div class="w-16 h-16 rounded-full mx-auto mb-3 flex items-center justify-center" :class="getRiskBgClass(record.violation_risk)">
                <WarningOutlined :class="getRiskTextClass(record.violation_risk)" class="text-2xl" />
              </div>
              <p class="font-semibold mb-2" :class="getRiskTextClass(record.violation_risk)">
                {{ getRiskLabel(record.violation_risk) }}
              </p>
              <p class="text-gray-600 text-sm">{{ getRiskDescription(record.violation_risk) }}</p>
            </div>
          </div>

          <!-- 创建信息 -->
          <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <h3 class="text-lg font-semibold text-gray-800 mb-4">创建信息</h3>
            <div class="space-y-3 text-sm">
              <div>
                <span class="text-gray-500">创建人：</span>
                <span class="text-gray-800">{{ record.created_by }}</span>
              </div>
              <div>
                <span class="text-gray-500">创建时间：</span>
                <span class="text-gray-800">{{ record.created_at }}</span>
              </div>
              <div>
                <span class="text-gray-500">更新时间：</span>
                <span class="text-gray-800">{{ record.updated_at }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧医嘱模拟抽屉 -->
    <a-drawer
      v-model:open="orderDrawerOpen"
      title="开立医嘱（模拟）"
      placement="right"
      :width="560"
      :maskClosable="false"
    >
      <div class="space-y-4">
        <a-alert type="info" show-icon message="在当前病历上下文下模拟提交药品医嘱，并实时获得医保质控提醒/拦截。" />

        <a-form layout="vertical">
          <a-row :gutter="12">
            <a-col :span="8">
              <a-form-item label="患者年龄">
                <a-input-number v-model:value="orderForm.patient.age" :min="0" style="width: 100%" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="患者性别">
                <a-select v-model:value="orderForm.patient.gender" :options="genderOptions" />
              </a-form-item>
            </a-col>
            <a-col :span="8">
              <a-form-item label="就诊方式">
                <a-select v-model:value="orderForm.visit.type" :options="visitTypeOptions" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="药品编码">
                <a-input v-model:value="orderForm.order.drug_code" placeholder="如 DEMO_DRUG_INPATIENT" />
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="药品名称">
                <a-input v-model:value="orderForm.order.drug_name" placeholder="可选" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-space>
            <a-button type="primary" :loading="submitting" @click="submitOrder">提交医嘱</a-button>
            <a-button @click="fillDemo('INPATIENT')">填充：住院专用药</a-button>
            <a-button @click="fillDemo('AGE')">填充：儿童限制药</a-button>
            <a-button @click="fillDemo('FEMALE')">填充：女性专用药</a-button>
          </a-space>
        </a-form>

        <a-divider />

        <div v-if="evaluation">
          <div class="flex items-center gap-2 mb-2">
            <span>决策：</span>
            <a-tag :color="severityColor(evaluation.severity)">{{ evaluation.severity }}</a-tag>
          </div>
          <div v-if="Array.isArray(hits) && hits.length">
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
          </div>

          <template v-if="evaluation.severity === 'warn'">
            <a-divider />
            <div>
              <div class="mb-2 text-gray-600">忽略理由（仅示例）</div>
              <a-select v-model:value="ignore.reason" :options="ignoreReasons" style="width: 100%" placeholder="选择忽略理由" />
              <a-textarea v-model:value="ignore.note" :rows="3" placeholder="备注（可选）" class="mt-2" />
              <div class="mt-3 text-right">
                <a-button type="primary" @click="confirmIgnore" :disabled="!firstViolationId">忽略并继续</a-button>
              </div>
            </div>
          </template>
        </div>
      </div>
    </a-drawer>
  </BasicLayout>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { message } from 'ant-design-vue'
import BasicLayout from '@/layouts/BasicLayout.vue'
import { functionsPost } from '@/services/functionsClient'
import { 
  FileTextOutlined, 
  EditOutlined, 
  ThunderboltOutlined,
  UserOutlined,
  CopyOutlined,
  TrophyOutlined,
  DownloadOutlined,
  DeleteOutlined,
  WarningOutlined
} from '@ant-design/icons-vue'

// 测试病历类型定义
interface TestMedicalRecord {
  id: string
  name: string
  patient_name: string
  patient_id: string
  department: string
  record_type: string
  disease_type: string
  complexity_level: string
  status: 'draft' | 'pending' | 'analyzing' | 'completed' | 'failed'
  qc_score?: number
  expected_grade?: string
  expected_score?: number
  content: string
  created_at: string
  updated_at: string
  created_by: string
  tags?: string[]
  medical_insurance_type?: string
  cost_amount?: number
  violation_risk?: 'low' | 'medium' | 'high'
}

const router = useRouter()
const route = useRoute()

const loading = ref(false)
const record = ref<TestMedicalRecord | null>(null)

// 下医嘱模拟相关状态
const orderDrawerOpen = ref(false)
const submitting = ref(false)
const hits = ref<any[]>([])
const evaluation = ref<{ severity: 'info'|'warn'|'block' } | null>(null)
const ignore = ref<{ reason?: string; note?: string }>({})
const ignoreReasons = [
  { label: '患者病情特殊', value: 'special_condition' },
  { label: '上级医师已同意', value: 'approved_by_senior' },
  { label: '与患者充分沟通', value: 'patient_informed' }
]
const genderOptions = [ { label: '男', value: 'M' }, { label: '女', value: 'F' } ]
const visitTypeOptions = [ { label: '门诊', value: 'OUTPATIENT' }, { label: '住院', value: 'INPATIENT' } ]
const orderForm = ref<any>({
  patient: { age: 45, gender: 'M' },
  visit: { id: '', type: 'INPATIENT' },
  order: { drug_code: 'DEMO_DRUG_INPATIENT', drug_name: '示例住院专用药', dosage: '', frequency: '' }
})

function severityColor(s?: string) {
  if (s === 'block') return 'red'
  if (s === 'warn') return 'orange'
  if (s === 'info') return 'blue'
  return 'default'
}

function openOrderDrawer() {
  if (!record.value) return
  const vtype = record.value.record_type?.includes('住院') ? 'INPATIENT' : 'OUTPATIENT'
  orderForm.value.visit = { id: record.value.id, type: vtype }
  orderDrawerOpen.value = true
}

function fillDemo(type: 'INPATIENT'|'AGE'|'FEMALE') {
  if (type === 'INPATIENT') {
    orderForm.value.order = { drug_code: 'DEMO_DRUG_INPATIENT', drug_name: '示例住院专用药' }
    orderForm.value.visit.type = 'OUTPATIENT'
  } else if (type === 'AGE') {
    orderForm.value.patient.age = 18
    orderForm.value.order = { drug_code: 'DEMO_DRUG_001', drug_name: '示例儿童药品A' }
  } else {
    orderForm.value.patient.gender = 'M'
    orderForm.value.order = { drug_code: 'DEMO_DRUG_FEMALE', drug_name: '示例女性专用药' }
  }
}

function buildContext() {
  return {
    patient: { age: Number(orderForm.value.patient.age) || 0, gender: orderForm.value.patient.gender },
    visit: { id: orderForm.value.visit.id || (record.value?.id ?? 'unknown'), type: orderForm.value.visit.type,
      department: { code: 'DEPT', name: record.value?.department || '' } },
    order: { drug_code: orderForm.value.order.drug_code, drug_name: orderForm.value.order.drug_name,
      dosage: orderForm.value.order.dosage, frequency: orderForm.value.order.frequency }
  }
}

async function submitOrder() {
  submitting.value = true
  hits.value = []
  evaluation.value = null
  try {
    const ctx = buildContext()
    const resp = await functionsPost('/evaluate-rule', { event: 'order.drug.submit', context: ctx, record: true })
    hits.value = Array.isArray(resp?.hits) ? resp.hits : []
    let sev: 'info'|'warn'|'block' = 'info'
    hits.value.forEach((h: any) => { if (h.severity === 'block') sev = 'block'; else if (h.severity === 'warn' && sev === 'info') sev = 'warn' })
    if (!hits.value.length) sev = 'info'
    evaluation.value = { severity: sev }
  } catch (e: any) {
    message.error(e?.message || '评估失败')
  } finally {
    submitting.value = false
  }
}

const firstViolationId = computed(() => hits.value?.[0]?.violationId || 0)

async function confirmIgnore() {
  try {
    if (!firstViolationId.value) return
    await functionsPost('/violations?action=ignore', { id: firstViolationId.value, reason: ignore.value.reason, note: ignore.value.note })
    message.success('忽略理由已记录')
  } catch (e: any) {
    message.error(e?.message || '忽略失败')
  }
}

// 方法
function handleEdit() {
  router.push(`/medical-records/${route.params.id}/edit`)
}

function handleAnalyze() {
  message.info('质控分析功能开发中...')
}

function handleDuplicate() {
  message.info('复制病历功能开发中...')
}

function handleExport() {
  message.info('导出数据功能开发中...')
}

function handleDelete() {
  message.info('删除病历功能开发中...')
}

async function copyContent() {
  if (record.value?.content) {
    try {
      await navigator.clipboard.writeText(record.value.content)
      message.success('内容已复制到剪贴板')
    } catch (error) {
      message.error('复制失败')
    }
  }
}

function getStatusColor(status: string) {
  const colors = {
    draft: 'default',
    pending: 'orange',
    analyzing: 'blue',
    completed: 'green',
    failed: 'red'
  }
  return colors[status as keyof typeof colors] || 'default'
}

function getStatusLabel(status: string) {
  const labels = {
    draft: '草稿',
    pending: '待审核',
    analyzing: '分析中',
    completed: '已完成',
    failed: '失败'
  }
  return labels[status as keyof typeof labels] || status
}

function getScoreClass(score: number) {
  if (score >= 90) return 'text-green-600'
  if (score >= 80) return 'text-blue-600'
  if (score >= 70) return 'text-orange-600'
  return 'text-red-600'
}

function getRiskLabel(risk: string) {
  const labels = {
    low: '低风险',
    medium: '中风险',
    high: '高风险'
  }
  return labels[risk as keyof typeof labels] || risk
}

function getRiskDescription(risk: string) {
  const descriptions = {
    low: '医保违规风险较低，建议正常处理',
    medium: '存在一定医保违规风险，需要关注',
    high: '医保违规风险较高，需要重点审核'
  }
  return descriptions[risk as keyof typeof descriptions] || ''
}

function getRiskBgClass(risk: string) {
  const classes = {
    low: 'bg-green-100',
    medium: 'bg-orange-100',
    high: 'bg-red-100'
  }
  return classes[risk as keyof typeof classes] || 'bg-gray-100'
}

function getRiskTextClass(risk: string) {
  const classes = {
    low: 'text-green-600',
    medium: 'text-orange-600',
    high: 'text-red-600'
  }
  return classes[risk as keyof typeof classes] || 'text-gray-600'
}

async function loadRecord() {
  loading.value = true
  try {
    // 模拟API调用
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    // 模拟数据
    record.value = {
      id: route.params.id as string,
      name: '张伟住院病历',
      patient_name: '张伟',
      patient_id: 'P001',
      department: '外二科',
      record_type: '住院记录',
      disease_type: '心血管疾病',
      complexity_level: '中等',
      status: 'completed',
      qc_score: 85,
      expected_grade: 'A',
      expected_score: 90,
      content: `患者张伟，男，45岁，因胸痛3天入院。

主诉：胸痛3天，加重1天。

现病史：患者3天前无明显诱因出现胸痛，位于胸骨后，呈压榨性疼痛，向左肩背部放射，持续时间约10-20分钟，休息后可缓解。1天前症状加重，疼痛持续时间延长，伴有出汗、恶心。

既往史：高血压病史5年，糖尿病病史3年，规律服药控制。

体格检查：
T 36.8℃，P 78次/分，R 18次/分，BP 150/90mmHg
心界不大，心率78次/分，律齐，各瓣膜听诊区未闻及病理性杂音。
双肺呼吸音清，未闻及干湿性啰音。

辅助检查：
心电图：V1-V4导联ST段压低0.1-0.2mV
心肌酶谱：CK-MB 25U/L（正常<25U/L），cTnI 0.8ng/ml（正常<0.04ng/ml）

诊断：
1. 急性冠脉综合征 不稳定性心绞痛
2. 高血压病 3级 极高危
3. 2型糖尿病

治疗方案：
1. 抗血小板聚集：阿司匹林100mg qd，氯吡格雷75mg qd
2. 抗凝治疗：低分子肝素钠4000IU q12h皮下注射
3. 他汀类药物：阿托伐他汀20mg qn
4. β受体阻滞剂：美托洛尔25mg bid
5. ACEI类药物：依那普利5mg bid
6. 血糖控制：胰岛素治疗
7. 完善冠脉造影检查`,
      created_at: '2025-05-02 16:25',
      updated_at: '2025-05-02 18:30',
      created_by: '质控医师',
      tags: ['心血管', '住院'],
      medical_insurance_type: '职工医保',
      cost_amount: 15680.50,
      violation_risk: 'low'
    }
  } catch (error) {
    message.error('加载病历数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadRecord()
})
</script>

<style scoped>
/* 自定义样式 */
</style>
