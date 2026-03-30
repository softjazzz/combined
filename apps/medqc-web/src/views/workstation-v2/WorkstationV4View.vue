<template>
  <div
    class="workstation-shell relative h-full flex overflow-hidden bg-[linear-gradient(180deg,#f8fafc_0%,#f1f5f9_48%,#edf2f7_100%)] dark:bg-slate-950"
  >
    <!-- ====== 列表模式 ====== -->
    <template v-if="viewMode === 'list'">
      <main class="relative z-10 flex min-w-0 flex-1 flex-col overflow-hidden">
        <div class="custom-scrollbar flex-1 overflow-y-auto px-4 pb-5 pt-4 xl:px-5">
          <div class="mx-auto w-full max-w-[1440px]">
            <div class="workstation-surface-enter">
              <PriorityLane
                v-model:active-group="activePriorityGroup"
                class="mb-4"
                :groups="priorityGroups"
                :cards="priorityCardsFiltered"
                :readonly="isStageQueueMode"
                @open-record="handlePriorityOpen"
                @defer-record="handlePriorityDefer"
              />
            </div>

            <div class="workstation-surface-enter workstation-surface-enter--delay-1 mb-4">
              <div class="workstation-panel workstation-panel--filters">
                <div
                  class="pointer-events-none absolute right-[-48px] top-[-72px] h-[220px] w-[220px] rounded-full bg-[radial-gradient(circle,rgba(255,255,255,0.68),rgba(255,255,255,0))]"
                />
                <div
                  class="pointer-events-none absolute bottom-[-120px] left-[18%] h-[220px] w-[260px] rounded-full bg-[radial-gradient(circle,rgba(226,232,240,0.8),rgba(226,232,240,0))]"
                />

                <div class="relative workbench-hero">
                  <div class="workbench-controls-panel">
                    <div class="workbench-controls-search-row">
                      <a-input
                        v-model:value="searchText"
                        class="workbench-controls__search-input"
                        placeholder="搜索病案号、姓名、住院号"
                        size="large"
                        allow-clear
                      >
                        <template #prefix>
                          <SearchOutlined class="text-slate-400" />
                        </template>
                      </a-input>
                    </div>

                    <div class="workbench-dept-row">
                      <div class="workbench-dept-row__list">
                        <button
                          v-for="dept in visibleDepartments"
                          :key="dept.name"
                          type="button"
                          :class="[
                            'workbench-dept-chip',
                            activeDept === dept.name
                              ? 'workbench-dept-chip--active'
                              : 'workbench-dept-chip--idle',
                          ]"
                          @click="selectDept(dept.name)"
                        >
                          <span>{{ dept.name }}</span>
                          <span class="workbench-dept-chip__count">
                            {{ dept.total }}
                          </span>
                        </button>

                        <a-dropdown
                          v-if="overflowDepartments.length > 0"
                          trigger="click"
                          placement="bottomRight"
                        >
                          <button
                            type="button"
                            class="workbench-dept-chip workbench-dept-chip--idle"
                          >
                            <span>更多科室</span>
                            <span class="workbench-dept-chip__count">
                              {{ overflowDepartments.length }}
                            </span>
                            <DownOutlined class="text-[10px]" />
                          </button>
                          <template #overlay>
                            <a-menu
                              class="max-h-[320px] w-[220px] overflow-y-auto rounded-xl p-1.5 shadow-[0_10px_40px_-10px_rgba(0,0,0,0.1)]"
                            >
                              <a-menu-item
                                v-for="dept in overflowDepartments"
                                :key="`overflow-${dept.name}`"
                                class="rounded-lg py-2"
                                @click="selectDept(dept.name)"
                              >
                                <div class="flex items-center justify-between gap-3">
                                  <span class="truncate font-medium text-slate-700">{{
                                    dept.name
                                  }}</span>
                                  <span
                                    class="rounded bg-slate-50 px-1.5 text-[11px] font-bold text-slate-400"
                                  >{{ dept.total }}</span>
                                </div>
                              </a-menu-item>
                            </a-menu>
                          </template>
                        </a-dropdown>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="workstation-surface-enter workstation-surface-enter--delay-2">
              <BatchTablePanel
                :rows="workbenchRows"
                :selected-row-keys="selectedWorkbenchKeys"
                :summary-text="tableSummaryText"
                :loading="loading"
                @update:selected-row-keys="selectedWorkbenchKeys = $event"
                @open-record="handleRowOpen"
                @batch-extract="handleBatchExtract"
                @batch-defer="handleBatchDefer"
                @batch-assign="handleBatchAssign"
                @clear-filters="handleClearFilters"
              />
            </div>

            <div
              v-if="listRecords.length === 0"
              class="workstation-empty-state mt-4 flex min-h-[160px] flex-col items-center justify-center px-5 py-10 text-center"
            >
              <InboxOutlined class="workstation-empty-state__icon mb-3 text-[36px]" />
              <div class="workstation-empty-state__text text-[13px] font-medium">
                {{ stageEmptyText }}
              </div>
            </div>

            <div
              v-if="serverTotalPages > 1"
              class="workstation-pagination-shell mt-3 flex justify-center px-5 py-3"
            >
              <a-pagination
                class="workstation-pagination"
                :current="currentPage"
                :total="serverTotal"
                :page-size="50"
                size="small"
                show-quick-jumper
                :show-total="(value: number) => `共 ${value} 例`"
                @change="handlePageChange"
              />
            </div>
          </div>
        </div>
      </main>
    </template>

    <!-- ====== 详情模式（全屏） ====== -->
    <template v-else-if="viewMode === 'detail'">
      <div
        class="relative z-10 flex-1 flex flex-col min-w-0 h-full bg-[linear-gradient(180deg,rgba(248,250,252,0.9),rgba(241,245,249,0.96))]"
      >
        <!-- 详情顶部栏 -->
        <DetailHeader
          :record="selectedRecord"
          :current-index="currentRecordIndex"
          :total-count="filteredRecords.length"
          :generating="frontpageGenerating"
          :has-draft="!!frontpageDraft"
          :can-generate="canGenerateFrontpage"
          :disabled-reason="frontpageDisabledReason"
          @back="goBackToList"
          @prev="goToPrevRecord"
          @next="goToNextRecord"
          @open-icd="icdDrawerVisible = true"
          @generate-frontpage="handleGenerateFrontpage"
        />

        <!-- 详情主体：左右分栏 -->
        <div class="flex flex-1 overflow-hidden">
          <!-- 左侧：患者信息 -->
          <DetailSidebar
            :record="selectedRecord"
            :documents="documentsList"
            :documents-loading="documentsLoading"
            :active-doc-type="activeDocType"
            @preview-doc="openDocPreview"
          />

          <!-- 文书预览抽屉 -->
          <a-drawer
            v-model:open="docDrawerVisible"
            :title="docDrawerTitle"
            placement="right"
            :width="560"
            :header-style="{
              borderBottom: '1px solid rgba(148,163,184,0.14)',
              background:
                'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,252,0.96) 100%)',
              padding: '16px 18px',
            }"
            :body-style="{
              padding: '16px',
              background: 'linear-gradient(180deg, #f8fafc 0%, #f3f6fa 100%)',
            }"
          >
            <div
              class="rounded-[20px] border border-slate-200/70 bg-white/92 p-4 shadow-[0_8px_18px_rgba(15,23,42,0.045)]"
            >
              <pre class="m-0 whitespace-pre-wrap font-sans text-[13px] leading-7 text-slate-700">{{
                docDrawerContent
              }}</pre>
            </div>
          </a-drawer>

          <!-- 右侧：三 Tab 内容区 -->
          <main
            class="relative flex flex-1 flex-col overflow-hidden bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] dark:bg-slate-950"
          >
            <!-- 自定义 Tab 栏 -->
            <div
              class="sticky top-0 z-10 border-b border-slate-200/55 bg-white/40 px-3 pb-1 pt-1 backdrop-blur-xl lg:px-4"
            >
              <div
                class="inline-flex items-center gap-1 rounded-full border border-slate-200/65 bg-white/66 p-1"
              >
                <button
                  :class="[
                    'rounded-full border px-4 py-1.5 text-[13px] transition-all cursor-pointer',
                    detailMainTab === 'records'
                      ? 'font-bold text-blue-900 bg-blue-50 border-blue-200 shadow-[0_3px_8px_rgba(37,99,235,0.05)]'
                      : 'font-medium text-slate-500 border-transparent hover:bg-white/70 hover:text-slate-800',
                  ]"
                  @click="detailMainTab = 'records'"
                >
                  <span class="flex items-center gap-1.5"><FileTextOutlined />病历详情</span>
                </button>
                <button
                  :class="[
                    'rounded-full border px-4 py-1.5 text-[13px] transition-all cursor-pointer',
                    detailMainTab === 'frontpage'
                      ? 'font-bold text-blue-900 bg-blue-50 border-blue-200 shadow-[0_3px_8px_rgba(37,99,235,0.05)]'
                      : 'font-medium text-slate-500 border-transparent hover:bg-white/70 hover:text-slate-800',
                  ]"
                  @click="detailMainTab = 'frontpage'"
                >
                  <span class="flex items-center gap-1.5"><FileSearchOutlined />病案首页</span>
                </button>
                <button
                  :class="[
                    'rounded-full border px-4 py-1.5 text-[13px] transition-all cursor-pointer',
                    detailMainTab === 'settlement'
                      ? 'font-bold text-blue-900 bg-blue-50 border-blue-200 shadow-[0_3px_8px_rgba(37,99,235,0.05)]'
                      : 'font-medium text-slate-500 border-transparent hover:bg-white/70 hover:text-slate-800',
                  ]"
                  @click="detailMainTab = 'settlement'"
                >
                  <span class="flex items-center gap-1.5">
                    <span style="font-size: 14px">💰</span>结算清单
                    <span
                      v-if="settlementQcFailed > 0"
                      class="ml-1 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-blue-100 text-blue-600 text-[10px] font-bold px-1"
                    >{{ settlementQcFailed }}</span>
                  </span>
                </button>
              </div>
            </div>

            <!-- Tab 内容区 -->
            <div class="flex-1 overflow-y-auto custom-scrollbar">
              <!-- ====== Tab 1: 病历详情 ====== -->
              <div
                v-if="detailMainTab === 'records'"
                class="px-3 pb-4 pt-1.5 lg:px-4 lg:pb-5"
              >
                <div
                  class="relative mx-auto w-full max-w-[1200px] rounded-[16px] border border-slate-200/45 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(252,253,255,0.98))] px-1 py-1.5 shadow-[0_6px_16px_rgba(15,23,42,0.02)] lg:px-1.5 lg:py-2"
                >
                  <!-- AI 预审状态小标签 -->
                  <div
                    v-if="selectedRecord"
                    class="absolute right-4 top-0 flex items-center gap-1 rounded-b-md border-x border-b px-2 py-0.5 text-[10px] font-bold opacity-75"
                    :class="
                      selectedRecord.status === 'completed'
                        ? 'bg-blue-50 text-blue-600 border-blue-100/50'
                        : selectedRecord.status === 'has_defects' ||
                          selectedRecord.status === 'warning'
                          ? 'bg-slate-50 text-slate-500 border-slate-200/70'
                          : 'bg-blue-50 text-blue-600 border-blue-100/50'
                    "
                  >
                    <CheckCircleOutlined v-if="selectedRecord.status === 'completed'" />
                    <WarningOutlined
                      v-else-if="
                        selectedRecord.status === 'has_defects' ||
                          selectedRecord.status === 'warning'
                      "
                    />
                    <ThunderboltOutlined v-else />
                    {{
                      selectedRecord.status === 'completed'
                        ? 'AI 预审通过'
                        : selectedRecord.status === 'has_defects' ||
                          selectedRecord.status === 'warning'
                          ? 'AI 发现缺陷'
                          : 'AI 待审'
                    }}
                  </div>

                  <EMRViewer
                    v-if="selectedRecord && emrRenderState !== 'fallback'"
                    ref="emrViewerRef"
                    :record-id="selectedRecord.id"
                    :visit-id="selectedRecord.visitId || selectedRecord.id"
                    :patient-id="selectedRecord.patientId"
                    :institute-id="selectedRecord.instituteId"
                    :max-height="760"
                    :hide-doc-tabs="true"
                    @loaded="handleEmrLoaded"
                    @error="handleEmrError"
                    @defect-click="handleEmrDefectClick"
                  />

                  <template v-else>
                    <div
                      v-if="concatLoading"
                      class="flex flex-col items-center py-20"
                    >
                      <a-spin size="large" />
                      <div class="text-sm text-slate-400 mt-4">
                        加载病历文书中...
                      </div>
                    </div>
                    <div
                      v-else-if="concatText"
                      class="medical-record-document mx-auto max-w-[116ch] px-3 py-0.5"
                    >
                      <div
                        class="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-[12px] border border-slate-200/80 bg-white/82 px-3 py-2"
                      >
                        <div class="text-[12px] font-semibold text-slate-500">
                          已加载
                          <span class="font-mono text-slate-700">{{ concatSections.length }}</span>
                          段文书， 共
                          <span class="font-mono text-slate-700">{{ concatTotalChars }}</span> 字
                        </div>
                        <a-button
                          size="small"
                          class="!rounded-full !border-slate-200/80 !bg-white !text-slate-700"
                          @click="toggleExpandAllSections"
                        >
                          {{ allConcatSectionsExpanded ? '收起全文' : '展开全文' }}
                        </a-button>
                      </div>
                      <div
                        class="mb-4 flex items-center gap-2 rounded-[10px] border border-blue-100/80 bg-blue-50/55 px-3 py-2 text-xs text-blue-700"
                      >
                        <WarningOutlined />
                        <span>EMR 高亮视图暂不可用，已自动切换到原始文书预览。</span>
                      </div>
                      <div
                        v-for="(section, idx) in concatSections"
                        :key="idx"
                        class="mb-5 rounded-[12px] border border-slate-200/75 bg-white/68 p-3 transition-all"
                      >
                        <button
                          class="mb-2 flex w-full items-center justify-between gap-2 border-none bg-transparent p-0 text-left cursor-pointer"
                          @click="toggleConcatSection(idx)"
                        >
                          <span class="flex items-center gap-2">
                            <FileTextOutlined class="text-blue-400" />
                            <h3 class="m-0 text-[15px] font-bold text-slate-800 dark:text-white">
                              {{ section.title }}
                            </h3>
                          </span>
                          <span class="text-[11px] font-semibold text-blue-600">
                            {{ isConcatSectionExpanded(idx) ? '收起' : '展开' }}
                          </span>
                        </button>
                        <div class="h-px bg-slate-100 mb-2" />
                        <div
                          :class="[
                            'medical-record-document__content-wrap',
                            !isConcatSectionExpanded(idx) &&
                              'medical-record-document__content-wrap--collapsed',
                          ]"
                        >
                          <pre
                            class="medical-record-document__content m-0 whitespace-pre-wrap rounded-[6px] bg-transparent px-0 py-0 font-sans text-[14px] leading-[2.05] text-slate-700 dark:text-slate-300"
                          >{{ section.content }}</pre>
                        </div>
                      </div>
                    </div>
                    <div
                      v-else
                      class="flex flex-col items-center justify-center py-20 text-slate-300"
                    >
                      <div
                        class="w-20 h-20 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center mb-4 border-2 border-dashed border-slate-200 dark:border-slate-700"
                      >
                        <FileTextOutlined class="text-3xl" />
                      </div>
                      <div class="text-sm font-medium mb-1">
                        暂无病历文书
                      </div>
                      <div class="text-xs text-slate-400">
                        该患者当前暂无可展示的病历文书内容。
                      </div>
                    </div>
                  </template>
                </div>
              </div>

              <!-- ====== Tab 2: 病案首页 ====== -->
              <div
                v-if="detailMainTab === 'frontpage'"
                class="px-3 pb-4 pt-1.5 lg:px-4 lg:pb-5"
              >
                <div
                  class="mx-auto w-full max-w-[1200px] rounded-[18px] border border-slate-200/55 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(250,252,255,0.98))] p-2.5 shadow-[0_8px_20px_rgba(15,23,42,0.03)]"
                >
                  <FrontpageWorkspacePanel
                    :generating="frontpageGenerating"
                    :post-processing="frontpagePostProcessing"
                    :draft="frontpageDraft"
                    :frontpage-tab="frontpageTab"
                    :module-cards="frontpageModuleCards"
                    :completed-count="completedModules.length"
                    :total-count="ALL_MODULE_KEYS.length"
                    :sheet-loading="frontpageSheetLoading"
                    :sheet-data="frontpageSheetData"
                    @update:frontpage-tab="frontpageTab = $event"
                    @export-frontpage="handleExportFrontpage"
                    @save-frontpage="handleSaveFrontpage"
                  />
                </div>
              </div>
              <!-- ====== Tab 3: 结算清单 ====== -->
              <div
                v-if="detailMainTab === 'settlement'"
                class="min-h-[400px] px-3 pb-4 pt-1.5 lg:px-4 lg:pb-5"
              >
                <div
                  class="mx-auto w-full max-w-[1200px] rounded-[18px] border border-slate-200/55 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(250,252,255,0.98))] p-2.5 shadow-[0_8px_20px_rgba(15,23,42,0.03)]"
                >
                  <div
                    v-if="settlementLoading"
                    class="flex flex-col items-center py-20"
                  >
                    <a-spin size="large" />
                    <div class="text-sm text-slate-400 mt-4">
                      加载结算清单...
                    </div>
                  </div>
                  <div v-else-if="settlementData">
                    <!-- AI 草稿横幅 -->
                    <div
                      v-if="settlementData?.data_source === 'generated_from_frontpage'"
                      class="mx-1 mb-3 flex items-center gap-3 rounded-[14px] border border-blue-100/80 bg-[linear-gradient(180deg,rgba(244,248,255,0.94),rgba(255,255,255,0.98))] px-4 py-3"
                    >
                      <span class="text-base text-blue-500">☑</span>
                      <div class="min-w-0">
                        <div class="text-sm font-semibold text-blue-700">
                          AI 生成草稿
                        </div>
                        <div class="text-xs text-slate-500">
                          本清单由病案首页 AI 抽取结果和 CDM
                          数据自动组装，需人工审核后方可上传医保系统。
                        </div>
                      </div>
                      <a-tag
                        color="blue"
                        class="ml-auto flex-shrink-0 !rounded-full"
                      >
                        Draft
                      </a-tag>
                    </div>
                    <!-- 操作栏 -->
                    <div
                      class="mb-4 flex items-center justify-between rounded-[14px] border border-slate-200/80 bg-white/72 px-4 py-3"
                    >
                      <div class="text-[13px] text-slate-500">
                        清单流水号:
                        <span class="font-mono font-bold text-slate-700">{{
                          settlementData.medinsur_serial_no || '-'
                        }}</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <a-button
                          size="small"
                          class="!rounded-full !border-slate-200/80 !shadow-none"
                          :loading="settlementQcLoading"
                          @click="runSettlementQc"
                        >
                          <template #icon>
                            <CheckOutlined />
                          </template>
                          执行质控
                        </a-button>
                      </div>
                    </div>
                    <!-- 系统结算清单 -->
                    <SettlementSheet :data="settlementData" />

                    <!-- 质控结果摘要 -->
                    <div
                      v-if="settlementQcReport"
                      class="mb-6"
                    >
                      <h4
                        class="mb-3 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400"
                      >
                        <CheckCircleOutlined class="text-blue-500" /> 质控结果
                      </h4>
                      <div class="mb-4 grid grid-cols-4 gap-2.5">
                        <div
                          class="rounded-[14px] border border-blue-100/80 bg-blue-50/70 p-3 text-center"
                        >
                          <div class="text-2xl font-black text-blue-600">
                            {{ settlementQcReport.summary.total }}
                          </div>
                          <div class="text-[10px] text-slate-400 mt-1">
                            总规则数
                          </div>
                        </div>
                        <div
                          class="rounded-[14px] border border-slate-200/80 bg-slate-50/88 p-3 text-center"
                        >
                          <div class="text-2xl font-black text-slate-700">
                            {{ settlementQcReport.summary.passed }}
                          </div>
                          <div class="text-[10px] text-slate-400 mt-1">
                            通过
                          </div>
                        </div>
                        <div
                          class="rounded-[14px] border border-blue-100/80 bg-blue-50/50 p-3 text-center"
                        >
                          <div class="text-2xl font-black text-blue-700">
                            {{ settlementQcReport.summary.failed }}
                          </div>
                          <div class="text-[10px] text-slate-400 mt-1">
                            未通过
                          </div>
                        </div>
                        <div
                          class="rounded-[14px] border border-slate-200/80 bg-white/88 p-3 text-center"
                        >
                          <div class="text-2xl font-black text-slate-700">
                            {{ settlementQcReport.summary.pass_rate }}
                          </div>
                          <div class="text-[10px] text-slate-400 mt-1">
                            通过率
                          </div>
                        </div>
                      </div>
                      <div class="space-y-2">
                        <div
                          v-for="r in settlementQcReport.results.filter((x: any) => !x.passed)"
                          :key="r.rule_id"
                          class="flex items-start gap-3 rounded-[14px] border bg-white/88 px-4 py-3 dark:bg-slate-800"
                          :class="
                            r.severity === 'error'
                              ? 'border-blue-200 bg-blue-50/35'
                              : 'border-slate-200/80'
                          "
                        >
                          <a-tag
                            color="blue"
                            class="mt-0.5 flex-shrink-0"
                          >
                            {{ r.rule_id }}
                          </a-tag>
                          <div class="min-w-0">
                            <div class="text-sm font-medium text-slate-800 dark:text-slate-200">
                              {{ r.field_name }}
                            </div>
                            <div class="text-xs text-slate-500 mt-0.5">
                              {{ r.message }}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else>
                    <!-- 无数据时展示空白结算清单样表 -->
                    <SettlementSheet :data="{}" />
                  </div>
                </div>
              </div>
            </div>
          </main>
        </div>

        <WorkstationAssistPanel
          v-if="selectedRecord"
          v-model:visible="assistPanelVisible"
          :default-tab="assistTab"
          :patient-info="assistPatientInfo"
          :content-count="contentQCCount"
          :qc-count="assistBadgeCount"
          :profile-count="frontpageDraft ? 1 : 0"
          :drg-count="drgResult ? 1 : 0"
          :message-count="notificationUnreadCount"
          @tab-change="handleAssistTabChange"
          @refresh-tab="handleAssistTabRefresh"
        >
          <template #content>
            <ContentQCTab
              :patient-id="selectedRecord?.patientId"
              :visit-id="selectedRecord?.id"
              :institute-id="selectedRecord?.instituteId"
              :documents="documentsList"
              @issues-change="(count: number) => (contentQCCount = count)"
            />
          </template>
          <template #qc="{ activeSubTab }">
            <QCResultTab
              ref="qcResultTabRef"
              :frontpage="frontpageDraft"
              :analyzing="frontpageGenerating"
              :refresh-seed="qcRefreshSeed"
              :active-tab="activeSubTab"
              :visit-id="selectedId"
              :patient-id="selectedRecord?.patientId"
              @issues-change="handleAssistIssuesChange"
              @locate-field="handleLocateFromQC"
              @jump-evidence="handleJumpEvidenceFromQC"
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

              <!-- 未分析状态 -->
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
                  @click="
                    () => {
                      aiProfileModalVisible = true
                      profileAnalyzed = true
                    }
                  "
                >
                  <template #icon>
                    <ThunderboltOutlined />
                  </template>
                  开始分析
                </a-button>
              </div>

              <!-- 已分析 / 摘要卡 -->
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
                    <div
                      class="flex items-center gap-1.5 rounded-[12px] bg-slate-50/85 px-2.5 py-2"
                    >
                      <span class="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0" />
                      <span>诊断时间轴 + 人体透视 + 器官画像</span>
                    </div>
                  </div>
                </div>
                <a-button
                  block
                  class="!h-9 !rounded-full !border-slate-200/90 !bg-white/85 !text-sm !font-bold !text-slate-700 !shadow-none hover:!border-blue-200 hover:!text-blue-700"
                  @click="aiProfileModalVisible = true"
                >
                  <template #icon>
                    <EyeOutlined />
                  </template>
                  查看完整 AI 画像
                </a-button>
              </template>
            </div>

            <!-- AI 画像 Modal -->
            <a-modal
              v-model:open="aiProfileModalVisible"
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
            >
              <div
                class="h-full overflow-hidden rounded-[18px] border border-white/85 bg-white/88 shadow-[0_10px_22px_rgba(15,23,42,0.05)]"
              >
                <AIProfileDashboard
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

              <!-- DRG 未分组状态 -->
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
                  @click="performDRGGrouping"
                >
                  <template #icon>
                    <ThunderboltOutlined />
                  </template>
                  开始分析
                </a-button>
              </div>

              <!-- DRG 加载中 -->
              <div
                v-else-if="drgLoading"
                class="flex flex-col items-center py-8"
              >
                <a-spin />
                <div class="text-xs text-slate-400 mt-3">
                  DRG 分组计算中...
                </div>
              </div>

              <!-- DRG 已分组 / 摘要卡 -->
              <template v-else-if="drgResult">
                <div class="rounded-[18px] border border-slate-200/80 bg-white/80 p-3.5">
                  <div class="mb-2 flex items-center gap-2">
                    <NodeIndexOutlined class="text-blue-500" />
                    <span class="text-xs font-bold text-slate-700">分组结果</span>
                  </div>
                  <div class="space-y-1.5">
                    <div
                      class="flex justify-between rounded-[12px] bg-slate-50/85 px-2.5 py-2 text-xs"
                    >
                      <span class="text-slate-500">DRG 分组</span>
                      <span class="font-bold text-slate-800">{{ drgResult.drg_code || '-' }}</span>
                    </div>
                    <div
                      class="flex justify-between rounded-[12px] bg-slate-50/85 px-2.5 py-2 text-xs"
                    >
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
                  @click="drgDetailModalVisible = true"
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
                  @click="performDRGGrouping"
                >
                  <SyncOutlined /> 重新分组
                </a-button>
              </template>
            </div>

            <!-- DRG 详情 Modal -->
            <a-modal
              v-model:open="drgDetailModalVisible"
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
            >
              <div
                class="rounded-[18px] border border-white/85 bg-white/88 p-1 shadow-[0_10px_22px_rgba(15,23,42,0.05)]"
              >
                <DRGGroupingTab
                  :drg-result="drgResult"
                  :loading="drgLoading"
                  :has-frontpage="!!frontpageDraft"
                  :main-diagnosis-code="frontpageDraft?.diagnoses?.discharge_main_icd || ''"
                  :main-diagnosis-text="
                    frontpageDraft?.diagnoses?.discharge_main_diagnosis_text || ''
                  "
                  :main-procedure-code="frontpageDraft?.procedures?.main_procedure_code || ''"
                  :main-procedure-name="frontpageDraft?.procedures?.main_procedure_text || ''"
                  @group="performDRGGrouping"
                  @open-optimization="openOptimization"
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
                  v-model:value="overviewViewMode"
                  size="small"
                  :options="[
                    { label: '问题概览', value: 'overview' },
                    { label: '消息明细', value: 'detail' },
                  ]"
                />
                <a-button
                  type="link"
                  size="small"
                  :disabled="notificationUnreadCount === 0"
                  class="!h-7 !rounded-full !px-2 !text-xs"
                  @click="markAllAssistNotificationsRead"
                >
                  <CheckOutlined /> 全部已读
                </a-button>
              </div>
              <div
                v-if="overviewViewMode === 'overview'"
                class="grid grid-cols-3 gap-2 rounded-[16px] border border-slate-200/70 bg-white/72 p-2"
              >
                <a-select
                  v-model:value="overviewDepartmentFilter"
                  size="small"
                  :options="[
                    { label: '全部科室', value: 'all' },
                    ...overviewDepartments.map((dept) => ({ label: dept, value: dept })),
                  ]"
                />
                <a-select
                  v-model:value="overviewTypeFilter"
                  size="small"
                  :options="[
                    { label: '全部类型', value: 'all' },
                    ...overviewTypes.map((type) => ({ label: type, value: type })),
                  ]"
                />
                <a-select
                  v-model:value="overviewSeverityFilter"
                  size="small"
                  :options="[
                    { label: '全部严重度', value: 'all' },
                    ...overviewSeverities.map((severity) => ({ label: severity, value: severity })),
                  ]"
                />
              </div>
              <div
                v-else
                class="rounded-[16px] border border-slate-200/70 bg-white/72 p-2"
              >
                <a-segmented
                  v-model:value="notificationReadFilter"
                  size="small"
                  :options="[
                    { label: '未读', value: 'unread' },
                    { label: '全部', value: 'all' },
                    { label: '已读', value: 'read' },
                  ]"
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
                        @click="handleAssistOverviewClick(item)"
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
                        @click="handleAssistNotificationClick(notif)"
                      >
                        去处理
                      </a-button>
                      <a-button
                        v-if="!notif.is_read"
                        type="link"
                        size="small"
                        class="!h-8 !rounded-full !text-xs"
                        @click="markAssistNotificationRead(notif)"
                      >
                        标记已读
                      </a-button>
                    </div>
                  </div>
                </template>
                <div
                  v-if="
                    (overviewViewMode === 'overview' &&
                      filteredNotificationOverviewItems.length === 0) ||
                      (overviewViewMode === 'detail' && filteredAssistNotifications.length === 0)
                  "
                  class="rounded-[18px] border border-dashed border-slate-200 bg-white/70 py-8"
                >
                  <a-empty
                    :description="
                      overviewViewMode === 'overview' ? '当天暂无问题集中点' : '暂无消息'
                    "
                  />
                </div>
              </div>
            </div>
          </template>
        </WorkstationAssistPanel>

        <a-drawer
          v-model:open="suggestionDrawerVisible"
          title="DRG 优化建议"
          placement="right"
          :width="560"
          :header-style="{
            borderBottom: '1px solid rgba(148,163,184,0.14)',
            background:
              'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,252,0.96) 100%)',
            padding: '16px 18px',
          }"
          :body-style="{
            padding: '16px',
            background: 'linear-gradient(180deg,#f8fafc 0%,#f3f6fa 100%)',
          }"
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
                  @click="handleDRGSuggestion('reject', item.suggestion_id)"
                >
                  忽略
                </a-button>
                <a-button
                  type="primary"
                  size="small"
                  class="!h-8 !rounded-full !border-0 !shadow-[0_6px_14px_rgba(37,99,235,0.14)]"
                  @click="handleDRGSuggestion('accept', item.suggestion_id)"
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
          v-model:open="icdDrawerVisible"
          title="ICD 编码查询"
          placement="right"
          :width="920"
          :header-style="{
            borderBottom: '1px solid rgba(148,163,184,0.14)',
            background:
              'linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(247,250,252,0.96) 100%)',
            padding: '16px 18px',
          }"
          :body-style="{
            padding: '0',
            background: 'linear-gradient(180deg,#f8fafc 0%,#f2f6fa 100%)',
          }"
        >
          <div class="border-b border-slate-200/70 bg-white/82 px-4 py-3">
            <div class="rounded-[16px] border border-slate-200/80 bg-slate-50/78 px-3 py-3">
              <div class="mb-2 text-[11px] font-bold uppercase tracking-[0.12em] text-slate-400">
                回填目标
              </div>
              <div class="flex flex-wrap items-center gap-3">
                <a-segmented
                  v-model:value="icdApplyTarget"
                  :options="icdTargetOptions"
                  size="small"
                />
                <div
                  v-if="isOtherTarget"
                  class="flex items-center gap-2 text-xs text-slate-500"
                >
                  <span>第</span>
                  <a-input-number
                    v-model:value="icdApplyIndex"
                    :min="1"
                    :max="20"
                    size="small"
                    style="width: 78px"
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
                @apply="handleApplyICDCode"
              />
            </div>
          </div>
        </a-drawer>
      </div>
    </template>

    <!-- ====== 质控规则模式 ====== -->
    <template v-else-if="viewMode === 'rules'">
      <aside
        class="w-56 flex-shrink-0 border-r border-slate-200/70 flex flex-col bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,247,251,0.95))] shadow-[8px_0_20px_rgba(15,23,42,0.03)]"
      >
        <div class="border-b border-slate-200/75 px-5 py-4 flex-shrink-0">
          <div class="flex items-center gap-3">
            <div
              class="flex h-10 w-10 items-center justify-center rounded-[16px] border border-blue-100 bg-blue-50/90 shadow-[0_8px_16px_rgba(37,99,235,0.08)]"
            >
              <MedicineBoxOutlined class="text-blue-600 text-lg" />
            </div>
            <div>
              <div class="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">
                Rules Console
              </div>
              <span class="font-black text-slate-900 text-[16px] tracking-tight">病案工作台</span>
            </div>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto py-2.5 custom-scrollbar">
          <div
            v-for="dept in departments"
            :key="dept.name"
            :class="[
              'mx-2 mb-1 flex items-center justify-between px-3.5 py-3 rounded-xl cursor-pointer text-sm transition-all duration-200',
              'text-slate-600 hover:bg-white hover:shadow-sm dark:text-slate-400 dark:hover:bg-slate-800',
            ]"
            @click="
              () => {
                viewMode = 'list'
                selectDept(dept.name)
              }
            "
          >
            <span class="truncate">{{ dept.name }}</span>
            <div class="flex items-center gap-1.5">
              <span
                v-if="dept.warningCount > 0"
                class="min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-blue-500 text-white text-[10px] font-bold px-1"
              >{{ dept.warningCount }}</span>
              <span
                class="min-w-[20px] h-[20px] flex items-center justify-center rounded-full text-[10px] font-bold px-1.5 bg-slate-200/80 text-slate-500 dark:bg-slate-700 dark:text-slate-400"
              >{{ dept.total }}</span>
            </div>
          </div>
        </div>
        <div class="flex-shrink-0 border-t border-slate-200/70 px-2.5 py-2.5">
          <div
            class="flex items-center gap-2.5 rounded-[16px] border border-blue-200 bg-[linear-gradient(180deg,rgba(239,246,255,0.96),rgba(219,234,254,0.9))] px-3.5 py-3 text-sm font-bold text-blue-700 shadow-[0_10px_22px_rgba(37,99,235,0.08)]"
          >
            <SafetyCertificateOutlined class="text-base" />
            <div>
              <div>质控规则</div>
              <div class="text-[11px] font-medium text-blue-600/80">
                统一规则总览
              </div>
            </div>
          </div>
        </div>
      </aside>
      <main
        class="flex-1 flex flex-col min-w-0 bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(241,245,249,0.98))] overflow-y-auto"
      >
        <header
          class="flex-shrink-0 border-b border-slate-200/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(247,250,252,0.96))] px-6 py-4"
        >
          <div class="flex items-start justify-between gap-4">
            <div class="min-w-0">
              <h2 class="text-[28px] font-black leading-none tracking-[-0.02em] text-slate-900">
                {{ rulesSubTabTitle }}
              </h2>
            </div>
            <div class="flex flex-col items-end gap-3">
              <button
                class="flex items-center gap-1.5 rounded-[14px] border border-slate-200 bg-white px-3.5 py-2 text-sm font-semibold text-slate-500 transition-all hover:border-blue-200 hover:text-blue-700 hover:shadow-[0_8px_18px_rgba(37,99,235,0.08)]"
                @click="viewMode = 'list'"
              >
                <LeftOutlined />
                返回病历列表
              </button>
            </div>
          </div>
        </header>
        <div class="flex-1 p-6">
          <CodingRulesTab v-if="rulesSubTab === 'coding'" />
          <FrontpageRulesOverview v-else-if="rulesSubTab === 'frontpage'" />
          <SettlementRulesOverview v-else-if="rulesSubTab === 'settlement'" />
        </div>
      </main>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { apiClient } from '@/services/apiService'
import { message, Modal } from 'ant-design-vue'
import {
  MedicineBoxOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  InboxOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  LeftOutlined,
  RightOutlined,
  UserOutlined,
  SearchOutlined,
  FileSearchOutlined,
  EyeOutlined,
  CheckOutlined,
  NotificationOutlined,
  ScanOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons-vue'
import FrontPagePanel from '@/views/workstation/FrontPagePanel.vue'
import EMRViewer from '@/components/qc/EMRViewer.vue'
import WorkstationAssistPanel from './components/WorkstationAssistPanel.vue'
import QCResultTab from './components/QCResultTab.vue'
import ContentQCTab from './components/ContentQCTab.vue'
import ICDSearchPanel from './components/ICDSearchPanel.vue'
import SettlementSheet from './components/SettlementSheet.vue'
import FrontpageWorkspacePanel from './components/FrontpageWorkspacePanel.vue'
import AIProfileDashboard from '@/views/demo/frontpage/components/AIProfileDashboard.vue'
import DRGGroupingTab from '@/views/demo/frontpage/components/DRGGroupingTab.vue'
import CodingRulesTab from '@/components/rules/CodingRulesTab.vue'
import FrontpageRulesOverview from './components/FrontpageRulesOverview.vue'
import SettlementRulesOverview from './components/SettlementRulesOverview.vue'
import DetailHeader from './components/DetailHeader.vue'
import DetailSidebar from './components/DetailSidebar.vue'
import PriorityLane from './components/workbench/PriorityLane.vue'
import BatchTablePanel from './components/workbench/BatchTablePanel.vue'
import { useDRGGrouping } from '@/views/demo/frontpage/composables/useDRGGrouping'
import type { ICDCodeDetail } from './components/ICDDetailPanel.vue'
import { useWorkstationSession } from './composables/useWorkstationSession'
import { useFrontpageDraft } from './composables/useFrontpageDraft'
import { useQcPipeline } from './composables/useQcPipeline'
import { usePatientRecords } from './composables/usePatientRecords'
import { useNotifications } from './composables/useNotifications'
import type { PatientRecord, DocItem, FrontpageFocusTarget, QCIssueLike } from './types'
import type { PriorityCard, PriorityGroup } from './components/workbench/PriorityLane.vue'
import type { WorkbenchRow } from './components/workbench/BatchTablePanel.vue'
import type {
  WorkstationLaunchAction,
  WorkstationLaunchContext,
  WorkflowStageKey,
} from '@/types/workflow'

const {
  viewMode,
  selectedId,
  frontpageTab,
  assistPanelVisible,
  assistTab,
  icdDrawerVisible,
  icdApplyTarget,
  icdApplyIndex,
  isOtherTarget,
  openRecord: openSessionRecord,
  goBackToList: backToList,
  resetPerRecordTransient,
} = useWorkstationSession()

const route = useRoute()
const router = useRouter()

const {
  allRecords,
  departments,
  currentPage,
  serverTotal,
  serverTotalPages,
  loading,
  activeDept,
  searchText,
  hospFilter,
  hospOptions,
  filteredRecords,
  fetchData,
  handlePageChange,
  refreshData,
  selectDept,
} = usePatientRecords()
const PINNED_DEPARTMENT_SLOTS = 8
const visibleDepartments = computed(() => {
  const all = departments.value
  if (all.length <= PINNED_DEPARTMENT_SLOTS) return all

  const visibleLimit = PINNED_DEPARTMENT_SLOTS - 1
  const head = all.slice(0, visibleLimit)
  const active = all.find((dept) => dept.name === activeDept.value)
  if (!active) return head
  if (head.some((dept) => dept.name === active.name)) return head

  return [head[0], ...head.slice(1, visibleLimit - 1), active]
})

const overflowDepartments = computed(() => {
  const visibleNames = new Set(visibleDepartments.value.map((dept) => dept.name))
  return departments.value.filter((dept) => !visibleNames.has(dept.name))
})

const stageQueues = computed(() => {
  const records = filteredRecords.value
  const generateQueue = records.filter((record) => hasAdmissionRecord(record))
  const frontpageQcQueue = records.filter((record) => hasFrontpageOfficialRecord(record))
  const settlementQcQueue = records.filter((record) => hasSettlementOfficialRecord(record))

  return {
    frontpage_generate: generateQueue,
    frontpage_qc: frontpageQcQueue,
    settlement_qc: settlementQcQueue,
  }
})

const currentStageFilter = computed<WorkflowStageKey | ''>(() => {
  const stage = String(route.query.stage || '').trim()
  return validStages.includes(stage as WorkflowStageKey) ? (stage as WorkflowStageKey) : ''
})

const isStageQueueMode = computed(() => Boolean(currentStageFilter.value))

const stageMeta = computed(() => {
  if (currentStageFilter.value === 'frontpage_generate') {
    return {
      pageTitle: '参考首页生成队列',
      pageDesc: '面向医生与病案科的参考草稿，不写入正式首页数据表。',
      tableTitle: '待生成首页（参考草稿）',
      tableDesc: '口径：有住院记录即可进入；与正式首页数据表无关。',
      batchActionText: '批量生成参考首页',
      singleActionText: '生成草稿',
      action: 'generate_frontpage' as WorkstationLaunchAction,
    }
  }
  if (currentStageFilter.value === 'frontpage_qc') {
    return {
      pageTitle: '正式首页质控队列',
      pageDesc: '仅针对正式首页数据表执行质控，与草稿生成结果解耦。',
      tableTitle: '待首页质控（正式数据）',
      tableDesc: '口径：正式首页数据表存在即可进入。',
      batchActionText: '批量首页质控',
      singleActionText: '执行首页质控',
      action: 'qc_frontpage' as WorkstationLaunchAction,
    }
  }
  if (currentStageFilter.value === 'settlement_qc') {
    return {
      pageTitle: '正式结算清单质控队列',
      pageDesc: '仅针对正式结算清单数据执行质控，与首页草稿无关。',
      tableTitle: '待结算清单质控（正式数据）',
      tableDesc: '口径：正式结算清单数据表存在即可进入。',
      batchActionText: '批量结算质控',
      singleActionText: '执行结算质控',
      action: 'qc_settlement' as WorkstationLaunchAction,
    }
  }
  return {
    pageTitle: '病案工作台',
    pageDesc: '先筛高优先病历，再进入单案详情。',
    tableTitle: '批量扫读',
    tableDesc: '按当前筛选条件展示病历列表。',
    batchActionText: '批量处理',
    singleActionText: '查看详情',
    action: 'open_record' as WorkstationLaunchAction,
  }
})

const stageStatusText = computed(() => {
  if (currentStageFilter.value === 'frontpage_generate') return '待生成'
  if (currentStageFilter.value === 'frontpage_qc') return '待首页质控'
  if (currentStageFilter.value === 'settlement_qc') return '待结算质控'
  return '待处理'
})

const stageStatusClass = computed(() => {
  if (currentStageFilter.value === 'frontpage_generate') {
    return 'border-sky-200 bg-sky-50 text-sky-700'
  }
  if (currentStageFilter.value === 'frontpage_qc') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700'
  }
  if (currentStageFilter.value === 'settlement_qc') {
    return 'border-amber-200 bg-amber-50 text-amber-700'
  }
  return 'border-slate-200 bg-slate-50 text-slate-600'
})

const stageEmptyText = computed(() => {
  if (currentStageFilter.value === 'frontpage_generate') return '当前筛选条件下暂无待生成首页病历'
  if (currentStageFilter.value === 'frontpage_qc') return '当前筛选条件下暂无待首页质控病历'
  if (currentStageFilter.value === 'settlement_qc') return '当前筛选条件下暂无待结算清单质控病历'
  return '当前筛选条件下暂无病历数据'
})

const DEMO_HOME_RECORD_ORDER = ['V-ZS-001', 'V-LM-001']
const DEMO_HOME_RECORD_ORDER_MAP = new Map(DEMO_HOME_RECORD_ORDER.map((id, index) => [id, index]))
const DEMO_HOME_RECORD_ID_SET = new Set(DEMO_HOME_RECORD_ORDER)
const DEMO_HOME_NAME_MAP: Record<string, string> = {
  'V-ZS-001': '张三',
  'V-LM-001': '李明',
}

const listRecords = computed(() => {
  const sourceRecords = currentStageFilter.value
    ? stageQueues.value[currentStageFilter.value] || []
    : filteredRecords.value
  const demoIdsInView = new Set(
    sourceRecords
      .filter((record) => record.isDemoRecord && DEMO_HOME_RECORD_ID_SET.has(record.id))
      .map((record) => record.id),
  )
  if (!demoIdsInView.size) return sourceRecords
  return sourceRecords.filter((record) => {
    if (!demoIdsInView.has(record.id)) return true
    return record.isDemoRecord === true
  })
})

function isDemoRecord(record: PatientRecord): boolean {
  return record.isDemoRecord === true
}

function displayRecordName(record: PatientRecord): string {
  const rawName = String(record.name || '').trim()
  if (isDemoRecord(record)) {
    const normalized = rawName.replace(/\s+/g, '')
    if (normalized.length >= 2 && normalized.length <= 3) return normalized
    return DEMO_HOME_NAME_MAP[record.id] || normalized || '演示患者'
  }
  return rawName || '未知患者'
}

function hasAdmissionRecord(record: PatientRecord): boolean {
  return (
    Boolean(record.hasAdmission) ||
    Boolean(record.admissionDate && record.admissionDate.trim() !== '') ||
    Boolean(record.visitId || record.id)
  )
}

function hasFrontpageOfficialRecord(record: PatientRecord): boolean {
  if (typeof record.hasFrontpageOfficial === 'boolean') return record.hasFrontpageOfficial
  if (typeof record.cdmFrontpageEmpty === 'boolean') return !record.cdmFrontpageEmpty
  return false
}

function hasSettlementOfficialRecord(record: PatientRecord): boolean {
  if (typeof record.hasSettlementOfficial === 'boolean') return record.hasSettlementOfficial
  return false
}

async function handleStageRecordAction(record: PatientRecord) {
  const action = stageMeta.value.action
  if (action === 'open_record') {
    openRecord(record)
    return
  }
  const ctx: WorkstationLaunchContext = {
    record_id: record.id,
    action,
    source: 'dashboard',
    from_stage: currentStageFilter.value || undefined,
  }
  await executeLaunchAction(ctx, record)
}

const activePriorityGroup = ref('all')
const selectedWorkbenchKeys = ref<string[]>([])

function priorityScore(record: PatientRecord) {
  let score = 0
  const days = record.days || 0
  const isDischarged = Boolean(record.dischargeDate && record.dischargeDate.trim() !== '')
  const cdmFrontpageEmpty = Boolean(record.cdmFrontpageEmpty)

  // 最高优先：已出院但 CDM 病案首页仍为空（影响上报与医保提交流转）
  if (isDischarged && cdmFrontpageEmpty) score += 200
  // 次优先：已出院但住院天数较长
  if (isDischarged) score += 50

  score += Math.min(days * 2, 40)
  return score
}

function riskTypeOf(record: PatientRecord): string {
  if (isDemoRecord(record)) return 'demo'
  const isDischarged = Boolean(record.dischargeDate && record.dischargeDate.trim() !== '')
  if (isDischarged && Boolean(record.cdmFrontpageEmpty)) return 'incomplete'
  if (isDischarged && (record.days || 0) >= 8) return 'timeout'
  if (record.status === 'warning' || record.status === 'has_defects') return 'ai_failed'
  return 'normal'
}

function priorityReason(record: PatientRecord) {
  void record
  return ''
}

const priorityCards = computed<PriorityCard[]>(() => {
  const pinnedDemoRecords = [...listRecords.value]
    .filter((record) => isDemoRecord(record) && DEMO_HOME_RECORD_ID_SET.has(record.id))
    .sort(
      (a, b) =>
        (DEMO_HOME_RECORD_ORDER_MAP.get(a.id) ?? 99) - (DEMO_HOME_RECORD_ORDER_MAP.get(b.id) ?? 99),
    )
  const pinnedSet = new Set(pinnedDemoRecords.map((record) => record.id))
  const rankedNormalRecords = [...listRecords.value]
    .filter((record) => !pinnedSet.has(record.id))
    .sort((a, b) => priorityScore(b) - priorityScore(a))
  return [...pinnedDemoRecords, ...rankedNormalRecords].map((record) => ({
    id: record.id,
    patientName: displayRecordName(record),
    visitId: record.id,
    department: record.department || '未分科室',
    hospitalDays: Number(record.days || 0),
    riskType: riskTypeOf(record),
    riskText: priorityReason(record),
    isDemo: isDemoRecord(record),
    updatedAt: record.dischargeDate || record.admissionDate || '',
  }))
})

const priorityGroups = computed<PriorityGroup[]>(() => {
  const counters = {
    all: priorityCards.value.length,
    timeout: 0,
    incomplete: 0,
    ai_failed: 0,
    demo: 0,
  }
  priorityCards.value.forEach((card) => {
    if (card.riskType in counters) {
      counters[card.riskType as keyof typeof counters] += 1
    }
  })
  return [
    { key: 'all', label: '全部', count: counters.all },
    { key: 'timeout', label: '超时风险', count: counters.timeout },
    { key: 'incomplete', label: '资料不全', count: counters.incomplete },
    { key: 'ai_failed', label: 'AI抽取失败', count: counters.ai_failed },
    { key: 'demo', label: 'Demo演示', count: counters.demo },
  ]
})

const priorityCardsFiltered = computed(() => {
  if (activePriorityGroup.value === 'all') return priorityCards.value.slice(0, 8)
  return priorityCards.value
    .filter((card) => card.riskType === activePriorityGroup.value)
    .slice(0, 8)
})

const totalVisibleCount = computed(() => serverTotal.value || listRecords.value.length)
const activeHospLabel = computed(
  () => hospOptions.find((option) => option.value === hospFilter.value)?.label || '全部',
)
const scopeStatusText = computed(() => {
  const parts = [activeDept.value]
  if (activeHospLabel.value !== '全部') {
    parts.push(activeHospLabel.value)
  }
  if (currentStageFilter.value) {
    parts.push(stageMeta.value.tableTitle)
  }
  return parts.join(' / ')
})

const workbenchRows = computed<WorkbenchRow[]>(() =>
  listRecords.value.map((record) => ({
    id: record.id,
    patientName: displayRecordName(record),
    visitId: record.id,
    department: record.department || '未分科室',
    stageStatus: stageStatusText.value,
    riskReason: priorityReason(record),
    updatedAt: record.dischargeDate || record.admissionDate || '-',
    isDemo: isDemoRecord(record),
  })),
)

const tableSummaryText = computed(() => {
  return `当前筛选：${activeDept.value} / ${activeHospLabel.value} / ${stageMeta.value.tableTitle}`
})

// ========== 质控规则 Tab ==========
const rulesSubTab = ref<'coding' | 'frontpage' | 'settlement'>('coding')
const rulesSubTabTitle = computed(() => {
  const map: Record<string, string> = {
    coding: '编码质控规则管理',
    frontpage: '首页质控规则管理',
    settlement: '结算清单质控规则管理',
  }
  return map[rulesSubTab.value] || '质控规则管理'
})

const rulesSubTabSubtitle = computed(() => {
  const map: Record<string, string> = {
    coding: '按编码规范维护规则，聚焦主诊断、手术操作与编码逻辑一致性。',
    frontpage: '按病案首页字段维护规则，聚焦完整性、口径一致性与填写规范。',
    settlement: '按结算清单数据维护规则，聚焦费用字段、必填项与清单逻辑校验。',
  }
  return map[rulesSubTab.value] || ''
})

const rulesSubTabDescription = computed(() => {
  const map: Record<string, string> = {
    coding: '基于 ICD 编码规范的质控规则，覆盖诊断与手术编码的完整性、格式与逻辑校验。',
    frontpage: '基于病案首页数据的质控规则，校验首页字段的完整性、一致性和填写规范。',
    settlement: '针对医保结算清单数据的质控规则，覆盖必填项校验及清单逻辑一致性检查。',
  }
  return map[rulesSubTab.value] || ''
})

// ========== ?? Tab ???? ==========
const contentQCCount = ref(0)

// ========== 质控 Tab 独立刷新 ==========
const qcResultTabRef = ref<InstanceType<typeof QCResultTab> | null>(null)

function handleAssistTabRefresh(tabKey: string) {
  if (tabKey === 'form' || tabKey === 'cost') {
    qcResultTabRef.value?.runFormQC()
  } else if (tabKey === 'coding') {
    qcResultTabRef.value?.runCodingQC()
  } else if (tabKey === 'drg') {
    performDRGGrouping()
  } else if (tabKey === 'content') {
    message.info('内涵质控将在后续版本支持独立刷新')
  }
}

const icdTargetOptions = [
  { label: '主诊断编码', value: 'mainDiagnosis' },
  { label: '其他诊断编码', value: 'otherDiagnosis' },
  { label: '主手术编码', value: 'mainProcedure' },
  { label: '其他手术编码', value: 'otherProcedure' },
]

const {
  drgLoading,
  drgResult,
  suggestionDrawerVisible,
  suggestionsLoading,
  suggestions,
  performDRGGrouping: doDRGGrouping,
  openOptimizationDrawer,
  handleSuggestion,
  getSuggestionTitle,
} = useDRGGrouping()

// ========== 消息通知（来自 composable） ==========
const {
  assistNotifications,
  notificationUnreadCount,
  notificationLoading,
  notificationReadFilter,
  overviewLoading,
  overviewViewMode,
  overviewTypeFilter,
  overviewSeverityFilter,
  overviewDepartmentFilter,
  filteredNotificationOverviewItems,
  overviewDepartments,
  overviewTypes,
  overviewSeverities,
  filteredAssistNotifications,
  fetchAssistNotifications,
  markAssistNotificationRead,
  markAllAssistNotificationsRead,
  handleAssistNotificationClick,
  handleAssistOverviewClick,
  formatRelativeTime,
} = useNotifications(allRecords, openSessionRecord, assistPanelVisible, assistTab, frontpageTab)

// ========== 病历文书预览 ==========
const documentsList = ref<DocItem[]>([])
const documentsLoading = ref(false)
const docDrawerVisible = ref(false)
const docDrawerTitle = ref('')
const docDrawerContent = ref('')
const activeDocType = ref<string>('')

// ========== 详情主 Tab ==========
const detailMainTab = ref('records') // records | frontpage | settlement
const emrViewerRef = ref<InstanceType<typeof EMRViewer> | null>(null)
const emrRenderState = ref<'idle' | 'loading' | 'ready' | 'fallback'>('idle')

// ========== 病历详情（拼接文书） ==========
const concatText = ref('')
const concatLoading = ref(false)
const concatSections = computed(() => {
  if (!concatText.value) return []
  const sections: { title: string; content: string }[] = []
  const pattern =
    /={40}\s*\r?\n(?:📋\s*)?([^\r\n]+)\r?\n={40}\s*\r?\n\r?\n([\s\S]*?)(?=(?:\r?\n){3}={40}|$)/g

  for (const match of concatText.value.matchAll(pattern)) {
    const [, rawTitle = '', rawContent = ''] = match
    sections.push({
      title: rawTitle.trim(),
      content: rawContent.trim(),
    })
  }

  if (!sections.length) {
    sections.push({
      title: '完整病历',
      content: concatText.value.trim(),
    })
  }

  return sections
})
const expandedConcatSectionIndexes = ref<Set<number>>(new Set())
const concatTotalChars = computed(() =>
  concatSections.value.reduce((sum, section) => sum + (section.content?.length || 0), 0),
)
const allConcatSectionsExpanded = computed(
  () =>
    concatSections.value.length > 0 &&
    concatSections.value.every((_, index) => expandedConcatSectionIndexes.value.has(index)),
)

function isConcatSectionExpanded(index: number) {
  return expandedConcatSectionIndexes.value.has(index)
}

function toggleConcatSection(index: number) {
  const next = new Set(expandedConcatSectionIndexes.value)
  if (next.has(index)) {
    next.delete(index)
  } else {
    next.add(index)
  }
  expandedConcatSectionIndexes.value = next
}

function toggleExpandAllSections() {
  if (allConcatSectionsExpanded.value) {
    expandedConcatSectionIndexes.value = new Set()
    return
  }
  expandedConcatSectionIndexes.value = new Set(concatSections.value.map((_, index) => index))
}

// ========== 结算清单 ==========
const settlementData = ref<any>(null)
const settlementLoading = ref(false)
const settlementQcReport = ref<any>(null)
const settlementQcLoading = ref(false)

// ========== 病案首页官方格式数据 ==========
const frontpageSheetData = ref<any>(null)
const frontpageSheetLoading = ref(false)

async function loadFrontpageSheet(patientId: string, visitId: string) {
  frontpageSheetLoading.value = true
  try {
    const { data } = await apiClient.get(
      `/api/medical-records/frontpage-sheet/${patientId}/${visitId}`,
    )
    frontpageSheetData.value = data ?? null
  } catch (e: any) {
    if (e?.response?.status !== 404) {
      console.error('加载病案首页数据失败:', e)
    }
    frontpageSheetData.value = null
  } finally {
    frontpageSheetLoading.value = false
  }
}
const settlementQcFailed = computed(() => settlementQcReport.value?.summary?.failed || 0)

// ========== 功能可用性判断（PRD 6） ==========
// AI 生成首页：仅要求已出院，已有首页数据时弹确认框覆盖
const isDischarged = computed(() => !!selectedRecord.value?.dischargeDate)
const hasExistingFrontpage = computed(() => !!frontpageSheetData.value)
const canGenerateFrontpage = computed(() => isDischarged.value)
const frontpageDisabledReason = computed(() => {
  if (!isDischarged.value) return '在院患者暂不支持生成首页'
  return ''
})
function handleGenerateFrontpage() {
  if (hasExistingFrontpage.value) {
    Modal.confirm({
      title: '该患者已有病案首页数据',
      content: '重新生成将覆盖已有的首页数据，是否继续？',
      okText: '重新生成',
      cancelText: '取消',
      onOk: () => {
        detailMainTab.value = 'frontpage'
        generateFrontpage()
      },
    })
  } else {
    detailMainTab.value = 'frontpage'
    generateFrontpage()
  }
}
// 结算清单生成：仅对已出院且无结算数据的病历可用
const hasExistingSettlement = computed(
  () => !!settlementData.value && settlementData.value?.data_source !== 'generated_from_frontpage',
)
const canGenerateSettlement = computed(() => isDischarged.value && !hasExistingSettlement.value)

const costColumns = [
  { title: '收费类别', dataIndex: 'type', width: 120 },
  { title: '等级', dataIndex: 'level', width: 80 },
  { title: '实收金额', dataIndex: 'charge', width: 100 },
  { title: '甲类', dataIndex: 'class_a_amount', width: 80 },
  { title: '乙类', dataIndex: 'class_b_amount', width: 80 },
  { title: '自费', dataIndex: 'own_pay_amount', width: 80 },
]

const settlementBasicFields = computed(() => {
  const d = settlementData.value
  if (!d) return []
  return [
    { label: '患者姓名', value: d.patient_name },
    { label: '性别', value: d.patient_sex },
    { label: '年龄', value: d.patient_age },
    { label: '医保类型', value: d.patient_insurance_type || d.insurance_type },
    { label: '病案号', value: d.mr_no },
    { label: '住院号', value: d.inpat_no },
  ]
})

const settlementHospFields = computed(() => {
  const d = settlementData.value
  if (!d) return []
  return [
    { label: '入院科室', value: d.admission_dept_name },
    { label: '出院科室', value: d.discharge_dept_name },
    { label: '入院时间', value: d.admission_datetime },
    { label: '出院时间', value: d.discharge_datetime },
    { label: '入院途径', value: d.admission_route },
    { label: '离院方式', value: d.leaving_hospital_way },
  ]
})

const settlementInsurFields = computed(() => {
  const d = settlementData.value
  if (!d) return []
  return [
    { label: '参保地', value: d.insured_place },
    { label: '个人自付', value: d.out_of_pocket_advance },
    { label: '个人自费', value: d.out_of_pocket_amount },
    { label: '个人现金支付', value: d.cash_payment_amount },
    { label: '医保支付方式', value: d.insurance_type },
    { label: '结算状态', value: d.settlement_status },
  ]
})

async function loadConcatText(visitId: string) {
  concatLoading.value = true
  concatText.value = ''
  try {
    const { data } = await apiClient.get(`/api/medical-records/documents/${visitId}`, {
      params: { mode: 'concat' },
    })
    concatText.value = data.text || ''
  } catch (err) {
    console.error('加载病历详情失败:', err)
  } finally {
    concatLoading.value = false
  }
}

async function loadSettlement(patientId: string, visitId: string) {
  settlementLoading.value = true
  settlementData.value = null
  settlementQcReport.value = null
  try {
    const { data } = await apiClient.get(`/api/medical-records/settlement/${patientId}/${visitId}`)
    settlementData.value = data
  } catch (err: any) {
    if (err?.response?.status === 404) {
      // Fallback: 从首页抽取结果与 CDM SQL 生成草稿
      try {
        const { data: draft } = await apiClient.post(
          `/api/medical-records/settlement/${patientId}/${visitId}/generate`,
        )
        settlementData.value = draft
      } catch (genErr: any) {
        if (genErr?.response?.status !== 404) {
          console.warn('草稿生成也失败，显示空白样表:', genErr)
        }
      }
    } else {
      console.error('加载结算清单失败:', err)
    }
  } finally {
    settlementLoading.value = false
  }
}

async function runSettlementQc() {
  if (!selectedRecord.value) return
  settlementQcLoading.value = true
  try {
    // 根据数据来源选择对应的 QC 端点
    const isGenerated = settlementData.value?.data_source === 'generated_from_frontpage'
    const qcUrl = isGenerated
      ? `/api/medical-records/settlement/${selectedRecord.value.patientId}/${selectedRecord.value.visitId}/generate/qc`
      : `/api/medical-records/settlement/${selectedRecord.value.patientId}/${selectedRecord.value.visitId}/qc`
    const { data } = await apiClient.post(qcUrl)
    settlementQcReport.value = data
    message.success(`质控完成: ${data.summary.passed}/${data.summary.total} 通过`)
  } catch (err) {
    message.error('结算清单质控执行失败')
    console.error(err)
  } finally {
    settlementQcLoading.value = false
  }
}

// ========== AI画像 & DRG Modal ==========
const aiProfileModalVisible = ref(false)
const profileAnalyzed = ref(false)
const profileAnalyzing = ref(false)
const drgDetailModalVisible = ref(false)

async function loadDocuments(visitId: string) {
  documentsLoading.value = true
  documentsList.value = []
  try {
    const { data } = await apiClient.get(`/api/medical-records/documents/${visitId}`)
    // 只显示有内容的与前 3 个核心文书类型（即使无内容也展示）
    const coreTypes = ['admission_record', 'discharge_record', 'surgery_record']
    const docs: DocItem[] = data.documents || []
    documentsList.value = docs.filter((d: DocItem) => d.has_content || coreTypes.includes(d.type))
  } catch (err) {
    console.error('加载病历文书失败:', err)
  } finally {
    documentsLoading.value = false
  }
}

function openDocPreview(doc: DocItem) {
  activeDocType.value = doc.type || ''
  docDrawerTitle.value = doc.label
  docDrawerContent.value = doc.content || '暂无内容'
  docDrawerVisible.value = true
}

const combinedMedicalText = computed(() =>
  documentsList.value
    .filter((doc) => doc.has_content && doc.content)
    .map((doc) => `${doc.label}\n${doc.content}`)
    .join('\n\n'),
)

const selectedRecord = computed(() => allRecords.value.find((r) => r.id === selectedId.value))

const {
  assistIssues,
  assistBadgeCount: qcIssueCount,
  qcRefreshSeed,
  handleAssistIssuesChange,
  touchCodingRefresh,
  findEvidenceDoc,
  findEvidenceSnippet,
} = useQcPipeline()

const {
  frontpageGenerating,
  frontpagePostProcessing,
  frontpageDraft,
  frontpageModule,
  frontpageFocusTarget,
  frontpageFields,
  defaultPreviewTab,
  completedModules,
  setDraftEmpty,
  ensureExtractionSettingsLoaded,
  generateFrontpage,
  handleExportFrontpage,
  handleSaveFrontpage,
  focusFrontpageSection,
  handleApplyICDCode: applyICDCodeToDraft,
  applyFrontPanelEdits,
} = useFrontpageDraft(selectedId, selectedRecord, combinedMedicalText, touchCodingRefresh)

// ========== AI 生成进度辅助 ==========
import { MODULE_LABELS, type CompletedModule } from './composables/useFrontpageDraft'

const ALL_MODULE_KEYS = [
  'basic_info',
  'hospitalization',
  'diagnoses',
  'procedures',
  'other_medical_info',
  'staff',
  'costs',
  'confidence',
]
const MODULE_LABELS_MAP = MODULE_LABELS

const frontpageModuleCards = computed(() =>
  ALL_MODULE_KEYS.map((key) => ({
    key,
    label: MODULE_LABELS_MAP[key] || key,
    status: getModuleStatus(key),
    entry: getModuleEntry(key),
  })),
)

function getModuleEntry(m: string): CompletedModule | undefined {
  return completedModules.value.find((c) => c.name === m)
}

function getModuleStatus(m: string): 'done' | 'active' | 'pending' {
  if (getModuleEntry(m)) return 'done'
  if (frontpageModule.value === m) return 'active'
  return 'pending'
}

// 生成完成后延迟 5 秒自动切到“首页预览/打印” tab，让用户有时间查看提取结果
let autoJumpTimer: ReturnType<typeof setTimeout> | null = null

watch(frontpageGenerating, (generating, wasGenerating) => {
  if (wasGenerating && !generating && frontpageDraft.value) {
    if (autoJumpTimer) clearTimeout(autoJumpTimer)
    autoJumpTimer = setTimeout(() => {
      // 只有当前还在提取结果页时才自动跳转，避免覆盖用户的手动切换行为
      if (frontpageTab.value === 'fields') {
        frontpageTab.value = defaultPreviewTab.value
      }
    }, 5000)
  }
})

const launchHandling = ref(false)
const handledLaunchKey = ref('')
const validLaunchActions: WorkstationLaunchAction[] = [
  'open_record',
  'generate_frontpage',
  'qc_frontpage',
  'qc_settlement',
]
const validStages: WorkflowStageKey[] = ['frontpage_generate', 'frontpage_qc', 'settlement_qc']

onMounted(() => {
  void ensureExtractionSettingsLoaded()
  fetchData()
  fetchAssistNotifications()
})

// 切换病历时清除上次生成结果，并加载文书列表与结算清单
watch(selectedId, (newId) => {
  setDraftEmpty()
  resetPerRecordTransient()
  assistIssues.value = []
  suggestionDrawerVisible.value = false
  docDrawerVisible.value = false
  activeDocType.value = ''
  expandedConcatSectionIndexes.value = new Set()
  settlementQcReport.value = null
  detailMainTab.value = 'records'
  emrRenderState.value = newId ? 'loading' : 'idle'
  if (newId) {
    loadDocuments(newId)
    loadConcatText(newId)
    // 加载结算清单（需要 patientId）
    const record = allRecords.value.find((r) => r.id === newId)
    if (record?.patientId) {
      loadSettlement(record.patientId, newId)
      loadFrontpageSheet(record.patientId, newId)
    }
  } else {
    documentsList.value = []
    concatText.value = ''
    settlementData.value = null
    frontpageSheetData.value = null
  }
})

watch(concatSections, (sections) => {
  if (!sections.length) {
    expandedConcatSectionIndexes.value = new Set()
    return
  }
  if (!expandedConcatSectionIndexes.value.size) {
    expandedConcatSectionIndexes.value = new Set([0])
  }
})

watch(
  [
    () => route.query.record_id,
    () => route.query.action,
    () => route.query.source,
    () => allRecords.value.length,
  ],
  () => {
    void handleWorkstationLaunch()
  },
  { immediate: true },
)

watch(
  () => route.query.stage,
  (stageRaw) => {
    const stage = String(stageRaw || '').trim()
    const stageKeys = ['frontpage_generate', 'frontpage_qc', 'settlement_qc']
    if (!stageKeys.includes(stage)) return
    activeDept.value = '全部科室'
    searchText.value = ''
    hospFilter.value = 'all'
    if (viewMode.value !== 'list') {
      backToList()
      assistPanelVisible.value = false
      icdDrawerVisible.value = false
      suggestionDrawerVisible.value = false
    }
  },
  { immediate: true },
)

// ========== 计算 ==========

const detailItems = computed(() => {
  const r = selectedRecord.value
  if (!r) return []
  return [
    { label: '科室', value: r.department },
    { label: '床号', value: r.bedNo ? `${r.bedNo}床` : '' },
    { label: '性别/年龄', value: `${r.sex} / ${r.age}岁` },
    { label: '医保类型', value: r.insurance },
    { label: '入院日期', value: r.admissionDate },
    { label: '住院天数', value: `${r.days}天` },
    { label: '主管医生', value: r.doctor },
    { label: '出院日期', value: r.dischargeDate },
    { label: '病案号', value: r.id },
  ]
})

const assistPatientInfo = computed(() => {
  const record = selectedRecord.value
  if (!record) return null
  return {
    name: record.name,
    sex: record.sex,
    age: `${record.age}岁`,
    diagnosis: record.diagnosis,
    visitId: record.id,
  }
})

const assistBadgeCount = computed(() => {
  if (qcIssueCount.value > 0) return qcIssueCount.value
  const record = selectedRecord.value
  if (!record) return 0
  return record.status === 'warning' ? 1 : 0
})

const icdApplyLabel = computed(() => {
  if (icdApplyTarget.value === 'mainDiagnosis') return '回填主诊断编码'
  if (icdApplyTarget.value === 'mainProcedure') return '回填主手术编码'
  if (icdApplyTarget.value === 'otherDiagnosis')
    return `回填其他诊断编码（第 ${icdApplyIndex.value} 条）`
  return `回填其他手术编码（第 ${icdApplyIndex.value} 条）`
})

function openRecord(record: PatientRecord) {
  openSessionRecord(record.id)
  assistPanelVisible.value = false
  icdDrawerVisible.value = false
  if (route.path === '/workstation-v4' && route.query.stage) {
    const nextQuery = { ...route.query } as Record<string, any>
    delete nextQuery.stage
    router.replace({ path: route.path, query: nextQuery })
  }
}

function findRecordById(recordId: string): PatientRecord | undefined {
  return listRecords.value.find((item) => item.id === recordId)
}

function handlePriorityOpen(recordId: string) {
  const record = findRecordById(recordId)
  if (!record) return
  handleStageRecordAction(record)
}

function handlePriorityDefer(recordId: string) {
  message.info(`已将 ${recordId} 标记为稍后处理`)
}

function handleRowOpen(recordId: string) {
  const record = findRecordById(recordId)
  if (!record) return
  handleStageRecordAction(record)
}

function handleBatchExtract(keys: string[]) {
  if (!keys.length) return
  message.info(`已加入批量抽取队列：${keys.length} 条`)
}

function handleBatchDefer(keys: string[]) {
  if (!keys.length) return
  message.info(`已批量标记稍后：${keys.length} 条`)
}

function handleBatchAssign(keys: string[]) {
  if (!keys.length) return
  message.info(`批量分派功能准备中，已选择 ${keys.length} 条`)
}

function handleClearFilters() {
  activeDept.value = '全部科室'
  searchText.value = ''
  hospFilter.value = 'all'
  selectedWorkbenchKeys.value = []
}

function goToFinalRecords() {
  router.push('/workstation-v4/records/final')
}

function goToSichuanRules() {
  router.push('/workstation-v4/rules?tab=semantic')
}

// 快捷翻页
const currentRecordIndex = computed(() => {
  if (!selectedRecord.value) return -1
  return filteredRecords.value.findIndex((r) => r.id === selectedRecord.value!.id)
})

function goToPrevRecord() {
  const idx = currentRecordIndex.value
  if (idx > 0) {
    openRecord(filteredRecords.value[idx - 1])
  }
}

function goToNextRecord() {
  const idx = currentRecordIndex.value
  if (idx < filteredRecords.value.length - 1) {
    openRecord(filteredRecords.value[idx + 1])
  }
}

function goBackToList() {
  backToList()
  assistPanelVisible.value = false
  icdDrawerVisible.value = false
  suggestionDrawerVisible.value = false
  // 不清空 selectedId，方便返回后仍能看到高亮
}

function parseLaunchContext(): WorkstationLaunchContext | null {
  const source = String(route.query.source || '').trim()
  const recordId = String(route.query.record_id || '').trim()
  const actionRaw = String(route.query.action || '').trim()
  if (!recordId || source !== 'dashboard') return null
  if (!validLaunchActions.includes(actionRaw as WorkstationLaunchAction)) return null
  const ctx: WorkstationLaunchContext = {
    record_id: recordId,
    action: actionRaw as WorkstationLaunchAction,
    source: 'dashboard',
  }
  const taskId = String(route.query.task_id || '').trim()
  if (taskId) ctx.task_id = taskId
  const stage = String(route.query.from_stage || '').trim()
  if (validStages.includes(stage as WorkflowStageKey)) {
    ctx.from_stage = stage as WorkflowStageKey
  }
  return ctx
}

function launchKeyOf(ctx: WorkstationLaunchContext): string {
  return [ctx.record_id, ctx.action, ctx.task_id || '', ctx.from_stage || ''].join('|')
}

function findRecordForLaunch(recordId: string): PatientRecord | null {
  const target = recordId.trim().toLowerCase()
  if (!target) return null
  const matched = allRecords.value.find((record: PatientRecord) => {
    const candidateIds = [
      String(record.id || '')
        .trim()
        .toLowerCase(),
      String(record.visitId || '')
        .trim()
        .toLowerCase(),
      String((record as any).record_id || '')
        .trim()
        .toLowerCase(),
      String((record as any).task_id || '')
        .trim()
        .toLowerCase(),
    ]
    return candidateIds.includes(target)
  })
  return matched || null
}

async function waitForSettlementReady(timeoutMs = 6000): Promise<void> {
  if (!settlementLoading.value) return
  const started = Date.now()
  while (settlementLoading.value && Date.now() - started < timeoutMs) {
    await new Promise((resolve) => window.setTimeout(resolve, 120))
  }
}

function clearLaunchQueryParams() {
  const nextQuery = { ...route.query } as Record<string, any>
  delete nextQuery.record_id
  delete nextQuery.task_id
  delete nextQuery.action
  delete nextQuery.source
  delete nextQuery.from_stage
  router.replace({ path: route.path, query: nextQuery })
}

async function executeLaunchAction(ctx: WorkstationLaunchContext, record: PatientRecord) {
  openRecord(record)
  await nextTick()

  if (ctx.action === 'open_record') {
    detailMainTab.value = 'records'
    return
  }

  if (ctx.action === 'generate_frontpage') {
    detailMainTab.value = 'frontpage'
    await nextTick()
    handleGenerateFrontpage()
    return
  }

  if (ctx.action === 'qc_frontpage') {
    detailMainTab.value = 'frontpage'
    assistPanelVisible.value = true
    assistTab.value = 'form'
    await nextTick()
    qcResultTabRef.value?.runFormQC()
    return
  }

  if (ctx.action === 'qc_settlement') {
    detailMainTab.value = 'settlement'
    await nextTick()
    if (!isDischarged.value) {
      message.warning('当前病历未出院，暂不可执行结算质控')
      return
    }
    await waitForSettlementReady()
    await runSettlementQc()
    assistPanelVisible.value = true
    assistTab.value = 'cost'
  }
}

async function handleWorkstationLaunch() {
  const ctx = parseLaunchContext()
  if (!ctx) {
    handledLaunchKey.value = ''
    return
  }
  if (!allRecords.value.length || launchHandling.value) return

  const key = launchKeyOf(ctx)
  if (handledLaunchKey.value === key) return

  const targetRecord = findRecordForLaunch(ctx.record_id)
  if (!targetRecord) {
    message.warning('未找到目标病历，已取消自动联动')
    handledLaunchKey.value = key
    clearLaunchQueryParams()
    return
  }

  launchHandling.value = true
  try {
    await executeLaunchAction(ctx, targetRecord)
    handledLaunchKey.value = key
    clearLaunchQueryParams()
  } finally {
    launchHandling.value = false
  }
}

function handleLocateFromQC(payload: {
  target: FrontpageFocusTarget
  issue: { description?: string }
}) {
  if (!frontpageDraft.value) {
    message.warning('请先生成首页后再定位字段')
    return
  }
  frontpageTab.value = 'fields'
  focusFrontpageSection(payload.target as FrontpageFocusTarget)
  if (payload?.issue?.description) {
    message.info(`已定位：${payload.issue.description}`)
  }
}

function handleApplyICDCode(detail: ICDCodeDetail) {
  const applied = applyICDCodeToDraft(
    detail,
    icdApplyTarget.value,
    Number(icdApplyIndex.value || 1),
  )
  if (!applied) return
  frontpageTab.value = 'fields'
  icdDrawerVisible.value = false
  touchCodingRefresh()
}

function handleFrontPanelDraftChange(payload: { diagnoses: any[]; procedures: any[] }) {
  applyFrontPanelEdits(payload)
  touchCodingRefresh()
}

function handleJumpEvidenceFromQC(issue: QCIssueLike) {
  const doc = findEvidenceDoc(issue, documentsList.value)
  if (!doc) {
    message.warning('暂无可跳转的文书依据')
    return
  }
  activeDocType.value = doc.type || ''
  docDrawerTitle.value = `依据文书：${doc.label}`
  docDrawerContent.value = findEvidenceSnippet(issue, doc.content) || doc.content || '暂无内容'
  docDrawerVisible.value = true
}

function handleEmrLoaded(payload: { content?: string }) {
  emrRenderState.value = payload?.content ? 'ready' : 'fallback'
}

function handleEmrError() {
  if (selectedId.value) {
    emrRenderState.value = 'fallback'
  }
}

function handleEmrDefectClick(defectId: string) {
  assistPanelVisible.value = true
  assistTab.value = 'form'
  const matched = assistIssues.value.find((issue) => issue?.id === defectId)
  if (matched?.description) {
    message.info(`已定位质控问题：${matched.description}`)
  }
}

function handleAssistTabChange(tab: unknown) {
  assistTab.value = tab as typeof assistTab.value
  if (tab === 'message') {
    fetchAssistNotifications()
  }
}

function performDRGGrouping() {
  if (!selectedId.value) {
    message.warning('请先选择病历')
    return
  }
  doDRGGrouping(selectedId.value)
}

function openOptimization() {
  if (!selectedId.value) {
    message.warning('请先选择病历')
    return
  }
  openOptimizationDrawer(selectedId.value)
}

function suggestionSeverityTag(severity?: string) {
  if (severity === 'high' || severity === 'error' || severity === 'critical') return 'error'
  if (severity === 'medium' || severity === 'warning') return 'warning'
  return 'processing'
}

function handleDRGSuggestion(action: 'accept' | 'reject', suggestionId: number) {
  if (!selectedId.value) {
    message.warning('请先选择病历')
    return
  }
  handleSuggestion(suggestionId, action, selectedId.value)
}
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(203, 213, 225, 0.4);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(148, 163, 184, 0.6);
}

.workstation-shell {
  --workstation-bg-page: #f4f6f8;
  --workstation-bg-card: #ffffff;
  --workstation-bg-surface: rgba(255, 255, 255, 0.76);
  --workstation-bg-surface-strong: rgba(255, 255, 255, 0.88);
  --workstation-bg-card-soft: rgba(248, 250, 252, 0.92);
  --workstation-bg-table-header: rgba(248, 250, 252, 0.92);
  --workstation-bg-table-row-hover: rgba(248, 250, 252, 0.88);
  --workstation-bg-table-row-selected: rgba(239, 246, 255, 0.92);
  --workstation-text-primary: #0f172a;
  --workstation-text-secondary: #5b6b84;
  --workstation-text-muted: #94a3b8;
  --workstation-border-soft: rgba(15, 23, 42, 0.06);
  --workstation-border-light: rgba(255, 255, 255, 0.92);
  --workstation-border-strong: rgba(15, 23, 42, 0.08);
  --workstation-divider: rgba(226, 232, 240, 0.88);
  --workstation-brand-500: #2f6fed;
  --workstation-brand-600: #1e5ae0;
  --workstation-brand-050: rgba(234, 242, 255, 0.98);
  --workstation-brand-100: rgba(239, 246, 255, 0.96);
  --workstation-brand-border: rgba(191, 219, 254, 0.96);
  --workstation-brand-shadow: rgba(191, 219, 254, 0.24);
  --workstation-state-warning-bg: #fff6e5;
  --workstation-state-warning-text: #b85a00;
  --workstation-state-danger-bg: #fdeded;
  --workstation-state-danger-text: #b94a48;
  --workstation-state-review-bg: #f3eeff;
  --workstation-state-review-text: #6e56cf;
  --workstation-state-demo-bg: #eaf5ff;
  --workstation-state-demo-text: #0f6cbd;
  --workstation-radius-panel: 28px;
  --workstation-radius-card: 24px;
  --workstation-radius-input: 20px;
  --workstation-radius-pill: 999px;
  --workstation-shadow-panel:
    inset 0 1px 0 rgba(255, 255, 255, 0.95), 0 22px 44px rgba(148, 163, 184, 0.12);
  --workstation-shadow-card:
    inset 0 1px 0 rgba(255, 255, 255, 0.98), 0 16px 32px rgba(148, 163, 184, 0.1);
  --workstation-shadow-card-hover:
    inset 0 1px 0 rgba(255, 255, 255, 0.98), 0 22px 40px rgba(148, 163, 184, 0.16);
  --workstation-shadow-input:
    inset 0 1px 0 rgba(255, 255, 255, 0.98), 0 14px 28px rgba(148, 163, 184, 0.12);
  --workstation-shadow-brand: 0 12px 22px rgba(47, 111, 237, 0.24);
  --workstation-shadow-brand-hover: 0 14px 28px rgba(47, 111, 237, 0.3);
}

.workstation-panel {
  position: relative;
  overflow: hidden;
  border-radius: 32px;
  border: 1px solid rgba(255, 255, 255, 0.85);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(246, 248, 251, 0.96));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.95),
    0 28px 60px rgba(148, 163, 184, 0.14);
}

.workstation-panel--filters {
  padding: 20px;
}

.workbench-hero {
  display: grid;
  gap: 0;
}

.workbench-controls-panel {
  display: grid;
  gap: 12px;
  border-radius: var(--workstation-radius-panel);
  border: 1px solid var(--workstation-border-light);
  background: var(--workstation-bg-surface);
  padding: 16px;
  box-shadow: var(--workstation-shadow-panel);
}

.workbench-controls-search-row {
  display: flex;
  align-items: center;
}

.workbench-controls__search-input {
  min-width: 0;
  width: min(50%, 520px);
}

.workbench-dept-row {
  display: block;
}

.workbench-dept-row__list {
  display: flex;
  align-items: center;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.workbench-dept-row__list::-webkit-scrollbar {
  display: none;
}

.workbench-dept-chip {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 8px;
  border-radius: var(--workstation-radius-pill);
  border: 1px solid transparent;
  padding: 6px 14px;
  font-size: 14px;
  font-weight: 600;
  transition: all 160ms ease;
}

.workbench-dept-chip__count {
  display: inline-flex;
  min-width: 18px;
  align-items: center;
  justify-content: center;
  border-radius: var(--workstation-radius-pill);
  padding: 1px 5px;
  font-size: 11px;
  font-weight: 700;
}

.workbench-dept-chip--active {
  border-color: var(--workstation-brand-border);
  background: var(--workstation-brand-100);
  color: var(--workstation-brand-600);
}

.workbench-dept-chip--active .workbench-dept-chip__count {
  background: rgba(47, 111, 237, 0.12);
  color: var(--workstation-brand-600);
}

.workbench-dept-chip--idle {
  border-color: var(--workstation-border-light);
  background: rgba(255, 255, 255, 0.82);
  color: var(--workstation-text-secondary);
}

.workbench-dept-chip--idle:hover {
  border-color: rgba(191, 219, 254, 0.95);
  background: rgba(255, 255, 255, 0.96);
  color: var(--workstation-text-primary);
}

.workbench-dept-chip--idle .workbench-dept-chip__count {
  background: rgba(241, 245, 249, 0.92);
  color: var(--workstation-text-secondary);
}

.workstation-empty-state {
  border-radius: var(--workstation-radius-card);
  border: 1px dashed var(--workstation-divider);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(248, 250, 252, 0.92));
  box-shadow: var(--workstation-shadow-card);
}

.workstation-empty-state__icon {
  color: rgba(148, 163, 184, 0.5);
}

.workstation-empty-state__text {
  color: var(--workstation-text-muted);
}

.workstation-pagination-shell {
  border-radius: var(--workstation-radius-card);
  border: 1px solid var(--workstation-border-light);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(247, 250, 252, 0.94));
  box-shadow: var(--workstation-shadow-card);
}

@media (max-width: 1279px) {
  .workbench-controls__search-input {
    width: min(64%, 520px);
  }
}

@media (max-width: 1023px) {
  .workbench-controls__search-input {
    width: 100%;
    max-width: none;
  }
}

.workstation-shell :deep(.ant-input-affix-wrapper),
.workstation-shell :deep(.ant-input-search .ant-input),
.workstation-shell :deep(.ant-select-selector) {
  border-radius: var(--workstation-radius-input) !important;
}

.workstation-shell :deep(.ant-input-affix-wrapper),
.workstation-shell :deep(.ant-select-selector) {
  min-height: 46px !important;
  border-color: var(--workstation-border-light) !important;
  background: var(--workstation-bg-surface-strong) !important;
  box-shadow: var(--workstation-shadow-input);
}

.workstation-shell :deep(.ant-input),
.workstation-shell :deep(.ant-input-affix-wrapper input),
.workstation-shell :deep(.ant-select-selection-item),
.workstation-shell :deep(.ant-select-selection-placeholder) {
  font-size: 14px !important;
  font-weight: 500;
}

.workstation-shell :deep(.ant-input-affix-wrapper:hover),
.workstation-shell :deep(.ant-select-focused .ant-select-selector),
.workstation-shell :deep(.ant-select-selector:hover) {
  border-color: var(--workstation-brand-border) !important;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.98),
    0 18px 32px var(--workstation-brand-shadow) !important;
}

.workstation-shell :deep(.ant-pagination) {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--workstation-text-secondary);
}

.workstation-shell :deep(.ant-pagination .ant-pagination-item),
.workstation-shell :deep(.ant-pagination .ant-pagination-prev),
.workstation-shell :deep(.ant-pagination .ant-pagination-next),
.workstation-shell :deep(.ant-pagination .ant-pagination-jump-prev),
.workstation-shell :deep(.ant-pagination .ant-pagination-jump-next) {
  border-radius: var(--workstation-radius-pill);
  border-color: transparent;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.95);
}

.workstation-shell :deep(.ant-pagination .ant-pagination-item a),
.workstation-shell :deep(.ant-pagination .ant-pagination-prev .ant-pagination-item-link),
.workstation-shell :deep(.ant-pagination .ant-pagination-next .ant-pagination-item-link) {
  color: var(--workstation-text-secondary);
}

.workstation-shell :deep(.ant-pagination .ant-pagination-item-active) {
  border-color: var(--workstation-brand-border);
  background: var(--workstation-brand-100);
  box-shadow: 0 12px 22px var(--workstation-brand-shadow);
}

.workstation-shell :deep(.ant-pagination .ant-pagination-item-active a) {
  color: var(--workstation-brand-600);
  font-weight: 700;
}

.workstation-shell :deep(.ant-pagination .ant-pagination-options-quick-jumper input) {
  border-radius: var(--workstation-radius-pill);
  border-color: var(--workstation-border-light);
  background: rgba(255, 255, 255, 0.82);
}

.workstation-surface-enter {
  animation: workstationSurfaceEnter 420ms ease-out both;
}

.workstation-surface-enter--delay-1 {
  animation-delay: 90ms;
}

@keyframes workstationSurfaceEnter {
  from {
    opacity: 0;
    transform: translateY(10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 详情主 Tab 样式 */
.detail-main-tabs .ant-tabs-content {
  flex: 1;
  overflow: hidden;
}
.detail-main-tabs .ant-tabs-tabpane {
  height: 100%;
  overflow-y: auto;
}

.medical-record-document__content-wrap {
  position: relative;
}

.medical-record-document__content-wrap--collapsed {
  max-height: 13.5rem;
  overflow: hidden;
}

.medical-record-document__content-wrap--collapsed::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 56px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.95));
}

.medical-record-document__content {
  letter-spacing: 0.01em;
}
</style>
