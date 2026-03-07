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
        component: () => import('@/views/dashboard/records/RunningRecordsViewNew.vue'),
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
      // 智能质控工作站 V1（旧版保留）
      {
        path: 'workstation',
        name: 'Workstation',
        component: () => import('@/views/workstation/WorkstationView.vue'),
        meta: {
          title: '智能质控工作站',
          icon: 'DesktopOutlined',
          permission: ['admin', 'qc_manager', 'coder']
        }
      },
      {
        path: 'workstation/import',
        name: 'DataImport',
        component: () => import('@/views/workstation/DataImportView.vue'),
        meta: {
          title: '病历数据导入',
          hidden: true,
          permission: ['admin', 'qc_manager']
        }
      },
      {
        path: 'workstation/qc-overview',
        name: 'QCOverview',
        component: () => import('@/views/workstation/QCOverviewView.vue'),
        meta: {
          title: '质控消息概览',
          hidden: true,
          permission: ['admin', 'qc_manager']
        }
      },
      {
        path: 'workstation/qc-stats',
        name: 'QCStats',
        component: () => import('@/views/workstation/QCStatsView.vue'),
        meta: {
          title: '质控统计分析',
          hidden: true,
          permission: ['admin', 'qc_manager']
        }
      },
      {
        path: 'frontpage-demo',
        name: 'FrontPageAutoDemo',
        component: () => import('@/views/demo/FrontPageDemoView.vue'),
        meta: {
          title: '首页自动生成（Demo）',
          icon: 'FileTextOutlined',
          permission: ['admin', 'qc_manager']
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
      // 质控流程相关路由
      {
        path: 'qc/appeals',
        name: 'AppealList',
        component: () => import('@/views/qc/AppealList.vue'),
        meta: {
          title: '质控申诉',
          icon: 'MessageOutlined',
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },
      {
        path: 'qc/rectifications',
        name: 'RectificationList',
        component: () => import('@/views/qc/RectificationList.vue'),
        meta: {
          title: '整改任务',
          icon: 'ToolOutlined',
          permission: ['admin', 'qc_manager', 'doctor']
        }
      },


      // 质控规则管理路由（统一的标签页版本，包含传统规则、语义规则和科室规则）
      {
        path: 'rules',
        name: 'Rules',
        component: () => import('@/views/rules/RulesView.vue'),
        meta: {
          title: '质控规则管理',
          icon: 'SettingOutlined',
          permission: ['admin', 'qc_manager']
        }
      },
      {
        path: 'rules/docs',
        name: 'RuleDocs',
        component: () => import('@/views/rules/RuleDocView.vue'),
        meta: {
          title: '质控规则说明',
          icon: 'FileTextOutlined',
          permission: ['admin', 'qc_manager'],
          hidden: true
        }
      },
      // 科室级质控规则管理路由（重定向到统一的规则管理页面）
      {
        path: 'department-rules',
        redirect: '/dashboard/rules?tab=department',
        meta: {
          hidden: true // 隐藏在菜单中，已整合到主规则管理页面
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
      // 自定义质控规则管理路由（泸县33条规则）
      {
        path: 'custom-rules',
        name: 'CustomRules',
        component: () => import('@/components/CustomRulesManager.vue'),
        meta: {
          title: '自定义质控规则',
          icon: 'AppstoreOutlined',
          permission: ['admin', 'qc_manager']
        }
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
          allowDemo: true  // 允许演示模式访问（通过?demo=true参数）
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
        path: 'llm-qc-demo-new',
        name: 'LLMQCDemoEnhancedNew',
        component: () => import('@/views/demo/LLMQCDemoEnhancedNew.vue'),
        meta: {
          title: 'LLM质控演示新版（测试）',
          icon: 'ExperimentOutlined',
          permission: ['admin'],
          description: '重构后的LLM质控演示系统 - P0测试版'
        }
      },
      {
        path: 'sichuan-qc-demo',
        name: 'SichuanQCDemo',
        component: () => import('@/views/demo/SichuanQCDemo.vue'),
        meta: {
          title: '四川质控引擎演示',
          icon: 'ThunderboltOutlined',
          permission: ['admin'],
          description: '基于阿里云百炼 LLM 的四川质控引擎演示，展示首次病程记录质控分析'
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
      // DRG/DIP 模块路由
      {
        path: 'drg',
        name: 'DRG',
        redirect: '/dashboard/drg/index',
        meta: {
          title: 'DRG/DIP',
          icon: 'MedicineBoxOutlined',
          allowDemo: true,
          permission: ['admin', 'qc_manager', 'coder', 'reviewer']
        },
        children: [
          {
            path: 'index',
            name: 'DRGIndex',
            component: () => import('@/views/drg/Index.vue'),
            meta: {
              title: 'DRG 首页',
              icon: 'HomeOutlined'
            }
          },
          {
            path: 'coding',
            name: 'CodingAssistant',
            component: () => import('@/views/drg/CodingAssistant.vue'),
            meta: {
              title: '编码辅助',
              icon: 'EditOutlined',
              description: 'ICD 编码推荐和校验'
            }
          },
          {
            path: 'coding/:admissionId',
            name: 'CodingDetail',
            component: () => import('@/views/drg/CodingDetail.vue'),
            meta: {
              title: '编码详情',
              hidden: true
            }
          },
          {
            path: 'grouping',
            name: 'GroupingPredict',
            component: () => import('@/views/drg/GroupingPredict.vue'),
            meta: {
              title: 'DRG 分组',
              icon: 'ClusterOutlined',
              description: 'DRG 入组预测和费用分析'
            }
          },
          {
            path: 'config',
            name: 'GrouperConfig',
            component: () => import('@/views/drg/GrouperConfig.vue'),
            meta: {
              title: '分组器配置',
              icon: 'SettingOutlined',
              description: '分组规则与参数配置'
            }
          },
          {
            path: 'settlement',
            name: 'SettlementForm',
            component: () => import('@/views/drg/SettlementForm.vue'),
            meta: {
              title: '医保结算清单',
              icon: 'FileProtectOutlined',
              description: '医保结算清单填报与质控'
            }
          },
          {
            path: 'monitor',
            name: 'MonitorDashboard',
            component: () => import('@/views/drg/MonitorDashboard.vue'),
            meta: {
              title: '事中监控',
              icon: 'DashboardOutlined',
              description: '实时预警和编码建议'
            }
          },
          {
            path: 'fee-monitoring',
            name: 'FeeMonitoring',
            component: () => import('@/views/drg/FeeMonitoring.vue'),
            meta: {
              title: '付费监测',
              icon: 'DollarOutlined',
              description: '费用监测与未入组修正建议'
            }
          },
          {
            path: 'analysis',
            name: 'DRGAnalysis',
            component: () => import('@/views/drg/Analysis.vue'),
            meta: {
              title: '事后分析',
              icon: 'BarChartOutlined',
              description: 'DRG 绩效统计和盈亏分析',
              permission: ['admin', 'qc_manager']
            }
          }
        ]
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
  // 演示页面路由 (无需登录)
  {
    path: '/demo/lx33',
    component: () => import('@/layouts/SimpleLayout.vue'),
    meta: {
      requiresAuth: false
    },
    children: [
      {
        path: '',
        name: 'LX33Demo',
        component: () => import('@/views/demo/LX33DemoView.vue'),
        meta: {
          requiresAuth: false,
          title: '泸县33条质控规则演示'
        }
      },
      {
        path: 'feedbacks',
        name: 'LX33Feedbacks',
        component: () => import('@/views/demo/FeedbacksView.vue'),
        meta: {
          requiresAuth: false,
          title: '反馈记录'
        }
      },
      {
        path: 'create',
        name: 'LX33CreateRule',
        component: () => import('@/views/demo/LX33CreateRuleView.vue'),
        meta: {
          requiresAuth: false,
          title: 'AI智能创建质控规则'
        }
      },
      {
        path: 'frontpage-demo',
        name: 'FrontPageDemo',
        component: () => import('@/views/demo/FrontPageDemoView.vue'),
        meta: {
          requiresAuth: false,
          title: '病案首页自动生成 Demo'
        }
      }
    ]
  },
  // 验收工作站 V2（独立 Layout，与 Dashboard 完全隔离）
  {
    path: '/workstation-v2',
    component: () => import('@/components/layout/WorkstationLayout.vue'),
    meta: {
      requiresAuth: false,
      title: '病案智能质控工作站'
    },
    children: [
      {
        path: '',
        name: 'WorkstationV2',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'workbench' },
        meta: { title: '工作台' }
      },

      {
        path: 'icd',
        name: 'WorkstationV2ICD',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'icd-search' },
        meta: { title: 'ICD 编码查询' }
      },
      {
        path: 'upload',
        name: 'WorkstationV2Upload',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'upload' },
        meta: { title: '数据上传' }
      },
      {
        path: 'stats',
        name: 'WorkstationV2Stats',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'workbench' },
        meta: { title: '统计分析' }
      },
      {
        path: 'drg/pre',
        name: 'WorkstationV2DRGPre',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'pre-analysis' },
        meta: { title: '事前分析' }
      },
      {
        path: 'drg/mid',
        name: 'WorkstationV2DRGMid',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'mid-analysis' },
        meta: { title: '事中监控' }
      },
      {
        path: 'drg/payment',
        name: 'WorkstationV2DRGPayment',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'payment' },
        meta: { title: '付费监测' }
      },
      {
        path: 'drg/post',
        name: 'WorkstationV2DRGPost',
        component: () => import('@/views/workstation-v2/WorkstationV2View.vue'),
        props: { embedded: true, initialView: 'post-analysis' },
        meta: { title: '事后分析' }
      },
      {
        path: 'data',
        name: 'WorkstationV2Data',
        component: () => import('@/views/workstation-v2/CDMDataView.vue'),
        meta: { title: '数据管理' }
      },
    ]
  },
  // 工作台 V3 (卡片式布局)
  {
    path: '/workstation-v3',
    component: () => import('@/components/layout/WorkstationLayout.vue'),
    meta: {
      requiresAuth: false,
      title: '病案智能提取工作台 V3'
    },
    children: [
      {
        path: '',
        name: 'WorkstationV3Index',
        component: () => import('@/views/workstation-v2/WorkstationV3View.vue'),
        meta: { title: '工作台 V3', permission: ['admin', 'qc_manager', 'doctor'] }
      }
    ]
  },
  // 病案工作台 V4（科室侧边栏 + 表格）
  {
    path: '/workstation-v4',
    component: () => import('@/components/layout/WorkstationLayout.vue'),
    meta: {
      requiresAuth: false,
      title: '病案工作台 V4'
    },
    children: [
      {
        path: '',
        name: 'WorkstationV4Index',
        component: () => import('@/views/workstation-v2/WorkstationV4View.vue'),
        meta: { title: '工作台 V4', permission: ['admin', 'qc_manager', 'doctor'] }
      }
    ]
  },
  // 系统配置（数据库连接、同步管理）
  {
    path: '/system-config',
    component: () => import('@/components/layout/WorkstationLayout.vue'),
    meta: {
      requiresAuth: false,
      title: '数据源配置'
    },
    children: [
      {
        path: '',
        name: 'SystemConfigIndex',
        component: () => import('@/views/workstation-v2/SystemConfigView.vue'),
        meta: { title: '数据源配置', permission: ['admin'] }
      }
    ]
  },
  {
    path: '/demo/clinical-workstation',
    name: 'ClinicalWorkstationDemo',
    component: () => import('@/views/demo/ClinicalWorkstationDemoView.vue'),
    meta: {
      requiresAuth: false,
      title: '临床工作站 Demo'
    }
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
