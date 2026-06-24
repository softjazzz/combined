<!--
  病例选择器组件
  支持预置病例和自定义病例的选择、筛选
-->
<template>
  <div class="case-selector">
    <!-- 头部：标题和新建按钮 -->
    <div class="selector-header">
      <div class="header-title">
        <svg
          class="icon"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
          />
        </svg>
        <span>病例选择</span>
      </div>
      <a-button
        type="primary"
        size="small"
        @click="handleNewCase"
      >
        <template #icon>
          <PlusOutlined />
        </template>
        新建
      </a-button>
    </div>

    <!-- Tab切换：预置/自定义 -->
    <a-tabs
      v-model:active-key="activeTab"
      size="small"
      class="case-tabs"
    >
      <a-tab-pane
        key="preset"
        tab="预置病例"
      >
        <!-- 筛选条件 -->
        <div class="filter-section">
          <a-select
            v-model:value="store.filter.department"
            size="small"
            placeholder="科室"
            style="width: 100%"
            @change="handleFilterChange"
          >
            <a-select-option value="全部">
              全部科室
            </a-select-option>
            <a-select-option value="心内科">
              心内科
            </a-select-option>
            <a-select-option value="普外科">
              普外科
            </a-select-option>
            <a-select-option value="呼吸内科">
              呼吸内科
            </a-select-option>
            <a-select-option value="ICU">
              ICU
            </a-select-option>
            <a-select-option value="神经内科">
              神经内科
            </a-select-option>
          </a-select>

          <a-select
            v-model:value="complexityFilter"
            size="small"
            placeholder="复杂度"
            style="width: 100%; margin-top: 8px"
            @change="handleFilterChange"
          >
            <a-select-option :value="undefined">
              全部复杂度
            </a-select-option>
            <a-select-option value="low">
              简单
            </a-select-option>
            <a-select-option value="medium">
              中等
            </a-select-option>
            <a-select-option value="high">
              复杂
            </a-select-option>
          </a-select>

          <a-input
            v-model:value="store.filter.keyword"
            size="small"
            placeholder="搜索病例..."
            style="margin-top: 8px"
            @input="handleFilterChange"
          >
            <template #prefix>
              <SearchOutlined />
            </template>
          </a-input>
        </div>

        <!-- 病例列表 -->
        <div class="cases-list">
          <div
            v-for="caseItem in displayPresetCases"
            :key="caseItem.caseId"
            class="case-card"
            :class="{ active: store.currentCaseId === caseItem.caseId }"
            @click="handleSelectCase(caseItem.caseId)"
          >
            <div class="case-header">
              <div class="case-name">
                {{ caseItem.caseName }}
              </div>
              <a-tag
                :color="getComplexityColor(caseItem.diagnosisInfo.complexity)"
                size="small"
              >
                {{ CaseComplexityLabels[caseItem.diagnosisInfo.complexity] }}
              </a-tag>
            </div>
            <div class="case-info">
              <div class="info-item">
                <UserOutlined class="info-icon" />
                {{ caseItem.patientInfo.name }} · {{ caseItem.patientInfo.age }}岁 · {{ caseItem.patientInfo.gender }}
              </div>
              <div class="info-item">
                <MedicineBoxOutlined class="info-icon" />
                {{ caseItem.visitInfo.department }}
              </div>
              <div class="info-item">
                <FileTextOutlined class="info-icon" />
                {{ caseItem.diagnosisInfo.diseaseType }}
              </div>
              <div class="info-item">
                <FolderOutlined class="info-icon" />
                {{ caseItem.documents.length }} 份文书
              </div>
            </div>
          </div>

          <a-empty
            v-if="displayPresetCases.length === 0"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
            description="暂无匹配的病例"
          />
        </div>
      </a-tab-pane>

      <a-tab-pane
        key="custom"
        tab="自定义病例"
      >
        <div class="cases-list">
          <div
            v-for="caseItem in store.customCases"
            :key="caseItem.caseId"
            class="case-card custom"
            :class="{ active: store.currentCaseId === caseItem.caseId }"
            @click="handleSelectCase(caseItem.caseId)"
          >
            <div class="case-header">
              <div class="case-name">
                {{ caseItem.caseName }}
              </div>
              <a-button
                type="text"
                size="small"
                danger
                @click.stop="handleDeleteCase(caseItem.caseId)"
              >
                <template #icon>
                  <DeleteOutlined />
                </template>
              </a-button>
            </div>
            <div class="case-info">
              <div class="info-item">
                <UserOutlined class="info-icon" />
                {{ caseItem.patientInfo.name }} · {{ caseItem.patientInfo.age }}岁
              </div>
              <div class="info-item">
                <MedicineBoxOutlined class="info-icon" />
                {{ caseItem.visitInfo.department }}
              </div>
              <div class="info-item">
                <FolderOutlined class="info-icon" />
                {{ caseItem.documents.length }} 份文书
              </div>
            </div>
          </div>

          <a-empty
            v-if="store.customCases.length === 0"
            :image="Empty.PRESENTED_IMAGE_SIMPLE"
            description="暂无自定义病例"
          >
            <a-button
              type="primary"
              @click="handleNewCase"
            >
              <template #icon>
                <PlusOutlined />
              </template>
              新建病例
            </a-button>
          </a-empty>
        </div>

        <!-- 清空按钮 -->
        <div
          v-if="store.customCases.length > 0"
          class="custom-actions"
        >
          <a-button
            size="small"
            danger
            block
            @click="handleClearAll"
          >
            <template #icon>
              <DeleteOutlined />
            </template>
            清空所有自定义病例
          </a-button>
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- 自定义病例对话框 -->
    <CustomCaseDialog
      v-model:visible="customDialogVisible"
      @submit="handleCustomCaseSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Modal, Empty } from 'ant-design-vue'
import { useClinicalWorkstationStore } from '@/stores/clinicalWorkstation'
import { CaseComplexityLabels } from '@/types/clinical-workstation'
import type { Case, CaseComplexity } from '@/types/clinical-workstation'
import CustomCaseDialog from './CustomCaseDialog.vue'
import {
  PlusOutlined,
  SearchOutlined,
  UserOutlined,
  MedicineBoxOutlined,
  FileTextOutlined,
  FolderOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'

// ========== Store ==========
const store = useClinicalWorkstationStore()

// ========== State ==========
const activeTab = ref<'preset' | 'custom'>('preset')
const complexityFilter = ref<CaseComplexity | undefined>(undefined)
const customDialogVisible = ref(false)

// ========== Computed ==========

/**
 * 显示的预置病例（经过筛选）
 */
const displayPresetCases = computed(() => {
  let cases = store.presetCases

  // 按科室筛选
  if (store.filter.department && store.filter.department !== '全部') {
    cases = cases.filter(c => c.visitInfo.department === store.filter.department)
  }

  // 按复杂度筛选
  if (complexityFilter.value) {
    cases = cases.filter(c => c.diagnosisInfo.complexity === complexityFilter.value)
  }

  // 关键字搜索
  if (store.filter.keyword) {
    const keyword = store.filter.keyword.toLowerCase()
    cases = cases.filter(c =>
      c.caseName.toLowerCase().includes(keyword) ||
      c.diagnosisInfo.diseaseType.toLowerCase().includes(keyword) ||
      c.visitInfo.department.toLowerCase().includes(keyword) ||
      c.patientInfo.name.toLowerCase().includes(keyword)
    )
  }

  return cases
})

// ========== Methods ==========

/**
 * 选择病例
 */
function handleSelectCase(caseId: string) {
  store.selectCase(caseId)
}

/**
 * 新建自定义病例
 */
function handleNewCase() {
  customDialogVisible.value = true
}

/**
 * 自定义病例提交
 */
function handleCustomCaseSubmit(customCase: Case) {
  store.addCustomCase(customCase)
  customDialogVisible.value = false
  activeTab.value = 'custom'
}

/**
 * 删除自定义病例
 */
function handleDeleteCase(caseId: string) {
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除这个自定义病例吗？',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => {
      store.deleteCustomCase(caseId)
    }
  })
}

/**
 * 清空所有自定义病例
 */
function handleClearAll() {
  Modal.confirm({
    title: '确认清空',
    content: '确定要清空所有自定义病例吗？此操作不可恢复。',
    okText: '清空',
    okType: 'danger',
    cancelText: '取消',
    onOk: () => {
      store.clearAllCustomCases()
    }
  })
}

/**
 * 筛选条件变更
 */
function handleFilterChange() {
  store.updateFilter({
    complexity: complexityFilter.value
  })
}

/**
 * 获取复杂度颜色
 */
function getComplexityColor(complexity: CaseComplexity): string {
  const colorMap: Record<CaseComplexity, string> = {
    low: 'green',
    medium: 'orange',
    high: 'red'
  }
  return colorMap[complexity]
}
</script>

<style scoped lang="less">
.case-selector {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;

  .selector-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid #e8e8e8;

    .header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
      font-size: 14px;
      color: #262626;

      .icon {
        width: 18px;
        height: 18px;
        color: #1890ff;
      }
    }
  }

  .case-tabs {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;

    :deep(.ant-tabs-nav) {
      padding: 0 16px;
      margin-bottom: 0;
    }

    :deep(.ant-tabs-content-holder) {
      flex: 1;
      overflow: hidden;
    }

    :deep(.ant-tabs-content) {
      height: 100%;
    }

    :deep(.ant-tabs-tabpane) {
      height: 100%;
      display: flex;
      flex-direction: column;
    }
  }

  .filter-section {
    padding: 12px 16px;
    border-bottom: 1px solid #f0f0f0;
  }

  .cases-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #d9d9d9;
      border-radius: 2px;
    }

    .case-card {
      padding: 12px;
      margin-bottom: 8px;
      border: 1px solid #e8e8e8;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.2s;

      &:hover {
        border-color: #1890ff;
        box-shadow: 0 2px 8px rgba(24, 144, 255, 0.1);
      }

      &.active {
        border-color: #1890ff;
        background: #e6f7ff;
      }

      &.custom {
        border-left: 3px solid #52c41a;
      }

      .case-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 8px;

        .case-name {
          flex: 1;
          font-weight: 500;
          font-size: 13px;
          color: #262626;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }

      .case-info {
        display: flex;
        flex-direction: column;
        gap: 4px;

        .info-item {
          display: flex;
          align-items: center;
          font-size: 12px;
          color: #8c8c8c;

          .info-icon {
            margin-right: 6px;
            color: #bfbfbf;
          }
        }
      }
    }
  }

  .custom-actions {
    padding: 12px 16px;
    border-top: 1px solid #f0f0f0;
  }
}
</style>
