<!--
  文书展示组件
  以纸张样式展示病历文书内容
-->
<template>
  <div class="document-viewer">
    <!-- Empty State -->
    <div
      v-if="!store.currentDocument"
      class="empty-state"
    >
      <a-empty
        :image="Empty.PRESENTED_IMAGE_SIMPLE"
        description="请选择病例和文书"
      />
    </div>

    <!-- Document Content -->
    <div
      v-else
      class="viewer-container"
    >
      <!-- Top Toolbar -->
      <div class="toolbar">
        <div class="breadcrumb-area">
          <FileTextOutlined class="icon" />
          <span class="current-doc">{{ store.currentDocument.title }}</span>
          <span class="divider">/</span>
          <span class="case-name">{{ store.currentCase?.caseName }}</span>
        </div>

        <div class="tool-actions">
          <a-tooltip title="打印">
            <a-button
              type="text"
              size="small"
              @click="handlePrint"
            >
              <template #icon>
                <PrinterOutlined />
              </template>
            </a-button>
          </a-tooltip>
          <a-tooltip title="复制内容">
            <a-button
              type="text"
              size="small"
              @click="handleCopy"
            >
              <template #icon>
                <CopyOutlined />
              </template>
            </a-button>
          </a-tooltip>
          <a-divider type="vertical" />
          <a-tooltip title="历史版本">
            <a-button
              type="text"
              size="small"
            >
              <template #icon>
                <HistoryOutlined />
              </template>
            </a-button>
          </a-tooltip>
        </div>
      </div>

      <!-- Scroll Area (Gray Background) -->
      <div class="scroll-area">
        <!-- A4 Paper -->
        <div class="paper-sheet">
          <!-- Document Header -->
          <div class="doc-header">
            <div class="hospital-name">
              第一人民医院
            </div>
            <h1 class="doc-title">
              {{ store.currentDocument.title }}
            </h1>
            <div class="meta-row">
              <span class="label">记录时间:</span>
              <span class="value">{{ store.currentDocument.recordTime }}</span>
            </div>
          </div>

          <!-- Patient Info Grid (Compact) -->
          <div class="patient-grid">
            <div class="grid-item">
              <span class="label">姓名:</span>
              <span class="value">{{ store.currentCase?.patientInfo.name }}</span>
            </div>
            <div class="grid-item">
              <span class="label">性别:</span>
              <span class="value">{{ store.currentCase?.patientInfo.gender }}</span>
            </div>
            <div class="grid-item">
              <span class="label">年龄:</span>
              <span class="value">{{ store.currentCase?.patientInfo.age }}岁</span>
            </div>
            <div class="grid-item">
              <span class="label">科室:</span>
              <span class="value">{{
                store.currentDocument.metadata?.department ||
                  store.currentCase?.visitInfo.department
              }}</span>
            </div>
            <div class="grid-item">
              <span class="label">住院号:</span>
              <span class="value">{{ store.currentDocument.metadata?.patientId || '-' }}</span>
            </div>
            <div class="grid-item">
              <span class="label">床号:</span>
              <span class="value">{{ store.currentCase?.visitInfo.bedNumber || '-' }}</span>
            </div>
          </div>

          <a-divider style="margin: 16px 0" />

          <!-- Main Text Content -->
          <div class="doc-body">
            <pre class="content-text">{{ store.currentDocument.content }}</pre>
          </div>

          <!-- Doctor Signatures -->
          <div class="signatures">
            <div class="sig-item">
              <span class="label">医师签名:</span>
              <span class="value">李医生</span>
            </div>
            <div class="sig-item">
              <span class="label">记录时间:</span>
              <span class="value">{{ store.currentDocument.recordTime }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Bottom Actions Bar -->
      <div class="action-bar">
        <div class="left-group">
          <a-dropdown>
            <template #overlay>
              <a-menu @click="handleRuleSetChange">
                <a-menu-item key="sichuan_146">
                  <CheckOutlined v-if="store.selectedRuleSet === 'sichuan_146'" /> 四川146条
                </a-menu-item>
                <a-menu-item key="lx33">
                  <CheckOutlined v-if="store.selectedRuleSet === 'lx33'" /> 泸县33条
                </a-menu-item>
                <a-menu-item key="default">
                  <CheckOutlined v-if="store.selectedRuleSet === 'default'" /> 默认规则集
                </a-menu-item>
              </a-menu>
            </template>
            <a-button size="small">
              规则集: {{ getRuleSetLabel(store.selectedRuleSet) }}
              <DownOutlined />
            </a-button>
          </a-dropdown>
        </div>

        <div class="right-group">
          <a-button
            type="primary"
            :loading="store.isQCAnalyzing"
            class="action-btn"
            @click="handleQCAnalysis"
          >
            <template #icon>
              <ThunderboltOutlined />
            </template>
            质控分析
          </a-button>

          <a-button
            :loading="store.isFrontpageGenerating"
            class="action-btn"
            @click="handleGenerateFrontpage"
          >
            <template #icon>
              <FileAddOutlined />
            </template>
            生成病案首页
          </a-button>

          <a-button
            v-if="store.currentCase && store.currentCase.documents.length > 1"
            :loading="store.isWholeCaseQCAnalyzing"
            class="action-btn"
            @click="handleWholeCaseQC"
          >
            整病例质控
          </a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message, Empty } from 'ant-design-vue'
import type { MenuInfo } from 'ant-design-vue/es/menu/src/interface'
import { useClinicalWorkstationStore } from '@/stores/clinicalWorkstation'
import { QCRuleSetLabels } from '@/types/clinical-workstation'
import type { QCRuleSet } from '@/types/clinical-workstation'
import {
  PrinterOutlined,
  CopyOutlined,
  HistoryOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  FileAddOutlined,
  DownOutlined,
  CheckOutlined,
} from '@ant-design/icons-vue'

// ========== Store ==========
const store = useClinicalWorkstationStore()

// ========== Methods ==========

async function handleQCAnalysis() {
  if (!store.currentDocumentId) {
    message.warning('请先选择文书')
    return
  }
  await store.analyzeDocument()
}

async function handleGenerateFrontpage() {
  if (!store.currentCaseId) {
    message.warning('请先选择病例')
    return
  }
  await store.generateFrontpage()
}

function handleRuleSetChange(info: MenuInfo) {
  store.switchRuleSet(String(info.key) as QCRuleSet)
}

async function handleWholeCaseQC() {
  if (!store.currentCaseId) {
    message.warning('请先选择病例')
    return
  }
  await store.analyzeWholeCase()
}

function handlePrint() {
  window.print()
}

async function handleCopy() {
  if (!store.currentDocument) return
  try {
    await navigator.clipboard.writeText(store.currentDocument.content)
    message.success('复制成功')
  } catch (error) {
    message.error('复制失败')
  }
}

function getRuleSetLabel(ruleSet: QCRuleSet): string {
  return QCRuleSetLabels[ruleSet] || ruleSet
}
</script>

<style scoped lang="less">
.document-viewer {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f0f2f5;

  .empty-state {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .viewer-container {
    height: 100%;
    display: flex;
    flex-direction: column;

    // Toolbar
    .toolbar {
      height: 48px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      background: white;
      border-bottom: 1px solid #e8e8e8;
      flex-shrink: 0;

      .breadcrumb-area {
        display: flex;
        align-items: center;
        font-size: 14px;

        .icon {
          color: #1890ff;
          margin-right: 8px;
        }
        .current-doc {
          font-weight: 500;
          color: #262626;
        }
        .divider {
          margin: 0 8px;
          color: #bfbfbf;
        }
        .case-name {
          color: #8c8c8c;
        }
      }
    }

    // Scroll Area
    .scroll-area {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      justify-content: center;

      &::-webkit-scrollbar {
        width: 8px;
      }
      &::-webkit-scrollbar-thumb {
        background: #d9d9d9;
        border-radius: 4px;
      }

      .paper-sheet {
        width: 794px; // A4 width at 96 DPI (approx)
        min-height: 1123px; // A4 height
        background: white;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        padding: 48px;
        display: flex;
        flex-direction: column;

        .doc-header {
          text-align: center;
          margin-bottom: 24px;

          .hospital-name {
            font-size: 14px;
            color: #8c8c8c;
            margin-bottom: 8px;
          }

          .doc-title {
            font-size: 24px;
            font-weight: bold;
            color: #262626;
            margin-bottom: 16px;
          }

          .meta-row {
            font-size: 12px;
            color: #8c8c8c;
            text-align: right;
          }
        }

        .patient-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 8px 16px;

          .grid-item {
            display: flex;
            font-size: 12px;
            .label {
              color: #8c8c8c;
              width: 50px;
            }
            .value {
              color: #262626;
              font-weight: 500;
            }
          }
        }

        .doc-body {
          flex: 1;

          .content-text {
            font-family:
              'SimSun', 'Songti SC', serif; // Use serif for more formal medical record look? Or YaHei.
            // Let's stick to sans-serif for screen readability but serif for "print" feel?
            // User screenshot had clean sans-serif.
            font-family: 'Microsoft YaHei', sans-serif;
            font-size: 15px;
            line-height: 1.8;
            color: #262626;
            white-space: pre-wrap;
            word-wrap: break-word;
          }
        }

        .signatures {
          margin-top: 48px;
          display: flex;
          justify-content: flex-end;
          gap: 32px;

          .sig-item {
            display: flex;
            gap: 8px;
            font-size: 14px;
            .label {
              color: #8c8c8c;
            }
            .value {
              border-bottom: 1px solid #262626;
              padding: 0 8px;
              min-width: 80px;
              text-align: center;
            }
          }
        }
      }
    }

    // Action Bar
    .action-bar {
      height: 56px;
      background: white;
      border-top: 1px solid #e8e8e8;
      padding: 0 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-shrink: 0;
      z-index: 10;

      .right-group {
        display: flex;
        gap: 12px;

        .action-btn {
          min-width: 90px;
        }
      }
    }
  }
}

@media print {
  .toolbar,
  .action-bar {
    display: none;
  }
  .document-viewer {
    background: white;
  }
  .scroll-area {
    padding: 0;
    overflow: visible;
  }
  .paper-sheet {
    box-shadow: none;
    width: 100%;
    min-height: auto;
  }
}
</style>
