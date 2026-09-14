<template>
  <div class="connection-studio flex flex-col h-full bg-white">
    <div class="px-5 py-4 border-b border-[#E5E7EB] flex items-center justify-between shrink-0">
      <h2 class="text-[14px] font-semibold text-slate-800 tracking-tight">
        连接配置
      </h2>
      <a-tooltip :title="isReadonly ? '仅 admin 可执行' : '测试当前标签连接'">
        <button
          class="text-[12px] font-medium text-slate-500 hover:text-slate-700 transition-colors"
          :disabled="isReadonly || state.isTestingActive"
          @click="handleTestCurrent"
        >
          检测连通性
        </button>
      </a-tooltip>
    </div>

    <div class="px-5 py-3 shrink-0 relative">
      <div class="flex p-1 rounded-[8px] bg-slate-100/80 border border-slate-200/50 relative">
        <button
          :class="tabClass('pg_local')"
          @click="state.activeTab = 'pg_local'"
        >
          本地库
        </button>
        <button
          :class="tabClass('pg_remote')"
          @click="state.activeTab = 'pg_remote'"
        >
          源库 PG
        </button>
      </div>
    </div>

    <div class="flex-1 overflow-y-auto custom-scrollbar px-5 pb-5">
      <div
        v-if="state.activeTab === 'pg_remote'"
        class="space-y-4"
      >
        <a-alert
          v-if="state.loadErrors.connection"
          type="warning"
          show-icon
          :message="state.loadErrors.connection"
        />

        <section class="rounded-xl border border-slate-200/80 bg-white p-3 space-y-3">
          <div class="pt-2 pb-3 border-b border-slate-100">
            <div class="text-[13px] font-semibold text-slate-800">
              数据融合库 clinical_data（PG 源库）
            </div>
            <div class="text-[11px] text-slate-500 mt-1">
              对接病案平台入 ES 前的融合库；客户样本优先用 visit_id 匹配，可辅以 inpat_no / mr_no。
            </div>
            <div class="text-[11px] text-slate-500 mt-1">
              仅 admin 可修改，qc_manager 只读。
            </div>
          </div>

          <div class="grid grid-cols-2 gap-3">
            <div class="col-span-2">
              <label class="text-[12px] text-slate-600 block mb-1">主机地址</label>
              <input
                v-model="state.pgConnectionForm.remote_host"
                type="text"
                :disabled="isReadonly"
                class="studio-input"
              >
            </div>

            <div>
              <label class="text-[12px] text-slate-600 block mb-1">端口</label>
              <input
                v-model="state.pgConnectionForm.remote_port"
                type="number"
                :min="1"
                :max="65535"
                :disabled="isReadonly"
                class="studio-input"
              >
            </div>

            <div>
              <label class="text-[12px] text-slate-600 block mb-1">Schema</label>
              <input
                v-model="state.pgConnectionForm.remote_schema"
                type="text"
                :disabled="isReadonly"
                class="studio-input"
              >
            </div>

            <div>
              <label class="text-[12px] text-slate-600 block mb-1">数据库名</label>
              <input
                v-model="state.pgConnectionForm.remote_database"
                type="text"
                :disabled="isReadonly"
                class="studio-input"
              >
            </div>

            <div>
              <label class="text-[12px] text-slate-600 block mb-1">用户名</label>
              <input
                v-model="state.pgConnectionForm.remote_username"
                type="text"
                :disabled="isReadonly"
                class="studio-input"
              >
            </div>

            <div class="col-span-2">
              <label class="text-[12px] font-medium text-slate-700 block mb-1">
                本院机构标识 <span class="text-red-500">*</span>
              </label>
              <input
                v-model="state.pgConnectionForm.default_institute_id"
                type="text"
                :disabled="isReadonly"
                class="studio-input"
                placeholder="例如：LUXIAN-HOSPITAL"
              >
              <div class="text-[11px] leading-5 text-slate-500 mt-1">
                源库没有 institute_id 时，用该值形成稳定病例身份；投入使用后不要随意修改。
              </div>
            </div>

            <div class="col-span-2">
              <label class="text-[12px] text-slate-600 block mb-1">同步模式</label>
              <a-select
                v-model:value="state.pgConnectionForm.sync_mode"
                :disabled="isReadonly"
                class="w-full"
                size="small"
                :options="syncModeOptions"
              />
            </div>

            <div class="col-span-2">
              <label class="text-[12px] text-slate-600 block mb-1">密码（留空保持不变）</label>
              <input
                v-model="state.pgConnectionForm.remote_password"
                type="password"
                :disabled="isReadonly"
                class="studio-input"
              >
              <div class="text-[11px] text-slate-400 mt-1">
                当前密码状态：{{ state.pgConnectionForm.remote_password_set ? '已设置' : '未设置' }}
              </div>
            </div>
          </div>

          <div class="pt-2">
            <button
              class="w-full px-4 py-2 mt-1 rounded-lg text-[13px] font-semibold text-white transition-all shadow-[0_2px_8px_rgba(43,108,246,0.16)] flex items-center justify-center gap-2"
              :class="
                isReadonly || state.isSavingPgConnection
                  ? 'bg-slate-300 shadow-none cursor-not-allowed text-slate-100'
                  : 'bg-[#2b6cf6] hover:bg-[#0057b8] hover:shadow-[0_4px_12px_rgba(43,108,246,0.18)] active:scale-[0.98]'
              "
              :disabled="isReadonly || state.isSavingPgConnection"
              @click="handleSavePg"
            >
              <span v-if="state.isSavingPgConnection">保存中...</span>
              <span v-else>保存配置</span>
            </button>
          </div>
        </section>

        <a-alert
          v-if="state.loadErrors.policy"
          type="warning"
          show-icon
          :message="state.loadErrors.policy"
        />

        <section class="rounded-xl border border-slate-200/80 bg-white p-3 space-y-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-[13px] font-semibold text-slate-800">
                PG 抽取模板
              </div>
              <div class="text-[11px] text-slate-500 mt-1">
                用模板快速下发场景、时间窗口、调度和夜间策略，再进入预检。
              </div>
            </div>
            <div class="flex items-center gap-2">
              <a-button
                size="small"
                :disabled="isReadonly"
                @click="expertMode = !expertMode"
              >
                {{ expertMode ? '切换新手模式' : '切换专业模式' }}
              </a-button>
              <a-button
                size="small"
                :loading="state.templatesLoading"
                @click="handleRefreshTemplateResources"
              >
                {{ state.templatesLoading ? '刷新中...' : '刷新模板' }}
              </a-button>
            </div>
          </div>

          <a-alert
            v-if="!expertMode"
            type="info"
            show-icon
            message="新手推荐：1) 选模板 2) 选科室与出院日期 3) 保存策略并执行预检。"
          />

          <div
            class="grid gap-3"
            :class="expertMode ? 'grid-cols-2' : 'grid-cols-[minmax(0,1fr)_140px]'"
          >
            <div :class="expertMode ? 'col-span-2' : ''">
              <label class="studio-label">模板</label>
              <a-select
                v-model:value="state.selectedTemplateId"
                :disabled="isReadonly"
                :loading="state.templatesLoading"
                :options="templateOptions"
                style="width: 100%"
              />
              <div class="text-[11px] text-slate-500 mt-1">
                {{ currentTemplate?.description || '按策略默认' }}
              </div>
              <div class="text-[11px] text-amber-600/90 mt-1">
                {{ currentTemplate?.risk_tip || '夜间窗口默认' }}
              </div>
            </div>

            <div
              v-if="!expertMode"
              class="rounded-lg border border-slate-200/80 bg-slate-50 px-3 py-2"
            >
              <div class="text-[11px] text-slate-500">
                映射场景
              </div>
              <div class="text-[13px] font-semibold text-slate-800 mt-0.5">
                {{ sceneLabel }}
              </div>
            </div>

            <template v-if="!expertMode">
              <div>
                <label class="studio-label">抽取科室（可多选）</label>
                <a-select
                  v-model:value="state.selectedTemplateDepartments"
                  mode="multiple"
                  :disabled="isReadonly"
                  :options="departmentOptions"
                  :max-tag-count="3"
                  :loading="state.departmentsLoading"
                  style="width: 100%"
                  placeholder="未选择时按全院处理"
                />
              </div>
              <div>
                <label class="studio-label">出院日期范围</label>
                <div class="grid grid-cols-2 gap-2">
                  <a-date-picker
                    :value="state.policyForm.start_date ? dayjs(state.policyForm.start_date) : null"
                    value-format="YYYY-MM-DD"
                    :disabled="isReadonly"
                    style="width: 100%"
                    placeholder="开始日期"
                    @update:value="handlePolicyStartDateChange"
                  />
                  <a-date-picker
                    :value="state.policyForm.end_date ? dayjs(state.policyForm.end_date) : null"
                    value-format="YYYY-MM-DD"
                    :disabled="isReadonly"
                    style="width: 100%"
                    placeholder="结束日期"
                    @update:value="handlePolicyEndDateChange"
                  />
                </div>
              </div>
            </template>

            <template v-else>
              <div>
                <label class="studio-label">模板科室</label>
                <a-select
                  v-model:value="state.selectedTemplateDepartments"
                  mode="multiple"
                  :disabled="isReadonly"
                  :options="departmentOptions"
                  :max-tag-count="3"
                  :loading="state.departmentsLoading"
                  style="width: 100%"
                  placeholder="请选择模板科室"
                />
                <div class="text-[11px] text-slate-500 mt-1">
                  未选择时沿用全院
                </div>
              </div>
              <div>
                <label class="studio-label">时间窗口 / 调度</label>
                <a-input
                  :value="`${state.policyForm.start_date || '未设'} ~ ${state.policyForm.end_date || '未设'}`"
                  readonly
                />
                <div class="text-[11px] text-slate-500 mt-1">
                  应用到 PG 策略
                </div>
              </div>
            </template>
          </div>

          <div class="flex items-center justify-end gap-2">
            <a-button
              :loading="state.templateApplying"
              :disabled="isReadonly"
              @click="handleApplyTemplate"
            >
              {{ state.templateApplying ? '应用中...' : '应用模板' }}
            </a-button>
            <a-button
              type="primary"
              :loading="state.isSavingPolicy"
              :disabled="isReadonly"
              @click="handleSavePolicy"
            >
              保存策略
            </a-button>
            <a-button
              type="primary"
              ghost
              :loading="state.isPreflighting"
              :disabled="isReadonly"
              @click="handleRunPreflight"
            >
              {{ state.isPreflighting ? '预检中...' : '执行预检' }}
            </a-button>
          </div>
        </section>

        <section class="rounded-xl border border-slate-200/80 bg-white p-3 space-y-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-[13px] font-semibold text-slate-800">
                抽取策略配置
              </div>
              <div class="text-[11px] text-slate-500 mt-1">
                新手模式下建议沿用模板默认策略，仅在需要时展开高级配置。
              </div>
              <div class="text-[11px] text-slate-500">
                约束 PG 预检与执行的场景、科室、时间窗口与调度节奏。
              </div>
            </div>
            <a-button
              size="small"
              :disabled="isReadonly"
              @click="showAdvancedPolicy = !showAdvancedPolicy"
            >
              {{ showAdvancedPolicy ? '收起策略' : '高级策略' }}
            </a-button>
          </div>

          <div class="grid grid-cols-4 gap-3">
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                当前场景
              </div>
              <div class="studio-summary-card__value">
                {{ sceneLabel }}
              </div>
            </div>
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                策略版本
              </div>
              <div class="studio-summary-card__value font-mono">
                {{ state.policyForm.policy_version || '未生成' }}
              </div>
            </div>
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                时间窗口
              </div>
              <div class="studio-summary-card__value font-mono">
                {{ policyDateRangeLabel }}
              </div>
            </div>
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                夜间窗口
              </div>
              <div class="studio-summary-card__value font-mono">
                {{ nightWindowLabel }}
              </div>
            </div>
          </div>

          <div v-if="showAdvancedPolicy">
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="studio-label">终末抽取场景</label>
                <a-select
                  v-model:value="state.policyForm.scope"
                  :disabled="isReadonly"
                  :options="sceneOptions"
                  style="width: 100%"
                />
              </div>
              <div>
                <label class="studio-label">策略版本</label>
                <a-input
                  :value="state.policyForm.policy_version || '未生成'"
                  readonly
                />
              </div>
              <div class="col-span-2">
                <label class="studio-label">目标科室</label>
                <a-select
                  v-model:value="state.policyForm.target_departments"
                  mode="multiple"
                  :disabled="isReadonly"
                  :options="policyDepartmentOptions"
                  :max-tag-count="4"
                  style="width: 100%"
                  @change="handlePolicyDepartmentChange"
                />
                <div class="text-[11px] text-slate-500 mt-1">
                  `*` 表示全院；不允许与具体科室同时出现。
                </div>
              </div>
              <div>
                <label class="studio-label">开始日期</label>
                <a-date-picker
                  :value="state.policyForm.start_date ? dayjs(state.policyForm.start_date) : null"
                  value-format="YYYY-MM-DD"
                  :disabled="isReadonly"
                  style="width: 100%"
                  @update:value="handlePolicyStartDateChange"
                />
              </div>
              <div>
                <label class="studio-label">结束日期</label>
                <a-date-picker
                  :value="state.policyForm.end_date ? dayjs(state.policyForm.end_date) : null"
                  value-format="YYYY-MM-DD"
                  :disabled="isReadonly"
                  style="width: 100%"
                  @update:value="handlePolicyEndDateChange"
                />
              </div>
              <div>
                <label class="studio-label">调度模式</label>
                <a-select
                  v-model:value="state.policyForm.schedule_mode"
                  :disabled="isReadonly"
                  :options="scheduleModeOptions"
                  style="width: 100%"
                />
              </div>
              <div>
                <label class="studio-label">调度间隔 (分)</label>
                <a-input-number
                  v-model:value="state.policyForm.schedule_minutes"
                  :disabled="isReadonly || state.policyForm.schedule_mode === 'cron'"
                  :min="1"
                  :max="1440"
                  style="width: 100%"
                />
              </div>
              <div>
                <label class="studio-label">镜像延迟保护 (分)</label>
                <a-input-number
                  v-model:value="state.policyForm.mirror_delay_base_minutes"
                  :disabled="isReadonly"
                  :min="0"
                  :max="720"
                  style="width: 100%"
                />
              </div>
              <div>
                <label class="studio-label">夜间窗口开始</label>
                <a-input
                  v-model:value="state.policyForm.night_window_start"
                  :disabled="isReadonly"
                  placeholder="22:00"
                />
              </div>
              <div>
                <label class="studio-label">夜间窗口结束</label>
                <a-input
                  v-model:value="state.policyForm.night_window_end"
                  :disabled="isReadonly"
                  placeholder="06:00"
                />
              </div>
            </div>
            <div class="flex items-center justify-end mt-3">
              <a-button
                type="primary"
                :loading="state.isSavingPolicy"
                :disabled="isReadonly"
                @click="handleSavePolicy"
              >
                保存策略
              </a-button>
            </div>
          </div>
        </section>

        <section class="rounded-xl border border-slate-200/80 bg-white p-3 space-y-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-[13px] font-semibold text-slate-800">
                同步目标表配置
              </div>
              <div class="text-[11px] text-slate-500 mt-1">
                控制当前阶段参与预检与执行的目标表，已启用 {{ enabledTableCount }}/{{
                  state.pgSyncTables.length
                }}
                张表
              </div>
              <div class="text-[11px] text-slate-500">
                新手建议：保持默认启用表，仅在数据源字段有变化时修改。
              </div>
            </div>
            <a-button
              size="small"
              :disabled="isReadonly"
              @click="showAdvancedTables = !showAdvancedTables"
            >
              {{ showAdvancedTables ? '收起表配置' : '高级表配置' }}
            </a-button>
          </div>

          <div class="grid grid-cols-4 gap-3">
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                当前模式
              </div>
              <div class="studio-summary-card__value">
                {{ state.pgConnectionForm.sync_mode === 'procedure' ? '存储过程回退' : '表直连' }}
              </div>
            </div>
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                启用表
              </div>
              <div class="studio-summary-card__value">
                {{ enabledTableCount }} / {{ state.pgSyncTables.length }}
              </div>
            </div>
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                Schema
              </div>
              <div class="studio-summary-card__value font-mono">
                {{ state.pgConnectionForm.remote_schema || 'public' }}
              </div>
            </div>
            <div class="studio-summary-card">
              <div class="studio-summary-card__label">
                分组选择
              </div>
              <div class="studio-summary-card__value">
                {{ selectedTableGroupSummary }}
              </div>
            </div>
          </div>

          <div class="rounded-lg border border-slate-200/80 bg-slate-50 px-3 py-2 space-y-2">
            <label class="studio-label !mb-0">同步表分组（推荐）</label>
            <a-select
              v-model:value="state.selectedTableGroups"
              mode="multiple"
              :disabled="isReadonly || !hasTableGroups"
              :options="tableGroupOptions"
              :max-tag-count="2"
              style="width: 100%"
              placeholder="默认核心8表，可按分组扩展"
            />
            <div class="text-[11px] text-slate-500">
              当前：{{ selectedTableGroupSummary }}
            </div>
            <div class="flex items-center gap-2">
              <a-button
                size="small"
                :disabled="isReadonly || !hasTableGroups"
                @click="applyTableGroupPreset('core')"
              >
                核心8表
              </a-button>
              <a-button
                size="small"
                :disabled="isReadonly || !hasTableGroups"
                @click="applyTableGroupPreset('clinical')"
              >
                临床常用
              </a-button>
              <a-button
                size="small"
                :disabled="isReadonly || !hasTableGroups"
                @click="applyTableGroupPreset('all')"
              >
                全量56表
              </a-button>
            </div>
          </div>

          <div class="flex items-center justify-end gap-2">
            <a-button
              size="small"
              :loading="state.isLoadingPgTables"
              @click="handleReloadPgTables"
            >
              刷新
            </a-button>
            <a-button
              size="small"
              type="primary"
              ghost
              :loading="state.isPreflighting"
              :disabled="isReadonly"
              @click="handleRunPreflight"
            >
              执行预检
            </a-button>
            <a-button
              size="small"
              type="primary"
              :loading="state.isSavingPgTables"
              :disabled="isReadonly"
              @click="handleSavePgTables"
            >
              保存表配置
            </a-button>
          </div>

          <div v-if="showAdvancedTables">
            <div class="flex items-center gap-2 mb-2">
              <a-input
                v-model:value="tableKeyword"
                placeholder="搜索本地表 / 远端源表 / 日期字段"
                allow-clear
              />
              <a-switch
                v-model:checked="onlyEnabledTables"
                :checked-children="'仅看启用'"
                :un-checked-children="'全部'"
                size="small"
              />
            </div>

            <div
              v-if="state.isLoadingPgTables"
              class="text-[12px] text-slate-500 py-3"
            >
              正在加载表配置...
            </div>
            <div
              v-else-if="filteredPgTables.length === 0"
              class="text-[12px] text-slate-500 py-3"
            >
              暂无匹配表，请调整搜索条件或关闭“仅看启用”。
            </div>
            <div
              v-else
              class="space-y-2 max-h-[420px] overflow-y-auto custom-scrollbar pr-1"
            >
              <div
                v-for="item in filteredPgTables"
                :key="item.name"
                class="rounded-lg border border-slate-200/80 bg-slate-50/70 p-2.5"
              >
                <div class="flex items-center justify-between gap-2 mb-2">
                  <div class="text-[12px] font-semibold text-slate-800 font-mono truncate">
                    {{ item.name }}
                  </div>
                  <a-switch
                    v-model:checked="item.enabled"
                    size="small"
                    :disabled="isReadonly"
                  />
                </div>
                <div class="grid grid-cols-3 gap-2">
                  <input
                    v-model="item.source_table"
                    type="text"
                    :disabled="isReadonly"
                    placeholder="source_table"
                    class="studio-input"
                  >
                  <input
                    v-model="item.date_field"
                    type="text"
                    :disabled="isReadonly"
                    placeholder="date_field"
                    class="studio-input"
                  >
                  <input
                    v-model="item.fallback_date_field"
                    type="text"
                    :disabled="isReadonly"
                    placeholder="fallback_date_field（可选）"
                    class="studio-input"
                  >
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="rounded-xl border border-slate-200/80 bg-white p-3 space-y-3">
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-[13px] font-semibold text-slate-800">
                PG 预检摘要
              </div>
              <div class="text-[11px] text-slate-500 mt-1">
                执行前检查连接、关键字段与表配置，避免“可触发但不可执行”。
              </div>
            </div>
            <span
              class="studio-pill"
              :class="preflightToneClass"
            >
              {{ preflightStatusText }}
            </span>
          </div>

          <div
            v-if="!state.preflightResult"
            class="text-[12px] text-slate-500 rounded-lg border border-dashed border-slate-200 px-3 py-3"
          >
            暂无预检结果，点击“执行预检”后展示执行矩阵。
          </div>

          <template v-else>
            <div class="grid grid-cols-4 gap-3">
              <div class="studio-summary-card">
                <div class="studio-summary-card__label">
                  执行状态
                </div>
                <div class="studio-summary-card__value">
                  {{ state.preflightResult.executable ? '可执行' : '阻断' }}
                </div>
              </div>
              <div class="studio-summary-card">
                <div class="studio-summary-card__label">
                  阻断项
                </div>
                <div class="studio-summary-card__value">
                  {{ state.preflightResult.blockers?.length || 0 }}
                </div>
              </div>
              <div class="studio-summary-card">
                <div class="studio-summary-card__label">
                  警告项
                </div>
                <div class="studio-summary-card__value">
                  {{ state.preflightResult.warnings?.length || 0 }}
                </div>
              </div>
              <div class="studio-summary-card">
                <div class="studio-summary-card__label">
                  预计影响
                </div>
                <div class="studio-summary-card__value font-mono">
                  {{ Number(state.preflightResult.estimated_impact || 0).toLocaleString() }}
                </div>
              </div>
            </div>

            <div
              v-if="state.preflightResult.blockers?.length"
              class="rounded-lg border border-rose-200/80 bg-rose-50/80 px-3 py-2"
            >
              <div class="text-[11px] font-semibold text-rose-700">
                阻断原因
              </div>
              <ul class="mt-1 space-y-1">
                <li
                  v-for="(item, idx) in state.preflightResult.blockers"
                  :key="`blocker-${idx}`"
                  class="text-[11px] text-rose-600"
                >
                  {{ item }}
                </li>
              </ul>
            </div>

            <div
              v-if="state.preflightResult.warnings?.length"
              class="rounded-lg border border-amber-200/80 bg-amber-50/80 px-3 py-2"
            >
              <div class="text-[11px] font-semibold text-amber-700">
                预警提示
              </div>
              <ul class="mt-1 space-y-1">
                <li
                  v-for="(item, idx) in state.preflightResult.warnings"
                  :key="`warning-${idx}`"
                  class="text-[11px] text-amber-700"
                >
                  {{ item }}
                </li>
              </ul>
            </div>

            <div class="rounded-lg border border-slate-200/80 overflow-hidden">
              <div
                class="px-3 py-2 border-b border-slate-200/80 bg-slate-50/70 text-[11px] text-slate-600"
              >
                执行范围：{{ matrixExecutionScopeLabel }} ｜ 全量范围：{{ matrixFullScopeLabel }}
              </div>
              <div class="max-h-[260px] overflow-auto">
                <table class="studio-matrix-table">
                  <thead>
                    <tr>
                      <th>本地表</th>
                      <th>远端源表</th>
                      <th>日期字段</th>
                      <th>状态</th>
                      <th>问题</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-if="preflightTableRows.length === 0">
                      <td
                        colspan="5"
                        class="text-center text-slate-400"
                      >
                        暂无表校验明细
                      </td>
                    </tr>
                    <tr
                      v-for="item in preflightTableRows"
                      :key="item.table"
                    >
                      <td class="font-mono">
                        {{ item.table }}
                      </td>
                      <td class="font-mono">
                        {{ item.source || '-' }}
                      </td>
                      <td class="font-mono">
                        {{ item.dateField || '-' }}
                      </td>
                      <td>
                        <span
                          class="studio-inline-status"
                          :class="
                            item.executable
                              ? 'studio-inline-status--ok'
                              : 'studio-inline-status--bad'
                          "
                        >
                          {{ item.executable ? '通过' : '阻断' }}
                        </span>
                      </td>
                      <td class="text-rose-600">
                        {{ item.blockers || '-' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </section>
      </div>

      <div
        v-else
        class="space-y-4"
      >
        <div class="pt-2 pb-3 border-b border-slate-100">
          <div class="text-[13px] font-semibold text-slate-800">
            本地核心仓 (PG 本地)
          </div>
          <div class="text-[11px] text-slate-500 mt-1">
            本地连接只读，支持检测连通性。
          </div>
        </div>

        <a-alert
          type="info"
          show-icon
          message="本地库配置由部署环境管理，不在控制台中修改。"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import { message } from 'ant-design-vue'
import type { SyncTableValidationItem } from '@/api/sync'
import { useDataSync } from '../../composables/useDataSync'

type DateValue = string | null

const {
  state,
  isReadonly,
  testActiveConnection,
  savePgConnection,
  loadPgSyncTables,
  loadPgSyncTableGroups,
  savePgSyncTables,
  savePolicy,
  runPreflight,
  applyTemplate,
  loadTemplates,
  loadDepartments,
} = useDataSync()

const expertMode = ref(false)
const showAdvancedPolicy = ref(false)
const showAdvancedTables = ref(false)
const tableKeyword = ref('')
const onlyEnabledTables = ref(false)

const syncModeOptions = [
  { label: '表直连（table）', value: 'table' },
  { label: '存储过程回退（procedure）', value: 'procedure' },
]

const scheduleModeOptions = [
  { label: '间隔轮询', value: 'interval' },
  { label: 'Cron（保留）', value: 'cron' },
]

const sceneOptions = [
  { label: '全部终末相关', value: 'both' },
  { label: '终末病历', value: 'final' },
  { label: '病案首页', value: 'frontpage' },
  { label: '编码质控', value: 'coding' },
  { label: '结算清单', value: 'settlement' },
]

const sceneLabelMap: Record<string, string> = {
  both: '全部终末相关',
  running: '在院病历（待接入）',
  final: '终末病历',
  frontpage: '病案首页',
  coding: '编码质控',
  settlement: '结算清单',
}

const templateOptions = computed(() =>
  state.syncTemplates.map((item) => ({
    label: item.name,
    value: item.id,
  })),
)

const currentTemplate = computed(() =>
  state.syncTemplates.find((item) => item.id === state.selectedTemplateId),
)

const sceneLabel = computed(() => sceneLabelMap[state.policyForm.scope] || '全部终末相关')

const departmentOptions = computed(() =>
  state.availableDepartments.map((name) => ({
    label: name,
    value: name,
  })),
)

const policyDepartmentOptions = computed(() => [
  { label: '* 全院', value: '*' },
  ...departmentOptions.value,
])

const enabledTableCount = computed(() => state.pgSyncTables.filter((item) => item.enabled).length)
const hasTableGroups = computed(() => state.pgTableGroups.length > 0)

const tableGroupOptions = computed(() =>
  state.pgTableGroups.map((item) => ({
    label: `${item.label}${item.table_count ? `（${item.table_count}）` : ''}`,
    value: item.id,
  })),
)

const selectedTableGroupSummary = computed(() => {
  const selected = Array.isArray(state.selectedTableGroups) ? state.selectedTableGroups : []
  if (selected.length === 0) {
    return '默认核心8表'
  }
  const labelMap = new Map(
    state.pgTableGroups.map((item) => [
      String(item.id || '').trim(),
      String(item.label || item.id || '').trim(),
    ]),
  )
  const labels = selected
    .map((item) => labelMap.get(String(item || '').trim()) || String(item || '').trim())
    .filter(Boolean)
  return labels.length > 0 ? labels.join(' / ') : '默认核心8表'
})

const policyDateRangeLabel = computed(() => {
  const start = state.policyForm.start_date || '未设'
  const end = state.policyForm.end_date || '未设'
  return `${start} ~ ${end}`
})

const nightWindowLabel = computed(() => {
  const start = state.policyForm.night_window_start || '--:--'
  const end = state.policyForm.night_window_end || '--:--'
  return `${start} ~ ${end}`
})

const filteredPgTables = computed(() => {
  const keyword = tableKeyword.value.trim().toLowerCase()
  return state.pgSyncTables.filter((item) => {
    if (onlyEnabledTables.value && !item.enabled) {
      return false
    }
    if (!keyword) {
      return true
    }
    return [item.name, item.source_table, item.date_field, item.fallback_date_field]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(keyword))
  })
})

const preflightTableRows = computed(() => {
  const result = state.preflightResult
  if (!result) {
    return [] as Array<{
      table: string
      source: string
      dateField: string
      executable: boolean
      blockers: string
    }>
  }
  const sourceRows: SyncTableValidationItem[] = result.execution_table_validations?.length
    ? result.execution_table_validations
    : result.table_validations || []

  return sourceRows.map((item) => ({
    table: item.table || '-',
    source: item.source || item.source_table || '-',
    dateField: item.resolved_date_field || item.date_field || item.fallback_date_field || '-',
    executable: Boolean(item.executable),
    blockers: (item.blockers || []).join('；'),
  }))
})

const matrixExecutionScopeLabel = computed(() => {
  const scope = state.preflightResult?.matrix_scope?.execution
  return scope === 'all' ? '全部表' : '启用表'
})

const matrixFullScopeLabel = computed(() => {
  const scope = state.preflightResult?.matrix_scope?.full
  return scope === 'all' ? '全部表' : '启用表'
})

const preflightStatusText = computed(() => {
  if (!state.preflightResult) {
    return '未预检'
  }
  return state.preflightResult.executable ? '预检通过' : '预检阻断'
})

const preflightToneClass = computed(() => {
  if (!state.preflightResult) {
    return 'studio-pill--neutral'
  }
  return state.preflightResult.executable ? 'studio-pill--success' : 'studio-pill--danger'
})

onMounted(() => {
  state.activeTab = 'pg_remote'
  if (!state.pgTableGroups.length) {
    void loadPgSyncTableGroups()
  }
})

const tabClass = (tab: 'pg_remote' | 'pg_local') => [
  'flex-1 py-1.5 rounded-[6px] text-[12px] font-medium transition-all duration-300 relative z-10',
  state.activeTab === tab
    ? 'bg-white text-slate-800 shadow-[0_1px_4px_rgba(15,23,42,0.08)] ring-1 ring-slate-900/5'
    : 'text-slate-500 hover:text-slate-700',
]

const normalizeDateValue = (value: DateValue): string => {
  if (!value) {
    return ''
  }
  return dayjs(value).format('YYYY-MM-DD')
}

const normalizeDepartments = (values: string[]): string[] => {
  const cleaned = [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))]
  if (cleaned.length === 0) {
    return ['*']
  }
  if (cleaned.includes('*') && cleaned.length > 1) {
    const latest = cleaned[cleaned.length - 1]
    return latest === '*' ? ['*'] : cleaned.filter((item) => item !== '*')
  }
  return cleaned
}

const normalizeSelectedTableGroups = (values: string[]): string[] => {
  const validIds = new Set(
    state.pgTableGroups.map((item) => String(item.id || '').trim()).filter(Boolean),
  )
  const cleaned = [...new Set(values.map((item) => String(item || '').trim()).filter(Boolean))]
  const kept = cleaned.filter((item) => validIds.has(item))
  if (kept.length > 0) {
    return kept
  }
  if (validIds.has('core_8')) {
    return ['core_8']
  }
  return Array.from(validIds).slice(0, 1)
}

const applyTableGroupPreset = (preset: 'core' | 'clinical' | 'all') => {
  const validIds = new Set(
    state.pgTableGroups.map((item) => String(item.id || '').trim()).filter(Boolean),
  )
  if (validIds.size === 0) {
    return
  }

  let next: string[] = []
  if (preset === 'core') {
    next = ['core_8']
  } else if (preset === 'all') {
    next = validIds.has('all_56') ? ['all_56'] : Array.from(validIds)
  } else {
    next = [
      'core_8',
      'document_extended',
      'diagnosis_extended',
      'orders_prescriptions',
      'exam_lab_pathology',
      'inpatient_notes',
    ]
  }
  state.selectedTableGroups = normalizeSelectedTableGroups(next)
}

const handlePolicyStartDateChange = (value: DateValue) => {
  state.policyForm.start_date = normalizeDateValue(value)
}

const handlePolicyEndDateChange = (value: DateValue) => {
  state.policyForm.end_date = normalizeDateValue(value)
}

const handlePolicyDepartmentChange = (values: string[]) => {
  state.policyForm.target_departments = normalizeDepartments(values)
}

const handleTestCurrent = async () => {
  try {
    const result = await testActiveConnection()
    if (result.connected) {
      message.success('连接成功')
    } else {
      message.warning(result.error || '连接失败')
    }
  } catch {
    message.error('连接测试失败')
  }
}

const handleSavePg = async () => {
  try {
    const result = await savePgConnection()
    if (result.connection?.connected) {
      message.success('PG 配置已保存并连通')
    } else {
      message.warning(`PG 配置已保存，但连接失败：${result.connection?.error || '未知错误'}`)
    }
  } catch {
    message.error('PG 配置保存失败')
  }
}

const handleReloadPgTables = async () => {
  try {
    await loadPgSyncTables()
    message.success('PG 表配置已刷新')
  } catch {
    message.error('刷新 PG 表配置失败')
  }
}

const handleSavePgTables = async () => {
  try {
    await savePgSyncTables()
    message.success('PG 表同步配置已保存')
  } catch {
    message.error('保存 PG 表同步配置失败')
  }
}

const handleRefreshTemplateResources = async () => {
  try {
    await Promise.all([loadTemplates(), loadDepartments(), loadPgSyncTableGroups()])
    state.selectedTableGroups = normalizeSelectedTableGroups(state.selectedTableGroups || [])
    message.success('模板、科室与分组列表已刷新')
  } catch {
    message.error('刷新模板资源失败')
  }
}

const handleApplyTemplate = async () => {
  try {
    await applyTemplate()
    message.success('模板已应用并触发预检')
  } catch {
    message.error('应用模板失败')
  }
}

const handleSavePolicy = async () => {
  const start = state.policyForm.start_date
  const end = state.policyForm.end_date
  if (start && end && dayjs(start).isAfter(dayjs(end))) {
    message.warning('开始日期不能晚于结束日期')
    return
  }

  state.policyForm.target_departments = normalizeDepartments(
    state.policyForm.target_departments || [],
  )
  try {
    await savePolicy()
    message.success('策略已保存')
  } catch {
    message.error('保存策略失败')
  }
}

const handleRunPreflight = async () => {
  state.selectedTableGroups = normalizeSelectedTableGroups(state.selectedTableGroups || [])
  try {
    const result = await runPreflight('pg')
    if (result.executable) {
      message.success('预检通过')
    } else {
      message.warning(`预检未通过：${result.blockers?.join('；') || '存在阻断项'}`)
    }
  } catch {
    message.error('执行预检失败')
  }
}
</script>

<style scoped>
.studio-input {
  width: 100%;
  padding: 6px 10px;
  font-size: 13px;
  line-height: 1.4;
  color: #1d1d1f;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  outline: none;
  transition: all 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.studio-input:focus {
  border-color: rgba(43, 108, 246, 0.38);
  box-shadow: 0 0 0 3px rgba(43, 108, 246, 0.08);
}

.studio-input:disabled {
  background: rgba(245, 245, 247, 0.72);
  color: rgba(29, 29, 31, 0.38);
  cursor: not-allowed;
}

.studio-label {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: rgba(29, 29, 31, 0.6);
  font-weight: 600;
}

.studio-summary-card {
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.86);
  padding: 10px 12px;
}

.studio-summary-card__label {
  font-size: 11px;
  color: rgba(29, 29, 31, 0.5);
  font-weight: 600;
}

.studio-summary-card__value {
  margin-top: 3px;
  font-size: 16px;
  font-weight: 600;
  color: #1d1d1f;
}

.studio-pill {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
}

.studio-pill--neutral {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(0, 0, 0, 0.04);
  color: rgba(29, 29, 31, 0.6);
}

.studio-pill--success {
  border-color: rgba(16, 185, 129, 0.2);
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
}

.studio-pill--danger {
  border-color: rgba(239, 68, 68, 0.2);
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
}

.studio-matrix-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  color: rgba(29, 29, 31, 0.7);
}

.studio-matrix-table thead th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: rgba(245, 245, 247, 0.72);
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
  font-weight: 600;
  text-align: left;
  padding: 8px 10px;
  white-space: nowrap;
}

.studio-matrix-table tbody td {
  padding: 8px 10px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  vertical-align: top;
}

.studio-inline-status {
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  height: 20px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
}

.studio-inline-status--ok {
  color: #047857;
  background: rgba(16, 185, 129, 0.08);
}

.studio-inline-status--bad {
  color: #b91c1c;
  background: rgba(239, 68, 68, 0.08);
}

.connection-studio {
  background: rgba(255, 255, 255, 0.9);
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
}

.connection-studio > div:first-child {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
}

.connection-studio > div:nth-child(2) > div {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(245, 245, 247, 0.68);
}

.connection-studio :deep(.rounded-xl),
.connection-studio :deep(.rounded-lg),
.connection-studio :deep(.rounded) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.connection-studio :deep(.bg-white),
.connection-studio :deep(.bg-slate-50),
.connection-studio :deep(.bg-slate-50\/70),
.connection-studio :deep(.bg-slate-100\/80) {
  background-color: rgba(255, 255, 255, 0.86) !important;
}

.connection-studio :deep(.text-slate-900),
.connection-studio :deep(.text-slate-800),
.connection-studio :deep(.text-slate-700) {
  color: #1d1d1f !important;
}

.connection-studio :deep(.text-slate-600),
.connection-studio :deep(.text-slate-500) {
  color: rgba(29, 29, 31, 0.6) !important;
}

.connection-studio :deep(.text-slate-400) {
  color: rgba(29, 29, 31, 0.38) !important;
}

.connection-studio :deep(.text-amber-600\/90),
.connection-studio :deep(.text-amber-700) {
  color: #b45309 !important;
}

.connection-studio :deep(.text-rose-600),
.connection-studio :deep(.text-rose-700) {
  color: #b91c1c !important;
}

.connection-studio :deep(.bg-amber-50\/80) {
  background-color: rgba(245, 158, 11, 0.08) !important;
}

.connection-studio :deep(.bg-rose-50\/80) {
  background-color: rgba(239, 68, 68, 0.08) !important;
}

.connection-studio :deep(.font-mono),
.studio-matrix-table td:nth-child(1),
.studio-matrix-table td:nth-child(2),
.studio-matrix-table td:nth-child(3) {
  font-family: 'SF Mono', 'Cascadia Code', ui-monospace, monospace;
}
</style>
