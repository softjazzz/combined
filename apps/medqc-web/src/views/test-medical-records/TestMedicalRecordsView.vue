<template>
  <div class="test-medical-records-page">
    <div class="page-header">
      <a-page-header
        title="测试病历管理"
        sub-title="管理质控验证所需的测试病历数据集"
      >
        <template #extra>
          <a-space>
            <a-button type="default" :disabled="!selectedCount" @click="handleBatchAction('export')">
              <template #icon>
                <ExportOutlined />
              </template>
              导出
            </a-button>
            <a-button type="default" :disabled="!selectedCount" @click="handleBatchAction('duplicate')">
              <template #icon>
                <CopyOutlined />
              </template>
              批量复制
            </a-button>
            <a-button type="primary">
              <template #icon>
                <PlusOutlined />
              </template>
              新建病历
            </a-button>
          </a-space>
        </template>
      </a-page-header>
    </div>

    <a-card class="filter-card" :bordered="false">
      <a-form layout="inline" class="filter-form" @submit.prevent>
        <a-form-item label="关键字">
          <a-input-group compact>
            <a-select v-model:value="filterForm.keywordType" style="width: 120px">
              <a-select-option value="name">病历名称</a-select-option>
              <a-select-option value="id">病历编号</a-select-option>
              <a-select-option value="creator">创建人</a-select-option>
            </a-select>
            <a-input
              v-model:value="filterForm.keyword"
              style="width: 220px"
              placeholder="输入关键字搜索"
              @press-enter="applyFilter"
            />
          </a-input-group>
        </a-form-item>

        <a-form-item label="病历类型">
          <a-select
            v-model:value="filterForm.recordType"
            mode="multiple"
            allow-clear
            placeholder="选择病历类型"
            style="width: 220px"
          >
            <a-select-option v-for="item in recordTypeOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="科室">
          <a-select
            v-model:value="filterForm.departments"
            mode="multiple"
            allow-clear
            placeholder="选择科室"
            style="width: 220px"
          >
            <a-select-option v-for="item in departmentOptions" :key="item" :value="item">
              {{ item }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="状态">
          <a-select
            v-model:value="filterForm.status"
            mode="multiple"
            allow-clear
            placeholder="选择状态"
            style="width: 200px"
          >
            <a-select-option v-for="item in statusOptions" :key="item.value" :value="item.value">
              {{ item.label }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item>
          <a-space>
            <a-button type="primary" @click="applyFilter">
              <template #icon>
                <SearchOutlined />
              </template>
              查询
            </a-button>
            <a-button @click="handleReset">
              <template #icon>
                <ReloadOutlined />
              </template>
              重置
            </a-button>
          </a-space>
        </a-form-item>
      </a-form>

      <div class="quick-filter-section">
        <span class="label">快速筛选:</span>
        <a-space wrap>
          <a-tag
            v-for="tag in quickFilters"
            :key="tag.key"
            :color="isQuickActive(tag.key) ? 'blue' : undefined"
            class="quick-filter-tag"
            @click="toggleQuick(tag)"
          >
            {{ tag.label }}
          </a-tag>
        </a-space>
      </div>
    </a-card>

    <a-card :bordered="false">
      <div class="table-toolbar">
        <div class="left">
          <a-space>
            <a-button size="small" @click="loadTemplates" :loading="templatesLoading">
              <template #icon>
                <FolderOpenOutlined />
              </template>
              筛选模板
            </a-button>
            <a-dropdown>
              <template #overlay>
                <a-menu>
                  <a-menu-item
                    v-for="template in filterTemplates"
                    :key="template.id"
                    @click="applyTemplate(template)"
                  >
                    {{ template.name }}
                  </a-menu-item>
                  <a-menu-divider v-if="filterTemplates.length" />
                  <a-menu-item key="create-template" @click="saveCurrentTemplate">
                    保存当前筛选为模板
                  </a-menu-item>
                </a-menu>
              </template>
              <a-button size="small">
                应用模板
                <DownOutlined />
              </a-button>
            </a-dropdown>
            <a-button size="small" danger v-if="hasActiveFilters" @click="handleReset">
              清除筛选
            </a-button>
          </a-space>
        </div>
        <div class="right">
          <span class="text-muted">已选择 {{ selectedCount }} 条</span>
        </div>
      </div>

      <a-table
        row-key="id"
        :loading="loading"
        :columns="columns"
        :data-source="records"
        :pagination="pagination"
        :row-selection="rowSelection"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <div class="record-name-cell">
              <div class="name">{{ record.name }}</div>
              <div class="meta">
                <a-tag color="geekblue">{{ getRecordTypeLabel(record.type) }}</a-tag>
                <span class="text-muted">编号：{{ record.recordCode }}</span>
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'department'">
            <div class="cell-stack">
              <span>{{ record.department }}</span>
              <span class="text-muted">{{ record.diseaseCategory }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'complexity'">
            <a-tag :color="complexityColorMap[record.complexity]">
              {{ complexityLabelMap[record.complexity] }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'passRate'">
            <a-progress
              :percent="Math.round(record.passRate * 100)"
              :status="record.passRate >= 0.85 ? 'success' : record.passRate >= 0.7 ? 'normal' : 'exception'"
              :show-info="false"
              size="small"
            />
            <div class="text-muted mt-1">{{ (record.passRate * 100).toFixed(1) }}%</div>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag :color="statusColorMap[record.status]">{{ statusLabelMap[record.status] }}</a-tag>
          </template>

          <template v-else-if="column.key === 'tags'">
            <a-space size="small" wrap>
              <a-tag v-for="tag in record.tags" :key="tag">{{ tag }}</a-tag>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive } from 'vue'
import { message, Modal } from 'ant-design-vue'
import type { ColumnsType } from 'ant-design-vue/es/table'
import { storeToRefs } from 'pinia'
import {
  CopyOutlined,
  DownOutlined,
  ExportOutlined,
  FolderOpenOutlined,
  PlusOutlined,
  ReloadOutlined,
  SearchOutlined
} from '@ant-design/icons-vue'
import type { BatchActionPayload, FilterTemplate, QuickFilterTag, TestMedicalRecordSummary } from '@/types/test-medical-records'
import { useTestMedicalRecordsStore } from '@/stores/testMedicalRecords'

const store = useTestMedicalRecordsStore()
const {
  records,
  loading,
  pagination,
  quickFilters,
  activeQuickFilters,
  filterTemplates,
  selectedRowKeys,
  hasActiveFilters,
  selectedCount
} = storeToRefs(store)

const { templatesLoading } = storeToRefs(store)

const filterForm = reactive({
  keyword: '',
  keywordType: 'name',
  recordType: [] as string[],
  departments: [] as string[],
  status: [] as string[]
})

const recordTypeOptions = [
  { value: 'admission', label: '入院记录' },
  { value: 'discharge', label: '出院记录' },
  { value: 'progress', label: '病程记录' }
]

const departmentOptions = ['心内科', '外科', '妇产科', '儿科', '呼吸内科', '内分泌科', '急诊科']

const statusOptions = [
  { value: 'draft', label: '草稿' },
  { value: 'ready', label: '已完成' },
  { value: 'verified', label: '已验证' },
  { value: 'archived', label: '已归档' }
]

const statusLabelMap = {
  draft: '草稿',
  ready: '已完成',
  verified: '已验证',
  archived: '已归档'
} as const

const statusColorMap = {
  draft: 'default',
  ready: 'blue',
  verified: 'green',
  archived: 'purple'
} as const

const complexityLabelMap = {
  simple: '简单',
  medium: '中等',
  complex: '复杂',
  very_complex: '极复杂'
} as const

const complexityColorMap = {
  simple: 'default',
  medium: 'processing',
  complex: 'orange',
  very_complex: 'red'
} as const

const columns: ColumnsType<TestMedicalRecordSummary> = [
  {
    title: '测试病历',
    dataIndex: 'name',
    key: 'name',
    width: 260,
    ellipsis: true
  },
  {
    title: '科室 / 疾病类型',
    dataIndex: 'department',
    key: 'department',
    width: 200
  },
  {
    title: '复杂度',
    dataIndex: 'complexity',
    key: 'complexity',
    width: 100
  },
  {
    title: '质控关联',
    dataIndex: 'relatedRuleCount',
    key: 'relatedRuleCount',
    width: 110,
    sorter: (a, b) => a.relatedRuleCount - b.relatedRuleCount
  },
  {
    title: '通过率',
    dataIndex: 'passRate',
    key: 'passRate',
    width: 140,
    sorter: (a, b) => a.passRate - b.passRate
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 100
  },
  {
    title: '标签',
    dataIndex: 'tags',
    key: 'tags',
    width: 240
  },
  {
    title: '更新时间',
    dataIndex: 'updatedAt',
    key: 'updatedAt',
    width: 180,
    sorter: (a, b) => new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime()
  }
]

const rowSelection = {
  selectedRowKeys,
  onChange: (keys: (string | number)[]) => {
    selectedRowKeys.value = keys as string[]
  }
}

const applyFilter = async () => {
  store.updateConditions({
    keyword: filterForm.keyword || undefined,
    keywordType: filterForm.keywordType,
    recordType: filterForm.recordType.length ? filterForm.recordType : undefined,
    departments: filterForm.departments.length ? filterForm.departments : undefined,
    status: filterForm.status.length ? filterForm.status : undefined
  })
  await store.applyFilters()
}

const handleReset = async () => {
  filterForm.keyword = ''
  filterForm.keywordType = 'name'
  filterForm.recordType = []
  filterForm.departments = []
  filterForm.status = []
  await store.resetFilters()
}

const isQuickActive = (key: string) => activeQuickFilters.value.has(key)

const toggleQuick = async (tag: QuickFilterTag) => {
  await store.toggleQuickFilter(tag)
}

const handleTableChange = async (paginationInfo: any) => {
  await store.changePage(paginationInfo.current, paginationInfo.pageSize)
}

const handleBatchAction = (action: BatchActionPayload['action']) => {
  if (!selectedRowKeys.value.length) {
    message.warning('请先选择至少一条病历')
    return
  }

  if (action === 'delete') {
    Modal.confirm({
      title: '确认删除选中的病历？',
      content: '删除后不可恢复，请谨慎操作。',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () => executeBatch(action)
    })
  } else {
    void executeBatch(action)
  }
}

const executeBatch = async (action: BatchActionPayload['action']) => {
  const result = await store.performBatchAction({
    action,
    recordIds: selectedRowKeys.value
  })
  if (result.failed.length) {
    message.warning(`操作完成，但部分病历未处理：${result.failed.join(', ')}`)
  } else {
    message.success('批量操作执行成功')
  }
}

const loadTemplates = async () => {
  await store.loadTemplates()
}

const applyTemplate = async (template: FilterTemplate) => {
  store.updateConditions(template.conditions)
  Object.assign(filterForm, {
    keyword: template.conditions.keyword ?? '',
    keywordType: template.conditions.keywordType ?? 'name',
    recordType: template.conditions.recordType ?? [],
    departments: template.conditions.departments ?? [],
    status: template.conditions.status ?? []
  })
  await store.applyFilters()
  augmentTable()
  message.success(`已应用模板 ${template.name}`)
}

const saveCurrentTemplate = async () => {
  if (!filterForm.keyword && !filterForm.recordType.length && !filterForm.departments.length && !filterForm.status.length) {
    message.info('当前没有可保存的筛选条件')
    return
  }
  const name = `筛选模板-${new Date().toLocaleString()}`
  await store.saveTemplate({
    name,
    conditions: store.conditions.value
  })
  message.success(`已保存模板：${name}`)
}

const getRecordTypeLabel = (type: string) =>
  recordTypeOptions.find(opt => opt.value === type)?.label ?? type

onMounted(async () => {
  await store.initialize()
})
</script>

<style scoped>
.test-medical-records-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px;
}

.page-header {
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.filter-card {
  background: #fff;
}

.filter-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 24px;
}

.quick-filter-section {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.quick-filter-section .label {
  color: var(--ant-color-text-secondary);
}

.quick-filter-tag {
  cursor: pointer;
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.text-muted {
  color: var(--ant-color-text-secondary);
  font-size: 12px;
}

.record-name-cell .name {
  font-weight: 600;
  color: var(--ant-color-text);
}

.record-name-cell .meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--ant-color-text-secondary);
}

.cell-stack {
  display: flex;
  flex-direction: column;
}
</style>
