import * as XLSX from 'xlsx'
import { saveAs } from 'file-saver'
import type { 
  StatisticsOverview, 
  TrendData, 
  DepartmentStats, 
  QCScoreDistribution, 
  QCIssueStats 
} from '../api/statistics-api'

// 导出数据接口
export interface ExportData {
  overview: StatisticsOverview
  trendData: TrendData[]
  departmentStats: DepartmentStats[]
  scoreDistribution: QCScoreDistribution[]
  issueStats: QCIssueStats[]
  exportTime: string
}

/**
 * 导出Excel报表
 */
export async function exportToExcel(data: ExportData): Promise<void> {
  try {
    // 创建工作簿
    const workbook = XLSX.utils.book_new()

    // 1. 概览数据工作表
    const overviewData = [
      ['指标', '数值'],
      ['总病案数', data.overview.totalRecords],
      ['待分析病案', data.overview.pendingRecords],
      ['分析中病案', data.overview.analyzingRecords],
      ['已完成病案', data.overview.completedRecords],
      ['平均评分', `${data.overview.averageScore}分`],
      ['通过率', `${data.overview.passRate}%`],
      ['今日新增', data.overview.todayUploads],
      ['周增长趋势', data.overview.weeklyTrend]
    ]
    const overviewSheet = XLSX.utils.aoa_to_sheet(overviewData)
    XLSX.utils.book_append_sheet(workbook, overviewSheet, '统计概览')

    // 2. 趋势数据工作表
    const trendHeaders = ['时间期间', '病案数量', '平均评分', '通过率(%)']
    const trendRows = data.trendData.map(item => [
      item.period,
      item.recordCount,
      item.averageScore,
      item.passRate
    ])
    const trendData = [trendHeaders, ...trendRows]
    const trendSheet = XLSX.utils.aoa_to_sheet(trendData)
    XLSX.utils.book_append_sheet(workbook, trendSheet, '趋势分析')

    // 3. 部门统计工作表
    const departmentHeaders = ['科室', '病案数量', '平均评分', '通过率(%)']
    const departmentRows = data.departmentStats.map(item => [
      item.department,
      item.recordCount,
      item.averageScore,
      item.passRate
    ])
    const departmentData = [departmentHeaders, ...departmentRows]
    const departmentSheet = XLSX.utils.aoa_to_sheet(departmentData)
    XLSX.utils.book_append_sheet(workbook, departmentSheet, '部门统计')

    // 4. 评分分布工作表
    const scoreHeaders = ['评分区间', '数量', '占比(%)']
    const scoreRows = data.scoreDistribution.map(item => [
      item.scoreRange,
      item.count,
      item.percentage
    ])
    const scoreData = [scoreHeaders, ...scoreRows]
    const scoreSheet = XLSX.utils.aoa_to_sheet(scoreData)
    XLSX.utils.book_append_sheet(workbook, scoreSheet, '评分分布')

    // 5. 问题统计工作表
    const issueHeaders = ['问题类型', '问题数量', '占比(%)']
    const issueRows = data.issueStats.map(item => [
      item.category,
      item.issueCount,
      item.percentage
    ])
    const issueData = [issueHeaders, ...issueRows]
    const issueSheet = XLSX.utils.aoa_to_sheet(issueData)
    XLSX.utils.book_append_sheet(workbook, issueSheet, '问题统计')

    // 6. 导出信息工作表
    const exportInfo = [
      ['导出信息', ''],
      ['导出时间', new Date(data.exportTime).toLocaleString('zh-CN')],
      ['系统名称', '病案质控系统'],
      ['报表类型', '统计分析报表'],
      ['数据范围', '全部数据'],
      ['', ''],
      ['说明', ''],
      ['1. 平均评分满分为100分', ''],
      ['2. 通过率以80分为及格线计算', ''],
      ['3. 数据统计截止到导出时间', ''],
      ['4. 如有疑问请联系系统管理员', '']
    ]
    const exportSheet = XLSX.utils.aoa_to_sheet(exportInfo)
    XLSX.utils.book_append_sheet(workbook, exportSheet, '导出信息')

    // 设置列宽
    const setColumnWidth = (sheet: XLSX.WorkSheet, widths: number[]) => {
      const cols = widths.map(width => ({ wch: width }))
      sheet['!cols'] = cols
    }

    // 应用样式
    setColumnWidth(overviewSheet, [20, 15])
    setColumnWidth(trendSheet, [15, 12, 12, 12])
    setColumnWidth(departmentSheet, [15, 12, 12, 12])
    setColumnWidth(scoreSheet, [15, 10, 12])
    setColumnWidth(issueSheet, [15, 12, 12])
    setColumnWidth(exportSheet, [25, 20])

    // 生成文件
    const fileName = `质控统计报表_${new Date().toISOString().split('T')[0]}.xlsx`
    const excelBuffer = XLSX.write(workbook, { bookType: 'xlsx', type: 'array' })
    const blob = new Blob([excelBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    
    saveAs(blob, fileName)
  } catch (error) {
    console.error('Excel导出失败:', error)
    throw new Error('Excel导出失败')
  }
}

/**
 * 导出PDF报表（简化版本）
 */
export async function exportToPDF(data: ExportData): Promise<void> {
  try {
    // 创建HTML内容
    const htmlContent = generatePDFHTML(data)
    
    // 创建临时窗口用于打印
    const printWindow = window.open('', '_blank')
    if (!printWindow) {
      throw new Error('无法打开打印窗口')
    }

    printWindow.document.write(htmlContent)
    printWindow.document.close()
    
    // 等待内容加载完成
    printWindow.onload = () => {
      printWindow.print()
      printWindow.close()
    }
  } catch (error) {
    console.error('PDF导出失败:', error)
    throw new Error('PDF导出失败')
  }
}

/**
 * 生成PDF的HTML内容
 */
function generatePDFHTML(data: ExportData): string {
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>质控统计报表</title>
      <style>
        body {
          font-family: 'Microsoft YaHei', Arial, sans-serif;
          margin: 20px;
          line-height: 1.6;
          color: #333;
        }
        .header {
          text-align: center;
          margin-bottom: 30px;
          border-bottom: 2px solid #1890ff;
          padding-bottom: 10px;
        }
        .title {
          font-size: 24px;
          font-weight: bold;
          color: #1890ff;
          margin-bottom: 10px;
        }
        .export-info {
          font-size: 14px;
          color: #666;
        }
        .section {
          margin-bottom: 30px;
        }
        .section-title {
          font-size: 18px;
          font-weight: bold;
          color: #333;
          margin-bottom: 15px;
          border-left: 4px solid #1890ff;
          padding-left: 10px;
        }
        .overview-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 20px;
          margin-bottom: 20px;
        }
        .overview-item {
          background: #f8f9fa;
          padding: 15px;
          border-radius: 8px;
          text-align: center;
        }
        .overview-label {
          font-size: 14px;
          color: #666;
          margin-bottom: 5px;
        }
        .overview-value {
          font-size: 20px;
          font-weight: bold;
          color: #1890ff;
        }
        table {
          width: 100%;
          border-collapse: collapse;
          margin-bottom: 20px;
        }
        th, td {
          border: 1px solid #ddd;
          padding: 12px;
          text-align: left;
        }
        th {
          background-color: #f8f9fa;
          font-weight: bold;
          color: #333;
        }
        tr:nth-child(even) {
          background-color: #fafafa;
        }
        .footer {
          margin-top: 40px;
          padding-top: 20px;
          border-top: 1px solid #ddd;
          font-size: 12px;
          color: #666;
          text-align: center;
        }
        @media print {
          body { margin: 0; }
          .section { page-break-inside: avoid; }
        }
      </style>
    </head>
    <body>
      <div class="header">
        <div class="title">病案质控系统 - 统计分析报表</div>
        <div class="export-info">
          导出时间: ${new Date(data.exportTime).toLocaleString('zh-CN')}
        </div>
      </div>

      <div class="section">
        <div class="section-title">统计概览</div>
        <div class="overview-grid">
          <div class="overview-item">
            <div class="overview-label">总病案数</div>
            <div class="overview-value">${data.overview.totalRecords}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">平均评分</div>
            <div class="overview-value">${data.overview.averageScore}分</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">通过率</div>
            <div class="overview-value">${data.overview.passRate}%</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">待分析</div>
            <div class="overview-value">${data.overview.pendingRecords}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">分析中</div>
            <div class="overview-value">${data.overview.analyzingRecords}</div>
          </div>
          <div class="overview-item">
            <div class="overview-label">今日新增</div>
            <div class="overview-value">${data.overview.todayUploads}</div>
          </div>
        </div>
      </div>

      <div class="section">
        <div class="section-title">部门统计</div>
        <table>
          <thead>
            <tr>
              <th>科室</th>
              <th>病案数量</th>
              <th>平均评分</th>
              <th>通过率</th>
            </tr>
          </thead>
          <tbody>
            ${data.departmentStats.map(item => `
              <tr>
                <td>${item.department}</td>
                <td>${item.recordCount}</td>
                <td>${item.averageScore}分</td>
                <td>${item.passRate}%</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>

      <div class="section">
        <div class="section-title">评分分布</div>
        <table>
          <thead>
            <tr>
              <th>评分区间</th>
              <th>数量</th>
              <th>占比</th>
            </tr>
          </thead>
          <tbody>
            ${data.scoreDistribution.map(item => `
              <tr>
                <td>${item.scoreRange}</td>
                <td>${item.count}</td>
                <td>${item.percentage}%</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>

      <div class="section">
        <div class="section-title">问题类型统计</div>
        <table>
          <thead>
            <tr>
              <th>问题类型</th>
              <th>问题数量</th>
              <th>占比</th>
            </tr>
          </thead>
          <tbody>
            ${data.issueStats.map(item => `
              <tr>
                <td>${item.category}</td>
                <td>${item.issueCount}</td>
                <td>${item.percentage}%</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>

      <div class="footer">
        <p>本报表由病案质控系统自动生成 | 数据截止时间: ${new Date(data.exportTime).toLocaleString('zh-CN')}</p>
        <p>如有疑问请联系系统管理员</p>
      </div>
    </body>
    </html>
  `
}

/**
 * 导出CSV格式（部门统计）
 */
export async function exportToCSV(data: ExportData): Promise<void> {
  try {
    const csvContent = [
      // CSV头部
      '科室,病案数量,平均评分,通过率',
      // 数据行
      ...data.departmentStats.map(item => 
        `${item.department},${item.recordCount},${item.averageScore},${item.passRate}`
      )
    ].join('\n')

    // 添加BOM以支持中文
    const BOM = '\uFEFF'
    const blob = new Blob([BOM + csvContent], { type: 'text/csv;charset=utf-8' })
    const fileName = `部门统计_${new Date().toISOString().split('T')[0]}.csv`
    
    saveAs(blob, fileName)
  } catch (error) {
    console.error('CSV导出失败:', error)
    throw new Error('CSV导出失败')
  }
}

/**
 * 通用导出函数
 */
export async function exportReport(
  data: ExportData, 
  format: 'excel' | 'pdf' | 'csv' = 'excel'
): Promise<void> {
  switch (format) {
    case 'excel':
      await exportToExcel(data)
      break
    case 'pdf':
      await exportToPDF(data)
      break
    case 'csv':
      await exportToCSV(data)
      break
    default:
      throw new Error(`不支持的导出格式: ${format}`)
  }
} 