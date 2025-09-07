<template>
  <div class="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50">
    <!-- 现代化工作站头部 -->
    <div class="bg-gradient-to-r from-blue-600 to-indigo-600 shadow-lg">
      <div class="max-w-full mx-auto px-6 py-4">
        <div class="flex items-center justify-between">
          <!-- 医生信息 -->
          <div class="flex items-center space-x-4">
            <div class="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
              <i class="fas fa-user-md text-white text-xl"></i>
            </div>
            <div>
              <h2 class="text-xl font-semibold text-white">{{ currentDoctor.name }}</h2>
              <p class="text-blue-100 text-sm">{{ currentDoctor.department }}</p>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex items-center space-x-3">
            <button
              @click="createNewRecord"
              class="bg-white/20 hover:bg-white/30 text-white px-4 py-2 rounded-lg backdrop-blur-sm transition-all duration-200 flex items-center space-x-2 hover:scale-105"
            >
              <i class="fas fa-plus"></i>
              <span>新建病历</span>
            </button>
            <div class="text-white/80 text-sm">
              当前时间: {{ currentTime }}
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 主要工作区域 - 左右分栏布局 -->
    <div class="flex h-[calc(100vh-80px)]">
      <!-- 左侧患者列表边栏 -->
      <div class="w-80 bg-white shadow-lg border-r border-gray-200 flex flex-col">
        <!-- 患者列表头部 -->
        <div class="p-4 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-semibold text-gray-800">患者列表</h3>
            <span class="text-sm text-gray-600">{{ filteredPatientList.length }} 位患者</span>
          </div>

          <!-- 搜索框 -->
          <div class="relative">
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="搜索患者姓名、科室..."
              class="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
            >
            <i class="fas fa-search absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"></i>
          </div>
        </div>

        <!-- 患者列表内容 -->
        <div class="flex-1 overflow-y-auto">
          <div class="p-2 space-y-2">
            <div
              v-for="patient in filteredPatientList"
              :key="patient.id"
              @click="selectPatient(patient)"
              class="p-3 rounded-xl border transition-all duration-200 cursor-pointer hover:shadow-md"
              :class="{
                'border-blue-500 bg-blue-50 shadow-md': currentRecord?.id === patient.id,
                'border-gray-200 bg-white hover:border-blue-300': currentRecord?.id !== patient.id
              }"
            >
              <!-- 患者基本信息 -->
              <div class="flex items-center space-x-3 mb-2">
                <div class="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <i class="fas fa-user text-white text-sm"></i>
                </div>
                <div class="flex-1 min-w-0">
                  <h4 class="font-semibold text-gray-800 truncate">{{ patient.patient_name }}</h4>
                  <p class="text-xs text-gray-600">{{ patient.patient_age }}岁 · {{ getGenderText(patient.patient_gender) }}</p>
                </div>
                <div class="flex-shrink-0">
                  <span
                    class="px-2 py-1 text-xs font-medium rounded-full"
                    :class="{
                      'bg-yellow-100 text-yellow-800': patient.status === 'pending',
                      'bg-blue-100 text-blue-800': patient.status === 'analyzing',
                      'bg-green-100 text-green-800': patient.status === 'completed',
                      'bg-red-100 text-red-800': patient.status === 'failed'
                    }"
                  >
                    {{ getStatusText(patient.status) }}
                  </span>
                </div>
              </div>

              <!-- 患者详细信息 -->
              <div class="text-xs text-gray-600 space-y-1">
                <div class="flex justify-between">
                  <span class="text-gray-500">科室:</span>
                  <span class="font-medium text-gray-700">{{ patient.department }}</span>
                </div>
                <div class="flex justify-between">
                  <span class="text-gray-500">入院:</span>
                  <span class="font-medium text-gray-700">{{ formatDate(patient.admission_date) }}</span>
                </div>
                <div v-if="patient.qc_score" class="flex justify-between">
                  <span class="text-gray-500">质控:</span>
                  <div class="flex items-center space-x-1">
                    <span class="font-medium text-gray-700">{{ patient.qc_score }}</span>
                    <span
                      class="px-1 py-0.5 text-xs font-medium rounded"
                      :class="{
                        'bg-green-100 text-green-800': patient.qc_score >= 90,
                        'bg-blue-100 text-blue-800': patient.qc_score >= 80 && patient.qc_score < 90,
                        'bg-yellow-100 text-yellow-800': patient.qc_score >= 70 && patient.qc_score < 80,
                        'bg-red-100 text-red-800': patient.qc_score < 70
                      }"
                    >
                      {{ getGrade(patient.qc_score) }}级
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧主工作区域 -->
      <div class="flex-1 flex flex-col">
        <div class="flex-1 p-6">
          <!-- 病历编辑区 - 现在占据全宽 -->
          <div class="flex flex-col h-full">
            <div class="bg-white rounded-2xl shadow-lg border border-gray-200 overflow-hidden flex-1 flex flex-col">
            <!-- 患者信息头部 -->
            <div v-if="currentRecord" class="bg-gradient-to-r from-blue-50 to-indigo-50 p-6 border-b border-gray-200">
              <div class="flex items-start justify-between">
                <!-- 患者基本信息 -->
                <div class="flex-1">
                  <div class="flex items-center space-x-3 mb-4">
                    <h3 class="text-2xl font-bold text-gray-800">{{ currentRecord.patient_name }}</h3>
                    <span class="px-3 py-1 bg-blue-100 text-blue-800 text-sm font-medium rounded-full">
                      #{{ currentRecord.id.slice(-6) }}
                    </span>
                  </div>

                  <!-- 患者详情 -->
                  <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-birthday-cake text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ currentRecord.patient_age }}岁</span>
                    </div>
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-venus-mars text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ getGenderText(currentRecord.patient_gender) }}</span>
                    </div>
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-hospital text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ currentRecord.department }}</span>
                    </div>
                    <div class="flex items-center space-x-2 bg-white/70 px-3 py-2 rounded-lg">
                      <i class="fas fa-calendar text-blue-600"></i>
                      <span class="text-sm font-medium text-gray-700">{{ formatDate(currentRecord.admission_date) }}</span>
                    </div>
                  </div>
                </div>

                <!-- 状态和质控信息 -->
                <div class="flex flex-col items-end space-y-3">
                  <span
                    class="px-4 py-2 text-sm font-medium rounded-full"
                    :class="{
                      'bg-yellow-100 text-yellow-800': currentRecord.status === 'pending',
                      'bg-blue-100 text-blue-800': currentRecord.status === 'analyzing',
                      'bg-green-100 text-green-800': currentRecord.status === 'completed',
                      'bg-red-100 text-red-800': currentRecord.status === 'failed'
                    }"
                  >
                    {{ getStatusText(currentRecord.status) }}
                  </span>

                  <div v-if="currentRecord.qc_score" class="flex items-center space-x-2 bg-white px-4 py-2 rounded-lg shadow-sm">
                    <span class="text-lg font-bold text-blue-600">{{ currentRecord.qc_score }}</span>
                    <span
                      class="px-2 py-1 text-xs font-medium rounded"
                      :class="{
                        'bg-green-100 text-green-800': currentRecord.qc_score >= 90,
                        'bg-blue-100 text-blue-800': currentRecord.qc_score >= 80 && currentRecord.qc_score < 90,
                        'bg-yellow-100 text-yellow-800': currentRecord.qc_score >= 70 && currentRecord.qc_score < 80,
                        'bg-red-100 text-red-800': currentRecord.qc_score < 70
                      }"
                    >
                      {{ getGrade(currentRecord.qc_score) }}级
                    </span>
                  </div>
                </div>
              </div>

              <!-- 操作按钮 -->
              <div class="flex items-center space-x-3 mt-4">
                <button
                  @click="loadTemplate"
                  class="bg-white hover:bg-gray-50 text-gray-700 px-4 py-2 rounded-lg border border-gray-300 transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas fa-file-medical"></i>
                  <span>模板</span>
                </button>
                <button
                  @click="saveRecord"
                  :disabled="!hasChanges"
                  class="bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas fa-save"></i>
                  <span>{{ hasChanges ? '保存' : '已保存' }}</span>
                </button>
                <button
                  @click="analyzeRecord"
                  :disabled="!currentRecord?.content || isAnalyzing"
                  class="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas" :class="isAnalyzing ? 'fa-spinner fa-spin' : 'fa-shield-alt'"></i>
                  <span>{{ isAnalyzing ? '分析中...' : '质控分析' }}</span>
                </button>
                <button
                  @click="toggleQCPanel"
                  class="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg transition-colors duration-200 flex items-center space-x-2"
                >
                  <i class="fas" :class="showQCPanel ? 'fa-eye-slash' : 'fa-eye'"></i>
                  <span>{{ showQCPanel ? '隐藏质控' : '显示质控' }}</span>
                </button>
              </div>
            </div>

            <!-- 编辑器容器 -->
            <div class="flex-1 p-6">
                <!-- 欢迎页面 -->
                <div v-if="!currentRecord" class="flex-1 flex items-center justify-center">
                  <div class="text-center max-w-2xl mx-auto">
                    <div class="w-24 h-24 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center mx-auto mb-8">
                      <i class="fas fa-stethoscope text-white text-4xl"></i>
                    </div>
                    <h2 class="text-3xl font-bold text-gray-800 mb-4">欢迎使用医生工作站</h2>
                    <p class="text-gray-600 text-lg mb-8 leading-relaxed">
                      请从左侧患者列表中选择一个患者开始工作，或创建新的病历记录。
                    </p>

                    <!-- 快速操作 -->
                    <div class="flex items-center justify-center space-x-4 mb-12">
                      <button
                        @click="createNewRecord"
                        class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl transition-all duration-200 flex items-center space-x-2 hover:scale-105 shadow-lg"
                      >
                        <i class="fas fa-plus"></i>
                        <span>新建病历</span>
                      </button>
                    </div>

                  <!-- 功能特色 -->
                  <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-edit text-blue-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">智能编辑</h3>
                      <p class="text-sm text-gray-600">智能病历编辑器</p>
                    </div>
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-shield-alt text-green-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">质控分析</h3>
                      <p class="text-sm text-gray-600">实时质控分析</p>
                    </div>
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-chart-line text-yellow-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">质量评分</h3>
                      <p class="text-sm text-gray-600">智能质量评分</p>
                    </div>
                    <div class="bg-white p-6 rounded-xl shadow-sm border border-gray-200 hover:shadow-md transition-shadow duration-200">
                      <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mb-4 mx-auto">
                        <i class="fas fa-lightbulb text-purple-600 text-xl"></i>
                      </div>
                      <h3 class="font-semibold text-gray-800 mb-2">改进建议</h3>
                      <p class="text-sm text-gray-600">智能改进建议</p>
                    </div>
                  </div>
                  </div>
                </div>

              <!-- 病历编辑器 -->
              <div v-else class="flex-1 flex flex-col overflow-hidden">
                <div class="flex-1 overflow-y-auto">
                  <MedicalRecordEditor
                    v-model="editorContent"
                    :placeholder="'请输入病历内容...'"
                    @input="onContentChange"
                    @save="saveRecord"
                    class="h-full min-h-[600px]"
                  />
                </div>
              </div>
            </div>

            <!-- 状态栏 -->
            <div class="bg-gradient-to-r from-gray-50 to-blue-50 px-6 py-3 border-t border-gray-200 flex items-center justify-between">
              <div class="flex items-center space-x-4">
                <div v-if="isDraftSaving" class="flex items-center space-x-2 text-blue-600">
                  <i class="fas fa-spinner fa-spin"></i>
                  <span class="text-sm font-medium">自动保存中...</span>
                </div>
                <div v-else-if="lastSaved" class="flex items-center space-x-2 text-green-600">
                  <i class="fas fa-check"></i>
                  <span class="text-sm font-medium">已保存于 {{ formatTime(lastSaved) }}</span>
                </div>
              </div>

              <div class="text-sm font-medium text-gray-600">
                字数：{{ wordCount }}
              </div>
            </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
