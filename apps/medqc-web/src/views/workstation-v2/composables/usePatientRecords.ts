import { computed, ref } from 'vue'
import axios from 'axios'
import type { DeptInfo, PatientRecord } from '../types'

export function usePatientRecords() {
  const allRecords = ref<PatientRecord[]>([])
  const departments = ref<DeptInfo[]>([])
  const currentPage = ref(1)
  const serverTotal = ref(0)
  const serverTotalPages = ref(1)
  const totalCount = computed(() => serverTotal.value)
  const loading = ref(false)

  const activeDept = ref('\u5168\u90e8\u79d1\u5ba4')
  const searchText = ref('')
  const hospFilter = ref<'all' | 'inpatient' | 'discharged'>('all')

  const hospOptions = [
    { value: 'all', label: '\u5168\u90e8' },
    { value: 'inpatient', label: '\u5728\u9662' },
    { value: 'discharged', label: '\u5df2\u51fa\u9662' },
  ]

  const scopedRecords = computed(() => {
    let list = allRecords.value

    if (activeDept.value !== '\u5168\u90e8\u79d1\u5ba4') {
      list = list.filter((record) => record.department === activeDept.value)
    }

    if (hospFilter.value !== 'all') {
      list = list.filter((record) => {
        const hasDischargeDate = Boolean(record.dischargeDate && record.dischargeDate.trim() !== '')
        return hospFilter.value === 'inpatient' ? !hasDischargeDate : hasDischargeDate
      })
    }

    if (searchText.value.trim()) {
      const keyword = searchText.value.trim().toLowerCase()
      list = list.filter((record) =>
        record.name.toLowerCase().includes(keyword) || record.id.toLowerCase().includes(keyword),
      )
    }

    return list
  })

  const filteredRecords = computed(() => scopedRecords.value)

  async function fetchData(page = 1) {
    loading.value = true
    try {
      const { data } = await axios.get('/api/medical-records/workstation', {
        params: { page, page_size: 50 },
      })

      allRecords.value = data.records || []
      departments.value = data.departments || []

      const total = Number(data.total ?? data.total_count ?? 0)
      const pageSize = Number(data.page_size ?? data.pageSize ?? 50)
      const totalPagesRaw = Number(data.totalPages ?? data.total_pages ?? 0)
      const totalPagesComputed = pageSize > 0 ? Math.ceil(total / pageSize) : 1

      serverTotal.value = total
      serverTotalPages.value = Math.max(1, totalPagesRaw || totalPagesComputed || 1)
      currentPage.value = Number(data.page ?? data.current_page ?? page) || 1
    } catch (error) {
      console.error('\u52a0\u8f7d\u5de5\u4f5c\u53f0\u6570\u636e\u5931\u8d25:', error)
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
    hospFilter,
    hospOptions,
    filteredRecords,
    fetchData,
    handlePageChange,
    refreshData,
    selectDept,
  }
}
