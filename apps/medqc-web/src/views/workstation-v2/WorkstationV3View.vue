<template>
  <div class="h-full flex flex-col bg-slate-50 dark:bg-slate-900 overflow-hidden">
    <!-- Header -->
    <header class="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 flex-shrink-0 dark:bg-slate-900 dark:border-slate-800 z-10 transition-colors duration-300">
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-bold text-slate-800 dark:text-slate-100 flex items-center gap-2">
          <ClusterOutlined class="text-blue-500" />
          病案智能提取工作台
        </h1>
        <div class="h-4 w-[1px] bg-slate-300 dark:bg-slate-700"></div>
        <span class="text-xs text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-700">
          V3 (卡片版)
        </span>
      </div>
      
      <div class="flex items-center gap-3">
        <button 
          @click="toggleTheme" 
          class="p-2 text-slate-500 hover:text-blue-500 hover:bg-blue-50 rounded-full transition-colors dark:text-slate-400 dark:hover:text-blue-400 dark:hover:bg-blue-900/30"
          title="切换深色/浅色模式"
        >
          <BgColorsOutlined />
        </button>
      </div>
    </header>

    <!-- Card Grid Layout -->
    <div class="flex-1 overflow-y-auto p-6 md:p-8 custom-scrollbar">
      <!-- Advanced Filter Bar (EMR Style) -->
      <!-- Advanced Filter Bar (EMR Style - Clean White) -->
      <div class="mb-6 bg-transparent">
        <!-- Row 1: Search & Filters -->
        <div class="flex flex-wrap gap-4 items-center mb-6">
          <a-input-search
            placeholder="姓名/病案号/身份证"
            style="width: 260px"
            allow-clear
            size="large"
            class="global-search-input"
          />
          <a-select defaultValue="all" size="large" style="width: 140px" class="global-filter-select" :options="[{value:'all', label:'全部科室'},{value:'cardio', label:'心血管内科'},{value:'resp', label:'呼吸内科'},{value:'surg', label:'外科系统'}]"></a-select>
          <a-select defaultValue="this_week" size="large" style="width: 140px" class="global-filter-select" :options="[{value:'all', label:'不限时间'},{value:'today', label:'今日出院'},{value:'this_week', label:'本周出院'},{value:'this_month', label:'本月出院'}]"></a-select>
          <a-select defaultValue="all" size="large" style="width: 120px" class="global-filter-select" :options="[{value:'all', label:'全部医保'},{value:'employee', label:'市职工'},{value:'resident', label:'省医保'},{value:'rural', label:'新农合'},{value:'self', label:'全自费'}]"></a-select>
          
          <div class="ml-auto flex gap-2">
            <a-button size="large" class="flex items-center gap-1 text-slate-600 hover:text-slate-800"><ReloadOutlined /> 重置筛选</a-button>
          </div>
        </div>
        
        <!-- Row 2: Status Tabs -->
        <div class="border-b border-slate-200 dark:border-slate-700">
          <a-tabs v-model:activeKey="statusFilter" :tabBarStyle="{ marginBottom: 0, borderBottom: 'none' }">
            <a-tab-pane key="all" tab="全部病历"></a-tab-pane>
            <a-tab-pane key="pending" tab="未处理"></a-tab-pane>
            <a-tab-pane key="processing" tab="提取中"></a-tab-pane>
            <a-tab-pane key="completed" tab="提取完成"></a-tab-pane>
            <a-tab-pane key="warning" tab="重度缺陷"></a-tab-pane>
            <template #rightExtra>
              <a-button type="primary" class="bg-blue-500 hover:bg-blue-600 shadow-sm shadow-blue-500/30 flex items-center mb-2">
                <SyncOutlined /> 刷新队列
              </a-button>
            </template>
          </a-tabs>
        </div>
      </div>

      <!-- High Density Bed Cards Layout -->
      <!-- High Density Bed Cards Layout (Ultra-Compact EMR Style) -->
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 gap-3.5 pt-4">
        <div 
          v-for="record in demoRecords" 
          :key="record.id" 
          v-show="statusFilter === 'all' || record.status === statusFilter"
          @click="handleSelectRecord(record.id)"
          class="bg-white dark:bg-slate-800 rounded-xl shadow-[0_2px_12px_rgba(0,0,0,0.06)] hover:shadow-[0_8px_24px_rgba(0,0,0,0.12)] cursor-pointer transition-all duration-300 flex flex-col overflow-hidden border border-slate-200 dark:border-slate-700/80 group"
        >
          <div class="p-3.5 flex flex-col h-full relative z-0">
            <!-- 顶部信息区：床位/姓名 及 右侧小红点标签 -->
            <div class="flex items-start justify-between mb-2">
              <div class="flex items-baseline gap-2">
                <span class="font-black text-slate-800 dark:text-slate-100 text-xl tracking-tighter leading-none">
                  {{ record.bedNo }}<span class="text-xs font-bold text-slate-500 ml-0.5">床</span>
                </span>
                <span class="font-extrabold text-slate-800 dark:text-slate-200 text-base tracking-wide ml-1 leading-none">
                  {{ record.patientName }}
                </span>
              </div>
              
              <!-- Ultra-Refined Micro Pill Badge -->
              <div 
                class="px-1.5 py-[1px] rounded-[4px] text-[9px] font-bold border"
                :class="{
                  'bg-red-50 text-red-500 border-red-100 dark:bg-red-900/20 dark:text-red-400 dark:border-red-800/30': record.severity === 'critical',
                  'bg-orange-50 text-orange-500 border-orange-100 dark:bg-orange-900/20 dark:text-orange-400 dark:border-orange-800/30': record.severity === 'urgent',
                  'bg-blue-50 text-blue-500 border-blue-100 dark:bg-blue-900/20 dark:text-blue-400 dark:border-blue-800/30': record.severity === 'normal'
                }"
              >
                {{ record.severity === 'critical' ? '危' : record.severity === 'urgent' ? '重' : '普' }}
              </div>
            </div>

            <!-- 第2层: 年龄/性别 / 医保类型 -->
            <div class="flex items-center gap-2 mb-2.5 text-[11px] font-medium text-slate-500 dark:text-slate-400">
              <span class="">{{ record.gender }}/{{ record.age }}岁</span>
              <span class="bg-slate-50 dark:bg-slate-700/50 text-slate-400 dark:text-slate-500 px-1.5 py-[1px] rounded border border-slate-100 dark:border-slate-600/50">
                {{ record.insrType }}
              </span>
            </div>

            <!-- 第3灰色区块: 日期与天数统计 -->
            <div class="bg-slate-50/80 dark:bg-slate-800/40 rounded p-2 mb-1.5 flex flex-col justify-center border border-slate-50 dark:border-slate-700/30">
              <div class="flex justify-between items-center text-[10px] text-slate-400 dark:text-slate-500 mb-1">
                <span>入院: <span class="text-slate-600 dark:text-slate-300 font-mono ml-1">{{ record.admissionDate.substring(5) }}</span></span>
                <!-- 天数指示器在右侧对齐 -->
                <div class="font-bold text-slate-700 dark:text-slate-200 text-[11px]">{{ record.days }} 天</div>
              </div>
              <div class="flex items-center text-[10px] text-slate-400 dark:text-slate-500">
                <span>出院: <span class="text-slate-600 dark:text-slate-300 font-mono ml-1">{{ record.dischargeDate.substring(5) }}</span></span>
              </div>
            </div>

            <!-- 第4灰色区块: 诊断明细 (极限单行截断) -->
            <div class="bg-slate-50/80 dark:bg-slate-800/40 rounded p-2 text-[10px] text-slate-500 dark:text-slate-400 flex items-center h-[26px] overflow-hidden mb-3.5 border border-slate-50 dark:border-slate-700/30">
              <span class="shrink-0 mr-1.5 font-medium text-slate-400">诊断:</span>
              <span class="truncate font-medium text-slate-600 dark:text-slate-300" :title="record.mainDiagnosis">{{ record.mainDiagnosis }}</span>
            </div>
            
            <!-- 底部状态图标 -->
            <div class="mt-auto flex items-center">
              <span 
                v-if="record.status === 'completed'" 
                class="inline-flex items-center gap-1.5 text-[#10b981] bg-[#ecfdf5] border border-[#d1fae5] dark:bg-[#10b981]/10 dark:border-[#10b981]/20 px-2 py-0.5 rounded text-[10px] font-bold"
              >
                <CheckCircleOutlined /> 提取完成
              </span>
              <span 
                v-else-if="record.status === 'warning'" 
                class="inline-flex items-center gap-1.5 text-[#f59e0b] bg-[#fffbeb] border border-[#fef3c7] dark:bg-[#f59e0b]/10 dark:border-[#f59e0b]/20 px-2 py-0.5 rounded text-[10px] font-bold"
              >
                <WarningOutlined /> 存在缺陷
              </span>
              <span 
                v-else-if="record.status === 'processing'" 
                class="inline-flex items-center gap-1.5 text-[#3b82f6] bg-[#eff6ff] border border-[#dbeafe] dark:bg-[#3b82f6]/10 dark:border-[#3b82f6]/20 px-2 py-0.5 rounded text-[10px] font-bold"
              >
                <SyncOutlined spin /> AI 提取中
              </span>
              <span 
                v-else 
                class="inline-flex items-center gap-1.5 text-slate-400 bg-slate-50 border border-slate-100 dark:bg-slate-800 dark:border-slate-700/80 px-2 py-0.5 rounded text-[10px] font-bold group-hover:bg-white transition-colors"
              >
                <InboxOutlined /> 待发提取
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- EMR Workspace Drawer -->
    <a-drawer
      v-model:open="drawerVisible"
      :title="null"
      placement="right"
      width="95vw"
      :closable="false"
      class="emr-workspace-drawer"
      :bodyStyle="{ padding: 0 }"
    >
      <div v-if="selectedRecord" class="h-full flex flex-col bg-slate-50 dark:bg-slate-900">
        <!-- Drawer Header -->
        <header class="h-14 bg-white border-b border-slate-100 dark:bg-slate-800 dark:border-slate-700 flex items-center justify-between px-6 flex-shrink-0 z-10 transition-colors duration-300">
          <div class="flex items-center gap-6">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center text-white font-bold text-base shadow-sm">
                {{ selectedRecord.patientName.charAt(0) }}
              </div>
              <div class="flex items-center gap-3">
                <span class="font-bold text-slate-800 dark:text-slate-200 text-lg tracking-wide">{{ selectedRecord.patientName }}</span>
                <span class="text-[11px] text-slate-400 font-mono tracking-wider bg-slate-50 dark:bg-slate-800 px-2 py-0.5 rounded border border-slate-100 dark:border-slate-700">NO: {{ selectedRecord.id }}</span>
              </div>
            </div>
            <div class="h-5 w-[1px] bg-slate-200 dark:bg-slate-700"></div>
            <div class="flex items-center gap-5 text-xs text-slate-500 dark:text-slate-400 font-medium">
              <span class="flex items-center gap-1.5"><BankOutlined class="text-slate-400" /> {{ selectedRecord.department }}</span>
              <span class="flex items-center gap-1.5"><CalendarOutlined class="text-slate-400" /> 入院: {{ selectedRecord.admissionDate }}</span>
              <span class="flex items-center gap-1.5"><ClockCircleOutlined class="text-slate-400" /> {{ selectedRecord.days }}天</span>
            </div>
          </div>
          
          <div class="flex items-center gap-4">
            <button 
              @click="extractStructuredData"
              :disabled="!hasMedicalText || isExtracting"
              class="bg-blue-500 hover:bg-blue-600 disabled:bg-blue-300 disabled:cursor-not-allowed text-white px-5 py-1.5 rounded-md text-sm font-bold transition-all shadow-sm shadow-blue-500/20 flex items-center gap-2"
            >
              <SyncOutlined v-if="isExtracting" spin />
              <ThunderboltOutlined v-else />
              {{ isExtracting ? `AI 提取中 ${Math.round(extractionProgress?.percent || 0)}%` : '启动 AI 提取' }}
            </button>
            <div class="w-[1px] h-4 bg-slate-200 dark:bg-slate-700"></div>
            <button 
              @click="drawerVisible = false"
              class="text-slate-400 hover:text-slate-600 transition-colors dark:text-slate-500 dark:hover:text-slate-300 flex items-center gap-1 text-sm font-medium"
            >
              <CloseOutlined /> 关闭
            </button>
          </div>
        </header>

        <!-- Split Workspace Layout -->
        <div class="flex-1 flex overflow-hidden bg-slate-50 dark:bg-slate-900">
          <!-- Left: Medical Record Source Text -->
          <div
            :style="{ width: leftCollapsed ? '0px' : '45%' }"
            class="border-r border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col flex-shrink-0 z-10 shadow-[2px_0_8px_rgba(0,0,0,0.02)] transition-all duration-300 overflow-hidden"
          >
            <div class="h-12 border-b border-slate-100 dark:border-slate-800 flex items-center px-6 bg-white dark:bg-slate-900 flex-shrink-0">
               <FileTextOutlined class="text-blue-500 mr-2 text-lg" />
               <span class="font-bold text-slate-700 dark:text-slate-200 whitespace-nowrap">病历原文</span>
            </div>
            <div class="flex-1 overflow-y-auto px-8 py-6 custom-scrollbar">
               <div class="max-w-3xl mx-auto">
                 <pre class="font-sans text-[13px] leading-[1.8] text-slate-700 dark:text-slate-300 whitespace-pre-wrap word-break-all">{{ medicalText }}</pre>
               </div>
            </div>
          </div>

          <!-- Divider with Collapse Toggle -->
          <div class="w-5 flex-shrink-0 relative flex items-center justify-center group cursor-col-resize bg-slate-100/50 dark:bg-slate-800/50 hover:bg-blue-50 dark:hover:bg-blue-900/20 transition-colors border-x border-slate-200/40 dark:border-slate-700/40">
            <button
              @click="leftCollapsed = !leftCollapsed"
              class="absolute z-20 w-6 h-12 bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 rounded-md shadow-md flex items-center justify-center text-slate-400 hover:text-blue-500 hover:border-blue-300 dark:hover:text-blue-400 transition-all hover:shadow-lg"
              :title="leftCollapsed ? '展开病历原文' : '折叠病历原文'"
            >
              <span class="text-[11px] font-bold transition-transform duration-300" :class="leftCollapsed ? 'rotate-0' : 'rotate-180'">❯</span>
            </button>
          </div>

          <!-- Right: AI Tools & Extraction Results -->
          <div class="flex-1 bg-slate-50/50 flex flex-col flex-shrink-0 dark:bg-slate-900/50 relative min-w-0">
            <!-- Tabs Header -->
            <div class="h-12 border-b border-slate-200/80 dark:border-slate-800 flex items-end px-4 gap-4 bg-white dark:bg-slate-800/80 flex-shrink-0">
              <button 
                v-for="tab in tabs" 
                :key="tab.key"
                @click="activeTab = tab.key"
                class="pb-3 text-sm font-bold border-b-[3px] transition-all relative px-2"
                :class="[
                  activeTab === tab.key 
                    ? 'border-blue-600 text-blue-600 dark:text-blue-400 dark:border-blue-500' 
                    : 'border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-300'
                ]"
              >
                <!-- Badge dot if needed -->
                <span v-if="tab.badge" class="absolute top-0 right-0 flex h-2 w-2">
                  <span :class="`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${tab.badgeColor || 'bg-blue-400'}`"></span>
                  <span :class="`relative inline-flex rounded-full h-2 w-2 ${tab.badgeColor || 'bg-blue-500'}`"></span>
                </span>
                <component :is="tab.icon" class="mr-1.5" />
                {{ tab.label }}
              </button>
            </div>

            <!-- Tab Content Area -->
            <div class="flex-1 overflow-y-auto custom-scrollbar relative">
              <!-- 1. 首页装配 Tab -->
              <div v-show="activeTab === 'frontpage'" class="h-full relative">
                <!-- Loading Overlay for extraction -->
                <div v-if="isExtracting" class="absolute inset-0 z-30 flex flex-col items-center justify-center bg-white/90 dark:bg-slate-900/90 backdrop-blur-sm">
                  <div class="relative w-24 h-24 mb-6">
                    <svg class="w-full h-full animate-spin text-blue-500/20" viewBox="0 0 100 100" fill="none">
                      <circle cx="50" cy="50" r="45" stroke="currentColor" stroke-width="8"/>
                      <path d="M50 5 a45 45 0 0 1 45 45" stroke="currentColor" stroke-width="8" class="text-blue-500 stroke-current"/>
                    </svg>
                    <div class="absolute inset-0 flex items-center justify-center">
                      <div class="w-12 h-12 bg-white dark:bg-slate-800 rounded-full shadow-lg flex items-center justify-center">
                        <RobotOutlined class="text-xl text-blue-500" />
                      </div>
                    </div>
                  </div>
                  <h3 class="text-lg font-bold text-slate-800 dark:text-white mb-2">AI 智能提取中...</h3>
                  <p class="text-sm text-slate-500 dark:text-slate-400 mb-6 text-center max-w-[250px]">
                    正在阅读病历记录并提取诊断、手术等首页数据结构
                  </p>
                  
                  <div class="w-64">
                    <div class="flex justify-between text-xs text-slate-500 dark:text-slate-400 mb-2">
                      <span>{{ extractionStatusText }}</span>
                      <span class="font-mono">{{ Math.round(extractionProgress?.percent || 0) }}%</span>
                    </div>
                    <div class="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                      <div class="h-full bg-blue-500 rounded-full transition-all duration-300 ease-out" :style="{ width: `${extractionProgress?.percent || 0}%` }"></div>
                    </div>
                  </div>
                </div>

                <StructuredDataView 
                  v-else
                  :frontpage="parsedData"
                  :hasMedicalText="hasMedicalText"
                  :extracting="isExtracting"
                  :extractionProgress="extractionProgress as any"
                  :extractionStatus="extractionStatus"
                  @extract="extractStructuredData"
                  @codeChange="handleCodeChange"
                />
              </div>

              <!-- 2. AI 画像 Tab -->
              <div v-if="activeTab === 'profile'" class="h-full flex-1 overflow-y-auto w-full custom-scrollbar">
                <AIProfileDashboard
                  :medicalText="medicalText"
                  :frontpage="parsedData"
                />
              </div>

              <!-- 3. AI 质控 Tab (Placeholder) -->
              <div v-show="activeTab === 'qc'" class="p-6">
                <div class="border border-red-100 bg-red-50/50 rounded-xl p-5 mb-5 dark:border-red-900/30 dark:bg-red-900/10">
                  <h3 class="text-red-700 font-bold mb-2 flex items-center gap-2"><WarningOutlined /> 发现 1 个潜在缺陷</h3>
                  <p class="text-sm text-red-600/80">入院记录提示有高血压病史，但在出院诊断中未明确记录高血压相关诊断。</p>
                </div>
                <div class="border border-amber-100 bg-amber-50/50 rounded-xl p-5 dark:border-amber-900/30 dark:bg-amber-900/10">
                  <h3 class="text-amber-700 font-bold mb-2 flex items-center gap-2"><WarningOutlined /> 发现 1 个编码分歧</h3>
                  <p class="text-sm text-amber-600/80">主诉描述了“不稳定型心绞痛”，提取结果将“冠状动脉粥样硬化性心脏病”作为主诊断，建议复核。</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { 
  ThunderboltOutlined, 
  RobotOutlined, 
  WarningOutlined,
  AppstoreOutlined,
  SyncOutlined,
  BgColorsOutlined,
  ClusterOutlined,
  MedicineBoxOutlined,
  SafetyCertificateOutlined,
  ClockCircleOutlined,
  CalendarOutlined,
  BankOutlined,
  CloseOutlined,
  FileTextOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  InboxOutlined,
  AreaChartOutlined
} from '@ant-design/icons-vue'

// 数据源 & 提取逻辑
import { getBuiltinTestCases } from '@/views/demo/frontpage/data/testCases'
import { useMedicalTextExtraction, type DemoCaseLike } from '@/views/demo/frontpage/composables/useMedicalTextExtraction'
import StructuredDataView from '@/views/demo/frontpage/components/StructuredDataView.vue'
import AIProfileDashboard from '@/views/demo/frontpage/components/AIProfileDashboard.vue'
import type { DraftRecord } from './components/DraftListSidebar.vue'

// ---------- Theme ----------
const isDark = ref(false)
const toggleTheme = () => {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('medqc-theme', isDark.value ? 'dark' : 'light')
}
onMounted(() => {
  const saved = localStorage.getItem('medqc-theme')
  isDark.value = saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.classList.toggle('dark', isDark.value)
})

// ---------- 测试病历数据 ----------
const builtinCases = getBuiltinTestCases()

// UI State
const drawerVisible = ref(false)
const selectedRecordId = ref<string | null>(null)
const statusFilter = ref('all')
const leftCollapsed = ref(false)

interface PatientCardRecord {
  id: string
  patientName: string
  gender: string
  age: number
  bedNo: string
  severity: 'critical' | 'urgent' | 'normal'
  department: string
  doctor: string
  insrType: string
  days: number
  admissionDate: string
  dischargeDate: string
  mainDiagnosis: string
  status: 'pending' | 'processing' | 'completed' | 'warning'
  caseIndex: number // 指向 builtinCases 的索引
}

const demoRecords = ref<PatientCardRecord[]>([
  { id: 'ZY2026110034', patientName: '张三', gender: '男', age: 58, bedNo: '03', severity: 'urgent', department: '心血管内科', doctor: '李建国', insrType: '市职工', days: 5, admissionDate: '2026-01-01', dischargeDate: '2026-01-06', mainDiagnosis: '冠心病、不稳定型心绞痛...', status: 'completed', caseIndex: 0 },
  { id: 'ZY2026110089', patientName: '王五', gender: '男', age: 35, bedNo: '22', severity: 'normal', department: '肛肠外科', doctor: '赵铁柱', insrType: '省医保', days: 8, admissionDate: '2026-01-05', dischargeDate: '2026-01-13', mainDiagnosis: '肛瘘伴感染...', status: 'warning', caseIndex: 1 },
  { id: 'ZY2026110112', patientName: '李四', gender: '女', age: 62, bedNo: '12', severity: 'critical', department: '呼吸内科', doctor: '孙尚香', insrType: '新农合', days: 12, admissionDate: '2026-01-10', dischargeDate: '2026-01-22', mainDiagnosis: '慢性阻塞性肺疾病急性加重...', status: 'pending', caseIndex: 0 },
  { id: 'ZY2026110145', patientName: '赵六', gender: '男', age: 45, bedNo: '08', severity: 'normal', department: '消化内科', doctor: '刘玄德', insrType: '市职工', days: 3, admissionDate: '2026-01-15', dischargeDate: '2026-01-18', mainDiagnosis: '急性胃肠炎伴脱水...', status: 'pending', caseIndex: 1 },
  { id: 'ZY2026110167', patientName: '钱七', gender: '女', age: 28, bedNo: '05', severity: 'urgent', department: '妇产科', doctor: '黄月英', insrType: '自费', days: 6, admissionDate: '2026-01-18', dischargeDate: '2026-01-24', mainDiagnosis: '先兆流产...', status: 'processing', caseIndex: 0 },
  { id: 'ZY2026110188', patientName: '孙八', gender: '男', age: 71, bedNo: '33', severity: 'critical', department: '神经内科', doctor: '关云长', insrType: '离休干部', days: 15, admissionDate: '2026-01-20', dischargeDate: '2026-02-04', mainDiagnosis: '急性脑梗死，偏瘫...', status: 'pending', caseIndex: 1 },
  { id: 'ZY2026110201', patientName: '周九', gender: '女', age: 50, bedNo: '18', severity: 'normal', department: '内分泌科', doctor: '张翼德', insrType: '市职工', days: 7, admissionDate: '2026-01-22', dischargeDate: '2026-01-29', mainDiagnosis: '2型糖尿病伴酮症...', status: 'completed', caseIndex: 0 },
  { id: 'ZY2026110234', patientName: '吴十', gender: '男', age: 19, bedNo: '41', severity: 'urgent', department: '骨科', doctor: '马孟起', insrType: '居民医保', days: 10, admissionDate: '2026-01-25', dischargeDate: '2026-02-04', mainDiagnosis: '右侧胫腓骨骨折...', status: 'warning', caseIndex: 1 },
])



// Extraction State
const currentDemoCase = ref<DemoCaseLike | null>(null)
const medicalText = ref('')
const selectedRecord = computed(() => demoRecords.value.find(r => r.id === selectedRecordId.value))

// ---------- Tabs ----------
const activeTab = ref('frontpage')
const tabs = [
  { key: 'frontpage', label: '首页自动装配', icon: AppstoreOutlined },
  { key: 'profile', label: 'AI智能画像', icon: AreaChartOutlined },
  { key: 'qc', label: '病历内涵质控', icon: SafetyCertificateOutlined, badge: true, badgeColor: 'bg-red-500' }
]

// ---------- 提取逻辑 ----------
const {
  extracting: isExtracting,
  extractionProgress,
  extractionStatus,
  extractStructuredData: _doExtract
} = useMedicalTextExtraction({
  demoCase: currentDemoCase,
})

const parsedData = computed(() => currentDemoCase.value?.frontpage || null)
const hasMedicalText = computed(() => medicalText.value.trim().length > 0)
const extractionStatusText = computed(() => {
  const mod = extractionProgress.value?.currentModule
  return mod || extractionStatus.value
})

const extractStructuredData = async () => {
  if (!selectedRecordId.value) return
  const idx = demoRecords.value.findIndex(r => r.id === selectedRecordId.value)
  if (idx !== -1) demoRecords.value[idx].status = 'processing'

  await _doExtract()

  if (idx !== -1) {
    demoRecords.value[idx].status = currentDemoCase.value?.frontpage?.basic_info?.patient_name ? 'completed' : 'warning'
  }
}

// ---------- 病历选择 ----------
const handleSelectRecord = (id: string) => {
  selectedRecordId.value = id
  const listIdx = demoRecords.value.findIndex(r => r.id === id)
  const record = demoRecords.value[listIdx]
  const caseData = builtinCases[record.caseIndex] || builtinCases[0]

  medicalText.value = caseData.medical_text
  currentDemoCase.value = {
    case_id: id,
    description: caseData.description,
    medical_text: caseData.medical_text,
    frontpage: null
  }
  activeTab.value = 'frontpage'
  drawerVisible.value = true // Open Drawer
}

const handleCodeChange = (field: string, value: string) => {
  console.log(`Code changed for ${field}: ${value}`)
}
</script>

<style>
/* 移除默认 padding 让左右分栏紧贴弹窗边缘 */
.emr-workspace-drawer .ant-drawer-body {
  padding: 0 !important;
  overflow: hidden;
}
.emr-workspace-drawer .ant-drawer-header {
  display: none; /* We use our own custom header */
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}
.custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(203, 213, 225, 0.5);
  border-radius: 4px;
}
.custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(148, 163, 184, 0.8);
}

:deep(.dark) .custom-scrollbar::-webkit-scrollbar-thumb {
  background-color: rgba(71, 85, 105, 0.5);
}
:deep(.dark) .custom-scrollbar::-webkit-scrollbar-thumb:hover {
  background-color: rgba(100, 116, 139, 0.8);
}

/* 覆盖 Ant Design Tabs 的基础下边框，使其融入白底 */
.ant-tabs-nav::before {
  border-bottom: none !important;
}

/* 全局搜索和筛选框统一样式 */
.global-search-input .ant-input,
.global-filter-select .ant-select-selector {
  border-radius: 8px !important;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05) !important;
  border-color: #e2e8f0 !important;
}
.global-search-input .ant-input:focus,
.global-search-input .ant-input:hover,
.global-filter-select:hover .ant-select-selector,
.global-filter-select-focused .ant-select-selector {
  border-color: #3b82f6 !important;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
}
</style>
