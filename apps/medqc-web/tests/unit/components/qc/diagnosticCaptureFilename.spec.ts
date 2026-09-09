import { describe, expect, it } from 'vitest'
import { diagnosticCaptureFilename } from '@/components/qc/diagnosticCaptureFilename'

describe('排障包文件名', () => {
  it('按患者、同次就诊和实际采集任务区分文件', () => {
    const context = { patientName: '测试患者', visitId: '2207717', jobId: 'old-job' }
    expect(diagnosticCaptureFilename(context, 'capture-1')).toBe(
      '质控排障包_测试患者_就诊-2207717_任务-capture-1.zip',
    )
    expect(diagnosticCaptureFilename(context, 'capture-2')).not.toBe(
      diagnosticCaptureFilename(context, 'capture-1'),
    )
  })

  it('清理路径字符，缺少姓名时保留病历定位', () => {
    expect(diagnosticCaptureFilename({ recordId: 'a/b:c' }, 'job')).toBe(
      '质控排障包_未命名患者_就诊-a-b-c_任务-job.zip',
    )
  })
})
