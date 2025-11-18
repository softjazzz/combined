<template>
  <a-modal
    v-model:open="isVisible"
    title="评估结果反馈"
    width="900px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleClose"
    :body-style="{ padding: '24px' }"
  >
    <div class="feedback-modal" v-if="evaluationResult">
      <!-- 评估结果信息 -->
      <a-card class="result-info-card" :bordered="false">
        <template #title>
          <div class="card-header">
            <FileTextOutlined class="card-icon" />
            <span>评估结果</span>
          </div>
        </template>

        <div class="result-content">
          <!-- 基本信息 -->
          <div class="info-row">
            <div class="info-item">
              <span class="info-label">规则编号</span>
              <a-tag color="blue" class="info-tag">{{ evaluationResult.rule_code }}</a-tag>
            </div>
            <div class="info-item">
              <span class="info-label">评估结果</span>
              <a-tag :color="evaluationResult.compliant ? 'success' : 'error'" class="info-tag result-tag">
                <CheckCircleOutlined v-if="evaluationResult.compliant" />
                <CloseCircleOutlined v-else />
                {{ evaluationResult.compliant ? '合规' : '不合规' }}
              </a-tag>
            </div>
          </div>

          <div class="info-row">
            <div class="info-item full-width">
              <span class="info-label">规则名称</span>
              <span class="info-value">{{ evaluationResult.rule_name }}</span>
            </div>
          </div>

          <div class="info-row">
            <div class="info-item full-width">
              <span class="info-label">文档名称</span>
              <span class="info-value">{{ evaluationResult.document_name }}</span>
            </div>
          </div>

          <!-- 置信度 -->
          <div class="confidence-section">
            <div class="confidence-header">
              <span class="info-label">
                <TrophyOutlined class="section-icon" />
                置信度
              </span>
              <span class="confidence-value">{{ Math.round(evaluationResult.confidence * 100) }}%</span>
            </div>
            <a-progress
              :percent="Math.round(evaluationResult.confidence * 100)"
              :stroke-color="getConfidenceColor(evaluationResult.confidence)"
              :show-info="false"
              stroke-linecap="round"
            />
          </div>

          <!-- 证据 -->
          <div class="detail-section evidence-section">
            <div class="section-header">
              <FileSearchOutlined class="section-icon" />
              <span>证据发现</span>
            </div>
            <div class="section-content evidence-box">
              {{ evaluationResult.evidence }}
            </div>
          </div>

          <!-- 推理过程 -->
          <div class="detail-section reasoning-section">
            <div class="section-header">
              <CodeOutlined class="section-icon" />
              <span>证据引用</span>
            </div>
            <div class="section-content reasoning-box">
              <pre class="reasoning-text">{{ evaluationResult.reasoning }}</pre>
            </div>
          </div>
        </div>
      </a-card>

      <!-- 反馈表单 -->
      <a-card class="feedback-form-card" :bordered="false">
        <template #title>
          <div class="card-header">
            <CommentOutlined class="card-icon" />
            <span>反馈信息</span>
          </div>
        </template>

        <a-form
          ref="formRef"
          :model="formState"
          :label-col="{ span: 6 }"
          :wrapper-col="{ span: 18 }"
          class="feedback-form"
        >
          <!-- 反馈类型 -->
          <a-form-item
            label="评估结果是否正确"
            name="feedbackType"
            :rules="[{ required: true, message: '请选择反馈类型' }]"
          >
            <a-radio-group v-model:value="formState.feedbackType" button-style="solid" size="large" class="feedback-type-radio">
              <a-radio-button value="correct" class="correct-btn">
                <CheckCircleOutlined class="radio-icon" /> 正确
              </a-radio-button>
              <a-radio-button value="incorrect" class="incorrect-btn">
                <CloseCircleOutlined class="radio-icon" /> 错误
              </a-radio-button>
            </a-radio-group>
          </a-form-item>

        <!-- 错误类别 (仅在选择"错误"时显示) -->
        <a-form-item
          v-if="formState.feedbackType === 'incorrect'"
          label="错误类别"
          name="errorCategory"
          :rules="[{ required: true, message: '请选择错误类别' }]"
        >
          <a-select
            v-model:value="formState.errorCategory"
            placeholder="请选择错误类别"
            size="large"
          >
            <a-select-option value="false_positive">
              <AlertOutlined /> 误报 (False Positive) - 实际合规但判定为不合规
            </a-select-option>
            <a-select-option value="false_negative">
              <WarningOutlined /> 漏报 (False Negative) - 实际不合规但判定为合规
            </a-select-option>
            <a-select-option value="wrong_reasoning">
              <BulbOutlined /> 推理错误 - 结论可能正确但推理过程有误
            </a-select-option>
            <a-select-option value="incomplete_check">
              <FileSearchOutlined /> 检查不完整 - 遗漏了重要检查点
            </a-select-option>
            <a-select-option value="rule_ambiguity">
              <QuestionCircleOutlined /> 规则歧义 - 规则描述不清晰导致误判
            </a-select-option>
            <a-select-option value="other">
              <InfoCircleOutlined /> 其他错误
            </a-select-option>
          </a-select>
        </a-form-item>

        <!-- 错误详情 (仅在选择"错误"时显示) -->
        <a-form-item
          v-if="formState.feedbackType === 'incorrect'"
          label="错误详情"
          name="errorDetail"
          :rules="[
            { required: true, message: '请输入错误详情' },
            { min: 10, message: '请至少输入10个字符的详细说明' }
          ]"
        >
          <a-textarea
            v-model:value="formState.errorDetail"
            placeholder="请详细描述发现的错误，包括：&#10;1. 具体哪里判断错误&#10;2. 正确的判断应该是什么&#10;3. 错误的原因分析&#10;4. 改进建议"
            :rows="6"
            show-count
            :maxlength="1000"
          />
        </a-form-item>

        <!-- 补充证据 (可选) -->
        <a-form-item label="补充证据" name="evidence">
          <a-textarea
            v-model:value="formState.evidence"
            placeholder="如有需要，可以补充证据信息或引用文档内容"
            :rows="4"
            show-count
            :maxlength="500"
          />
        </a-form-item>

          <!-- 反馈人 (可选) -->
          <a-form-item label="反馈人" name="feedbackBy">
            <a-input
              v-model:value="formState.feedbackBy"
              placeholder="请输入您的姓名或工号(可选)"
              size="large"
              :maxlength="50"
            >
              <template #prefix>
                <UserOutlined style="color: rgba(0, 0, 0, 0.45)" />
              </template>
            </a-input>
          </a-form-item>
        </a-form>
      </a-card>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch, reactive } from 'vue'
import { message } from 'ant-design-vue'
import type { FormInstance } from 'ant-design-vue'
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  AlertOutlined,
  WarningOutlined,
  BulbOutlined,
  FileSearchOutlined,
  QuestionCircleOutlined,
  InfoCircleOutlined,
  FileTextOutlined,
  TrophyOutlined,
  CodeOutlined,
  CommentOutlined,
  UserOutlined
} from '@ant-design/icons-vue'
import type { EvaluationResult, FeedbackRequest, ErrorCategory } from '@/types/demo'

interface Props {
  visible: boolean
  evaluationResult: EvaluationResult | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:visible': [value: boolean]
  submit: [data: FeedbackRequest]
}>()

const isVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value)
})

// 表单引用
const formRef = ref<FormInstance>()

// 表单状态
const formState = reactive({
  feedbackType: 'correct' as 'correct' | 'incorrect',
  errorCategory: undefined as ErrorCategory | undefined,
  errorDetail: '',
  evidence: '',
  feedbackBy: ''
})

// 提交状态
const submitting = ref(false)

// 置信度颜色
const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#52c41a'
  if (confidence >= 0.6) return '#faad14'
  return '#ff4d4f'
}

// 提交反馈
const handleSubmit = async () => {
  if (!formRef.value || !props.evaluationResult) return

  try {
    await formRef.value.validate()

    submitting.value = true

    // 构建反馈数据
    const feedbackData: FeedbackRequest = {
      rule_id: props.evaluationResult.rule_id,
      rule_code: props.evaluationResult.rule_code,
      rule_name: props.evaluationResult.rule_name,
      document_name: props.evaluationResult.document_name,
      evaluation_result: props.evaluationResult.compliant,
      feedback_type: formState.feedbackType,
      error_category: formState.feedbackType === 'incorrect' ? formState.errorCategory : undefined,
      error_detail: formState.feedbackType === 'incorrect' ? formState.errorDetail : undefined,
      evidence: formState.evidence || undefined,
      feedback_by: formState.feedbackBy || undefined,
      medical_text: props.evaluationResult.medical_text || undefined // 病历原文
    }

    // 触发提交事件
    emit('submit', feedbackData)

    // 重置表单
    resetForm()
  } catch (error) {
    console.error('表单验证失败:', error)
  } finally {
    submitting.value = false
  }
}

// 关闭弹窗
const handleClose = () => {
  resetForm()
  isVisible.value = false
}

// 重置表单
const resetForm = () => {
  formState.feedbackType = 'correct'
  formState.errorCategory = undefined
  formState.errorDetail = ''
  formState.evidence = ''
  formState.feedbackBy = ''
  formRef.value?.clearValidate()
}

// 监听反馈类型变化，清空错误相关字段
watch(() => formState.feedbackType, (newValue) => {
  if (newValue === 'correct') {
    formState.errorCategory = undefined
    formState.errorDetail = ''
    formRef.value?.clearValidate(['errorCategory', 'errorDetail'])
  }
})

// 监听弹窗打开，重置表单
watch(() => props.visible, (newValue) => {
  if (newValue) {
    resetForm()
  }
})
</script>

<style scoped lang="less">
.feedback-modal {
  .result-info-card,
  .feedback-form-card {
    margin-bottom: 20px;
    border: 1px solid #d9d9d9 !important;
    border-radius: 8px !important;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08) !important;
    transition: all 0.3s ease;

    &:hover {
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12) !important;
    }

    :deep(.ant-card-head) {
      background: linear-gradient(to bottom, #fafafa, #f5f5f5);
      border-bottom: 2px solid #e8e8e8;
      padding: 14px 20px;

      .card-header {
        display: flex;
        align-items: center;
        font-size: 16px;
        font-weight: 600;
        color: #262626;

        .card-icon {
          margin-right: 8px;
          font-size: 18px;
          color: #1890ff;
        }
      }
    }

    :deep(.ant-card-body) {
      padding: 20px;
      background-color: #ffffff;
    }
  }

  // 评估结果卡片
  .result-content {
    .info-row {
      display: flex;
      gap: 16px;
      margin-bottom: 16px;

      .info-item {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 8px;

        &.full-width {
          flex: 1 1 100%;
        }

        .info-label {
          font-size: 13px;
          font-weight: 600;
          color: rgba(0, 0, 0, 0.65);
          display: flex;
          align-items: center;
          gap: 4px;

          .section-icon {
            color: #1890ff;
          }
        }

        .info-value {
          font-size: 14px;
          color: rgba(0, 0, 0, 0.85);
          line-height: 1.6;
        }

        .info-tag {
          font-size: 13px;
          padding: 4px 12px;
          border-radius: 4px;
          font-weight: 500;

          &.result-tag {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 14px;
            padding: 6px 16px;
          }
        }
      }
    }

    .confidence-section {
      margin: 20px 0;
      padding: 16px;
      background: linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%);
      border-radius: 8px;
      border: 1px solid #d6e4ff;

      .confidence-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;

        .info-label {
          font-size: 14px;
          font-weight: 600;
          color: rgba(0, 0, 0, 0.85);
        }

        .confidence-value {
          font-size: 18px;
          font-weight: 700;
          color: #1890ff;
        }
      }

      :deep(.ant-progress-line) {
        height: 10px;
      }
    }

    .detail-section {
      margin-top: 20px;

      .section-header {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 14px;
        font-weight: 600;
        color: rgba(0, 0, 0, 0.85);
        margin-bottom: 12px;

        .section-icon {
          color: #1890ff;
          font-size: 16px;
        }
      }

      .section-content {
        padding: 16px;
        border-radius: 6px;
        font-size: 14px;
        line-height: 1.8;
        color: rgba(0, 0, 0, 0.85);

        &.evidence-box {
          background: #fff7e6;
          border: 1px solid #ffd591;
        }

        &.reasoning-box {
          background: #f5f5f5;
          border: 1px solid #d9d9d9;

          .reasoning-text {
            margin: 0;
            white-space: pre-wrap;
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 14px;
            line-height: 1.6;
          }
        }
      }
    }
  }

  // 反馈表单
  .feedback-form {
    :deep(.ant-form-item) {
      margin-bottom: 20px;

      .ant-form-item-label {
        label {
          font-weight: 600;
          font-size: 14px;
          color: rgba(0, 0, 0, 0.85);
        }
      }
    }

    .feedback-type-radio {
      display: flex;
      gap: 12px;

      :deep(.ant-radio-button-wrapper) {
        flex: 1;
        height: 48px;
        line-height: 46px;
        text-align: center;
        font-size: 15px;
        font-weight: 600;
        border-radius: 8px;
        border: 2px solid #d9d9d9;
        transition: all 0.3s ease;

        &:not(.ant-radio-button-wrapper-checked) {
          background: #fafafa;

          &:hover {
            border-color: #1890ff;
            color: #1890ff;
          }
        }

        &.correct-btn.ant-radio-button-wrapper-checked {
          background: linear-gradient(135deg, #52c41a 0%, #73d13d 100%);
          border-color: #52c41a;
          color: #fff;
          box-shadow: 0 4px 12px rgba(82, 196, 26, 0.3);

          &:hover {
            background: linear-gradient(135deg, #73d13d 0%, #95de64 100%);
          }
        }

        &.incorrect-btn.ant-radio-button-wrapper-checked {
          background: linear-gradient(135deg, #ff4d4f 0%, #ff7875 100%);
          border-color: #ff4d4f;
          color: #fff;
          box-shadow: 0 4px 12px rgba(255, 77, 79, 0.3);

          &:hover {
            background: linear-gradient(135deg, #ff7875 0%, #ffa39e 100%);
          }
        }

        .radio-icon {
          margin-right: 6px;
          font-size: 16px;
        }
      }
    }

    :deep(.ant-select) {
      .ant-select-selector {
        height: 40px;
        padding: 8px 12px;
        border-radius: 6px;
        border: 1.5px solid #d9d9d9;
        transition: all 0.3s ease;

        &:hover {
          border-color: #1890ff;
        }
      }

      &.ant-select-focused .ant-select-selector {
        border-color: #1890ff;
        box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.1);
      }
    }

    :deep(.ant-input),
    :deep(.ant-input-textarea textarea) {
      border-radius: 6px;
      border: 1.5px solid #d9d9d9;
      transition: all 0.3s ease;

      &:hover {
        border-color: #1890ff;
      }

      &:focus {
        border-color: #1890ff;
        box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.1);
      }
    }

    :deep(.ant-input-textarea) {
      textarea {
        min-height: 100px;
      }
    }
  }
}

// Modal 覆盖样式
:deep(.ant-modal) {
  .ant-modal-header {
    background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
    border-bottom: none;
    padding: 18px 24px;

    .ant-modal-title {
      color: #fff;
      font-size: 18px;
      font-weight: 600;
    }
  }

  .ant-modal-close {
    color: rgba(255, 255, 255, 0.85);

    &:hover {
      color: #fff;
    }
  }

  .ant-modal-footer {
    padding: 14px 24px;
    border-top: 1px solid #f0f0f0;

    .ant-btn {
      height: 40px;
      font-size: 15px;
      font-weight: 600;
      border-radius: 6px;

      &.ant-btn-default {
        border: 1.5px solid #d9d9d9;

        &:hover {
          border-color: #1890ff;
          color: #1890ff;
        }
      }

      &.ant-btn-primary {
        background: linear-gradient(135deg, #1890ff 0%, #096dd9 100%);
        border: none;
        box-shadow: 0 2px 8px rgba(24, 144, 255, 0.3);

        &:hover {
          background: linear-gradient(135deg, #40a9ff 0%, #1890ff 100%);
          box-shadow: 0 4px 12px rgba(24, 144, 255, 0.4);
        }
      }
    }
  }
}
</style>
