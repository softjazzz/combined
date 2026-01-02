import type { CaseFrontPage, DRGGroupingResult, CodingSuggestionItem } from '@/types/drg'

export type ListTabKey = 'loss' | 'highRate' | 'base' | 'better' | 'ungrouped'
export type GroupingStatus = 'grouped' | 'ungrouped'

export interface FeeMonitoringRow extends CaseFrontPage {
    grouping?: DRGGroupingResult | null
    groupingStatus: GroupingStatus
    baselinePayment?: number | null
    actualCost: number
    costRate?: number | null
    profitMargin?: number | null
    suggestions?: CodingSuggestionItem[]
    department?: string
    admitAt?: string
    dischargeAt?: string
    selfPay?: number
    isBaseGroup?: boolean | null
    settlementType?: string
    settlementMethod?: string
    ungroupedReason?: string
    fixSuggestion?: string
}

export type ActiveDrawerTab = 'basic' | 'feeDetail' | 'fix'
