<template>
  <a-modal
    v-model:visible="modalVisible"
    title="提交申诉"
    width="600px"
    :confirm-loading="submitting"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <div
      v-if="notification"
      class="appeal-modal-content"
    >
      <!-- 通知信息摘要 -->
      <div class="notification-summary">
        <h4>申诉的通知信息</h4>
        <a-descriptions
          :column="1"
          bordered
          size="small"
        >
          <a-descriptions-item label="通知标题">
            {{ notification.title }}
          </a-descriptions-item>
          <a-descriptions-item label="质控评分">
            <span :style="{ color: getScoreColor(notification.qcResult.overallScore) }">
              {{ notification.qcResult.overallScore }}分
            </span>
          </a-descriptions-item>
          <a-descriptions-item label="问题数量">
            {{ notification.qcResult.issues.length }}个
          </a-descriptions-item>
        </a-descriptions>
      </div>

      <!-- 申诉表单 -->
      <div class="appeal-form">
        <a-form
          ref="formRef"
          :model="formData"
          :rules="formRules"
          layout="vertical"
        >
          <a-form-item
            label="申诉类型"
            name="appealType"
            required
          >
            <a-radio-group v-model:value="formData.appealType">
              <a-radio value="quality_dispute">
                质量争议
              </a-radio>
              <a-radio value="rule_challenge">
                规则质疑
              </a-radio>
              <a-radio value="data_correction">
                数据纠正
              </a-radio>
              <a-radio value="process_appeal">
                流程申诉
              </a-radio>
            </a-radio-group>
          </a-form-item>

          <a-form-item
            label="申诉理由"
            name="reason"
            required
          >
            <a-select
              v-model:value="formData.reason"
              placeholder="请选择申诉理由"
              @change="handleReasonChange"
            >
              <a-select-option value="rule_misapplication">
                规则误用 - 质控规则应用不当
              </a-select-option>
              <a-select-option value="data_inaccuracy">
                数据不准确 - 病历数据存在错误
              </a-select-option>
              <a-select-option value="context_missing">
                缺少上下文 - 质控分析缺少关键信息
              </a-select-option>
              <a-select-option value="technical_error">
                技术错误 - 系统或算法错误
              </a-select-option>
              <a-select-option value="scoring_error">
                评分错误 - 评分计算有误
              </a-select-option>
              <a-select-option value="rule_outdated">
                规则过时 - 质控规则需要更新
              </a-select-option>
              <a-select-option value="other">
                其他原因
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item
            label="优先级"
            name="priority"
            required
          >
            <a-select
              v-model:value="formData.priority"
              placeholder="请选择申诉优先级"
            >
              <a-select-option value="low">
                <a-tag color="green">
                  低优先级
                </a-tag>
                - 一般性问题，不影响诊疗
              </a-select-option>
              <a-select-option value="medium">
                <a-tag color="orange">
                  中优先级
                </a-tag>
                - 可能影响质量评估
              </a-select-option>
              <a-select-option value="high">
                <a-tag color="red">
                  高优先级
                </a-tag>
                - 严重影响诊疗决策
              </a-select-option>
              <a-select-option value="urgent">
                <a-tag color="purple">
                  紧急
                </a-tag>
                - 需要立即处理
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item
            v-if="formData.reason === 'other'"
            label="其他理由说明"
            name="reasonText"
            required
          >
            <a-input
              v-model:value="formData.reasonText"
              placeholder="请详细说明申诉理由"
            />
          </a-form-item>

          <a-form-item
            label="详细描述"
            name="description"
            required
          >
            <a-textarea
              v-model:value="formData.description"
              placeholder="请详细描述申诉的具体内容，包括相关证据和理由"
              :rows="4"
              :maxlength="500"
              show-count
            />
          </a-form-item>

          <a-form-item label="支持材料">
            <a-upload
              v-model:file-list="fileList"
              :before-upload="beforeUpload"
              :remove="handleRemoveFile"
              multiple
              :max-count="5"
            >
              <a-button>
                <UploadOutlined />
                上传附件
              </a-button>
            </a-upload>
            <div class="upload-tip">
              支持上传图片、文档等文件，最多5个文件，单个文件不超过10MB
            </div>
          </a-form-item>

          <a-form-item
            label="联系方式"
            name="contact"
          >
            <a-input
              v-model:value="formData.contact"
              placeholder="请提供联系电话或邮箱（可选）"
            />
          </a-form-item>
        </a-form>
      </div>

      <!-- 申诉须知 -->
      <div class="appeal-notice">
        <a-alert
          message="申诉须知"
          type="info"
          show-icon
        >
          <template #description>
            <ul>
              <li>申诉提交后将进入审核流程，通常在3-5个工作日内给出回复</li>
              <li>请提供真实、准确的申诉理由和支持材料</li>
              <li>恶意申诉或提供虚假信息可能影响后续申诉权限</li>
              <li>申诉结果将通过系统通知的方式告知</li>
            </ul>
          </template>
        </a-alert>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { computed, ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import type { FormInstance, UploadProps } from 'ant-design-vue'
import type { FormProps } from 'ant-design-vue'
import { UploadOutlined } from '@ant-design/icons-vue'
import type { QCNotification, AppealReason } from '@/types/quality-control'

// Props
const props = defineProps<{
  visible: boolean
  notification: QCNotification | null
}>()

// Emits
const emit = defineEmits<{
  'update:visible': [visible: boolean]
  'appeal-submitted': [appeal: unknown]
}>()

// 响应式数据
const formRef = ref<FormInstance>()
const submitting = ref(false)
const fileList = ref<any[]>([])

const formData = reactive({
  appealType: 'quality_dispute',
  reason: '' as AppealReason | '',
  reasonText: '',
  description: '',
  contact: '',
  priority: 'medium',
})

// 表单验证规则
const formRules: FormProps['rules'] = {
  appealType: [{ required: true, message: '请选择申诉类型', trigger: 'change' }],
  reason: [{ required: true, message: '请选择申诉理由', trigger: 'change' }],
  reasonText: [
    { required: true, message: '请说明其他理由', trigger: 'blur' },
    { min: 5, message: '理由说明至少需要5个字符', trigger: 'blur' },
  ],
  description: [
    { required: true, message: '请填写详细描述', trigger: 'blur' },
    { min: 20, message: '描述至少需要20个字符', trigger: 'blur' },
    { max: 500, message: '描述不能超过500个字符', trigger: 'blur' },
  ],
  priority: [{ required: true, message: '请选择申诉优先级', trigger: 'change' }],
  contact: [
    {
      pattern: /^(1[3-9]\d{9}|[\w-]+(\.[\w-]+)*@[\w-]+(\.[\w-]+)+)$/,
      message: '请输入有效的手机号或邮箱',
      trigger: 'blur',
    },
  ],
}

// 计算属性
const modalVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

// 方法
const getScoreColor = (score: number) => {
  if (score >= 90) return '#52c41a'
  if (score >= 80) return '#faad14'
  if (score >= 60) return '#fa8c16'
  return '#f5222d'
}

const handleReasonChange = (value: AppealReason) => {
  if (value !== 'other') {
    formData.reasonText = ''
  }
}

const beforeUpload: UploadProps['beforeUpload'] = (file) => {
  const isValidType = [
    'image/jpeg',
    'image/png',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  ].includes(file.type)
  if (!isValidType) {
    message.error('只能上传图片、PDF或Word文档!')
    return false
  }

  const isLt10M = file.size / 1024 / 1024 < 10
  if (!isLt10M) {
    message.error('文件大小不能超过10MB!')
    return false
  }

  return false // 阻止自动上传
}

const handleRemoveFile = (file: unknown) => {
  const index = fileList.value.indexOf(file)
  if (index > -1) {
    fileList.value.splice(index, 1)
  }
}

const handleSubmit = async () => {
  if (!formRef.value || !props.notification) return

  try {
    await formRef.value.validate()
    submitting.value = true

    // 构建完整的申诉数据
    const appealData = {
      id: `appeal-${Date.now()}`,
      notificationId: props.notification.id,
      appealType: formData.appealType,
      reason: formData.reason,
      reasonText: formData.reasonText,
      description: formData.description,
      contact: formData.contact,
      priority: formData.priority,
      attachments: fileList.value.map((file) => ({
        name: file.name,
        size: file.size,
        type: file.type,
        url: URL.createObjectURL(file.originFileObj),
      })),
      status: 'pending',
      submittedAt: new Date(),
      submittedBy: '当前用户', // 实际应用中应该从用户上下文获取
      reviewerComment: '',
      reviewedAt: null,
      reviewedBy: '',
      estimatedReviewTime: new Date(Date.now() + 3 * 24 * 60 * 60 * 1000), // 3天后
      relatedQCResult: props.notification.qcResult,
    }

    // 模拟API调用延迟
    await new Promise((resolve) => setTimeout(resolve, 1500))

    emit('appeal-submitted', appealData)
    message.success('申诉提交成功！预计3个工作日内给出回复。')

    // 重置表单
    resetForm()
    modalVisible.value = false
  } catch (error) {
    console.error('表单验证失败:', error)
    message.error('表单验证失败，请检查输入内容')
  } finally {
    submitting.value = false
  }
}

const handleCancel = () => {
  resetForm()
  modalVisible.value = false
}

const resetForm = () => {
  formData.appealType = 'quality_dispute'
  formData.reason = ''
  formData.reasonText = ''
  formData.description = ''
  formData.contact = ''
  formData.priority = 'medium'
  fileList.value = []

  // 重置表单验证状态
  if (formRef.value) {
    formRef.value.resetFields()
  }
  formData.description = ''
  formData.contact = ''
  fileList.value = []
  formRef.value?.resetFields()
}
</script>

<style scoped lang="less">
.appeal-modal-content {
  .notification-summary {
    margin-bottom: 24px;

    h4 {
      font-weight: 600;
      margin-bottom: 12px;
      color: #333;
    }
  }

  .appeal-form {
    margin-bottom: 24px;

    .upload-tip {
      margin-top: 8px;
      font-size: 12px;
      color: #666;
    }
  }

  .appeal-notice {
    ul {
      margin: 8px 0 0 0;
      padding-left: 20px;

      li {
        margin-bottom: 4px;
        font-size: 14px;
        line-height: 1.5;
      }
    }
  }
}
</style>
