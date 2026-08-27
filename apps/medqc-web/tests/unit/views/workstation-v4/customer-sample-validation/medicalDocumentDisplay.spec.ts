import { describe, expect, it } from 'vitest'
import { resolveMedicalDocumentGroup } from '@/views/workstation-v4/customer-sample-validation/medicalDocumentDisplay'

describe('medicalDocumentDisplay', () => {
  it.each([
    { document_type: 'presurg_summary', title: '术前小结记录' },
    { document_type: 'custom_document', title: '术前小结' },
  ])('将术前小结归入手术麻醉分组', (document) => {
    expect(
      resolveMedicalDocumentGroup({
        key: 'presurg-summary',
        content: '',
        enabled: true,
        ...document,
      }),
    ).toEqual({ key: 'surgery', label: '手术麻醉' })
  })
})
