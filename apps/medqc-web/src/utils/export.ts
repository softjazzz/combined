type XLSXModule = typeof import('xlsx')
type JsPdfCtor = typeof import('jspdf').default
type AutoTableFn = typeof import('jspdf-autotable').default

let xlsxModulePromise: Promise<XLSXModule> | null = null
let pdfDepsPromise: Promise<{ jsPDF: JsPdfCtor; autoTable: AutoTableFn }> | null = null

function loadXlsxModule() {
  if (!xlsxModulePromise) {
    xlsxModulePromise = import('xlsx')
  }
  return xlsxModulePromise
}

function loadPdfDeps() {
  if (!pdfDepsPromise) {
    pdfDepsPromise = Promise.all([import('jspdf'), import('jspdf-autotable')]).then(
      ([jspdfModule, autoTableModule]) => ({
        jsPDF: jspdfModule.default,
        autoTable: autoTableModule.default,
      })
    )
  }
  return pdfDepsPromise
}

function runExportTask(taskName: string, task: () => Promise<void>) {
  void task().catch((error) => {
    console.error(`[export:${taskName}] failed`, error)
  })
}

/**
 * 导出数据到 Excel 文件
 * @param data 要导出的数据数组 (JSON对象数组)
 * @param fileName 导出的文件名 (不含后缀)
 * @param sheetName 工作表名称
 * @param headerMap 表头映射 (key: data中的key, value: Excel表头名称)
 */
export function exportToExcel<T extends Record<string, any>>(
  data: T[],
  fileName: string,
  sheetName: string = 'Sheet1',
  headerMap?: Record<string, string>
) {
  runExportTask('excel-single-sheet', async () => {
    const XLSX = await loadXlsxModule()

    // 1. 处理表头映射
    let exportData = data
    if (headerMap) {
      exportData = data.map(item => {
        const newItem: Record<string, any> = {}
        for (const key in headerMap) {
          if (Object.prototype.hasOwnProperty.call(item, key)) {
            newItem[headerMap[key]] = item[key]
          } else {
            newItem[headerMap[key]] = item[key as keyof T] || ''
          }
        }
        return newItem
      }) as T[]
    }

    // 2. 创建工作簿和工作表
    const workSheet = XLSX.utils.json_to_sheet(exportData)
    const workBook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workBook, workSheet, sheetName)

    // 3. 生成并下载文件
    XLSX.writeFile(workBook, `${fileName}.xlsx`)
  })
}

/**
 * 导出多Sheet Excel文件
 * @param sheets 多个Sheet的数据配置
 * @param fileName 文件名
 */
export function exportMultiSheetExcel(
  sheets: { name: string; data: Record<string, any>[]; headerMap?: Record<string, string> }[],
  fileName: string
) {
  runExportTask('excel-multi-sheet', async () => {
    const XLSX = await loadXlsxModule()
    const workBook = XLSX.utils.book_new()

    sheets.forEach(sheet => {
      let exportData = sheet.data
      if (sheet.headerMap) {
        exportData = sheet.data.map(item => {
          const newItem: Record<string, any> = {}
          for (const key in sheet.headerMap) {
            newItem[sheet.headerMap[key]] = item[key] ?? ''
          }
          return newItem
        })
      }
      const workSheet = XLSX.utils.json_to_sheet(exportData)
      XLSX.utils.book_append_sheet(workBook, workSheet, sheet.name)
    })

    XLSX.writeFile(workBook, `${fileName}.xlsx`)
  })
}

/**
 * PDF报告数据接口
 */
export interface PDFReportData {
  title: string
  subtitle?: string
  generatedAt?: string
  overview?: { label: string; value: string | number }[]
  tables?: {
    title: string
    headers: string[]
    rows: (string | number)[][]
  }[]
  notes?: string[]
}

/**
 * 导出数据到 PDF 文件
 * @param reportData 报告数据
 * @param fileName 文件名
 */
export function exportToPDF(reportData: PDFReportData, fileName: string) {
  runExportTask('pdf', async () => {
    const { jsPDF, autoTable } = await loadPdfDeps()
    const doc = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4'
    })

    // 添加中文字体支持 - 使用内置字体
    doc.setFont('helvetica')

    let yPos = 20

    // 标题
    doc.setFontSize(18)
    doc.setTextColor(30, 41, 59) // slate-800
    doc.text(reportData.title, 105, yPos, { align: 'center' })
    yPos += 8

    // 副标题
    if (reportData.subtitle) {
      doc.setFontSize(11)
      doc.setTextColor(100, 116, 139) // slate-500
      doc.text(reportData.subtitle, 105, yPos, { align: 'center' })
      yPos += 6
    }

    // 生成时间
    doc.setFontSize(9)
    doc.setTextColor(148, 163, 184) // slate-400
    const timestamp = reportData.generatedAt || new Date().toLocaleString('zh-CN')
    doc.text(`Report Generated: ${timestamp}`, 105, yPos, { align: 'center' })
    yPos += 12

    // 概览数据
    if (reportData.overview && reportData.overview.length > 0) {
      doc.setFontSize(12)
      doc.setTextColor(30, 41, 59)
      doc.text('Overview', 14, yPos)
      yPos += 6

      const overviewRows = reportData.overview.map(item => [item.label, String(item.value)])
      autoTable(doc, {
        startY: yPos,
        head: [['Metric', 'Value']],
        body: overviewRows,
        theme: 'grid',
        headStyles: { fillColor: [29, 78, 216], textColor: 255, fontStyle: 'bold' },
        styles: { fontSize: 10, cellPadding: 3 },
        columnStyles: { 0: { fontStyle: 'bold' } },
        margin: { left: 14, right: 14 }
      })
      yPos = (doc as any).lastAutoTable.finalY + 10
    }

    // 数据表格
    if (reportData.tables && reportData.tables.length > 0) {
      reportData.tables.forEach(table => {
        // 检查是否需要新页
        if (yPos > 250) {
          doc.addPage()
          yPos = 20
        }

        doc.setFontSize(12)
        doc.setTextColor(30, 41, 59)
        doc.text(table.title, 14, yPos)
        yPos += 6

        autoTable(doc, {
          startY: yPos,
          head: [table.headers],
          body: table.rows.map(row => row.map(cell => String(cell))),
          theme: 'striped',
          headStyles: { fillColor: [99, 102, 241], textColor: 255, fontStyle: 'bold' },
          styles: { fontSize: 9, cellPadding: 2.5 },
          margin: { left: 14, right: 14 }
        })
        yPos = (doc as any).lastAutoTable.finalY + 10
      })
    }

    // 备注
    if (reportData.notes && reportData.notes.length > 0) {
      if (yPos > 260) {
        doc.addPage()
        yPos = 20
      }

      doc.setFontSize(10)
      doc.setTextColor(100, 116, 139)
      doc.text('Notes:', 14, yPos)
      yPos += 5

      doc.setFontSize(9)
      reportData.notes.forEach(note => {
        doc.text(`• ${note}`, 18, yPos)
        yPos += 4
      })
    }

    // 页脚
    const pageCount = doc.getNumberOfPages()
    for (let i = 1; i <= pageCount; i++) {
      doc.setPage(i)
      doc.setFontSize(8)
      doc.setTextColor(148, 163, 184)
      doc.text(`Page ${i} of ${pageCount}`, 105, 290, { align: 'center' })
      doc.text('MedQC DRG/DIP Analysis Platform', 14, 290)
    }

    doc.save(`${fileName}.pdf`)
  })
}

/**
 * 导出格式类型
 */
export type ExportFormat = 'excel' | 'pdf'

/**
 * 综合报告导出配置
 */
export interface ComprehensiveReportConfig {
  title: string
  dateRange: string
  dimension: string
  overview: { label: string; value: string | number }[]
  tableData: Record<string, any>[]
  tableHeaders: { key: string; label: string }[]
}

/**
 * 导出综合分析报告
 */
export function exportComprehensiveReport(
  config: ComprehensiveReportConfig,
  format: ExportFormat
) {
  const timestamp = new Date().toLocaleString('zh-CN')

  if (format === 'excel') {
    // Excel: 多Sheet导出
    const headerMap: Record<string, string> = {}
    config.tableHeaders.forEach(h => {
      headerMap[h.key] = h.label
    })

    const overviewData = config.overview.map(item => ({
      metric: item.label,
      value: item.value
    }))

    exportMultiSheetExcel([
      { name: 'Overview', data: overviewData, headerMap: { metric: 'Metric', value: 'Value' } },
      { name: 'Detail Data', data: config.tableData, headerMap }
    ], `${config.title}_${config.dateRange}`)

  } else if (format === 'pdf') {
    // PDF: 综合报告
    const tableRows = config.tableData.map(row =>
      config.tableHeaders.map(h => row[h.key] ?? '')
    )

    exportToPDF({
      title: config.title,
      subtitle: `Analysis Period: ${config.dateRange} | Dimension: ${config.dimension}`,
      generatedAt: timestamp,
      overview: config.overview,
      tables: [{
        title: 'Detailed Analysis Data',
        headers: config.tableHeaders.map(h => h.label),
        rows: tableRows
      }],
      notes: [
        'This report is auto-generated by MedQC DRG/DIP Analysis Platform.',
        'Cost Rate > 1.0 indicates potential over-spending.',
        'CMI (Case Mix Index) reflects case complexity.'
      ]
    }, `${config.title}_${config.dateRange}`)
  }
}
