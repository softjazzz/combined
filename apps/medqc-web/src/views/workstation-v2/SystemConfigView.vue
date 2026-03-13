<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50/30 dark:from-slate-900 dark:to-slate-800 p-6">
    <div class="max-w-5xl mx-auto space-y-6">

      <!-- 页面标题 -->
      <div class="flex items-center gap-3 mb-2">
        <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
          <SettingOutlined class="text-white text-lg" />
        </div>
        <div>
          <h1 class="text-xl font-bold text-slate-800 dark:text-slate-100">数据源配置</h1>
          <p class="text-sm text-slate-500 dark:text-slate-400">管理本地与远端数据库连接、数据同步</p>
        </div>
      </div>

      <!-- ========== 数据库连接状态 ========== -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
        <!-- 本地数据库 -->
        <div class="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/50 p-5 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <DatabaseOutlined class="text-blue-500 text-lg" />
              <span class="font-semibold text-slate-700 dark:text-slate-200">本地数据库</span>
            </div>
            <span :class="localDb.connected ? 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400' : 'bg-red-50 text-red-600 border-red-200'"
              class="text-xs px-2.5 py-1 rounded-full border font-medium">
              {{ localDb.connected ? '✅ 已连接' : '❌ 未连接' }}
            </span>
          </div>
          <div class="space-y-2.5 text-sm">
            <div class="flex justify-between">
              <span class="text-slate-500">连接地址</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ localDb.url || '—' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">版本</span>
              <span class="text-slate-700 dark:text-slate-300 text-xs">{{ localDb.version || '—' }}</span>
            </div>
            <div v-if="localDb.tables" class="pt-2 border-t border-slate-100 dark:border-slate-700 space-y-1.5">
              <div class="text-xs text-slate-400 uppercase tracking-wider">表数据量</div>
              <div v-for="(count, name) in localDb.tables" :key="name" class="flex justify-between">
                <span class="text-slate-500 font-mono">{{ name }}</span>
                <span class="text-slate-700 dark:text-slate-300 font-semibold">{{ count }} 条</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 远端 PG 数据库 -->
        <div class="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/50 p-5 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <CloudServerOutlined class="text-indigo-500 text-lg" />
              <span class="font-semibold text-slate-700 dark:text-slate-200">远端 DHC PG</span>
            </div>
            <div class="flex items-center gap-2">
              <span :class="remoteDb.connected ? 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400' : 'bg-amber-50 text-amber-600 border-amber-200 dark:bg-amber-900/20 dark:text-amber-400'"
                class="text-xs px-2.5 py-1 rounded-full border font-medium">
                {{ remoteDb.connected ? '✅ 已连接' : '⚠️ 未连接' }}
              </span>
              <a-button size="small" type="text" @click="showConfigModal = true" class="!text-blue-500">
                <template #icon><EditOutlined /></template>
              </a-button>
            </div>
          </div>
          <div class="space-y-2.5 text-sm">
            <div class="flex justify-between">
              <span class="text-slate-500">主机</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ dbConfig.remote_host }}:{{ dbConfig.remote_port }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">数据库</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ dbConfig.remote_database }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">版本</span>
              <span class="text-slate-700 dark:text-slate-300 text-xs">{{ remoteDb.version || '—' }}</span>
            </div>
            <div v-if="!remoteDb.connected" class="pt-2 border-t border-slate-100 dark:border-slate-700">
              <div class="text-xs text-amber-600 bg-amber-50 dark:bg-amber-900/20 p-2 rounded-lg">
                💡 远端未连接是正常的 — 需要在医院内网环境才能访问
              </div>
            </div>
          </div>
        </div>

        <!-- MongoDB 连接 -->
        <div class="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/50 p-5 shadow-sm">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <div class="w-5 h-5 rounded bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
                <span class="text-white text-[9px] font-black">M</span>
              </div>
              <span class="font-semibold text-slate-700 dark:text-slate-200">MongoDB</span>
            </div>
            <div class="flex items-center gap-2">
              <span :class="mongoStatus.connected ? 'bg-emerald-50 text-emerald-600 border-emerald-200 dark:bg-emerald-900/20 dark:text-emerald-400' : 'bg-slate-50 text-slate-500 border-slate-200 dark:bg-slate-700/30 dark:text-slate-400'"
                class="text-xs px-2.5 py-1 rounded-full border font-medium">
                {{ mongoStatus.connected ? '✅ 已连接' : '⬚ 未配置' }}
              </span>
              <a-button size="small" type="text" @click="showMongoModal = true" class="!text-teal-500">
                <template #icon><EditOutlined /></template>
              </a-button>
            </div>
          </div>
          <div class="space-y-2.5 text-sm">
            <div class="flex justify-between">
              <span class="text-slate-500">URI</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs truncate max-w-[160px]">{{ mongoConfig.mongo_uri_display || '未配置' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">数据库</span>
              <span class="text-slate-700 dark:text-slate-300 font-mono text-xs">{{ mongoConfig.mongo_database || '—' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">读偏好</span>
              <span class="text-slate-700 dark:text-slate-300 text-xs">{{ mongoConfig.read_preference || '—' }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-500">同步开关</span>
              <span :class="mongoConfig.enabled ? 'text-emerald-600' : 'text-slate-400'" class="text-xs font-medium">
                {{ mongoConfig.enabled ? '● 已启用' : '○ 已关闭' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- ========== 同步控制面板（Tab 化） ========== -->
      <div class="bg-white dark:bg-slate-800/60 rounded-2xl border border-slate-200/60 dark:border-slate-700/50 p-5 shadow-sm">
        <a-tabs v-model:activeKey="syncTab" class="sync-tabs">
          <!-- Tab 1: PG 存储过程同步 -->
          <a-tab-pane key="pg" tab="PG 存储过程同步">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <SyncOutlined class="text-blue-500 text-lg" :spin="syncState.is_running" />
                <span class="font-semibold text-slate-700 dark:text-slate-200">远端 DHC → 本地 PG</span>
              </div>
              <div class="flex gap-2">
                <a-date-picker v-model:value="syncDate" placeholder="同步日期" size="small" class="!w-36" />
                <a-button type="primary" size="small" @click="triggerSync" :loading="syncState.is_running"
                  :disabled="!remoteDb.connected" class="!rounded-lg">
                  <template #icon><SyncOutlined /></template>
                  立即同步
                </a-button>
                <a-button size="small" @click="refreshStatus" class="!rounded-lg">
                  <template #icon><ReloadOutlined /></template>
                  刷新
                </a-button>
              </div>
            </div>

            <!-- PG 同步状态 -->
            <div class="grid grid-cols-4 gap-4 mb-4">
              <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
                <div class="text-2xl font-bold text-slate-700 dark:text-slate-200">{{ syncState.total_records_synced }}</div>
                <div class="text-xs text-slate-500 mt-1">已同步记录数</div>
              </div>
              <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
                <div class="text-sm font-semibold" :class="syncStatusColor">{{ syncStatusLabel }}</div>
                <div class="text-xs text-slate-500 mt-1">同步状态</div>
              </div>
              <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
                <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ syncState.last_sync_time || '—' }}</div>
                <div class="text-xs text-slate-500 mt-1">上次同步时间</div>
              </div>
              <div class="text-center p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
                <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ syncTables.length }}</div>
                <div class="text-xs text-slate-500 mt-1">可同步表</div>
              </div>
            </div>

            <!-- 可同步表列表 -->
            <div class="border-t border-slate-100 dark:border-slate-700 pt-4">
              <div class="text-xs text-slate-400 uppercase tracking-wider mb-3">同步表配置</div>
              <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                <div v-for="t in syncTables" :key="t.name"
                  class="flex items-center justify-between p-2.5 rounded-lg bg-slate-50 dark:bg-slate-700/30 border border-slate-100 dark:border-slate-600/30">
                  <div>
                    <span class="text-sm font-medium text-slate-700 dark:text-slate-200">{{ t.label }}</span>
                    <span class="text-xs text-slate-400 ml-1 font-mono">{{ t.name }}</span>
                  </div>
                  <span class="text-xs text-slate-400 font-mono">{{ t.procedure }}</span>
                </div>
              </div>
            </div>

            <!-- PG 同步日志 -->
            <div v-if="syncState.logs && syncState.logs.length > 0" class="border-t border-slate-100 dark:border-slate-700 pt-4 mt-4">
              <div class="text-xs text-slate-400 uppercase tracking-wider mb-3">最近同步日志</div>
              <div class="space-y-2">
                <div v-for="(log, idx) in syncState.logs" :key="idx"
                  class="flex items-center justify-between p-2.5 rounded-lg text-sm"
                  :class="log.status === 'success' ? 'bg-emerald-50 dark:bg-emerald-900/10' : log.status === 'failed' ? 'bg-red-50 dark:bg-red-900/10' : 'bg-slate-50 dark:bg-slate-700/20'">
                  <div class="flex items-center gap-2">
                    <span v-if="log.status === 'success'" class="text-emerald-500">✅</span>
                    <span v-else-if="log.status === 'failed'" class="text-red-500">❌</span>
                    <span v-else class="text-blue-500"><SyncOutlined spin /></span>
                    <span class="font-medium text-slate-700 dark:text-slate-300">{{ log.table_name }}</span>
                    <span class="text-slate-400 font-mono text-xs">{{ log.stored_procedure }}</span>
                  </div>
                  <div class="flex items-center gap-3">
                    <span v-if="log.record_count > 0" class="text-emerald-600 font-semibold">{{ log.record_count }} 条</span>
                    <span v-if="log.error_msg" class="text-red-500 text-xs max-w-[200px] truncate">{{ log.error_msg }}</span>
                    <span class="text-xs text-slate-400">{{ log.finished_at || '' }}</span>
                  </div>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <!-- Tab 2: MongoDB 增量同步 -->
          <a-tab-pane key="mongo" tab="MongoDB 增量同步">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <SyncOutlined class="text-teal-500 text-lg" :spin="mongoSyncState.is_running" />
                <span class="font-semibold text-slate-700 dark:text-slate-200">MongoDB → 本地 PG</span>
                <span v-if="!mongoConfig.enabled"
                  class="text-xs px-2 py-0.5 rounded bg-amber-50 text-amber-600 border border-amber-200 dark:bg-amber-900/20 dark:text-amber-400">
                  同步已关闭
                </span>
              </div>
              <div class="flex gap-2">
                <a-select v-model:value="mongoSyncTier" size="small" class="!w-28">
                  <a-select-option value="all">全部 Tier</a-select-option>
                  <a-select-option value="tier1">Tier1 索引</a-select-option>
                  <a-select-option value="tier2">Tier2 结构</a-select-option>
                  <a-select-option value="tier3">Tier3 全文</a-select-option>
                </a-select>
                <a-button type="primary" size="small" @click="triggerMongoSync"
                  :loading="mongoSyncState.is_running"
                  :disabled="!mongoConfig.enabled"
                  class="!rounded-lg !bg-teal-600 hover:!bg-teal-500 !border-teal-600">
                  <template #icon><SyncOutlined /></template>
                  执行同步
                </a-button>
                <a-button size="small" @click="loadMongoStatus" class="!rounded-lg">
                  <template #icon><ReloadOutlined /></template>
                </a-button>
              </div>
            </div>

            <!-- MongoDB 同步状态卡片 -->
            <div class="grid grid-cols-5 gap-3 mb-5">
              <div class="text-center p-3 bg-blue-50/50 dark:bg-blue-900/10 rounded-xl border border-blue-100/50 dark:border-blue-800/30">
                <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">{{ mongoStats.PENDING || 0 }}</div>
                <div class="text-xs text-slate-500 mt-1">待抽取</div>
              </div>
              <div class="text-center p-3 bg-amber-50/50 dark:bg-amber-900/10 rounded-xl border border-amber-100/50 dark:border-amber-800/30">
                <div class="text-2xl font-bold text-amber-600 dark:text-amber-400">{{ mongoStats.PARTIAL || 0 }}</div>
                <div class="text-xs text-slate-500 mt-1">部分同步</div>
              </div>
              <div class="text-center p-3 bg-emerald-50/50 dark:bg-emerald-900/10 rounded-xl border border-emerald-100/50 dark:border-emerald-800/30">
                <div class="text-2xl font-bold text-emerald-600 dark:text-emerald-400">{{ mongoStats.SYNCED || 0 }}</div>
                <div class="text-xs text-slate-500 mt-1">已完成</div>
              </div>
              <div class="text-center p-3 bg-orange-50/50 dark:bg-orange-900/10 rounded-xl border border-orange-100/50 dark:border-orange-800/30">
                <div class="text-2xl font-bold text-orange-500 dark:text-orange-400">{{ mongoStats.STALE || 0 }}</div>
                <div class="text-xs text-slate-500 mt-1">需重拉</div>
              </div>
              <div class="text-center p-3 bg-red-50/50 dark:bg-red-900/10 rounded-xl border border-red-100/50 dark:border-red-800/30">
                <div class="text-2xl font-bold text-red-500 dark:text-red-400">{{ mongoStats.FAILED || 0 }}</div>
                <div class="text-xs text-slate-500 mt-1">失败</div>
              </div>
            </div>

            <!-- Tier 运行状态 -->
            <div class="grid grid-cols-3 gap-3 mb-5">
              <div class="p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
                <div class="text-xs text-slate-400 uppercase tracking-wider mb-1">Tier 1 · 索引发现</div>
                <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ mongoSyncState.tier1_discovered || 0 }} 条</div>
                <div class="text-xs text-slate-400 mt-0.5">{{ mongoSyncState.tier1_last_run || '从未运行' }}</div>
              </div>
              <div class="p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
                <div class="text-xs text-slate-400 uppercase tracking-wider mb-1">Tier 2 · 结构化</div>
                <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ mongoSyncState.tier2_synced || 0 }} 条</div>
                <div class="text-xs text-slate-400 mt-0.5">{{ mongoSyncState.tier2_last_run || '从未运行' }}</div>
              </div>
              <div class="p-3 bg-slate-50 dark:bg-slate-700/30 rounded-xl">
                <div class="text-xs text-slate-400 uppercase tracking-wider mb-1">Tier 3 · 全文</div>
                <div class="text-sm font-semibold text-slate-700 dark:text-slate-200">{{ mongoSyncState.tier3_synced || 0 }} 条</div>
                <div class="text-xs text-slate-400 mt-0.5">{{ mongoSyncState.tier3_last_run || '从未运行' }}</div>
              </div>
            </div>

            <!-- 抽取策略配置 -->
            <a-collapse ghost class="config-collapse">
              <a-collapse-panel key="strategy" header="抽取策略配置">
                <div class="grid grid-cols-2 gap-x-8 gap-y-4">
                  <!-- 左列 -->
                  <div class="space-y-4">
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">出院稳定窗口 (天)</label>
                      <a-input-number v-model:value="mongoConfigForm.discharge_stable_days" :min="0" :max="30" class="!w-full" />
                      <div class="text-xs text-slate-400 mt-0.5">出院后 N 天才纳入终末质控抽取</div>
                    </div>
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">回看窗口 (分钟)</label>
                      <a-input-number v-model:value="mongoConfigForm.lookback_minutes" :min="0" :max="120" class="!w-full" />
                      <div class="text-xs text-slate-400 mt-0.5">水位线回退 N 分钟，对冲时钟漂移</div>
                    </div>
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">滚动重扫 (天)</label>
                      <a-input-number v-model:value="mongoConfigForm.rescan_recent_days" :min="0" :max="30" class="!w-full" />
                      <div class="text-xs text-slate-400 mt-0.5">最近 N 天的修订强制重查</div>
                    </div>
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">Tier1 频率 (分钟)</label>
                      <a-input-number v-model:value="mongoConfigForm.tier1_interval_minutes" :min="5" :max="1440" class="!w-full" />
                    </div>
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">Tier2 频率 (分钟)</label>
                      <a-input-number v-model:value="mongoConfigForm.tier2_interval_minutes" :min="10" :max="1440" class="!w-full" />
                    </div>
                  </div>
                  <!-- 右列 -->
                  <div class="space-y-4">
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">Tier3 Cron 表达式</label>
                      <a-input v-model:value="mongoConfigForm.tier3_cron" placeholder="0 2 * * *" />
                      <div class="text-xs text-slate-400 mt-0.5">全文抽取定时（默认凌晨 2 点）</div>
                    </div>
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">单批数量</label>
                      <a-input-number v-model:value="mongoConfigForm.max_batch_size" :min="10" :max="1000" class="!w-full" />
                    </div>
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">请求间隔 (ms)</label>
                      <a-input-number v-model:value="mongoConfigForm.inter_request_delay_ms" :min="50" :max="5000" :step="50" class="!w-full" />
                    </div>
                    <div>
                      <label class="text-xs text-slate-500 block mb-1">夜间窗口</label>
                      <div class="flex items-center gap-2">
                        <a-input v-model:value="mongoConfigForm.night_window_start" placeholder="22:00" class="!w-24" />
                        <span class="text-slate-400">—</span>
                        <a-input v-model:value="mongoConfigForm.night_window_end" placeholder="06:00" class="!w-24" />
                      </div>
                    </div>
                    <div class="flex items-center justify-between pt-2">
                      <label class="text-xs text-slate-500">同步总开关</label>
                      <a-switch v-model:checked="mongoConfigForm.enabled" checked-children="启用" un-checked-children="关闭" />
                    </div>
                  </div>
                </div>
                <div class="flex justify-end mt-5 pt-4 border-t border-slate-100 dark:border-slate-700">
                  <a-button type="primary" @click="saveMongoConfig" :loading="mongoConfigSaving"
                    class="!rounded-lg !bg-teal-600 hover:!bg-teal-500 !border-teal-600">
                    保存配置
                  </a-button>
                </div>
              </a-collapse-panel>
            </a-collapse>
          </a-tab-pane>
        </a-tabs>
      </div>

    </div>

    <!-- ========== 远端 PG 连接编辑弹窗 ========== -->
    <a-modal
      v-model:open="showConfigModal"
      title="远端数据库连接配置"
      :confirm-loading="configSaving"
      @ok="saveConfig"
      ok-text="保存并测试"
      cancel-text="取消"
      :width="500"
    >
      <div class="space-y-4 pt-2">
        <div class="text-xs text-slate-400 mb-2">
          修改后点击「保存并测试」将自动测试连接，配置保存到服务端（Docker 容器重启不丢失）
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">主机地址</label>
          <a-input v-model:value="configForm.remote_host" placeholder="192.168.140.4" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">端口</label>
          <a-input v-model:value="configForm.remote_port" placeholder="5432" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">数据库名</label>
          <a-input v-model:value="configForm.remote_database" placeholder="dhc-app" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">用户名</label>
          <a-input v-model:value="configForm.remote_username" placeholder="Baidu" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">
            密码
            <span v-if="dbConfig.remote_password_set" class="text-xs text-emerald-500 ml-1">(已设置，留空则保持不变)</span>
          </label>
          <a-input-password v-model:value="configForm.remote_password" placeholder="输入密码" />
        </div>
        <div v-if="configTestResult" class="mt-3 p-3 rounded-lg text-sm"
          :class="configTestResult.connected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'">
          <div class="font-medium">{{ configTestResult.connected ? '✅ 连接成功' : '❌ 连接失败' }}</div>
          <div v-if="configTestResult.version" class="text-xs mt-1 opacity-70">{{ configTestResult.version }}</div>
          <div v-if="configTestResult.error" class="text-xs mt-1">{{ configTestResult.error }}</div>
        </div>
      </div>
    </a-modal>

    <!-- ========== MongoDB 连接编辑弹窗 ========== -->
    <a-modal
      v-model:open="showMongoModal"
      title="MongoDB 连接配置"
      :confirm-loading="mongoConfigSaving"
      @ok="saveMongoConnection"
      ok-text="保存并测试"
      cancel-text="取消"
      :width="520"
    >
      <div class="space-y-4 pt-2">
        <div class="text-xs text-slate-400 mb-2">
          配置对端 MongoDB 连接。建议使用只读账号 + secondaryPreferred 读偏好。
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">连接 URI</label>
          <a-input v-model:value="mongoConnForm.mongo_uri" placeholder="mongodb://user:pass@host:27017/db" />
          <div class="text-xs text-slate-400 mt-0.5">支持 mongodb:// 和 mongodb+srv:// 格式，TLS 可在 URI 中加 ?tls=true</div>
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">数据库名</label>
          <a-input v-model:value="mongoConnForm.mongo_database" placeholder="his_emr" />
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">读偏好</label>
          <a-select v-model:value="mongoConnForm.read_preference" class="!w-full">
            <a-select-option value="secondaryPreferred">secondaryPreferred（推荐：优先从库）</a-select-option>
            <a-select-option value="secondary">secondary（仅从库）</a-select-option>
            <a-select-option value="primaryPreferred">primaryPreferred（优先主库）</a-select-option>
            <a-select-option value="nearest">nearest（最近节点）</a-select-option>
          </a-select>
        </div>
        <div>
          <label class="text-sm text-slate-600 dark:text-slate-400 block mb-1">连接超时 (ms)</label>
          <a-input-number v-model:value="mongoConnForm.connect_timeout_ms" :min="1000" :max="30000" :step="1000" class="!w-full" />
        </div>
        <div v-if="mongoTestResult" class="mt-3 p-3 rounded-lg text-sm"
          :class="mongoTestResult.connected ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-red-50 text-red-700 border border-red-200'">
          <div class="font-medium">{{ mongoTestResult.connected ? '✅ 连接成功' : '❌ 连接失败' }}</div>
          <div v-if="mongoTestResult.version" class="text-xs mt-1 opacity-70">MongoDB v{{ mongoTestResult.version }}</div>
          <div v-if="mongoTestResult.error" class="text-xs mt-1">{{ mongoTestResult.error }}</div>
        </div>
      </div>
    </a-modal>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
import {
  SettingOutlined,
  DatabaseOutlined,
  CloudServerOutlined,
  SyncOutlined,
  ReloadOutlined,
  EditOutlined,
} from '@ant-design/icons-vue'

// ========== PG 相关状态（保持不变） ==========
const localDb = ref<any>({})
const remoteDb = ref<any>({})
const syncState = ref<any>({ is_running: false, logs: [], total_records_synced: 0 })
const syncTables = ref<any[]>([])
const syncDate = ref<string | null>(null)
const dbConfig = ref<any>({})
const syncTab = ref('pg')

// 远端 PG 编辑弹窗
const showConfigModal = ref(false)
const configSaving = ref(false)
const configTestResult = ref<any>(null)
const configForm = ref({
  remote_host: '',
  remote_port: '5432',
  remote_database: '',
  remote_username: '',
  remote_password: '',
})

// ========== MongoDB 相关状态 ==========
const mongoConfig = ref<any>({})
const mongoSyncState = ref<any>({})
const mongoStats = ref<any>({ PENDING: 0, PARTIAL: 0, SYNCED: 0, STALE: 0, FAILED: 0 })
const mongoStatus = ref<any>({ connected: false })
const mongoSyncTier = ref('all')

// MongoDB 连接编辑弹窗
const showMongoModal = ref(false)
const mongoConfigSaving = ref(false)
const mongoTestResult = ref<any>(null)
const mongoConnForm = ref({
  mongo_uri: '',
  mongo_database: 'his_emr',
  read_preference: 'secondaryPreferred',
  connect_timeout_ms: 5000,
})

// MongoDB 抽取策略表单
const mongoConfigForm = ref({
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

// ========== PG 同步状态计算 ==========
const syncStatusLabel = computed(() => {
  switch (syncState.value.last_sync_status) {
    case 'success': return '✅ 同步成功'
    case 'partial': return '⚠️ 部分成功'
    case 'failed': return '❌ 同步失败'
    default: return '—— 未同步'
  }
})

const syncStatusColor = computed(() => {
  switch (syncState.value.last_sync_status) {
    case 'success': return 'text-emerald-600 dark:text-emerald-400'
    case 'partial': return 'text-amber-600 dark:text-amber-400'
    case 'failed': return 'text-red-600 dark:text-red-400'
    default: return 'text-slate-400'
  }
})

// ========== PG 数据库 API ==========
async function loadDbStatus() {
  try {
    const { data } = await axios.get('/api/system/db/status')
    localDb.value = data.local || {}
    remoteDb.value = data.remote || {}
  } catch (err) {
    console.error('获取数据库状态失败:', err)
  }
}

async function loadDbConfig() {
  try {
    const { data } = await axios.get('/api/system/db/config')
    dbConfig.value = data
    configForm.value = {
      remote_host: data.remote_host || '',
      remote_port: data.remote_port || '5432',
      remote_database: data.remote_database || '',
      remote_username: data.remote_username || '',
      remote_password: '',
    }
  } catch (err) {
    console.error('获取数据库配置失败:', err)
  }
}

async function saveConfig() {
  configSaving.value = true
  configTestResult.value = null
  try {
    const { data } = await axios.put('/api/system/db/config', configForm.value)
    configTestResult.value = data.connection
    if (data.connection?.connected) {
      message.success('连接配置已保存，远端数据库连接成功！')
      showConfigModal.value = false
      await Promise.all([loadDbStatus(), loadDbConfig()])
    } else {
      message.warning('配置已保存，但远端连接失败（在医院内网才可连通）')
      await loadDbConfig()
    }
  } catch (err) {
    message.error('保存失败')
    console.error(err)
  } finally {
    configSaving.value = false
  }
}

async function loadSyncStatus() {
  try {
    const { data } = await axios.get('/api/system/sync/status')
    syncState.value = data
  } catch (err) {
    console.error('获取同步状态失败:', err)
  }
}

async function loadSyncTables() {
  try {
    const { data } = await axios.get('/api/system/sync/tables')
    syncTables.value = data.tables || []
  } catch (err) {
    console.error('获取同步表配置失败:', err)
  }
}

async function triggerSync() {
  try {
    const params: any = {}
    if (syncDate.value) params.sync_date = syncDate.value
    await axios.post('/api/system/sync/trigger', null, { params })
    const poll = setInterval(async () => {
      await loadSyncStatus()
      if (!syncState.value.is_running) {
        clearInterval(poll)
        await loadDbStatus()
      }
    }, 1000)
  } catch (err) {
    console.error('触发同步失败:', err)
  }
}

async function refreshStatus() {
  await Promise.all([loadDbStatus(), loadSyncStatus(), loadMongoStatus()])
}

// ========== MongoDB API ==========
async function loadMongoConfig() {
  try {
    const { data } = await axios.get('/api/v1/sync/config/mongo')
    mongoConfig.value = data
    // 填充连接表单
    mongoConnForm.value = {
      mongo_uri: '', // 不回填 URI（安全），只显示脱敏版
      mongo_database: data.mongo_database || 'his_emr',
      read_preference: data.read_preference || 'secondaryPreferred',
      connect_timeout_ms: data.connect_timeout_ms || 5000,
    }
    // 填充策略表单
    mongoConfigForm.value = {
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
  mongoConfigSaving.value = true
  mongoTestResult.value = null
  try {
    // 保存连接配置
    const updatePayload: any = {
      mongo_database: mongoConnForm.value.mongo_database,
      read_preference: mongoConnForm.value.read_preference,
      connect_timeout_ms: mongoConnForm.value.connect_timeout_ms,
    }
    if (mongoConnForm.value.mongo_uri) {
      updatePayload.mongo_uri = mongoConnForm.value.mongo_uri
    }
    await axios.put('/api/v1/sync/config/mongo', updatePayload)

    // 测试连接
    const { data } = await axios.post('/api/v1/sync/test-connection/mongo')
    mongoTestResult.value = data
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
    console.error(err)
  } finally {
    mongoConfigSaving.value = false
  }
}

async function saveMongoConfig() {
  mongoConfigSaving.value = true
  try {
    await axios.put('/api/v1/sync/config/mongo', mongoConfigForm.value)
    message.success('抽取策略配置已保存')
    await loadMongoConfig()
  } catch (err) {
    message.error('保存失败')
    console.error(err)
  } finally {
    mongoConfigSaving.value = false
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
    // 轮询状态
    const poll = setInterval(async () => {
      await loadMongoStatus()
      if (!mongoSyncState.value.is_running) {
        clearInterval(poll)
      }
    }, 2000)
  } catch (err) {
    message.error('触发同步失败')
    console.error(err)
  }
}

// ========== 初始化 ==========
onMounted(async () => {
  await Promise.all([
    loadDbStatus(),
    loadDbConfig(),
    loadSyncStatus(),
    loadSyncTables(),
    loadMongoConfig(),
    loadMongoStatus(),
  ])
})
</script>

<style scoped>
.sync-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 16px;
}
.sync-tabs :deep(.ant-tabs-tab) {
  font-weight: 600;
  font-size: 14px;
}
.config-collapse :deep(.ant-collapse-header) {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 12px 0 !important;
  border-top: 1px solid #e2e8f0;
}
.config-collapse :deep(.ant-collapse-content-box) {
  padding: 16px 0 !important;
}
</style>
