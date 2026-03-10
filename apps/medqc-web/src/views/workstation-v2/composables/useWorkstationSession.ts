import { computed, ref, watch } from 'vue'
import type { IcdApplyTarget } from '../types'

type ViewMode = 'list' | 'detail'
type AssistTabKey = 'form' | 'coding' | 'cost' | 'profile' | 'drg' | 'message'

interface PersistedState {
  frontpageTab: 'fields' | 'preview'
  assistPanelVisible: boolean
  assistTab: AssistTabKey
  icdDrawerVisible: boolean
  icdApplyTarget: IcdApplyTarget
  icdApplyIndex: number
}

const STORAGE_KEY = 'workstation_v4_session'
const VALID_ASSIST_TABS: AssistTabKey[] = ['form', 'coding', 'cost', 'profile', 'drg', 'message']

function loadState(): PersistedState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) throw new Error('missing')
    const parsed = JSON.parse(raw) as PersistedState
    return {
      frontpageTab: parsed.frontpageTab === 'preview' ? 'preview' : 'fields',
      assistPanelVisible: !!parsed.assistPanelVisible,
      assistTab: VALID_ASSIST_TABS.includes(parsed.assistTab) ? parsed.assistTab : 'form',
      icdDrawerVisible: !!parsed.icdDrawerVisible,
      icdApplyTarget: parsed.icdApplyTarget || 'mainDiagnosis',
      icdApplyIndex: Math.max(1, Number(parsed.icdApplyIndex || 1)),
    }
  } catch {
    return {
      frontpageTab: 'fields',
      assistPanelVisible: false,
      assistTab: 'form',
      icdDrawerVisible: false,
      icdApplyTarget: 'mainDiagnosis',
      icdApplyIndex: 1,
    }
  }
}

export function useWorkstationSession() {
  const state = loadState()

  const viewMode = ref<ViewMode>('list')
  const selectedId = ref<string | null>(null)

  const frontpageTab = ref<'fields' | 'preview'>(state.frontpageTab)
  const assistPanelVisible = ref(state.assistPanelVisible)
  const assistTab = ref<AssistTabKey>(state.assistTab)
  const icdDrawerVisible = ref(state.icdDrawerVisible)
  const icdApplyTarget = ref<IcdApplyTarget>(state.icdApplyTarget)
  const icdApplyIndex = ref(state.icdApplyIndex)

  const isOtherTarget = computed(() =>
    icdApplyTarget.value === 'otherDiagnosis' || icdApplyTarget.value === 'otherProcedure',
  )

  watch(
    [frontpageTab, assistPanelVisible, assistTab, icdDrawerVisible, icdApplyTarget, icdApplyIndex],
    () => {
      const payload: PersistedState = {
        frontpageTab: frontpageTab.value,
        assistPanelVisible: assistPanelVisible.value,
        assistTab: assistTab.value,
        icdDrawerVisible: icdDrawerVisible.value,
        icdApplyTarget: icdApplyTarget.value,
        icdApplyIndex: Math.max(1, Number(icdApplyIndex.value || 1)),
      }
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
    },
    { deep: false },
  )

  function openRecord(visitId: string) {
    selectedId.value = visitId
    viewMode.value = 'detail'
  }

  function goBackToList() {
    viewMode.value = 'list'
  }

  function resetPerRecordTransient() {
    icdDrawerVisible.value = false
    icdApplyTarget.value = 'mainDiagnosis'
    icdApplyIndex.value = 1
  }

  return {
    viewMode,
    selectedId,
    frontpageTab,
    assistPanelVisible,
    assistTab,
    icdDrawerVisible,
    icdApplyTarget,
    icdApplyIndex,
    isOtherTarget,
    openRecord,
    goBackToList,
    resetPerRecordTransient,
  }
}
