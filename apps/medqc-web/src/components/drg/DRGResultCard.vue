<template>
  <div class="drg-result-card">
    <a-card
      :bordered="false"
      class="result-card"
    >
      <template #title>
        <span class="card-title">
          <ThunderboltOutlined style="color: #2b6cf6; margin-right: 8px" />
          分组结果
        </span>
      </template>
      <template #extra>
        <a-tag
          v-if="riskLevel"
          :color="getRiskColor(riskLevel)"
        >
          {{ getRiskText(riskLevel) }}风险
        </a-tag>
      </template>

      <div
        v-if="isDIP"
        class="main-info"
      >
        <div class="code-box drg-box">
          <div class="label">
            DIP病种
          </div>
          <div class="code">
            {{ dipResult.dip_code }}
          </div>
          <div class="name">
            {{ dipResult.dip_name }}
          </div>
        </div>
        <div class="divider">
          <ArrowRightOutlined />
        </div>
        <div class="code-box adrg-box">
          <div class="label">
            病种类型
          </div>
          <div
            class="code"
            style="font-size: 18px"
          >
            {{ dipResult.dip_type }}
          </div>
          <div class="name">
            分值点数: -
          </div>
        </div>
      </div>

      <div
        v-else
        class="main-info"
      >
        <div class="code-box drg-box">
          <div class="label">
            DRG组
          </div>
          <div class="code">
            {{ drgResult.drg_code }}
          </div>
          <div class="name">
            {{ drgResult.drg_name }}
          </div>
        </div>
        <div class="divider">
          <ArrowRightOutlined />
        </div>
        <div class="code-box adrg-box">
          <div class="label">
            ADRG组
          </div>
          <div class="code">
            {{ drgResult.adrg_code }}
          </div>
          <div class="name">
            {{ drgResult.adrg_name }}
          </div>
        </div>
      </div>

      <a-divider style="margin: 16px 0" />

      <a-descriptions
        :column="2"
        size="small"
      >
        <a-descriptions-item label="相对权重 (RW)">
          <span class="statistic-value">{{ displayWeight.toFixed(4) }}</span>
        </a-descriptions-item>
        <a-descriptions-item label="基准支付">
          <span
            class="statistic-value"
            style="color: #cf1322"
          >¥{{ displayPayment.toLocaleString() }}</span>
        </a-descriptions-item>
        <a-descriptions-item
          v-if="expectedLos"
          label="预期住院日"
        >
          {{ expectedLos.min }} - {{ expectedLos.max }} 天
        </a-descriptions-item>
        <a-descriptions-item
          v-if="confidence"
          label="置信度"
        >
          <a-progress
            :percent="Math.round(confidence * 100)"
            size="small"
            style="width: 100px"
          />
        </a-descriptions-item>
      </a-descriptions>
      
      <div
        v-if="groupingLogic"
        class="logic-section"
      >
        <div class="section-title">
          入组逻辑
        </div>
        <div class="logic-content">
          {{ groupingLogic }}
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ThunderboltOutlined, ArrowRightOutlined } from '@ant-design/icons-vue'
import type { DRGGroupingResult, DIPGroupingResult, RiskLevel } from '@/types/drg'

const props = defineProps<{
  result: DRGGroupingResult | DIPGroupingResult
  engineType?: 'DRG' | 'DIP'
}>()

const isDIP = computed(() => props.engineType === 'DIP' || (props.result as DIPGroupingResult).dip_code !== undefined)
const dipResult = computed(() => props.result as DIPGroupingResult)
const drgResult = computed(() => props.result as DRGGroupingResult)

// Computed properties for safe access
const riskLevel = computed(() => (props.result as any).risk_level as RiskLevel | undefined)
const displayWeight = computed(() => (props.result as DRGGroupingResult).weight ?? (props.result as any).weight ?? 0)
const displayPayment = computed(() => (props.result as DRGGroupingResult).baseline_payment ?? (props.result as any).baseline_payment ?? 0)
const expectedLos = computed(() => (props.result as DRGGroupingResult).expected_los)
const confidence = computed(() => (props.result as DRGGroupingResult).confidence)
const groupingLogic = computed(() => (props.result as DRGGroupingResult).grouping_logic)

const getRiskColor = (level: RiskLevel) => {
  switch (level) {
    case 'low': return 'success'
    case 'medium': return 'warning'
    case 'high': return 'error'
    default: return 'default'
  }
}

const getRiskText = (level: RiskLevel) => {
  switch (level) {
    case 'low': return '低'
    case 'medium': return '中'
    case 'high': return '高'
    default: return '未知'
  }
}
</script>

<style scoped lang="scss">
.drg-result-card {
  .result-card {
    background: linear-gradient(180deg, #ffffff 0%, #f9faff 100%);
    border: 1px solid #e8e8e8;
  }

  .main-info {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 0;
    
    .divider {
      color: #bfbfbf;
      font-size: 20px;
    }

    .code-box {
      text-align: center;
      flex: 1;
      
      .label {
        font-size: 12px;
        color: #999;
        margin-bottom: 4px;
      }
      
      .code {
        font-size: 24px;
        font-weight: bold;
        font-family: monospace;
        line-height: 1.2;
      }
      
      .name {
        font-size: 14px;
        color: #666;
        margin-top: 4px;
      }
      
      &.drg-box .code { color: #52c41a; }
      &.adrg-box .code { color: #2b6cf6; }
    }
  }

  .statistic-value {
    font-weight: bold;
    font-family: monospace;
    font-size: 16px;
  }
  
  .logic-section {
    margin-top: 16px;
    background-color: #f5f5f5;
    padding: 8px 12px;
    border-radius: 4px;
    
    .section-title {
      font-size: 12px;
      color: #999;
      margin-bottom: 4px;
    }
    
    .logic-content {
      font-size: 13px;
      color: #333;
    }
  }
}
</style>
