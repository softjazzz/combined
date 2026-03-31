<template>
  <a-modal
    :open="visible"
    :title="isEdit ? '编辑用户' : '新增用户'"
    :width="600"
    :confirm-loading="loading"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <a-form
      ref="formRef"
      :model="formData"
      :rules="rules"
      layout="vertical"
      class="mt-4"
    >
      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item
            label="邮箱地址"
            name="email"
          >
            <a-input
              v-model:value="formData.email"
              placeholder="请输入邮箱地址"
              :disabled="isEdit"
            >
              <template #prefix>
                <MailOutlined class="text-gray-400" />
              </template>
            </a-input>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item
            label="显示名称"
            name="display_name"
          >
            <a-input
              v-model:value="formData.display_name"
              placeholder="请输入显示名称"
            >
              <template #prefix>
                <UserOutlined class="text-gray-400" />
              </template>
            </a-input>
          </a-form-item>
        </a-col>
      </a-row>

      <a-row
        v-if="!isEdit"
        :gutter="16"
      >
        <a-col :span="12">
          <a-form-item
            label="登录密码"
            name="password"
          >
            <a-input-password
              v-model:value="formData.password"
              placeholder="请输入登录密码"
            >
              <template #prefix>
                <LockOutlined class="text-gray-400" />
              </template>
            </a-input-password>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item
            label="确认密码"
            name="confirmPassword"
          >
            <a-input-password
              v-model:value="formData.confirmPassword"
              placeholder="请再次输入密码"
            >
              <template #prefix>
                <LockOutlined class="text-gray-400" />
              </template>
            </a-input-password>
          </a-form-item>
        </a-col>
      </a-row>

      <a-row :gutter="16">
        <a-col :span="12">
          <a-form-item
            label="部门"
            name="department"
          >
            <a-select
              v-model:value="formData.department"
              placeholder="请选择部门"
              allow-clear
            >
              <a-select-option value="信息科">
                信息科
              </a-select-option>
              <a-select-option value="质控科">
                质控科
              </a-select-option>
              <a-select-option value="内科">
                内科
              </a-select-option>
              <a-select-option value="外科">
                外科
              </a-select-option>
              <a-select-option value="妇产科">
                妇产科
              </a-select-option>
              <a-select-option value="儿科">
                儿科
              </a-select-option>
              <a-select-option value="急诊科">
                急诊科
              </a-select-option>
              <a-select-option value="影像科">
                影像科
              </a-select-option>
              <a-select-option value="检验科">
                检验科
              </a-select-option>
            </a-select>
          </a-form-item>
        </a-col>
        <a-col :span="12">
          <a-form-item
            label="医院"
            name="hospital_name"
          >
            <a-input
              v-model:value="formData.hospital_name"
              placeholder="请输入医院名称"
            >
              <template #prefix>
                <BankOutlined class="text-gray-400" />
              </template>
            </a-input>
          </a-form-item>
        </a-col>
      </a-row>

      <a-form-item
        label="用户角色"
        name="roles"
      >
        <a-checkbox-group v-model:value="formData.roles">
          <a-row>
            <a-col :span="12">
              <a-checkbox value="admin">
                <CrownOutlined class="text-orange-500 mr-2" />
                系统管理员
              </a-checkbox>
            </a-col>
            <a-col :span="12">
              <a-checkbox value="qc_manager">
                <SafetyCertificateOutlined class="text-blue-500 mr-2" />
                质控管理员
              </a-checkbox>
            </a-col>
            <a-col :span="12">
              <a-checkbox value="qc_staff">
                <SafetyOutlined class="text-green-500 mr-2" />
                质控人员
              </a-checkbox>
            </a-col>
            <a-col :span="12">
              <a-checkbox value="doctor">
                <MedicineBoxOutlined class="text-purple-500 mr-2" />
                医务人员
              </a-checkbox>
            </a-col>
          </a-row>
        </a-checkbox-group>
      </a-form-item>

      <a-form-item
        label="用户状态"
        name="is_active"
      >
        <a-radio-group v-model:value="formData.is_active">
          <a-radio :value="true">
            <a-badge
              status="success"
              text="激活"
            />
          </a-radio>
          <a-radio :value="false">
            <a-badge
              status="default"
              text="停用"
            />
          </a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item
        label="备注"
        name="notes"
      >
        <a-textarea
          v-model:value="formData.notes"
          placeholder="请输入备注信息"
          :rows="3"
        />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import type { FormInstance, FormProps } from 'ant-design-vue'
import {
  MailOutlined,
  UserOutlined,
  LockOutlined,
  BankOutlined,
  CrownOutlined,
  SafetyCertificateOutlined,
  SafetyOutlined,
  MedicineBoxOutlined,
} from '@ant-design/icons-vue'

interface Props {
  visible: boolean
  user?: Record<string, unknown>
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'submit', data: unknown): void
  (e: 'cancel'): void
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
})

const emit = defineEmits<Emits>()

// 表单引用
const formRef = ref<FormInstance>()

// 加载状态
const loading = ref(false)

// 表单数据
const formData = reactive({
  email: '',
  display_name: '',
  password: '',
  confirmPassword: '',
  department: '',
  hospital_name: '',
  roles: [],
  is_active: true,
  notes: '',
})

// 表单规则
const rules: NonNullable<FormProps['rules']> = {
  email: [
    { required: true, message: '请输入邮箱地址', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
  display_name: [
    { required: true, message: '请输入显示名称', trigger: 'blur' },
    { min: 2, max: 20, message: '显示名称长度为2-20个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入登录密码', trigger: 'blur' },
    { min: 6, message: '密码至少6位字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule: unknown, value: string) => {
        if (value && value !== formData.password) {
          return Promise.reject('两次输入的密码不一致')
        }
        return Promise.resolve()
      },
      trigger: 'blur',
    },
  ],
  roles: [{ required: true, message: '请选择用户角色', trigger: 'change' }],
} satisfies NonNullable<FormProps['rules']>

// 计算属性
const isEdit = computed(() => !!props.user)

// 监听用户数据变化
watch(
  () => props.user,
  (newUser) => {
    if (newUser) {
      // 编辑模式，填充表单数据
      Object.assign(formData, {
        email: newUser.email || '',
        display_name: newUser.display_name || '',
        password: '',
        confirmPassword: '',
        department: newUser.department || '',
        hospital_name: newUser.hospital_name || '',
        roles: newUser.roles || [],
        is_active: newUser.is_active ?? true,
        notes: newUser.notes || '',
      })
    } else {
      // 新增模式，重置表单
      Object.assign(formData, {
        email: '',
        display_name: '',
        password: '',
        confirmPassword: '',
        department: '',
        hospital_name: '',
        roles: [],
        is_active: true,
        notes: '',
      })
    }
  },
  { immediate: true },
)

// 监听visible变化
watch(
  () => props.visible,
  (newVisible: unknown) => {
    if (!newVisible) {
      // 关闭时重置表单
      formRef.value?.resetFields()
    }
  },
)

// 方法
const handleSubmit = async () => {
  try {
    await formRef.value?.validate()
    loading.value = true

    // 准备提交数据
    const submitData = { ...formData }

    // 如果是编辑模式且没有输入密码，则不更新密码
    if (isEdit.value && !submitData.password) {
      const { password: _password, confirmPassword: _confirmPassword, ...rest } = submitData
      emit('submit', rest)
      return
    }

    emit('submit', submitData)
  } catch (error) {
    message.warning('请检查表单输入')
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  emit('cancel')
}
</script>

<style scoped>
:deep(.ant-form-item-label) {
  font-weight: 500;
}

:deep(.ant-checkbox-group .ant-checkbox-wrapper) {
  margin-bottom: 8px;
}
</style>
