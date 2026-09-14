<template>
  <div class="ai-profile-dashboard h-full">
    <div
      v-if="!profile && !profileLoading"
      class="h-full flex flex-col items-center justify-start text-center p-6 pt-16"
    >
      <div
        class="w-20 h-20 bg-blue-50 dark:bg-blue-900/20 rounded-2xl mb-6 flex items-center justify-center border border-blue-100 dark:border-blue-800/50 shadow-sm"
      >
        <ScanOutlined class="text-4xl text-blue-500" />
      </div>
      <h3 class="text-xl font-bold text-slate-800 dark:text-white mb-3">
        AI 深度画像分析
      </h3>
      <p class="text-sm text-slate-500 dark:text-slate-400 mb-8 max-w-sm leading-relaxed">
        对病历全文进行深度阅读，构建诊断发生发展时间轴，验证手术闭环完整性，并自动发现首页填报差异。
      </p>
      <button
        :disabled="!medicalText"
        class="bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 disabled:cursor-not-allowed text-white px-8 py-3 rounded-xl text-sm font-bold transition-all shadow-lg shadow-blue-500/20 flex items-center gap-2 hover:-translate-y-0.5 active:translate-y-0"
        @click="analyzeProfile"
      >
        <ThunderboltOutlined />
        开始深度画像分析
      </button>
    </div>

    <!-- Loading State -->
    <div
      v-else-if="profileLoading"
      class="h-full flex flex-col items-center justify-center bg-slate-50/50 dark:bg-slate-900/50"
    >
      <div class="relative w-28 h-28 mb-8">
        <svg
          class="w-full h-full animate-spin text-blue-500/20"
          viewBox="0 0 100 100"
          fill="none"
        >
          <circle
            cx="50"
            cy="50"
            r="45"
            stroke="currentColor"
            stroke-width="8"
          />
          <path
            d="M50 5 a45 45 0 0 1 45 45"
            stroke="currentColor"
            stroke-width="8"
            class="text-blue-500 stroke-current"
          />
        </svg>
        <div class="absolute inset-0 flex items-center justify-center">
          <div
            class="w-14 h-14 bg-white dark:bg-slate-800 rounded-full shadow-lg flex items-center justify-center animate-pulse border border-blue-100 dark:border-blue-900"
          >
            <RobotOutlined class="text-2xl text-blue-500" />
          </div>
        </div>
      </div>
      <h3 class="text-xl font-bold text-slate-800 dark:text-white mb-2">
        AI 智能分析中...
      </h3>
      <p class="text-sm text-slate-500 dark:text-slate-400 mb-8 text-center max-w-[280px]">
        正在深度阅读病历记录并构建诊断时间轴映射...
      </p>

      <div class="w-72">
        <div class="flex justify-between text-xs text-blue-500 dark:text-blue-400 mb-2 font-medium">
          <span>画像构建中...</span>
          <span class="font-mono animate-pulse">Running</span>
        </div>
        <div
          class="h-2 w-full bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden relative"
        >
          <div class="absolute inset-0 bg-blue-500/20 rounded-full" />
          <div
            class="h-full bg-gradient-to-r from-blue-400 to-indigo-500 rounded-full transition-all duration-300 ease-out animate-pulse w-[70%]"
          />
          <div
            class="absolute top-0 left-0 h-full w-[30%] bg-gradient-to-r from-transparent via-white/50 to-transparent -translate-x-[150%] animate-[shimmer_1.5s_infinite]"
          />
        </div>
      </div>
    </div>
    <div
      v-else
      class="h-full overflow-hidden flex flex-col"
    >
      <!-- Dashboard grid -->
      <div class="h-full p-4 overflow-y-auto custom-scrollbar flex flex-col">
        <!-- Stats Cards Removed as per request -->

        <div class="flex flex-col lg:grid lg:grid-cols-12 gap-4 flex-1 min-h-[600px]">
          <!-- Left: Problem List -->
          <div
            class="col-span-12 lg:col-span-3 bg-white dark:bg-slate-800 rounded-xl shadow-[0_2px_12px_rgba(0,0,0,0.04)] border border-slate-200/60 dark:border-slate-700/80 flex flex-col"
          >
            <div
              class="p-3 border-b border-slate-100 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-200"
            >
              问题列表
            </div>
            <div class="flex-1 overflow-y-auto p-2 space-y-2">
              <div
                class="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30 cursor-pointer hover:shadow-md transition-all"
              >
                <div class="flex justify-between items-start mb-1">
                  <span class="font-medium text-red-700 dark:text-red-300 text-sm">高血压3级 极高危</span>
                  <ExclamationCircleOutlined class="text-red-500" />
                </div>
                <div class="text-xs text-red-500/80">
                  I10.x00
                </div>
              </div>
              <div
                class="p-3 bg-slate-50 dark:bg-slate-700/30 rounded-lg border border-slate-100 dark:border-slate-700 cursor-pointer hover:shadow-md transition-all"
              >
                <div class="flex justify-between items-start mb-1">
                  <span class="font-medium text-slate-700 dark:text-slate-200 text-sm">2型糖尿病</span>
                </div>
                <div class="text-xs text-slate-500">
                  E11.900
                </div>
              </div>
              <div
                class="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-900/30 cursor-pointer hover:shadow-md transition-all"
              >
                <div class="flex justify-between items-start mb-1">
                  <span class="font-medium text-yellow-700 dark:text-yellow-300 text-sm">冠心病 (待查)</span>
                  <QuestionCircleOutlined class="text-yellow-500" />
                </div>
                <div class="text-xs text-yellow-500/80">
                  疑似诊断
                </div>
              </div>
            </div>
          </div>

          <!-- Center: 3D Body Model -->
          <div
            class="col-span-12 lg:col-span-5 bg-white dark:bg-slate-800 rounded-xl border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.04)] flex flex-col relative overflow-hidden group min-h-[280px]"
          >
            <div class="absolute inset-0 bg-slate-50 dark:bg-slate-900/50 opacity-40" />
            <div
              class="absolute top-4 left-5 text-slate-400 dark:text-slate-500 text-[11px] font-bold tracking-widest z-10 flex items-center gap-1.5"
            >
              <ScanOutlined /> AI 人体透视
            </div>

            <!-- QC Details Button -->
            <div class="absolute bottom-4 right-4 z-30">
              <button
                class="bg-white/80 hover:bg-white backdrop-blur-md border border-slate-200 shadow-sm text-slate-600 dark:bg-slate-800/80 dark:border-slate-700 dark:text-slate-300 px-4 py-2 flex items-center gap-2 rounded-lg text-[13px] font-bold transition-all group"
                @click="showQCModal"
              >
                <FileTextOutlined
                  class="text-blue-500 group-hover:scale-110 transition-transform text-base"
                />
                质控详情报告
              </button>
            </div>

            <div class="flex-1 flex items-center justify-center relative">
              <!-- Body Image -->
              <img
                :src="bodySchematicPng"
                class="h-[85%] object-contain opacity-90 drop-shadow-lg"
                alt="Body Map"
              >

              <!-- Dynamic Hotspots with Staggered Animation -->
              <template
                v-for="(marker, index) in currentBodyMarkers"
                :key="index"
              >
                <!-- Marker Container with Staggered Entry -->
                <div
                  class="absolute cursor-pointer z-20 transition-all duration-500"
                  :class="[
                    visibleMarkerIndices.includes(index)
                      ? 'opacity-100 scale-100'
                      : 'opacity-0 scale-0',
                  ]"
                  :style="{
                    top: getMarkerPosition(marker, 'top'),
                    left: getMarkerPosition(marker, 'left'),
                    transitionDelay: `${index * 300}ms`,
                  }"
                  @click="setActiveMarker(index)"
                >
                  <!-- Ping animation for active/severe markers -->
                  <div
                    v-if="activeMarkerIndex === index || marker.severity === 'severe'"
                    class="rounded-full animate-ping absolute opacity-75"
                    :class="[
                      getSeverityColor(marker.severity),
                      activeMarkerIndex === index ? 'w-6 h-6 -ml-1 -mt-1' : 'w-4 h-4',
                    ]"
                  />
                  <!-- Marker dot -->
                  <div
                    class="rounded-full border-2 border-white shadow-lg relative z-10 transition-all duration-300"
                    :class="[
                      getSeverityColor(marker.severity),
                      activeMarkerIndex === index ? 'w-5 h-5 ring-4 ring-white/30' : 'w-3 h-3',
                    ]"
                  />
                </div>

                <!-- Connection Line (SVG) -->
                <svg
                  v-if="activeMarkerIndex === index && visibleMarkerIndices.includes(index)"
                  class="absolute inset-0 w-full h-full pointer-events-none z-10 overflow-visible"
                >
                  <line
                    :x1="getMarkerPosition(marker, 'left')"
                    :y1="getMarkerPosition(marker, 'top')"
                    x2="5%"
                    y2="50%"
                    :stroke="
                      marker.severity === 'severe'
                        ? '#ef4444'
                        : marker.severity === 'moderate'
                          ? '#eab308'
                          : '#2b6cf6'
                    "
                    stroke-width="2"
                    stroke-dasharray="5,5"
                    class="animate-pulse"
                  />
                </svg>
              </template>

              <!-- Navigation dots -->
              <div
                v-if="currentBodyMarkers.length > 1"
                class="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 z-30"
              >
                <button
                  v-for="(_, idx) in currentBodyMarkers"
                  :key="idx"
                  class="w-2 h-2 rounded-full transition-all duration-300"
                  :class="
                    activeMarkerIndex === idx ? 'bg-white w-6' : 'bg-white/50 hover:bg-white/80'
                  "
                  @click="setActiveMarker(idx)"
                />
              </div>
            </div>
          </div>

          <!-- Right: Info Card Details -->
          <div class="col-span-12 lg:col-span-4 flex flex-col">
            <!-- Active Marker Info Card (Moved out) -->
            <div
              v-if="activeMarkerIndex !== null && currentBodyMarkers[activeMarkerIndex]"
              class="bg-white dark:bg-slate-800 rounded-xl shadow-[0_2px_12px_rgba(0,0,0,0.04)] border border-slate-200/60 dark:border-slate-700/80 p-4 h-full transition-all duration-500 flex flex-col"
              :class="
                visibleMarkerIndices.includes(activeMarkerIndex)
                  ? 'opacity-100 translate-y-0'
                  : 'opacity-0 translate-y-4'
              "
            >
              <div
                class="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100 dark:border-slate-700"
              >
                <div
                  class="w-3 h-3 rounded-full"
                  :class="getSeverityColor(currentBodyMarkers[activeMarkerIndex].severity)"
                />
                <span class="font-bold text-lg text-slate-800 dark:text-white">
                  {{ getRegionLabel(currentBodyMarkers[activeMarkerIndex].region) }}
                </span>
                <span
                  class="ml-auto px-2 py-1 rounded-full text-xs font-medium"
                  :class="getSeverityBadgeClass(currentBodyMarkers[activeMarkerIndex].severity)"
                >
                  {{ getSeverityLabel(currentBodyMarkers[activeMarkerIndex].severity) }}
                </span>
              </div>

              <div class="mb-4">
                <div class="text-xs text-slate-400 mb-1">
                  识别问题
                </div>
                <p class="text-base font-medium text-slate-700 dark:text-slate-200 leading-relaxed">
                  {{ currentBodyMarkers[activeMarkerIndex].condition }}
                </p>
              </div>

              <!-- Related Timeline Events -->
              <div
                v-if="
                  getRelatedTimelineEvents(currentBodyMarkers[activeMarkerIndex].condition).length >
                    0
                "
                class="flex-1 overflow-y-auto custom-scrollbar min-h-0"
              >
                <div class="text-xs font-semibold text-slate-500 mb-2">
                  相关诊疗事件
                </div>
                <div class="bg-slate-50 dark:bg-slate-700/30 rounded-lg p-3">
                  <ul class="space-y-3">
                    <li
                      v-for="(event, eIdx) in getRelatedTimelineEvents(
                        currentBodyMarkers[activeMarkerIndex].condition,
                      )"
                      :key="eIdx"
                      class="text-xs text-slate-600 dark:text-slate-400 flex gap-2"
                    >
                      <span class="text-blue-500 mt-0.5">•</span>
                      <span class="">
                        <span class="block text-xs text-slate-400 mb-0.5">{{ event.date }}</span>
                        {{ event.event }}
                      </span>
                    </li>
                  </ul>
                </div>
              </div>

              <div
                class="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700 flex justify-between items-center text-xs text-slate-400"
              >
                <span>AI 智能分析</span>
                <span>{{ activeMarkerIndex + 1 }} / {{ currentBodyMarkers.length }}</span>
              </div>
            </div>

            <!-- Empty State -->
            <div
              v-else
              class="bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200/60 dark:border-slate-700/80 p-8 h-full flex flex-col items-center justify-center text-center text-slate-400 border-dashed"
            >
              <ScanOutlined class="text-4xl mb-3 opacity-20" />
              <p class="text-sm">
                点击左侧人体部位<br>查看详细分析
              </p>
            </div>
          </div>

          <!-- Vertical Timeline -->
          <div
            v-if="profile?.diagnosis_timeline?.length"
            class="col-span-12 mt-5 bg-white dark:bg-slate-800 rounded-xl shadow-[0_2px_12px_rgba(0,0,0,0.04)] border border-slate-200/60 dark:border-slate-700/80 p-5 overflow-hidden flex flex-col"
            style="height: 600px"
          >
            <div class="flex items-center justify-between mb-4 flex-shrink-0">
              <div class="flex items-center gap-3">
                <h4
                  class="text-sm font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2"
                >
                  <ClockCircleOutlined class="text-blue-500 text-base" />
                  诊断发生发展时间轴
                </h4>
                <div
                  class="bg-slate-100 dark:bg-slate-900 border border-slate-200/60 dark:border-slate-700/80 p-0.5 rounded-lg flex items-center shadow-inner"
                >
                  <button
                    class="px-2.5 py-1 text-[11px] font-medium rounded-md transition-all duration-200 flex items-center gap-1"
                    :class="
                      sortOrder === 'asc'
                        ? 'bg-white dark:bg-slate-700 text-[#2b6cf6] dark:text-blue-400 shadow-sm'
                        : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-200/50 dark:hover:bg-slate-800/50'
                    "
                    @click="sortOrder = 'asc'"
                  >
                    早 <ArrowRightOutlined class="text-[9px]" /> 晚
                  </button>
                  <button
                    class="px-2.5 py-1 text-[11px] font-medium rounded-md transition-all duration-200 flex items-center gap-1"
                    :class="
                      sortOrder === 'desc'
                        ? 'bg-white dark:bg-slate-700 text-[#2b6cf6] dark:text-blue-400 shadow-sm'
                        : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-200/50 dark:hover:bg-slate-800/50'
                    "
                    @click="sortOrder = 'desc'"
                  >
                    晚 <ArrowRightOutlined class="text-[9px]" /> 早
                  </button>
                </div>
              </div>
              <span
                class="bg-slate-50 dark:bg-slate-700/50 text-slate-500 px-2 py-0.5 rounded text-[11px] font-bold border border-slate-200 dark:border-slate-600"
              >{{ profile.diagnosis_timeline.length }} 个事件</span>
            </div>
            <!-- Kanban-style Multi-column Timeline -->
            <div
              class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4 flex-1 overflow-y-auto custom-scrollbar min-h-0 p-1"
            >
              <!-- Column 1: Diagnosis -->
              <div class="flex flex-col gap-3">
                <div
                  class="sticky top-0 z-10 bg-blue-50/90 text-[#0057b8] dark:bg-blue-900/50 dark:text-blue-300 font-bold px-3 py-2 border-l-4 border-blue-500 rounded-r-md shadow-sm backdrop-blur flex items-center gap-2 text-sm"
                >
                  <HeartOutlined /> 诊断
                </div>
                <div
                  v-if="!groupedEvents.diagnosis.length"
                  class="text-xs text-slate-400 p-2 text-center border border-dashed rounded-lg border-slate-200"
                >
                  无相关记录
                </div>
                <div
                  v-for="(event, idx) in groupedEvents.diagnosis"
                  :key="'diag-' + idx"
                  class="bg-blue-50/30 dark:bg-slate-700/30 border border-blue-100 dark:border-slate-600 rounded-lg p-3 hover:shadow-md transition-all"
                >
                  <div class="text-[11px] text-slate-400 font-mono mb-1">
                    {{ event.date }}
                  </div>
                  <div
                    class="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-2 leading-snug"
                  >
                    {{ event.event }}
                  </div>
                  <div class="flex items-center gap-1">
                    <CheckCircleOutlined class="text-blue-500 text-xs" />
                    <span class="text-xs text-slate-500">确诊</span>
                  </div>
                </div>
              </div>

              <!-- Column 2: Treatment / Surgery -->
              <div class="flex flex-col gap-3">
                <div
                  class="sticky top-0 z-10 bg-red-50/90 text-red-700 dark:bg-red-900/50 dark:text-red-300 font-bold px-3 py-2 border-l-4 border-red-500 rounded-r-md shadow-sm backdrop-blur flex items-center gap-2 text-sm"
                >
                  <ToolOutlined /> 手术/治疗
                </div>
                <div
                  v-if="!groupedEvents.treatment.length"
                  class="text-xs text-slate-400 p-2 text-center border border-dashed rounded-lg border-slate-200"
                >
                  无相关记录
                </div>
                <div
                  v-for="(event, idx) in groupedEvents.treatment"
                  :key="'treat-' + idx"
                  class="bg-red-50/30 dark:bg-slate-700/30 border border-red-100 dark:border-slate-600 rounded-lg p-3 hover:shadow-md transition-all"
                >
                  <div class="text-[11px] text-slate-400 font-mono mb-1">
                    {{ event.date }}
                  </div>
                  <div
                    class="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-2 leading-snug"
                  >
                    {{ event.event }}
                  </div>
                  <div class="flex items-center gap-1">
                    <CheckCircleOutlined class="text-red-500 text-xs" />
                    <span class="text-xs text-slate-500">已执行</span>
                  </div>
                </div>
              </div>

              <!-- Column 3: Medication & Symptoms -->
              <div class="flex flex-col gap-3">
                <div
                  class="sticky top-0 z-10 bg-green-50/90 text-green-700 dark:bg-green-900/50 dark:text-green-300 font-bold px-3 py-2 border-l-4 border-green-500 rounded-r-md shadow-sm backdrop-blur flex items-center gap-2 text-sm"
                >
                  <MedicineBoxOutlined /> 症状/用药
                </div>
                <div
                  v-if="!groupedEvents.medication.length"
                  class="text-xs text-slate-400 p-2 text-center border border-dashed rounded-lg border-slate-200"
                >
                  无相关记录
                </div>
                <div
                  v-for="(event, idx) in groupedEvents.medication"
                  :key="'med-' + idx"
                  class="bg-white dark:bg-slate-700/30 border border-slate-200 dark:border-slate-600 rounded-lg p-3 hover:shadow-md transition-all shadow-sm"
                >
                  <div class="text-[11px] text-slate-400 font-mono mb-1">
                    {{ event.date }}
                  </div>
                  <div
                    class="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-2 leading-snug"
                  >
                    {{ event.event }}
                  </div>
                  <div class="flex items-center gap-1">
                    <CheckCircleOutlined class="text-green-500 text-xs" />
                    <span class="text-xs text-slate-500">记录</span>
                  </div>
                </div>
              </div>

              <!-- Column 4: Examination & Tests -->
              <div class="flex flex-col gap-3">
                <div
                  class="sticky top-0 z-10 bg-yellow-50/90 text-yellow-700 dark:bg-yellow-900/50 dark:text-yellow-300 font-bold px-3 py-2 border-l-4 border-yellow-500 rounded-r-md shadow-sm backdrop-blur flex items-center gap-2 text-sm"
                >
                  <ExperimentOutlined /> 检验/检查
                </div>
                <div
                  v-if="!groupedEvents.examination.length"
                  class="text-xs text-slate-400 p-2 text-center border border-dashed rounded-lg border-slate-200"
                >
                  无相关记录
                </div>
                <div
                  v-for="(event, idx) in groupedEvents.examination"
                  :key="'exam-' + idx"
                  class="bg-yellow-50/30 dark:bg-slate-700/30 border border-yellow-100 dark:border-slate-600 rounded-lg p-3 hover:shadow-md transition-all"
                >
                  <div class="text-[11px] text-slate-400 font-mono mb-1">
                    {{ event.date }}
                  </div>
                  <div
                    class="text-sm font-semibold text-slate-800 dark:text-slate-200 mb-2 leading-snug"
                  >
                    {{ event.event }}
                  </div>
                  <div
                    v-if="event.severity === 'severe' || event.severity === 'critical'"
                    class="flex items-center gap-1"
                  >
                    <ExclamationCircleOutlined class="text-yellow-600 text-xs" />
                    <span class="text-xs text-yellow-600 font-medium">异常指标</span>
                  </div>
                  <div
                    v-else
                    class="flex items-center gap-1"
                  >
                    <CheckCircleOutlined class="text-green-500 text-xs" />
                    <span class="text-xs text-slate-500">正常</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- QC Report Modal -->
          <a-modal
            v-model:open="isQCModalVisible"
            title="AI 质控详情报告"
            width="800px"
            :footer="null"
          >
            <a-tabs default-active-key="1">
              <a-tab-pane
                key="1"
                tab="诊断发生发展时间轴"
              >
                <div class="max-h-[500px] overflow-y-auto p-4">
                  <a-timeline mode="left">
                    <a-timeline-item
                      v-for="(event, idx) in profile?.diagnosis_timeline"
                      :key="idx"
                      :color="
                        event.severity === 'critical' || event.severity === 'severe'
                          ? 'red'
                          : 'blue'
                      "
                    >
                      <template #label>
                        <span class="text-slate-500 text-xs">{{ event.date }}</span>
                      </template>
                      <div class="font-medium text-slate-800 dark:text-slate-200">
                        {{ event.event }}
                      </div>
                      <div class="text-xs text-slate-500 mt-1">
                        <span class="capitalize bg-slate-100 dark:bg-slate-800 px-1.5 rounded">{{
                          event.type
                        }}</span>
                      </div>
                    </a-timeline-item>
                  </a-timeline>
                </div>
              </a-tab-pane>
              <a-tab-pane
                key="2"
                tab="首页填报差异验证"
              >
                <div class="max-h-[500px] overflow-y-auto p-4">
                  <div
                    v-if="!profile?.discrepancies || profile.discrepancies.length === 0"
                    class="text-center text-slate-400 p-8"
                  >
                    <CheckCircleOutlined class="text-4xl text-green-500 mb-2" />
                    <div>未发现显著填报问题</div>
                  </div>
                  <a-list
                    v-else
                    item-layout="horizontal"
                    :data-source="profile.discrepancies"
                  >
                    <template #renderItem="{ item }">
                      <a-list-item
                        class="border-b border-slate-100 dark:border-slate-700 px-2 py-3"
                      >
                        <a-list-item-meta>
                          <template #title>
                            <span class="text-slate-800 dark:text-slate-200 font-medium">{{
                              item.field
                            }}</span>
                            <span
                              class="ml-2 px-2 py-0.5 rounded text-xs"
                              :class="
                                item.type === 'missing'
                                  ? 'bg-red-100 text-red-700'
                                  : 'bg-orange-100 text-orange-700'
                              "
                            >
                              {{ item.type === 'missing' ? '漏填' : '不一致' }}
                            </span>
                          </template>
                          <template #description>
                            <div class="text-slate-600 dark:text-slate-400 mt-1">
                              <div class="mb-1">
                                <span class="text-slate-400">问题:</span> {{ item.description }}
                              </div>
                              <div class="text-[#2b6cf6] dark:text-blue-400">
                                <span class="text-slate-400"> 建议:</span> {{ item.suggestion }}
                              </div>
                            </div>
                          </template>
                        </a-list-item-meta>
                      </a-list-item>
                    </template>
                  </a-list>
                </div>
              </a-tab-pane>
            </a-tabs>
          </a-modal>

          <!-- Right: Vitals & Labs Removed as per request -->
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { message } from 'ant-design-vue'
import { getAccessToken } from '@/utils/auth-token'
import bodySchematicPng from '@/assets/images/lx-logo.png'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  FileTextOutlined,
  QuestionCircleOutlined,
  ScanOutlined,
  HeartOutlined,
  ToolOutlined,
  MedicineBoxOutlined,
  ExperimentOutlined,
  ArrowRightOutlined,
  RobotOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'

const emit = defineEmits<{
  (e: 'expand'): void
}>()

const props = defineProps<{
  medicalText?: string
  frontpage?: any | null
}>()

const frontpage = computed(() => props.frontpage || null)

const profile = ref<any>(null)
const profileLoading = ref(false)

// Group events by type for the 4-column timeline layout
const sortOrder = ref<'asc' | 'desc'>('asc')

const groupedEvents = computed(() => {
  if (!profile.value?.diagnosis_timeline) {
    return { diagnosis: [], treatment: [], medication: [], examination: [] }
  }

  // Clone to safely sort without mutating original state while filtering
  let sortedTimeline = [...profile.value.diagnosis_timeline]
  if (sortOrder.value === 'desc') {
    sortedTimeline.sort((a, b) => (b.date || '').localeCompare(a.date || ''))
  } else {
    // Backend API already sorted Ascending originally, but ensure safe sort
    sortedTimeline.sort((a, b) => (a.date || '').localeCompare(b.date || ''))
  }

  const grouped: Record<string, any[]> = {
    diagnosis: [],
    treatment: [],
    medication: [],
    examination: [],
  }

  // Loop over sorted events to distribute into columns keeping sort order
  sortedTimeline.forEach((event: any) => {
    if (event.type === 'diagnosis') {
      grouped.diagnosis.push(event)
    } else if (event.type === 'treatment') {
      grouped.treatment.push(event)
    } else if (event.type === 'medication' || event.type === 'symptom') {
      grouped.medication.push(event)
    } else if (event.type === 'examination' || event.type === 'lab' || event.type === 'exam') {
      grouped.examination.push(event)
    } else {
      grouped.medication.push(event) // fallback to medication/symptom column
    }
  })

  return grouped
})

// Body marker animation state
const activeMarkerIndex = ref<number | null>(0)
const visibleMarkerIndices = ref<number[]>([])
const markerAnimationTimer = ref<number | null>(null)

// Default body markers (used before LLM analysis)
const defaultBodyMarkers = [
  {
    region: 'heart',
    condition: '冠状动脉粥样硬化',
    severity: 'severe',
    position: { top: '32%', left: '52%' },
  },
  {
    region: 'pancreas',
    condition: '2型糖尿病',
    severity: 'moderate',
    position: { top: '45%', left: '55%' },
  },
]

const currentBodyMarkers = computed(() => profile.value?.body_markers || defaultBodyMarkers)

const isQCModalVisible = ref(false)

const showQCModal = () => {
  isQCModalVisible.value = true
}

const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'severe':
      return 'bg-red-500'
    case 'moderate':
      return 'bg-yellow-500'
    case 'mild':
      return 'bg-blue-400'
    default:
      return 'bg-slate-400'
  }
}

const getRegionLabel = (region: string): string => {
  const labels: Record<string, string> = {
    heart: '心脏',
    lung: '肺部',
    liver: '肝脏',
    kidney: '肾脏',
    brain: '脑部',
    pancreas: '胰腺',
    stomach: '胃部',
  }
  return labels[region] || region
}

// Fixed coordinates for each region to ensure accurate positioning
const REGION_COORDINATES: Record<string, { top: string; left: string }> = {
  brain: { top: '8%', left: '50%' },
  lung: { top: '25%', left: '48%' }, // Slightly offset to avoid center overlapping
  heart: { top: '28%', left: '55%' }, // Heart is typically on the left side of the body (right side of image)
  liver: { top: '40%', left: '45%' },
  stomach: { top: '42%', left: '54%' },
  pancreas: { top: '44%', left: '52%' },
  kidney: { top: '48%', left: '42%' },
  intestine: { top: '55%', left: '50%' },
  spine: { top: '35%', left: '50%' },
}

const getMarkerPosition = (marker: any, axis: 'top' | 'left'): string => {
  // First try to resolve valid region-based coordinates
  if (marker.region && REGION_COORDINATES[marker.region]) {
    return REGION_COORDINATES[marker.region][axis]
  }

  // Fallback to coordinates provided in marker object if available
  const pos = marker.position?.[axis]
  if (typeof pos === 'number') return `${pos}%`
  if (typeof pos === 'string') return pos

  return '50%'
}

// Wave timeline helper functions
const getWavePath = (eventCount: number): string => {
  if (eventCount < 1) return ''

  const width = eventCount * 180 + 40
  const height = 200
  const centerY = height / 2
  const amplitude = 40 // Wave amplitude
  const startX = 20
  const endX = width - 20
  const segmentWidth = (endX - startX) / Math.max(1, eventCount - 1)

  let path = `M ${startX} ${centerY}`

  for (let i = 0; i < eventCount; i++) {
    const x = startX + i * segmentWidth
    const y = i % 2 === 0 ? centerY - amplitude : centerY + amplitude

    if (i === 0) {
      path = `M ${x} ${y}`
    } else {
      const prevX = startX + (i - 1) * segmentWidth
      const prevY = (i - 1) % 2 === 0 ? centerY - amplitude : centerY + amplitude
      const cp1x = prevX + segmentWidth * 0.5
      const cp1y = prevY
      const cp2x = x - segmentWidth * 0.5
      const cp2y = y
      path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x} ${y}`
    }
  }

  return path
}

const getWaveNodePosition = (index: number, total: number): Record<string, string> => {
  const width = total * 180 + 40
  const height = 200
  const centerY = height / 2
  const amplitude = 40
  const startX = 20
  const endX = width - 20
  const segmentWidth = (endX - startX) / Math.max(1, total - 1)

  const x = total === 1 ? width / 2 : startX + index * segmentWidth
  const y = index % 2 === 0 ? centerY - amplitude : centerY + amplitude

  return {
    left: `${x}px`,
    top: `${y}px`,
  }
}

const getSeverityBadgeClass = (severity: string): string => {
  switch (severity) {
    case 'severe':
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    case 'moderate':
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
    case 'mild':
      return 'bg-blue-100 text-[#0057b8] dark:bg-blue-900/30 dark:text-blue-400'
    default:
      return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400'
  }
}

const getSeverityLabel = (severity: string): string => {
  switch (severity) {
    case 'severe':
      return '严重'
    case 'moderate':
      return '中度'
    case 'mild':
      return '轻度'
    default:
      return '未知'
  }
}

const setActiveMarker = (index: number) => {
  activeMarkerIndex.value = index
}

const stopMarkerAnimation = () => {
  if (markerAnimationTimer.value) {
    clearInterval(markerAnimationTimer.value)
    markerAnimationTimer.value = null
  }
}

const startMarkerAnimation = () => {
  stopMarkerAnimation()
  visibleMarkerIndices.value = []
  activeMarkerIndex.value = 0

  const markers = currentBodyMarkers.value
  markers.forEach((_: any, idx: number) => {
    setTimeout(
      () => {
        visibleMarkerIndices.value.push(idx)
      },
      idx * 500 + 300,
    )
  })

  setTimeout(
    () => {
      markerAnimationTimer.value = window.setInterval(() => {
        if (activeMarkerIndex.value === null) {
          activeMarkerIndex.value = 0
        } else {
          activeMarkerIndex.value = (activeMarkerIndex.value + 1) % markers.length
        }
      }, 3000)
    },
    markers.length * 500 + 1000,
  )
}

const getRelatedTimelineEvents = (markerCondition: string) => {
  if (!profile.value?.diagnosis_timeline || !markerCondition) return []

  const keywords = markerCondition.split(/[,，\s]/).filter((k: string) => k.length > 1)

  return profile.value.diagnosis_timeline
    .filter((item: any) => {
      const eventText = item?.event || ''
      if (keywords.some((k: string) => eventText.includes(k))) return true
      if (eventText.includes(markerCondition)) return true
      if (markerCondition.includes('心') && eventText.includes('胸闷')) return true
      return false
    })
    .slice(0, 3)
}

const analyzeProfile = async () => {
  if (!props.medicalText) return

  profileLoading.value = true
  try {
    const token = getAccessToken()
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`
    }

    const response = await fetch('/api/v1/frontpage/profile/analyze', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        medical_text: props.medicalText,
        frontpage_diagnoses: frontpage.value?.diagnoses?.discharge_main_diagnosis_text
          ? [frontpage.value.diagnoses.discharge_main_diagnosis_text]
          : [],
        frontpage_procedures: (frontpage.value as any)?.procedures?.main_procedure_text
          ? [(frontpage.value as any).procedures.main_procedure_text]
          : [],
      }),
    })

    const data = await response.json()

    if (data.success && data.data) {
      // 转换后端数据格式为前端期望的格式
      const backendData = data.data

      // 转换 diagnosis_timeline 格式
      const transformedTimeline: any[] = []
      if (backendData.diagnosis_timeline) {
        for (const diag of backendData.diagnosis_timeline) {
          // 添加诊断本身作为时间线事件
          transformedTimeline.push({
            date: diag.first_mention_time?.split(' ')[0] || '未知日期',
            event: diag.diagnosis_name || '诊断',
            type: 'diagnosis',
            severity: diag.status === 'confirmed' ? 'moderate' : 'mild',
          })

          // 添加该诊断下的时间线事件
          if (diag.timeline_events) {
            for (const evt of diag.timeline_events) {
              transformedTimeline.push({
                date: evt.time?.split(' ')[0] || '未知日期',
                event: `${diag.diagnosis_name}: ${evt.event || '事件'}`,
                type: evt.event_type || 'symptom',
                severity: 'mild',
              })
            }
          }
        }
      }

      // 添加手术验证信息到时间线
      if (backendData.surgery_verification) {
        for (const surg of backendData.surgery_verification) {
          transformedTimeline.push({
            date: surg.execution_time || surg.plan_time || '未知日期',
            event: surg.surgery_name || '手术',
            type: 'treatment',
            severity: surg.verification_status === 'verified' ? 'moderate' : 'severe',
          })
        }
      }

      // 按日期排序
      transformedTimeline.sort((a, b) => (a.date || '').localeCompare(b.date || ''))

      // 器官坐标映射字典 (适配高保真医疗人体透视图)
      const organPositions: Record<string, { top: string; left: string }> = {
        heart: { top: '34%', left: '52%' }, // 心脏 (稍偏左、胸腔中央偏上)
        lung: { top: '35%', left: '42%' }, // 肺部 (胸腔两侧，这里标示右肺)
        liver: { top: '48%', left: '45%' }, // 肝脏 (右上腹、胸腔下方)
        kidney: { top: '55%', left: '43%' }, // 肾脏 (腰部两侧背侧，稍靠下)
        stomach: { top: '50%', left: '55%' }, // 胃部 (左上腹)
        brain: { top: '15%', left: '50%' }, // 大脑
        intestine: { top: '65%', left: '50%' }, // 肠道 (腹腔中下部)
        pancreas: { top: '50%', left: '52%' }, // 胰腺/糖尿病 (胃部后方，腹腔中央偏左)
      }

      // 推断相关器官
      const inferRegion = (
        condition: string,
        index: number,
      ): { key: string; pos: { top: string; left: string } } => {
        const text = condition || ''
        if (text.includes('心') || text.includes('冠脉') || text.includes('血压'))
          return { key: 'heart', pos: organPositions['heart'] }
        if (text.includes('脑') || text.includes('梗') || text.includes('神'))
          return { key: 'brain', pos: organPositions['brain'] }
        if (text.includes('肺') || text.includes('呼吸') || text.includes('咳'))
          return { key: 'lung', pos: organPositions['lung'] }
        if (text.includes('肝') || text.includes('胆'))
          return { key: 'liver', pos: organPositions['liver'] }
        if (text.includes('肾') || text.includes('泌尿'))
          return { key: 'kidney', pos: organPositions['kidney'] }
        if (text.includes('胃')) return { key: 'stomach', pos: organPositions['stomach'] }
        if (text.includes('肠') || text.includes('消化'))
          return { key: 'intestine', pos: organPositions['intestine'] }
        if (text.includes('糖') || text.includes('胰'))
          return { key: 'pancreas', pos: organPositions['pancreas'] }

        // 兜底轮换分配
        const keys = Object.keys(organPositions)
        const matchedKey = keys[index % keys.length]
        return { key: matchedKey, pos: organPositions[matchedKey] }
      }

      profile.value = {
        ...backendData,
        diagnosis_timeline: transformedTimeline,
        // 生成 body_markers
        body_markers:
          backendData.body_markers ||
          transformedTimeline
            .filter((e: any) => e.type === 'diagnosis')
            .slice(0, 4) // 最多展示4个核心问题点
            .map((e: any, idx: number) => {
              const inferred = inferRegion(e.event, idx)
              return {
                region: inferred.key,
                condition: e.event,
                severity: e.severity || 'moderate',
                position: inferred.pos,
              }
            }),
      }

      message.success('AI 画像分析完成')
      startMarkerAnimation()
      setTimeout(() => emit('expand'), 500)
    } else {
      profile.value = {
        diagnosis_timeline: [
          { date: '2026-01-01', event: '因胸闷心悸入院', type: 'symptom', severity: 'moderate' },
        ],
        vital_signs: {},
        lab_results: {},
        risk_assessment: {
          overall_risk_score: 85,
          risk_level: 'high',
          primary_risks: [],
          recommendations: [],
        },
        body_markers: [],
        discrepancies: [],
      }
      message.warning('使用模拟分析结果')
    }
  } catch (error) {
    console.error('Profile analysis error:', error)
    message.error('分析失败，请检查网络连接')
  } finally {
    profileLoading.value = false
  }
}

watch(
  () => props.medicalText,
  () => {
    profile.value = null
    isQCModalVisible.value = false
    visibleMarkerIndices.value = []
    activeMarkerIndex.value = 0
    stopMarkerAnimation()
  },
)

onUnmounted(() => {
  stopMarkerAnimation()
})
</script>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}
.dark .custom-scrollbar::-webkit-scrollbar-thumb {
  background: #475569;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.ai-profile-dashboard {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.ai-profile-dashboard :deep(.dark\:bg-slate-900\/50),
.ai-profile-dashboard :deep(.dark\:bg-slate-900),
.ai-profile-dashboard :deep(.dark\:bg-slate-800),
.ai-profile-dashboard :deep(.dark\:bg-slate-800\/80),
.ai-profile-dashboard :deep(.dark\:bg-slate-700\/30),
.ai-profile-dashboard :deep(.dark\:bg-blue-900\/20) {
  background: rgba(255, 255, 255, 0.86) !important;
}

.ai-profile-dashboard :deep(.bg-white),
.ai-profile-dashboard :deep(.bg-slate-50\/50),
.ai-profile-dashboard :deep(.bg-slate-50),
.ai-profile-dashboard :deep(.bg-slate-100\/60),
.ai-profile-dashboard :deep(.bg-slate-200) {
  background: rgba(255, 255, 255, 0.86) !important;
  -webkit-backdrop-filter: blur(18px);
  backdrop-filter: blur(18px);
}

.ai-profile-dashboard :deep(.border-slate-100),
.ai-profile-dashboard :deep(.border-slate-200),
.ai-profile-dashboard :deep(.border-slate-200\/60),
.ai-profile-dashboard :deep(.dark\:border-slate-700),
.ai-profile-dashboard :deep(.dark\:border-slate-700\/80),
.ai-profile-dashboard :deep(.dark\:border-blue-800\/50) {
  border-color: rgba(0, 0, 0, 0.08) !important;
}

.ai-profile-dashboard :deep(.text-slate-900),
.ai-profile-dashboard :deep(.text-slate-800),
.ai-profile-dashboard :deep(.text-slate-700),
.ai-profile-dashboard :deep(.dark\:text-white),
.ai-profile-dashboard :deep(.dark\:text-slate-100),
.ai-profile-dashboard :deep(.dark\:text-slate-200),
.ai-profile-dashboard :deep(.dark\:text-slate-300) {
  color: #1d1d1f !important;
}

.ai-profile-dashboard :deep(.text-slate-600),
.ai-profile-dashboard :deep(.text-slate-500),
.ai-profile-dashboard :deep(.text-slate-400),
.ai-profile-dashboard :deep(.dark\:text-slate-400),
.ai-profile-dashboard :deep(.dark\:text-slate-500) {
  color: rgba(29, 29, 31, 0.6) !important;
}

.ai-profile-dashboard :deep(.text-blue-500),
.ai-profile-dashboard :deep(.text-blue-400),
.ai-profile-dashboard :deep(.text-\[\#2b6cf6\]) {
  color: #2b6cf6 !important;
}

.ai-profile-dashboard :deep(.bg-blue-500),
.ai-profile-dashboard :deep(.hover\:bg-blue-600:hover) {
  background: #2b6cf6 !important;
}

.ai-profile-dashboard :deep(.from-blue-400),
.ai-profile-dashboard :deep(.from-\[\#2b6cf6\]) {
  --tw-gradient-from: #2b6cf6 var(--tw-gradient-from-position) !important;
  --tw-gradient-to: rgba(43, 108, 246, 0) var(--tw-gradient-to-position) !important;
}

.ai-profile-dashboard :deep(.to-indigo-500),
.ai-profile-dashboard :deep(.to-\[\#0057b8\]) {
  --tw-gradient-to: #0057b8 var(--tw-gradient-to-position) !important;
}

.ai-profile-dashboard :deep(.rounded-xl),
.ai-profile-dashboard :deep(.rounded-2xl) {
  border-radius: 16px !important;
}

.ai-profile-dashboard :deep(.shadow-lg),
.ai-profile-dashboard :deep(.shadow-\[0_2px_12px_rgba\(0\,0\,0\,0\.04\)\]) {
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 2px 8px rgba(0, 0, 0, 0.035) !important;
}

.ai-profile-dashboard button {
  border-radius: 8px;
  font-weight: 600;
  transition:
    border-color 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 260ms cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 260ms cubic-bezier(0.25, 0.1, 0.25, 1);
}

.ai-profile-dashboard button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 5px 14px rgba(43, 108, 246, 0.18);
}
</style>
