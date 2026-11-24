export const HTML_EXPORT_MISMATCH_MESSAGE =
  '后端未返回 HTML 明细文件，请确认客户机后端已更新到支持 HTML 导出的版本。'

export const EMPTY_EXPORT_BLOB_MESSAGE = '导出文件为空，请稍后重试。'
export const JSON_EXPORT_ERROR_FALLBACK_MESSAGE = '导出失败，后端返回了错误响应。'

function extractJsonErrorMessage(text: string): string {
  try {
    const parsed = JSON.parse(text) as Record<string, unknown>
    const nestedData =
      typeof parsed?.data === 'object' && parsed.data !== null
        ? (parsed.data as Record<string, unknown>)
        : null
    const candidates = [
      parsed?.message,
      parsed?.detail,
      parsed?.error,
      nestedData?.message,
      nestedData?.detail,
    ]
    for (const candidate of candidates) {
      if (typeof candidate === 'string' && candidate.trim()) {
        return candidate.trim()
      }
    }
  } catch {
    // Non-JSON payload falls back to default message.
  }
  return ''
}

async function readBlobText(blob: Blob): Promise<string> {
  if (typeof blob.text === 'function') {
    return blob.text()
  }
  if (typeof FileReader !== 'undefined') {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
      reader.onerror = () => reject(reader.error || new Error('读取导出文件失败'))
      reader.readAsText(blob, 'utf-8')
    })
  }
  return new Response(blob).text()
}

export async function normalizeBatchExportBlob(
  blob: Blob,
  format: 'xlsx' | 'csv' | 'html',
): Promise<Blob> {
  if (!blob || blob.size <= 0) {
    throw new Error(EMPTY_EXPORT_BLOB_MESSAGE)
  }
  const contentType = String(blob.type || '').toLowerCase()
  if (contentType.includes('application/json') || contentType.includes('+json')) {
    const text = await readBlobText(blob)
    throw new Error(extractJsonErrorMessage(text) || JSON_EXPORT_ERROR_FALLBACK_MESSAGE)
  }
  if (format !== 'html') return blob
  if (
    contentType.includes('spreadsheet') ||
    contentType.includes('officedocument') ||
    contentType.includes('zip')
  ) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  const preview = await readBlobText(blob.slice(0, 96))
  if (/^\s*PK/u.test(preview) || preview.includes('[Content_Types].xml')) {
    throw new Error(HTML_EXPORT_MISMATCH_MESSAGE)
  }
  const text = await readBlobText(blob)
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
  window.setTimeout(() => {
    window.URL.revokeObjectURL(url)
  }, 1000)
}
