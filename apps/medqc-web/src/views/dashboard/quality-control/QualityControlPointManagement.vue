<template>
  <div class="quality-control-point-management">
    <!-- 页面标题 -->
    <div class="page-header mb-6">
      <h2 class="page-title">
        非编码质控点管理
      </h2>
    </div>

    <!-- 标签页 -->
    <div class="tabs-container mb-6">
      <a-tabs
        v-model:active-key="activeTab"
        class="custom-tabs"
      >
        <a-tab-pane
          key="online"
          tab="已上线"
        />
        <a-tab-pane
          key="offline"
          tab="未上线"
        />
      </a-tabs>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar mb-4">
      <!-- 左侧批量操作按钮 -->
      <div class="batch-actions">
        <template v-if="activeTab === 'online'">
          <a-button
            :disabled="selectedRowKeys.length === 0"
            class="batch-btn"
            @click="handleBatchEnable"
          >
            批量开启
          </a-button>
          <a-button
            :disabled="selectedRowKeys.length === 0"
            class="batch-btn"
            @click="handleBatchDisable"
          >
            批量关闭
          </a-button>
          <a-button
            :disabled="selectedRowKeys.length === 0"
            class="batch-btn"
            @click="handleBatchOffline"
          >
            批量下线
          </a-button>
        </template>
        <template v-else>
          <a-button
            :disabled="selectedRowKeys.length === 0"
            class="batch-btn"
            @click="handleBatchDelete"
          >
            批量删除
          </a-button>
          <a-button
            :disabled="selectedRowKeys.length === 0"
            class="batch-btn"
            @click="handleBatchOnline"
          >
            批量上线
          </a-button>
        </template>

        <!-- 导入导出按钮 -->
        <a-button
          class="action-btn"
          @click="handleImport"
        >
          导入质控点
        </a-button>
        <a-button
          class="action-btn"
          @click="handleExport"
        >
          导出质控点
        </a-button>
        <a-button
          type="primary"
          class="create-btn"
          @click="handleCreateNew"
        >
          新建质控点
        </a-button>
      </div>

      <!-- 右侧搜索 -->
      <div class="search-area">
        <a-select
          v-model:value="searchType"
          class="search-type-select"
          placeholder="质控点ID"
        >
          <a-select-option value="id">
            质控点ID
          </a-select-option>
          <a-select-option value="name">
            质控点名称
          </a-select-option>
        </a-select>
        <a-input-search
          v-model:value="searchKeyword"
          placeholder="请输入"
          class="search-input"
          enter-button
          @search="handleSearch"
        />
      </div>
    </div>

    <!-- 数据表格 -->
    <div class="table-container">
      <a-table
        :columns="tableColumns"
        :data-source="tableData"
        :row-selection="rowSelection"
        :pagination="paginationConfig"
        :loading="loading"
        row-key="id"
        size="middle"
        class="quality-point-table"
      >
        <!-- 质控点名称列 -->
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <div class="name-cell">
              <div class="name-text">
                {{ record.name }}
              </div>
              <div class="source-text">
                {{ record.source }}
              </div>
            </div>
          </template>

          <!-- 启用状态列 -->
          <template v-if="column.key === 'enabled' && activeTab === 'online'">
            <a-switch
              v-model:checked="record.enabled"
              size="small"
              @change="(checked: boolean) => handleToggleEnable(record, checked)"
            />
          </template>

          <!-- 操作列 -->
          <template v-if="column.key === 'action'">
            <div class="action-buttons">
              <a-button
                type="link"
                size="small"
                @click="handleView(record)"
              >
                查看
              </a-button>
              <a-button
                type="link"
                size="small"
                @click="handleEdit(record)"
              >
                编辑
              </a-button>
              <a-button
                type="link"
                size="small"
                danger
                @click="handleDelete(record)"
              >
                下线
              </a-button>
            </div>
          </template>
        </template>
      </a-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import { useRouter } from 'vue-router'
import type {
  QualityControlPoint,
  QualityControlSearchParams,
  TableColumn,
  PaginationConfig,
} from '@/types/quality-control'

const router = useRouter()

// 响应式数据
const loading = ref(false)
const activeTab = ref('online')
const selectedRowKeys = ref<string[]>([])
const searchType = ref('id')
const searchKeyword = ref('')

// 表格数据
const tableData = ref<QualityControlPoint[]>([
  {
    id: 'Q2120',
    name: '专病-乳腺癌-乳腺癌...',
    source: '病历书写与管理基本规...',
    category: '内涵质控',
    type: '规范性',
    coreSystem: '',
    document: '入院记录',
    onlineDate: '2024-03-11 16:46',
    lastOperator: '王某',
    enabled: true,
    status: 'online',
  },
  {
    id: 'Q2121',
    name: '专病-乳腺癌-乳腺癌...',
    source: '病历书写与管理基本规...',
    category: '内涵质控',
    type: '规范性',
    coreSystem: '',
    document: '入院记录',
    onlineDate: '2024-03-11 16:46',
    lastOperator: '王某',
    enabled: true,
    status: 'online',
  },
  {
    id: 'Q2122',
    name: '专病-乳腺癌-乳腺癌...',
    source: '病历书写与管理基本规...',
    category: '内涵质控',
    type: '规范性',
    coreSystem: '',
    document: '入院记录',
    onlineDate: '2024-03-11 16:46',
    lastOperator: '王某',
    enabled: true,
    status: 'online',
  },
])

// 表格列配置
const tableColumns = computed<TableColumn[]>(() => {
  const baseColumns: TableColumn[] = [
    {
      title: '质控点ID',
      dataIndex: 'id',
      key: 'id',
      width: 100,
      sorter: true,
    },
    {
      title: '质控点名称',
      dataIndex: 'name',
      key: 'name',
      width: 200,
      sorter: true,
    },
    {
      title: '质控点来源',
      dataIndex: 'source',
      key: 'source',
      width: 150,
      sorter: true,
    },
    {
      title: '质控大类',
      dataIndex: 'category',
      key: 'category',
      width: 120,
      sorter: true,
    },
    {
      title: '质控类型',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      sorter: true,
    },
    {
      title: '核心制度分类',
      dataIndex: 'coreSystem',
      key: 'coreSystem',
      width: 120,
      sorter: true,
    },
    {
      title: '质控文书',
      dataIndex: 'document',
      key: 'document',
      width: 100,
      sorter: true,
    },
  ]

  if (activeTab.value === 'online') {
    baseColumns.push(
      {
        title: '上线日期',
        dataIndex: 'onlineDate',
        key: 'onlineDate',
        width: 150,
        sorter: true,
      },
      {
        title: '最后操作人',
        dataIndex: 'lastOperator',
        key: 'lastOperator',
        width: 100,
        sorter: true,
      },
      {
        title: '启用状态',
        dataIndex: 'enabled',
        key: 'enabled',
        width: 100,
      },
    )
  } else {
    baseColumns.push(
      {
        title: '最后状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        sorter: true,
      },
      {
        title: '上线日期',
        dataIndex: 'onlineDate',
        key: 'onlineDate',
        width: 150,
        sorter: true,
      },
    )
  }

  baseColumns.push({
    title: '操作',
    dataIndex: 'action',
    key: 'action',
    width: 150,
    fixed: 'right',
  })

  return baseColumns
})

// 行选择配置
const rowSelection = {
  selectedRowKeys: selectedRowKeys,
  onChange: (keys: string[]) => {
    selectedRowKeys.value = keys
  },
}

// 分页配置
const paginationConfig = reactive({
  current: 1,
  pageSize: 10,
  total: 2093,
  showSizeChanger: true,
  showQuickJumper: true,
  showTotal: (total: number) => `共 ${total} 条`,
  pageSizeOptions: ['10', '20', '50', '100'],
})

// 事件处理函数
const handleBatchEnable = () => {
  message.success(`已批量开启 ${selectedRowKeys.value.length} 个质控点`)
  selectedRowKeys.value = []
}

const handleBatchDisable = () => {
  message.success(`已批量关闭 ${selectedRowKeys.value.length} 个质控点`)
  selectedRowKeys.value = []
}

const handleBatchOffline = () => {
  message.success(`已批量下线 ${selectedRowKeys.value.length} 个质控点`)
  selectedRowKeys.value = []
}

const handleBatchDelete = () => {
  message.success(`已批量删除 ${selectedRowKeys.value.length} 个质控点`)
  selectedRowKeys.value = []
}

const handleBatchOnline = () => {
  message.success(`已批量上线 ${selectedRowKeys.value.length} 个质控点`)
  selectedRowKeys.value = []
}

const handleImport = () => {
  message.info('导入质控点功能')
}

const handleExport = () => {
  message.info('导出质控点功能')
}

const handleCreateNew = () => {
  router.push('/dashboard/quality-control/create')
}

const handleSearch = () => {
  message.info(`搜索: ${searchType.value} - ${searchKeyword.value}`)
}

const handleToggleEnable = (record: QualityControlPoint, checked: boolean) => {
  message.success(`质控点 ${record.id} 已${checked ? '启用' : '禁用'}`)
}

const handleView = (record: QualityControlPoint) => {
  message.info(`查看质控点: ${record.id}`)
}

const handleEdit = (record: QualityControlPoint) => {
  message.info(`编辑质控点: ${record.id}`)
}

const handleDelete = (record: QualityControlPoint) => {
  message.info(`删除质控点: ${record.id}`)
}

onMounted(() => {
  // 初始化数据加载
})
</script>

<style scoped lang="less">
.quality-control-point-management {
  padding: 24px;
  background: #f5f5f5;
  min-height: 100vh;

  .page-header {
    .page-title {
      font-size: 20px;
      font-weight: 600;
      color: #333333;
      margin: 0;
    }
  }

  .tabs-container {
    background: #ffffff;
    border-radius: 8px 8px 0 0;

    :deep(.ant-tabs) {
      margin: 0;

      .ant-tabs-nav {
        margin: 0;
        padding: 0 24px;

        .ant-tabs-tab {
          padding: 16px 24px;
          font-size: 14px;
          font-weight: 500;

          &.ant-tabs-tab-active {
            color: #1890ff;
          }
        }
      }

      .ant-tabs-content-holder {
        display: none;
      }
    }
  }

  .action-bar {
    background: #ffffff;
    padding: 16px 24px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #f0f0f0;

    .batch-actions {
      display: flex;
      gap: 8px;
      align-items: center;

      .batch-btn {
        height: 32px;
        padding: 0 16px;
        font-size: 14px;
        border-radius: 6px;

        &:disabled {
          opacity: 0.5;
        }
      }

      .action-btn {
        height: 32px;
        padding: 0 16px;
        font-size: 14px;
        border-radius: 6px;
        border-color: #d9d9d9;
        color: #666666;

        &:hover {
          border-color: #1890ff;
          color: #1890ff;
        }
      }

      .create-btn {
        height: 32px;
        padding: 0 16px;
        font-size: 14px;
        border-radius: 6px;
        background: #1890ff;
        border-color: #1890ff;
      }
    }

    .search-area {
      display: flex;
      gap: 8px;
      align-items: center;

      .search-type-select {
        width: 120px;

        :deep(.ant-select-selector) {
          height: 32px;
          border-radius: 6px;
        }
      }

      .search-input {
        width: 240px;

        :deep(.ant-input-group-wrapper) {
          .ant-input-wrapper {
            .ant-input {
              height: 32px;
              border-radius: 6px 0 0 6px;
            }
          }

          .ant-input-group-addon {
            .ant-btn {
              height: 32px;
              border-radius: 0 6px 6px 0;
            }
          }
        }
      }
    }
  }

  .table-container {
    background: #ffffff;
    border-radius: 0 0 8px 8px;
    overflow: hidden;

    .quality-point-table {
      :deep(.ant-table-thead > tr > th) {
        background: #fafafa;
        font-weight: 500;
        color: #333333;
        border-bottom: 1px solid #f0f0f0;
      }

      :deep(.ant-table-tbody > tr > td) {
        border-bottom: 1px solid #f0f0f0;
        padding: 12px 16px;
      }

      :deep(.ant-table-tbody > tr:hover > td) {
        background: #f5f5f5;
      }

      .name-cell {
        .name-text {
          font-size: 14px;
          color: #333333;
          margin-bottom: 4px;
        }

        .source-text {
          font-size: 12px;
          color: #999999;
        }
      }

      .action-buttons {
        display: flex;
        gap: 8px;

        :deep(.ant-btn-link) {
          padding: 0;
          height: auto;
          font-size: 14px;
        }
      }
    }
  }
}

/* 响应式设计 */
@media (max-width: 768px) {
  .quality-control-point-management {
    padding: 16px;

    .action-bar {
      flex-direction: column;
      gap: 16px;
      align-items: stretch;

      .batch-actions {
        flex-wrap: wrap;
      }

      .search-area {
        justify-content: stretch;

        .search-type-select {
          flex: 1;
        }

        .search-input {
          flex: 2;
        }
      }
    }
  }
}
</style>
