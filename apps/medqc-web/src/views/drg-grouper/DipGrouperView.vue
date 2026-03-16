<template>
  <div class="dip-grouper-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <div class="header-left">
        <h1 class="page-title">
          <ApartmentOutlined class="title-icon" />
          DIP 分组器
        </h1>
        <a-tag color="green" class="scheme-tag">{{ schemeInfo.version }} · {{ schemeInfo.zdCount }} 病种</a-tag>
      </div>
    </div>

    <div class="grouper-layout">
      <!-- 左侧：输入区域 -->
      <div class="input-section">
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
            DIP 分组
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
            <ApartmentOutlined class="empty-icon" />
          </div>
          <h3>等待分组</h3>
          <p>请在左侧输入病案信息，然后点击"DIP 分组"按钮</p>
        </div>

        <!-- 加载中 -->
        <div v-else-if="grouping" class="result-loading">
          <a-spin size="large" />
          <p>正在分组...</p>
        </div>

        <!-- 分组结果 -->
        <template v-else-if="result">
          <!-- DIP 分组结果卡片 -->
          <a-card size="small" class="result-card" :class="result.status === '分组成功' ? 'success' : 'fail'">
            <template #title>
              <CheckCircleOutlined v-if="result.status === '分组成功'" style="color: #52c41a" />
              <CloseCircleOutlined v-else style="color: #ff4d4f" />
              {{ result.status }}
            </template>

            <!-- DIP 分组路径 -->
            <div v-if="result.status === '分组成功'" class="dip-result">
              <div class="dip-code-display">
                <div class="dip-code-label">DIP 编码</div>
                <div class="dip-code-value">{{ result.dipCode }}</div>
              </div>
              <div class="dip-info-grid">
                <div class="dip-info-item">
                  <span class="dip-info-label">病种名称</span>
                  <span class="dip-info-value">{{ result.dipName }}</span>
                </div>
                <div class="dip-info-item">
                  <span class="dip-info-label">主诊断</span>
                  <span class="dip-info-value">{{ result.primaryZd }} {{ result.primaryZdName }}</span>
                </div>
                <div class="dip-info-item" v-if="result.matchedSs">
                  <span class="dip-info-label">匹配手术</span>
                  <span class="dip-info-value">{{ result.matchedSs }}</span>
                </div>
                <div class="dip-info-item" v-if="result.matchedRelSs">
                  <span class="dip-info-label">相关手术</span>
                  <span class="dip-info-value">{{ result.matchedRelSs }}</span>
                </div>
                <div class="dip-info-item">
                  <span class="dip-info-label">匹配方式</span>
                  <a-tag :color="matchTypeColor">{{ result.matchType }}</a-tag>
                </div>
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
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { message } from 'ant-design-vue'
import {
  ApartmentOutlined,
  MedicineBoxOutlined,
  ToolOutlined,
  PlusOutlined,
  DeleteOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  ExperimentOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons-vue'
import {
  performDipGrouping,
  getDipSchemeInfo,
  type DipGrouperResult,
} from './dipGrouper'

// ==================== 状态 ====================
const schemeInfo = getDipSchemeInfo()

const formData = reactive({
  zdList: [''] as string[],
  ssList: [''] as string[],
})

const grouping = ref(false)
const result = ref<DipGrouperResult | null>(null)

const matchTypeColor = computed(() => {
  if (!result.value?.matchType) return 'default'
  switch (result.value.matchType) {
    case '诊断+手术+相关手术': return 'purple'
    case '诊断+手术': return 'blue'
    case '纯诊断': return 'green'
    default: return 'default'
  }
})

// ==================== 操作 ====================
function addDiagnosis() {
  formData.zdList.push('')
}

function addProcedure() {
  formData.ssList.push('')
}

function resetForm() {
  formData.zdList = ['']
  formData.ssList = ['']
  result.value = null
}

/** 填入测试用例 - 胆囊结石 + 腹腔镜胆囊切除 */
function fillTestCase() {
  formData.zdList = ['K80.1', 'K83.1']
  formData.ssList = ['51.2300']
  result.value = null
  message.success('已填入测试用例：胆囊结石 + 腹腔镜胆囊切除')
}

function doGrouping() {
  const zdList = formData.zdList.filter(z => z.trim())
  const ssList = formData.ssList.filter(s => s.trim())

  if (zdList.length === 0) {
    message.warning('请至少输入一个诊断编码')
    return
  }

  grouping.value = true
  result.value = null

  // 使用 setTimeout 模拟异步，让 UI 有机会显示 loading
  setTimeout(() => {
    try {
      result.value = performDipGrouping({ zdList, ssList })

      if (result.value.status === '分组成功') {
        message.success(`分组成功: ${result.value.dipCode}`)
      } else {
        message.warning('未入组')
      }
    } catch (err) {
      message.error('分组失败: ' + (err instanceof Error ? err.message : String(err)))
    } finally {
      grouping.value = false
    }
  }, 100)
}
</script>

<style scoped>
/* ==================== 页面布局 ==================== */
.dip-grouper-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(135deg, #f0faf5 0%, #f5f7fa 100%);
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
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #1a1a1a;
}
.title-icon {
  color: #52c41a;
  margin-right: 8px;
}
.scheme-tag {
  font-size: 13px;
}

/* ==================== 分组布局 ==================== */
.grouper-layout {
  display: flex;
  flex: 1;
  gap: 20px;
  padding: 20px 24px;
  overflow: hidden;
}

.input-section {
  width: 420px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
}

.result-section {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ==================== 输入区域 ==================== */
.input-card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.code-input-area {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.code-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.code-tag {
  min-width: 64px;
  text-align: center;
}

.code-input {
  flex: 1;
  font-family: 'SF Mono', 'Menlo', monospace;
}

.add-btn {
  margin-top: 4px;
}

/* ==================== 操作按钮 ==================== */
.action-bar {
  display: flex;
  gap: 8px;
  padding-top: 4px;
}

.group-btn {
  flex: 1;
  background: linear-gradient(135deg, #52c41a, #389e0d) !important;
  border: none !important;
  font-weight: 600;
}

/* ==================== 结果区 ==================== */
.result-empty, .result-loading {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #bfbfbf;
}

.empty-icon-wrap {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #f0fff0, #e6ffe6);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-icon {
  font-size: 36px;
  color: #95de64;
}

.result-card {
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.result-card.success {
  border-left: 3px solid #52c41a;
}

.result-card.fail {
  border-left: 3px solid #ff4d4f;
}

/* ==================== DIP 结果展示 ==================== */
.dip-result {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dip-code-display {
  text-align: center;
  padding: 16px;
  background: linear-gradient(135deg, #f6ffed 0%, #e6fffb 100%);
  border-radius: 8px;
  border: 1px dashed #b7eb8f;
}

.dip-code-label {
  font-size: 12px;
  color: #8c8c8c;
  margin-bottom: 4px;
}

.dip-code-value {
  font-size: 24px;
  font-weight: 700;
  color: #237804;
  font-family: 'SF Mono', 'Menlo', monospace;
  letter-spacing: 1px;
}

.dip-info-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dip-info-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 6px;
}

.dip-info-label {
  min-width: 72px;
  font-size: 12px;
  color: #8c8c8c;
  flex-shrink: 0;
}

.dip-info-value {
  font-size: 13px;
  color: #262626;
  word-break: break-all;
}
</style>
