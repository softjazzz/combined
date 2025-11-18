import { ref, reactive } from 'vue'
import { message } from 'ant-design-vue'
import type { TablePaginationConfig } from 'ant-design-vue'
import dayjs from 'dayjs'
import {
  departmentQCRulesService,
  type DepartmentRule,
  type RuleChangeLog,
  RuleStatus,
  OverrideAction,
} from '@/services/department-qc-rules-service'
import { RulesService } from '@/services/rules-service'

export interface Department {
  id: string
  name: string
  code?: string
}

export function useDepartmentRules() {
  // ============================================================================
  // 响应式数据
  // ============================================================================

  const loading = ref(false)
  const rules = ref<DepartmentRule[]>([])
  const departments = ref<Department[]>([])
  const globalRules = ref<any[]>([])

  // 筛选器
  const filters = reactive({
    department_id: undefined as string | undefined,
    status_filter: undefined as string | undefined,
    override_action: undefined as string | undefined,
    keyword: undefined as string | undefined,
  })

  // 分页
  const pagination = reactive({
    current: 1,
    pageSize: 20,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total: number) => `共 ${total} 条`,
  })

  // 模态框
  const modalVisible = ref(false)
  const modalLoading = ref(false)
  const modalTitle = ref('')
  const isCreateMode = ref(false)
  const createMode = ref<'override' | 'new'>('new')

  // 表单
  const formRef = ref()
  const formData = reactive({
    id: '',
    department_id: '',
    base_rule_id: undefined as string | undefined,
    rule_code: '',
    name: '',
    description: '',
    category: 'completeness',
    severity: 'minor',
    override_action: OverrideAction.OVERRIDE,
    priority: 0,
    status: RuleStatus.DRAFT,
    effective_from: undefined as string | undefined,
    effective_to: undefined as string | undefined,
    check_logic: {} as Record<string, any>,
    scoring_config: {} as Record<string, any>,
    applicable_documents: [] as string[],
  })

  const effectiveDateRange = ref<[string, string] | undefined>()

  const formRules = {
    department_id: [{ required: true, message: '请选择科室', trigger: 'change' }],
    rule_code: [{ required: true, message: '请输入规则编号', trigger: 'blur' }],
    name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
    category: [{ required: true, message: '请选择规则分类', trigger: 'change' }],
    severity: [{ required: true, message: '请选择严重程度', trigger: 'change' }],
  }

  // 变更历史
  const historyModalVisible = ref(false)
  const changeLogs = ref<RuleChangeLog[]>([])
  const currentRuleId = ref<string>('')
  const historyPagination = reactive({
    current: 1,
    pageSize: 10,
    total: 0,
  })

  // ============================================================================
  // 辅助函数
  // ============================================================================

  const getDepartmentName = (departmentId?: string) => {
    if (!departmentId) return '-'
    const dept = departments.value.find((d) => d.id === departmentId)
    return dept?.name || departmentId
  }

  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      draft: 'orange',
      published: 'green',
      archived: 'gray',
    }
    return colorMap[status] || 'default'
  }

  const getStatusText = (status: string) => {
    const textMap: Record<string, string> = {
      draft: '草稿',
      published: '已发布',
      archived: '已归档',
    }
    return textMap[status] || status
  }

  const getActionColor = (action: string) => {
    const colorMap: Record<string, string> = {
      create: 'green',
      update: 'blue',
      delete: 'red',
      publish: 'purple',
      archive: 'gray',
    }
    return colorMap[action] || 'blue'
  }

  const getActionText = (action: string) => {
    const textMap: Record<string, string> = {
      create: '创建',
      update: '更新',
      delete: '删除',
      publish: '发布',
      archive: '归档',
      enable: '启用',
      disable: '禁用',
    }
    return textMap[action] || action
  }

  const formatDateTime = (dateStr: string) => {
    return dayjs(dateStr).format('YYYY-MM-DD HH:mm:ss')
  }

  const filterDepartmentOption = (input: string, option: any) => {
    return option.children[0].children.toLowerCase().includes(input.toLowerCase())
  }

  const filterRuleOption = (input: string, option: any) => {
    return option.children[0].children.toLowerCase().includes(input.toLowerCase())
  }

  // ============================================================================
  // 数据加载
  // ============================================================================

  const loadDepartments = async () => {
    try {
      // TODO: 调用真实的科室列表 API
      // 暂时使用模拟数据
      departments.value = [
        { id: '11111111-1111-1111-1111-111111111111', name: 'TEST_CARDIO (测试心内科)', code: 'TEST_CARDIO' },
        { id: '22222222-2222-2222-2222-222222222222', name: 'TEST_SURGERY (测试外科)', code: 'TEST_SURGERY' },
        { id: '33333333-3333-3333-3333-333333333333', name: 'TEST_PEDIATRICS (测试儿科)', code: 'TEST_PEDIATRICS' },
        { id: '44444444-4444-4444-4444-444444444444', name: 'TEST_OBGYN (测试妇产科)', code: 'TEST_OBGYN' },
      ]
    } catch (error) {
      console.error('加载科室列表失败:', error)
    }
  }

  const loadGlobalRules = async () => {
    try {
      const allRules = await RulesService.getAllRules()
      // 过滤出全局规则（scope === 'global' 或者没有 scope 字段的规则）
      globalRules.value = allRules.filter((rule: any) => {
        return !rule.scope || rule.scope === 'global'
      })
    } catch (error) {
      console.error('加载全局规则失败:', error)
      globalRules.value = []
    }
  }

  const loadRules = async () => {
    loading.value = true
    try {
      const result = await departmentQCRulesService.listDepartmentRules({
        department_id: filters.department_id,
        status_filter: filters.status_filter,
        override_action: filters.override_action,
        keyword: filters.keyword,
        page: pagination.current,
        limit: pagination.pageSize,
      })

      rules.value = result.items
      pagination.total = result.total
    } catch (error) {
      console.error('加载规则列表失败:', error)
      message.error('加载规则列表失败')
    } finally {
      loading.value = false
    }
  }

  const refreshRules = () => {
    loadRules()
  }

  // ============================================================================
  // 事件处理
  // ============================================================================

  const handleFilterChange = () => {
    pagination.current = 1
    loadRules()
  }

  const handleTableChange = (pag: TablePaginationConfig) => {
    pagination.current = pag.current || 1
    pagination.pageSize = pag.pageSize || 20
    loadRules()
  }

  // ============================================================================
  // 模态框操作
  // ============================================================================

  const showCreateModal = () => {
    isCreateMode.value = true
    createMode.value = 'new'
    modalTitle.value = '新增科室规则'
    resetFormData()
    modalVisible.value = true
  }

  const editRule = (record: DepartmentRule) => {
    isCreateMode.value = false
    modalTitle.value = '编辑科室规则'
    Object.assign(formData, {
      id: record.id,
      department_id: record.department_id,
      rule_code: record.rule_code,
      name: record.name,
      description: record.description,
      category: record.category,
      severity: record.severity,
      override_action: record.override_action,
      priority: record.priority,
      status: record.status,
      check_logic: record.check_logic || {},
      scoring_config: record.scoring_config || {},
      applicable_documents: record.applicable_documents || [],
    })

    if (record.effective_from && record.effective_to) {
      effectiveDateRange.value = [record.effective_from, record.effective_to]
    }

    modalVisible.value = true
  }

  const viewRule = (record: DepartmentRule) => {
    // TODO: 实现查看详情
    message.info('查看规则详情功能待实现')
  }

  const publishRule = async (record: DepartmentRule) => {
    try {
      await departmentQCRulesService.publishDepartmentRule(record.id, {
        approved_by: 'current_user', // TODO: 从用户上下文获取
        reason: '发布规则',
      })
      message.success('规则发布成功')
      await refreshRules()
    } catch (error) {
      console.error('规则发布失败:', error)
      message.error('规则发布失败')
    }
  }

  const deleteRule = async (record: DepartmentRule) => {
    try {
      await departmentQCRulesService.deleteDepartmentRule(record.id)
      message.success('规则删除成功')
      await refreshRules()
    } catch (error) {
      console.error('规则删除失败:', error)
      message.error('规则删除失败')
    }
  }

  const viewHistory = async (record: DepartmentRule) => {
    currentRuleId.value = record.id
    historyModalVisible.value = true
    await loadHistory()
  }

  const loadHistory = async () => {
    try {
      const result = await departmentQCRulesService.getRuleChangeHistory(
        currentRuleId.value,
        historyPagination.current,
        historyPagination.pageSize
      )
      changeLogs.value = result.items
      historyPagination.total = result.total
    } catch (error) {
      console.error('加载变更历史失败:', error)
      message.error('加载变更历史失败')
    }
  }

  const handleHistoryPageChange = (page: number, pageSize: number) => {
    historyPagination.current = page
    historyPagination.pageSize = pageSize
    loadHistory()
  }

  const handleCreateModeChange = () => {
    if (createMode.value === 'new') {
      formData.base_rule_id = undefined
      formData.rule_code = ''
      formData.name = ''
      formData.description = ''
    }
  }

  const handleBaseRuleChange = (ruleId: string) => {
    const baseRule = globalRules.value.find((r) => r.id === ruleId)
    if (baseRule) {
      // 自动填充基础规则的信息
      formData.rule_code = baseRule.rule_code
      formData.name = `${baseRule.name} (科室定制)`
      formData.description = baseRule.description
      formData.category = baseRule.category
      formData.severity = baseRule.severity
      formData.check_logic = baseRule.check_logic || {}
      formData.scoring_config = baseRule.scoring_config || {}
      formData.applicable_documents = baseRule.applicable_documents || []
    }
  }

  const handleModalOk = async () => {
    try {
      await formRef.value?.validate()
      modalLoading.value = true

      const submitData: any = {
        department_id: formData.department_id,
        rule_code: formData.rule_code,
        name: formData.name,
        description: formData.description,
        category: formData.category,
        severity: formData.severity,
        override_action: formData.override_action,
        priority: formData.priority,
        check_logic: formData.check_logic,
        scoring_config: formData.scoring_config,
        applicable_documents: formData.applicable_documents,
      }

      if (effectiveDateRange.value && effectiveDateRange.value.length === 2) {
        submitData.effective_from = effectiveDateRange.value[0]
        submitData.effective_to = effectiveDateRange.value[1]
      }

      // 如果是覆盖模式，添加 base_rule_id
      if (isCreateMode.value && createMode.value === 'override' && formData.base_rule_id) {
        submitData.base_rule_id = formData.base_rule_id
      }

      if (isCreateMode.value) {
        await departmentQCRulesService.createDepartmentRule(submitData)
        message.success('规则创建成功')
      } else {
        await departmentQCRulesService.updateDepartmentRule(formData.id, submitData)
        message.success('规则更新成功')
      }

      modalVisible.value = false
      await refreshRules()
    } catch (error) {
      console.error('保存规则失败:', error)
      message.error('保存规则失败')
    } finally {
      modalLoading.value = false
    }
  }

  const handleModalCancel = () => {
    modalVisible.value = false
    resetFormData()
  }

  const resetFormData = () => {
    Object.assign(formData, {
      id: '',
      department_id: '',
      base_rule_id: undefined,
      rule_code: '',
      name: '',
      description: '',
      category: 'completeness',
      severity: 'minor',
      override_action: OverrideAction.OVERRIDE,
      priority: 0,
      status: RuleStatus.DRAFT,
      effective_from: undefined,
      effective_to: undefined,
      check_logic: {},
      scoring_config: {},
      applicable_documents: [],
    })
    effectiveDateRange.value = undefined
    formRef.value?.resetFields()
  }

  // ============================================================================
  // 初始化
  // ============================================================================

  const initialize = async () => {
    await Promise.all([loadDepartments(), loadGlobalRules(), loadRules()])
  }

  return {
    // 数据
    loading,
    rules,
    departments,
    globalRules,
    filters,
    pagination,
    modalVisible,
    modalLoading,
    modalTitle,
    isCreateMode,
    createMode,
    formRef,
    formData,
    formRules,
    effectiveDateRange,
    historyModalVisible,
    changeLogs,
    historyPagination,

    // 方法
    getDepartmentName,
    getStatusColor,
    getStatusText,
    getActionColor,
    getActionText,
    formatDateTime,
    filterDepartmentOption,
    filterRuleOption,
    loadDepartments,
    loadGlobalRules,
    loadRules,
    refreshRules,
    handleFilterChange,
    handleTableChange,
    showCreateModal,
    editRule,
    viewRule,
    publishRule,
    deleteRule,
    viewHistory,
    loadHistory,
    handleHistoryPageChange,
    handleCreateModeChange,
    handleBaseRuleChange,
    handleModalOk,
    handleModalCancel,
    resetFormData,
    initialize,
  }
}

