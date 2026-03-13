<template>
  <div class="data-sync-root">

    <!-- ============ 区块 1: MongoDB 数据源 ============ -->
    <div class="config-section">
      <div class="config-section__header">
        <h2 class="config-section__title">MongoDB 数据源</h2>
        <p class="config-section__desc">管理对端 HIS MongoDB 的连接信息和读取偏好</p>
      </div>
      <div class="config-section__body divide-y divide-slate-100">
        <!-- 连接状态 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">连接状态</h3>
            <p class="config-row__hint">当前数据源的连通性。需要在医院内网环境才能连通。</p>
          </div>
          <div class="config-row__right">
            <span v-if="mongoStatus.connected" class="status-pill status-pill--ok">已连接</span>
            <span v-else class="status-pill status-pill--off">未配置</span>
          </div>
        </div>
        <!-- URI -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">连接 URI</h3>
            <p class="config-row__hint">MongoDB 连接地址（密码已脱敏）</p>
          </div>
          <div class="config-row__right">
            <code class="config-row__mono">{{ mongoConfig.mongo_uri_display || '未配置' }}</code>
          </div>
        </div>
        <!-- Database -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">数据库</h3>
            <p class="config-row__hint">目标 MongoDB 数据库名称</p>
          </div>
          <div class="config-row__right">
            <code class="config-row__mono">{{ mongoConfig.mongo_database || '—' }}</code>
          </div>
        </div>
        <!-- 读偏好 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">读偏好</h3>
            <p class="config-row__hint">
              <code class="code-inline">secondaryPreferred</code> 可避免影响临床主库写入
            </p>
          </div>
          <div class="config-row__right">
            <span class="text-sm text-slate-700">{{ mongoConfig.read_preference || '—' }}</span>
          </div>
        </div>
        <!-- 操作 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">连接配置</h3>
            <p class="config-row__hint">修改 URI、数据库名、读偏好和超时参数</p>
          </div>
          <div class="config-row__right">
            <button class="btn-outline" @click="showMongoModal = true">编辑连接</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ============ 区块 2: 同步概览 ============ -->
    <div class="config-section">
      <div class="config-section__header">
        <div>
          <h2 class="config-section__title">同步概览</h2>
          <p class="config-section__desc">Visit 同步状态分布与各 Tier 运行情况</p>
        </div>
        <div class="config-section__actions">
          <button class="btn-outline btn-sm" @click="loadMongoStatus">
            <ReloadOutlined style="font-size: 12px" /> 刷新
          </button>
        </div>
      </div>
      <div class="config-section__body">
        <!-- 状态统计 — 克制版 -->
        <div class="stats-bar">
          <div class="stats-bar__item">
            <span class="stats-bar__dot stats-bar__dot--slate"></span>
            <span class="stats-bar__num">{{ mongoStats.PENDING || 0 }}</span>
            <span class="stats-bar__label">待抽取</span>
          </div>
          <div class="stats-bar__divider"></div>
          <div class="stats-bar__item">
            <span class="stats-bar__dot stats-bar__dot--amber"></span>
            <span class="stats-bar__num">{{ mongoStats.PARTIAL || 0 }}</span>
            <span class="stats-bar__label">部分同步</span>
          </div>
          <div class="stats-bar__divider"></div>
          <div class="stats-bar__item">
            <span class="stats-bar__dot stats-bar__dot--green"></span>
            <span class="stats-bar__num">{{ mongoStats.SYNCED || 0 }}</span>
            <span class="stats-bar__label">已完成</span>
          </div>
          <div class="stats-bar__divider"></div>
          <div class="stats-bar__item">
            <span class="stats-bar__dot stats-bar__dot--orange"></span>
            <span class="stats-bar__num">{{ mongoStats.STALE || 0 }}</span>
            <span class="stats-bar__label">需重拉</span>
          </div>
          <div class="stats-bar__divider"></div>
          <div class="stats-bar__item">
            <span class="stats-bar__dot stats-bar__dot--red"></span>
            <span class="stats-bar__num">{{ mongoStats.FAILED || 0 }}</span>
            <span class="stats-bar__label">失败</span>
          </div>
        </div>

        <!-- Tier 运行状态 -->
        <div class="divide-y divide-slate-100 mt-1">
          <div class="config-row config-row--compact">
            <div class="config-row__left">
              <h3 class="config-row__label">Tier 1 · 索引发现</h3>
              <p class="config-row__hint">轻量扫描出院索引，发现新增 visit</p>
            </div>
            <div class="config-row__right config-row__right--stats">
              <span class="stats-value">{{ mongoSyncState.tier1_discovered || 0 }} 条</span>
              <span class="stats-time">{{ mongoSyncState.tier1_last_run || '从未运行' }}</span>
            </div>
          </div>
          <div class="config-row config-row--compact">
            <div class="config-row__left">
              <h3 class="config-row__label">Tier 2 · 结构化数据</h3>
              <p class="config-row__hint">首页、诊断、手术、费用 4 张核心表</p>
            </div>
            <div class="config-row__right config-row__right--stats">
              <span class="stats-value">{{ mongoSyncState.tier2_synced || 0 }} 条</span>
              <span class="stats-time">{{ mongoSyncState.tier2_last_run || '从未运行' }}</span>
            </div>
          </div>
          <div class="config-row config-row--compact">
            <div class="config-row__left">
              <h3 class="config-row__label">Tier 3 · 病历全文</h3>
              <p class="config-row__hint">23 类文书全量拉取（仅夜间窗口执行）</p>
            </div>
            <div class="config-row__right config-row__right--stats">
              <span class="stats-value">{{ mongoSyncState.tier3_synced || 0 }} 条</span>
              <span class="stats-time">{{ mongoSyncState.tier3_last_run || '从未运行' }}</span>
            </div>
          </div>
        </div>
      </div>
      <!-- 底栏：手动触发 -->
      <div class="config-section__footer">
        <div class="config-section__footer-hint">
          <span v-if="!mongoConfig.enabled" class="text-amber-600 text-xs">⚠ 同步已关闭，需先在下方启用</span>
        </div>
        <div class="config-section__footer-actions">
          <select v-model="mongoSyncTier" class="select-native">
            <option value="all">全部 Tier</option>
            <option value="tier1">Tier1 · 索引</option>
            <option value="tier2">Tier2 · 结构</option>
            <option value="tier3">Tier3 · 全文</option>
          </select>
          <button class="btn-primary" @click="triggerMongoSync" :disabled="!mongoConfig.enabled || mongoSyncState.is_running">
            <SyncOutlined v-if="!mongoSyncState.is_running" style="font-size: 12px" />
            <a-spin v-else size="small" />
            执行同步
          </button>
        </div>
      </div>
    </div>

    <!-- ============ 区块 3: 抽取策略配置 ============ -->
    <div class="config-section">
      <div class="config-section__header">
        <div>
          <h2 class="config-section__title">抽取策略配置</h2>
          <p class="config-section__desc">控制数据抽取的节奏、窗口与速率保护参数</p>
        </div>
      </div>
      <div class="config-section__body divide-y divide-slate-100">
        <!-- 同步开关 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">同步总开关</h3>
            <p class="config-row__hint">开启后系统将按设定频率自动执行增量抽取。关闭后仅可手动触发。</p>
          </div>
          <div class="config-row__right">
            <a-switch
              v-model:checked="configForm.enabled"
              checked-children="启用"
              un-checked-children="关闭"
            />
          </div>
        </div>
        <!-- 出院稳定窗口 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">出院稳定窗口</h3>
            <p class="config-row__hint">
              出院后等待 N 天才纳入终末质控抽取。等待期间编码员完成 ICD 编码、费用结算和文书补录。
            </p>
          </div>
          <div class="config-row__right">
            <div class="input-with-unit">
              <a-input-number v-model:value="configForm.discharge_stable_days" :min="0" :max="30" class="input-num" />
              <span class="input-unit">天</span>
            </div>
          </div>
        </div>
        <!-- 回看窗口 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">回看窗口</h3>
            <p class="config-row__hint">
              水位线回退 N 分钟重新扫描，对冲时钟漂移和同毫秒时间戳导致的漏数风险。
            </p>
          </div>
          <div class="config-row__right">
            <div class="input-with-unit">
              <a-input-number v-model:value="configForm.lookback_minutes" :min="0" :max="120" class="input-num" />
              <span class="input-unit">分钟</span>
            </div>
          </div>
        </div>
        <!-- 滚动重扫 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">滚动重扫</h3>
            <p class="config-row__hint">
              最近 N 天内有修订的已完成 visit 将被标记为
              <code class="code-inline">STALE</code> 并强制重拉，防止晚到修订遗漏。
            </p>
          </div>
          <div class="config-row__right">
            <div class="input-with-unit">
              <a-input-number v-model:value="configForm.rescan_recent_days" :min="0" :max="30" class="input-num" />
              <span class="input-unit">天</span>
            </div>
          </div>
        </div>
        <!-- Tier1 频率 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">Tier 1 索引发现频率</h3>
            <p class="config-row__hint">轻量查询，可较高频率执行。建议 15 - 60 分钟。</p>
          </div>
          <div class="config-row__right">
            <div class="input-with-unit">
              <a-input-number v-model:value="configForm.tier1_interval_minutes" :min="5" :max="1440" class="input-num" />
              <span class="input-unit">分钟</span>
            </div>
          </div>
        </div>
        <!-- Tier2 频率 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">Tier 2 结构化拉取频率</h3>
            <p class="config-row__hint">每次拉取 4 张表，开销中等。建议 60 - 240 分钟。</p>
          </div>
          <div class="config-row__right">
            <div class="input-with-unit">
              <a-input-number v-model:value="configForm.tier2_interval_minutes" :min="10" :max="1440" class="input-num" />
              <span class="input-unit">分钟</span>
            </div>
          </div>
        </div>
        <!-- Tier3 Cron -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">Tier 3 全文抽取定时</h3>
            <p class="config-row__hint">
              Cron 表达式。全文抽取开销最大，建议仅在夜间低峰执行。默认
              <code class="code-inline">0 2 * * *</code> 即凌晨 2 点。
            </p>
          </div>
          <div class="config-row__right">
            <a-input v-model:value="configForm.tier3_cron" placeholder="0 2 * * *" class="input-text" />
          </div>
        </div>
        <!-- 单批数量 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">单批处理数量</h3>
            <p class="config-row__hint">每次同步最多处理的 visit 数。越大吞吐越高，但对端压力也越大。</p>
          </div>
          <div class="config-row__right">
            <div class="input-with-unit">
              <a-input-number v-model:value="configForm.max_batch_size" :min="10" :max="1000" class="input-num" />
              <span class="input-unit">条</span>
            </div>
          </div>
        </div>
        <!-- 请求间隔 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">请求间隔</h3>
            <p class="config-row__hint">两次 MongoDB 查询之间的等待时间，防止并发过高冲击对端数据库。</p>
          </div>
          <div class="config-row__right">
            <div class="input-with-unit">
              <a-input-number v-model:value="configForm.inter_request_delay_ms" :min="50" :max="5000" :step="50" class="input-num" />
              <span class="input-unit">ms</span>
            </div>
          </div>
        </div>
        <!-- 夜间窗口 -->
        <div class="config-row">
          <div class="config-row__left">
            <h3 class="config-row__label">夜间窗口</h3>
            <p class="config-row__hint">仅在此时间段内允许 Tier 3 全文抽取，保护白天临床生产时段。</p>
          </div>
          <div class="config-row__right">
            <div class="input-time-range">
              <a-input v-model:value="configForm.night_window_start" placeholder="22:00" class="input-time" />
              <span class="input-time-sep">—</span>
              <a-input v-model:value="configForm.night_window_end" placeholder="06:00" class="input-time" />
            </div>
          </div>
        </div>
      </div>
      <!-- 底栏：保存 -->
      <div class="config-section__footer">
        <button class="btn-ghost" @click="loadMongoConfig">取消更改</button>
        <button class="btn-primary" @click="saveMongoConfig" :disabled="configSaving">
          保存配置
        </button>
      </div>
    </div>

    <!-- ============ MongoDB 连接编辑弹窗 ============ -->
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
            <div class="form-hint">支持 mongodb:// 和 mongodb+srv://，TLS 在 URI 中加 ?tls=true</div>
          </a-form-item>
          <a-form-item label="数据库名">
            <a-input v-model:value="connForm.mongo_database" placeholder="his_emr" />
          </a-form-item>
          <a-form-item label="读偏好">
            <a-select v-model:value="connForm.read_preference" style="width: 100%">
              <a-select-option value="secondaryPreferred">secondaryPreferred（推荐）</a-select-option>
              <a-select-option value="secondary">secondary（仅从库）</a-select-option>
              <a-select-option value="primaryPreferred">primaryPreferred</a-select-option>
              <a-select-option value="nearest">nearest</a-select-option>
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
import { SyncOutlined, ReloadOutlined } from '@ant-design/icons-vue'

// ========== 状态 ==========
const mongoConfig = ref<any>({})
const mongoSyncState = ref<any>({})
const mongoStats = ref<any>({ PENDING: 0, PARTIAL: 0, SYNCED: 0, STALE: 0, FAILED: 0 })
const mongoStatus = ref<any>({ connected: false })
const mongoSyncTier = ref('all')

const showMongoModal = ref(false)
const connSaving = ref(false)
const connTestResult = ref<any>(null)
const connForm = ref({
  mongo_uri: '',
  mongo_database: 'his_emr',
  read_preference: 'secondaryPreferred',
  connect_timeout_ms: 5000,
})

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

onMounted(async () => {
  await Promise.all([loadMongoConfig(), loadMongoStatus()])
})
</script>

<style scoped>
/* ==================== 设计系统 Token ==================== */
.data-sync-root {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ---- 区块容器 ---- */
.config-section {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}
.config-section__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid #f1f5f9;
}
.config-section__title {
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  line-height: 1.4;
}
.config-section__desc {
  font-size: 13px;
  color: #64748b;
  margin: 2px 0 0;
  line-height: 1.4;
}
.config-section__body {
  /* divide-y 由 tailwind 类驱动 */
}
.config-section__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  padding: 12px 24px;
  background: #f8fafc;
  border-top: 1px solid #e2e8f0;
}
.config-section__footer-hint {
  flex: 1;
}
.config-section__footer-actions {
  display: flex;
  gap: 8px;
}
.config-section__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

/* ---- 同行配置项（核心：左文案 + 右操作） ---- */
.config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 24px;
  transition: background 0.15s ease;
}
.config-row:hover {
  background: rgba(248, 250, 252, 0.6);
}
.config-row--compact {
  padding: 12px 24px;
}
.config-row__left {
  flex: 1;
  min-width: 0;
}
.config-row__label {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
  line-height: 1.4;
}
.config-row__hint {
  font-size: 12.5px;
  color: #94a3b8;
  margin: 2px 0 0;
  line-height: 1.5;
  max-width: 480px;
}
.config-row__right {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.config-row__right--stats {
  flex-direction: column;
  align-items: flex-end;
  gap: 0;
}
.config-row__mono {
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  font-size: 12px;
  color: #334155;
  background: #f1f5f9;
  padding: 3px 8px;
  border-radius: 5px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- 状态药丸 ---- */
.status-pill {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  letter-spacing: 0.01em;
}
.status-pill--ok {
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #dcfce7;
}
.status-pill--off {
  background: #f8fafc;
  color: #94a3b8;
  border: 1px solid #e2e8f0;
}

/* ---- 状态条（克制版：白底 + 小圆点 + 数字） ---- */
.stats-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 20px 24px;
}
.stats-bar__item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
}
.stats-bar__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.stats-bar__dot--slate  { background: #94a3b8; }
.stats-bar__dot--amber  { background: #f59e0b; }
.stats-bar__dot--green  { background: #22c55e; }
.stats-bar__dot--orange { background: #f97316; }
.stats-bar__dot--red    { background: #ef4444; }
.stats-bar__num {
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
  font-variant-numeric: tabular-nums;
}
.stats-bar__label {
  font-size: 12px;
  color: #94a3b8;
}
.stats-bar__divider {
  width: 1px;
  height: 24px;
  background: #e2e8f0;
}
.stats-value {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}
.stats-time {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 1px;
}

/* ---- 按钮 ---- */
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 16px;
  background: #2563eb;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  border: none;
  border-radius: 7px;
  cursor: pointer;
  transition: background 0.15s;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.18);
}
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  background: #fff;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-outline:hover { background: #f8fafc; color: #1e293b; }
.btn-ghost {
  padding: 7px 14px;
  background: none;
  border: none;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s;
}
.btn-ghost:hover { color: #1e293b; }
.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

/* ---- 表单控件 ---- */
.input-with-unit {
  display: flex;
  align-items: center;
  gap: 6px;
}
.input-num {
  width: 90px !important;
}
.input-num :deep(.ant-input-number-input) {
  text-align: center;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px;
}
.input-unit {
  font-size: 13px;
  color: #64748b;
  font-weight: 500;
  min-width: 28px;
}
.input-text {
  width: 160px !important;
}
.input-text :deep(.ant-input) {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px;
}
.input-time-range {
  display: flex;
  align-items: center;
  gap: 6px;
}
.input-time {
  width: 80px !important;
}
.input-time :deep(.ant-input) {
  text-align: center;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px;
}
.input-time-sep {
  color: #94a3b8;
  font-size: 14px;
}
.select-native {
  appearance: none;
  padding: 6px 28px 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M3 4.5L6 7.5L9 4.5' stroke='%2394a3b8' fill='none' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") right 10px center no-repeat;
  font-size: 13px;
  font-weight: 500;
  color: #334155;
  cursor: pointer;
  outline: none;
}
.select-native:focus { border-color: #2563eb; box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12); }

/* ---- 行内 code ---- */
.code-inline {
  background: #f1f5f9;
  color: #475569;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11.5px;
  border: 1px solid #e2e8f0;
}
.form-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
}
</style>
