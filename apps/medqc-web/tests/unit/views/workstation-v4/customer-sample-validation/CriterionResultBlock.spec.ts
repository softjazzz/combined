import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { compileStyle } from '@vue/compiler-sfc'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CriterionResultBlock from '@/views/workstation-v4/customer-sample-validation/CriterionResultBlock.vue'
import type { SingleRecordQcCriterionResult } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'

const criteria: SingleRecordQcCriterionResult[] = [
  {
    criterion_id: 'chief_complaint_length',
    kind: 'text_length',
    status: 'passed',
    reason_code: 'requirement_satisfied',
    actual_value: 14,
    expected_value: 20,
  },
  {
    criterion_id: 'diagnostic_direction',
    kind: 'semantic_relation',
    status: 'failed',
    reason_code: 'complaint_primary_diagnosis_mismatch',
    medical_analysis: '主诉缺少区分第一诊断的特异性表现与病程线索。',
  },
]

describe('CriterionResultBlock', () => {
  it('compliant variant 保留合规依据完整 DOM、文案和状态类，并直接展示医学分析', () => {
    const wrapper = mount(CriterionResultBlock, {
      props: { criteria, variant: 'compliant' },
    })

    const block = wrapper.get('[data-testid="single-record-compliant-criteria"]')
    expect(block.element.tagName).toBe('SECTION')
    expect(block.classes()).toEqual(
      expect.arrayContaining(['detail-block', 'criterion-block', 'compliant-criterion-block']),
    )
    expect(block.get('h4').text()).toBe('合规依据')

    const rows = block.findAll('article.criterion-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.get('.criterion-head strong').text()).toBe('主诉书写规范性')
    expect(rows[0]!.get('.criterion-head span').classes()).toContain('is-passed')
    expect(rows[0]!.get('.criterion-head span').text()).toBe('通过')
    expect(rows[0]!.get('p').text()).toBe('主诉共 14 字；标准为不超过 20 字。')
    expect(rows[1]!.get('.criterion-head strong').text()).toBe('诊断指向性')
    expect(rows[1]!.get('.criterion-head span').classes()).toContain('is-failed')
    expect(rows[1]!.get('.criterion-head span').text()).toBe('未通过')
    expect(rows[1]!.get('p.criterion-analysis').text()).toBe(
      '主诉缺少区分第一诊断的特异性表现与病程线索。',
    )
    expect(rows[1]!.find('details.medical-analysis').exists()).toBe(false)
  })

  it('decision variant 保留逐项判定 DOM，并将医学分析放在默认收起的 details 中', () => {
    const wrapper = mount(CriterionResultBlock, {
      props: { criteria, variant: 'decision' },
    })

    const block = wrapper.get('section.detail-block.criterion-block')
    expect(block.classes()).not.toContain('compliant-criterion-block')
    expect(block.attributes('data-testid')).toBeUndefined()
    expect(block.get('h4').text()).toBe('逐项判定')
    expect(block.findAll('article.criterion-row')).toHaveLength(2)

    const analysis = block.get('details.medical-analysis')
    expect(analysis.attributes('open')).toBeUndefined()
    expect(analysis.get('summary').text()).toBe('查看医学分析')
    // 已通过子项压成一行，未通过子项完整展示；状态由定制图标表达
    const rows = block.findAll('article.criterion-row')
    expect(rows[0]!.classes()).toContain('is-passed')
    expect(rows[1]!.classes()).toContain('is-failed')
    expect(rows[0]!.find('svg.mq-icon').exists()).toBe(true)
    expect(analysis.get('p').text()).toBe('主诉缺少区分第一诊断的特异性表现与病程线索。')
  })

  it('保留未知状态的原始 class，并冻结 chief、diagnostic、generic 的边界文案', () => {
    const edgeCriteria: SingleRecordQcCriterionResult[] = [
      {
        criterion_id: 'chief_complaint_length',
        kind: 'text_length',
        status: 'unknown',
        reason_code: 'unknown',
        actual_value: null,
        expected_value: 0,
      },
      {
        criterion_id: 'diagnostic_direction',
        kind: 'semantic_relation',
        status: 'review_pending',
        reason_code: 'unknown',
      },
      {
        criterion_id: 'unmapped_criterion',
        kind: 'other',
        status: 'failed',
        reason_code: 'unknown',
        actual_value: false,
        expected_value: null,
      },
      {
        criterion_id: 'empty_criterion',
        kind: 'other',
        status: 'passed',
        reason_code: 'unknown',
      },
    ]

    const wrapper = mount(CriterionResultBlock, {
      props: { criteria: edgeCriteria, variant: 'decision' },
    })
    const rows = wrapper.findAll('article.criterion-row')

    expect(rows[0]!.get('.criterion-head strong').text()).toBe('主诉书写规范性')
    expect(rows[0]!.get('.criterion-head span').classes()).toContain('is-unknown')
    expect(rows[0]!.get('.criterion-head span').text()).toBe('待确认')
    expect(rows[0]!.get('p').text()).toBe('主诉共 未返回 字；标准为不超过 0 字。')

    expect(rows[1]!.get('.criterion-head strong').text()).toBe('诊断指向性')
    expect(rows[1]!.get('.criterion-head span').classes()).toContain('is-review_pending')
    expect(rows[1]!.get('.criterion-head span').text()).toBe('待确认')
    expect(rows[1]!.get('p').text()).toBe('当前资料不足以完成主诉与第一诊断的医学指向核对。')

    expect(rows[2]!.get('.criterion-head strong').text()).toBe('子项核对')
    expect(rows[2]!.get('p').text()).toBe('实际值：false；标准：null。')
    expect(rows[3]!.get('p').text()).toBe('该子项已按规则要求完成核对。')
  })

  it('criteria 为空时不渲染 criterion block', () => {
    const wrapper = mount(CriterionResultBlock, {
      props: { criteria: [], variant: 'compliant' },
    })

    expect(wrapper.find('section').exists()).toBe(false)
    expect(wrapper.html()).toBe('<!--v-if-->')
  })

  it('scoped CSS 不使用 global/deep，并保留 criterion 所需的局部基础样式', () => {
    const source = readFileSync(
      resolve(
        process.cwd(),
        'src/views/workstation-v4/customer-sample-validation/CriterionResultBlock.vue',
      ),
      'utf8',
    )
    const styleSource = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1]
    expect(styleSource).toBeTruthy()

    const compiled = compileStyle({
      source: styleSource || '',
      filename: 'CriterionResultBlock.vue',
      id: 'data-v-criterion-result-block',
      scoped: true,
    })
    expect(compiled.errors).toEqual([])
    expect(compiled.code).not.toMatch(/:(?:global|deep)/)
    for (const selector of [
      '.detail-block h4',
      '.detail-block p',
      '.criterion-block',
      '.criterion-row',
      '.medical-analysis summary',
      '.medical-analysis p',
    ]) {
      expect(compiled.code).toContain(selector)
    }
  })
})
