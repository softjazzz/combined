<template>
  <div class="create-rule-view">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <a-button type="text" @click="() => router.push('/demo/lx33')" class="back-btn">
          <template #icon><LeftOutlined /></template>
          返回规则列表
        </a-button>
        <div class="header-divider"></div>
        <h1 class="page-title">
          <RobotOutlined class="title-icon" />
          AI智能创建质控规则
        </h1>
      </div>
    </div>

    <!-- 引导提示 -->
    <a-alert
      type="info"
      show-icon
      closable
      class="intro-alert"
    >
      <template #message>
        <span><BulbOutlined /> 请用自然语言描述您的质控需求，AI 将自动生成完整的规则草案</span>
      </template>
      <template #description>
        示例：检查入院记录是否记录了患者的过敏史，包括药物过敏与食物过敏。如无过敏史需明确写明。<br />
        <a @click="showExamples = true">查看更多示例</a>
      </template>
    </a-alert>

    <!-- 主要内容区域 -->
    <div class="content-grid">
      <!-- 左侧：需求输入表单 -->
      <div class="form-panel">
        <a-card :bordered="false" class="input-card">
          <template #title>
            <span><EditOutlined /> 描述您的质控需求</span>
          </template>
          <a-form :model="formData" layout="vertical">
            <a-form-item
              label="需求描述"
              required
              :help="requirementHelp"
              :validate-status="requirementTooShort ? 'warning' : ''"
            >
              <a-textarea
                v-model:value="formData.requirement"
                :rows="8"
                :maxlength="500"
                show-count
                placeholder="例如：检查入院记录中是否记录患者药物过敏史和食物过敏史，如无过敏史需注明。"
                class="requirement-textarea"
              />
            </a-form-item>

            <a-row :gutter="12">
              <a-col :span="8">
                <a-form-item label="适用文书">
                  <a-select v-model:value="formData.documentType" size="large">
                    <a-select-option value="入院记录">入院记录</a-select-option>
                    <a-select-option value="首次病程记录">首次病程记录</a-select-option>
                    <a-select-option value="病程记录">病程记录</a-select-option>
                    <a-select-option value="手术记录">手术记录</a-select-option>
                    <a-select-option value="出院记录">出院记录</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="缺陷级别">
                  <a-select v-model:value="formData.defectLevel" size="large">
                    <a-select-option value="严重缺陷">严重缺陷</a-select-option>
                    <a-select-option value="一般缺陷">一般缺陷</a-select-option>
                    <a-select-option value="提示性缺陷">提示性缺陷</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
              <a-col :span="8">
                <a-form-item label="复杂度">
                  <a-select v-model:value="formData.complexity" size="large">
                    <a-select-option value="低复杂度">低复杂度</a-select-option>
                    <a-select-option value="中复杂度">中复杂度</a-select-option>
                    <a-select-option value="高复杂度">高复杂度</a-select-option>
                  </a-select>
                </a-form-item>
              </a-col>
            </a-row>

            <a-form-item>
              <a-space size="middle">
                <a-button
                  type="primary"
                  size="large"
                  :loading="generating"
                  :disabled="!canGenerate"
                  :title="requirementTooShort ? `需求描述至少需要 ${MIN_REQUIREMENT_LENGTH} 个字` : ''"
                  @click="handleGenerate"
                  class="generate-btn"
                >
                  <template #icon>
                    <ThunderboltOutlined />
                  </template>
                  AI智能生成
                </a-button>
                <a-button size="large" @click="showExamples = true">
                  查看示例需求
                </a-button>
              </a-space>
            </a-form-item>
          </a-form>
        </a-card>
      </div>

      <!-- 右侧：生成进度和规则预览 -->
      <div class="preview-panel">
        <!-- 生成进度提示 -->
        <a-card v-if="generating" :bordered="false" class="generating-card">
          <div class="generating-content">
            <a-spin size="large">
              <template #tip>
                <div class="generating-tip">{{ generatingTip }}</div>
              </template>
            </a-spin>
          </div>
        </a-card>

        <!-- 规则预览 -->
        <rule-preview-card
          v-if="generatedRule"
          class="rule-preview-container"
          :rule="generatedRule"
          @save="handleSave"
          @regenerate="handleRegenerate"
        />

        <!-- 空状态 -->
        <a-card v-if="!generating && !generatedRule" :bordered="false" class="empty-state-card">
          <a-empty
            description="填写需求描述后，点击 AI智能生成 按钮，系统将自动生成质控规则"
          >
            <template #image>
              <div class="empty-icon">
                <ThunderboltOutlined />
              </div>
            </template>
          </a-empty>
        </a-card>
      </div>
    </div>

    <!-- 示例需求弹窗 -->
    <examples-modal
      v-model:visible="showExamples"
      @select="handleSelectExample"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { message, Modal } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import {
  LeftOutlined,
  ThunderboltOutlined,
  RobotOutlined,
  BulbOutlined,
  EditOutlined
} from '@ant-design/icons-vue'
import RulePreviewCard from './components/RulePreviewCard.vue'
import ExamplesModal from './components/ExamplesModal.vue'

type GeneratedRule = Record<string, any>

type RuleParams = {
  requirement: string
  documentType: string
  defectLevel: string
  complexity: string
}

const router = useRouter()

const formData = ref<RuleParams>({
  requirement: '',
  documentType: '入院记录',
  defectLevel: '一般缺陷',
  complexity: '中复杂度'
})

const generating = ref(false)
const generatingTip = ref('')
const generatedRule = ref<GeneratedRule | null>(null)
const showExamples = ref(false)

const MIN_REQUIREMENT_LENGTH = 20
const requirementLength = computed(() => formData.value.requirement.trim().length)
const requirementTooShort = computed(() => requirementLength.value < MIN_REQUIREMENT_LENGTH)
const requirementHelp = computed(() => {
  if (requirementTooShort.value) {
    return `请至少输入 ${MIN_REQUIREMENT_LENGTH} 个字，更详细的需求描述有助于生成精准规则（当前 ${requirementLength.value} 个字）`
  }
  return '建议描述场景、触发条件和预期检查要点，以便生成更精准的规则草案'
})

const canGenerate = computed(() => !requirementTooShort.value)

const handleGenerate = async () => {
  if (!canGenerate.value || generating.value) return
  generating.value = true
  generatedRule.value = null

  const tips = [
    'AI正在理解您的需求...',
    '正在生成规则定义...',
    '正在构建质控提示词...',
    '正在生成病历示例...'
  ]

  let tipIndex = 0
  const tipInterval = setInterval(() => {
    if (tipIndex < tips.length) {
      generatingTip.value = tips[tipIndex]
      tipIndex++
    } else {
      // 循环显示最后一个提示
      tipIndex = tips.length - 1
      generatingTip.value = tips[tipIndex]
    }
  }, 800)

  try {
    const response = await fetch('/api/v1/demo/custom-rules/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        requirement: formData.value.requirement.trim(),
        applicable_documents: [formData.value.documentType],
        defect_level: formData.value.defectLevel,
        complexity: formData.value.complexity,
        category: formData.value.documentType
      })
    })

    clearInterval(tipInterval)

    const result = await response.json()
    if (!result.success) {
      throw new Error(result.error || '生成失败，请稍后重试')
    }

    generatedRule.value = result.data
    message.success('规则生成成功！')

    requestAnimationFrame(() => {
      const el = document.querySelector('.rule-preview-container')
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    })
  } catch (error: any) {
    clearInterval(tipInterval)
    console.error('生成规则失败:', error)
    message.error(error?.message || '规则生成失败，请稍后重试')
  } finally {
    generating.value = false
  }
}

const handleSave = async (rule: GeneratedRule) => {
  try {
    const response = await fetch('/api/v1/demo/custom-rules/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rule })
    })

    const result = await response.json()
    if (!result.success) {
      throw new Error(result.error || '保存失败')
    }

    message.success('规则已保存，现在可以在规则列表中查看')
    Modal.confirm({
      title: '规则已保存',
      content: '是否立即返回规则列表？',
      okText: '返回列表',
      cancelText: '停留此页',
      onOk: () => router.push('/demo/lx33')
    })
  } catch (error: any) {
    console.error('保存规则失败:', error)
    message.error(error?.message || '保存失败，请稍后重试')
  }
}

const handleRegenerate = () => {
  handleGenerate()
}

const handleSelectExample = (example: { content: string; params: Partial<RuleParams> }) => {
  formData.value.requirement = example.content
  if (example.params.documentType) {
    formData.value.documentType = example.params.documentType
  }
  if (example.params.defectLevel) {
    formData.value.defectLevel = example.params.defectLevel
  }
  if (example.params.complexity) {
    formData.value.complexity = example.params.complexity
  }
  showExamples.value = false
}
</script>

<style scoped lang="less">
.create-rule-view {
  min-height: 100vh;
  background: #f5f7fa;

  .page-header {
    background: #fff;
    padding: 16px 24px;
    margin-bottom: 24px;
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);

    .header-left {
      display: flex;
      align-items: center;
      gap: 16px;
    }

    .back-btn {
      font-size: 14px;
      color: #64748b;
      transition: all 0.2s;

      &:hover {
        color: #1890ff;
      }
    }

    .header-divider {
      width: 1px;
      height: 24px;
      background: #e2e8f0;
    }

    .page-title {
      margin: 0;
      font-size: 20px;
      font-weight: 600;
      color: #1e293b;
      display: flex;
      align-items: center;
      gap: 8px;

      .title-icon {
        font-size: 22px;
        color: #1890ff;
      }
    }
  }

  .intro-alert {
    margin: 0 24px 24px;
    border-radius: 8px;
    border: 1px solid #91d5ff;
  }

  .content-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    padding: 0 24px 24px;

    .form-panel,
    .preview-panel {
      min-height: 500px;
    }

    .input-card {
      height: 100%;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);

      :deep(.ant-card-head) {
        border-bottom: 2px solid #f1f5f9;
        font-size: 16px;
        font-weight: 600;
        background: #fafafa;
      }

      :deep(.ant-card-body) {
        padding: 24px;
      }

      :deep(.ant-form-item) {
        margin-bottom: 24px;
      }

      :deep(.ant-form-item-label > label) {
        font-size: 14px;
        font-weight: 500;
        color: #475569;
      }

      :deep(.ant-select) {
        .ant-select-selector {
          border-radius: 8px;
          border: 1px solid #e2e8f0;
          font-size: 14px;
          padding: 4px 12px;
          height: 44px;
          display: flex;
          align-items: center;
          transition: all 0.2s;

          &:hover {
            border-color: #94a3b8;
          }
        }

        &.ant-select-focused .ant-select-selector {
          border-color: #1890ff;
          box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.1);
        }
      }

      .requirement-textarea {
        font-size: 14px;
        line-height: 1.6;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        transition: all 0.2s;

        &:hover {
          border-color: #94a3b8;
        }

        &:focus {
          border-color: #1890ff;
          box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.1);
        }
      }

      .generate-btn {
        min-width: 140px;
        height: 44px;
        font-size: 15px;
        font-weight: 500;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(24, 144, 255, 0.2);

        &:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 4px 8px rgba(24, 144, 255, 0.3);
        }
      }

      :deep(.ant-btn-lg) {
        border-radius: 8px;
        height: 44px;
        font-size: 14px;
      }
    }

    .generating-card {
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      background: linear-gradient(135deg, #e6f7ff 0%, #f0f9ff 100%);
      border: 2px dashed #91d5ff;

      .generating-content {
        padding: 60px 0;
        text-align: center;

        .generating-tip {
          margin-top: 20px;
          font-size: 16px;
          font-weight: 500;
          color: #1890ff;
          animation: fadePulse 1.5s ease-in-out infinite;
        }
      }
    }

    .rule-preview-container {
      :deep(.ant-card) {
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      }
    }

    .empty-state-card {
      height: 100%;
      border-radius: 12px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
      display: flex;
      align-items: center;
      justify-content: center;

      :deep(.ant-card-body) {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 300px;
      }

      .empty-icon {
        font-size: 72px;
        color: #94a3b8;
        margin-bottom: 16px;

        :deep(.anticon) {
          font-size: 72px;
        }
      }

      :deep(.ant-empty-description) {
        color: #64748b;
        font-size: 14px;
        line-height: 1.6;
        max-width: 320px;
      }
    }
  }

  @media (max-width: 1400px) {
    .content-grid {
      grid-template-columns: 1fr;

      .preview-panel {
        min-height: auto;
      }
    }
  }
}

@keyframes fadePulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}
</style>
