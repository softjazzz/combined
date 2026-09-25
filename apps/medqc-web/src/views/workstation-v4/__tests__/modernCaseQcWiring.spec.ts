import { describe, expect, it } from 'vitest'

import { ModernCaseQcSnapshotError } from '@/api/modernCaseQcResult'
import type { ModernCaseQcSnapshot } from '@/api/modernCaseQcResult'
import {
  allowsLegacyWriteWorkspace,
  buildModernCaseQcDefectPageRequest,
  buildModernCaseQcRequestKey,
  hasModernCaseQcDefectPageEnvelopes,
  isModernCaseQcDefectPageResponseStale,
  isModernCaseQcResponseStale,
  latestModernCaseQcResultIdOf,
  mergeModernCaseQcDefectPage,
  readModernCaseQcDefectPageEnvelope,
  resolveModernCaseQcErrorMessage,
  resolveModernCaseQcReadTarget,
  resolveSelectedRecord,
} from '../modernCaseQcReadController'

const COORDINATES = { instituteId: 'LX001', patientId: 'P-1', visitId: 'V-1' }
const WORKLIST_KEY = 'worklist:["LX001","P-1","V-1"]'

function worklistRow(overrides: Record<string, unknown> = {}) {
  return {
    workflowType: 'frontpage' as const,
    identityStatus: 'unverified' as const,
    ...COORDINATES,
    ...overrides,
  }
}

function stageRecord(overrides: Record<string, unknown> = {}) {
  return {
    id: 'V-1',
    recordKey: WORKLIST_KEY,
    identityStatus: 'unverified' as const,
    ...COORDINATES,
    ...overrides,
  }
}

const TARGET_BASE = {
  isDetailMode: true,
  isWorklistMode: true,
  stageSelectedKey: WORKLIST_KEY,
  settlementSourceKey: 'settlement_qc' as const,
}

interface FakeRecord {
  id: string
  recordKey: string
  identityStatus?: 'ambiguous' | 'unverified'
  name?: string
}

describe('现代只读快照接线：读取触发条件', () => {
  it('工作清单唯一未核实行按工作流映射来源', () => {
    const frontpage = resolveModernCaseQcReadTarget({
      ...TARGET_BASE,
      stageRecord: stageRecord(),
      worklistRow: worklistRow(),
    })
    expect(frontpage).toEqual({
      workflowType: 'frontpage',
      sourceKey: 'frontpage_formal_qc',
      ...COORDINATES,
    })

    const coding = resolveModernCaseQcReadTarget({
      ...TARGET_BASE,
      stageRecord: stageRecord(),
      worklistRow: worklistRow({ workflowType: 'coding' }),
    })
    expect(coding?.sourceKey).toBe('coding_qc')
  })

  it('结算两条来源按显式切换取值，互不回退', () => {
    const saved = resolveModernCaseQcReadTarget({
      ...TARGET_BASE,
      stageRecord: stageRecord(),
      worklistRow: worklistRow({ workflowType: 'settlement' }),
      settlementSourceKey: 'settlement_qc',
    })
    expect(saved?.sourceKey).toBe('settlement_qc')

    const generated = resolveModernCaseQcReadTarget({
      ...TARGET_BASE,
      stageRecord: stageRecord(),
      worklistRow: worklistRow({ workflowType: 'settlement' }),
      settlementSourceKey: 'settlement_generate_qc',
    })
    expect(generated?.sourceKey).toBe('settlement_generate_qc')
  })

  it('歧义行、普通旧列表与非详情模式都不触发读取', () => {
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageRecord: stageRecord(),
        worklistRow: worklistRow({ identityStatus: 'ambiguous' }),
      }),
    ).toBeNull()

    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        isWorklistMode: false,
        stageRecord: stageRecord({ identityStatus: undefined }),
        worklistRow: worklistRow(),
      }),
    ).toBeNull()

    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        isDetailMode: false,
        stageRecord: stageRecord(),
        worklistRow: worklistRow(),
      }),
    ).toBeNull()
  })

  it('旧列表选中行或同键阴影都不读取：身份与坐标必须来自工作清单唯一行', () => {
    // 工作清单模式下选到旧列表同键记录：没有 identityStatus。
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageRecord: stageRecord({ identityStatus: undefined }),
        worklistRow: worklistRow(),
      }),
    ).toBeNull()

    // 同 visit 跨 patient / institute 的阴影行。
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageRecord: stageRecord({ patientId: 'P-2' }),
        worklistRow: worklistRow(),
      }),
    ).toBeNull()
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageRecord: stageRecord({ instituteId: 'LX999' }),
        worklistRow: worklistRow(),
      }),
    ).toBeNull()

    // 工作清单已刷新掉该行，或选中键与工作清单行无法严格对应。
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        worklistRow: null,
        stageRecord: stageRecord(),
      }),
    ).toBeNull()
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageSelectedKey: 'worklist:["LX001","P-1","V-OTHER"]',
        stageRecord: stageRecord(),
        worklistRow: worklistRow(),
      }),
    ).toBeNull()
  })

  it('三坐标缺失或含非规范前后空格时不读取', () => {
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageRecord: stageRecord({ patientId: undefined }),
        worklistRow: worklistRow({ patientId: undefined }),
      }),
    ).toBeNull()
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageRecord: stageRecord({ instituteId: ' LX001' }),
        worklistRow: worklistRow({ instituteId: ' LX001' }),
      }),
    ).toBeNull()
    expect(
      resolveModernCaseQcReadTarget({
        ...TARGET_BASE,
        stageRecord: stageRecord({ visitId: '   ' }),
        worklistRow: worklistRow({ visitId: '   ' }),
      }),
    ).toBeNull()
  })
})

describe('现代只读快照接线：请求键与迟到响应', () => {
  const target = {
    workflowType: 'settlement' as const,
    sourceKey: 'settlement_qc' as const,
    ...COORDINATES,
  }

  it('请求键包含来源，且用 JSON 编码避免坐标含分隔符时键碰撞', () => {
    expect(buildModernCaseQcRequestKey(target)).toBe(
      JSON.stringify(['LX001', 'P-1', 'V-1', 'settlement_qc']),
    )
    expect(buildModernCaseQcRequestKey(null)).toBe('')

    const spliced = buildModernCaseQcRequestKey({
      ...target,
      instituteId: 'LX001::P-1::V-1',
      patientId: '',
      visitId: '',
    })
    const plain = buildModernCaseQcRequestKey({ ...target, instituteId: 'LX001' })
    expect(spliced).not.toBe(plain)
  })

  it('同 visit 跨 patient/institute 的迟到响应被丢弃', () => {
    const requested = buildModernCaseQcRequestKey(target)
    const otherPatient = buildModernCaseQcRequestKey({ ...target, patientId: 'P-2' })
    const otherInstitute = buildModernCaseQcRequestKey({ ...target, instituteId: 'LX999' })

    expect(
      isModernCaseQcResponseStale({
        token: 1,
        currentToken: 2,
        requestedKey: requested,
        currentKey: otherPatient,
      }),
    ).toBe(true)
    expect(
      isModernCaseQcResponseStale({
        token: 1,
        currentToken: 1,
        requestedKey: requested,
        currentKey: otherInstitute,
      }),
    ).toBe(true)
  })

  it('结算两来源切换后旧响应被丢弃，同一请求不会被误判为迟到', () => {
    const savedKey = buildModernCaseQcRequestKey(target)
    const generatedKey = buildModernCaseQcRequestKey({
      ...target,
      sourceKey: 'settlement_generate_qc',
    })
    expect(savedKey).not.toBe(generatedKey)

    expect(
      isModernCaseQcResponseStale({
        token: 1,
        currentToken: 2,
        requestedKey: savedKey,
        currentKey: generatedKey,
      }),
    ).toBe(true)
    expect(
      isModernCaseQcResponseStale({
        token: 2,
        currentToken: 2,
        requestedKey: generatedKey,
        currentKey: generatedKey,
      }),
    ).toBe(false)
  })
})

describe('现代只读快照接线：选中行解析与写保护', () => {
  const shadow: FakeRecord = { id: 'V-1', recordKey: WORKLIST_KEY, name: '旧列表同键阴影' }
  const stage: FakeRecord = { id: 'V-1', recordKey: WORKLIST_KEY, identityStatus: 'unverified' }

  it('工作清单模式下同键阴影不覆盖选中工作清单行的身份状态', () => {
    expect(
      resolveSelectedRecord({
        isWorklistMode: true,
        stageSelectedKey: WORKLIST_KEY,
        fallbackSelectedKey: null,
        stageRecord: stage,
        allRecords: [shadow],
      }),
    ).toBe(stage)
  })

  it('工作清单选中行与选中键不一致时失败关闭，不回退旧列表', () => {
    expect(
      resolveSelectedRecord({
        isWorklistMode: true,
        stageSelectedKey: WORKLIST_KEY,
        fallbackSelectedKey: null,
        stageRecord: { id: 'V-OTHER', recordKey: 'legacy:V-OTHER' },
        allRecords: [shadow],
      }),
    ).toBeNull()

    // 没有工作清单权威行时同样不采用旧列表阴影。
    expect(
      resolveSelectedRecord({
        isWorklistMode: true,
        stageSelectedKey: WORKLIST_KEY,
        fallbackSelectedKey: WORKLIST_KEY,
        stageRecord: null,
        allRecords: [shadow],
      }),
    ).toBeNull()
  })

  it('工作清单模式下没有工作清单选中键时失败关闭，通知按就诊号跳转也不放开旧列表', () => {
    const legacy: FakeRecord = { id: 'shared-visit', recordKey: '' }
    expect(
      resolveSelectedRecord({
        isWorklistMode: true,
        stageSelectedKey: null,
        fallbackSelectedKey: 'shared-visit',
        stageRecord: null,
        allRecords: [legacy],
      }),
    ).toBeNull()
  })

  it('非工作清单模式仍按 selectedId 解析旧列表记录', () => {
    const legacy: FakeRecord = { id: 'shared-visit', recordKey: '' }
    expect(
      resolveSelectedRecord({
        isWorklistMode: false,
        stageSelectedKey: null,
        fallbackSelectedKey: 'shared-visit',
        stageRecord: null,
        allRecords: [legacy],
      }),
    ).toBe(legacy)
  })

  it('非工作清单模式保持旧解析顺序，选中键仍优先命中旧列表记录', () => {
    expect(
      resolveSelectedRecord({
        isWorklistMode: false,
        stageSelectedKey: null,
        fallbackSelectedKey: WORKLIST_KEY,
        stageRecord: stage,
        allRecords: [shadow],
      }),
    ).toBe(shadow)
  })

  it('没有选中键时不返回任何记录', () => {
    expect(
      resolveSelectedRecord({
        isWorklistMode: true,
        stageSelectedKey: null,
        fallbackSelectedKey: null,
        stageRecord: stage,
        allRecords: [shadow],
      }),
    ).toBeNull()
  })

  it('旧的写操作工作区只在「已选中且身份已核实」时开放', () => {
    expect(allowsLegacyWriteWorkspace(null)).toBe(false)
    expect(allowsLegacyWriteWorkspace(undefined)).toBe(false)
    expect(allowsLegacyWriteWorkspace({})).toBe(true)
    expect(allowsLegacyWriteWorkspace({ identityStatus: 'unverified' })).toBe(false)
    expect(allowsLegacyWriteWorkspace({ identityStatus: 'ambiguous' })).toBe(false)
  })
})

describe('现代只读快照接线：失败语义脱敏', () => {
  it('HTTP 状态从 AxiosError.response.status 读取并脱敏', () => {
    const notFound = { response: { status: 404 }, message: 'Request failed with status code 404' }
    expect(resolveModernCaseQcErrorMessage(notFound)).toBe('未找到该病例的现代质控结果')
    expect(resolveModernCaseQcErrorMessage(notFound)).not.toContain('404')
    expect(resolveModernCaseQcErrorMessage({ response: { status: 409 } })).toBe(
      '病例身份不唯一，无法读取质控结果',
    )
    expect(resolveModernCaseQcErrorMessage({ response: { status: 503 } })).toBe(
      '质控结果暂时不可用',
    )
    expect(resolveModernCaseQcErrorMessage({ response: { status: 422 } })).toBe(
      '病例身份参数不合法',
    )
    // 新接口暂时只对 admin/qc_manager 开放，403 是权限态而不是空结果或网络错误。
    const forbidden = {
      response: { status: 403, data: { detail: '患者 LX001/P-1 无权访问' } },
      message: 'Request failed with status code 403',
    }
    expect(resolveModernCaseQcErrorMessage(forbidden)).toBe('当前账号无权查看该质控结果')
    expect(resolveModernCaseQcErrorMessage(forbidden)).not.toContain('LX001')
    // 已归一化的 error.status 同样兼容。
    expect(resolveModernCaseQcErrorMessage({ status: 503, response: undefined })).toBe(
      '质控结果暂时不可用',
    )
  })

  it('网络异常与未知错误都回落到脱敏文案', () => {
    const networkError = {
      code: 'ERR_NETWORK',
      message: 'Network Error at http://user:secret@db.internal/LX001',
    }
    const message = resolveModernCaseQcErrorMessage(networkError)
    expect(message).toBe('质控结果读取失败')
    expect(message).not.toContain('db.internal')
    expect(message).not.toContain('secret')
  })

  it('快照业务错误按 code 映射为脱敏文案', () => {
    expect(
      resolveModernCaseQcErrorMessage(
        new ModernCaseQcSnapshotError('identity_mismatch', '响应 patient_id 与请求不一致'),
      ),
    ).toBe('病例身份未核实，暂不可读取现代质控结果')
    expect(
      resolveModernCaseQcErrorMessage(
        new ModernCaseQcSnapshotError('unexpected_status', '快照接口返回非 200 状态：500'),
      ),
    ).toBe('质控结果暂时不可用')
    expect(
      resolveModernCaseQcErrorMessage(new ModernCaseQcSnapshotError('malformed_payload', '字段缺失')),
    ).toBe('质控结果读取失败')
  })
})

function buildEnvelopeSnapshot(
  overrides: Partial<ModernCaseQcSnapshot> = {},
): ModernCaseQcSnapshot {
  return {
    identity_status: 'verified',
    source_key: 'frontpage_formal_qc',
    institute_id: 'LX001',
    patient_id: 'P-1',
    visit_id: 'V-1',
    latest_qc_result: { id: 'result-1' },
    recent_results: [],
    active_defects: [],
    current_result_defects: [],
    latest_notification: null,
    active_defects_has_more: false,
    current_result_defects_has_more: false,
    active_defects_next_offset: null,
    current_result_defects_next_offset: null,
    ...overrides,
  }
}

describe('现代只读快照接线：缺陷分组分页（纯决策）', () => {
  it('信封与 API 同口径：has_more=false 必须严格配 next_offset=null', () => {
    expect(readModernCaseQcDefectPageEnvelope(buildEnvelopeSnapshot(), 'active')).toEqual({
      ok: true,
      hasMore: false,
      nextOffset: null,
    })

    // 缺字段（undefined）不是 null，不得被当成「已加载完」。
    const missingOffset = buildEnvelopeSnapshot()
    delete (missingOffset as unknown as Record<string, unknown>).active_defects_next_offset
    expect(readModernCaseQcDefectPageEnvelope(missingOffset, 'active').ok).toBe(false)

    const missingHasMore = buildEnvelopeSnapshot()
    delete (missingHasMore as unknown as Record<string, unknown>).current_result_defects_has_more
    expect(readModernCaseQcDefectPageEnvelope(missingHasMore, 'current').ok).toBe(false)

    expect(
      readModernCaseQcDefectPageEnvelope(
        buildEnvelopeSnapshot({ active_defects_next_offset: 20 }),
        'active',
      ).ok,
    ).toBe(false)
    expect(
      readModernCaseQcDefectPageEnvelope(
        buildEnvelopeSnapshot({ active_defects_has_more: 'true' as unknown as boolean }),
        'active',
      ).ok,
    ).toBe(false)
  })

  it('has_more=true 只接受安全非负整数游标', () => {
    expect(
      readModernCaseQcDefectPageEnvelope(
        buildEnvelopeSnapshot({ active_defects_has_more: true, active_defects_next_offset: 20 }),
        'active',
      ),
    ).toEqual({ ok: true, hasMore: true, nextOffset: 20 })

    for (const invalid of [null, -1, 1.5, Number.POSITIVE_INFINITY] as const) {
      expect(
        readModernCaseQcDefectPageEnvelope(
          buildEnvelopeSnapshot({
            active_defects_has_more: true,
            active_defects_next_offset: invalid as unknown as number,
          }),
          'active',
        ).ok,
      ).toBe(false)
    }
  })

  it('两组信封必须同时成立，缺一即视为响应不完整', () => {
    expect(hasModernCaseQcDefectPageEnvelopes(buildEnvelopeSnapshot())).toBe(true)

    const oneGroupOnly = buildEnvelopeSnapshot()
    delete (oneGroupOnly as unknown as Record<string, unknown>).current_result_defects_next_offset
    expect(hasModernCaseQcDefectPageEnvelopes(oneGroupOnly)).toBe(false)
  })

  it('分页请求只带目标组 offset，另一组不参与覆盖', () => {
    expect(buildModernCaseQcDefectPageRequest({ group: 'active', offset: 20, limit: 20 })).toEqual({
      active_defects_offset: 20,
      defects_limit: 20,
    })

    const currentRequest = buildModernCaseQcDefectPageRequest({
      group: 'current',
      offset: 40,
      limit: 20,
    })
    expect(currentRequest).toEqual({ current_result_defects_offset: 40, defects_limit: 20 })
    expect('active_defects_offset' in currentRequest).toBe(false)
  })

  it('拼接只改写目标组数组与该组信封，另一组已加载页与游标保持原样', () => {
    const current = buildEnvelopeSnapshot({
      active_defects: [{ id: 'd-1' }],
      active_defects_has_more: true,
      active_defects_next_offset: 20,
      current_result_defects: [{ id: 'r-1' }, { id: 'r-2' }],
      current_result_defects_has_more: true,
      current_result_defects_next_offset: 20,
    })
    // 未请求的一组按默认第 1 页返回：不得用它覆盖已加载的后续页。
    const incoming = buildEnvelopeSnapshot({
      active_defects: [{ id: 'd-2' }],
      active_defects_has_more: false,
      active_defects_next_offset: null,
      current_result_defects: [{ id: 'r-1' }],
      current_result_defects_has_more: true,
      current_result_defects_next_offset: 20,
    })

    const merged = mergeModernCaseQcDefectPage({ group: 'active', current, incoming })
    expect(merged?.active_defects.map((defect) => defect.id)).toEqual(['d-1', 'd-2'])
    expect(merged?.active_defects_has_more).toBe(false)
    expect(merged?.active_defects_next_offset).toBeNull()
    expect(merged?.current_result_defects.map((defect) => defect.id)).toEqual(['r-1', 'r-2'])
    expect(merged?.current_result_defects_has_more).toBe(true)
    expect(merged?.current_result_defects_next_offset).toBe(20)

    // 反向：拼接「本次结果缺陷」时不得改写活跃缺陷组。
    const mergedCurrent = mergeModernCaseQcDefectPage({
      group: 'current',
      current,
      incoming: buildEnvelopeSnapshot({
        active_defects: [{ id: 'd-9' }],
        active_defects_has_more: true,
        active_defects_next_offset: 20,
        current_result_defects: [{ id: 'r-3' }],
        current_result_defects_has_more: false,
        current_result_defects_next_offset: null,
      }),
    })
    expect(mergedCurrent?.current_result_defects.map((defect) => defect.id)).toEqual([
      'r-1',
      'r-2',
      'r-3',
    ])
    expect(mergedCurrent?.current_result_defects_has_more).toBe(false)
    expect(mergedCurrent?.current_result_defects_next_offset).toBeNull()
    expect(mergedCurrent?.active_defects.map((defect) => defect.id)).toEqual(['d-1'])
    expect(mergedCurrent?.active_defects_next_offset).toBe(20)
  })

  it('拼接按 id 稳定去重：并发插入导致同一缺陷落到两页时不重复渲染', () => {
    const merged = mergeModernCaseQcDefectPage({
      group: 'active',
      current: buildEnvelopeSnapshot({ active_defects: [{ id: 'd-1' }, { id: 'd-2' }] }),
      incoming: buildEnvelopeSnapshot({
        active_defects: [{ id: 'd-2' }, { id: 'd-3' }],
        active_defects_has_more: false,
        active_defects_next_offset: null,
      }),
    })
    expect(merged?.active_defects.map((defect) => defect.id)).toEqual(['d-1', 'd-2', 'd-3'])

    // 无 id 的条目无法判等，一律保留。
    const withoutIds = mergeModernCaseQcDefectPage({
      group: 'active',
      current: buildEnvelopeSnapshot({ active_defects: [{ rule_name: '示例规则' }] }),
      incoming: buildEnvelopeSnapshot({ active_defects: [{ rule_name: '示例规则' }] }),
    })
    expect(withoutIds?.active_defects).toHaveLength(2)
  })

  it('响应信封不成立时不拼接，交由调用方按该组加载失败处理', () => {
    const current = buildEnvelopeSnapshot({ active_defects: [{ id: 'd-1' }] })
    const broken = buildEnvelopeSnapshot({
      active_defects_has_more: true,
      active_defects_next_offset: null,
    })
    expect(mergeModernCaseQcDefectPage({ group: 'active', current, incoming: broken })).toBeNull()
  })

  it('迟到判定：令牌、请求键或期间已换结果都丢弃，同请求不误判', () => {
    const base = {
      token: 1,
      currentToken: 1,
      requestedKey: 'k',
      currentKey: 'k',
      requestedResultId: 'result-1',
      loadedResultId: 'result-1',
    }
    expect(isModernCaseQcDefectPageResponseStale(base)).toBe(false)
    expect(isModernCaseQcDefectPageResponseStale({ ...base, currentToken: 2 })).toBe(true)
    expect(isModernCaseQcDefectPageResponseStale({ ...base, currentKey: 'k2' })).toBe(true)
    // 期间已有新结果落地：旧 offset 的分页响应必须丢弃，不能再落地或拼接。
    expect(isModernCaseQcDefectPageResponseStale({ ...base, loadedResultId: 'result-2' })).toBe(true)
  })

  it('最新结果标识取 id/result_id，缺失为空串', () => {
    expect(latestModernCaseQcResultIdOf(buildEnvelopeSnapshot())).toBe('result-1')
    expect(
      latestModernCaseQcResultIdOf(buildEnvelopeSnapshot({ latest_qc_result: { result_id: 'r-9' } })),
    ).toBe('r-9')
    expect(latestModernCaseQcResultIdOf(buildEnvelopeSnapshot({ latest_qc_result: null }))).toBe('')
    expect(latestModernCaseQcResultIdOf(null)).toBe('')
  })
})
