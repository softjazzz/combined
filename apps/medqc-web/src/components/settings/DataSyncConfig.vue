<template>
  <div class="data-sync-config">
    <!-- 连接状态卡片 -->
    <div class="sync-cards">
      <!-- MongoDB 连接 -->
      <a-card class="sync-conn-card" :bordered="false">
        <div class="conn-header">
          <div class="conn-header__left">
            <div class="conn-icon conn-icon--mongo">
              <span class="conn-icon__text">M</span>
            </div>
            <div>
              <div class="conn-title">MongoDB 数据源</div>
              <div class="conn-subtitle">{{ mongoConfig.mongo_database || '未配置' }}</div>
            </div>
          </div>
          <div class="conn-header__right">
            <a-tag :color="mongoStatus.connected ? 'green' : 'default'" class="conn-status-tag">
              {{ mongoStatus.connected ? '✅ 已连接' : '⬚ 未配置' }}
            </a-tag>
            <a-button size="small" type="text" @click="showMongoModal = true">
              <template #icon><EditOutlined /></template>
              编辑
            </a-button>
          </div>
        </div>
        <div class="conn-details">
          <div class="conn-detail-row">
            <span class="conn-detail-label">URI</span>
            <span class="conn-detail-value mono">{{ mongoConfig.mongo_uri_display || '未配置' }}</span>
          </div>
          <div class="conn-detail-row">
            <span class="conn-detail-label">读偏好</span>
            <span class="conn-detail-value">{{ mongoConfig.read_preference || '—' }}</span>
          </div>
          <div class="conn-detail-row">
            <span class="conn-detail-label">同步开关</span>
            <a-switch
              :checked="mongoConfig.enabled"
              checked-children="启用"
              un-checked-children="关闭"
              size="small"
              @change="toggleEnabled"
            />
          </div>
        </div>
      </a-card>

      <!-- 同步统计 -->
      <a-card class="sync-conn-card" :bordered="false">
        <div class="conn-header">
          <div class="conn-header__left">
            <SyncOutlined class="text-blue-500" style="font-size: 20px" :spin="mongoSyncState.is_running" />
            <div>
              <div class="conn-title">同步统计</div>
              <div class="conn-subtitle">Visit 同步状态分布</div>
            </div>
          </div>
          <a-button size="small" type="text" @click="loadMongoStatus">
            <template #icon><ReloadOutlined /></template>
            刷新
          </a-button>
        </div>
        <div class="stats-grid">
          <div class="stat-item stat-item--blue">
            <div class="stat-value">{{ mongoStats.PENDING || 0 }}</div>
            <div class="stat-label">待抽取</div>
          </div>
          <div class="stat-item stat-item--amber">
            <div class="stat-value">{{ mongoStats.PARTIAL || 0 }}</div>
            <div class="stat-label">部分同步</div>
          </div>
          <div class="stat-item stat-item--green">
            <div class="stat-value">{{ mongoStats.SYNCED || 0 }}</div>
            <div class="stat-label">已完成</div>
          </div>
          <div class="stat-item stat-item--orange">
            <div class="stat-value">{{ mongoStats.STALE || 0 }}</div>
            <div class="stat-label">需重拉</div>
          </div>
          <div class="stat-item stat-item--red">
            <div class="stat-value">{{ mongoStats.FAILED || 0 }}</div>
            <div class="stat-label">失败</div>
          </div>
        </div>
      </a-card>
    </div>

    <!-- 手动触发同步 -->
    <a-card :bordered="false" class="sync-action-card">
      <div class="action-bar">
        <div class="action-bar__left">
          <span class="action-title">手动触发同步</span>
          <span class="action-hint">选择 Tier 级别后点击执行</span>
        </div>
        <div class="action-bar__right">
          <a-select v-model:value="mongoSyncTier" size="small" style="width: 140px">
            <a-select-option value="all">全部 Tier</a-select-option>
            <a-select-option value="tier1">Tier1 · 索引发现</a-select-option>
            <a-select-option value="tier2">Tier2 · 结构化</a-select-option>
            <a-select-option value="tier3">Tier3 · 全文</a-select-option>
          </a-select>
          <a-button
            type="primary"
            size="small"
            @click="triggerMongoSync"
            :loading="mongoSyncState.is_running"
            :disabled="!mongoConfig.enabled"
          >
            <template #icon><SyncOutlined /></template>
            执行同步
          </a-button>
        </div>
      </div>
      <!-- Tier 运行状态 -->
      <div class="tier-status-grid">
        <div class="tier-item">
          <div class="tier-item__label">Tier 1 · 索引发现</div>
          <div class="tier-item__value">{{ mongoSyncState.tier1_discovered || 0 }} 条</div>
          <div class="tier-item__time">{{ mongoSyncState.tier1_last_run || '从未运行' }}</div>
        </div>
        <div class="tier-item">
          <div class="tier-item__label">Tier 2 · 结构化数据</div>
          <div class="tier-item__value">{{ mongoSyncState.tier2_synced || 0 }} 条</div>
          <div class="tier-item__time">{{ mongoSyncState.tier2_last_run || '从未运行' }}</div>
        </div>
        <div class="tier-item">
          <div class="tier-item__label">Tier 3 · 病历全文</div>
          <div class="tier-item__value">{{ mongoSyncState.tier3_synced || 0 }} 条</div>
          <div class="tier-item__time">{{ mongoSyncState.tier3_last_run || '从未运行' }}</div>
        </div>
      </div>
    </a-card>

    <!-- 抽取策略配置 -->
    <a-card title="抽取策略配置" :bordered="false" class="sync-strategy-card">
      <template #extra>
        <a-button type="primary" size="small" @click="saveMongoConfig" :loading="configSaving">
          保存配置
        </a-button>
      </template>

      <a-form layout="vertical">
        <a-divider orientation="left">采集窗口</a-divider>
        <a-row :gutter="[24, 16]">
          <a-col :xs="24" :md="8">
            <a-form-item label="出院稳定窗口 (天)">
              <a-input-number v-model:value="configForm.discharge_stable_days" :min="0" :max="30" style="width: 100%" />
              <div class="qc-setting-hint">出院后 N 天才纳入终末质控抽取</div>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="回看窗口 (分钟)">
              <a-input-number v-model:value="configForm.lookback_minutes" :min="0" :max="120" style="width: 100%" />
              <div class="qc-setting-hint">水位线回退 N 分钟，防止同毫秒漏数</div>
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="滚动重扫 (天)">
              <a-input-number v-model:value="configForm.rescan_recent_days" :min="0" :max="30" style="width: 100%" />
              <div class="qc-setting-hint">最近 N 天晚到修订强制重查</div>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">调度频率</a-divider>
        <a-row :gutter="[24, 16]">
          <a-col :xs="24" :md="8">
            <a-form-item label="Tier1 频率 (分钟)">
              <a-input-number v-model:value="configForm.tier1_interval_minutes" :min="5" :max="1440" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="Tier2 频率 (分钟)">
              <a-input-number v-model:value="configForm.tier2_interval_minutes" :min="10" :max="1440" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="Tier3 Cron 表达式">
              <a-input v-model:value="configForm.tier3_cron" placeholder="0 2 * * *" />
              <div class="qc-setting-hint">病历全文抽取定时（默认凌晨 2 点）</div>
            </a-form-item>
          </a-col>
        </a-row>

        <a-divider orientation="left">速率保护</a-divider>
        <a-row :gutter="[24, 16]">
          <a-col :xs="24" :md="8">
            <a-form-item label="单批数量">
              <a-input-number v-model:value="configForm.max_batch_size" :min="10" :max="1000" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="请求间隔 (ms)">
              <a-input-number v-model:value="configForm.inter_request_delay_ms" :min="50" :max="5000" :step="50" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :xs="24" :md="8">
            <a-form-item label="夜间窗口">
              <div style="display: flex; align-items: center; gap: 8px">
                <a-input v-model:value="configForm.night_window_start" placeholder="22:00" style="width: 100px" />
                <span style="color: #94a3b8">—</span>
                <a-input v-model:value="configForm.night_window_end" placeholder="06:00" style="width: 100px" />
              </div>
              <div class="qc-setting-hint">Tier3 全文仅在夜间窗口执行</div>
            </a-form-item>
          </a-col>
        </a-row>
      </a-form>
    </a-card>

    <!-- MongoDB 连接编辑弹窗 -->
    <a-modal
      v-model:open="showMongoModal"
      title="MongoDB 连接配置"
      :confirm-loading="connSaving"
      @ok="saveMongoConnection"
      ok-text="保存并测试"
      cancel-text="取消"
      :width="520"
    >
      <div style="padding-top: 8px">
        <a-alert
          message="建议使用只读账号 + secondaryPreferred 读偏好，避免影响临床主库写入"
          type="info"
          show-icon
          style="margin-bottom: 16px"
        />
        <a-form layout="vertical">
          <a-form-item label="连接 URI">
            <a-input v-model:value="connForm.mongo_uri" placeholder="mongodb://user:pass@host:27017/db" />
            <div class="qc-setting-hint">支持 mongodb:// 和 mongodb+srv://，TLS 可在 URI 中加 ?tls=true</div>
          </a-form-item>
          <a-form-item label="数据库名">
            <a-input v-model:value="connForm.mongo_database" placeholder="his_emr" />
          </a-form-item>
          <a-form-item label="读偏好">
            <a-select v-model:value="connForm.read_preference" style="width: 100%">
              <a-select-option value="secondaryPreferred">secondaryPreferred（推荐：优先从库）</a-select-option>
              <a-select-option value="secondary">secondary（仅从库）</a-select-option>
              <a-select-option value="primaryPreferred">primaryPreferred（优先主库）</a-select-option>
              <a-select-option value="nearest">nearest（最近节点）</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item label="连接超时 (ms)">
            <a-input-number v-model:value="connForm.connect_timeout_ms" :min="1000" :max="30000" :step="1000" style="width: 100%" />
          </a-form-item>
        </a-form>
        <div v-if="connTestResult" style="margin-top: 12px">
          <a-alert
            :type="connTestResult.connected ? 'success' : 'error'"
            :message="connTestResult.connected ? '✅ 连接成功 — MongoDB v' + (connTestResult.version || '') : '❌ 连接失败'"
            :description="connTestResult.error || ''"
            show-icon
          />
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
import {
  SyncOutlined,
  ReloadOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'

// ========== 状态 ==========
const mongoConfig = ref<any>({})
const mongoSyncState = ref<any>({})
const mongoStats = ref<any>({ PENDING: 0, PARTIAL: 0, SYNCED: 0, STALE: 0, FAILED: 0 })
const mongoStatus = ref<any>({ connected: false })
const mongoSyncTier = ref('all')

// 连接弹窗
const showMongoModal = ref(false)
const connSaving = ref(false)
const connTestResult = ref<any>(null)
const connForm = ref({
  mongo_uri: '',
  mongo_database: 'his_emr',
  read_preference: 'secondaryPreferred',
  connect_timeout_ms: 5000,
})

// 策略表单
const configSaving = ref(false)
const configForm = ref({
  discharge_stable_days: 3,
  lookback_minutes: 10,
  rescan_recent_days: 7,
  tier1_interval_minutes: 30,
  tier2_interval_minutes: 120,
  tier3_cron: '0 2 * * *',
  max_batch_size: 100,
  inter_request_delay_ms: 200,
  night_window_start: '22:00',
  night_window_end: '06:00',
  enabled: false,
})

// ========== API ==========
async function loadMongoConfig() {
  try {
    const { data } = await axios.get('/api/v1/sync/config/mongo')
    mongoConfig.value = data
    connForm.value = {
      mongo_uri: '',
      mongo_database: data.mongo_database || 'his_emr',
      read_preference: data.read_preference || 'secondaryPreferred',
      connect_timeout_ms: data.connect_timeout_ms || 5000,
    }
    configForm.value = {
      discharge_stable_days: data.discharge_stable_days ?? 3,
      lookback_minutes: data.lookback_minutes ?? 10,
      rescan_recent_days: data.rescan_recent_days ?? 7,
      tier1_interval_minutes: data.tier1_interval_minutes ?? 30,
      tier2_interval_minutes: data.tier2_interval_minutes ?? 120,
      tier3_cron: data.tier3_cron || '0 2 * * *',
      max_batch_size: data.max_batch_size ?? 100,
      inter_request_delay_ms: data.inter_request_delay_ms ?? 200,
      night_window_start: data.night_window_start || '22:00',
      night_window_end: data.night_window_end || '06:00',
      enabled: data.enabled ?? false,
    }
  } catch (err) {
    console.error('获取 MongoDB 配置失败:', err)
  }
}

async function loadMongoStatus() {
  try {
    const [statusRes, statsRes] = await Promise.all([
      axios.get('/api/v1/sync/status'),
      axios.get('/api/v1/sync/statistics'),
    ])
    mongoSyncState.value = statusRes.data?.mongo_sync || {}
    mongoStats.value = statsRes.data || {}
    mongoStatus.value = { connected: mongoSyncState.value.connected || false }
  } catch (err) {
    console.error('获取 MongoDB 状态失败:', err)
  }
}

async function saveMongoConnection() {
  connSaving.value = true
  connTestResult.value = null
  try {
    const payload: any = {
      mongo_database: connForm.value.mongo_database,
      read_preference: connForm.value.read_preference,
      connect_timeout_ms: connForm.value.connect_timeout_ms,
    }
    if (connForm.value.mongo_uri) payload.mongo_uri = connForm.value.mongo_uri
    await axios.put('/api/v1/sync/config/mongo', payload)

    const { data } = await axios.post('/api/v1/sync/test-connection/mongo')
    connTestResult.value = data
    if (data.connected) {
      message.success('MongoDB 连接成功！')
      showMongoModal.value = false
      await loadMongoConfig()
      await loadMongoStatus()
    } else {
      message.warning('配置已保存，但连接失败')
    }
  } catch (err) {
    message.error('保存失败')
  } finally {
    connSaving.value = false
  }
}

async function saveMongoConfig() {
  configSaving.value = true
  try {
    await axios.put('/api/v1/sync/config/mongo', configForm.value)
    message.success('抽取策略配置已保存')
    await loadMongoConfig()
  } catch (err) {
    message.error('保存失败')
  } finally {
    configSaving.value = false
  }
}

async function toggleEnabled(checked: boolean) {
  try {
    await axios.put('/api/v1/sync/config/mongo', { enabled: checked })
    message.success(checked ? '同步已启用' : '同步已关闭')
    await loadMongoConfig()
  } catch (err) {
    message.error('操作失败')
  }
}

async function triggerMongoSync() {
  try {
    const { data } = await axios.post('/api/v1/sync/trigger', {
      source: 'mongo',
      tier: mongoSyncTier.value,
    })
    if (data.success) {
      message.success('同步任务已启动')
    } else {
      message.warning(data.error || '同步启动失败')
    }
    const poll = setInterval(async () => {
      await loadMongoStatus()
      if (!mongoSyncState.value.is_running) clearInterval(poll)
    }, 2000)
  } catch (err) {
    message.error('触发同步失败')
  }
}

// ========== 初始化 ==========
onMounted(async () => {
  await Promise.all([loadMongoConfig(), loadMongoStatus()])
})
</script>

<style scoped>
.data-sync-config {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.sync-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.sync-conn-card {
  border-radius: 12px;
  background: var(--color-bg-elevated, #fff);
}
.conn-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.conn-header__left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.conn-header__right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.conn-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.conn-icon--mongo {
  background: linear-gradient(135deg, #10b981, #0d9488);
}
.conn-icon__text {
  color: #fff;
  font-size: 14px;
  font-weight: 900;
}
.conn-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #1e293b);
}
.conn-subtitle {
  font-size: 12px;
  color: var(--color-text-tertiary, #94a3b8);
}
.conn-details {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.conn-detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}
.conn-detail-label {
  color: var(--color-text-tertiary, #64748b);
}
.conn-detail-value {
  color: var(--color-text-primary, #334155);
  font-size: 12px;
}
.conn-detail-value.mono {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conn-status-tag {
  border-radius: 12px;
  font-size: 12px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
}
.stat-item {
  text-align: center;
  padding: 10px 4px;
  border-radius: 10px;
  border: 1px solid transparent;
}
.stat-item--blue { background: #eff6ff; border-color: #dbeafe; }
.stat-item--amber { background: #fffbeb; border-color: #fef3c7; }
.stat-item--green { background: #f0fdf4; border-color: #dcfce7; }
.stat-item--orange { background: #fff7ed; border-color: #ffedd5; }
.stat-item--red { background: #fef2f2; border-color: #fecaca; }
.stat-value {
  font-size: 20px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-item--blue .stat-value { color: #2563eb; }
.stat-item--amber .stat-value { color: #d97706; }
.stat-item--green .stat-value { color: #16a34a; }
.stat-item--orange .stat-value { color: #ea580c; }
.stat-item--red .stat-value { color: #dc2626; }
.stat-label {
  font-size: 11px;
  color: #64748b;
  margin-top: 2px;
}

.sync-action-card {
  border-radius: 12px;
}
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.action-bar__right {
  display: flex;
  gap: 8px;
}
.action-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #1e293b);
}
.action-hint {
  font-size: 12px;
  color: var(--color-text-tertiary, #94a3b8);
  margin-left: 8px;
}
.tier-status-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.tier-item {
  padding: 12px;
  border-radius: 10px;
  background: var(--color-bg-tertiary, #f8fafc);
  border: 1px solid var(--color-border, #e2e8f0);
}
.tier-item__label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-tertiary, #94a3b8);
  margin-bottom: 4px;
}
.tier-item__value {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary, #334155);
}
.tier-item__time {
  font-size: 11px;
  color: var(--color-text-tertiary, #94a3b8);
  margin-top: 2px;
}

.sync-strategy-card {
  border-radius: 12px;
}
.qc-setting-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
