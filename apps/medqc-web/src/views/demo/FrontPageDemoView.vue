<template>
  <div class="bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-100 min-h-screen flex overflow-hidden transition-colors duration-300">
    <div v-if="!isAuthorized" class="fixed inset-0 z-[9999] flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
      <div class="w-full max-w-md bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-slate-200 dark:border-slate-700 p-8">
        <h2 class="text-xl font-semibold text-slate-800 dark:text-white mb-2">请输入访问密码</h2>
        <p class="text-sm text-slate-500 dark:text-slate-400 mb-6">需要输入密码才能进入页面</p>
        <a-input-password
          v-model:value="passwordInput"
          placeholder="请输入密码"
          size="large"
          @pressEnter="verifyPassword"
        />
        <p v-if="passwordError" class="text-sm text-red-500 mt-3">{{ passwordError }}</p>
        <div class="mt-6 flex justify-end">
          <a-button type="primary" size="large" @click="verifyPassword">进入</a-button>
        </div>
      </div>
    </div>
    <!-- Sidebar -->
    <!-- Sidebar -->
    <aside :class="['bg-white dark:bg-slate-800 flex-shrink-0 flex flex-col justify-between border-r border-slate-200 dark:border-slate-700 hidden md:flex z-20 transition-all duration-300', isSidebarCollapsed ? 'w-20' : 'w-64']">
      <div>
        <!-- Sidebar Header with Toggle -->
        <div class="h-16 flex items-center justify-center px-4 border-b border-slate-100 dark:border-slate-700/50">
           <button @click="isSidebarCollapsed = !isSidebarCollapsed" class="text-slate-400 hover:text-blue-500 transition-colors">
              <MenuUnfoldOutlined v-if="isSidebarCollapsed" class="text-lg" />
              <MenuFoldOutlined v-else class="text-lg" />
           </button>
        </div>

        <div class="p-4 flex flex-col items-center border-b border-slate-100 dark:border-slate-700/50">
          <div class="relative transition-transform duration-300" :class="isSidebarCollapsed ? 'scale-75' : ''">
            <div class="w-16 h-16 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-2xl shadow-lg border-4 border-white dark:border-slate-600 overflow-hidden">
               <UserOutlined class="text-slate-400" />
            </div>
            <div class="absolute bottom-0 right-0 w-3.5 h-3.5 bg-green-500 rounded-full border-2 border-white dark:border-slate-800"></div>
          </div>
          <div v-if="!isSidebarCollapsed" class="mt-3 text-center transition-opacity duration-300">
             <h2 class="text-lg font-bold text-slate-800 dark:text-white">张医生</h2>
             <p class="text-xs text-slate-500 dark:text-slate-400">首席编码员</p>
          </div>
        </div>

        <nav class="p-3 space-y-1 mt-2">
	          <a @click="goToWorkbench" :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer group', isSidebarCollapsed ? 'justify-center' : '', currentView === 'workbench' ? 'bg-blue-500 text-white shadow-md' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400']">
	            <AppstoreOutlined class="text-[20px]" />
	            <span v-if="!isSidebarCollapsed" class="font-medium text-sm">工作台</span>
	          </a>
          
          <div class="my-2 border-t border-slate-100 dark:border-slate-700 mx-2"></div>
          
          <!-- DRG/DIP 折叠菜单组 -->
          <div class="space-y-1">
            <a @click="drgMenuExpanded = !drgMenuExpanded" :class="['flex items-center justify-between px-3 py-3 rounded-xl transition-all cursor-pointer group', isSidebarCollapsed ? 'justify-center' : '', ['pre-analysis', 'monitoring', 'payment', 'analysis'].includes(currentView) ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400']">
              <div class="flex items-center gap-3">
                <MedicineBoxOutlined class="text-[20px]" />
                <span v-if="!isSidebarCollapsed" class="font-medium text-sm">DRG/DIP</span>
              </div>
              <DownOutlined v-if="!isSidebarCollapsed" :class="['text-xs transition-transform', drgMenuExpanded ? 'rotate-180' : '']" />
            </a>
            
            <div v-show="drgMenuExpanded && !isSidebarCollapsed" class="pl-4 space-y-1">
              <!-- 6.1 事前分析 -->
              <a @click="currentView = 'pre-analysis'" :class="['flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all cursor-pointer group', currentView === 'pre-analysis' ? 'bg-blue-500 text-white shadow-md' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400']">
                <FileSearchOutlined class="text-[18px]" />
                <span class="font-medium text-sm">事前分析</span>
              </a>
              
              <!-- 6.2 事中分析 (可展开) -->
              <div class="space-y-1">
                <a @click="midAnalysisExpanded = !midAnalysisExpanded" :class="['flex items-center justify-between px-3 py-2.5 rounded-xl transition-all cursor-pointer group', ['monitoring', 'payment'].includes(currentView) ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400']">
                  <div class="flex items-center gap-3">
                    <SafetyCertificateOutlined class="text-[18px]" />
                    <span class="font-medium text-sm">事中分析</span>
                  </div>
                  <RightOutlined :class="['text-xs transition-transform', midAnalysisExpanded ? 'rotate-90' : '']" />
                </a>
                <div v-show="midAnalysisExpanded" class="pl-5 space-y-1">
                  <a @click="currentView = 'monitoring'" :class="['flex items-center gap-3 px-3 py-2 rounded-lg transition-all cursor-pointer', currentView === 'monitoring' ? 'bg-blue-500 text-white shadow-sm' : 'hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400']">
                    <span class="text-sm">事中监控</span>
                  </a>
                  <a @click="currentView = 'payment'" :class="['flex items-center gap-3 px-3 py-2 rounded-lg transition-all cursor-pointer', currentView === 'payment' ? 'bg-blue-500 text-white shadow-sm' : 'hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400']">
                    <span class="text-sm">付费监测</span>
                  </a>
                </div>
              </div>
              
              <!-- 6.3 事后分析 -->
              <a @click="currentView = 'analysis'" :class="['flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all cursor-pointer group', currentView === 'analysis' ? 'bg-blue-500 text-white shadow-md' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400']">
                <BarChartOutlined class="text-[18px]" />
                <span class="font-medium text-sm">事后分析</span>
              </a>
            </div>
          </div>
          
          <div class="my-2 border-t border-slate-100 dark:border-slate-700 mx-2"></div>

          <a @click="currentView = 'testcases'" :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer group', isSidebarCollapsed ? 'justify-center' : '', currentView === 'testcases' ? 'bg-blue-500 text-white shadow-md' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400']">
            <FolderOpenOutlined class="text-[20px]" :class="currentView === 'testcases' ? '' : 'group-hover:text-blue-500'" />
            <span v-if="!isSidebarCollapsed" class="font-medium text-sm">测试病历列表</span>
          </a>
          <a @click="currentView = 'upload'" :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer group', isSidebarCollapsed ? 'justify-center' : '', currentView === 'upload' ? 'bg-blue-500 text-white shadow-md' : 'hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400']">
            <CloudUploadOutlined class="text-[20px]" :class="currentView === 'upload' ? '' : 'group-hover:text-blue-500'" />
            <span v-if="!isSidebarCollapsed" class="font-medium text-sm">数据上传</span>
          </a>
          <a :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer group hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400', isSidebarCollapsed ? 'justify-center' : '']">
            <SettingOutlined class="text-[20px] group-hover:text-blue-500" />
            <span v-if="!isSidebarCollapsed" class="font-medium text-sm">系统设置</span>
          </a>
        </nav>
      </div>
      <div class="p-3">
        <a :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer text-slate-500 dark:text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/10', isSidebarCollapsed ? 'justify-center' : '']">
          <LogoutOutlined class="text-[20px]" />
          <span v-if="!isSidebarCollapsed" class="font-medium text-sm">退出登录</span>
        </a>
      </div>
    </aside>

    <main class="flex-1 flex flex-col h-screen overflow-hidden relative">
      <div class="absolute top-0 right-0 w-full h-64 bg-gradient-to-b from-blue-50/50 to-transparent dark:from-blue-900/10 dark:to-transparent pointer-events-none -z-10"></div>
      
      <!-- Header -->
      <!-- Header Removed -->
      <div class="h-6"></div>
      
      <!-- Content Area -->
      <div class="flex-1 overflow-hidden px-8 pb-8">
        <div v-if="currentView === 'workbench'" class="h-full w-full">
          <div class="flex h-full" ref="containerRef">
          
	          <!-- Left Column: Medical Record -->
	          <div class="flex flex-col gap-6 overflow-y-auto custom-scrollbar pr-2 transition-all duration-700" :style="{ width: isExpanded ? '0%' : leftPanelWidth + '%', opacity: isExpanded ? 0 : 1, paddingRight: isExpanded ? '0' : '' }">
	            <MedicalRecordPanel
	              :loading="loading"
	              :medical-text="demoCase?.medical_text"
	              :test-cases="testCases"
	              @selectTestCase="loadDemoCase"
	            />
	          </div>

          <!-- Resizable Splitter -->
          <div 
            v-show="!isExpanded"
            class="w-2 flex-shrink-0 cursor-col-resize group flex items-center justify-center hover:bg-blue-100 dark:hover:bg-blue-900/30 transition-colors mx-1 rounded"
            @mousedown="startResize"
          >
            <div class="w-1 h-16 bg-slate-200 dark:bg-slate-600 rounded-full group-hover:bg-blue-400 dark:group-hover:bg-blue-500 transition-colors"></div>
          </div>

	          <!-- Right Column: Results & Tools -->
	          <div class="flex flex-col gap-4 h-full pl-2 transition-all duration-700" :style="{ width: isExpanded ? '100%' : (100 - leftPanelWidth) + '%' }">
	            <!-- Back (collapse expanded view) -->
	            <div v-if="isExpanded" class="flex items-center">
	              <button
	                class="inline-flex items-center gap-2 px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:border-slate-300 dark:hover:border-slate-600 transition-colors shadow-sm"
	                @click="collapseExpanded"
	              >
	                <ArrowLeftOutlined class="text-base" /> 返回
	              </button>
	            </div>

	            <!-- Tabs -->
	            <FrontPageResultTabs
	              :tabs="tabs"
	              :active-tab="activeTab"
	              :is-expanded="isExpanded"
              @update:activeTab="activeTab = $event"
              @toggleExpand="toggleExpand"
            />
            
            <!-- Main Content Area -->
            <div class="flex-1 bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 flex flex-col overflow-hidden">
              <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center">
                <h3 class="font-semibold text-slate-800 dark:text-white">{{ activeTabLabel }}</h3>
                <button 
                  v-if="activeTab === 'structured' || activeTab === 'print'" 
                  @click="handlePrint"
                  class="text-blue-500 hover:text-blue-600 text-sm font-medium flex items-center gap-1"
                >
                  <PrinterOutlined class="text-base" /> 打印
                </button>
              </div>
              
              <div class="flex-1 p-6 relative overflow-hidden flex flex-col">
                 <!-- Background Grid -->
                 <div class="absolute inset-0 bg-grid-slate-100 [mask-image:linear-gradient(0deg,white,rgba(255,255,255,0.6))] dark:bg-grid-slate-700/25 dark:[mask-image:linear-gradient(0deg,rgba(255,255,255,0.1),rgba(255,255,255,0.5))] pointer-events-none -z-0"></div>
                 
                 <div class="relative z-10 overflow-y-auto custom-scrollbar" style="max-height: calc(100vh - 280px)">
                    
                    <!-- Content: Structured -->
	                    <StructuredDataView
	                      v-if="activeTab === 'structured'"
	                      :extracting="extracting"
	                      :frontpage="frontpage"
	                      :has-medical-text="!!demoCase?.medical_text"
	                      @extract="extractStructuredData"
	                    />

                    <!-- Content: AI Analysis -->
                    <AIProfileDashboard v-else-if="activeTab === 'profile'" :medical-text="demoCase?.medical_text" :frontpage="frontpage" @expand="onProfileExpand" />
                    <!-- Content: HM Template -->
                    <div v-else-if="activeTab === 'hm'" class="h-full">
                      <HmFrontpagePreview :draft="frontpage" class="h-full" />
                    </div>
                    
	                    <!-- Content: Insurance -->
	                     <InsuranceClaimView v-else-if="activeTab === 'insurance'" :insurance-claim="insuranceClaim" />
	                     
	                 </div>
	              </div>
              
              <!-- Footer Actions -->
              <div class="px-6 py-4 border-t border-slate-100 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/30 flex justify-between items-center rounded-b-2xl">
                <div class="flex items-center gap-3">
                  <button 
                    v-if="frontpage && activeTab === 'structured'"
                    @click="fillToFrontpage"
                    class="px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600 text-white rounded-lg text-sm font-medium transition-all shadow-sm hover:shadow flex items-center gap-2"
                  >
                    <FormOutlined class="text-base" />
                    回填到病案首页
                  </button>
                </div>
                <div class="flex items-center gap-3">
                  <button class="px-4 py-2 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white font-medium transition-colors">清空</button>
                  <button class="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 rounded-lg text-sm font-medium cursor-not-allowed">导出 CSV</button>
                </div>
              </div>
            </div>
            
          </div>
        </div>
        
        <!-- Recent Cases Table -->
        <div class="mt-6 bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 p-6">
          <div class="flex items-center justify-between mb-4">
            <h3 class="font-semibold text-slate-800 dark:text-white flex items-center gap-2">
              <HistoryOutlined class="text-slate-400" /> 最近病案
            </h3>
            <a class="text-sm text-blue-500 hover:underline cursor-pointer">查看全部</a>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm text-left text-slate-500 dark:text-slate-400">
              <thead class="text-xs text-slate-700 uppercase bg-slate-50 dark:bg-slate-700/50 dark:text-slate-300">
	                <tr>
	                  <th class="px-4 py-3 rounded-l-lg font-semibold">病案号</th>
	                  <th class="px-4 py-3 font-semibold">科室</th>
	                  <th class="px-4 py-3 font-semibold">出院日期</th>
	                  <th class="px-4 py-3 rounded-r-lg font-semibold">状态</th>
	                </tr>
	              </thead>
	              <tbody>
	                <tr class="bg-white dark:bg-slate-800 border-b dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
	                  <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">#2026010001</td>
	                  <td class="px-4 py-3">心内科</td>
	                  <td class="px-4 py-3">2026-01-04</td>
	                  <td class="px-4 py-3"><span class="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-green-900 dark:text-green-300">已完成</span></td>
	                </tr>
	                <tr class="bg-white dark:bg-slate-800 border-b dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
	                  <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">#2026010002</td>
	                  <td class="px-4 py-3">神经内科</td>
	                  <td class="px-4 py-3">2026-01-03</td>
	                  <td class="px-4 py-3"><span class="bg-yellow-100 text-yellow-800 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-yellow-900 dark:text-yellow-300">审核中</span></td>
	                </tr>
	              </tbody>
	            </table>
	          </div>
	        </div>
        </div>

        <!-- 事前分析：自包含的完整功能 -->
        <PreAnalysisView v-else-if="currentView === 'pre-analysis'" />

        <InProcessMonitoringView v-else-if="currentView === 'monitoring'" />
        <PaymentMonitoringView v-else-if="currentView === 'payment'" />
        <PostEventAnalysisView v-else-if="currentView === 'analysis'" :session-id="selectedSessionId" :batch-id="selectedBatchId" />
        <TestCaseListView 
          v-else-if="currentView === 'testcases'" 
          :test-cases="testCases"
          @back="currentView = 'workbench'"
          @loadCase="handleLoadTestCase"
          @createCase="handleCreateTestCase"
          @updateCase="handleUpdateTestCase"
          @deleteCase="handleDeleteTestCase"
        />
        <ExcelUploadView
          v-else-if="currentView === 'upload'"
          @back="currentView = 'workbench'"
          @goAnalysis="handleGoAnalysis"
        />
      </div>
	      
	    </main>
	  </div>
	</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  AppstoreOutlined,
  FolderOpenOutlined,
  BarChartOutlined,
	  SettingOutlined,
	  LogoutOutlined,
	  CheckCircleOutlined,
	  ThunderboltOutlined,
		  PrinterOutlined,
		  UserOutlined,
		  HistoryOutlined,
		  ArrowLeftOutlined,
		  MenuFoldOutlined,
		  MenuUnfoldOutlined,
		  DollarOutlined,
		  CalculatorOutlined,
		  RiseOutlined,
	  FallOutlined,
  ExclamationCircleOutlined,
  CloudUploadOutlined,
  QuestionCircleOutlined,
  SafetyCertificateOutlined,
  DollarCircleOutlined,
  MedicineBoxOutlined,
  DownOutlined,
  RightOutlined,
  FileSearchOutlined,
  FormOutlined
} from '@ant-design/icons-vue'
	import { message } from 'ant-design-vue'
	import HmFrontpagePreview from '@/components/frontpage/HmFrontpagePreview.vue'
		import { 
		  AIProfileDashboard, 
		  FrontPageResultTabs, 
		  InsuranceClaimView, 
		  MedicalRecordPanel, 
		  StructuredDataView,
		  InProcessMonitoringView,
		  PaymentMonitoringView,
		  PostEventAnalysisView,
		  TestCaseListView,
		  ExcelUploadView,
		  PreAnalysisView
		} from '@/views/demo/frontpage/components'
		import { useMedicalTextExtraction, useDRGGrouping } from '@/views/demo/frontpage/composables'

// Basic Types
interface DemoCase {
  case_id: string
  description?: string
  medical_text?: string
  frontpage?: any
  insurance_claim?: any
}

// State
const activeTab = ref('structured')
const currentView = ref('workbench')
const loading = ref(false)
const demoCase = ref<DemoCase | null>(null)
const isExpanded = ref(false)
const isDark = ref(false)
const isSidebarCollapsed = ref(false)
const drgMenuExpanded = ref(true)
const midAnalysisExpanded = ref(true)
const selectedBatchId = ref<string | null>(null)
const selectedSessionId = ref<string | null>(null)  // 新增：session_id
const isAuthorized = ref(false)
const passwordInput = ref('')
const passwordError = ref('')

const PASSWORD = 'lxry888'
const AUTH_STORAGE_KEY = 'frontpage_demo_auth'

const verifyPassword = () => {
  if (passwordInput.value.trim() === PASSWORD) {
    isAuthorized.value = true
    passwordError.value = ''
    sessionStorage.setItem(AUTH_STORAGE_KEY, '1')
  } else {
    passwordError.value = '密码错误，请重试'
  }
}

const { extracting, extractStructuredData } = useMedicalTextExtraction({
  demoCase,
  onStartExtract: () => {
    // 开始提取 2 秒后即扩展页面，不等待提取完成
    setTimeout(() => {
      isExpanded.value = true
    }, 2000)
  },
  onExtracted: () => {
    // 提取完成的回调（可选：用于其他后续操作）
  }
})

// DRG Grouping
const { drgLoading: drgGrouping, drgResult, performDRGGrouping: doDRGGrouping } = useDRGGrouping()
const performDRGGrouping = () => {
  if (demoCase.value?.case_id) {
    doDRGGrouping(demoCase.value.case_id, frontpage.value?.insurance?.insurance_total_cost)
  }
}

// Print functionality
const handlePrint = () => {
  // Create a printable version of the structured data
  const printContent = document.querySelector('.space-y-6.pb-10') as HTMLElement
  if (!printContent) {
    message.warning('没有可打印的内容')
    return
  }
  
  // Create print window
  const printWindow = window.open('', '_blank')
  if (!printWindow) {
    message.error('无法打开打印窗口，请检查浏览器弹窗设置')
    return
  }
  
  // Get current styles
  const styles = Array.from(document.styleSheets)
    .map(sheet => {
      try {
        return Array.from(sheet.cssRules).map(rule => rule.cssText).join('\n')
      } catch {
        return ''
      }
    })
    .join('\n')
  
  // Build print document
  const patientName = frontpage.value?.basic_info?.patient_name || '未知患者'
  const printDate = new Date().toLocaleDateString('zh-CN')
  
  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>病案首页 - ${patientName}</title>
      <style>
        ${styles}
        @media print {
          body { 
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }
          .no-print { display: none !important; }
        }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          padding: 20px;
          background: white;
        }
        .print-header {
          text-align: center;
          margin-bottom: 20px;
          padding-bottom: 10px;
          border-bottom: 2px solid #3b82f6;
        }
        .print-header h1 {
          font-size: 24px;
          color: #1e40af;
          margin: 0 0 5px 0;
        }
        .print-header p {
          color: #64748b;
          font-size: 12px;
          margin: 0;
        }
        .print-footer {
          margin-top: 30px;
          text-align: center;
          color: #94a3b8;
          font-size: 11px;
          border-top: 1px solid #e2e8f0;
          padding-top: 10px;
        }
      </style>
    </head>
    <body>
      <div class="print-header">
        <h1>病案首页结构化数据</h1>
        <p>患者：${patientName} | 打印日期：${printDate}</p>
      </div>
      ${printContent.outerHTML}
      <div class="print-footer">
        由 AI 病案首页系统自动生成 | 仅供参考，以正式病历为准
      </div>
    </body>
    </html>
  `)
  
  printWindow.document.close()
  
  // Wait for styles to load then print
  setTimeout(() => {
    printWindow.focus()
    printWindow.print()
  }, 500)
}

// Fill to frontpage function
const fillToFrontpage = () => {
  if (!frontpage.value) {
    message.warning('请先进行 AI 提取')
    return
  }
  
  // Switch to HM tab
  activeTab.value = 'hm'
  
  // Show success notification
  message.success({
    content: '✅ 已将提取数据回填到病案首页',
    duration: 3
  })
}

// Test Cases Data
const testCases = ref([
  {
    name: '测试病历1',
    description: '冠心病支架植入术完整住院病历',
    medical_text: `【病案首页基本信息】
医疗机构名称：四川省人民医院
组织机构代码：12345678-9
病案号：2026010001

姓名：张三
性别：男
出生日期：1968-01-15
年龄：58岁
国籍：中国
民族：汉族
婚姻状况：已婚
职业：退休工人
身份证号码：510102196801151234
现住址：四川省成都市青羊区人民路123号
联系人：李四（妻子）
联系电话：13812345678

住院次数：第2次
医疗付费方式：城镇职工基本医疗保险
入院途径：急诊
入院日期时间：2026-01-01 09:30
入院科室：心血管内科
入院病房：心内科一病区

药物过敏：有，青霉素过敏
ABO血型：A型
Rh血型：阳性

================================================================================
【入院记录】
记录时间：2026-01-01 11:00

主诉：反复胸闷、心悸3年，加重伴胸痛1周

现病史：
患者3年前开始出现活动后胸闷、心悸，休息5-10分钟后可缓解，未予重视。近3年来症状间断发作，发作频率逐渐增加。1周前患者于快步行走100米后出现胸闷、心悸加重，伴有胸骨后压榨样疼痛，向左肩背部放射，含服速效救心丸后约15分钟缓解。此后胸痛反复发作，每日2-3次，发作时伴出汗、恶心，持续时间较前延长。今日凌晨静息状态下再次出现胸痛，含服硝酸甘油后约20分钟方缓解，遂来我院急诊就诊，急诊心电图示ST-T改变，拟"冠心病 不稳定型心绞痛"收入院。病程中无晕厥、黑矇，无呼吸困难，无下肢水肿。发病以来精神、食欲尚可，睡眠欠佳，大小便正常，体重无明显变化。

既往史：
高血压病史10年，最高血压180/110mmHg，长期口服氨氯地平5mg qd，血压控制在140/90mmHg左右。
2型糖尿病病史5年，口服二甲双胍0.5g tid控制血糖，空腹血糖7-8mmol/L。
否认肝炎、结核等传染病史。否认外伤史、手术史、输血史。
对青霉素过敏，表现为皮疹。

个人史：
生于原籍，无疫区接触史。吸烟30年，20支/日，戒烟1年。饮酒史20年，白酒2两/日，戒酒1年。

家族史：
父亲因"脑卒中"去世，母亲患高血压健在。兄弟姐妹体健。否认家族遗传病史。

体格检查：
T 36.8℃，P 88次/分，R 20次/分，BP 145/92mmHg
身高170cm，体重75kg，BMI 26.0kg/m²
神志清楚，精神尚可，发育正常，营养中等，自主体位，查体合作。
皮肤黏膜无黄染，无出血点，浅表淋巴结未触及肿大。
头颅无畸形，双眼睑无水肿，巩膜无黄染，双侧瞳孔等大等圆，对光反射灵敏。
颈软，气管居中，甲状腺不大，颈静脉无怒张。
胸廓对称，双肺呼吸音清，未闻及干湿啰音。
心前区无隆起，心界向左下扩大，心率88次/分，律齐，心尖部可闻及S4奔马律，各瓣膜听诊区未闻及病理性杂音。
腹软，无压痛、反跳痛，肝脾肋下未触及，移动性浊音阴性，肠鸣音正常。
双下肢无水肿，双侧足背动脉搏动减弱。
生理反射存在，病理反射未引出。

辅助检查：
2026-01-01 急诊心电图：窦性心律，心率88次/分，V1-V4导联ST段压低0.1-0.2mV，T波倒置
2026-01-01 急诊心肌酶谱：CK 156U/L，CK-MB 12U/L，肌钙蛋白I 0.08ng/ml
2026-01-01 急诊BNP：386pg/ml

初步诊断：
1. 冠状动脉粥样硬化性心脏病
   不稳定型心绞痛
2. 高血压病3级 极高危
3. 2型糖尿病
4. 心功能II级（NYHA分级）

诊疗计划：
1. 心电监护、吸氧
2. 抗血小板聚集：阿司匹林100mg qd + 氯吡格雷75mg qd
3. 抗凝：低分子肝素5000U q12h皮下注射
4. 降脂稳定斑块：阿托伐他汀40mg qn
5. 改善心肌供血：硝酸异山梨酯10mg tid
6. 控制血压、血糖
7. 完善术前检查，拟行冠状动脉造影

医师签名：张主任
记录时间：2026-01-01 11:00

================================================================================
【首次病程记录】
记录时间：2026-01-01 14:00

患者张三，男，58岁，以"反复胸闷、心悸3年，加重伴胸痛1周"为主诉入院。

病例特点：
1. 老年男性，慢性病程，急性加重
2. 主要表现为活动后胸闷、心悸，近1周出现胸痛，放射至左肩背
3. 有高血压、糖尿病、吸烟等冠心病危险因素
4. 心电图示ST-T改变
5. 心肌酶轻度升高，肌钙蛋白阳性

诊断依据：
1. 冠心病 不稳定型心绞痛：依据典型心绞痛症状、危险因素、心电图及心肌标志物改变
2. 高血压病3级：高血压病史10年，血压最高180/110mmHg，合并心脏靶器官损害
3. 2型糖尿病：糖尿病病史5年，口服降糖药

鉴别诊断：
1. 急性心肌梗死：患者肌钙蛋白轻度升高，心电图ST段压低，需动态观察
2. 心包炎：无发热、心包摩擦音，不考虑
3. 主动脉夹层：无撕裂样疼痛、血压差异，暂不考虑

诊疗计划：
1. 完善冠脉造影前准备
2. 拟于明日行冠状动脉造影检查，必要时行PCI术
3. 加强抗栓治疗，监测心肌酶变化

医师签名：李医师

================================================================================
【日常病程记录】
2026-01-02 08:00
今日患者一般情况可，诉胸闷症状较前好转，无胸痛发作。生命体征平稳：T 36.5℃，P 76次/分，R 18次/分，BP 135/85mmHg。复查心电图：窦性心律，ST-T改变较前减轻。心肌酶谱：CK 128U/L，CK-MB 9U/L，肌钙蛋白I 0.05ng/ml，呈下降趋势。今日拟行冠状动脉造影检查。术前准备完善，已签署手术知情同意书。

医师签名：李医师

================================================================================
【主任查房记录】
2026-01-02 10:00

今日张主任查房。

患者一般情况尚可，病情较入院时稳定。张主任认为：
1. 患者为冠心病不稳定型心绞痛诊断明确
2. 结合患者危险因素及临床表现，建议尽早行冠脉造影
3. 目前内科治疗方案合适，继续加强抗栓
4. 术中发现严重病变，可同期行PCI治疗

指示：
1. 今日下午安排行冠状动脉造影
2. 备足血制品
3. 做好术中转PCI准备

参加人员：张主任、刘副主任、李医师、王医师

================================================================================
【手术记录】
手术日期：2026-01-02
手术开始时间：14:30
手术结束时间：16:00
麻醉方式：局部麻醉
手术名称：经皮冠状动脉造影术+支架植入术
术前诊断：冠状动脉粥样硬化性心脏病 不稳定型心绞痛
术中诊断：冠状动脉粥样硬化性心脏病 三支病变

手术医师：张主任
第一助手：刘副主任
麻醉医师：王医师
器械护士：赵护士
巡回护士：钱护士

手术经过：
患者取平卧位，常规消毒铺巾。1%利多卡因局麻下行右桡动脉穿刺，置入6F桡动脉鞘。送入6F造影导管，行选择性左右冠状动脉造影检查。

造影结果：
左主干：无明显狭窄
前降支：近段85%狭窄，中段60%狭窄
回旋支：近段50%狭窄
右冠状动脉：中段70%狭窄

经讨论，决定对前降支近段病变行PCI治疗。选用6F EBU3.5 指引导管，送入BMW导丝通过病变至前降支远端。以2.5×15mm半顺应性球囊预扩张病变处，然后植入3.0×23mm药物洗脱支架（雷帕霉素涂层）一枚，12atm释放。复查造影示支架贴壁良好，残余狭窄＜10%，前向血流TIMI 3级。

术中顺利，出血约5ml。术后即刻桡动脉穿刺点予弹力绷带加压包扎。

术后处理：
1. 心电监护24小时
2. 继续双联抗血小板治疗
3. 穿刺点观察有无渗血

主刀医师签名：张主任
记录时间：2026-01-02 16:30

================================================================================
【术后病程记录】
2026-01-02 20:00
术后6小时，患者一般情况好，无胸闷胸痛，无呼吸困难。生命体征平稳：T 36.6℃，P 72次/分，R 18次/分，BP 128/82mmHg。穿刺处敷料干燥，无渗血。心电图：窦性心律，V1-V4导联ST-T改变较术前好转。继续观察，维持目前治疗方案。

医师签名：李医师

================================================================================
【病程记录】
2026-01-03 08:00
术后第1天，患者情况良好。今晨无胸闷胸痛，活动耐量较前改善。生命体征稳定。右桡动脉穿刺处无红肿渗血。复查心电图：ST段改变较前明显好转。拟明日复查心脏彩超、心肌酶谱。

2026-01-04 08:00
术后第2天。患者自诉症状完全缓解。复查心脏彩超：LVEF 58%，左室壁运动未见明显异常，较术前改善。心肌酶谱正常范围。今日可下地活动，逐步恢复日常活动。

2026-01-05 08:00
术后第3天。患者一般情况好，活动如常，无不适主诉。各项检查指标稳定。征得患者同意，拟明日出院。今日完成出院宣教，告知服药依从性重要性。

医师签名：李医师

================================================================================
【出院记录】
出院日期时间：2026-01-06 10:00
出院科室：心血管内科
出院病房：心内科一病区
实际住院天数：5天

入院情况：
患者因"反复胸闷、心悸3年，加重伴胸痛1周"入院。入院时神志清楚，生命体征尚平稳，心电图示ST-T改变，心肌酶轻度升高。

入院诊断：
1. 冠状动脉粥样硬化性心脏病 不稳定型心绞痛
2. 高血压病3级 极高危
3. 2型糖尿病
4. 心功能II级

诊疗经过：
入院后完善相关检查，予抗栓、降脂、控压、控糖等内科治疗。于2026-01-02行冠状动脉造影示三支病变，对前降支近段85%狭窄病变行PCI，植入药物洗脱支架1枚。术后患者恢复良好，症状缓解，复查各项指标正常。

出院情况：
患者一般情况好，无胸闷胸痛。T 36.5℃，P 70次/分，R 18次/分，BP 125/80mmHg。心肺查体无异常。穿刺处愈合良好。

出院诊断：
1. 冠状动脉粥样硬化性心脏病
   不稳定型心绞痛
   冠状动脉支架植入术后
2. 高血压病3级 极高危
3. 2型糖尿病
4. 心功能II级

出院医嘱：
1. 休息：避免剧烈运动，可适当散步
2. 饮食：低盐低脂糖尿病饮食
3. 药物：
   - 阿司匹林肠溶片 100mg qd 口服（长期服用）
   - 氯吡格雷 75mg qd 口服（至少服用12个月）
   - 阿托伐他汀 20mg qn 口服（长期服用）
   - 氨氯地平 5mg qd 口服
   - 美托洛尔缓释片 47.5mg qd 口服
   - 二甲双胍 0.5g tid 口服
4. 复查：出院后1周、1个月、3个月门诊随访，监测血压、血糖、血脂
5. 注意事项：如出现胸痛、胸闷加重，立即来院就诊

科主任：张主任
主任医师：张主任
主治医师：刘副主任
住院医师：李医师
责任护士：赵护士
编码员：周编码

医师签名：李医师
出院日期：2026-01-06

================================================================================
【费用清单】
住院总费用：58326.80元
自付金额：8750.00元
医保报销：49576.80元

费用明细：
1. 综合医疗服务费：2850.00元
2. 诊断类费用（检查检验）：4580.50元
   - 心电图：120.00元
   - 心脏彩超：350.00元
   - 冠脉造影：2800.00元
   - 检验费：1310.50元
3. 治疗类费用：38650.00元
   - 介入手术费：8500.00元
   - 药物洗脱支架（1枚）：28500.00元
   - 其他材料费：1650.00元
4. 西药费：8246.30元
5. 护理费：2500.00元
6. 床位费：1500.00元（300元/天×5天）`
  },
  {
    name: '测试病历2',
    description: '肛瘘手术完整住院病历',
    medical_text: `【病案首页基本信息】
医疗机构名称：泸州市中心医院
组织机构代码：99999999-9
病案号：A000123

姓名：李明
性别：男
出生日期：1990-06-15
年龄：35岁
国籍：中国
民族：汉族
婚姻状况：已婚
职业：职员
身份证号码：999999199006150011
现住址：四川省泸州市江岸区滨江路88号
联系人：李明（本人）
联系电话：13900000000

住院次数：第2次
医疗付费方式：新型农村合作医疗
入院途径：门诊
入院日期时间：2025-03-29 13:49
入院科室：外二科（肛肠外科）
入院病房：外二科病区

药物过敏：无
ABO血型：O型
Rh血型：阳性

================================================================================
【入院记录】
记录时间：2025-03-29 15:00

主诉：发现肛旁肿物伴疼痛2天

现病史：
患者2天前无明显诱因出现肛旁肿物，伴局部疼痛，行走及排便时加重，无发热寒战，无腹痛腹泻，无便血及黏液便。患者既往曾于2024年3月因"肛周脓肿"于外院行切开引流术，术后恢复可，未正规随访。此次发病后自行外用药膏无明显好转，遂来我院门诊就诊，查体发现肛旁肿物较大，伴波动感，门诊以"肛周脓肿"收入住院。

既往史：
甲状腺功能减退病史3年，口服优甲乐50μg qd，甲功控制可。
2024年10月因"右肾结石"行体外冲击波碎石术，术后复查结石排出。
2024年3月因"肛周脓肿"于外院行切开引流术。
否认高血压、糖尿病、冠心病等慢性疾病史。
否认肝炎、结核等传染病史。
否认药物、食物过敏史。
预防接种史随当地。

个人史：
生于原籍，无疫区接触史。吸烟10年，10支/日。偶饮酒。

家族史：
否认家族遗传性疾病及肿瘤病史。

体格检查：
T 36.3℃，P 98次/分，R 20次/分，BP 147/95mmHg
身高170cm，体重75kg，BMI 26.0kg/m²
神志清楚，精神可，发育正常，营养中等，步入病房。
皮肤黏膜无黄染，浅表淋巴结未触及肿大。
心肺腹查体无明显异常。
专科检查：截石位，肛门居中，肛门2-3点位方向见一大小约4.0×3.0cm肿块，皮肤红肿明显，无破溃，扪及中央波动感，皮温升高，触痛明显。肛门指检：括约肌张力正常，可触及肛管直肠环，2-3点位方向肛管内可触及内口，距肛缘约2.5cm，有触痛。指套退出无血染及脓性分泌物。

辅助检查：
2025-03-29 血常规：WBC 8.58×10^9/L，RBC 5.17×10^12/L，HGB 158g/L，PLT 266×10^9/L
2025-03-29 肝肾功能：正常范围
2025-03-29 凝血功能：正常
2025-03-29 心电图：窦性心律
2025-03-29 心脏彩超：二、三尖瓣反流（轻度），左室舒张功能降低
2025-03-29 腹部彩超：轻度脂肪肝，右肾结石（0.4cm），左肾砂粒样结石

初步诊断：
1. 肛周脓肿
2. 肛瘘（可疑）
3. 甲状腺功能减退
4. 脂肪肝
5. 双肾结石
6. 心脏瓣膜病（轻度）

诊疗计划：
1. 完善术前检查
2. 排除手术禁忌后，择期行肛周脓肿切开引流术
3. 术中探查有无肛瘘，如有则同期处理
4. 预防性抗感染治疗
5. 控制血压

医师签名：李志强
记录时间：2025-03-29 15:00

================================================================================
【首次病程记录】
记录时间：2025-03-30 01:08

患者李明，男，35岁，以"发现肛旁肿物疼痛2天"为主诉于2025年03月29日13:49入院。

病例特点：
1. 中年男性，起病急，病程短
2. 主要表现为肛旁肿物伴局部疼痛
3. 既往有肛周脓肿手术史
4. 合并甲减、肾结石等基础疾病
5. 体格检查：肛门2-3点位方向见4.0×3.0cm肿块，红肿明显，波动感阳性
6. 辅助检查：血常规正常，心脏彩超示轻度瓣膜反流

诊断依据：
1. 肛周脓肿：典型症状体征，波动感阳性
2. 可疑肛瘘：既往肛周脓肿手术史，肛管内可触及内口

鉴别诊断：
1. 血栓性外痔：通常表现为肛缘硬结，无波动感，与本例不符
2. 肛周肿瘤：病程较长，质地硬，无感染征象
3. 骶尾部藏毛窦：位置偏高，窦道通向尾骨方向

诊疗计划：
1. 完善术前准备，明日安排手术
2. 术中探查确定有无肛瘘及瘘管走行
3. 根据术中情况决定手术方式

医师签名：周敏

================================================================================
【术前讨论记录】
讨论时间：2025-03-30 16:00
主持人：刘海波副主任医师
参加人员：陈国华主任医师、周敏主治医师、赵天宇主治医师、韩晓东主治医师、何立新主治医师、李志强主治医师

病情汇报：
患者李明，男，35岁，因"发现肛旁肿物疼痛2天"入院。查体见肛门2-3点位4.0×3.0cm肿块，波动感阳性。既往有肛周脓肿手术史。

讨论意见：
陈国华主任医师：该患者肛周脓肿诊断明确，既往手术史提示可能合并肛瘘。建议术中仔细探查，明确瘘管走行后一并处理。

刘海波副主任医师：同意陈主任意见。根据肿物位置及指检内口位置，考虑可能为高位复杂性肛瘘。术中需注意保护括约肌功能。

讨论结论：
1. 诊断：肛周脓肿合并肛瘘
2. 拟行手术：肛周脓肿切开引流术+肛瘘切除术
3. 麻醉方式：腰麻联合硬膜外麻醉
4. 手术医师：李志强主治医师
5. 术中探查明确瘘管类型后决定具体术式
6. 告知患者高位瘘管手术风险

记录者：李志强

================================================================================
【手术记录】
手术日期：2025-03-31
手术开始时间：09:30
手术结束时间：10:45
麻醉方式：腰麻联合硬脊膜外腔阻滞麻醉
手术名称：高位复杂性肛瘘切除术+肛周脓肿切开引流术+亚甲蓝肛周封闭术
术前诊断：1. 肛周脓肿  2. 肛瘘
术中诊断：1. 高位复杂性肛瘘  2. 肛周脓肿  3. 肛窦炎

手术者：李志强（主治医师）
第一助手：周敏（主治医师）
麻醉医师：唐静
器械护士：王璐
巡回护士：杨倩

手术经过：
1. 麻醉成功后，取截石位，常规消毒铺巾。
2. 用手指探查脓腔，脓腔约4.0×3.0×2.5cm，排出约15ml黄白色臭脓。
3. 亚甲蓝经外口注入探查瘘管走行，见主瘘管自外口向肛管方向走行，穿过内括约肌及部分外括约肌浅层，内口位于肛管2点位齿线处。另见分支瘘管经外括约肌外侧向上延伸约3cm。
4. 扩大外口切口，探查脓腔及瘘管走行，彻底清除坏死组织及瘘管壁。
5. 内口处行内括约肌部分切开术，保留外括约肌主体。
6. 分支瘘管予以切开搔刮引流。
7. 创面彻底止血，凡士林纱条填塞引流。
8. 术中出血约5ml，患者麻醉满意，安返病房。

术后诊断：
1. 高位复杂性肛瘘
2. 肛周脓肿
3. 肛窦炎

术后处理：
1. 心电监护6小时
2. 抗感染治疗
3. 保持大便通畅
4. 每日换药

主刀医师签名：李志强
记录时间：2025-03-31 11:00

================================================================================
【术后病程记录】
2025-03-31 15:00
术后6小时，患者一般情况好，麻醉已完全清醒。生命体征平稳：T 36.8℃，P 80次/分，R 18次/分，BP 130/85mmHg。诉术区轻度疼痛，可耐受。敷料少量血性渗出。已可进流质饮食。继续抗感染、对症支持治疗。

2025-04-01 08:00
术后第1天。患者一般情况可，术区疼痛减轻。今日首次换药：创面引流通畅，少量脓血性分泌物，无坏死组织，肉芽新鲜。予生理盐水冲洗，凡士林纱条引流。进半流质饮食，大便未解。

2025-04-02 08:00
术后第2天。患者情况良好，术区疼痛明显减轻。今日换药：创面缩小，引流物减少。患者已排大便1次，质软，无明显疼痛。

2025-04-03 08:00
术后第3天。患者一般情况好，无发热，饮食正常。换药见创面肉芽生长良好，渗出减少。拟明日出院。

医师签名：李志强

================================================================================
【主任查房记录】
2025-04-02 10:00

今日陈国华主任医师查房。

查房意见：
1. 患者术后恢复顺利，无发热感染征象
2. 创面愈合良好，引流通畅
3. 术后病理需追踪，以排除特殊感染
4. 可考虑近日出院，门诊继续换药
5. 嘱患者注意饮食，保持大便通畅，避免辛辣刺激

参加人员：陈国华主任、刘海波副主任、周敏、李志强

================================================================================
【出院记录】
出院日期时间：2025-04-03 10:00
出院科室：外二科
出院病房：外二科病区
实际住院天数：5天

入院情况：
患者因"发现肛旁肿物疼痛2天"入院。入院时见肛门2-3点位4.0×3.0cm肿块，红肿明显，波动感阳性。

入院诊断：
1. 肛周脓肿
2. 肛瘘
3. 甲状腺功能减退
4. 脂肪肝
5. 双肾结石

诊疗经过：
入院后完善术前检查，于2025-03-31在腰麻联合硬膜外麻醉下行高位复杂性肛瘘切除术+肛周脓肿切开引流术。术中见高位复杂性肛瘘及肛周脓肿，手术顺利。术后予抗感染、止痛、每日换药等治疗，创面愈合良好。

出院情况：
患者一般情况好，无发热，创面肉芽生长良好，引流通畅。

出院诊断：
1. 高位复杂性肛瘘
2. 肛周脓肿
3. 肛窦炎
4. 甲状腺功能减退
5. 脂肪肝
6. 双肾结石
7. 心脏瓣膜病（轻度）

出院医嘱：
1. 休息：避免剧烈活动，避免久坐久站
2. 饮食：清淡饮食，多食蔬菜水果，保持大便通畅
3. 药物：
   - 头孢克洛缓释片 0.375g bid 口服 5天
   - 甲硝唑片 0.4g tid 口服 5天
   - 优甲乐 50μg qd 口服（长期服用）
4. 换药：每日一次，门诊换药直至愈合
5. 复查：术后1周、2周、1个月门诊复查
6. 注意事项：如出现发热、大出血、剧烈疼痛等，及时就诊

科主任：陈国华
主任医师：陈国华
主治医师：刘海波
住院医师：李志强
责任护士：王璐
编码员：孙婧

医师签名：李志强
出院日期：2025-04-03

================================================================================
【费用清单】
住院总费用：12680.50元
自付金额：3804.15元
医保报销：8876.35元

费用明细：
1. 综合医疗服务费：1200.00元
2. 诊断类费用（检查检验）：1580.00元
   - 心电图：120.00元
   - 心脏彩超：350.00元
   - 腹部彩超：260.00元
   - 检验费：850.00元
3. 治疗类费用：5850.50元
   - 手术费：3500.00元
   - 麻醉费：1200.00元
   - 换药费：650.50元
   - 其他治疗：500.00元
4. 西药费：1850.00元
5. 护理费：1200.00元
6. 床位费：1000.00元（200元/天×5天）`
  }
])

// Resizable splitter state
const leftPanelWidth = ref(55) // percentage
const isResizing = ref(false)
const containerRef = ref<HTMLElement | null>(null)

// Resize handlers
const startResize = (e: MouseEvent) => {
  isResizing.value = true
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  e.preventDefault()
}

const doResize = (e: MouseEvent) => {
  if (!isResizing.value || !containerRef.value) return
  
  const containerRect = containerRef.value.getBoundingClientRect()
  const newWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100
  
  // Limit to reasonable bounds (20% - 80%)
  leftPanelWidth.value = Math.min(80, Math.max(20, newWidth))
}

const stopResize = () => {
  isResizing.value = false
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onMounted(() => {
  document.addEventListener('mousemove', doResize)
  document.addEventListener('mouseup', stopResize)
})

onMounted(() => {
  if (sessionStorage.getItem(AUTH_STORAGE_KEY) === '1') {
    isAuthorized.value = true
  }
})

onUnmounted(() => {
  document.removeEventListener('mousemove', doResize)
  document.removeEventListener('mouseup', stopResize)
})

// Computed
	const frontpage = computed(() => demoCase.value?.frontpage || null)
	const insuranceClaim = computed(() => demoCase.value?.insurance_claim || null)

	const tabs = [
	  { key: 'structured', label: '结构化结果' },
	  { key: 'profile', label: 'AI 画像分析' },
	  { key: 'hm', label: '病案首页' },
	  { key: 'insurance', label: '医保清单' }
	]

	const activeTabLabel = computed(() => tabs.find(t => t.key === activeTab.value)?.label || '结果展示')

// Actions
const toggleDarkMode = () => {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

	const normalizeTestCaseIndex = (input: unknown) => {
	  let idx = 0
	  if (typeof input === 'number') {
	    idx = input
	  } else if (typeof input === 'string') {
	    idx = Number.parseInt(input, 10)
	  } else if (input && typeof input === 'object') {
	    const maybe = input as any
	    if (maybe.key != null) idx = Number.parseInt(String(maybe.key), 10)
	    else if (maybe.index != null) idx = Number.parseInt(String(maybe.index), 10)
	  }
	
	  if (!Number.isFinite(idx) || Number.isNaN(idx)) idx = 0
	  const total = testCases.value.length
	  if (total <= 0) return 0
	  return Math.min(Math.max(0, idx), total - 1)
	}
	
	const loadDemoCase = async (caseIndex: unknown = 0) => {
	  loading.value = true
	  try {
	    // Get selected test case
	    const index = normalizeTestCaseIndex(caseIndex)
	    const selectedCase = testCases.value[index]
	    if (!selectedCase) {
	      throw new Error('Invalid test case index')
	    }
	    
	    await new Promise(resolve => setTimeout(resolve, 500)) // Brief delay for UX
	    
	    demoCase.value = {
	      case_id: `demo_case_${index + 1}`,
	      description: selectedCase.description,
	      medical_text: selectedCase.medical_text,
	      frontpage: null, // 不直接加载，需要用户点击"开始 AI 提取"
	      insurance_claim: null // 也延迟加载
    }
    
    
    message.success(`${selectedCase.name} 加载成功`)
  } catch (error: any) {
    console.error('加载测试病历失败:', error)
    message.error(error?.message || '加载测试病历失败')
  } finally {
    loading.value = false
  }
}

const onProfileExpand = () => {
  isExpanded.value = true
}

const collapseExpanded = () => {
  isExpanded.value = false
}

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
}

const goToWorkbench = () => {
  // Restore the initial workbench state (two-column layout + no loaded case)
  stopResize()
  currentView.value = 'workbench'
  activeTab.value = 'structured'
  isExpanded.value = false
  leftPanelWidth.value = 55
  loading.value = false
  demoCase.value = null
}

const handleLoadTestCase = (caseIndex: number) => {
  currentView.value = 'workbench'
  loadDemoCase(caseIndex)
}

const handleGoAnalysis = (sessionId: string, batchId: string) => {
  selectedSessionId.value = sessionId
  selectedBatchId.value = batchId
  currentView.value = 'analysis'
}

// 创建新的测试病历
const handleCreateTestCase = (data: { title: string; medical_text: string; createdAt: string }) => {
  testCases.value.push({
    name: data.title,
    title: data.title,
    description: '',
    medical_text: data.medical_text,
    type: '住院病历',
    createdAt: data.createdAt
  })
}

const handleUpdateTestCase = (payload: { index: number; title: string; medical_text: string }) => {
  if (payload.index < 2) {
    message.warning('测试病历1和测试病历2不可编辑')
    return
  }
  const target = testCases.value[payload.index]
  if (!target) return
  target.name = payload.title
  target.title = payload.title
  target.medical_text = payload.medical_text
}

const handleDeleteTestCase = (index: number) => {
  if (index < 2) {
    message.warning('测试病历1和测试病历2不可删除')
    return
  }
  testCases.value.splice(index, 1)
}

// 编码变更处理 - 触发DRG重新分组
const handleCodeChange = async (field: string, value: string) => {
  if (!frontpage.value?.diagnoses) return
  
  // 更新本地数据
  frontpage.value.diagnoses[field] = value
  
  // 显示提示并触发重新分组
  message.loading('编码已更新，正在重新计算DRG分组...', 1)
  
  // 延迟触发DRG分组
  setTimeout(() => {
    if (demoCase.value?.admission_id) {
      performDRGGrouping(demoCase.value.admission_id)
    }
  }, 500)
}
</script>

<style scoped>
/* Custom Scrollbar for inner containers */
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
</style>
