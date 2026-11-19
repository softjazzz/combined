import { describe, expect, it } from 'vitest'
import type { DocItem } from '@/views/workstation-v4/types'
import {
  buildFallbackTreeFromDocs,
  resolveDocDisplayTitle,
  resolveMaterialDisplayNotice,
  resolveMaterialScopeNotice,
} from '@/views/workstation-v4/utils/documentDisplay'

describe('病历池文书目录', () => {
  function document(id: string, type: string, label: string): DocItem {
    return { id, type, doc_type: type, label, has_content: true, content: null, length: 0 }
  }

  it('没有会诊文书时，病程仍位于入院之后、检查和医嘱之前', () => {
    const tree = buildFallbackTreeFromDocs([
      document('discharge', 'discharge_record', '出院记录'),
      document('order', 'medical_order', '医嘱'),
      document('exam', 'exam_item_report', 'CT检查报告'),
      document('course', 'daily_course_record', '日常病程记录'),
      document('admission', 'admission_record', '入院记录'),
    ])

    expect(tree.map(({ key }) => key)).toEqual([
      'admission',
      'course',
      'exam_lab',
      'orders',
      'discharge',
    ])
  })

  it('结构化上级查房以文书类型为准，普通查房保留原分组和标题', () => {
    const upperRound = {
      ...document('senior', 'senior_course_record', '主治医师查房记录'),
      doc_key: 'senior_course_record::senior',
    }
    const ordinaryRound = document('ordinary', 'daily_course_record', '主治医师查房记录')
    const [group] = buildFallbackTreeFromDocs([upperRound, ordinaryRound])

    expect(group.subgroups).toMatchObject([
      {
        key: 'course.senior',
        children: [{ title: '上级医师查房记录', doc_key: upperRound.doc_key }],
      },
      { key: 'course.ordinary', children: [{ title: '主治医师查房记录' }] },
    ])
  })
})

describe('材料来源提示纯投影', () => {
  it('目录显示已选来源及完整版本，保留旧文书标题', () => {
    const doc = { type: 'daily_course_record', label: '日常病程记录', version_id: 'clinical-v1', material_source_label: 'clinical', material_selected: true, material_rule_usable: true }
    expect(resolveMaterialDisplayNotice(doc)).toContain('clinical · 版本：clinical-v1 · 已选中')
    expect(resolveDocDisplayTitle({ type: 'daily_course_record', label: '日常病程记录', content: '' })).toBe('日常病程记录')
  })

  it('直接显示冲突及HELD提示，不把可见材料当成已选事实', () => {
    const doc = { version_id: 'cache-v2', material_source_label: 'Caché', material_selected: false, material_rule_usable: false, material_notice: '替代版本；内容冲突；状态待核（HELD）' }
    expect(resolveMaterialDisplayNotice(doc)).toBe('Caché · 版本：cache-v2 · 仅展示，未选用 · 规则暂不可用 · 替代版本；内容冲突；状态待核（HELD）')
    expect(resolveMaterialDisplayNotice({ material_notice: '旧材料提示' })).toBe('旧材料提示')
  })

  it('优先搬运四类范围提示，旧daily与PDF缺字段安全回退', () => {
    expect(resolveMaterialScopeNotice({ primary_material_status: { notice: '来源未覆盖；尚未发布；状态待核' }, daily_material_status: { notice: '旧提示' } })).toBe('来源未覆盖；尚未发布；状态待核')
    expect(resolveMaterialScopeNotice({ daily_material_status: { notice: '旧提示' } })).toBe('旧提示')
    expect(resolveMaterialScopeNotice({ documents: [] })).toBe('')
  })

  it('四类状态按后端结果逐类显示，不将空来源判定为未书写', () => {
    const notice = resolveMaterialScopeNotice({ primary_material_status: { notice: '来源覆盖待核', kinds: { daily_course_record: { status: 'AVAILABLE', notice: '部分字段待核' }, presurg_summary: { status: 'HELD', notice: '等待批准发布' }, surgery_record: { status: 'EMPTY_UNCONFIRMED', notice: '来源未覆盖' }, postsurg_firstcourse_record: { status: 'NOT_DEPLOYED', notice: '接口未部署' } } } })
    expect(notice).toContain('日常病程记录：材料可用（部分字段待核）')
    expect(notice).toContain('术前小结：状态待核（等待批准发布）')
    expect(notice).toContain('手术记录：暂无可用版本，不能判定未书写（来源未覆盖）')
    expect(notice).toContain('术后首次病程记录：接口未部署')
  })
})
