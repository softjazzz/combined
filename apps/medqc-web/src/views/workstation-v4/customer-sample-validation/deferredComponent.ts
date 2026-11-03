import { defineAsyncComponent, defineComponent, h, type AsyncComponentLoader, type Component } from 'vue'

function feedback(text: string, role: 'status' | 'alert') {
  return defineComponent({
    props: {
      open: { type: Boolean, default: undefined },
      visible: { type: Boolean, default: undefined },
    },
    setup(props) {
      return () => props.open === false || props.visible === false ? null : h('div', {
        role,
        style: { padding: '20px', color: '#64748b' },
      }, text)
    },
  })
}

const loadingComponent = feedback('正在加载页面内容…', 'status')
const errorComponent = feedback('页面内容加载失败，请刷新后重试。', 'alert')

export function deferredComponent<T extends Component>(loader: AsyncComponentLoader<T>, name?: string): T {
  const component = defineAsyncComponent({ loader, loadingComponent, errorComponent, delay: 0 })
  return name ? Object.assign(component, { name }) : component
}
