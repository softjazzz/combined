<template>
  <div class="target-selection-step">
    <!-- 顶部统计卡片 -->
    <a-row :gutter="16" class="stats-row">
      <a-col :span="8">
        <a-card size="small" :bordered="false" class="stat-card">
          <a-statistic
            title="可用病历"
            :value="demoStore.availableRecords.length"
            :prefix="h(FileTextOutlined)"
          >
            <template #suffix>
              <span class="stat-suffix">份</span>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card size="small" :bordered="false" class="stat-card">
          <a-statistic
            title="已选病历"
            :value="demoStore.testRecord ? 1 : 0"
            :prefix="h(CheckCircleOutlined)"
            :value-style="{ color: demoStore.testRecord ? '#3f8600' : '#999' }"
          >
            <template #suffix>
              <span class="stat-suffix">份</span>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="8">
        <a-card size="small" :bordered="false" class="stat-card">
          <a-statistic
            title="已选文书"
            :value="demoStore.selectedDocumentList.length"
            :prefix="h(FileOutlined)"
            :value-style="{ color: demoStore.selectedDocumentList.length > 0 ? '#3f8600' : '#999' }"
          >
            <template #suffix>
              <span class="stat-suffix">份</span>
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>

    <!-- 主内容区 -->
    <a-row :gutter="16" class="content-row">
      <!-- 左侧：病历列表 -->
      <a-col :span="12">
        <a-card title="选择测试病历" :bordered="false" class="section-card">
          <template #extra>
            <a-space>
              <a-button
                size="small"
                :icon="h(ReloadOutlined)"
                @click="handleRefreshRecords"
                :loading="demoStore.isLoadingData"
              >
                刷新
              </a-button>
            </a-space>
          </template>

          <!-- 筛选器 -->
          <div class="filters-section">
            <a-space direction="vertical" style="width: 100%" :size="12">
              <a-input-search
                v-model:value="searchKeyword"
                placeholder="搜索病历（患者姓名、病历号）"
                allow-clear
                @search="handleSearch"
              />
              <a-row :gutter="8">
                <a-col :span="12">
                  <a-select
                    v-model:value="selectedDepartment"
                    placeholder="选择科室"
                    allow-clear
                    style="width: 100%"
                    @change="handleDepartmentChange"
                  >
                    <a-select-option value="">全部科室</a-select-option>
                    <a-select-option
                      v-for="dept in demoStore.availableDepartments"
                      :key="dept"
                      :value="dept"
                    >
                      {{ dept }}
                    </a-select-option>
                  </a-select>
                </a-col>
                <a-col :span="12">
                  <a-select
                    v-model:value="selectedStatus"
                    placeholder="选择状态"
                    allow-clear
                    style="width: 100%"
                    @change="handleStatusChange"
                  >
                    <a-select-option value="">全部状态</a-select-option>
                    <a-select-option value="active">活跃</a-select-option>
                    <a-select-option value="archived">已归档</a-select-option>
                  </a-select>
                </a-col>
              </a-row>
            </a-space>
          </div>

          <!-- 病历列表 -->
          <div class="records-list">
            <a-spin :spinning="demoStore.isLoadingData">
              <a-list
                :data-source="paginatedRecords"
                :pagination="recordPaginationConfig"
                size="small"
              >
                <template #renderItem="{ item }">
                  <a-list-item
                    class="record-item"
                    :class="{ 'selected': isRecordSelected(item) }"
                    @click="handleSelectRecord(item)"
                  >
                    <a-list-item-meta>
                      <template #title>
                        <a-space>
                          <UserOutlined />
                          <span class="patient-name">{{ item.patient_name || '未知患者' }}</span>
                          <a-tag v-if="item.patient_gender" size="small">
                            {{ item.patient_gender === 'M' ? '男' : '女' }}
                          </a-tag>
                          <a-tag v-if="item.patient_age" size="small" color="blue">
                            {{ item.patient_age }}岁
                          </a-tag>
                        </a-space>
                      </template>
                      <template #description>
                        <a-space direction="vertical" :size="4" style="width: 100%">
                          <div>
                            <a-space :size="8">
                              <span><EnvironmentOutlined /> {{ item.department || '未知科室' }}</span>
                              <span><CalendarOutlined /> {{ formatDate(item.admission_date) }}</span>
                            </a-space>
                          </div>
                          <div v-if="item.primary_diagnosis">
                            <MedicineBoxOutlined /> {{ item.primary_diagnosis }}
                          </div>
                        </a-space>
                      </template>
                    </a-list-item-meta>
                    <template #actions>
                      <CheckCircleOutlined
                        v-if="isRecordSelected(item)"
                        style="color: #52c41a; font-size: 20px"
                      />
                    </template>
                  </a-list-item>
                </template>
                <template #empty>
                  <a-empty>
                    <template #description>
                      <div class="empty-description">
                        <span>暂无病历数据</span>
                        <a-button type="link" size="small" @click="handleResetFilters">
                          重置筛选
                        </a-button>
                      </div>
                    </template>
                  </a-empty>
                </template>
              </a-list>
            </a-spin>
          </div>
        </a-card>
      </a-col>

      <!-- 右侧：文书选择 -->
      <a-col :span="12">
        <a-card title="选择测试文书" :bordered="false" class="section-card">
          <template #extra>
            <a-space>
              <a-tag v-if="demoStore.testRecord" color="blue">
                {{ demoStore.testRecord.patient_name }}
              </a-tag>
            </a-space>
          </template>

          <div v-if="!demoStore.testRecord" class="empty-state">
            <a-empty description="请先选择测试病历">
              <template #image>
                <FileSearchOutlined :style="{ fontSize: '64px', color: '#bfbfbf' }" />
              </template>
            </a-empty>
          </div>

          <div v-else class="documents-section">
            <!-- 病历信息摘要 -->
            <a-descriptions :column="1" size="small" bordered class="record-summary">
              <a-descriptions-item label="患者姓名">
                {{ demoStore.testRecord.patient_name }}
              </a-descriptions-item>
              <a-descriptions-item label="科室">
                {{ demoStore.testRecord.department }}
              </a-descriptions-item>
              <a-descriptions-item label="入院日期">
                {{ formatDate(demoStore.testRecord.admission_date) }}
              </a-descriptions-item>
              <a-descriptions-item label="主要诊断" v-if="demoStore.testRecord.primary_diagnosis">
                {{ demoStore.testRecord.primary_diagnosis }}
              </a-descriptions-item>
            </a-descriptions>

            <a-divider />

            <!-- 文书列表 -->
            <div class="documents-list">
              <h4>可用文书</h4>
              <a-spin :spinning="demoStore.isLoadingData">
                <a-list
                  :data-source="availableDocuments"
                  size="small"
                >
                  <template #renderItem="{ item }">
                    <a-list-item
                      class="document-item"
                      :class="{ 'selected': isDocumentSelected(item) }"
                      @click="handleSelectDocument(item)"
                    >
                      <a-list-item-meta>
                        <template #title>
                          <a-space>
                            <FileTextOutlined />
                            <span>{{ item.title || item.type }}</span>
                          </a-space>
                        </template>
                        <template #description>
                          <CalendarOutlined /> {{ formatDate(item.created_at) }}
                        </template>
                      </a-list-item-meta>
                      <template #actions>
                        <a-space>
                          <a-tooltip title="预览文书内容">
                            <a-button
                              type="link"
                              size="small"
                              @click.stop="handlePreviewDocument(item)"
                            >
                              <EyeOutlined />
                            </a-button>
                          </a-tooltip>
                          <CheckCircleOutlined
                            v-if="isDocumentSelected(item)"
                            style="color: #52c41a; font-size: 18px"
                          />
                        </a-space>
                      </template>
                    </a-list-item>
                  </template>
                  <template #empty>
                    <a-empty description="该病历暂无文书" />
                  </template>
                </a-list>
              </a-spin>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 底部操作栏 -->
    <div class="footer-actions">
      <a-space>
        <a-button
          type="primary"
          size="large"
          :disabled="!canProceed"
          @click="handleProceed"
        >
          下一步：配置规则
          <RightOutlined />
        </a-button>
        <a-button size="large" @click="handleClearSelection">
          清空选择
        </a-button>
      </a-space>
    </div>

    <!-- 文书内容预览抽屉 -->
    <a-drawer
      v-model:open="previewDrawerVisible"
      title="文书内容预览"
      placement="right"
      :width="720"
      :body-style="{ paddingBottom: '80px' }"
    >
      <div v-if="previewDocument" class="document-preview">
        <!-- 文书信息 -->
        <a-descriptions :column="1" bordered size="small" class="document-info">
          <a-descriptions-item label="文书标题">
            <a-space>
              <FileTextOutlined />
              <strong>{{ previewDocument.title || previewDocument.type || '未命名文书' }}</strong>
            </a-space>
          </a-descriptions-item>
          <a-descriptions-item label="文书类型">
            {{ previewDocument.document_type || previewDocument.type || '未知类型' }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间" v-if="previewDocument.created_at">
            <CalendarOutlined /> {{ formatDate(previewDocument.created_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="文档ID" v-if="previewDocument.id">
            <a-typography-text copyable>{{ previewDocument.id }}</a-typography-text>
          </a-descriptions-item>
        </a-descriptions>

        <a-divider />

        <!-- 文书内容 -->
        <div class="document-content-section">
          <h4>
            <FileSearchOutlined />
            文书内容
            <a-tag v-if="getContentLength(previewDocument)" color="blue" style="margin-left: 8px">
              {{ getContentLength(previewDocument) }} 字
            </a-tag>
          </h4>

          <div v-if="getDocumentContent(previewDocument)" class="content-wrapper">
            <div class="content-text" v-html="getDocumentContentHtml(previewDocument)"></div>
          </div>
          <a-empty v-else description="该文书暂无内容" />
        </div>
      </div>

      <!-- 抽屉底部操作按钮 -->
      <template #footer>
        <a-space>
          <a-button @click="previewDrawerVisible = false">关闭</a-button>
          <a-button
            type="primary"
            @click="handleSelectFromPreview"
            :disabled="isDocumentSelected(previewDocument)"
          >
            <CheckCircleOutlined />
            选择此文书
          </a-button>
        </a-space>
      </template>
    </a-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, h, onMounted, watch, reactive } from 'vue'
import { useQCDemoStore } from '@/stores/qcDemo'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  CheckCircleOutlined,
  FileOutlined,
  ReloadOutlined,
  UserOutlined,
  EnvironmentOutlined,
  CalendarOutlined,
  MedicineBoxOutlined,
  FileSearchOutlined,
  RightOutlined,
  EyeOutlined
} from '@ant-design/icons-vue'
import type { MedicalRecord } from '@/types/quality-control'

import { ApiService } from '@/services/apiService'

const demoStore = useQCDemoStore()

// 文书预览状态
const previewDrawerVisible = ref(false)
const previewDocument = ref<any>(null)

// 筛选状态
const searchKeyword = ref('')
const selectedDepartment = ref('')
const selectedStatus = ref('')

// 分页配置
const recordsPagination = reactive({
  current: 1,
  pageSize: 6,
  total: 0
})

const handleRecordPageChange = (page: number, pageSize?: number) => {
  recordsPagination.current = page
  if (pageSize && pageSize !== recordsPagination.pageSize) {
    recordsPagination.pageSize = pageSize
  }
}

const recordPaginationConfig = computed(() => ({
  current: recordsPagination.current,
  pageSize: recordsPagination.pageSize,
  total: recordsPagination.total,
  showSizeChanger: true,
  pageSizeOptions: ['6', '10', '20'],
  showTotal: (total: number) => `共 ${total} 条`,
  onChange: handleRecordPageChange,
  onShowSizeChange: handleRecordPageChange
}))

// 过滤后的病历列表
const filteredRecords = computed(() => {
  let records = demoStore.availableRecords

  // 科室筛选
  if (selectedDepartment.value) {
    records = records.filter(r => r.department === selectedDepartment.value)
  }

  // 状态筛选
  if (selectedStatus.value) {
    records = records.filter(r => r.status === selectedStatus.value)
  }

  // 关键词搜索
  if (searchKeyword.value) {
    const keyword = searchKeyword.value.toLowerCase()
    records = records.filter(r =>
      r.patient_name?.toLowerCase().includes(keyword) ||
      r.id?.toLowerCase().includes(keyword)
    )
  }

  return records
})

const paginatedRecords = computed(() => {
  const { current, pageSize } = recordsPagination
  const start = (current - 1) * pageSize
  return filteredRecords.value.slice(start, start + pageSize)
})

watch(
  filteredRecords,
  (records) => {
    recordsPagination.total = records.length
    const { pageSize } = recordsPagination
    const maxPage = Math.max(1, Math.ceil(records.length / pageSize))
    if (recordsPagination.current > maxPage) {
      recordsPagination.current = maxPage
    }
  },
  { immediate: true }
)

// 可用文书列表
const availableDocuments = computed(() => {
  if (!demoStore.testRecord) return []

  const documents = demoStore.testRecord.documents || []
  if (documents.length > 0) {
    return documents
  }

  // 如果没有文书列表，返回默认文书
  return [{
    id: `doc-${demoStore.testRecord.id}`,
    title: '首次病程记录',
    type: '首次病程记录',
    created_at: demoStore.testRecord.admission_date || new Date().toISOString()
  }]
})

// 是否可以继续
const canProceed = computed(() => {
  return demoStore.testRecord && demoStore.selectedDocumentList.length > 0
})

// 判断病历是否被选中
const isRecordSelected = (record: MedicalRecord) => {
  return demoStore.testRecord?.id === record.id
}

// 判断文书是否被选中
const isDocumentSelected = (doc: any) => {
  const selectedDocs = demoStore.selectedDocumentList
  return selectedDocs.some(d => d.id === doc.id)
}

// 格式化日期
const formatDate = (date: string | undefined) => {
  if (!date) return '未知'
  return new Date(date).toLocaleDateString('zh-CN')
}

// 处理病历选择
const handleSelectRecord = async (record: MedicalRecord) => {
  try {
    // 先设置选中的病历，保证右侧信息区立即更新
    demoStore.selectTestRecord(record)

    // 加载该病历的真实文书列表
    const resp = await ApiService.getMedicalRecordDocuments(record.id)
    if (resp.success && Array.isArray(resp.data) && resp.data.length > 0) {
      // 回填到 testRecord.documents，供可用文书列表使用
      demoStore.selectTestRecord({ ...(record as any), documents: resp.data } as any)
      // 自动选择优先文书（入院记录优先），以便可以直接开始质控
      const docList = resp.data
      const preferred = docList.find((d: any) =>
        d.type === 'admission_record' || (d.title && String(d.title).includes('入院记录'))
      ) || docList[0]
      if (preferred) {
        demoStore.setSelectedDocument(preferred as any)
      }
      message.success(`已选择病历：${record.patient_name}（已加载 ${resp.data.length} 篇文书）`)
    } else {
      // 接口成功但无文书，保持默认占位文书
      message.warning(`已选择病历：${record.patient_name}（未找到关联文书，使用默认文书）`)
    }
  } catch (err) {
    console.error('[TargetSelectionStep] 加载文书失败:', err)
    // 接口失败，保持默认占位文书
    message.warning(`已选择病历：${record.patient_name}（加载文书失败，使用默认文书）`)
  }
}

// 处理文书选择
const handleSelectDocument = (doc: any) => {
  demoStore.setSelectedDocument(doc)
  message.success(`已选择文书：${doc.title || doc.type}`)
}

// 处理文书预览
const handlePreviewDocument = (doc: any) => {
  previewDocument.value = doc
  previewDrawerVisible.value = true
}

// 从预览中选择文书
const handleSelectFromPreview = () => {
  if (previewDocument.value) {
    handleSelectDocument(previewDocument.value)
    previewDrawerVisible.value = false
  }
}

// 获取文书内容
const getDocumentContent = (doc: any) => {
  if (!doc) return ''
  return doc.content || ''
}

const escapeHtml = (text: string) => {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

const getDocumentContentHtml = (doc: any) => {
  const content = getDocumentContent(doc)
  if (!content) return ''
  return escapeHtml(content).replace(/\r?\n/g, '<br />')
}

// 获取文书内容长度
const getContentLength = (doc: any) => {
  const content = getDocumentContent(doc)
  return content ? content.length : 0
}

// 处理刷新
const handleRefreshRecords = async () => {
  await demoStore.refreshData(true)
  message.success('数据已刷新')
}

// 处理搜索
const handleSearch = () => {
  recordsPagination.current = 1
}

// 处理科室变化
const handleDepartmentChange = () => {
  recordsPagination.current = 1
}

// 处理状态变化
const handleStatusChange = () => {
  recordsPagination.current = 1
}

const handleResetFilters = () => {
  searchKeyword.value = ''
  selectedDepartment.value = ''
  selectedStatus.value = ''
  recordsPagination.current = 1
}

// 处理继续
const handleProceed = async () => {
  await demoStore.nextStep()
}

// 处理清空选择
const handleClearSelection = () => {
  demoStore.selectTestRecord(null as any)
  demoStore.clearSelectedDocument()
  message.info('已清空选择')
}

// 组件挂载时加载数据
onMounted(async () => {
  if (demoStore.availableRecords.length === 0) {
    await demoStore.loadTestData()
  }
})
</script>

<style scoped lang="less">
.target-selection-step {
  .stats-row {
    margin-bottom: 16px;

    .stat-card {
      background: linear-gradient(135deg, var(--primary-color-light) 0%, var(--primary-color) 100%);
      color: white;

      :deep(.ant-statistic-title) {
        color: rgba(255, 255, 255, 0.85);
      }

      :deep(.ant-statistic-content) {
        color: white;
      }

      .stat-suffix {
        font-size: 14px;
        margin-left: 4px;
      }
    }
  }

  .content-row {
    .section-card {
      height: 600px;
      display: flex;
      flex-direction: column;
      gap: 12px;

      :deep(.ant-card-body) {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 12px;
        padding: 16px;
      }

      .filters-section {
        margin-bottom: 0;

        :deep(.ant-input-affix-wrapper),
        :deep(.ant-select-selector) {
          background-color: #ffffff;
          border-radius: 20px;
          border-color: #d9dee5;
          transition: all 0.2s ease;
          height: 36px;
        }

        :deep(.ant-input-affix-wrapper:focus),
        :deep(.ant-input-affix-wrapper-focused),
        :deep(.ant-select-selector:focus),
        :deep(.ant-select-focused .ant-select-selector) {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 3px rgba(11, 100, 212, 0.12);
        }
      }

      .records-list,
      .documents-section {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        margin-bottom: 8px;
      }

      .record-item,
      .document-item {
        cursor: pointer;
        transition: all 0.2s ease;
        border-radius: 6px;
        padding: 10px 12px;
        margin-bottom: 6px;
        border: 1px solid transparent;

        &:hover {
          background-color: #f0f5ff;
          border-color: #bae0ff;
        }

        &.selected {
          background-color: #e6f4ff;
          border-color: #1890ff;
          box-shadow: 0 0 0 3px rgba(24, 144, 255, 0.12);
        }

        .patient-name {
          font-weight: 500;
          font-size: 14px;
        }
      }

      .document-item {
        :deep(.ant-list-item-action) {
          margin-left: 8px;
        }
      }

      .empty-state {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
      }

      .record-summary {
        margin-bottom: 8px;
      }

      .records-list {
        :deep(.ant-spin-nested-loading),
        :deep(.ant-spin-container),
        :deep(.ant-list) {
          height: 100%;
          display: flex;
          flex-direction: column;
          padding-bottom: 4px;
        }

        :deep(.ant-list-items) {
          flex: 1;
          overflow-y: auto;
          padding-right: 4px;
        }

        :deep(.ant-list-pagination) {
          margin-top: auto;
          padding-top: 8px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        :deep(.ant-pagination-options) {
          margin-left: auto;
        }
      }

      .documents-list {
        h4 {
          margin-bottom: 12px;
          font-weight: 500;
        }

        :deep(.ant-spin-nested-loading),
        :deep(.ant-spin-container),
        :deep(.ant-list) {
          height: 100%;
          display: flex;
          flex-direction: column;
          padding-bottom: 4px;
        }

        :deep(.ant-list-items) {
          flex: 1;
          overflow-y: auto;
          padding-right: 4px;
        }

        :deep(.ant-list-pagination) {
          margin-top: auto;
          padding-top: 8px;
        }

        :deep(.ant-empty-description) {
          color: var(--text-secondary);
        }
      }

      .empty-description {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        font-size: 13px;
      }
    }
  }

  .footer-actions {
    margin-top: 24px;
    padding: 16px 20px;
    background-color: #ffffff;
    border-radius: 12px;
    box-shadow: 0 1px 6px rgba(15, 23, 42, 0.06);
    text-align: center;

    :deep(.ant-btn) {
      border-radius: 24px;
      padding: 0 20px;
      height: 38px;
      font-weight: 600;
    }
  }

  // 文书预览抽屉样式
  .document-preview {
    .document-info {
      margin-bottom: 24px;
    }

    .document-content-section {
      h4 {
        font-weight: 600;
        margin-bottom: 16px;
        color: #333;
        display: flex;
        align-items: center;
        gap: 8px;
      }

      .content-wrapper {
        background-color: #f5f5f5;
        border: 1px solid #d9d9d9;
        border-radius: 4px;
        padding: 16px;
        max-height: calc(100vh - 400px);
        overflow-y: auto;

        .content-text {
          margin: 0;
          white-space: normal;
          word-break: break-word;
          overflow-wrap: anywhere;
          font-family: 'Courier New', Courier, monospace;
          font-size: 14px;
          line-height: 1.8;
          color: #333;
        }
      }
    }
  }
}

@media (max-width: 768px) {
  .target-selection-step {
    .content-row {
      flex-direction: column;

      .section-card {
        height: auto;
      }
    }
  }
}
</style>
