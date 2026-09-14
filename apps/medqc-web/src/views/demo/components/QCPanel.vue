<!--
  质控面板组件
  右侧CDSS面板，展示质控结果和病案首页
-->
<template>
  <div class="qc-panel">
    <!-- CDSS Header -->
    <div class="panel-header">
      <div class="header-title">
        <SafetyCertificateOutlined class="icon" />
        <span>灵医智慧CDSS</span>
      </div>
    </div>

    <div class="panel-body">
      <!-- Left Sidebar Tabs -->
      <div class="tab-sidebar">
        <div
          class="tab-item"
          :class="{ active: store.activeCdssTab === 'qc' }"
          @click="store.activeCdssTab = 'qc'"
        >
          <div class="tab-icon">
            <SafetyCertificateOutlined />
          </div>
          <span class="tab-text">病历质控</span>
        </div>

        <div
          class="tab-item"
          :class="{ active: store.activeCdssTab === 'frontpage' }"
          @click="store.activeCdssTab = 'frontpage'"
        >
          <div class="tab-icon">
            <FileTextOutlined />
          </div>
          <span class="tab-text">病案首页</span>
        </div>
      </div>

      <!-- Right Content Area -->
      <div class="content-area">
        <!-- Tab 1: QC Results -->
        <div
          v-if="store.activeCdssTab === 'qc'"
          class="tab-pane fade-in"
        >
          <!-- Empty State -->
          <div
            v-if="!store.currentQCResult"
            class="empty-state"
          >
            <a-empty
              :image="Empty.PRESENTED_IMAGE_SIMPLE"
              description="暂无质控结果"
            >
              <template #description>
                <span class="empty-text">请选择文书并点击"质控分析"</span>
              </template>
            </a-empty>
          </div>

          <!-- QC Content -->
          <div
            v-else
            class="qc-content scrollable"
          >
            <!-- Summary Card -->
            <div class="section-card summary-section">
              <div class="card-header">
                <span class="title">质控结果概览</span>
                <a-tag color="cyan">
                  {{ QCRuleSetLabels[store.currentQCResult.ruleSet] }}
                </a-tag>
              </div>
              
              <div class="grade-row">
                <div
                  class="grade-badge"
                  :class="`grade-${store.currentQCResult.evaluationSummary.overallGrade}`"
                >
                  {{ store.currentQCResult.evaluationSummary.overallGrade }}
                </div>
                <div class="score-info">
                  <div class="score-row">
                    <span class="label">合规率</span>
                    <span class="value">{{ store.currentQCResult.evaluationSummary.complianceRate.toFixed(1) }}%</span>
                  </div>
                  <a-progress
                    :percent="store.currentQCResult.evaluationSummary.complianceRate"
                    :stroke-color="getComplianceColor(store.currentQCResult.evaluationSummary.complianceRate)"
                    :show-info="false"
                    size="small"
                  />
                </div>
              </div>

              <div class="stats-grid">
                <div class="stat-item">
                  <span class="label">总规则</span>
                  <span class="value">{{ store.currentQCResult.evaluationSummary.totalRules }}</span>
                </div>
                <div class="stat-item">
                  <span class="label">合规</span>
                  <span class="value">{{ store.currentQCResult.evaluationSummary.compliantRules }}</span>
                </div>
                <div class="stat-item">
                  <span class="label">严重</span>
                  <span class="value red">{{ store.currentQCResult.evaluationSummary.criticalViolations }}</span>
                </div>
                <div class="stat-item">
                  <span class="label">耗时</span>
                  <span class="value">{{ store.currentQCResult.performanceMetrics.processingTime.toFixed(2) }}s</span>
                </div>
              </div>
            </div>

            <!-- Violations List -->
            <div class="section-card violations-section">
              <div class="card-header">
                <span class="title">问题详情</span>
                <a-tag :color="store.currentViolations.length > 0 ? 'orange' : 'green'">
                  {{ store.currentViolations.length }} 项
                </a-tag>
              </div>

              <div
                v-if="store.currentViolations.length === 0"
                class="no-violations"
              >
                <CheckCircleOutlined class="success-icon" />
                <p>质控通过，未发现问题</p>
              </div>

              <div
                v-else
                class="violations-list"
              >
                <div
                  v-for="(violation, index) in store.currentViolations"
                  :key="`${violation.ruleId}-${index}`"
                  class="violation-item"
                >
                  <div class="violation-header">
                    <a-tag
                      :color="ViolationSeverityColors[violation.severity]"
                      class="severity-tag"
                    >
                      {{ ViolationSeverityLabels[violation.severity] }}
                    </a-tag>
                    <span class="rule-name">{{ violation.ruleName }}</span>
                  </div>
                  <div class="violation-desc">
                    {{ violation.description }}
                  </div>
                  <div
                    v-if="violation.suggestion"
                    class="violation-suggestion"
                  >
                    <BulbOutlined class="icon" />
                    <span>{{ violation.suggestion }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="panel-footer">
              <a-button
                block
                @click="handleExportReport"
              >
                <template #icon>
                  <ExportOutlined />
                </template>
                导出质控报告
              </a-button>
            </div>
          </div>
        </div>

        <!-- Tab 2: Frontpage -->
        <div
          v-else-if="store.activeCdssTab === 'frontpage'"
          class="tab-pane fade-in"
        >
          <!-- Empty State -->
          <div
            v-if="!store.frontpageDraft"
            class="empty-state"
          >
            <a-empty
              :image="Empty.PRESENTED_IMAGE_SIMPLE"
              description="暂无病案首页数据"
            >
              <a-button
                type="primary"
                :loading="store.isFrontpageGenerating"
                @click="handleGenerateFrontpage"
              >
                <template #icon>
                  <FileAddOutlined />
                </template>
                {{ store.isFrontpageGenerating ? '生成中...' : '生成病案首页' }}
              </a-button>
            </a-empty>
          </div>

          <div
            v-else
            class="frontpage-content scrollable"
          >
            <div class="section-card">
              <div class="card-header">
                <span class="title">基本信息</span>
              </div>
              <div class="info-grid">
                <div class="info-item">
                  <span class="label">姓名</span>
                  <span class="value">{{ store.frontpageDraft.basicInfo.patientName }}</span>
                </div>
                <div class="info-item">
                  <span class="label">性别</span>
                  <span class="value">{{ store.frontpageDraft.basicInfo.genderText || store.frontpageDraft.basicInfo.gender }}</span>
                </div>
                <div class="info-item">
                  <span class="label">年龄</span>
                  <span class="value">{{ store.frontpageDraft.basicInfo.ageYears || '-' }}岁</span>
                </div>
                <div class="info-item">
                  <span class="label">出生日期</span>
                  <span class="value">{{ store.frontpageDraft.basicInfo.birthDate || '-' }}</span>
                </div>
              </div>
            </div>

            <div class="section-card">
              <div class="card-header">
                <span class="title">住院信息</span>
              </div>
              <div class="info-list">
                <div class="list-row">
                  <span class="label">入院时间</span>
                  <span class="value">{{ store.frontpageDraft.hospitalization.admissionDatetime || '-' }}</span>
                </div>
                <div class="list-row">
                  <span class="label">出院时间</span>
                  <span class="value">{{ store.frontpageDraft.hospitalization.dischargeDatetime || '-' }}</span>
                </div>
                <div class="list-row">
                  <span class="label">住院天数</span>
                  <span class="value">{{ store.frontpageDraft.hospitalization.actualHospitalDays || '-' }}天</span>
                </div>
                <div class="list-row">
                  <span class="label">入院科别</span>
                  <span class="value">{{ store.frontpageDraft.hospitalization.admissionDept || '-' }}</span>
                </div>
                <div class="list-row">
                  <span class="label">出院科别</span>
                  <span class="value">{{ store.frontpageDraft.hospitalization.dischargeDept || '-' }}</span>
                </div>
              </div>
            </div>

            <div class="section-card">
              <div class="card-header">
                <span class="title">诊断信息</span>
              </div>
              <div class="diagnosis-section">
                <div class="diag-group main">
                  <span class="label">主要诊断</span>
                  <div class="diag-value">
                    {{ store.frontpageDraft.diagnoses.dischargeMainDiagnosisText || '-' }}
                  </div>
                </div>
                <div
                  v-if="store.frontpageDraft.diagnoses.dischargeOtherDiagnosesTexts.length > 0"
                  class="diag-group"
                >
                  <span class="label">其他诊断</span>
                  <div class="diag-list">
                    <div
                      v-for="(diagnosis, index) in store.frontpageDraft.diagnoses.dischargeOtherDiagnosesTexts"
                      :key="index"
                      class="diag-item"
                    >
                      <span class="index">{{ index + 1 }}.</span>
                      <span>{{ diagnosis }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div class="panel-footer">
              <a-button
                block
                @click="handleViewFullFrontpage"
              >
                <template #icon>
                  <EyeOutlined />
                </template>
                查看完整首页
              </a-button>
              <a-button
                block
                style="margin-top: 8px"
                @click="handleGenerateFrontpage"
              >
                <template #icon>
                  <ReloadOutlined />
                </template>
                重新生成
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { message, Empty } from 'ant-design-vue'
import { useClinicalWorkstationStore } from '@/stores/clinicalWorkstation'
import {
  QCRuleSetLabels,
  ViolationSeverityLabels,
  ViolationSeverityColors
} from '@/types/clinical-workstation'
import {
  SafetyCertificateOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  BulbOutlined,
  ExportOutlined,
  FileAddOutlined,
  EyeOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue'

// ========== Store ==========
const store = useClinicalWorkstationStore()

// ========== Methods ==========

/**
 * 生成病案首页
 */
async function handleGenerateFrontpage() {
  await store.generateFrontpage()
}

/**
 * 导出质控报告
 */
function handleExportReport() {
  if (!store.currentQCResult) return

  const reportData = {
    病例: store.currentCase?.caseName,
    文书: store.currentDocument?.title,
    规则集: QCRuleSetLabels[store.currentQCResult.ruleSet],
    质控时间: store.currentQCResult.timestamp,
    总体等级: store.currentQCResult.evaluationSummary.overallGrade,
    合规率: `${store.currentQCResult.evaluationSummary.complianceRate.toFixed(1)}%`,
    总规则数: store.currentQCResult.evaluationSummary.totalRules,
    违规项数: store.currentViolations.length,
    违规详情: store.currentViolations.map(v => ({
      规则名称: v.ruleName,
      严重程度: ViolationSeverityLabels[v.severity],
      问题描述: v.description,
      改进建议: v.suggestion
    }))
  }

  const blob = new Blob([JSON.stringify(reportData, null, 2)], {
    type: 'application/json'
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `质控报告_${store.currentDocument?.title}_${new Date().getTime()}.json`
  a.click()
  URL.revokeObjectURL(url)

  message.success('质控报告已导出')
}

/**
 * 查看完整病案首页
 */
function handleViewFullFrontpage() {
  message.info('完整病案首页查看功能开发中...')
}

/**
 * 获取合规率对应的颜色
 */
function getComplianceColor(rate: number): string {
  if (rate >= 90) return '#52c41a'
  if (rate >= 80) return '#2b6cf6'
  if (rate >= 70) return '#faad14'
  return '#f5222d'
}
</script>

<style scoped lang="less">
.qc-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #f5f7fa; // Light gray background for the whole panel area

  .panel-header {
    height: 48px;
    display: flex;
    align-items: center;
    padding: 0 16px;
    background: #0052CC; // Professional Medical Blue
    color: white;
    flex-shrink: 0;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    z-index: 2;

    .header-title {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 15px;
      font-weight: 600;

      .icon {
        font-size: 18px;
      }
    }
  }

  .panel-body {
    flex: 1;
    display: flex;
    overflow: hidden;

    // Vertical Tabs Sidebar
    .tab-sidebar {
      width: 64px;
      background: #ebedf0;
      display: flex;
      flex-direction: column;
      padding-top: 12px;
      gap: 12px;
      flex-shrink: 0;
      border-right: 1px solid #e0e0e0;

      .tab-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        padding: 12px 4px;
        gap: 4px;
        color: #595959;
        transition: all 0.3s ease;
        position: relative;
        margin-left: 8px; // Indent to create the fusion effect
        border-top-left-radius: 12px;
        border-bottom-left-radius: 12px;

        .tab-icon {
          font-size: 20px;
        }

        .tab-text {
          font-size: 10px;
          font-weight: 500;
        }

        &:hover {
          color: #2b6cf6;
          background: rgba(255, 255, 255, 0.5);
        }

        &.active {
          background: white; // Matches content area
          color: #0052CC;
          box-shadow: -2px 2px 4px rgba(0, 0, 0, 0.02);
          
          // Cover the right border of sidebar to fuse
          &::after {
            content: '';
            position: absolute;
            right: -2px; // Overlap border
            top: 0;
            bottom: 0;
            width: 4px;
            background: white;
          }
        }
      }
    }

    // Main Content
    .content-area {
      flex: 1;
      background: white;
      overflow: hidden;
      display: flex;
      flex-direction: column;

      .tab-pane {
        height: 100%;
        display: flex;
        flex-direction: column;
      }

      .empty-state {
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        
        .empty-text {
          color: #8c8c8c;
          font-size: 13px;
        }
      }

      .scrollable {
        flex: 1;
        overflow-y: auto;
        padding: 16px;
        
        &::-webkit-scrollbar {
          width: 6px;
        }
        &::-webkit-scrollbar-thumb {
          background: #d9d9d9;
          border-radius: 3px;
        }
      }

      // Common Card Style
      .section-card {
        border: 1px solid #f0f0f0;
        border-radius: 6px;
        padding: 12px;
        margin-bottom: 16px;
        background: #fff;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);

        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
          padding-bottom: 8px;
          border-bottom: 1px solid #f5f5f5;

          .title {
            font-weight: 600;
            font-size: 14px;
            color: #262626;
            border-left: 3px solid #0052CC;
            padding-left: 8px;
          }
        }
      }

      // QC Content Specific
      .qc-content {
        .summary-section {
          .grade-row {
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 16px;

            .grade-badge {
              width: 56px;
              height: 56px;
              border-radius: 50%;
              display: flex;
              align-items: center;
              justify-content: center;
              font-size: 24px;
              font-weight: bold;
              color: white;
              box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);

              &.grade-A { background: linear-gradient(135deg, #52c41a, #95de64); }
              &.grade-B { background: linear-gradient(135deg, #2b6cf6, #69c0ff); }
              &.grade-C { background: linear-gradient(135deg, #faad14, #ffc53d); }
              &.grade-D, &.grade-F { background: linear-gradient(135deg, #f5222d, #ff7875); }
            }

            .score-info {
              flex: 1;
              .score-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 4px;
                font-size: 13px;
                .value { font-weight: 600; color: #262626; }
              }
            }
          }

          .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;

            .stat-item {
              background: #f9fafb;
              padding: 8px;
              border-radius: 4px;
              display: flex;
              flex-direction: column;
              align-items: center;
              
              .label { font-size: 11px; color: #8c8c8c; margin-bottom: 2px; }
              .value { font-weight: 600; color: #262626; font-size: 14px; }
              .value.red { color: #f5222d; }
            }
          }
        }

        .violations-section {
          .no-violations {
            text-align: center;
            padding: 24px 0;
            color: #52c41a;
            .success-icon { font-size: 40px; margin-bottom: 8px; }
            p { font-size: 13px; color: #595959; }
          }

          .violations-list {
            display: flex;
            flex-direction: column;
            gap: 10px;

            .violation-item {
              background: #fffbfb;
              border: 1px solid #ffecec;
              border-radius: 4px;
              padding: 10px;
              transition: all 0.2s;

              &:hover {
                background: #fff5f5;
                border-color: #ffccc7;
              }

              .violation-header {
                display: flex;
                align-items: flex-start;
                gap: 8px;
                margin-bottom: 6px;

                .severity-tag {
                  margin: 0;
                  font-size: 11px;
                  padding: 0 4px;
                  line-height: 18px;
                }

                .rule-name {
                  font-weight: 500;
                  font-size: 13px;
                  color: #262626;
                  line-height: 1.4;
                }
              }

              .violation-desc {
                font-size: 12px;
                color: #595959;
                margin-bottom: 8px;
                line-height: 1.5;
                padding-left: 2px;
              }

              .violation-suggestion {
                background: #e6f7ff;
                padding: 6px 8px;
                border-radius: 4px;
                display: flex;
                gap: 6px;
                font-size: 12px;
                color: #0052CC;
                
                .icon { margin-top: 2px; flex-shrink: 0; }
              }
            }
          }
        }
      }

      // Frontpage Content Specific
      .frontpage-content {
        .info-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          
          .info-item {
            display: flex;
            flex-direction: column;
            .label { font-size: 11px; color: #8c8c8c; }
            .value { font-size: 13px; color: #262626; font-weight: 500; }
          }
        }

        .info-list {
          display: flex;
          flex-direction: column;
          gap: 10px;

          .list-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed #f0f0f0;
            padding-bottom: 6px;
            
            &:last-child { border-bottom: none; padding-bottom: 0; }
            
            .label { font-size: 12px; color: #8c8c8c; }
            .value { font-size: 13px; color: #262626; }
          }
        }

        .diagnosis-section {
          .diag-group {
            margin-bottom: 12px;
            .label { display: block; font-size: 11px; color: #8c8c8c; margin-bottom: 4px; }
            .diag-value { font-size: 13px; color: #262626; font-weight: 500; padding: 4px 8px; background: #f9f9f9; border-radius: 4px; }
            
            .diag-list {
              display: flex;
              flex-direction: column;
              gap: 4px;
              .diag-item {
                display: flex;
                gap: 6px;
                font-size: 13px;
                color: #262626;
                padding: 4px 8px;
                background: #f9f9f9;
                border-radius: 4px;
                .index { color: #8c8c8c; width: 20px; }
              }
            }
          }
        }
      }

      .panel-footer {
        margin-top: auto;
        padding-top: 16px;
      }
    }
  }
}

// Animation
.fade-in {
  animation: fadeIn 0.3s ease-in-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(5px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
