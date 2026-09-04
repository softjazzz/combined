import { describe, expect, it } from 'vitest'

import { resolveMedicalDocumentTitle } from '../medicalDocumentTaxonomy'

describe('resolveMedicalDocumentTitle', () => {
  it.each(['CT检查报告', '核磁共振检查报告', '心电图检查报告'])(
    '文书树保留检查报告的明确类型标题：%s',
    (documentTitle) => {
      expect(
        resolveMedicalDocumentTitle({
          document_type: 'exam_item_report',
          source_table: 'exam_item_report',
          document_title: documentTitle,
        }),
      ).toBe(documentTitle)
    },
  )

  it('普通检查报告仍使用既有类型名称', () => {
    expect(
      resolveMedicalDocumentTitle({
        document_type: 'exam_item_report',
        source_table: 'exam_item_report',
        document_title: '检查报告',
      }),
    ).toBe('检查报告')
  })
})
