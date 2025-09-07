<template>
  <div class="realtime-qc-view">
    <!-- 页面头部 -->
    <PageHeaderComponent
      title="实时质控监控"
      subtitle="病案录入过程中的实时质控分析和预警系统"
    >
      <template #actions>
        <div class="header-actions">
          <div class="status-indicator">
            <div 
              class="status-dot"
              :class="{
                'status-active': isMonitoring,
                'status-inactive': !isMonitoring
              }"
            ></div>
            <span class="status-text">
              {{ isMonitoring ? '监控中' : '已停止' }}
            </span>
          </div>
          
          <button
            v-if="!isMonitoring"
            @click="startMonitoring"
            class="btn-primary"
            :disabled="isStarting"
          >
            <i class="fas fa-play mr-2"></i>
            {{ isStarting ? '启动中...' : '启动监控' }}
          </button>
          
          <button
            v-else
            @click="stopMonitoring"
            class="btn-secondary"
            :disabled="isStopping"
          >
            <i class="fas fa-stop mr-2"></i>
            {{ isStopping ? '停止中...' : '停止监控' }}
          </button>
        </div>
      </template>
    </PageHeaderComponent>

    <!-- 主要内容区域 -->
    <div class="main-content">
      <!-- 实时监控仪表板 -->
      <div class="dashboard-section">
        <RealTimeQCDashboard />
      </div>

      <!-- 质控规则管理 -->
      <div class="rules-section">
        <div class="section-card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-rules mr-2"></i>
              质控规则管理
            </h3>
            <div class="card-actions">
              <button
                @click="refreshRules"
                class="btn-refresh"
                :disabled="isRefreshingRules"
              >
                <i class="fas fa-sync-alt" :class="{ 'fa-spin': isRefreshingRules }"></i>
              </button>
              <button
                @click="showAddRule"
                class="btn-add"
              >
                <i class="fas fa-plus mr-1"></i>
                新增规则
              </button>
            </div>
          </div>

          <div class="card-content">
            <div v-if="qcRules.length === 0" class="empty-state">
              <i class="fas fa-clipboard-list text-gray-400 text-4xl mb-3"></i>
              <p class="text-gray-600">暂无质控规则</p>
              <button
                @click="loadDefaultRules"
                class="btn-load-default"
              >
                加载默认规则
              </button>
            </div>

            <div v-else class="rules-list">
              <div
                v-for="rule in qcRules"
                :key="rule.id"
                class="rule-item"
                :class="{ 'rule-inactive': !rule.isActive }"
              >
                <div class="rule-info">
                  <div class="rule-header">
                    <h4 class="rule-name">{{ rule.name }}</h4>
                    <div class="rule-badges">
                      <span class="rule-type" :class="`type-${rule.type}`">
                        {{ getRuleTypeText(rule.type) }}
                      </span>
                      <span class="rule-severity" :class="`severity-${rule.severity}`">
                        {{ getSeverityText(rule.severity) }}
                      </span>
                    </div>
                  </div>
                  <p class="rule-description">{{ rule.description }}</p>
                  <div class="rule-meta">
                    <span class="rule-priority">优先级: {{ rule.priority }}</span>
                    <span class="rule-status">
                      {{ rule.isActive ? '启用' : '禁用' }}
                    </span>
                  </div>
                </div>

                <div class="rule-actions">
                  <button
                    @click="toggleRule(rule)"
                    class="btn-toggle"
                    :class="rule.isActive ? 'btn-disable' : 'btn-enable'"
                  >
                    <i :class="rule.isActive ? 'fas fa-pause' : 'fas fa-play'"></i>
                  </button>
                  <button
                    @click="editRule(rule)"
                    class="btn-edit"
                  >
                    <i class="fas fa-edit"></i>
                  </button>
                  <button
                    @click="deleteRule(rule)"
                    class="btn-delete"
                  >
                    <i class="fas fa-trash"></i>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 实时分析日志 -->
      <div class="logs-section">
        <div class="section-card">
          <div class="card-header">
            <h3 class="card-title">
              <i class="fas fa-file-alt mr-2"></i>
              实时分析日志
            </h3>
            <div class="card-actions">
              <select v-model="logFilter" class="filter-select">
                <option value="all">全部</option>
                <option value="critical">严重</option>
                <option value="error">错误</option>
                <option value="warning">警告</option>
                <option value="info">信息</option>
              </select>
              <button
                @click="clearLogs"
                class="btn-clear"
              >
                <i class="fas fa-trash mr-1"></i>
                清空日志
              </button>
            </div>
          </div>

          <div class="card-content">
            <div v-if="filteredLogs.length === 0" class="empty-state">
              <i class="fas fa-file-alt text-gray-400 text-4xl mb-3"></i>
              <p class="text-gray-600">暂无分析日志</p>
            </div>

            <div v-else class="logs-list">
              <div
                v-for="log in filteredLogs.slice(0, 50)"
                :key="log.id"
                class="log-item"
                :class="`log-${log.alertLevel}`"
              >
                <div class="log-header">
                  <div class="log-info">
                    <span class="log-time">{{ formatTime(log.timestamp) }}</span>
                    <span class="log-record">记录: {{ log.recordId.slice(-8) }}</span>
                    <span class="log-level" :class="`level-${log.alertLevel}`">
                      {{ getLevelText(log.alertLevel) }}
                    </span>
                  </div>
                  <div class="log-metrics">
                    <span class="log-duration">{{ log.processingTime }}ms</span>
                    <span class="log-confidence">{{ Math.round(log.confidence * 100) }}%</span>
                  </div>
                </div>

                <div class="log-content" v-if="log.issues.length > 0">
                  <div class="log-issues">
                    <span
                      v-for="(issue, idx) in log.issues.slice(0, 3)"
                      :key="idx"
                      class="issue-tag"
                      :class="`issue-${issue.severity}`"
                    >
                      {{ issue.message }}
                    </span>
                    <span v-if="log.issues.length > 3" class="more-issues">
                      +{{ log.issues.length - 3 }} 更多
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 实时预警组件 -->
    <RealTimeQCAlert />

    <!-- 规则编辑对话框 -->
    <div v-if="showRuleDialog" class="rule-dialog-overlay">
      <div class="rule-dialog">
        <div class="dialog-header">
          <h3 class="dialog-title">
            {{ editingRule ? '编辑规则' : '新增规则' }}
          </h3>
          <button
            @click="closeRuleDialog"
            class="btn-close"
          >
            <i class="fas fa-times"></i>
          </button>
        </div>

        <div class="dialog-content">
          <div class="form-group">
            <label class="form-label">规则名称</label>
            <input
              v-model="ruleForm.name"
              type="text"
              class="form-input"
              placeholder="请输入规则名称"
            />
          </div>

          <div class="form-group">
            <label class="form-label">规则描述</label>
            <textarea
              v-model="ruleForm.description"
              class="form-textarea"
              placeholder="请输入规则描述"
              rows="3"
            ></textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">规则类型</label>
              <select v-model="ruleForm.type" class="form-select">
                <option value="content">内容检查</option>
                <option value="format">格式检查</option>
                <option value="logic">逻辑检查</option>
                <option value="completeness">完整性检查</option>
              </select>
            </div>

            <div class="form-group">
              <label class="form-label">严重程度</label>
              <select v-model="ruleForm.severity" class="form-select">
                <option value="info">信息</option>
                <option value="warning">警告</option>
                <option value="error">错误</option>
                <option value="critical">严重</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">优先级</label>
              <input
                v-model.number="ruleForm.priority"
                type="number"
                class="form-input"
                min="1"
                max="10"
              />
            </div>

            <div class="form-group">
              <label class="form-label">状态</label>
              <label class="checkbox-label">
                <input
                  v-model="ruleForm.isActive"
                  type="checkbox"
                  class="form-checkbox"
                />
                <span>启用规则</span>
              </label>
            </div>
          </div>

          <div class="form-group" v-if="ruleForm.type === 'content'">
            <label class="form-label">匹配模式</label>
            <input
              v-model="ruleForm.pattern"
              type="text"
              class="form-input"
              placeholder="请输入正则表达式"
            />
          </div>
        </div>

        <div class="dialog-actions">
          <button
            @click="closeRuleDialog"
            class="btn-cancel"
          >
            取消
          </button>
          <button
            @click="saveRule"
            class="btn-save"
            :disabled="!isRuleFormValid"
          >
            保存
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRealTimeQC } from '@/composables/useRealTimeQC'
import type { QCRule, RealTimeQCResult, QCAlertLevel } from '@/composables/useRealTimeQC'
import RealTimeQCDashboard from '@/components/qc/RealTimeQCDashboard.vue'
import RealTimeQCAlert from '@/components/qc/RealTimeQCAlert.vue'
import PageHeaderComponent from '@/components/common/PageHeaderComponent.vue'
import { message } from 'ant-design-vue'

// 使用实时质控组合式函数
const {
  isMonitoring,
  recentResults,
  qcRules,
  startRealTimeMonitoring,
  stopRealTimeMonitoring,
  loadQCRules
} = useRealTimeQC()

// 组件状态
const isStarting = ref(false)
const isStopping = ref(false)
const isRefreshingRules = ref(false)
const logFilter = ref<string>('all')
const showRuleDialog = ref(false)
const editingRule = ref<QCRule | null>(null)

// 规则表单
const ruleForm = ref({
  name: '',
  description: '',
  type: 'content' as 'content' | 'format' | 'logic' | 'completeness',
  severity: 'warning' as QCAlertLevel,
  priority: 5,
  isActive: true,
  pattern: ''
})

// 计算属性
const filteredLogs = computed(() => {
  if (logFilter.value === 'all') {
    return recentResults.value
  }
  return recentResults.value.filter(log => log.alertLevel === logFilter.value)
})

const isRuleFormValid = computed(() => {
  return ruleForm.value.name.trim() !== '' && ruleForm.value.description.trim() !== ''
})

// 方法
const startMonitoring = async () => {
  isStarting.value = true
  try {
    await startRealTimeMonitoring()
    message.success('实时质控监控已启动')
  } catch (error) {
    console.error('启动监控失败:', error)
    message.error('启动监控失败')
  } finally {
    isStarting.value = false
  }
}

const stopMonitoring = async () => {
  isStopping.value = true
  try {
    stopRealTimeMonitoring()
    message.success('实时质控监控已停止')
  } catch (error) {
    console.error('停止监控失败:', error)
    message.error('停止监控失败')
  } finally {
    isStopping.value = false
  }
}

const refreshRules = async () => {
  isRefreshingRules.value = true
  try {
    await loadQCRules()
    message.success('质控规则已刷新')
  } catch (error) {
    console.error('刷新规则失败:', error)
    message.error('刷新规则失败')
  } finally {
    isRefreshingRules.value = false
  }
}

const showAddRule = () => {
  editingRule.value = null
  ruleForm.value = {
    name: '',
    description: '',
    type: 'content',
    severity: 'warning',
    priority: 5,
    isActive: true,
    pattern: ''
  }
  showRuleDialog.value = true
}

const editRule = (rule: QCRule) => {
  editingRule.value = rule
  ruleForm.value = { ...rule }
  showRuleDialog.value = true
}

const closeRuleDialog = () => {
  showRuleDialog.value = false
  editingRule.value = null
}

const saveRule = async () => {
  try {
    // 这里应该调用API保存规则
    console.log('保存规则:', ruleForm.value)
    message.success('规则保存成功')
    closeRuleDialog()
    await refreshRules()
  } catch (error) {
    console.error('保存规则失败:', error)
    message.error('保存规则失败')
  }
}

const toggleRule = async (rule: QCRule) => {
  try {
    // 这里应该调用API切换规则状态
    rule.isActive = !rule.isActive
    message.success(`规则已${rule.isActive ? '启用' : '禁用'}`)
  } catch (error) {
    console.error('切换规则状态失败:', error)
    message.error('操作失败')
  }
}

const deleteRule = async (rule: QCRule) => {
  try {
    // 这里应该调用API删除规则
    const index = qcRules.value.findIndex(r => r.id === rule.id)
    if (index !== -1) {
      qcRules.value.splice(index, 1)
    }
    message.success('规则已删除')
  } catch (error) {
    console.error('删除规则失败:', error)
    message.error('删除失败')
  }
}

const loadDefaultRules = async () => {
  try {
    await loadQCRules()
    message.success('默认规则已加载')
  } catch (error) {
    console.error('加载默认规则失败:', error)
    message.error('加载失败')
  }
}

const clearLogs = () => {
  recentResults.value.splice(0)
  message.success('日志已清空')
}

// 工具函数
const getRuleTypeText = (type: string): string => {
  const texts = {
    content: '内容',
    format: '格式',
    logic: '逻辑',
    completeness: '完整性'
  }
  return texts[type as keyof typeof texts] || type
}

const getSeverityText = (severity: QCAlertLevel): string => {
  const texts = {
    critical: '严重',
    error: '错误',
    warning: '警告',
    info: '信息'
  }
  return texts[severity]
}

const getLevelText = (level: QCAlertLevel): string => {
  return getSeverityText(level)
}

const formatTime = (timestamp: string): string => {
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 生命周期
onMounted(async () => {
  console.log('实时质控监控页面已加载')
  await refreshRules()
})
</script>

<style scoped>
.realtime-qc-view {
  @apply min-h-screen bg-gray-50;
}

.header-actions {
  @apply flex items-center space-x-4;
}

.status-indicator {
  @apply flex items-center space-x-2;
}

.status-dot {
  @apply w-3 h-3 rounded-full;
}

.status-active {
  @apply bg-green-500 animate-pulse;
}

.status-inactive {
  @apply bg-gray-400;
}

.status-text {
  @apply text-sm font-medium text-gray-700;
}

.btn-primary {
  @apply px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

.btn-secondary {
  @apply px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

.main-content {
  @apply p-6 space-y-6;
}

.section-card {
  @apply bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden;
}

.card-header {
  @apply flex items-center justify-between p-6 bg-gray-50 border-b border-gray-200;
}

.card-title {
  @apply text-lg font-semibold text-gray-800 flex items-center;
}

.card-actions {
  @apply flex items-center space-x-2;
}

.btn-refresh {
  @apply p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors duration-200 disabled:opacity-50;
}

.btn-add {
  @apply px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors duration-200 flex items-center text-sm;
}

.card-content {
  @apply p-6;
}

.empty-state {
  @apply text-center py-12;
}

.btn-load-default {
  @apply mt-4 px-4 py-2 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded-lg transition-colors duration-200;
}

.rules-list {
  @apply space-y-4;
}

.rule-item {
  @apply flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200;
}

.rule-inactive {
  @apply opacity-60 bg-gray-50;
}

.rule-info {
  @apply flex-1;
}

.rule-header {
  @apply flex items-center justify-between mb-2;
}

.rule-name {
  @apply text-lg font-semibold text-gray-800;
}

.rule-badges {
  @apply flex items-center space-x-2;
}

.rule-type {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.type-content {
  @apply bg-blue-100 text-blue-800;
}

.type-format {
  @apply bg-green-100 text-green-800;
}

.type-logic {
  @apply bg-purple-100 text-purple-800;
}

.type-completeness {
  @apply bg-orange-100 text-orange-800;
}

.rule-severity {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.severity-critical {
  @apply bg-red-100 text-red-800;
}

.severity-error {
  @apply bg-orange-100 text-orange-800;
}

.severity-warning {
  @apply bg-yellow-100 text-yellow-800;
}

.severity-info {
  @apply bg-blue-100 text-blue-800;
}

.rule-description {
  @apply text-gray-600 text-sm mb-2;
}

.rule-meta {
  @apply flex items-center space-x-4 text-sm text-gray-500;
}

.rule-actions {
  @apply flex items-center space-x-2;
}

.btn-toggle {
  @apply p-2 rounded-lg transition-colors duration-200;
}

.btn-enable {
  @apply text-green-600 hover:bg-green-50;
}

.btn-disable {
  @apply text-orange-600 hover:bg-orange-50;
}

.btn-edit {
  @apply p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors duration-200;
}

.btn-delete {
  @apply p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors duration-200;
}

.filter-select {
  @apply px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}

.btn-clear {
  @apply px-3 py-2 bg-red-100 text-red-700 hover:bg-red-200 rounded-lg transition-colors duration-200 flex items-center text-sm;
}

.logs-list {
  @apply space-y-3;
}

.log-item {
  @apply border border-gray-200 rounded-lg p-4;
}

.log-critical {
  @apply border-red-300 bg-red-50;
}

.log-error {
  @apply border-orange-300 bg-orange-50;
}

.log-warning {
  @apply border-yellow-300 bg-yellow-50;
}

.log-info {
  @apply border-blue-300 bg-blue-50;
}

.rule-dialog-overlay {
  @apply fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50;
}

.rule-dialog {
  @apply bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-screen overflow-y-auto;
}

.dialog-header {
  @apply flex items-center justify-between p-6 border-b border-gray-200;
}

.dialog-title {
  @apply text-xl font-semibold text-gray-800;
}

.btn-close {
  @apply p-2 text-gray-400 hover:text-red-600 rounded-lg transition-colors duration-200;
}

.dialog-content {
  @apply p-6 space-y-4;
}

.form-group {
  @apply space-y-2;
}

.form-row {
  @apply grid grid-cols-1 md:grid-cols-2 gap-4;
}

.form-label {
  @apply block text-sm font-medium text-gray-700;
}

.form-input,
.form-textarea,
.form-select {
  @apply w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}

.form-textarea {
  @apply resize-none;
}

.checkbox-label {
  @apply flex items-center space-x-2 cursor-pointer;
}

.form-checkbox {
  @apply rounded border-gray-300 text-blue-600 focus:ring-blue-500;
}

.dialog-actions {
  @apply flex items-center justify-end space-x-3 p-6 border-t border-gray-200;
}

.btn-cancel {
  @apply px-4 py-2 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-lg transition-colors duration-200;
}

.btn-save {
  @apply px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed;
}

@media (max-width: 768px) {
  .main-content {
    @apply p-4 space-y-4;
  }

  .header-actions {
    @apply flex-col space-y-2 space-x-0 items-stretch;
  }

  .card-header {
    @apply flex-col space-y-3 items-start;
  }

  .rule-item {
    @apply flex-col space-y-3 items-start;
  }

  .rule-header {
    @apply flex-col space-y-2 items-start;
  }

  .form-row {
    @apply grid-cols-1;
  }
}
</style>

<style scoped>
.realtime-qc-view {
  @apply min-h-screen bg-gray-50;
}

/* 页面头部 */
.header-actions {
  @apply flex items-center space-x-4;
}

.status-indicator {
  @apply flex items-center space-x-2;
}

.status-dot {
  @apply w-3 h-3 rounded-full;
}

.status-active {
  @apply bg-green-500 animate-pulse;
}

.status-inactive {
  @apply bg-gray-400;
}

.status-text {
  @apply text-sm font-medium text-gray-700;
}

.btn-primary {
  @apply px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

.btn-secondary {
  @apply px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center;
}

/* 主要内容区域 */
.main-content {
  @apply p-6 space-y-6;
}

.dashboard-section {
  @apply w-full;
}

.rules-section,
.logs-section {
  @apply w-full;
}

.section-card {
  @apply bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden;
}

.card-header {
  @apply flex items-center justify-between p-6 bg-gray-50 border-b border-gray-200;
}

.card-title {
  @apply text-lg font-semibold text-gray-800 flex items-center;
}

.card-actions {
  @apply flex items-center space-x-2;
}

.btn-refresh {
  @apply p-2 text-gray-600 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors duration-200 disabled:opacity-50;
}

.btn-add {
  @apply px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors duration-200 flex items-center text-sm;
}

.card-content {
  @apply p-6;
}

.empty-state {
  @apply text-center py-12;
}

.btn-load-default {
  @apply mt-4 px-4 py-2 bg-blue-100 text-blue-700 hover:bg-blue-200 rounded-lg transition-colors duration-200;
}

/* 规则列表 */
.rules-list {
  @apply space-y-4;
}

.rule-item {
  @apply flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200;
}

.rule-inactive {
  @apply opacity-60 bg-gray-50;
}

.rule-info {
  @apply flex-1;
}

.rule-header {
  @apply flex items-center justify-between mb-2;
}

.rule-name {
  @apply text-lg font-semibold text-gray-800;
}

.rule-badges {
  @apply flex items-center space-x-2;
}

.rule-type {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.type-content {
  @apply bg-blue-100 text-blue-800;
}

.type-format {
  @apply bg-green-100 text-green-800;
}

.type-logic {
  @apply bg-purple-100 text-purple-800;
}

.type-completeness {
  @apply bg-orange-100 text-orange-800;
}

.rule-severity {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.severity-critical {
  @apply bg-red-100 text-red-800;
}

.severity-error {
  @apply bg-orange-100 text-orange-800;
}

.severity-warning {
  @apply bg-yellow-100 text-yellow-800;
}

.severity-info {
  @apply bg-blue-100 text-blue-800;
}

.rule-description {
  @apply text-gray-600 text-sm mb-2;
}

.rule-meta {
  @apply flex items-center space-x-4 text-sm text-gray-500;
}

.rule-actions {
  @apply flex items-center space-x-2;
}

.btn-toggle {
  @apply p-2 rounded-lg transition-colors duration-200;
}

.btn-enable {
  @apply text-green-600 hover:bg-green-50;
}

.btn-disable {
  @apply text-orange-600 hover:bg-orange-50;
}

.btn-edit {
  @apply p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors duration-200;
}

.btn-delete {
  @apply p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors duration-200;
}

/* 日志列表 */
.filter-select {
  @apply px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}

.btn-clear {
  @apply px-3 py-2 bg-red-100 text-red-700 hover:bg-red-200 rounded-lg transition-colors duration-200 flex items-center text-sm;
}

.logs-list {
  @apply space-y-3;
}

.log-item {
  @apply border border-gray-200 rounded-lg p-4;
}

.log-critical {
  @apply border-red-300 bg-red-50;
}

.log-error {
  @apply border-orange-300 bg-orange-50;
}

.log-warning {
  @apply border-yellow-300 bg-yellow-50;
}

.log-info {
  @apply border-blue-300 bg-blue-50;
}

.log-header {
  @apply flex items-center justify-between mb-2;
}

.log-info {
  @apply flex items-center space-x-3;
}

.log-time {
  @apply text-sm text-gray-500 font-mono;
}

.log-record {
  @apply text-sm text-gray-600 font-mono;
}

.log-level {
  @apply px-2 py-1 text-xs font-medium rounded-full;
}

.level-critical {
  @apply bg-red-100 text-red-800;
}

.level-error {
  @apply bg-orange-100 text-orange-800;
}

.level-warning {
  @apply bg-yellow-100 text-yellow-800;
}

.level-info {
  @apply bg-blue-100 text-blue-800;
}

.log-metrics {
  @apply flex items-center space-x-3 text-sm text-gray-600;
}

.log-duration,
.log-confidence {
  @apply font-mono;
}

.log-content {
  @apply mt-2;
}

.log-issues {
  @apply flex flex-wrap gap-2;
}

.issue-tag {
  @apply px-2 py-1 text-xs rounded-full;
}

.issue-critical {
  @apply bg-red-100 text-red-800;
}

.issue-error {
  @apply bg-orange-100 text-orange-800;
}

.issue-warning {
  @apply bg-yellow-100 text-yellow-800;
}

.issue-info {
  @apply bg-blue-100 text-blue-800;
}

.more-issues {
  @apply px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full;
}

/* 规则编辑对话框 */
.rule-dialog-overlay {
  @apply fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50;
}

.rule-dialog {
  @apply bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-screen overflow-y-auto;
}

.dialog-header {
  @apply flex items-center justify-between p-6 border-b border-gray-200;
}

.dialog-title {
  @apply text-xl font-semibold text-gray-800;
}

.btn-close {
  @apply p-2 text-gray-400 hover:text-red-600 rounded-lg transition-colors duration-200;
}

.dialog-content {
  @apply p-6 space-y-4;
}

.form-group {
  @apply space-y-2;
}

.form-row {
  @apply grid grid-cols-1 md:grid-cols-2 gap-4;
}

.form-label {
  @apply block text-sm font-medium text-gray-700;
}

.form-input,
.form-textarea,
.form-select {
  @apply w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500;
}

.form-textarea {
  @apply resize-none;
}

.checkbox-label {
  @apply flex items-center space-x-2 cursor-pointer;
}

.form-checkbox {
  @apply rounded border-gray-300 text-blue-600 focus:ring-blue-500;
}

.dialog-actions {
  @apply flex items-center justify-end space-x-3 p-6 border-t border-gray-200;
}

.btn-cancel {
  @apply px-4 py-2 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-lg transition-colors duration-200;
}

.btn-save {
  @apply px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .main-content {
    @apply p-4 space-y-4;
  }

  .header-actions {
    @apply flex-col space-y-2 space-x-0 items-stretch;
  }

  .card-header {
    @apply flex-col space-y-3 items-start;
  }

  .rule-item {
    @apply flex-col space-y-3 items-start;
  }

  .rule-header {
    @apply flex-col space-y-2 items-start;
  }

  .log-header {
    @apply flex-col space-y-2 items-start;
  }

  .form-row {
    @apply grid-cols-1;
  }
}
</style>
