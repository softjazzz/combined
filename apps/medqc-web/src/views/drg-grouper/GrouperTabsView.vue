<template>
  <div class="grouper-shell">
    <header class="grouper-header">
      <div class="header-main">
        <div class="breadcrumb">
          <HomeOutlined />
          <span>工作台</span>
          <span>/</span>
          <strong>分组器</strong>
        </div>
        <div class="title-row">
          <div>
            <h1>医保分组器</h1>
            <p>输入诊断、手术和费用条件，输出 DRG/DIP 模拟入组结果。</p>
          </div>
          <span class="safety-chip">
            <AlertOutlined />
            仅模拟，不写入正式结果
          </span>
        </div>
      </div>

      <div class="tab-segment">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="tab-button"
          :class="{ active: activeTab === tab.key }"
          type="button"
          @click="activeTab = tab.key"
        >
          <component :is="tab.icon" />
          <span>{{ tab.label }}</span>
        </button>
      </div>
    </header>

    <main class="grouper-content">
      <DrgGrouperView v-if="activeTab === 'drg'" />
      <CnDrgGrouperView v-if="activeTab === 'cndrg'" />
      <DipGrouperView v-if="activeTab === 'dip'" />
    </main>
  </div>
</template>

<script setup lang="ts">
import { defineAsyncComponent, ref } from 'vue'
import {
  AlertOutlined,
  BarChartOutlined,
  ClusterOutlined,
  HomeOutlined,
  PartitionOutlined,
} from '@ant-design/icons-vue'

const DrgGrouperView = defineAsyncComponent(() => import('./DrgGrouperView.vue'))
const CnDrgGrouperView = defineAsyncComponent(() => import('./CnDrgGrouperView.vue'))
const DipGrouperView = defineAsyncComponent(() => import('./DipGrouperView.vue'))

const tabs = [
  {
    key: 'drg',
    label: 'CHS-DRG 四川 2.0',
    icon: ClusterOutlined,
  },
  {
    key: 'cndrg',
    label: 'CN-DRG 2023',
    icon: BarChartOutlined,
  },
  {
    key: 'dip',
    label: 'DIP 泸州版',
    icon: PartitionOutlined,
  },
]

const activeTab = ref('drg')
</script>

<style scoped>
.grouper-shell {
  display: flex;
  height: 100%;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: #f5f9fc;
  color: #0f172a;
  font-family: Inter, 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
}

.grouper-header {
  display: flex;
  flex: 0 0 auto;
  align-items: end;
  justify-content: space-between;
  gap: 18px;
  padding: 18px 24px 12px;
}

.header-main {
  min-width: 0;
}

.breadcrumb {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  line-height: 18px;
}

.breadcrumb strong {
  color: #0f172a;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.title-row h1 {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
  font-weight: 850;
  line-height: 30px;
}

.title-row p {
  margin: 3px 0 0;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  line-height: 20px;
}

.safety-chip {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  border-radius: 6px;
  background: #fff7ed;
  color: #ea580c;
  padding: 6px 9px;
  font-size: 12px;
  font-weight: 800;
}

.tab-segment {
  display: flex;
  flex: 0 0 auto;
  gap: 0;
  overflow: hidden;
  border: 1px solid #dbe3ef;
  border-radius: 8px;
  background: #fff;
}

.tab-button {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: 0;
  border-right: 1px solid #e2e8f0;
  background: #fff;
  color: #334155;
  cursor: pointer;
  padding: 10px 18px;
  font-size: 14px;
  font-weight: 800;
  line-height: 18px;
  transition:
    background 0.16s ease,
    color 0.16s ease,
    box-shadow 0.16s ease;
}

.tab-button:last-child {
  border-right: 0;
}

.tab-button:hover {
  background: #f8fbff;
  color: #2563eb;
}

.tab-button.active {
  background: #eaf2ff;
  color: #2563eb;
  box-shadow: inset 0 -2px 0 #2563eb;
}

.grouper-content {
  min-height: 0;
  flex: 1;
  overflow: hidden;
}

@media (max-width: 1040px) {
  .grouper-header {
    align-items: stretch;
    flex-direction: column;
  }

  .tab-segment {
    width: fit-content;
    max-width: 100%;
    overflow-x: auto;
  }
}

@media (max-width: 720px) {
  .title-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
