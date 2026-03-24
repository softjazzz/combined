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

export type DrgExportFormat = 'excel' | 'pdf' | 'word'

export interface DrgReportSection {
  title: string
  columns: string[]
  rows: Array<Array<string | number>>
}

export interface DrgMockExportPayload {
  title: string
  filenameBase: string
  meta: Array<[string, string]>
  kpis?: Array<[string, string]>
  sections?: DrgReportSection[]
}

function downloadBlob(filename: string, blob: Blob) {
  const downloadUrl = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = downloadUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(downloadUrl)
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function exportExcel(payload: DrgMockExportPayload) {
  void (async () => {
    const XLSX = await loadXlsxModule()
    const wb = XLSX.utils.book_new()
    const summaryRows: Array<Array<string>> = [['项目', '值']]
    summaryRows.push(...payload.meta.map(([k, v]) => [k, v]))
    if (payload.kpis?.length) {
      summaryRows.push(['', ''])
      summaryRows.push(...payload.kpis.map(([k, v]) => [k, v]))
    }
    const summarySheet = XLSX.utils.aoa_to_sheet(summaryRows)
    XLSX.utils.book_append_sheet(wb, summarySheet, '概览')

    payload.sections?.forEach((section, index) => {
      const sheet = XLSX.utils.aoa_to_sheet([section.columns, ...section.rows])
      XLSX.utils.book_append_sheet(wb, sheet, `${index + 1}-${section.title}`.slice(0, 31))
    })

    const arrayBuffer = XLSX.write(wb, { bookType: 'xlsx', type: 'array' })
    const blob = new Blob([arrayBuffer], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    })
    downloadBlob(`${payload.filenameBase}.xlsx`, blob)
  })().catch((error) => {
    console.error('[drgMockExport:excel] failed', error)
  })
  
}

function exportPdf(payload: DrgMockExportPayload) {
  void (async () => {
    const { jsPDF, autoTable } = await loadPdfDeps()
    const doc = new jsPDF({ unit: 'pt', format: 'a4' })
    doc.setFontSize(14)
    doc.text(payload.title, 40, 44)
    doc.setFontSize(10)

    const metaRows = payload.meta.map(([k, v]) => [k, v])
    autoTable(doc, {
      startY: 58,
      head: [['项目', '值']],
      body: metaRows,
      styles: { fontSize: 9 }
    })

    if (payload.kpis?.length) {
      autoTable(doc, {
        startY: (doc as any).lastAutoTable.finalY + 12,
        head: [['指标', '值']],
        body: payload.kpis.map(([k, v]) => [k, v]),
        styles: { fontSize: 9 }
      })
    }

    payload.sections?.forEach((section) => {
      autoTable(doc, {
        startY: (doc as any).lastAutoTable.finalY + 14,
        head: [section.columns],
        body: section.rows,
        styles: { fontSize: 8 },
        didDrawPage: (data) => {
          if (data.cursor) {
            doc.setFontSize(11)
            doc.text(section.title, 40, data.cursor.y - 8)
            doc.setFontSize(10)
          }
        }
      })
    })

    const blob = doc.output('blob')
    downloadBlob(`${payload.filenameBase}.pdf`, blob)
  })().catch((error) => {
    console.error('[drgMockExport:pdf] failed', error)
  })
}

function exportWord(payload: DrgMockExportPayload) {
  const metaHtml = payload.meta
    .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(v)}</td></tr>`)
    .join('')
  const kpiHtml = (payload.kpis || [])
    .map(([k, v]) => `<tr><td>${escapeHtml(k)}</td><td>${escapeHtml(v)}</td></tr>`)
    .join('')
  const sectionHtml = (payload.sections || [])
    .map((section) => {
      const head = section.columns.map((col) => `<th>${escapeHtml(String(col))}</th>`).join('')
      const rows = section.rows
        .map((row) => `<tr>${row.map((col) => `<td>${escapeHtml(String(col))}</td>`).join('')}</tr>`)
        .join('')
      return `<h3>${escapeHtml(section.title)}</h3><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`
    })
    .join('')

  const html = `<!doctype html><html><head><meta charset="utf-8" />
  <style>
  body{font-family:Microsoft YaHei,Arial,sans-serif;font-size:12px;line-height:1.6;padding:20px;}
  h1{font-size:18px;margin:0 0 12px;}
  h2{font-size:14px;margin:16px 0 8px;}
  h3{font-size:13px;margin:14px 0 6px;}
  table{border-collapse:collapse;width:100%;margin-bottom:12px;}
  th,td{border:1px solid #d1d5db;padding:6px 8px;text-align:left;vertical-align:top;}
  th{background:#f8fafc;}
  </style></head><body>
  <h1>${escapeHtml(payload.title)}</h1>
  <h2>导出信息</h2><table><thead><tr><th>项目</th><th>值</th></tr></thead><tbody>${metaHtml}</tbody></table>
  <h2>核心指标</h2><table><thead><tr><th>指标</th><th>值</th></tr></thead><tbody>${kpiHtml}</tbody></table>
  ${sectionHtml}
  </body></html>`

  const blob = new Blob([html], { type: 'application/msword;charset=utf-8' })
  downloadBlob(`${payload.filenameBase}.doc`, blob)
}

export function exportDrgMockReport(format: DrgExportFormat, payload: DrgMockExportPayload) {
  if (format === 'excel') {
    exportExcel(payload)
    return
  }
  if (format === 'pdf') {
    exportPdf(payload)
    return
  }
  exportWord(payload)
}
