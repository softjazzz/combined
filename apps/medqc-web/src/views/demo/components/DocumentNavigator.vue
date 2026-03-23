<!--
  文书导航组件
  以树形菜单展示当前病例的所有文书
-->
<template>
  <div class="document-navigator">
    <!-- 头部标题 -->
    <div class="navigator-header">
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
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <span>住院文书</span>
    </div>

    <!-- 菜单 -->
    <a-menu
      v-model:selected-keys="selectedKeys"
      v-model:open-keys="openKeys"
      mode="inline"
      class="document-menu"
      @select="handleMenuSelect"
    >
      <!-- 病案首页 -->
      <a-menu-item
        key="frontpage"
        @click="handleFrontpageClick"
      >
        <template #icon>
          <FileTextOutlined />
        </template>
        病案首页
      </a-menu-item>

      <a-menu-item
        key="frontpage-medical"
        disabled
      >
        <template #icon>
          <FileOutlined />
        </template>
        病案首页（病案科）
      </a-menu-item>

      <!-- 病历文书分组 -->
      <a-sub-menu
        key="documents"
        title="病历文书"
      >
        <template #icon>
          <FolderOpenOutlined />
        </template>

        <!-- 动态文书列表 -->
        <a-menu-item
          v-for="doc in sortedDocuments"
          :key="doc.documentId"
        >
          <template #icon>
            <FileTextOutlined />
          </template>
          <div class="menu-item-content">
            <span class="doc-title">{{ doc.title }}</span>
            <span class="doc-time">{{ formatTime(doc.recordTime) }}</span>
          </div>
        </a-menu-item>

        <!-- 无文书提示 -->
        <a-menu-item
          v-if="sortedDocuments.length === 0"
          key="no-docs"
          disabled
        >
          <template #icon>
            <FileUnknownOutlined />
          </template>
          暂无文书
        </a-menu-item>
      </a-sub-menu>

      <!-- 书写病历（未来功能） -->
      <a-menu-item
        key="write-record"
        disabled
      >
        <template #icon>
          <EditOutlined />
        </template>
        书写病历
      </a-menu-item>
    </a-menu>

    <!-- 底部信息：当前病例 -->
    <div
      v-if="store.currentCase"
      class="case-info-footer"
    >
      <div class="info-title">
        当前病例
      </div>
      <div class="info-content">
        <div class="info-row">
          <span class="label">患者：</span>
          <span class="value">{{ store.currentCase.patientInfo.name }}</span>
        </div>
        <div class="info-row">
          <span class="label">科室：</span>
          <span class="value">{{ store.currentCase.visitInfo.department }}</span>
        </div>
        <div class="info-row">
          <span class="label">诊断：</span>
          <span class="value text-ellipsis">{{ store.currentCase.diagnosisInfo.diseaseType }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useClinicalWorkstationStore } from '@/stores/clinicalWorkstation'
import { DocumentType } from '@/types/clinical-workstation'
import type { Document } from '@/types/clinical-workstation'
import {
  FileTextOutlined,
  FileOutlined,
  FolderOpenOutlined,
  FileUnknownOutlined,
  EditOutlined
} from '@ant-design/icons-vue'

// ========== Store ==========
const store = useClinicalWorkstationStore()

// ========== State ==========
const selectedKeys = ref<string[]>([])
const openKeys = ref<string[]>(['documents']) // 默认展开病历文书

// ========== Computed ==========

/**
 * 排序后的文书列表（按类型和时间排序）
 */
const sortedDocuments = computed(() => {
  if (!store.currentCase) return []

  const docs = [...store.currentCase.documents]

  // 定义文书类型的优先级
  const typeOrder: Record<DocumentType, number> = {
    [DocumentType.ADMISSION]: 1,
    [DocumentType.INOUT_24H]: 2,
    [DocumentType.FIRST_COURSE]: 3,
    [DocumentType.DAILY_COURSE]: 4,
    [DocumentType.SURGERY_APPLY]: 5,
    [DocumentType.PRE_OP_DISCUSSION]: 6,
    [DocumentType.PRE_OP_SUMMARY]: 7,
    [DocumentType.SURGERY_RECORD]: 8,
    [DocumentType.SAFETY_CHECK]: 9,
    [DocumentType.ANESTHESIA]: 10,
    [DocumentType.POST_OP_COURSE]: 11,
    [DocumentType.NURSING]: 12,
    [DocumentType.CONSULTATION]: 13,
    [DocumentType.DISCUSSION]: 14,
    [DocumentType.ROUNDS]: 15,
    [DocumentType.RESCUE]: 16,
    [DocumentType.DISCHARGE]: 17,
    [DocumentType.OTHER]: 99
  }

  return docs.sort((a, b) => {
    // 先按类型优先级排序
    const orderDiff = (typeOrder[a.documentType] || 99) - (typeOrder[b.documentType] || 99)
    if (orderDiff !== 0) return orderDiff

    // 同类型按时间排序
    return new Date(a.recordTime).getTime() - new Date(b.recordTime).getTime()
  })
})

// ========== Watchers ==========

/**
 * 监听当前选中的文书，更新菜单选中状态
 */
watch(
  () => store.currentDocumentId,
  (newDocId) => {
    if (newDocId) {
      selectedKeys.value = [newDocId]
    } else {
      selectedKeys.value = []
    }
  },
  { immediate: true }
)

/**
 * 监听病例切换，确保文书分组展开
 */
watch(
  () => store.currentCaseId,
  () => {
    if (!openKeys.value.includes('documents')) {
      openKeys.value.push('documents')
    }
  }
)

// ========== Methods ==========

/**
 * 菜单选择事件
 */
function handleMenuSelect({ key }: { key: string }) {
  if (key === 'frontpage' || key === 'frontpage-medical' || key === 'write-record') {
    return
  }

  // 选择文书
  store.selectDocument(key)
}

/**
 * 病案首页点击
 */
function handleFrontpageClick() {
  // 切换到病案首页Tab并生成
  store.activeCdssTab = 'frontpage'

  // 如果还没有生成过病案首页，自动生成
  if (!store.frontpageDraft && !store.isFrontpageGenerating) {
    store.generateFrontpage()
  }
}

/**
 * 格式化时间
 */
function formatTime(timeStr: string): string {
  try {
    // 支持多种时间格式
    if (timeStr.includes('年')) {
      // 中文格式：2025年10月11日 10:30
      return timeStr.split(' ')[1] || timeStr
    } else {
      // ISO格式或其他格式
      const date = new Date(timeStr)
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      return `${hours}:${minutes}`
    }
  } catch {
    return timeStr
  }
}
</script>

<style scoped lang="less">
.document-navigator {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: white;

  .navigator-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-bottom: 1px solid #e8e8e8;
    font-weight: 500;
    font-size: 14px;
    color: #262626;

    .icon {
      width: 18px;
      height: 18px;
      color: #1890ff;
    }
  }

  .document-menu {
    flex: 1;
    overflow-y: auto;
    border-right: none;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-thumb {
      background: #d9d9d9;
      border-radius: 2px;
    }

    .menu-item-content {
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;

      .doc-title {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .doc-time {
        margin-left: 8px;
        font-size: 11px;
        color: #bfbfbf;
        flex-shrink: 0;
      }
    }

    :deep(.ant-menu-item) {
      font-size: 13px;
    }

    :deep(.ant-menu-submenu-title) {
      font-size: 13px;
    }

    :deep(.ant-menu-item-selected) {
      background-color: #e6f7ff;

      &::after {
        border-right-color: #1890ff;
      }
    }
  }

  .case-info-footer {
    padding: 12px 16px;
    border-top: 1px solid #e8e8e8;
    background: #fafafa;

    .info-title {
      font-size: 12px;
      font-weight: 500;
      color: #8c8c8c;
      margin-bottom: 8px;
    }

    .info-content {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .info-row {
        display: flex;
        font-size: 12px;

        .label {
          color: #8c8c8c;
          margin-right: 4px;
          flex-shrink: 0;
        }

        .value {
          color: #262626;
          flex: 1;

          &.text-ellipsis {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
        }
      }
    }
  }
}
</style>
