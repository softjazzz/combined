import { describe, expect, it } from 'vitest'

import { ModernCaseQcSnapshotError } from '@/api/modernCaseQcResult'
import {
  allowsLegacyWriteWorkspace,
  buildModernCaseQcRequestKey,
  isModernCaseQcResponseStale,
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
