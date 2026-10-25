import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Communication } from '@/api/caseCommunications'
import History from '@/components/qc/CaseCommunicationHistory.vue'
import { communicationStatus, communicationStatusClass, formatCommunicationTime } from '@/components/qc/caseCommunicationPresentation'

const original: Communication = {
  id: 'urge1', institute_id: 'H', patient_id: 'P', visit_id: 'V', scene: 'running',
  root_job_id: 'J', envelope_id: 'E', rule_set_key: 'K', rule_set_version: '1',
  actor_id: 'qc', recipient_id: 'doc', request_id: 'r1', notification_id: 'n1',
  action: 'urge', content: '原催办说明', related_event_id: null,
  is_read: false, read_at: null, withdrawn: true, department: '内科', created_at: '2026-10-25T07:28:21Z',
}
describe('病历沟通时间线展示', () => {
  it('原催办与撤回分别保留、精确标记目标并折叠完整事件身份', () => {
    const withdrawal: Communication = { ...original, id: 'withdraw1', action: 'withdraw', related_event_id: 'urge1', content: '本次撤回', withdrawn: false }
    const items = [withdrawal, original]
    const before = JSON.stringify(items)
    const wrapper = mount(History, { props: { items, activeId: 'withdraw1', recipientLabel: () => '医生甲' } })
    expect(wrapper.findAll('li')).toHaveLength(2)
    expect(wrapper.findAll('li.is-active')).toHaveLength(1)
    expect(wrapper.get('li.is-active').text()).toContain('当前查看')
    expect(wrapper.get('li.is-active').text()).toContain('原催办：urge1')
    expect(wrapper.get('li.is-active').text()).toContain('受领医生 · 医生甲')
    expect(wrapper.findAll('li')[1].text()).toContain('已撤回')
    expect(wrapper.get('details').attributes('open')).toBeUndefined()
    expect(wrapper.get('time').attributes('datetime')).toBe(original.created_at)
    expect(wrapper.get('time').text()).toBe('2026/10/25 15:28')
    expect(JSON.stringify(items)).toBe(before)
    wrapper.unmount()
  })
  it('未读撤回事件不误标成已撤回或已读', () => {
    const notice = { ...original, action: 'withdraw', withdrawn: false, is_read: false }
    expect(communicationStatus(notice)).toBe('未读')
    expect(communicationStatusClass(notice)).toBe('mq-status--info')
    expect(communicationStatus(original)).toBe('已撤回')
    expect(communicationStatusClass(original)).toBe('')
  })
  it('北京时间展示支持UTC、无时区保存值及未知时间，不编造日期', () => {
    expect(formatCommunicationTime('2026-10-25T07:28:21')).toBe('2026/10/25 15:28')
    expect(formatCommunicationTime('2026-10-25T15:28:21+08:00')).toBe('2026/10/25 15:28')
    expect(formatCommunicationTime('invalid')).toBe('invalid')
    expect(formatCommunicationTime(null)).toBe('时间未提供')
  })
})
