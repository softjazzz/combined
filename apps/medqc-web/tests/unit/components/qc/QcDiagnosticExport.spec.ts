import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import QcDiagnosticExport from '@/components/qc/QcDiagnosticExport.vue'
import * as debugExport from '@/views/workstation-v4/customer-sample-validation/qcResultDebugExport'
import type { SingleRecordQcResultItem } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'
import * as captureApi from '@/services/qc-diagnostics-service'
vi.mock('@/services/qc-diagnostics-service', () => ({
  startDiagnosticCapture: vi.fn(),
  getDiagnosticCapture: vi.fn(),
  downloadDiagnosticCapture: vi.fn(),
}))

const { downloadBlob } = vi.hoisted(() => ({ downloadBlob: vi.fn() }))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({ downloadBlob }))
const context = {
  patientName: '张小川',
  patientId: 'PATIENT-SYNTHETIC-009',
  visitId: 'VISIT-SYNTHETIC-009',
}
const item: SingleRecordQcResultItem = {
  rule_id: 'LX0609-01-01-02',
  rule_name: '主诉与第一诊断',
  status: 'non_compliant',
  reason_code: 'diagnosis_mismatch',
  conclusion: '患者张小川，主诉与诊断不一致。',
  detail: '就诊 VISIT-SYNTHETIC-009 需要人工核查。',
  customer_display_facts: { visit_id: 'VISIT-SYNTHETIC-009', mismatch: true },
  evidence: [{ source_ref: 'evidence-synthetic-009', evidence_excerpt: '张小川主诉头痛。' }],
}

function render(items: SingleRecordQcResultItem[] = [item]) {
  return mount(QcDiagnosticExport, {
    props: { items, context: { ...context } },
    global: {
      stubs: {
        'a-button': { template: '<button :disabled="$attrs.disabled"><slot /></button>' },
        'a-modal': {
          props: ['open'],
          emits: ['cancel'],
          template: '<section v-if="open"><slot /></section>',
        },
        'a-alert': { props: ['message'], template: '<p>{{ message }}</p>' },
        'a-checkbox': {
          props: ['checked'],
          emits: ['update:checked'],
          template: `<input type="checkbox" :checked="checked" @change="$emit('update:checked', $event.target.checked)" />`,
        },
      },
    },
  })
}

function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = reject
    reader.readAsText(blob)
  })
}

beforeEach(() => vi.clearAllMocks())
afterEach(() => {
  vi.restoreAllMocks()
  vi.useRealTimers()
})

describe('本地诊断导包', () => {
  it('用真实脱敏器生成全部规则结果，确认后下载同一预览快照', async () => {
    const generate = vi.spyOn(debugExport, 'buildQcResultDebugText')
    const wrapper = render([
      item,
      { rule_id: 'LX0609-07-01-03', rule_name: '其他规则', status: 'compliant' },
    ])
    await wrapper.get('button').trigger('click')
    const preview = wrapper.get('pre').element.textContent!
    expect(generate).toHaveBeenCalledTimes(1)
    expect(preview).toContain('LX0609-01-01-02')
    expect(preview).toContain('LX0609-07-01-03')
    expect(preview).toContain('diagnosis_mismatch')
    expect(preview).toContain('主诉头痛')
    expect(preview).not.toContain(context.patientName)
    expect(preview).not.toContain(context.patientId)
    expect(preview).not.toContain(context.visitId)
    expect(wrapper.text()).toContain('不支持自动回放')
    expect(wrapper.text()).toContain('不自动发送')
    const download = wrapper.findAll('button').find((button) => button.text() === '下载诊断包')!
    expect(download.attributes('disabled')).toBeDefined()
    await download.trigger('click')
    expect(downloadBlob).not.toHaveBeenCalled()
    await wrapper.get('input').setValue(true)
    await download.trigger('click')
    expect(downloadBlob).toHaveBeenCalledTimes(1)
    const [blob, filename] = downloadBlob.mock.calls[0] as [Blob, string]
    expect(filename).toBe('qc-diagnostic.md')
    expect(blob.type).toBe('text/markdown;charset=utf-8')
    expect(await readBlob(blob)).toBe(preview)
    expect(generate).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })

  it.each(['context', 'items'] as const)('%s 变化立即清空预览和确认，不串病例', async (prop) => {
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    await wrapper.get('input').setValue(true)
    if (prop === 'context') await wrapper.setProps({ context: { visitId: 'OTHER-VISIT' } })
    else await wrapper.setProps({ items: [{ ...item, status: 'compliant' }] })
    expect(wrapper.find('pre').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect((wrapper.get('input').element as HTMLInputElement).checked).toBe(false)
    expect(downloadBlob).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('关闭后重新预览必须再次确认', async () => {
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    await wrapper.get('input').setValue(true)
    await wrapper
      .findAll('button')
      .find((button) => button.text() === '取消')!
      .trigger('click')
    expect(wrapper.find('pre').exists()).toBe(false)
    await wrapper.get('button').trigger('click')
    expect((wrapper.get('input').element as HTMLInputElement).checked).toBe(false)
    wrapper.unmount()
  })

  it('空结果禁用入口', async () => {
    const generate = vi.spyOn(debugExport, 'buildQcResultDebugText')
    const wrapper = render([])
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    await wrapper.get('button').trigger('click')
    expect(generate).not.toHaveBeenCalled()
    expect(wrapper.find('pre').exists()).toBe(false)
    wrapper.unmount()
  })

  it('拒绝超过 200 条的结果', async () => {
    const generate = vi.spyOn(debugExport, 'buildQcResultDebugText')
    const wrapper = render(Array.from({ length: 201 }, () => ({ ...item })))
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toContain('超过 200 条')
    expect(generate).not.toHaveBeenCalled()
    expect(wrapper.find('pre').exists()).toBe(false)
    wrapper.unmount()
  })

  it('拒绝超过 2 MiB 的 UTF-8 文本', async () => {
    vi.spyOn(debugExport, 'buildQcResultDebugText').mockReturnValue('中'.repeat(750000))
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toContain('超过 2 MiB')
    expect(wrapper.find('pre').exists()).toBe(false)
    expect(downloadBlob).not.toHaveBeenCalled()
    wrapper.unmount()
  })

  it('生成失败仅显示安全错误，不输出原始异常', async () => {
    vi.spyOn(debugExport, 'buildQcResultDebugText').mockImplementation(() => {
      throw new Error(context.patientName)
    })
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    expect(wrapper.text()).toContain('无法生成诊断包')
    expect(wrapper.text()).not.toContain(context.patientName)
    expect(wrapper.find('pre').exists()).toBe(false)
    expect(downloadBlob).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})

describe('执行排障包采集', () => {
  it('重新进入已完成采集任务时恢复下载，不重新质控', async () => {
    vi.mocked(captureApi.getDiagnosticCapture).mockResolvedValue({
      state: 'ready',
      capture_completeness: 'complete',
    })
    const wrapper = render()
    await wrapper.setProps({
      context: { ...context, instituteId: 'hospital', jobId: 'saved-capture', recordRef: 'ref-1' },
    })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(captureApi.getDiagnosticCapture).toHaveBeenCalledWith('saved-capture')
    expect(wrapper.find('.diagnostic-export__capture').text()).toContain('采集完整')
    expect(
      wrapper
        .findAll('button')
        .find((b) => b.text() === '重新质控并采集排障包')!
        .attributes('disabled'),
    ).toBeDefined()
    expect(captureApi.startDiagnosticCapture).not.toHaveBeenCalled()
    expect(captureApi.downloadDiagnosticCapture).not.toHaveBeenCalled()
    wrapper.unmount()
  })
  async function setup() {
    vi.useFakeTimers()
    vi.mocked(captureApi.startDiagnosticCapture).mockResolvedValue({ job_id: 'capture-1' })
    vi.mocked(captureApi.getDiagnosticCapture)
      .mockRejectedValueOnce({ response: { status: 404 } })
      .mockResolvedValue({ state: 'running' })
    const wrapper = render()
    await wrapper.setProps({
      context: { ...context, instituteId: 'hospital', jobId: 'old-job', recordRef: 'ref-1' },
    })
    await wrapper.get('button').trigger('click')
    await flushPromises()
    return wrapper
  }
  it('传递完整选择，防重复启动，仅确认后下载', async () => {
    const wrapper = await setup()
    vi.mocked(captureApi.getDiagnosticCapture).mockResolvedValue({
      state: 'ready',
      capture_completeness: 'partial',
      missing_components: ['model_outputs'],
    })
    vi.mocked(captureApi.downloadDiagnosticCapture).mockResolvedValue(new Blob(['zip']))
    const start = wrapper.findAll('button').find((b) => b.text() === '重新质控并采集排障包')!
    await start.trigger('click')
    await flushPromises()
    expect(captureApi.startDiagnosticCapture).toHaveBeenCalledWith({
      job_id: 'old-job',
      record_ref: 'ref-1',
      institute_id: 'hospital',
      patient_id: context.patientId,
      visit_id: context.visitId,
    })
    await start.trigger('click')
    expect(captureApi.startDiagnosticCapture).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('采集不完整')
    const button = wrapper.findAll('button').find((b) => b.text() === '下载执行排障包')!
    await button.trigger('click')
    expect(captureApi.downloadDiagnosticCapture).not.toHaveBeenCalled()
    await wrapper.findAll('input')[1].setValue(true)
    await button.trigger('click')
    await flushPromises()
    expect(captureApi.downloadDiagnosticCapture).toHaveBeenCalledWith('capture-1')
    expect(downloadBlob).toHaveBeenCalledTimes(1)
    wrapper.unmount()
  })
  it('关闭停止轮询，重开恢复同一任务，切病例忽略旧响应', async () => {
    const wrapper = await setup()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '重新质控并采集排障包')!
      .trigger('click')
    await flushPromises()
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '取消')!
      .trigger('click')
    await vi.advanceTimersByTimeAsync(9000)
    expect(captureApi.getDiagnosticCapture).toHaveBeenCalledTimes(2)
    let finish!: (value: captureApi.DiagnosticCaptureStatus) => void
    vi.mocked(captureApi.getDiagnosticCapture).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    await wrapper.get('button').trigger('click')
    await wrapper.setProps({ context: { visitId: 'other' } })
    finish({ state: 'ready', capture_completeness: 'complete' })
    await flushPromises()
    await wrapper.get('button').trigger('click')
    expect(wrapper.find('.diagnostic-export__capture').text()).not.toContain('采集完整')
    expect(captureApi.startDiagnosticCapture).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(9000)
    expect(captureApi.getDiagnosticCapture).toHaveBeenCalledTimes(3)
  })
  it('失败状态可见，不显示下载或完整声明', async () => {
    const wrapper = await setup()
    vi.mocked(captureApi.getDiagnosticCapture).mockResolvedValue({
      state: 'failed',
      error_code: 'capture_failed',
    })
    await wrapper
      .findAll('button')
      .find((b) => b.text() === '重新质控并采集排障包')!
      .trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('capture_failed')
    expect(wrapper.text()).not.toContain('下载执行排障包')
    wrapper.unmount()
  })
})
