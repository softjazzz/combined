import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

import LLMParseResultView from '@/views/medical-records/LLMParseResultView.vue'

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  // 认证相关路由
  {
    path: '/auth',
    redirect: '/auth/login',
    children: [
      {
        path: 'login',
        alias: ['/login'],
        name: 'Login',
        component: () => import('@/views/auth/LoginView.vue'),
        meta: {
          requiresAuth: false,
          title: '登录'
        }
      },
      {
        path: 'register',
        name: 'Register',
        component: () => import('@/views/auth/RegisterView.vue'),
        meta: {
          requiresAuth: false,
          title: '注册'
        }
      },
      {
        path: 'forgot-password',
        name: 'ForgotPassword',
        component: () => import('@/views/auth/ForgotPasswordView.vue'),
        meta: {
          requiresAuth: false,
          title: '忘记密码'
        }
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/auth/ProfileView.vue'),
        meta: {
          requiresAuth: true,
          title: '个人资料'
        }
      }
    ]
  },
  {
    path: '/dashboard',
    component: () => import('@/components/layout/MainLayout.vue'),
    meta: {
      requiresAuth: true
    },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/DashboardView.vue'),
        meta: {
          title: '仪表板',
          icon: 'DashboardOutlined'
        }
      },
      // 病案质控相关路由
      {
        path: 'records/running',
        name: 'RunningRecords',
        component: () => import('@/views/dashboard/records/RunningRecordsView.vue'),
        meta: {
          title: '运行病历',
          icon: 'PlayCircleOutlined'
        }
      },
      {
        path: 'records/final',
        name: 'FinalRecords',
        component: () => import('@/views/dashboard/records/FinalRecordsView.vue'),
        meta: {
          title: '终末病历',
          icon: 'CheckCircleOutlined'
        }
      },
      {
        path: 'records/test',
        name: 'TestMedicalRecords',
        component: () => import('@/views/test-medical-records/TestMedicalRecordsView.vue'),
        meta: {
          title: '测试病历管理',
          icon: 'ProfileOutlined',
          permission: ['admin', 'qc_manager', 'developer']
        }
      },
      {
        path: 'records/:id',
        name: 'RecordDetail',
        component: () => import('@/views/records/RecordDetailView.vue'),
        meta: {
          title: '病案详情',
          hidden: true
        }
      },
      // 任务管理相关路由
      {
        path: 'tasks/my',
        name: 'MyTasks',
        component: () => import('@/views/dashboard/tasks/MyTasksView.vue'),
        meta: {
          title: '我的任务',
          icon: 'UserOutlined'
        }
      },
      {
        path: 'tasks/all',
        name: 'AllTasks',
        component: () => import('@/views/dashboard/tasks/AllTasksView.vue'),
        meta: {
          title: '全部任务',
          icon: 'TeamOutlined',
          permission: ['admin', 'qc_manager']
        }
      },


      // 质控规则管理路由（统一的标签页版本）
      {
        path: 'rules',
        name: 'Rules',
        component: () => import('@/views/rules/RulesView.vue'),
        meta: {
          title: '质控规则管理',
          icon: 'SettingOutlined',
          permission: ['admin']
        }
      },
      // 质控集成测试路由
      {
        path: 'qc-integration-test',
        name: 'QCIntegrationTest',
        component: () => import('@/views/test/QCIntegrationTest.vue'),
        meta: {
          title: '质控集成测试',
          icon: 'ExperimentOutlined',
          permission: ['admin', 'developer']
        }
      },
      // 语义质控规则管理路由（独立路由，保留作为备用）
      {
        path: 'semantic-rules',
        name: 'SemanticRules',
        component: () => import('@/views/rules/SemanticRulesView.vue'),
        meta: {
          title: '语义质控规则管理',
          icon: 'BranchesOutlined',
          permission: ['admin'],
          hidden: true // 隐藏在菜单中，因为现在集成到主规则管理页面
        }
      },
      // 质控点管理路由
      {
        path: 'quality-control',
        name: 'QualityControlPointManagement',
        component: () => import('@/views/dashboard/quality-control/QualityControlPointManagement.vue'),
        meta: {
          title: '非编码质控点管理',
          icon: 'ControlOutlined',
          permission: ['admin', 'qc_manager']
        }
      },
      {
        path: 'quality-control/create',
        name: 'QualityControlPointCreate',
        component: () => import('@/views/dashboard/quality-control/QualityControlPointCreate.vue'),
        meta: {
          title: '新建质控点',
          hidden: true,
          permission: ['admin', 'qc_manager']
        }
      },

      // 数据权限配置路由
      {
        path: 'permissions',
        name: 'Permissions',
        component: () => import('@/views/dashboard/permissions/PermissionsView.vue'),
        meta: {
          title: '数据权限配置',
          icon: 'SafetyCertificateOutlined',
          permission: ['admin']
        }
      },
      {
        path: 'llm-qc-demo',
        name: 'LLMQCDemo',
        component: () => import('@/views/demo/LLMQCDemo.vue'),
        meta: {
          title: 'LLM质控演示',
          icon: 'ExperimentOutlined',
          permission: ['admin']
        }
      },
      {
        path: 'llm-qc-demo-enhanced',
        name: 'LLMQCDemoEnhanced',
        component: () => import('@/views/demo/LLMQCDemoEnhanced.vue'),
        meta: {
          title: 'LLM质控演示增强版',
          icon: 'ExperimentOutlined',
          permission: ['admin'],
          description: '完整的LLM质控演示系统，包含规则应用、通知提醒和申诉功能'
        }
      },
      {
        path: 'test-demo',
        name: 'TestDemo',
        component: () => import('@/views/demo/TestDemo.vue'),
        meta: {
          title: '组件测试',
          icon: 'BugOutlined',
          permission: ['admin'],
          description: '测试演示组件功能'
        }
      },
      {
        path: 'test/llm-config',
        name: 'LLMConfigTest',
        component: () => import('@/views/test/LLMConfigTest.vue'),
        meta: {
          title: 'LLM配置测试',
          icon: 'SettingOutlined',
          hidden: true // 隐藏在菜单中，只能直接访问
        }
      },
      {
        path: 'test/simple-llm',
        name: 'SimpleLLMTest',
        component: () => import('@/views/test/SimpleLLMTest.vue'),
        meta: {
          title: '简化LLM测试',
          icon: 'ExperimentOutlined',
          hidden: true
        }
      },

      {
        path: 'llm-result',
        name: 'LLMParseResult',
        component: LLMParseResultView,
        meta: { title: 'LLM解析结果', icon: 'FileTextOutlined', hidden: true }
      },

      // 测试页面
      {
        path: 'test/modal',
        name: 'ModalTest',
        component: () => import('@/views/test/ModalTest.vue'),
        meta: { title: 'Modal测试', icon: 'ExperimentOutlined', hidden: true }
      },
      {
        path: 'test/batch-processor',
        name: 'BatchProcessorTest',
        component: () => import('@/views/test/BatchProcessorTest.vue'),
        meta: { title: '批量处理测试', icon: 'ExperimentOutlined', hidden: true }
      },
      {
        path: 'test/multi-file-upload',
        name: 'MultiFileUploadTest',
        component: () => import('@/views/test/MultiFileUploadTest.vue'),
        meta: { title: '多文件上传测试', icon: 'ExperimentOutlined', hidden: true }
      },
      {
        path: 'test/multi-document-merge',
        name: 'MultiDocumentMergeTest',
        component: () => import('@/views/test/MultiDocumentMergeTest.vue'),
        meta: { title: '多文档合并测试', icon: 'ExperimentOutlined', hidden: true }
      },
      {
        path: 'test/classification-version',
        name: 'ClassificationVersionTest',
        component: () => import('@/views/test/ClassificationVersionTest.vue'),
        meta: { title: '分类算法版本测试', icon: 'BranchesOutlined', hidden: true }
      },

      // 测试病历管理路由
      {
        path: 'medical-records',
        name: 'MedicalRecords',
        component: () => import('@/views/medical-records/MedicalRecordsView.vue'),
        meta: {
          title: '测试病历管理',
          icon: 'FileTextOutlined',
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'medical-records/create',
        name: 'CreateMedicalRecord',
        component: () => import('@/views/medical-records/CreateMedicalRecord.vue'),
        meta: {
          title: '新建病历',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'medical-records/:id',
        name: 'MedicalRecordDetail',
        component: () => import('@/views/medical-records/MedicalRecordDetail.vue'),
        meta: {
          title: '病历详情',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'medical-records/:id/legacy',
        name: 'MedicalRecordDetailLegacy',
        component: () => import('@/views/medical-records/MedicalRecordDetail.legacy.vue'),
        meta: {
          title: '病历详情（经典版）',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'test/three-column',
        name: 'TestThreeColumn',
        component: () => import('@/views/test/TestThreeColumn.vue'),
        meta: {
          title: '三栏布局测试',
          hidden: true,
          requiresAuth: false
        }
      },
      {
        path: 'test/basic',
        name: 'BasicTest',
        component: () => import('@/views/test/ApiTestView.vue'),
        meta: {
          title: '基础功能测试',
          hidden: true,
          requiresAuth: false
        }
      },
      {
        path: 'test/validation',
        name: 'ThreeColumnValidation',
        component: () => import('@/views/test/ThreeColumnValidation.vue'),
        meta: {
          title: '三栏布局验证',
          hidden: true,
          requiresAuth: false
        }
      },
      {
        path: 'medical-records/:id/simple',
        name: 'MedicalRecordDetailSimple',
        component: () => import('@/views/medical-records/MedicalRecordDetailSimple.vue'),
        meta: {
          title: '病历详情（简化版）',
          hidden: true,
          requiresAuth: false
        }
      },
      {
        path: 'medical-records/:id/qc-sichuan',
        name: 'MedicalRecordQCSichuan',
        component: () => import('@/views/qc/SichuanQCView.vue'),
        meta: {
          title: '四川省质控结果',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'medical-records/edit/:id',
        name: 'EditMedicalRecord',
        component: () => import('@/views/medical-records/EditMedicalRecord.vue'),
        meta: {
          title: '编辑病历',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'medical-records/smart-import',
        name: 'SmartImportMedicalRecord',
        // 暂时使用简化版本，避免语法错误
        component: () => import('@/views/medical-records/SmartImportSimple.vue'),
        meta: {
          title: '智能导入病历',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'medical-records/batch-import',
        name: 'BatchSmartImport',
        component: () => import('@/views/medical-records/BatchSmartImportView.vue'),
        meta: {
          title: '批量智能导入',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      // 简化版本作为备用
      {
        path: 'medical-records/smart-import-simple',
        name: 'SmartImportMedicalRecordSimple',
        component: () => import('@/views/medical-records/SmartImportSimple.vue'),
        meta: {
          title: '智能导入病历（简化版）',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      // 保留原版本作为备用（可选）
      {
        path: 'medical-records/smart-import-legacy',
        name: 'SmartImportMedicalRecordLegacy',
        component: () => import('@/views/medical-records/SmartImportMedicalRecord.vue'),
        meta: {
          title: '智能导入病历（经典版）',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'department-config',
        name: 'DepartmentConfig',
        component: () => import('@/views/DepartmentConfig.vue'),
        meta: {
          title: '专科化配置',
          icon: 'BranchesOutlined',
          permission: ['admin']
        }
      },
      {
        path: 'department-config-test',
        name: 'DepartmentConfigTest',
        component: () => import('@/views/DepartmentConfigTest.vue'),
        meta: {
          title: '专科化配置测试',
          icon: 'ExperimentOutlined',
          permission: ['admin']
        }
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('@/views/statistics/StatisticsView.vue'),
        meta: {
          title: '统计分析',
          icon: 'BarChartOutlined'
        }
      },
      {
        path: 'analytics',
        name: 'Analytics',
        component: () => import('@/views/analytics/AnalyticsView.vue'),
        meta: {
          title: '360度分析',
          icon: 'RadarChartOutlined',
          permission: ['admin', 'qc_manager']
        }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/SettingsView.vue'),
        meta: {
          title: '系统设置',
          icon: 'SettingOutlined',
          permission: ['admin']
        }
      },
      {
        path: 'debug/api-test',
        name: 'ApiTest',
        component: () => import('@/views/debug/ApiTestView.vue'),
        meta: {
          title: 'API测试',
          icon: 'ApiOutlined',
          hidden: true // 隐藏在菜单中，仅用于调试
        }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFoundView.vue'),
    meta: {
      title: '页面未找到'
    }
  }
]

// 创建路由实例
const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) {
      return savedPosition
    } else {
      return { top: 0 }
    }
  }
})

// 路由守卫
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // 检查是否需要认证
  if (to.meta.requiresAuth !== false) {
    // 检查用户是否已登录
    if (!authStore.isAuthenticated) {
      // 尝试从存储中恢复用户状态
      await authStore.initialize()

      if (!authStore.isAuthenticated) {
        next('/auth/login')
        return
      }
    }

    // 检查权限
    if (to.meta.permission) {
      const userRoles = authStore.userRoles
      const requiredPermissions = to.meta.permission as string[]

      const hasPermission = requiredPermissions.some(permission =>
        userRoles.includes(permission)
      )

      if (!hasPermission) {
        // 没有权限，重定向到仪表板
        next('/dashboard')
        return
      }
    }
  }

  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 大模型病案质控系统`
  }

  next()
})

export default router
