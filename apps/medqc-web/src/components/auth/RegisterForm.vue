<template>
  <div class="register-form">
    <a-form
      ref="formRef"
      :model="registerForm"
      :rules="registerRules"
      @finish="handleRegister"
      layout="vertical"
      size="large"
    >
      <!-- 姓名输入 -->
      <a-form-item name="display_name" class="mb-4">
        <label class="block text-xs font-medium text-slate-300 mb-2">姓名</label>
        <div class="relative">
          <a-input
            v-model:value="registerForm.display_name"
            placeholder="请输入真实姓名"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <UserOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 邮箱输入 -->
      <a-form-item name="email" class="mb-4">
        <label class="block text-xs font-medium text-slate-300 mb-2">邮箱</label>
        <div class="relative">
          <a-input
            v-model:value="registerForm.email"
            placeholder="请输入工作邮箱"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <MailOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 科室选择 -->
      <a-form-item name="department" class="mb-4">
        <label class="block text-xs font-medium text-slate-300 mb-2">科室</label>
        <a-select
          v-model:value="registerForm.department"
          placeholder="选择所属科室"
          size="large"
          class="department-select"
          show-search
          :filter-option="filterDepartment"
        >
          <a-select-option 
            v-for="dept in departments" 
            :key="dept.value" 
            :value="dept.value"
          >
            {{ dept.label }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <!-- 角色申请 -->
      <a-form-item name="role" class="mb-4">
        <label class="block text-xs font-medium text-slate-300 mb-2">申请角色</label>
        <a-select
          v-model:value="registerForm.role"
          placeholder="选择申请角色"
          size="large"
          class="role-select"
        >
          <a-select-option value="doctor">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white text-xs font-bold">D</div>
              医生 - 可查看和编辑病案
            </div>
          </a-select-option>
          <a-select-option value="qc_staff">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold">Q</div>
              质控员 - 可执行质控分析
            </div>
          </a-select-option>
          <a-select-option value="viewer">
            <div class="flex items-center gap-2">
              <div class="w-6 h-6 rounded bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center text-white text-xs font-bold">V</div>
              查看者 - 仅可查看数据
            </div>
          </a-select-option>
        </a-select>
      </a-form-item>

      <!-- 密码输入 -->
      <a-form-item name="password" class="mb-4">
        <label class="block text-xs font-medium text-slate-300 mb-2">密码</label>
        <div class="relative">
          <a-input-password
            v-model:value="registerForm.password"
            placeholder="请设置登录密码"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <LockOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 确认密码 -->
      <a-form-item name="confirmPassword" class="mb-4">
        <label class="block text-xs font-medium text-slate-300 mb-2">确认密码</label>
        <div class="relative">
          <a-input-password
            v-model:value="registerForm.confirmPassword"
            placeholder="请再次输入密码"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <SafetyCertificateOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 密码强度指示器 -->
      <PasswordStrength 
        v-if="registerForm.password" 
        :password="registerForm.password" 
        class="mb-4"
      />

      <!-- 手机号输入（可选） -->
      <a-form-item name="phone" class="mb-4">
        <label class="block text-xs font-medium text-slate-300 mb-2">手机号（可选）</label>
        <div class="relative">
          <a-input
            v-model:value="registerForm.phone"
            placeholder="用于接收验证码"
            class="h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400"
          />
          <div class="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400">
            <PhoneOutlined />
          </div>
        </div>
      </a-form-item>

      <!-- 服务条款同意 -->
      <a-form-item name="agreeTerms" class="mb-6">
        <a-checkbox v-model:checked="registerForm.agreeTerms" class="text-xs text-slate-300">
          我已阅读并同意
          <a class="text-cyan-300 hover:text-cyan-200 mx-1" @click="showTerms">《服务条款》</a>
          和
          <a class="text-cyan-300 hover:text-cyan-200 mx-1" @click="showPrivacy">《隐私政策》</a>
        </a-checkbox>
      </a-form-item>

      <!-- 注册按钮 -->
      <a-button
        type="primary"
        html-type="submit"
        :loading="loading"
        block
        size="large"
        class="h-12 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 border-none font-semibold shadow-lg hover:shadow-xl"
      >
        <UserAddOutlined v-if="!loading" class="mr-2" />
        提交注册申请
      </a-button>
    </a-form>

    <!-- 注册说明 -->
    <div class="mt-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20">
      <div class="flex items-start gap-3">
        <InfoCircleOutlined class="text-blue-400 text-sm mt-0.5" />
        <div class="text-xs text-blue-200">
          <div class="font-medium mb-1">注册说明：</div>
          <ul class="space-y-1 text-blue-200/80">
            <li>• 注册申请需要管理员审核，通常在1-2个工作日内完成</li>
            <li>• 请使用真实的工作邮箱，审核结果将发送至该邮箱</li>
            <li>• 高级角色（质控管理员、系统管理员）需要额外的权限申请流程</li>
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { message } from 'ant-design-vue'
import { 
  UserOutlined, 
  MailOutlined, 
  LockOutlined, 
  SafetyCertificateOutlined,
  PhoneOutlined,
  UserAddOutlined,
  InfoCircleOutlined
} from '@ant-design/icons-vue'
import type { FormInstance } from 'ant-design-vue'
import type { RegisterRequest, UserRole } from '@/types/auth'
import PasswordStrength from './PasswordStrength.vue'

// Props
interface Props {
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  loading: false
})

// Emits
const emit = defineEmits<{
  register: [formData: RegisterRequest]
  'show-terms': []
  'show-privacy': []
}>()

// Form reference
const formRef = ref<FormInstance>()

// Form data
const registerForm = reactive({
  display_name: '',
  email: '',
  department: '',
  role: undefined as UserRole | undefined,
  password: '',
  confirmPassword: '',
  phone: '',
  agreeTerms: false
})

// 科室列表
const departments = [
  { value: '内科', label: '内科' },
  { value: '外科', label: '外科' },
  { value: '妇产科', label: '妇产科' },
  { value: '儿科', label: '儿科' },
  { value: '急诊科', label: '急诊科' },
  { value: '骨科', label: '骨科' },
  { value: '神经科', label: '神经科' },
  { value: '心血管科', label: '心血管科' },
  { value: '呼吸科', label: '呼吸科' },
  { value: '消化科', label: '消化科' },
  { value: '泌尿科', label: '泌尿科' },
  { value: '眼科', label: '眼科' },
  { value: '耳鼻喉科', label: '耳鼻喉科' },
  { value: '皮肤科', label: '皮肤科' },
  { value: '精神科', label: '精神科' },
  { value: '康复科', label: '康复科' },
  { value: '影像科', label: '影像科' },
  { value: '检验科', label: '检验科' },
  { value: '药剂科', label: '药剂科' },
  { value: '质控科', label: '质控科' },
  { value: '信息科', label: '信息科' },
  { value: '其他', label: '其他' }
]

// Form validation rules
const registerRules = {
  display_name: [
    { required: true, message: '请输入姓名', trigger: 'blur' },
    { min: 2, message: '姓名至少2个字符', trigger: 'blur' },
    { max: 20, message: '姓名不能超过20个字符', trigger: 'blur' }
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
  ],
  department: [
    { required: true, message: '请选择科室', trigger: 'change' }
  ],
  role: [
    { required: true, message: '请选择申请角色', trigger: 'change' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 8, message: '密码至少8位字符', trigger: 'blur' },
    { 
      validator: (_: unknown, value: string) => {
        if (!value) return Promise.resolve()
        
        const hasUpper = /[A-Z]/.test(value)
        const hasLower = /[a-z]/.test(value)
        const hasNumber = /\d/.test(value)
        
        if (!hasUpper || !hasLower || !hasNumber) {
          return Promise.reject('密码必须包含大小写字母和数字')
        }
        return Promise.resolve()
      },
      trigger: 'blur'
    }
  ],
  confirmPassword: [
    { required: true, message: '请确认密码', trigger: 'blur' },
    {
      validator: (_: unknown, value: string) => {
        if (!value) return Promise.resolve()
        if (value !== registerForm.password) {
          return Promise.reject('两次输入的密码不一致')
        }
        return Promise.resolve()
      },
      trigger: 'blur'
    }
  ],
  phone: [
    {
      validator: (_: unknown, value: string) => {
        if (!value) return Promise.resolve()
        if (!/^1[3-9]\d{9}$/.test(value)) {
          return Promise.reject('手机号格式不正确')
        }
        return Promise.resolve()
      },
      trigger: 'blur'
    }
  ],
  agreeTerms: [
    {
      validator: (_: unknown, value: boolean) => {
        if (!value) {
          return Promise.reject('请阅读并同意服务条款')
        }
        return Promise.resolve()
      },
      trigger: 'change'
    }
  ]
}

// Handle register
const handleRegister = async () => {
  try {
    await formRef.value?.validate()
    
    const { confirmPassword, agreeTerms, ...registerData } = registerForm
    emit('register', registerData as RegisterRequest)
  } catch (error) {
    if (error?.errorFields) {
      message.warning('请检查输入信息')
    }
  }
}

// Filter department options
const filterDepartment = (input: string, option: unknown) => {
  return option.children.toLowerCase().includes(input.toLowerCase())
}

// Show terms and privacy
const showTerms = () => emit('show-terms')
const showPrivacy = () => emit('show-privacy')

// Expose methods
defineExpose({
  resetForm: () => {
    formRef.value?.resetFields()
    Object.assign(registerForm, {
      display_name: '',
      email: '',
      department: '',
      role: undefined,
      password: '',
      confirmPassword: '',
      phone: '',
      agreeTerms: false
    })
  },
  validateForm: () => formRef.value?.validate()
})
</script>

<style scoped>
/* 复用登录表单的样式 */
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

:deep(.ant-select-selector) {
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
  border-radius: 0.75rem !important;
  height: 3rem !important;
  color: rgb(241 245 249) !important;
}

:deep(.ant-select-selection-placeholder) {
  color: rgb(100 116 139) !important;
}

:deep(.ant-checkbox-wrapper) {
  color: rgb(203 213 225) !important;
}

:deep(.ant-checkbox-checked .ant-checkbox-inner) {
  background-color: #06b6d4 !important;
  border-color: #06b6d4 !important;
}

:deep(.ant-checkbox-inner) {
  background-color: rgba(255, 255, 255, 0.05) !important;
  border-color: rgba(255, 255, 255, 0.2) !important;
}

:deep(.ant-form-item-explain-error) {
  color: #f87171 !important;
  font-size: 12px;
  margin-top: 4px;
}

.department-select :deep(.ant-select-dropdown),
.role-select :deep(.ant-select-dropdown) {
  background: rgb(15 23 42) !important;
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

.department-select :deep(.ant-select-item),
.role-select :deep(.ant-select-item) {
  color: rgb(241 245 249) !important;
}

.department-select :deep(.ant-select-item-option-selected),
.role-select :deep(.ant-select-item-option-selected) {
  background: rgba(6, 182, 212, 0.2) !important;
}
</style>
