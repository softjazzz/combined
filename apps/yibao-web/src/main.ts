import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import Antd from 'ant-design-vue'
import 'ant-design-vue/dist/reset.css'
import './styles/tailwind.css'
import { createPinia } from 'pinia'
import { initAuthSync } from './utils/authSync'
import { useAuthStore } from './stores/auth'
import { authEventHandler } from './services/authEventHandler'
import { tokenDebugger } from './utils/tokenDebugger'

// 创建应用实例
const app = createApp(App)
const pinia = createPinia()

// 安装插件
app.use(pinia)
app.use(router)
app.use(Antd)

// 应用初始化函数
async function initializeApp() {
  try {
    console.log('🚀 开始初始化智慧医保质控系统...')

    // 初始化认证事件处理器
    authEventHandler.initialize()
    console.log('✅ 认证事件处理器已初始化')

    // 初始化认证状态同步
    initAuthSync()
    console.log('✅ 认证状态同步已初始化')

    // 预初始化认证状态（可选，提前准备）
    const authStore = useAuthStore()
    await authStore.initialize()
    console.log('✅ 认证状态预初始化完成')

    console.log('🎉 智慧医保质控系统启动完成')

    // 在开发环境下提供调试工具提示
    if (import.meta.env.DEV) {
      console.log('🔧 开发模式提示:')
      console.log('  - 使用 tokenDebugger.enable() 启用token调试')
      console.log('  - 使用 tokenDebugger.logTokenStatus() 查看token状态')
      console.log('  - 使用 authEventHandler.getStatus() 查看认证事件状态')
    }
  } catch (error) {
    console.error('❌ 应用初始化失败:', error)
    // 即使初始化失败，也要继续启动应用
  }
}

// 挂载应用
app.mount('#app')

// 异步初始化（不阻塞应用挂载）
initializeApp()


