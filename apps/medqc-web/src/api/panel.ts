/**
 * 演示面板 API
 *
 * 提供事中监控、质控消息、事后分析等面板数据接口。
 * 使用原生 fetch，与项目其他 API 模块保持一致。
 */

const API_PREFIX = '/api/v1/panel'

// ==================== 类型定义 ====================

export type MonitoringLevel = 'info' | 'warning' | 'critical'

export interface MonitoringControlTip {
    title: string
    indicator: string
    current_value: string
    target_value: string
    suggestion: string
    level: MonitoringLevel
}

export interface DrgAlert {
    id: number
    case_no: string
    dept: string
    diagnosis: string
    drg: string
    ratio: number
    status: 'warning' | 'normal'
    los: number
    est_cost: number
    baseline_payment: number
    actual_cost: number
    payment_gap: number
    monitor_level: MonitoringLevel
    control_tip: string
}

export interface CmiTrend {
    labels: string[]
    values: number[]
    benchmark: number
}

export interface DeptCostIndex {
    departments: string[]
    values: number[]
    benchmark: number
}

export interface MonitoringStats {
    total_alerts: number
    severe_alerts: number
    pending_suggestions: number
    today_new: number
    simulated_groups: number
    control_threshold: number
    mock_scope_note: string
    control_tips: MonitoringControlTip[]
}

export interface QCMessageSummary {
    total: number
    by_severity: Record<string, number>
    by_category: Record<string, number>
    unread: number
    today_new: number
}

export interface QCMessage {
    id: string
    title: string
    severity: string
    category: string
    patient_name: string
    dept: string
    created_at: string
    is_read: boolean
}

export interface KpiItem {
    name: string
    value: number
    unit: string
    trend: string
    trend_type: 'up' | 'down'
}

export interface PostAnalysisReport {
    summary: {
        period: string
        total_cases: number
        total_drg_groups: number
        avg_los: number
        cmi: number
    }
    drg_distribution: Array<{
        drg: string
        name: string
        count: number
        avg_cost: number
    }>
    ai_insights: string[]
}

// ==================== 辅助函数 ====================

async function fetchJson<T>(url: string): Promise<T> {
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json' }
    })
    if (!response.ok) {
        throw new Error(`API请求失败: ${response.status} ${response.statusText}`)
    }
    const result = await response.json()
    return result?.data ?? result
}

// ==================== API 接口 ====================

export const panelApi = {
    // ---- P5: 质控消息概览 ----

    /** 获取质控消息统计摘要 */
    async getMessageSummary(): Promise<QCMessageSummary> {
        return fetchJson<QCMessageSummary>(`${API_PREFIX}/messages/summary`)
    },

    /** 获取质控消息列表 */
    async getMessages(page = 1, limit = 20): Promise<{ items: QCMessage[]; total: number }> {
        return fetchJson(`${API_PREFIX}/messages?page=${page}&limit=${limit}`)
    },

    // ---- P7: 事中监控 ----

    /** 获取 DRG 预警列表 */
    async getDrgAlerts(): Promise<DrgAlert[]> {
        return fetchJson<DrgAlert[]>(`${API_PREFIX}/monitoring/alerts`)
    },

    /** 获取 CMI 趋势数据 */
    async getCmiTrend(days = 7): Promise<CmiTrend> {
        return fetchJson<CmiTrend>(`${API_PREFIX}/monitoring/cmi-trend?days=${days}`)
    },

    /** 获取各科室费用消耗指数 */
    async getDeptCostIndex(): Promise<DeptCostIndex> {
        return fetchJson<DeptCostIndex>(`${API_PREFIX}/monitoring/cost-index`)
    },

    /** 获取事中监控统计卡片数据 */
    async getMonitoringStats(): Promise<MonitoringStats> {
        return fetchJson<MonitoringStats>(`${API_PREFIX}/monitoring/stats`)
    },

    // ---- P8: 事后分析 ----

    /** 获取事后分析 KPI 卡片 */
    async getPostAnalysisKpis(): Promise<KpiItem[]> {
        return fetchJson<KpiItem[]>(`${API_PREFIX}/analysis/kpis`)
    },

    /** 获取事后分析报告 */
    async getPostAnalysisReport(): Promise<PostAnalysisReport> {
        return fetchJson<PostAnalysisReport>(`${API_PREFIX}/analysis/report`)
    },
}

export default panelApi
