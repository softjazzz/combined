import { createRouter, createWebHistory } from 'vue-router'
import { canUseMessageCenter, MESSAGE_CENTER_PATH, MESSAGE_CENTER_ROLES } from '@/views/workstation/notificationNavigation'
import type { RouteRecordRaw } from 'vue-router'

const WORKSTATION_BASE_PATH = '/workstation-v5'
const LEGACY_WORKSTATION_BASE_PATH = '/workstation-v4'

function isTruthyFlag(value: unknown): boolean {
  return String(value ?? '').trim().toLowerCase() === 'true'
}

/**
 * 生产构建下默认关闭匿名 ?demo=true 认证旁路及匿名 /dashboard/test/* 测试路由，
 * 仅当非生产环境或显式开启 VITE_ALLOW_DEMO_MODE=true / VITE_ENABLE_DEMO_MODE=true 时允许。
 */
export function isDemoRouteBypassEnabled(
  env: Record<string, unknown> = import.meta.env as Record<string, unknown>,
): boolean {
  const explicitDemo =
    isTruthyFlag(env.VITE_ALLOW_DEMO_MODE) || isTruthyFlag(env.VITE_ENABLE_DEMO_MODE)
  if (Boolean(env.PROD)) {
    return explicitDemo
  }
  return true
}

function isDashboardTestPath(path: string): boolean {
  return path === '/dashboard/test' || path.startsWith('/dashboard/test/')
}

// 历史页面统一经 V4 兼容入口，沿用工作台的 URL 规范化和鉴权。
const retiredPageRedirect = { path: LEGACY_WORKSTATION_BASE_PATH }

function normalizeWorkstationPath(path: string) {
  if (
    path === LEGACY_WORKSTATION_BASE_PATH ||
    path.startsWith(`${LEGACY_WORKSTATION_BASE_PATH}/`)
  ) {
    return `${WORKSTATION_BASE_PATH}${path.slice(LEGACY_WORKSTATION_BASE_PATH.length)}`
  }
  return path.startsWith(WORKSTATION_BASE_PATH) ? path : WORKSTATION_BASE_PATH
}

// 路由配置
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workstation-v5',
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
          title: '登录',
        },
      },
      {
        path: 'register',
        name: 'Register',
        component: () => import('@/views/auth/RegisterView.vue'),
        meta: {
          requiresAuth: false,
          title: '注册',
        },
      },
      {
        path: 'forgot-password',
        name: 'ForgotPassword',
        component: () => import('@/views/auth/ForgotPasswordView.vue'),
        meta: {
          requiresAuth: false,
          title: '忘记密码',
        },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/auth/ProfileView.vue'),
        meta: {
          requiresAuth: true,
          title: '个人资料',
        },
      },
    ],
  },
  {
    path: '/dashboard',
    component: () => import('@/components/layout/MainLayout.vue'),
    meta: {
      requiresAuth: true,
    },
    children: [
      {
        path: '',
        name: 'Dashboard',
        redirect: (to) => ({
          path: '/workstation-v5',
          // 旧首页没有业务参数合同；保留原样 query/hash，避免丢失外部入口上下文。
          query: to.query,
          hash: to.hash,
        }),
        meta: {
          title: '仪表板',
          icon: 'DashboardOutlined',
        },
      },
      // 病案质控相关路由
      {
        path: 'records/outpatient-emergency',
        name: 'OutpatientEmergencyRecords',
        redirect: retiredPageRedirect,
      },
      {
        path: 'records/running',
        name: 'RunningRecords',
        redirect: retiredPageRedirect,
      },
      {
        path: 'records/final',
        name: 'FinalRecords',
        redirect: retiredPageRedirect,
      },
      // 智能质控工作站 V4（主质控工作台）
      {
        path: 'workstation',
        name: 'Workstation',
        component: () => import('@/views/workstation-v4/WorkstationV4View.vue'),
        meta: {
          title: '智能质控工作站',
          icon: 'DesktopOutlined',
          permission: ['admin', 'qc_manager', 'coder', 'doctor'],
        },
      },
      {
        path: 'workstation/import',
        name: 'DataImport',
        component: () => import('@/views/workstation/DataImportView.vue'),
        meta: {
          title: '病历数据导入',
          hidden: true,
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'workstation/qc-overview',
        redirect: '/workstation-v5/qc-overview',
        meta: {
          title: '质控首页概览',
          permission: ['admin', 'qc_manager', 'doctor', 'sync_admin', 'super_admin'],
        },
      },
      {
        path: 'workstation/qc-stats',
        name: 'QCStats',
        component: () => import('@/views/workstation/QCStatsView.vue'),
        meta: {
          title: '质控统计分析',
          hidden: true,
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'frontpage-demo',
        name: 'FrontPageAutoDemo',
        redirect: retiredPageRedirect,
      },
      {
        path: 'records/test',
        name: 'TestMedicalRecords',
        component: () => import('@/views/test-medical-records/TestMedicalRecordsView.vue'),
        meta: {
          title: '病历管理',
          icon: 'ProfileOutlined',
          hidden: true,
          permission: ['admin', 'qc_manager', 'developer'],
        },
      },
      {
        path: 'records/:id',
        name: 'RecordDetail',
        component: () => import('@/views/records/RecordDetailView.vue'),
        meta: {
          title: '病案详情',
          hidden: true,
        },
      },
      // 任务管理相关路由
      {
        path: 'tasks/my',
        name: 'MyTasks',
        redirect: retiredPageRedirect,
      },
      {
        path: 'tasks/all',
        name: 'AllTasks',
        redirect: retiredPageRedirect,
      },
      // 质控流程相关路由
      {
        path: 'qc/appeals',
        name: 'AppealList',
        component: () => import('@/views/qc/AppealList.vue'),
        meta: {
          title: '质控申诉',
          icon: 'MessageOutlined',
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'qc/scoring-config',
        name: 'ScoringConfig',
        component: () => import('@/views/qc/ScoringConfigView.vue'),
        meta: {
          title: '评分阈值配置',
          icon: 'SettingOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'qc/rectifications',
        name: 'RectificationList',
        component: () => import('@/views/workstation/HomeRectificationTodos.vue'),
        meta: {
          title: '整改任务',
          icon: 'ToolOutlined',
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },

      // 质控规则管理路由（统一的标签页版本，包含传统规则、语义规则和科室规则）
      {
        path: 'rules',
        name: 'Rules',
        component: () => import('@/views/rules/RulesView.vue'),
        meta: {
          title: '质控规则管理',
          icon: 'SettingOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'rules/custom-workspace',
        name: 'CustomRuleWorkspace',
        component: () => import('@/views/rules/CustomRuleWorkspaceView.vue'),
        meta: {
          title: '自定义质控点',
          icon: 'AppstoreOutlined',
          permission: ['admin', 'qc_manager'],
          hidden: true,
        },
      },
      {
        path: 'rules/docs',
        name: 'RuleDocs',
        component: () => import('@/views/rules/RuleDocView.vue'),
        meta: {
          title: '质控规则说明',
          icon: 'FileTextOutlined',
          permission: ['admin', 'qc_manager'],
          hidden: true,
        },
      },
      // 科室级质控规则管理路由（重定向到统一的规则管理页面）
      {
        path: 'department-rules',
        redirect: '/dashboard/rules?tab=department',
        meta: {
          hidden: true, // 隐藏在菜单中，已整合到主规则管理页面
        },
      },
      // 质控集成测试路由
      {
        path: 'qc-integration-test',
        name: 'QCIntegrationTest',
        component: () => import('@/views/test/' + 'QCIntegrationTest.vue'),
        meta: {
          title: '质控集成测试',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin', 'developer'],
        },
      },
      // 语义质控规则管理路由（独立路由，保留作为备用）
      {
        path: 'semantic-rules',
        name: 'SemanticRules',
        component: () => import('@/views/rules/' + 'SemanticRulesView.vue'),
        meta: {
          title: '语义质控规则管理',
          icon: 'BranchesOutlined',
          permission: ['admin'],
          hidden: true, // 隐藏在菜单中，因为现在集成到主规则管理页面
        },
      },
      // 自定义质控规则管理路由（泸县33条规则）
      {
        path: 'custom-rules',
        name: 'CustomRules',
        component: () => import('@/components/CustomRulesManager.vue'),
        meta: {
          title: '自定义质控规则',
          icon: 'AppstoreOutlined',
          hidden: true,
          permission: ['admin', 'qc_manager'],
        },
      },
      // 批量质控评估路由
      {
        path: 'custom-rules/batch-test',
        name: 'BatchRuleTest',
        component: () => import('@/components/BatchRuleTest.vue'),
        meta: {
          title: '批量质控评估',
          icon: 'CheckSquareOutlined',
          hidden: true,
          permission: ['admin', 'qc_manager'],
          allowDemo: true, // 允许演示模式访问（通过?demo=true参数）
        },
      },
      // 质控点管理路由
      {
        path: 'quality-control',
        name: 'QualityControlPointManagement',
        redirect: retiredPageRedirect,
      },
      {
        path: 'quality-control/create',
        name: 'QualityControlPointCreate',
        redirect: retiredPageRedirect,
      },

      // 评分标准配置路由
      {
        path: 'scoring-rules',
        name: 'ScoringRules',
        redirect: retiredPageRedirect,
      },
      {
        path: 'staff-ranking',
        name: 'StaffRanking',
        redirect: retiredPageRedirect,
      },
      {
        path: 'notifications',
        name: 'Notifications',
        redirect: retiredPageRedirect,
      },

      // 数据权限配置路由
      {
        path: 'permissions',
        name: 'Permissions',
        redirect: retiredPageRedirect,
      },
      {
        path: 'llm-qc-demo',
        name: 'LLMQCDemo',
        redirect: retiredPageRedirect,
      },
      {
        path: 'llm-qc-demo-enhanced',
        name: 'LLMQCDemoEnhanced',
        redirect: retiredPageRedirect,
      },
      {
        path: 'llm-qc-demo-new',
        name: 'LLMQCDemoEnhancedNew',
        redirect: retiredPageRedirect,
      },
      {
        path: 'sichuan-qc-demo',
        name: 'SichuanQCDemo',
        redirect: retiredPageRedirect,
      },
      {
        path: 'test-demo',
        name: 'TestDemo',
        redirect: retiredPageRedirect,
      },
      {
        path: 'test/llm-config',
        name: 'LLMConfigTest',
        component: () => import('@/views/test/LLMConfigTest.vue'),
        meta: {
          title: 'LLM配置测试',
          icon: 'SettingOutlined',
          hidden: true, // 隐藏在菜单中，只能直接访问
          permission: ['admin', 'developer'],
        },
      },
      {
        path: 'test/simple-llm',
        name: 'SimpleLLMTest',
        component: () => import('@/views/test/SimpleLLMTest.vue'),
        meta: {
          title: '简化LLM测试',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin', 'developer'],
        },
      },

      {
        path: 'llm-result',
        name: 'LLMParseResult',
        component: () => import('@/views/medical-records/LLMParseResultView.vue'),
        meta: { title: 'LLM解析结果', icon: 'FileTextOutlined', hidden: true },
      },

      // 测试页面
      {
        path: 'test/modal',
        name: 'ModalTest',
        component: () => import('@/views/test/ModalTest.vue'),
        meta: {
          title: 'Modal测试',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin', 'developer'],
        },
      },
      {
        path: 'test/batch-processor',
        name: 'BatchProcessorTest',
        component: () => import('@/views/test/BatchProcessorTest.vue'),
        meta: {
          title: '批量处理测试',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin', 'developer'],
        },
      },
      {
        path: 'test/multi-file-upload',
        name: 'MultiFileUploadTest',
        component: () => import('@/views/test/MultiFileUploadTest.vue'),
        meta: {
          title: '多文件上传测试',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin', 'developer'],
        },
      },
      {
        path: 'test/multi-document-merge',
        name: 'MultiDocumentMergeTest',
        component: () => import('@/views/test/MultiDocumentMergeTest.vue'),
        meta: {
          title: '多文档合并测试',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin', 'developer'],
        },
      },
      {
        path: 'test/classification-version',
        name: 'ClassificationVersionTest',
        component: () => import('@/views/test/ClassificationVersionTest.vue'),
        meta: {
          title: '分类算法版本测试',
          icon: 'BranchesOutlined',
          hidden: true,
          permission: ['admin', 'developer'],
        },
      },

      // 病历管理路由（隐藏入口，保留兼容访问）
      {
        path: 'medical-records',
        name: 'MedicalRecords',
        component: () => import('@/views/medical-records/MedicalRecordsView.vue'),
        meta: {
          title: '病历管理',
          icon: 'FileTextOutlined',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'medical-records/create',
        name: 'CreateMedicalRecord',
        component: () => import('@/views/medical-records/CreateMedicalRecord.vue'),
        meta: {
          title: '新建病历',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'medical-records/:id',
        name: 'MedicalRecordDetail',
        component: () => import('@/views/medical-records/MedicalRecordDetail.vue'),
        meta: {
          title: '病历详情',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'medical-records/:id/legacy',
        name: 'MedicalRecordDetailLegacy',
        redirect: retiredPageRedirect,
      },
      {
        path: 'test/three-column',
        name: 'TestThreeColumn',
        component: () => import('@/views/test/TestThreeColumn.vue'),
        meta: {
          title: '三栏布局测试',
          hidden: true,
          requiresAuth: false,
        },
      },
      {
        path: 'test/basic',
        name: 'BasicTest',
        component: () => import('@/views/test/ApiTestView.vue'),
        meta: {
          title: '基础功能测试',
          hidden: true,
          requiresAuth: false,
        },
      },
      {
        path: 'test/validation',
        name: 'ThreeColumnValidation',
        component: () => import('@/views/test/ThreeColumnValidation.vue'),
        meta: {
          title: '三栏布局验证',
          hidden: true,
          requiresAuth: false,
        },
      },
      {
        path: 'medical-records/:id/simple',
        name: 'MedicalRecordDetailSimple',
        redirect: retiredPageRedirect,
      },
      {
        path: 'medical-records/:id/qc-sichuan',
        name: 'MedicalRecordQCSichuan',
        component: () => import('@/views/qc/SichuanQCView.vue'),
        meta: {
          title: '四川省质控结果',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'medical-records/edit/:id',
        name: 'EditMedicalRecord',
        component: () => import('@/views/medical-records/EditMedicalRecord.vue'),
        meta: {
          title: '编辑病历',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'medical-records/smart-import',
        name: 'SmartImportMedicalRecord',
        // 暂时使用简化版本，避免语法错误
        component: () => import('@/views/medical-records/SmartImportSimple.vue'),
        meta: {
          title: '智能导入病历',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'medical-records/batch-import',
        name: 'BatchSmartImport',
        component: () => import('@/views/medical-records/BatchSmartImportView.vue'),
        meta: {
          title: '批量智能导入',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      // 简化版本作为备用
      {
        path: 'medical-records/smart-import-simple',
        name: 'SmartImportMedicalRecordSimple',
        component: () => import('@/views/medical-records/SmartImportSimple.vue'),
        meta: {
          title: '智能导入病历（简化版）',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      // 保留原版本作为备用（可选）
      {
        path: 'medical-records/smart-import-legacy',
        name: 'SmartImportMedicalRecordLegacy',
        component: () => import('@/views/medical-records/SmartImportMedicalRecord.vue'),
        meta: {
          title: '智能导入病历（经典版）',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
      },
      {
        path: 'department-config',
        name: 'DepartmentConfig',
        component: () => import('@/views/DepartmentConfig.vue'),
        meta: {
          title: '专科化配置',
          icon: 'BranchesOutlined',
          permission: ['admin'],
        },
      },
      {
        path: 'department-config-test',
        name: 'DepartmentConfigTest',
        component: () => import('@/views/DepartmentConfigTest.vue'),
        meta: {
          title: '专科化配置测试',
          icon: 'ExperimentOutlined',
          permission: ['admin'],
        },
      },
      {
        path: 'statistics',
        name: 'Statistics',
        component: () => import('@/views/statistics/StatisticsView.vue'),
        meta: {
          title: '统计分析',
          icon: 'BarChartOutlined',
        },
      },
      {
        path: 'analytics',
        name: 'Analytics',
        component: () => import('@/views/analytics/AnalyticsView.vue'),
        meta: {
          title: '360度分析',
          icon: 'RadarChartOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      // DRG/DIP 模块路由
      {
        path: 'drg',
        name: 'DRG',
        redirect: '/dashboard/drg/index',
        meta: {
          title: 'DRG/DIP',
          icon: 'MedicineBoxOutlined',
          allowDemo: true,
          permission: ['admin', 'qc_manager', 'coder', 'reviewer'],
        },
        children: [
          {
            path: 'index',
            name: 'DRGIndex',
            component: () => import('@/views/drg/Index.vue'),
            meta: {
              title: 'DRG 首页',
              icon: 'HomeOutlined',
            },
          },
          {
            path: 'coding',
            name: 'CodingAssistant',
            component: () => import('@/views/drg/CodingAssistant.vue'),
            meta: {
              title: '编码辅助',
              icon: 'EditOutlined',
              description: 'ICD 编码推荐和校验',
            },
          },
          {
            path: 'coding/:admissionId',
            name: 'CodingDetail',
            component: () => import('@/views/drg/CodingDetail.vue'),
            meta: {
              title: '编码详情',
              hidden: true,
            },
          },
          {
            path: 'grouping',
            name: 'GroupingPredict',
            component: () => import('@/views/drg/GroupingPredict.vue'),
            meta: {
              title: 'DRG 分组',
              icon: 'ClusterOutlined',
              description: 'DRG 入组预测和费用分析',
            },
          },
          {
            path: 'config',
            name: 'GrouperConfig',
            component: () => import('@/views/drg/GrouperConfig.vue'),
            meta: {
              title: '分组器配置',
              icon: 'SettingOutlined',
              description: '分组规则与参数配置',
            },
          },
          {
            path: 'settlement',
            name: 'SettlementForm',
            component: () => import('@/views/drg/SettlementForm.vue'),
            meta: {
              title: '医保结算清单',
              icon: 'FileProtectOutlined',
              description: '医保结算清单填报与质控',
            },
          },
          {
            path: 'monitor',
            name: 'MonitorDashboard',
            component: () => import('@/views/drg/MonitorDashboard.vue'),
            meta: {
              title: '事中监控',
              icon: 'DashboardOutlined',
              description: '实时预警和编码建议',
            },
          },
          {
            path: 'fee-monitoring',
            name: 'FeeMonitoring',
            component: () => import('@/views/drg/FeeMonitoring.vue'),
            meta: {
              title: '付费监测',
              icon: 'DollarOutlined',
              description: '费用监测与未入组修正建议',
            },
          },
          {
            path: 'analysis',
            name: 'DRGAnalysis',
            component: () => import('@/views/drg/Analysis.vue'),
            meta: {
              title: '事后分析',
              icon: 'BarChartOutlined',
              description: 'DRG 绩效统计和盈亏分析',
              permission: ['admin', 'qc_manager'],
            },
          },
        ],
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/settings/SettingsView.vue'),
        meta: {
          title: '系统设置',
          icon: 'SettingOutlined',
          permission: ['admin'],
        },
      },
      {
        path: 'debug/api-test',
        name: 'ApiTest',
        component: () => import('@/views/debug/ApiTestView.vue'),
        meta: {
          title: 'API测试',
          icon: 'ApiOutlined',
          hidden: true, // 隐藏在菜单中，仅用于调试
        },
      },
    ],
  },
  {
    path: '/demo/:legacyPath(.*)*',
    alias: ['/workstation-v2/:legacyPath(.*)*', '/workstation-v3/:legacyPath(.*)*'],
    redirect: retiredPageRedirect,
  },
  {
    path: '/workstation-v5/login',
    alias: ['/workstation-v4/login'],
    name: 'WorkstationV4Login',
    component: () => import('@/views/workstation-v4/WorkstationLoginView.vue'),
    meta: {
      requiresAuth: false,
      title: '工作台登录',
    },
  },
  // 现行 V5 使用 workstation-v4 源码目录；V4 URL 保留为兼容别名。
  {
    path: '/workstation-v5',
    alias: ['/workstation-v4'],
    component: () => import('@/components/layout/WorkstationLayout.vue'),
    meta: {
      requiresAuth: true,
      title: '病案工作台 V5',
    },
    children: [
      {
        path: '',
        name: 'WorkstationV4Index',
        component: () => import('@/views/workstation-v4/WorkstationV4HomeEntry.vue'),
        meta: {
          title: '工作台',
          permission: ['admin', 'qc_manager', 'doctor', 'sync_admin', 'super_admin'],
        },
      },
      {
        path: 'worklist',
        name: 'WorkstationV4Worklist',
        component: () => import('@/views/workstation-v4/WorkstationV4View.vue'),
        meta: {
          title: '病历池',
          permission: ['admin', 'qc_manager', 'doctor', 'sync_admin', 'super_admin'],
        },
      },
      {
        path: 'records/outpatient-emergency',
        name: 'WorkstationV4OutpatientEmergencyRecords',
        component: () => import('@/views/workstation/OutpatientEmergencyRecordsView.vue'),
        meta: { title: '门急诊病历', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'records/running',
        name: 'WorkstationV4RunningRecords',
        component: () => import('@/views/workstation-v4/QcRecordResultListView.vue'),
        props: { carePhase: 'inpatient' },
        meta: { title: '运行病历', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'records/final',
        name: 'WorkstationV4FinalRecords',
        component: () => import('@/views/workstation-v4/QcRecordResultListView.vue'),
        props: { carePhase: 'discharged' },
        meta: { title: '终末病历质控', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'frontpage-qc',
        name: 'WorkstationV5FrontpageQc',
        component: () => import('@/views/workstation-v4/frontpage-qc/FrontpageQcView.vue'),
        meta: { title: '首页质控（新）', permission: ['admin', 'super_admin', 'qc_manager', 'coder'] },
      },
      {
        path: 'qc-feedback-demo',
        name: 'WorkstationV4QcFeedbackDemo',
        component: () => import('@/views/workstation-v4/QcResultFeedbackDemoListView.vue'),
        meta: { title: '质控反馈记录', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'case-communications',
        name: 'WorkstationV5CaseCommunications',
        component: () => import('@/views/workstation/HomeCaseCommunications.vue'),
        meta: { title: '病历沟通', permission: ['doctor'] },
      },
      {
        path: 'feedback',
        name: 'WorkstationV5Feedback',
        component: () => import('@/views/workstation/HomeRectificationTodos.vue'),
        meta: { title: '整改待办', permission: ['admin', 'qc_manager', 'qc_staff', 'doctor'] },
      },
      {
        path: 'qc-task',
        name: 'WorkstationV5QcTaskDetail',
        component: () => import('@/views/workstation/NotificationQcResult.vue'),
        props: { entryMode: 'task' },
        meta: {
          title: '质控任务详情',
          permission: ['admin', 'qc_manager', 'qc_staff', 'sync_admin', 'super_admin'],
        },
      },
      {
        path: 'qc-result',
        name: 'WorkstationV5NotificationQcResult',
        component: () => import('@/views/workstation/NotificationQcResult.vue'),
        meta: { title: '质控任务结果', permission: ['admin', 'qc_manager', 'qc_staff', 'sync_admin', 'super_admin'] },
      },
      {
        path: 'messages',
        name: 'WorkstationV5MessageCenter',
        component: () => import('@/views/workstation/MessageCenter.vue'),
        meta: { title: '消息中心', permission: MESSAGE_CENTER_ROLES },
      },
      {
        path: 'customer-sample-validation',
        name: 'WorkstationV4CustomerSampleValidation',
        component: () => import('@/views/workstation-v4/CustomerSampleValidationView.vue'),
        meta: { title: '客户样本验证', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'customer-sample-validation/synthetic-case/new',
        name: 'WorkstationV4SyntheticCaseNew',
        component: () =>
          import('@/views/workstation-v4/customer-sample-validation/SyntheticCaseBuilderView.vue'),
        meta: { title: '创建测试病历', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'customer-sample-validation/tasks',
        name: 'WorkstationV4CustomerSampleValidationTasks',
        component: () =>
          import(
            '@/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue'
          ),
        meta: { title: '质控记录', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'customer-sample-validation/surgery-catalog',
        name: 'WorkstationV4SurgeryProcedureCatalog',
        component: () =>
          import('@/views/workstation-v4/components/SurgeryProcedureCatalogView.vue'),
        meta: { title: '手术分级目录', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'custom-qc-experience',
        name: 'WorkstationV4CustomQCExperience',
        component: () => import('@/views/workstation-v4/CustomQCExperienceView.vue'),
        meta: { title: '自定义质控点体验', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'icd',
        name: 'WorkstationV4ICD',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'icd-search' },
        meta: { title: 'ICD 编码查询' },
      },
      {
        path: 'upload',
        name: 'WorkstationV4Upload',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'upload' },
        meta: { title: '数据上传', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'stats',
        name: 'WorkstationV4Stats',
        component: () => import('@/views/workstation-v4/LuxianQcAnalyticsView.vue'),
        meta: { title: '统计分析', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'reports/record-quality',
        name: 'WorkstationV5RecordQualityReport',
        component: () => import('@/views/qc/reports/RecordQualityReportView.vue'),
        meta: { title: '病历质量分析', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'reports/special-records',
        name: 'WorkstationV5SpecialRecordReport',
        component: () => import('@/views/qc/reports/SpecialRecordReportView.vue'),
        meta: { title: '特殊病历报表', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'reports/frontpage-quality',
        name: 'WorkstationV5FrontpageQualityReport',
        component: () => import('@/views/qc/reports/FrontpageQualityReportView.vue'),
        meta: { title: '病案首页统计', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'reports/staff-analysis',
        name: 'WorkstationV5StaffAnalysisReport',
        component: () => import('@/views/qc/reports/StaffAnalysisView.vue'),
        meta: { title: '质控员工作分析', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'drg/pre',
        name: 'WorkstationV4DRGPre',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'pre-analysis' },
        meta: { title: '事前分析', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'drg/mid',
        name: 'WorkstationV4DRGMid',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'mid-analysis' },
        meta: { title: '事中监控', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'drg/payment',
        name: 'WorkstationV4DRGPayment',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'payment' },
        meta: { title: '付费监测', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'drg/post',
        name: 'WorkstationV4DRGPost',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'post-analysis' },
        meta: { title: '事后分析', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'grouper',
        name: 'WorkstationV4Grouper',
        component: () => import('@/views/drg-grouper/GrouperTabsView.vue'),
        meta: { title: '医保分组器', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'data',
        name: 'WorkstationV4Data',
        component: () => import('@/views/workstation-v4/CDMDataView.vue'),
        meta: { title: '数据管理', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'rules',
        name: 'WorkstationV4Rules',
        component: () => import('@/views/workstation-v4/WorkstationRulesView.vue'),
        meta: { title: '质控规则管理', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'rules/custom-workspace',
        name: 'WorkstationV4CustomRuleWorkspace',
        component: () => import('@/views/rules/CustomRuleWorkspaceView.vue'),
        meta: { title: '自定义质控点', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'rules/validation',
        name: 'WorkstationV4RuleValidation',
        component: () => import('@/views/workstation-v4/rule-validation/RuleValidationListView.vue'),
        meta: { title: '规则验收', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'rules/validation/:ruleId',
        name: 'WorkstationV4RuleValidationDetail',
        component: () => import('@/views/workstation-v4/rule-validation/RuleValidationDetailView.vue'),
        meta: { title: '规则验收详情', permission: ['admin', 'qc_manager', 'sync_admin'] },
      },
      {
        path: 'rules/validation/:ruleId/cases/new',
        name: 'WorkstationV4RuleValidationNewCase',
        component: () =>
          import('@/views/workstation-v4/rule-validation/RuleValidationNewCaseView.vue'),
        meta: { title: '新建测试病例', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'qc-overview',
        name: 'WorkstationV4QCOverview',
        component: () => import('@/views/workstation/QCOverviewView.vue'),
        meta: {
          title: '质控首页概览',
          permission: ['admin', 'qc_manager', 'doctor', 'sync_admin', 'super_admin'],
        },
      },
      {
        path: 'system-config',
        name: 'WorkstationV4SystemConfig',
        component: () => import('@/views/workstation-v4/DataSyncConfigPage.vue'),
        meta: {
          title: '系统配置',
          permission: ['admin', 'qc_manager', 'sync_admin', 'super_admin'],
        },
      },
      {
        path: 'users',
        name: 'WorkstationUserManagement',
        component: () => import('@/views/workstation/UserManagementView.vue'),
        meta: { title: '用户管理', permission: ['admin', 'sync_admin'] },
      },
      {
        path: 'tender-acceptance',
        name: 'WorkstationV4TenderAcceptance',
        component: () => import('@/views/workstation-v4/components/TenderAcceptanceDashboard.vue'),
        meta: { title: '投标验收看板', permission: ['admin', 'qc_manager'] },
      },
    ],
  },
  // 系统配置（数据库连接、同步管理）
  {
    path: '/system-config',
    redirect: { path: '/workstation-v5/system-config' },
    meta: {
      requiresAuth: false,
      title: '数据同步配置',
    },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFoundView.vue'),
    meta: {
      title: '页面未找到',
    },
  },
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
  },
})

type AuthStoreFactory = (typeof import('@/stores/auth'))['useAuthStore']

let authStoreLoader: Promise<AuthStoreFactory> | null = null

async function getAuthStore() {
  if (!authStoreLoader) {
    authStoreLoader = import('@/stores/auth').then((module) => module.useAuthStore)
  }

  const useAuthStore = await authStoreLoader
  return useAuthStore()
}

// 路由守卫
router.beforeEach(async (to, from, next) => {
  if (
    to.path === LEGACY_WORKSTATION_BASE_PATH ||
    to.path.startsWith(`${LEGACY_WORKSTATION_BASE_PATH}/`)
  ) {
    next({
      path: normalizeWorkstationPath(to.path),
      query: to.query,
      hash: to.hash,
      replace: true,
    })
    return
  }

  const authStore = await getAuthStore()
  const isWorkstationRoute = to.path.startsWith(WORKSTATION_BASE_PATH)
  const isWorkstationLogin = to.name === 'WorkstationV4Login'
  const demoBypassEnabled = isDemoRouteBypassEnabled()
  const isDashboardTestRoute = to.name !== 'NotFound' && isDashboardTestPath(to.path)

  // 检查是否为演示模式（通过URL参数 ?demo=true）
  const isDemoMode = to.query.demo === 'true'
  const allowDemo = to.meta.allowDemo === true

  // 仅在非生产构建或显式开启演示开关时允许 ?demo=true 跳过认证检查
  if (demoBypassEnabled && isDemoMode && allowDemo) {
    // 设置页面标题
    if (to.meta.title) {
      document.title = `${to.meta.title} - 大模型病案质控系统`
    }
    next()
    return
  }

  // 工作台专属登录页：已登录则直接回工作台目标页
  if (isWorkstationLogin) {
    if (!authStore.isAuthenticated) {
      await authStore.initialize()
    }

    if (authStore.isAuthenticated) {
      const redirect =
        typeof to.query.redirect === 'string'
          ? normalizeWorkstationPath(to.query.redirect)
          : WORKSTATION_BASE_PATH
      next(redirect)
      return
    }
  }

  // 生产构建且未开启演示开关时，关闭匿名 /dashboard/test/* 路由，强制认证并拦截访问
  const requiresAuth = to.meta.requiresAuth !== false || (isDashboardTestRoute && !demoBypassEnabled)

  // 检查是否需要认证
  if (requiresAuth) {
    // 检查用户是否已登录
    if (!authStore.isAuthenticated) {
      // 尝试从存储中恢复用户状态
      await authStore.initialize()

      if (!authStore.isAuthenticated) {
        if (isWorkstationRoute) {
          next({
            path: '/workstation-v5/login',
            query: { redirect: to.fullPath },
          })
        } else {
          next({
            path: '/auth/login',
            query: { redirect: to.fullPath },
          })
        }
        return
      }
    }

    if (isDashboardTestRoute && !demoBypassEnabled) {
      next({
        name: 'NotFound',
        params: { pathMatch: to.path.replace(/^\/+/, '').split('/') },
        replace: true,
      })
      return
    }

    if (to.path === `${WORKSTATION_BASE_PATH}/worklist` && to.query.assist === 'message' &&
        Object.keys(to.query).length === 1 && canUseMessageCenter(authStore.userRoles)) {
      next({ path: MESSAGE_CENTER_PATH, replace: true })
      return
    }

    // 检查权限
    if (to.meta.permission) {
      const userRoles = authStore.userRoles
      const requiredPermissions = to.meta.permission as string[]

      const hasPermission = userRoles.includes('sync_admin') || requiredPermissions.some((permission) => userRoles.includes(permission))

      if (!hasPermission) {
        // 普通质控员已有待办权限，不能回到无权进入的首页形成重定向循环。
        if (userRoles.includes('qc_staff')) {
          next('/workstation-v5/feedback')
          return
        }
        // 仪表板会返回工作台首页。已在首页时，使用登录后可访问的个人资料页。
        next(to.name === 'WorkstationV4Index' ? '/auth/profile' : '/dashboard')
        return
      }
    }

    // 联动参数会在病历打开后清除，先进入稳定的病历池路由。
    if (
      to.name === 'WorkstationV4Index' &&
      to.query.source === 'dashboard' &&
      typeof to.query.record_id === 'string' && to.query.record_id.trim() &&
      typeof to.query.action === 'string' && to.query.action.trim()
    ) {
      next({ name: 'WorkstationV4Worklist', query: to.query, hash: to.hash, replace: true })
      return
    }
  }

  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - 大模型病案质控系统`
  }

  next()
})

export default router
