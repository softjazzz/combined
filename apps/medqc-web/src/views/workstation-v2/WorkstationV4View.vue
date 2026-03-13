<template>
  <div class="h-full flex bg-white dark:bg-slate-900 overflow-hidden">
    <!-- ====== 列表模式 ====== -->
    <template v-if="viewMode === 'list'">
      <!-- 左侧科室导航 -->
      <aside class="w-56 flex-shrink-0 border-r border-slate-100 dark:border-slate-800 flex flex-col bg-slate-50/70 dark:bg-slate-900">
        <div class="h-14 flex items-center gap-2.5 px-5 border-b border-slate-100 dark:border-slate-800 flex-shrink-0">
          <MedicineBoxOutlined class="text-blue-500 text-lg" />
          <span class="font-bold text-slate-800 dark:text-slate-100 text-base tracking-tight">病案工作台</span>
        </div>
        <div class="flex-1 overflow-y-auto py-2.5 custom-scrollbar">
          <div
            v-for="dept in departments"
            :key="dept.name"
            @click="selectDept(dept.name)"
            :class="[
              'mx-2 mb-1 flex items-center justify-between px-3.5 py-3 rounded-xl cursor-pointer text-sm transition-all duration-200',
              activeDept === dept.name
                ? 'bg-blue-100 text-blue-700 font-bold dark:bg-blue-500/20 dark:text-blue-300 shadow-sm ring-1 ring-blue-200 dark:ring-blue-500/20'
                : 'text-slate-600 hover:bg-white hover:shadow-sm dark:text-slate-400 dark:hover:bg-slate-800'
            ]"
          >
            <span class="truncate">{{ dept.name }}</span>
            <div class="flex items-center gap-1.5">
              <span
                v-if="dept.warningCount > 0"
                class="min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold px-1"
              >{{ dept.warningCount }}</span>
              <span
                :class="[
                  'min-w-[20px] h-[20px] flex items-center justify-center rounded-full text-[10px] font-bold px-1.5',
                  activeDept === dept.name
                    ? 'bg-blue-500 text-white'
                    : 'bg-slate-200/80 text-slate-500 dark:bg-slate-700 dark:text-slate-400'
                ]"
              >{{ dept.total }}</span>
            </div>
          </div>
        </div>

      </aside>

      <!-- 右侧主内容 -->
      <main class="flex-1 flex flex-col min-w-0 bg-slate-50/40 dark:bg-slate-900">
        <header class="h-14 flex items-center justify-between px-6 border-b border-slate-100 dark:border-slate-800 flex-shrink-0 bg-white dark:bg-slate-900">
          <div class="flex items-center gap-4">
            <h2 class="text-lg font-bold text-slate-800 dark:text-white">{{ activeDept }}</h2>
            <span class="text-xs text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full">
              {{ filteredRecords.length }} 例
            </span>
          </div>
          <div class="flex items-center gap-3">
            <a-input-search
              v-model:value="searchText"
              placeholder="搜索姓名/病案号"
              style="width: 200px"
              size="small"
              allow-clear
            />
            <a-select
              v-model:value="statusFilter"
              style="width: 110px"
              size="small"
              :options="statusOptions"
            />
            <a-button size="small" @click="refreshData" :loading="loading">
              <template #icon><SyncOutlined /></template>
            </a-button>
          </div>
        </header>

        <!-- 状态统计条 — 可点击的分段控制器风格 -->
        <div class="h-11 flex items-center gap-2 px-6 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900/80 flex-shrink-0">
          <div
            v-for="st in statusPills"
            :key="st.key"
            @click="statusFilter = st.key"
            :class="[
              'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium cursor-pointer transition-all duration-150',
              statusFilter === st.key ? st.activeClass : 'text-slate-500 hover:bg-slate-50 dark:text-slate-400 dark:hover:bg-slate-800'
            ]"
          >
            <span v-if="st.dotClass" :class="['w-1.5 h-1.5 rounded-full', st.dotClass]"></span>
            <span>{{ st.label }}</span>
            <span class="font-bold">{{ st.count }}</span>
          </div>
          <div class="ml-auto text-[11px] text-slate-400">
            完成率
            <span class="ml-1 font-bold text-emerald-600 dark:text-emerald-400">{{ completionRate }}%</span>
          </div>
        </div>

        <!-- 病历卡片网格 -->
        <div class="flex-1 overflow-y-auto p-5 custom-scrollbar">
          <div v-if="filteredRecords.length === 0" class="flex flex-col items-center justify-center h-full text-slate-400">
            <InboxOutlined class="text-4xl mb-3" />
            <div class="text-sm">暂无病历记录</div>
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-4">
            <!-- ===== 重构后的病案卡片 ===== -->
            <div
              v-for="record in filteredRecords"
              :key="record.id"
              @click="openRecord(record)"
              class="relative bg-white dark:bg-slate-800 rounded-xl shadow-[0_4px_16px_rgba(0,0,0,0.04)] hover:shadow-[0_8px_30px_rgba(0,0,0,0.08)] hover:-translate-y-0.5 cursor-pointer transition-all duration-300 border border-transparent hover:border-blue-100 dark:hover:border-blue-900/30 group"
            >
              <div class="p-4 flex flex-col gap-3">
                <!-- 头部：姓名为主标题，床号为辅标签 -->
                <div class="flex items-center justify-between">
                  <div class="flex items-center gap-2.5">
                    <span v-if="record.bedNo" class="px-2 py-0.5 bg-blue-50 text-blue-600 text-[11px] font-semibold rounded-md dark:bg-blue-900/30 dark:text-blue-300">
                      {{ record.bedNo }}床
                    </span>
                    <h3 class="text-[17px] font-bold text-slate-800 dark:text-slate-100 leading-none m-0 tracking-tight">
                      {{ record.name }}
                    </h3>
                  </div>
                  <!-- 右上角状态圆点 -->
                  <span
                    :class="[
                      'w-2.5 h-2.5 rounded-full flex-shrink-0',
                      record.status === 'completed' ? 'bg-emerald-400' :
                      record.status === 'has_defects' || record.status === 'warning' ? 'bg-amber-400' :
                      record.status === 'processing' ? 'bg-blue-400 animate-pulse' :
                      'bg-slate-200 dark:bg-slate-600'
                    ]"
                    :title="record.status === 'completed' ? '已完成' : record.status === 'has_defects' || record.status === 'warning' ? '有缺陷' : record.status === 'processing' ? '处理中' : '待处理'"
                  ></span>
                </div>

                <!-- 性别/年龄 + 保险标签（浅彩色） -->
                <div class="flex items-center gap-2 text-xs">
                  <span class="text-slate-500 dark:text-slate-400 font-medium">{{ record.sex }} / {{ record.age }}岁</span>
                  <span v-if="record.insurance" class="px-1.5 py-0.5 bg-blue-50 text-blue-500 rounded dark:bg-blue-900/20 dark:text-blue-300 text-[10px] font-medium">
                    {{ record.insurance }}
                  </span>
                </div>

                <!-- 住院信息区块 -->
                <div class="bg-slate-50/80 dark:bg-slate-700/20 rounded-lg p-2.5 flex justify-between items-center">
                  <div class="flex flex-col gap-1 text-[11px]">
                    <div class="flex gap-2 items-baseline">
                      <span class="text-slate-400 dark:text-slate-500">入院</span>
                      <span class="text-slate-700 dark:text-slate-200 font-semibold font-mono">{{ record.admissionDate }}</span>
                    </div>
                    <div class="flex gap-2 items-baseline">
                      <span class="text-slate-400 dark:text-slate-500">出院</span>
                      <span class="text-slate-700 dark:text-slate-200 font-semibold font-mono">{{ record.dischargeDate }}</span>
                    </div>
                  </div>
                  <!-- 住院天数（高风险背景高亮，加大背景块） -->
                  <div class="flex flex-col items-end">
                    <span class="text-[10px] text-slate-400 mb-0.5">住院</span>
                    <span :class="[
                      'text-base font-bold px-2.5 py-1 rounded-md leading-none',
                      record.days > 14 ? 'text-red-600 bg-red-50 dark:bg-red-900/20 dark:text-red-400' :
                      record.days > 7 ? 'text-amber-600 bg-amber-50 dark:bg-amber-900/20 dark:text-amber-400' :
                      'text-slate-700 bg-slate-100 dark:bg-slate-700/50 dark:text-slate-300'
                    ]">{{ record.days }}<span class="text-[10px] font-medium ml-0.5">天</span></span>
                  </div>
                </div>

                <!-- 底部：主治医生(左) + 状态(右) — 合并为一行节省垂直空间 -->
                <div class="flex items-center justify-between pt-2 border-t border-slate-50 dark:border-slate-700/30">
                  <div class="flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
                    <UserOutlined class="text-[11px]" />
                    <span class="font-medium text-slate-600 dark:text-slate-300">{{ record.doctor || '未分配' }}</span>
                  </div>
                  <span
                    v-if="record.status === 'completed'"
                    class="inline-flex items-center gap-1 text-emerald-600 text-[11px] font-semibold"
                  >
                    <CheckCircleOutlined /> 质控完成
                  </span>
                  <span
                    v-else-if="record.status === 'has_defects' || record.status === 'warning'"
                    class="inline-flex items-center gap-1 text-amber-600 text-[11px] font-semibold"
                  >
                    <WarningOutlined /> 存在缺陷
                  </span>
                  <span
                    v-else-if="record.status === 'processing'"
                    class="inline-flex items-center gap-1 text-blue-500 text-[11px] font-semibold"
                  >
                    <SyncOutlined spin /> AI 提取中
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1 text-slate-400 text-[11px] font-medium group-hover:text-blue-500 transition-colors"
                  >
                    <InboxOutlined /> 待处理
                  </span>
                </div>
              </div>
            </div>
          </div>
          <!-- 分页器 -->
          <div v-if="serverTotalPages > 1" class="flex justify-center py-4">
            <a-pagination
              v-model:current="currentPage"
              :total="serverTotal"
              :page-size="50"
              size="small"
              show-quick-jumper
              :show-total="(total: number) => `共 ${total} 例`"
              @change="handlePageChange"
            />
          </div>
        </div>
      </main>
    </template>

    <!-- ====== 详情模式（全屏） ====== -->
    <template v-else>
      <div class="flex-1 flex flex-col min-w-0 h-full">
        <!-- 详情顶部栏 -->
        <header class="h-14 flex items-center justify-between px-6 border-b border-slate-200 dark:border-slate-800 flex-shrink-0 bg-white dark:bg-slate-900">
          <div class="flex items-center gap-4">
            <button
              @click="goBackToList"
              class="flex items-center gap-2 text-slate-500 hover:text-blue-600 transition-colors text-sm font-medium"
            >
              <LeftOutlined />
              <span>返回列表</span>
            </button>
            <div class="w-px h-6 bg-slate-200 dark:bg-slate-700"></div>
            <div v-if="selectedRecord" class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-base">
                {{ selectedRecord.name.charAt(0) }}
              </div>
              <div>
                <div class="font-bold text-slate-800 dark:text-white text-base leading-tight">{{ selectedRecord.name }}</div>
                <div class="text-[11px] text-slate-400 font-mono">{{ selectedRecord.id }}</div>
              </div>
              <span class="text-xs text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full ml-2">
                {{ selectedRecord.department }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-3">
            <!-- 快捷翻页 -->
            <div class="flex items-center gap-1 mr-2">
              <a-tooltip title="上一例 (Alt+←)">
                <button
                  @click="goToPrevRecord"
                  :disabled="currentRecordIndex <= 0"
                  :class="[
                    'w-8 h-8 rounded-lg flex items-center justify-center transition-all text-sm',
                    currentRecordIndex <= 0
                      ? 'text-slate-300 cursor-not-allowed'
                      : 'text-slate-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20'
                  ]"
                >
                  <LeftOutlined />
                </button>
              </a-tooltip>
              <span class="text-xs text-slate-400 font-mono min-w-[48px] text-center">
                {{ currentRecordIndex + 1 }} / {{ filteredRecords.length }}
              </span>
              <a-tooltip title="下一例 (Alt+→)">
                <button
                  @click="goToNextRecord"
                  :disabled="currentRecordIndex >= filteredRecords.length - 1"
                  :class="[
                    'w-8 h-8 rounded-lg flex items-center justify-center transition-all text-sm',
                    currentRecordIndex >= filteredRecords.length - 1
                      ? 'text-slate-300 cursor-not-allowed'
                      : 'text-slate-500 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20'
                  ]"
                >
                  <RightOutlined />
                </button>
              </a-tooltip>
            </div>
            <a-button
              @click="icdDrawerVisible = true"
              class="!rounded-lg"
            >
              <template #icon><SearchOutlined /></template>
              ICD 查询
            </a-button>
            <a-button
              type="primary"
              :loading="frontpageGenerating"
              @click="detailMainTab = 'frontpage'; generateFrontpage()"
              class="!rounded-lg !shadow-[0_4px_14px_rgba(59,130,246,0.4)] hover:!shadow-[0_4px_20px_rgba(99,102,241,0.5)] transition-shadow duration-300"
            >
              <template #icon><ThunderboltOutlined /></template>
              {{ frontpageDraft ? '重新生成' : 'AI 生成首页' }}
            </a-button>
          </div>
        </header>

        <!-- 详情主体：左右分栏 -->
        <div class="flex-1 flex overflow-hidden">
          <!-- 左侧：患者信息 (35%) -->
          <aside class="w-[27%] min-w-[260px] max-w-[340px] border-r border-slate-200 dark:border-slate-800 overflow-y-auto custom-scrollbar bg-slate-50 dark:bg-slate-900/80">
            <div v-if="selectedRecord" class="px-4 py-5 space-y-5">

              <!-- ① 住院时间轴 + 关键数字 -->
              <div class="bg-white dark:bg-slate-800 rounded-xl p-5 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50">
                <div class="flex items-center justify-between mb-3">
                  <span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">住院信息</span>
                  <span v-if="selectedRecord.insurance" class="text-[11px] font-semibold bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-2.5 py-0.5 rounded-md">{{ selectedRecord.insurance }}</span>
                </div>
                <!-- 入院→出院时间轴 -->
                <div class="flex items-center gap-2 mb-3">
                  <div class="text-center">
                    <div class="text-[10px] text-slate-400 dark:text-slate-500 mb-0.5 font-medium">入院</div>
                    <div class="text-sm font-bold text-slate-700 dark:text-slate-200">{{ selectedRecord.admissionDate || '—' }}</div>
                  </div>
                  <div class="flex-1 flex items-center gap-1">
                    <div class="flex-1 h-px bg-slate-100 dark:bg-slate-700"></div>
                    <div class="px-2.5 py-0.5 bg-slate-100 dark:bg-slate-700 rounded-full text-xs font-bold text-slate-500 dark:text-slate-400 border border-white dark:border-slate-600">
                      {{ selectedRecord.days }}天
                    </div>
                    <div class="flex-1 h-px bg-slate-100 dark:bg-slate-700"></div>
                  </div>
                  <div class="text-center">
                    <div class="text-[10px] text-slate-400 dark:text-slate-500 mb-0.5 font-medium">出院</div>
                    <div class="text-sm font-bold text-slate-600 dark:text-slate-300">{{ selectedRecord.dischargeDate || '—' }}</div>
                  </div>
                </div>
                <!-- 底部：科室 + 医生 -->
                <div class="flex items-center gap-3 pt-2.5 border-t border-slate-100 dark:border-slate-700 text-[12px] text-slate-500 dark:text-slate-400">
                  <span>{{ selectedRecord.department }}</span>
                  <span class="opacity-40">·</span>
                  <UserOutlined class="text-[10px]" />
                  <span>{{ selectedRecord.doctor || '未分配' }}</span>
                </div>
              </div>

              <!-- ② 患者基本属性（只显示有值的行，grid 亲密对齐） -->
              <div class="bg-white dark:bg-slate-800 rounded-xl px-5 py-4 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50">
                <div class="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest mb-3.5">患者信息</div>
                <div class="grid grid-cols-[64px_1fr] gap-y-3 text-[13px]">
                  <template v-for="item in detailItems" :key="item.label">
                    <template v-if="item.value && item.value !== 'null床' && item.value !== 'null' && String(item.value).trim()">
                      <div class="text-slate-400 dark:text-slate-500 leading-snug">{{ item.label }}</div>
                      <div class="text-slate-800 dark:text-slate-200 font-medium leading-snug">{{ item.value }}</div>
                    </template>
                  </template>
                </div>
              </div>

              <!-- ③ 诊断信息 -->
              <div v-if="selectedRecord.diagnosis">
                <div class="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-3.5">诊断信息</div>
                <div class="bg-white dark:bg-slate-800 rounded-xl px-5 py-4 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50">
                  <div class="flex gap-2 items-start">
                    <span class="mt-0.5 text-[10px] text-white bg-blue-500 px-1.5 py-0.5 rounded font-bold flex-shrink-0">主诊断</span>
                    <span class="text-[13px] font-medium text-slate-800 dark:text-slate-100 leading-snug">{{ selectedRecord.diagnosis }}</span>
                  </div>
                  <div v-if="selectedRecord.diagnosisCode" class="mt-2 text-[11px] text-blue-400 font-mono pl-1">
                    ICD-10 · {{ selectedRecord.diagnosisCode }}
                  </div>
                </div>
              </div>

              <!-- ④ 病历文书 -->
              <div class="bg-white dark:bg-slate-800 rounded-xl px-5 py-4 shadow-[0_2px_10px_rgba(0,0,0,0.03)] border border-slate-100/80 dark:border-slate-700/50">
                <div class="flex items-center mb-2 px-1">
                  <span class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">病历文书</span>
                  <SyncOutlined v-if="documentsLoading" spin class="ml-2 text-blue-400 text-[10px]" />
                </div>
                <div class="space-y-1.5">
                  <div
                    v-for="doc in documentsList"
                    :key="doc.type + doc.label"
                    :class="[
                      'flex items-center justify-between rounded-lg px-3.5 py-2.5 text-[13px] transition-all duration-150',
                      doc.has_content
                        ? 'bg-slate-50 dark:bg-slate-800/60 hover:bg-blue-50 dark:hover:bg-blue-950/30 cursor-pointer border border-transparent hover:border-blue-100 dark:hover:border-blue-900/40'
                        : 'bg-slate-50/40 dark:bg-slate-800/20 text-slate-300 dark:text-slate-600'
                    ]"
                    @click="doc.has_content && openDocPreview(doc)"
                  >
                    <span class="flex items-center gap-2">
                      <FileTextOutlined :class="doc.has_content ? 'text-blue-400' : 'text-slate-200 dark:text-slate-700'" />
                      <span :class="doc.has_content ? 'text-slate-600 dark:text-slate-300' : ''">{{ doc.label }}</span>
                    </span>
                    <span v-if="doc.has_content" class="flex items-center gap-1.5 flex-shrink-0">
                      <span class="px-1.5 py-0.5 bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-400 text-[11px] font-semibold rounded">{{ doc.length }}字</span>
                      <EyeOutlined class="text-blue-300 text-[11px]" />
                    </span>
                    <span v-else class="text-[11px] text-slate-200 dark:text-slate-700">—</span>
                  </div>
                  <div v-if="!documentsLoading && documentsList.length === 0" class="text-[12px] text-slate-400 text-center py-4">
                    暂无病历文书
                  </div>
                </div>
              </div>

              <!-- 文书预览抽屉 -->
              <a-drawer
                v-model:open="docDrawerVisible"
                :title="docDrawerTitle"
                placement="right"
                :width="600"
                :headerStyle="{ borderBottom: '1px solid #e2e8f0' }"
                :bodyStyle="{ padding: '20px', backgroundColor: '#fafbfc' }"
              >
                <div class="bg-white rounded-lg border border-slate-200 p-5 shadow-sm">
                  <pre class="whitespace-pre-wrap font-sans text-sm text-slate-700 leading-7 m-0">{{ docDrawerContent }}</pre>
                </div>
              </a-drawer>
            </div>
          </aside>


          <!-- 右侧：三 Tab 内容区 (65%) -->
          <main class="flex-1 overflow-hidden flex flex-col bg-white dark:bg-slate-900">
            <a-tabs v-model:activeKey="detailMainTab" size="small" class="detail-main-tabs flex-1 flex flex-col overflow-hidden" :tabBarStyle="{ margin: 0, padding: '0 24px', borderBottom: '1px solid #e2e8f0', flexShrink: 0 }">
              <!-- ====== Tab 1: 病历详情 ====== -->
              <a-tab-pane key="records" class="flex-1 overflow-y-auto custom-scrollbar">
                <template #tab>
                  <span class="flex items-center gap-1.5"><FileTextOutlined />病历详情</span>
                </template>
                <div class="p-6">
                  <EMRViewer
                    v-if="selectedRecord && emrRenderState !== 'fallback'"
                    ref="emrViewerRef"
                    :record-id="selectedRecord.id"
                    :visit-id="selectedRecord.visitId || selectedRecord.id"
                    :patient-id="selectedRecord.patientId"
                    :institute-id="selectedRecord.instituteId"
                    :max-height="650"
                    :hide-doc-tabs="true"
                    @loaded="handleEmrLoaded"
                    @error="handleEmrError"
                    @defect-click="handleEmrDefectClick"
                  />

                  <template v-else>
                    <div v-if="concatLoading" class="flex flex-col items-center py-20">
                      <a-spin size="large" />
                      <div class="text-sm text-slate-400 mt-4">加载病历文书中...</div>
                    </div>
                    <div v-else-if="concatText" class="medical-record-document">
                      <div class="mb-4 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                        <WarningOutlined />
                        <span>EMR 高亮视图暂不可用，已自动切换到原始文书预览。</span>
                      </div>
                      <div v-for="(section, idx) in concatSections" :key="idx" class="mb-8">
                        <div class="flex items-center gap-2 mb-3 pb-2 border-b-2 border-blue-100">
                          <FileTextOutlined class="text-blue-500" />
                          <h3 class="text-base font-bold text-slate-800 dark:text-white m-0">{{ section.title }}</h3>
                        </div>
                        <pre class="whitespace-pre-wrap font-sans text-sm text-slate-700 dark:text-slate-300 leading-7 m-0 bg-slate-50/50 dark:bg-slate-800/30 rounded-lg p-4 border border-slate-100 dark:border-slate-700/30">{{ section.content }}</pre>
                      </div>
                    </div>
                    <div v-else class="flex flex-col items-center justify-center py-20 text-slate-300">
                      <div class="w-20 h-20 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center mb-4 border-2 border-dashed border-slate-200 dark:border-slate-700">
                        <FileTextOutlined class="text-3xl" />
                      </div>
                      <div class="text-sm font-medium mb-1">暂无病历文书</div>
                      <div class="text-xs text-slate-400">该患者尚无可展示的病历文书内容</div>
                    </div>
                  </template>
                </div>
              </a-tab-pane>

              <!-- ====== Tab 2: 病案首页 ====== -->
              <a-tab-pane key="frontpage" class="flex-1 overflow-y-auto custom-scrollbar">
                <template #tab>
                  <span class="flex items-center gap-1.5"><FileSearchOutlined />病案首页</span>
                </template>
                <div class="p-6">
                  <div v-if="frontpageGenerating" class="py-8">
                    <!-- 进度头部 -->
                    <div class="flex items-center gap-3 mb-6 px-2">
                      <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-200">
                        <ThunderboltOutlined class="text-white text-lg" />
                      </div>
                      <div>
                        <div class="text-sm font-bold text-slate-800">正在从病历中提取首页信息</div>
                        <div class="text-xs text-slate-400 mt-0.5">已完成 {{ completedModules.length }} / 8 个模块</div>
                      </div>
                      <a-spin class="ml-auto" />
                    </div>

                    <!-- 进度条 -->
                    <div class="mb-6 px-2">
                      <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
                        <div class="h-full rounded-full bg-gradient-to-r from-blue-500 to-indigo-500 transition-all duration-500" :style="{ width: `${Math.round(completedModules.length / 8 * 100)}%` }"></div>
                      </div>
                    </div>

                    <!-- 模块时间线 -->
                    <div class="space-y-1 px-2">
                      <div
                        v-for="m in ALL_MODULE_KEYS"
                        :key="m"
                        class="flex items-start gap-3 px-3 py-2.5 rounded-lg transition-all duration-300"
                        :class="getModuleStatus(m) === 'done' ? 'bg-green-50/80' : getModuleStatus(m) === 'active' ? 'bg-blue-50 animate-pulse' : 'bg-slate-50/50'"
                      >
                        <!-- 状态图标 -->
                        <div class="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5"
                          :class="getModuleStatus(m) === 'done' ? 'bg-green-500' : getModuleStatus(m) === 'active' ? 'bg-blue-500' : 'bg-slate-200'"
                        >
                          <CheckCircleOutlined v-if="getModuleStatus(m) === 'done'" class="text-white text-[10px]" />
                          <span v-else-if="getModuleStatus(m) === 'active'" class="w-2 h-2 rounded-full bg-white animate-ping"></span>
                          <span v-else class="w-1.5 h-1.5 rounded-full bg-slate-400"></span>
                        </div>
                        <!-- 内容 -->
                        <div class="flex-1 min-w-0">
                          <div class="flex items-center gap-2">
                            <span class="text-sm font-medium"
                              :class="getModuleStatus(m) === 'done' ? 'text-green-700' : getModuleStatus(m) === 'active' ? 'text-blue-600' : 'text-slate-400'"
                            >{{ MODULE_LABELS_MAP[m] || m }}</span>
                            <span v-if="getModuleEntry(m)?.timestamp" class="text-[10px] text-slate-400 tabular-nums">{{ (getModuleEntry(m).timestamp / 1000).toFixed(1) }}s</span>
                            <span v-if="getModuleStatus(m) === 'active'" class="text-[10px] text-blue-400 font-medium">提取中...</span>
                          </div>
                          <!-- 提取结果预览 -->
                          <div v-if="getModuleEntry(m)?.preview?.length" class="flex flex-wrap gap-1.5 mt-1">
                            <span
                              v-for="(p, pi) in getModuleEntry(m).preview"
                              :key="pi"
                              class="text-[11px] px-1.5 py-0.5 rounded bg-white border border-green-200 text-green-700 truncate max-w-[200px]"
                            >{{ p }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="frontpageDraft">
                    <a-tabs v-model:activeKey="frontpageTab" size="small">
                      <a-tab-pane key="fields" tab="提取结果">
                        <!-- 完成头部 -->
                        <div class="flex items-center gap-3 mb-4">
                          <div class="w-9 h-9 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-md shadow-green-200">
                            <CheckCircleOutlined class="text-white text-base" />
                          </div>
                          <div class="flex-1">
                            <div class="text-sm font-bold text-slate-800">首页信息提取完成</div>
                            <div class="text-xs text-slate-400 mt-0.5">已从病历中提取 {{ completedModules.length }} 个模块的字段信息</div>
                          </div>
                          <div class="flex gap-2">
                            <a-button size="small" @click="handleExportFrontpage('health')">
                              <template #icon><DownloadOutlined /></template>
                              导出
                            </a-button>
                            <a-button size="small" type="primary" @click="handleSaveFrontpage">
                              <template #icon><SaveOutlined /></template>
                              保存到数据库
                            </a-button>
                          </div>
                        </div>

                        <!-- 完成后的模块清单 -->
                        <div class="space-y-1.5">
                          <div
                            v-for="m in ALL_MODULE_KEYS"
                            :key="m"
                            class="px-3 py-2.5 rounded-lg bg-slate-50/80 border border-slate-100"
                          >
                            <div class="flex items-center gap-2 mb-1.5">
                              <div class="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
                                <CheckCircleOutlined class="text-white text-[9px]" />
                              </div>
                              <span class="text-sm font-medium text-slate-700">{{ MODULE_LABELS_MAP[m] || m }}</span>
                              <span v-if="getModuleEntry(m)?.timestamp" class="text-[10px] text-slate-400 tabular-nums">{{ (getModuleEntry(m).timestamp / 1000).toFixed(1) }}s</span>
                              <span v-if="!getModuleEntry(m)?.preview?.length" class="text-[10px] text-slate-400 italic">未提取到数据</span>
                            </div>
                            <div v-if="getModuleEntry(m)?.preview?.length" class="flex flex-wrap gap-1.5 pl-6">
                              <span
                                v-for="(p, pi) in getModuleEntry(m).preview"
                                :key="pi"
                                class="text-[11px] px-1.5 py-0.5 rounded-md bg-white border border-slate-200 text-slate-600 leading-tight max-w-[260px] truncate"
                              >{{ p }}</span>
                            </div>
                          </div>
                        </div>
                      </a-tab-pane>
                      <a-tab-pane key="preview" tab="首页预览/打印">
                        <!-- AI 生成成功提示条 -->
                        <div v-if="completedModules.length > 0" class="mb-4 px-4 py-3 rounded-lg bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 flex items-center gap-3">
                          <div class="w-8 h-8 rounded-full bg-green-500 flex items-center justify-center flex-shrink-0">
                            <CheckCircleOutlined class="text-white text-sm" />
                          </div>
                          <div class="flex-1">
                            <div class="text-sm font-medium text-green-800">AI 已自动生成病案首页</div>
                            <div class="text-xs text-green-600 mt-0.5">从 {{ completedModules.length }} 个模块中提取字段信息并填入下方首页，请核对后确认</div>
                          </div>
                          <a-button size="small" type="link" @click="frontpageTab = 'fields'" class="text-green-600 hover:text-green-800">查看提取详情</a-button>
                        </div>
                        <HmFrontpagePreview :draft="frontpageDraft" />
                      </a-tab-pane>
                      <a-tab-pane key="official" tab="官方格式">
                        <div v-if="frontpageSheetLoading" class="flex items-center justify-center py-12">
                          <a-spin />
                        </div>
                        <FrontpageSheet v-else-if="frontpageSheetData" :data="frontpageSheetData" />
                        <div v-else class="text-center text-slate-400 py-12">暂无数据库首页数据</div>
                      </a-tab-pane>
                    </a-tabs>
                  </div>
                  <div v-else>
                    <!-- 未AI生成时，直接显示数据库中的官方格式 -->
                    <div v-if="frontpageSheetLoading" class="flex flex-col items-center py-20">
                      <a-spin size="large" />
                      <div class="text-sm text-slate-400 mt-4">加载病案首页数据中...</div>
                    </div>
                    <div v-else-if="frontpageSheetData">
                      <FrontpageSheet :data="frontpageSheetData" />
                    </div>
                    <div v-else class="flex flex-col items-center justify-center py-20 text-slate-300">
                      <div class="w-20 h-20 rounded-full bg-slate-50 dark:bg-slate-800 flex items-center justify-center mb-4 border-2 border-dashed border-slate-200 dark:border-slate-700">
                        <FileTextOutlined class="text-3xl" />
                      </div>
                      <div class="text-sm font-medium mb-1">暂无病案首页数据</div>
                      <div class="text-xs text-slate-400">可点击右上角「AI 生成首页」按钮从病历中自动提取</div>
                    </div>
                  </div>
                </div>
              </a-tab-pane>

              <!-- ====== Tab 3: 结算清单 ====== -->
              <a-tab-pane key="settlement" class="flex-1 overflow-y-auto custom-scrollbar">
                <template #tab>
                  <span class="flex items-center gap-1.5">
                    <span style="font-size:14px">💰</span>结算清单
                    <span v-if="settlementQcFailed > 0" class="ml-1 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-red-100 text-red-600 text-[10px] font-bold px-1">{{ settlementQcFailed }}</span>
                  </span>
                </template>
                <div class="bg-slate-100 p-6 min-h-[400px]">
                  <div v-if="settlementLoading" class="flex flex-col items-center py-20">
                    <a-spin size="large" />
                    <div class="text-sm text-slate-400 mt-4">加载结算清单中...</div>
                  </div>
                  <div v-else-if="settlementData">
                    <!-- AI 草稿横幅 -->
                    <div v-if="settlementData?.data_source === 'generated_from_frontpage'" class="mx-2 mb-3 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg flex items-center gap-3">
                      <span class="text-amber-500 text-lg">⚠️</span>
                      <div>
                        <div class="text-sm font-semibold text-amber-700">AI 生成草稿</div>
                        <div class="text-xs text-amber-600">本清单由病案首页 AI 抽取结果 + CDM 数据自动组装，需人工审核后方可上传医保系统</div>
                      </div>
                      <a-tag color="orange" class="ml-auto flex-shrink-0">Draft</a-tag>
                    </div>
                    <!-- 操作栏 -->
                    <div class="flex items-center justify-between mb-4 px-2">
                      <div class="text-sm text-slate-500">
                        清单流水号: <span class="font-mono font-bold text-slate-700">{{ settlementData.medinsur_serial_no || '-' }}</span>
                      </div>
                      <div class="flex items-center gap-2">
                        <a-button size="small" @click="runSettlementQc" :loading="settlementQcLoading">
                          <template #icon><CheckOutlined /></template>
                          执行质控
                        </a-button>
                      </div>
                    </div>
                    <!-- 官方格式结算清单 -->
                    <SettlementSheet :data="settlementData" />

                    <!-- 质控结果摘要 -->
                    <div v-if="settlementQcReport" class="mb-6">
                      <h4 class="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <CheckCircleOutlined class="text-green-500" /> 质控结果
                      </h4>
                      <div class="grid grid-cols-4 gap-3 mb-4">
                        <div class="bg-blue-50 rounded-lg p-3 text-center border border-blue-100">
                          <div class="text-2xl font-black text-blue-600">{{ settlementQcReport.summary.total }}</div>
                          <div class="text-[10px] text-slate-400 mt-1">总规则数</div>
                        </div>
                        <div class="bg-green-50 rounded-lg p-3 text-center border border-green-100">
                          <div class="text-2xl font-black text-green-600">{{ settlementQcReport.summary.passed }}</div>
                          <div class="text-[10px] text-slate-400 mt-1">通过</div>
                        </div>
                        <div class="bg-red-50 rounded-lg p-3 text-center border border-red-100">
                          <div class="text-2xl font-black text-red-600">{{ settlementQcReport.summary.failed }}</div>
                          <div class="text-[10px] text-slate-400 mt-1">不通过</div>
                        </div>
                        <div class="bg-amber-50 rounded-lg p-3 text-center border border-amber-100">
                          <div class="text-2xl font-black text-amber-600">{{ settlementQcReport.summary.pass_rate }}</div>
                          <div class="text-[10px] text-slate-400 mt-1">通过率</div>
                        </div>
                      </div>
                      <div class="space-y-2">
                        <div v-for="r in settlementQcReport.results.filter((x: any) => !x.passed)" :key="r.rule_id"
                          class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 border flex items-start gap-3"
                          :class="r.severity === 'error' ? 'border-red-200' : 'border-amber-200'"
                        >
                          <a-tag :color="r.severity === 'error' ? 'red' : 'orange'" class="mt-0.5 flex-shrink-0">{{ r.rule_id }}</a-tag>
                          <div class="min-w-0">
                            <div class="text-sm font-medium text-slate-800 dark:text-slate-200">{{ r.field_name }}</div>
                            <div class="text-xs text-slate-500 mt-0.5">{{ r.message }}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-else>
                    <!-- 无数据时仍展示空白结算清单样表 -->
                    <SettlementSheet :data="{}" />
                  </div>
                </div>
              </a-tab-pane>
            </a-tabs>
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
        >
          <template #content>
            <ContentQCTab
              :patient-id="selectedRecord?.patientId"
              :visit-id="selectedRecord?.id"
              :institute-id="selectedRecord?.instituteId"
              :documents="documentsList"
              @issues-change="(count: number) => contentQCCount = count"
            />
          </template>
          <template #qc="{ activeSubTab }">
            <QCResultTab
              :frontpage="frontpageDraft"
              :analyzing="frontpageGenerating"
              :refresh-seed="qcRefreshSeed"
              :active-tab="activeSubTab"
              @issues-change="handleAssistIssuesChange"
              @locate-field="handleLocateFromQC"
              @jump-evidence="handleJumpEvidenceFromQC"
              @refresh="generateFrontpage"
            />
          </template>
          <template #profile>
            <div class="p-3 space-y-3">
              <!-- 未分析状态 -->
              <div v-if="!profileAnalyzed && !profileAnalyzing" class="flex flex-col items-center text-center py-6">
                <div class="w-14 h-14 bg-blue-50 rounded-xl mb-4 flex items-center justify-center border border-blue-100">
                  <ScanOutlined class="text-2xl text-blue-500" />
                </div>
                <div class="text-sm font-bold text-slate-700 mb-1">AI 深度画像</div>
                <div class="text-xs text-slate-400 mb-4 max-w-[200px] leading-5">对病历全文进行深度阅读，构建诊断时间轴与风险画像</div>
                <a-button type="primary" size="small" @click="aiProfileModalVisible = true; profileAnalyzed = true" :disabled="!combinedMedicalText" class="!rounded-lg">
                  <template #icon><ThunderboltOutlined /></template>
                  开始分析
                </a-button>
              </div>

              <!-- 已分析 / 摘要卡 -->
              <template v-else>
                <div class="rounded-lg border border-blue-200 bg-blue-50/50 p-3">
                  <div class="flex items-center gap-2 mb-2">
                    <ScanOutlined class="text-blue-500" />
                    <span class="text-xs font-bold text-slate-700">画像摘要</span>
                    <span class="ml-auto text-[10px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded font-bold">已生成</span>
                  </div>
                  <div class="space-y-1.5 text-xs text-slate-600">
                    <div v-if="frontpageDraft?.diagnoses?.discharge_main_diagnosis_text" class="flex items-center gap-1.5">
                      <span class="w-1.5 h-1.5 rounded-full bg-red-400 flex-shrink-0"></span>
                      <span class="truncate">{{ frontpageDraft.diagnoses.discharge_main_diagnosis_text }}</span>
                    </div>
                    <div class="flex items-center gap-1.5">
                      <span class="w-1.5 h-1.5 rounded-full bg-blue-400 flex-shrink-0"></span>
                      <span>诊断时间轴 + 人体透视 + 器官画像</span>
                    </div>
                  </div>
                </div>
                <a-button block @click="aiProfileModalVisible = true" class="!rounded-lg !text-sm !font-bold">
                  <template #icon><EyeOutlined /></template>
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
              :bodyStyle="{ padding: 0, height: '78vh', overflow: 'hidden' }"
              centered
              destroyOnClose
            >
              <AIProfileDashboard
                :frontpage="frontpageDraft"
                :medical-text="combinedMedicalText"
                style="height: 100%; overflow-y: auto;"
              />
            </a-modal>
          </template>
          <template #drg>
            <div class="p-3 space-y-3">
              <!-- DRG 未分组状态 -->
              <div v-if="!drgResult && !drgLoading" class="flex flex-col items-center text-center py-6">
                <div class="w-14 h-14 bg-emerald-50 rounded-xl mb-4 flex items-center justify-center border border-emerald-100">
                  <NodeIndexOutlined class="text-2xl text-emerald-500" />
                </div>
                <div class="text-sm font-bold text-slate-700 mb-1">DRG 分组分析</div>
                <div class="text-xs text-slate-400 mb-4 max-w-[200px] leading-5">基于诊断和手术编码进行 DRG 分组与盈亏预测</div>
                <a-button type="primary" size="small" @click="performDRGGrouping" :disabled="!frontpageDraft" class="!rounded-lg">
                  <template #icon><ThunderboltOutlined /></template>
                  开始分组
                </a-button>
              </div>

              <!-- DRG 加载中 -->
              <div v-else-if="drgLoading" class="flex flex-col items-center py-8">
                <a-spin />
                <div class="text-xs text-slate-400 mt-3">DRG 分组计算中...</div>
              </div>

              <!-- DRG 已分组 / 摘要卡 -->
              <template v-else-if="drgResult">
                <div class="rounded-lg border border-emerald-200 bg-emerald-50/50 p-3">
                  <div class="flex items-center gap-2 mb-2">
                    <NodeIndexOutlined class="text-emerald-500" />
                    <span class="text-xs font-bold text-slate-700">分组结果</span>
                  </div>
                  <div class="space-y-1.5">
                    <div class="flex justify-between text-xs">
                      <span class="text-slate-500">DRG 分组</span>
                      <span class="font-bold text-slate-800">{{ drgResult.drg_code || '-' }}</span>
                    </div>
                    <div class="flex justify-between text-xs">
                      <span class="text-slate-500">权重</span>
                      <span class="font-bold text-blue-600">{{ drgResult.weight || '-' }}</span>
                    </div>
                    <div v-if="drgResult.payment" class="flex justify-between text-xs">
                      <span class="text-slate-500">支付标准</span>
                      <span class="font-bold text-emerald-600">¥{{ drgResult.payment }}</span>
                    </div>
                  </div>
                </div>
                <a-button block @click="drgDetailModalVisible = true" class="!rounded-lg !text-sm !font-bold">
                  <template #icon><EyeOutlined /></template>
                  查看 DRG 详情
                </a-button>
                <a-button block type="link" size="small" @click="performDRGGrouping">
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
              :bodyStyle="{ padding: '16px', maxHeight: '78vh', overflowY: 'auto' }"
              centered
              destroyOnClose
            >
              <DRGGroupingTab
                :drg-result="drgResult"
                :loading="drgLoading"
                :has-frontpage="!!frontpageDraft"
                :main-diagnosis-code="frontpageDraft?.diagnoses?.discharge_main_icd || ''"
                :main-diagnosis-text="frontpageDraft?.diagnoses?.discharge_main_diagnosis_text || ''"
                :main-procedure-code="frontpageDraft?.procedures?.main_procedure_code || ''"
                :main-procedure-name="frontpageDraft?.procedures?.main_procedure_text || ''"
                @group="performDRGGrouping"
                @open-optimization="openOptimization"
              />
            </a-modal>
          </template>
          <template #message>
            <div class="p-3 space-y-3">
              <div class="flex items-center justify-between gap-2">
                <a-segmented
                  v-model:value="notificationReadFilter"
                  size="small"
                  :options="[
                    { label: '未读', value: 'unread' },
                    { label: '全部', value: 'all' },
                    { label: '已读', value: 'read' },
                  ]"
                />
                <a-button type="link" size="small" :disabled="notificationUnreadCount === 0" @click="markAllAssistNotificationsRead">
                  <CheckOutlined /> 全部已读
                </a-button>
              </div>
              <div v-if="notificationLoading" class="py-8 text-center">
                <a-spin />
              </div>
              <div v-else class="space-y-2 max-h-[440px] overflow-y-auto custom-scrollbar pr-1">
                <div
                  v-for="notif in filteredAssistNotifications"
                  :key="notif.id"
                  class="rounded-lg border p-3"
                  :class="notif.is_read ? 'border-slate-200 bg-slate-50/50' : 'border-blue-200 bg-blue-50/50'"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0">
                      <div class="text-sm font-semibold text-slate-800 flex items-center gap-2">
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
                    <a-tag v-if="!notif.is_read" color="blue">未读</a-tag>
                  </div>
                  <div class="mt-2 flex items-center justify-end gap-2">
                    <a-button size="small" @click="handleAssistNotificationClick(notif)">去处理</a-button>
                    <a-button v-if="!notif.is_read" type="link" size="small" @click="markAssistNotificationRead(notif)">标记已读</a-button>
                  </div>
                </div>
                <a-empty v-if="filteredAssistNotifications.length === 0" description="暂无消息" />
              </div>
            </div>
          </template>
        </WorkstationAssistPanel>

        <a-drawer
          v-model:open="suggestionDrawerVisible"
          title="DRG 优化建议"
          placement="right"
          :width="560"
        >
          <div class="space-y-3">
            <div
              v-for="item in suggestions"
              :key="item.suggestion_id"
              class="rounded-lg border border-slate-200 bg-white p-4"
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
              <div v-if="item.evidence" class="mt-2 rounded bg-slate-50 px-3 py-2 text-xs text-slate-500">
                依据：{{ item.evidence }}
              </div>
              <div class="mt-3 flex justify-end gap-2">
                <a-button
                  size="small"
                  @click="handleDRGSuggestion('reject', item.suggestion_id)"
                >
                  忽略
                </a-button>
                <a-button
                  type="primary"
                  size="small"
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
            <div v-if="suggestionsLoading" class="flex items-center justify-center py-10">
              <a-spin />
            </div>
          </div>
        </a-drawer>

        <a-drawer
          v-model:open="icdDrawerVisible"
          title="ICD 编码查询"
          placement="right"
          :width="920"
          :bodyStyle="{ padding: '0', backgroundColor: '#f8fafc' }"
        >
          <div class="border-b border-slate-200 bg-white px-5 py-4">
            <div class="text-xs font-bold tracking-wider text-slate-400 uppercase mb-2">回填目标</div>
            <div class="flex items-center gap-3 flex-wrap">
              <a-segmented
                v-model:value="icdApplyTarget"
                :options="icdTargetOptions"
                size="small"
              />
              <div v-if="isOtherTarget" class="flex items-center gap-2 text-xs text-slate-500">
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
          <ICDSearchPanel
            allow-apply
            :apply-label="icdApplyLabel"
            @apply="handleApplyICDCode"
          />
        </a-drawer>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import axios from 'axios'
import { message } from 'ant-design-vue'
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
  FileSearchOutlined,
  EyeOutlined,
  SearchOutlined,
  CheckOutlined,
  NotificationOutlined,
  ScanOutlined,
  NodeIndexOutlined,
} from '@ant-design/icons-vue'
import FrontPagePanel from '@/views/workstation/FrontPagePanel.vue'
import HmFrontpagePreview from '@/components/frontpage/HmFrontpagePreview.vue'
import EMRViewer from '@/components/qc/EMRViewer.vue'
import WorkstationAssistPanel from './components/WorkstationAssistPanel.vue'
import QCResultTab from './components/QCResultTab.vue'
import ContentQCTab from './components/ContentQCTab.vue'
import ICDSearchPanel from './components/ICDSearchPanel.vue'
import SettlementSheet from './components/SettlementSheet.vue'
import FrontpageSheet from './components/FrontpageSheet.vue'
import AIProfileDashboard from '@/views/demo/frontpage/components/AIProfileDashboard.vue'
import DRGGroupingTab from '@/views/demo/frontpage/components/DRGGroupingTab.vue'
import { useDRGGrouping } from '@/views/demo/frontpage/composables/useDRGGrouping'
import type { ICDCodeDetail } from './components/ICDDetailPanel.vue'
import { useWorkstationSession } from './composables/useWorkstationSession'
import { useFrontpageDraft } from './composables/useFrontpageDraft'
import { useQcPipeline } from './composables/useQcPipeline'
import type {
  PatientRecord,
  DeptInfo,
  DocItem,
  FrontpageFocusTarget,
  QCIssueLike,
} from './types'

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

// ========== 数据（从 API 加载） ==========
const allRecords = ref<PatientRecord[]>([])
const departments = ref<DeptInfo[]>([])
const currentPage = ref(1)
const serverTotal = ref(0)
const serverTotalPages = ref(1)
const totalCount = computed(() => serverTotal.value)

// ========== 筛选状态 ==========
const activeDept = ref('全部科室')
const searchText = ref('')
const statusFilter = ref('all')
const loading = ref(false)
const contentQCCount = ref(0)

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

const assistNotifications = ref<any[]>([])
const notificationUnreadCount = ref(0)
const notificationLoading = ref(false)
const notificationReadFilter = ref<'all' | 'unread' | 'read'>('unread')

// ========== 病历文书预览 ==========
const documentsList = ref<DocItem[]>([])
const documentsLoading = ref(false)
const docDrawerVisible = ref(false)
const docDrawerTitle = ref('')
const docDrawerContent = ref('')

// ========== 详情主 Tab ==========
const detailMainTab = ref('records')  // records | frontpage | settlement
const emrViewerRef = ref<InstanceType<typeof EMRViewer> | null>(null)
const emrRenderState = ref<'idle' | 'loading' | 'ready' | 'fallback'>('idle')

// ========== 病历详情（拼接文本） ==========
const concatText = ref('')
const concatLoading = ref(false)
const concatSections = computed(() => {
  if (!concatText.value) return []
  const parts = concatText.value.split(/={40}/)
  const sections: { title: string; content: string }[] = []
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i].trim()
    if (part.startsWith('📋')) {
      const title = part.replace('📋', '').trim()
      const nextContent = parts[i + 1] || ''
      sections.push({ title, content: nextContent.trim() })
      i++ // skip next part since it's content
    }
  }
  return sections
})

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
    const resp = await fetch(`/api/medical-records/frontpage-sheet/${patientId}/${visitId}`)
    if (resp.ok) {
      frontpageSheetData.value = await resp.json()
    } else {
      frontpageSheetData.value = null
    }
  } catch (e) {
    console.error('加载病案首页数据失败:', e)
    frontpageSheetData.value = null
  } finally {
    frontpageSheetLoading.value = false
  }
}
const settlementQcFailed = computed(() => settlementQcReport.value?.summary?.failed || 0)

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
    const { data } = await axios.get(`/api/medical-records/documents/${visitId}`, { params: { mode: 'concat' } })
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
    const { data } = await axios.get(`/api/medical-records/settlement/${patientId}/${visitId}`)
    settlementData.value = data
  } catch (err: any) {
    if (err?.response?.status === 404) {
      // Fallback: 从首页抽取 + CDM SQL 生成草稿
      try {
        const { data: draft } = await axios.post(`/api/medical-records/settlement/${patientId}/${visitId}/generate`)
        settlementData.value = draft
      } catch (genErr) {
        console.warn('草稿生成也失败，显示空白样表:', genErr)
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
    const { data } = await axios.post(qcUrl)
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
    const { data } = await axios.get(`/api/medical-records/documents/${visitId}`)
    // 只显示有内容的 + 前 3 个核心文书类型（即使没内容也展示）
    const coreTypes = ['admission_record', 'discharge_record', 'surgery_record']
    const docs: DocItem[] = data.documents || []
    documentsList.value = docs.filter(
      (d: DocItem) => d.has_content || coreTypes.includes(d.type)
    )
  } catch (err) {
    console.error('加载病历文书失败:', err)
  } finally {
    documentsLoading.value = false
  }
}

function openDocPreview(doc: DocItem) {
  docDrawerTitle.value = doc.label
  docDrawerContent.value = doc.content || '暂无内容'
  docDrawerVisible.value = true
}

const combinedMedicalText = computed(() =>
  documentsList.value
    .filter(doc => doc.has_content && doc.content)
    .map(doc => `${doc.label}\n${doc.content}`)
    .join('\n\n')
)

const selectedRecord = computed(() =>
  allRecords.value.find(r => r.id === selectedId.value),
)

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
  frontpageDraft,
  frontpageModule,
  frontpageFocusTarget,
  frontpageFields,
  completedModules,
  setDraftEmpty,
  generateFrontpage,
  handleExportFrontpage,
  handleSaveFrontpage,
  focusFrontpageSection,
  handleApplyICDCode: applyICDCodeToDraft,
  applyFrontPanelEdits,
} = useFrontpageDraft(
  selectedId,
  selectedRecord,
  combinedMedicalText,
  touchCodingRefresh,
)

// ========== AI 生成进度辅助 ==========
import { MODULE_LABELS, type CompletedModule } from './composables/useFrontpageDraft'

const ALL_MODULE_KEYS = ['basic_info', 'hospitalization', 'diagnoses', 'procedures', 'other_medical_info', 'staff', 'costs', 'confidence']
const MODULE_LABELS_MAP = MODULE_LABELS

function getModuleEntry(m: string): CompletedModule | undefined {
  return completedModules.value.find(c => c.name === m)
}

function getModuleStatus(m: string): 'done' | 'active' | 'pending' {
  if (getModuleEntry(m)) return 'done'
  if (frontpageModule.value === m) return 'active'
  return 'pending'
}

// 生成完成后自动切到 "首页预览/打印" tab
watch(frontpageGenerating, (generating, wasGenerating) => {
  if (wasGenerating && !generating && frontpageDraft.value) {
    // 延迟一帧确保 DOM 已更新
    nextTick(() => {
      frontpageTab.value = 'preview'
    })
  }
})

const statusOptions = [
  { value: 'all', label: '全部状态' },
  { value: 'pending', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'completed', label: '已完成' },
  { value: 'warning', label: '有缺陷' },
]

// ========== API 加载 ==========
async function fetchData(page = 1) {
  loading.value = true
  try {
    const { data } = await axios.get('/api/medical-records/workstation', {
      params: { page, page_size: 50 }
    })
    allRecords.value = data.records || []
    departments.value = data.departments || []
    serverTotal.value = data.total || 0
    serverTotalPages.value = data.totalPages || 1
    currentPage.value = data.page || 1
  } catch (err) {
    console.error('加载工作台数据失败:', err)
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  fetchData(page)
  // 翻页后滚动到顶部
  document.querySelector('.custom-scrollbar')?.scrollTo({ top: 0, behavior: 'smooth' })
}

function refreshData() {
  fetchData(currentPage.value)
}

function selectDept(deptName: string) {
  activeDept.value = deptName
  currentPage.value = 1
  // 科室筛选在前端做，不需要重新请求
}

onMounted(() => {
  fetchData()
  fetchAssistNotifications()
})

// 切换病历时清除上次生成结果 + 加载文书列表 + 加载结算清单
watch(selectedId, (newId) => {
  setDraftEmpty()
  resetPerRecordTransient()
  assistIssues.value = []
  suggestionDrawerVisible.value = false
  docDrawerVisible.value = false
  settlementQcReport.value = null
  detailMainTab.value = 'records'
  emrRenderState.value = newId ? 'loading' : 'idle'
  if (newId) {
    loadDocuments(newId)
    loadConcatText(newId)
    // 加载结算清单（需要 patientId）
    const record = allRecords.value.find(r => r.id === newId)
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

// ========== 计算 ==========
const filteredRecords = computed(() => {
  let list = allRecords.value
  if (activeDept.value !== '全部科室') {
    list = list.filter(r => r.department === activeDept.value)
  }
  if (statusFilter.value !== 'all') {
    list = list.filter(r => r.status === statusFilter.value)
  }
  if (searchText.value.trim()) {
    const keyword = searchText.value.trim().toLowerCase()
    list = list.filter(r =>
      r.name.toLowerCase().includes(keyword) ||
      r.id.toLowerCase().includes(keyword)
    )
  }
  return list
})

const statusCounts = computed(() => {
  const all = activeDept.value === '全部科室'
    ? allRecords.value
    : allRecords.value.filter(r => r.department === activeDept.value)
  return {
    completed: all.filter(r => r.status === 'completed').length,
    warning: all.filter(r => r.status === 'warning').length,
    processing: all.filter(r => r.status === 'processing').length,
    pending: all.filter(r => r.status === 'pending').length,
  }
})

const completionRate = computed(() => {
  const all = activeDept.value === '全部科室'
    ? allRecords.value
    : allRecords.value.filter(r => r.department === activeDept.value)
  if (all.length === 0) return 0
  return Math.round((all.filter(r => r.status === 'completed').length / all.length) * 100)
})

// 状态分段控制器配置（预定义完整 class，避免 Tailwind 动态类名被 purge）
const statusPills = computed(() => [
  { key: 'all', label: '全部', count: filteredRecords.value.length,
    activeClass: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200', dotClass: '' },
  { key: 'completed', label: '已完成', count: statusCounts.value.completed,
    activeClass: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200', dotClass: 'bg-emerald-500' },
  { key: 'has_defects', label: '有缺陷', count: statusCounts.value.warning,
    activeClass: 'bg-amber-50 text-amber-700 ring-1 ring-amber-200', dotClass: 'bg-amber-500' },
  { key: 'processing', label: '处理中', count: statusCounts.value.processing,
    activeClass: 'bg-blue-50 text-blue-700 ring-1 ring-blue-200', dotClass: 'bg-blue-500' },
  { key: 'pending', label: '待处理', count: statusCounts.value.pending,
    activeClass: 'bg-slate-100 text-slate-700 ring-1 ring-slate-200', dotClass: 'bg-slate-400' },
])

const detailItems = computed(() => {
  const r = selectedRecord.value
  if (!r) return []
  return [
    { label: '科室', value: r.department },
    { label: '床号', value: r.bedNo + '床' },
    { label: '性别/年龄', value: `${r.sex} / ${r.age}岁` },
    { label: '医保类型', value: r.insurance },
    { label: '入院日期', value: r.admissionDate },
    { label: '住院天数', value: r.days + '天' },
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
  if (icdApplyTarget.value === 'otherDiagnosis') return `回填其他诊断编码（第 ${icdApplyIndex.value} 条）`
  return `回填其他手术编码（第 ${icdApplyIndex.value} 条）`
})

const filteredAssistNotifications = computed(() => {
  if (notificationReadFilter.value === 'all') return assistNotifications.value
  const expectRead = notificationReadFilter.value === 'read'
  return assistNotifications.value.filter(item => !!item.is_read === expectRead)
})


function openRecord(record: PatientRecord) {
  openSessionRecord(record.id)
  assistPanelVisible.value = false
  icdDrawerVisible.value = false
}

// 快捷翻页
const currentRecordIndex = computed(() => {
  if (!selectedRecord.value) return -1
  return filteredRecords.value.findIndex(r => r.id === selectedRecord.value!.id)
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
  // 不清空 selectedId，方便返回后还能看到高亮
}


async function fetchAssistNotifications() {
  notificationLoading.value = true
  try {
    const res = await axios.get('/api/v1/notifications', { params: { page_size: 30 } })
    const data = res.data?.data || {}
    assistNotifications.value = Array.isArray(data.items) ? data.items : []
    notificationUnreadCount.value = Number(data.unread_count || 0)
  } catch (err) {
    console.error('加载消息概览失败:', err)
  } finally {
    notificationLoading.value = false
  }
}

async function markAssistNotificationRead(notif: any) {
  if (!notif?.id || notif.is_read) return
  try {
    await axios.put(`/api/v1/notifications/${notif.id}/read`)
    notif.is_read = true
    notificationUnreadCount.value = Math.max(0, notificationUnreadCount.value - 1)
  } catch (err) {
    console.error('标记消息已读失败:', err)
    message.error('标记已读失败')
  }
}

async function markAllAssistNotificationsRead() {
  try {
    await axios.put('/api/v1/notifications/read-all')
    await fetchAssistNotifications()
    message.success('已全部标记为已读')
  } catch (err) {
    console.error('全部已读失败:', err)
    message.error('全部已读失败')
  }
}

async function handleAssistNotificationClick(notif: any) {
  await markAssistNotificationRead(notif)
  const targetRecordId = notif?.record_id
  if (!targetRecordId) {
    assistTab.value = 'form'
    frontpageTab.value = 'fields'
    message.info('该消息未绑定病历，已切换到质控页')
    return
  }

  const record = allRecords.value.find(item => item.id === targetRecordId)
  if (!record) {
    message.warning(`未找到病历 ${targetRecordId}`)
    return
  }

  openSessionRecord(record.id)
  assistPanelVisible.value = true
  assistTab.value = 'form'
  frontpageTab.value = 'fields'
}

function formatRelativeTime(iso: string) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diff = Math.floor((now.getTime() - d.getTime()) / 1000)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return `${Math.floor(diff / 86400)} 天前`
}

function handleLocateFromQC(payload: { target: FrontpageFocusTarget; issue: { description?: string } }) {
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
  const applied = applyICDCodeToDraft(detail, icdApplyTarget.value, Number(icdApplyIndex.value || 1))
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
  docDrawerTitle.value = `依据文书：${doc.label}`
  docDrawerContent.value = findEvidenceSnippet(issue, doc.content) || (doc.content || '暂无内容')
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
  const matched = assistIssues.value.find(issue => issue?.id === defectId)
  if (matched?.description) {
    message.info(`已定位质控问题：${matched.description}`)
  }
}

function handleAssistTabChange(tab: 'form' | 'coding' | 'cost' | 'profile' | 'drg' | 'message') {
  assistTab.value = tab
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
.custom-scrollbar::-webkit-scrollbar { width: 5px; height: 5px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(203, 213, 225, 0.4); border-radius: 4px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: rgba(148, 163, 184, 0.6); }

/* 详情主 Tab 样式 */
.detail-main-tabs .ant-tabs-content {
  flex: 1;
  overflow: hidden;
}
.detail-main-tabs .ant-tabs-tabpane {
  height: 100%;
  overflow-y: auto;
}
</style>
