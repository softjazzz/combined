import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiService } from '@/services/apiService'
import {
  DOCUMENT_DEFINITION_IMPORT_MAX_BYTES,
  downloadDocumentDefinitionImportTemplate,
  importDocumentDefinitions,
  listDocumentDefinitions,
} from '@/api/documentDefinitions'

const definition = {
  id: 'definition-1', code: 'DOC-001', name: '入院记录', category: '住院文书',
  template_content: '主诉：', import_batch_id: 'batch-1', created_by: 'admin-1',
  created_at: '2026-09-28T12:00:00Z',
}

function response(data: unknown): AxiosResponse {
  return {
    status: 200, statusText: 'OK', data, headers: {},
    config: { headers: new AxiosHeaders() },
  }
}

function httpError(status: number, data: unknown) {
  return new AxiosError('failed', String(status), undefined, undefined, {
    status, statusText: 'failed', data, headers: {}, config: { headers: new AxiosHeaders() },
  })
}

describe('documentDefinitions API', () => {
  beforeEach(() => vi.restoreAllMocks())

  it('读取可信分页列表并透传页码', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({
      success: true, data: { items: [definition], total: 21, page: 2, page_size: 20 },
    }))
    const result = await listDocumentDefinitions({ page: 2, page_size: 20 })
    expect(result).toEqual({ success: true, data: { items: [definition], total: 21, page: 2, page_size: 20 } })
    expect(request).toHaveBeenCalledWith({
      method: 'GET', url: '/api/v1/document-definitions', params: { page: 2, page_size: 20 },
    })
  })

  it.each([
    { items: [definition], page: 1, page_size: 20 },
    { items: [definition], total: -1, page: 1, page_size: 20 },
    { items: [{ ...definition, template_content: 3 }], total: 1, page: 1, page_size: 20 },
  ])('列表回执缺失或错型时不伪造空列表：%j', async (payload) => {
    vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({ success: true, data: payload }))
    expect(await listDocumentDefinitions({ page: 1, page_size: 20 })).toMatchObject({
      success: false, message: expect.stringContaining('格式异常'),
    })
  })

  it('只接受有效 XLSX 模板 Blob', async () => {
    const xlsx = new Blob(['xlsx'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    vi.spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(response(xlsx))
      .mockResolvedValueOnce(response(new Blob(['json'], { type: 'application/json' })))
    expect(await downloadDocumentDefinitionImportTemplate()).toEqual({ success: true, data: xlsx })
    expect(await downloadDocumentDefinitionImportTemplate()).toMatchObject({ success: false })
  })

  it('以 multipart 上传并严格核对导入回执', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw').mockResolvedValue(response({
      success: true, data: { import_batch_id: 'batch-1', imported_count: 1, items: [definition] },
    }))
    const file = new File(['xlsx'], 'definitions.xlsx')
    expect(await importDocumentDefinitions(file)).toMatchObject({ success: true, resultUnknown: false })
    const config = request.mock.calls[0]?.[0]
    expect(config).toMatchObject({ method: 'POST', url: '/api/v1/document-definitions/import', timeout: 120000 })
    expect(config?.data).toBeInstanceOf(FormData)
    expect((config?.data as FormData).get('file')).toBe(file)
  })

  it('展示 422 逐字段问题，库存冲突也不标记结果未知', async () => {
    const problems = [{ sheet: '文书定义', row: 3, field: '文书编码', code: 'duplicate', message: '编码重复' }]
    vi.spyOn(ApiService, 'requestRaw')
      .mockRejectedValueOnce(httpError(422, { detail: { code: 'document_definition_import_invalid', message: '模板校验失败', problems } }))
      .mockRejectedValueOnce(httpError(409, { detail: { code: 'document_definition_code_conflict', message: '编码已存在', codes: ['DOC-001'] } }))
    expect(await importDocumentDefinitions(new File(['x'], 'definitions.xlsx'))).toEqual({
      success: false, message: '模板校验失败', resultUnknown: false, problems,
    })
    expect(await importDocumentDefinitions(new File(['x'], 'definitions.xlsx'))).toMatchObject({
      success: false, message: '编码已存在', resultUnknown: false,
    })
  })

  it('畸形成功回执和网络异常均标记结果未知', async () => {
    vi.spyOn(ApiService, 'requestRaw')
      .mockResolvedValueOnce(response({ success: true, data: { imported_count: 1, items: [] } }))
      .mockRejectedValueOnce(new Error('network'))
    expect(await importDocumentDefinitions(new File(['x'], 'definitions.xlsx'))).toMatchObject({ success: false, resultUnknown: true })
    expect(await importDocumentDefinitions(new File(['x'], 'definitions.xlsx'))).toMatchObject({ success: false, resultUnknown: true })
  })

  it('本地拒绝非 xlsx 和超过 2 MiB 文件', async () => {
    const request = vi.spyOn(ApiService, 'requestRaw')
    const oversized = new File(['x'], 'definitions.xlsx')
    Object.defineProperty(oversized, 'size', { value: DOCUMENT_DEFINITION_IMPORT_MAX_BYTES + 1 })
    expect(await importDocumentDefinitions(new File(['x'], 'definitions.xls'))).toMatchObject({ success: false, resultUnknown: false })
    expect(await importDocumentDefinitions(oversized)).toMatchObject({ success: false, resultUnknown: false })
    expect(request).not.toHaveBeenCalled()
  })
})
