<template>
  <!-- Extracting state (only show when no data yet) -->
  <!-- Extracting state (Organic AI) -->
  <div
    v-if="extracting && !hasAnyData"
    class="flex flex-col h-full min-h-[500px] bg-white dark:bg-slate-900 rounded-xl flex-1 relative z-0"
  >
    <div class="flex-1 flex flex-col items-center justify-center p-8 mt-4">
      <!-- 1. Organic Pulse Ring -->
      <div class="relative w-40 h-40 flex items-center justify-center mb-10">
        <div
          class="absolute inset-0 bg-blue-500/10 dark:bg-blue-500/20 rounded-full animate-ping shadow-[0_0_30px_rgba(59,130,246,0.3)]"
          style="animation-duration: 2.5s"
        />
        <div
          class="absolute inset-4 bg-gradient-to-br from-blue-300/40 to-indigo-500/40 rounded-full animate-pulse blur-sm"
          style="animation-duration: 2s"
        />
        <div
          class="absolute inset-8 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-[0_8px_32px_rgba(59,130,246,0.5)] z-10 w-[100px] h-[100px] mx-auto border-[4px] border-white/20 dark:border-white/10"
        >
          <RobotOutlined class="text-white text-4xl opacity-90" />
        </div>
      </div>

      <!-- 2. Text Content -->
      <h2 class="text-2xl font-bold text-slate-800 dark:text-slate-100 mb-4 tracking-tight">
        AI 智能提取中...
      </h2>
      <p
        class="text-slate-500 dark:text-slate-400 text-sm max-w-[320px] text-center mb-12 leading-relaxed"
      >
        正在阅读病历记录并提取诊断、手术等<br>首页数据结构
      </p>

      <!-- 3. Progress Stages -->
      <div
        v-if="extractionProgress"
        class="w-full max-w-md"
      >
        <div class="flex justify-between text-xs font-bold text-slate-500 dark:text-slate-400 mb-3">
          <span>{{ extractionProgress.currentModule ? '正在解析...' : '正在初始化...' }}</span>
          <span class="font-mono text-blue-600 dark:text-blue-400">{{ extractionProgress.percent }}%</span>
        </div>

        <!-- Background Track -->
        <div
          class="w-full h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-visible relative flex items-center shadow-inner"
        >
          <!-- Active Bar -->
          <div
            class="absolute left-0 top-0 h-full bg-gradient-to-r from-blue-400 to-indigo-500 rounded-full transition-all duration-700 ease-out z-0"
            :style="{ width: extractionProgress.percent + '%' }"
          />

          <!-- Nodes -->
          <div class="absolute w-full flex justify-between z-10 -ml-1.5 pr-3">
            <!-- Node 1 -->
            <div
              class="w-3.5 h-3.5 rounded-full border-[2.5px] border-white dark:border-slate-900 bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.5)] transition-colors duration-300"
            />
            <!-- Node 2 -->
            <div
              class="w-3.5 h-3.5 rounded-full border-[2.5px] border-white dark:border-slate-900 shadow-sm transition-colors duration-500 delay-200"
              :class="
                extractionProgress.percent >= 40
                  ? 'bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]'
                  : 'bg-slate-200 dark:bg-slate-700'
              "
            />
            <!-- Node 3 -->
            <div
              class="w-3.5 h-3.5 rounded-full border-[2.5px] border-white dark:border-slate-900 shadow-sm transition-colors duration-500 delay-200"
              :class="
                extractionProgress.percent >= 80
                  ? 'bg-purple-500 shadow-[0_0_8px_rgba(168,85,247,0.5)]'
                  : 'bg-slate-200 dark:bg-slate-700'
              "
            />
          </div>
        </div>

        <!-- Node Labels -->
        <div class="flex justify-between mt-3 px-1">
          <span class="text-[11px] font-bold text-slate-700 dark:text-slate-300 -ml-3">读取原文</span>
          <span
            class="text-[11px] font-bold text-slate-700 dark:text-slate-300 opacity-60 transition-opacity"
            :style="{ opacity: extractionProgress.percent >= 40 ? 1 : 0.6 }"
          >实体识别</span>
          <span
            class="text-[11px] font-bold text-slate-700 dark:text-slate-300 opacity-60 transition-opacity"
            :style="{ opacity: extractionProgress.percent >= 80 ? 1 : 0.6 }"
          >结构生成</span>
        </div>
      </div>
    </div>

    <!-- 4. Live Log Panel -->
    <div
      class="h-36 bg-slate-50 border-t border-slate-100 dark:bg-slate-800/80 dark:border-slate-700 p-5 font-mono text-[11px] flex flex-col justify-end mx-4 mb-4 rounded-xl relative overflow-hidden group"
    >
      <!-- Top fixed header inside log -->
      <div
        class="absolute top-0 left-0 w-full h-8 bg-gradient-to-b from-slate-50 to-transparent dark:from-slate-800/80 pointer-events-none z-10"
      />

      <div class="flex flex-col gap-2 text-slate-500 dark:text-slate-400 z-0 relative">
        <p class="font-bold mb-1 opacity-50 flex items-center gap-1.5">
          <span class="w-2 h-2 rounded-full bg-slate-300 dark:bg-slate-600" /> Live Log
        </p>
        <p class="opacity-40 filter blur-[0.3px]">
          Live Log: Parsing text segments...
        </p>
        <p class="opacity-60 transition-all">
          > Extracting {{ extractionProgress?.currentModule || 'ICD-10 codes' }}...
        </p>
        <p class="font-bold text-slate-700 dark:text-slate-200 tracking-tight">
          > Analyzing procedural structures...
          <span class="animate-pulse font-bold text-blue-500 text-xs">_</span>
        </p>
      </div>
    </div>

    <!-- 5. Footer -->
    <div
      class="h-10 flex-shrink-0 bg-transparent flex items-center justify-between px-6 text-[11px] text-slate-400 font-bold max-w-full pb-2"
    >
      <div class="flex items-center gap-2">
        <span
          class="w-1.5 h-1.5 rounded-full bg-[#10b981] shadow-[0_0_6px_#10b981] animate-pulse"
        />
        System Online
      </div>
      <div>Model: MedBERT-v4.2</div>
    </div>
  </div>
  <!-- Has frontpage data (show progressively even while still extracting) -->
  <div
    v-else-if="frontpage || hasAnyData"
    class="space-y-6 pb-10"
  >
    <!-- Progressive extraction indicator -->
    <div
      v-if="extracting"
      class="bg-blue-50 dark:bg-blue-900/20 px-4 py-3 rounded-lg border border-blue-100 dark:border-blue-800/30"
    >
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400">
          <a-spin size="small" />
          <span>正在提取: {{ extractionProgress?.currentModule || '...' }}</span>
        </div>
        <span class="text-xs font-medium text-blue-600 dark:text-blue-400">{{ extractionProgress?.percent || 0 }}%</span>
      </div>
      <div class="w-full h-1.5 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-500 ease-out"
          :style="{ width: (extractionProgress?.percent || 0) + '%' }"
        />
      </div>
      <div class="flex flex-wrap gap-1.5 mt-2">
        <span
          v-for="mod in allModules"
          :key="mod.key"
          :class="[
            'text-xs px-2 py-0.5 rounded-full transition-all',
            extractionProgress?.completed?.includes(mod.key)
              ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
              : 'bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500',
          ]"
        >
          {{ extractionProgress?.completed?.includes(mod.key) ? '✓' : '○' }} {{ mod.label }}
        </span>
      </div>
    </div>
    <!-- 提取完成状态横幅（持久显示） -->
    <div
      v-if="!extracting && extractionStatus === 'completed'"
      class="flex items-center gap-2.5 px-4 py-3 rounded-lg bg-[#f0fdf4] dark:bg-emerald-900/20 border border-[#bbf7d0] dark:border-emerald-800/30 shadow-[0_2px_10px_rgba(22,163,74,0.05)]"
    >
      <span
        class="text-[#16a34a] dark:text-emerald-400 text-sm font-bold tracking-wide flex items-center gap-2"
      ><CheckCircleFilled v-if="false" />✅ AI 提取完成，共提取
        {{ extractionProgress?.completed?.length || 0 }} 个模块</span>
    </div>
    <div
      v-else-if="!extracting && extractionStatus === 'mock_fallback'"
      class="flex items-center gap-2.5 px-4 py-3 rounded-lg bg-[#fffbeb] dark:bg-orange-900/20 border border-[#fde68a] dark:border-orange-800/30 shadow-sm"
    >
      <span class="text-[#d97706] dark:text-orange-400 text-sm font-bold tracking-wide">⚠️ LLM 连接失败，当前显示的是模拟数据（非真实提取结果）</span>
    </div>
    <!-- 1. Basic Info & Hospitalization (Grid) -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-5">
      <!-- Basic Info -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)]"
      >
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 mb-5 flex items-center gap-2"
        >
          <UserOutlined class="text-blue-500 text-base" /> 患者基本信息
        </h4>
        <div class="grid grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-4 text-sm">
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              姓名
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.patient_name || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              性别
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.gender_text || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              年龄
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.age_years ? frontpage.basic_info.age_years + ' 岁' : '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              出生日期
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.birth_date || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              国籍
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.nationality || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              民族
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.ethnicity || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              婚姻状况
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.marital_status_text || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              职业
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.occupation || frontpage.basic_info?.job || '-' }}
            </div>
          </div>
          <div class="col-span-2 lg:col-span-1">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              身份证号
            </div>
            <div class="font-medium font-mono dark:text-slate-200">
              {{ frontpage.basic_info?.id_number || '-' }}
            </div>
          </div>
          <div class="col-span-2 lg:col-span-3">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              现住址
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.current_address || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              联系人
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.contact_name || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              联系人关系
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.contact_relation || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              联系人电话
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.basic_info?.contact_phone || '-' }}
            </div>
          </div>
        </div>
      </div>

      <!-- Hospitalization -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)]"
      >
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 mb-5 flex items-center gap-2"
        >
          <HistoryOutlined class="text-blue-500 text-base" /> 住院过程信息
        </h4>
        <div class="grid grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-4 text-sm">
          <div class="col-span-2 lg:col-span-3">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              医疗机构
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization?.hospital_name || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              病案号
            </div>
            <div class="font-medium font-mono dark:text-slate-200">
              {{ frontpage.hospitalization?.medical_record_no || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              住院次数
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{
                frontpage.hospitalization?.admission_times_in_hospital
                  ? '第 ' + frontpage.hospitalization.admission_times_in_hospital + ' 次'
                  : '-'
              }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              医疗付费方式
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization?.payment_method_text || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              入院途径
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization?.admission_way_text || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              入院日期
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{
                frontpage.hospitalization?.admission_datetime ||
                  frontpage.hospitalization?.admission_date ||
                  '-'
              }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              出院日期
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{
                frontpage.hospitalization?.discharge_datetime ||
                  frontpage.hospitalization?.discharge_date ||
                  '-'
              }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              入院科室
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{
                frontpage.hospitalization?.admission_dept ||
                  frontpage.hospitalization?.admitted_dept ||
                  '-'
              }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              出院科室
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{
                frontpage.hospitalization?.discharge_dept ||
                  frontpage.hospitalization?.discharged_dept ||
                  '-'
              }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              入院病房
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization?.admission_ward || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              出院病房
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization?.discharge_ward || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              住院天数
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{
                frontpage.hospitalization?.actual_hospital_days ||
                  frontpage.hospitalization?.hospital_days
                  ? (frontpage.hospitalization?.actual_hospital_days ||
                    frontpage.hospitalization?.hospital_days) + ' 天'
                  : '-'
              }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              离院方式
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization?.leaving_hospital_way || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              31天内再住院
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization?.rehospital_within_month || '-' }}
            </div>
          </div>
          <div
            v-if="frontpage.hospitalization?.rehospital_purpose"
            class="col-span-2"
          >
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              再住院目的
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.hospitalization.rehospital_purpose }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. Diagnoses (Dynamic: Admission and/or Discharge) -->
    <!-- Admission Diagnosis Table -->
    <div
      v-if="hasAdmissionDiagnosis"
      class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)] overflow-hidden"
    >
      <div
        class="bg-white dark:bg-slate-800 px-5 py-4 border-b border-slate-100 dark:border-slate-700/50 flex justify-between items-center"
      >
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2"
        >
          <MedicineBoxOutlined class="text-blue-500 text-base" /> 入院诊断
        </h4>
        <span
          class="text-[11px] font-bold bg-[#f0fdf4] text-[#16a34a] border border-[#bbf7d0] px-2 py-0.5 rounded"
        >ICD-10</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead
            class="bg-slate-50/50 dark:bg-slate-800/80 text-slate-400 dark:text-slate-400 font-bold text-[12px]"
          >
            <tr>
              <th class="px-4 py-3 w-20">
                类型
              </th>
              <th class="px-4 py-3 w-32">
                ICD编码
              </th>
              <th class="px-4 py-3">
                诊断名称
              </th>
              <th class="px-4 py-3 w-24">
                入院病情
              </th>
              <th class="px-4 py-3 w-24 text-center">
                AI置信度
              </th>
            </tr>
          </thead>
          <tbody
            class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50"
          >
            <!-- Admission Main Diagnosis -->
            <tr
              v-if="frontpage.diagnoses.admission_main_diagnosis_text"
              class="hover:bg-slate-50 dark:hover:bg-slate-700/50"
            >
              <td class="px-4 py-3">
                <span
                  class="bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded text-xs font-medium dark:bg-blue-900/50 dark:text-blue-300"
                >主要</span>
              </td>
              <td class="px-4 py-3">
                <input
                  type="text"
                  :value="frontpage.diagnoses.admission_main_icd || ''"
                  placeholder="待编码"
                  class="font-mono text-sm w-28 px-2 py-1 border border-slate-200 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none"
                  @change="
                    (e) =>
                      handleCodeChange('admission_main_icd', (e.target as HTMLInputElement).value)
                  "
                >
              </td>
              <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">
                {{ frontpage.diagnoses.admission_main_diagnosis_text }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ frontpage.diagnoses.admission_main_conn || '-' }}
              </td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[95%]" />
                  </div>
                </div>
              </td>
            </tr>
            <!-- Admission Other Diagnoses -->
            <tr
              v-for="(diag, idx) in admissionOtherDiagnoses"
              :key="'adm-' + idx"
              class="hover:bg-slate-50 dark:hover:bg-slate-700/50"
            >
              <td class="px-4 py-3">
                <span class="text-slate-400 text-xs">其他</span>
              </td>
              <td
                class="px-4 py-3 font-mono"
                :class="
                  isValidIcdCode(diag.code)
                    ? 'text-slate-600 dark:text-slate-300'
                    : 'text-slate-400 dark:text-slate-500 italic'
                "
              >
                {{ diag.code || '待编码' }}
              </td>
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                {{ diag.name }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ diag.conn || '-' }}
              </td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[88%]" />
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Discharge Diagnosis Table -->
    <div
      v-if="hasDischargeDiagnosis"
      class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)] overflow-hidden mt-6"
    >
      <div
        class="bg-white dark:bg-slate-800 px-5 py-4 border-b border-slate-100 dark:border-slate-700/50 flex justify-between items-center"
      >
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2"
        >
          <MedicineBoxOutlined class="text-green-500 text-base" /> 出院诊断
        </h4>
        <span
          class="text-[11px] font-bold bg-[#f0fdf4] text-[#16a34a] border border-[#bbf7d0] px-2 py-0.5 rounded"
        >ICD-10</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead
            class="bg-slate-50/50 dark:bg-slate-800/80 text-slate-400 dark:text-slate-400 font-bold text-[12px]"
          >
            <tr>
              <th class="px-4 py-3 w-20">
                类型
              </th>
              <th class="px-4 py-3 w-32">
                ICD编码
              </th>
              <th class="px-4 py-3">
                诊断名称
              </th>
              <th class="px-4 py-3 w-24">
                入院病情
              </th>
              <th class="px-4 py-3 w-24 text-center">
                AI置信度
              </th>
            </tr>
          </thead>
          <tbody
            class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50"
          >
            <!-- Discharge Main Diagnosis -->
            <tr
              v-if="frontpage.diagnoses.discharge_main_diagnosis_text"
              class="hover:bg-slate-50 dark:hover:bg-slate-700/50"
            >
              <td class="px-4 py-3">
                <span
                  class="bg-green-100 text-green-700 px-1.5 py-0.5 rounded text-xs font-medium dark:bg-green-900/50 dark:text-green-300"
                >主要</span>
              </td>
              <td class="px-4 py-3">
                <input
                  type="text"
                  :value="frontpage.diagnoses.discharge_main_icd || ''"
                  placeholder="待编码"
                  class="font-mono text-sm w-28 px-2 py-1 border border-slate-200 dark:border-slate-600 rounded bg-white dark:bg-slate-700 text-slate-600 dark:text-slate-300 focus:border-green-500 focus:ring-1 focus:ring-green-500 outline-none"
                  @change="
                    (e) =>
                      handleCodeChange('discharge_main_icd', (e.target as HTMLInputElement).value)
                  "
                >
              </td>
              <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">
                {{ frontpage.diagnoses.discharge_main_diagnosis_text }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ frontpage.diagnoses.discharge_main_conn || '-' }}
              </td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[95%]" />
                  </div>
                </div>
              </td>
            </tr>
            <!-- Discharge Other Diagnoses -->
            <tr
              v-for="(diag, idx) in dischargeOtherDiagnoses"
              :key="'dis-' + idx"
              class="hover:bg-slate-50 dark:hover:bg-slate-700/50"
            >
              <td class="px-4 py-3">
                <span class="text-slate-400 text-xs">其他</span>
              </td>
              <td
                class="px-4 py-3 font-mono"
                :class="
                  isValidIcdCode(diag.code)
                    ? 'text-slate-600 dark:text-slate-300'
                    : 'text-slate-400 dark:text-slate-500 italic'
                "
              >
                {{ diag.code || '待编码' }}
              </td>
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                {{ diag.name }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ diag.conn || '-' }}
              </td>
              <td class="px-4 py-3 text-center">
                <div class="flex items-center justify-center gap-1 text-green-600">
                  <div class="w-16 h-1.5 bg-slate-200 rounded-full overflow-hidden">
                    <div class="h-full bg-green-500 w-[88%]" />
                  </div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 3. Procedures (Table) -->
    <div
      class="bg-white dark:bg-slate-800 rounded-xl border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)] overflow-hidden mt-6 mb-6"
    >
      <div
        class="bg-white dark:bg-slate-800 px-5 py-4 border-b border-slate-100 dark:border-slate-700/50 flex justify-between items-center"
      >
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2"
        >
          <ScissorOutlined class="text-orange-500 text-base" /> 手术操作
        </h4>
        <span
          class="text-[11px] font-bold bg-[#fffbeb] text-[#d97706] border border-[#fde68a] px-2 py-0.5 rounded"
        >ICD-9-CM-3</span>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-sm text-left">
          <thead
            class="bg-slate-50/50 dark:bg-slate-800/80 text-slate-400 dark:text-slate-400 font-bold text-[12px]"
          >
            <tr>
              <th class="px-4 py-3 w-32">
                手术编码
              </th>
              <th class="px-4 py-3">
                手术名称
              </th>
              <th class="px-4 py-3 w-32">
                手术日期
              </th>
              <th class="px-4 py-3 w-24">
                术者
              </th>
              <th class="px-4 py-3 w-24">
                I助/II助
              </th>
              <th class="px-4 py-3 w-24">
                麻醉方式
              </th>
              <th class="px-4 py-3 w-20">
                切口等级
              </th>
              <th class="px-4 py-3 w-20">
                愈合等级
              </th>
              <th class="px-4 py-3 w-20">
                ASA分级
              </th>
            </tr>
          </thead>
          <tbody
            class="divide-y divide-slate-100 dark:divide-slate-700 bg-white dark:bg-slate-800/50"
          >
            <tr v-if="frontpage.procedures.main?.code || frontpage.procedures?.main_procedure_text">
              <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">
                {{
                  frontpage.procedures.main?.code ||
                    frontpage.procedures?.main_procedure_code ||
                    '-'
                }}
              </td>
              <td class="px-4 py-3 font-medium text-slate-900 dark:text-white">
                {{
                  frontpage.procedures.main?.name ||
                    frontpage.procedures?.main_procedure_text ||
                    '-'
                }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{
                  frontpage.procedures.main?.date ||
                    frontpage.procedures?.main_procedure_date ||
                    '-'
                }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{
                  frontpage.procedures.main?.surgeon || frontpage.procedures?.surgeon_name || '-'
                }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400 text-xs">
                {{ frontpage.procedures?.assistant1_name || '-' }} /
                {{ frontpage.procedures?.assistant2_name || '-' }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{
                  frontpage.procedures.main?.anesthesia ||
                    frontpage.procedures?.anesthesia_method ||
                    '-'
                }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ frontpage.procedures?.incision_grade || '-' }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ frontpage.procedures?.incision_healing_grade || '-' }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ frontpage.procedures?.anesthesia_grade || '-' }}
              </td>
            </tr>
            <!-- 手术时间和特殊标记行 -->
            <tr
              v-if="
                frontpage.procedures?.main_procedure_start_time ||
                  frontpage.procedures?.unplanned_reoperation
              "
              class="bg-slate-50/50 dark:bg-slate-800/30"
            >
              <td
                colspan="3"
                class="px-4 py-2 text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
              >
                <span v-if="frontpage.procedures?.main_procedure_start_time">开始: {{ frontpage.procedures.main_procedure_start_time }}</span>
                <span
                  v-if="frontpage.procedures?.main_procedure_end_time"
                  class="ml-3"
                >结束: {{ frontpage.procedures.main_procedure_end_time }}</span>
              </td>
              <td
                colspan="3"
                class="px-4 py-2 text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
              >
                <span v-if="frontpage.procedures?.anesthetist_name">麻醉医师: {{ frontpage.procedures.anesthetist_name }}</span>
              </td>
              <td
                colspan="3"
                class="px-4 py-2 text-xs"
              >
                <span
                  v-if="frontpage.procedures?.unplanned_reoperation === '是'"
                  class="text-red-600 font-medium"
                >⚠ 非计划再手术</span>
              </td>
            </tr>
            <tr
              v-for="(proc, idx) in frontpage.procedures.others"
              :key="idx"
            >
              <td class="px-4 py-3 font-mono text-slate-600 dark:text-slate-300">
                {{ proc.code }}
              </td>
              <td class="px-4 py-3 text-slate-700 dark:text-slate-300">
                {{ proc.name }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ proc.date }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                {{ proc.surgeon }}
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                -
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                -
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                -
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                -
              </td>
              <td class="px-4 py-3 text-slate-600 dark:text-slate-400">
                -
              </td>
            </tr>
            <tr
              v-if="
                !frontpage.procedures.main?.code &&
                  !frontpage.procedures?.main_procedure_text &&
                  (!frontpage.procedures.others || frontpage.procedures.others.length === 0)
              "
            >
              <td
                colspan="9"
                class="px-4 py-8 text-center text-slate-400"
              >
                无手术操作
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 4. Other Medical Info & Staff (Grid) -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <!-- Other Medical Info -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)]"
      >
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 mb-5 flex items-center gap-2"
        >
          <HeartOutlined class="text-red-500" /> 其他医疗信息
        </h4>
        <div class="grid grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-4 text-sm">
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              药物过敏
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              <span
                v-if="
                  frontpage.other_medical_info?.drug_allergy_flag === '1' ||
                    frontpage.other_medical_info?.drug_allergy_flag === 1
                "
                class="text-green-600"
              >无</span>
              <span
                v-else-if="
                  frontpage.other_medical_info?.drug_allergy_flag === '2' ||
                    frontpage.other_medical_info?.drug_allergy_flag === 2
                "
                class="text-red-600"
              >
                有: {{ frontpage.other_medical_info?.drug_allergy_drugs?.join(', ') || '未知' }}
              </span>
              <span v-else>-</span>
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              ABO 血型
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info?.abo_blood_type || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              Rh 血型
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info?.rh_blood_type_text || '-' }}
            </div>
          </div>
          <div
            v-if="frontpage.other_medical_info?.pathology_text"
            class="col-span-2 lg:col-span-3"
          >
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              病理诊断
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info.pathology_text }}
            </div>
          </div>
          <div v-if="frontpage.other_medical_info?.pathology_no">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              病理号
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info.pathology_no }}
            </div>
          </div>
          <div v-if="frontpage.other_medical_info?.ventilation_hours">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              机械通气时长
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info.ventilation_hours }} 小时
            </div>
          </div>
          <div v-if="frontpage.other_medical_info?.icu_type">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              ICU 类型
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info.icu_type }}
            </div>
          </div>
          <div v-if="frontpage.other_medical_info?.icu_enter_time">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              进入 ICU 时间
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info.icu_enter_time }}
            </div>
          </div>
          <div v-if="frontpage.other_medical_info?.icu_leave_time">
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              退出 ICU 时间
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.other_medical_info.icu_leave_time }}
            </div>
          </div>
        </div>
      </div>

      <!-- Staff Info -->
      <div
        class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)]"
      >
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 mb-5 flex items-center gap-2"
        >
          <TeamOutlined class="text-indigo-500" /> 人员信息
        </h4>
        <div class="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              科主任
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.staff?.dept_director || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              主任/副主任医师
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.staff?.chief_physician || '-' }}
            </div>
          </div>
          <div>
            <div
              class="text-[11px] font-medium text-slate-400 dark:text-slate-500 mb-0.5 tracking-wide"
            >
              主治医师
            </div>
            <div class="text-[13px] font-bold text-slate-800 dark:text-slate-100">
              {{ frontpage.staff?.attending_physician || '-' }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              住院医师
            </div>
            <div class="font-medium dark:text-slate-200">
              {{ frontpage.staff?.resident_physician || '-' }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              责任护士
            </div>
            <div class="font-medium dark:text-slate-200">
              {{ frontpage.staff?.responsible_nurse || '-' }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              编码员
            </div>
            <div class="font-medium dark:text-slate-200">
              {{ frontpage.staff?.coder || '-' }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              质控医师
            </div>
            <div class="font-medium dark:text-slate-200">
              {{ frontpage.staff?.qc_physician || '-' }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              质控护士
            </div>
            <div class="font-medium dark:text-slate-200">
              {{ frontpage.staff?.qc_nurse || '-' }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              质控日期
            </div>
            <div class="font-medium dark:text-slate-200">
              {{ frontpage.staff?.qc_date || '-' }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500 dark:text-slate-400">
              病案质量等级
            </div>
            <div class="font-medium dark:text-slate-200">
              <span
                v-if="frontpage.staff?.medical_record_quality"
                :class="{
                  'text-green-600': frontpage.staff.medical_record_quality === '甲',
                  'text-yellow-600': frontpage.staff.medical_record_quality === '乙',
                  'text-red-600': frontpage.staff.medical_record_quality === '丙',
                }"
              >{{ frontpage.staff.medical_record_quality }}</span>
              <span v-else>-</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 5. Costs Info -->
    <div
      v-if="frontpage.costs?.total_cost"
      class="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-900/20 dark:to-teal-900/20 rounded-xl p-5 border border-emerald-100 dark:border-emerald-800/30"
    >
      <h4 class="text-sm font-bold text-slate-800 dark:text-slate-200 mb-4 flex items-center gap-2">
        <DollarOutlined class="text-emerald-600" /> 费用信息
      </h4>
      <div class="flex flex-wrap gap-6">
        <div class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 shadow-sm">
          <div class="text-xs text-slate-500 dark:text-slate-400">
            住院总费用
          </div>
          <div class="text-xl font-bold text-emerald-600 dark:text-emerald-400">
            ¥ {{ formatNumber(frontpage.costs?.total_cost) }}
          </div>
        </div>
        <div
          v-if="frontpage.costs?.self_paid"
          class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 shadow-sm"
        >
          <div class="text-xs text-slate-500 dark:text-slate-400">
            自付金额
          </div>
          <div class="text-xl font-bold text-orange-600 dark:text-orange-400">
            ¥ {{ formatNumber(frontpage.costs?.self_paid) }}
          </div>
        </div>
        <div
          v-if="frontpage.costs?.total_cost && frontpage.costs?.self_paid"
          class="bg-white dark:bg-slate-800 rounded-lg px-4 py-3 shadow-sm"
        >
          <div class="text-xs text-slate-500 dark:text-slate-400">
            医保支付
          </div>
          <div class="text-xl font-bold text-blue-600 dark:text-blue-400">
            ¥ {{ formatNumber(frontpage.costs?.total_cost - frontpage.costs?.self_paid) }}
          </div>
        </div>
      </div>
    </div>

    <!-- 6. Field Extraction Summary Table -->
    <div
      class="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200/60 dark:border-slate-700/80 shadow-[0_2px_12px_rgba(0,0,0,0.02)] mb-8"
    >
      <div class="flex items-center justify-between mb-5">
        <h4
          class="text-[13px] font-bold text-slate-700 dark:text-slate-200 flex items-center gap-2"
        >
          <span
            class="w-6 h-6 rounded-full bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center"
          >
            <span class="text-white text-xs">📊</span>
          </span>
          字段提取汇总
        </h4>
        <div class="flex items-center gap-4 text-xs">
          <div class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-green-500" />
            <span class="text-slate-600 dark:text-slate-400">已提取</span>
          </div>
          <div class="flex items-center gap-1.5">
            <span class="w-2.5 h-2.5 rounded-full bg-slate-300 dark:bg-slate-600" />
            <span class="text-slate-600 dark:text-slate-400">未识别</span>
          </div>
          <div
            class="px-2.5 py-1 bg-gradient-to-r from-green-100 to-emerald-100 dark:from-green-900/30 dark:to-emerald-900/30 rounded-full text-green-700 dark:text-green-400 font-medium"
          >
            完整度: {{ extractionStats.completeness }}%
          </div>
        </div>
      </div>

      <!-- Summary Stats Row -->
      <div class="grid grid-cols-4 gap-3 mb-4">
        <div class="bg-slate-50 dark:bg-slate-700/50 rounded-lg px-3 py-2 text-center">
          <div class="text-lg font-bold text-green-600 dark:text-green-400">
            {{ extractionStats.extracted }}
          </div>
          <div class="text-xs text-slate-500 dark:text-slate-400">
            已提取字段
          </div>
        </div>
        <div class="bg-slate-50 dark:bg-slate-700/50 rounded-lg px-3 py-2 text-center">
          <div class="text-lg font-bold text-slate-400 dark:text-slate-500">
            {{ extractionStats.missing }}
          </div>
          <div class="text-xs text-slate-500 dark:text-slate-400">
            未识别字段
          </div>
        </div>
        <div class="bg-slate-50 dark:bg-slate-700/50 rounded-lg px-3 py-2 text-center">
          <div class="text-lg font-bold text-blue-600 dark:text-blue-400">
            {{ extractionStats.total }}
          </div>
          <div class="text-xs text-slate-500 dark:text-slate-400">
            总字段数
          </div>
        </div>
        <div class="bg-slate-50 dark:bg-slate-700/50 rounded-lg px-3 py-2 text-center">
          <div class="text-lg font-bold text-purple-600 dark:text-purple-400">
            {{ extractionStats.confidence }}%
          </div>
          <div class="text-xs text-slate-500 dark:text-slate-400">
            可信度
          </div>
        </div>
      </div>

      <!-- Field Categories Table -->
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-slate-200 dark:border-slate-700">
              <th class="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium w-28">
                类别
              </th>
              <th class="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">
                字段名称
              </th>
              <th class="text-left py-2 px-3 text-slate-500 dark:text-slate-400 font-medium">
                提取值
              </th>
              <th class="text-center py-2 px-3 text-slate-500 dark:text-slate-400 font-medium w-20">
                状态
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100 dark:divide-slate-700">
            <template
              v-for="(fields, category) in fieldCategories"
              :key="category"
            >
              <tr
                v-for="(field, idx) in fields"
                :key="`${category}-${idx}`"
                class="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
              >
                <td
                  v-if="idx === 0"
                  :rowspan="fields?.length || 1"
                  class="py-2 px-3 font-medium text-slate-700 dark:text-slate-300 align-top border-r border-slate-100 dark:border-slate-700/50"
                >
                  {{ category }}
                </td>
                <td class="py-2 px-3 text-slate-600 dark:text-slate-400">
                  {{ field.label }}
                </td>
                <td class="py-2 px-3 text-slate-800 dark:text-slate-200 font-mono text-xs">
                  <span
                    v-if="field.value"
                    class="truncate block max-w-xs"
                    :title="String(field.value)"
                  >{{ truncateValue(field.value) }}</span>
                  <span
                    v-else
                    class="text-slate-400 dark:text-slate-500 italic"
                  >-</span>
                </td>
                <td class="py-2 px-3 text-center whitespace-nowrap">
                  <span
                    v-if="field.value"
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-xs whitespace-nowrap"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-green-500 flex-shrink-0" />
                    已提取
                  </span>
                  <span
                    v-else
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 text-xs whitespace-nowrap"
                  >
                    <span class="w-1.5 h-1.5 rounded-full bg-slate-400 flex-shrink-0" />
                    未识别
                  </span>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>
  </div>
  <!-- Empty state: needs extraction -->
  <div
    v-else
    class="h-full flex flex-col items-center justify-start text-center p-6 pt-4"
  >
    <div
      class="w-20 h-20 bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-blue-900/30 dark:to-indigo-900/30 rounded-2xl mb-5 flex items-center justify-center"
    >
      <RobotOutlined class="text-4xl text-blue-500" />
    </div>
    <h3 class="text-lg font-semibold text-slate-800 dark:text-white mb-2">
      AI 结构化提取
    </h3>
    <p class="text-sm text-slate-500 dark:text-slate-400 mb-6 max-w-xs">
      从病历原文中自动识别患者信息、诊断、手术操作，并映射到 ICD 标准编码。
    </p>
    <button
      :disabled="!hasMedicalText"
      class="bg-blue-500 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl text-sm font-medium transition-all shadow-lg shadow-blue-500/25 flex items-center gap-2"
      @click="$emit('extract')"
    >
      <ThunderboltOutlined />
      开始 AI 提取
    </button>
    <p
      v-if="!hasMedicalText"
      class="text-xs text-orange-500 mt-3"
    >
      请先在左侧加载病历原文
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  HistoryOutlined,
  MedicineBoxOutlined,
  RobotOutlined,
  ScissorOutlined,
  ThunderboltOutlined,
  UserOutlined,
  HeartOutlined,
  TeamOutlined,
  DollarOutlined,
} from '@ant-design/icons-vue'

const props = defineProps<{
  extracting: boolean
  extractionProgress: {
    completed: string[]
    currentModule: string
    total: number
    percent: number
  } | null
  extractionStatus: 'idle' | 'extracting' | 'completed' | 'mock_fallback'
  frontpage: any | null
  hasMedicalText: boolean
}>()

const allModules = [
  { key: 'basic_info', label: '基本信息' },
  { key: 'hospitalization', label: '住院信息' },
  { key: 'diagnoses', label: '诊断' },
  { key: 'procedures', label: '手术' },
  { key: 'other_medical_info', label: '其他医疗' },
  { key: 'staff', label: '人员' },
  { key: 'costs', label: '费用' },
  { key: 'coding_result', label: 'ICD编码' },
  { key: 'confidence', label: '校验' },
]

const emit = defineEmits<{
  (e: 'extract'): void
  (e: 'codeChange', field: string, value: string): void
}>()

// 处理编码变更
const handleCodeChange = (field: string, value: string) => {
  emit('codeChange', field, value)
}

// 格式化数字
const formatNumber = (num: number | null | undefined): string => {
  if (num === null || num === undefined) return '-'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 离院方式映射
const getDischargeMethodText = (code: number | null | undefined): string => {
  const map: Record<number, string> = {
    1: '医嘱离院',
    2: '医嘱转院',
    3: '医嘱转社区',
    4: '非医嘱离院',
    5: '死亡',
    9: '其他',
  }
  return code ? map[code] || '-' : '-'
}

// 检查是否有任何数据（用于渐进式显示）
const hasAnyData = computed(() => {
  const fp = props.frontpage
  if (!fp) return false
  return !!(
    fp.basic_info?.patient_name ||
    fp.hospitalization?.hospital_name ||
    fp.diagnoses?.discharge_main_diagnosis_text ||
    fp.procedures?.main_procedure_text
  )
})

// 检查是否有入院诊断
const hasAdmissionDiagnosis = computed(() => {
  if (!props.frontpage?.diagnoses) return false
  return !!(
    props.frontpage.diagnoses.admission_main_diagnosis_text ||
    props.frontpage.diagnoses.admission_other_diagnoses_texts?.length > 0
  )
})

// 检查是否有出院诊断
const hasDischargeDiagnosis = computed(() => {
  if (!props.frontpage?.diagnoses) return false
  return !!(
    props.frontpage.diagnoses.discharge_main_diagnosis_text ||
    props.frontpage.diagnoses.discharge_other_diagnoses_texts?.length > 0
  )
})

// 格式化入院其他诊断（合并名称和编码）
const admissionOtherDiagnoses = computed(() => {
  if (!props.frontpage?.diagnoses) return []
  const texts = props.frontpage.diagnoses.admission_other_diagnoses_texts || []
  const codes = props.frontpage.diagnoses.admission_other_icds || []

  return texts.map((name: string, index: number) => ({
    name,
    code: codes[index] || '待编码',
    conn: null,
  }))
})

// 格式化出院其他诊断（合并名称和编码）
const dischargeOtherDiagnoses = computed(() => {
  if (!props.frontpage?.diagnoses) return []
  const texts = props.frontpage.diagnoses.discharge_other_diagnoses_texts || []
  const codes = props.frontpage.diagnoses.discharge_other_icds || []

  const normalizeDiagnosisName = (name: string): string => {
    return String(name || '')
      .replace(/[（(]\s*出院转归\s*[：:]\s*[^（）()]*[）)]\s*$/u, '')
      .replace(/[，,;；]\s*出院转归\s*[：:]\s*[^，,;；。]*\s*$/u, '')
      .replace(/\s*出院转归\s*[：:]\s*[^，,;；。]*\s*$/u, '')
      .replace(/[（(]\s*$/u, '')
      .trim()
  }

  const diagnosisKey = (name: string): string => {
    return normalizeDiagnosisName(name)
      .toLowerCase()
      .replace(/[（(].*$/u, '')
      .replace(/[\s·•,，;；:：()[\]【】-]+/gu, '')
  }

  const hasRealCode = (code: string): boolean => {
    return !!code && code !== '待编码' && code !== '待人工编码'
  }

  const mainDiagnosisKey = diagnosisKey(
    props.frontpage.diagnoses.discharge_main_diagnosis_text || '',
  )
  const dedup = new Map<string, { name: string; code: string; conn: null }>()

  texts.forEach((rawName: string, index: number) => {
    const name = normalizeDiagnosisName(rawName)
    if (!name) return
    const code = codes[index] || '待编码'
    const key = diagnosisKey(name)
    if (!key) return
    if (mainDiagnosisKey && key === mainDiagnosisKey) return
    const existing = dedup.get(key)

    if (!existing) {
      dedup.set(key, { name, code, conn: null })
      return
    }

    // Prefer the row with real ICD code when duplicates collide.
    if (!hasRealCode(existing.code) && hasRealCode(code)) {
      dedup.set(key, { name, code, conn: null })
    }
  })

  return Array.from(dedup.values())
})

// 验证 ICD 编码是否有效（不是待编码状态）
const isValidIcdCode = (code: string | null | undefined): boolean => {
  if (!code) return false
  if (code === '待编码' || code === '待人工编码') return false
  return true
}

// 截断过长的值
const truncateValue = (value: any): string => {
  if (value === null || value === undefined) return '-'
  const str = String(value)
  return str.length > 40 ? str.slice(0, 40) + '...' : str
}

// 字段分类定义
const fieldCategories = computed(() => {
  const fp = props.frontpage
  if (!fp) return {}

  return {
    基本信息: [
      { label: '患者姓名', value: fp.basic_info?.patient_name },
      { label: '性别', value: fp.basic_info?.gender_text },
      { label: '年龄', value: fp.basic_info?.age_years ? `${fp.basic_info.age_years}岁` : null },
      { label: '出生日期', value: fp.basic_info?.birth_date },
      { label: '身份证号', value: fp.basic_info?.id_number },
      { label: '国籍', value: fp.basic_info?.nationality },
      { label: '民族', value: fp.basic_info?.ethnicity },
      { label: '婚姻状况', value: fp.basic_info?.marital_status_text },
      { label: '职业', value: fp.basic_info?.occupation },
      { label: '现住址', value: fp.basic_info?.current_address },
      { label: '联系人', value: fp.basic_info?.contact_name },
      { label: '联系电话', value: fp.basic_info?.contact_phone },
    ].filter((f) => true), // Keep all fields for display
    住院信息: [
      { label: '医疗机构', value: fp.hospitalization?.hospital_name },
      { label: '病案号', value: fp.hospitalization?.medical_record_no },
      { label: '住院次数', value: fp.hospitalization?.admission_times_in_hospital },
      { label: '入院日期', value: fp.hospitalization?.admission_datetime },
      { label: '出院日期', value: fp.hospitalization?.discharge_datetime },
      { label: '住院天数', value: fp.hospitalization?.actual_hospital_days },
      { label: '入院科室', value: fp.hospitalization?.admission_dept },
      { label: '出院科室', value: fp.hospitalization?.discharge_dept },
      { label: '入院病房', value: fp.hospitalization?.admission_ward },
      { label: '出院病房', value: fp.hospitalization?.discharge_ward },
      { label: '入院途径', value: fp.hospitalization?.admission_way_text },
      { label: '付费方式', value: fp.hospitalization?.payment_method_text },
      { label: '离院方式', value: fp.hospitalization?.leaving_hospital_way },
      { label: '31天内再住院', value: fp.hospitalization?.rehospital_within_month },
      { label: '再住院目的', value: fp.hospitalization?.rehospital_purpose },
    ],
    诊断信息: [
      { label: '出院主诊断', value: fp.diagnoses?.discharge_main_diagnosis_text },
      { label: '主诊断ICD编码', value: fp.diagnoses?.discharge_main_icd },
      { label: '其他诊断', value: fp.diagnoses?.discharge_other_diagnoses_texts?.join('、') },
      { label: '入院诊断', value: fp.diagnoses?.admission_main_diagnosis_text },
      { label: '入院病情', value: fp.diagnoses?.admission_condition },
      { label: '主诊断出院转归', value: fp.diagnoses?.discharge_main_outcome },
      { label: '其他诊断出院转归', value: fp.diagnoses?.discharge_other_outcomes?.join('、') },
    ],
    手术操作: [
      { label: '主要手术', value: fp.procedures?.main_procedure_text || fp.procedures?.main?.name },
      { label: '手术编码', value: fp.procedures?.main_procedure_code || fp.procedures?.main?.code },
      { label: '手术日期', value: fp.procedures?.main_procedure_date || fp.procedures?.main?.date },
      { label: '手术开始时间', value: fp.procedures?.main_procedure_start_time },
      { label: '手术结束时间', value: fp.procedures?.main_procedure_end_time },
      { label: '主刀医师', value: fp.procedures?.surgeon_name || fp.procedures?.main?.surgeon },
      { label: 'I助', value: fp.procedures?.assistant1_name },
      { label: 'II助', value: fp.procedures?.assistant2_name },
      {
        label: '麻醉方式',
        value: fp.procedures?.anesthesia_method || fp.procedures?.main?.anesthesia,
      },
      { label: '麻醉医师', value: fp.procedures?.anesthetist_name },
      { label: '切口等级', value: fp.procedures?.incision_grade },
      { label: '切口愈合等级', value: fp.procedures?.incision_healing_grade },
      { label: '麻醉分级(ASA)', value: fp.procedures?.anesthesia_grade },
      { label: '非计划再次手术', value: fp.procedures?.unplanned_reoperation },
    ],
    其他医疗信息: [
      {
        label: '药物过敏',
        value:
          fp.other_medical_info?.drug_allergy_flag === '2' ||
          fp.other_medical_info?.drug_allergy_flag === 2
            ? '有'
            : fp.other_medical_info?.drug_allergy_flag === '1' ||
                fp.other_medical_info?.drug_allergy_flag === 1
              ? '无'
              : null,
      },
      { label: 'ABO血型', value: fp.other_medical_info?.abo_blood_type },
      { label: 'Rh血型', value: fp.other_medical_info?.rh_blood_type_text },
      { label: '病理诊断', value: fp.other_medical_info?.pathology_text },
      { label: '病理号', value: fp.other_medical_info?.pathology_no },
      {
        label: '机械通气时长',
        value: fp.other_medical_info?.ventilation_hours
          ? `${fp.other_medical_info.ventilation_hours}小时`
          : null,
      },
      { label: 'ICU类型', value: fp.other_medical_info?.icu_type },
    ],
    人员信息: [
      { label: '科主任', value: fp.staff?.dept_director },
      { label: '主任医师', value: fp.staff?.chief_physician },
      { label: '主治医师', value: fp.staff?.attending_physician },
      { label: '住院医师', value: fp.staff?.resident_physician },
      { label: '责任护士', value: fp.staff?.responsible_nurse },
      { label: '编码员', value: fp.staff?.coder },
      { label: '质控医师', value: fp.staff?.qc_physician },
      { label: '质控护士', value: fp.staff?.qc_nurse },
      { label: '质控日期', value: fp.staff?.qc_date },
      { label: '病案质量等级', value: fp.staff?.medical_record_quality },
    ],
    费用信息: [
      { label: '住院总费用', value: fp.costs?.total_cost ? `¥${fp.costs.total_cost}` : null },
      { label: '自付金额', value: fp.costs?.self_paid ? `¥${fp.costs.self_paid}` : null },
      {
        label: '费用分类数',
        value:
          fp.costs?.categories && Object.keys(fp.costs.categories).length > 0
            ? `${Object.keys(fp.costs.categories).length}项`
            : null,
      },
    ],
  }
})

// 提取统计计算
const extractionStats = computed(() => {
  const categories = fieldCategories.value
  let total = 0
  let extracted = 0

  for (const fields of Object.values(categories)) {
    for (const field of fields as Array<{ label: string; value: any }>) {
      total++
      if (
        field.value !== null &&
        field.value !== undefined &&
        field.value !== '' &&
        field.value !== '-'
      ) {
        extracted++
      }
    }
  }

  const missing = total - extracted
  const completeness = total > 0 ? Math.round((extracted / total) * 100) : 0

  // 可信度基于编码质量和关键字段
  const fp = props.frontpage
  let confidence = completeness
  if (fp?.diagnoses?.discharge_main_icd && isValidIcdCode(fp.diagnoses.discharge_main_icd)) {
    confidence = Math.min(100, confidence + 10)
  }
  if (fp?.procedures?.main_procedure_code && isValidIcdCode(fp.procedures.main_procedure_code)) {
    confidence = Math.min(100, confidence + 5)
  }

  return {
    total,
    extracted,
    missing,
    completeness,
    confidence: Math.round(confidence),
  }
})
</script>
