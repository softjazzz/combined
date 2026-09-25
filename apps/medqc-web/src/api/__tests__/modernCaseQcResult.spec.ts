import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosRequestConfig, AxiosResponse } from 'axios'

import {
  ModernCaseQcSnapshotError,
  getModernCaseQcSnapshot,
  type ModernCaseQcIdentity,
  type ModernCaseQcSnapshotErrorCode,
} from '@/api/modernCaseQcResult'
import { ApiService } from '@/services/apiService'

const SNAPSHOT_URL = '/api/v1/workstation/case-qc/snapshot'

const baseIdentity: ModernCaseQcIdentity = {
  institute_id: 'INST-001',
  patient_id: 'PAT-001',
  visit_id: 'VISIT-001',
  source_key: 'coding_qc',
}

function buildPayload(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    identity_status: 'verified',
    source_key: baseIdentity.source_key,
    institute_id: baseIdentity.institute_id,
    patient_id: baseIdentity.patient_id,
    visit_id: baseIdentity.visit_id,
    latest_qc_result: null,
    recent_results: [],
    active_defects: [],
    current_result_defects: [],
    latest_notification: null,
    ...overrides,
  }
}

function okResponse(payload: unknown, status = 200): AxiosResponse<unknown> {
  return { status, data: payload } as AxiosResponse<unknown>
}

function envelopeResponse(data: Record<string, unknown>): AxiosResponse<unknown> {
  return okResponse({ success: true, data })
}

/** 负向用例需要传入缺参/畸形入参，统一在这里收敛一次断言。 */
function callWith(identity: unknown) {
  return getModernCaseQcSnapshot(identity as ModernCaseQcIdentity)
}

async function captureError(promise: Promise<unknown>): Promise<ModernCaseQcSnapshotError> {
  const error = await promise.then(
    () => null,
    (reason: unknown) => reason as ModernCaseQcSnapshotError,
  )
  expect(error).toBeInstanceOf(ModernCaseQcSnapshotError)
  return error as ModernCaseQcSnapshotError
}

async function expectErrorCode(promise: Promise<unknown>, code: ModernCaseQcSnapshotErrorCode) {
  const error = await captureError(promise)
  expect(error.code).toBe(code)
  return error
}

describe('getModernCaseQcSnapshot', () => {
  let requestRawMock: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    vi.restoreAllMocks()
    requestRawMock = vi.spyOn(ApiService, 'requestRaw')
  })

  it('按四维发起 GET 请求并原样保留缺陷语义', async () => {
    requestRawMock.mockResolvedValueOnce(
      envelopeResponse(
        buildPayload({
          latest_qc_result: { id: 'q-1', status: 'completed' },
          recent_results: [{ id: 'q-1', status: 'completed' }],
          active_defects: [
            { id: 'd-1', rule_name: 'R-001', description: '缺项', status: 'open', severity: 'error' },
          ],
          current_result_defects: [{ id: 'd-1', status: 'open' }],
          latest_notification: { id: 'n-1', title: '质控完成' },
        }),
      ),
    )

    const snapshot = await getModernCaseQcSnapshot(baseIdentity)

    expect(requestRawMock).toHaveBeenCalledTimes(1)
    expect(requestRawMock).toHaveBeenCalledWith({
      method: 'GET',
      url: SNAPSHOT_URL,
      params: {
        institute_id: 'INST-001',
        patient_id: 'PAT-001',
        visit_id: 'VISIT-001',
        source_key: 'coding_qc',
      },
    })
    expect(snapshot.identity_status).toBe('verified')
    expect(snapshot.source_key).toBe('coding_qc')
    expect(snapshot.latest_qc_result?.status).toBe('completed')
    expect(snapshot.active_defects[0].status).toBe('open')
    expect(snapshot.active_defects[0].severity).toBe('error')
    expect(snapshot.current_result_defects[0].id).toBe('d-1')
    expect(snapshot.latest_notification?.id).toBe('n-1')
  })

  it('两个结算来源各自独立透传，不合并', async () => {
    requestRawMock
      .mockResolvedValueOnce(
        envelopeResponse(buildPayload({ source_key: 'settlement_qc', active_defects: [] })),
      )
      .mockResolvedValueOnce(
        envelopeResponse(
          buildPayload({
            source_key: 'settlement_generate_qc',
            active_defects: [{ id: 'd-gen-1' }],
          }),
        ),
      )

    const settlement = await getModernCaseQcSnapshot({
      ...baseIdentity,
      source_key: 'settlement_qc',
    })
    const generated = await getModernCaseQcSnapshot({
      ...baseIdentity,
      source_key: 'settlement_generate_qc',
    })

    const firstParams = (requestRawMock.mock.calls[0][0] as AxiosRequestConfig)
      .params as Record<string, unknown>
    const secondParams = (requestRawMock.mock.calls[1][0] as AxiosRequestConfig)
      .params as Record<string, unknown>
    expect(firstParams.source_key).toBe('settlement_qc')
    expect(secondParams.source_key).toBe('settlement_generate_qc')
    expect(settlement.source_key).toBe('settlement_qc')
    expect(settlement.active_defects).toHaveLength(0)
    expect(generated.source_key).toBe('settlement_generate_qc')
    expect(generated.active_defects).toHaveLength(1)
  })

  it('响应 source_key 与请求不一致时失败关闭', async () => {
    requestRawMock.mockResolvedValueOnce(
      envelopeResponse(buildPayload({ source_key: 'settlement_generate_qc' })),
    )

    const error = await expectErrorCode(
      getModernCaseQcSnapshot({ ...baseIdentity, source_key: 'settlement_qc' }),
      'identity_mismatch',
    )
    expect(error.details).toMatchObject({
      field: 'source_key',
      expected_source_key: 'settlement_qc',
      received_source_key: 'settlement_generate_qc',
    })
  })

  it('响应三坐标与请求不一致时失败关闭', async () => {
    requestRawMock.mockResolvedValueOnce(
      envelopeResponse(buildPayload({ patient_id: 'PAT-OTHER' })),
    )

    const error = await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'identity_mismatch')
    expect(error.details).toMatchObject({ field: 'patient_id' })
  })

  it('响应 identity_status 未确认为 verified 时失败关闭', async () => {
    requestRawMock.mockResolvedValueOnce(
      envelopeResponse(buildPayload({ identity_status: 'unverified' })),
    )

    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'identity_unverified')
  })

  it('四维缺参、空白或含非规范前后空格时本地拒绝且不发请求', async () => {
    const { patient_id: _omitted, ...missingPatient } = baseIdentity

    await expectErrorCode(callWith(missingPatient), 'invalid_identity')
    await expectErrorCode(callWith({ ...baseIdentity, visit_id: '' }), 'invalid_identity')
    await expectErrorCode(callWith({ ...baseIdentity, visit_id: '   ' }), 'invalid_identity')
    await expectErrorCode(callWith({ ...baseIdentity, institute_id: ' INST-001' }), 'invalid_identity')
    await expectErrorCode(callWith({ ...baseIdentity, patient_id: 'PAT-001 ' }), 'invalid_identity')
    await expectErrorCode(
      callWith({ ...baseIdentity, source_key: 'coding_qc ' }),
      'invalid_identity',
    )
    await expectErrorCode(callWith({ ...baseIdentity, source_key: 'unknown_qc' }), 'unsupported_source_key')

    expect(requestRawMock).not.toHaveBeenCalled()
  })

  it('网络错误原样抛出，不返回假空结果', async () => {
    const networkError = Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })
    requestRawMock.mockRejectedValueOnce(networkError)

    await expect(getModernCaseQcSnapshot(baseIdentity)).rejects.toBe(networkError)
  })

  it('409 / 503 原样抛出，不吞异常', async () => {
    const conflict = Object.assign(new Error('conflict'), {
      response: { status: 409, data: { success: false, error: 'IDENTITY_CONFLICT' } },
    })
    requestRawMock.mockRejectedValueOnce(conflict)
    await expect(getModernCaseQcSnapshot(baseIdentity)).rejects.toBe(conflict)

    const unavailable = Object.assign(new Error('service unavailable'), {
      response: { status: 503, data: { success: false, error: 'SNAPSHOT_UNAVAILABLE' } },
    })
    requestRawMock.mockRejectedValueOnce(unavailable)
    await expect(getModernCaseQcSnapshot(baseIdentity)).rejects.toBe(unavailable)
  })

  it('200 但信封畸形时失败关闭', async () => {
    requestRawMock.mockResolvedValueOnce(
      okResponse({ success: false, error: 'IDENTITY_REQUIRED', data: buildPayload() }),
    )
    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'malformed_envelope')

    requestRawMock.mockResolvedValueOnce(okResponse({ success: true, data: [] }))
    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'malformed_envelope')

    requestRawMock.mockResolvedValueOnce(okResponse(buildPayload()))
    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'malformed_envelope')
  })

  it('200 但数组字段畸形时失败关闭，不补空数组', async () => {
    requestRawMock.mockResolvedValueOnce(
      envelopeResponse(buildPayload({ recent_results: {} })),
    )
    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'malformed_payload')

    requestRawMock.mockResolvedValueOnce(
      envelopeResponse(buildPayload({ active_defects: ['d-1'] })),
    )
    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'malformed_payload')

    const { current_result_defects: _dropped, ...withoutCurrentDefects } = buildPayload()
    requestRawMock.mockResolvedValueOnce(envelopeResponse(withoutCurrentDefects))
    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'malformed_payload')

    requestRawMock.mockResolvedValueOnce(
      envelopeResponse(buildPayload({ latest_notification: 'none' })),
    )
    await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'malformed_payload')
  })

  it('非 200 状态失败关闭', async () => {
    requestRawMock.mockResolvedValueOnce(okResponse({ success: true, data: buildPayload() }, 204))

    const error = await expectErrorCode(getModernCaseQcSnapshot(baseIdentity), 'unexpected_status')
    expect(error.details).toMatchObject({ status: 204 })
  })
})
