import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 图标由各组件按需 import，不再全量全局注册（原 793 个图标会导致请求风暴）

import App from './App.vue'
import router from './router'

import 'ant-design-vue/dist/reset.css'
// 导入样式 - 项目样式放在 Ant reset 之后，确保字体与主题 token 生效
import '@/styles/index.css'
import '@/styles/tokens-v2.css'

// 创建应用实例
const app = createApp(App)

// 配置Pinia状态管理
const pinia = createPinia()
app.use(pinia)

// 配置路由
app.use(router)

let errorHandlerLoader: Promise<typeof import('./utils/error-handler')> | null = null

function loadErrorHandler() {
  if (!errorHandlerLoader) {
    errorHandlerLoader = import('./utils/error-handler')
  }

  return errorHandlerLoader
}

// 全局错误处理
app.config.errorHandler = (err, vm: unknown, info: unknown) => {
  console.error('Global error:', err, vm, info)
  void loadErrorHandler().then(({ default: errorHandler }) => {
    errorHandler.handleError(err)
  })
}

// 全局属性
app.config.globalProperties.$SITE_NAME = '病案质控系统'

// 挂载应用
app.mount('#app')

// 开发环境下加载API测试工具（设置 VITE_LOAD_TEST_UTILS=true 启用）
if (import.meta.env.DEV && import.meta.env.VITE_LOAD_TEST_UTILS === 'true') {
  import('./utils/test-aliyun-api')
  import('./utils/test-qc-api')
}
