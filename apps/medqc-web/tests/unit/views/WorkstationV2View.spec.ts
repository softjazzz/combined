/**
 * 验收工作站 V2 — 单元测试
 *
 * 测试范围：
 * 1. WorkstationV2View 组件渲染和布局
 * 2. 侧边栏导航和视图切换
 * 3. 分析 Tab 切换
 * 4. 测试用例加载
 * 5. 拖拽分隔线逻辑
 * 6. DRG 分组触发
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { shallowMount, VueWrapper } from '@vue/test-utils'
import { ref, nextTick } from 'vue'
import WorkstationV2View from '@/views/workstation-v2/WorkstationV2View.vue'

// Mock 所有复用组件（它们是 Tailwind 组件，无法在 jsdom 中完整渲染）
vi.mock('@/views/demo/frontpage/components', () => ({
  AIProfileDashboard: {
    name: 'AIProfileDashboard',
    template: '<div class="mock-ai-profile">AI画像</div>',
    props: ['frontpage'],
  },
  InsuranceClaimView: {
    name: 'InsuranceClaimView',
    template: '<div class="mock-insurance">医保清单</div>',
  },
  MedicalRecordPanel: {
    name: 'MedicalRecordPanel',
    template: '<div class="mock-medical-record">{{ medicalText }}</div>',
    props: ['medicalText', 'loading'],
  },
  StructuredDataView: {
    name: 'StructuredDataView',
    template: '<div class="mock-structured-data">首页结果</div>',
    props: ['extracting', 'frontpage', 'hasMedicalText'],
  },
  DRGGroupingTab: {
    name: 'DRGGroupingTab',
    template: '<div class="mock-drg-tab">DRG分组</div>',
    props: [
      'drgResult',
      'loading',
      'hasFrontpage',
      'mainDiagnosisCode',
      'mainDiagnosisText',
      'mainProcedureCode',
      'mainProcedureName',
    ],
  },
  CodingOptimizationDrawer: {
    name: 'CodingOptimizationDrawer',
    template: '<div class="mock-drawer">优化建议</div>',
    props: ['visible', 'loading', 'suggestions', 'getSuggestionTitle'],
  },
  InProcessMonitoringView: {
    name: 'InProcessMonitoringView',
    template: '<div class="mock-mid">事中监控</div>',
  },
  PaymentMonitoringView: {
    name: 'PaymentMonitoringView',
    template: '<div class="mock-payment">付费监测</div>',
  },
  PostEventAnalysisView: {
    name: 'PostEventAnalysisView',
    template: '<div class="mock-post">事后分析</div>',
  },
  ExcelUploadView: { name: 'ExcelUploadView', template: '<div class="mock-upload">数据上传</div>' },
  PreAnalysisView: {
    name: 'PreAnalysisView',
    template: '<div class="mock-pre">事前分析</div>',
    props: ['sessionId', 'batchId'],
  },
}))

// Mock composables
const mockExtractStructuredData = vi.fn()
const mockPerformDRGGrouping = vi.fn()
const mockOpenOptimizationDrawer = vi.fn()
const mockHandleSuggestion = vi.fn()
const mockGetSuggestionTitle = vi.fn(() => '建议标题')

vi.mock('@/views/demo/frontpage/composables', () => ({
  useMedicalTextExtraction: vi.fn(() => ({
    extracting: ref(false),
    extractStructuredData: mockExtractStructuredData,
  })),
  useDRGGrouping: vi.fn(() => ({
    drgLoading: ref(false),
    drgResult: ref(null),
    suggestionDrawerVisible: ref(false),
    suggestionsLoading: ref(false),
    suggestions: ref([]),
    performDRGGrouping: mockPerformDRGGrouping,
    openOptimizationDrawer: mockOpenOptimizationDrawer,
    handleSuggestion: mockHandleSuggestion,
    getSuggestionTitle: mockGetSuggestionTitle,
  })),
}))

// Mock ant-design-vue message
vi.mock('ant-design-vue', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    loading: vi.fn(),
  },
}))

// Mock fetch
globalThis.fetch = vi.fn()

describe('WorkstationV2View', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    vi.clearAllMocks()
    ;(globalThis.fetch as any).mockRejectedValue(new Error('Network error'))
  })

  function createWrapper() {
    return shallowMount(WorkstationV2View, {
      global: {
        stubs: {
          'a-menu': { template: '<div class="a-menu"><slot /></div>', props: ['selectedKeys'] },
          'a-menu-item': {
            template: '<div class="a-menu-item" @click="$emit(\'click\')"><slot /></div>',
          },
          'a-sub-menu': {
            template:
              '<div class="a-sub-menu"><slot /><slot name="title" /><slot name="icon" /></div>',
          },
          'a-menu-divider': { template: '<hr />' },
          'a-button': {
            template: '<button @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'size', 'loading'],
          },
          'a-space': { template: '<div class="a-space"><slot /></div>' },
          'a-tag': { template: '<span class="a-tag"><slot /></span>', props: ['color'] },
          'a-segmented': {
            template: '<div class="a-segmented"></div>',
            props: ['value', 'options', 'size'],
            emits: ['update:value'],
          },
          // Stub all icons
          ThunderboltOutlined: { template: '<i />' },
          MenuFoldOutlined: { template: '<i />' },
          MenuUnfoldOutlined: { template: '<i />' },
          DesktopOutlined: { template: '<i />' },
          ClusterOutlined: { template: '<i />' },
          FileSearchOutlined: { template: '<i />' },
          DashboardOutlined: { template: '<i />' },
          DollarOutlined: { template: '<i />' },
          BarChartOutlined: { template: '<i />' },
          CloudUploadOutlined: { template: '<i />' },
          BellOutlined: { template: '<i />' },
          FileTextOutlined: { template: '<i />' },
          SafetyCertificateOutlined: { template: '<i />' },
          SearchOutlined: { template: '<i />' },
          ProfileOutlined: { template: '<i />' },
        },
      },
    })
  }

  // ==================== 组件渲染 ====================
  describe('组件渲染', () => {
    it('应该正确渲染工作站', () => {
      wrapper = createWrapper()
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.ws-v2').exists()).toBe(true)
    })

    it('应该包含侧边栏', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.ws-v2-sidebar').exists()).toBe(true)
    })

    it('应该包含主内容区', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.ws-v2-main').exists()).toBe(true)
    })

    it('应该默认显示工作台视图', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.workbench-layout').exists()).toBe(true)
    })

    it('应该包含底部测试用例栏', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.workbench-footer').exists()).toBe(true)
    })
  })

  // ==================== 侧边栏 ====================
  describe('侧边栏', () => {
    it('默认应该展开', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.ws-v2-sidebar.collapsed').exists()).toBe(false)
    })

    it('应该包含"AI 质控工作站"标题', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.sidebar-title').exists()).toBe(true)
    })
  })

  // ==================== 视图切换 ====================
  describe('视图切换', () => {
    it('默认 currentView 应该是 workbench', () => {
      wrapper = createWrapper()
      expect(wrapper.vm.currentView).toBe('workbench')
    })

    it('切换到 upload 时应显示上传视图', async () => {
      wrapper = createWrapper()
      wrapper.vm.currentView = 'upload'
      await nextTick()
      expect(wrapper.findComponent({ name: 'ExcelUploadView' }).exists()).toBe(true)
      expect(wrapper.find('.workbench-layout').exists()).toBe(false)
    })

    it('切换到 mid-analysis 时应显示事中监控', async () => {
      wrapper = createWrapper()
      wrapper.vm.currentView = 'mid-analysis'
      await nextTick()
      expect(wrapper.findComponent({ name: 'InProcessMonitoringView' }).exists()).toBe(true)
    })

    it('切换到 payment 时应显示付费监测', async () => {
      wrapper = createWrapper()
      wrapper.vm.currentView = 'payment'
      await nextTick()
      expect(wrapper.findComponent({ name: 'PaymentMonitoringView' }).exists()).toBe(true)
    })

    it('切换到 post-analysis 时应显示事后分析', async () => {
      wrapper = createWrapper()
      wrapper.vm.currentView = 'post-analysis'
      await nextTick()
      expect(wrapper.findComponent({ name: 'PostEventAnalysisView' }).exists()).toBe(true)
    })

    it('切换到 pre-analysis 时应显示事前分析', async () => {
      wrapper = createWrapper()
      wrapper.vm.currentView = 'pre-analysis'
      await nextTick()
      expect(wrapper.findComponent({ name: 'PreAnalysisView' }).exists()).toBe(true)
    })

    it('onMenuClick 应该更新 currentView', () => {
      wrapper = createWrapper()
      wrapper.vm.onMenuClick({ key: 'upload' })
      expect(wrapper.vm.currentView).toBe('upload')
      expect(wrapper.vm.menuSelectedKeys).toEqual(['upload'])
    })
  })

  // ==================== 分析 Tab ====================
  describe('分析 Tab', () => {
    it('默认 activeTab 应该是 frontpage', () => {
      wrapper = createWrapper()
      expect(wrapper.vm.activeTab).toBe('frontpage')
    })

    it('应该有 5 个分析 Tab', () => {
      wrapper = createWrapper()
      expect(wrapper.vm.analysisTabs).toHaveLength(5)
      expect(wrapper.vm.analysisTabs.map((t: any) => t.value)).toEqual([
        'frontpage',
        'qc',
        'drg',
        'profile',
        'icd',
      ])
    })

    it('切换到 drg Tab 应显示 DRGGroupingTab', async () => {
      wrapper = createWrapper()
      wrapper.vm.activeTab = 'drg'
      await nextTick()
      expect(wrapper.findComponent({ name: 'DRGGroupingTab' }).exists()).toBe(true)
    })

    it('切换到 profile Tab 应显示 AIProfileDashboard', async () => {
      wrapper = createWrapper()
      wrapper.vm.activeTab = 'profile'
      await nextTick()
      expect(wrapper.findComponent({ name: 'AIProfileDashboard' }).exists()).toBe(true)
    })

    it('默认 frontpage Tab 应显示 StructuredDataView', () => {
      wrapper = createWrapper()
      expect(wrapper.findComponent({ name: 'StructuredDataView' }).exists()).toBe(true)
    })
  })

  // ==================== 测试用例 ====================
  describe('测试用例', () => {
    it('应该有 2 个默认测试用例', () => {
      wrapper = createWrapper()
      expect(wrapper.vm.testCases).toHaveLength(2)
      expect(wrapper.vm.testCases[0].name).toBe('测试病历1')
      expect(wrapper.vm.testCases[1].name).toBe('测试病历2')
    })

    it('loadDemoCase 应该设置 demoCase', async () => {
      wrapper = createWrapper()
      // 先给测试用例赋值
      wrapper.vm.testCases[0].medical_text = '测试文本'
      await wrapper.vm.loadDemoCase(0)
      expect(wrapper.vm.demoCase).not.toBeNull()
      expect(wrapper.vm.demoCase.case_id).toBe('case_1')
      expect(wrapper.vm.currentCaseIndex).toBe(0)
    })

    it('loadDemoCase 超出范围应该直接返回', async () => {
      wrapper = createWrapper()
      await wrapper.vm.loadDemoCase(-1)
      expect(wrapper.vm.demoCase).toBeNull()

      await wrapper.vm.loadDemoCase(99)
      expect(wrapper.vm.demoCase).toBeNull()
    })
  })

  // ==================== 业务逻辑 ====================
  describe('业务逻辑', () => {
    it('frontpage 计算属性在没有 demoCase 时应为 null', () => {
      wrapper = createWrapper()
      expect(wrapper.vm.frontpage).toBeNull()
    })

    it('performDRGGrouping 在没有 demoCase 时不应调用 composable', () => {
      wrapper = createWrapper()
      wrapper.vm.performDRGGrouping()
      expect(mockPerformDRGGrouping).not.toHaveBeenCalled()
    })

    it('performDRGGrouping 有 demoCase 时应调用 composable', async () => {
      wrapper = createWrapper()
      wrapper.vm.testCases[0].medical_text = '测试'
      await wrapper.vm.loadDemoCase(0)
      wrapper.vm.performDRGGrouping()
      expect(mockPerformDRGGrouping).toHaveBeenCalledWith('case_1', undefined)
    })

    it('handleGoAnalysis 应该切换到 pre-analysis 视图', () => {
      wrapper = createWrapper()
      wrapper.vm.handleGoAnalysis('session_123', 'batch_456')
      expect(wrapper.vm.currentView).toBe('pre-analysis')
      expect(wrapper.vm.selectedSessionId).toBe('session_123')
      expect(wrapper.vm.selectedBatchId).toBe('batch_456')
      expect(wrapper.vm.menuSelectedKeys).toEqual(['pre-analysis'])
    })
  })

  // ==================== 拖拽分隔线 ====================
  describe('拖拽分隔线', () => {
    it('默认左面板宽度应为 50%', () => {
      wrapper = createWrapper()
      expect(wrapper.vm.leftPanelWidth).toBe(50)
    })

    it('分隔线元素应该存在', () => {
      wrapper = createWrapper()
      expect(wrapper.find('.resize-handle').exists()).toBe(true)
    })

    it('startResize 应该设置 isResizing 为 true', () => {
      wrapper = createWrapper()
      const mockEvent = { preventDefault: vi.fn() } as any
      wrapper.vm.startResize(mockEvent)
      expect(wrapper.vm.isResizing).toBe(true)
      expect(mockEvent.preventDefault).toHaveBeenCalled()
    })

    it('stopResize 应该设置 isResizing 为 false', () => {
      wrapper = createWrapper()
      wrapper.vm.isResizing = true
      wrapper.vm.stopResize()
      expect(wrapper.vm.isResizing).toBe(false)
    })
  })
})
