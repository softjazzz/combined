<template>
  <div class="sync-config-page min-h-screen flex flex-col font-sans text-slate-800">
    <div
      class="flex-1 p-5 lg:p-6 overflow-hidden flex flex-col min-h-0 container mx-auto max-w-[1680px] w-full"
    >
      <a-tabs
        v-model:active-key="activeTab"
        class="system-config-tabs flex-1 min-h-0"
      >
        <a-tab-pane
          key="dataSync"
          tab="数据同步配置"
        >
          <div class="layout-shell flex flex-col h-full gap-4">
            <section class="zone zone-top">
              <SyncOverviewBar />
            </section>

            <div class="layout-main flex-1 flex gap-4 overflow-hidden min-h-0">
              <div
                class="zone zone-connection w-[24%] shrink-0 overflow-hidden flex flex-col"
              >
                <ConnectionStudio />
              </div>

              <div
                class="zone zone-schema flex-1 shrink-0 overflow-hidden flex flex-col"
              >
                <SchemaExplorer />
              </div>

              <div class="w-[30%] shrink-0 flex flex-col gap-4 overflow-hidden right-stack">
                <div
                  class="zone zone-policy shrink-0 overflow-hidden flex flex-col"
                >
                  <SyncPolicyPanel />
                </div>
                <div
                  class="zone zone-runs flex-1 overflow-hidden flex flex-col"
                >
                  <SyncRunPanel />
                </div>
              </div>
            </div>

            <div
              class="zone zone-mapping shrink-0 overflow-hidden"
            >
              <FieldMappingWorkbench />
            </div>
          </div>
        </a-tab-pane>

        <a-tab-pane
          key="frontpageExtraction"
          tab="首页抽取设置"
        >
          <div
            class="bg-white/95 backdrop-blur-md rounded-2xl shadow-[0_2px_16px_rgba(15,23,42,0.03)] border border-slate-200/60 p-5"
          >
            <FrontpageExtractionSettingsPanel />
          </div>
        </a-tab-pane>
      </a-tabs>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import SyncOverviewBar from './components/sync-console/SyncOverviewBar.vue'
import ConnectionStudio from './components/sync-console/ConnectionStudio.vue'
import SchemaExplorer from './components/sync-console/SchemaExplorer.vue'
import SyncPolicyPanel from './components/sync-console/SyncPolicyPanel.vue'
import SyncRunPanel from './components/sync-console/SyncRunPanel.vue'
import FieldMappingWorkbench from './components/sync-console/FieldMappingWorkbench.vue'
import FrontpageExtractionSettingsPanel from './components/system-config/FrontpageExtractionSettingsPanel.vue'
import { useDataSync } from './composables/useDataSync'

const activeTab = ref('dataSync')
const route = useRoute()
const { initialize, resetState } = useDataSync()

onMounted(async () => {
  if (route.query.tab === 'frontpageExtraction') {
    activeTab.value = 'frontpageExtraction'
  }
  await initialize()
})

onUnmounted(() => {
  resetState()
})
</script>

<style scoped>
.sync-config-page {
  background:
    radial-gradient(1200px 400px at 20% -20%, #dbeafe 0%, rgba(219, 234, 254, 0) 60%),
    radial-gradient(800px 300px at 100% -10%, #e0f2fe 0%, rgba(224, 242, 254, 0) 60%),
    #f3f4f6;
}

.layout-shell {
  position: relative;
}

.zone {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
}

.zone-top {
  padding: 14px;
  border-color: rgba(59, 130, 246, 0.28);
}

.zone-policy {
  border-color: rgba(59, 130, 246, 0.3);
}

.zone-runs {
  border-color: rgba(148, 163, 184, 0.32);
}

.system-config-tabs {
  display: flex !important;
  flex-direction: column;
  height: 100%;
}

.system-config-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 16px;
  flex-shrink: 0;
}

.system-config-tabs :deep(.ant-tabs-content-holder) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.system-config-tabs :deep(.ant-tabs-content) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.system-config-tabs :deep(.ant-tabs-tabpane) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.system-config-tabs :deep(.ant-tabs-tab) {
  font-weight: 600;
}

@media (max-width: 1366px) {
  .layout-main {
    flex-direction: column;
  }

  .layout-main > .zone-connection,
  .layout-main > .zone-schema,
  .layout-main > .right-stack {
    width: 100%;
  }

  .right-stack {
    min-height: 520px;
  }
}

@media (max-width: 768px) {
  .sync-config-page {
    background: #f3f4f6;
  }

  .zone-top {
    padding: 10px;
  }
}
</style>
