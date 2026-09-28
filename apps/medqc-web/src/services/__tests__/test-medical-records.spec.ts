import { beforeEach, describe, expect, it, vi } from 'vitest'

const requestRaw = vi.fn()
vi.mock('@/services/apiService', () => ({
  ApiService: { requestRaw: (...args: unknown[]) => requestRaw(...args) },
}))

import {
  buildTestRecordEditPayload,
  buildTestRecordRunPayload,
  downloadTestRecordImportTemplate,
  findMissingEditBasics,
  getCurrentRuleSetCatalog,
  importTestRecords,
  listTestRecords,
  removeTestRecord,
  TEST_RECORD_IMPORT_MAX_BYTES,
  unionTestRecordRuleIds,
  updateTestRecordRules,
} from '@/services/test-medical-records'
import {
  buildRuleOptions,
  formatDocumentCount,
  resolveStateTag,
} from '@/views/test-medical-records/components/testRecordPresentation'
import type { TestRecordItem } from '@/types/test-medical-records'

function makeItem(overrides: Partial<TestRecordItem> = {}): TestRecordItem {
  return {
    id: 'ct-1',
    institute_id: 'CUSTOMER_TEST',
    patient_id: 'CUSTOMER_PATIENT_1',
    visit_id: 'CUSTOMER_TEST_1',
    case_title: '测试病历一',
    patient_name: '测试患者',
    department: '心内科',
    mr_no: 'MR-1',
    document_count: 2,
    rule_ids: ['LX0609-001'],
    rule_count: 1,
    latest_job_id: '',
    bundle_status: 'ready',
    origin: 'created',
    source_item_id: '',
    sex: '男',
    age: 45,
    admission_time: '2026-09-01T08:00:00',
    state: 'active',
    removed: false,
    superseded_by: null,
    created_at: '2026-09-27T08:00:00',
    updated_at: '2026-09-27T08:00:00.123456',
    ...overrides,
  }
}

describe('测试病历服务', () => {
  beforeEach(() => {
    requestRaw.mockReset()
  })

  it('列表请求只在需要时带 include_removed 与关键字', async () => {
    requestRaw.mockResolvedValue({ data: { success: true, data: { items: [], total: 0, page: 1, page_size: 20 } } })
    await listTestRecords({ page: 1, page_size: 20, include_removed: true, q: ' 张 ' })
    expect(requestRaw).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'GET',
        url: '/api/v1/qc/sample-pools/test-records',
        params: { page: 1, page_size: 20, include_removed: true, q: '张' },
      }),
    )
  })

  it('关联质控点与移除原样回传 updated_at 作为 CAS', async () => {
    requestRaw.mockResolvedValue({ data: { success: true, data: makeItem() } })
    const item = makeItem()
    await updateTestRecordRules(item, ['LX0609-002'])
    expect(requestRaw).toHaveBeenLastCalledWith(
      expect.objectContaining({
        method: 'PUT',
        url: '/api/v1/qc/sample-pools/test-records/ct-1/rules',
        data: { rule_ids: ['LX0609-002'], updated_at: item.updated_at },
      }),
    )
    await removeTestRecord(item)
    expect(requestRaw).toHaveBeenLastCalledWith(
      expect.objectContaining({ method: 'DELETE', params: { updated_at: item.updated_at } }),
    )
  })

  it('冲突错误把后端 detail 透传给页面', async () => {
    requestRaw.mockRejectedValue({ response: { data: { detail: '测试病历已被修改，请刷新后重试' } } })
    const result = await removeTestRecord(makeItem())
    expect(result).toEqual({ success: false, message: '测试病历已被修改，请刷新后重试' })
  })

  it('规则目录取当前版本详情 entries，缺名称时保留 null', async () => {
    requestRaw
      .mockResolvedValueOnce({ data: { success: true, data: { current_version: 'v2' } } })
      .mockResolvedValueOnce({
        data: {
          success: true,
          data: {
            entries: [
              { rule_id: 'LX0609-001', state: 'active', qc_point: '入院记录24小时', source_document: '入院记录' },
              { rule_id: 'LX0609-002', state: 'paused' },
              { rule_id: '', state: 'active' },
            ],
          },
        },
      })
    const result = await getCurrentRuleSetCatalog()
    expect(requestRaw).toHaveBeenLastCalledWith(
      expect.objectContaining({ url: '/api/v1/rule-set-versions/luxian_0609_qc_v1/v2' }),
    )
    expect(result.data?.entries).toEqual([
      { rule_id: 'LX0609-001', state: 'active', qc_point: '入院记录24小时', source_document: '入院记录' },
      { rule_id: 'LX0609-002', state: 'paused', qc_point: null, source_document: null },
    ])
  })

  it('运行载荷使用固定池三坐标与所选规则，拒绝非有效条目', () => {
    const items = [makeItem(), makeItem({ id: 'ct-2', visit_id: 'CUSTOMER_TEST_2', rule_ids: ['LX0609-002', 'LX0609-001'] })]
    expect(unionTestRecordRuleIds(items)).toEqual(['LX0609-001', 'LX0609-002'])
    const payload = buildTestRecordRunPayload(items, ['LX0609-001', 'LX0609-001'])
    expect(payload).toMatchObject({
      sample_item_ids: ['ct-1', 'ct-2'],
      selected_rule_ids: ['LX0609-001'],
      validation_mode: 'customer',
      rule_set_key: 'luxian_0609_qc_v1',
    })
    expect(payload.record_refs?.[1]).toEqual({
      institute_id: 'CUSTOMER_TEST',
      patient_id: 'CUSTOMER_PATIENT_1',
      visit_id: 'CUSTOMER_TEST_2',
    })
    expect(() => buildTestRecordRunPayload([makeItem({ state: 'superseded' })], ['LX0609-001'])).toThrow()
    expect(() => buildTestRecordRunPayload([makeItem({ patient_id: '' })], ['LX0609-001'])).toThrow()
    expect(() => buildTestRecordRunPayload([makeItem()], [])).toThrow('请先选择要运行的质控点')
  })

  it('编辑载荷派生新副本、使用用户确认的人口学字段并指向被替换条目', () => {
    const item = makeItem()
    const payload = buildTestRecordEditPayload(
      item,
      { caseTitle: '改后', sex: '女', age: 67, admissionTime: '2026-09-01 08:30' },
      [
        { key: 'a', document_type: 'admission_record', title: '入院记录', content: '正文', record_time: '2026-09-01 09:00:00', enabled: true },
        { key: 'b', document_type: 'daily_course_record', title: '病程', content: '停用', enabled: false },
      ],
    )
    expect(payload.basic_info).toMatchObject({ sex: '女', age: 67, admission_time: '2026-09-01T08:30:00' })
    // 墙上时间原样传递，不做时区换算。
    expect(payload.documents).toEqual([expect.objectContaining({ record_time: '2026-09-01T09:00:00' })])
    expect(payload.selected_rule_ids).toEqual(['LX0609-001'])
    expect(payload.source).toMatchObject({
      source_pool_id: 'customer-created-test-records-v1',
      source_item_ids: ['ct-1'],
      supersedes_item_id: 'ct-1',
      supersedes_updated_at: item.updated_at,
    })
  })

  it('缺少性别、年龄或入院时间时拒绝构造载荷，不使用默认值', () => {
    const docs = [{ key: 'a', document_type: 'admission_record', title: '入院记录', content: '正文', enabled: true }]
    expect(findMissingEditBasics({ caseTitle: '', sex: '', age: null, admissionTime: '' })).toEqual([
      '性别',
      '年龄',
      '入院时间',
    ])
    expect(() =>
      buildTestRecordEditPayload(makeItem(), { caseTitle: '', sex: '', age: 50, admissionTime: '2026-09-01' }, docs),
    ).toThrow('请填写性别')
  })

  it('导入用 multipart 上传并保留 created/unknown 逐病例结果', async () => {
    requestRaw.mockResolvedValue({
      data: {
        success: true,
        data: {
          total: 2,
          created: 1,
          unknown: 1,
          results: [
            {
              case_key: 'CASE-1', case_row: 2, document_rows: [2], status: 'created',
              message: '病历已创建', item_id: 'item-1', institute_id: 'CUSTOMER_TEST',
              patient_id: 'patient-1', visit_id: 'visit-1', bundle_status: 'ready',
            },
            {
              case_key: 'CASE-2', case_row: 3, document_rows: [3, 4], status: 'unknown',
              message: '创建结果未知',
            },
          ],
        },
      },
    })
    const file = new File(['xlsx'], 'records.xlsx')

    const result = await importTestRecords(file)

    expect(result).toMatchObject({ success: true, data: { total: 2, created: 1, unknown: 1 } })
    const config = requestRaw.mock.calls[0][0]
    expect(config).toMatchObject({
      method: 'POST',
      url: '/api/v1/qc/sample-pools/test-records/import',
      timeout: 15 * 60 * 1000,
    })
    expect(config.data).toBeInstanceOf(FormData)
    expect(config.data.get('file')).toBe(file)
  })

  it('下载模板使用 Blob 响应并拒绝空文件', async () => {
    requestRaw.mockResolvedValueOnce({ data: new Blob(['xlsx']) })
    const downloaded = await downloadTestRecordImportTemplate()
    expect(downloaded.data).toBeInstanceOf(Blob)
    expect(requestRaw).toHaveBeenLastCalledWith(expect.objectContaining({
      method: 'GET',
      url: '/api/v1/qc/sample-pools/test-records/import-template',
      responseType: 'blob',
    }))

    requestRaw.mockResolvedValueOnce({ data: new Blob([]) })
    const empty = await downloadTestRecordImportTemplate()
    expect(empty).toEqual({ success: false, message: '下载的测试病历导入模板无效' })
  })

  it.each([
    ['created 缺回执', {
      total: 1, created: 1, unknown: 0,
      results: [{ case_key: 'A', case_row: 2, document_rows: [2], status: 'created', message: '已创建' }],
    }],
    ['状态计数不匹配', {
      total: 1, created: 1, unknown: 0,
      results: [{ case_key: 'A', case_row: 2, document_rows: [2], status: 'unknown', message: '未知' }],
    }],
    ['重复病例编号', {
      total: 2, created: 0, unknown: 2,
      results: [
        { case_key: 'A', case_row: 2, document_rows: [2], status: 'unknown', message: '未知' },
        { case_key: 'A', case_row: 3, document_rows: [3], status: 'unknown', message: '未知' },
      ],
    }],
    ['空文书行', {
      total: 1, created: 0, unknown: 1,
      results: [{ case_key: 'A', case_row: 2, document_rows: [], status: 'unknown', message: '未知' }],
    }],
  ])('HTTP 200 的异常逐病例结果不冒充成功：%s', async (_label, data) => {
    requestRaw.mockResolvedValue({ data: { success: true, data } })

    const result = await importTestRecords(new File(['xlsx'], 'records.xlsx'))

    expect(result).toMatchObject({ success: false, resultUnknown: true })
    expect(result.message).toContain('不要盲目重试')
  })

  it('HTTP 200 却声明失败时不能证明整批未写入', async () => {
    requestRaw.mockResolvedValue({ data: { success: false, message: '服务异常' } })

    const result = await importTestRecords(new File(['xlsx'], 'records.xlsx'))

    expect(result).toMatchObject({ success: false, resultUnknown: true })
    expect(result.message).toContain('不要盲目重试')
  })

  it('解析 422 sheet/行号/字段错误，并将包装 error 视为写入前拒绝', async () => {
    requestRaw.mockRejectedValue({
      response: {
        status: 422,
        data: {
          error: {
            code: 'invalid_test_record_import',
            message: '模板校验失败',
            errors: [{ sheet: '病历', row: 3, field: '年龄', message: '必须是 1–120 的整数' }],
          },
        },
      },
    })

    const result = await importTestRecords(new File(['xlsx'], 'records.xlsx'))

    expect(result.resultUnknown).toBe(false)
    expect(result.validationErrors).toEqual([
      { sheet: '病历', row: 3, field: '年龄', message: '必须是 1–120 的整数' },
    ])
  })

  it.each([409, 500, 503])('HTTP %s 无法证明未写入，结果标记未知', async (status) => {
    requestRaw.mockRejectedValue({ response: { status, data: { detail: '服务异常' } } })

    const result = await importTestRecords(new File(['xlsx'], 'records.xlsx'))

    expect(result).toMatchObject({ success: false, resultUnknown: true })
  })

  it('网络无响应时提醒先刷新核对', async () => {
    requestRaw.mockRejectedValue(new Error('timeout'))

    const result = await importTestRecords(new File(['xlsx'], 'records.xlsx'))

    expect(result).toMatchObject({ success: false, resultUnknown: true })
    expect(result.message).toContain('先刷新列表核对')
  })

  it('非 xlsx 或超过 5 MiB 在发请前拒绝', async () => {
    const wrongType = await importTestRecords(new File(['x'], 'records.xls'))
    const oversized = await importTestRecords(
      new File([new Uint8Array(TEST_RECORD_IMPORT_MAX_BYTES + 1)], 'records.xlsx'),
    )

    expect(wrongType.message).toContain('.xlsx')
    expect(oversized.message).toContain('5 MiB')
    expect(requestRaw).not.toHaveBeenCalled()
  })
})

describe('测试病历展示', () => {
  it('未知文书数显示未知，被替换条目显示新条目 ID', () => {
    expect(formatDocumentCount(null)).toBe('未知')
    expect(resolveStateTag(makeItem({ state: 'superseded', superseded_by: 'ct-9' })).text).toBe('已被替换 → ct-9')
    expect(resolveStateTag(makeItem({ state: 'unknown' })).text).toBe('状态未知')
  })

  it('规则选项缺名称时只显示 rule_id，并标出不在当前版本的已选规则', () => {
    const options = buildRuleOptions(
      {
        rule_set_key: 'luxian_0609_qc_v1',
        version: 'v2',
        entries: [
          { rule_id: 'LX0609-001', state: 'active', qc_point: null, source_document: null },
          { rule_id: 'LX0609-002', state: 'offline', qc_point: '名称', source_document: '首次病程' },
        ],
      },
      ['LX0609-999'],
    )
    expect(options.map((option) => option.label)).toEqual([
      'LX0609-001',
      'LX0609-002 · 首次病程 · 名称（下线）',
      'LX0609-999（不在当前版本）',
    ])
  })
})
