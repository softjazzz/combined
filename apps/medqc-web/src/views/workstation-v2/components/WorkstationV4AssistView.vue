<template>
  <WorkstationAssistPanel
    v-if="selectedRecord"
    :visible="visible"
    :default-tab="assistTab"
    :patient-info="assistPatientInfo"
    :content-count="contentQCCount"
    :qc-count="assistBadgeCount"
    :profile-count="frontpageDraft ? 1 : 0"
    :drg-count="drgResult ? 1 : 0"
    :message-count="notificationUnreadCount"
    @update:visible="emit('update:visible', $event)"
    @tab-change="emit('tab-change', $event)"
    @refresh-tab="emit('refresh-tab', $event)"
  >
    <template #content>
      <ContentQCTab
        :patient-id="selectedRecord?.patientId"
        :visit-id="selectedRecord?.id"
        :institute-id="selectedRecord?.instituteId"
        :documents="documentsList"
        @issues-change="emit('content-issues-change', $event)"
      />
    </template>
    <template #qc="{ activeSubTab }">
      <QCResultTab
        ref="qcResultTabRef"
        :frontpage="frontpageDraft"
        :analyzing="frontpageGenerating"
        :refresh-seed="qcRefreshSeed"
        :active-tab="activeSubTab"
        :visit-id="selectedRecord?.visitId || selectedId"
        :patient-id="selectedRecord?.patientId"
        :institute-id="selectedRecord?.instituteId"
        @issues-change="emit('qc-issues-change', $event)"
        @locate-field="emit('locate-field', $event)"
        @jump-evidence="emit('jump-evidence', $event)"
      />
    </template>
    <template #profile>
      <div class="space-y-3 p-3">
        <div
          class="rounded-[18px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(247,250,252,0.98))] p-3.5 shadow-[0_10px_22px_rgba(15,23,42,0.04)]"
        >
          <div class="mb-1 text-[10px] font-black uppercase tracking-[0.08em] text-blue-600">
            当前分析
          </div>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-[15px] font-black text-slate-900">
                AI 深度画像
              </div>
              <div class="mt-1 max-w-[240px] text-[12px] leading-5 text-slate-500">
                对病历全文进行深度阅读，生成时间轴、风险线索与结构化患者画像。
              </div>
            </div>
            <div
              v-if="profileAnalyzed"
              class="rounded-[14px] border border-blue-200 bg-blue-50/85 px-3 py-2 text-right"
            >
              <div class="text-[10px] font-bold uppercase tracking-[0.08em] text-blue-600">
                状态
              </div>
              <div class="mt-1 text-[13px] font-black text-blue-700">
                已生成
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="!profileAnalyzed && !profileAnalyzing"
          class="flex min-h-[268px] flex-col items-center justify-center rounded-[20px] border border-dashed border-blue-200/75 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(248,251,255,0.98))] px-5 py-10 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.82),0_16px_34px_rgba(148,163,184,0.1)]"
        >
          <div
            class="mb-4 flex h-14 w-14 items-center justify-center rounded-[16px] border border-blue-200 bg-[linear-gradient(180deg,#eef4ff,#dbeafe)] shadow-[0_10px_20px_rgba(59,130,246,0.12),inset_0_1px_0_rgba(255,255,255,0.72)]"
          >
            <ScanOutlined class="text-[24px] text-blue-600" />
          </div>
          <div class="mb-1 text-[15px] font-black text-slate-800">
            AI 深度画像
          </div>
          <div class="mb-5 max-w-[228px] text-[12px] leading-6 text-slate-500">
            对病历全文进行深度阅读，构建诊断时间轴与患者风险画像。
          </div>
          <a-button
            type="primary"
            size="small"
            :disabled="!combinedMedicalText"
            class="!h-9 !rounded-full !border-0 !px-5 !text-sm !font-bold !shadow-[0_10px_20px_rgba(37,99,235,0.18),inset_0_1px_0_rgba(255,255,255,0.14)]"
            @click="emit('open-ai-profile')"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            开始分析
          </a-button>
        </div>

        <template v-else>
          <div class="rounded-[18px] border border-slate-200/80 bg-white/80 p-3.5">
            <div class="mb-2 flex items-center gap-2">
              <ScanOutlined class="text-blue-500" />
              <span class="text-xs font-bold text-slate-700">画像摘要</span>
              <span
                class="ml-auto rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-bold text-blue-600"
              >已生成</span>
            </div>
            <div class="space-y-1.5 text-xs text-slate-600">
              <div
                v-if="frontpageDraft?.diagnoses?.discharge_main_diagnosis_text"
                class="flex items-center gap-1.5 rounded-[12px] bg-slate-50/85 px-2.5 py-2"
              >
                <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0" />
                <span class="truncate">{{
                  frontpageDraft.diagnoses.discharge_main_diagnosis_text
                }}</span>
              </div>
              <div class="flex items-center gap-1.5 rounded-[12px] bg-slate-50/85 px-2.5 py-2">
                <span class="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                <span>诊断时间轴 + 人体透视 + 器官画像</span>
              </div>
            </div>
          </div>
          <a-button
            block
            class="!h-9 !rounded-full !border-slate-200/90 !bg-white/85 !text-sm !font-bold !text-slate-700 !shadow-none hover:!border-blue-200 hover:!text-blue-700"
            @click="emit('open-ai-profile')"
          >
            <template #icon>
              <EyeOutlined />
            </template>
            查看完整 AI 画像
          </a-button>
        </template>
      </div>

      <a-modal
        :open="aiProfileModalVisible"
        title="AI 深度画像分析"
        :width="1100"
        :footer="null"
        :body-style="{
          padding: '12px',
          height: '78vh',
          overflow: 'hidden',
          background: 'linear-gradient(180deg,#f8fafc 0%,#f2f6fa 100%)',
        }"
        centered
        destroy-on-close
        @update:open="emit('update:aiProfileModalVisible', $event)"
      >
        <div
          class="h-full overflow-hidden rounded-[18px] border border-white/85 bg-white/88 shadow-[0_10px_22px_rgba(15,23,42,0.05)]"
        >
          <AsyncAIProfileDashboard
            :frontpage="frontpageDraft"
            :medical-text="combinedMedicalText"
            style="height: 100%; overflow-y: auto"
          />
        </div>
      </a-modal>
    </template>
    <template #drg>
      <div class="space-y-3 p-3">
        <div
          class="rounded-[18px] border border-slate-200/80 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(247,250,252,0.98))] p-3.5 shadow-[0_10px_22px_rgba(15,23,42,0.04)]"
        >
          <div class="mb-1 text-[10px] font-black uppercase tracking-[0.08em] text-blue-600">
            当前分析
          </div>
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-[15px] font-black text-slate-900">
                DRG 分组分析
              </div>
              <div class="mt-1 max-w-[240px] text-[12px] leading-5 text-slate-500">
                基于首页诊断与手术编码，生成分组结果、权重与支付风险判断。
              </div>
            </div>
            <div
              v-if="drgResult"
              class="rounded-[14px] border border-blue-200 bg-blue-50/85 px-3 py-2 text-right"
            >
              <div class="text-[10px] font-bold uppercase tracking-[0.08em] text-blue-600">
                状态
              </div>
              <div class="mt-1 text-[13px] font-black text-blue-700">
                已生成
              </div>
            </div>
          </div>
        </div>

        <div
          v-if="!drgResult && !drgLoading"
          class="flex min-h-[268px] flex-col items-center justify-center rounded-[20px] border border-dashed border-blue-200/75 bg-[linear-gradient(180deg,rgba(255,255,255,0.95),rgba(248,251,255,0.98))] px-5 py-10 text-center shadow-[inset_0_1px_0_rgba(255,255,255,0.82),0_16px_34px_rgba(148,163,184,0.1)]"
        >
          <div
            class="mb-4 flex h-14 w-14 items-center justify-center rounded-[16px] border border-blue-200 bg-[linear-gradient(180deg,#eef4ff,#dbeafe)] shadow-[0_10px_20px_rgba(59,130,246,0.12),inset_0_1px_0_rgba(255,255,255,0.72)]"
          >
            <NodeIndexOutlined class="text-[24px] text-blue-600" />
          </div>
          <div class="mb-1 text-[15px] font-black text-slate-800">
            DRG 分组分析
          </div>
          <div class="mb-5 max-w-[228px] text-[12px] leading-6 text-slate-500">
            基于诊断与手术编码进行 DRG 分组，输出分组结果与盈亏风险判断。
          </div>
          <a-button
            type="primary"
            size="small"
            :disabled="!frontpageDraft"
            class="!h-9 !rounded-full !border-0 !px-5 !text-sm !font-bold !shadow-[0_10px_20px_rgba(37,99,235,0.18),inset_0_1px_0_rgba(255,255,255,0.14)]"
            @click="emit('group-drg')"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            开始分析
          </a-button>
        </div>

        <div
          v-else-if="drgLoading"
          class="flex flex-col items-center py-8"
        >
          <a-spin />
          <div class="text-xs text-slate-400 mt-3">
            DRG 分组计算中...
          </div>
        </div>

        <template v-else-if="drgResult">
          <div class="rounded-[18px] border border-slate-200/80 bg-white/80 p-3.5">
            <div class="mb-2 flex items-center gap-2">
              <NodeIndexOutlined class="text-blue-500" />
              <span class="text-xs font-bold text-slate-700">分组结果</span>
            </div>
            <div class="space-y-1.5">
              <div class="flex justify-between rounded-[12px] bg-slate-50/85 px-2.5 py-2 text-xs">
                <span class="text-slate-500">DRG 分组</span>
                <span class="font-bold text-slate-800">{{ drgResult.drg_code || '-' }}</span>
              </div>
              <div class="flex justify-between rounded-[12px] bg-slate-50/85 px-2.5 py-2 text-xs">
                <span class="text-slate-500">权重</span>
                <span class="font-bold text-blue-600">{{ drgResult.weight || '-' }}</span>
              </div>
              <div
                v-if="drgResult.payment"
                class="flex justify-between rounded-[12px] bg-slate-50/85 px-2.5 py-2 text-xs"
              >
                <span class="text-slate-500">支付标准</span>
                <span class="font-bold text-blue-600">¥{{ drgResult.payment }}</span>
              </div>
            </div>
          </div>
          <a-button
            block
            class="!h-9 !rounded-full !border-slate-200/90 !bg-white/85 !text-sm !font-bold !text-slate-700 !shadow-none hover:!border-blue-200 hover:!text-blue-700"
            @click="emit('update:drgDetailModalVisible', true)"
          >
            <template #icon>
              <EyeOutlined />
            </template>
            查看 DRG 详情
          </a-button>
          <a-button
            block
            type="link"
            size="small"
            class="!h-8 !rounded-full !text-xs !font-semibold"
            @click="emit('group-drg')"
          >
            <SyncOutlined /> 重新分组
          </a-button>
        </template>
      </div>

      <a-modal
        :open="drgDetailModalVisible"
        title="DRG 分组详情"
        :width="960"
        :footer="null"
        :body-style="{
          padding: '12px',
          maxHeight: '78vh',
          overflowY: 'auto',
          background: 'linear-gradient(180deg,#f8fafc 0%,#f2f6fa 100%)',
        }"
        centered
        destroy-on-close
        @update:open="emit('update:drgDetailModalVisible', $event)"
      >
        <div
          class="rounded-[18px] border border-white/85 bg-white/88 p-1 shadow-[0_10px_22px_rgba(15,23,42,0.05)]"
        >
          <AsyncDRGGroupingTab
            :drg-result="drgResult as any"
            :loading="drgLoading"
            :has-frontpage="!!frontpageDraft"
            :main-diagnosis-code="frontpageDraft?.diagnoses?.discharge_main_icd || ''"
            :main-diagnosis-text="frontpageDraft?.diagnoses?.discharge_main_diagnosis_text || ''"
            :main-procedure-code="frontpageDraft?.procedures?.main_procedure_code || ''"
            :main-procedure-name="frontpageDraft?.procedures?.main_procedure_text || ''"
            @group="emit('group-drg')"
            @open-optimization="emit('open-optimization')"
          />
        </div>
      </a-modal>
    </template>
    <template #message>
      <div class="space-y-3 p-3">
        <div
          class="flex items-center justify-between gap-2 rounded-[16px] border border-slate-200/80 bg-white/72 px-3 py-2"
        >
          <a-segmented
            :value="overviewViewMode"
            size="small"
            :options="[
              { label: '问题概览', value: 'overview' },
              { label: '消息明细', value: 'detail' },
            ]"
            @update:value="emit('update:overviewViewMode', $event as 'overview' | 'detail')"
          />
          <a-button
            type="link"
            size="small"
            :disabled="notificationUnreadCount === 0"
            class="!h-7 !rounded-full !px-2 !text-xs"
            @click="emit('mark-all-assist-notifications-read')"
          >
            <CheckOutlined /> 全部已读
          </a-button>
        </div>
        <div
          v-if="overviewViewMode === 'overview'"
          class="grid grid-cols-3 gap-2 rounded-[16px] border border-slate-200/70 bg-white/72 p-2"
        >
          <a-select
            :value="overviewDepartmentFilter"
            size="small"
            :options="[
              { label: '全部科室', value: 'all' },
              ...overviewDepartments.map((dept) => ({ label: dept, value: dept })),
            ]"
            @update:value="emit('update:overviewDepartmentFilter', $event as string)"
          />
          <a-select
            :value="overviewTypeFilter"
            size="small"
            :options="[
              { label: '全部类型', value: 'all' },
              ...overviewTypes.map((type) => ({ label: type, value: type })),
            ]"
            @update:value="emit('update:overviewTypeFilter', $event as string)"
          />
          <a-select
            :value="overviewSeverityFilter"
            size="small"
            :options="[
              { label: '全部严重度', value: 'all' },
              ...overviewSeverities.map((severity) => ({ label: severity, value: severity })),
            ]"
            @update:value="emit('update:overviewSeverityFilter', $event as string)"
          />
        </div>
        <div
          v-else
          class="rounded-[16px] border border-slate-200/70 bg-white/72 p-2"
        >
          <a-segmented
            :value="notificationReadFilter"
            size="small"
            :options="[
              { label: '未读', value: 'unread' },
              { label: '全部', value: 'all' },
              { label: '已读', value: 'read' },
            ]"
            @update:value="
              emit('update:notificationReadFilter', $event as 'all' | 'unread' | 'read')
            "
          />
        </div>
        <div
          v-if="notificationLoading || (overviewViewMode === 'overview' && overviewLoading)"
          class="py-8 text-center"
        >
          <a-spin />
        </div>
        <div
          v-else
          class="space-y-2 max-h-[440px] overflow-y-auto custom-scrollbar pr-1"
        >
          <template v-if="overviewViewMode === 'overview'">
            <div
              v-for="item in filteredNotificationOverviewItems"
              :key="item.overview_id"
              class="rounded-[16px] border p-3 shadow-[0_4px_12px_rgba(15,23,42,0.025)]"
              :class="
                item.unread_count > 0
                  ? 'border-blue-200/80 bg-blue-50/72'
                  : 'border-slate-200/80 bg-white/74'
              "
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 text-sm font-semibold text-slate-800">
                    <NotificationOutlined class="text-blue-500" />
                    <span class="truncate">{{ item.title || '病案问题集中点' }}</span>
                    <a-tag
                      color="blue"
                      class="!text-[10px]"
                    >
                      {{ item.type || 'general' }}
                    </a-tag>
                    <a-tag class="!text-[10px]">
                      {{ item.severity || 'info' }}
                    </a-tag>
                  </div>
                  <div class="mt-1 text-xs text-slate-500 leading-5">
                    {{ item.summary || '暂无内容' }}
                  </div>
                  <div class="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                    <span>{{ item.department || '未分科室' }}</span>
                    <span>·</span>
                    <span>触发 {{ item.occurrence_count }} 次</span>
                    <span>·</span>
                    <span>{{ formatRelativeTime(item.latest_created_at) }}</span>
                  </div>
                </div>
                <a-tag
                  v-if="item.unread_count > 0"
                  color="blue"
                >
                  {{ item.unread_count }} 未读
                </a-tag>
              </div>
              <div class="mt-2 flex items-center justify-end gap-2">
                <a-button
                  size="small"
                  class="!h-8 !rounded-full !border-slate-200/90 !shadow-none"
                  @click="emit('assist-overview-click', item)"
                >
                  定位处理
                </a-button>
              </div>
            </div>
          </template>
          <template v-else>
            <div
              v-for="notif in filteredAssistNotifications"
              :key="notif.id"
              class="rounded-[16px] border p-3 shadow-[0_4px_12px_rgba(15,23,42,0.025)]"
              :class="
                notif.is_read
                  ? 'border-slate-200/80 bg-white/74'
                  : 'border-blue-200/80 bg-blue-50/72'
              "
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 text-sm font-semibold text-slate-800">
                    <NotificationOutlined class="text-blue-500" />
                    <span class="truncate">{{ notif.title || '通知消息' }}</span>
                  </div>
                  <div class="mt-1 text-xs text-slate-500 leading-5">
                    {{ notif.content || '暂无内容' }}
                  </div>
                  <div class="mt-1 text-[11px] text-slate-400">
                    {{ formatRelativeTime(notif.created_at) }}
                  </div>
                </div>
                <a-tag
                  v-if="!notif.is_read"
                  color="blue"
                >
                  未读
                </a-tag>
              </div>
              <div class="mt-2 flex items-center justify-end gap-2">
                <a-button
                  size="small"
                  class="!h-8 !rounded-full !border-slate-200/90 !shadow-none"
                  @click="emit('assist-notification-click', notif)"
                >
                  去处理
                </a-button>
                <a-button
                  v-if="!notif.is_read"
                  type="link"
                  size="small"
                  class="!h-8 !rounded-full !text-xs"
                  @click="emit('mark-assist-notification-read', notif)"
                >
                  标记已读
                </a-button>
              </div>
            </div>
          </template>
          <div
            v-if="
              (overviewViewMode === 'overview' && filteredNotificationOverviewItems.length === 0) ||
                (overviewViewMode === 'detail' && filteredAssistNotifications.length === 0)
            "
            class="rounded-[18px] border border-dashed border-slate-200 bg-white/70 py-8"
          >
            <a-empty
              :description="overviewViewMode === 'overview' ? '当天暂无问题集中点' : '暂无消息'"
            />
          </div>
        </div>
      </div>
    </template>
  </WorkstationAssistPanel>

  <a-drawer
    :open="suggestionDrawerVisible"
    title="DRG 优化建议"
    placement="right"
    :width="560"
    :header-style="{
      borderBottom: '1px solid rgba(148,163,184,0.14)',
      background: 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,252,0.96) 100%)',
      padding: '16px 18px',
    }"
    :body-style="{
      padding: '16px',
      background: 'linear-gradient(180deg,#f8fafc 0%,#f3f6fa 100%)',
    }"
    @update:open="emit('update:suggestionDrawerVisible', $event)"
  >
    <div class="space-y-3">
      <div
        v-for="item in suggestions"
        :key="item.suggestion_id"
        class="rounded-[18px] border border-slate-200/80 bg-white/88 p-4 shadow-[0_6px_16px_rgba(15,23,42,0.03)]"
      >
        <div class="mb-2 flex items-center justify-between gap-3">
          <div class="text-sm font-semibold text-slate-800">
            {{ getSuggestionTitle(item.suggestion_type) }}
          </div>
          <a-tag :color="suggestionSeverityTag(item.severity)">
            {{ item.severity || 'info' }}
          </a-tag>
        </div>
        <div class="text-sm text-slate-700 leading-6">
          {{ item.message }}
        </div>
        <div
          v-if="item.evidence"
          class="mt-2 rounded-[12px] bg-slate-50/88 px-3 py-2 text-xs text-slate-500"
        >
          依据：{{ item.evidence }}
        </div>
        <div class="mt-3 flex justify-end gap-2">
          <a-button
            size="small"
            class="!h-8 !rounded-full !border-slate-200/90 !shadow-none"
            @click="emit('drg-suggestion', 'reject', item.suggestion_id)"
          >
            忽略
          </a-button>
          <a-button
            type="primary"
            size="small"
            class="!h-8 !rounded-full !border-0 !shadow-[0_6px_14px_rgba(37,99,235,0.14)]"
            @click="emit('drg-suggestion', 'accept', item.suggestion_id)"
          >
            采纳并重算
          </a-button>
        </div>
      </div>

      <a-empty
        v-if="!suggestionsLoading && suggestions.length === 0"
        description="暂无待处理优化建议"
      />
      <div
        v-if="suggestionsLoading"
        class="flex items-center justify-center py-10"
      >
        <a-spin />
      </div>
    </div>
  </a-drawer>

  <a-drawer
    :open="icdDrawerVisible"
    title="ICD 编码查询"
    placement="right"
    :width="920"
    :header-style="{
      borderBottom: '1px solid rgba(148,163,184,0.14)',
      background: 'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,252,0.96) 100%)',
      padding: '16px 18px',
    }"
    :body-style="{
      padding: '0',
      background: 'linear-gradient(180deg,#f8fafc 0%,#f2f6fa 100%)',
    }"
    @update:open="emit('update:icdDrawerVisible', $event)"
  >
    <div class="border-b border-slate-200/70 bg-white/82 px-4 py-3">
      <div class="rounded-[16px] border border-slate-200/80 bg-slate-50/78 px-3 py-3">
        <div class="mb-2 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
          回填目标
        </div>
        <div class="flex flex-wrap items-center gap-3">
          <a-segmented
            :value="icdApplyTarget"
            :options="icdTargetOptions as any"
            size="small"
            @update:value="emit('update:icdApplyTarget', $event)"
          />
          <div
            v-if="isOtherTarget"
            class="flex items-center gap-2 text-xs text-slate-500"
          >
            <span>第</span>
            <a-input-number
              :value="icdApplyIndex"
              :min="1"
              :max="20"
              size="small"
              style="width: 78px"
              @update:value="emit('update:icdApplyIndex', $event as number)"
            />
            <span>条</span>
          </div>
        </div>
      </div>
    </div>
    <div class="p-3">
      <div
        class="overflow-hidden rounded-[18px] border border-white/85 bg-white/88 shadow-[0_8px_18px_rgba(15,23,42,0.04)]"
      >
        <ICDSearchPanel
          allow-apply
          :apply-label="icdApplyLabel"
          @apply="emit('apply-icd-code', $event)"
        />
      </div>
    </div>
  </a-drawer>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref } from 'vue'
import {
  CheckOutlined,
  EyeOutlined,
  NodeIndexOutlined,
  NotificationOutlined,
  ScanOutlined,
  SyncOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'

import WorkstationAssistPanel from './WorkstationAssistPanel.vue'
import QCResultTab from './QCResultTab.vue'
import ContentQCTab from './ContentQCTab.vue'
import ICDSearchPanel from './ICDSearchPanel.vue'
import type { ICDCodeDetail } from './ICDDetailPanel.vue'
import type { DocItem, PatientRecord } from '../types'

type AssistTabKey = 'content' | 'form' | 'coding' | 'cost' | 'profile' | 'drg' | 'message'

const AsyncAIProfileDashboard = defineAsyncComponent(
  () => import('../../demo/frontpage/components/AIProfileDashboard.vue'),
)
const AsyncDRGGroupingTab = defineAsyncComponent(
  () => import('../../demo/frontpage/components/DRGGroupingTab.vue'),
)

defineProps<{
  visible: boolean
  assistTab: AssistTabKey
  selectedRecord?: PatientRecord | null
  assistPatientInfo?: Record<string, unknown> | null
  contentQCCount: number
  assistBadgeCount: number
  frontpageDraft?: Record<string, any> | null
  frontpageGenerating: boolean
  qcRefreshSeed: number
  selectedId: string
  documentsList: DocItem[]
  notificationUnreadCount: number
  profileAnalyzed: boolean
  profileAnalyzing: boolean
  aiProfileModalVisible: boolean
  combinedMedicalText: string
  drgResult?: any | null
  drgLoading: boolean
  drgDetailModalVisible: boolean
  overviewViewMode: 'overview' | 'detail'
  overviewDepartmentFilter: string
  overviewTypeFilter: string
  overviewSeverityFilter: string
  notificationReadFilter: 'all' | 'unread' | 'read'
  overviewDepartments: string[]
  overviewTypes: string[]
  overviewSeverities: string[]
  notificationLoading: boolean
  overviewLoading: boolean
  filteredNotificationOverviewItems: Array<Record<string, any>>
  filteredAssistNotifications: Array<Record<string, any>>
  formatRelativeTime: (value?: string | null) => string
  suggestionDrawerVisible: boolean
  suggestions: Array<Record<string, any>>
  suggestionsLoading: boolean
  getSuggestionTitle: (type?: string) => string
  suggestionSeverityTag: (severity?: string) => string
  icdDrawerVisible: boolean
  icdApplyTarget: string
  icdTargetOptions: Array<string | number | Record<string, any>>
  isOtherTarget: boolean
  icdApplyIndex: number
  icdApplyLabel: string
}>()

const emit = defineEmits<{
  'update:visible': [boolean]
  'tab-change': [AssistTabKey]
  'refresh-tab': [AssistTabKey]
  'content-issues-change': [number]
  'qc-issues-change': [unknown[]]
  'locate-field': [unknown]
  'jump-evidence': [unknown]
  'open-ai-profile': []
  'update:aiProfileModalVisible': [boolean]
  'group-drg': []
  'open-optimization': []
  'update:drgDetailModalVisible': [boolean]
  'update:overviewViewMode': ['overview' | 'detail']
  'mark-all-assist-notifications-read': []
  'update:overviewDepartmentFilter': [string]
  'update:overviewTypeFilter': [string]
  'update:overviewSeverityFilter': [string]
  'update:notificationReadFilter': ['all' | 'unread' | 'read']
  'assist-overview-click': [Record<string, any>]
  'assist-notification-click': [Record<string, any>]
  'mark-assist-notification-read': [Record<string, any>]
  'update:suggestionDrawerVisible': [boolean]
  'drg-suggestion': ['accept' | 'reject', number]
  'update:icdDrawerVisible': [boolean]
  'update:icdApplyTarget': [unknown]
  'update:icdApplyIndex': [number]
  'apply-icd-code': [ICDCodeDetail]
}>()

const qcResultTabRef = ref<InstanceType<typeof QCResultTab> | null>(null)

defineExpose({
  runFormQC: () => qcResultTabRef.value?.runFormQC(),
  runCodingQC: () => qcResultTabRef.value?.runCodingQC(),
})
</script>
