<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import type { TableColumnsType } from 'ant-design-vue'
import {
  UserOutlined,
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SearchOutlined,
  ReloadOutlined,
  SettingOutlined,
  CrownOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons-vue'
import PermissionGuard from '@/components/auth/PermissionGuard.vue'
import PermissionButton from '@/components/auth/PermissionButton.vue'
// import { usePermissions } from '@/composables/usePermissions'

// 临时用户数据类型
interface User {
  id: string
  email: string
  display_name: string
  department: string
  roles: string[]
  status: 'active' | 'inactive' | 'locked'
  last_login?: string
  created_at: string
}

// 模拟用户数据
const users = ref<User[]>([
  {
    id: '1',
    email: 'admin@demo.com',
    display_name: '系统管理员',
    department: '信息科',
    roles: ['admin'],
    status: 'active',
    last_login: '2024-01-15 10:30:00',
    created_at: '2024-01-01 00:00:00',
  },
  {
    id: '2',
    email: 'qc@demo.com',
    display_name: '质控管理员',
    department: '质控科',
    roles: ['qc_manager'],
    status: 'active',
    last_login: '2024-01-15 09:15:00',
    created_at: '2024-01-02 00:00:00',
  },
  {
    id: '3',
    email: 'doctor@demo.com',
    display_name: '医务人员',
    department: '内科',
    roles: ['doctor'],
    status: 'active',
    last_login: '2024-01-15 08:45:00',
    created_at: '2024-01-03 00:00:00',
  },
])

// 搜索和过滤
const searchForm = reactive({
  keyword: '',
  department: '',
  role: '',
  status: '',
})

const loading = ref(false)
const selectedRowKeys = ref<string[]>([])
const asUser = (record: Record<string, any>) => record as User

// 过滤后的用户列表
const filteredUsers = computed(() => {
  return users.value.filter((user) => {
    const matchKeyword =
      !searchForm.keyword ||
      user.display_name.includes(searchForm.keyword) ||
      user.email.includes(searchForm.keyword)

    const matchDepartment = !searchForm.department || user.department === searchForm.department
    const matchRole = !searchForm.role || user.roles.includes(searchForm.role)
    const matchStatus = !searchForm.status || user.status === searchForm.status

    return matchKeyword && matchDepartment && matchRole && matchStatus
  })
})

// 表格列定义
const columns: TableColumnsType<User> = [
  {
    title: '用户信息',
    dataIndex: 'display_name',
    key: 'display_name',
    width: 200,
    customRender: ({ record }: { record: User }) => ({
      children: [
        {
          type: 'div',
          props: { class: 'user-info' },
          children: [
            {
              type: 'div',
              props: { class: 'user-name' },
              children: record.display_name,
            },
            {
              type: 'div',
              props: { class: 'user-email' },
              children: record.email,
            },
          ],
        },
      ],
    }),
  },
  {
    title: '科室',
    dataIndex: 'department',
    key: 'department',
    width: 120,
  },
  {
    title: '角色',
    dataIndex: 'roles',
    key: 'roles',
    width: 150,
    customRender: ({ record }: { record: User }) => record.roles.map((role) => getRoleTag(role)),
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    customRender: ({ record }: { record: User }) => getStatusTag(record.status),
  },
  {
    title: '最后登录',
    dataIndex: 'last_login',
    key: 'last_login',
    width: 150,
  },
  {
    title: '创建时间',
    dataIndex: 'created_at',
    key: 'created_at',
    width: 150,
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    fixed: 'right' as const,
  },
]

// 获取角色标签
const getRoleTag = (role: string) => {
  const roleConfig = {
    admin: { color: 'red', text: '管理员', icon: CrownOutlined },
    qc_manager: { color: 'blue', text: '质控管理员', icon: SafetyCertificateOutlined },
    qc_staff: { color: 'green', text: '质控人员', icon: SettingOutlined },
    doctor: { color: 'orange', text: '医务人员', icon: UserOutlined },
  }

  return (
    roleConfig[role as keyof typeof roleConfig] || {
      color: 'default',
      text: role,
      icon: UserOutlined,
    }
  )
}

// 获取状态标签
const getStatusTag = (status: string) => {
  const statusConfig = {
    active: { color: 'success', text: '正常' },
    inactive: { color: 'default', text: '停用' },
    locked: { color: 'error', text: '锁定' },
  }

  return statusConfig[status as keyof typeof statusConfig] || { color: 'default', text: status }
}

// 新增用户
const showCreateModal = ref(false)
const createForm = reactive({
  email: '',
  display_name: '',
  department: '',
  roles: [] as string[],
  password: '',
})

const handleCreateUser = () => {
  showCreateModal.value = true
  Object.assign(createForm, {
    email: '',
    display_name: '',
    department: '',
    roles: [],
    password: '',
  })
}

const handleCreateSubmit = () => {
  // 模拟创建用户
  const newUser: User = {
    id: Date.now().toString(),
    email: createForm.email,
    display_name: createForm.display_name,
    department: createForm.department,
    roles: createForm.roles,
    status: 'active',
    created_at: new Date().toISOString(),
  }

  users.value.unshift(newUser)
  showCreateModal.value = false
  message.success('用户创建成功')
}

// 编辑用户
const showEditModal = ref(false)
const editForm = reactive<{
  id: string
  email: string
  display_name: string
  department: string
  roles: string[]
  status: User['status']
}>({
  id: '',
  email: '',
  display_name: '',
  department: '',
  roles: [],
  status: 'active',
})

const handleEditUser = (user: User) => {
  showEditModal.value = true
  Object.assign(editForm, {
    id: user.id,
    email: user.email,
    display_name: user.display_name,
    department: user.department,
    roles: [...user.roles],
    status: user.status,
  })
}

const handleEditSubmit = () => {
  const userIndex = users.value.findIndex((u) => u.id === editForm.id)
  if (userIndex !== -1) {
    users.value[userIndex] = {
      ...users.value[userIndex],
      email: editForm.email,
      display_name: editForm.display_name,
      department: editForm.department,
      roles: editForm.roles,
      status: editForm.status,
    }
    showEditModal.value = false
    message.success('用户更新成功')
  }
}

// 删除用户
const handleDeleteUser = (user: User) => {
  const userIndex = users.value.findIndex((u) => u.id === user.id)
  if (userIndex !== -1) {
    users.value.splice(userIndex, 1)
    message.success('用户删除成功')
  }
}

// 批量删除
const handleBatchDelete = () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请选择要删除的用户')
    return
  }

  users.value = users.value.filter((user) => !selectedRowKeys.value.includes(user.id))
  selectedRowKeys.value = []
  message.success('批量删除成功')
}

// 重置密码
const handleResetPassword = (user: User) => {
  message.success(`已为用户 ${user.display_name} 重置密码`)
}

// 刷新数据
const handleRefresh = () => {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    message.success('数据刷新成功')
  }, 1000)
}

// 搜索
const handleSearch = () => {
  // 搜索逻辑已在computed中实现
  message.success('搜索完成')
}

// 重置搜索
const handleResetSearch = () => {
  Object.assign(searchForm, {
    keyword: '',
    department: '',
    role: '',
    status: '',
  })
}

// 选择变化
const onSelectChange = (selectedKeys: string[]) => {
  selectedRowKeys.value = selectedKeys
}

// 组件挂载
onMounted(() => {
  // 初始化数据
})
</script>

<template>
  <div class="user-management-view">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">
        <UserOutlined class="title-icon" />
        用户管理
      </h1>
      <p class="page-description">
        管理系统用户账户、角色和权限
      </p>
    </div>

    <!-- 搜索表单 -->
    <a-card
      class="search-card"
      :bordered="false"
    >
      <a-form
        layout="inline"
        :model="searchForm"
      >
        <a-form-item label="关键词">
          <a-input
            v-model:value="searchForm.keyword"
            placeholder="用户名或邮箱"
            allow-clear
            style="width: 200px"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>
        </a-form-item>

        <a-form-item label="科室">
          <a-select
            v-model:value="searchForm.department"
            placeholder="请选择科室"
            allow-clear
            style="width: 150px"
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
          </a-select>
        </a-form-item>

        <a-form-item label="角色">
          <a-select
            v-model:value="searchForm.role"
            placeholder="请选择角色"
            allow-clear
            style="width: 150px"
          >
            <a-select-option value="admin">
              管理员
            </a-select-option>
            <a-select-option value="qc_manager">
              质控管理员
            </a-select-option>
            <a-select-option value="qc_staff">
              质控人员
            </a-select-option>
            <a-select-option value="doctor">
              医务人员
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="状态">
          <a-select
            v-model:value="searchForm.status"
            placeholder="请选择状态"
            allow-clear
            style="width: 120px"
          >
            <a-select-option value="active">
              正常
            </a-select-option>
            <a-select-option value="inactive">
              停用
            </a-select-option>
            <a-select-option value="locked">
              锁定
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item>
          <a-button
            type="primary"
            @click="handleSearch"
          >
            <SearchOutlined />
            搜索
          </a-button>
          <a-button
            style="margin-left: 8px"
            @click="handleResetSearch"
          >
            重置
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>

    <!-- 操作工具栏 -->
    <a-card
      class="toolbar-card"
      :bordered="false"
    >
      <div class="toolbar">
        <div class="toolbar-left">
          <PermissionButton
            resource="users"
            action="create"
            type="primary"
            @click="handleCreateUser"
          >
            <PlusOutlined />
            新增用户
          </PermissionButton>

          <PermissionButton
            resource="users"
            action="delete"
            danger
            :disabled="selectedRowKeys.length === 0"
            @click="handleBatchDelete"
          >
            <DeleteOutlined />
            批量删除
          </PermissionButton>
        </div>

        <div class="toolbar-right">
          <a-button
            :loading="loading"
            @click="handleRefresh"
          >
            <ReloadOutlined />
            刷新
          </a-button>
        </div>
      </div>
    </a-card>

    <!-- 用户表格 -->
    <a-card :bordered="false">
      <a-table
        :columns="columns"
        :data-source="filteredUsers"
        :loading="loading"
        :pagination="{
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total: number) => `共 ${total} 条记录`,
        }"
        :row-selection="{
          selectedRowKeys,
          onChange: onSelectChange,
        }"
        row-key="id"
        size="middle"
      >
        <!-- 用户信息列 -->
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'display_name'">
            <div class="user-info">
              <div class="user-name">
                {{ asUser(record).display_name }}
              </div>
              <div class="user-email">
                {{ asUser(record).email }}
              </div>
            </div>
          </template>

          <!-- 角色列 -->
          <template v-else-if="column.key === 'roles'">
            <div class="role-tags">
              <a-tag
                v-for="role in asUser(record).roles"
                :key="role"
                :color="getRoleTag(role).color"
                class="role-tag"
              >
                <component
                  :is="getRoleTag(role).icon"
                  class="role-icon"
                />
                {{ getRoleTag(role).text }}
              </a-tag>
            </div>
          </template>

          <!-- 状态列 -->
          <template v-else-if="column.key === 'status'">
            <a-tag :color="getStatusTag(asUser(record).status).color">
              {{ getStatusTag(asUser(record).status).text }}
            </a-tag>
          </template>

          <!-- 操作列 -->
          <template v-else-if="column.key === 'actions'">
            <div class="action-buttons">
              <PermissionButton
                resource="users"
                action="update"
                type="link"
                size="small"
                @click="handleEditUser(asUser(record))"
              >
                <EditOutlined />
                编辑
              </PermissionButton>

              <PermissionButton
                resource="users"
                action="update"
                type="link"
                size="small"
                @click="handleResetPassword(asUser(record))"
              >
                <SettingOutlined />
                重置密码
              </PermissionButton>

              <PermissionButton
                resource="users"
                action="delete"
                type="link"
                size="small"
                danger
                @click="handleDeleteUser(asUser(record))"
              >
                <DeleteOutlined />
                删除
              </PermissionButton>
            </div>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 新增用户模态框 -->
    <a-modal
      v-model:open="showCreateModal"
      title="新增用户"
      :width="600"
      @ok="handleCreateSubmit"
    >
      <a-form
        :model="createForm"
        layout="vertical"
      >
        <a-form-item
          label="邮箱地址"
          required
        >
          <a-input
            v-model:value="createForm.email"
            placeholder="请输入邮箱地址"
          />
        </a-form-item>

        <a-form-item
          label="显示名称"
          required
        >
          <a-input
            v-model:value="createForm.display_name"
            placeholder="请输入显示名称"
          />
        </a-form-item>

        <a-form-item
          label="所属科室"
          required
        >
          <a-select
            v-model:value="createForm.department"
            placeholder="请选择科室"
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
          </a-select>
        </a-form-item>

        <a-form-item
          label="用户角色"
          required
        >
          <a-select
            v-model:value="createForm.roles"
            mode="multiple"
            placeholder="请选择角色"
          >
            <a-select-option value="admin">
              管理员
            </a-select-option>
            <a-select-option value="qc_manager">
              质控管理员
            </a-select-option>
            <a-select-option value="qc_staff">
              质控人员
            </a-select-option>
            <a-select-option value="doctor">
              医务人员
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item
          label="初始密码"
          required
        >
          <a-input-password
            v-model:value="createForm.password"
            placeholder="请输入初始密码"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑用户模态框 -->
    <a-modal
      v-model:open="showEditModal"
      title="编辑用户"
      :width="600"
      @ok="handleEditSubmit"
    >
      <a-form
        :model="editForm"
        layout="vertical"
      >
        <a-form-item
          label="邮箱地址"
          required
        >
          <a-input
            v-model:value="editForm.email"
            placeholder="请输入邮箱地址"
          />
        </a-form-item>

        <a-form-item
          label="显示名称"
          required
        >
          <a-input
            v-model:value="editForm.display_name"
            placeholder="请输入显示名称"
          />
        </a-form-item>

        <a-form-item
          label="所属科室"
          required
        >
          <a-select
            v-model:value="editForm.department"
            placeholder="请选择科室"
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
          </a-select>
        </a-form-item>

        <a-form-item
          label="用户角色"
          required
        >
          <a-select
            v-model:value="editForm.roles"
            mode="multiple"
            placeholder="请选择角色"
          >
            <a-select-option value="admin">
              管理员
            </a-select-option>
            <a-select-option value="qc_manager">
              质控管理员
            </a-select-option>
            <a-select-option value="qc_staff">
              质控人员
            </a-select-option>
            <a-select-option value="doctor">
              医务人员
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item
          label="用户状态"
          required
        >
          <a-select
            v-model:value="editForm.status"
            placeholder="请选择状态"
          >
            <a-select-option value="active">
              正常
            </a-select-option>
            <a-select-option value="inactive">
              停用
            </a-select-option>
            <a-select-option value="locked">
              锁定
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<style scoped>
.user-management-view {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  display: flex;
  align-items: center;
  font-size: 24px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 8px 0;
}

.title-icon {
  margin-right: 12px;
  color: #3b82f6;
}

.page-description {
  color: #6b7280;
  margin: 0;
}

.search-card {
  margin-bottom: 16px;
}

.toolbar-card {
  margin-bottom: 16px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.toolbar-left {
  display: flex;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.user-info {
  display: flex;
  flex-direction: column;
}

.user-name {
  font-weight: 500;
  color: #1f2937;
}

.user-email {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

.role-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.role-tag {
  display: flex;
  align-items: center;
  margin: 0;
}

.role-icon {
  margin-right: 4px;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

:deep(.ant-card-body) {
  padding: 16px;
}

:deep(.ant-form-inline .ant-form-item) {
  margin-right: 16px;
  margin-bottom: 8px;
}
</style>
