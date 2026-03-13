<template>
  <div class="ds-root">

    <!-- ══════════ Section 1: MongoDB 数据源 ══════════ -->
    <div class="ds-split">
      <!-- 左 1/3：解释区 -->
      <div class="ds-split__aside">
        <h2 class="ds-section-title">MongoDB 数据源</h2>
        <p class="ds-section-desc">
          管理对端 HIS MongoDB 的连接信息和读取偏好。建议使用只读账号 +
          <code class="ds-code">secondaryPreferred</code> 读偏好，避免影响临床主库。
        </p>
      </div>
      <!-- 右 2/3：操作区 -->
      <div class="ds-split__main">
        <div class="ds-card">
          <div class="ds-card__rows">
            <div class="ds-row">
              <div class="ds-row__left">
                <span class="ds-row__label">连接状态</span>
              </div>
              <span v-if="mongoStatus.connected" class="ds-pill ds-pill--ok">已连接</span>
              <span v-else class="ds-pill ds-pill--off">未配置</span>
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <span class="ds-row__label">连接 URI</span>
                <span class="ds-row__sub">密码已脱敏</span>
              </div>
              <code class="ds-mono-badge">{{ mongoConfig.mongo_uri_display || '未配置' }}</code>
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <span class="ds-row__label">数据库</span>
              </div>
              <code class="ds-mono-badge">{{ mongoConfig.mongo_database || '—' }}</code>
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <span class="ds-row__label">读偏好</span>
              </div>
              <span class="ds-text-sm">{{ mongoConfig.read_preference || '—' }}</span>
            </div>
          </div>
          <div class="ds-card__footer">
            <button class="ds-btn ds-btn--outline" @click="showMongoModal = true">编辑连接</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════ Section 2: 同步概览 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">同步概览</h2>
        <p class="ds-section-desc">
          Visit 生命周期状态分布与各 Tier 最近运行情况。
          只有 <code class="ds-code">SYNCED</code> 状态的 visit 才对质控引擎可见。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <!-- 统计条：白底 + 小圆点 -->
          <div class="ds-stats-row">
            <div class="ds-stat">
              <span class="ds-stat__dot ds-stat__dot--slate"></span>
              <span class="ds-stat__num">{{ mongoStats.PENDING || 0 }}</span>
              <span class="ds-stat__label">待抽取</span>
            </div>
            <div class="ds-stat__sep"></div>
            <div class="ds-stat">
              <span class="ds-stat__dot ds-stat__dot--amber"></span>
              <span class="ds-stat__num">{{ mongoStats.PARTIAL || 0 }}</span>
              <span class="ds-stat__label">部分同步</span>
            </div>
            <div class="ds-stat__sep"></div>
            <div class="ds-stat">
              <span class="ds-stat__dot ds-stat__dot--green"></span>
              <span class="ds-stat__num">{{ mongoStats.SYNCED || 0 }}</span>
              <span class="ds-stat__label">已完成</span>
            </div>
            <div class="ds-stat__sep"></div>
            <div class="ds-stat">
              <span class="ds-stat__dot ds-stat__dot--orange"></span>
              <span class="ds-stat__num">{{ mongoStats.STALE || 0 }}</span>
              <span class="ds-stat__label">需重拉</span>
            </div>
            <div class="ds-stat__sep"></div>
            <div class="ds-stat">
              <span class="ds-stat__dot ds-stat__dot--red"></span>
              <span class="ds-stat__num">{{ mongoStats.FAILED || 0 }}</span>
              <span class="ds-stat__label">失败</span>
            </div>
          </div>
          <!-- Tier 状态 -->
          <div class="ds-card__rows">
            <div class="ds-row">
              <div class="ds-row__left">
                <span class="ds-row__label">Tier 1 · 索引发现</span>
                <span class="ds-row__sub">轻量扫描出院索引</span>
              </div>
              <div class="ds-row__right-stack">
                <span class="ds-text-semibold">{{ mongoSyncState.tier1_discovered || 0 }} 条</span>
                <span class="ds-text-xs">{{ mongoSyncState.tier1_last_run || '从未运行' }}</span>
              </div>
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <span class="ds-row__label">Tier 2 · 结构化数据</span>
                <span class="ds-row__sub">首页、诊断、手术、费用</span>
              </div>
              <div class="ds-row__right-stack">
                <span class="ds-text-semibold">{{ mongoSyncState.tier2_synced || 0 }} 条</span>
                <span class="ds-text-xs">{{ mongoSyncState.tier2_last_run || '从未运行' }}</span>
              </div>
            </div>
            <div class="ds-row">
              <div class="ds-row__left">
                <span class="ds-row__label">Tier 3 · 病历全文</span>
                <span class="ds-row__sub">23 类文书（仅夜间窗口）</span>
              </div>
              <div class="ds-row__right-stack">
                <span class="ds-text-semibold">{{ mongoSyncState.tier3_synced || 0 }} 条</span>
                <span class="ds-text-xs">{{ mongoSyncState.tier3_last_run || '从未运行' }}</span>
              </div>
            </div>
          </div>
          <!-- 底栏：触发 -->
          <div class="ds-card__footer">
            <span v-if="!mongoConfig.enabled" class="ds-text-warn">⚠ 同步已关闭，需先启用</span>
            <span v-else></span>
            <div class="ds-card__footer-right">
              <select v-model="mongoSyncTier" class="ds-select-native">
                <option value="all">全部 Tier</option>
                <option value="tier1">Tier1 索引</option>
                <option value="tier2">Tier2 结构</option>
                <option value="tier3">Tier3 全文</option>
              </select>
              <button class="ds-btn ds-btn--primary" @click="triggerMongoSync"
                :disabled="!mongoConfig.enabled || mongoSyncState.is_running">
                <SyncOutlined v-if="!mongoSyncState.is_running" style="font-size:12px" />
                执行同步
              </button>
              <button class="ds-btn ds-btn--ghost" @click="loadMongoStatus">
                <ReloadOutlined style="font-size:12px" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════ Section 3: 抽取策略配置 ══════════ -->
    <div class="ds-split">
      <div class="ds-split__aside">
        <h2 class="ds-section-title">抽取策略配置</h2>
        <p class="ds-section-desc">
          控制数据抽取的节奏、窗口与速率保护参数。调整这些参数将直接影响 HIS 数据库的读取压力，请在非业务高峰期谨慎修改。
        </p>
      </div>
      <div class="ds-split__main">
        <div class="ds-card">
          <!-- 置顶：全局开关 -->
          <div class="ds-switch-banner">
            <div>
              <div class="ds-row__label">全局同步总开关</div>
              <div class="ds-row__sub">开启后系统将按设定频率自动执行增量抽取</div>
            </div>
            <a-switch v-model:checked="configForm.enabled" checked-children="启用" un-checked-children="关闭" />
          </div>

          <!-- 采集窗口 — 双列网格 -->
          <div class="ds-grid-section">
            <div class="ds-grid-section__label">采集窗口</div>
            <div class="ds-grid">
              <div class="ds-field">
                <label class="ds-field__label">出院稳定窗口</label>
                <div class="ds-field__hint">出院后等待 N 天才纳入终末质控</div>
                <div class="ds-input-group">
                  <a-input-number v-model:value="configForm.discharge_stable_days" :min="0" :max="30" :controls="false" class="ds-input-group__input" />
                  <span class="ds-input-group__suffix">天</span>
                </div>
              </div>
              <div class="ds-field">
                <label class="ds-field__label">回看窗口</label>
                <div class="ds-field__hint">水位线回退 N 分钟，防时钟漂移漏数</div>
                <div class="ds-input-group">
                  <a-input-number v-model:value="configForm.lookback_minutes" :min="0" :max="120" :controls="false" class="ds-input-group__input" />
                  <span class="ds-input-group__suffix">分钟</span>
                </div>
              </div>
              <div class="ds-field">
                <label class="ds-field__label">滚动重扫</label>
                <div class="ds-field__hint">最近 N 天修订的已完成 visit 强制重拉</div>
                <div class="ds-input-group">
                  <a-input-number v-model:value="configForm.rescan_recent_days" :min="0" :max="30" :controls="false" class="ds-input-group__input" />
                  <span class="ds-input-group__suffix">天</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 调度频率 — 双列网格 -->
          <div class="ds-grid-section">
            <div class="ds-grid-section__label">调度频率</div>
            <div class="ds-grid">
              <div class="ds-field">
                <label class="ds-field__label">Tier 1 索引发现</label>
                <div class="ds-field__hint">轻量查询，建议 15 - 60 分钟</div>
                <div class="ds-input-group">
                  <a-input-number v-model:value="configForm.tier1_interval_minutes" :min="5" :max="1440" :controls="false" class="ds-input-group__input" />
                  <span class="ds-input-group__suffix">分钟</span>
                </div>
              </div>
              <div class="ds-field">
                <label class="ds-field__label">Tier 2 结构化拉取</label>
                <div class="ds-field__hint">中等开销，建议 60 - 240 分钟</div>
                <div class="ds-input-group">
                  <a-input-number v-model:value="configForm.tier2_interval_minutes" :min="10" :max="1440" :controls="false" class="ds-input-group__input" />
                  <span class="ds-input-group__suffix">分钟</span>
                </div>
              </div>
            </div>
            <!-- Tier3 Cron 单独一行（跨列） -->
            <div class="ds-field ds-field--wide">
              <label class="ds-field__label">Tier 3 全文抽取定时</label>
              <div class="ds-field__hint">Cron 表达式，开销最大，建议仅夜间执行</div>
              <div class="ds-cron-input">
                <a-input v-model:value="configForm.tier3_cron" placeholder="0 2 * * *" class="ds-cron-input__field" />
                <span class="ds-cron-input__hint">每天凌晨 02:00 执行</span>
              </div>
            </div>
          </div>

          <!-- 速率保护 — 三列网格 -->
          <div class="ds-grid-section">
            <div class="ds-grid-section__label">速率保护</div>
            <div class="ds-grid ds-grid--3">
              <div class="ds-field">
                <label class="ds-field__label">单批处理量</label>
                <div class="ds-field__hint">每次最多处理的 visit 数</div>
                <div class="ds-input-group">
                  <a-input-number v-model:value="configForm.max_batch_size" :min="10" :max="1000" :controls="false" class="ds-input-group__input" />
                  <span class="ds-input-group__suffix">条</span>
                </div>
              </div>
              <div class="ds-field">
                <label class="ds-field__label">请求间隔</label>
                <div class="ds-field__hint">两次查询间的等待</div>
                <div class="ds-input-group">
                  <a-input-number v-model:value="configForm.inter_request_delay_ms" :min="50" :max="5000" :step="50" :controls="false" class="ds-input-group__input" />
                  <span class="ds-input-group__suffix">ms</span>
                </div>
              </div>
              <div class="ds-field">
                <label class="ds-field__label">夜间窗口</label>
                <div class="ds-field__hint">Tier3 仅在此时段执行</div>
                <div class="ds-time-range">
                  <a-input v-model:value="configForm.night_window_start" placeholder="22:00" class="ds-time-range__input" />
                  <span class="ds-time-range__sep">—</span>
                  <a-input v-model:value="configForm.night_window_end" placeholder="06:00" class="ds-time-range__input" />
                </div>
              </div>
            </div>
          </div>

          <!-- 底栏 -->
          <div class="ds-card__footer">
            <button class="ds-btn ds-btn--ghost" @click="loadMongoConfig">取消更改</button>
            <button class="ds-btn ds-btn--primary" @click="saveMongoConfig" :disabled="configSaving">
              保存抽取策略
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- ══════════ MongoDB 连接编辑弹窗 ══════════ -->
    <a-modal v-model:open="showMongoModal" title="MongoDB 连接配置" :confirm-loading="connSaving"
      @ok="saveMongoConnection" ok-text="保存并测试" cancel-text="取消" :width="520">
      <div style="padding-top: 8px">
        <a-alert message="建议使用只读账号 + secondaryPreferred 读偏好" type="info" show-icon style="margin-bottom: 16px" />
        <a-form layout="vertical">
          <a-form-item label="连接 URI">
            <a-input v-model:value="connForm.mongo_uri" placeholder="mongodb://user:pass@host:27017/db" />
            <div class="ds-modal-hint">支持 mongodb:// 和 mongodb+srv://，TLS 在 URI 中加 ?tls=true</div>
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
          <a-alert :type="connTestResult.connected ? 'success' : 'error'"
            :message="connTestResult.connected ? '✅ 连接成功 — MongoDB v' + (connTestResult.version || '') : '❌ 连接失败'"
            :description="connTestResult.error || ''" show-icon />
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
  } catch (err) { console.error('获取 MongoDB 配置失败:', err) }
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
  } catch (err) { console.error('获取 MongoDB 状态失败:', err) }
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
  } catch (err) { message.error('保存失败') } finally { connSaving.value = false }
}

async function saveMongoConfig() {
  configSaving.value = true
  try {
    await axios.put('/api/v1/sync/config/mongo', configForm.value)
    message.success('抽取策略配置已保存')
    await loadMongoConfig()
  } catch (err) { message.error('保存失败') } finally { configSaving.value = false }
}

async function triggerMongoSync() {
  try {
    const { data } = await axios.post('/api/v1/sync/trigger', { source: 'mongo', tier: mongoSyncTier.value })
    if (data.success) message.success('同步任务已启动')
    else message.warning(data.error || '同步启动失败')
    const poll = setInterval(async () => {
      await loadMongoStatus()
      if (!mongoSyncState.value.is_running) clearInterval(poll)
    }, 2000)
  } catch (err) { message.error('触发同步失败') }
}

onMounted(async () => { await Promise.all([loadMongoConfig(), loadMongoStatus()]) })
</script>

<style scoped>
/* ==================== Design Tokens ==================== */
:root {
  --ds-bg: #f8fafc;
  --ds-card: #ffffff;
  --ds-border: #e2e8f0;
  --ds-border-light: #f1f5f9;
  --ds-text-primary: #0f172a;
  --ds-text-secondary: #334155;
  --ds-text-tertiary: #64748b;
  --ds-text-muted: #94a3b8;
  --ds-accent: #2563eb;
}

.ds-root {
  display: flex;
  flex-direction: column;
  gap: 40px;
  max-width: 960px;
}

/* ---- 1/3 + 2/3 分栏 ---- */
.ds-split {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}
@media (min-width: 768px) {
  .ds-split {
    grid-template-columns: 260px 1fr;
    gap: 32px;
  }
}
.ds-split__aside {
  padding-top: 2px;
}
.ds-split__main {
  min-width: 0;
}

/* ---- Section 标题 ---- */
.ds-section-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--ds-text-primary);
  margin: 0 0 6px;
  line-height: 1.4;
}
.ds-section-desc {
  font-size: 13px;
  color: var(--ds-text-tertiary);
  line-height: 1.6;
  margin: 0;
}

/* ---- 白色卡片容器 ---- */
.ds-card {
  background: var(--ds-card);
  border: 1px solid var(--ds-border);
  border-radius: 10px;
  overflow: hidden;
}
.ds-card__rows {
  /* 行列表 */
}
.ds-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  background: #f8fafc;
  border-top: 1px solid var(--ds-border);
}
.ds-card__footer-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ---- 同行配置行 ---- */
.ds-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--ds-border-light);
  transition: background 0.12s ease;
}
.ds-row:last-child { border-bottom: none; }
.ds-row:hover { background: rgba(248, 250, 252, 0.6); }
.ds-row__left {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}
.ds-row__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ds-text-secondary);
}
.ds-row__sub {
  font-size: 12px;
  color: var(--ds-text-muted);
}
.ds-row__right-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 1px;
}

/* ---- 状态药丸 ---- */
.ds-pill {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
}
.ds-pill--ok { background: #f0fdf4; color: #16a34a; border: 1px solid #dcfce7; }
.ds-pill--off { background: #f8fafc; color: #94a3b8; border: 1px solid #e2e8f0; }

/* ---- 克制版统计条 ---- */
.ds-stats-row {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 18px 20px;
  border-bottom: 1px solid var(--ds-border-light);
  gap: 0;
}
.ds-stat {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 0 14px;
}
.ds-stat__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.ds-stat__dot--slate  { background: #94a3b8; }
.ds-stat__dot--amber  { background: #f59e0b; }
.ds-stat__dot--green  { background: #22c55e; }
.ds-stat__dot--orange { background: #f97316; }
.ds-stat__dot--red    { background: #ef4444; }
.ds-stat__num {
  font-size: 17px;
  font-weight: 700;
  color: var(--ds-text-primary);
  font-variant-numeric: tabular-nums;
}
.ds-stat__label {
  font-size: 12px;
  color: var(--ds-text-muted);
}
.ds-stat__sep {
  width: 1px;
  height: 22px;
  background: var(--ds-border);
}

/* ---- 顶部开关 Banner ---- */
.ds-switch-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  background: #f8fafc;
  border-bottom: 1px solid var(--ds-border-light);
}

/* ---- 网格区块（带小标题） ---- */
.ds-grid-section {
  padding: 20px;
  border-bottom: 1px solid var(--ds-border-light);
}
.ds-grid-section:last-of-type { border-bottom: none; }
.ds-grid-section__label {
  font-size: 11px;
  font-weight: 700;
  color: var(--ds-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 14px;
}

/* 双列/三列网格 */
.ds-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px 24px;
}
.ds-grid--3 {
  grid-template-columns: 1fr 1fr 1fr;
}
@media (max-width: 640px) {
  .ds-grid, .ds-grid--3 {
    grid-template-columns: 1fr;
  }
}

/* ---- 表单字段 ---- */
.ds-field {
  display: flex;
  flex-direction: column;
}
.ds-field--wide {
  margin-top: 16px;
}
.ds-field__label {
  font-size: 13px;
  font-weight: 600;
  color: var(--ds-text-secondary);
  margin-bottom: 2px;
}
.ds-field__hint {
  font-size: 12px;
  color: var(--ds-text-muted);
  margin-bottom: 8px;
  line-height: 1.4;
}

/* ---- 复合 InputGroup（值+单位合体） ---- */
.ds-input-group {
  display: flex;
  align-items: stretch;
}
.ds-input-group__input {
  flex: 1;
  border-top-right-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
}
.ds-input-group__input :deep(.ant-input-number) {
  border-top-right-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
}
.ds-input-group__input :deep(.ant-input-number-input) {
  text-align: center;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px;
}
.ds-input-group__suffix {
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  background: #f8fafc;
  border: 1px solid #d9d9d9;
  border-left: 0;
  border-radius: 0 6px 6px 0;
  font-size: 12px;
  font-weight: 600;
  color: var(--ds-text-tertiary);
  white-space: nowrap;
}

/* Cron 输入 */
.ds-cron-input {
  position: relative;
}
.ds-cron-input__field {
  width: 100% !important;
}
.ds-cron-input__field :deep(.ant-input) {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px;
  background: #f8fafc;
  padding-right: 160px;
}
.ds-cron-input__hint {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 12px;
  font-weight: 500;
  color: #16a34a;
  pointer-events: none;
}

/* 时间范围 */
.ds-time-range {
  display: flex;
  align-items: center;
  gap: 4px;
}
.ds-time-range__input {
  width: 68px !important;
}
.ds-time-range__input :deep(.ant-input) {
  text-align: center;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 13px;
}
.ds-time-range__sep {
  color: var(--ds-text-muted);
  font-size: 13px;
}

/* ---- 按钮系统 ---- */
.ds-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  font-weight: 600;
  border-radius: 7px;
  cursor: pointer;
  transition: all 0.12s ease;
  white-space: nowrap;
  border: none;
}
.ds-btn--primary {
  padding: 7px 16px;
  background: var(--ds-accent);
  color: #fff;
  box-shadow: 0 1px 3px rgba(37, 99, 235, 0.18);
}
.ds-btn--primary:hover:not(:disabled) { background: #1d4ed8; }
.ds-btn--primary:disabled { opacity: 0.5; cursor: not-allowed; }
.ds-btn--outline {
  padding: 6px 14px;
  background: #fff;
  color: #475569;
  border: 1px solid #d1d5db;
  box-shadow: 0 1px 2px rgba(0,0,0,0.04);
}
.ds-btn--outline:hover { background: #f8fafc; color: #1e293b; }
.ds-btn--ghost {
  padding: 6px 10px;
  background: none;
  color: var(--ds-text-tertiary);
}
.ds-btn--ghost:hover { color: var(--ds-text-primary); background: #f1f5f9; border-radius: 6px; }

/* ---- 工具样式 ---- */
.ds-mono-badge {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 12px;
  color: var(--ds-text-secondary);
  background: #f1f5f9;
  padding: 3px 8px;
  border-radius: 5px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ds-code {
  background: #f1f5f9;
  color: #475569;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11.5px;
  border: 1px solid #e2e8f0;
}
.ds-text-sm { font-size: 13px; color: var(--ds-text-secondary); }
.ds-text-semibold { font-size: 13px; font-weight: 600; color: var(--ds-text-secondary); }
.ds-text-xs { font-size: 11px; color: var(--ds-text-muted); }
.ds-text-warn { font-size: 12px; color: #d97706; }
.ds-modal-hint { font-size: 12px; color: var(--ds-text-muted); margin-top: 4px; }
.ds-select-native {
  appearance: none;
  padding: 6px 28px 6px 12px;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M3 4.5L6 7.5L9 4.5' stroke='%2394a3b8' fill='none' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") right 10px center no-repeat;
  font-size: 13px;
  font-weight: 500;
  color: var(--ds-text-secondary);
  cursor: pointer;
  outline: none;
}
.ds-select-native:focus {
  border-color: var(--ds-accent);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}
</style>
