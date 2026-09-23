import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import RecordDetailView from '@/views/records/RecordDetailView.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'V1' } }),
  useRouter: () => ({ go: vi.fn() }),
}))

const emrViewerStub = defineComponent({
  name: 'EMRViewer',
  emits: ['loaded', 'defect-click'],
  setup: () => () => h('div'),
})

const tagStub = defineComponent({
  name: 'ATag',
  setup: (_, { slots }) => () => h('span', slots.default?.()),
})

function mountDetail() {
  return mount(RecordDetailView, {
    global: {
      stubs: {
        EMRViewer: emrViewerStub,
        AButton: true,
        ATag: tagStub,
      },
    },
  })
}

describe('RecordDetailView 缺陷标注可用性', () => {
  it('旧结果未绑定完整病历身份时不把空标注显示为无问题', async () => {
    const wrapper = mountDetail()
    expect(wrapper.text()).toContain('标注不可用')
    expect(wrapper.text()).not.toContain('暂无质控问题')

    wrapper.getComponent({ name: 'EMRViewer' }).vm.$emit('loaded', {
      annotations_status: 'unavailable_unscoped_source',
      defect_annotations: [],
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('当前无法核对缺陷标注')
    expect(wrapper.text()).not.toContain('0 个问题')
  })

})
