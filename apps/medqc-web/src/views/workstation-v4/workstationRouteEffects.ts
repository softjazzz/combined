import { watch } from 'vue'
import type { Ref } from 'vue'
import type { RouteLocationNormalizedLoaded, Router } from 'vue-router'
import type { WorkstationLaunchAction, WorkflowStageKey } from '@/types/workflow'
import type { PatientRecord } from './types'
import { handleWorkstationLaunchFlow } from './workstationLaunchController'

interface UseWorkstationRouteEffectsOptions {
  route: RouteLocationNormalizedLoaded
  router: Router
  allRecords: Ref<PatientRecord[]>
  allRecordsCount: Ref<number>
  validLaunchActions: WorkstationLaunchAction[]
  validStages: WorkflowStageKey[]
  handledLaunchKey: Ref<string>
  launchHandling: Ref<boolean>
  openRecord: (record: PatientRecord) => void
  setDetailMainTab: (tab: 'records' | 'frontpage' | 'settlement') => void
  setAssistPanelVisible: (visible: boolean) => void
  setAssistTab: (tab: 'coding' | 'form' | 'cost') => void
  nextTick: () => Promise<void>
  handleGenerateFrontpage: () => Promise<void>
  showWarning: (message: string) => void
  activeDept: Ref<string>
  searchText: Ref<string>
  hospFilter: Ref<string>
  currentPage: Ref<number>
  viewMode: Ref<string>
  backToList: () => void
  assistPanelVisible: Ref<boolean>
  icdDrawerVisible: Ref<boolean>
  suggestionDrawerVisible: Ref<boolean>
}

export function useWorkstationRouteEffects(options: UseWorkstationRouteEffectsOptions) {
  const {
    route,
    router,
    allRecords,
    allRecordsCount,
    validLaunchActions,
    validStages,
    handledLaunchKey,
    launchHandling,
    openRecord,
    setDetailMainTab,
    setAssistPanelVisible,
    setAssistTab,
    nextTick,
    handleGenerateFrontpage,
    showWarning,
    activeDept,
    searchText,
    hospFilter,
    currentPage,
    viewMode,
    backToList,
    assistPanelVisible,
    icdDrawerVisible,
    suggestionDrawerVisible,
  } = options

  const clearLaunchQueryParams = () => {
    const nextQuery = { ...route.query } as Record<string, any>
    delete nextQuery.record_id
    delete nextQuery.task_id
    delete nextQuery.action
    delete nextQuery.source
    delete nextQuery.from_stage
    void router.replace({ path: route.path, query: nextQuery })
  }

  const handleWorkstationLaunch = async () => {
    await handleWorkstationLaunchFlow({
      routeQuery: route.query as Record<string, unknown>,
      allRecords: allRecords.value,
      validLaunchActions,
      validStages,
      handledLaunchKey: handledLaunchKey.value,
      launchHandling: launchHandling.value,
      setHandledLaunchKey: (value) => {
        handledLaunchKey.value = value
      },
      setLaunchHandling: (value) => {
        launchHandling.value = value
      },
      clearLaunchQueryParams,
      openRecord,
      setDetailMainTab,
      setAssistPanelVisible,
      setAssistTab,
      nextTick,
      handleGenerateFrontpage,
      showWarning,
    })
  }

  watch(
    [
      () => route.query.record_id,
      () => route.query.action,
      () => route.query.source,
      () => allRecordsCount.value,
    ],
    () => {
      void handleWorkstationLaunch()
    },
    { immediate: true },
  )

  watch(
    () => route.query.stage,
    (stageRaw) => {
      const stage = String(stageRaw || '').trim()
      if (!validStages.includes(stage as WorkflowStageKey)) return
      activeDept.value = '全部科室'
      searchText.value = ''
      hospFilter.value = 'all'
      currentPage.value = 1
      if (viewMode.value !== 'list') {
        backToList()
        assistPanelVisible.value = false
        icdDrawerVisible.value = false
        suggestionDrawerVisible.value = false
      }
    },
    { immediate: true },
  )
}
