<template>
  <section class="batch-shell">
    <div class="batch-shell-head">
      <div>
        <p class="batch-shell-eyebrow">
          批量任务
        </p>
        <h3 class="batch-shell-title">
          全病历质控任务
        </h3>
      </div>
      <div class="batch-shell-right">
        <div class="batch-shell-meta">
          <span class="batch-shell-count">{{ total }}</span>
          <span class="batch-shell-label">任务数量</span>
        </div>
        <a-button
          type="primary"
          class="batch-primary-btn"
          @click="emit('openBatchLaunch')"
        >
          发起批量质控
        </a-button>
      </div>
    </div>

    <div class="batch-filters">
      <a-input
        :value="query.keyword"
        allow-clear
        placeholder="搜索规则名称/编码/任务ID"
        class="batch-filter-input"
        @update:value="(value) => updateQuery('keyword', value)"
        @press-enter="emit('searchBatchJobs')"
      >
        <template #prefix>
          <SearchOutlined />
        </template>
      </a-input>
      <a-select
        :value="query.status"
        allow-clear
        placeholder="任务状态"
        :options="statusOptions"
        class="batch-filter-select"
        @update:value="(value) => updateQuery('status', value)"
        @change="emit('searchBatchJobs')"
      />
      <a-select
        :value="query.scope"
        allow-clear
        placeholder="病历范围"
        :options="scopeOptions"
        class="batch-filter-select"
        @update:value="(value) => updateQuery('scope', value)"
        @change="emit('searchBatchJobs')"
      />
      <a-select
        :value="query.executor_type"
        allow-clear
        placeholder="执行器"
        :options="executorOptions"
        class="batch-filter-select"
        @update:value="(value) => updateQuery('executor_type', value)"
        @change="emit('searchBatchJobs')"
      />
      <a-select
        :value="query.cache_hit"
        allow-clear
        placeholder="缓存命中"
        :options="cacheHitOptions"
        class="batch-filter-select"
        @update:value="(value) => updateQuery('cache_hit', value)"
        @change="emit('searchBatchJobs')"
      />
    </div>

    <ProStandardTable
      class="batch-table"
      :columns="columns"
      :data-source="displayBatchJobs"
      :loading="loading"
      :pagination="pagination"
      row-key="id"
      :scroll="{ x: 980 }"
      :locale="{ emptyText: '暂无批量任务' }"
      @change="emit('tableChange', $event)"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'rule'">
          <div class="batch-rule">
            <div class="batch-rule-name">
              {{ record.rule_name || record.rule_code }}
            </div>
            <div class="batch-rule-meta">
              规则数：{{ record.rule_count || 0 }}
            </div>
          </div>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :class="getBatchJobStatusTagClass(record.status)">
            {{
              record.status === 'failed' && record.summary?.execution_status === 'partial_failed'
                ? '部分执行失败'
                : getBatchJobStatusText(record.status)
            }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'execution'">
          <div class="batch-execution">
            <div class="batch-execution-row">
              <span>Program {{ record.summary?.executor_breakdown?.program || 0 }}</span>
              <span>LLM {{ record.summary?.executor_breakdown?.llm || 0 }}</span>
            </div>
            <div class="batch-execution-row batch-execution-cache">
              <span>命中 {{ record.summary?.cache_breakdown?.hit || 0 }}</span>
              <span>未命中 {{ record.summary?.cache_breakdown?.miss || 0 }}</span>
            </div>
          </div>
        </template>
        <template v-else-if="column.key === 'created_at'">
          <span class="text-slate-500">{{ formatDateTime(record.created_at) }}</span>
        </template>
        <template v-else-if="column.key === 'actions'">
          <div class="batch-actions">
            <a-button
              size="small"
              @click="emit('openBatchJobDrawer', record as SichuanBatchJob)"
            >
              查看
            </a-button>
            <a-button
              v-if="['queued', 'running'].includes(record.status)"
              size="small"
              danger
              :loading="cancellingBatchJobId === record.id"
              @click="emit('cancelBatchJob', record.id)"
            >
              停止
            </a-button>
            <a-button
              v-else-if="['failed', 'completed', 'canceled'].includes(record.status)"
              size="small"
              :loading="retryingBatchJobId === record.id"
              @click="emit('retryBatchJob', record.id)"
            >
              {{
                record.status === 'failed' && record.summary?.execution_status === 'partial_failed'
                  ? '重试失败项'
                  : '重试'
              }}
            </a-button>
          </div>
        </template>
      </template>
    </ProStandardTable>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { SearchOutlined } from '@ant-design/icons-vue'
import ProStandardTable from '@/components/pro/ProStandardTable.vue'
import type { TablePaginationConfig } from 'ant-design-vue'
import type { SichuanBatchJob } from '@/views/workstation-v4/semantic-rules/types'
import {
  getBatchJobStatusTagClass,
  getBatchJobStatusText,
} from '@/views/rules/utils/customQcWorkspacePresentation'

const props = defineProps<{
  loading: boolean
  batchJobs: SichuanBatchJob[]
  total: number
  pagination: TablePaginationConfig
  query: {
    keyword: string
    status: string | undefined
    scope: string | undefined
    executor_type?: 'program' | 'llm'
    cache_hit?: 'hit' | 'miss'
  }
  statusOptions: Array<{ label: string; value: string }>
  scopeOptions: Array<{ label: string; value: string }>
  cancellingBatchJobId: string
  retryingBatchJobId: string
  formatDateTime: (value?: string | Date | null) => string
}>()

const emit = defineEmits<{
  openBatchLaunch: []
  searchBatchJobs: []
  tableChange: [pagination: TablePaginationConfig]
  openBatchJobDrawer: [job: SichuanBatchJob]
  cancelBatchJob: [jobId: string]
  retryBatchJob: [jobId: string]
  updateQuery: [value: typeof props.query]
}>()

const columns = computed(() => [
  { title: '规则', key: 'rule', width: 320 },
  { title: '范围', dataIndex: 'scope', key: 'scope', width: 110 },
  { title: '执行统计', key: 'execution', width: 220 },
  { title: '状态', key: 'status', width: 110 },
  { title: '创建时间', key: 'created_at', width: 180 },
  { title: '操作', key: 'actions', width: 160, fixed: 'right' as const },
])

const executorOptions = [
  { label: 'Program', value: 'program' },
  { label: 'LLM', value: 'llm' },
]

const cacheHitOptions = [
  { label: '已命中', value: 'hit' },
  { label: '未命中', value: 'miss' },
]

const displayBatchJobs = computed(() => props.batchJobs)

function updateQuery(
  field: 'keyword' | 'status' | 'scope' | 'executor_type' | 'cache_hit',
  value: unknown,
) {
  if (field === 'keyword') {
    emit('updateQuery', {
      ...props.query,
      keyword: String(value || ''),
    })
    return
  }
  emit('updateQuery', {
    ...props.query,
    [field]: value ? String(value) : undefined,
  })
}
</script>

<style scoped>
.batch-shell {
  margin-top: 16px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  background: #ffffff;
  box-shadow: 0 14px 34px rgba(148, 163, 184, 0.12);
  overflow: hidden;
}

.batch-shell-head {
  border-bottom: 1px solid rgba(226, 232, 240, 0.8);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

.batch-shell-eyebrow {
  margin: 0;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.batch-shell-title {
  margin: 2px 0 0;
  font-size: 17px;
  font-weight: 600;
  color: #0f2747;
  line-height: 1.2;
}

.batch-shell-right {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.batch-shell-meta {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  border-radius: 999px;
  border: 1px solid #dbe7f5;
  background: #f8fbff;
  padding: 8px 12px;
}

.batch-shell-count {
  font-size: 20px;
  line-height: 1;
  color: #0f2747;
  font-weight: 700;
}

.batch-shell-label {
  color: #6b7280;
  font-size: 11px;
}

.batch-primary-btn {
  height: 30px;
  border-radius: 10px;
  font-size: 12px;
}

.batch-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px 20px 0;
}

.batch-filter-input {
  width: 280px;
  min-width: 220px;
  height: 30px;
  border-radius: 10px;
}

.batch-filter-select {
  width: 160px;
}

.batch-table {
  padding: 12px 16px 16px;
}

.batch-rule {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.batch-rule-name {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.batch-rule-meta {
  font-size: 11px;
  color: #64748b;
}

.batch-execution {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #334155;
}

.batch-execution-row {
  display: flex;
  gap: 12px;
}

.batch-execution-cache {
  color: #64748b;
}

.batch-actions {
  display: inline-flex;
  gap: 6px;
}

@media (max-width: 1023px) {
  .batch-shell-head {
    flex-direction: column;
    align-items: flex-start;
  }
  .batch-shell-right {
    width: 100%;
    justify-content: space-between;
  }
  .batch-filter-input,
  .batch-filter-select {
    width: 100%;
  }
}
</style>
