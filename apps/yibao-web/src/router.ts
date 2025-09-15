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
import DataAnalytics from '@/views/analytics/DataAnalytics.vue'
import AdvancedAnalytics from '@/views/analytics/AdvancedAnalytics.vue'
import DepartmentDoctorReports from '@/views/analytics/DepartmentDoctorReports.vue'
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

    // 根路径重定向到仪表盘
    {
      path: '/',
      redirect: '/dashboard'
    },

    // 首页路由
    {
      path: '/home',
      name: 'home',
      component: Home,
      meta: {
        requiresAuth: true,
        title: '首页',
        icon: 'HomeOutlined'
      }
    },

    // 重定向路由
    { path: '/qc', redirect: '/dashboard' },

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

    // 数据分析
    {
      path: '/analytics',
      name: 'analytics',
      component: DataAnalytics,
      meta: {
        requiresAuth: true,
        title: '数据分析',
        icon: 'BarChartOutlined',
        description: '违规趋势分析和统计报告'
      }
    },

    // 高级数据分析
    {
      path: '/analytics/advanced',
      name: 'advanced-analytics',
      component: AdvancedAnalytics,
      meta: {
        requiresAuth: true,
        title: '高级分析',
        icon: 'FundOutlined',
        description: '深度数据洞察与预测分析',
        hideInMenu: true,
        breadcrumb: [
          { name: 'analytics', title: '数据分析' },
          { name: 'advanced-analytics', title: '高级分析' }
        ]
      }
    },

    // 科室医生报告
    {
      path: '/analytics/reports',
      name: 'department-doctor-reports',
      component: DepartmentDoctorReports,
      meta: {
        requiresAuth: true,
        title: '科室医生报告',
        icon: 'TeamOutlined',
        description: '科室绩效分析与医生质控档案',
        hideInMenu: true,
        breadcrumb: [
          { name: 'analytics', title: '数据分析' },
          { name: 'department-doctor-reports', title: '科室医生报告' }
        ]
      }
    },

    // 报表调度管理
    {
      path: '/analytics/scheduler',
      name: 'report-scheduler',
      component: () => import('@/views/analytics/ReportScheduler.vue'),
      meta: {
        requiresAuth: true,
        title: '报表调度',
        icon: 'ScheduleOutlined',
        description: '自动化报表生成与邮件推送',
        hideInMenu: true,
        breadcrumb: [
          { name: 'analytics', title: '数据分析' },
          { name: 'report-scheduler', title: '报表调度' }
        ]
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
    },

    // 测试病历管理路由
    {
      path: '/medical-records',
      name: 'medical-records',
      component: () => import('@/views/medical-records/MedicalRecordsView.vue'),
      meta: {
        requiresAuth: true,
        title: '测试病历管理',
        icon: 'FileTextOutlined',
        description: '管理医保质控测试病历'
      }
    },
    {
      path: '/medical-records/create',
      name: 'medical-record-create',
      component: () => import('@/views/medical-records/MedicalRecordForm.vue'),
      meta: {
        requiresAuth: true,
        title: '新建测试病历',
        hideInMenu: true,
        breadcrumb: [
          { name: 'medical-records', title: '测试病历管理' },
          { name: 'medical-record-create', title: '新建病历' }
        ]
      }
    },
    {
      path: '/medical-records/:id',
      name: 'medical-record-detail',
      component: () => import('@/views/medical-records/MedicalRecordDetail.vue'),
      meta: {
        requiresAuth: true,
        title: '病历详情',
        hideInMenu: true,
        breadcrumb: [
          { name: 'medical-records', title: '测试病历管理' },
          { name: 'medical-record-detail', title: '病历详情' }
        ]
      }
    },
    {
      path: '/medical-records/:id/edit',
      name: 'medical-record-edit',
      component: () => import('@/views/medical-records/MedicalRecordForm.vue'),
      meta: {
        requiresAuth: true,
        title: '编辑测试病历',
        hideInMenu: true,
        breadcrumb: [
          { name: 'medical-records', title: '测试病历管理' },
          { name: 'medical-record-edit', title: '编辑病历' }
        ]
      }
    }
  ]
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()

  try {
    console.log(`🛡️ 路由守卫: ${from.path || '/'} → ${to.path}`)

    // 确保认证状态已初始化
    if (!auth.initialized) {
      console.log('🔄 初始化认证状态...')
      await auth.initialize()
    }

    // 获取当前认证状态
    const isAuthenticated = auth.isAuthenticated
    const requiresAuth = to.meta?.requiresAuth

    console.log(`🔍 认证检查: 需要认证=${requiresAuth}, 已认证=${isAuthenticated}`)

    // 对于需要认证的路由，进行额外的token检查（但不强制刷新）
    if (requiresAuth && isAuthenticated) {
      try {
        // 只检查token是否有效，不强制刷新
        const token = auth.user?.id ? localStorage.getItem('yibao_access_token') : null
        if (!token) {
          console.log('❌ Token缺失，重定向到登录页')
          next({
            name: 'login',
            query: { redirect: to.fullPath }
          })
          return
        }
        console.log('✅ Token存在，允许访问')
      } catch (error) {
        console.warn('⚠️ Token检查异常:', error)
        // Token检查异常时，如果是页面刷新场景，给一次机会重新初始化
        if (!from.name) { // 页面刷新时from.name为undefined
          console.log('🔄 页面刷新场景，重新初始化认证状态')
          auth.initialized = false
          await auth.initialize()

          if (!auth.isAuthenticated) {
            console.log('❌ 重新初始化后仍未认证，重定向到登录页')
            next({
              name: 'login',
              query: { redirect: to.fullPath }
            })
            return
          }
        } else {
          // 非页面刷新场景的异常，直接重定向到登录页
          next({
            name: 'login',
            query: { redirect: to.fullPath }
          })
          return
        }
      }
    }

    // 检查认证要求
    if (requiresAuth && !isAuthenticated) {
      console.log('❌ 需要认证但未登录，重定向到登录页')
      next({
        name: 'login',
        query: { redirect: to.fullPath }
      })
      return
    }

    // 如果已登录用户访问登录页，重定向到仪表盘
    if (to.name === 'login' && isAuthenticated) {
      console.log('✅ 已登录用户访问登录页，重定向到仪表盘')
      const redirectPath = (to.query.redirect as string) || '/dashboard'
      next(redirectPath)
      return
    }

    // 设置页面标题
    if (to.meta?.title) {
      document.title = `${to.meta.title} - 智慧医保质控系统`
    } else {
      document.title = '智慧医保质控系统'
    }

    console.log('✅ 路由守卫检查通过')
    next()
  } catch (error) {
    console.error('❌ 路由守卫执行失败:', error)

    // 发生错误时的处理策略
    if (to.meta?.requiresAuth) {
      // 需要认证的路由发生错误，重定向到登录页
      console.log('❌ 认证路由异常，重定向到登录页')
      next({
        name: 'login',
        query: { redirect: to.fullPath }
      })
    } else {
      // 公开路由发生错误，允许继续访问
      console.log('⚠️ 公开路由异常，允许继续访问')
      next()
    }
  }
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


