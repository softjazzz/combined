import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import QcRecordColumnSettings from '@/views/workstation-v4/components/qc/QcRecordColumnSettings.vue'
import type { QcRecordOptionalColumn } from '@/views/workstation-v4/components/qc/qcRecordColumnPreferences'

const mocks = vi.hoisted(() => ({
  error: vi.fn(),
}))

vi.mock('ant-design-vue', () => ({
  message: { error: mocks.error },
}))

const availableColumns: QcRecordOptionalColumn[] = [
  'department',
  'time',
  'summary',
  'latestQc',
  'score',
]
const defaultColumns: QcRecordOptionalColumn[] = [
  'department',
  'time',
  'summary',
  'latestQc',
  'score',
]

function mountSettings(
  overrides: Partial<{
    userId: string
    carePhase: 'inpatient' | 'discharged'
    modelValue: QcRecordOptionalColumn[]
  }> = {},
) {
  return mount(QcRecordColumnSettings, {
    props: {
      userId: 'qc-user-a',
      carePhase: 'inpatient',
      modelValue: [...defaultColumns],
      availableColumns,
      defaultColumns,
      ...overrides,
    },
  })
}

function lastColumns(wrapper: ReturnType<typeof mountSettings>): QcRecordOptionalColumn[] {
  const updates = wrapper.emitted('update:modelValue') ?? []
  return updates.at(-1)?.[0] as QcRecordOptionalColumn[]
}

describe('QcRecordColumnSettings', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    window.localStorage.clear()
    mocks.error.mockReset()
  })

  it('展示固定列说明和所有允许的选配列', () => {
    const wrapper = mountSettings()

    expect(wrapper.get('[data-testid="qc-record-column-settings-trigger"]').attributes()).toMatchObject({
      title: '自定义列表列',
      'aria-label': '自定义列表列',
    })
    expect(wrapper.get('[aria-label="固定列"]').text()).toContain('选择、患者身份、操作')
    expect(
      wrapper.findAll('[data-testid^="qc-record-column-"][type="checkbox"]'),
    ).toHaveLength(5)
  })

  it('保存后同一用户同一阶段刷新复用，另一用户和另一阶段不串配置', async () => {
    const wrapper = mountSettings()
    await wrapper.get('[data-testid="qc-record-column-time"]').setValue(false)
    expect(lastColumns(wrapper)).toEqual(['department', 'summary', 'latestQc', 'score'])
    expect(JSON.parse(window.localStorage.getItem('medqc:qc-record-columns:v1:qc-user-a:inpatient')!)).toEqual({
      version: 1,
      columns: ['department', 'summary', 'latestQc', 'score'],
    })

    const refreshed = mountSettings()
    expect(lastColumns(refreshed)).toEqual(['department', 'summary', 'latestQc', 'score'])

    await refreshed.setProps({ userId: 'qc-user-b' })
    expect(lastColumns(refreshed)).toEqual(defaultColumns)
    await refreshed.setProps({ userId: 'qc-user-a', carePhase: 'discharged' })
    expect(lastColumns(refreshed)).toEqual(defaultColumns)
    await refreshed.setProps({ carePhase: 'inpatient' })
    expect(lastColumns(refreshed)).toEqual(['department', 'summary', 'latestQc', 'score'])
  })

  it('退出后的无 id 状态只在内存更新且不读写上一用户配置', async () => {
    window.localStorage.setItem(
      'medqc:qc-record-columns:v1:qc-user-a:inpatient',
      JSON.stringify({ version: 1, columns: ['summary'] }),
    )
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const wrapper = mountSettings({ userId: '' })

    expect(lastColumns(wrapper)).toEqual(defaultColumns)
    await wrapper.get('[data-testid="qc-record-column-time"]').setValue(false)
    expect(lastColumns(wrapper)).toEqual(['department', 'summary', 'latestQc', 'score'])
    expect(setItem).not.toHaveBeenCalled()
    expect(window.localStorage.getItem('medqc:qc-record-columns:v1:qc-user-a:inpatient')).not.toBeNull()
  })

  it('恢复默认会持久化默认列，刷新后继续使用默认列', async () => {
    window.localStorage.setItem(
      'medqc:qc-record-columns:v1:qc-user-a:inpatient',
      JSON.stringify({ version: 1, columns: ['summary'] }),
    )
    const wrapper = mountSettings({ modelValue: ['summary'] })
    expect(lastColumns(wrapper)).toEqual(['summary'])

    await wrapper.get('[data-testid="qc-record-column-restore-default"]').trigger('click')
    expect(lastColumns(wrapper)).toEqual(defaultColumns)
    expect(JSON.parse(window.localStorage.getItem('medqc:qc-record-columns:v1:qc-user-a:inpatient')!)).toEqual({
      version: 1,
      columns: defaultColumns,
    })

    expect(lastColumns(mountSettings())).toEqual(defaultColumns)
  })

  it('浏览器存储失败时明确提示且不发出成功更新', async () => {
    const wrapper = mountSettings()
    const initialUpdateCount = wrapper.emitted('update:modelValue')?.length ?? 0
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage disabled')
    })

    const timeCheckbox = wrapper.get<HTMLInputElement>('[data-testid="qc-record-column-time"]')
    await timeCheckbox.setValue(false)

    expect(mocks.error).toHaveBeenCalledWith('列设置无法保存，请检查浏览器存储权限')
    expect(wrapper.emitted('update:modelValue')).toHaveLength(initialUpdateCount)
    expect(timeCheckbox.element.checked).toBe(true)
  })

  it('读取 localStorage 本身被浏览器拒绝时加载降级，保存提示且复选框回弹', async () => {
    const localStorageGetter = vi
      .spyOn(window, 'localStorage', 'get')
      .mockImplementation(() => {
        throw new DOMException('access denied', 'SecurityError')
      })

    const wrapper = mountSettings()
    expect(lastColumns(wrapper)).toEqual(defaultColumns)

    const initialUpdateCount = wrapper.emitted('update:modelValue')?.length ?? 0
    const timeCheckbox = wrapper.get<HTMLInputElement>('[data-testid="qc-record-column-time"]')
    await timeCheckbox.setValue(false)

    expect(mocks.error).toHaveBeenCalledWith('列设置无法保存，请检查浏览器存储权限')
    expect(wrapper.emitted('update:modelValue')).toHaveLength(initialUpdateCount)
    expect(timeCheckbox.element.checked).toBe(true)
    localStorageGetter.mockRestore()
  })
})
