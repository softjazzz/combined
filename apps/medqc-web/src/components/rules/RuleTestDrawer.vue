<template>
  <a-drawer
    :open="open"
    @close="emit('update:open', false)"
    width="720"
    title="规则评估测试"
    destroyOnClose
    class="rule-test-drawer"
  >
    <div v-if="rule" class="space-y-6">
      <!-- 规则信息卡片 -->
      <div class="bg-slate-50 rounded-lg p-4 border border-slate-100">
        <div class="flex items-center gap-2 mb-2">
          <a-tag color="blue" class="text-xs font-mono">{{ rule.rule_code }}</a-tag>
          <span class="text-sm font-semibold text-slate-800">{{ rule.name }}</span>
        </div>
        <p class="text-xs text-slate-500 m-0 leading-relaxed">{{ rule.description }}</p>
      </div>

      <!-- 病历文本输入 -->
      <div>
        <div class="flex items-center justify-between mb-2">
          <label class="text-sm font-semibold text-slate-700">
            <FileTextOutlined class="mr-1" />
            病历文本
          </label>
          <a-dropdown :trigger="['click']">
            <a-button size="small" type="text" class="text-slate-400">
              <template #icon><AppstoreOutlined /></template>
              示例文本
            </a-button>
            <template #overlay>
              <a-menu @click="handleSampleSelect">
                <a-menu-item key="admission">入院记录示例</a-menu-item>
                <a-menu-item key="progress">病程记录示例</a-menu-item>
                <a-menu-item key="discharge">出院记录示例</a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
        <a-textarea
          v-model:value="medicalText"
          placeholder="请粘贴或输入需要评估的病历文本..."
          :rows="10"
          :maxlength="5000"
          showCount
          :disabled="testing"
        />
      </div>

      <!-- 执行按钮 -->
      <div class="flex gap-3">
        <a-button
          type="primary"
          :loading="testing"
          :disabled="!medicalText.trim()"
          @click="executeTest"
          block
          size="large"
        >
          <template #icon><ThunderboltOutlined /></template>
          {{ testing ? '评估中...' : '开始评估' }}
        </a-button>
      </div>

      <!-- 评估结果 -->
      <div v-if="result" class="mt-4">
        <h3 class="text-sm font-semibold text-slate-700 mb-3 flex items-center">
          <ExperimentOutlined class="mr-2" />
          评估结果
        </h3>

        <!-- 合规状态 -->
        <div :class="['result-card', result.compliant ? 'result-pass' : 'result-fail']">
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
              <CheckCircleOutlined v-if="result.compliant" class="text-green-500 text-lg" />
              <CloseCircleOutlined v-else class="text-red-500 text-lg" />
              <span class="font-bold text-base">
                {{ result.compliant ? '合规' : '不合规' }}
              </span>
            </div>
            <div class="flex items-center gap-4 text-xs text-slate-400">
              <span>置信度: {{ (result.confidence * 100).toFixed(0) }}%</span>
              <span>耗时: {{ result.execution_time?.toFixed(2) || '-' }}s</span>
            </div>
          </div>

          <!-- 推理过程 -->
          <div v-if="result.reasoning" class="mb-3">
            <div class="text-xs font-semibold text-slate-500 mb-1">推理过程</div>
            <div class="text-sm text-slate-700 bg-white/60 rounded p-3 leading-relaxed">
              {{ result.reasoning }}
            </div>
          </div>

          <!-- 证据 -->
          <div v-if="result.evidence">
            <div class="text-xs font-semibold text-slate-500 mb-1">相关证据</div>
            <div class="text-sm text-slate-600 bg-white/60 rounded p-3 italic">
              "{{ result.evidence }}"
            </div>
          </div>

          <!-- 缺陷详情 -->
          <div v-if="result.defect_details && Object.keys(result.defect_details).length > 0" class="mt-3">
            <div class="text-xs font-semibold text-slate-500 mb-1">缺陷详情</div>
            <div class="bg-white/60 rounded p-3">
              <pre class="text-xs m-0 whitespace-pre-wrap">{{ JSON.stringify(result.defect_details, null, 2) }}</pre>
            </div>
          </div>
        </div>

        <!-- Token 使用 -->
        <div v-if="result.token_usage" class="text-xs text-slate-400 mt-2 text-right">
          Token: {{ result.token_usage.total || 0 }}
        </div>
      </div>

      <!-- 错误状态 -->
      <a-alert
        v-if="errorMsg"
        type="error"
        :message="errorMsg"
        show-icon
        closable
        @close="errorMsg = ''"
        class="mt-4"
      />
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  AppstoreOutlined,
  ThunderboltOutlined,
  ExperimentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons-vue'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

interface Props {
  open: boolean
  rule: Record<string, any> | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const medicalText = ref('')
const testing = ref(false)
const errorMsg = ref('')
const result = ref<Record<string, any> | null>(null)

// Reset when rule changes
watch(() => props.rule, () => {
  result.value = null
  errorMsg.value = ''
})

const SAMPLE_TEXTS: Record<string, string> = {
  admission: `患者张某，男，58岁，因"反复胸闷、气促2年，加重3天"于2024年1月15日入院。
主诉：反复胸闷、气促2年，加重3天。
现病史：患者2年前无明显诱因出现胸闷、气促，活动后加重，休息后可缓解。近3天来症状加重，伴有下肢水肿。
既往史：高血压病史10年，糖尿病病史5年，规律服药。
个人史：吸烟30年，20支/日，已戒烟2年。
体格检查：T 36.5℃，P 88次/分，R 22次/分，BP 145/90mmHg。
初步诊断：1. 慢性心力衰竭急性加重 2. 高血压病3级 3. 2型糖尿病`,
  progress: `2024年1月16日 首次病程记录
患者入院后完善相关检查，心电图示：窦性心律，ST段改变。
心脏彩超示：左室射血分数45%，左心室扩大。
BNP: 1250pg/ml。
目前诊断明确，予以利尿剂、ACEI、β受体阻滞剂等规范化抗心衰治疗。
患者目前一般情况尚可，胸闷症状较前好转。
治疗方案：
1. 呋塞米 20mg ivd qd
2. 培哚普利 4mg po qd
3. 美托洛尔 25mg po bid`,
  discharge: `出院记录
患者张某，男，58岁，住院号：20240115001
入院日期：2024年1月15日  出院日期：2024年1月25日
入院诊断：1. 慢性心力衰竭急性加重 2. 高血压病3级 3. 2型糖尿病
出院诊断：1. 慢性心力衰竭（NYHA III级） 2. 高血压病3级（很高危） 3. 2型糖尿病
治疗经过：入院后予以规范化抗心衰治疗，患者症状明显改善。
出院医嘱：
1. 继续口服药物治疗
2. 低盐低脂饮食
3. 适当活动
4. 2周后门诊复查`
}

const handleSampleSelect = (e: { key: string }) => {
  medicalText.value = SAMPLE_TEXTS[e.key] || ''
  message.success('已填入示例文本')
}

const executeTest = async () => {
  if (!props.rule || !medicalText.value.trim()) return

  testing.value = true
  errorMsg.value = ''
  result.value = null

  const ruleId = props.rule.id || props.rule.rule_id || props.rule.rule_code
  try {
    const resp = await fetch(`${API_BASE}/api/v1/semantic-rules/${encodeURIComponent(ruleId)}/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input_data: { content: medicalText.value }
      })
    })

    if (!resp.ok) {
      const errText = await resp.text()
      throw new Error(`HTTP ${resp.status}: ${errText}`)
    }

    const json = await resp.json()
    result.value = json.data?.result || json.result || json.data || json
  } catch (err) {
    errorMsg.value = `评估请求失败: ${err instanceof Error ? err.message : '未知错误'}`
  } finally {
    testing.value = false
  }
}
</script>

<style scoped>
.result-card {
  @apply rounded-lg p-4 border;
}

.result-pass {
  @apply bg-green-50 border-green-200;
}

.result-fail {
  @apply bg-red-50 border-red-200;
}
</style>
