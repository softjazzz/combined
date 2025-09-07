<template>
  <div class="unstructured-documents-view">
    <div class="page-header">
      <h1>非结构化文档管理</h1>
      <p>管理复制粘贴的原始病历文本和文档</p>
    </div>

    <!-- 快速添加区域 -->
    <Card class="quick-add-card" title="快速添加文档">
      <div class="quick-add-form">
        <div class="form-row">
          <Input
            v-model:value="newDocument.title"
            placeholder="文档标题（可选）"
            style="width: 200px; margin-right: 12px;"
          />
          <Select
            v-model:value="newDocument.category"
            placeholder="选择分类"
            style="width: 150px; margin-right: 12px;"
          >
            <SelectOption value="心血管内科">心血管内科</SelectOption>
            <SelectOption value="呼吸内科">呼吸内科</SelectOption>
            <SelectOption value="消化内科">消化内科</SelectOption>
            <SelectOption value="神经内科">神经内科</SelectOption>
            <SelectOption value="妇产科">妇产科</SelectOption>
            <SelectOption value="外科">外科</SelectOption>
            <SelectOption value="其他">其他</SelectOption>
          </Select>
          <Button type="primary" @click="saveDocument" :loading="saving">
            保存文档
          </Button>
        </div>
        <div class="form-row">
          <TextArea
            v-model:value="newDocument.content"
            placeholder="在此粘贴病历文本内容..."
            :rows="8"
            style="width: 100%;"
          />
        </div>
      </div>
    </Card>

    <!-- 文档列表 -->
    <Card class="documents-list-card" title="文档列表">
      <template #extra>
        <Space>
          <Input.Search
            v-model:value="searchTerm"
            placeholder="搜索文档..."
            style="width: 200px;"
            @search="handleSearch"
          />
          <Select
            v-model:value="filters.processing_status"
            placeholder="处理状态"
            style="width: 120px;"
            allowClear
            @change="loadDocuments"
          >
            <SelectOption value="pending">待处理</SelectOption>
            <SelectOption value="processing">处理中</SelectOption>
            <SelectOption value="completed">已完成</SelectOption>
            <SelectOption value="failed">失败</SelectOption>
          </Select>
          <Button @click="loadDocuments" :loading="loading">
            <template #icon><ReloadOutlined /></template>
            刷新
          </Button>
        </Space>
      </template>

      <Table
        :columns="columns"
        :data-source="documents"
        :loading="loading"
        :pagination="pagination"
        @change="handleTableChange"
        row-key="id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'title'">
            <div class="document-title">
              <strong>{{ record.title }}</strong>
              <div class="document-meta">
                <Tag :color="getDocumentTypeColor(record.document_type)">
                  {{ getDocumentTypeText(record.document_type) }}
                </Tag>
                <span class="content-length">{{ record.content_length }} 字符</span>
              </div>
            </div>
          </template>

          <template v-if="column.key === 'processing_status'">
            <Tag :color="getStatusColor(record.processing_status)">
              {{ getStatusText(record.processing_status) }}
            </Tag>
          </template>

          <template v-if="column.key === 'qc_status'">
            <Tag :color="getQCStatusColor(record.qc_status)">
              {{ getQCStatusText(record.qc_status) }}
            </Tag>
          </template>

          <template v-if="column.key === 'created_at'">
            {{ formatDate(record.created_at) }}
          </template>

          <template v-if="column.key === 'actions'">
            <Space>
              <Button size="small" @click="viewDocument(record)">
                查看
              </Button>
              <Button size="small" @click="editDocument(record)">
                编辑
              </Button>
              <Button size="small" danger @click="deleteDocument(record)">
                删除
              </Button>
            </Space>
          </template>
        </template>
      </Table>
    </Card>

    <!-- 文档详情模态框 -->
    <Modal
      v-model:open="documentModalVisible"
      :title="currentDocument?.title || '文档详情'"
      width="80%"
      :footer="null"
    >
      <div v-if="currentDocument" class="document-detail">
        <Descriptions :column="2" bordered>
          <DescriptionsItem label="文档类型">
            <Tag :color="getDocumentTypeColor(currentDocument.document_type)">
              {{ getDocumentTypeText(currentDocument.document_type) }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem label="处理状态">
            <Tag :color="getStatusColor(currentDocument.processing_status)">
              {{ getStatusText(currentDocument.processing_status) }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem label="质控状态">
            <Tag :color="getQCStatusColor(currentDocument.qc_status)">
              {{ getQCStatusText(currentDocument.qc_status) }}
            </Tag>
          </DescriptionsItem>
          <DescriptionsItem label="分类">
            {{ currentDocument.category || '未分类' }}
          </DescriptionsItem>
          <DescriptionsItem label="内容长度">
            {{ currentDocument.content_length }} 字符
          </DescriptionsItem>
          <DescriptionsItem label="创建时间">
            {{ formatDate(currentDocument.created_at) }}
          </DescriptionsItem>
        </Descriptions>

        <Divider>文档内容</Divider>
        <div class="document-content">
          <pre>{{ currentDocument.raw_content }}</pre>
        </div>

        <div v-if="currentDocument.extracted_data && Object.keys(currentDocument.extracted_data).length > 0">
          <Divider>提取的结构化数据</Divider>
          <pre>{{ JSON.stringify(currentDocument.extracted_data, null, 2) }}</pre>
        </div>
      </div>
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { 
  Card, Table, Button, Input, Textarea, Select, SelectOption, 
  Space, Tag, Modal, Descriptions, DescriptionsItem, Divider,
  message
} from 'ant-design-vue'
import { ReloadOutlined } from '@ant-design/icons-vue'
import { 
  getUnstructuredDocuments, 
  saveRawMedicalText, 
  deleteUnstructuredDocument,
  searchUnstructuredDocuments
} from '@/api/unstructured-documents'
import type { Database } from '@/types/database'

type UnstructuredDocument = Database['public']['Tables']['unstructured_medical_documents']['Row']

// 响应式数据
const documents = ref<UnstructuredDocument[]>([])
const loading = ref(false)
const saving = ref(false)
const searchTerm = ref('')
const documentModalVisible = ref(false)
const currentDocument = ref<UnstructuredDocument | null>(null)

// 新文档表单
const newDocument = reactive({
  title: '',
  content: '',
  category: ''
})

// 筛选条件
const filters = reactive({
  processing_status: undefined as string | undefined,
  qc_status: undefined as string | undefined,
  category: undefined as string | undefined
})

// 分页配置
const pagination = reactive({
  current: 1,
  pageSize: 10,
  total: 0,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条记录`
})

// 表格列配置
const columns = [
  {
    title: '文档信息',
    key: 'title',
    width: 300
  },
  {
    title: '分类',
    dataIndex: 'category',
    key: 'category',
    width: 120
  },
  {
    title: '处理状态',
    key: 'processing_status',
    width: 100
  },
  {
    title: '质控状态',
    key: 'qc_status',
    width: 100
  },
  {
    title: '创建时间',
    key: 'created_at',
    width: 150
  },
  {
    title: '操作',
    key: 'actions',
    width: 200
  }
]

// 方法
const loadDocuments = async () => {
  loading.value = true
  try {
    const response = await getUnstructuredDocuments({
      ...filters,
      limit: pagination.pageSize,
      offset: (pagination.current - 1) * pagination.pageSize
    })

    if (response.success && response.data) {
      documents.value = response.data
      // 这里应该从API获取总数，暂时使用数据长度
      pagination.total = response.data.length
    } else {
      message.error(response.error?.message || '加载文档失败')
    }
  } catch (error) {
    message.error('加载文档失败')
  } finally {
    loading.value = false
  }
}

const saveDocument = async () => {
  if (!newDocument.content.trim()) {
    message.warning('请输入文档内容')
    return
  }

  saving.value = true
  try {
    const response = await saveRawMedicalText(
      newDocument.content,
      newDocument.title || undefined,
      newDocument.category || undefined
    )

    if (response.success) {
      message.success('文档保存成功')
      // 重置表单
      newDocument.title = ''
      newDocument.content = ''
      newDocument.category = ''
      // 重新加载列表
      await loadDocuments()
    } else {
      message.error(response.error?.message || '保存失败')
    }
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

const handleSearch = async () => {
  if (!searchTerm.value.trim()) {
    await loadDocuments()
    return
  }

  loading.value = true
  try {
    const response = await searchUnstructuredDocuments(searchTerm.value, {
      limit: pagination.pageSize,
      offset: (pagination.current - 1) * pagination.pageSize
    })

    if (response.success && response.data) {
      documents.value = response.data
      pagination.total = response.data.length
    } else {
      message.error(response.error?.message || '搜索失败')
    }
  } catch (error) {
    message.error('搜索失败')
  } finally {
    loading.value = false
  }
}

const viewDocument = (document: UnstructuredDocument) => {
  currentDocument.value = document
  documentModalVisible.value = true
}

const editDocument = (document: UnstructuredDocument) => {
  // TODO: 实现编辑功能
  message.info('编辑功能开发中...')
}

const deleteDocument = async (document: UnstructuredDocument) => {
  try {
    const response = await deleteUnstructuredDocument(document.id)
    if (response.success) {
      message.success('删除成功')
      await loadDocuments()
    } else {
      message.error(response.error?.message || '删除失败')
    }
  } catch (error) {
    message.error('删除失败')
  }
}

const handleTableChange = (pag) => {
  pagination.current = pag.current
  pagination.pageSize = pag.pageSize
  loadDocuments()
}

// 工具方法
const getDocumentTypeColor = (type: string) => {
  const colors = {
    'raw_text': 'blue',
    'copied_record': 'green',
    'uploaded_file': 'orange',
    'scanned_document': 'purple'
  }
  return colors[type as keyof typeof colors] || 'default'
}

const getDocumentTypeText = (type: string) => {
  const texts = {
    'raw_text': '原始文本',
    'copied_record': '复制记录',
    'uploaded_file': '上传文件',
    'scanned_document': '扫描文档'
  }
  return texts[type as keyof typeof texts] || type
}

const getStatusColor = (status: string) => {
  const colors = {
    'pending': 'orange',
    'processing': 'blue',
    'completed': 'green',
    'failed': 'red',
    'skipped': 'gray'
  }
  return colors[status as keyof typeof colors] || 'default'
}

const getStatusText = (status: string) => {
  const texts = {
    'pending': '待处理',
    'processing': '处理中',
    'completed': '已完成',
    'failed': '失败',
    'skipped': '跳过'
  }
  return texts[status as keyof typeof texts] || status
}

const getQCStatusColor = (status: string) => {
  const colors = {
    'not_analyzed': 'gray',
    'analyzing': 'blue',
    'completed': 'green',
    'failed': 'red'
  }
  return colors[status as keyof typeof colors] || 'default'
}

const getQCStatusText = (status: string) => {
  const texts = {
    'not_analyzed': '未分析',
    'analyzing': '分析中',
    'completed': '已完成',
    'failed': '失败'
  }
  return texts[status as keyof typeof texts] || status
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.unstructured-documents-view {
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.page-header p {
  margin: 0;
  color: #666;
}

.quick-add-card {
  margin-bottom: 24px;
}

.quick-add-form .form-row {
  margin-bottom: 16px;
}

.quick-add-form .form-row:last-child {
  margin-bottom: 0;
}

.documents-list-card {
  margin-bottom: 24px;
}

.document-title {
  line-height: 1.4;
}

.document-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #666;
}

.content-length {
  margin-left: 8px;
}

.document-detail {
  max-height: 70vh;
  overflow-y: auto;
}

.document-content {
  background: #f5f5f5;
  padding: 16px;
  border-radius: 6px;
  max-height: 400px;
  overflow-y: auto;
}

.document-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.6;
}
</style>
