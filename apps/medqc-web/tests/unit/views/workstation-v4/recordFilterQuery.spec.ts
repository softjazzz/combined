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
    expect(mergeRecordFilterQuery({ tab: 'x' }, {}, true)).toEqual({
      tab: 'x',
      review_scope: 'all',
    })
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

  it('评分筛选在 URL 中完整往返，并忽略非法状态或非数值', () => {
    const parsed = parseRecordFilterQuery({
      standard_id: '11111111-1111-4111-8111-111111111111',
      score_status: 'scored',
      grade: ' 甲 ',
      score_min: '80',
      score_max: '99.5',
    })
    expect(parsed).toEqual({
      standard_id: '11111111-1111-4111-8111-111111111111',
      score_status: 'scored',
      grade: '甲',
      score_min: 80,
      score_max: 99.5,
    })
    expect(mergeRecordFilterQuery({ tab: 'records' }, parsed)).toEqual({
      tab: 'records',
      standard_id: '11111111-1111-4111-8111-111111111111',
      score_status: 'scored',
      grade: '甲',
      score_min: '80',
      score_max: '99.5',
    })
    expect(parseRecordFilterQuery({ score_status: 'bogus', score_min: 'NaN' })).toEqual({})
  })

  it('缺陷视图、来源和病例缺陷状态在 URL 中完整往返', () => {
    const parsed = parseRecordFilterQuery({
      result_view: 'defects',
      defect_source: 'manual',
      has_defect: 'true',
    })
    expect(parsed).toEqual({
      result_view: 'defects',
      defect_source: 'manual',
      has_defect: true,
    })
    expect(mergeRecordFilterQuery({}, parsed)).toEqual({
      result_view: 'defects',
      defect_source: 'manual',
      has_defect: 'true',
    })
    expect(parseRecordFilterQuery({ result_view: 'bogus', has_defect: 'unknown' })).toEqual({})
  })

  it('视图与缺陷来源按各自枚举边界独立解析和写回', () => {
    const parsed = parseRecordFilterQuery({ result_view: 'records', defect_source: 'auto' })
    expect(parsed).toEqual({ result_view: 'records', defect_source: 'auto' })
    expect(mergeRecordFilterQuery({}, parsed)).toEqual({
      result_view: 'records',
      defect_source: 'auto',
    })
    expect(parseRecordFilterQuery({ result_view: 'manual', defect_source: 'defects' })).toEqual({})
  })
})
