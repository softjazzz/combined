<template>
  <div class="bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-100 min-h-screen flex overflow-hidden transition-colors duration-300">
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
        <div v-if="currentView === 'workbench'" class="flex flex-col h-full w-full">
          <div class="flex-1 flex min-h-[1200px]" ref="containerRef">
          
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
	          <div class="flex flex-col gap-6 overflow-y-auto custom-scrollbar pl-2 transition-all duration-700" :style="{ width: isExpanded ? '100%' : (100 - leftPanelWidth) + '%' }">
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
            <div class="flex-1 bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 flex flex-col relative min-h-[1200px]">
              <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center">
                <h3 class="font-semibold text-slate-800 dark:text-white">{{ activeTabLabel }}</h3>
                <button v-if="activeTab === 'structured' || activeTab === 'print'" class="text-blue-500 hover:text-blue-600 text-sm font-medium flex items-center gap-1">
                  <PrinterOutlined class="text-base" /> 打印
                </button>
              </div>
              
              <div class="flex-1 p-6 relative overflow-auto flex flex-col">
                 <!-- Background Grid -->
                 <div class="absolute inset-0 bg-grid-slate-100 [mask-image:linear-gradient(0deg,white,rgba(255,255,255,0.6))] dark:bg-grid-slate-700/25 dark:[mask-image:linear-gradient(0deg,rgba(255,255,255,0.1),rgba(255,255,255,0.5))] pointer-events-none -z-0"></div>
                 
                 <div class="relative z-10 flex-1 overflow-y-auto custom-scrollbar">
                    
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
              <div class="px-6 py-4 border-t border-slate-100 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/30 flex justify-end gap-3 rounded-b-2xl">
                <button class="px-4 py-2 text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-white font-medium transition-colors">清空</button>
                <button class="px-4 py-2 bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 rounded-lg text-sm font-medium cursor-not-allowed">导出 CSV</button>
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
        <PostEventAnalysisView v-else-if="currentView === 'analysis'" :batchId="selectedBatchId" />
        <TestCaseListView 
          v-else-if="currentView === 'testcases'" 
          :test-cases="testCases"
          @back="currentView = 'workbench'"
          @loadCase="handleLoadTestCase"
          @createCase="handleCreateTestCase"
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
  FileSearchOutlined
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
// Test Cases Data
const testCases = ref([
  {
    name: '测试病历1',
    description: '高血压合并冠心病 - 简单病例',
    medical_text: `入院记录

患者张三，男，58岁，因"反复胸闷、心悸3年，加重1周"于2026年1月1日入院。

现病史：
患者3年前开始出现活动后胸闷、心悸，休息后可缓解。近1周症状加重，轻度活动即感胸闷不适，伴有头晕，无胸痛、无晕厥。

既往史：
高血压病史10年，最高血压180/110mmHg，长期口服降压药物控制。
2型糖尿病病史5年，口服二甲双胍控制血糖。

体格检查：
T 36.5℃，P 78次/分，R 18次/分，BP 158/98mmHg
神清，双肺呼吸音清，心率78次/分，律齐，各瓣膜听诊区未闻及病理性杂音。

辅助检查：
心电图示：窦性心律，ST-T改变
心脏彩超：左室舒张功能减低

初步诊断：
1. 高血压3级 极高危
2. 2型糖尿病
3. 冠状动脉粥样硬化性心脏病？

诊疗计划：
1. 完善冠状动脉造影检查
2. 继续降压、降糖治疗
3. 视造影结果决定下一步治疗方案

主治医师：刘主任
记录时间：2026-01-01 11:00`
  },
  {
    name: '测试病历2',
    description: '肛瘘合并肛周脓肿 - 完整病程记录',
    medical_text: `首次病程记录
2025-03-30 01:08
患者张伟，性别男，年龄44岁，以"发现肛旁肿物疼痛2+天"为主诉于2025年03月29日 13:49入院。

本病例特点：
1. 患者为44岁男性，起病缓，病程短
2. 发现肛旁肿物疼痛2+天
3. 一般情况良好。有慢病病史"甲减"病史，现口服优甲乐。否认传染病史。否认外伤史，有手术史2024-10-01行体外冲击波碎石术，否认输血史，无预防接种史，否认过敏史。
4. 体格检查：T36.3℃，P98次/分，R20次/分，BP147/95mmHg,身高170cm,体重75Kg。截石位，肛门居中，肛门2-3点位方向见一大小约4.0cm*3.0cm肿块，红肿明显，无破溃，扪及中央波动感，皮温升高。

初步诊断：1.肛周脓肿

入院记录
姓名：张伟
性别：男
年龄：44岁
出生日期：1981-02-04
婚姻：已婚
籍贯：四川省
民族：汉族
身份证号：510521198102040018
联系电话：13541593206
住址：泸州泸县天立B区01号
职业：农民
入院时间：2025-03-29 13:49
联系人姓名：张伟
联系人电话：13541593206
联系人与患者关系：本人
第2次入院记录

辅助检查:
2025-03-29 常规心电图检查 窦性心律
2025-03-29 腹部彩超 轻度脂肪肝。右肾结石。左肾砂粒样结石。
2025-03-29 心脏彩超 二、三尖瓣反流（轻度）。左室舒张功能降低。
2025-03-29 血常规:WBC 8.58×109/L,RBC 5.17×1012/L,HGB 158g/L,PLT 266×109/L

目前诊断：1.肛瘘；2.肛周脓肿；3.心脏瓣膜病；4.脂肪肝；5.双肾结石

手术记录:
手术时间：2025年03月31日
麻醉方式：腰麻联合硬脊膜外腔阻滞麻醉
手术方式：高位复杂性肛瘘切除术+肛周脓肿切开引流术+亚甲蓝肛周封闭术
术中诊断：1.高位复杂性肛瘘；2.肛周脓肿；3.肛窦炎
术者：王标
手术顺利，术中出血约5ml，麻醉满意

术前讨论记录
主持人：王飞副主任医师
参加讨论者：张云海主任医师、孙治庆主治医师、杜忠宜主治医师、李方健主治医师、刘杰主治医师、王标主治医师

科室：外二科
床号：54
住院号:350827`
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

const handleGoAnalysis = (batchId: string) => {
  selectedBatchId.value = batchId
  currentView.value = 'analysis'
}

// 创建新的测试病历
const handleCreateTestCase = (data: { title: string; description: string; medical_text: string; type: string; createdAt: string }) => {
  testCases.value.push({
    name: data.title,
    description: data.description,
    medical_text: data.medical_text,
    type: data.type,
    createdAt: data.createdAt
  })
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
