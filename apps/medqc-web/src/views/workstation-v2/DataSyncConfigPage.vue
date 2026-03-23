<template>
  <div class="min-h-screen bg-[#F4F6F8] flex flex-col font-sans text-slate-800">
    <div
      class="flex-1 p-6 overflow-hidden flex flex-col min-h-0 container mx-auto max-w-[1600px] w-full"
    >
      <a-tabs
        v-model:active-key="activeTab"
        class="system-config-tabs"
      >
        <a-tab-pane
          key="dataSync"
          tab="数据同步配置"
        >
          <div class="flex flex-col min-h-0 gap-6">
            <SyncOverviewBar />

            <div class="flex-1 flex gap-6 overflow-hidden min-h-0">
              <div
                class="w-[24%] shrink-0 bg-white rounded-[8px] shadow-[0_1px_2px_0_rgba(0,0,0,0.03),0_1px_6px_-1px_rgba(0,0,0,0.02)] border border-[#E5E7EB] overflow-hidden flex flex-col"
              >
                <ConnectionStudio />
              </div>

              <div
                class="flex-1 shrink-0 bg-white rounded-[8px] shadow-[0_1px_2px_0_rgba(0,0,0,0.03),0_1px_6px_-1px_rgba(0,0,0,0.02)] border border-[#E5E7EB] overflow-hidden flex flex-col"
              >
                <SchemaExplorer />
              </div>

              <div class="w-[30%] shrink-0 flex flex-col gap-6 overflow-hidden">
                <div
                  class="shrink-0 bg-white rounded-[8px] shadow-[0_1px_2px_0_rgba(0,0,0,0.03),0_1px_6px_-1px_rgba(0,0,0,0.02)] border border-[#E5E7EB] overflow-hidden flex flex-col"
                >
                  <SyncPolicyPanel />
                </div>
                <div
                  class="flex-1 bg-white rounded-[8px] shadow-[0_1px_2px_0_rgba(0,0,0,0.03),0_1px_6px_-1px_rgba(0,0,0,0.02)] border border-[#E5E7EB] overflow-hidden flex flex-col"
                >
                  <SyncRunPanel />
                </div>
              </div>
            </div>

            <div
              class="shrink-0 bg-white rounded-[8px] shadow-[0_1px_2px_0_rgba(0,0,0,0.03),0_1px_6px_-1px_rgba(0,0,0,0.02)] border border-[#E5E7EB] overflow-hidden"
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
            class="bg-white rounded-[8px] shadow-[0_1px_2px_0_rgba(0,0,0,0.03),0_1px_6px_-1px_rgba(0,0,0,0.02)] border border-[#E5E7EB] p-5"
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
.system-config-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 16px;
}

.system-config-tabs :deep(.ant-tabs-tab) {
  font-weight: 600;
}
</style>
