import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import QcDiagnosticExport from '@/components/qc/QcDiagnosticExport.vue'

const { prepareDiagnostic, downloadDiagnostic, discardDiagnostic, downloadBlob } = vi.hoisted(
  () => ({
    prepareDiagnostic: vi.fn(),
    downloadDiagnostic: vi.fn(),
    discardDiagnostic: vi.fn(),
    downloadBlob: vi.fn(),
  }),
)
vi.mock('@/services/qc-diagnostics-service', () => ({
  prepareDiagnostic,
  downloadDiagnostic,
  discardDiagnostic,
}))
vi.mock('@/views/workstation-v4/customer-sample-validation/batchExport', () => ({ downloadBlob }))

function render() {
  return mount(QcDiagnosticExport, {
    props: {
      selection: {
        job_id: 'job',
        record_ref: 'ref',
        institute_id: 'i',
        patient_id: 'p',
        visit_id: 'v',
      },
    },
    global: {
      stubs: {
        'a-button': { template: '<button :disabled="$attrs.disabled"><slot /></button>' },
        'a-modal': { props: ['open'], template: '<section v-if="open"><slot /></section>' },
        'a-spin': { template: '<div><slot /></div>' },
        'a-alert': { props: ['message'], template: '<p>{{ message }}</p>' },
        'a-checkbox': {
          props: ['checked'],
          emits: ['update:checked'],
          template:
            '<input type="checkbox" :checked="checked" @change="$emit(\'update:checked\', $event.target.checked)" />',
        },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  discardDiagnostic.mockResolvedValue(undefined)
  downloadDiagnostic.mockResolvedValue(new Blob(['safe']))
  prepareDiagnostic.mockResolvedValue({
    token: 'safe-token',
    notice: '历史受限包，不是完整质控复现。',
    included: ['规则编号与保存状态'],
    excluded: ['患者身份和病历正文'],
    expires_in_seconds: 300,
    preview: {
      results: [{ rule_id: 'LX0609-032', supported: true, current_findings: '受控文案' }],
    },
  })
})

describe('诊断导包', () => {
  it('只传任务与病历引用，预览确认后才能下载', async () => {
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(prepareDiagnostic).toHaveBeenCalledWith({
      job_id: 'job',
      record_ref: 'ref',
      institute_id: 'i',
      patient_id: 'p',
      visit_id: 'v',
    })
    expect(wrapper.text()).toContain('不是完整质控复现')
    const download = wrapper.findAll('button').find((button) => button.text() === '下载诊断包')!
    expect(download.attributes('disabled')).toBeDefined()
    await wrapper.get('input').setValue(true)
    await download.trigger('click')
    await flushPromises()
    expect(downloadDiagnostic).toHaveBeenCalledWith('safe-token')
    expect(downloadBlob).toHaveBeenCalledTimes(1)
    wrapper.unmount()
    expect(discardDiagnostic).toHaveBeenCalledWith('safe-token')
  })

  it('切换病例后丢弃迟到的预览，不串包', async () => {
    let resolve!: (value: unknown) => void
    prepareDiagnostic.mockReturnValue(
      new Promise((done) => {
        resolve = done
      }),
    )
    const wrapper = render()
    await wrapper.get('button').trigger('click')
    await wrapper.setProps({
      selection: {
        job_id: 'other',
        record_ref: 'other-ref',
        institute_id: 'i',
        patient_id: 'p',
        visit_id: 'v',
      },
    })
    resolve({ token: 'late-token' })
    await flushPromises()
    expect(discardDiagnostic).toHaveBeenCalledWith('late-token')
    expect(downloadBlob).not.toHaveBeenCalled()
    wrapper.unmount()
  })
})
