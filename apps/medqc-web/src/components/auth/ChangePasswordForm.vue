<template>
  <div class="change-password-form">
    <a-form
      ref="formRef"
      :model="passwordForm"
      :rules="passwordRules"
      layout="vertical"
      size="large"
      @finish="handleSubmit"
    >
      <!-- 当前密码 -->
      <a-form-item
        name="current_password"
        class="mb-4"
      >
        <label class="block text-xs font-medium text-slate-300 mb-2">当前密码</label>
        <div class="relative">
          <a-input-password
            v-model:value="passwordForm.current_password"
            placeholder="请输入当前密码"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <LockOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 新密码 -->
      <a-form-item
        name="new_password"
        class="mb-4"
      >
        <label class="block text-xs font-medium text-slate-300 mb-2">新密码</label>
        <div class="relative">
          <a-input-password
            v-model:value="passwordForm.new_password"
            placeholder="请输入新密码"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <SafetyCertificateOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 确认新密码 -->
      <a-form-item
        name="confirm_password"
        class="mb-4"
      >
        <label class="block text-xs font-medium text-slate-300 mb-2">确认新密码</label>
        <div class="relative">
          <a-input-password
            v-model:value="passwordForm.confirm_password"
            placeholder="请再次输入新密码"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <CheckCircleOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 密码强度指示器 -->
      <PasswordStrength
        v-if="passwordForm.new_password"
        :password="passwordForm.new_password"
        class="mb-6"
      />

      <!-- 密码安全提示 -->
      <div class="mb-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
        <div class="flex items-start gap-3">
          <InfoCircleOutlined class="text-blue-400 text-sm mt-0.5" />
          <div class="text-xs text-blue-200">
            <div class="font-medium mb-2">
              密码安全建议：
            </div>
            <ul class="space-y-1 text-blue-200/80">
              <li>• 使用至少8个字符，包含大小写字母、数字和特殊符号</li>
              <li>• 避免使用个人信息（如姓名、生日）作为密码</li>
              <li>• 定期更换密码，建议每3-6个月更换一次</li>
              <li>• 不要在多个账户中使用相同密码</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="flex gap-3">
        <a-button
          type="primary"
          html-type="submit"
          :loading="loading"
          size="large"
          class="flex-1 h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none font-semibold shadow-lg hover:shadow-xl"
        >
          <SaveOutlined
            v-if="!loading"
            class="mr-2"
          />
          确认修改
        </a-button>

        <a-button
          size="large"
          class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20"
          @click="handleCancel"
        >
          <CloseOutlined class="mr-2" />
          取消
        </a-button>
      </div>
    </a-form>

    <!-- 最近密码修改记录 -->
    <div class="mt-8 p-4 rounded-xl bg-slate-700/30 border border-slate-600/30">
      <div class="flex items-center gap-2 mb-3">
        <HistoryOutlined class="text-slate-400" />
        <h4 class="text-sm font-medium text-slate-300">
          密码修改记录
        </h4>
      </div>

      <div class="space-y-2">
        <div class="flex items-center justify-between text-xs">
          <span class="text-slate-400">上次修改时间</span>
          <span class="text-slate-300">{{ lastPasswordChange || '从未修改' }}</span>
        </div>
        <div class="flex items-center justify-between text-xs">
          <span class="text-slate-400">修改次数</span>
          <span class="text-slate-300">{{ passwordChangeCount }} 次</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  LockOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  InfoCircleOutlined,
  SaveOutlined,
  CloseOutlined,
  HistoryOutlined,
} from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'
import type { PasswordUpdateRequest } from '@/types/auth'
import PasswordStrength from './PasswordStrength.vue'

const passwordSymbolPattern = new RegExp('[!@#$%^&*()_+=[\\]{};:\'"\\\\|,.<>/?-]')

// Props
interface Props {
  loading?: boolean
  lastPasswordChange?: string
  passwordChangeCount?: number
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  lastPasswordChange: '',
  passwordChangeCount: 0,
})

// Emits
const emit = defineEmits<{
  'change-password': [data: PasswordUpdateRequest]
  cancel: []
}>()

// Form reference
const formRef = ref<FormInstance>()

// Form data
const passwordForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

// Form validation rules
const passwordRules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 8, message: '新密码至少8位字符', trigger: 'blur' },
    {
      validator: (_: unknown, value: string) => {
        if (!value) return Promise.resolve()

        // 检查是否与当前密码相同
        if (value === passwordForm.current_password) {
          return Promise.reject('新密码不能与当前密码相同')
        }

        // 检查密码强度
        const hasUpper = /[A-Z]/.test(value)
        const hasLower = /[a-z]/.test(value)
        const hasNumber = /\d/.test(value)
        const hasSymbol = passwordSymbolPattern.test(value)

        if (!hasUpper || !hasLower || !hasNumber) {
          return Promise.reject('密码必须包含大小写字母和数字')
        }

        return Promise.resolve()
      },
      trigger: 'blur',
    },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    {
      validator: (_: unknown, value: string) => {
        if (!value) return Promise.resolve()
        if (value !== passwordForm.new_password) {
          return Promise.reject('两次输入的密码不一致')
        }
        return Promise.resolve()
      },
      trigger: 'blur',
    },
  ],
}

// Handle form submit
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()

    const { confirm_password, ...passwordData } = passwordForm
    emit('change-password', passwordData as PasswordUpdateRequest)
  } catch (error) {
    const validateError = error as { errorFields?: unknown[] }
    if (validateError?.errorFields) {
      message.warning('请检查输入信息')
    }
  }
}

// Handle cancel
const handleCancel = () => {
  // 重置表单
  formRef.value?.resetFields()
  Object.assign(passwordForm, {
    current_password: '',
    new_password: '',
    confirm_password: '',
  })

  emit('cancel')
}

// 计算密码强度
const passwordStrength = computed(() => {
  const password = passwordForm.new_password
  if (!password) return 0

  let score = 0
  if (password.length >= 8) score++
  if (/[A-Z]/.test(password)) score++
  if (/[a-z]/.test(password)) score++
  if (/\d/.test(password)) score++
  if (passwordSymbolPattern.test(password)) score++

  return score
})

// 是否为强密码
const isStrongPassword = computed(() => passwordStrength.value >= 4)

// 格式化最后修改时间
const lastPasswordChange = computed(() => {
  if (!props.lastPasswordChange) return null

  try {
    const date = new Date(props.lastPasswordChange)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return '时间格式错误'
  }
})

// Expose methods
defineExpose({
  resetForm: () => {
    formRef.value?.resetFields()
    Object.assign(passwordForm, {
      current_password: '',
      new_password: '',
      confirm_password: '',
    })
  },
  validateForm: () => formRef.value?.validate(),
  isStrongPassword,
})
</script>

<style scoped>
/* 复用之前的样式 */
:deep(.ant-input) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
  padding-left: 0 !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-input:focus),
:deep(.ant-input-focused) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-input-password) {
  border: none !important;
  box-shadow: none !important;
  background: transparent !important;
}

:deep(.ant-input-password .ant-input) {
  padding-left: 0 !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-input-password .ant-input-suffix) {
  color: rgb(148 163 184) !important;
}

:deep(.ant-btn-primary) {
  border: none !important;
  box-shadow: none !important;
}

:deep(.ant-form-item-explain-error) {
  color: #f87171 !important;
  font-size: 12px;
  margin-top: 4px;
}

/* 表单项动画 */
.change-password-form > * {
  animation: slideInUp 0.3s ease-out;
}

@keyframes slideInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 按钮悬浮效果 */
:deep(.ant-btn) {
  transition: all 0.2s ease-out;
}

:deep(.ant-btn:hover) {
  transform: translateY(-1px);
}

/* 安全提示动画 */
.bg-blue-500\/10 {
  animation: fadeIn 0.5s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* 记录区域样式 */
.bg-slate-700\/30 {
  transition: all 0.2s ease-out;
}

.bg-slate-700\/30:hover {
  background: rgba(71, 85, 105, 0.4) !important;
}
</style>
