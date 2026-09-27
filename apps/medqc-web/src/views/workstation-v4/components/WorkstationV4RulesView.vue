<template>
  <div class="rules-sub-page flex h-full min-w-0 flex-1 overflow-hidden bg-[#f5f5f7] p-4">
    <main
      class="custom-scrollbar rules-sub-shell flex min-w-0 flex-1 flex-col overflow-y-auto rounded-[22px] border px-5 pb-5 pt-5"
    >
      <section class="wv4-analysis-overview mb-4">
        <div class="wv4-analysis-overview__header">
          <div>
            <div class="wv4-analysis-overview__eyebrow">
              规则工作台
            </div>
            <h2 class="wv4-analysis-overview__title">
              {{ rulesSubTabTitle }}
            </h2>
            <p class="wv4-analysis-overview__subtitle">
              {{ rulesSubTabDesc }}
            </p>
          </div>
          <div class="wv4-analysis-overview__actions">
            <button
              class="rules-sub-back-btn"
              @click="emit('back')"
            >
              <LeftOutlined />
              返回病历列表
            </button>
          </div>
        </div>
      </section>
      <div class="cw-rules-content flex-1 min-w-0">
        <AsyncCodingRulesTab v-if="rulesSubTab === 'coding'" />
        <AsyncFrontpageRulesOverview v-else-if="rulesSubTab === 'frontpage'" />
        <AsyncSettlementRulesOverview v-else-if="rulesSubTab === 'settlement'" />
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { LeftOutlined } from '@ant-design/icons-vue'
import type { DeptInfo } from '../types'

const props = defineProps<{
  departments: DeptInfo[]
  rulesSubTab: 'coding' | 'frontpage' | 'settlement'
  rulesSubTabTitle: string
}>()

const emit = defineEmits<{
  'select-department': [dept: string]
  back: []
}>()

const AsyncCodingRulesTab = defineAsyncComponent(
  () => import('@/components/rules/CodingRulesTab.vue'),
)
const AsyncFrontpageRulesOverview = defineAsyncComponent(
  () => import('./FrontpageRulesOverview.vue'),
)
const AsyncSettlementRulesOverview = defineAsyncComponent(
  () => import('./SettlementRulesOverview.vue'),
)

const rulesSubTabDesc = computed(() => {
  const map = {
    coding: '维护编码质控规则的审核逻辑、扣分策略与适用范围。',
    frontpage: '聚焦病案首页字段完整性与一致性规则，保障首页生成质量。',
    settlement: '统一结算清单质控规则，提前识别费用与医保字段异常。',
  }
  return map[props.rulesSubTab]
})
</script>

<style scoped>
.rules-sub-page {
  color: #1d1d1f;
  font-family:
    'Source Han Sans SC', 'San Francisco', 'SF Pro Text', 'SF Pro Display', Inter, 'PingFang SC',
    'Microsoft YaHei UI', 'Microsoft YaHei', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.rules-sub-shell {
  border-color: rgba(0, 0, 0, 0.08);
  background: rgba(255, 255, 255, 0.88);
  -webkit-backdrop-filter: blur(20px);
  backdrop-filter: blur(20px);
  box-shadow:
    0 1px 4px rgba(0, 0, 0, 0.045),
    0 8px 28px rgba(0, 0, 0, 0.06);
}

.wv4-analysis-overview__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.wv4-analysis-overview__eyebrow {
  color: #0a6cff;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.wv4-analysis-overview__title {
  margin: 4px 0 0;
  color: #1d1d1f;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0;
  line-height: 1.2;
}

.wv4-analysis-overview__subtitle {
  margin: 8px 0 0;
  color: rgba(29, 29, 31, 0.6);
  font-size: 14px;
  line-height: 1.7;
}

.rules-sub-back-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 38px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.78);
  color: rgba(29, 29, 31, 0.7);
  font-size: 14px;
  font-weight: 600;
  padding: 0 14px;
  transition:
    background 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    border-color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    color 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.25s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.rules-sub-back-btn:hover {
  border-color: rgba(10, 108, 255, 0.28);
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  color: #0a6cff;
  transform: translateY(-1px);
}

.cw-rules-content {
  border-radius: 18px;
}

@media (max-width: 768px) {
  .wv4-analysis-overview__header {
    flex-direction: column;
  }
}
</style>
