import { createRouter, createWebHistory } from 'vue-router'
import Home from '@/views/Home.vue'
import RulesList from '@/views/RulesList.vue'
import RulesEditor from '@/views/RulesEditor.vue'
import RuleImport from '@/views/RuleImport.vue'
import DoctorReminderDemo from '@/views/DoctorReminderDemo.vue'
import Audit from '@/views/Audit.vue'
import Dashboard from '@/views/Dashboard.vue'
import Login from '@/views/Login.vue'
import Sandbox from '@/views/Sandbox.vue'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // 认证相关路由
    {
      path: '/login',
      name: 'login',
      component: Login,
      meta: {
        title: '登录',
        hideInMenu: true
      }
    },

    // 首页路由
    {
      path: '/',
      name: 'home',
      component: Home,
      meta: {
        title: '首页',
        icon: 'HomeOutlined'
      }
    },

    // 重定向路由
    { path: '/qc', redirect: '/' },

    // 主要功能路由
    {
      path: '/dashboard',
      name: 'dashboard',
      component: Dashboard,
      meta: {
        requiresAuth: true,
        title: '仪表盘',
        icon: 'DashboardOutlined'
      }
    },

    // 规则管理路由
    {
      path: '/rules',
      name: 'rules',
      component: RulesList,
      meta: {
        requiresAuth: true,
        title: '规则管理',
        icon: 'SettingOutlined',
        description: '管理医保质控规则'
      }
    },
    {
      path: '/rules/create',
      name: 'rule-create',
      component: RulesEditor,
      meta: {
        requiresAuth: true,
        title: '新建规则',
        hideInMenu: true,
        breadcrumb: [
          { name: 'rules', title: '规则管理' },
          { name: 'rule-create', title: '新建规则' }
        ]
      }
    },
    {
      path: '/rules/edit',
      name: 'rule-edit',
      component: RulesEditor,
      meta: {
        requiresAuth: true,
        title: '编辑规则',
        hideInMenu: true,
        breadcrumb: [
          { name: 'rules', title: '规则管理' },
          { name: 'rule-edit', title: '编辑规则' }
        ]
      }
    },
    {
      path: '/rules/import',
      name: 'rule-import',
      component: RuleImport,
      meta: {
        requiresAuth: true,
        title: '规则导入',
        hideInMenu: true,
        breadcrumb: [
          { name: 'rules', title: '规则管理' },
          { name: 'rule-import', title: '规则导入' }
        ]
      }
    },

    // 质控审计路由
    {
      path: '/audit',
      name: 'audit',
      component: Audit,
      meta: {
        requiresAuth: true,
        title: '质控审计',
        icon: 'AuditOutlined',
        description: '查看质控审计结果'
      }
    },

    // 医生提醒演示
    {
      path: '/reminder-demo',
      name: 'reminder-demo',
      component: DoctorReminderDemo,
      meta: {
        requiresAuth: true,
        title: '医生提醒演示',
        icon: 'NotificationOutlined',
        description: '演示医生工作站提醒功能'
      }
    },

    // 沙箱测试
    {
      path: '/sandbox',
      name: 'sandbox',
      component: Sandbox,
      meta: {
        requiresAuth: true,
        title: '规则测试沙箱',
        icon: 'ExperimentOutlined',
        description: '测试规则配置'
      }
    }
  ]
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  // 获取用户信息
  if (!auth.user) {
    await auth.fetchUser()
  }

  // 检查认证要求
  if (to.meta?.requiresAuth && !auth.user) {
    next({
      name: 'login',
      query: { redirect: to.fullPath }
    })
    return
  }

  // 如果已登录用户访问登录页，重定向到仪表盘
  if (to.name === 'login' && auth.user) {
    next({ name: 'dashboard' })
    return
  }

  // 设置页面标题
  if (to.meta?.title) {
    document.title = `${to.meta.title} - 智慧医保质控系统`
  } else {
    document.title = '智慧医保质控系统'
  }

  next()
})

// 路由后置守卫
router.afterEach((to, from) => {
  // 可以在这里添加页面访问统计等逻辑
  console.log(`导航到: ${to.path}`)
})

// 导出路由实例
export default router

// 导出路由配置用于菜单生成
export const getMenuRoutes = () => {
  return router.getRoutes()
    .filter(route => route.meta?.requiresAuth && !route.meta?.hideInMenu)
    .map(route => ({
      key: route.name as string,
      path: route.path,
      title: route.meta?.title || route.name,
      icon: route.meta?.icon,
      description: route.meta?.description
    }))
}


