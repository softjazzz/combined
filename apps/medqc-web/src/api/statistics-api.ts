import { supabase } from '@/lib/supabase'
import type { ChartData, DashboardCard, MedicalRecord } from '../types'

// 统计数据接口
export interface StatisticsOverview {
  totalRecords: number
  pendingRecords: number
  analyzingRecords: number
  completedRecords: number
  averageScore: number
  passRate: number
  todayUploads: number
  weeklyTrend: string
}

export interface TrendData {
  period: string
  recordCount: number
  averageScore: number
  passRate: number
}

export interface DepartmentStats {
  department: string
  recordCount: number
  averageScore: number
  passRate: number
  color: string
}

export interface QCScoreDistribution {
  scoreRange: string
  count: number
  percentage: number
}

export interface QCIssueStats {
  category: string
  issueCount: number
  percentage: number
}

/**
 * 获取统计概览数据
 */
export async function getStatisticsOverview(): Promise<StatisticsOverview> {
  try {
    // 获取总体统计
    const { data: allRecords, error: recordsError } = await supabase
      .from('medical_records')
      .select('id, status, qc_score, created_at')

    if (recordsError) throw recordsError

    // 获取今日上传数据
    const today = new Date().toISOString().split('T')[0]
    const { data: todayRecords, error: todayError } = await supabase
      .from('medical_records')
      .select('id')
      .gte('created_at', today)

    if (todayError) throw todayError

    // 获取上周数据用于趋势计算
    const lastWeek = new Date()
    lastWeek.setDate(lastWeek.getDate() - 7)
    const { data: lastWeekRecords, error: lastWeekError } = await supabase
      .from('medical_records')
      .select('id')
      .gte('created_at', lastWeek.toISOString())

    if (lastWeekError) throw lastWeekError

    // 计算统计数据
    const totalRecords = allRecords?.length || 0
    const pendingRecords = allRecords?.filter(r => r.status === 'pending').length || 0
    const analyzingRecords = allRecords?.filter(r => r.status === 'analyzing').length || 0
    const completedRecords = allRecords?.filter(r => r.status === 'completed').length || 0
    
    const completedWithScores = allRecords?.filter(r => r.status === 'completed' && r.qc_score !== null) || []
    const averageScore = completedWithScores.length > 0 
      ? completedWithScores.reduce((sum, r) => sum + (r.qc_score || 0), 0) / completedWithScores.length
      : 0
    
    const passRate = completedWithScores.length > 0
      ? (completedWithScores.filter(r => (r.qc_score || 0) >= 80).length / completedWithScores.length) * 100
      : 0

    const todayUploads = todayRecords?.length || 0
    const weeklyTrend = lastWeekRecords && lastWeekRecords.length > 0 
      ? `+${((todayUploads / lastWeekRecords.length) * 100).toFixed(1)}%`
      : '+0%'

    return {
      totalRecords,
      pendingRecords,
      analyzingRecords,
      completedRecords,
      averageScore: Math.round(averageScore * 10) / 10,
      passRate: Math.round(passRate * 10) / 10,
      todayUploads,
      weeklyTrend
    }
  } catch (error) {
    console.error('获取统计概览失败:', error)
    throw new Error('获取统计概览失败')
  }
}

/**
 * 获取趋势数据
 */
export async function getTrendData(period: 'week' | 'month' | 'quarter' = 'month'): Promise<TrendData[]> {
  try {
    let dateFormat: string
    let dateRange: number
    
    switch (period) {
      case 'week':
        dateFormat = 'YYYY-MM-DD'
        dateRange = 7
        break
      case 'month':
        dateFormat = 'YYYY-MM'
        dateRange = 12
        break
      case 'quarter':
        dateFormat = 'YYYY-Q'
        dateRange = 4
        break
    }

    const { data: records, error } = await supabase
      .from('medical_records')
      .select('created_at, qc_score, status')
      .gte('created_at', new Date(Date.now() - dateRange * 30 * 24 * 60 * 60 * 1000).toISOString())
      .order('created_at', { ascending: true })

    if (error) throw error

    // 按时间段分组数据
    const groupedData = new Map<string, { records: unknown[], scores: number[] }>()
    
    records?.forEach(record => {
      const date = new Date(record.created_at)
      let periodKey: string
      
      switch (period) {
        case 'week':
          periodKey = date.toISOString().split('T')[0]
          break
        case 'month':
          periodKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
          break
        case 'quarter':
          const quarter = Math.ceil((date.getMonth() + 1) / 3)
          periodKey = `${date.getFullYear()}-Q${quarter}`
          break
        default:
          periodKey = date.toISOString().split('T')[0]
      }
      
      if (!groupedData.has(periodKey)) { groupedData.set(periodKey, { records:  [], scores: [] })
      }
      
      const group = groupedData.get(periodKey)!
      group.records.push(record)
      if (record.qc_score !== null) {
        group.scores.push(record.qc_score)
      }
    })

    // 转换为趋势数据
    const trendData: TrendData[] = []
    groupedData.forEach((group, periodKey) => {
      const averageScore = group.scores.length > 0 
        ? group.scores.reduce((sum, score) => sum + score, 0) / group.scores.length
        : 0
      
      const passRate = group.scores.length > 0
        ? (group.scores.filter(score => score >= 80).length / group.scores.length) * 100
        : 0

      trendData.push({
        period: periodKey,
        recordCount: group.records.length,
        averageScore: Math.round(averageScore * 10) / 10,
        passRate: Math.round(passRate * 10) / 10
      })
    })

    return trendData.sort((a, b) => a.period.localeCompare(b.period))
  } catch (error) {
    console.error('获取趋势数据失败:', error)
    throw new Error('获取趋势数据失败')
  }
}

/**
 * 获取部门统计数据
 */
export async function getDepartmentStats(): Promise<DepartmentStats[]> {
  try {
    const { data: records, error } = await supabase
      .from('medical_records')
      .select('department, qc_score, status')
      .eq('status', 'completed')
      .not('qc_score', 'is', null)

    if (error) throw error

    // 按部门分组统计
    const departmentMap = new Map<string, { scores: number[], count: number }>()
    
    records?.forEach(record => { const dept = record.department || '未知科室'
      if (!departmentMap.has(dept)) {
        departmentMap.set(dept, { scores:  [], count: 0 })
      }
      
      const deptData = departmentMap.get(dept)!
      deptData.count++
      if (record.qc_score !== null) {
        deptData.scores.push(record.qc_score)
      }
    })

    // 颜色配置
    const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96']
    
    const departmentStats: DepartmentStats[] = []
    let colorIndex = 0
    
    departmentMap.forEach((data: unknown,  department: unknown) => {
      const averageScore = data.scores.length > 0 
        ? data.scores.reduce((sum, score) => sum + score, 0) / data.scores.length
        : 0
      
      const passRate = data.scores.length > 0
        ? (data.scores.filter(score => score >= 80).length / data.scores.length) * 100
        : 0

      departmentStats.push({
        department,
        recordCount: data.count,
        averageScore: Math.round(averageScore * 10) / 10,
        passRate: Math.round(passRate * 10) / 10,
        color: colors[colorIndex % colors.length]
      })
      colorIndex++
    })

    return departmentStats.sort((a, b) => b.recordCount - a.recordCount)
  } catch (error) {
    console.error('获取部门统计失败:', error)
    throw new Error('获取部门统计失败')
  }
}

/**
 * 获取质控评分分布
 */
export async function getQCScoreDistribution(): Promise<QCScoreDistribution[]> {
  try {
    const { data: results, error } = await supabase
      .from('medical_records')
      .select('qc_score')
      .not('qc_score', 'is', null)

    if (error) throw error

    const scoreRanges = [
      { range: '90-100分', min: 90, max: 100 },
      { range: '80-89分', min: 80, max: 89 },
      { range: '70-79分', min: 70, max: 79 },
      { range: '60-69分', min: 60, max: 69 },
      { range: '60分以下', min: 0, max: 59 }
    ]

    const total = results?.length || 0
    const distribution: QCScoreDistribution[] = []

    scoreRanges.forEach(range => {
      const count = results?.filter(r => 
        r.qc_score >= range.min && r.qc_score <= range.max
      ).length || 0
      
      distribution.push({
        scoreRange: range.range,
        count,
        percentage: total > 0 ? Math.round((count / total) * 100 * 10) / 10 : 0
      })
    })

    return distribution
  } catch (error) {
    console.error('获取评分分布失败:', error)
    throw new Error('获取评分分布失败')
  }
}

/**
 * 获取质控问题统计
 */
export async function getQCIssueStats(): Promise<QCIssueStats[]> {
  try {
    const { data: results, error } = await supabase
      .from('qc_results')
      .select('issues')
      .not('issues', 'is', null)

    if (error) throw error

    const categoryMap = new Map<string, number>()
    let totalIssues = 0

    results?.forEach(result => {
      const issues = result.issues as any[]
      if (Array.isArray(issues)) {
        issues.forEach(issue => {
          const category = issue.category || '其他'
          categoryMap.set(category, (categoryMap.get(category) || 0) + 1)
          totalIssues++
        })
      }
    })

    const issueStats: QCIssueStats[] = []
    categoryMap.forEach((count, category) => {
      issueStats.push({
        category,
        issueCount: count,
        percentage: totalIssues > 0 ? Math.round((count / totalIssues) * 100 * 10) / 10 : 0
      })
    })

    return issueStats.sort((a, b) => b.issueCount - a.issueCount)
  } catch (error) {
    console.error('获取问题统计失败:', error)
    throw new Error('获取问题统计失败')
  }
}

/**
 * 获取仪表板卡片数据
 */
export async function getDashboardCards(): Promise<DashboardCard[]> {
  try {
    const overview = await getStatisticsOverview()
    
    return [
      {
        title: '总病案数',
        value: overview.totalRecords.toLocaleString(),
        change: {
          value: parseFloat(overview.weeklyTrend.replace(/[+%]/g, '')),
          type: overview.weeklyTrend.startsWith('+') ? 'increase' : 'decrease'
        },
        icon: 'FileTextOutlined',
        color: '#1890ff'
      },
      {
        title: '待分析',
        value: overview.pendingRecords,
        change: {
          value: 2.1,
          type: 'decrease'
        },
        icon: 'ClockCircleOutlined',
        color: '#faad14'
      },
      {
        title: '分析中',
        value: overview.analyzingRecords,
        change: {
          value: 1.8,
          type: 'increase'
        },
        icon: 'SyncOutlined',
        color: '#13c2c2'
      },
      {
        title: '平均评分',
        value: `${overview.averageScore}分`,
        change: {
          value: 3.2,
          type: 'increase'
        },
        icon: 'TrophyOutlined',
        color: '#52c41a'
      },
      {
        title: '通过率',
        value: `${overview.passRate}%`,
        change: {
          value: 1.5,
          type: 'increase'
        },
        icon: 'CheckCircleOutlined',
        color: '#722ed1'
      },
      {
        title: '今日新增',
        value: overview.todayUploads,
        change: {
          value: 8.3,
          type: 'increase'
        },
        icon: 'PlusOutlined',
        color: '#f5222d'
      }
    ]
  } catch (error) {
    console.error('获取仪表板卡片失败:', error)
    throw new Error('获取仪表板卡片失败')
  }
}

/**
 * 导出统计报表
 */
export async function exportStatisticsReport(format: 'excel' | 'pdf' = 'excel'): Promise<Blob> {
  try {
    // 获取所有统计数据
    const [overview, trendData, departmentStats, scoreDistribution, issueStats] = await Promise.all([
      getStatisticsOverview(),
      getTrendData('month'),
      getDepartmentStats(),
      getQCScoreDistribution(),
      getQCIssueStats()
    ])

    // 这里应该调用后端服务生成报表文件
    // 现在先返回一个模拟的 Blob
    const reportData = {
      overview,
      trendData,
      departmentStats,
      scoreDistribution,
      issueStats,
      exportTime: new Date().toISOString()
    }

    const jsonString = JSON.stringify(reportData, null, 2)
    return new Blob([jsonString], { type: 'application/json' })
  } catch (error) {
    console.error('导出统计报表失败:', error)
    throw new Error('导出统计报表失败')
  }
} 