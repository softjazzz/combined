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

// 模拟延时
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * 获取统计概览数据 (Mock)
 */
export async function getStatisticsOverview(): Promise<StatisticsOverview> {
  await delay(800)
  
  return {
    totalRecords: 12458,
    pendingRecords: 125,
    analyzingRecords: 45,
    completedRecords: 12288,
    averageScore: 87.5,
    passRate: 94.2,
    todayUploads: 156,
    weeklyTrend: '+12.5%'
  }
}

/**
 * 获取趋势数据 (Mock)
 */
export async function getTrendData(period: 'week' | 'month' | 'quarter' = 'month'): Promise<TrendData[]> {
  await delay(1000)
  
  const data: TrendData[] = []
  
  if (period === 'week') {
    const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    days.forEach(day => {
      data.push({
        period: day,
        recordCount: Math.floor(Math.random() * 50) + 100,
        averageScore: 85 + Math.random() * 10,
        passRate: 90 + Math.random() * 8
      })
    })
  } else if (period === 'month') {
    const months = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
    months.forEach(month => {
      data.push({
        period: month,
        recordCount: Math.floor(Math.random() * 500) + 1000,
        averageScore: 86 + Math.random() * 8,
        passRate: 92 + Math.random() * 6
      })
    })
  } else {
    const quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    quarters.forEach(q => {
      data.push({
        period: q,
        recordCount: Math.floor(Math.random() * 1500) + 3000,
        averageScore: 88 + Math.random() * 6,
        passRate: 93 + Math.random() * 5
      })
    })
  }
  
  // 格式化数据保留一位小数
  return data.map(item => ({
    ...item,
    averageScore: parseFloat(item.averageScore.toFixed(1)),
    passRate: parseFloat(item.passRate.toFixed(1))
  }))
}

/**
 * 获取部门统计数据 (Mock)
 */
export async function getDepartmentStats(): Promise<DepartmentStats[]> {
  await delay(800)
  
  const departments = [
    { name: '心血管内科', count: 1245, score: 92.5, pass: 98.2 },
    { name: '呼吸内科', count: 986, score: 88.4, pass: 94.5 },
    { name: '普外科', count: 856, score: 86.2, pass: 91.8 },
    { name: '骨科', count: 745, score: 85.8, pass: 90.5 },
    { name: '神经内科', count: 654, score: 89.5, pass: 95.2 },
    { name: '妇产科', count: 542, score: 87.2, pass: 92.8 },
    { name: '儿科', count: 423, score: 90.1, pass: 96.4 }
  ]
  
  const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96']
  
  return departments.map((dept, index) => ({
    department: dept.name,
    recordCount: dept.count,
    averageScore: dept.score,
    passRate: dept.pass,
    color: colors[index % colors.length]
  }))
}

/**
 * 获取质控评分分布 (Mock)
 */
export async function getQCScoreDistribution(): Promise<QCScoreDistribution[]> {
  await delay(600)
  
  return [
    { scoreRange: '90-100分', count: 5420, percentage: 43.5 },
    { scoreRange: '80-89分', count: 4250, percentage: 34.1 },
    { scoreRange: '70-79分', count: 1850, percentage: 14.8 },
    { scoreRange: '60-69分', count: 650, percentage: 5.2 },
    { scoreRange: '60分以下', count: 288, percentage: 2.4 }
  ]
}

/**
 * 获取质控问题统计 (Mock)
 */
export async function getQCIssueStats(): Promise<QCIssueStats[]> {
  await delay(700)
  
  return [
    { category: '病案首页', issueCount: 452, percentage: 28.5 },
    { category: '入院记录', issueCount: 385, percentage: 24.3 },
    { category: '病程记录', issueCount: 320, percentage: 20.2 },
    { category: '医嘱单', issueCount: 210, percentage: 13.2 },
    { category: '出院记录', issueCount: 145, percentage: 9.1 },
    { category: '其他', issueCount: 74, percentage: 4.7 }
  ]
}

/**
 * 获取仪表板卡片数据 (Mock)
 */
export async function getDashboardCards(): Promise<DashboardCard[]> {
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
}

/**
 * 导出统计报表 (Mock)
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
