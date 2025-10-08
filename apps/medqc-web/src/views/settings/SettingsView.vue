<template>
  <div class="settings-container min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
    <!-- 页面头部 -->
    <div class="max-w-7xl mx-auto px-6 py-6">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center space-x-4">
          <SettingOutlined class="text-3xl text-blue-600" />
          <div>
            <h1 class="text-2xl font-bold text-gray-900">系统设置</h1>
            <p class="text-gray-600">用户权限管理和系统配置</p>
          </div>
        </div>

        <div class="flex space-x-3">
          <a-button @click="exportConfig">
            <DownloadOutlined />
            导出配置
          </a-button>
          <a-button @click="importConfig">
            <UploadOutlined />
            导入配置
          </a-button>
        </div>
      </div>

      <!-- 设置导航 -->
      <div class="mb-6">
        <a-card class="bg-white/80 backdrop-blur-sm border-0 shadow-xl">
          <a-tabs v-model:activeKey="activeTab" type="card" class="settings-tabs">
            <a-tab-pane key="users" tab="用户管理">
              <template #tab>
                <UserOutlined class="mr-2" />
                用户管理
              </template>
            </a-tab-pane>
            <a-tab-pane key="roles" tab="角色管理">
              <template #tab>
                <TeamOutlined class="mr-2" />
                角色管理
              </template>
            </a-tab-pane>
            <a-tab-pane key="permissions" tab="权限配置">
              <template #tab>
                <SafetyCertificateOutlined class="mr-2" />
                权限配置
              </template>
            </a-tab-pane>
            <a-tab-pane key="system" tab="系统配置">
              <template #tab>
                <SettingOutlined class="mr-2" />
                系统配置
              </template>
            </a-tab-pane>
            <a-tab-pane key="llm" tab="LLM配置">
              <template #tab>
                <ApiOutlined class="mr-2" />
                LLM配置
              </template>
            </a-tab-pane>
            <a-tab-pane key="classification" tab="分类算法">
              <template #tab>
                <BranchesOutlined class="mr-2" />
                分类算法
              </template>
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </div>

      <!-- 用户管理 -->
      <div v-if="activeTab === 'users'">
        <a-card
          title="用户管理"
          class="bg-white/80 backdrop-blur-sm border-0 shadow-xl"
        >
          <template #extra>
            <a-space>
              <a-button
                type="primary"
                @click="showCreateUserModal"
                :icon="h(PlusOutlined)"
              >
                新增用户
              </a-button>
              <a-button
                @click="refreshUsers"
                :loading="loading.users"
                :icon="h(ReloadOutlined)"
              >
                刷新
              </a-button>
            </a-space>
          </template>

          <!-- 用户搜索 -->
          <div class="mb-4">
            <a-row :gutter="16">
              <a-col :span="8">
                <a-input
                  v-model:value="userSearch.email"
                  placeholder="搜索邮箱"
                  allow-clear
                  @change="handleUserSearch"
                >
                  <template #prefix>
                    <SearchOutlined class="text-gray-400" />
                  </template>
                </a-input>
              </a-col>
              <a-col :span="6">
                <a-select
                  v-model:value="userSearch.role"
                  placeholder="筛选角色"
                  allow-clear
                  @change="handleUserSearch"
                >
                  <a-select-option value="">全部角色</a-select-option>
                  <a-select-option value="admin">管理员</a-select-option>
                  <a-select-option value="qc_manager">质控管理员</a-select-option>
                  <a-select-option value="qc_staff">质控人员</a-select-option>
                  <a-select-option value="doctor">医务人员</a-select-option>
                </a-select>
              </a-col>
              <a-col :span="6">
                <a-select
                  v-model:value="userSearch.status"
                  placeholder="筛选状态"
                  allow-clear
                  @change="handleUserSearch"
                >
                  <a-select-option value="">全部状态</a-select-option>
                  <a-select-option value="active">激活</a-select-option>
                  <a-select-option value="inactive">停用</a-select-option>
                </a-select>
              </a-col>
            </a-row>
          </div>

          <!-- 用户表格 -->
          <a-table
            :columns="userColumns"
            :dataSource="filteredUsers"
            :loading="loading.users"
            :pagination="{ pageSize: 10 }"
            row-key="id"
          >
            <template #bodyCell="{ column, record }">
              <!-- 用户信息 -->
              <template v-if="column.key === 'user_info'">
                <div class="flex items-center space-x-3">
                  <a-avatar :size="40" :style="{ backgroundColor: getUserAvatarColor(record.email) }">
                    {{ record.display_name?.charAt(0) || record.email?.charAt(0) }}
                  </a-avatar>
                  <div>
                    <div class="font-medium">{{ record.display_name || record.email }}</div>
                    <div class="text-sm text-gray-500">{{ record.email }}</div>
                  </div>
                </div>
              </template>

              <!-- 角色标签 -->
              <template v-else-if="column.key === 'roles'">
                <div class="space-y-1">
                  <a-tag
                    v-for="role in record.roles"
                    :key="role"
                    :color="getRoleColor(role)"
                    class="mb-1"
                  >
                    {{ getRoleText(role) }}
                  </a-tag>
                </div>
              </template>

              <!-- 部门信息 -->
              <template v-else-if="column.key === 'department'">
                <div>
                  <div class="font-medium">{{ record.department || '-' }}</div>
                  <div class="text-sm text-gray-500">{{ record.hospital_name || '全院' }}</div>
                </div>
              </template>

              <!-- 状态 -->
              <template v-else-if="column.key === 'status'">
                <a-badge
                  :status="record.is_active ? 'success' : 'default'"
                  :text="record.is_active ? '激活' : '停用'"
                />
              </template>

              <!-- 最后登录 -->
              <template v-else-if="column.key === 'last_login'">
                <div v-if="record.last_login">
                  {{ formatDateTime(record.last_login) }}
                </div>
                <span v-else class="text-gray-400">从未登录</span>
              </template>

              <!-- 操作按钮 -->
              <template v-else-if="column.key === 'actions'">
                <a-space size="small">
                  <a-button
                    type="link"
                    size="small"
                    @click="editUser(record)"
                  >
                    编辑
                  </a-button>
                  <a-button
                    type="link"
                    size="small"
                    @click="toggleUserStatus(record)"
                    :class="record.is_active ? 'text-red-500' : 'text-green-500'"
                  >
                    {{ record.is_active ? '停用' : '激活' }}
                  </a-button>
                  <a-button
                    type="link"
                    size="small"
                    danger
                    @click="deleteUser(record)"
                  >
                    删除
                  </a-button>
                </a-space>
              </template>
            </template>
          </a-table>
        </a-card>
      </div>

      <!-- 角色管理 -->
      <div v-if="activeTab === 'roles'">
        <a-card
          title="角色管理"
          class="bg-white/80 backdrop-blur-sm border-0 shadow-xl"
        >
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <div v-for="role in roles" :key="role.key" class="role-card">
              <a-card
                :class="['h-full', 'transition-all', 'duration-300', 'hover:shadow-lg', 'cursor-pointer']"
                @click="editRole(role)"
              >
                <div class="text-center">
                  <div class="mb-4">
                    <component
                      :is="role.icon"
                      :class="['text-4xl', role.color]"
                    />
                  </div>
                  <h3 class="text-lg font-semibold mb-2">{{ role.name }}</h3>
                  <p class="text-gray-600 text-sm mb-4">{{ role.description }}</p>
                  <div class="space-y-2">
                    <div class="flex justify-between text-sm">
                      <span>用户数量:</span>
                      <span class="font-medium">{{ role.userCount }}人</span>
                    </div>
                    <div class="flex justify-between text-sm">
                      <span>权限数量:</span>
                      <span class="font-medium">{{ role.permissionCount }}项</span>
                    </div>
                  </div>
                </div>
              </a-card>
            </div>
          </div>
        </a-card>
      </div>

      <!-- 权限配置 -->
      <div v-if="activeTab === 'permissions'">
        <a-card
          title="权限配置"
          class="bg-white/80 backdrop-blur-sm border-0 shadow-xl"
        >
          <div class="mb-6">
            <a-alert
              message="权限配置说明"
              description="以下是系统各角色的权限配置矩阵，您可以根据需要调整各角色的权限设置。"
              type="info"
              show-icon
              class="mb-4"
            />
          </div>

          <!-- 权限矩阵 -->
          <div class="permission-matrix">
            <a-table
              :columns="permissionColumns"
              :data-source="permissionMatrix"
              :pagination="false"
              bordered
              size="small"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key !== 'resource'">
                  <a-checkbox
                    v-model:checked="record[column.key]"
                    @change="handlePermissionChange(record.resource, column.key, $event)"
                  />
                </template>
              </template>
            </a-table>
          </div>
        </a-card>
      </div>

      <!-- 系统配置 -->
      <div v-if="activeTab === 'system'">
        <a-card
          title="系统配置"
          class="bg-white/80 backdrop-blur-sm border-0 shadow-xl"
        >
          <a-form :model="systemConfig" layout="vertical">
            <a-row :gutter="24">
              <a-col :span="12">
                <a-form-item label="系统名称">
                  <a-input v-model:value="systemConfig.systemName" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="系统版本">
                  <a-input v-model:value="systemConfig.version" readonly />
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="24">
              <a-col :span="12">
                <a-form-item label="会话超时时间(分钟)">
                  <a-input-number
                    v-model:value="systemConfig.sessionTimeout"
                    :min="5"
                    :max="1440"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="密码最小长度">
                  <a-input-number
                    v-model:value="systemConfig.passwordMinLength"
                    :min="6"
                    :max="20"
                    style="width: 100%"
                  />
                </a-form-item>
              </a-col>
            </a-row>

            <a-row :gutter="24">
              <a-col :span="12">
                <a-form-item label="启用多因素认证">
                  <a-switch v-model:checked="systemConfig.enableMFA" />
                </a-form-item>
              </a-col>
              <a-col :span="12">
                <a-form-item label="启用审计日志">
                  <a-switch v-model:checked="systemConfig.enableAuditLog" />
                </a-form-item>
              </a-col>

              <a-divider orientation="left">LLM 解析优化</a-divider>
              <a-row :gutter="24">
                <a-col :span="12">
                  <a-form-item label="启用指针模式（Pointer Mode）">
                    <a-switch v-model:checked="systemConfig.llmPointerMode" />
                  </a-form-item>
                </a-col>
                <a-col :span="12">
                  <a-form-item label="摘要长度上限">
                    <a-select v-model:value="systemConfig.llmSummaryMaxLen" style="width: 100%">
                      <a-select-option :value="0">禁用摘要（0）</a-select-option>
                      <a-select-option :value="40">40 字符</a-select-option>
                      <a-select-option :value="80">80 字符</a-select-option>
                    </a-select>
                  </a-form-item>
                </a-col>
              </a-row>

            </a-row>

            <a-form-item>
              <a-button
                type="primary"
                @click="saveSystemConfig"
                :loading="loading.systemConfig"
              >
                保存配置
              </a-button>
            </a-form-item>
          </a-form>
        </a-card>
      </div>

      <!-- 分类算法管理 -->
      <div v-if="activeTab === 'classification'">
        <ClassificationVersionManager />
      </div>
    </div>

    <!-- 用户编辑模态框 -->
    <UserEditModal
      :visible="modals.userEdit"
      :user="selectedUser"
      @submit="handleUserSubmit"
      @cancel="modals.userEdit = false"
      @update:visible="(val: boolean) => modals.userEdit = val"
    />

    <!-- 角色编辑模态框 -->
    <RoleEditModal
      :visible="modals.roleEdit"
      :role="selectedRole"
      @submit="handleRoleSubmit"
      @cancel="modals.roleEdit = false"
      @update:visible="(val: boolean) => modals.roleEdit = val"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, h } from 'vue'
import { message } from 'ant-design-vue'
import {
  SettingOutlined,
  UserOutlined,
  TeamOutlined,
  SafetyCertificateOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined,
  CrownOutlined,
  SafetyOutlined,
  MedicineBoxOutlined,
  DownloadOutlined,
  UploadOutlined,
  BranchesOutlined,
  ApiOutlined
} from '@ant-design/icons-vue'

// 导入组件
import UserEditModal from '@/components/settings/UserEditModal.vue'
import RoleEditModal from '@/components/settings/RoleEditModal.vue'
import ClassificationVersionManager from '@/components/settings/ClassificationVersionManager.vue'

// 页面状态
const activeTab = ref('users')
const loading = reactive({
  users: false,
  roles: false,
  permissions: false,
  systemConfig: false
})

// 模态框状态
const modals = reactive({
  userEdit: false,
  roleEdit: false
})

// 选中的数据
const selectedUser = ref(null)
const selectedRole = ref(null)

// 用户管理相关
const users = ref([
  {
    id: '1',
    email: 'admin@demo.com',
    display_name: '系统管理员',
    roles: ['admin'],
    department: '信息科',
    hospital_name: '示例医院',
    is_active: true,
    last_login: new Date().toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: '2',
    email: 'qc@demo.com',
    display_name: '质控管理员',
    roles: ['qc_manager'],
    department: '质控科',
    hospital_name: '示例医院',
    is_active: true,
    last_login: new Date(Date.now() - 86400000).toISOString(),
    created_at: new Date().toISOString()
  },
  {
    id: '3',
    email: 'doctor@demo.com',
    display_name: '医务人员',
    roles: ['doctor'],
    department: '内科',
    hospital_name: '示例医院',
    is_active: true,
    last_login: new Date(Date.now() - 3600000).toISOString(),
    created_at: new Date().toISOString()
  }
])

const userSearch = reactive({
  email: '',
  role: '',
  status: ''
})

// 角色管理相关
const roles = ref([
  {
    key: 'admin',
    name: '系统管理员',
    description: '拥有系统全部权限，可以管理用户、角色和系统配置',
    icon: CrownOutlined,
    color: 'text-orange-500',
    userCount: 2,
    permissionCount: 25
  },
  {
    key: 'qc_manager',
    name: '质控管理员',
    description: '负责质控规则管理和质控流程监督',
    icon: SafetyOutlined,
    color: 'text-blue-500',
    userCount: 5,
    permissionCount: 18
  },
  {
    key: 'qc_staff',
    name: '质控人员',
    description: '执行质控分析和审核工作',
    icon: SafetyCertificateOutlined,
    color: 'text-green-500',
    userCount: 12,
    permissionCount: 10
  },
  {
    key: 'doctor',
    name: '医务人员',
    description: '上传和管理自己的病案记录',
    icon: MedicineBoxOutlined,
    color: 'text-purple-500',
    userCount: 45,
    permissionCount: 6
  }
])

// 权限配置相关
const permissionMatrix = ref([
  {
    resource: '病案记录',
    admin: true,
    qc_manager: true,
    qc_staff: true,
    doctor: true
  },
  {
    resource: '质控结果',
    admin: true,
    qc_manager: true,
    qc_staff: true,
    doctor: false
  },
  {
    resource: '质控规则',
    admin: true,
    qc_manager: true,
    qc_staff: false,
    doctor: false
  },
  {
    resource: '用户管理',
    admin: true,
    qc_manager: false,
    qc_staff: false,
    doctor: false
  },
  {
    resource: '统计报表',
    admin: true,
    qc_manager: true,
    qc_staff: true,
    doctor: false
  },
  {
    resource: '系统设置',
    admin: true,
    qc_manager: false,
    qc_staff: false,
    doctor: false
  }
])

// 系统配置
const systemConfig = reactive({
  systemName: '病案质控系统',
  version: '1.0.0',
  sessionTimeout: 30,
  passwordMinLength: 6,
  enableMFA: false,
  enableAuditLog: true,
  llmPointerMode: true,
  llmSummaryMaxLen: 80
})

// 用户表格列配置
const userColumns = [
  {
    title: '用户信息',
    key: 'user_info',
    width: 250
  },
  {
    title: '角色',
    key: 'roles',
    width: 150
  },
  {
    title: '部门',
    key: 'department',
    width: 150
  },
  {
    title: '状态',
    key: 'status',
    width: 100
  },
  {
    title: '最后登录',
    key: 'last_login',
    width: 150
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    fixed: 'right'
  }
]

// 权限表格列配置
const permissionColumns = [
  {
    title: '资源',
    dataIndex: 'resource',
    key: 'resource',
    width: 150
  },
  {
    title: '管理员',
    key: 'admin',
    width: 100,
    align: 'center'
  },
  {
    title: '质控管理员',
    key: 'qc_manager',
    width: 120,
    align: 'center'
  },
  {
    title: '质控人员',
    key: 'qc_staff',
    width: 100,
    align: 'center'
  },
  {
    title: '医务人员',
    key: 'doctor',
    width: 100,
    align: 'center'
  }
]

// 计算属性
const filteredUsers = computed(() => {
  return users.value.filter(user => {
    const emailMatch = !userSearch.email || user.email?.toLowerCase().includes(userSearch.email.toLowerCase())
    const roleMatch = !userSearch.role || user.roles?.includes(userSearch.role)
    const statusMatch = !userSearch.status || (userSearch.status === 'active' ? user.is_active : !user.is_active)

    return emailMatch && roleMatch && statusMatch
  })
})

// 方法
const refreshUsers = async () => {
  loading.users = true
  try {
    // TODO: 从数据库获取用户列表
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('用户列表已刷新')
  } catch (error) {
    message.error('获取用户列表失败')
  } finally {
    loading.users = false
  }
}

const handleUserSearch = () => {
  // 搜索逻辑在computed中处理
}

const showCreateUserModal = () => {
  selectedUser.value = null
  modals.userEdit = true
}

const editUser = (user: unknown) => {
  selectedUser.value = user
  modals.userEdit = true
}

const editRole = (role: unknown) => {
  selectedRole.value = role
  modals.roleEdit = true
}

const toggleUserStatus = async (user: unknown) => {
  try {
    user.is_active = !user.is_active
    message.success(`用户已${user.is_active ? '激活' : '停用'}`)
  } catch (error) {
    message.error('操作失败')
  }
}

const deleteUser = (user: unknown) => {
  message.info('删除用户功能开发中')
}

const handleUserSubmit = async (userData: unknown) => {
  try {
    message.success('用户保存成功')
    modals.userEdit = false
    refreshUsers()
  } catch (error) {
    message.error('保存失败')
  }
}

const handleRoleSubmit = async (roleData: unknown) => {
  try {
    message.success('角色保存成功')
    modals.roleEdit = false
  } catch (error) {
    message.error('保存失败')
  }
}

const handlePermissionChange = (resource: string, role: string, checked: boolean) => {
  message.info(`${resource} - ${role}: ${checked ? '授权' : '取消授权'}`)
}

const saveSystemConfig = async () => {
  loading.systemConfig = true
  try {
    // 将配置同步到运行时 LLM 服务
    const { llmService } = await import('@/services/llmService')
    const pointerMode = !!systemConfig.llmPointerMode
    const summaryMaxLength = Number(systemConfig.llmSummaryMaxLen) || 0
    llmService.updateConfig({ pointerMode, summaryMaxLength })

    // 全局持久化到 Supabase（user_id=null）
    const { llmConfigService } = await import('@/services/llmConfigService')
    await llmConfigService.saveUserPointerPrefs({ pointerMode, summaryMaxLength })

    await new Promise(resolve => setTimeout(resolve, 600))
    message.success('系统配置保存成功（已全局持久化至数据库）')
  } catch (error) {
    message.error('保存失败')
  } finally {
    loading.systemConfig = false
  }
}

const exportConfig = () => {
  message.info('导出配置功能开发中')
}

const importConfig = () => {
  message.info('导入配置功能开发中')
}

// 工具函数
const getUserAvatarColor = (email: string) => {
  const colors = ['#f56a00', '#7265e6', '#ffbf00', '#00a2ae', '#f56a00']
  const index = email.charCodeAt(0) % colors.length
  return colors[index]
}

const getRoleColor = (role: string) => {
  const colorMap: Record<string, string> = {
    'admin': 'orange',
    'qc_manager': 'blue',
    'qc_staff': 'green',
    'doctor': 'purple'
  }
  return colorMap[role] || 'default'
}

const getRoleText = (role: string) => {
  const textMap: Record<string, string> = {
    'admin': '管理员',
    'qc_manager': '质控管理员',
    'qc_staff': '质控人员',
    'doctor': '医务人员'
  }
  return textMap[role] || role
}

const formatDateTime = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

// 组件挂载
onMounted(async () => {
  // 启动时尝试从全局持久化中恢复配置
  try {
    const { llmConfigService } = await import('@/services/llmConfigService')
    const prefs = await llmConfigService.getUserPointerPrefs()
    if (prefs) {
      systemConfig.llmPointerMode = !!prefs.pointerMode
      systemConfig.llmSummaryMaxLen = Number(prefs.summaryMaxLength) || 0
      const { llmService } = await import('@/services/llmService')
      llmService.updateConfig(prefs)
    }
  } catch (e) {
    console.warn('加载全局LLM解析优化配置失败（可忽略）:', e)
  }
})
</script>

<style scoped>
.settings-container {
  min-height: 100vh;
}

:deep(.settings-tabs .ant-tabs-tab) {
  padding: 12px 24px;
  font-weight: 500;
}

:deep(.settings-tabs .ant-tabs-tab-active) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 8px 8px 0 0;
}

.role-card {
  transition: all 0.3s ease;
}

.role-card:hover {
  transform: translateY(-2px);
}

.permission-matrix {
  overflow-x: auto;
}

:deep(.permission-matrix .ant-table-thead > tr > th) {
  background: #f8fafc;
  font-weight: 600;
}

:deep(.permission-matrix .ant-checkbox-wrapper) {
  display: flex;
  justify-content: center;
}
</style>
