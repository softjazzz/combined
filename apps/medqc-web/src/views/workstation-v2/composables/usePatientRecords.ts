import { ref, computed } from 'vue'
import axios from 'axios'
import type { PatientRecord, DeptInfo } from '../types'
import { isDefectStatus } from '../normalize'

export function usePatientRecords() {
  const allRecords = ref<PatientRecord[]>([])
  const departments = ref<DeptInfo[]>([])
  const currentPage = ref(1)
  const serverTotal = ref(0)
  const serverTotalPages = ref(1)
  const totalCount = computed(() => serverTotal.value)
  const loading = ref(false)

  const activeDept = ref('全部科室')
  const searchText = ref('')
  const statusFilter = ref('all')
  const hospFilter = ref<'all' | 'inpatient' | 'discharged'>('all')

  const statusOptions = [
    { value: 'all', label: '全部状态' },
    { value: 'pending', label: '待处理' },
    { value: 'processing', label: '处理中' },
    { value: 'completed', label: '已完成' },
    { value: 'warning', label: '有缺陷' },
  ]

  const hospOptions = [
    { value: 'all', label: '全部' },
    { value: 'inpatient', label: '在院' },
    { value: 'discharged', label: '已出院' },
  ]

  const filteredRecords = computed(() => {
    let list = allRecords.value

    if (activeDept.value !== '全部科室') {
      list = list.filter((r) => r.department === activeDept.value)
    }

    if (hospFilter.value !== 'all') {
      list = list.filter((r) => {
        const hasDischargeDate = !!r.dischargeDate && r.dischargeDate.trim() !== ''
        return hospFilter.value === 'inpatient' ? !hasDischargeDate : hasDischargeDate
      })
    }

    if (statusFilter.value !== 'all') {
      list = list.filter((r) =>
        statusFilter.value === 'warning' ? isDefectStatus(r.status) : r.status === statusFilter.value,
      )
    }

    if (searchText.value.trim()) {
      const keyword = searchText.value.trim().toLowerCase()
      list = list.filter((r) => r.name.toLowerCase().includes(keyword) || r.id.toLowerCase().includes(keyword))
    }

    return list
  })

  const statusCounts = computed(() => {
    const all = activeDept.value === '全部科室'
      ? allRecords.value
      : allRecords.value.filter((r) => r.department === activeDept.value)

    return {
      completed: all.filter((r) => r.status === 'completed').length,
      warning: all.filter((r) => isDefectStatus(r.status)).length,
      processing: all.filter((r) => r.status === 'processing').length,
      pending: all.filter((r) => r.status === 'pending').length,
    }
  })

  const completionRate = computed(() => {
    const all = activeDept.value === '全部科室'
      ? allRecords.value
      : allRecords.value.filter((r) => r.department === activeDept.value)

    if (all.length === 0) return 0
    return Math.round((all.filter((r) => r.status === 'completed').length / all.length) * 100)
  })

  const statusPills = computed(() => [
    {
      key: 'all',
      label: '全部',
      count: filteredRecords.value.length,
      activeClass: 'bg-slate-900 text-white border-slate-900 shadow-sm',
      dotClass: '',
    },
    {
      key: 'completed',
      label: '已完成',
      count: statusCounts.value.completed,
      activeClass: 'bg-emerald-50 text-emerald-800 border-emerald-200 shadow-sm',
      dotClass: 'bg-emerald-500',
    },
    {
      key: 'warning',
      label: '有缺陷',
      count: statusCounts.value.warning,
      activeClass: 'bg-rose-50 text-rose-800 border-rose-200 shadow-sm',
      dotClass: 'bg-rose-500',
    },
    {
      key: 'processing',
      label: '处理中',
      count: statusCounts.value.processing,
      activeClass: 'bg-cyan-50 text-cyan-800 border-cyan-200 shadow-sm',
      dotClass: 'bg-cyan-500',
    },
    {
      key: 'pending',
      label: '待处理',
      count: statusCounts.value.pending,
      activeClass: 'bg-amber-50 text-amber-800 border-amber-200 shadow-sm',
      dotClass: 'bg-amber-500',
    },
  ])

  async function fetchData(page = 1) {
    loading.value = true
    try {
      const { data } = await axios.get('/api/medical-records/workstation', {
        params: { page, page_size: 50 },
      })

      allRecords.value = data.records || []
      departments.value = data.departments || []

      // Backward/forward compatible pagination fields.
      const total = Number(data.total ?? data.total_count ?? 0)
      const pageSize = Number(data.page_size ?? data.pageSize ?? 50)
      const totalPagesRaw = Number(data.totalPages ?? data.total_pages ?? 0)
      const totalPagesComputed = pageSize > 0 ? Math.ceil(total / pageSize) : 1

      serverTotal.value = total
      serverTotalPages.value = Math.max(1, totalPagesRaw || totalPagesComputed || 1)
      currentPage.value = Number(data.page ?? data.current_page ?? page) || 1
    } catch (err) {
      console.error('加载工作台数据失败:', err)
    } finally {
      loading.value = false
    }
  }

  function handlePageChange(page: number) {
    currentPage.value = page
    fetchData(page)
    document.querySelector('.custom-scrollbar')?.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function refreshData() {
    fetchData(currentPage.value)
  }

  function selectDept(deptName: string) {
    activeDept.value = deptName
    currentPage.value = 1
  }

  return {
    allRecords,
    departments,
    currentPage,
    serverTotal,
    serverTotalPages,
    totalCount,
    loading,
    activeDept,
    searchText,
    statusFilter,
    hospFilter,
    statusOptions,
    hospOptions,
    filteredRecords,
    statusCounts,
    completionRate,
    statusPills,
    fetchData,
    handlePageChange,
    refreshData,
    selectDept,
  }
}

