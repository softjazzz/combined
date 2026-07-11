export const HTML_EXPORT_MISMATCH_MESSAGE =
  '后端未返回 HTML 明细文件，请确认客户机后端已更新到支持 HTML 导出的版本。'

export async function normalizeBatchExportBlob(
  blob: Blob,
  format: 'xlsx' | 'csv' | 'html',
): Promise<Blob> {
  if (format !== 'html') return blob
  const contentType = String(blob.type || '').toLowerCase()
  if (
    contentType.includes('spreadsheet') ||
    contentType.includes('officedocument') ||
    contentType.includes('zip')
  ) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  if (blob.size <= 0) {
    return new Blob([], { type: 'text/html;charset=utf-8' })
  }
  const preview = await blob.slice(0, 96).text()
  if (/^\s*PK/u.test(preview) || preview.includes('[Content_Types].xml')) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  const text = await blob.text()
  return new Blob([text.startsWith('\ufeff') ? text : `\ufeff${text}`], {
    type: 'text/html;charset=utf-8',
  })
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}
