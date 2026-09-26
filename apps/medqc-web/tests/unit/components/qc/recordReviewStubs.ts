import { defineComponent, h } from 'vue'

/** 病历审核组件测试共用的 Ant Design Vue 轻量桩。 */
export const ButtonStub = defineComponent({
  name: 'AButton',
  inheritAttrs: false,
  props: { disabled: Boolean },
  emits: ['click'],
  setup(props, { attrs, emit, slots }) {
    return () => h('button', { ...attrs, disabled: props.disabled, onClick: () => emit('click') }, slots.default?.())
  },
})

export const ModalStub = defineComponent({
  name: 'AModal',
  props: { open: Boolean },
  emits: ['ok', 'cancel'],
  setup(props, { emit, slots }) {
    return () => props.open
      ? h('div', { 'data-testid': 'modal' }, [
          slots.default?.(),
          h('button', { 'data-testid': 'modal-ok', onClick: () => emit('ok') }, '提交'),
          h('button', { 'data-testid': 'modal-cancel', onClick: () => emit('cancel') }, '取消'),
        ])
      : null
  },
})

export const TextareaStub = defineComponent({
  name: 'ATextarea',
  inheritAttrs: false,
  props: { value: String },
  emits: ['update:value'],
  setup(props, { attrs, emit }) {
    return () => h('textarea', {
      ...attrs,
      value: props.value,
      onInput: (event: Event) => emit('update:value', (event.target as HTMLTextAreaElement).value),
    })
  },
})

export const recordReviewStubs = {
  'a-button': ButtonStub,
  'a-modal': ModalStub,
  'a-textarea': TextareaStub,
  'a-tag': { template: '<span><slot /></span>' },
  RotateCw: true,
}
