/**
 * 数据分析服务
 * 提供统一的数据分析API接口
 */

import { functionsClient } from './functionsClient'

// 类型定义
export interface DashboardKPIs {
  todayViolations: number
  yesterdayViolations: number
  activeRules: number
  severityBreakdown: {
    block: number
    warn: number
    info: number
  }
}

export interface TrendData {
  date: string
  block: number
  warn: number
  info: number
  total: number
  unique_visits: number
  unique_rules: number
  severity_rate: {
    block_rate: number
    warn_rate: number
    info_rate: number
  }
}

export interface TrendAnalysis {
  total_trend: {
    trend: 'increasing' | 'decreasing' | 'stable'
    slope: number
    correlation: number
    confidence: number
  }
  block_trend: any
  warn_trend: any
  moving_averages: {
    total_7day: number[]
    block_7day: number[]
    warn_7day: number[]
  }
  anomalies: {
    total_anomalies: number[]
    block_anomalies: number[]
    warn_anomalies: number[]
  }
  summary: {
    total_violations: number
    avg_daily_violations: number
    peak_day: string
    peak_violations: number
  }
}

export interface DepartmentStats {
  department_code: string
  department_name: string
  total_violations: number
  unique_visits: number
  unique_rules: number
  violation_rate: number
  risk_level: 'high' | 'medium' | 'low'
  severity_breakdown: {
    block: number
    warn: number
    info: number
  }
  trend: 'increasing' | 'decreasing' | 'stable'
  trend_change: number
  top_rules: Array<{
    code: string
    name: string
    count: number
  }>
}

export interface DoctorStats {
  doctor_code: string
  doctor_name: string
  department_code: string
  department_name: string
  total_violations: number
  unique_visits: number
  unique_rules: number
  violation_rate: number
  quality_score: number
  risk_level: 'high' | 'medium' | 'low'
  severity_breakdown: {
    block: number
    warn: number
    info: number
  }
  rule_types: Record<string, number>
  improvement_suggestions: string[]
  performance_grade: 'A' | 'B' | 'C' | 'D'
}

export interface AnomalyDetection {
  time_series: Array<{
    date: string
    violations: number
  }>
  anomalies: Array<{
    date: string
    violations: number
    z_score: number
    severity: 'high' | 'low'
  }>
  statistics: {
    mean: number
    std_dev: number
    min: number
    max: number
    total_anomalies: number
    anomaly_rate: number
  }
  parameters: {
    sensitivity_threshold: number
    days_analyzed: number
    detection_method: string
  }
}

export interface PredictionResult {
  predictions: Array<{
    date: string
    predicted_violations: number
    confidence_level: number
    trend?: string
    predicted_breakdown?: {
      block: number
      warn: number
      info: number
    }
    day_of_week?: number
  }>
  model_info: {
    type: string
    r_squared?: number
    slope?: number
    intercept?: number
    window_size?: number
    weekly_pattern?: Record<string, number>
    training_days: number
  }
  confidence: number
  historical_summary: {
    total_days: number
    avg_daily_violations: number
    max_daily_violations: number
    min_daily_violations: number
  }
}

export interface ReportTemplate {
  id: string
  name: string
  description: string
  type: 'violations' | 'departments' | 'doctors' | 'trends' | 'summary'
  fields: string[]
  defaultFormat: 'csv' | 'excel' | 'pdf'
  parameters: Record<string, any>
}

// 数据分析服务类
export class AnalyticsService {
  /**
   * 获取仪表盘KPI指标
   */
  static async getDashboardKPIs(): Promise<DashboardKPIs> {
    const response = await functionsClient.invoke('statistics', {
      path: 'dashboard'
    })
    
    if (response.error) {
      throw new Error(`获取仪表盘KPI失败: ${response.error.message}`)
    }
    
    return response.data.kpis
  }

  /**
   * 获取趋势分析数据
   */
  static async getTrendsAnalysis(params: {
    days?: number
    granularity?: 'day' | 'week' | 'month'
    includeAnalysis?: boolean
  } = {}): Promise<{
    trends: TrendData[]
    analysis?: TrendAnalysis
    metadata: any
  }> {
    const { days = 30, granularity = 'day', includeAnalysis = true } = params
    
    const response = await functionsClient.invoke('statistics', {
      path: 'trends',
      query: {
        days: days.toString(),
        granularity,
        analysis: includeAnalysis.toString()
      }
    })
    
    if (response.error) {
      throw new Error(`获取趋势分析失败: ${response.error.message}`)
    }
    
    return response.data
  }

  /**
   * 获取科室维度分析
   */
  static async getDepartmentAnalysis(params: {
    timeRange?: string
    includeComparison?: boolean
  } = {}): Promise<{
    departments: DepartmentStats[]
    summary: any
    comparison?: any
    metadata: any
  }> {
    const { timeRange = '30d', includeComparison = true } = params
    
    const response = await functionsClient.invoke('statistics', {
      path: 'departments',
      query: {
        range: timeRange,
        comparison: includeComparison.toString()
      }
    })
    
    if (response.error) {
      throw new Error(`获取科室分析失败: ${response.error.message}`)
    }
    
    return response.data
  }

  /**
   * 获取医生维度分析
   */
  static async getDoctorAnalysis(params: {
    timeRange?: string
    departmentCode?: string
    includeProfile?: boolean
  } = {}): Promise<{
    doctors: DoctorStats[]
    summary: any
    metadata: any
  }> {
    const { timeRange = '30d', departmentCode, includeProfile = true } = params
    
    const query: Record<string, string> = {
      range: timeRange,
      profile: includeProfile.toString()
    }
    
    if (departmentCode) {
      query.department = departmentCode
    }
    
    const response = await functionsClient.invoke('statistics', {
      path: 'doctors',
      query
    })
    
    if (response.error) {
      throw new Error(`获取医生分析失败: ${response.error.message}`)
    }
    
    return response.data
  }

  /**
   * 获取违规深度分析
   */
  static async getViolationAnalysis(params: {
    timeRange?: string
    groupBy?: 'rule_type' | 'severity'
  } = {}): Promise<any> {
    const { timeRange = '30d', groupBy = 'rule_type' } = params
    
    const response = await functionsClient.invoke('statistics', {
      path: 'violations-analysis',
      query: {
        range: timeRange,
        group_by: groupBy
      }
    })
    
    if (response.error) {
      throw new Error(`获取违规分析失败: ${response.error.message}`)
    }
    
    return response.data
  }

  /**
   * 异常检测
   */
  static async detectAnomalies(params: {
    days?: number
    sensitivity?: number
  } = {}): Promise<AnomalyDetection> {
    const { days = 30, sensitivity = 2.0 } = params
    
    const response = await functionsClient.invoke('statistics', {
      path: 'anomaly-detection',
      query: {
        days: days.toString(),
        sensitivity: sensitivity.toString()
      }
    })
    
    if (response.error) {
      throw new Error(`异常检测失败: ${response.error.message}`)
    }
    
    return response.data
  }

  /**
   * 预测分析
   */
  static async getPredictions(params: {
    timeRange?: string
    predictionDays?: number
    model?: 'linear' | 'moving_average' | 'seasonal'
  } = {}): Promise<PredictionResult> {
    const { timeRange = '90d', predictionDays = 7, model = 'linear' } = params
    
    const response = await functionsClient.invoke('statistics', {
      path: 'predictions',
      query: {
        range: timeRange,
        days: predictionDays.toString(),
        model
      }
    })
    
    if (response.error) {
      throw new Error(`预测分析失败: ${response.error.message}`)
    }
    
    return response.data
  }

  /**
   * 获取报表模板
   */
  static async getReportTemplates(): Promise<{
    templates: ReportTemplate[]
    total: number
  }> {
    const response = await functionsClient.invoke('data-export', {
      path: 'templates'
    })
    
    if (response.error) {
      throw new Error(`获取报表模板失败: ${response.error.message}`)
    }
    
    return response.data
  }

  /**
   * 生成报表
   */
  static async generateReport(params: {
    templateId: string
    format?: 'csv' | 'excel' | 'pdf'
    parameters?: Record<string, any>
    customFields?: string[]
  }): Promise<Blob> {
    const response = await functionsClient.invoke('data-export', {
      path: 'generate',
      method: 'POST',
      body: params
    })
    
    if (response.error) {
      throw new Error(`生成报表失败: ${response.error.message}`)
    }
    
    // 返回二进制数据作为 Blob
    return new Blob([response.data], {
      type: params.format === 'csv' ? 'text/csv' : 
            params.format === 'excel' ? 'application/vnd.ms-excel' : 
            'application/pdf'
    })
  }

  /**
   * 下载报表
   */
  static async downloadReport(
    templateId: string, 
    format: 'csv' | 'excel' | 'pdf' = 'excel',
    filename?: string
  ): Promise<void> {
    try {
      const blob = await this.generateReport({ templateId, format })
      
      // 创建下载链接
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename || `report_${templateId}_${new Date().toISOString().split('T')[0]}.${format}`
      
      // 触发下载
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      
      // 清理URL对象
      window.URL.revokeObjectURL(url)
    } catch (error) {
      throw new Error(`下载报表失败: ${error.message}`)
    }
  }
}

// 导出默认实例
export default AnalyticsService
