/* eslint-disable vue/one-component-per-file */
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import BatchResultTraceModal from '@/views/workstation-v4/semantic-rules/components/BatchResultTraceModal.vue'

const AModalStub = defineComponent({
  name: 'AModalStub',
  props: {
    open: Boolean,
    title: {
      type: String,
      default: '',
    },
  },
  emits: ['cancel'],
  setup(props, { emit, slots }) {
    return () =>
      props.open
        ? h('section', { class: 'a-modal-stub', 'data-title': props.title }, [
            h(
              'button',
              {
                'data-testid': 'trace-close',
                onClick: () => emit('cancel'),
              },
              '关闭',
            ),
            slots.default?.(),
          ])
        : null
  },
})

const AAlertStub = defineComponent({
  name: 'AAlertStub',
  props: {
    message: {
      type: String,
      default: '',
    },
    description: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    return () => h('div', { class: 'a-alert-stub' }, [props.message, props.description])
  },
})

const ASpinStub = defineComponent({
  name: 'ASpinStub',
  props: {
    spinning: Boolean,
  },
  setup(props, { slots }) {
    return () =>
      h(
        'div',
        {
          class: 'a-spin-stub',
          'data-spinning': String(props.spinning),
        },
        slots.default?.(),
      )
  },
})

const ATagStub = defineComponent({
  name: 'ATagStub',
  setup(_, { slots }) {
    return () => h('span', { class: 'a-tag-stub' }, slots.default?.())
  },
})

const stubs = {
  'a-modal': AModalStub,
  'a-alert': AAlertStub,
  'a-spin': ASpinStub,
  'a-tag': ATagStub,
}

const sections = [
  {
    key: 'final-result',
    title: '最终客户点结果',
    description: '展示最终状态。',
    badge: '确定问题',
    rows: [{ key: 'status', label: '状态', value: '不合规' }],
  },
  {
    key: 'decision',
    title: '门控与判定',
    description: '展示受控判定。',
    rows: [],
  },
]

describe('BatchResultTraceModal', () => {
  it('关闭时不渲染诊断追踪内容', () => {
    const wrapper = mount(BatchResultTraceModal, {
      props: {
        open: false,
        loading: false,
        error: '',
        sections,
      },
      global: { stubs },
    })

    expect(wrapper.text()).toBe('')
  })

  it('应原样展示加载状态、错误和追踪分区', () => {
    const wrapper = mount(BatchResultTraceModal, {
      props: {
        open: true,
        loading: true,
        error: '诊断追踪获取失败',
        sections,
      },
      global: { stubs },
    })

    expect(wrapper.find('.a-modal-stub').attributes('data-title')).toBe('诊断追踪')
    expect(wrapper.find('.a-spin-stub').attributes('data-spinning')).toBe('true')
    expect(wrapper.text()).toContain('仅供管理员或实施人员排查使用')
    expect(wrapper.text()).toContain('诊断追踪获取失败')
    expect(wrapper.text()).toContain('最终客户点结果')
    expect(wrapper.text()).toContain('确定问题')
    expect(wrapper.text()).toContain('状态')
    expect(wrapper.text()).toContain('不合规')
    expect(wrapper.text()).toContain('当前结果未保存该层级的可展示诊断数据。')
  })

  it('取消弹窗时只向父组件发出关闭事件', async () => {
    const wrapper = mount(BatchResultTraceModal, {
      props: {
        open: true,
        loading: false,
        error: '',
        sections,
      },
      global: { stubs },
    })

    await wrapper.get('[data-testid="trace-close"]').trigger('click')

    expect(wrapper.emitted('close')).toHaveLength(1)
  })
})
