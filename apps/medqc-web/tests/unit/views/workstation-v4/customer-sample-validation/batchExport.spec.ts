import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  downloadBlob,
  EMPTY_EXPORT_BLOB_MESSAGE,
  HTML_EXPORT_MISMATCH_MESSAGE,
  JSON_EXPORT_ERROR_FALLBACK_MESSAGE,
  normalizeBatchExportBlob,
} from '@/views/workstation-v4/customer-sample-validation/batchExport'

async function readBlobAsUtf8(blob: Blob): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(blob, 'utf-8')
  })
}

describe('batchExport', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('对所有格式拒绝 0 字节空 Blob', async () => {
    const empty = new Blob([], { type: 'text/html' })
    await expect(normalizeBatchExportBlob(empty, 'html')).rejects.toThrow(EMPTY_EXPORT_BLOB_MESSAGE)
    await expect(normalizeBatchExportBlob(empty, 'xlsx')).rejects.toThrow(EMPTY_EXPORT_BLOB_MESSAGE)
    await expect(normalizeBatchExportBlob(empty, 'csv')).rejects.toThrow(EMPTY_EXPORT_BLOB_MESSAGE)
  })

  it('拒绝 application/json 错误响应并解码后端报错文案', async () => {
    const jsonError = new Blob([JSON.stringify({ message: '任务尚未完成，暂不可导出' })], {
      type: 'application/json;charset=utf-8',
    })
    await expect(normalizeBatchExportBlob(jsonError, 'xlsx')).rejects.toThrow(
      '任务尚未完成，暂不可导出',
    )
    await expect(normalizeBatchExportBlob(jsonError, 'html')).rejects.toThrow(
      '任务尚未完成，暂不可导出',
    )

    const detailError = new Blob([JSON.stringify({ detail: '导出权限不足' })], {
      type: 'application/problem+json',
    })
    await expect(normalizeBatchExportBlob(detailError, 'csv')).rejects.toThrow('导出权限不足')

    const badJson = new Blob(['{not-json'], { type: 'application/json' })
    await expect(normalizeBatchExportBlob(badJson, 'xlsx')).rejects.toThrow(
      JSON_EXPORT_ERROR_FALLBACK_MESSAGE,
    )
  })

  it('HTML 导出校验 ZIP/Excel 错配并保留 UTF-8 BOM', async () => {
    const zipBlob = new Blob(['PK\x03\x04fake-xlsx'], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    await expect(normalizeBatchExportBlob(zipBlob, 'html')).rejects.toThrow(
      HTML_EXPORT_MISMATCH_MESSAGE,
    )

    const htmlBlob = new Blob(['<html><body>报告</body></html>'], { type: 'text/html' })
    const normalized = await normalizeBatchExportBlob(htmlBlob, 'html')
    expect(normalized.type).toBe('text/html;charset=utf-8')
    expect(await readBlobAsUtf8(normalized)).toBe('<html><body>报告</body></html>')
    expect(normalized.size).toBe(htmlBlob.size + 3)
  })

  it('downloadBlob 延迟 1000ms 再释放 ObjectURL', () => {
    vi.useFakeTimers()
    const createObjectURL = vi.fn(() => 'blob:mock-url')
    const revokeObjectURL = vi.fn()
    Object.defineProperty(window, 'URL', {
      value: { createObjectURL, revokeObjectURL },
      configurable: true,
    })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    downloadBlob(new Blob(['ok'], { type: 'text/plain' }), 'report.html')

    expect(createObjectURL).toHaveBeenCalledTimes(1)
    expect(clickSpy).toHaveBeenCalledTimes(1)
    expect(revokeObjectURL).not.toHaveBeenCalled()

    vi.advanceTimersByTime(999)
    expect(revokeObjectURL).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
  })
})
