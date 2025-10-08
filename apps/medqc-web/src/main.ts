import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import * as Icons from '@ant-design/icons-vue'

import App from './App.vue'
import router from './router'

// 导入样式 - 调整顺序以确保Tailwind样式优先级
import './styles/index.css'
import 'ant-design-vue/dist/reset.css'

// 创建应用实例
const app = createApp(App)

// 配置Pinia状态管理
const pinia = createPinia()
app.use(pinia)

// 配置路由
app.use(router)

// 配置Ant Design Vue
app.use(Antd)

// 注册Ant Design图标
Object.keys(Icons).forEach(key => {
  app.component(key, Icons[key as keyof typeof Icons])
})

// 导入错误处理
import errorHandler from './utils/error-handler'

// 全局错误处理
app.config.errorHandler = (err, vm: unknown,  info: unknown) => {
  console.error('Global error:', err, vm, info)
  errorHandler.handleError(err)
}

// 全局属性
app.config.globalProperties.$SITE_NAME = '病案质控系统'

// 挂载应用
app.mount('#app')

// 开发环境下加载API测试工具
if (process.env.NODE_ENV === 'development') {
  import('./utils/test-aliyun-api')
  import('./utils/test-qc-api')
} 