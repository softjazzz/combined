<template>
  <div class="settings-page">
    <div class="settings-page__inner">
      <a-card
        class="settings-card settings-header-card"
        :bordered="false"
      >
        <div class="settings-header">
          <div class="settings-header__meta">
            <div class="settings-header__icon">
              <SettingOutlined />
            </div>
            <div>
              <h1 class="settings-header__title">
                系统设置
              </h1>
              <p class="settings-header__subtitle">
                用户权限管理和系统配置
              </p>
            </div>
          </div>
          <div class="settings-header__actions">
            <a-space
              size="middle"
              wrap
            >
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

      <a-card
        class="settings-card settings-tabs-card"
        :bordered="false"
      >
        <a-tabs
          v-model:active-key="activeTab"
          type="card"
          class="settings-tabs"
        >
          <a-tab-pane
            key="users"
            tab="用户管理"
          >
            <template #tab>
              <UserOutlined class="settings-tabs__icon" />
              <span>用户管理</span>
            </template>
          </a-tab-pane>
          <a-tab-pane
            key="roles"
            tab="角色管理"
          >
            <template #tab>
              <TeamOutlined class="settings-tabs__icon" />
              <span>角色管理</span>
            </template>
          </a-tab-pane>
          <a-tab-pane
            key="permissions"
            tab="权限配置"
          >
            <template #tab>
              <SafetyCertificateOutlined class="settings-tabs__icon" />
              <span>权限配置</span>
            </template>
          </a-tab-pane>
          <a-tab-pane
            key="system"
            tab="系统配置"
          >
            <template #tab>
              <SettingOutlined class="settings-tabs__icon" />
              <span>系统配置</span>
            </template>
          </a-tab-pane>
          <a-tab-pane
            key="llm"
            tab="LLM配置"
          >
            <template #tab>
              <ApiOutlined class="settings-tabs__icon" />
              <span>LLM配置</span>
            </template>
          </a-tab-pane>
          <a-tab-pane
            key="classification"
            tab="分类算法"
          >
            <template #tab>
              <BranchesOutlined class="settings-tabs__icon" />
              <span>分类算法</span>
            </template>
          </a-tab-pane>
          <a-tab-pane
            key="qc_engine"
            tab="质控配置"
          >
            <template #tab>
              <ExperimentOutlined class="settings-tabs__icon" />
              <span>质控配置</span>
            </template>
          </a-tab-pane>
          <a-tab-pane
            key="data_sync"
            tab="数据同步"
          >
            <template #tab>
              <SyncOutlined class="settings-tabs__icon" />
              <span>数据同步</span>
            </template>
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <div v-if="activeTab === 'users'">
        <UserManagement
          @create-user="showCreateUserModal"
          @edit-user="editUser"
        />
      </div>

      <div v-if="activeTab === 'roles'">
        <RoleManagement @edit-role="editRole" />
      </div>

      <div v-if="activeTab === 'permissions'">
        <PermissionConfig />
      </div>

      <div v-if="activeTab === 'system'">
        <SystemConfig />
      </div>

      <div v-if="activeTab === 'llm'">
        <div class="ds-root">
          <div class="ds-split">
            <div class="ds-split__aside">
              <h2 class="ds-section-title">
                LLM 配置
              </h2>
              <p class="ds-section-desc">
                配置大语言模型的 API 服务商、密钥和运行参数。支持阿里通义千问、OpenAI 等多家服务商。
              </p>
            </div>
            <div class="ds-split__main">
              <div
                class="ds-card"
                style="overflow: visible"
              >
                <div
                  class="ds-card__body"
                  style="padding: 20px"
                >
                  <LLMApiConfig />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'classification'">
        <div class="ds-root">
          <div class="ds-split">
            <div class="ds-split__aside">
              <h2 class="ds-section-title">
                分类算法
              </h2>
              <p class="ds-section-desc">
                管理医疗文书分类器的版本和运行状态。支持在基础、增强、先进三个版本之间切换。
              </p>
            </div>
            <div class="ds-split__main">
              <div
                class="ds-card"
                style="overflow: visible"
              >
                <div
                  class="ds-card__body"
                  style="padding: 20px"
                >
                  <ClassificationVersionManager />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 质控引擎配置 -->
      <div v-if="activeTab === 'qc_engine'">
        <QcEngineConfig />
      </div>

      <!-- 数据同步已迁移至 Workstation V4 -->
      <div v-if="activeTab === 'data_sync'">
        <a-alert
          type="info"
          show-icon
          message="数据同步控制台已迁移到 Workstation V4"
          description="正在跳转到 /workstation-v4/system-config ..."
        />
      </div>
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
import { ref, reactive, h, watch, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
  ApiOutlined,
  ExperimentOutlined,
  SyncOutlined,
} from '@ant-design/icons-vue'

import UserEditModal from '@/components/settings/UserEditModal.vue'
import RoleEditModal from '@/components/settings/RoleEditModal.vue'
import ClassificationVersionManager from '@/components/settings/ClassificationVersionManager.vue'
import LLMApiConfig from '@/components/LLMApiConfig.vue'
import SystemConfig from '@/components/settings/SystemConfig.vue'
import QcEngineConfig from '@/components/settings/QcEngineConfig.vue'
import UserManagement from '@/components/settings/UserManagement.vue'
import RoleManagement from '@/components/settings/RoleManagement.vue'
import PermissionConfig from '@/components/settings/PermissionConfig.vue'

type SettingsTab =
  | 'users'
  | 'roles'
  | 'permissions'
  | 'system'
  | 'llm'
  | 'classification'
  | 'qc_engine'
  | 'data_sync'

const route = useRoute()
const router = useRouter()
const activeTab = ref<SettingsTab>('users')
const validTabs: SettingsTab[] = [
  'users',
  'roles',
  'permissions',
  'system',
  'llm',
  'classification',
  'qc_engine',
  'data_sync',
]

const resolveTab = (tab: unknown): SettingsTab => {
  const value = Array.isArray(tab) ? tab[0] : tab
  if (typeof value === 'string' && validTabs.includes(value as SettingsTab)) {
    return value as SettingsTab
  }
  return 'users'
}

watch(
  () => route.query.tab,
  (tab) => {
    activeTab.value = resolveTab(tab)
  },
  { immediate: true },
)

watch(activeTab, async (tab) => {
  if (tab !== 'data_sync') {
    return
  }
  await router.push({ path: '/workstation-v4/system-config', query: { tab: 'dataSync' } })
})

const modals = reactive({
  userEdit: false,
  roleEdit: false,
})

const selectedUser = ref<Record<string, unknown> | undefined>(undefined)
type EditableRole = {
  key: string
  name: string
  description: string
  icon?: Component
  color?: string
  userCount?: number
  permissionCount?: number
}
const selectedRole = ref<EditableRole | undefined>(undefined)

const showCreateUserModal = () => {
  selectedUser.value = undefined
  modals.userEdit = true
}

const editUser = (user: any) => {
  selectedUser.value = user
  modals.userEdit = true
}

const editRole = (role: EditableRole) => {
  selectedRole.value = role
  modals.roleEdit = true
}

const handleUserSubmit = async (userData: any) => {
  try {
    message.success('用户保存成功')
    modals.userEdit = false
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

const exportConfig = () => {
  message.info('导出配置功能开发中')
}

const importConfig = () => {
  message.info('导入配置功能开发中')
}
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
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;

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

.qc-setting-hint {
  font-size: 12px;
  color: #999;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
