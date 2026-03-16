<template>
  <div class="drg-grouper-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <ForkOutlined class="title-icon" />
          DRG 分组器
        </h1>
        <a-tag color="blue" class="scheme-tag">{{ currentScheme.label }} · {{ currentScheme.drgs }} 组</a-tag>
      </div>
    </div>

    <div class="grouper-layout">
      <!-- 左侧：输入区域 -->
      <div class="input-section">
        <!-- 基本信息 -->
        <a-card size="small" class="input-card">
          <template #title>
            <UserOutlined /> 基本信息
          </template>
          <a-row :gutter="12">
            <a-col :span="6">
              <div class="field-label">性别</div>
              <a-select v-model:value="formData.gender" style="width: 100%">
                <a-select-option value="1">男</a-select-option>
                <a-select-option value="2">女</a-select-option>
              </a-select>
            </a-col>
            <a-col :span="6">
              <div class="field-label">年龄</div>
              <a-input-number v-model:value="formData.age" :min="0" :max="150" style="width: 100%" placeholder="岁" />
            </a-col>
            <a-col :span="6">
              <div class="field-label">住院天数</div>
              <a-input-number v-model:value="formData.days" :min="0" style="width: 100%" placeholder="天" />
            </a-col>
            <a-col :span="6">
              <div class="field-label">离院方式</div>
              <a-select v-model:value="formData.leavingType" style="width: 100%">
                <a-select-option value="1">医嘱离院</a-select-option>
                <a-select-option value="5">死亡</a-select-option>
                <a-select-option value="2">医嘱转院</a-select-option>
                <a-select-option value="3">医嘱转社区</a-select-option>
                <a-select-option value="4">非医嘱离院</a-select-option>
              </a-select>
            </a-col>
          </a-row>
        </a-card>

        <!-- 诊断编码 -->
        <a-card size="small" class="input-card">
          <template #title>
            <MedicineBoxOutlined /> 诊断编码
          </template>
          <div class="code-input-area">
            <div class="code-row" v-for="(zd, index) in formData.zdList" :key="'zd-' + index">
              <a-tag :color="index === 0 ? 'red' : 'default'" class="code-tag">
                {{ index === 0 ? '主诊断' : `其他${index}` }}
              </a-tag>
              <a-input
                v-model:value="formData.zdList[index]"
                placeholder="输入 ICD-10 编码（如 K80.501）"
                class="code-input"
                @pressEnter="addDiagnosis"
              />
              <a-button
                v-if="index > 0"
                type="text"
                danger
                size="small"
                @click="formData.zdList.splice(index, 1)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
            <a-button type="dashed" size="small" block @click="addDiagnosis" class="add-btn">
              <PlusOutlined /> 添加诊断
            </a-button>
          </div>
        </a-card>

        <!-- 手术操作编码 -->
        <a-card size="small" class="input-card">
          <template #title>
            <ToolOutlined /> 手术操作编码
          </template>
          <div class="code-input-area">
            <div class="code-row" v-for="(ss, index) in formData.ssList" :key="'ss-' + index">
              <a-tag :color="index === 0 ? 'blue' : 'default'" class="code-tag">
                {{ index === 0 ? '主手术' : `其他${index}` }}
              </a-tag>
              <a-input
                v-model:value="formData.ssList[index]"
                placeholder="输入手术操作编码（如 51.8803）"
                class="code-input"
                @pressEnter="addProcedure"
              />
              <a-button
                v-if="formData.ssList.length > 1 || (formData.ssList.length === 1 && formData.ssList[0])"
                type="text"
                danger
                size="small"
                @click="formData.ssList.splice(index, 1)"
              >
                <DeleteOutlined />
              </a-button>
            </div>
            <a-button type="dashed" size="small" block @click="addProcedure" class="add-btn">
              <PlusOutlined /> 添加手术操作
            </a-button>
          </div>
        </a-card>

        <!-- 操作按钮 -->
        <div class="action-bar">
          <a-button
            type="primary"
            size="large"
            :loading="grouping"
            @click="doGrouping"
            class="group-btn"
          >
            <ThunderboltOutlined />
            DRG 分组
          </a-button>
          <a-button size="large" @click="resetForm">
            <ReloadOutlined />
            重置
          </a-button>
          <a-button size="large" @click="fillTestCase">
            <ExperimentOutlined />
            填入测试用例
          </a-button>
        </div>
      </div>

      <!-- 右侧：结果区域 -->
      <div class="result-section">
        <!-- 结果为空 -->
        <div v-if="!result && !grouping" class="result-empty">
          <div class="empty-icon-wrap">
            <ClusterOutlined class="empty-icon" />
          </div>
          <h3>等待分组</h3>
          <p>请在左侧输入病案信息，然后点击"DRG 分组"按钮</p>
        </div>

        <!-- 加载中 -->
        <div v-else-if="grouping" class="result-loading">
          <a-spin size="large" />
          <p>正在分组...</p>
        </div>

        <!-- 分组结果 -->
        <template v-else-if="result">
          <!-- 分组路径卡片 -->
          <a-card size="small" class="result-card" :class="result.status === '分组成功' ? 'success' : 'fail'">
            <template #title>
              <CheckCircleOutlined v-if="result.status === '分组成功'" style="color: #52c41a" />
              <CloseCircleOutlined v-else style="color: #ff4d4f" />
              {{ result.status }}
            </template>

            <!-- 分组路径 -->
            <div v-if="result.status === '分组成功'" class="group-path">
              <div class="path-step">
                <div class="path-label">MDC</div>
                <div class="path-value mdc">{{ result.mdc }}</div>
                <div class="path-name">{{ mdcName }}</div>
              </div>
              <div class="path-arrow">→</div>
              <div class="path-step">
                <div class="path-label">ADRG</div>
                <div class="path-value adrg">{{ result.adrg }}</div>
              </div>
              <div class="path-arrow">→</div>
              <div class="path-step">
                <div class="path-label">DRG</div>
                <div class="path-value drg">{{ result.drg }}</div>
              </div>
            </div>
          </a-card>

          <!-- 分组过程 -->
          <a-card size="small" class="result-card" title="分组过程">
            <a-timeline>
              <a-timeline-item
                v-for="(msg, idx) in result.messages"
                :key="idx"
                :color="idx === result.messages.length - 1 ? 'green' : 'blue'"
              >
                {{ msg }}
              </a-timeline-item>
            </a-timeline>
          </a-card>

          <!-- 质控消息 -->
          <a-card v-if="result.qcMessages.length > 0" size="small" class="result-card qc-card" title="质控提醒">
            <a-alert
              v-for="(msg, idx) in result.qcMessages"
              :key="idx"
              :message="msg"
              type="warning"
              show-icon
              class="qc-alert"
            />
          </a-card>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  ForkOutlined,
  UserOutlined,
  MedicineBoxOutlined,
  ToolOutlined,
  PlusOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  ExperimentOutlined,
  ClusterOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons-vue'
import {
  performGrouping,
  getAvailableSchemes,
  getMdcName,
  type GrouperResult,
} from './drgGrouper'

// ==================== 状态 ====================
const schemes = getAvailableSchemes()
const currentScheme = schemes[0]

const formData = reactive({
  gender: '2',
  age: 30,
  days: 15,
  leavingType: '1',
  zdList: [''] as string[],
  ssList: [''] as string[],
})

const grouping = ref(false)
const result = ref<GrouperResult | null>(null)

const mdcName = computed(() => {
  if (!result.value?.mdc) return ''
  return getMdcName(result.value.mdc)
})

// ==================== 操作 ====================
function addDiagnosis() {
  formData.zdList.push('')
}

function addProcedure() {
  formData.ssList.push('')
}

function resetForm() {
  formData.gender = '2'
  formData.age = 30
  formData.days = 15
  formData.leavingType = '1'
  formData.zdList = ['']
  formData.ssList = ['']
  result.value = null
}

/** 填入 OpenDRG 截图中的测试用例 */
function fillTestCase() {
  formData.gender = '2'
  formData.age = 30
  formData.days = 15
  formData.leavingType = '1'
  formData.zdList = ['K80.501', 'K80.100x001', 'K83.109', 'K72.905', 'E11.900']
  formData.ssList = ['51.8803', '51.8701', '51.2300']
  result.value = null
  message.success('已填入测试用例')
}

async function doGrouping() {
  // 过滤空编码
  const zdList = formData.zdList.filter(z => z.trim())
  const ssList = formData.ssList.filter(s => s.trim())

  if (zdList.length === 0) {
    message.warning('请至少输入一个诊断编码')
    return
  }

  grouping.value = true
  result.value = null

  try {
    result.value = await performGrouping({
      gender: formData.gender,
      age: formData.age,
      zdList,
      ssList,
      days: formData.days,
      leavingType: formData.leavingType,
    })

    if (result.value.status === '分组成功') {
      message.success(`分组成功: ${result.value.drg}`)
    } else {
      message.warning('未入组')
    }
  } catch (err) {
    message.error('分组失败: ' + (err instanceof Error ? err.message : String(err)))
  } finally {
    grouping.value = false
  }
}
</script>

<style scoped>
/* ==================== 页面布局 ==================== */
.drg-grouper-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(135deg, #f0f5ff 0%, #f5f7fa 100%);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.title-icon {
  color: #1677ff;
  font-size: 22px;
}
.scheme-tag {
  font-size: 12px;
}

/* ==================== 主体双栏 ==================== */
.grouper-layout {
  flex: 1;
  display: flex;
  gap: 16px;
  padding: 16px 24px;
  overflow: hidden;
  min-height: 0;
}

.input-section {
  width: 480px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-right: 4px;
}

.result-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  min-width: 0;
}

/* ==================== 输入卡片 ==================== */
.input-card {
  border-radius: 10px;
  border: 1px solid #e6e9f0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.input-card :deep(.ant-card-head) {
  min-height: 40px;
  padding: 0 16px;
  font-size: 13px;
  font-weight: 600;
  border-bottom: 1px solid #f0f2f5;
}
.input-card :deep(.ant-card-body) {
  padding: 12px 16px;
}

.field-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
  font-weight: 500;
}

/* ==================== 编码输入 ==================== */
.code-input-area {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.code-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.code-tag {
  flex-shrink: 0;
  min-width: 56px;
  text-align: center;
  font-size: 11px;
}
.code-input {
  flex: 1;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
}
.add-btn {
  margin-top: 4px;
  border-style: dashed;
  color: #999;
}

/* ==================== 操作按钮 ==================== */
.action-bar {
  display: flex;
  gap: 10px;
  padding-top: 4px;
}
.group-btn {
  flex: 1;
  font-weight: 600;
  font-size: 15px;
  height: 44px;
  border-radius: 8px;
  background: linear-gradient(135deg, #1677ff, #4096ff);
  border: none;
  box-shadow: 0 4px 12px rgba(22,119,255,0.3);
}
.group-btn:hover {
  background: linear-gradient(135deg, #4096ff, #69b1ff);
  box-shadow: 0 6px 16px rgba(22,119,255,0.4);
}

/* ==================== 结果区域 ==================== */
.result-empty,
.result-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #999;
}
.empty-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f0f5ff, #e6f4ff);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}
.empty-icon {
  font-size: 36px;
  color: #91caff;
}
.result-empty h3 {
  font-size: 18px;
  color: #333;
  margin: 0 0 8px;
}
.result-empty p {
  font-size: 13px;
  color: #aaa;
  margin: 0;
}

.result-card {
  border-radius: 10px;
  border: 1px solid #e6e9f0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.result-card.success {
  border-color: #b7eb8f;
  background: linear-gradient(135deg, #f6ffed, white);
}
.result-card.fail {
  border-color: #ffccc7;
  background: linear-gradient(135deg, #fff2f0, white);
}
.result-card :deep(.ant-card-head) {
  min-height: 40px;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 600;
}

/* ==================== 分组路径 ==================== */
.group-path {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 0;
  justify-content: center;
}
.path-step {
  text-align: center;
}
.path-label {
  font-size: 11px;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
  font-weight: 600;
}
.path-value {
  display: inline-block;
  font-size: 22px;
  font-weight: 800;
  font-family: 'Monaco', 'Menlo', 'Consolas', monospace;
  padding: 6px 16px;
  border-radius: 8px;
  letter-spacing: 1px;
}
.path-value.mdc {
  background: linear-gradient(135deg, #e6f4ff, #bae0ff);
  color: #0958d9;
}
.path-value.adrg {
  background: linear-gradient(135deg, #fff7e6, #ffe58f);
  color: #d46b08;
}
.path-value.drg {
  background: linear-gradient(135deg, #f6ffed, #b7eb8f);
  color: #389e0d;
  font-size: 28px;
}
.path-name {
  font-size: 11px;
  color: #666;
  margin-top: 4px;
  max-width: 160px;
}
.path-arrow {
  font-size: 24px;
  color: #bbb;
  font-weight: 300;
  margin-top: 16px;
}

/* ==================== 质控消息 ==================== */
.qc-card :deep(.ant-card-head) {
  border-bottom-color: #fff1b8;
}
.qc-alert {
  margin-bottom: 6px;
  border-radius: 6px;
}
.qc-alert:last-child {
  margin-bottom: 0;
}

/* ==================== 滚动条 ==================== */
.input-section::-webkit-scrollbar,
.result-section::-webkit-scrollbar {
  width: 5px;
}
.input-section::-webkit-scrollbar-track,
.result-section::-webkit-scrollbar-track {
  background: transparent;
}
.input-section::-webkit-scrollbar-thumb,
.result-section::-webkit-scrollbar-thumb {
  background: #d9d9d9;
  border-radius: 3px;
}
</style>
