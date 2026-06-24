<template>
  <a-modal
    :visible="props.visible"
    :title="modalTitle"
    width="1200px"
    :footer="null"
    @cancel="handleCancel"
  >
    <div class="record-detail-content">
      <a-tabs
        v-model:active-key="activeTab"
        type="card"
      >
        <!-- 基本信息 -->
        <a-tab-pane
          key="basic"
          tab="基本信息"
        >
          <div class="basic-info">
            <a-descriptions
              :column="2"
              bordered
            >
              <a-descriptions-item label="登记号">
                {{ record?.registrationNo }}
              </a-descriptions-item>
              <a-descriptions-item label="流水号">
                {{ record?.serialNo }}
              </a-descriptions-item>
              <a-descriptions-item label="病案号">
                {{ record?.caseNo }}
              </a-descriptions-item>
              <a-descriptions-item label="患者姓名">
                {{ record?.patientName }}
              </a-descriptions-item>
              <a-descriptions-item label="科室">
                {{ record?.department }}
              </a-descriptions-item>
              <a-descriptions-item label="临床医生">
                {{ record?.doctor }}
              </a-descriptions-item>
              <a-descriptions-item label="审核状态">
                <a-tag :color="getAuditStatusColor(record?.auditStatus)">
                  {{ getAuditStatusText(record?.auditStatus) }}
                </a-tag>
              </a-descriptions-item>
              <a-descriptions-item label="评分">
                <span class="score-value">{{ record?.score }}</span>
              </a-descriptions-item>
              <a-descriptions-item label="评分标准">
                {{ record?.scoringStandard }}
              </a-descriptions-item>
              <a-descriptions-item label="缺陷数量">
                <a-badge
                  :count="record?.defectCount"
                  :number-style="{ backgroundColor: '#f50' }"
                />
              </a-descriptions-item>
              <a-descriptions-item label="创建时间">
                {{ record?.createTime }}
              </a-descriptions-item>
              <a-descriptions-item label="更新时间">
                {{ record?.updateTime }}
              </a-descriptions-item>
            </a-descriptions>
          </div>
        </a-tab-pane>

        <!-- 缺陷列表 -->
        <a-tab-pane
          key="defects"
          tab="缺陷列表"
        >
          <div class="defects-list">
            <a-table
              :columns="defectColumns"
              :data-source="defectList"
              :pagination="false"
              size="small"
              row-key="id"
            >
              <template #bodyCell="{ column, record: defect }">
                <template v-if="column.key === 'defectType'">
                  <a-tag color="blue">
                    {{ defect.defectType }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'priority'">
                  <a-tag :color="getPriorityColor(defect.priority)">
                    {{ getPriorityText(defect.priority) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'defectStatus'">
                  <a-tag :color="getDefectStatusColor(defect.defectStatus)">
                    {{ getDefectStatusText(defect.defectStatus) }}
                  </a-tag>
                </template>
                <template v-if="column.key === 'action'">
                  <a-button
                    type="link"
                    size="small"
                    @click="handleDefectDetail(defect)"
                  >
                    查看详情
                  </a-button>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <!-- 电子病历 -->
        <a-tab-pane
          key="document"
          tab="电子病历"
        >
          <div class="document-viewer">
            <div class="document-toolbar mb-4">
              <a-space>
                <a-button
                  type="primary"
                  @click="handleViewFullDocument"
                >
                  <FileTextOutlined />
                  查看完整病历
                </a-button>
                <a-button @click="handlePrintDocument">
                  <PrinterOutlined />
                  打印病历
                </a-button>
                <a-button @click="handleDownloadDocument">
                  <DownloadOutlined />
                  下载病历
                </a-button>
              </a-space>
            </div>

            <div class="document-sections">
              <a-collapse
                v-model:active-key="activeSections"
                ghost
              >
                <a-collapse-panel
                  v-for="section in documentSections"
                  :key="section.id"
                  :header="section.name"
                >
                  <div class="section-content">
                    <div
                      class="section-text"
                      v-html="section.content"
                    />
                    
                    <!-- 该章节的缺陷 -->
                    <div
                      v-if="section.defects && section.defects.length > 0"
                      class="section-defects mt-4"
                    >
                      <h5 class="text-red-600 mb-2">
                        本章节缺陷:
                      </h5>
                      <div class="defect-items">
                        <div
                          v-for="defect in section.defects"
                          :key="defect.id"
                          class="defect-item p-3 bg-red-50 border border-red-200 rounded mb-2"
                        >
                          <div class="defect-header flex justify-between items-center mb-2">
                            <span class="defect-type font-medium">{{ defect.defectType }}</span>
                            <a-tag :color="getPriorityColor(defect.priority)">
                              {{ getPriorityText(defect.priority) }}
                            </a-tag>
                          </div>
                          <div class="defect-description text-gray-700">
                            {{ defect.defectDescription }}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </a-collapse-panel>
              </a-collapse>
            </div>
          </div>
        </a-tab-pane>

        <!-- 操作历史 -->
        <a-tab-pane
          key="history"
          tab="操作历史"
        >
          <div class="operation-history">
            <a-timeline>
              <a-timeline-item
                v-for="operation in operationHistory"
                :key="operation.id"
                :color="getOperationColor(operation.type)"
              >
                <div class="operation-item">
                  <div class="operation-header">
                    <span class="operation-type font-medium">
                      {{ getOperationText(operation.type) }}
                    </span>
                    <span class="operation-time text-gray-500 ml-2">
                      {{ operation.operateTime }}
                    </span>
                  </div>
                  <div class="operation-operator text-sm text-gray-600">
                    操作人: {{ operation.operator }}
                  </div>
                  <div class="operation-description text-sm mt-1">
                    {{ operation.description }}
                  </div>
                  <div
                    v-if="operation.result"
                    class="operation-result text-sm text-green-600 mt-1"
                  >
                    结果: {{ operation.result }}
                  </div>
                </div>
              </a-timeline-item>
            </a-timeline>
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>

    <!-- 底部操作按钮 -->
    <template #footer>
      <div class="flex justify-between">
        <div>
          <a-button
            v-if="viewType === 'records'"
            type="primary"
            @click="handleAudit"
          >
            审核
          </a-button>
          <a-button
            v-if="viewType === 'records'"
            @click="handleUrge"
          >
            催办
          </a-button>
          <a-button @click="handleExportDetail">
            导出详情
          </a-button>
        </div>
        <div>
          <a-button @click="handleCancel">
            关闭
          </a-button>
        </div>
      </div>
    </template>
  </a-modal>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { message } from 'ant-design-vue'
import {
  FileTextOutlined,
  PrinterOutlined,
  DownloadOutlined
} from '@ant-design/icons-vue'

interface Props {
  visible: boolean
  record?: {
    registrationNo?: string
    serialNo?: string
    caseNo?: string
    patientName?: string
    department?: string
    doctor?: string
    auditStatus?: string
    score?: number
    scoringStandard?: string
    defectCount?: number
    createTime?: string
    updateTime?: string
  }
  viewType: 'records' | 'defects'
}

interface Emits {
  (e: 'update:visible', value: boolean): void
}

const props = withDefaults(defineProps<Props>(), {
  visible: false,
  viewType: 'records'
})

const emit = defineEmits<Emits>()

const activeTab = ref('basic')
const activeSections = ref(['1', '2'])

// 模态框标题
const modalTitle = computed(() => {
  if (!props.record) return '详情'
  return `${props.viewType === 'records' ? '病历' : '缺陷'}详情 - ${props.record.registrationNo}`
})

// 缺陷列表列配置
const defectColumns = [
  { title: '缺陷类型', dataIndex: 'defectType', key: 'defectType', width: 120 },
  { title: '缺陷描述', dataIndex: 'defectDescription', key: 'defectDescription' },
  { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
  { title: '状态', dataIndex: 'defectStatus', key: 'defectStatus', width: 100 },
  { title: '创建时间', dataIndex: 'createTime', key: 'createTime', width: 150 },
  { title: '操作', key: 'action', width: 100 }
]

// 模拟数据
const defectList = ref([
  {
    id: '1',
    defectType: '诊断不完整',
    defectDescription: '主要诊断缺少具体分型',
    priority: 'high',
    defectStatus: 'pending',
    createTime: '2024-01-15 10:30:00'
  },
  {
    id: '2',
    defectType: '用药记录',
    defectDescription: '抗生素使用未记录过敏史',
    priority: 'medium',
    defectStatus: 'rectified',
    createTime: '2024-01-15 11:00:00'
  }
])

const documentSections = ref([
  {
    id: '1',
    name: '入院记录',
    type: 'admission',
    content: '<p>患者因"胸痛3小时"入院...</p><p>既往史：高血压病史5年...</p>',
    defects: [defectList.value[0]]
  },
  {
    id: '2',
    name: '病程记录',
    type: 'progress',
    content: '<p>2024-01-15 入院第1天...</p><p>患者一般情况可...</p>',
    defects: [defectList.value[1]]
  }
])

const operationHistory = ref([
  {
    id: '1',
    type: 'audit',
    operator: '质控医生A',
    operateTime: '2024-01-15 14:30:00',
    description: '进行质控审核',
    result: '发现2处缺陷'
  },
  {
    id: '2',
    type: 'urge',
    operator: '质控医生A',
    operateTime: '2024-01-15 15:00:00',
    description: '催办整改',
    result: '已通知临床医生'
  }
])

// 状态颜色和文本映射
const getAuditStatusColor = (status?: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    reviewing: 'blue',
    passed: 'green',
    questioned: 'red'
  }
  return status ? (colorMap[status] || 'default') : 'default'
}

const getAuditStatusText = (status?: string) => {
  const textMap: Record<string, string> = {
    pending: '待审核',
    reviewing: '审核中',
    passed: '已通过',
    questioned: '存疑'
  }
  return status ? (textMap[status] || status) : '未知'
}

const getPriorityColor = (priority: string) => {
  const colorMap: Record<string, string> = {
    high: 'red',
    medium: 'orange',
    low: 'green'
  }
  return colorMap[priority] || 'default'
}

const getPriorityText = (priority: string) => {
  const textMap: Record<string, string> = {
    high: '高',
    medium: '中',
    low: '低'
  }
  return textMap[priority] || priority
}

const getDefectStatusColor = (status: string) => {
  const colorMap: Record<string, string> = {
    pending: 'orange',
    urged: 'red',
    rectified: 'green',
    appealed: 'purple'
  }
  return colorMap[status] || 'default'
}

const getDefectStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    pending: '待整改',
    urged: '已催办',
    rectified: '已整改',
    appealed: '已申诉'
  }
  return textMap[status] || status
}

const getOperationColor = (type: string) => {
  const colorMap: Record<string, string> = {
    audit: 'blue',
    urge: 'orange',
    rectify: 'green',
    comment: 'purple'
  }
  return colorMap[type] || 'gray'
}

const getOperationText = (type: string) => {
  const textMap: Record<string, string> = {
    audit: '质控审核',
    urge: '催办整改',
    rectify: '缺陷整改',
    comment: '添加备注'
  }
  return textMap[type] || type
}

// 事件处理
const handleCancel = () => {
  emit('update:visible', false)
}

const handleDefectDetail = (defect: { defectType?: string }) => {
  message.info(`查看缺陷详情: ${defect.defectType}`)
}

const handleViewFullDocument = () => {
  message.info('打开完整病历查看器')
}

const handlePrintDocument = () => {
  message.info('打印病历')
}

const handleDownloadDocument = () => {
  message.info('下载病历文档')
}

const handleAudit = () => {
  message.info('进入审核流程')
}

const handleUrge = () => {
  message.info('发送催办通知')
}

const handleExportDetail = () => {
  message.info('导出详情报告')
}

// 监听visible变化，重置activeTab
watch(() => props.visible, (newVal) => {
  if (newVal) {
    activeTab.value = 'basic'
  }
})
</script>

<style scoped>
.record-detail-content {
  max-height: 70vh;
  overflow-y: auto;
}

.score-value {
  font-size: 18px;
  font-weight: bold;
  color: #1890ff;
}

.section-content {
  background-color: #fafafa;
  padding: 16px;
  border-radius: 6px;
}

.section-text {
  line-height: 1.6;
  color: #333;
}

.section-defects {
  border-top: 1px solid #e8e8e8;
  padding-top: 16px;
}

.defect-item {
  transition: all 0.3s;
}

.defect-item:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.operation-item {
  padding: 8px 0;
}

.operation-header {
  display: flex;
  align-items: center;
}

:deep(.ant-descriptions-item-label) {
  font-weight: 500;
  background-color: #f8f9fa;
}

:deep(.ant-collapse-ghost > .ant-collapse-item > .ant-collapse-header) {
  padding: 12px 0;
  font-weight: 500;
}

:deep(.ant-timeline-item-content) {
  margin-left: 24px;
}
</style>
