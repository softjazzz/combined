export type MedicalOrderFilters = { category: string; status: string; query: string }
export type FilterableMedicalOrderRow = { orderType: string; status: string; item: string }

export function emptyMedicalOrderFilters(): MedicalOrderFilters {
  return { category: '', status: '', query: '' }
}

export function matchesMedicalOrderFilters(
  row: FilterableMedicalOrderRow,
  filters: MedicalOrderFilters,
): boolean {
  if (filters.category && row.orderType !== filters.category) return false
  if (filters.status && row.status !== filters.status) return false
  const query = filters.query.trim().toLocaleLowerCase()
  return !query || row.item.toLocaleLowerCase().includes(query)
}

export function hasMedicalOrderFilters(filters: MedicalOrderFilters): boolean {
  return Boolean(filters.category || filters.status || filters.query.trim())
}
