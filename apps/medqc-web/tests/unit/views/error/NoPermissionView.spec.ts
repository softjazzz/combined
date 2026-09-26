import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const { routerPush, signOut } = vi.hoisted(() => ({ routerPush: vi.fn(), signOut: vi.fn() }))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: routerPush }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ signOut }) }))

import NoPermissionView from '@/views/error/NoPermissionView.vue'

const ResultStub = defineComponent({
  props: { title: String, subTitle: String },
  setup(props, { slots }) {
    return () => h('div', [h('p', props.title), h('p', props.subTitle), slots.extra?.()])
  },
})
const ButtonStub = defineComponent({
  emits: ['click'],
  setup(_, { slots, emit }) {
    return () => h('button', { onClick: () => emit('click') }, slots.default?.())
  },
})

describe('NoPermissionView', () => {
  it('显示提示并可退出登录', async () => {
    const wrapper = mount(NoPermissionView, {
      global: { stubs: { 'a-result': ResultStub, 'a-button': ButtonStub } },
    })
    expect(wrapper.text()).toContain('当前账号无可访问页面，请联系管理员')
    await wrapper.find('button').trigger('click')
    await flushPromises()
    expect(signOut).toHaveBeenCalled()
    expect(routerPush).toHaveBeenCalledWith('/auth/login')
  })
})
