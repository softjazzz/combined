<template>
  <div class="min-h-screen bg-gray-50 p-4">
    <!-- 页面头部 -->
    <div class="max-w-7xl mx-auto mb-6">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-4">
          <a-button
            type="default"
            size="large"
            class="hover:shadow-md"
            @click="goBack"
          >
            <template #icon>
              <ArrowLeftOutlined />
            </template>
            返回
          </a-button>
          <div>
            <h1 class="text-2xl font-bold text-gray-800">
              医疗记录详情
            </h1>
            <p class="text-gray-600 mt-1">
              查看完整的医疗记录信息
            </p>
          </div>
        </div>
        <div class="flex items-center space-x-3">
          <!-- 视图切换 -->
          <a-button-group>
            <a-button
              :type="viewMode === 'classic' ? 'primary' : 'default'"
              @click="viewMode = 'classic'"
            >
              经典视图
            </a-button>
            <a-button
              :type="viewMode === 'enhanced' ? 'primary' : 'default'"
              @click="viewMode = 'enhanced'"
            >
              增强视图
            </a-button>
          </a-button-group>

          <a-button
            type="primary"
            size="large"
            class="hover:shadow-md bg-blue-600 border-blue-600"
            :loading="qcLoading"
            @click="goToSichuanQC"
          >
            <template #icon>
              <CheckCircleOutlined />
            </template>
            🏥 四川省病历质控
          </a-button>
          <a-button
            type="primary"
            size="large"
            class="hover:shadow-md"
            :loading="editLoading"
            @click="handleEdit"
          >
            <template #icon>
              <EditOutlined />
            </template>
            编辑
          </a-button>
          <a-button
            type="default"
            size="large"
            class="hover:shadow-md"
            :loading="exportLoading"
            @click="handleExport"
          >
            <template #icon>
              <DownloadOutlined />
            </template>
            导出
          </a-button>
          <a-button
            danger
            type="default"
            size="large"
            class="hover:shadow-md"
            :loading="deleteLoading"
            @click="handleDelete"
          >
            <template #icon>
              <DeleteOutlined />
            </template>
            删除
          </a-button>
          <a-button
            type="default"
            size="large"
            class="hover:shadow-md"
            :loading="loading"
            @click="refreshData"
          >
            <template #icon>
              <ReloadOutlined />
            </template>
            刷新
          </a-button>
        </div>
      </div>
    </div>

    <!-- 侧栏被隐藏时的快速按钮（悬浮） -->
    <a-button
      v-if="record && !showSidebar && viewMode === 'enhanced'"
      type="primary"
      class="show-sidebar-fab"
      @click="toggleSidebar"
    >
      显示侧栏
    </a-button>

    <!-- 加载状态 -->
    <div
      v-if="loading"
      class="max-w-7xl mx-auto"
    >
      <a-card class="bg-white shadow-sm border border-gray-200 rounded-lg">
        <div class="flex items-center justify-center py-12">
          <a-spin size="large">
            <template #indicator>
              <LoadingOutlined
                style="font-size: 24px"
                spin
              />
            </template>
          </a-spin>
          <span class="ml-3 text-lg text-gray-600">加载中...</span>
        </div>
      </a-card>
    </div>

    <!-- 错误状态 -->
    <div
      v-else-if="error"
      class="max-w-7xl mx-auto"
    >
      <a-card class="bg-white shadow-sm border border-gray-200 rounded-lg">
        <a-result
          status="error"
          :title="error"
          sub-title="请检查记录ID是否正确，或稍后重试"
        >
          <template #extra>
            <a-button
              type="primary"
              @click="loadRecord"
            >
              重新加载
            </a-button>
            <a-button @click="goBack">
              返回
            </a-button>
          </template>
        </a-result>
      </a-card>
    </div>

    <!-- 增强视图 -->
    <div
      v-if="record && viewMode === 'enhanced'"
      class="max-w-7xl mx-auto"
    >
      <div class="enhanced-view-container">
        <div
          class="enhanced-layout"
          :class="{ 'sidebar-hidden': !showSidebar }"
        >
          <!-- 左侧：增强内容查看器 -->
          <div class="enhanced-content">
            <!-- 内容切换提示 -->
            <div
              v-if="record.selectedDocumentContent"
              class="content-switch-bar"
            >
              <div class="switch-info">
                <span class="current-content">当前查看: {{ record.selectedDocumentTitle }}</span>
              </div>
              <a-button
                size="small"
                @click="returnToOriginalContent"
              >
                <ArrowLeftOutlined />
                返回完整病历
              </a-button>
            </div>

            <EnhancedContentViewer
              :content="record.selectedDocumentContent || record.content || record.raw_text || ''"
              :summary-text="computedSummaryText"
              :enable-summary-toggle="true"
              :title="record.selectedDocumentTitle || '病历原始内容'"
              @search="handleContentSearch"
              @highlight="handleContentHighlight"
            />
          </div>

          <!-- 右侧：患者信息和文档分类 -->
          <div
            v-if="showSidebar"
            class="enhanced-sidebar"
          >
            <!-- 患者基本信息卡片 -->
            <div class="patient-info-card">
              <div class="card-header">
                <h3>患者信息</h3>
                <a-tag :color="getStatusColor(record.status)">
                  {{ getStatusText(record.status) }}
                </a-tag>
              </div>
              <div class="card-content">
                <div class="info-grid">
                  <div class="info-item">
                    <label>姓名</label>
                    <span class="info-value">{{ record.patient_name }}</span>
                  </div>
                  <div class="info-item">
                    <label>年龄</label>
                    <span class="info-value">{{ record.patient_age }}岁</span>
                  </div>
                  <div class="info-item">
                    <label>性别</label>
                    <span class="info-value">{{ record.patient_gender }}</span>
                  </div>
                  <div class="info-item">
                    <label>病历号</label>
                    <span class="info-value">{{ record.record_number }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 增强文档分类 -->
            <EnhancedDocumentClassification
              :documents="documentClassificationData.documents || []"
              :classification-result="documentClassificationData.classificationResult"
              @document-select="handleDocumentSelect"
              @classification-filter="handleClassificationFilter"
              @refresh="refreshClassification"
              @reclassify="reclassifyDocuments"
              @export="exportClassification"
              @validate="validateClassification"
              @toggle-sidebar="toggleSidebar"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- 经典视图（原有内容） -->
    <div
      v-else-if="record && viewMode === 'classic'"
      class="max-w-7xl mx-auto space-y-6"
    >
      <!-- 患者基本信息 -->
      <a-card
        title="患者基本信息"
        class="bg-white shadow-sm border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200"
      >
        <template #extra>
          <a-tag :color="getStatusColor(record.status)">
            {{ getStatusText(record.status) }}
          </a-tag>
        </template>

        <a-row :gutter="[24, 16]">
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>患者姓名</label>
              <div class="info-value">
                {{ record.patient_name }}
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>年龄性别</label>
              <div class="info-value">
                {{ record.patient_age }}岁 {{ record.patient_gender }}
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>病历编号</label>
              <div class="info-value">
                <a-typography-text
                  :copyable="{
                    text: record.record_number,
                    onCopy: () => handleCopySuccess('病历编号'),
                  }"
                >
                  {{ record.record_number }}
                </a-typography-text>
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>记录ID</label>
              <div class="info-value">
                <a-typography-text
                  :copyable="{
                    text: record.id,
                    onCopy: () => handleCopySuccess('记录ID'),
                  }"
                  class="text-xs"
                >
                  {{ record.id }}
                </a-typography-text>
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>创建时间</label>
              <div class="info-value">
                {{ formatDateTime(record.created_at) }}
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>更新时间</label>
              <div class="info-value">
                {{ formatDateTime(record.updated_at) }}
              </div>
            </div>
          </a-col>
        </a-row>
      </a-card>

      <!-- 诊断信息 -->
      <a-card
        title="诊断信息"
        class="bg-white shadow-sm border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200"
      >
        <template #extra>
          <a-tag color="processing">
            <MedicineBoxOutlined />
            诊断信息
          </a-tag>
        </template>

        <a-row :gutter="[24, 16]">
          <a-col
            :xs="24"
            :md="12"
          >
            <div class="info-item">
              <label>主要诊断</label>
              <div class="info-value">
                {{ record.diagnosis_primary || '未填写' }}
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :md="12"
          >
            <div class="info-item">
              <label>次要诊断</label>
              <div class="info-value">
                <div
                  v-if="record.diagnosis_secondary && record.diagnosis_secondary.length > 0"
                  class="space-y-1"
                >
                  <a-tag
                    v-for="(diagnosis, index) in record.diagnosis_secondary"
                    :key="index"
                    color="blue"
                    class="mb-1"
                  >
                    {{ diagnosis }}
                  </a-tag>
                </div>
                <span
                  v-else
                  class="text-gray-500"
                >无</span>
              </div>
            </div>
          </a-col>
        </a-row>
      </a-card>

      <!-- 病历内容 - 使用标签页展示 -->
      <a-card
        title="病历内容"
        class="bg-white shadow-sm border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200"
      >
        <template #extra>
          <a-space>
            <a-tag color="orange">
              <FileTextOutlined />
              {{ record.word_count }} 字
            </a-tag>
            <a-tag
              v-if="documentStats.total_documents > 0"
              color="blue"
            >
              <FolderOutlined />
              {{ documentStats.total_documents }} 个文档
            </a-tag>
          </a-space>
        </template>

        <a-tabs
          v-model:active-key="activeContentTab"
          type="card"
          class="content-tabs"
        >
          <!-- 原始内容标签页 -->
          <a-tab-pane
            key="original"
            tab="原始内容"
          >
            <div class="medical-content">
              <div class="flex justify-between items-center mb-4">
                <span class="text-sm text-gray-600">
                  完整病历内容
                  <span
                    v-if="currentRecordContent.length > 1000"
                    class="text-xs text-blue-600 ml-2"
                  >
                    ({{ currentRecordContent.length }} 字符)
                  </span>
                </span>
                <a-button
                  v-if="currentRecordContent.length > 1000"
                  size="small"
                  type="primary"
                  @click="toggleContentExpanded"
                >
                  {{ contentExpanded ? '收起' : '展开全部' }}
                </a-button>
              </div>
              <div
                :class="[
                  'content-text',
                  { 'content-collapsed': !contentExpanded && currentRecordContent.length > 1000 },
                ]"
              >
                <pre class="whitespace-pre-wrap font-sans">{{ currentRecordContent }}</pre>
              </div>
              <div
                v-if="!contentExpanded && currentRecordContent.length > 1000"
                class="content-fade"
              >
                <div class="text-center pt-4">
                  <a-button
                    type="link"
                    class="text-blue-600"
                    @click="toggleContentExpanded"
                  >
                    点击展开查看完整内容 (剩余 {{ currentRecordContent.length - 1000 }} 字符)
                  </a-button>
                </div>
              </div>
            </div>
          </a-tab-pane>

          <!-- 文档分类标签页 -->
          <a-tab-pane
            key="documents"
            tab="文档分类"
          >
            <DocumentCategoryView
              :record-id="record.id"
              @document-edit="handleDocumentEdit"
              @document-view="handleDocumentView"
            />
          </a-tab-pane>

          <!-- 编辑模式标签页 -->
          <a-tab-pane
            v-if="showEditor"
            key="editor"
            tab="编辑文档"
          >
            <DocumentCategoryEditor
              :record-id="record.id"
              @save-success="handleDocumentSaveSuccess"
              @save-error="handleDocumentSaveError"
            />
          </a-tab-pane>
        </a-tabs>
      </a-card>

      <!-- 文件信息 -->
      <a-card
        title="文件信息"
        class="bg-white shadow-sm border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200"
      >
        <template #extra>
          <a-tag color="purple">
            <FolderOpenOutlined />
            {{ record.file_attachments?.length || 0 }} 个文件
          </a-tag>
        </template>

        <div v-if="record.file_attachments && record.file_attachments.length > 0">
          <div
            v-for="(file, index) in record.file_attachments"
            :key="index"
            class="file-item p-4 border border-gray-200 rounded-lg mb-3 last:mb-0"
          >
            <a-row :gutter="[16, 8]">
              <a-col
                :xs="24"
                :sm="12"
                :md="6"
              >
                <div class="info-item">
                  <label>文件名</label>
                  <div class="info-value">
                    {{ file.filename }}
                  </div>
                </div>
              </a-col>
              <a-col
                :xs="24"
                :sm="12"
                :md="6"
              >
                <div class="info-item">
                  <label>文件大小</label>
                  <div class="info-value">
                    {{ formatFileSize(file.size) }}
                  </div>
                </div>
              </a-col>
              <a-col
                :xs="24"
                :sm="12"
                :md="6"
              >
                <div class="info-item">
                  <label>文件类型</label>
                  <div class="info-value">
                    {{ file.type }}
                  </div>
                </div>
              </a-col>
              <a-col
                :xs="24"
                :sm="12"
                :md="6"
              >
                <div class="info-item">
                  <label>页数</label>
                  <div class="info-value">
                    {{ file.pages || 1 }} 页
                  </div>
                </div>
              </a-col>
            </a-row>
          </div>
        </div>
        <div
          v-else
          class="text-center py-8 text-gray-500"
        >
          <InboxOutlined class="text-4xl mb-2" />
          <p>暂无文件信息</p>
        </div>
      </a-card>

      <!-- 质控信息 -->
      <a-card
        title="质控信息"
        class="bg-white shadow-sm border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200"
      >
        <template #extra>
          <a-space>
            <a-tag
              v-if="record.qc_score"
              :color="getQcScoreColor(record.qc_score)"
            >
              评分: {{ record.qc_score }}
            </a-tag>
            <a-tag
              v-if="record.qc_grade"
              :color="getQcGradeColor(record.qc_grade)"
            >
              等级: {{ record.qc_grade }}
            </a-tag>
          </a-space>
        </template>

        <a-row :gutter="[24, 16]">
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>优先级</label>
              <div class="info-value">
                <a-tag :color="getPriorityColor(record.priority_level)">
                  {{ getPriorityText(record.priority_level) }}
                </a-tag>
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>标签</label>
              <div class="info-value">
                <div
                  v-if="record.tags && record.tags.length > 0"
                  class="space-y-1"
                >
                  <a-tag
                    v-for="(tag, index) in record.tags"
                    :key="index"
                    color="cyan"
                    class="mb-1"
                  >
                    {{ tag }}
                  </a-tag>
                </div>
                <span
                  v-else
                  class="text-gray-500"
                >无标签</span>
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>记录类型</label>
              <div class="info-value">
                {{ getRecordTypeText(record.record_type) }}
              </div>
            </div>
          </a-col>
        </a-row>
      </a-card>

      <!-- 元数据信息 -->
      <a-card
        title="元数据信息"
        class="bg-white shadow-sm border border-gray-200 rounded-lg hover:shadow-md transition-shadow duration-200"
      >
        <template #extra>
          <a-tag color="default">
            <DatabaseOutlined />
            系统信息
          </a-tag>
        </template>

        <a-row :gutter="[24, 16]">
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>导入方法</label>
              <div class="info-value">
                {{ record.metadata?.import_method || '未知' }}
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>解析方法</label>
              <div class="info-value">
                {{ record.metadata?.parse_result?.method || '未知' }}
              </div>
            </div>
          </a-col>
          <a-col
            :xs="24"
            :sm="12"
            :md="8"
          >
            <div class="info-item">
              <label>导入时间</label>
              <div class="info-value">
                {{ formatDateTime(record.metadata?.import_time) }}
              </div>
            </div>
          </a-col>
        </a-row>

        <!-- 解析结果详情 -->
        <div
          v-if="record.metadata?.parse_result"
          class="mt-6"
        >
          <a-divider>解析结果详情</a-divider>
          <a-descriptions
            bordered
            size="small"
            :column="1"
          >
            <a-descriptions-item
              v-if="record.metadata.parse_result.medical_info?.department"
              label="科室"
            >
              {{ record.metadata.parse_result.medical_info.department }}
            </a-descriptions-item>
            <a-descriptions-item
              v-if="record.metadata.parse_result.medical_info?.symptoms?.length"
              label="症状"
            >
              <a-tag
                v-for="(symptom, index) in record.metadata.parse_result.medical_info.symptoms"
                :key="index"
                color="orange"
                class="mb-1 mr-1"
              >
                {{ symptom }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item
              v-if="record.metadata.parse_result.medical_info?.procedures?.length"
              label="手术/操作"
            >
              <a-tag
                v-for="(procedure, index) in record.metadata.parse_result.medical_info.procedures"
                :key="index"
                color="purple"
                class="mb-1 mr-1"
              >
                {{ procedure }}
              </a-tag>
            </a-descriptions-item>
            <a-descriptions-item
              v-if="record.metadata.parse_result.medical_info?.medications?.length"
              label="用药"
            >
              <a-tag
                v-for="(medication, index) in record.metadata.parse_result.medical_info.medications"
                :key="index"
                color="green"
                class="mb-1 mr-1"
              >
                {{ medication }}
              </a-tag>
            </a-descriptions-item>
          </a-descriptions>
        </div>
      </a-card>
    </div>
  </div>

  <!-- 四川省病历质控模态框 -->
  <a-modal
    v-model:open="showQCModal"
    title="🏥 四川省住院病历语义质控评估"
    width="1200px"
    :footer="null"
    :closable="qcStatus === 'completed' || qcStatus === 'error'"
    :mask-closable="false"
    centered
  >
    <div class="qc-modal-content">
      <!-- 质控模式选择 -->
      <div
        v-if="qcStatus === 'idle'"
        class="qc-mode-selector mb-4"
      >
        <div class="p-4 bg-gray-50 rounded-lg border border-gray-200">
          <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3">
              <span class="text-sm font-medium text-gray-700">质控模式:</span>
              <a-switch
                v-model:checked="useMultiDocumentMode"
                :disabled="qcStatus !== 'idle'"
                checked-children="多文书"
                un-checked-children="单一prompt"
                size="default"
              />
            </div>
            <a-tooltip placement="left">
              <template #title>
                <div class="text-sm">
                  <p class="mb-2">
                    <strong>🔄 多文书模式</strong> (推荐):
                  </p>
                  <p class="mb-1">
                    • 智能分离不同文书类型
                  </p>
                  <p class="mb-1">
                    • 为每种文书设计专门化prompt
                  </p>
                  <p class="mb-1">
                    • 并行评估，准确性更高
                  </p>
                  <p class="mb-3">
                    • 处理速度更快
                  </p>
                  <p class="mb-2">
                    <strong>📝 单一prompt模式</strong>:
                  </p>
                  <p class="mb-1">
                    • 使用一个大prompt评估整本病历
                  </p>
                  <p class="mb-1">
                    • 兼容旧版本
                  </p>
                  <p>• 适用于简单病历</p>
                </div>
              </template>
              <QuestionCircleOutlined class="text-blue-500 cursor-help" />
            </a-tooltip>
          </div>
          <div class="mt-2 text-xs text-gray-600">
            {{
              useMultiDocumentMode
                ? '🚀 将使用多文书模式进行精准质控评估'
                : '📋 将使用单一prompt模式进行整体评估'
            }}
          </div>
        </div>
      </div>

      <!-- 质控状态头部 -->
      <div class="qc-header mb-6">
        <a-alert
          :message="getQCStatusMessage()"
          :description="getQCStatusDescription()"
          :type="getQCAlertType()"
          show-icon
          class="mb-4"
        />

        <!-- 文书类型识别结果 -->
        <div
          v-if="detectedDocumentTypes.length > 0"
          class="detected-types mb-4"
        >
          <h4 class="text-lg font-semibold mb-2">
            📋 识别到的文书类型
          </h4>
          <div class="flex flex-wrap gap-2">
            <a-tag
              v-for="docType in detectedDocumentTypes"
              :key="docType"
              color="blue"
              size="large"
              class="px-3 py-1"
            >
              {{ documentTypeRuleMapping[docType]?.icon }}
              {{ documentTypeRuleMapping[docType]?.displayName }}
              <span class="ml-2 text-xs">
                ({{ documentTypeRuleMapping[docType]?.rules.length }}条规则)
              </span>
            </a-tag>
          </div>
        </div>
      </div>

      <!-- 质控进度 -->
      <div
        v-if="qcStatus === 'evaluating'"
        class="qc-progress mb-6"
      >
        <h4 class="text-lg font-semibold mb-4">
          📊 质控评估进度
        </h4>
        <div class="space-y-4">
          <div
            v-for="docType in detectedDocumentTypes"
            :key="docType"
            class="progress-item"
          >
            <div class="flex items-center justify-between mb-2">
              <span class="font-medium">
                {{ documentTypeRuleMapping[docType]?.icon }}
                {{ documentTypeRuleMapping[docType]?.displayName }}
              </span>
              <span class="text-sm text-gray-500">
                {{ qcProgress[docType]?.completed || 0 }} / {{ qcProgress[docType]?.total || 0 }}
              </span>
            </div>
            <a-progress
              :percent="getQCProgress(docType)"
              :status="
                qcProgress[docType]?.completed === qcProgress[docType]?.total ? 'success' : 'active'
              "
              :stroke-color="{ '0%': '#108ee9', '100%': '#87d068' }"
            />
          </div>
        </div>
      </div>

      <!-- 质控结果 -->
      <div
        v-if="qcStatus === 'completed'"
        class="qc-results"
      >
        <h4 class="text-lg font-semibold mb-4">
          📋 质控评估结果
        </h4>

        <a-tabs
          v-model:active-key="activeQCTab"
          type="card"
        >
          <a-tab-pane
            v-for="docType in detectedDocumentTypes"
            :key="docType"
            :tab="`${documentTypeRuleMapping[docType]?.icon} ${documentTypeRuleMapping[docType]?.displayName}`"
          >
            <div class="doc-type-results">
              <!-- 统计概览 -->
              <div class="results-summary mb-4">
                <a-row :gutter="16">
                  <a-col :span="6">
                    <a-statistic
                      title="总规则数"
                      :value="qcProgress[docType]?.total || 0"
                      :value-style="{ color: '#2b6cf6' }"
                    />
                  </a-col>
                  <a-col :span="6">
                    <a-statistic
                      title="通过规则"
                      :value="qcProgress[docType]?.passed || 0"
                      :value-style="{ color: '#52c41a' }"
                    />
                  </a-col>
                  <a-col :span="6">
                    <a-statistic
                      title="不通过规则"
                      :value="qcProgress[docType]?.failed || 0"
                      :value-style="{ color: '#f5222d' }"
                    />
                  </a-col>
                  <a-col :span="6">
                    <a-statistic
                      title="通过率"
                      :value="
                        qcProgress[docType]?.total > 0
                          ? Math.round(
                            (qcProgress[docType]?.passed / qcProgress[docType]?.total) * 100,
                          )
                          : 0
                      "
                      suffix="%"
                      :value-style="{
                        color:
                          qcProgress[docType]?.passed === qcProgress[docType]?.total
                            ? '#52c41a'
                            : '#faad14',
                      }"
                    />
                  </a-col>
                </a-row>
              </div>

              <!-- 详细结果列表 -->
              <div class="results-list">
                <a-list
                  :data-source="qcResults[docType] || []"
                  item-layout="vertical"
                  size="large"
                >
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <template #actions>
                        <span>
                          <component
                            :is="
                              getQCStatusIcon(
                                item.compliant || item.is_compliant ? 'passed' : 'failed',
                              )
                            "
                            :style="{
                              color: item.compliant || item.is_compliant ? '#52c41a' : '#f5222d',
                            }"
                          />
                          {{ item.compliant || item.is_compliant ? '通过' : '不通过' }}
                        </span>
                        <span>置信度: {{ Math.round(item.confidence * 100) }}%</span>
                        <span v-if="!(item.compliant || item.is_compliant)">扣分: {{ item.score_deduction }}分</span>
                      </template>

                      <div class="qc-result-content w-full">
                        <a-list-item-meta>
                          <template #title>
                            <a-tag
                              :color="item.compliant || item.is_compliant ? 'success' : 'error'"
                              class="mr-2"
                            >
                              {{ item.rule_id }}
                            </a-tag>
                            {{ item.rule_name }}
                          </template>
                          <template #description>
                            <div class="text-gray-600 mb-2">
                              {{ item.reasoning || item.findings || '暂无详细说明' }}
                            </div>
                          </template>
                        </a-list-item-meta>

                        <!-- 佐证依据组件 -->
                        <div class="evidence-section mt-3">
                          <EvidenceViewer
                            :evidence="{
                              rule_id: item.rule_id,
                              rule_name: item.rule_name || '质控规则',
                              is_compliant: item.compliant || item.is_compliant,
                              confidence: item.confidence,
                              findings: item.findings || item.reasoning || '',
                              evidence: item.evidence || '',
                              reasoning: item.reasoning || item.findings || '',
                              suggestions: item.suggestions || [],
                            }"
                            :document-type="docType"
                            @highlight-text="handleHighlightText"
                          />
                        </div>
                      </div>
                    </a-list-item>
                  </template>
                </a-list>
              </div>
            </div>
          </a-tab-pane>
        </a-tabs>
      </div>

      <!-- 病历原文高亮显示区域 -->
      <div
        v-if="showOriginalContent && highlightTexts.length > 0"
        class="original-content-section mb-6"
      >
        <div class="bg-white rounded-lg border border-gray-200 shadow-sm">
          <div class="bg-gray-50 px-4 py-3 border-b border-gray-200 rounded-t-lg">
            <div class="flex items-center justify-between">
              <h4 class="text-lg font-semibold text-gray-800 flex items-center">
                <FileTextOutlined class="mr-2 text-blue-600" />
                病历原文 - 证据标注
              </h4>
              <div class="flex items-center space-x-2">
                <a-tag color="blue">
                  {{ highlightTexts.length }} 处证据
                </a-tag>
                <a-button
                  type="link"
                  size="small"
                  @click="clearAllHighlights"
                >
                  <template #icon>
                    <CloseOutlined />
                  </template>
                  清除标注
                </a-button>
                <a-button
                  type="link"
                  size="small"
                  @click="showOriginalContent = false"
                >
                  <template #icon>
                    <EyeInvisibleOutlined />
                  </template>
                  隐藏
                </a-button>
              </div>
            </div>
          </div>
          <div class="p-4">
            <HighlightedText
              ref="highlightedTextRef"
              :content="record?.content || ''"
              :search-texts="highlightTexts"
            />
          </div>
        </div>
      </div>

      <!-- 错误状态 -->
      <div
        v-if="qcStatus === 'error'"
        class="qc-error text-center py-8"
      >
        <a-result
          status="error"
          title="质控评估失败"
          sub-title="请检查网络连接或联系系统管理员"
        >
          <template #extra>
            <a-button
              type="primary"
              @click="showQCModal = false"
            >
              关闭
            </a-button>
            <a-button @click="goToSichuanQC">
              重试
            </a-button>
          </template>
        </a-result>
      </div>

      <!-- 模态框底部操作 -->
      <div
        v-if="qcStatus === 'completed'"
        class="qc-footer mt-6 text-center"
      >
        <a-space>
          <a-button
            type="primary"
            @click="exportQCReport"
          >
            📄 导出质控报告
          </a-button>
          <a-button @click="showQCModal = false">
            关闭
          </a-button>
        </a-space>
      </div>
    </div>
  </a-modal>

  <!-- 文档查看对话框 -->
  <a-modal
    v-model:open="documentViewDialogVisible"
    :title="selectedDocument?.title || '文档详情'"
    width="80%"
    class="document-view-dialog"
    :footer="null"
  >
    <div
      v-if="selectedDocument"
      class="document-detail-content"
    >
      <!-- 文档信息 -->
      <div class="document-info-section mb-4">
        <a-descriptions
          :column="2"
          bordered
          size="small"
        >
          <a-descriptions-item label="文档类型">
            <a-tag color="blue">
              {{ selectedDocument.type_info?.type_name || '未知类型' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="AI分类">
            <a-tag :color="selectedDocument.ai_classified ? 'green' : 'default'">
              {{ selectedDocument.ai_classified ? '是' : '否' }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item
            v-if="(selectedDocument.classification_confidence || 0) > 0"
            label="置信度"
          >
            {{ Math.round((selectedDocument.classification_confidence || 0) * 100) }}%
          </a-descriptions-item>
          <a-descriptions-item label="质控状态">
            <a-tag :color="getQCStatusColor(selectedDocument.qc_status || '')">
              {{ getStatusText(selectedDocument.qc_status || '') }}
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item
            v-if="selectedDocument.qc_score"
            label="质控分数"
          >
            <a-tag color="orange">
              {{ selectedDocument.qc_score }}分
            </a-tag>
          </a-descriptions-item>
          <a-descriptions-item label="创建时间">
            {{ formatDateTime(selectedDocument.created_at) }}
          </a-descriptions-item>
        </a-descriptions>
      </div>

      <!-- 文档内容 -->
      <div class="document-content-section">
        <h4 class="mb-3">
          文档内容
        </h4>
        <div class="document-content-wrapper">
          <pre class="document-content-text">{{ selectedDocument.content }}</pre>
        </div>
      </div>

      <!-- 操作按钮 -->
      <div class="document-actions-section mt-4 text-center">
        <a-space>
          <a-button
            type="primary"
            @click="handleEditSelectedDocument"
          >
            <template #icon>
              <EditOutlined />
            </template>
            编辑文档
          </a-button>
          <a-button @click="copyDocumentContent">
            <template #icon>
              <CopyOutlined />
            </template>
            复制内容
          </a-button>
          <a-button @click="documentViewDialogVisible = false">
            关闭
          </a-button>
        </a-space>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, onMounted, h, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { message, Modal } from 'ant-design-vue'
import {
  ArrowLeftOutlined,
  EditOutlined,
  DownloadOutlined,
  DeleteOutlined,
  LoadingOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  FolderOutlined,
  InboxOutlined,
  MedicineBoxOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons-vue'

// 导入佐证依据组件
import EvidenceViewer from '@/components/qc/EvidenceViewer.vue'
import HighlightedText from '@/components/qc/HighlightedText.vue'
import DocumentCategoryView from '@/components/DocumentCategoryView.vue'
import DocumentCategoryEditor from '@/components/DocumentCategoryEditor.vue'

// 导入增强的医疗记录组件
import EnhancedContentViewer from '@/components/medical-records/EnhancedContentViewer.vue'
import EnhancedDocumentClassification from '@/components/medical-records/EnhancedDocumentClassification.vue'
import { extractApiData } from '@/utils/api-helpers'

// 路由和状态
const route = useRoute()
const router = useRouter()
const loading = ref(false)
const error = ref('')
interface LegacyRecordLike {
  id: string
  content?: string
  raw_text?: string
  selectedDocumentContent?: string | null
  selectedDocumentTitle?: string | null
  patient_name?: string
  patient_age?: string | number
  patient_gender?: string
  status: string
  [key: string]: any
}

interface LegacyDocumentLike {
  id?: string
  title?: string
  type?: string
  content?: string
  content_preview?: string
  type_info?: {
    type_name?: string
    type_code?: string
    [key: string]: any
  }
  ai_classified?: boolean
  classification_confidence?: number
  qc_status?: string
  qc_score?: number
  created_at?: string
  category_code?: string
  [key: string]: any
}

interface QCEvaluationProgressLike {
  total: number
  completed: number
  passed: number
  failed: number
  rules: Record<
    string,
    {
      status?: string
      confidence?: number
      reasoning?: string
      [key: string]: any
    }
  >
  [key: string]: any
}

interface QCEvaluationResultLike {
  rule_id?: string
  rule_code?: string
  rule_name?: string
  compliant?: boolean
  is_compliant?: boolean
  confidence?: number
  score_deduction?: number
  reasoning?: string
  findings?: string
  evidence?: string
  suggestions?: string[]
  [key: string]: any
}

interface DocumentClassificationDataLike {
  documents: LegacyDocumentLike[]
  classificationResult?: { [key: string]: unknown; method?: string }
  categories: unknown[]
  totalDocuments: number
}

const record = ref<LegacyRecordLike | null>(null)
const contentExpanded = ref(false)

// 视图模式状态
const viewMode = ref<'classic' | 'enhanced'>('enhanced')

// 操作状态
const editLoading = ref(false)
const deleteLoading = ref(false)
const exportLoading = ref(false)

// 四川省质控相关状态
const qcLoading = ref(false)
const showQCModal = ref(false)
const qcProgress = ref<Record<string, QCEvaluationProgressLike>>({})
const qcResults = ref<Record<string, QCEvaluationResultLike[]>>({})
const detectedDocumentTypes = ref<string[]>([])
const applicableRules = ref<any[]>([])
const qcStatus = ref<'idle' | 'analyzing' | 'evaluating' | 'completed' | 'error'>('idle')
const activeQCTab = ref<string>('')
const useMultiDocumentMode = ref<boolean>(true) // 默认使用多文书模式

// 高亮文本相关状态
const highlightTexts = ref<string[]>([])
const showOriginalContent = ref<boolean>(false)
const highlightedTextRef = ref()

// 新增：文档相关状态
const activeContentTab = ref('original')
const showEditor = ref(false)
const documentStats = ref({
  total_documents: 0,
  categories_count: 0,
  ai_classified_count: 0,
})

// 文档分类数据状态
const documentClassificationData = ref<DocumentClassificationDataLike>({
  documents: [],
  classificationResult: undefined,
  categories: [],
  totalDocuments: 0,
})

// 文档查看对话框状态
const documentViewDialogVisible = ref(false)
const selectedDocument = ref<LegacyDocumentLike | null>(null)
const showSidebar = ref(true)

const computedSummaryText = computed(() => {
  if (selectedDocument.value) {
    const doc = selectedDocument.value
    if (doc.content_preview && String(doc.content_preview).trim())
      return String(doc.content_preview)
    if (record.value?.selectedDocumentContent)
      return String(record.value.selectedDocumentContent).slice(0, 400)
  }
  const base = record.value?.content || record.value?.raw_text || ''
  return String(base).slice(0, 400)
})

const currentRecordContent = computed(() =>
  String(record.value?.content || record.value?.raw_text || ''),
)

const toggleSidebar = () => {
  showSidebar.value = !showSidebar.value
}

// API 配置：优先使用环境变量，否则走相对路径交由 Vite 代理
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

// 加载医疗记录详情
const loadRecord = async () => {
  const recordId = route.params.id as string
  if (!recordId) {
    error.value = '缺少记录ID参数'
    return
  }

  loading.value = true
  error.value = ''

  try {
    const response = await fetch(`${API_BASE_URL}/api/medical-records/${recordId}`)

    if (!response.ok) {
      if (response.status === 404) {
        throw new Error('医疗记录不存在')
      } else if (response.status === 400) {
        throw new Error('无效的记录ID格式')
      } else {
        throw new Error(`服务器错误: ${response.status}`)
      }
    }

    const data = await response.json()
    record.value = data

    console.log('医疗记录详情加载成功:', data)

    // 加载文档统计信息
    await loadDocumentStats()
  } catch (err: any) {
    console.error('加载医疗记录失败:', err)
    error.value = err.message || '加载医疗记录失败'
    message.error(error.value)
  } finally {
    loading.value = false
  }
}

// 返回上一页
const goBack = () => {
  router.back()
}

// 刷新数据
const refreshData = () => {
  loadRecord()
}

// 切换内容展开状态
const toggleContentExpanded = () => {
  contentExpanded.value = !contentExpanded.value
}

// 复制成功回调
const handleCopySuccess = (type: string) => {
  message.success(`${type}已复制到剪贴板`)
}

// 增强视图相关处理函数
const handleContentSearch = (keyword: string) => {
  console.log('搜索内容:', keyword)
  // 可以在这里添加搜索相关的逻辑
}

const handleContentHighlight = (texts: string[]) => {
  console.log('高亮文本:', texts)
  // 可以在这里添加高亮相关的逻辑
}

const handleDocumentSelect = async (document: LegacyDocumentLike) => {
  console.log('=== 文档选择调试信息 ===')
  console.log('选择的文档:', document)
  console.log('文档类型:', document?.type)
  console.log('文档标题:', document?.title)
  console.log('是否有content:', !!document?.content)
  console.log('是否有content_preview:', !!document?.content_preview)
  console.log('当前record状态:', !!record.value)

  selectedDocument.value = document

  // 尝试获取文档的完整内容
  let documentContent = ''
  let documentTitle = document.title || document.type || '选中文档'

  try {
    // 首先尝试从API获取完整的文档内容
    if (record.value?.id) {
      console.log('尝试从API获取完整文档内容...')
      const response = await fetch(
        `${API_BASE_URL}/api/medical-records/${record.value.id}/documents`,
      )
      if (response.ok) {
        const data = await response.json()
        console.log('API返回的文档数据:', data)

        // 查找匹配的文档
        const matchedDoc = findMatchingDocument(data, document)
        if (matchedDoc && matchedDoc.content) {
          documentContent = matchedDoc.content
          console.log('找到完整文档内容，长度:', documentContent.length)
        }
      }
    }

    // 如果API获取失败，使用备用方案
    if (!documentContent) {
      console.log('API获取失败，使用备用方案...')

      // 尝试使用 content 字段
      if (document.content) {
        documentContent = document.content
      }
      // 如果没有 content，尝试从原始文本中提取
      else if (document.type && record.value?.raw_text) {
        documentContent = extractDocumentFromRawText(document.type, record.value.raw_text)
        if (documentContent) {
          console.log('从原始文本提取成功，长度:', documentContent.length)
        }
      }
      // 最后使用 content_preview
      if (!documentContent && document.content_preview) {
        documentContent = document.content_preview
        documentTitle += ' (仅预览)'
        console.log('使用预览内容，长度:', documentContent.length)
      }
    }

    // 如果还是没有内容
    if (!documentContent) {
      documentContent = '暂无该文档的详细内容'
    }
  } catch (error) {
    console.error('获取文档内容时出错:', error)
    // 降级到预览内容
    if (document.content_preview) {
      documentContent = document.content_preview
      documentTitle += ' (仅预览)'
    } else {
      documentContent = '获取文档内容失败'
    }
  }

  // 更新内容查看器显示选中文档的内容
  if (record.value) {
    record.value.selectedDocumentContent = documentContent
    record.value.selectedDocumentTitle = documentTitle
    console.log('=== 内容更新调试信息 ===')
    console.log('设置的内容长度:', documentContent.length)
    console.log('设置的标题:', documentTitle)
    console.log('内容前100字符:', documentContent.substring(0, 100))
  }

  if (
    documentContent &&
    documentContent !== '暂无该文档的详细内容' &&
    documentContent !== '获取文档内容失败'
  ) {
    message.success(`已选择文档: ${document.title || document.type || '未命名文档'}`)
  } else {
    message.info('该文档暂无详细内容，显示预览信息')
  }
}

const handleClassificationFilter = (filter: any) => {
  console.log('分类筛选:', filter)
  // 可以在这里添加筛选相关的逻辑
}

const refreshClassification = () => {
  console.log('刷新分类')
  loadDocumentStats()
}

const reclassifyDocuments = () => {
  console.log('重新分类文档')
  message.info('重新分类功能开发中...')
}

const exportClassification = () => {
  console.log('导出分类')
  message.info('导出分类功能开发中...')
}

const validateClassification = () => {
  console.log('验证分类')
  message.info('验证分类功能开发中...')
}

// 从API返回的数据中查找匹配的文档
const findMatchingDocument = (apiData: any, targetDocument: any): any => {
  if (!apiData || !apiData.categories) return null

  // 规范化比较
  const norm = (s: any) =>
    String(s || '')
      .replace(/\s+/g, '')
      .toLowerCase()
  const tId = targetDocument?.id ? String(targetDocument.id) : ''
  const tType = norm(targetDocument?.type)
  const tTitle = norm(targetDocument?.title)

  let best: any = null
  let bestScore = -1

  for (const category of apiData.categories) {
    for (const doc of category.documents || []) {
      // ID 直匹配优先
      if (tId && String(doc.id || '') === tId) {
        return doc
      }

      const dTypeCode = norm(doc?.type_info?.type_code || doc?.metadata?.type_code)
      const dTypeName = norm(doc?.type_info?.type_name || doc?.type)
      const dTitle = norm(doc?.title)

      let score = 0
      if (tType && (tType === dTypeCode || tType === dTypeName)) score += 4
      if (tTitle && tTitle === dTitle) score += 3
      if (tType && (dTypeCode.includes(tType) || dTypeName.includes(tType))) score += 2
      if (tTitle && dTitle.includes(tTitle)) score += 1

      // 平分时更偏向内容更长的（更可能是完整内容）
      if (
        score > bestScore ||
        (score === bestScore && (doc?.content?.length || 0) > (best?.content?.length || 0))
      ) {
        best = doc
        bestScore = score
      }
    }
  }

  if (best) {
    console.log('找到匹配的文档(打分):', { score: bestScore, id: best.id, title: best.title })
    return best
  }

  console.log('未找到匹配的文档')
  return null
}

// 从原始文本中提取特定类型的文档内容
const extractDocumentFromRawText = (documentType: string, rawText: string): string => {
  if (!rawText) return ''

  console.log('开始从原始文本提取文档:', documentType)
  console.log('原始文本长度:', rawText.length)

  // 定义文档类型的关键词映射
  const typeKeywords: Record<string, string[]> = {
    first_progress_note: ['首次病程记录', '首次病程', '入院记录', '病程记录'],
    attending_progress: ['主治医师查房', '查房记录', '医师查房', '主任医师查房'],
    imaging_report: ['CT检查', '核磁检查', 'MRI', '影像检查', '检查记录', 'CT', '核磁'],
    preoperative_summary: ['术前', '手术前', '术前讨论', '术前小结', '术前准备', '术前主刀'],
    postoperative_note: ['术后', '手术后', '术后记录', '术后首次'],
    病理检查报告: ['病理检查', '病理报告', '病理结果'],
  }

  const keywords = typeKeywords[documentType] || [documentType]
  console.log('搜索关键词:', keywords)

  // 尝试多种分割方式
  const splitMethods = [
    () => rawText.split(/=== 第\d+页 ===/), // 按页分割
    () => rawText.split(/\n\s*\n/), // 按空行分割
    () => [rawText], // 整体文本
  ]

  for (const splitMethod of splitMethods) {
    const sections = splitMethod()
    console.log(`使用分割方法，得到 ${sections.length} 个部分`)

    for (const section of sections) {
      for (const keyword of keywords) {
        if (section.includes(keyword)) {
          console.log(`在部分中找到关键词: ${keyword}`)

          // 找到包含关键词的段落，提取相关内容
          const lines = section.split('\n')
          let startIndex = -1
          let endIndex = lines.length

          // 找到关键词所在行
          for (let i = 0; i < lines.length; i++) {
            if (lines[i].includes(keyword)) {
              startIndex = Math.max(0, i - 2) // 包含前面2行作为上下文
              console.log(`找到关键词在第 ${i} 行，开始索引: ${startIndex}`)
              break
            }
          }

          if (startIndex >= 0) {
            // 查找下一个文档开始的位置作为结束点
            for (let i = startIndex + 10; i < lines.length; i++) {
              // 至少包含10行内容
              const line = lines[i].trim()

              // 检查是否是下一个文档的开始
              const isNextDocument =
                line.match(/^\d{4}-\d{2}-\d{2}.*记录$/) ||
                line.includes('医师签名') ||
                line.match(/^={3,}/) ||
                line.match(/^第\d+页/) ||
                (line.length > 10 && keywords.some((k) => k !== keyword && line.includes(k)))

              if (isNextDocument) {
                endIndex = i
                console.log(`找到结束位置在第 ${i} 行`)
                break
              }
            }

            // 提取内容
            const extractedLines = lines.slice(startIndex, endIndex)
            const content = extractedLines
              .filter((line) => line.trim().length > 0) // 过滤空行
              .join('\n')
              .trim()

            console.log(`提取的内容长度: ${content.length}`)
            console.log(`内容前200字符: ${content.substring(0, 200)}`)

            if (content.length > 100) {
              // 确保提取的内容有意义
              return content
            }
          }
        }
      }
    }
  }

  console.log('未能从原始文本中提取到内容')
  return ''
}

// 显示原始完整内容
const returnToOriginalContent = () => {
  if (record.value) {
    record.value.selectedDocumentContent = null
    record.value.selectedDocumentTitle = null
    selectedDocument.value = null
    message.success('已切换到完整病历内容')
  }
}

// 新增：文档相关方法
const handleDocumentEdit = (document: LegacyDocumentLike) => {
  console.log('编辑文档:', document)
  showEditor.value = true
  activeContentTab.value = 'editor'
}

const handleDocumentView = (document: LegacyDocumentLike) => {
  console.log('查看文档:', document)

  // 设置选中的文档并显示对话框
  selectedDocument.value = document
  documentViewDialogVisible.value = true
}

const handleDocumentSaveSuccess = (document: LegacyDocumentLike) => {
  console.log('文档保存成功:', document)
  message.success('文档保存成功')
  // 刷新文档统计信息
  loadDocumentStats()
}

// 编辑选中的文档
const handleEditSelectedDocument = () => {
  if (selectedDocument.value) {
    handleDocumentEdit(selectedDocument.value)
    documentViewDialogVisible.value = false
  }
}

// 复制文档内容
const copyDocumentContent = async () => {
  if (selectedDocument.value?.content) {
    try {
      await navigator.clipboard.writeText(selectedDocument.value.content)
      message.success('文档内容已复制到剪贴板')
    } catch (error) {
      message.error('复制失败')
    }
  }
}

const handleDocumentSaveError = (error: any) => {
  console.error('文档保存失败:', error)
  message.error('文档保存失败')
}

// 加载文档统计信息和分类数据
const loadDocumentStats = async () => {
  if (!record.value?.id) return

  try {
    const response = await fetch(`${API_BASE_URL}/api/medical-records/${record.value.id}/documents`)
    if (response.ok) {
      const data = await response.json()
      console.log('=== 文档分类数据加载成功 ===')
      console.log('API返回数据:', data)

      // 更新统计信息
      documentStats.value = {
        total_documents: data.total_documents || 0,
        categories_count: data.categories?.length || 0,
        ai_classified_count:
          data.categories?.reduce((count: number, category: any) => {
            return count + category.documents.filter((doc: any) => doc.ai_classified).length
          }, 0) || 0,
      }

      // 构建文档列表用于增强分类组件
      const documents: LegacyDocumentLike[] = []
      if (data.categories && Array.isArray(data.categories)) {
        data.categories.forEach((category: any) => {
          if (category.documents && Array.isArray(category.documents)) {
            category.documents.forEach((doc: any) => {
              documents.push({
                ...doc,
                type: doc.type_info?.type_name || doc.category_code || '未分类',
                confidence: doc.classification_confidence || 0,
                ai_classified: doc.ai_classified || false,
              })
            })
          }
        })
      }

      // 更新文档分类数据
      documentClassificationData.value = {
        documents: documents,
        classificationResult: {
          method: 'AI自动分类',
          confidence:
            documents.length > 0
              ? documents.reduce((sum, doc) => sum + (doc.confidence || 0), 0) / documents.length
              : 0,
          categories: data.categories?.length || 0,
        },
        categories: data.categories || [],
        totalDocuments: data.total_documents || 0,
      }

      console.log('构建的文档列表:', documents)
      console.log('文档分类数据更新完成:', documentClassificationData.value)
    }
  } catch (error) {
    console.error('加载文档统计失败:', error)
  }
}

// 编辑功能
const handleEdit = () => {
  if (!record.value?.id) {
    message.error('记录尚未加载，无法编辑')
    return
  }

  editLoading.value = true
  try {
    // 跳转到编辑页面
    router.push(`/dashboard/medical-records/edit/${record.value.id}`)
  } catch (error) {
    message.error('跳转到编辑页面失败')
  } finally {
    editLoading.value = false
  }
}

// 导出功能
const handleExport = async () => {
  const currentRecord = record.value
  if (!currentRecord) {
    message.error('记录尚未加载，无法导出')
    return
  }

  exportLoading.value = true
  try {
    // 创建导出内容
    const exportData = {
      基本信息: {
        患者姓名: currentRecord.patient_name,
        年龄: currentRecord.patient_age,
        性别: currentRecord.patient_gender,
        病历编号: currentRecord.record_number,
        记录ID: currentRecord.id,
        创建时间: formatDateTime(currentRecord.created_at),
      },
      诊断信息: {
        主要诊断: currentRecord.diagnosis_primary,
        次要诊断: currentRecord.diagnosis_secondary,
      },
      病历内容: currentRecord.content,
      文件信息: currentRecord.file_attachments,
      质控信息: {
        状态: getStatusText(currentRecord.status),
        优先级: getPriorityText(currentRecord.priority_level),
        标签: currentRecord.tags,
        质控评分: currentRecord.qc_score,
        质控等级: currentRecord.qc_grade,
      },
      元数据: currentRecord.metadata,
    }

    // 创建并下载文件
    const dataStr = JSON.stringify(exportData, null, 2)
    const dataBlob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(dataBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `医疗记录_${currentRecord.patient_name}_${currentRecord.record_number}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    message.success('医疗记录导出成功')
  } catch (error) {
    console.error('导出失败:', error)
    message.error('导出医疗记录失败')
  } finally {
    exportLoading.value = false
  }
}

// 删除功能
const handleDelete = () => {
  if (!record.value || !record.value.id) {
    message.error('记录尚未加载，无法删除')
    return
  }

  console.log('删除按钮被点击，记录信息:', record.value)

  const confirmed = window.confirm(
    `确定要删除患者 "${record.value.patient_name}" 的医疗记录吗？\n\n` +
      `病历编号: ${record.value.record_number}\n` +
      `记录ID: ${record.value.id}\n\n` +
      `此操作不可撤销！`,
  )

  if (confirmed) {
    console.log('用户确认删除')
    performDelete()
  } else {
    console.log('用户取消删除')
  }
}

// 执行删除操作
const performDelete = async () => {
  if (!record.value?.id) {
    message.error('记录尚未加载，无法删除')
    return
  }
  const currentRecordId = record.value.id

  console.log('开始执行删除操作，记录ID:', currentRecordId)
  deleteLoading.value = true

  try {
    const deleteUrl = `${API_BASE_URL}/api/medical-records/${currentRecordId}`
    console.log('删除请求URL:', deleteUrl)

    const response = await fetch(deleteUrl, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    console.log('删除响应状态:', response.status)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('删除请求失败:', response.status, errorText)

      if (response.status === 404) {
        throw new Error('医疗记录不存在')
      } else if (response.status === 400) {
        throw new Error('无效的记录ID格式')
      } else {
        throw new Error(`删除失败: ${response.status} - ${errorText}`)
      }
    }

    const result = await response.json()
    console.log('删除成功，服务器响应:', result)

    message.success('医疗记录删除成功')

    // 延迟跳转，让用户看到成功消息
    setTimeout(() => {
      console.log('准备跳转回上一页')
      router.back()
    }, 1500)
  } catch (err: any) {
    console.error('删除医疗记录失败:', err)
    message.error(err.message || '删除医疗记录失败')
  } finally {
    deleteLoading.value = false
  }
}

// 四川省质控相关接口定义
interface SichuanQCRule {
  rule_id: string
  name: string
  description: string
  category: string
  complexity: string
  defect_level: string
  score_deduction: number
  applicable_documents: string[]
  medical_domain: string
  requires_rag: boolean
  requires_cot: boolean
}

interface QCEvaluationResult {
  rule_id: string
  rule_name: string
  compliant: boolean
  confidence: number
  reasoning: string
  evidence: string
  score_deduction: number
  suggestions: string[]
}

interface DocumentTypeMapping {
  [key: string]: {
    rules: string[]
    displayName: string
    icon: string
  }
}

// 文书类型与规则映射（默认兜底，启动时将用后端数据覆盖 rules 数组）
const documentTypeRuleMapping: DocumentTypeMapping = {
  病程记录: {
    rules: [
      'SC-001',
      'SC-002',
      'SC-003',
      'SC-004',
      'SC-005',
      'SC-006',
      'SC-007',
      'SC-008',
      'SC-009',
      'SC-010',
      'SC-011',
      'SC-012',
      'SC-013',
      'SC-014',
      'SC-015',
      'SC-016',
      'SC-017',
      'SC-018',
      'SC-019',
      'SC-020',
    ],
    displayName: '病程记录',
    icon: '📋',
  },
  手术记录: {
    rules: [
      'SC-021',
      'SC-022',
      'SC-023',
      'SC-024',
      'SC-025',
      'SC-026',
      'SC-027',
      'SC-028',
      'SC-029',
      'SC-030',
      'SC-031',
      'SC-032',
      'SC-033',
      'SC-034',
      'SC-035',
    ],
    displayName: '手术记录',
    icon: '🏥',
  },
  入院记录: {
    rules: [
      'SC-036',
      'SC-037',
      'SC-038',
      'SC-039',
      'SC-040',
      'SC-041',
      'SC-042',
      'SC-043',
      'SC-044',
      'SC-045',
      'SC-046',
      'SC-047',
      'SC-048',
      'SC-049',
      'SC-050',
    ],
    displayName: '入院记录',
    icon: '📝',
  },
  出院记录: {
    rules: [
      'SC-051',
      'SC-052',
      'SC-053',
      'SC-054',
      'SC-055',
      'SC-056',
      'SC-057',
      'SC-058',
      'SC-059',
      'SC-060',
      'SC-061',
      'SC-062',
      'SC-063',
      'SC-064',
      'SC-065',
      'SC-066',
      'SC-067',
      'SC-068',
    ],
    displayName: '出院记录',
    icon: '📄',
  },
}

// 存储完整的分组规则数据，用于传递给后端评估
const rulesByDocumentType = ref<Record<string, any[]>>({})

// 根据文书类型给一个图标（用于从后端动态填充时）
const getIconForDocType = (t: string): string => {
  if (t.includes('手术')) return '🏥'
  if (t.includes('出院')) return '📄'
  if (t.includes('入院')) return '📝'
  if (t.includes('病程')) return '📋'
  return '📑'
}

// 动态加载文书→规则映射：优先调用后端分组接口，失败则前端自行分组
const loadRulesMapping = async (docTypes: string[]) => {
  try {
    const params = new URLSearchParams()
    params.set('grouped', 'true')
    params.set('document_types', docTypes.join(','))
    const resp = await fetch(`${API_BASE_URL}/api/qc/sichuan/rules?${params.toString()}`)
    let rulesByType: Record<string, any[]> = {}
    if (resp.ok) {
      const data = await resp.json()
      rulesByType = data.rules_by_document_type || {}
      // 若后端未分组返回，则尝试用扁平 rules 聚合
      if ((!rulesByType || Object.keys(rulesByType).length === 0) && Array.isArray(data.rules)) {
        // 若后端未分组或无法根据applicable_documents分组，则兜底：按请求的每个文书类型使用全量规则
        for (const dt of docTypes) {
          rulesByType[dt] = [...data.rules]
        }
      }
    }

    // 写入映射（仅覆盖 rules 列表，保持显示名/图标）
    for (const dt of docTypes) {
      const fromBackend = (rulesByType[dt] || []) as any[]
      const ruleIds = fromBackend.map((r) => r.rule_id || r.rule_code).filter(Boolean)
      if (!documentTypeRuleMapping[dt]) {
        documentTypeRuleMapping[dt] = { rules: [], displayName: dt, icon: getIconForDocType(dt) }
      }
      // 如果没有规则ID，兜底使用all rules的前若干个ID（最多200）
      if (ruleIds.length > 0) {
        documentTypeRuleMapping[dt].rules = ruleIds
      } else if (Array.isArray(rulesByType[dt]) && rulesByType[dt].length > 0) {
        documentTypeRuleMapping[dt].rules = rulesByType[dt]
          .map((r: any) => r.rule_id || r.rule_code)
          .filter(Boolean)
          .slice(0, 200)
      }
      // 存储完整的规则数据
      rulesByDocumentType.value[dt] = fromBackend
    }
  } catch (e) {
    // 失败忽略，沿用默认映射
    console.warn('加载文书-规则映射失败，使用默认映射', e)
  }
}

// 智能识别文书类型
const detectDocumentTypes = (content: string): string[] => {
  const types: string[] = []
  const contentLower = content.toLowerCase()

  // 检测病程记录
  if (
    contentLower.includes('病程记录') ||
    contentLower.includes('日常病程') ||
    contentLower.includes('主治医师查房')
  ) {
    types.push('病程记录')
  }

  // 检测手术记录
  if (
    contentLower.includes('手术记录') ||
    contentLower.includes('术中') ||
    contentLower.includes('手术过程') ||
    contentLower.includes('麻醉')
  ) {
    types.push('手术记录')
  }

  // 检测入院记录
  if (
    contentLower.includes('入院记录') ||
    contentLower.includes('主诉') ||
    contentLower.includes('现病史') ||
    contentLower.includes('入院诊断')
  ) {
    types.push('入院记录')
  }

  // 检测出院记录
  if (
    contentLower.includes('出院记录') ||
    contentLower.includes('出院诊断') ||
    contentLower.includes('出院医嘱') ||
    contentLower.includes('出院情况')
  ) {
    types.push('出院记录')
  }

  return types.length > 0 ? types : ['病程记录'] // 默认为病程记录
}

// 获取适用的规则
const getApplicableRules = async (documentTypes: string[]): Promise<SichuanQCRule[]> => {
  try {
    // 获取所有四川省规则
    const response = await fetch(`${API_BASE_URL}/api/qc/sichuan/rules`)
    if (!response.ok) {
      throw new Error('获取规则失败')
    }

    const data = await response.json()
    const allRules: SichuanQCRule[] = data.rules || []

    // 根据文书类型筛选适用规则
    const applicableRuleIds = new Set<string>()
    documentTypes.forEach((docType) => {
      const mapping = documentTypeRuleMapping[docType]
      if (mapping) {
        mapping.rules.forEach((ruleId) => applicableRuleIds.add(ruleId))
      }
    })

    return allRules.filter((rule) => applicableRuleIds.has(rule.rule_id))
  } catch (error) {
    console.error('获取适用规则失败:', error)
    return []
  }
}

// 跳转到四川省质控结果页（不自动开始）
const goToSichuanQC = () => {
  if (!record.value?.id) {
    message.error('记录尚未加载')
    return
  }
  router.push(`/dashboard/medical-records/${record.value.id}/qc-sichuan`)
}

// 开始四川省质控评估（保留给结果页内触发调用）
const startSichuanQC = async () => {
  const currentRecord = record.value
  if (!currentRecord) {
    message.error('记录尚未加载，无法执行质控')
    return
  }

  const hasBaseText =
    !!(currentRecord.content && String(currentRecord.content).trim().length > 0) ||
    !!(currentRecord.raw_text && String(currentRecord.raw_text).trim().length > 0)

  // 若无正文内容，但存在多文书模式能力，则自动切换到多文书模式
  if (!hasBaseText && !useMultiDocumentMode.value) {
    message.warning('未检测到病历正文，将使用多文书模式进行质控')
    useMultiDocumentMode.value = true
  }

  qcLoading.value = true
  qcStatus.value = 'analyzing'
  showQCModal.value = true

  try {
    // 1. 智能识别文书类型
    console.log('🔍 开始智能识别文书类型...')
    const baseForDetect = String(currentRecord.content || currentRecord.raw_text || '')
    const types = detectDocumentTypes(baseForDetect)
    detectedDocumentTypes.value = types
    activeQCTab.value = types.length > 0 ? types[0] : ''
    console.log('📋 识别到的文书类型:', types)

    // 2. 动态加载文书→规则映射并获取适用规则
    await loadRulesMapping(types)
    console.log('📚 获取适用的质控规则...')
    const rules = await getApplicableRules(types)
    applicableRules.value = rules
    console.log('✅ 获取到', rules.length, '条适用规则')

    // 3. 开始质控评估
    qcStatus.value = 'evaluating'
    await performQCEvaluation(types, rules)
  } catch (error: any) {
    console.error('❌ 四川省质控评估失败:', error)
    message.error('质控评估失败: ' + (error.message || '未知错误'))
    qcStatus.value = 'error'
  } finally {
    qcLoading.value = false
  }
}

// 执行质控评估
const performQCEvaluation = async (documentTypes: string[], rules: SichuanQCRule[]) => {
  console.log('🚀 开始执行质控评估...')
  const currentRecord = record.value
  if (!currentRecord) {
    throw new Error('记录尚未加载，无法执行质控评估')
  }

  // 初始化进度
  qcProgress.value = {}
  qcResults.value = {}

  documentTypes.forEach((docType) => {
    qcProgress.value[docType] = {
      total: documentTypeRuleMapping[docType]?.rules.length || 0,
      completed: 0,
      passed: 0,
      failed: 0,
      rules: {},
    }
    qcResults.value[docType] = []
  })

  try {
    // 获取预分类文书映射（仅在多文书模式下）
    let documentsByType = null
    if (useMultiDocumentMode.value) {
      documentsByType = await getPreclassifiedDocuments(documentTypes)
    }

    // 调用后端API进行质控评估 - 使用新的多文书模式
    const evaluationRequest = {
      document_id: currentRecord.id || 'unknown',
      document_content: String(currentRecord.content || currentRecord.raw_text || ''), // 确保不为null/undefined
      document_type: documentTypes.length > 0 ? documentTypes[0] : '病程记录', // 兼容性
      document_types: documentTypes,
      rule_ids: rules.map((rule) => rule.rule_id),
      use_multi_document_mode: useMultiDocumentMode.value, // 根据用户选择
      documents_by_type: documentsByType, // 预分类文书映射
      // 将已加载的分组规则传给后端，后端优先使用
      rules_by_document_type: Object.fromEntries(
        documentTypes.map((dt) => [dt, rulesByDocumentType.value[dt] || []]),
      ),
      patient_info: {
        name: currentRecord.patient_name || '未知',
        age: String(currentRecord.patient_age || '未知'), // 确保转换为字符串
        gender: currentRecord.patient_gender || '未知',
        record_id: currentRecord.id,
      },
    }

    console.log('📤 发送质控评估请求:', JSON.stringify(evaluationRequest, null, 2))

    const response = await fetch(`${API_BASE_URL}/api/v1/qc/sichuan/evaluate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(evaluationRequest),
      // 统一超时到3分钟（180秒），与后端LLM超时保持一致
      signal: AbortSignal.timeout(180000),
    })

    if (!response.ok) {
      throw new Error(`质控评估API调用失败: ${response.status} ${response.statusText}`)
    }

    const rawEvaluationResults = await response.json()
    const evaluationResults = extractApiData<any>(rawEvaluationResults, '质控评估失败')
    console.log('📥 收到质控评估结果:', evaluationResults)

    // 处理评估结果
    processQCResults(evaluationResults, documentTypes)

    qcStatus.value = 'completed'
    message.success(`质控评估完成！共评估 ${rules.length} 条规则`)
  } catch (error: any) {
    console.error('❌ 质控评估执行失败:', error)
    qcStatus.value = 'error'
    throw error
  }
}

// 处理质控结果
const processQCResults = (apiResponse: any, documentTypes: string[]) => {
  console.log('📊 开始处理质控结果...')
  console.log('📋 API响应结构:', apiResponse)

  // 检查是否为多文书模式响应
  if (apiResponse.mode === 'multi_document' && apiResponse.document_results) {
    console.log('🔄 处理多文书模式结果...')
    processMultiDocumentResults(apiResponse, documentTypes)
  } else {
    console.log('🔄 处理单一prompt模式结果...')
    processSinglePromptResults(apiResponse, documentTypes)
  }
}

// 处理多文书模式结果
const processMultiDocumentResults = (apiResponse: any, documentTypes: string[]) => {
  const documentResults = apiResponse.document_results || {}

  documentTypes.forEach((docType) => {
    if (documentResults[docType]) {
      const docResult = documentResults[docType]

      console.log(`📋 ${docType} 结果:`, docResult)
      qcResults.value[docType] = docResult.evaluation_results || []

      // 更新进度统计
      const progress = qcProgress.value[docType]
      if (progress) {
        progress.completed = docResult.evaluation_results?.length || 0
        progress.passed = docResult.compliant_rules || 0
        progress.failed = (docResult.total_rules || 0) - (docResult.compliant_rules || 0)

        console.log(`📊 ${docType} 进度统计:`, progress)

        // 更新每个规则的状态
        if (docResult.evaluation_results) {
          docResult.evaluation_results.forEach((result: any) => {
            const isCompliant = result.is_compliant
            progress.rules[result.rule_id] = {
              status: isCompliant ? 'passed' : 'failed',
              confidence: result.confidence,
              reasoning: result.findings || result.reasoning,
            }
          })
        }
      }
    } else {
      console.log(`⚠️ ${docType} 未找到评估结果`)
      // 初始化空结果
      qcResults.value[docType] = []
      if (qcProgress.value[docType]) {
        qcProgress.value[docType].completed = 0
        qcProgress.value[docType].passed = 0
        qcProgress.value[docType].failed = 0
      }
    }
  })
}

// 处理单一prompt模式结果（保持向后兼容）
const processSinglePromptResults = (apiResponse: any, documentTypes: string[]) => {
  // 兼容不同的API响应结构
  const evaluationResults = apiResponse.evaluation_results || apiResponse.results || []
  console.log('📊 评估结果数组:', evaluationResults)

  documentTypes.forEach((docType) => {
    const docTypeResults =
      evaluationResults.filter((result: any) => {
        const ruleMapping = documentTypeRuleMapping[docType]
        return ruleMapping && ruleMapping.rules.includes(result.rule_id)
      }) || []

    console.log(`📋 ${docType} 相关结果:`, docTypeResults)
    qcResults.value[docType] = docTypeResults

    // 更新进度统计
    const progress = qcProgress.value[docType]
    progress.completed = docTypeResults.length
    // 兼容 compliant 和 is_compliant 字段
    progress.passed = docTypeResults.filter((r: any) => r.compliant || r.is_compliant).length
    progress.failed = docTypeResults.filter((r: any) => !(r.compliant || r.is_compliant)).length

    console.log(`📊 ${docType} 进度统计:`, progress)

    // 更新每个规则的状态
    docTypeResults.forEach((result: any) => {
      const isCompliant = result.compliant || result.is_compliant
      progress.rules[result.rule_id] = {
        status: isCompliant ? 'passed' : 'failed',
        confidence: result.confidence,
        reasoning: result.reasoning || result.findings,
      }
    })
  })

  console.log('✅ 质控结果处理完成')
  console.log('📊 最终结果:', qcResults.value)
  console.log('📈 最终进度:', qcProgress.value)
}

// 处理高亮文本请求
const handleHighlightText = (text: string) => {
  console.log('🔍 请求高亮文本:', text)

  // 添加到高亮文本列表
  if (!highlightTexts.value.includes(text)) {
    highlightTexts.value.push(text)
  }

  // 显示原文内容区域
  showOriginalContent.value = true

  // 提示用户
  message.info(`已在病历原文中标注相关证据: "${text.substring(0, 20)}..."`)
}

// 清除所有高亮
const clearAllHighlights = () => {
  highlightTexts.value = []
  showOriginalContent.value = false

  if (highlightedTextRef.value) {
    highlightedTextRef.value.clearHighlights()
  }

  message.success('已清除所有证据标注')
}

// 获取预分类文书映射
const getPreclassifiedDocuments = async (
  documentTypes: string[],
): Promise<Record<string, unknown> | null> => {
  if (!record.value?.id) {
    console.warn('⚠️ 无法获取预分类文书：缺少记录ID')
    return null
  }

  try {
    console.log('🔍 获取预分类文书映射...')
    const response = await fetch(`${API_BASE_URL}/api/medical-records/${record.value.id}/documents`)

    if (!response.ok) {
      console.warn('⚠️ 获取预分类文书失败，将使用自动分离模式')
      return null
    }

    const data = await response.json()
    console.log('📋 获取到分类文书数据:', data)

    // 构建文书类型到内容的映射
    const documentsByType: Record<string, string[]> = {}

    // 遍历分类数据
    if (data.categories && Array.isArray(data.categories)) {
      for (const category of data.categories) {
        if (category.documents && Array.isArray(category.documents)) {
          for (const doc of category.documents) {
            // 映射文书类型名称
            const originalTypeName = doc.type_info?.type_name || doc.type_name || ''
            const docTypeName = mapDocumentTypeToQCType(originalTypeName)

            console.log(`📋 文书映射: "${originalTypeName}" -> "${docTypeName}"`)

            if (documentTypes.includes(docTypeName) && doc.content) {
              if (!documentsByType[docTypeName]) {
                documentsByType[docTypeName] = []
              }
              documentsByType[docTypeName].push(doc.content)
              console.log(`✅ 添加文书内容: ${docTypeName} (${doc.content.length}字符)`)
            } else {
              console.log(`⚠️ 跳过文书: ${docTypeName} (不在需要的类型中或无内容)`)
            }
          }
        }
      }
    }

    // 合并同类型文书内容
    const mergedDocuments: Record<string, string> = {}
    for (const [docType, contents] of Object.entries(documentsByType)) {
      if (Array.isArray(contents) && contents.length > 0) {
        mergedDocuments[docType] = contents.join('\n\n')
      }
    }

    console.log('✅ 构建预分类文书映射:', Object.keys(mergedDocuments))
    return Object.keys(mergedDocuments).length > 0 ? mergedDocuments : null
  } catch (error) {
    console.error('❌ 获取预分类文书失败:', error)
    return null
  }
}

// 映射数据库文书类型到质控文书类型
const mapDocumentTypeToQCType = (dbTypeName: string): string => {
  const typeMapping: Record<string, string> = {
    // 入院记录相关
    入院记录: '入院记录',
    住院病历: '入院记录',
    入院病历: '入院记录',
    入院诊断: '入院记录',

    // 病程记录相关
    病程记录: '病程记录',
    日常病程: '病程记录',
    首次病程: '病程记录',
    首次病程记录: '病程记录',
    主治医师查房: '病程记录',
    上级医师查房: '病程记录',
    上级医师查房记录: '病程记录',
    主任医师查房: '病程记录',
    主任医师查房记录: '病程记录',
    日常病程记录: '病程记录',
    病程记录单: '病程记录',

    // 手术记录相关
    手术记录: '手术记录',
    手术操作记录: '手术记录',
    术前小结: '手术记录',
    术后记录: '手术记录',
    术前讨论: '手术记录',
    术前讨论记录: '手术记录',
    术前查房: '手术记录',
    术前查房记录: '手术记录',
    手术同意书: '手术记录',

    // 出院记录相关
    出院记录: '出院记录',
    出院小结: '出院记录',
    出院诊断: '出院记录',
    出院医嘱: '出院记录',
  }

  return typeMapping[dbTypeName] || dbTypeName
}

// 获取质控进度百分比
const getQCProgress = (docType: string): number => {
  const progress = qcProgress.value[docType]
  if (!progress || progress.total === 0) return 0
  return Math.round((progress.completed / progress.total) * 100)
}

// 获取质控状态颜色
const getQCStatusColor = (status?: string): string => {
  switch (status) {
    case 'passed':
      return 'success'
    case 'failed':
      return 'error'
    case 'evaluating':
      return 'processing'
    default:
      return 'default'
  }
}

// 获取质控状态图标
const getQCStatusIcon = (status: string) => {
  switch (status) {
    case 'passed':
      return CheckCircleOutlined
    case 'failed':
      return CloseCircleOutlined
    case 'evaluating':
      return ClockCircleOutlined
    default:
      return WarningOutlined
  }
}

// 模态框状态辅助函数
const getQCStatusMessage = (): string => {
  switch (qcStatus.value) {
    case 'analyzing':
      return '正在分析病历内容...'
    case 'evaluating':
      return '正在执行质控评估...'
    case 'completed':
      return '质控评估完成'
    case 'error':
      return '质控评估失败'
    default:
      return '准备开始质控评估'
  }
}

const getQCStatusDescription = (): string => {
  switch (qcStatus.value) {
    case 'analyzing':
      return '智能识别文书类型，匹配适用的四川省质控规则'
    case 'evaluating':
      return '基于《四川省住院病历质量评定标准（2023年版）》进行评估'
    case 'completed':
      return '已完成所有规则的评估，请查看详细结果'
    case 'error':
      return '评估过程中出现错误，请重试或联系管理员'
    default:
      return '即将开始四川省住院病历语义质控评估'
  }
}

const getQCAlertType = (): 'success' | 'error' | 'warning' | 'info' => {
  switch (qcStatus.value) {
    case 'analyzing':
    case 'evaluating':
      return 'info'
    case 'completed':
      return 'success'
    case 'error':
      return 'error'
    default:
      return 'info'
  }
}

// 导出质控报告
const exportQCReport = async () => {
  try {
    const reportData = {
      patient_info: {
        name: record.value?.patient_name || '未知',
        age: String(record.value?.patient_age || '未知'), // 确保转换为字符串
        gender: record.value?.patient_gender || '未知',
        record_id: record.value?.id || '未知',
      },
      evaluation_time: new Date().toLocaleString('zh-CN'),
      document_types: detectedDocumentTypes.value,
      qc_results: qcResults.value,
      qc_progress: qcProgress.value,
      summary: {
        total_rules: applicableRules.value.length,
        total_passed: Object.values(qcProgress.value).reduce(
          (sum: number, progress: QCEvaluationProgressLike) => sum + (progress.passed || 0),
          0,
        ),
        total_failed: Object.values(qcProgress.value).reduce(
          (sum: number, progress: QCEvaluationProgressLike) => sum + (progress.failed || 0),
          0,
        ),
        total_score_deduction: Object.values(qcResults.value)
          .flat()
          .reduce(
            (sum: number, result: QCEvaluationResultLike) =>
              sum + (result.compliant ? 0 : result.score_deduction || 0),
            0,
          ),
      },
    }

    // 创建并下载报告文件
    const reportContent = generateQCReportContent(reportData)
    const blob = new Blob([reportContent], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `四川省病历质控报告_${record.value?.patient_name || '未知'}_${new Date().toISOString().slice(0, 10)}.txt`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)

    message.success('质控报告导出成功')
  } catch (error) {
    console.error('导出质控报告失败:', error)
    message.error('导出质控报告失败')
  }
}

// 生成质控报告内容
const generateQCReportContent = (data: any): string => {
  let content = `四川省住院病历语义质控评估报告\n`
  content += `${'='.repeat(50)}\n\n`

  content += `患者信息:\n`
  content += `  姓名: ${data.patient_info.name}\n`
  content += `  年龄: ${data.patient_info.age}\n`
  content += `  性别: ${data.patient_info.gender}\n`
  content += `  记录ID: ${data.patient_info.record_id}\n`
  content += `  评估时间: ${data.evaluation_time}\n\n`

  content += `评估概要:\n`
  content += `  识别文书类型: ${data.document_types.join(', ')}\n`
  content += `  总规则数: ${data.summary.total_rules}\n`
  content += `  通过规则: ${data.summary.total_passed}\n`
  content += `  不通过规则: ${data.summary.total_failed}\n`
  content += `  总扣分: ${data.summary.total_score_deduction}分\n\n`

  data.document_types.forEach((docType: string) => {
    content += `${docType}评估结果:\n`
    content += `${'-'.repeat(30)}\n`

    const results = data.qc_results[docType] || []
    results.forEach((result: any) => {
      content += `  规则: ${result.rule_id} - ${result.rule_name}\n`
      content += `  结果: ${result.compliant ? '✓ 通过' : '✗ 不通过'}\n`
      content += `  置信度: ${Math.round(result.confidence * 100)}%\n`
      if (!result.compliant) {
        content += `  扣分: ${result.score_deduction}分\n`
      }
      content += `  评估理由: ${result.reasoning}\n`
      if (result.evidence) {
        content += `  支持证据: ${result.evidence}\n`
      }
      if (result.suggestions && result.suggestions.length > 0) {
        content += `  改进建议: ${result.suggestions.join('; ')}\n`
      }
      content += `\n`
    })
  })

  content += `\n报告生成时间: ${new Date().toLocaleString('zh-CN')}\n`
  content += `基于《四川省住院病历质量评定标准（2023年版）》\n`

  return content
}

// 格式化日期时间
const formatDateTime = (dateStr: string | undefined) => {
  if (!dateStr) return '未知'
  try {
    return new Date(dateStr).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return dateStr
  }
}

// 格式化文件大小
const formatFileSize = (bytes: number) => {
  if (bytes === 0) return '0 Bytes'
  const k = 1024
  const sizes = ['Bytes', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

// 获取状态颜色
const getStatusColor = (status?: string) => {
  const colors: Record<string, string> = {
    pending: 'processing',
    completed: 'success',
    failed: 'error',
    reviewing: 'warning',
  }
  if (!status) return 'default'
  return colors[status] || 'default'
}

// 获取状态文本
const getStatusText = (status?: string) => {
  const texts: Record<string, string> = {
    pending: '待处理',
    completed: '已完成',
    failed: '失败',
    reviewing: '审核中',
  }
  if (!status) return '未知'
  return texts[status] || status
}

// 获取优先级颜色
const getPriorityColor = (level: number) => {
  if (level >= 4) return 'red'
  if (level >= 3) return 'orange'
  if (level >= 2) return 'blue'
  return 'green'
}

// 获取优先级文本
const getPriorityText = (level: number) => {
  const texts: Record<number, string> = {
    1: '低',
    2: '普通',
    3: '高',
    4: '紧急',
    5: '特急',
  }
  return texts[level] || `级别${level}`
}

// 获取质控评分颜色
const getQcScoreColor = (score: number) => {
  if (score >= 90) return 'green'
  if (score >= 80) return 'blue'
  if (score >= 70) return 'orange'
  return 'red'
}

// 获取质控等级颜色
const getQcGradeColor = (grade: string) => {
  const colors: Record<string, string> = {
    A: 'green',
    B: 'blue',
    C: 'orange',
    D: 'red',
  }
  return colors[grade] || 'default'
}

// 获取记录类型文本
const getRecordTypeText = (type: string) => {
  const texts: Record<string, string> = {
    inpatient: '住院',
    outpatient: '门诊',
    emergency: '急诊',
  }
  return texts[type] || type
}

// 组件挂载时加载数据
onMounted(() => {
  loadRecord()
  // 设置默认的质控结果标签页
  if (detectedDocumentTypes.value.length > 0) {
    activeQCTab.value = detectedDocumentTypes.value[0]
  }
})
</script>

<style scoped>
/* 增强视图样式 */
.enhanced-view-container {
  background: linear-gradient(180deg, #f7fafc 0%, #eef2f7 100%);
  min-height: calc(100vh - 160px);
  padding: 16px 20px;
  border-radius: 12px;
}

.enhanced-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 16px;
  align-items: start;
  max-width: 1400px;
  margin: 0 auto;
}
.enhanced-layout.sidebar-hidden {
  grid-template-columns: 1fr;
}

.enhanced-content {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
  height: calc(100vh - 220px);
  min-height: 520px;
  display: flex;
  flex-direction: column;
}

.content-switch-bar {
  background: #f0f9ff;
  border-bottom: 1px solid #e0f2fe;
  padding: 12px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.switch-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.current-content {
  font-size: 14px;
  color: #0369a1;
  font-weight: 500;
}

.enhanced-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  position: sticky;
  top: 88px;
}

.patient-info-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.card-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 16px 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}

.card-content {
  padding: 20px;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.info-item label {
  font-size: 12px;
  font-weight: 500;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}

.show-sidebar-fab {
  position: fixed;
  right: 16px;
  top: 96px;
  z-index: 100;
}

/* 响应式设计 */
@media (max-width: 1200px) {
  .enhanced-layout {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .enhanced-sidebar {
    order: -1;
    position: static;
  }
}

@media (max-width: 768px) {
  .enhanced-view-container {
    padding: 12px;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }
}

/* 经典视图信息项样式 */
.info-item {
  margin-bottom: 8px;
}

.info-item label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  margin-bottom: 4px;
}

.info-value {
  font-size: 16px;
  color: #111827;
  font-weight: 500;
}

/* 医疗内容样式 */
.medical-content {
  position: relative;
}

.content-text {
  color: #374151;
  line-height: 1.625;
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
}

.content-collapsed {
  max-height: 384px;
  overflow: hidden;
}

.content-fade {
  position: relative;
  margin-top: -64px;
  height: 120px;
  background: linear-gradient(to top, white 30%, rgba(255, 255, 255, 0.8) 70%, transparent);
  pointer-events: none;
}

.content-fade .text-center {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  pointer-events: auto;
  padding: 12px 0;
  border-top: 1px solid #e8e8e8;
}

/* 文件项样式 */
.file-item {
  background-color: #f9fafb;
  transition: background-color 0.2s ease;
}

.file-item:hover {
  background-color: #f3f4f6;
}

/* 简洁卡片样式 */
.simple-card {
  background-color: white;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.simple-card-hover {
  transition: box-shadow 0.2s ease;
}

.simple-card-hover:hover {
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

/* 响应式调整 */
@media (max-width: 768px) {
  .info-item {
    margin-bottom: 12px;
  }

  .content-collapsed {
    max-height: 256px;
  }
}

/* 自定义滚动条 */
.medical-content::-webkit-scrollbar {
  width: 6px;
}

.medical-content::-webkit-scrollbar-track {
  background-color: #f3f4f6;
  border-radius: 9999px;
}

.medical-content::-webkit-scrollbar-thumb {
  background-color: #9ca3af;
  border-radius: 9999px;
}

.medical-content::-webkit-scrollbar-thumb:hover {
  background-color: #6b7280;
}

/* 标签样式增强 */
.ant-tag {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

/* 四川省质控模态框样式 */
.qc-modal-content {
  max-height: 80vh;
  overflow-y: auto;
}

/* 质控结果项样式 */
.qc-result-item {
  border-bottom: 1px solid #f3f4f6;
  transition: background-color 0.2s ease;
}

.qc-result-item:last-child {
  border-bottom: none;
}

.qc-result-item:hover {
  background-color: #f9fafb;
}

.qc-result-content {
  width: 100%;
}

.evidence-section {
  border-top: 1px solid #f3f4f6;
  padding-top: 12px;
  margin-top: 12px;
}

/* 原文高亮显示区域样式 */
.original-content-section {
  animation: fadeIn 0.3s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fadeIn {
  animation: fadeIn 0.3s ease-out;
}

.qc-header {
  border-bottom: 1px solid #e5e7eb;
  padding-bottom: 16px;
}

.detected-types {
  background-color: #f8fafc;
  border-radius: 8px;
  padding: 16px;
}

.qc-progress {
  background-color: #f8fafc;
  border-radius: 8px;
  padding: 16px;
}

.progress-item {
  background-color: white;
  border-radius: 6px;
  padding: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.qc-results {
  background-color: #f8fafc;
  border-radius: 8px;
  padding: 16px;
}

.results-summary {
  background-color: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.results-list {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.doc-type-results {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.qc-footer {
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
}

/* 质控状态图标动画 */
.qc-status-icon {
  transition: all 0.3s ease;
}

.qc-status-icon.evaluating {
  animation: spin 1s linear infinite;
}

/* 质控结果列表项样式 */
.ant-list-item {
  transition: background-color 0.2s ease;
}

.ant-list-item:hover {
  background-color: #f9fafb;
}

/* 质控进度条样式 */
.ant-progress-line {
  margin-bottom: 8px;
}

/* 质控标签页样式 */
.ant-tabs-card > .ant-tabs-content {
  margin-top: 16px;
}

.ant-tabs-card > .ant-tabs-content > .ant-tabs-tabpane {
  background-color: white;
  border-radius: 8px;
  padding: 16px;
}

/* 按钮样式增强 */
.ant-btn {
  transition: all 0.2s ease;
}

.ant-btn:hover {
  transform: translateY(-1px);
}

/* 文档查看对话框样式 */
.document-view-dialog .ant-modal-body {
  padding: 24px;
}

.document-detail-content {
  max-height: 70vh;
  overflow-y: auto;
}

.document-info-section {
  background-color: #f8fafc;
  padding: 16px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.document-content-section h4 {
  color: #374151;
  font-weight: 600;
  margin-bottom: 12px;
}

.document-content-wrapper {
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
}

.document-content-text {
  font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Roboto Mono', monospace;
  font-size: 14px;
  line-height: 1.6;
  color: #374151;
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
}

.document-actions-section {
  border-top: 1px solid #e5e7eb;
  padding-top: 16px;
}
</style>
