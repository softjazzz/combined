<template>
  <div class="bg-slate-100 dark:bg-slate-900 text-slate-800 dark:text-slate-100 min-h-screen flex overflow-hidden transition-colors duration-300">
    <!-- Sidebar -->
    <!-- Sidebar -->
    <aside :class="['bg-white dark:bg-slate-800 flex-shrink-0 flex flex-col justify-between border-r border-slate-200 dark:border-slate-700 hidden md:flex z-20 transition-all duration-300', isSidebarCollapsed ? 'w-20' : 'w-64']">
      <div>
        <!-- Sidebar Header with Toggle -->
        <div class="h-16 flex items-center justify-between px-6 border-b border-slate-100 dark:border-slate-700/50">
           <div v-if="!isSidebarCollapsed" class="font-bold text-lg text-blue-600 dark:text-blue-400 flex items-center gap-2">
             <RobotOutlined /> MedQC
           </div>
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
          <a :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer group', isSidebarCollapsed ? 'justify-center' : '', true ? 'bg-blue-500 text-white shadow-md' : '']">
            <AppstoreOutlined class="text-[20px]" />
            <span v-if="!isSidebarCollapsed" class="font-medium text-sm">工作台</span>
          </a>
          <a :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer group hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400', isSidebarCollapsed ? 'justify-center' : '']">
            <FolderOpenOutlined class="text-[20px] group-hover:text-blue-500" />
            <span v-if="!isSidebarCollapsed" class="font-medium text-sm">病案历史</span>
          </a>
          <a :class="['flex items-center gap-3 px-3 py-3 rounded-xl transition-all cursor-pointer group hover:bg-slate-50 dark:hover:bg-slate-700/50 hover:text-blue-500 text-slate-500 dark:text-slate-400', isSidebarCollapsed ? 'justify-center' : '']">
            <BarChartOutlined class="text-[20px] group-hover:text-blue-500" />
            <span v-if="!isSidebarCollapsed" class="font-medium text-sm">统计分析</span>
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
      <header class="flex-shrink-0 px-8 py-6 flex justify-between items-center bg-transparent backdrop-blur-sm z-10">
        <div>
          <h1 class="text-2xl font-bold text-slate-800 dark:text-white">AI 智能编码工作站</h1>
          <p class="text-sm text-slate-500 dark:text-slate-400 mt-1">MedQC Copilot 演示版 v2.0</p>
        </div>
        <div class="flex items-center gap-4">
          <div class="relative hidden sm:block">
            <input class="pl-10 pr-4 py-2.5 w-64 md:w-80 rounded-full bg-white dark:bg-slate-800 border-none ring-1 ring-slate-200 dark:ring-slate-700 focus:ring-2 focus:ring-blue-500 shadow-sm text-sm text-slate-700 dark:text-slate-200 placeholder-slate-400 outline-none" placeholder="搜索患者、病案号或诊断..." type="text"/>
            <SearchOutlined class="absolute left-3 top-3 text-slate-400 text-lg" />
          </div>
          <button class="p-2 bg-white dark:bg-slate-800 rounded-full shadow-sm text-slate-600 dark:text-slate-300 hover:text-blue-500 transition-colors ring-1 ring-slate-200 dark:ring-slate-700 w-10 h-10 flex items-center justify-center">
            <BellOutlined class="text-lg" />
          </button>
          <button @click="toggleDarkMode" class="p-2 bg-white dark:bg-slate-800 rounded-full shadow-sm text-slate-600 dark:text-slate-300 hover:text-blue-500 transition-colors ring-1 ring-slate-200 dark:ring-slate-700 w-10 h-10 flex items-center justify-center">
            <SkinOutlined class="text-lg" />
          </button>
        </div>
      </header>
      
      <!-- Content Area -->
      <div class="flex-1 overflow-hidden px-8 pb-8">
        <div class="flex h-full min-h-[600px]" ref="containerRef">
          
          <!-- Left Column: Medical Record -->
          <div class="flex flex-col gap-6 overflow-y-auto custom-scrollbar pr-2 transition-all duration-300" :style="{ width: isExpanded ? '0%' : leftPanelWidth + '%', opacity: isExpanded ? 0 : 1, paddingRight: isExpanded ? '0' : '' }">
            <div class="bg-white dark:bg-slate-800 rounded-2xl shadow-sm flex flex-col flex-1 border border-slate-100 dark:border-slate-700 overflow-hidden relative min-h-[500px]">
              <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center bg-gradient-to-r from-blue-500/5 to-transparent">
                <div class="flex items-center gap-2">
                  <FileTextOutlined class="text-blue-500" />
                  <h3 class="font-semibold text-slate-800 dark:text-white">病历原文</h3>
                </div>
                <div class="flex gap-2">
                  <button class="text-xs font-medium text-slate-500 hover:text-blue-500 px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded-md">全屏</button>
                  <button class="text-xs font-medium text-slate-500 hover:text-blue-500 px-2 py-1 bg-slate-100 dark:bg-slate-700 rounded-md">放大</button>
                </div>
              </div>
              
              <!-- Content -->
              <div v-if="loading" class="p-8">
                 <a-skeleton active :paragraph="{ rows: 10 }" />
              </div>
              <div v-else-if="demoCase?.medical_text" class="flex-1 p-6 bg-slate-50/30 dark:bg-slate-900/30 overflow-y-auto custom-scrollbar">
                <pre class="font-mono text-sm leading-relaxed whitespace-pre-wrap text-slate-700 dark:text-slate-300">{{ demoCase.medical_text }}</pre>
              </div>
              <div v-else class="flex-1 flex flex-col items-center justify-center p-10 bg-slate-50/50 dark:bg-slate-800/30">
                <div class="w-32 h-32 bg-blue-50 dark:bg-blue-900/20 rounded-full flex items-center justify-center mb-6 relative group cursor-pointer transition-all hover:scale-105" @click="loadDemoCase">
                  <UploadOutlined class="text-6xl text-blue-500/40 group-hover:text-blue-500 transition-colors" />
                  <div class="absolute -bottom-2 -right-2 bg-white dark:bg-slate-700 p-2 rounded-full shadow-md">
                    <RobotOutlined class="text-blue-500 text-xl" />
                  </div>
                </div>
                <h3 class="text-lg font-medium text-slate-700 dark:text-slate-200 mb-2">未加载病历</h3>
                <p class="text-slate-500 dark:text-slate-400 text-sm mb-6 text-center max-w-xs">上传扫描的 PDF 或图片以开始 AI 分析流程。</p>
                <button @click="loadDemoCase" class="bg-blue-500 hover:bg-blue-600 text-white px-6 py-3 rounded-xl font-medium shadow-lg shadow-blue-500/30 transition-all flex items-center gap-2">
                  <PlusOutlined />
                  加载测试病历
                </button>
              </div>
            </div>
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
          <div class="flex flex-col gap-6 overflow-y-auto custom-scrollbar pl-2 transition-all duration-300" :style="{ width: isExpanded ? '100%' : (100 - leftPanelWidth) + '%' }">
            <!-- Tabs -->
            <div class="bg-white dark:bg-slate-800 rounded-2xl shadow-sm p-1.5 flex gap-1 border border-slate-100 dark:border-slate-700">
               <button 
                  v-for="tab in tabs" 
                  :key="tab.key"
                  @click="activeTab = tab.key"
                  :class="[
                    'flex-1 py-2.5 text-sm font-medium rounded-xl transition-all text-center',
                    activeTab === tab.key 
                      ? 'bg-blue-500 text-white shadow-sm' 
                      : 'text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700'
                  ]"
               >
                 {{ tab.label }}
               </button>
               
               <div class="w-px bg-slate-100 dark:bg-slate-700 my-2 mx-1"></div>
               
               <button 
                 @click="toggleExpand"
                 class="px-3 text-slate-400 hover:text-blue-500 hover:bg-blue-50 dark:hover:bg-slate-700 rounded-xl transition-all flex items-center justify-center"
                 :title="isExpanded ? '恢复分栏' : '展开工作台'"
               >
                 <MenuUnfoldOutlined v-if="isExpanded" class="text-lg" />
                 <ArrowsAltOutlined v-else class="text-lg" />
               </button>
            </div>
            
            <!-- Stats Cards (hide on profile and structured tabs) -->
            <div v-if="!['profile', 'structured'].includes(activeTab)" class="grid grid-cols-2 gap-4">
              <div class="bg-white dark:bg-slate-800 rounded-2xl p-5 border border-slate-100 dark:border-slate-700 shadow-sm flex items-center justify-between">
                <div>
                  <p class="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold tracking-wider">AI 置信度</p>
                  <div class="flex items-baseline mt-1">
                    <span class="text-2xl font-bold text-slate-800 dark:text-white">{{ aiConfidence }}</span>
                    <span class="text-sm text-slate-400 ml-1">%</span>
                  </div>
                </div>
                <div class="h-10 w-10 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center">
                  <CheckCircleOutlined class="text-slate-400 text-xl" />
                </div>
              </div>
              <div class="bg-white dark:bg-slate-800 rounded-2xl p-5 border border-slate-100 dark:border-slate-700 shadow-sm flex items-center justify-between">
                <div>
                  <p class="text-xs text-slate-500 dark:text-slate-400 uppercase font-semibold tracking-wider">编码效率</p>
                  <div class="flex items-baseline mt-1">
                    <span class="text-2xl font-bold text-green-500">高</span>
                  </div>
                </div>
                <div class="h-10 w-10 rounded-full bg-green-50 dark:bg-green-900/20 flex items-center justify-center">
                  <ThunderboltOutlined class="text-green-500 text-xl" />
                </div>
              </div>
            </div>
            
            <!-- Main Content Area -->
            <div class="flex-1 bg-white dark:bg-slate-800 rounded-2xl shadow-sm border border-slate-100 dark:border-slate-700 flex flex-col relative min-h-[400px]">
              <div class="px-6 py-4 border-b border-slate-100 dark:border-slate-700 flex justify-between items-center">
                <h3 class="font-semibold text-slate-800 dark:text-white">{{ activeTabLabel }}</h3>
                <button v-if="activeTab === 'structured' || activeTab === 'print'" class="text-blue-500 hover:text-blue-600 text-sm font-medium flex items-center gap-1">
                  <PrinterOutlined class="text-base" /> 打印
                </button>
              </div>
              
              <div class="flex-1 p-6 relative overflow-hidden flex flex-col">
                 <!-- Background Grid -->
                 <div class="absolute inset-0 bg-grid-slate-100 [mask-image:linear-gradient(0deg,white,rgba(255,255,255,0.6))] dark:bg-grid-slate-700/25 dark:[mask-image:linear-gradient(0deg,rgba(255,255,255,0.1),rgba(255,255,255,0.5))] pointer-events-none -z-0"></div>
                 
                 <div class="relative z-10 flex-1 overflow-y-auto custom-scrollbar">
                    
                    <!-- Content: Structured -->
                    <div v-if="activeTab === 'structured'">
                       <!-- Extracting state -->
                       <div v-if="extracting" class="flex flex-col items-center justify-center h-64">
                          <a-spin size="large" />
                          <p class="mt-4 text-slate-500 dark:text-slate-400">AI 正在从病历原文中提取结构化信息...</p>
                       </div>
                       <!-- Has frontpage data -->
                       <div v-else-if="frontpage" class="space-y-6 pb-10">
                         <!-- 1. Basic Info & Hospitalization (Grid) -->
                         <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
                             <!-- Basic Info -->
                             <div class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-5 border border-slate-100 dark:border-slate-700">
                               <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
                                 <UserOutlined class="text-blue-500" /> 患者基本信息
                               </h4>
                               <div class="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">姓名</div><div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.patient_name }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">性别</div><div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.gender_text }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">出生日期</div><div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.birth_date }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">年龄</div><div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.age_years }} 岁</div></div>
                                 <div class="col-span-2"><div class="text-xs text-slate-500 dark:text-slate-400">身份证号</div><div class="font-medium font-mono dark:text-slate-200">{{ frontpage.basic_info.id_number }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">籍贯</div><div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.native_place || '-' }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">职业</div><div class="font-medium dark:text-slate-200">{{ frontpage.basic_info.job || '-' }}</div></div>
                               </div>
                             </div>

                             <!-- Hospitalization -->
                             <div class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-5 border border-slate-100 dark:border-slate-700">
                               <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
                                 <HistoryOutlined class="text-blue-500" /> 住院过程信息
                               </h4>
                               <div class="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">入院日期</div><div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.admission_date }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">出院日期</div><div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.discharge_date }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">入院科室</div><div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.admitted_dept }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">出院科室</div><div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.discharged_dept }}</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">住院天数</div><div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.hospital_days }} 天</div></div>
                                 <div><div class="text-xs text-slate-500 dark:text-slate-400">离院方式</div><div class="font-medium dark:text-slate-200">{{ frontpage.hospitalization?.leaving_way || '医嘱离院' }}</div></div>
                               </div>
                             </div>
                         </div>
                         
                         <!-- 2. Diagnoses (Table) -->
                         <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                            <div class="bg-blue-50/80 dark:bg-blue-900/20 px-4 py-3 border-b border-blue-100 dark:border-blue-800/30 flex justify-between items-center">
                               <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                                 <MedicineBoxOutlined class="text-blue-600" /> 出院诊断
                               </h4>
                               <span class="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full dark:bg-blue-900 dark:text-blue-300">ICD-10</span>
                            </div>
                            <div class="overflow-x-auto">
                                <table class="w-full text-sm text-left">
                                   <thead class="bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium">
                                      <tr>
                                         <th class="px-4 py-3 w-20">类型</th>
                                         <th class="px-4 py-3 w-32">ICD编码</th>
                                         <th class="px-4 py-3">诊断名称</th>
                                         <th class="px-4 py-3 w-24">入院病情</th>
                                         <th class="px-4 py-3 w-24 text-center">AI置信度</th>
                                      </tr>
                                   </thead>
                                   <tbody class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50">
                                      <!-- Main -->
                                      <tr class="hover:bg-slate-50 dark:hover:bg-slate-700/50">
                                         <td class="px-4 py-3"><span class="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-xs font-medium dark:bg-blue-900/50 dark:text-blue-300">主要</span></td>
                                         <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">{{ frontpage.diagnoses.discharge_main_icd }}</td>
                                         <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">{{ frontpage.diagnoses.discharge_main_diagnosis_text }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.diagnoses.discharge_main_conn || '-' }}</td>
                                         <td class="px-4 py-3 text-center">
                                            <div class="flex items-center justify-center gap-1 text-green-600">
                                                <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                                    <div class="h-full bg-green-500 w-[95%]"></div>
                                                </div>
                                            </div>
                                         </td>
                                      </tr>
                                      <!-- Others -->
                                      <tr v-for="(diag, idx) in frontpage.diagnoses.discharge_other_diagnoses" :key="idx" class="hover:bg-slate-50 dark:hover:bg-slate-700/50">
                                         <td class="px-4 py-3"><span class="text-slate-400 text-xs">其他</span></td>
                                         <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">{{ diag.code }}</td>
                                         <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ diag.name }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ diag.conn || '-' }}</td>
                                         <td class="px-4 py-3 text-center">
                                            <div class="flex items-center justify-center gap-1 text-green-600">
                                                <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                                                    <div class="h-full bg-green-500 w-[88%]"></div>
                                                </div>
                                            </div>
                                         </td>
                                      </tr>
                                   </tbody>
                                </table>
                            </div>
                         </div>
                         
                         <!-- 3. Procedures (Table) -->
                         <div class="border border-slate-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm">
                            <div class="bg-orange-50/80 dark:bg-orange-900/20 px-4 py-3 border-b border-orange-100 dark:border-orange-800/30 flex justify-between items-center">
                               <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2">
                                 <ScissorOutlined class="text-orange-600" /> 手术操作
                               </h4>
                               <span class="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full dark:bg-orange-900 dark:text-orange-300">ICD-9-CM-3</span>
                            </div>
                            <div class="overflow-x-auto">
                                <table class="w-full text-sm text-left">
                                   <thead class="bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-medium">
                                      <tr>
                                         <th class="px-4 py-3 w-32">手术编码</th>
                                         <th class="px-4 py-3">手术名称</th>
                                         <th class="px-4 py-3 w-32">手术日期</th>
                                         <th class="px-4 py-3 w-24">术者</th>
                                         <th class="px-4 py-3 w-24">麻醉方式</th>
                                         <th class="px-4 py-3 w-24">切口等级</th>
                                      </tr>
                                   </thead>
                                   <tbody class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50">
                                      <tr v-if="frontpage.procedures.main?.code">
                                         <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">{{ frontpage.procedures.main.code }}</td>
                                         <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">{{ frontpage.procedures.main.name }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.date }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.surgeon }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.anesthesia || '-' }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ frontpage.procedures.main.level || '-' }}</td>
                                      </tr>
                                      <tr v-for="(proc, idx) in frontpage.procedures.others" :key="idx">
                                         <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">{{ proc.code }}</td>
                                         <td class="px-4 py-3 text-slate-700 dark:text-slate-300">{{ proc.name }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ proc.date }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">{{ proc.surgeon }}</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">-</td>
                                         <td class="px-4 py-3 text-slate-600 dark:text-slate-400">-</td>
                                      </tr>
                                      <tr v-if="!frontpage.procedures.main?.code && (!frontpage.procedures.others || frontpage.procedures.others.length === 0)">
                                          <td colspan="6" class="px-4 py-8 text-center text-slate-400">无手术操作</td>
                                      </tr>
                                   </tbody>
                                </table>
                            </div>
                         </div>
                       </div>
                       <!-- Empty state: needs extraction -->
                       <div v-else class="h-full flex flex-col items-center justify-center text-center p-6">
                          <div class="w-20 h-20 bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 rounded-2xl mb-5 flex items-center justify-center">
                             <RobotOutlined class="text-4xl text-blue-500" />
                          </div>
                          <h3 class="text-lg font-semibold text-slate-800 dark:text-white mb-2">AI 结构化提取</h3>
                          <p class="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-xs">从病历原文中自动识别患者信息、诊断、手术操作，并映射到 ICD 标准编码。</p>
                          <button 
                            @click="extractStructuredData" 
                            :disabled="!demoCase?.medical_text"
                            class="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl text-sm font-medium transition-all shadow-lg shadow-blue-500/25 flex items-center gap-2"
                          >
                            <ThunderboltOutlined />
                            开始 AI 提取
                          </button>
                          <p v-if="!demoCase?.medical_text" class="text-xs text-orange-500 mt-3">请先在左侧加载病历原文</p>
                       </div>
                    </div>

                    <!-- Content: AI Analysis -->
                    <div v-else-if="activeTab === 'profile'" class="h-full">
                       <div v-if="!profile" class="h-full flex flex-col items-center justify-center text-center p-6">
                           <div class="w-16 h-16 bg-blue-50 dark:bg-blue-900/20 rounded-2xl mb-4 flex items-center justify-center">
                              <ScanOutlined class="text-3xl text-blue-500" />
                           </div>
                           <h3 class="text-lg font-medium text-slate-800 dark:text-white mb-2">AI 深度画像分析</h3>
                           <p class="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-xs">对病历全文进行深度阅读，构建诊断发生发展时间轴，验证手术闭环完整性，并自动发现首页填报差异。</p>
                           <button @click="analyzeProfile" :disabled="!demoCase?.medical_text" class="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-5 py-2.5 rounded-xl text-sm font-medium transition-colors">
                              {{ profileLoading ? '正在分析...' : '开始深度分析' }}
                           </button>
                       </div>
                       <div v-else class="h-full overflow-hidden flex flex-col">
                           <!-- Dashboard grid -->
                           <div class="h-full p-4 overflow-y-auto custom-scrollbar flex flex-col">
                              <!-- Top Stats -->
                              <div class="grid grid-cols-4 gap-4 mb-4 flex-shrink-0">
                                <div class="bg-white dark:bg-slate-800 p-3 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700">
                                   <div class="text-xs text-slate-500 mb-1">主要诊断</div>
                                   <div class="font-bold text-slate-800 dark:text-white truncate" :title="frontpage?.diagnoses?.discharge_main_diagnosis_text">{{ frontpage?.diagnoses?.discharge_main_diagnosis_text || '--' }}</div>
                                </div>
                                <div class="bg-white dark:bg-slate-800 p-3 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700">
                                   <div class="text-xs text-slate-500 mb-1">住院天数</div>
                                   <div class="font-bold text-slate-800 dark:text-white">{{ frontpage?.hospitalization?.actual_hospital_days || '--' }} <span class="text-xs font-normal text-slate-400">天</span></div>
                                </div>
                                <div class="bg-white dark:bg-slate-800 p-3 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700">
                                   <div class="text-xs text-slate-500 mb-1">总费用</div>
                                   <div class="font-bold text-slate-800 dark:text-white">¥ {{ insuranceClaim?.total_cost?.toFixed(0) || '--' }}</div>
                                </div>
                                <div class="bg-white dark:bg-slate-800 p-3 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700">
                                   <div class="text-xs text-slate-500 mb-1">DRG 组</div>
                                   <div class="font-bold text-green-600">FM19 <span class="bg-green-100 text-green-700 text-xs px-1.5 py-0.5 rounded ml-1">低风险</span></div>
                                </div>
                              </div>
                              
                              <div class="flex flex-col lg:grid lg:grid-cols-12 gap-4 flex-1 min-h-[600px]">
                                <!-- Left: Problem List -->
                                <div class="col-span-12 lg:col-span-3 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 flex flex-col">
                                   <div class="p-3 border-b border-slate-100 dark:border-slate-700 font-semibold text-slate-700 dark:text-slate-200">
                                      Problems List
                                   </div>
                                   <div class="flex-1 overflow-y-auto p-2 space-y-2">
                                      <div class="p-3 bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-100 dark:border-red-900/30 cursor-pointer hover:shadow-md transition-all">
                                         <div class="flex justify-between items-start mb-1">
                                            <span class="font-medium text-red-700 dark:text-red-300 text-sm">高血压3级 极高危</span>
                                            <ExclamationCircleOutlined class="text-red-500" />
                                         </div>
                                         <div class="text-xs text-red-500/80">I10.x00</div>
                                      </div>
                                      <div class="p-3 bg-slate-50 dark:bg-slate-700/30 rounded-lg border border-slate-100 dark:border-slate-700 cursor-pointer hover:shadow-md transition-all">
                                         <div class="flex justify-between items-start mb-1">
                                            <span class="font-medium text-slate-700 dark:text-slate-200 text-sm">2型糖尿病</span>
                                         </div>
                                         <div class="text-xs text-slate-500">E11.900</div>
                                      </div>
                                      <div class="p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-100 dark:border-yellow-900/30 cursor-pointer hover:shadow-md transition-all">
                                         <div class="flex justify-between items-start mb-1">
                                            <span class="font-medium text-yellow-700 dark:text-yellow-300 text-sm">冠心病 (待查)</span>
                                            <QuestionCircleOutlined class="text-yellow-500" />
                                         </div>
                                         <div class="text-xs text-yellow-500/80">疑似诊断</div>
                                      </div>
                                   </div>
                                </div>
                                
                                <!-- Center: 3D Body Model -->
                                <div class="col-span-12 lg:col-span-5 bg-gradient-to-b from-slate-900 to-slate-800 rounded-xl shadow-sm border border-slate-700 flex flex-col relative overflow-hidden group min-h-[300px]">
                                   <div class="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-20"></div>
                                   <div class="absolute top-4 left-4 text-white/50 text-xs font-mono uppercase tracking-widest z-10">3D Body Analysis</div>
                                   
                                   <div class="flex-1 flex items-center justify-center relative">
                                      <!-- Body Image -->
                                      <img src="/human_body_schematic.png" class="h-[90%] object-contain drop-shadow-[0_0_15px_rgba(59,130,246,0.5)] opacity-90" alt="Body Map" />
                                      
                                      <!-- Dynamic Hotspots with Staggered Animation -->
                                      <template v-for="(marker, index) in currentBodyMarkers" :key="index">
                                        <!-- Marker Container with Staggered Entry -->
                                        <div 
                                          class="absolute cursor-pointer z-20 transition-all duration-500"
                                          :class="[
                                            visibleMarkerIndices.includes(index) ? 'opacity-100 scale-100' : 'opacity-0 scale-0'
                                          ]"
                                          :style="{ 
                                            top: getMarkerPosition(marker, 'top'), 
                                            left: getMarkerPosition(marker, 'left'),
                                            transitionDelay: `${index * 300}ms`
                                          }"
                                          @click="setActiveMarker(index)"
                                        >
                                          <!-- Ping animation for active/severe markers -->
                                          <div 
                                            v-if="activeMarkerIndex === index || marker.severity === 'severe'" 
                                            class="rounded-full animate-ping absolute opacity-75"
                                            :class="[
                                              getSeverityColor(marker.severity),
                                              activeMarkerIndex === index ? 'w-6 h-6 -ml-1 -mt-1' : 'w-4 h-4'
                                            ]"
                                          ></div>
                                          <!-- Marker dot -->
                                          <div 
                                            class="rounded-full border-2 border-white shadow-lg relative z-10 transition-all duration-300"
                                            :class="[
                                              getSeverityColor(marker.severity),
                                              activeMarkerIndex === index ? 'w-5 h-5 ring-4 ring-white/30' : 'w-3 h-3'
                                            ]"
                                          ></div>
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
                                            :stroke="marker.severity === 'severe' ? '#ef4444' : marker.severity === 'moderate' ? '#eab308' : '#60a5fa'"
                                            stroke-width="2"
                                            stroke-dasharray="5,5"
                                            class="animate-pulse"
                                          />
                                        </svg>
                                      </template>
                                      
                                      <!-- Active Marker Info Card (positioned on left side) -->
                                      <div 
                                        v-if="activeMarkerIndex !== null && currentBodyMarkers[activeMarkerIndex]"
                                        class="absolute left-4 top-1/2 -translate-y-1/2 w-48 bg-white/95 dark:bg-slate-800/95 backdrop-blur-sm rounded-xl shadow-xl border border-slate-200 dark:border-slate-600 p-4 z-30 transition-all duration-500"
                                        :class="visibleMarkerIndices.includes(activeMarkerIndex) ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-4'"
                                      >
                                        <div class="flex items-center gap-2 mb-2">
                                          <div 
                                            class="w-3 h-3 rounded-full"
                                            :class="getSeverityColor(currentBodyMarkers[activeMarkerIndex].severity)"
                                          ></div>
                                          <span class="font-bold text-slate-800 dark:text-white">
                                            {{ getRegionLabel(currentBodyMarkers[activeMarkerIndex].region) }}
                                          </span>
                                        </div>
                                        <p class="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
                                          {{ currentBodyMarkers[activeMarkerIndex].condition }}
                                        </p>
                                        <div class="mt-3 flex items-center justify-between text-xs">
                                          <span 
                                            class="px-2 py-1 rounded-full"
                                            :class="getSeverityBadgeClass(currentBodyMarkers[activeMarkerIndex].severity)"
                                          >
                                            {{ getSeverityLabel(currentBodyMarkers[activeMarkerIndex].severity) }}
                                          </span>
                                          <span class="text-slate-400">{{ activeMarkerIndex + 1 }} / {{ currentBodyMarkers.length }}</span>
                                        </div>
                                      </div>
                                      
                                      <!-- Navigation dots -->
                                      <div 
                                        v-if="currentBodyMarkers.length > 1"
                                        class="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 z-30"
                                      >
                                        <button 
                                          v-for="(_, idx) in currentBodyMarkers" 
                                          :key="idx"
                                          @click="setActiveMarker(idx)"
                                          class="w-2 h-2 rounded-full transition-all duration-300"
                                          :class="activeMarkerIndex === idx ? 'bg-white w-6' : 'bg-white/50 hover:bg-white/80'"
                                        ></button>
                                      </div>
                                   </div>
                                </div>
                                
                                <!-- Right: Vitals & Labs -->
                                <div class="col-span-12 lg:col-span-4 flex flex-col gap-4 h-full">
                                   <!-- Vitals -->
                                   <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 p-4 flex-1 flex flex-col min-h-[180px]">
                                      <div class="flex justify-between items-center mb-2">
                                         <h4 class="font-semibold text-slate-700 dark:text-slate-200">Vitals Monitor</h4>
                                         <span class="text-xs text-slate-400">Last 24h</span>
                                      </div>
                                      <div class="flex-1 min-h-0 w-full relative">
                                         <v-chart :option="vitalsChartOption" autoresize class="w-full h-full absolute inset-0" />
                                      </div>
                                   </div>
                                   
                                   <!-- Labs -->
                                   <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 p-4 flex-1 flex flex-col min-h-[180px]">
                                      <div class="flex justify-between items-center mb-2">
                                         <h4 class="font-semibold text-slate-700 dark:text-slate-200">Lab Results</h4>
                                         <span class="text-xs text-slate-400">Latest</span>
                                      </div>
                                      <div class="flex-1 min-h-0 w-full relative">
                                         <v-chart :option="labsChartOption" autoresize class="w-full h-full absolute inset-0" />
                                      </div>
                                   </div>
                                   
                                   <!-- Risk -->
                                   <div class="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-100 dark:border-slate-700 p-4 flex-1 flex flex-col min-h-[150px]">
                                      <div class="flex justify-between items-center mb-2">
                                         <h4 class="font-semibold text-slate-700 dark:text-slate-200">Risk Assessment</h4>
                                      </div>
                                      <div class="flex-1 min-h-0 relative w-full">
                                          <v-chart :option="riskGaugeOption" autoresize class="w-full h-full absolute inset-0" />
                                          <div class="absolute bottom-0 left-0 right-0 text-center text-xs text-slate-500">建议转诊上级医院</div>
                                      </div>
                                   </div>
                                </div>
                              </div>
                           </div>
                       </div>
                    </div>

                    <!-- Content: HM Template -->
                    <div v-else-if="activeTab === 'hm'" class="h-full">
                      <HmFrontpagePreview v-if="frontpage" :draft="frontpage" class="h-full" />
                      <div v-else class="flex items-center justify-center h-full text-slate-400">暂无数据</div>
                    </div>
                    
                    <!-- Content: Insurance -->
                     <div v-else-if="activeTab === 'insurance'">
                        <div v-if="insuranceClaim" class="bg-slate-50 dark:bg-slate-700/30 rounded-xl p-6 border border-slate-100 dark:border-slate-700">
                           <div class="text-center mb-6">
                              <p class="text-xs text-slate-500 uppercase tracking-wide mb-1">总费用</p>
                              <div class="text-3xl font-bold text-slate-800 dark:text-white">¥ {{ insuranceClaim.total_cost.toFixed(2) }}</div>
                           </div>
                           <div class="space-y-3">
                              <div class="flex justify-between text-sm py-2 border-b border-slate-200 dark:border-slate-600">
                                <span class="text-slate-500 dark:text-slate-400">基金支付</span>
                                <span class="font-medium text-green-600">¥ {{ insuranceClaim.fund_pay.toFixed(2) }}</span>
                              </div>
                              <div class="flex justify-between text-sm py-2 border-b border-slate-200 dark:border-slate-600">
                                <span class="text-slate-500 dark:text-slate-400">个人自付</span>
                                <span class="font-medium text-orange-600">¥ {{ insuranceClaim.patient_pay.toFixed(2) }}</span>
                              </div>
                              <div class="flex justify-between text-sm py-2">
                                <span class="text-slate-500 dark:text-slate-400">医保类型</span>
                                <span class="text-slate-700 dark:text-slate-300">{{ insuranceClaim.insurance_type }}</span>
                              </div>
                           </div>
                        </div>
                        <div v-else class="flex items-center justify-center h-48 text-slate-400">暂无医保数据</div>
                     </div>
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
                  <th class="px-4 py-3 font-semibold">状态</th>
                  <th class="px-4 py-3 rounded-r-lg font-semibold">主DRG</th>
                </tr>
              </thead>
              <tbody>
                <tr class="bg-white dark:bg-slate-800 border-b dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                  <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">#2026010001</td>
                  <td class="px-4 py-3">心内科</td>
                  <td class="px-4 py-3">2026-01-04</td>
                  <td class="px-4 py-3"><span class="bg-green-100 text-green-800 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-green-900 dark:text-green-300">已完成</span></td>
                  <td class="px-4 py-3 text-slate-900 dark:text-white">FM19</td>
                </tr>
                <tr class="bg-white dark:bg-slate-800 border-b dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                  <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">#2026010002</td>
                  <td class="px-4 py-3">神经内科</td>
                  <td class="px-4 py-3">2026-01-03</td>
                  <td class="px-4 py-3"><span class="bg-yellow-100 text-yellow-800 text-xs font-medium px-2.5 py-0.5 rounded dark:bg-yellow-900 dark:text-yellow-300">审核中</span></td>
                  <td class="px-4 py-3 text-slate-900 dark:text-white">BR23</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
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
  SearchOutlined,
  BellOutlined,
  FileTextOutlined,
  UploadOutlined,
  RobotOutlined,
  PlusOutlined,
  CheckCircleOutlined,
  ThunderboltOutlined,
  PrinterOutlined,
  UserOutlined,
  MedicineBoxOutlined,
  ScissorOutlined,
  ScanOutlined,
  HistoryOutlined,
  SkinOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ArrowsAltOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import HmFrontpagePreview from '@/components/frontpage/HmFrontpagePreview.vue'
import DiagnosisSurgeryTimeline from '@/components/frontpage/DiagnosisSurgeryTimeline.vue'

// ECharts
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, RadarChart, GaugeChart } from 'echarts/charts'
import { 
  GridComponent, 
  TooltipComponent, 
  LegendComponent, 
  PolarComponent,
  TitleComponent 
} from 'echarts/components'

use([
  CanvasRenderer, 
  LineChart, 
  BarChart, 
  RadarChart,
  GaugeChart,
  GridComponent, 
  TooltipComponent, 
  LegendComponent, 
  PolarComponent,
  TitleComponent
])

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
const loading = ref(false)
const extracting = ref(false)
const demoCase = ref<DemoCase | null>(null)
const profile = ref<any>(null)
const profileLoading = ref(false)
const isDark = ref(false)
const isSidebarCollapsed = ref(false)

// Body marker animation state
const activeMarkerIndex = ref<number | null>(0)
const visibleMarkerIndices = ref<number[]>([])
const markerAnimationTimer = ref<number | null>(null)

// Computed property for current body markers
const currentBodyMarkers = computed(() => profile.value?.body_markers || defaultBodyMarkers)

// Chart Options
const vitalsChartOption = ref({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'axis' },
  grid: { top: 30, right: 20, bottom: 20, left: 40, containLabel: true },
  xAxis: {
    type: 'category',
    data: ['08:00', '12:00', '16:00', '20:00', '08:00', '12:00', '16:00'],
    axisLine: { lineStyle: { color: '#94a3b8' } },
    axisLabel: { color: '#64748b' }
  },
  yAxis: {
    type: 'value',
    splitLine: { lineStyle: { type: 'dashed', color: '#e2e8f0' } },
    axisLabel: { color: '#64748b' }
  },
  series: [
    {
      name: '收缩压',
      type: 'line',
      smooth: true,
      data: [135, 138, 142, 140, 136, 132, 130],
      itemStyle: { color: '#ef4444' },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(239,68,68,0.2)' }, { offset: 1, color: 'rgba(239,68,68,0)' }]
        }
      }
    },
    {
      name: '舒张压',
      type: 'line',
      smooth: true,
      data: [85, 88, 92, 90, 86, 84, 82],
      itemStyle: { color: '#3b82f6' }
    }
  ]
})

const labsChartOption = ref({
  backgroundColor: 'transparent',
  tooltip: { trigger: 'item' },
  radar: {
    indicator: [
      { name: '空腹血糖', max: 10 },
      { name: '总胆固醇', max: 8 },
      { name: '甘油三酯', max: 5 },
      { name: 'LDH-C', max: 5 },
      { name: '肌酐', max: 120 }
    ],
    splitArea: { areaStyle: { color: ['rgba(255,255,255,0)', 'rgba(255,255,255,0)'] } },
    axisName: { color: '#64748b' }
  },
  series: [
    {
      type: 'radar',
      data: [
        {
          value: [7.8, 6.2, 2.8, 3.5, 95],
          name: '本次检查',
          itemStyle: { color: '#8b5cf6' },
          areaStyle: { opacity: 0.3 }
        }
      ]
    }
  ]
})

const riskGaugeOption = ref({
  series: [
    {
      type: 'gauge',
      startAngle: 180,
      endAngle: 0,
      min: 0,
      max: 100,
      splitNumber: 5,
      itemStyle: { color: '#f59e0b' },
      progress: { show: true, width: 30 },
      pointer: { show: false },
      axisLine: { lineStyle: { width: 30 } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: { fontSize: 30, offsetCenter: [0, '-10%'], valueAnimation: true, formatter: '{value}%', color: 'auto' },
      data: [{ value: 85, name: '心血管风险' }]
    }
  ]
})

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
  stopMarkerAnimation() // Clean up auto-play timer
})

// Computed
const frontpage = computed(() => demoCase.value?.frontpage || null)
const insuranceClaim = computed(() => demoCase.value?.insurance_claim || null)
const aiConfidence = computed(() => frontpage.value ? 98 : '--')

const tabs = [
  { key: 'structured', label: '结构化结果' },
  { key: 'profile', label: 'AI 画像分析' },
  { key: 'hm', label: 'HM 模板' },
  { key: 'insurance', label: '医保清单' }
]

const activeTabLabel = computed(() => tabs.find(t => t.key === activeTab.value)?.label || '结果展示')

// Default body markers (used before LLM analysis)
const defaultBodyMarkers = [
  { region: 'heart', condition: '冠状动脉粥样硬化', severity: 'severe', position: { top: '32%', left: '52%' } },
  { region: 'pancreas', condition: '2型糖尿病', severity: 'moderate', position: { top: '45%', left: '55%' } }
]

// Helper functions for body markers
const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'severe': return 'bg-red-500'
    case 'moderate': return 'bg-yellow-500'
    case 'mild': return 'bg-blue-400'
    default: return 'bg-slate-400'
  }
}

const getSeverityTextColor = (severity: string): string => {
  switch (severity) {
    case 'severe': return 'text-red-400'
    case 'moderate': return 'text-yellow-400'
    case 'mild': return 'text-blue-400'
    default: return 'text-slate-400'
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
    stomach: '胃部'
  }
  return labels[region] || region
}

// Animation helper functions
const getMarkerPosition = (marker: any, axis: 'top' | 'left'): string => {
  const pos = marker.position?.[axis]
  if (typeof pos === 'number') return `${pos}%`
  if (typeof pos === 'string') return pos
  return '50%'
}

const setActiveMarker = (index: number) => {
  activeMarkerIndex.value = index
}

const startMarkerAnimation = () => {
  // Clear any existing timer
  stopMarkerAnimation()
  
  // Reset visible indices
  visibleMarkerIndices.value = []
  activeMarkerIndex.value = 0
  
  // Staggered reveal of markers
  const markers = currentBodyMarkers.value
  markers.forEach((_: any, idx: number) => {
    setTimeout(() => {
      visibleMarkerIndices.value.push(idx)
    }, idx * 500 + 300) // 500ms delay between each marker
  })
  
  // Start auto-play after all markers are visible
  setTimeout(() => {
    markerAnimationTimer.value = window.setInterval(() => {
      if (activeMarkerIndex.value === null) {
        activeMarkerIndex.value = 0
      } else {
        activeMarkerIndex.value = (activeMarkerIndex.value + 1) % markers.length
      }
    }, 3000) // Switch every 3 seconds
  }, markers.length * 500 + 1000)
}

const stopMarkerAnimation = () => {
  if (markerAnimationTimer.value) {
    clearInterval(markerAnimationTimer.value)
    markerAnimationTimer.value = null
  }
}

const getSeverityBadgeClass = (severity: string): string => {
  switch (severity) {
    case 'severe': return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
    case 'moderate': return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
    case 'mild': return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
    default: return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-400'
  }
}

const getSeverityLabel = (severity: string): string => {
  switch (severity) {
    case 'severe': return '严重'
    case 'moderate': return '中度'
    case 'mild': return '轻度'
    default: return '未知'
  }
}

// Actions
const toggleDarkMode = () => {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }
}

const loadDemoCase = async () => {
  loading.value = true
  try {
    // Mock Data
    await new Promise(resolve => setTimeout(resolve, 800)) // Fake delay
    
    const mockFrontpage = {
      basic_info: {
        patient_name: '张三',
        gender_text: '男',
        age_years: 58,
        id_number: '510102196601151234',
        birth_date: '1966-01-15',
        marital_status_text: '已婚',
        occupation: '退休教师',
        current_address: '四川省成都市武侯区人民南路100号'
      },
      hospitalization: {
        medical_record_no: '2026010001',
        admission_times_in_hospital: 3,
        admission_datetime: '2026-01-01 10:30',
        discharge_datetime: '2026-01-04 14:00',
        admission_dept: '心内科',
        discharge_dept: '心内科',
        actual_hospital_days: 3,
        payment_method_text: '城镇职工医保'
      },
      diagnoses: {
        discharge_main_diagnosis_text: '高血压3级 极高危',
        discharge_main_icd: 'I10.x00',
        admission_condition: '有',
        discharge_other_diagnoses_texts: [
          '2型糖尿病',
          '冠状动脉粥样硬化性心脏病'
        ]
      },
      procedures: {
        main_procedure_text: '冠状动脉造影术',
        main_procedure_code: '88.55',
        main_procedure_date: '2026-01-02',
        surgeon_name: '李医生',
        anesthesia_method: '局部麻醉',
        incision_healing_grade: '甲/I'
      }
    }

    const mockMedicalText = `入院记录

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

    demoCase.value = {
      case_id: 'demo_mock_case',
      description: '演示病例 - 高血压合并冠心病',
      medical_text: mockMedicalText,
      frontpage: null, // 不直接加载，需要用户点击"开始 AI 提取"
      insurance_claim: null // 也延迟加载
    }
    
    message.success('测试病历加载成功')
  } catch (error: any) {
    console.error('加载病案首页草稿失败:', error)
    message.error(error?.message || '加载病案首页草稿失败')
  } finally {
    loading.value = false
  }
}

// AI 结构化提取函数（使用 LLM 从原文提取全量首页字段）
const extractStructuredData = async () => {
  if (!demoCase.value?.medical_text) {
    message.warning('请先加载病历原文')
    return
  }
  
  extracting.value = true
  try {
    // 调用 LLM 全量提取 API
    const response = await fetch('/api/v1/frontpage/auto-generate-draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        medical_text: demoCase.value.medical_text
      })
    })
    
    const data = await response.json()
    
    if (response.ok && data.success && data.data?.frontpage) {
      // 使用 LLM 提取的完整首页数据
      const fp = data.data.frontpage
      
      if (demoCase.value) {
        // 映射 LLM 返回的数据到前端展示结构
        demoCase.value.frontpage = {
          basic_info: {
            patient_name: fp.basic_info?.patient_name || '未识别',
            gender_text: fp.basic_info?.gender_text || '未知',
            age_years: fp.basic_info?.age_years || 0,
            birth_date: fp.basic_info?.birth_date || '',
            id_number: fp.basic_info?.id_number || '',
            nationality: fp.basic_info?.nationality || '',
            native_place: fp.basic_info?.current_address || '',
            marriage: fp.basic_info?.marital_status_text || '',
            job: fp.basic_info?.occupation || ''
          },
          hospitalization: {
            admission_date: fp.hospitalization?.admission_datetime || '',
            discharge_date: fp.hospitalization?.discharge_datetime || '',
            hospital_days: fp.hospitalization?.actual_hospital_days || 0,
            admitted_dept: fp.hospitalization?.admission_dept || '',
            discharged_dept: fp.hospitalization?.discharge_dept || '',
            admission_way: fp.hospitalization?.admission_way_text || '',
            leaving_way: '医嘱离院'
          },
          diagnoses: {
            discharge_main_diagnosis_text: fp.diagnoses?.discharge_main_diagnosis_text || '未识别',
            discharge_main_icd: fp.diagnoses?.discharge_main_icd || '待编码',
            discharge_main_conn: '有',
            discharge_other_diagnoses: (fp.diagnoses?.discharge_other_diagnoses_texts || []).map((name: string, idx: number) => ({
              name: name,
              code: fp.diagnoses?.discharge_other_diagnoses?.[idx]?.code || '待编码',
              conn: '有'
            }))
          },
          procedures: {
            main: {
              name: fp.procedures?.main_procedure_text || '无',
              code: fp.procedures?.main_procedure_code || '',
              date: fp.procedures?.main_procedure_date || '',
              surgeon: fp.procedures?.surgeon_name || '',
              anesthesia: fp.procedures?.anesthesia_method || '',
              level: fp.procedures?.main_procedure_level || ''
            },
            others: []
          },
          quality: {
            director: fp.staff?.director || '',
            chief_doctor: fp.staff?.chief_physician || '',
            attending_doctor: fp.staff?.attending_physician || '',
            coder: 'AI 预编'
          }
        }
        
        // 医保清单（费用信息）
        demoCase.value.insurance_claim = {
          settlement_id: 'SET' + Date.now(),
          insurance_type: fp.hospitalization?.payment_method_text || '城镇职工基本医疗保险',
          total_cost: fp.costs?.total_cost || 0,
          fund_pay: fp.costs?.total_cost ? fp.costs.total_cost * 0.8 : 0,
          patient_pay: fp.costs?.self_paid || 0
        }
      }
      
      message.success('AI 病案首页提取完成')
    } else {
      // API 调用失败，使用 fallback mock 数据
      console.warn('LLM 提取失败，使用模拟数据:', data.error || data.detail || 'Unknown error')
      useMockFallback()
      message.warning('LLM 服务暂不可用，已使用模拟数据')
    }
  } catch (error: any) {
    console.error('结构化提取失败:', error)
    // 网络错误等，使用 fallback
    useMockFallback()
    message.warning('网络请求失败，已使用模拟数据')
  } finally {
    extracting.value = false
  }
}

// Fallback mock 数据
const useMockFallback = () => {
  const mockFrontpage = {
    basic_info: {
      patient_name: '张三',
      gender_text: '男',
      age_years: 58,
      birth_date: '1966-01-15',
      id_number: '510102196601151234',
      nationality: '中国',
      native_place: '四川成都',
      marriage: '已婚',
      job: '退休人员'
    },
    hospitalization: {
      admission_date: '2025-12-28 09:30',
      discharge_date: '2026-01-04 10:00',
      hospital_days: 7,
      admitted_dept: '心血管内科',
      discharged_dept: '心血管内科',
      admission_way: '急诊',
      leaving_way: '医嘱离院'
    },
    diagnoses: {
      discharge_main_diagnosis_text: '高血压3级 极高危',
      discharge_main_icd: 'I10.x00',
      discharge_main_conn: '有', // 入院病情
      discharge_other_diagnoses: [
          { name: '2型糖尿病', code: 'E11.900', conn: '有' },
          { name: '冠状动脉粥样硬化性心脏病', code: 'I25.100', conn: '有' },
          { name: '高脂血症', code: 'E78.500', conn: '有' }
      ]
    },
    procedures: {
        main: {
            name: '冠状动脉造影术',
            code: '88.55',
            date: '2026-01-02',
            surgeon: '李医生',
            anesthesia: '局麻',
            level: 'III级'
        },
        others: []
    },
    quality: { // 质控部分
        director: '王院长',
        chief_doctor: '赵主任',
        attending_doctor: '李医生',
        coder: '张编码'
    }
  }
  
  if (demoCase.value) {
    demoCase.value.frontpage = mockFrontpage
    demoCase.value.insurance_claim = {
      settlement_id: 'SET2026010001',
      insurance_type: '城镇职工基本医疗保险',
      total_cost: 12580.50,
      fund_pay: 10064.40,
      patient_pay: 2516.10
    }
  }
}
const analyzeProfile = async () => {
  if (!demoCase.value?.medical_text) return
  
  profileLoading.value = true
  try {
    // Call the correct backend API endpoint
    const response = await fetch('/api/v1/case-front-page/analyze-profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        medical_text: demoCase.value.medical_text,
        frontpage_diagnoses: frontpage.value?.diagnoses?.discharge_main_diagnosis_text 
          ? [frontpage.value.diagnoses.discharge_main_diagnosis_text] 
          : [],
        frontpage_procedures: frontpage.value?.procedures?.main_procedure_text 
          ? [frontpage.value.procedures.main_procedure_text] 
          : []
      })
    })
    const data = await response.json()
    
    if (data.success && data.data) {
       profile.value = data.data
       
       // Update charts with real data from LLM
       if (data.data.vital_signs?.blood_pressure?.values) {
         const bpData = data.data.vital_signs.blood_pressure.values
         vitalsChartOption.value.xAxis.data = bpData.map((v: any) => v.time)
         vitalsChartOption.value.series[0].data = bpData.map((v: any) => v.systolic)
         vitalsChartOption.value.series[1].data = bpData.map((v: any) => v.diastolic)
       }
       
       if (data.data.lab_results) {
         const labs = data.data.lab_results
         labsChartOption.value.series[0].data[0].value = [
           labs.blood_glucose?.value || 0,
           labs.cholesterol?.value || 0,
           labs.triglycerides?.value || 0,
           labs.ldl?.value || 0,
           labs.creatinine?.value || 0
         ]
       }
       
       if (data.data.risk_assessment?.overall_risk_score) {
         riskGaugeOption.value.series[0].data[0].value = data.data.risk_assessment.overall_risk_score
       }
       
       message.success('AI 画像分析完成')
       
       // Start staggered animation for body markers
       startMarkerAnimation()
    } else {
       // Fallback mock profile if backend not ready
       profile.value = {
         diagnosis_timeline: [{ date: '2026-01-01', event: '因胸闷心悸入院', type: 'symptom', severity: 'moderate' }],
         vital_signs: {},
         lab_results: {},
         risk_assessment: { overall_risk_score: 85, risk_level: 'high', primary_risks: [], recommendations: [] },
         body_markers: [],
         discrepancies: []
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
const isExpanded = ref(false)

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value
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
