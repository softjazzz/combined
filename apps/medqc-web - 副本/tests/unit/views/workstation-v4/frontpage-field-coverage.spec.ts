import { describe, expect, it } from 'vitest'
import {
  coverageStatusText,
  extractCoverageFields,
  summarizeCoverageFields,
  topMissingCoverageFields,
} from '@/types/frontpage'

describe('frontpage field coverage helpers', () => {
  it('normalizes report coverage fields and summarizes by group', () => {
    const fields = extractCoverageFields({
      coverage: {
        fields: [
          {
            group: '患者基本信息',
            field: '患者姓名',
            path: 'frontpage.basic_info.patient_name',
            status: 'present',
          },
          {
            group: '患者基本信息',
            field: '身份证号',
            path: 'frontpage.basic_info.id_number',
            status: 'missing',
          },
          { group: '医保结算清单', field: '结算清单草稿', path: 'settlement', status: 'partial' },
        ],
      },
    })

    expect(fields).toHaveLength(3)
    const summaries = summarizeCoverageFields(fields)
    expect(summaries).toEqual([
      {
        group: '患者基本信息',
        total: 2,
        present: 1,
        missing: 1,
        partial: 0,
        status: 'missing',
      },
      {
        group: '医保结算清单',
        total: 1,
        present: 0,
        missing: 0,
        partial: 1,
        status: 'review',
      },
    ])
  })

  it('returns top missing fields and status text', () => {
    const fields = extractCoverageFields({
      fields: [
        { group: 'A', field: '字段1', path: 'a.one', status: 'missing' },
        { group: 'A', field: '字段2', path: 'a.two', status: 'present' },
        { group: 'B', field: '字段3', path: 'b.three', status: 'missing' },
      ],
    })

    expect(topMissingCoverageFields(fields, 1).map((item) => item.field)).toEqual(['字段1'])
    expect(coverageStatusText('completed')).toBe('已完成')
    expect(coverageStatusText('review')).toBe('需复核')
    expect(coverageStatusText('missing')).toBe('有缺失')
  })
})
