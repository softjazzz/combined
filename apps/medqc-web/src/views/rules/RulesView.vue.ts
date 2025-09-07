"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
// import { RulesService } from '@/services/rules-service'
// import { RulesValidator } from '@/utils/rules-validator'
// import { RULES_CONFIG } from '@/config/rules-config'
// 模拟配置
const RULES_CONFIG = {
    categories: {
        completeness: { label: '完整性', color: 'blue' },
        consistency: { label: '一致性', color: 'green' },
        rationality: { label: '合理性', color: 'orange' },
        timeliness: { label: '及时性', color: 'purple' }
    },
    severities: {
        critical: { label: '严重', color: 'red' },
        major: { label: '重要', color: 'orange' },
        minor: { label: '轻微', color: 'blue' }
    },
    types: {
        objective: { label: '客观规则', color: 'cyan' },
        subjective: { label: '主观规则', color: 'magenta' },
        hybrid: { label: '混合规则', color: 'geekblue' }
    }
};
// 响应式数据
const loading = (0, vue_1.ref)(false);
const rules = (0, vue_1.ref)(: any[]);
const selectedRowKeys = (0, vue_1.ref)(: any[]);
const searchText = (0, vue_1.ref)('');
const filterCategory = (0, vue_1.ref)();
const filterSeverity = (0, vue_1.ref)();
const filterType = (0, vue_1.ref)();
const filterStatus = (0, vue_1.ref)();
// 模态框相关
const modalVisible = (0, vue_1.ref)(false);
const modalLoading = (0, vue_1.ref)(false);
const modalTitle = (0, vue_1.ref)('');
const formRef = (0, vue_1.ref)();
const isEditing = (0, vue_1.ref)(false);
const editingId = (0, vue_1.ref)();
// 表单数据
const formData = (0, vue_1.reactive)({
    rule_code: '',
    name: '',
    description: '',
    category: 'completeness',
    rule_type: 'objective',
    severity: 'minor',
    max_score: 0,
    weight: 1.0,
    is_active: true,
    check_logic: {},
    prompt_template: '',
    version: '1.0'
});
const checkLogicText = (0, vue_1.ref)('');
// 表单验证规则
const formRules = {
    rule_code: [
        { required: true, message: '请输入规则编码' },
        { pattern: /^\d+(\.\d+)*$/, message: '规则编码格式不正确，如: 1.1.1' }
    ],
    name: [
        { required: true, message: '请输入规则名称' },
        { min: 2, max: 100, message: '规则名称长度在2-100个字符' }
    ],
    description: [
        { required: true, message: '请输入规则描述' },
        { min: 10, max: 500, message: '规则描述长度在10-500个字符' }
    ],
    category: [{ required: true, message: '请选择规则分类' }],
    rule_type: [{ required: true, message: '请选择规则类型' }],
    severity: [{ required: true, message: '请选择严重程度' }],
    max_score: [{ required: true, type: 'number', min: 0, max: 100, message: '最大扣分范围0-100' }],
    weight: [{ required: true, type: 'number', min: 0.1, max: 5.0, message: '权重范围0.1-5.0' }]
};
// 分页配置
const pagination = (0, vue_1.reactive)({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
});
// 表格列配置
const columns = [
    {
        title: '规则编码',
        dataIndex: 'rule_code',
        key: 'rule_code',
        width: 90,
        sorter: true
    },
    {
        title: '质控点来源',
        dataIndex: 'name',
        key: 'source',
        width: 180
    },
    {
        title: '质控点名称',
        dataIndex: 'description',
        key: 'name',
        width: 220
    },
    {
        title: '分类',
        dataIndex: 'category',
        key: 'category',
        width: 80,
        filters: [
            { text: '完整性', value: 'completeness' },
            { text: '一致性', value: 'consistency' },
            { text: '合理性', value: 'rationality' },
            { text: '及时性', value: 'timeliness' }
        ]
    },
    {
        title: '严重程度',
        dataIndex: 'severity',
        key: 'severity',
        width: 90,
        filters: [
            { text: '严重', value: 'critical' },
            { text: '重要', value: 'major' },
            { text: '轻微', value: 'minor' }
        ]
    },
    {
        title: '类型',
        dataIndex: 'rule_type',
        key: 'rule_type',
        width: 80,
        filters: [
            { text: '客观规则', value: 'objective' },
            { text: '主观规则', value: 'subjective' },
            { text: '混合规则', value: 'hybrid' }
        ]
    },
    {
        title: '最大扣分',
        dataIndex: 'max_score',
        key: 'max_score',
        width: 85,
        sorter: true
    },
    {
        title: '权重',
        dataIndex: 'weight',
        key: 'weight',
        width: 60,
        sorter: true
    },
    {
        title: '状态',
        dataIndex: 'is_active',
        key: 'is_active',
        width: 60
    },
    {
        title: '操作',
        key: 'actions',
        width: 200,
        fixed: 'right'
    }
];
// 行选择配置
const rowSelection = {
    selectedRowKeys: selectedRowKeys,
    onChange: (keys: any) => {
        selectedRowKeys.value = keys;
    }
};
// 计算属性
const statistics = (0, vue_1.computed)(() => {
    const total = rules.value.length;
    const active = rules.value.filter(r => r.is_active).length;
    const critical = rules.value.filter(r => r.severity === 'critical').length;
    const categories = new Set(rules.value.map(r => r.category)).size;
    return { total, active, critical, categories };
});
const filteredRules = (0, vue_1.computed)(() => {
    let filtered = [...rules.value];
    // 搜索过滤
    if (searchText.value) {
        const search = searchText.value.toLowerCase();
        filtered = filtered.filter(rule => rule.name.toLowerCase().includes(search) ||
            rule.description.toLowerCase().includes(search) ||
            rule.rule_code.toLowerCase().includes(search));
    }
    // 分类过滤
    if (filterCategory.value) {
        filtered = filtered.filter(rule => rule.category === filterCategory.value);
    }
    // 严重程度过滤
    if (filterSeverity.value) {
        filtered = filtered.filter(rule => rule.severity === filterSeverity.value);
    }
    // 类型过滤
    if (filterType.value) {
        filtered = filtered.filter(rule => rule.rule_type === filterType.value);
    }
    // 状态过滤
    if (filterStatus.value) {
        const isActive = filterStatus.value === 'active';
        filtered = filtered.filter(rule => rule.is_active === isActive);
    }
    return filtered;
});
// 工具函数
const getCategoryColor = (category) => {
    return RULES_CONFIG.categories[category]?.color || 'default';
};
const getCategoryLabel = (category) => {
    return RULES_CONFIG.categories[category]?.label || category;
};
const getSeverityColor = (severity) => {
    return RULES_CONFIG.severities[severity]?.color || 'default';
};
const getSeverityLabel = (severity) => {
    return RULES_CONFIG.severities[severity]?.label || severity;
};
const getTypeColor = (type) => {
    return RULES_CONFIG.types[type]?.color || 'default';
};
const getTypeLabel = (type) => {
    return RULES_CONFIG.types[type]?.label || type;
};
// 模拟数据
const mockRules = [
    {
        id: '1',
        rule_code: '1.1.1',
        name: '入院记录完整性检查',
        description: '检查入院记录是否包含必要的基本信息，包括患者基本信息、主诉、现病史、既往史等',
        category: 'completeness',
        rule_type: 'objective',
        severity: 'critical',
        max_score: 0,
        weight: 2.0,
        is_active: true,
        check_logic: {
            required_fields: ['patient_name', 'admission_date', 'chief_complaint', 'present_illness']
        },
        prompt_template: '请检查入院记录是否包含以下必要信息：患者姓名、入院日期、主诉、现病史',
        version: '1.0',
        created_at: '2024-01-15T10:00:00Z',
        updated_at: '2024-01-15T10:00:00Z'
    },
    {
        id: '2',
        rule_code: '1.2.1',
        name: '诊断一致性检查',
        description: '检查入院诊断与出院诊断的一致性，确保诊断变更有合理依据',
        category: 'consistency',
        rule_type: 'hybrid',
        severity: 'major',
        max_score: 5,
        weight: 1.5,
        is_active: true,
        check_logic: {
            compare_fields: ['admission_diagnosis', 'discharge_diagnosis'],
            tolerance: 0.8
        },
        prompt_template: '请分析入院诊断与出院诊断的一致性，如有变更请说明理由',
        version: '1.0',
        created_at: '2024-01-15T10:30:00Z',
        updated_at: '2024-01-15T10:30:00Z'
    },
    {
        id: '3',
        rule_code: '2.1.1',
        name: '用药合理性检查',
        description: '检查药物使用是否符合适应症，剂量是否合理，是否存在禁忌症',
        category: 'rationality',
        rule_type: 'subjective',
        severity: 'critical',
        max_score: 0,
        weight: 3.0,
        is_active: true,
        check_logic: {
            drug_interaction_check: true,
            dosage_check: true,
            contraindication_check: true
        },
        prompt_template: '请评估患者的用药方案是否合理，包括适应症、剂量、禁忌症等方面',
        version: '1.0',
        created_at: '2024-01-15T11:00:00Z',
        updated_at: '2024-01-15T11:00:00Z'
    },
    {
        id: '4',
        rule_code: '3.1.1',
        name: '手术记录及时性检查',
        description: '检查手术记录是否在规定时间内完成，确保医疗文书的及时性',
        category: 'timeliness',
        rule_type: 'objective',
        severity: 'major',
        max_score: 3,
        weight: 1.0,
        is_active: true,
        check_logic: {
            time_limit: 24,
            time_unit: 'hours'
        },
        prompt_template: '请检查手术记录是否在术后24小时内完成',
        version: '1.0',
        created_at: '2024-01-15T11:30:00Z',
        updated_at: '2024-01-15T11:30:00Z'
    },
    {
        id: '5',
        rule_code: '1.1.2',
        name: '病程记录完整性检查',
        description: '检查病程记录是否按规定频次记录，内容是否完整',
        category: 'completeness',
        rule_type: 'objective',
        severity: 'minor',
        max_score: 2,
        weight: 1.0,
        is_active: false,
        check_logic: {
            frequency_check: true,
            content_completeness: ['symptoms', 'treatment', 'response']
        },
        prompt_template: '请检查病程记录的频次和内容完整性',
        version: '1.0',
        created_at: '2024-01-15T12:00:00Z',
        updated_at: '2024-01-15T12:00:00Z'
    },
    {
        id: '6',
        rule_code: '2.2.1',
        name: '检查结果合理性分析',
        description: '分析检查结果是否与临床表现相符，是否需要进一步检查',
        category: 'rationality',
        rule_type: 'hybrid',
        severity: 'major',
        max_score: 4,
        weight: 1.8,
        is_active: true,
        check_logic: {
            clinical_correlation: true,
            reference_range_check: true
        },
        prompt_template: '请分析检查结果与临床表现的相关性，评估是否需要进一步检查',
        version: '1.0',
        created_at: '2024-01-15T12:30:00Z',
        updated_at: '2024-01-15T12:30:00Z'
    }
];
// 模拟服务
const mockRulesService = {
    getAllRules: async () => {
        await new Promise(resolve => setTimeout(resolve, 500)); // 模拟网络延迟
        return mockRules;
    },
    createRule: async (ruleData: any) => {
        await new Promise(resolve => setTimeout(resolve, 300));
        const newRule = {
            ...ruleData,
            id: Date.now().toString(),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
        };
        mockRules.push(newRule);
        return newRule;
    },
    updateRule: async (id: any,  ruleData: any) => {
        await new Promise(resolve => setTimeout(resolve, 300));
        const index = mockRules.findIndex(r => r.id === id);
        if (index !== -1) {
            mockRules[index] = { ...mockRules[index], ...ruleData, updated_at: new Date().toISOString() };
        }
        return mockRules[index];
    },
    deleteRule: async (id: any) => {
        await new Promise(resolve => setTimeout(resolve, 300));
        const index = mockRules.findIndex(r => r.id === id);
        if (index !== -1) {
            mockRules.splice(index, 1);
        }
    },
    toggleRuleStatus: async (id: any,  isActive: any) => {
        await new Promise(resolve => setTimeout(resolve, 200));
        const rule = mockRules.find(r => r.id === id);
        if (rule) {
            rule.is_active = isActive;
            rule.updated_at = new Date().toISOString();
        }
    },
    batchUpdateRuleStatus: async (ids: any,  isActive: any) => {
        await new Promise(resolve => setTimeout(resolve, 500));
        ids.forEach(id => {
            const rule = mockRules.find(r => r.id === id);
            if (rule) {
                rule.is_active = isActive;
                rule.updated_at = new Date().toISOString();
            }
        });
    },
    deleteRules: async (ids: any) => {
        await new Promise(resolve => setTimeout(resolve, 500));
        ids.forEach(id => {
            const index = mockRules.findIndex(r => r.id === id);
            if (index !== -1) {
                mockRules.splice(index, 1);
            }
        });
    },
    exportRules: async (format: any) => {
        await new Promise(resolve => setTimeout(resolve, 300));
        return JSON.stringify(mockRules, null, 2);
    }
};
// 模拟验证器
const mockRulesValidator = {
    validateRule: (ruleData: any) => {
        const errors = [];
        const warnings = [];
        if (!ruleData.rule_code)
            errors.push('规则编码不能为空');
        if (!ruleData.name)
            errors.push('规则名称不能为空');
        if (!ruleData.description)
            errors.push('规则描述不能为空');
        if (ruleData.max_score < 0 || ruleData.max_score > 100) {
            errors.push('最大扣分必须在0-100之间');
        }
        if (ruleData.weight < 0.1 || ruleData.weight > 5.0) {
            warnings.push('权重建议在0.1-5.0之间');
        }
        return {
            isValid: errors.length === 0,
            errors,
            warnings
        };
    }
};
// 数据加载
const loadRules = async () => {
    try {
        loading.value = true;
        const data = await mockRulesService.getAllRules();
        rules.value = data;
        pagination.total = data.length;
    }
    catch (error) {
        console.error('加载规则失败:', error);
        ant_design_vue_1.message.error('加载规则失败');
    }
    finally {
        loading.value = false;
    }
};
// 事件处理
const refreshRules = () => {
    loadRules();
};
const handleSearch = () => {
    // 搜索逻辑已在计算属性中处理
};
const handleFilter = () => {
    // 过滤逻辑已在计算属性中处理
};
const resetFilters = () => {
    searchText.value = '';
    filterCategory.value = undefined;
    filterSeverity.value = undefined;
    filterType.value = undefined;
    filterStatus.value = undefined;
};
const handleTableChange = (pag, filters: any,  sorter: any) => {
    if (pag) {
        pagination.current = pag.current || 1;
        pagination.pageSize = pag.pageSize || 10;
    }
};
// 规则操作
const showCreateModal = () => {
    isEditing.value = false;
    modalTitle.value = '新增规则';
    resetFormData();
    modalVisible.value = true;
};
const editRule = (rule) => {
    isEditing.value = true;
    editingId.value = rule.id;
    modalTitle.value = '编辑规则';
    // 填充表单数据
    Object.assign(formData, {
        rule_code: rule.rule_code,
        name: rule.name,
        description: rule.description,
        category: rule.category,
        rule_type: rule.rule_type,
        severity: rule.severity,
        max_score: rule.max_score,
        weight: rule.weight,
        is_active: rule.is_active,
        check_logic: rule.check_logic,
        prompt_template: rule.prompt_template || '',
        version: rule.version
    });
    checkLogicText.value = JSON.stringify(rule.check_logic, null, 2);
    modalVisible.value = true;
};
const viewRule = (rule) => {
    // 可以打开详情页面或模态框
    ant_design_vue_1.message.info('查看规则详情功能待实现');
};
const testRule = (rule) => {
    // 可以打开测试页面
    ant_design_vue_1.message.info('规则测试功能待实现');
};
const deleteRule = async (rule) => {
    try {
        await mockRulesService.deleteRule(rule.id);
        ant_design_vue_1.message.success('删除成功');
        loadRules();
    }
    catch (error) {
        console.error('删除规则失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '删除规则失败');
    }
};
const toggleRuleStatus = async (rule, checked) => {
    try {
        rule.updating = true;
        await mockRulesService.toggleRuleStatus(rule.id, checked);
        rule.is_active = checked;
        ant_design_vue_1.message.success(checked ? '规则已激活' : '规则已停用');
    }
    catch (error) {
        console.error('更新规则状态失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '更新规则状态失败');
        rule.is_active = !checked; // 回滚状态
    }
    finally {
        rule.updating = false;
    }
};
// 批量操作
const handleBatchAction = async ({ key }) => {
    if (selectedRowKeys.value.length === 0) {
        ant_design_vue_1.message.warning('请先选择要操作的规则');
        return;
    }
    try {
        loading.value = true;
        switch (key) {
            case 'activate':
                await mockRulesService.batchUpdateRuleStatus(selectedRowKeys.value, true);
                ant_design_vue_1.message.success('批量激活成功');
                break;
            case 'deactivate':
                await mockRulesService.batchUpdateRuleStatus(selectedRowKeys.value, false);
                ant_design_vue_1.message.success('批量停用成功');
                break;
            case 'delete':
                await mockRulesService.deleteRules(selectedRowKeys.value);
                ant_design_vue_1.message.success('批量删除成功');
                break;
        }
        selectedRowKeys.value = [];
        loadRules();
    }
    catch (error) {
        console.error('批量操作失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '批量操作失败');
    }
    finally {
        loading.value = false;
    }
};
// 模态框操作
const handleModalOk = async () => {
    try {
        await formRef.value.validate();
        modalLoading.value = true;
        // 解析检查逻辑JSON
        let checkLogic = {};
        if (checkLogicText.value.trim()) {
            try {
                checkLogic = JSON.parse(checkLogicText.value);
            }
            catch (e) {
                ant_design_vue_1.message.error('检查逻辑JSON格式不正确');
                return;
            }
        }
        const ruleData = {
            ...formData,
            check_logic: checkLogic
        };
        // 验证规则数据
        const validation = mockRulesValidator.validateRule(ruleData);
        if (!validation.isValid) {
            ant_design_vue_1.message.error(`规则验证失败: ${validation.errors.join(', ')}`);
            return;
        }
        if (validation.warnings.length > 0) {
            console.warn('规则验证警告:', validation.warnings);
        }
        if (isEditing.value && editingId.value) {
            // 更新规则
            await mockRulesService.updateRule(editingId.value, ruleData);
            ant_design_vue_1.message.success('更新规则成功');
        }
        else {
            // 创建规则
            await mockRulesService.createRule(ruleData);
            ant_design_vue_1.message.success('创建规则成功');
        }
        modalVisible.value = false;
        loadRules();
    }
    catch (error) {
        console.error('保存规则失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '保存规则失败');
    }
    finally {
        modalLoading.value = false;
    }
};
const handleModalCancel = () => {
    modalVisible.value = false;
    resetFormData();
};
const resetFormData = () => {
    Object.assign(formData, {
        rule_code: '',
        name: '',
        description: '',
        category: 'completeness',
        rule_type: 'objective',
        severity: 'minor',
        max_score: 0,
        weight: 1.0,
        is_active: true,
        check_logic: {},
        prompt_template: '',
        version: '1.0'
    });
    checkLogicText.value = '';
    formRef.value?.resetFields();
};
// 导入导出
const importRules = () => {
    ant_design_vue_1.message.info('规则导入功能待实现');
};
const exportRules = async () => {
    try {
        const exportData = await mockRulesService.exportRules('json');
        const blob = new Blob([exportData], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `qc-rules-${new Date().toISOString().split('T')[0]}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        ant_design_vue_1.message.success('规则导出成功');
    }
    catch (error) {
        console.error('导出规则失败:', error);
        ant_design_vue_1.message.error('导出规则失败');
    }
};
// 生命周期
(0, vue_1.onMounted)(() => {
    loadRules();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-table-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-thead']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-statistic-content-value']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-search']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-switch']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-switch-handle']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-switch-handle']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-space-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-space']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-form-item-control-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-form-item-control-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-form-item-control-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-pagination']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-pagination-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-pagination-item-link']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-actions" },
});
const __VLS_0 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (__VLS_ctx.refreshRules)
};
__VLS_7.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_7.slots;
    const __VLS_12 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
}
var __VLS_7;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    type: "primary",
    icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    type: "primary",
    icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.showCreateModal)
};
__VLS_19.slots.default;
var __VLS_19;
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ImportOutlined)),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ImportOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.importRules)
};
__VLS_27.slots.default;
var __VLS_27;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stats-grid" },
});
const __VLS_32 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ class: "stat-card" },
}));
const __VLS_34 = __VLS_33({
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    title: "总规则数",
    value: (__VLS_ctx.statistics.total),
    valueStyle: ({ color: '#1890ff' }),
}));
const __VLS_38 = __VLS_37({
    title: "总规则数",
    value: (__VLS_ctx.statistics.total),
    valueStyle: ({ color: '#1890ff' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_39.slots;
    const __VLS_40 = {}.FileTextOutlined;
    /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
    const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
var __VLS_39;
var __VLS_35;
const __VLS_44 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ class: "stat-card" },
}));
const __VLS_46 = __VLS_45({
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    title: "激活规则",
    value: (__VLS_ctx.statistics.active),
    valueStyle: ({ color: '#52c41a' }),
}));
const __VLS_50 = __VLS_49({
    title: "激活规则",
    value: (__VLS_ctx.statistics.active),
    valueStyle: ({ color: '#52c41a' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_51.slots;
    const __VLS_52 = {}.CheckCircleOutlined;
    /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
    const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
}
var __VLS_51;
var __VLS_47;
const __VLS_56 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ class: "stat-card" },
}));
const __VLS_58 = __VLS_57({
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    title: "严重规则",
    value: (__VLS_ctx.statistics.critical),
    valueStyle: ({ color: '#ff4d4f' }),
}));
const __VLS_62 = __VLS_61({
    title: "严重规则",
    value: (__VLS_ctx.statistics.critical),
    valueStyle: ({ color: '#ff4d4f' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_63.slots;
    const __VLS_64 = {}.ExclamationCircleOutlined;
    /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({}));
    const __VLS_66 = __VLS_65({}, ...__VLS_functionalComponentArgsRest(__VLS_65));
}
var __VLS_63;
var __VLS_59;
const __VLS_68 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    ...{ class: "stat-card" },
}));
const __VLS_70 = __VLS_69({
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    title: "规则分类",
    value: (__VLS_ctx.statistics.categories),
    valueStyle: ({ color: '#722ed1' }),
}));
const __VLS_74 = __VLS_73({
    title: "规则分类",
    value: (__VLS_ctx.statistics.categories),
    valueStyle: ({ color: '#722ed1' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_75.slots;
    const __VLS_76 = {}.TagsOutlined;
    /** @type {[typeof __VLS_components.TagsOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({}));
    const __VLS_78 = __VLS_77({}, ...__VLS_functionalComponentArgsRest(__VLS_77));
}
var __VLS_75;
var __VLS_71;
const __VLS_80 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    ...{ class: "filter-card" },
}));
const __VLS_82 = __VLS_81({
    ...{ class: "filter-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
const __VLS_84 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    gutter: (16),
}));
const __VLS_86 = __VLS_85({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
const __VLS_88 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    span: (6),
}));
const __VLS_90 = __VLS_89({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
const __VLS_92 = {}.AInputSearch;
/** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchText),
    placeholder: "搜索规则名称或描述",
    allowClear: true,
}));
const __VLS_94 = __VLS_93({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchText),
    placeholder: "搜索规则名称或描述",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
let __VLS_96;
let __VLS_97;
let __VLS_98;
const __VLS_99 = {
    onSearch: (__VLS_ctx.handleSearch)
};
var __VLS_95;
var __VLS_91;
const __VLS_100 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    span: (4),
}));
const __VLS_102 = __VLS_101({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
__VLS_103.slots.default;
const __VLS_104 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterCategory),
    placeholder: "选择分类",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_106 = __VLS_105({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterCategory),
    placeholder: "选择分类",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
let __VLS_108;
let __VLS_109;
let __VLS_110;
const __VLS_111 = {
    onChange: (__VLS_ctx.handleFilter)
};
__VLS_107.slots.default;
const __VLS_112 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    value: "completeness",
}));
const __VLS_114 = __VLS_113({
    value: "completeness",
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
var __VLS_115;
const __VLS_116 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    value: "consistency",
}));
const __VLS_118 = __VLS_117({
    value: "consistency",
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
var __VLS_119;
const __VLS_120 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
    value: "rationality",
}));
const __VLS_122 = __VLS_121({
    value: "rationality",
}, ...__VLS_functionalComponentArgsRest(__VLS_121));
__VLS_123.slots.default;
var __VLS_123;
const __VLS_124 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    value: "timeliness",
}));
const __VLS_126 = __VLS_125({
    value: "timeliness",
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
var __VLS_127;
var __VLS_107;
var __VLS_103;
const __VLS_128 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    span: (4),
}));
const __VLS_130 = __VLS_129({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
const __VLS_132 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterSeverity),
    placeholder: "选择严重程度",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_134 = __VLS_133({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterSeverity),
    placeholder: "选择严重程度",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_133));
let __VLS_136;
let __VLS_137;
let __VLS_138;
const __VLS_139 = {
    onChange: (__VLS_ctx.handleFilter)
};
__VLS_135.slots.default;
const __VLS_140 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    value: "critical",
}));
const __VLS_142 = __VLS_141({
    value: "critical",
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
__VLS_143.slots.default;
var __VLS_143;
const __VLS_144 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
    value: "major",
}));
const __VLS_146 = __VLS_145({
    value: "major",
}, ...__VLS_functionalComponentArgsRest(__VLS_145));
__VLS_147.slots.default;
var __VLS_147;
const __VLS_148 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    value: "minor",
}));
const __VLS_150 = __VLS_149({
    value: "minor",
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
__VLS_151.slots.default;
var __VLS_151;
var __VLS_135;
var __VLS_131;
const __VLS_152 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
    span: (4),
}));
const __VLS_154 = __VLS_153({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_153));
__VLS_155.slots.default;
const __VLS_156 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterType),
    placeholder: "选择规则类型",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_158 = __VLS_157({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterType),
    placeholder: "选择规则类型",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
let __VLS_160;
let __VLS_161;
let __VLS_162;
const __VLS_163 = {
    onChange: (__VLS_ctx.handleFilter)
};
__VLS_159.slots.default;
const __VLS_164 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    value: "objective",
}));
const __VLS_166 = __VLS_165({
    value: "objective",
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
__VLS_167.slots.default;
var __VLS_167;
const __VLS_168 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    value: "subjective",
}));
const __VLS_170 = __VLS_169({
    value: "subjective",
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
var __VLS_171;
const __VLS_172 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    value: "hybrid",
}));
const __VLS_174 = __VLS_173({
    value: "hybrid",
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
__VLS_175.slots.default;
var __VLS_175;
var __VLS_159;
var __VLS_155;
const __VLS_176 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
    span: (4),
}));
const __VLS_178 = __VLS_177({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_177));
__VLS_179.slots.default;
const __VLS_180 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterStatus),
    placeholder: "选择状态",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_182 = __VLS_181({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filterStatus),
    placeholder: "选择状态",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_181));
let __VLS_184;
let __VLS_185;
let __VLS_186;
const __VLS_187 = {
    onChange: (__VLS_ctx.handleFilter)
};
__VLS_183.slots.default;
const __VLS_188 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
    value: "active",
}));
const __VLS_190 = __VLS_189({
    value: "active",
}, ...__VLS_functionalComponentArgsRest(__VLS_189));
__VLS_191.slots.default;
var __VLS_191;
const __VLS_192 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
    value: "inactive",
}));
const __VLS_194 = __VLS_193({
    value: "inactive",
}, ...__VLS_functionalComponentArgsRest(__VLS_193));
__VLS_195.slots.default;
var __VLS_195;
var __VLS_183;
var __VLS_179;
const __VLS_196 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    span: (2),
}));
const __VLS_198 = __VLS_197({
    span: (2),
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
__VLS_199.slots.default;
const __VLS_200 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ClearOutlined)),
}));
const __VLS_202 = __VLS_201({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ClearOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_201));
let __VLS_204;
let __VLS_205;
let __VLS_206;
const __VLS_207 = {
    onClick: (__VLS_ctx.resetFilters)
};
__VLS_203.slots.default;
var __VLS_203;
var __VLS_199;
var __VLS_87;
var __VLS_83;
const __VLS_208 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
    title: "规则列表",
    ...{ class: "rules-table-card" },
}));
const __VLS_210 = __VLS_209({
    title: "规则列表",
    ...{ class: "rules-table-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_209));
__VLS_211.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_211.slots;
    const __VLS_212 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({}));
    const __VLS_214 = __VLS_213({}, ...__VLS_functionalComponentArgsRest(__VLS_213));
    __VLS_215.slots.default;
    const __VLS_216 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
        ...{ 'onClick': {} },
        size: "small",
        icon: (__VLS_ctx.h(__VLS_ctx.ExportOutlined)),
    }));
    const __VLS_218 = __VLS_217({
        ...{ 'onClick': {} },
        size: "small",
        icon: (__VLS_ctx.h(__VLS_ctx.ExportOutlined)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_217));
    let __VLS_220;
    let __VLS_221;
    let __VLS_222;
    const __VLS_223 = {
        onClick: (__VLS_ctx.exportRules)
    };
    __VLS_219.slots.default;
    var __VLS_219;
    const __VLS_224 = {}.ADropdown;
    /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
    // @ts-ignore
    const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({}));
    const __VLS_226 = __VLS_225({}, ...__VLS_functionalComponentArgsRest(__VLS_225));
    __VLS_227.slots.default;
    {
        const { overlay: __VLS_thisSlot } = __VLS_227.slots;
        const __VLS_228 = {}.AMenu;
        /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
        // @ts-ignore
        const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
            ...{ 'onClick': {} },
        }));
        const __VLS_230 = __VLS_229({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_229));
        let __VLS_232;
        let __VLS_233;
        let __VLS_234;
        const __VLS_235 = {
            onClick: (__VLS_ctx.handleBatchAction)
        };
        __VLS_231.slots.default;
        const __VLS_236 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
            key: "activate",
        }));
        const __VLS_238 = __VLS_237({
            key: "activate",
        }, ...__VLS_functionalComponentArgsRest(__VLS_237));
        __VLS_239.slots.default;
        var __VLS_239;
        const __VLS_240 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
            key: "deactivate",
        }));
        const __VLS_242 = __VLS_241({
            key: "deactivate",
        }, ...__VLS_functionalComponentArgsRest(__VLS_241));
        __VLS_243.slots.default;
        var __VLS_243;
        const __VLS_244 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
            key: "delete",
        }));
        const __VLS_246 = __VLS_245({
            key: "delete",
        }, ...__VLS_functionalComponentArgsRest(__VLS_245));
        __VLS_247.slots.default;
        var __VLS_247;
        var __VLS_231;
    }
    const __VLS_248 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
        size: "small",
    }));
    const __VLS_250 = __VLS_249({
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_249));
    __VLS_251.slots.default;
    const __VLS_252 = {}.DownOutlined;
    /** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({}));
    const __VLS_254 = __VLS_253({}, ...__VLS_functionalComponentArgsRest(__VLS_253));
    var __VLS_251;
    var __VLS_227;
    var __VLS_215;
}
const __VLS_256 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.filteredRules),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    size: "middle",
}));
const __VLS_258 = __VLS_257({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.filteredRules),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_257));
let __VLS_260;
let __VLS_261;
let __VLS_262;
const __VLS_263 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_259.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_259.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'rule_code') {
        const __VLS_264 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
            color: "blue",
        }));
        const __VLS_266 = __VLS_265({
            color: "blue",
        }, ...__VLS_functionalComponentArgsRest(__VLS_265));
        __VLS_267.slots.default;
        (record.rule_code);
        var __VLS_267;
    }
    else if (column.key === 'source') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "rule-source" },
        });
        (record.name);
    }
    else if (column.key === 'name') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "rule-name" },
        });
        (record.description);
    }
    else if (column.key === 'category') {
        const __VLS_268 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
            color: (__VLS_ctx.getCategoryColor(record.category)),
        }));
        const __VLS_270 = __VLS_269({
            color: (__VLS_ctx.getCategoryColor(record.category)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_269));
        __VLS_271.slots.default;
        (__VLS_ctx.getCategoryLabel(record.category));
        var __VLS_271;
    }
    else if (column.key === 'severity') {
        const __VLS_272 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
            color: (__VLS_ctx.getSeverityColor(record.severity)),
        }));
        const __VLS_274 = __VLS_273({
            color: (__VLS_ctx.getSeverityColor(record.severity)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_273));
        __VLS_275.slots.default;
        (__VLS_ctx.getSeverityLabel(record.severity));
        var __VLS_275;
    }
    else if (column.key === 'rule_type') {
        const __VLS_276 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({
            color: (__VLS_ctx.getTypeColor(record.rule_type)),
        }));
        const __VLS_278 = __VLS_277({
            color: (__VLS_ctx.getTypeColor(record.rule_type)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_277));
        __VLS_279.slots.default;
        (__VLS_ctx.getTypeLabel(record.rule_type));
        var __VLS_279;
    }
    else if (column.key === 'is_active') {
        const __VLS_280 = {}.ASwitch;
        /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
        // @ts-ignore
        const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
            ...{ 'onChange': {} },
            checked: (record.is_active),
            loading: (record.updating),
        }));
        const __VLS_282 = __VLS_281({
            ...{ 'onChange': {} },
            checked: (record.is_active),
            loading: (record.updating),
        }, ...__VLS_functionalComponentArgsRest(__VLS_281));
        let __VLS_284;
        let __VLS_285;
        let __VLS_286;
        const __VLS_287 = {
            onChange: ((checked) => __VLS_ctx.toggleRuleStatus(record, checked))
        };
        var __VLS_283;
    }
    else if (column.key === 'max_score') {
        if (record.max_score === 0) {
            const __VLS_288 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
                color: "red",
            }));
            const __VLS_290 = __VLS_289({
                color: "red",
            }, ...__VLS_functionalComponentArgsRest(__VLS_289));
            __VLS_291.slots.default;
            var __VLS_291;
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (record.max_score);
        }
    }
    else if (column.key === 'actions') {
        const __VLS_292 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({}));
        const __VLS_294 = __VLS_293({}, ...__VLS_functionalComponentArgsRest(__VLS_293));
        __VLS_295.slots.default;
        const __VLS_296 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_298 = __VLS_297({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_297));
        let __VLS_300;
        let __VLS_301;
        let __VLS_302;
        const __VLS_303 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'rule_code'))
                    return;
                if (!!(column.key === 'source'))
                    return;
                if (!!(column.key === 'name'))
                    return;
                if (!!(column.key === 'category'))
                    return;
                if (!!(column.key === 'severity'))
                    return;
                if (!!(column.key === 'rule_type'))
                    return;
                if (!!(column.key === 'is_active'))
                    return;
                if (!!(column.key === 'max_score'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.viewRule(record);
            }
        };
        __VLS_299.slots.default;
        var __VLS_299;
        const __VLS_304 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_306 = __VLS_305({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_305));
        let __VLS_308;
        let __VLS_309;
        let __VLS_310;
        const __VLS_311 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'rule_code'))
                    return;
                if (!!(column.key === 'source'))
                    return;
                if (!!(column.key === 'name'))
                    return;
                if (!!(column.key === 'category'))
                    return;
                if (!!(column.key === 'severity'))
                    return;
                if (!!(column.key === 'rule_type'))
                    return;
                if (!!(column.key === 'is_active'))
                    return;
                if (!!(column.key === 'max_score'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.editRule(record);
            }
        };
        __VLS_307.slots.default;
        var __VLS_307;
        const __VLS_312 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_313 = __VLS_asFunctionalComponent(__VLS_312, new __VLS_312({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_314 = __VLS_313({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_313));
        let __VLS_316;
        let __VLS_317;
        let __VLS_318;
        const __VLS_319 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'rule_code'))
                    return;
                if (!!(column.key === 'source'))
                    return;
                if (!!(column.key === 'name'))
                    return;
                if (!!(column.key === 'category'))
                    return;
                if (!!(column.key === 'severity'))
                    return;
                if (!!(column.key === 'rule_type'))
                    return;
                if (!!(column.key === 'is_active'))
                    return;
                if (!!(column.key === 'max_score'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.testRule(record);
            }
        };
        __VLS_315.slots.default;
        var __VLS_315;
        const __VLS_320 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
            ...{ 'onConfirm': {} },
            title: "确定要删除这条规则吗？",
        }));
        const __VLS_322 = __VLS_321({
            ...{ 'onConfirm': {} },
            title: "确定要删除这条规则吗？",
        }, ...__VLS_functionalComponentArgsRest(__VLS_321));
        let __VLS_324;
        let __VLS_325;
        let __VLS_326;
        const __VLS_327 = {
            onConfirm: (...[$event]) => {
                if (!!(column.key === 'rule_code'))
                    return;
                if (!!(column.key === 'source'))
                    return;
                if (!!(column.key === 'name'))
                    return;
                if (!!(column.key === 'category'))
                    return;
                if (!!(column.key === 'severity'))
                    return;
                if (!!(column.key === 'rule_type'))
                    return;
                if (!!(column.key === 'is_active'))
                    return;
                if (!!(column.key === 'max_score'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.deleteRule(record);
            }
        };
        __VLS_323.slots.default;
        const __VLS_328 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
            type: "link",
            size: "small",
            danger: true,
        }));
        const __VLS_330 = __VLS_329({
            type: "link",
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_329));
        __VLS_331.slots.default;
        var __VLS_331;
        var __VLS_323;
        var __VLS_295;
    }
}
var __VLS_259;
var __VLS_211;
const __VLS_332 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.modalVisible),
    title: (__VLS_ctx.modalTitle),
    width: "800px",
    confirmLoading: (__VLS_ctx.modalLoading),
}));
const __VLS_334 = __VLS_333({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.modalVisible),
    title: (__VLS_ctx.modalTitle),
    width: "800px",
    confirmLoading: (__VLS_ctx.modalLoading),
}, ...__VLS_functionalComponentArgsRest(__VLS_333));
let __VLS_336;
let __VLS_337;
let __VLS_338;
const __VLS_339 = {
    onOk: (__VLS_ctx.handleModalOk)
};
const __VLS_340 = {
    onCancel: (__VLS_ctx.handleModalCancel)
};
__VLS_335.slots.default;
const __VLS_341 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_342 = __VLS_asFunctionalComponent(__VLS_341, new __VLS_341({
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
}));
const __VLS_343 = __VLS_342({
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_342));
/** @type {typeof __VLS_ctx.formRef} */ ;
var __VLS_345 = {};
__VLS_344.slots.default;
const __VLS_347 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_348 = __VLS_asFunctionalComponent(__VLS_347, new __VLS_347({
    gutter: (16),
}));
const __VLS_349 = __VLS_348({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_348));
__VLS_350.slots.default;
const __VLS_351 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_352 = __VLS_asFunctionalComponent(__VLS_351, new __VLS_351({
    span: (12),
}));
const __VLS_353 = __VLS_352({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_352));
__VLS_354.slots.default;
const __VLS_355 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_356 = __VLS_asFunctionalComponent(__VLS_355, new __VLS_355({
    label: "规则编码",
    name: "rule_code",
}));
const __VLS_357 = __VLS_356({
    label: "规则编码",
    name: "rule_code",
}, ...__VLS_functionalComponentArgsRest(__VLS_356));
__VLS_358.slots.default;
const __VLS_359 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_360 = __VLS_asFunctionalComponent(__VLS_359, new __VLS_359({
    value: (__VLS_ctx.formData.rule_code),
    placeholder: "如: 1.1.1",
}));
const __VLS_361 = __VLS_360({
    value: (__VLS_ctx.formData.rule_code),
    placeholder: "如: 1.1.1",
}, ...__VLS_functionalComponentArgsRest(__VLS_360));
var __VLS_358;
var __VLS_354;
const __VLS_363 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_364 = __VLS_asFunctionalComponent(__VLS_363, new __VLS_363({
    span: (12),
}));
const __VLS_365 = __VLS_364({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_364));
__VLS_366.slots.default;
const __VLS_367 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_368 = __VLS_asFunctionalComponent(__VLS_367, new __VLS_367({
    label: "规则名称",
    name: "name",
}));
const __VLS_369 = __VLS_368({
    label: "规则名称",
    name: "name",
}, ...__VLS_functionalComponentArgsRest(__VLS_368));
__VLS_370.slots.default;
const __VLS_371 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_372 = __VLS_asFunctionalComponent(__VLS_371, new __VLS_371({
    value: (__VLS_ctx.formData.name),
    placeholder: "输入规则名称",
}));
const __VLS_373 = __VLS_372({
    value: (__VLS_ctx.formData.name),
    placeholder: "输入规则名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_372));
var __VLS_370;
var __VLS_366;
var __VLS_350;
const __VLS_375 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_376 = __VLS_asFunctionalComponent(__VLS_375, new __VLS_375({
    label: "规则描述",
    name: "description",
}));
const __VLS_377 = __VLS_376({
    label: "规则描述",
    name: "description",
}, ...__VLS_functionalComponentArgsRest(__VLS_376));
__VLS_378.slots.default;
const __VLS_379 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_380 = __VLS_asFunctionalComponent(__VLS_379, new __VLS_379({
    value: (__VLS_ctx.formData.description),
    placeholder: "详细描述规则内容和检查要点",
    rows: (3),
}));
const __VLS_381 = __VLS_380({
    value: (__VLS_ctx.formData.description),
    placeholder: "详细描述规则内容和检查要点",
    rows: (3),
}, ...__VLS_functionalComponentArgsRest(__VLS_380));
var __VLS_378;
const __VLS_383 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_384 = __VLS_asFunctionalComponent(__VLS_383, new __VLS_383({
    gutter: (16),
}));
const __VLS_385 = __VLS_384({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_384));
__VLS_386.slots.default;
const __VLS_387 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_388 = __VLS_asFunctionalComponent(__VLS_387, new __VLS_387({
    span: (8),
}));
const __VLS_389 = __VLS_388({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_388));
__VLS_390.slots.default;
const __VLS_391 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_392 = __VLS_asFunctionalComponent(__VLS_391, new __VLS_391({
    label: "分类",
    name: "category",
}));
const __VLS_393 = __VLS_392({
    label: "分类",
    name: "category",
}, ...__VLS_functionalComponentArgsRest(__VLS_392));
__VLS_394.slots.default;
const __VLS_395 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_396 = __VLS_asFunctionalComponent(__VLS_395, new __VLS_395({
    value: (__VLS_ctx.formData.category),
    placeholder: "选择分类",
}));
const __VLS_397 = __VLS_396({
    value: (__VLS_ctx.formData.category),
    placeholder: "选择分类",
}, ...__VLS_functionalComponentArgsRest(__VLS_396));
__VLS_398.slots.default;
const __VLS_399 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_400 = __VLS_asFunctionalComponent(__VLS_399, new __VLS_399({
    value: "completeness",
}));
const __VLS_401 = __VLS_400({
    value: "completeness",
}, ...__VLS_functionalComponentArgsRest(__VLS_400));
__VLS_402.slots.default;
var __VLS_402;
const __VLS_403 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_404 = __VLS_asFunctionalComponent(__VLS_403, new __VLS_403({
    value: "consistency",
}));
const __VLS_405 = __VLS_404({
    value: "consistency",
}, ...__VLS_functionalComponentArgsRest(__VLS_404));
__VLS_406.slots.default;
var __VLS_406;
const __VLS_407 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_408 = __VLS_asFunctionalComponent(__VLS_407, new __VLS_407({
    value: "rationality",
}));
const __VLS_409 = __VLS_408({
    value: "rationality",
}, ...__VLS_functionalComponentArgsRest(__VLS_408));
__VLS_410.slots.default;
var __VLS_410;
const __VLS_411 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_412 = __VLS_asFunctionalComponent(__VLS_411, new __VLS_411({
    value: "timeliness",
}));
const __VLS_413 = __VLS_412({
    value: "timeliness",
}, ...__VLS_functionalComponentArgsRest(__VLS_412));
__VLS_414.slots.default;
var __VLS_414;
var __VLS_398;
var __VLS_394;
var __VLS_390;
const __VLS_415 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_416 = __VLS_asFunctionalComponent(__VLS_415, new __VLS_415({
    span: (8),
}));
const __VLS_417 = __VLS_416({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_416));
__VLS_418.slots.default;
const __VLS_419 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_420 = __VLS_asFunctionalComponent(__VLS_419, new __VLS_419({
    label: "严重程度",
    name: "severity",
}));
const __VLS_421 = __VLS_420({
    label: "严重程度",
    name: "severity",
}, ...__VLS_functionalComponentArgsRest(__VLS_420));
__VLS_422.slots.default;
const __VLS_423 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_424 = __VLS_asFunctionalComponent(__VLS_423, new __VLS_423({
    value: (__VLS_ctx.formData.severity),
    placeholder: "选择严重程度",
}));
const __VLS_425 = __VLS_424({
    value: (__VLS_ctx.formData.severity),
    placeholder: "选择严重程度",
}, ...__VLS_functionalComponentArgsRest(__VLS_424));
__VLS_426.slots.default;
const __VLS_427 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_428 = __VLS_asFunctionalComponent(__VLS_427, new __VLS_427({
    value: "critical",
}));
const __VLS_429 = __VLS_428({
    value: "critical",
}, ...__VLS_functionalComponentArgsRest(__VLS_428));
__VLS_430.slots.default;
var __VLS_430;
const __VLS_431 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_432 = __VLS_asFunctionalComponent(__VLS_431, new __VLS_431({
    value: "major",
}));
const __VLS_433 = __VLS_432({
    value: "major",
}, ...__VLS_functionalComponentArgsRest(__VLS_432));
__VLS_434.slots.default;
var __VLS_434;
const __VLS_435 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_436 = __VLS_asFunctionalComponent(__VLS_435, new __VLS_435({
    value: "minor",
}));
const __VLS_437 = __VLS_436({
    value: "minor",
}, ...__VLS_functionalComponentArgsRest(__VLS_436));
__VLS_438.slots.default;
var __VLS_438;
var __VLS_426;
var __VLS_422;
var __VLS_418;
const __VLS_439 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_440 = __VLS_asFunctionalComponent(__VLS_439, new __VLS_439({
    span: (8),
}));
const __VLS_441 = __VLS_440({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_440));
__VLS_442.slots.default;
const __VLS_443 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_444 = __VLS_asFunctionalComponent(__VLS_443, new __VLS_443({
    label: "规则类型",
    name: "rule_type",
}));
const __VLS_445 = __VLS_444({
    label: "规则类型",
    name: "rule_type",
}, ...__VLS_functionalComponentArgsRest(__VLS_444));
__VLS_446.slots.default;
const __VLS_447 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_448 = __VLS_asFunctionalComponent(__VLS_447, new __VLS_447({
    value: (__VLS_ctx.formData.rule_type),
    placeholder: "选择规则类型",
}));
const __VLS_449 = __VLS_448({
    value: (__VLS_ctx.formData.rule_type),
    placeholder: "选择规则类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_448));
__VLS_450.slots.default;
const __VLS_451 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_452 = __VLS_asFunctionalComponent(__VLS_451, new __VLS_451({
    value: "objective",
}));
const __VLS_453 = __VLS_452({
    value: "objective",
}, ...__VLS_functionalComponentArgsRest(__VLS_452));
__VLS_454.slots.default;
var __VLS_454;
const __VLS_455 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_456 = __VLS_asFunctionalComponent(__VLS_455, new __VLS_455({
    value: "subjective",
}));
const __VLS_457 = __VLS_456({
    value: "subjective",
}, ...__VLS_functionalComponentArgsRest(__VLS_456));
__VLS_458.slots.default;
var __VLS_458;
const __VLS_459 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_460 = __VLS_asFunctionalComponent(__VLS_459, new __VLS_459({
    value: "hybrid",
}));
const __VLS_461 = __VLS_460({
    value: "hybrid",
}, ...__VLS_functionalComponentArgsRest(__VLS_460));
__VLS_462.slots.default;
var __VLS_462;
var __VLS_450;
var __VLS_446;
var __VLS_442;
var __VLS_386;
const __VLS_463 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_464 = __VLS_asFunctionalComponent(__VLS_463, new __VLS_463({
    gutter: (16),
}));
const __VLS_465 = __VLS_464({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_464));
__VLS_466.slots.default;
const __VLS_467 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_468 = __VLS_asFunctionalComponent(__VLS_467, new __VLS_467({
    span: (8),
}));
const __VLS_469 = __VLS_468({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_468));
__VLS_470.slots.default;
const __VLS_471 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_472 = __VLS_asFunctionalComponent(__VLS_471, new __VLS_471({
    label: "最大扣分",
    name: "max_score",
}));
const __VLS_473 = __VLS_472({
    label: "最大扣分",
    name: "max_score",
}, ...__VLS_functionalComponentArgsRest(__VLS_472));
__VLS_474.slots.default;
const __VLS_475 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_476 = __VLS_asFunctionalComponent(__VLS_475, new __VLS_475({
    value: (__VLS_ctx.formData.max_score),
    min: (0),
    max: (100),
    placeholder: "0表示单否",
    ...{ style: {} },
}));
const __VLS_477 = __VLS_476({
    value: (__VLS_ctx.formData.max_score),
    min: (0),
    max: (100),
    placeholder: "0表示单否",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_476));
var __VLS_474;
var __VLS_470;
const __VLS_479 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_480 = __VLS_asFunctionalComponent(__VLS_479, new __VLS_479({
    span: (8),
}));
const __VLS_481 = __VLS_480({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_480));
__VLS_482.slots.default;
const __VLS_483 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_484 = __VLS_asFunctionalComponent(__VLS_483, new __VLS_483({
    label: "权重",
    name: "weight",
}));
const __VLS_485 = __VLS_484({
    label: "权重",
    name: "weight",
}, ...__VLS_functionalComponentArgsRest(__VLS_484));
__VLS_486.slots.default;
const __VLS_487 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_488 = __VLS_asFunctionalComponent(__VLS_487, new __VLS_487({
    value: (__VLS_ctx.formData.weight),
    min: (0.1),
    max: (5.0),
    step: (0.1),
    placeholder: "1.0",
    ...{ style: {} },
}));
const __VLS_489 = __VLS_488({
    value: (__VLS_ctx.formData.weight),
    min: (0.1),
    max: (5.0),
    step: (0.1),
    placeholder: "1.0",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_488));
var __VLS_486;
var __VLS_482;
const __VLS_491 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_492 = __VLS_asFunctionalComponent(__VLS_491, new __VLS_491({
    span: (8),
}));
const __VLS_493 = __VLS_492({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_492));
__VLS_494.slots.default;
const __VLS_495 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_496 = __VLS_asFunctionalComponent(__VLS_495, new __VLS_495({
    label: "状态",
    name: "is_active",
}));
const __VLS_497 = __VLS_496({
    label: "状态",
    name: "is_active",
}, ...__VLS_functionalComponentArgsRest(__VLS_496));
__VLS_498.slots.default;
const __VLS_499 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_500 = __VLS_asFunctionalComponent(__VLS_499, new __VLS_499({
    checked: (__VLS_ctx.formData.is_active),
    checkedChildren: "激活",
    unCheckedChildren: "停用",
}));
const __VLS_501 = __VLS_500({
    checked: (__VLS_ctx.formData.is_active),
    checkedChildren: "激活",
    unCheckedChildren: "停用",
}, ...__VLS_functionalComponentArgsRest(__VLS_500));
var __VLS_498;
var __VLS_494;
var __VLS_466;
const __VLS_503 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_504 = __VLS_asFunctionalComponent(__VLS_503, new __VLS_503({
    label: "检查逻辑配置",
    name: "check_logic",
}));
const __VLS_505 = __VLS_504({
    label: "检查逻辑配置",
    name: "check_logic",
}, ...__VLS_functionalComponentArgsRest(__VLS_504));
__VLS_506.slots.default;
const __VLS_507 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_508 = __VLS_asFunctionalComponent(__VLS_507, new __VLS_507({
    value: (__VLS_ctx.checkLogicText),
    placeholder: "JSON格式的检查逻辑配置",
    rows: (4),
}));
const __VLS_509 = __VLS_508({
    value: (__VLS_ctx.checkLogicText),
    placeholder: "JSON格式的检查逻辑配置",
    rows: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_508));
var __VLS_506;
const __VLS_511 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_512 = __VLS_asFunctionalComponent(__VLS_511, new __VLS_511({
    label: "提示模板",
    name: "prompt_template",
}));
const __VLS_513 = __VLS_512({
    label: "提示模板",
    name: "prompt_template",
}, ...__VLS_functionalComponentArgsRest(__VLS_512));
__VLS_514.slots.default;
const __VLS_515 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_516 = __VLS_asFunctionalComponent(__VLS_515, new __VLS_515({
    value: (__VLS_ctx.formData.prompt_template),
    placeholder: "AI分析时使用的提示模板",
    rows: (6),
}));
const __VLS_517 = __VLS_516({
    value: (__VLS_ctx.formData.prompt_template),
    placeholder: "AI分析时使用的提示模板",
    rows: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_516));
var __VLS_514;
var __VLS_344;
var __VLS_335;
/** @type {__VLS_StyleScopedClasses['page-container']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-card']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-table-card']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-source']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-name']} */ ;
// @ts-ignore
var __VLS_346 = __VLS_345;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            PlusOutlined: icons_vue_1.PlusOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            ImportOutlined: icons_vue_1.ImportOutlined,
            ExportOutlined: icons_vue_1.ExportOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            ClearOutlined: icons_vue_1.ClearOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            TagsOutlined: icons_vue_1.TagsOutlined,
            loading: loading,
            searchText: searchText,
            filterCategory: filterCategory,
            filterSeverity: filterSeverity,
            filterType: filterType,
            filterStatus: filterStatus,
            modalVisible: modalVisible,
            modalLoading: modalLoading,
            modalTitle: modalTitle,
            formRef: formRef,
            formData: formData,
            checkLogicText: checkLogicText,
            formRules: formRules,
            pagination: pagination,
            columns: columns,
            rowSelection: rowSelection,
            statistics: statistics,
            filteredRules: filteredRules,
            getCategoryColor: getCategoryColor,
            getCategoryLabel: getCategoryLabel,
            getSeverityColor: getSeverityColor,
            getSeverityLabel: getSeverityLabel,
            getTypeColor: getTypeColor,
            getTypeLabel: getTypeLabel,
            refreshRules: refreshRules,
            handleSearch: handleSearch,
            handleFilter: handleFilter,
            resetFilters: resetFilters,
            handleTableChange: handleTableChange,
            showCreateModal: showCreateModal,
            editRule: editRule,
            viewRule: viewRule,
            testRule: testRule,
            deleteRule: deleteRule,
            toggleRuleStatus: toggleRuleStatus,
            handleBatchAction: handleBatchAction,
            handleModalOk: handleModalOk,
            handleModalCancel: handleModalCancel,
            importRules: importRules,
            exportRules: exportRules,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
