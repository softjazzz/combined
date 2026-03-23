<template>
  <div class="permissions-container p-8 bg-gray-50 min-h-screen">
    <!-- 页面标题 -->
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-gray-800 mb-2">
        数据权限配置
      </h1>
      <p class="text-gray-600">
        管理用户和角色的数据访问权限
      </p>
    </div>

    <!-- 权限概览 -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              用户总数
            </p>
            <p class="text-3xl font-bold text-gray-800">
              156
            </p>
          </div>
          <div class="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
            <UserOutlined class="text-blue-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              角色数量
            </p>
            <p class="text-3xl font-bold text-gray-800">
              8
            </p>
          </div>
          <div class="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
            <TeamOutlined class="text-green-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              权限规则
            </p>
            <p class="text-3xl font-bold text-gray-800">
              24
            </p>
          </div>
          <div class="w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center">
            <SafetyCertificateOutlined class="text-purple-600 text-xl" />
          </div>
        </div>
      </div>
      
      <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-gray-600 text-sm mb-1">
              活跃用户
            </p>
            <p class="text-3xl font-bold text-gray-800">
              142
            </p>
          </div>
          <div class="w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center">
            <CheckCircleOutlined class="text-orange-600 text-xl" />
          </div>
        </div>
      </div>
    </div>

    <!-- 标签页 -->
    <div class="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
      <a-tabs
        v-model:active-key="activeTab"
        type="card"
        class="custom-tabs"
      >
        <!-- 用户权限管理 -->
        <a-tab-pane
          key="users"
          tab="用户权限"
        >
          <div class="mb-6">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold text-gray-800">
                用户权限管理
              </h3>
              <a-button
                type="primary"
                class="rounded-lg"
                @click="handleAddUser"
              >
                <PlusOutlined />
                添加用户
              </a-button>
            </div>
            
            <!-- 搜索筛选 -->
            <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <a-input
                v-model:value="userSearch"
                placeholder="搜索用户名、姓名"
                class="rounded-lg"
              >
                <template #prefix>
                  <SearchOutlined class="text-gray-400" />
                </template>
              </a-input>
              
              <a-select
                v-model:value="selectedRole"
                placeholder="选择角色"
                class="rounded-lg"
                :options="roleOptions"
              />
              
              <a-select
                v-model:value="selectedDepartment"
                placeholder="选择科室"
                class="rounded-lg"
                :options="departmentOptions"
              />
              
              <a-button
                type="primary"
                class="rounded-lg"
                @click="handleUserSearch"
              >
                <SearchOutlined />
                搜索
              </a-button>
            </div>

            <!-- 用户表格 -->
            <a-table
              :columns="userColumns"
              :data-source="users"
              :loading="loading"
              :pagination="userPagination"
              row-key="id"
              class="rounded-lg"
              @change="handleUserTableChange"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'status'">
                  <a-tag :color="record.status === 'active' ? 'green' : 'red'">
                    {{ record.status === 'active' ? '活跃' : '禁用' }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'roles'">
                  <a-tag
                    v-for="role in record.roles"
                    :key="role"
                    color="blue"
                    class="mb-1"
                  >
                    {{ getRoleText(role) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'action'">
                  <div class="flex space-x-2">
                    <a-button
                      type="link"
                      size="small"
                      @click="handleEditUser(record)"
                    >
                      <EditOutlined />
                      编辑
                    </a-button>
                    <a-button
                      type="link"
                      size="small"
                      @click="handleUserPermissions(record)"
                    >
                      <SafetyCertificateOutlined />
                      权限
                    </a-button>
                    <a-button 
                      type="link" 
                      size="small" 
                      :danger="record.status === 'active'"
                      @click="handleToggleUserStatus(record)"
                    >
                      {{ record.status === 'active' ? '禁用' : '启用' }}
                    </a-button>
                  </div>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <!-- 角色权限管理 -->
        <a-tab-pane
          key="roles"
          tab="角色权限"
        >
          <div class="mb-6">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold text-gray-800">
                角色权限管理
              </h3>
              <a-button
                type="primary"
                class="rounded-lg"
                @click="handleAddRole"
              >
                <PlusOutlined />
                添加角色
              </a-button>
            </div>

            <!-- 角色卡片 -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div
                v-for="role in roles"
                :key="role.id"
                class="bg-gray-50 rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow duration-300"
              >
                <div class="flex items-center justify-between mb-4">
                  <div class="flex items-center">
                    <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
                      <TeamOutlined class="text-blue-600" />
                    </div>
                    <div>
                      <h4 class="font-semibold text-gray-800">
                        {{ role.name }}
                      </h4>
                      <p class="text-sm text-gray-600">
                        {{ role.description }}
                      </p>
                    </div>
                  </div>
                  <a-dropdown>
                    <a-button
                      type="text"
                      size="small"
                    >
                      <MoreOutlined />
                    </a-button>
                    <template #overlay>
                      <a-menu>
                        <a-menu-item @click="handleEditRole(role)">
                          <EditOutlined />
                          编辑
                        </a-menu-item>
                        <a-menu-item @click="handleRolePermissions(role)">
                          <SafetyCertificateOutlined />
                          权限设置
                        </a-menu-item>
                        <a-menu-item
                          danger
                          @click="handleDeleteRole(role)"
                        >
                          <DeleteOutlined />
                          删除
                        </a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </div>
                
                <div class="mb-4">
                  <p class="text-sm text-gray-600 mb-2">
                    用户数量: <span class="font-medium">{{ role.userCount }}</span>
                  </p>
                  <p class="text-sm text-gray-600">
                    权限数量: <span class="font-medium">{{ role.permissions?.length || 0 }}</span>
                  </p>
                </div>
                
                <div class="flex flex-wrap gap-1">
                  <a-tag
                    v-for="permission in role.permissions?.slice(0, 3)"
                    :key="permission"
                    size="small"
                  >
                    {{ getPermissionText(permission) }}
                  </a-tag>
                  <a-tag
                    v-if="role.permissions?.length > 3"
                    size="small"
                  >
                    +{{ role.permissions.length - 3 }}
                  </a-tag>
                </div>
              </div>
            </div>
          </div>
        </a-tab-pane>

        <!-- 权限规则 -->
        <a-tab-pane
          key="permissions"
          tab="权限规则"
        >
          <div class="mb-6">
            <div class="flex justify-between items-center mb-4">
              <h3 class="text-lg font-semibold text-gray-800">
                权限规则配置
              </h3>
              <a-button
                type="primary"
                class="rounded-lg"
                @click="handleAddPermission"
              >
                <PlusOutlined />
                添加权限
              </a-button>
            </div>

            <!-- 权限树 -->
            <a-tree
              v-model:checked-keys="checkedPermissions"
              :tree-data="permissionTree"
              checkable
              :default-expand-all="true"
              class="bg-gray-50 p-4 rounded-lg"
            >
              <template #title="{ title, key, type }">
                <div class="flex items-center justify-between">
                  <span>{{ title }}</span>
                  <div class="flex space-x-2">
                    <a-tag
                      :color="getPermissionTypeColor(type)"
                      size="small"
                    >
                      {{ getPermissionTypeText(type) }}
                    </a-tag>
                    <a-button
                      type="text"
                      size="small"
                      @click="handleEditPermission(key)"
                    >
                      <EditOutlined />
                    </a-button>
                  </div>
                </div>
              </template>
            </a-tree>
          </div>
        </a-tab-pane>

        <!-- 访问日志 -->
        <a-tab-pane
          key="logs"
          tab="访问日志"
        >
          <div class="mb-6">
            <h3 class="text-lg font-semibold text-gray-800 mb-4">
              访问日志
            </h3>
            
            <!-- 日志筛选 -->
            <div class="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
              <a-input
                v-model:value="logSearch"
                placeholder="搜索用户、操作"
                class="rounded-lg"
              >
                <template #prefix>
                  <SearchOutlined class="text-gray-400" />
                </template>
              </a-input>
              
              <a-select
                v-model:value="selectedLogType"
                placeholder="操作类型"
                class="rounded-lg"
                :options="logTypeOptions"
              />
              
              <a-range-picker
                v-model:value="logDateRange"
                placeholder="选择日期范围"
                class="rounded-lg"
              />
              
              <a-button
                type="primary"
                class="rounded-lg"
                @click="handleLogSearch"
              >
                <SearchOutlined />
                搜索
              </a-button>
              
              <a-button
                class="rounded-lg"
                @click="handleExportLogs"
              >
                <DownloadOutlined />
                导出
              </a-button>
            </div>

            <!-- 日志表格 -->
            <a-table
              :columns="logColumns"
              :data-source="logs"
              :loading="logLoading"
              :pagination="logPagination"
              row-key="id"
              class="rounded-lg"
              @change="handleLogTableChange"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'type'">
                  <a-tag :color="getLogTypeColor(record.type)">
                    {{ getLogTypeText(record.type) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'result'">
                  <a-tag :color="record.result === 'success' ? 'green' : 'red'">
                    {{ record.result === 'success' ? '成功' : '失败' }}
                  </a-tag>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  UserOutlined,
  TeamOutlined,
  SafetyCertificateOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  MoreOutlined,
  DownloadOutlined
} from '@ant-design/icons-vue'

interface UserRecord {
  id: number
  username: string
  name: string
  department: string
  roles: string[]
  status: 'active' | 'disabled'
  lastLogin: string
}

interface RoleRecord {
  id: number
  name: string
  description: string
  userCount: number
  permissions: string[]
}

interface PermissionTreeNode {
  title: string
  key: string
  type: string
  children?: PermissionTreeNode[]
}

interface LogRecord {
  id: number
  username: string
  type: string
  description: string
  result: 'success' | 'failed'
  ip: string
  timestamp: string
}

interface PaginationState {
  current: number
  pageSize: number
  total: number
}

// 响应式数据
const activeTab = ref('users')
const loading = ref(false)
const logLoading = ref(false)

// 用户管理相关
const userSearch = ref('')
const selectedRole = ref<string | undefined>(undefined)
const selectedDepartment = ref<string | undefined>(undefined)
const users = ref<UserRecord[]>([])
const userPagination = ref<PaginationState>({
  current: 1,
  pageSize: 10,
  total: 0
})

// 角色管理相关
const roles = ref<RoleRecord[]>([])

// 权限管理相关
const checkedPermissions = ref<string[]>([])
const permissionTree = ref<PermissionTreeNode[]>([])

// 日志管理相关
const logSearch = ref('')
const selectedLogType = ref<string | undefined>(undefined)
const logDateRange = ref<unknown[]>([])
const logs = ref<LogRecord[]>([])
const logPagination = ref<PaginationState>({
  current: 1,
  pageSize: 10,
  total: 0
})

// 选项配置
const roleOptions = [
  { value: 'admin', label: '系统管理员' },
  { value: 'qc_manager', label: '质控管理员' },
  { value: 'doctor', label: '医生' },
  { value: 'nurse', label: '护士' }
]

const departmentOptions = [
  { value: 'internal', label: '内科' },
  { value: 'surgery', label: '外科' },
  { value: 'pediatrics', label: '儿科' }
]

const logTypeOptions = [
  { value: 'login', label: '登录' },
  { value: 'logout', label: '登出' },
  { value: 'view', label: '查看' },
  { value: 'edit', label: '编辑' },
  { value: 'delete', label: '删除' }
]

// 表格列配置
const userColumns = [
  { title: '用户名', dataIndex: 'username', key: 'username', width: 120 },
  { title: '姓名', dataIndex: 'name', key: 'name', width: 100 },
  { title: '科室', dataIndex: 'department', key: 'department', width: 100 },
  { title: '角色', dataIndex: 'roles', key: 'roles', width: 150 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
  { title: '最后登录', dataIndex: 'lastLogin', key: 'lastLogin', width: 150 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
]

const logColumns = [
  { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
  { title: '操作类型', dataIndex: 'type', key: 'type', width: 100 },
  { title: '操作描述', dataIndex: 'description', key: 'description', width: 200 },
  { title: '结果', dataIndex: 'result', key: 'result', width: 80 },
  { title: 'IP地址', dataIndex: 'ip', key: 'ip', width: 120 },
  { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 150 }
]

// 工具函数
const getRoleText = (role: string) => {
  const roleMap: Record<string, string> = {
    admin: '系统管理员',
    qc_manager: '质控管理员',
    doctor: '医生',
    nurse: '护士'
  }
  return roleMap[role] || role
}

const getPermissionText = (permission: string) => {
  const permissionMap: Record<string, string> = {
    'user.view': '查看用户',
    'user.edit': '编辑用户',
    'record.view': '查看病历',
    'record.edit': '编辑病历'
  }
  return permissionMap[permission] || permission
}

const getPermissionTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    module: 'blue',
    action: 'green',
    resource: 'orange'
  }
  return colorMap[type] || 'default'
}

const getPermissionTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    module: '模块',
    action: '操作',
    resource: '资源'
  }
  return textMap[type] || type
}

const getLogTypeColor = (type: string) => {
  const colorMap: Record<string, string> = {
    login: 'green',
    logout: 'blue',
    view: 'cyan',
    edit: 'orange',
    delete: 'red'
  }
  return colorMap[type] || 'default'
}

const getLogTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    login: '登录',
    logout: '登出',
    view: '查看',
    edit: '编辑',
    delete: '删除'
  }
  return textMap[type] || type
}

// 事件处理函数
const handleAddUser = () => {
  message.info('添加用户')
}

const handleUserSearch = () => {
  fetchUsers()
}

const handleEditUser = (record: UserRecord) => {
  message.info(`编辑用户: ${record.name}`)
}

const handleUserPermissions = (record: UserRecord) => {
  message.info(`设置用户权限: ${record.name}`)
}

const handleToggleUserStatus = (record: UserRecord) => {
  const action = record.status === 'active' ? '禁用' : '启用'
  message.info(`${action}用户: ${record.name}`)
}

const handleUserTableChange = (pag: Partial<PaginationState>) => {
  userPagination.value = { ...userPagination.value, ...pag }
  fetchUsers()
}

const handleAddRole = () => {
  message.info('添加角色')
}

const handleEditRole = (role: RoleRecord) => {
  message.info(`编辑角色: ${role.name}`)
}

const handleRolePermissions = (role: RoleRecord) => {
  message.info(`设置角色权限: ${role.name}`)
}

const handleDeleteRole = (role: RoleRecord) => {
  message.info(`删除角色: ${role.name}`)
}

const handleAddPermission = () => {
  message.info('添加权限')
}

const handleEditPermission = (key: string) => {
  message.info(`编辑权限: ${key}`)
}

const handleLogSearch = () => {
  fetchLogs()
}

const handleExportLogs = () => {
  message.info('导出日志')
}

const handleLogTableChange = (pag: Partial<PaginationState>) => {
  logPagination.value = { ...logPagination.value, ...pag }
  fetchLogs()
}

// 数据获取函数
const fetchUsers = async () => {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    users.value = [
      {
        id: 1,
        username: 'zhangsan',
        name: '张三',
        department: '内科',
        roles: ['doctor'],
        status: 'active',
        lastLogin: '2024-01-16 10:30:00'
      },
      {
        id: 2,
        username: 'lisi',
        name: '李四',
        department: '外科',
        roles: ['qc_manager'],
        status: 'active',
        lastLogin: '2024-01-16 09:15:00'
      }
    ]
    
    userPagination.value.total = 50
  } catch (error) {
    message.error('获取用户数据失败')
  } finally {
    loading.value = false
  }
}

const fetchRoles = async () => {
  try {
    roles.value = [
      {
        id: 1,
        name: '系统管理员',
        description: '拥有系统所有权限',
        userCount: 5,
        permissions: ['user.view', 'user.edit', 'record.view', 'record.edit']
      },
      {
        id: 2,
        name: '质控管理员',
        description: '负责质控相关功能',
        userCount: 12,
        permissions: ['record.view', 'record.edit']
      }
    ]
  } catch (error) {
    message.error('获取角色数据失败')
  }
}

const fetchPermissions = async () => {
  try {
    permissionTree.value = [
      {
        title: '用户管理',
        key: 'user',
        type: 'module',
        children: [
          { title: '查看用户', key: 'user.view', type: 'action' },
          { title: '编辑用户', key: 'user.edit', type: 'action' }
        ]
      },
      {
        title: '病历管理',
        key: 'record',
        type: 'module',
        children: [
          { title: '查看病历', key: 'record.view', type: 'action' },
          { title: '编辑病历', key: 'record.edit', type: 'action' }
        ]
      }
    ]
  } catch (error) {
    message.error('获取权限数据失败')
  }
}

const fetchLogs = async () => {
  logLoading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    
    logs.value = [
      {
        id: 1,
        username: '张三',
        type: 'login',
        description: '用户登录系统',
        result: 'success',
        ip: '192.168.1.100',
        timestamp: '2024-01-16 10:30:00'
      },
      {
        id: 2,
        username: '李四',
        type: 'view',
        description: '查看病历 R2024001',
        result: 'success',
        ip: '192.168.1.101',
        timestamp: '2024-01-16 10:25:00'
      }
    ]
    
    logPagination.value.total = 200
  } catch (error) {
    message.error('获取日志数据失败')
  } finally {
    logLoading.value = false
  }
}

onMounted(() => {
  fetchUsers()
  fetchRoles()
  fetchPermissions()
  fetchLogs()
})
</script>

<style scoped>
:deep(.ant-tabs-card .ant-tabs-tab) {
  border-radius: 8px 8px 0 0;
}

:deep(.ant-table-thead > tr > th) {
  background-color: #f8fafc;
  border-bottom: 1px solid #e5e7eb;
}

:deep(.ant-table-tbody > tr:hover > td) {
  background-color: #f8fafc;
}

:deep(.ant-btn-link) {
  padding: 0 4px;
}

:deep(.ant-tree .ant-tree-node-content-wrapper) {
  padding: 4px 8px;
  border-radius: 6px;
}
</style>
