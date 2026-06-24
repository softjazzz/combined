<template>
  <a-modal
    :open="visible"
    title="角色权限配置"
    :width="800"
    :confirm-loading="loading"
    @ok="handleSubmit"
    @cancel="handleCancel"
  >
    <div
      v-if="role"
      class="role-edit-content"
    >
      <!-- 角色基本信息 -->
      <div class="mb-6">
        <div class="flex items-center space-x-4 mb-4">
          <component
            :is="role.icon"
            :class="['text-4xl', role.color]"
          />
          <div>
            <h3 class="text-xl font-semibold">
              {{ role.name }}
            </h3>
            <p class="text-gray-600">
              {{ role.description }}
            </p>
          </div>
        </div>

        <a-row :gutter="16">
          <a-col :span="12">
            <a-statistic
              title="当前用户数"
              :value="Number(role.userCount ?? 0)"
              suffix="人"
            />
          </a-col>
          <a-col :span="12">
            <a-statistic
              title="权限数量"
              :value="Number(role.permissionCount ?? 0)"
              suffix="项"
            />
          </a-col>
        </a-row>
      </div>

      <!-- 权限配置 -->
      <div class="permissions-config">
        <h4 class="text-lg font-semibold mb-4">
          权限配置
        </h4>

        <div class="space-y-4">
          <div
            v-for="resource in resources"
            :key="resource.key"
            class="permission-group"
          >
            <div class="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
              <div class="flex items-center space-x-3">
                <component
                  :is="resource.icon"
                  :class="['text-xl', resource.color]"
                />
                <div>
                  <h5 class="font-medium">
                    {{ resource.name }}
                  </h5>
                  <p class="text-sm text-gray-600">
                    {{ resource.description }}
                  </p>
                </div>
              </div>

              <a-switch
                v-model:checked="resource.enabled"
                @change="(checked) => handleResourceToggle(resource.key, Boolean(checked))"
              />
            </div>

            <!-- 详细权限 -->
            <div
              v-if="resource.enabled"
              class="ml-8 mt-3 space-y-2"
            >
              <div
                v-for="action in resource.actions"
                :key="action.key"
                class="flex items-center justify-between"
              >
                <div class="flex items-center space-x-2">
                  <component
                    :is="action.icon"
                    class="text-gray-500"
                  />
                  <span class="text-sm">{{ action.name }}</span>
                  <a-tooltip :title="action.description">
                    <QuestionCircleOutlined class="text-gray-400 cursor-help" />
                  </a-tooltip>
                </div>

                <a-checkbox
                  v-model:checked="action.enabled"
                  @change="(e) => handleActionChange(resource.key, action.key, e)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 用户列表 -->
      <div class="mt-6">
        <h4 class="text-lg font-semibold mb-4">
          拥有此角色的用户
        </h4>

        <div class="space-y-2 max-h-40 overflow-y-auto">
          <div
            v-for="user in roleUsers"
            :key="user.id"
            class="flex items-center justify-between p-2 bg-gray-50 rounded"
          >
            <div class="flex items-center space-x-3">
              <a-avatar
                :size="32"
                :style="{ backgroundColor: getUserAvatarColor(user.email) }"
              >
                {{ user.display_name?.charAt(0) || user.email?.charAt(0) }}
              </a-avatar>
              <div>
                <div class="font-medium text-sm">
                  {{ user.display_name || user.email }}
                </div>
                <div class="text-xs text-gray-500">
                  {{ user.department || '-' }}
                </div>
              </div>
            </div>

            <a-badge
              :status="user.is_active ? 'success' : 'default'"
              :text="user.is_active ? '激活' : '停用'"
            />
          </div>

          <div
            v-if="roleUsers.length === 0"
            class="text-center py-4 text-gray-500"
          >
            暂无用户拥有此角色
          </div>
        </div>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, type Component } from 'vue'
import { message } from 'ant-design-vue'
import type { CheckboxChangeEvent } from 'ant-design-vue/es/checkbox/interface'
import {
  QuestionCircleOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  SettingOutlined,
  UserOutlined,
  BarChartOutlined,
  SafetyCertificateOutlined,
  EyeOutlined,
  EditOutlined,
  DeleteOutlined,
  PlusOutlined,
  DownloadOutlined,
  AuditOutlined,
  ToolOutlined,
} from '@ant-design/icons-vue'

interface Props {
  visible: boolean
  role?: {
    key: string
    name: string
    description: string
    icon?: Component
    color?: string
    userCount?: number
    permissionCount?: number
  }
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

// 加载状态
const loading = ref(false)

// 资源权限配置
const resources = ref([
  {
    key: 'medical_records',
    name: '病案记录',
    description: '医疗病案的管理和操作',
    icon: FileTextOutlined,
    color: 'text-blue-500',
    enabled: true,
    actions: [
      {
        key: 'create',
        name: '创建',
        description: '创建新的病案记录',
        icon: PlusOutlined,
        enabled: true,
      },
      {
        key: 'read',
        name: '查看',
        description: '查看病案记录详情',
        icon: EyeOutlined,
        enabled: true,
      },
      {
        key: 'update',
        name: '修改',
        description: '修改病案记录信息',
        icon: EditOutlined,
        enabled: true,
      },
      {
        key: 'delete',
        name: '删除',
        description: '删除病案记录',
        icon: DeleteOutlined,
        enabled: false,
      },
      {
        key: 'export',
        name: '导出',
        description: '导出病案记录数据',
        icon: DownloadOutlined,
        enabled: true,
      },
    ],
  },
  {
    key: 'qc_results',
    name: '质控结果',
    description: '质控分析结果的管理',
    icon: CheckCircleOutlined,
    color: 'text-green-500',
    enabled: true,
    actions: [
      { key: 'read', name: '查看', description: '查看质控结果', icon: EyeOutlined, enabled: true },
      {
        key: 'update',
        name: '修改',
        description: '修改质控结果',
        icon: EditOutlined,
        enabled: true,
      },
      {
        key: 'review',
        name: '审核',
        description: '审核质控结果',
        icon: AuditOutlined,
        enabled: true,
      },
      {
        key: 'export',
        name: '导出',
        description: '导出质控结果',
        icon: DownloadOutlined,
        enabled: true,
      },
    ],
  },
  {
    key: 'qc_rules',
    name: '质控规则',
    description: '质控规则的配置和管理',
    icon: SettingOutlined,
    color: 'text-purple-500',
    enabled: true,
    actions: [
      {
        key: 'create',
        name: '创建',
        description: '创建质控规则',
        icon: PlusOutlined,
        enabled: true,
      },
      { key: 'read', name: '查看', description: '查看质控规则', icon: EyeOutlined, enabled: true },
      {
        key: 'update',
        name: '修改',
        description: '修改质控规则',
        icon: EditOutlined,
        enabled: true,
      },
      {
        key: 'delete',
        name: '删除',
        description: '删除质控规则',
        icon: DeleteOutlined,
        enabled: true,
      },
      {
        key: 'manage',
        name: '管理',
        description: '管理质控规则',
        icon: ToolOutlined,
        enabled: true,
      },
    ],
  },
  {
    key: 'users',
    name: '用户管理',
    description: '系统用户的管理',
    icon: UserOutlined,
    color: 'text-orange-500',
    enabled: false,
    actions: [
      {
        key: 'create',
        name: '创建',
        description: '创建新用户',
        icon: PlusOutlined,
        enabled: false,
      },
      { key: 'read', name: '查看', description: '查看用户信息', icon: EyeOutlined, enabled: false },
      {
        key: 'update',
        name: '修改',
        description: '修改用户信息',
        icon: EditOutlined,
        enabled: false,
      },
      {
        key: 'delete',
        name: '删除',
        description: '删除用户',
        icon: DeleteOutlined,
        enabled: false,
      },
      {
        key: 'manage',
        name: '管理',
        description: '管理用户权限',
        icon: ToolOutlined,
        enabled: false,
      },
    ],
  },
  {
    key: 'statistics',
    name: '统计报表',
    description: '系统统计数据和报表',
    icon: BarChartOutlined,
    color: 'text-indigo-500',
    enabled: true,
    actions: [
      { key: 'read', name: '查看', description: '查看统计数据', icon: EyeOutlined, enabled: true },
      {
        key: 'export',
        name: '导出',
        description: '导出统计报表',
        icon: DownloadOutlined,
        enabled: true,
      },
    ],
  },
  {
    key: 'settings',
    name: '系统设置',
    description: '系统配置和设置',
    icon: SafetyCertificateOutlined,
    color: 'text-red-500',
    enabled: false,
    actions: [
      { key: 'read', name: '查看', description: '查看系统设置', icon: EyeOutlined, enabled: false },
      {
        key: 'update',
        name: '修改',
        description: '修改系统设置',
        icon: EditOutlined,
        enabled: false,
      },
      {
        key: 'manage',
        name: '管理',
        description: '管理系统配置',
        icon: ToolOutlined,
        enabled: false,
      },
    ],
  },
])

// 角色用户列表
const roleUsers = ref([
  {
    id: '1',
    email: 'admin@demo.com',
    display_name: '系统管理员',
    department: '信息科',
    is_active: true,
  },
  {
    id: '2',
    email: 'qc@demo.com',
    display_name: '质控管理员',
    department: '质控科',
    is_active: true,
  },
])

// 监听角色变化
watch(
  () => props.role,
  (newRole) => {
    if (newRole) {
      // 根据角色类型设置权限
      updatePermissionsByRole(newRole.key)
    }
  },
  { immediate: true },
)

// 方法
const updatePermissionsByRole = (roleKey: string) => {
  // 根据角色设置默认权限
  const rolePermissions: Record<string, Record<string, { enabled: boolean; actions: string[] }>> = {
    admin: {
      medical_records: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'export'] },
      qc_results: { enabled: true, actions: ['read', 'update', 'review', 'export'] },
      qc_rules: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'manage'] },
      users: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'manage'] },
      statistics: { enabled: true, actions: ['read', 'export'] },
      settings: { enabled: true, actions: ['read', 'update', 'manage'] },
    },
    qc_manager: {
      medical_records: { enabled: true, actions: ['read', 'export'] },
      qc_results: { enabled: true, actions: ['read', 'update', 'review', 'export'] },
      qc_rules: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'manage'] },
      users: { enabled: true, actions: ['read'] },
      statistics: { enabled: true, actions: ['read', 'export'] },
      settings: { enabled: false, actions: [] },
    },
    qc_staff: {
      medical_records: { enabled: true, actions: ['read'] },
      qc_results: { enabled: true, actions: ['read', 'update', 'review'] },
      qc_rules: { enabled: true, actions: ['read'] },
      users: { enabled: false, actions: [] },
      statistics: { enabled: true, actions: ['read'] },
      settings: { enabled: false, actions: [] },
    },
    doctor: {
      medical_records: { enabled: true, actions: ['create', 'read', 'update'] },
      qc_results: { enabled: true, actions: ['read'] },
      qc_rules: { enabled: false, actions: [] },
      users: { enabled: false, actions: [] },
      statistics: { enabled: true, actions: ['read'] },
      settings: { enabled: false, actions: [] },
    },
  }

  const permissions = rolePermissions[roleKey as keyof typeof rolePermissions]
  if (permissions) {
    resources.value.forEach((resource) => {
      const resourcePermission = permissions[resource.key as keyof typeof permissions]
      if (resourcePermission) {
        resource.enabled = resourcePermission.enabled
        resource.actions.forEach((action) => {
          action.enabled = resourcePermission.actions.includes(action.key)
        })
      }
    })
  }
}

const handleResourceToggle = (resourceKey: string, enabled: boolean) => {
  const resource = resources.value.find((r) => r.key === resourceKey)
  if (resource) {
    resource.enabled = enabled
    if (!enabled) {
      // 如果禁用资源，则禁用所有操作
      resource.actions.forEach((action) => {
        action.enabled = false
      })
    }
  }
}

const handleActionToggle = (resourceKey: string, actionKey: string, enabled: boolean) => {
  const resource = resources.value.find((r) => r.key === resourceKey)
  if (resource) {
    const action = resource.actions.find((a) => a.key === actionKey)
    if (action) {
      action.enabled = enabled
    }
  }
}

const handleActionChange = (resourceKey: string, actionKey: string, event: CheckboxChangeEvent) => {
  handleActionToggle(resourceKey, actionKey, !!event.target.checked)
}

const handleSubmit = async () => {
  try {
    loading.value = true

    // 收集权限配置
    const permissions = resources.value.map((resource) => ({
      resource: resource.key,
      enabled: resource.enabled,
      actions: resource.actions.filter((action) => action.enabled).map((action) => action.key),
    }))

    emit('submit', {
      role: props.role?.key,
      permissions,
    })
  } catch (error) {
    message.error('保存失败')
  } finally {
    loading.value = false
  }
}

const handleCancel = () => {
  emit('cancel')
}

const getUserAvatarColor = (email: string) => {
  const colors = ['#f56a00', '#7265e6', '#ffbf00', '#00a2ae', '#f56a00']
  const index = email.charCodeAt(0) % colors.length
  return colors[index]
}
</script>

<style scoped>
.role-edit-content {
  max-height: 600px;
  overflow-y: auto;
}

.permission-group {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
}

.permission-group:hover {
  border-color: #d9d9d9;
}

:deep(.ant-statistic-title) {
  font-size: 14px;
  color: #666;
}

:deep(.ant-statistic-content) {
  font-size: 20px;
  font-weight: 600;
}
</style>
