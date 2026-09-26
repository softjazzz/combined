import { describe, expect, it } from 'vitest'
import {
  hasExplicitRecordQuery,
  isSameRecordFilter,
  mergeRecordFilterQuery,
  parseRecordFilterQuery,
} from '@/views/workstation-v4/composables/recordFilterQuery'

describe('recordFilterQuery', () => {
  it('解析 query：去空白、忽略非法审核状态并按固定顺序去重', () => {
    expect(
      parseRecordFilterQuery({
        department: ' ICU ',
        keyword: '',
        review_state: 'pending_recheck, bogus,pending_review,pending_recheck',
      }),
    ).toEqual({ dept: 'ICU', review_state: ['pending_review', 'pending_recheck'] })
  })

  it('合并 query 时只替换筛选键，保留下钻与定位参数', () => {
    expect(
      mergeRecordFilterQuery(
        { analytics_scope: 'final', record_key: 'k', department: 'old', review_state: 'approved' },
        { doctor: '张医师', review_state: ['doubtful', 'approved'] },
      ),
    ).toEqual({
      analytics_scope: 'final',
      record_key: 'k',
      doctor: '张医师',
      review_state: 'approved,doubtful',
    })
  })

  it('筛选键、record_key 或下钻参数存在才视为显式；无关参数不算', () => {
    expect(hasExplicitRecordQuery({})).toBe(false)
    expect(hasExplicitRecordQuery({ tab: 'records', department: '' })).toBe(false)
    expect(hasExplicitRecordQuery({ review_state: 'pending_review' })).toBe(true)
    expect(hasExplicitRecordQuery({ record_key: 'k' })).toBe(true)
    expect(hasExplicitRecordQuery({ analytics_scope: 'final' })).toBe(true)
  })

  it('review_scope=all 标记：显式写入/移除/沿用，且有审核状态时不写', () => {
    expect(mergeRecordFilterQuery({ tab: 'x' }, {}, true)).toEqual({ tab: 'x', review_scope: 'all' })
    expect(mergeRecordFilterQuery({ review_scope: 'all' }, {}, false)).toEqual({})
    expect(mergeRecordFilterQuery({ review_scope: 'all' }, { doctor: '张' })).toEqual({
      doctor: '张',
      review_scope: 'all',
    })
    expect(
      mergeRecordFilterQuery({ review_scope: 'all' }, { review_state: ['pending_review'] }, true),
    ).toEqual({ review_state: 'pending_review' })
    expect(hasExplicitRecordQuery({ review_scope: 'all' })).toBe(true)
    expect(hasExplicitRecordQuery({ review_scope: 'other' })).toBe(false)
    expect(parseRecordFilterQuery({ review_scope: 'all' })).toEqual({})
  })

  it('比较时忽略空值与审核状态顺序', () => {
    expect(
      isSameRecordFilter(
        { keyword: ' ', review_state: ['pending_recheck', 'pending_review'] },
        { review_state: ['pending_review', 'pending_recheck'] },
      ),
    ).toBe(true)
  })
})
