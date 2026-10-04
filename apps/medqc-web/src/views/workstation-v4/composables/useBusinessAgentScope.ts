import { computed, ref, watch, type Ref } from 'vue'
import {
  businessAgentApi,
  type BusinessAgentAccess,
  type BusinessAgentContext,
} from '@/api/businessAgent'

interface ScopeHost {
  userContext?: BusinessAgentContext
  allowCaseSelection?: boolean
  // 内嵌页签：页签切换只是显隐，进行中的对话不能因此中断，授权在后台静默刷新。
  embedded?: boolean
}

const scopeKey = (scope: { institute_id: string; department: string }) =>
  JSON.stringify([scope.institute_id, scope.department])

// 助手的授权范围与实际会话上下文：读取授权、选择科室/病例，并给出最终发送给后端的上下文。
// 宿主固定了管理者范围（病例入口）时，科室与病例范围以宿主为准，只能用匹配的授权，不回退到其它科室。
export function useBusinessAgentScope(props: ScopeHost, open: Ref<boolean>) {
  const accessScope = ref<BusinessAgentAccess>()
  const accessLoading = ref(false)
  const loadError = ref('')
  const selectedScope = ref('')
  const selectedCase = ref('')
  const selectedView = ref<'doctor' | 'manager'>('manager')
  const carePhase = ref<'inpatient' | 'discharged'>('discharged')
  const dates = ref<[string, string]>()
  const carePhaseOptions = [
    { value: 'inpatient', label: '在院' },
    { value: 'discharged', label: '已出院' },
  ]

  const activeView = computed(() =>
    props.allowCaseSelection ? selectedView.value : props.userContext?.view || 'manager',
  )
  // 宿主（病例入口）已给定科室与病例范围：界面只展示，不允许在助手内改成别的科室或范围。
  const hostFixed = computed(
    () => !props.allowCaseSelection && props.userContext?.view === 'manager',
  )
  const caseOptions = computed(() =>
    (accessScope.value?.doctor_cases || []).map((record) => ({
      value: JSON.stringify([record.institute_id, record.patient_id, record.visit_id]),
      label: `住院 ${record.visit_id} · 患者 ${record.patient_id} · ${record.institute_id}`,
    })),
  )
  const doctorCase = computed(() =>
    accessScope.value?.doctor_cases?.find(
      (record) =>
        JSON.stringify([record.institute_id, record.patient_id, record.visit_id]) ===
        selectedCase.value,
    ),
  )
  const scopeOptions = computed(() =>
    (accessScope.value?.manager_scopes || []).map((scope) => ({
      value: scopeKey(scope),
      label: `${scope.department} · ${scope.institute_id}`,
    })),
  )
  const managerScope = computed(() =>
    accessScope.value?.manager_scopes.find((scope) => scopeKey(scope) === selectedScope.value),
  )

  // 宿主指定了科室但账号没有匹配的管理授权：明确报错，不选取其它授权科室。
  const hostedDepartment = computed(() =>
    hostFixed.value ? props.userContext?.department : undefined,
  )
  const scopeError = computed(() => {
    if (!accessScope.value || !hostedDepartment.value) return ''
    const matched = accessScope.value.manager_scopes.some(
      (scope) =>
        scope.institute_id === props.userContext?.institute_id &&
        scope.department === hostedDepartment.value,
    )
    return matched ? '' : '当前账号对该病例所在科室没有管理授权。'
  })
  // 授权结果与当前入口是否匹配随宿主上下文变化（例如换到没有医生授权的病例），所以按当前入口实时判断。
  const noGrantError = computed(() => {
    const result = accessScope.value
    if (!result) return ''
    const missing = props.allowCaseSelection
      ? !result.doctor_case_count && !result.manager_scopes.length
      : props.userContext?.view === 'doctor'
        ? !result.doctor_case_count
        : !result.manager_scopes.length
    return missing ? '当前账号没有此入口的明确授权范围。' : ''
  })
  const accessError = computed(() => loadError.value || noGrantError.value || scopeError.value)

  // 把选中的科室同步到宿主给定的科室；未指定科室时（全局入口）只在唯一授权时自动选择。
  function syncScope() {
    const grants = accessScope.value?.manager_scopes
    if (!grants) {
      selectedScope.value = ''
      return
    }
    const host = props.userContext
    if (hostedDepartment.value) {
      const matched = grants.find(
        (scope) =>
          scope.institute_id === host?.institute_id && scope.department === hostedDepartment.value,
      )
      selectedScope.value = matched ? scopeKey(matched) : ''
      return
    }
    if (grants.length === 1 && !selectedScope.value) selectedScope.value = scopeKey(grants[0])
  }

  let accessGeneration = 0
  function clearAccess() {
    accessScope.value = undefined
    selectedScope.value = ''
    selectedCase.value = ''
  }
  watch(
    open,
    async (visible) => {
      const epoch = ++accessGeneration
      // 抽屉每次打开都重新读取并清空旧授权；内嵌页签保持当前授权直到新结果返回。
      if (!props.embedded) {
        clearAccess()
        loadError.value = ''
      }
      accessLoading.value = false
      if (!visible) return
      accessLoading.value = true
      try {
        const result = await businessAgentApi.access()
        if (epoch !== accessGeneration) return
        accessScope.value = result
        loadError.value = ''
        if (props.allowCaseSelection)
          selectedView.value = result.manager_scopes.length ? 'manager' : 'doctor'
        syncScope()
      } catch {
        if (epoch === accessGeneration) {
          // 读取失败不沿用旧身份或旧范围。
          clearAccess()
          loadError.value = '访问范围读取失败，请确认账号授权配置。'
        }
      } finally {
        if (epoch === accessGeneration) accessLoading.value = false
      }
    },
    { immediate: true },
  )
  // 宿主切换病例（同科室或跨科室）时，实际使用的科室立即跟随。
  watch(() => [props.userContext?.institute_id, props.userContext?.department], syncScope)
  // 病例入口给定的在院/出院范围必须传到底，不能被初始值覆盖。
  watch(
    () => (hostFixed.value ? props.userContext?.care_phase : undefined),
    (phase) => {
      if (phase) carePhase.value = phase
    },
    { immediate: true },
  )

  const context = computed<BusinessAgentContext>(() =>
    activeView.value === 'doctor'
      ? props.allowCaseSelection
        ? { view: 'doctor', ...doctorCase.value }
        : props.userContext || { view: 'doctor' }
      : {
          view: 'manager',
          institute_id: managerScope.value?.institute_id,
          department: managerScope.value?.department,
          care_phase: carePhase.value,
          completed_from: dates.value ? `${dates.value[0]}T00:00:00+08:00` : undefined,
          completed_to: dates.value ? `${dates.value[1]}T23:59:59+08:00` : undefined,
        },
  )
  // 授权已读取、没有授权错误，且科室/病例已确定；日期不属于“确定”的条件（沿用原有行为）。
  const contextReady = computed(
    () =>
      !!accessScope.value &&
      !accessError.value &&
      (context.value.view === 'doctor'
        ? !!accessScope.value.doctor_case_count &&
          !!context.value.institute_id &&
          !!context.value.patient_id &&
          !!context.value.visit_id &&
          (!props.allowCaseSelection || !!doctorCase.value)
        : !!managerScope.value),
  )
  const canQuery = computed(
    () =>
      contextReady.value &&
      (context.value.view === 'doctor' || (!!dates.value?.[0] && !!dates.value?.[1])),
  )

  return {
    accessScope,
    accessLoading,
    accessError,
    selectedScope,
    selectedCase,
    selectedView,
    activeView,
    hostFixed,
    caseOptions,
    doctorCase,
    scopeOptions,
    managerScope,
    carePhase,
    carePhaseOptions,
    dates,
    context,
    contextReady,
    canQuery,
  }
}
