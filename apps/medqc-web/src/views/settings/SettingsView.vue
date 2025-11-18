<template>
  <div class="settings-page">
    <div class="settings-page__inner">
      <a-card class="settings-card settings-header-card" :bordered="false">
        <div class="settings-header">
          <div class="settings-header__meta">
            <div class="settings-header__icon">
              <SettingOutlined />
            </div>
            <div>
              <h1 class="settings-header__title">系统设置</h1>
              <p class="settings-header__subtitle">用户权限管理和系统配置</p>
            </div>
          </div>
          <div class="settings-header__actions">
            <a-space size="middle" wrap>
              <a-button
                class="settings-header__action"
                :icon="h(DownloadOutlined)"
                @click="exportConfig"
              >
                导出配置
              </a-button>
              <a-button
                class="settings-header__action"
                :icon="h(UploadOutlined)"
                @click="importConfig"
              >
                导入配置
              </a-button>
            </a-space>
          </div>
        </div>
      </a-card>

      <a-card class="settings-card settings-tabs-card" :bordered="false">
        <a-tabs v-model:activeKey="activeTab" type="card" class="settings-tabs">
          <a-tab-pane key="users" tab="用户管理">
            <template #tab>
              <UserOutlined class="settings-tabs__icon" />
              <span>用户管理</span>
            </template>
          </a-tab-pane>
          <a-tab-pane key="roles" tab="角色管理">
            <template #tab>
              <TeamOutlined class="settings-tabs__icon" />
              <span>角色管理</span>
            </template>
          </a-tab-pane>
          <a-tab-pane key="permissions" tab="权限配置">
            <template #tab>
              <SafetyCertificateOutlined class="settings-tabs__icon" />
              <span>权限配置</span>
            </template>
          </a-tab-pane>
          <a-tab-pane key="system" tab="系统配置">
            <template #tab>
              <SettingOutlined class="settings-tabs__icon" />
              <span>系统配置</span>
            </template>
          </a-tab-pane>
          <a-tab-pane key="llm" tab="LLM配置">
            <template #tab>
              <ApiOutlined class="settings-tabs__icon" />
              <span>LLM配置</span>
            </template>
          </a-tab-pane>
          <a-tab-pane key="classification" tab="分类算法">
            <template #tab>
              <BranchesOutlined class="settings-tabs__icon" />
              <span>分类算法</span>
            </template>
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <a-card
        v-if="activeTab === 'users'"
        title="用户管理"
        class="settings-card"
        :bordered="false"
      >
        <template #extra>
          <a-space size="middle">
            <a-button
              type="primary"
              class="elevated-action"
              @click="showCreateUserModal"
              :icon="h(PlusOutlined)"
            >
              新增用户
            </a-button>
            <a-button
              class="elevated-action"
              @click="refreshUsers"
              :loading="loading.users"
              :icon="h(ReloadOutlined)"
            >
              刷新
            </a-button>
          </a-space>
        </template>

        <div class="settings-filter-bar">
          <a-row :gutter="[16, 16]">
            <a-col :xs="24" :sm="12" :md="8">
              <a-input
                v-model:value="userSearch.email"
                placeholder="搜索邮箱"
                allow-clear
                @change="handleUserSearch"
              >
                <template #prefix>
                  <SearchOutlined class="filter-icon" />
                </template>
              </a-input>
            </a-col>
            <a-col :xs="24" :sm="12" :md="8">
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
            <a-col :xs="24" :sm="12" :md="8">
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

        <a-table
          class="settings-table"
          :columns="userColumns"
          :dataSource="filteredUsers"
          :loading="loading.users"
          :pagination="{ pageSize: 10 }"
          row-key="id"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'user_info'">
              <div class="user-info-cell">
                <a-avatar
                  :size="40"
                  :style="{ backgroundColor: getUserAvatarColor(record.email) }"
                >
                  {{ record.display_name?.charAt(0) || record.email?.charAt(0) }}
                </a-avatar>
                <div class="user-info-cell__meta">
                  <div class="user-info-cell__name">
                    {{ record.display_name || record.email }}
                  </div>
                  <div class="user-info-cell__email">
                    {{ record.email }}
                  </div>
                </div>
              </div>
            </template>

            <template v-else-if="column.key === 'roles'">
              <div class="user-role-tags">
                <a-tag
                  v-for="role in record.roles"
                  :key="role"
                  class="user-role-tags__tag"
                  :style="getRoleStyle(role)"
                >
                  {{ getRoleText(role) }}
                </a-tag>
              </div>
            </template>

            <template v-else-if="column.key === 'department'">
              <div class="user-department">
                <div class="user-department__name">{{ record.department || '-' }}</div>
                <div class="user-department__hospital">
                  {{ record.hospital_name || '全院' }}
                </div>
              </div>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-badge
                :status="record.is_active ? 'success' : 'default'"
                :text="record.is_active ? '激活' : '停用'"
              />
            </template>

            <template v-else-if="column.key === 'last_login'">
              <div v-if="record.last_login">
                {{ formatDateTime(record.last_login) }}
              </div>
              <span v-else class="text-tertiary">从未登录</span>
            </template>

            <template v-else-if="column.key === 'actions'">
              <a-space size="small">
                <a-button
                  type="link"
                  size="small"
                  class="action-link"
                  @click="editUser(record)"
                >
                  编辑
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  class="action-link"
                  :class="record.is_active ? 'action-link--warning' : 'action-link--success'"
                  @click="toggleUserStatus(record)"
                >
                  {{ record.is_active ? '停用' : '激活' }}
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  class="action-link action-link--danger"
                  @click="deleteUser(record)"
                >
                  删除
                </a-button>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <a-card
        v-if="activeTab === 'roles'"
        title="角色管理"
        class="settings-card"
        :bordered="false"
      >
        <div class="settings-role-grid">
          <a-card
            v-for="role in roles"
            :key="role.key"
            class="settings-card role-card"
            :bordered="false"
            @click="editRole(role)"
          >
            <div class="role-card__header">
              <div class="role-card__icon-wrap">
                <component :is="role.icon" class="role-card__icon" :style="{ color: role.color }" />
              </div>
              <div>
                <h3 class="role-card__title">{{ role.name }}</h3>
                <p class="role-card__description">{{ role.description }}</p>
              </div>
            </div>
            <div class="role-card__metrics">
              <div class="role-card__metric">
                <span>用户数量</span>
                <span class="role-card__metric-value">{{ role.userCount }}人</span>
              </div>
              <div class="role-card__metric">
                <span>权限数量</span>
                <span class="role-card__metric-value">{{ role.permissionCount }}项</span>
              </div>
            </div>
          </a-card>
        </div>
      </a-card>

      <a-card
        v-if="activeTab === 'permissions'"
        title="权限配置"
        class="settings-card"
        :bordered="false"
      >
        <a-alert
          message="权限配置说明"
          description="以下是系统各角色的权限配置矩阵，您可以根据需要调整各角色的权限设置。"
          type="info"
          show-icon
          class="settings-alert"
        />

        <div class="permission-matrix">
          <a-table
            class="settings-table settings-table--compact"
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

      <a-card
        v-if="activeTab === 'system'"
        title="系统配置"
        class="settings-card"
        :bordered="false"
      >
        <a-form :model="systemConfig" layout="vertical">
          <a-row :gutter="[24, 24]">
            <a-col :xs="24" :md="12">
              <a-form-item label="系统名称">
                <a-input v-model:value="systemConfig.systemName" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12">
              <a-form-item label="系统版本">
                <a-input v-model:value="systemConfig.version" readonly />
              </a-form-item>
            </a-col>
          </a-row>

          <a-row :gutter="[24, 24]">
            <a-col :xs="24" :md="12">
              <a-form-item label="会话超时时间(分钟)">
                <a-input-number
                  v-model:value="systemConfig.sessionTimeout"
                  :min="5"
                  :max="1440"
                  style="width: 100%"
                />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12">
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

          <a-row :gutter="[24, 24]">
            <a-col :xs="24" :md="12">
              <a-form-item label="启用多因素认证">
                <a-switch v-model:checked="systemConfig.enableMFA" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12">
              <a-form-item label="启用审计日志">
                <a-switch v-model:checked="systemConfig.enableAuditLog" />
              </a-form-item>
            </a-col>
          </a-row>

          <a-divider orientation="left">LLM 解析优化</a-divider>

          <a-row :gutter="[24, 24]">
            <a-col :xs="24" :md="12">
              <a-form-item label="启用指针模式（Pointer Mode）">
                <a-switch v-model:checked="systemConfig.llmPointerMode" />
              </a-form-item>
            </a-col>
            <a-col :xs="24" :md="12">
              <a-form-item label="摘要长度上限">
                <a-select v-model:value="systemConfig.llmSummaryMaxLen" style="width: 100%">
                  <a-select-option :value="0">禁用摘要（0）</a-select-option>
                  <a-select-option :value="40">40 字符</a-select-option>
                  <a-select-option :value="80">80 字符</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>

          <a-form-item class="settings-form__actions">
            <a-button
              type="primary"
              class="elevated-action"
              @click="saveSystemConfig"
              :loading="loading.systemConfig"
            >
              保存配置
            </a-button>
          </a-form-item>
        </a-form>
      </a-card>

      <a-card
        v-if="activeTab === 'llm'"
        title="LLM API 配置"
        class="settings-card"
        :bordered="false"
      >
        <LLMApiConfig />
      </a-card>

      <a-card
        v-if="activeTab === 'classification'"
        class="settings-card"
        :bordered="false"
      >
        <ClassificationVersionManager />
      </a-card>
    </div>

    <UserEditModal
      :visible="modals.userEdit"
      :user="selectedUser"
      @submit="handleUserSubmit"
      @cancel="modals.userEdit = false"
      @update:visible="(val: boolean) => (modals.userEdit = val)"
    />

    <RoleEditModal
      :visible="modals.roleEdit"
      :role="selectedRole"
      @submit="handleRoleSubmit"
      @cancel="modals.roleEdit = false"
      @update:visible="(val: boolean) => (modals.roleEdit = val)"
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

import UserEditModal from '@/components/settings/UserEditModal.vue'
import RoleEditModal from '@/components/settings/RoleEditModal.vue'
import ClassificationVersionManager from '@/components/settings/ClassificationVersionManager.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'

const activeTab = ref('users')
const loading = reactive({
  users: false,
  roles: false,
  permissions: false,
  systemConfig: false
})

const modals = reactive({
  userEdit: false,
  roleEdit: false
})

const selectedUser = ref(null)
const selectedRole = ref(null)

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

const roles = ref([
  {
    key: 'admin',
    name: '系统管理员',
    description: '拥有系统全部权限，可以管理用户、角色和系统配置',
    icon: CrownOutlined,
    color: '#FF7A45',
    userCount: 2,
    permissionCount: 25
  },
  {
    key: 'qc_manager',
    name: '质控管理员',
    description: '负责质控规则管理和质控流程监督',
    icon: SafetyOutlined,
    color: '#0B64D4',
    userCount: 5,
    permissionCount: 18
  },
  {
    key: 'qc_staff',
    name: '质控人员',
    description: '执行质控分析和审核工作',
    icon: SafetyCertificateOutlined,
    color: '#52C41A',
    userCount: 12,
    permissionCount: 10
  },
  {
    key: 'doctor',
    name: '医务人员',
    description: '上传和管理自己的病案记录',
    icon: MedicineBoxOutlined,
    color: '#8E63F7',
    userCount: 45,
    permissionCount: 6
  }
])

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

const filteredUsers = computed(() => {
  return users.value.filter(user => {
    const emailMatch = !userSearch.email || user.email?.toLowerCase().includes(userSearch.email.toLowerCase())
    const roleMatch = !userSearch.role || user.roles?.includes(userSearch.role)
    const statusMatch = !userSearch.status || (userSearch.status === 'active' ? user.is_active : !user.is_active)

    return emailMatch && roleMatch && statusMatch
  })
})

const refreshUsers = async () => {
  loading.users = true
  try {
    await new Promise(resolve => setTimeout(resolve, 1000))
    message.success('用户列表已刷新')
  } catch (error) {
    message.error('获取用户列表失败')
  } finally {
    loading.users = false
  }
}

const handleUserSearch = () => {}

const showCreateUserModal = () => {
  selectedUser.value = null
  modals.userEdit = true
}

const editUser = (user: any) => {
  selectedUser.value = user
  modals.userEdit = true
}

const editRole = (role: any) => {
  selectedRole.value = role
  modals.roleEdit = true
}

const toggleUserStatus = async (user: any) => {
  try {
    user.is_active = !user.is_active
    message.success(`用户已${user.is_active ? '激活' : '停用'}`)
  } catch (error) {
    message.error('操作失败')
  }
}

const deleteUser = (user: any) => {
  message.info('删除用户功能开发中')
}

const handleUserSubmit = async (userData: any) => {
  try {
    message.success('用户保存成功')
    modals.userEdit = false
    refreshUsers()
  } catch (error) {
    message.error('保存失败')
  }
}

const handleRoleSubmit = async (roleData: any) => {
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
    const { llmService } = await import('@/services/llmService')
    const pointerMode = !!systemConfig.llmPointerMode
    const summaryMaxLength = Number(systemConfig.llmSummaryMaxLen) || 0
    llmService.updateConfig({ pointerMode, summaryMaxLength })

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

const getUserAvatarColor = (email: string) => {
  const palette = ['#0B64D4', '#2C8EAA', '#52C41A', '#FAAD14', '#13C2C2']
  const index = email.charCodeAt(0) % palette.length
  return palette[index]
}

const roleStyleMap: Record<string, { backgroundColor: string; color: string }> = {
  admin: { backgroundColor: 'rgba(250, 140, 22, 0.16)', color: '#D46B08' },
  qc_manager: { backgroundColor: 'rgba(11, 100, 212, 0.14)', color: '#0B64D4' },
  qc_staff: { backgroundColor: 'rgba(82, 196, 26, 0.16)', color: '#237804' },
  doctor: { backgroundColor: 'rgba(142, 99, 247, 0.18)', color: '#6139B7' }
}

const getRoleText = (role: string) => {
  const textMap: Record<string, string> = {
    admin: '管理员',
    qc_manager: '质控管理员',
    qc_staff: '质控人员',
    doctor: '医务人员'
  }
  return textMap[role] || role
}

const getRoleStyle = (role: string) => {
  return roleStyleMap[role] || { backgroundColor: 'rgba(30, 136, 255, 0.12)', color: '#0B64D4' }
}

const formatDateTime = (dateString: string) => {
  return new Date(dateString).toLocaleString()
}

onMounted(async () => {
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

<style scoped lang="less">
.settings-page {
  min-height: 100vh;
  background: var(--background-page);
  padding: 24px 32px 48px;

  &__inner {
    max-width: 1200px;
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 24px;
  }
}

.settings-card {
  border-radius: 16px;
  background: var(--color-bg-card, #ffffff);
  box-shadow: var(--shadow-light, 0 6px 18px rgba(14, 110, 209, 0.08));
  border: 1px solid rgba(11, 100, 212, 0.08);

  :deep(.ant-card-head) {
    border-bottom: 1px solid rgba(12, 53, 106, 0.08);
    min-height: 56px;
    padding: 0 24px;
    display: flex;
    align-items: center;
  }

  :deep(.ant-card-head-title) {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
  }

  :deep(.ant-card-extra) {
    padding: 14px 24px 0;
  }

  :deep(.ant-card-body) {
    padding: 24px;
  }
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;

  &__meta {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  &__icon {
    width: 48px;
    height: 48px;
    border-radius: 16px;
    background: linear-gradient(135deg, rgba(30, 136, 255, 0.16), rgba(11, 100, 212, 0.12));
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--primary-color);
    font-size: 28px;
  }

  &__title {
    margin: 0;
    font-size: 24px;
    font-weight: 600;
    color: var(--text-primary);
  }

  &__subtitle {
    margin: 4px 0 0;
    font-size: 14px;
    color: var(--text-secondary);
  }

  &__actions {
    display: flex;
    align-items: center;
  }

  &__action {
    border-radius: 20px;
    padding: 0 18px;
    height: 36px;
    font-weight: 500;
  }
}

.settings-tabs-card {
  :deep(.ant-card-body) {
    padding: 16px 24px 0;
  }
}

.settings-tabs {
  :deep(.ant-tabs-nav) {
    margin: 0;
  }

  :deep(.ant-tabs-nav::before) {
    border: none;
  }

  :deep(.ant-tabs-tab) {
    border: none;
    background: transparent;
    border-radius: 20px;
    margin: 0 12px 12px 0;
    padding: 8px 20px;
    font-size: 14px;
    color: var(--text-secondary);
    transition: all 0.2s ease;
  }

  :deep(.ant-tabs-tab:hover) {
    color: var(--primary-color);
    background: rgba(11, 100, 212, 0.08);
  }

  :deep(.ant-tabs-tab-btn) {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  :deep(.ant-tabs-tab-active) {
    background: var(--primary-color-subtle);
    color: var(--primary-color);
    box-shadow: inset 0 0 0 1px rgba(11, 100, 212, 0.25);
  }

  :deep(.ant-tabs-tab-active .ant-tabs-tab-btn) {
    color: var(--primary-color);
  }

  :deep(.ant-tabs-ink-bar) {
    display: none !important;
  }
}

.settings-tabs__icon {
  font-size: 16px;
}

.settings-filter-bar {
  margin-bottom: 16px;
  padding: 16px;
  background: var(--background-light);
  border-radius: 12px;
  border: 1px solid rgba(11, 100, 212, 0.12);

  :deep(.ant-input) {
    border-radius: 24px;
  }

  :deep(.ant-select-selector) {
    border-radius: 24px !important;
    padding: 4px 12px !important;
  }
}

.filter-icon {
  color: var(--text-tertiary);
}

.user-info-cell {
  display: flex;
  align-items: center;
  gap: 12px;

  &__meta {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  &__name {
    font-weight: 600;
    color: var(--text-primary);
  }

  &__email {
    font-size: 12px;
    color: var(--text-tertiary);
  }
}

.text-tertiary {
  color: var(--text-tertiary);
}

.user-role-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;

  &__tag {
    border-radius: 16px;
    border: none !important;
    font-size: 12px;
    font-weight: 600;
    padding: 2px 12px;
    line-height: 20px;
  }
}

.user-department {
  display: flex;
  flex-direction: column;
  gap: 4px;

  &__name {
    font-weight: 500;
    color: var(--text-primary);
  }

  &__hospital {
    font-size: 12px;
    color: var(--text-tertiary);
  }
}

.action-link {
  color: var(--primary-color);
  padding: 0;
}

.action-link--warning {
  color: var(--warning-color);
}

.action-link--success {
  color: var(--success-color);
}

.action-link--danger {
  color: var(--error-color);
}

.settings-role-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.role-card {
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  :deep(.ant-card-body) {
    padding: 20px;
  }
}

.role-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-medium, 0 12px 24px rgba(15, 23, 42, 0.12));
}

.role-card__header {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 16px;
}

.role-card__icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  background: var(--primary-color-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
}

.role-card__icon {
  font-size: 26px;
}

.role-card__title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.role-card__description {
  margin: 0;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 20px;
}

.role-card__metrics {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.role-card__metric {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text-secondary);
}

.role-card__metric-value {
  font-weight: 600;
  color: var(--text-primary);
}

.settings-alert {
  margin-bottom: 24px;

  :deep(.ant-alert) {
    border-radius: 12px;
  }

  :deep(.ant-alert-message) {
    font-weight: 600;
  }

  :deep(.ant-alert-description) {
    color: var(--text-secondary);
  }
}

.permission-matrix {
  overflow-x: auto;
}

.settings-table {
  :deep(.ant-table) {
    border-radius: 12px;
    overflow: hidden;
  }

  :deep(.ant-table-thead > tr > th) {
    background: var(--background-light);
    color: var(--text-secondary);
    font-weight: 500;
  }

  :deep(.ant-table-tbody > tr > td) {
    color: var(--text-secondary);
  }

  :deep(.ant-table-tbody > tr:hover > td) {
    background: var(--primary-color-subtle);
  }
}

.settings-table--compact {
  :deep(.ant-table-tbody > tr > td) {
    padding: 12px 16px;
  }
}

.settings-form__actions {
  margin-top: 8px;
}

.elevated-action {
  border-radius: 20px !important;
  padding: 0 18px !important;
  height: 36px;
  font-weight: 500;
}

@media (max-width: 768px) {
  .settings-page {
    padding: 16px;
  }

  .settings-header {
    align-items: flex-start;
  }

  .settings-header__actions {
    width: 100%;
  }

  .settings-header__action {
    width: 100%;
    justify-content: center;
  }

  .settings-card {
    :deep(.ant-card-head) {
      padding: 0 16px;
    }

    :deep(.ant-card-body) {
      padding: 16px;
    }
  }

  .settings-filter-bar {
    padding: 12px;
  }
}
</style>
