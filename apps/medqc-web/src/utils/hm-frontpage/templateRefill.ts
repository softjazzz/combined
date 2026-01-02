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
 * - 一期仅做“写值”，不实现 hm_editor 的交互能力（searchbox 联想、timebox 弹窗等）
 */
export function applyDeValuesToHmTemplateBody(
  bodyHtml: string,
  valuesByDeCode: Record<string, DeValue>
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

  return body.outerHTML
}

export function buildHmTemplateSrcdoc(params: {
  filledBodyHtml: string
  contentsCss: string
  printCss: string
}): string {
  const { filledBodyHtml, contentsCss, printCss } = params

  return `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <style>${contentsCss}</style>
    <style>${printCss}</style>
  </head>
  ${filledBodyHtml}
</html>`
}

