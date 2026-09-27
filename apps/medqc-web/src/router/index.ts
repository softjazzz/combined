import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import {
  NO_PERMISSION_PATH,
  canAccessRouteMeta,
  resolveDeniedFallback,
  resolveLoginLanding,
} from '@/utils/routeAccess'
import {
  DRG_ANALYSIS_ROLES,
  DRG_ROLES,
  QC_ANALYTICS_ROLES,
  RULE_ADMIN_ROLES,
} from './routeRoles'

const WORKSTATION_BASE_PATH = '/workstation-v5'
const LEGACY_WORKSTATION_BASE_PATH = '/workstation-v4'

function normalizeWorkstationPath(path: string) {
  if (path === LEGACY_WORKSTATION_BASE_PATH || path.startsWith(`${LEGACY_WORKSTATION_BASE_PATH}/`)) {
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
        component: () => import('@/views/dashboard/records/OutpatientEmergencyRecordsView.vue'),
        meta: {
          title: '门急诊病历',
          icon: 'MedicineBoxOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'records/running',
        name: 'RunningRecords',
        redirect: (to) => ({
          path: '/workstation-v5/records/running',
          query: to.query,
          hash: to.hash,
        }),
        meta: {
          title: '运行病历',
          icon: 'PlayCircleOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'records/final',
        name: 'FinalRecords',
        component: () => import('@/views/dashboard/records/FinalRecordsView.vue'),
        meta: {
          title: '已出院病历',
          icon: 'CheckCircleOutlined',
          permission: ['admin', 'qc_manager'],
        },
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
          title: '问题集中点',
          permission: ['admin', 'qc_manager'],
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
        component: () => import('@/views/demo/FrontPageDemoView.vue'),
        meta: {
          title: '首页自动生成样例',
          icon: 'FileTextOutlined',
          hidden: true,
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'records/test',
        name: 'TestMedicalRecords',
        component: () => import('@/views/test-medical-records/TestMedicalRecordsView.vue'),
        meta: {
          title: '病历管理',
          icon: 'ProfileOutlined',
          hidden: true,
          // 与后端 /api/v1/qc/sample-pools 路由角色一致，避免可见但接口 403。
          permission: ['admin', 'qc_manager', 'sync_admin'],
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
        component: () => import('@/views/dashboard/tasks/MyTasksView.vue'),
        meta: {
          title: '我的任务',
          icon: 'UserOutlined',
        },
      },
      {
        path: 'tasks/all',
        name: 'AllTasks',
        component: () => import('@/views/dashboard/tasks/AllTasksView.vue'),
        meta: {
          title: '全部任务',
          icon: 'TeamOutlined',
          permission: ['admin', 'qc_manager'],
        },
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
        path: 'qc/manual-defects',
        name: 'ManualDefectReview',
        component: () => import('@/views/qc/ManualDefectReviewView.vue'),
        meta: {
          title: '人工缺陷审核',
          icon: 'AuditOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'qc/record-reviews',
        name: 'RecordReviewTodo',
        component: () => import('@/views/qc/RecordReviewTodoView.vue'),
        meta: {
          title: '病历审核待办',
          icon: 'FileSearchOutlined',
          permission: ['admin', 'qc_manager', 'qc_staff'],
        },
      },
      {
        path: 'qc/scoring-config',
        name: 'ScoringConfig',
        // V3.6 P2-S：替换为评分标准管理页；旧阈值页接的是未被计分服务读取的旧 scoring_config 表。
        component: () => import('@/views/qc/ScoringStandardsView.vue'),
        meta: {
          title: '评分标准配置',
          icon: 'SettingOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'qc/rectifications',
        name: 'RectificationList',
        component: () => import('@/views/qc/RectificationList.vue'),
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
        component: () =>
          import('@/views/dashboard/quality-control/QualityControlPointManagement.vue'),
        meta: {
          title: '非编码质控点管理',
          icon: 'ControlOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'quality-control/create',
        name: 'QualityControlPointCreate',
        component: () => import('@/views/dashboard/quality-control/QualityControlPointCreate.vue'),
        meta: {
          title: '新建质控点',
          hidden: true,
          permission: ['admin', 'qc_manager'],
        },
      },

      // 评分标准配置路由
      {
        path: 'scoring-rules',
        name: 'ScoringRules',
        component: () => import('@/views/dashboard/scoring/ScoringRulesView.vue'),
        meta: {
          title: '评分标准配置',
          icon: 'StarOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'staff-ranking',
        name: 'StaffRanking',
        component: () => import('@/views/dashboard/ranking/StaffRankingView.vue'),
        meta: {
          title: '质控员工作量排名',
          icon: 'TrophyOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'notifications',
        name: 'Notifications',
        component: () => import('@/views/dashboard/notifications/NotificationsView.vue'),
        meta: {
          title: '通知与整改',
          icon: 'BellOutlined',
        },
      },

      // 数据权限配置路由
      {
        path: 'permissions',
        name: 'Permissions',
        component: () => import('@/views/dashboard/permissions/PermissionsView.vue'),
        meta: {
          title: '数据权限配置',
          icon: 'SafetyCertificateOutlined',
          permission: ['admin'],
        },
      },
      {
        path: 'llm-qc-demo',
        name: 'LLMQCDemo',
        component: () => import('@/views/demo/LLMQCDemo.vue'),
        meta: {
          title: 'LLM质控演示',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin'],
        },
      },
      {
        path: 'llm-qc-demo-enhanced',
        name: 'LLMQCDemoEnhanced',
        component: () => import('@/views/demo/LLMQCDemoEnhanced.vue'),
        meta: {
          title: 'LLM质控演示增强版',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin'],
          description: '完整的LLM质控演示系统，包含规则应用、通知提醒和申诉功能',
        },
      },
      {
        path: 'llm-qc-demo-new',
        name: 'LLMQCDemoEnhancedNew',
        component: () => import('@/views/demo/LLMQCDemoEnhancedNew.vue'),
        meta: {
          title: 'LLM质控演示新版（测试）',
          icon: 'ExperimentOutlined',
          hidden: true,
          permission: ['admin'],
          description: '重构后的LLM质控演示系统 - P0测试版',
        },
      },
      {
        path: 'sichuan-qc-demo',
        name: 'SichuanQCDemo',
        component: () => import('@/views/demo/SichuanQCDemo.vue'),
        meta: {
          title: '四川质控引擎演示',
          icon: 'ThunderboltOutlined',
          hidden: true,
          permission: ['admin'],
          description: '基于阿里云百炼 LLM 的四川质控引擎演示，展示首次病程记录质控分析',
        },
      },
      {
        path: 'test-demo',
        name: 'TestDemo',
        component: () => import('@/views/demo/TestDemo.vue'),
        meta: {
          title: '组件测试',
          icon: 'BugOutlined',
          hidden: true,
          permission: ['admin'],
          description: '测试演示组件功能',
        },
      },
      {
        path: 'test/llm-config',
        name: 'LLMConfigTest',
        component: () => import('@/views/test/LLMConfigTest.vue'),
        meta: {
          title: 'LLM配置测试',
          icon: 'SettingOutlined',
          hidden: true, // 隐藏在菜单中，只能直接访问
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
        meta: { title: 'Modal测试', icon: 'ExperimentOutlined', hidden: true },
      },
      {
        path: 'test/batch-processor',
        name: 'BatchProcessorTest',
        component: () => import('@/views/test/BatchProcessorTest.vue'),
        meta: { title: '批量处理测试', icon: 'ExperimentOutlined', hidden: true },
      },
      {
        path: 'test/multi-file-upload',
        name: 'MultiFileUploadTest',
        component: () => import('@/views/test/MultiFileUploadTest.vue'),
        meta: { title: '多文件上传测试', icon: 'ExperimentOutlined', hidden: true },
      },
      {
        path: 'test/multi-document-merge',
        name: 'MultiDocumentMergeTest',
        component: () => import('@/views/test/MultiDocumentMergeTest.vue'),
        meta: { title: '多文档合并测试', icon: 'ExperimentOutlined', hidden: true },
      },
      {
        path: 'test/classification-version',
        name: 'ClassificationVersionTest',
        component: () => import('@/views/test/ClassificationVersionTest.vue'),
        meta: { title: '分类算法版本测试', icon: 'BranchesOutlined', hidden: true },
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
        component: () => import('@/views/medical-records/MedicalRecordDetail.legacy.vue'),
        meta: {
          title: '病历详情（经典版）',
          hidden: true,
          permission: ['admin', 'qc_manager', 'doctor'],
        },
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
        component: () => import('@/views/medical-records/MedicalRecordDetailSimple.vue'),
        meta: {
          title: '病历详情（简化版）',
          hidden: true,
          requiresAuth: false,
        },
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
        path: 'qc/reports/record-quality',
        name: 'RecordQualityReport',
        component: () => import('@/views/qc/reports/RecordQualityReportView.vue'),
        meta: {
          title: '病历质量分析',
          icon: 'BarChartOutlined',
          permission: ['admin', 'qc_manager'],
        },
      },
      {
        path: 'qc/reports/staff-analysis',
        name: 'StaffAnalysisReport',
        component: () => import('@/views/qc/reports/StaffAnalysisView.vue'),
        meta: {
          title: '质控员工作分析',
          icon: 'BarChartOutlined',
          permission: ['admin', 'qc_manager'],
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
          permission: DRG_ROLES,
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
              permission: DRG_ANALYSIS_ROLES,
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
  // 演示页面路由 (无需登录)
  {
    path: '/demo/lx33',
    component: () => import('@/layouts/SimpleLayout.vue'),
    meta: {
      requiresAuth: false,
    },
    children: [
      {
        path: '',
        name: 'LX33Demo',
        component: () => import('@/views/demo/LX33DemoView.vue'),
        meta: {
          requiresAuth: false,
          title: '泸县33条质控规则演示',
        },
      },
      {
        path: 'feedbacks',
        name: 'LX33Feedbacks',
        component: () => import('@/views/demo/FeedbacksView.vue'),
        meta: {
          requiresAuth: false,
          title: '反馈记录',
        },
      },
      {
        path: 'create',
        name: 'LX33CreateRule',
        component: () => import('@/views/demo/LX33CreateRuleView.vue'),
        meta: {
          requiresAuth: false,
          title: 'AI智能创建质控规则',
        },
      },
      {
        path: 'frontpage-demo',
        name: 'FrontPageDemo',
        component: () => import('@/views/demo/FrontPageDemoView.vue'),
        meta: {
          requiresAuth: false,
          title: '病案首页自动生成样例',
        },
      },
    ],
  },
  // 验收工作站 V2（独立 Layout，与 Dashboard 完全隔离）
  {
    path: '/workstation-v2',
    component: () => import('@/components/layout/WorkstationLayout.vue'),
    meta: {
      requiresAuth: false,
      title: '病案智能质控工作站',
    },
    children: [
      {
        path: '',
        name: 'WorkstationV2',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'workbench' },
        meta: { title: '工作台' },
      },

      {
        path: 'icd',
        name: 'WorkstationV2ICD',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'icd-search' },
        meta: { title: 'ICD 编码查询' },
      },
      {
        path: 'upload',
        name: 'WorkstationV2Upload',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'upload' },
        meta: { title: '数据上传' },
      },
      {
        path: 'stats',
        name: 'WorkstationV2Stats',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'workbench' },
        meta: { title: '统计分析' },
      },
      {
        path: 'drg/pre',
        name: 'WorkstationV2DRGPre',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'pre-analysis' },
        meta: { title: '事前分析' },
      },
      {
        path: 'drg/mid',
        name: 'WorkstationV2DRGMid',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'mid-analysis' },
        meta: { title: '事中监控' },
      },
      {
        path: 'drg/payment',
        name: 'WorkstationV2DRGPayment',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'payment' },
        meta: { title: '付费监测' },
      },
      {
        path: 'drg/post',
        name: 'WorkstationV2DRGPost',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'post-analysis' },
        meta: { title: '事后分析' },
      },
      {
        path: 'data',
        name: 'WorkstationV2Data',
        component: () => import('@/views/workstation-v2/CDMDataView.vue'),
        meta: { title: '数据管理' },
      },
    ],
  },
  // 工作台 V3 (卡片式布局)
  {
    path: '/workstation-v3',
    component: () => import('@/components/layout/WorkstationLayout.vue'),
    meta: {
      requiresAuth: false,
      title: '病案智能提取工作台 V3',
    },
    children: [
      {
        path: '',
        name: 'WorkstationV3Index',
        component: () => import('@/views/workstation-v2/WorkstationV3View.vue'),
        meta: { title: '工作台 V3', permission: ['admin', 'qc_manager', 'doctor'] },
      },
    ],
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
  // 病案工作台 V5（沿用已验证的工作台组件与内部路由名称）
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
        component: () => import('@/views/dashboard/records/OutpatientEmergencyRecordsView.vue'),
        meta: { title: '门急诊病历', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'records/running',
        name: 'WorkstationV4RunningRecords',
        component: () => import('@/views/workstation-v4/QcRecordResultListView.vue'),
        props: { carePhase: 'inpatient' },
        meta: { title: '运行病历', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'records/final',
        name: 'WorkstationV4FinalRecords',
        component: () => import('@/views/workstation-v4/QcRecordResultListView.vue'),
        props: { carePhase: 'discharged' },
        meta: { title: '已出院病历质控结果', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'qc-feedback-demo',
        name: 'WorkstationV4QcFeedbackDemo',
        component: () => import('@/views/workstation-v4/QcResultFeedbackDemoListView.vue'),
        meta: { title: '质控反馈记录', permission: ['admin', 'qc_manager'] },
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
          import('@/views/workstation-v4/customer-sample-validation/CustomerSampleTaskHistoryView.vue'),
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
        // 上传后的批次查询走 /api/v1/drg/batches（DRG 角色）
        meta: { title: '数据上传', permission: DRG_ROLES },
      },
      {
        path: 'stats',
        name: 'WorkstationV4Stats',
        component: () => import('@/views/workstation-v4/LuxianQcAnalyticsView.vue'),
        meta: { title: '统计分析', permission: QC_ANALYTICS_ROLES },
      },
      {
        path: 'drg/pre',
        name: 'WorkstationV4DRGPre',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'pre-analysis' },
        meta: { title: '事前分析', permission: DRG_ROLES },
      },
      {
        path: 'drg/mid',
        name: 'WorkstationV4DRGMid',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'mid-analysis' },
        meta: { title: '事中监控', permission: DRG_ROLES },
      },
      {
        path: 'drg/payment',
        name: 'WorkstationV4DRGPayment',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'payment' },
        meta: { title: '付费监测', permission: DRG_ROLES },
      },
      {
        path: 'drg/post',
        name: 'WorkstationV4DRGPost',
        component: () => import('@/views/workstation-v4/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'post-analysis' },
        meta: { title: '事后分析', permission: DRG_ANALYSIS_ROLES },
      },
      {
        path: 'grouper',
        name: 'WorkstationV4Grouper',
        component: () => import('@/views/drg-grouper/GrouperTabsView.vue'),
        meta: { title: '医保分组器', permission: DRG_ROLES },
      },
      {
        path: 'data',
        name: 'WorkstationV4Data',
        component: () => import('@/views/workstation-v4/CDMDataView.vue'),
        meta: { title: '数据管理' },
      },
      {
        path: 'rules',
        name: 'WorkstationV4Rules',
        component: () => import('@/views/workstation-v4/WorkstationRulesView.vue'),
        meta: { title: '质控规则管理', permission: RULE_ADMIN_ROLES },
      },
      {
        path: 'rules/custom-workspace',
        name: 'WorkstationV4CustomRuleWorkspace',
        component: () => import('@/views/rules/CustomRuleWorkspaceView.vue'),
        meta: { title: '自定义质控点', permission: ['admin', 'qc_manager'] },
      },
      {
        path: 'qc-overview',
        name: 'WorkstationV4QCOverview',
        component: () => import('@/views/workstation/QCOverviewView.vue'),
        meta: { title: '问题集中点', permission: ['admin', 'qc_manager'] },
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
    path: '/demo/clinical-workstation',
    name: 'ClinicalWorkstationDemo',
    component: () => import('@/views/demo/ClinicalWorkstationDemoView.vue'),
    meta: {
      requiresAuth: false,
      title: '临床工作站样例',
    },
  },
  // 无权访问兜底页：登录即可访问（不设 meta.permission），供守卫在无可访问默认页时落地
  {
    path: NO_PERMISSION_PATH,
    name: 'NoPermission',
    component: () => import('@/views/error/NoPermissionView.vue'),
    meta: {
      requiresAuth: true,
      title: '无权访问',
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

  // 检查是否为演示模式（通过URL参数 ?demo=true）
  const isDemoMode = to.query.demo === 'true'
  const allowDemo = to.meta.allowDemo === true

  // 如果是演示模式且路由允许演示访问，跳过认证检查
  if (isDemoMode && allowDemo) {
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
      // 已登录：redirect 可访问则去 redirect，否则按角色默认落地（避免无 V5 权限的角色被送回工作台后循环重定向）
      const redirect =
        typeof to.query.redirect === 'string' ? normalizeWorkstationPath(to.query.redirect) : null
      next(resolveLoginLanding(router, authStore.userRoles, redirect).target)
      return
    }
  }

  // 检查是否需要认证
  if (to.meta.requiresAuth !== false) {
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

    // 检查权限：以路由 meta.permission 为唯一来源，与菜单过滤、登录落地共用同一判断
    if (!canAccessRouteMeta(to.meta, authStore.userRoles)) {
      // 没有权限：转到角色默认页；默认页不可访问或就是当前被拒目标时落到无权访问页，避免循环重定向
      next(resolveDeniedFallback(router, authStore.userRoles, to.path))
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
