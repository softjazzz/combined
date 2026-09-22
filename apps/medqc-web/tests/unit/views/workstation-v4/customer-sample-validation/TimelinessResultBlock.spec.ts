import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { compileStyle, parse } from '@vue/compiler-sfc'
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TimelinessResultBlock from '@/views/workstation-v4/customer-sample-validation/TimelinessResultBlock.vue'
import type { SingleRecordQcResultItem } from '@/views/workstation-v4/customer-sample-validation/single-record-result-model'
import {
  hasTimelinessResult,
  timelinessResultRows,
} from '@/views/workstation-v4/customer-sample-validation/timelinessResultPresentation'

const componentPath = resolve(
  process.cwd(),
  'src/views/workstation-v4/customer-sample-validation/TimelinessResultBlock.vue',
)

function buildItem(
  status: SingleRecordQcResultItem['status'],
  customer_display_facts?: Record<string, unknown>,
): SingleRecordQcResultItem {
  return {
    rule_id: 'LX0609-01-02-01',
    rule_name: '首次病程记录',
    status,
    conclusion: '已核对时限事实。',
    customer_display_facts,
  }
}

describe('TimelinessResultBlock', () => {
  it('合规结果按固定顺序展示指标和时间轴，且不高亮超出时限', () => {
    const wrapper = mount(TimelinessResultBlock, {
      props: {
        item: buildItem('compliant', {
          source_label: '首次病程记录',
          anchor_time: '2026-06-20 17:19:08',
          observed_time: '2026-06-20 19:23:45',
          threshold_hours: 24,
          elapsed_hours: 2.08,
          overdue_hours: 0,
        }),
        variant: 'compliant',
      },
    })

    const metrics = wrapper.get('[data-testid="timeliness-metrics"]')
    expect(metrics.classes()).toContain('is-compliant')
    expect(metrics.classes()).toContain('has-3-metrics')
    expect(metrics.text()).toContain('规定时限24 小时')
    expect(metrics.text()).toContain('实际间隔2.08 小时')
    expect(metrics.text()).toContain('超出时限0 小时')
    expect(metrics.find('.is-overdue').exists()).toBe(false)
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain('入院时间')
    expect(wrapper.get('[data-testid="timeliness-timeline"]').classes()).toContain('is-compliant')
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain('首次病程记录时间')
  })

  it('非合规结果只在明确强调时限时高亮 overdue_hours', () => {
    const wrapper = mount(TimelinessResultBlock, {
      props: {
        item: buildItem('non_compliant', {
          anchor_time: '2026-06-20 17:19:08',
          observed_time: '2026-07-09 09:54:57',
          threshold_hours: 8,
          elapsed_hours: 448.6,
          overdue_hours: 440.6,
        }),
        variant: 'decision',
      },
    })

    expect(wrapper.findAll('.timeliness-metric.is-overdue')).toHaveLength(1)
    expect(wrapper.get('[data-testid="timeliness-metrics"]').classes()).toContain('is-decision')
    expect(wrapper.get('[data-testid="timeliness-timeline"]').classes()).toContain('is-decision')
    expect(wrapper.get('.timeliness-metric.is-overdue').text()).toContain('440.6 小时')
  })

  it('只有时间轴事实时不生成空指标带', () => {
    const item = buildItem('data_gap', {
      anchor_time: '2026-06-20 17:19:08',
      observed_time: '2026-07-09 09:54:57',
    })
    const wrapper = mount(TimelinessResultBlock, { props: { item, variant: 'decision' } })

    expect(wrapper.find('[data-testid="timeliness-metrics"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="timeliness-timeline"]').text()).toContain(
      '2026-06-20 17:19:08',
    )
    expect(timelinessResultRows(item).map((row) => row.key)).toEqual([
      'anchor_time',
      'observed_time',
    ])
    expect(hasTimelinessResult(item)).toBe(true)
  })

  it('合规结果只有时间轴或单一指标时保持独立区域与列数', () => {
    const timelineOnly = mount(TimelinessResultBlock, {
      props: {
        item: buildItem('compliant', { anchor_time: '2026-06-20 17:19:08' }),
        variant: 'compliant',
      },
    })
    expect(timelineOnly.find('[data-testid="timeliness-metrics"]').exists()).toBe(false)
    expect(timelineOnly.find('[data-testid="timeliness-timeline"]').exists()).toBe(true)

    const metricOnly = mount(TimelinessResultBlock, {
      props: {
        item: buildItem('compliant', { threshold_hours: 24 }),
        variant: 'compliant',
      },
    })
    expect(metricOnly.get('[data-testid="timeliness-metrics"]').classes()).toEqual([
      'timeliness-metrics',
      'is-compliant',
      'has-1-metrics',
    ])
    expect(metricOnly.find('[data-testid="timeliness-timeline"]').exists()).toBe(false)
  })

  it('没有时限事实时不生成任何指标或时间轴内容', () => {
    const item = buildItem('non_compliant', {
      failure_kind: 'timeliness_requirement_not_met',
      target_document: 'first_course_record',
    })
    const wrapper = mount(TimelinessResultBlock, { props: { item, variant: 'decision' } })

    expect(wrapper.find('[data-testid="timeliness-metrics"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="timeliness-timeline"]').exists()).toBe(false)
    expect(timelinessResultRows(item)).toEqual([])
    expect(hasTimelinessResult(item)).toBe(false)
  })

  it('保留旧事实值转换语义：受控枚举、布尔值、空值、数组和非有限数字', () => {
    const item = buildItem('data_gap', {
      anchor_time: 'unknown',
      observed_time: ['unknown', 'none'],
      threshold_hours: true,
      elapsed_hours: false,
      overdue_hours: Number.NaN,
    })

    expect(timelinessResultRows(item)).toEqual([
      { key: 'threshold_hours', label: '规定时限', value: '是' },
      { key: 'elapsed_hours', label: '实际间隔', value: '否' },
      { key: 'overdue_hours', label: '超出时限', value: 'NaN' },
      { key: 'anchor_time', label: '入院时间', value: '暂无法确认' },
      { key: 'observed_time', label: '记录时间', value: '暂无法确认、未实施手术' },
    ])
  })

  it('时限模块样式保持 scoped，且不依赖裸祖先选择器', () => {
    const source = readFileSync(componentPath, 'utf8')
    const descriptor = parse(source, { filename: componentPath }).descriptor
    const style = descriptor.styles.find((candidate) => candidate.scoped)
    expect(style).toBeDefined()
    if (!style) return

    const compiled = compileStyle({
      source: style.content,
      filename: componentPath,
      id: 'data-v-timeliness-test',
      scoped: true,
    })
    expect(compiled.errors).toEqual([])
    expect(compiled.code).not.toContain('.compliant-detail')
    expect(compiled.code).not.toContain(':global')
    expect(compiled.code).toContain('.timeliness-metrics.is-compliant[data-v-timeliness-test]')
  })
})
