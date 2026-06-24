<template>
  <a-drawer
    :open="visible"
    title="✨ AI 智能创建质控规则"
    :width="720"
    :destroy-on-close="true"
    class="ai-rule-creator-drawer"
    @close="handleClose"
  >
    <!-- 引导提示 -->
    <a-alert
      type="info"
      show-icon
      closable
      style="margin-bottom: 16px;"
    >
      <template #message>
        <span><BulbOutlined /> 用自然语言描述您的质控需求，AI 将自动生成完整的规则草案</span>
      </template>
      <template #description>
        示例：检查入院记录是否记录了患者的过敏史，包括药物过敏与食物过敏。<br>
        <a @click="showExamples = true">查看更多示例</a>
      </template>
    </a-alert>

    <!-- 需求输入表单 -->
    <a-card
      :bordered="false"
      class="input-card"
      size="small"
    >
      <template #title>
        <span><EditOutlined /> 描述您的质控需求</span>
      </template>
      <a-form
        :model="formData"
        layout="vertical"
      >
        <a-form-item
          label="需求描述"
          required
          :help="requirementHelp"
          :validate-status="requirementTooShort ? 'warning' : ''"
        >
          <a-textarea
            v-model:value="formData.requirement"
            :rows="5"
            :maxlength="500"
            show-count
            placeholder="例如：检查入院记录中是否记录患者药物过敏史和食物过敏史，如无过敏史需注明。"
          />
        </a-form-item>

        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="适用文书">
              <a-select
                v-model:value="formData.documentType"
                show-search
              >
                <a-select-opt-group label="病案首页">
                  <a-select-option value="病案首页">
                    病案首页
                  </a-select-option>
                  <a-select-option value="病案首页手术记录明细">
                    病案首页手术记录明细
                  </a-select-option>
                  <a-select-option value="病案首页费用明细">
                    病案首页费用明细
                  </a-select-option>
                  <a-select-option value="病案首页输血记录明细">
                    病案首页输血记录明细
                  </a-select-option>
                  <a-select-option value="病案首页重症监护记录明细">
                    病案首页重症监护记录明细
                  </a-select-option>
                  <a-select-option value="病案首页医院自定义明细">
                    病案首页医院自定义明细
                  </a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="入出院/死亡记录">
                  <a-select-option value="入院记录">
                    入院记录
                  </a-select-option>
                  <a-select-option value="出院记录">
                    出院记录
                  </a-select-option>
                  <a-select-option value="24小时入出院记录">
                    24小时入出院记录
                  </a-select-option>
                  <a-select-option value="死亡记录">
                    死亡记录
                  </a-select-option>
                  <a-select-option value="24小时入院死亡记录">
                    24小时入院死亡记录
                  </a-select-option>
                  <a-select-option value="死亡病例讨论记录">
                    死亡病例讨论记录
                  </a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="病程记录">
                  <a-select-option value="首次病程记录">
                    首次病程记录
                  </a-select-option>
                  <a-select-option value="日常病程记录">
                    日常病程记录
                  </a-select-option>
                  <a-select-option value="上级医师查房记录">
                    上级医师查房记录
                  </a-select-option>
                  <a-select-option value="术后首次病程记录">
                    术后首次病程记录
                  </a-select-option>
                  <a-select-option value="抢救记录">
                    抢救记录
                  </a-select-option>
                  <a-select-option value="阶段小结">
                    阶段小结
                  </a-select-option>
                  <a-select-option value="交班记录">
                    交班记录
                  </a-select-option>
                  <a-select-option value="接班记录">
                    接班记录
                  </a-select-option>
                  <a-select-option value="会诊记录">
                    会诊记录
                  </a-select-option>
                  <a-select-option value="疑难病例讨论记录">
                    疑难病例讨论记录
                  </a-select-option>
                  <a-select-option value="转出记录">
                    转出记录
                  </a-select-option>
                  <a-select-option value="转入记录">
                    转入记录
                  </a-select-option>
                  <a-select-option value="医患沟通记录">
                    医患沟通记录
                  </a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="手术相关">
                  <a-select-option value="手术申请">
                    手术申请
                  </a-select-option>
                  <a-select-option value="手术记录">
                    手术记录
                  </a-select-option>
                  <a-select-option value="手术风险评估">
                    手术风险评估
                  </a-select-option>
                  <a-select-option value="术前讨论">
                    术前讨论
                  </a-select-option>
                  <a-select-option value="术前小结">
                    术前小结
                  </a-select-option>
                  <a-select-option value="手术知情同意书">
                    手术知情同意书
                  </a-select-option>
                  <a-select-option value="手术安全核查记录">
                    手术安全核查记录
                  </a-select-option>
                  <a-select-option value="手术清点记录">
                    手术清点记录
                  </a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="麻醉相关">
                  <a-select-option value="麻醉术前访视记录">
                    麻醉术前访视记录
                  </a-select-option>
                  <a-select-option value="麻醉术后访视记录">
                    麻醉术后访视记录
                  </a-select-option>
                  <a-select-option value="麻醉记录">
                    麻醉记录
                  </a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="输血相关">
                  <a-select-option value="输血申请单">
                    输血申请单
                  </a-select-option>
                  <a-select-option value="输血记录">
                    输血记录
                  </a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="检验检查">
                  <a-select-option value="检验报告">
                    检验报告
                  </a-select-option>
                  <a-select-option value="检查报告">
                    检查报告
                  </a-select-option>
                  <a-select-option value="病理检查报告">
                    病理检查报告
                  </a-select-option>
                </a-select-opt-group>
                <a-select-opt-group label="护理与其他">
                  <a-select-option value="护理记录">
                    护理记录
                  </a-select-option>
                  <a-select-option value="危急值记录">
                    危急值记录
                  </a-select-option>
                  <a-select-option value="新生儿记录">
                    新生儿记录
                  </a-select-option>
                  <a-select-option value="门诊病历">
                    门诊病历
                  </a-select-option>
                  <a-select-option value="医保结算清单">
                    医保结算清单
                  </a-select-option>
                </a-select-opt-group>
              </a-select>
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="缺陷级别">
              <a-select v-model:value="formData.defectLevel">
                <a-select-option value="严重缺陷">
                  严重缺陷
                </a-select-option>
                <a-select-option value="一般缺陷">
                  一般缺陷
                </a-select-option>
                <a-select-option value="提示性缺陷">
                  提示性缺陷
                </a-select-option>
              </a-select>
            </a-form-item>
          </a-col>
        </a-row>

        <a-form-item>
          <a-space size="middle">
            <a-button
              type="primary"
              :loading="generating"
              :disabled="!canGenerate"
              @click="handleGenerate"
            >
              <template #icon>
                <ThunderboltOutlined />
              </template>
              AI 智能生成
            </a-button>
            <a-button @click="showExamples = true">
              查看示例需求
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 生成进度 -->
    <a-card
      v-if="generating"
      :bordered="false"
      class="generating-card"
      style="margin-top: 16px;"
    >
      <div class="generating-content">
        <a-spin size="large">
          <template #tip>
            <div class="generating-tip">
              {{ generatingTip }}
            </div>
          </template>
        </a-spin>
      </div>
    </a-card>

    <!-- 规则预览 -->
    <div
      v-if="generatedRule"
      style="margin-top: 16px;"
    >
      <RulePreviewCard
        :rule="generatedRule"
        @save="handleSave"
        @regenerate="handleRegenerate"
      />
    </div>

    <!-- 示例需求弹窗 -->
    <ExamplesModal
      v-model:visible="showExamples"
      @select="handleSelectExample"
    />
  </a-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  BulbOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'
import RulePreviewCard from '@/views/demo/components/RulePreviewCard.vue'
import ExamplesModal from '@/views/demo/components/ExamplesModal.vue'

type GeneratedRule = Record<string, any>
type RuleParams = {
  requirement: string
  documentType: string
  defectLevel: string
}

const props = defineProps<{
  visible: boolean
  defaultDocType?: string
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'saved', rule: GeneratedRule): void
}>()

// 表单数据
const formData = ref<RuleParams>({
  requirement: '',
  documentType: '入院记录',
  defectLevel: '一般缺陷',
})

// 如果父组件传了 defaultDocType，同步到表单
watch(
  () => props.defaultDocType,
  (val) => {
    if (val) formData.value.documentType = val
  },
  { immediate: true },
)

// 生成状态
const generating = ref(false)
const generatingTip = ref('')
const generatedRule = ref<GeneratedRule | null>(null)
const showExamples = ref(false)

// 验证
const MIN_REQUIREMENT_LENGTH = 20
const requirementLength = computed(() => formData.value.requirement.trim().length)
const requirementTooShort = computed(() => requirementLength.value < MIN_REQUIREMENT_LENGTH)
const requirementHelp = computed(() => {
  if (requirementTooShort.value) {
    return `请至少输入 ${MIN_REQUIREMENT_LENGTH} 个字（当前 ${requirementLength.value} 个字）`
  }
  return '建议描述场景、触发条件和预期检查要点'
})
const canGenerate = computed(() => !requirementTooShort.value)

// 关闭抽屉
const handleClose = () => {
  emit('update:visible', false)
}

// 打开时重置状态
watch(
  () => props.visible,
  (open) => {
    if (open) {
      generatedRule.value = null
      generating.value = false
    }
  },
)

// 生成规则
const handleGenerate = async () => {
  if (!canGenerate.value || generating.value) return
  generating.value = true
  generatedRule.value = null

  const tips = [
    'AI 正在理解您的需求...',
    '正在生成规则定义...',
    '正在构建质控提示词...',
    '正在生成病历示例...',
  ]

  let tipIndex = 0
  const tipInterval = setInterval(() => {
    generatingTip.value = tips[Math.min(tipIndex, tips.length - 1)]
    tipIndex++
  }, 800)

  try {
    const response = await fetch('/api/v1/demo/custom-rules/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requirement: formData.value.requirement.trim(),
        applicable_documents: [formData.value.documentType],
        defect_level: formData.value.defectLevel,
        complexity: '中复杂度',
        category: formData.value.documentType,
      }),
    })

    clearInterval(tipInterval)

    const result = await response.json()
    if (!result.success) {
      throw new Error(result.error || '生成失败，请稍后重试')
    }

    generatedRule.value = result.data
    message.success('规则生成成功！')
  } catch (error: any) {
    clearInterval(tipInterval)
    console.error('生成规则失败:', error)
    message.error(error?.message || '规则生成失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

// 保存规则
const handleSave = async (rule: GeneratedRule) => {
  try {
    const response = await fetch('/api/v1/demo/custom-rules/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule }),
    })

    const result = await response.json()
    if (!result.success) {
      throw new Error(result.error || '保存失败')
    }

    message.success('规则已保存到规则库')
    emit('saved', rule)
    emit('update:visible', false)
  } catch (error: any) {
    console.error('保存规则失败:', error)
    message.error(error?.message || '保存失败，请稍后重试')
  }
}

// 重新生成
const handleRegenerate = () => {
  handleGenerate()
}

// 选择示例
const handleSelectExample = (example: { content: string; params: Partial<RuleParams> }) => {
  formData.value.requirement = example.content
  if (example.params.documentType) formData.value.documentType = example.params.documentType
  if (example.params.defectLevel) formData.value.defectLevel = example.params.defectLevel
  showExamples.value = false
}
</script>

<style scoped>
.input-card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.input-card :deep(.ant-card-head) {
  border-bottom: 1px solid #f0f0f0;
  font-weight: 600;
  background: #fafbfc;
  min-height: 40px;
}

.generating-card {
  border-radius: 8px;
  background: linear-gradient(135deg, #e6f7ff 0%, #f0f9ff 100%);
  border: 2px dashed #91d5ff;
}

.generating-content {
  padding: 40px 0;
  text-align: center;
}

.generating-tip {
  margin-top: 16px;
  font-size: 15px;
  font-weight: 500;
  color: #1890ff;
  animation: fadePulse 1.5s ease-in-out infinite;
}

@keyframes fadePulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
