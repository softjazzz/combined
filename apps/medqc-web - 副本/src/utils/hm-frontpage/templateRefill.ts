export type DeValue = string | number | null | undefined

function toText(value: DeValue): string {
  if (value === null || value === undefined) return ''
  return String(value)
}

function setTextContent(element: Element, value: DeValue) {
  const text = toText(value)
  const newTextboxContent = element.querySelector('.new-textbox-content')
  if (newTextboxContent) {
    newTextboxContent.textContent = text
    return
  }
  element.textContent = text
}

/**
 * 将 `data-hm-code="DE..."` 对应的值回填到 HM 模板 HTML 中。
 *
 * 约束：
 * - 输入模板通常是 `<body ...>...</body>` 片段（来自 hm_editor 的 `inpatient_record.html`）
 * - 一期仅做"写值"，不实现 hm_editor 的交互能力（searchbox 联想、timebox 弹窗等）
 */
export function applyDeValuesToHmTemplateBody(
  bodyHtml: string,
  valuesByDeCode: Record<string, DeValue>,
  diagnosisRows?: Array<{ name?: string; code?: string }>,
  procedureRows?: Array<{ name?: string; code?: string }>
): string {
  const parser = new DOMParser()
  const doc = parser.parseFromString(`<!doctype html><html>${bodyHtml}</html>`, 'text/html')
  const body = doc.querySelector('body')
  if (!body) return bodyHtml

  for (const [deCode, rawValue] of Object.entries(valuesByDeCode)) {
    if (!deCode) continue
    const target = body.querySelector(`[data-hm-code="${CSS.escape(deCode)}"]`)
    if (!target) continue

    const hmNode = target.getAttribute('data-hm-node')
    switch (hmNode) {
      case 'newtextbox':
      case 'searchbox':
      case 'timebox':
        setTextContent(target, rawValue)
        break
      default:
        setTextContent(target, rawValue)
        break
    }
  }

  // 填充其他诊断表格行（模板中诊断行没有 data-hm-code 元素，需要按行索引填充空白单元格）
  if (diagnosisRows && diagnosisRows.length > 0) {
    fillDiagnosisTableRows(body, diagnosisRows)
  }

  // 填充其他手术/操作表格行
  if (procedureRows && procedureRows.length > 0) {
    fillProcedureTableRows(body, procedureRows)
  }

  return body.outerHTML
}

/**
 * 填充出院诊断表格中的其他诊断行。
 *
 * 诊断表的布局：诊断表有左右两栏共 8 列
 * - 左4列: 出院诊断名称 | 疾病编码 | 入院情况 | 出院情况
 * - 右4列: 出院诊断名称 | 疾病编码 | 入院情况 | 出院情况
 *
 * 第一行是表头行（出院诊断 | 疾病编码 | ...）
 * 第二行是主要诊断行（有 data-hm-code 标记）
 * 第三行起是空行（左侧对应其他诊断 1-10，右侧对应 11-21）
 *
 * 我们通过定位包含"主要诊断:"标签的表格来找到诊断表。
 */
function fillDiagnosisTableRows(body: Element, rows: Array<{ name?: string; code?: string }>) {
  // 找到诊断表格：包含"主要诊断:"标签的表格
  const allTables = body.querySelectorAll('table[data-hm-table]')
  let diagTable: Element | null = null

  for (const table of allTables) {
    const mainDiagLabel = table.querySelector('[data-hm-name="主要诊断:"]')
    if (mainDiagLabel) {
      diagTable = table
      break
    }
  }

  if (!diagTable) return

  const tbody = diagTable.querySelector('tbody')
  if (!tbody) return

  const tableRows = tbody.querySelectorAll('tr')
  // 跳过第0行(表头)和第1行(主要诊断行)
  // 第2行起：左侧其他诊断1，右侧其他诊断11
  // 第3行起：左侧其他诊断2，右侧其他诊断12
  // ...
  // 最多10行（其他诊断1-10在左侧，11-20在右侧），加额外的入院病情/出院情况说明行

  for (let i = 0; i < rows.length && i < 20; i++) {
    const diag = rows[i]
    if (!diag.name && !diag.code) continue

    let rowIdx: number
    let colOffset: number

    if (i < 10) {
      // 左侧: 第 (i+2) 行，前两列（col 0 = 诊断名称, col 1 = 疾病编码）
      rowIdx = i + 2
      colOffset = 0
    } else {
      // 右侧: 第 (i-10+2) 行，后面的列（col 4 = 诊断名称, col 5 = 疾病编码）
      rowIdx = i - 10 + 2
      colOffset = 4
    }

    if (rowIdx >= tableRows.length) continue
    const tr = tableRows[rowIdx]
    const cells = tr.querySelectorAll('td')

    // 左侧填写诊断名称
    if (diag.name && cells[colOffset]) {
      const cell = cells[colOffset]
      // 如果单元格有 searchbox，用 setTextContent 填充
      const searchbox = cell.querySelector('[data-hm-node="searchbox"]')
      if (searchbox) {
        setTextContent(searchbox, diag.name)
      } else {
        // 直接设置单元格文本（保留 Unicode zero-width spaces）
        cell.textContent = `\u200B${diag.name}`
      }
    }

    // 疾病编码
    if (diag.code && cells[colOffset + 1]) {
      const cell = cells[colOffset + 1]
      const searchbox = cell.querySelector('[data-hm-node="searchbox"]')
      if (searchbox) {
        setTextContent(searchbox, diag.code)
      } else {
        cell.textContent = `\u200B${diag.code}`
      }
    }
  }
}

/**
 * 填充手术/操作表格中的其他手术行（第2行起）。
 * 手术表格通过包含"手术及操作名称"表头来定位。
 */
function fillProcedureTableRows(body: Element, rows: Array<{ name?: string; code?: string }>) {
  // 通过手术表头定位手术表格
  const allTables = body.querySelectorAll('table[data-hm-table]')
  let surgeryTable: Element | null = null

  for (const table of allTables) {
    const headerLabel = table.querySelector('[data-hm-name="手术及操作名称"]')
    if (headerLabel) {
      surgeryTable = table
      break
    }
  }

  if (!surgeryTable) return

  const tbody = surgeryTable.querySelector('tbody')
  if (!tbody) return

  const tableRows = tbody.querySelectorAll('tr')
  // 手术表格：前2行是表头行，第2行起是手术数据行（第一行已通过 DE code 填充主手术）
  // 从第3行起填充其他手术

  for (let i = 0; i < rows.length; i++) {
    const proc = rows[i]
    if (!proc.name && !proc.code) continue

    const rowIdx = i + 3 // 跳过2行表头 + 1行主手术
    if (rowIdx >= tableRows.length) continue

    const tr = tableRows[rowIdx]
    const cells = tr.querySelectorAll('td')

    // col 1 = 编码, col 4 = 名称（根据手术表结构）
    if (proc.code && cells[1]) {
      const searchbox = cells[1].querySelector('[data-hm-node="searchbox"]')
      if (searchbox) {
        setTextContent(searchbox, proc.code)
      } else {
        cells[1].textContent = `\u200B${proc.code}`
      }
    }
    if (proc.name && cells[4]) {
      const searchbox = cells[4].querySelector('[data-hm-node="searchbox"]')
      if (searchbox) {
        setTextContent(searchbox, proc.name)
      } else {
        cells[4].textContent = `\u200B${proc.name}`
      }
    }
  }
}

export function buildHmTemplateSrcdoc(params: {
  filledBodyHtml: string
  contentsCss: string
  printCss: string
}): string {
  const { filledBodyHtml, contentsCss, printCss } = params

  // Custom CSS to make filled values more visible
  const filledValuesCss = `
    /* 让回填的值更加清晰可见 */
    [data-hm-node="newtextbox"],
    [data-hm-node="searchbox"],
    [data-hm-node="timebox"],
    [data-hm-node="textboxwidget"],
    [data-hm-node="dropbox"],
    span.new-textbox-content,
    .new-textbox {
      color: #1a1a1a !important;
      font-weight: 500 !important;
    }
    
    /* 移除占位符样式，使用实际文本样式 */
    [_placeholdertext] {
      color: #1a1a1a !important;
    }
    
    /* 确保表格单元格中的文本清晰 */
    td[data-hm-code], 
    span[data-hm-code] {
      color: #1a1a1a !important;
    }
    
    /* 移除淡色背景，使用更清晰的样式 */
    span[data-hm-node="textboxwidget"],
    span[data-hm-node="newtextbox"],
    span[data-hm-node="searchbox"],
    span[data-hm-node="timebox"],
    span[data-hm-node="dropbox"] {
      background-color: transparent !important;
      background-image: none !important;
    }
  `

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>${contentsCss}</style>
    <style>${printCss}</style>
    <style>${filledValuesCss}</style>
  </head>
  ${filledBodyHtml}
</html>`
}
