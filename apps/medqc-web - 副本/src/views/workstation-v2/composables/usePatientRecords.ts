import { computed, ref } from 'vue'
import { ApiService } from '@/services/apiService'
import type { DeptInfo, PatientRecord } from '../types'
import { normalizeRecord } from '../normalize'

function normalizeDepartment(raw: unknown): DeptInfo {
  const source = (raw || {}) as Record<string, unknown>
  const name = String(source.name ?? source.department ?? source.dept_name ?? '未分科室').trim()
  const total = Number(source.total ?? source.count ?? 0)
  const warningCount = Number(source.warningCount ?? source.warning_count ?? 0)
  return {
    name: name || '未分科室',
    total: Number.isFinite(total) ? total : 0,
    warningCount: Number.isFinite(warningCount) ? warningCount : 0,
  }
}

function buildDepartments(records: PatientRecord[]): DeptInfo[] {
  const map = new Map<string, DeptInfo>()
  for (const record of records) {
    const name = record.department || '未分科室'
    const current = map.get(name) || { name, total: 0, warningCount: 0 }
    current.total += 1
    if (record.status === 'warning' || record.status === 'has_defects') {
      current.warningCount += 1
    }
    map.set(name, current)
  }
  const values = [...map.values()].sort((a, b) => b.total - a.total)
  return [{ name: '全部科室', total: records.length, warningCount: values.reduce((sum, item) => sum + item.warningCount, 0) }, ...values]
}

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
      const response = await ApiService.getRaw('/api/medical-records/workstation', {
        params: { page, page_size: 50 },
      })
      const raw = response.data as Record<string, unknown>
      const data = (raw && typeof raw === 'object' && 'data' in raw
        ? (raw.data as Record<string, unknown>)
        : raw) as Record<string, unknown>

      const normalizedRecords = Array.isArray(data.records)
        ? data.records.map((record: unknown) => normalizeRecord(record))
        : []
      allRecords.value = normalizedRecords
      departments.value = Array.isArray(data.departments) && data.departments.length > 0
        ? data.departments.map((dept: unknown) => normalizeDepartment(dept))
        : buildDepartments(normalizedRecords)

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
