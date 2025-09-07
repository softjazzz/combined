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
// 响应式数据
const loading = (0, vue_1.ref)(false);
const exportLoading = (0, vue_1.ref)(false);
const showFilterModal = (0, vue_1.ref)(false);
const showColumnSettings = (0, vue_1.ref)(false);
const currentView = (0, vue_1.ref)('records');
const selectedRowKeys = (0, vue_1.ref)(: any[]);
const customTimeRange = (0, vue_1.ref)();
const activeTab = (0, vue_1.ref)('defects');
// 查询条件
const queryConditions = (0, vue_1.reactive)({
    timeRange: 'all',
    scoringStandard: 'all',
    searchType: 'registrationNo',
    searchValue: ''
});
// 筛选条件
const activeFilterConditions = (0, vue_1.ref)([
    { label: '科室', value: '内科' },
    { label: '状态', value: '待审核' }
]);
const filterTemplates = (0, vue_1.ref)([
    { id: 1, name: '今日待审核' },
    { id: 2, name: '本周超时' },
    { id: 3, name: '高风险病历' },
    { id: 4, name: '重点科室' }
]);
// 快速筛选标签
const quickFilters = (0, vue_1.ref)([
    { key: 'all', label: '全部', active: true },
    { key: 'pending', label: '待审核缺陷', active: false },
    { key: 'reviewing', label: '核心质控缺陷', active: false },
    { key: 'internal', label: '内涵质控缺陷', active: false },
    { key: 'critical', label: '重点病历缺陷', active: false },
    { key: 'completed', label: '已修正未审核缺陷', active: false },
    { key: 'approved', label: '核查申请未审核缺陷', active: false }
]);
// 当前筛选条件
const currentFilterConditions = (0, vue_1.ref)([
    '核查申请: 行政查房'
]);
// 多选框筛选条件
const filterConditions = (0, vue_1.ref)([
    { key: 'pending', label: '待审核病历', checked: false },
    { key: 'reviewing', label: '核查申请中', checked: true },
    { key: 'overtime', label: '超时病历', checked: false }
]);
// 新建筛选表单数据
const filterForm = (0, vue_1.reactive)({
    selectionMode: 'single',
    filterName: '',
    department: undefined,
    recordStatus: undefined,
    gender: undefined,
    staffType: undefined,
    hospitalStatus: undefined,
    dischargeDept: undefined,
    admissionDept: undefined,
    dischargeDate: undefined,
    admissionStartDate: undefined,
    admissionEndDate: undefined,
    submitMethod: undefined,
    scoreContent: undefined,
    scoreItem: undefined,
    testCategory: undefined,
    qcType: undefined,
    testType: undefined,
    coreQcCategory: undefined,
    qcResultType: undefined,
    comprehensiveName: undefined,
    scoreValue: '',
    testName: undefined
});
// 表格数据
const records = (0, vue_1.ref)([
    {
        id: '1',
        registrationNo: 'R2024001',
        serialNo: 'S2024001',
        caseNo: 'C2024001',
        patientName: '张三',
        doctorName: '李医生',
        department: '内科',
        auditStatus: 'pending',
        isUrgent: false
    }
]);
// 表格列配置
const recordColumns = [
    { title: '登记号', dataIndex: 'registrationNo', key: 'registrationNo', width: 120 },
    { title: '流水号', dataIndex: 'serialNo', key: 'serialNo', width: 120 },
    { title: '病案号', dataIndex: 'caseNo', key: 'caseNo', width: 120 },
    { title: '患者姓名', dataIndex: 'patientName', key: 'patientName', width: 100 },
    { title: '临床医生', dataIndex: 'doctorName', key: 'doctorName', width: 100 },
    { title: '科室', dataIndex: 'department', key: 'department', width: 100 },
    { title: '审核状态', dataIndex: 'auditStatus', key: 'auditStatus', width: 100 },
    { title: '操作', key: 'action', width: 120, fixed: 'right' }
];
// 分页配置
const pagination = (0, vue_1.reactive)({
    current: 1,
    pageSize: 20,
    total: 100,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
});
// 行选择配置
const rowSelection = (0, vue_1.computed)(() => ({
    selectedRowKeys: selectedRowKeys.value, onChange: (keys) => {
        selectedRowKeys.value = keys;
    },
    getCheckboxProps: (record) => ({
        disabled: record.disabled
    })
}));
// 计算属性
const canBatchUrge = (0, vue_1.computed)(() => {
    return selectedRowKeys.value.length > 0;
});
// 方法
const handleTimeRangeChange = (value) => {
    console.log('Time range changed:', value);
    handleQuery();
};
const handleCustomTimeChange = (dates) => {
    console.log('Custom time range:', dates);
    handleQuery();
};
const handleQuery = () => {
    loading.value = true;
    // 模拟查询
    setTimeout(() => {
        loading.value = false;
        ant_design_vue_1.message.success('查询完成');
    }, 1000);
};
const handleQuickFilter = ({ key }) => {
    console.log('Quick filter:', key);
    ant_design_vue_1.message.info('应用快捷筛选');
};
const handleResetFilter = () => {
    activeFilterConditions.value = [];
    ant_design_vue_1.message.info('筛选条件已重置');
};
const removeFilterCondition = (index) => {
    activeFilterConditions.value.splice(index, 1);
};
const handleQuickFilterClick = (filter) => {
    // 重置所有筛选状态
    quickFilters.value.forEach(f => f.active = false);
    // 激活当前筛选
    filter.active = true;
    console.log('Quick filter clicked:', filter.key);
    ant_design_vue_1.message.info(`应用筛选: ${filter.label}`);
    // 这里可以添加实际的筛选逻辑
    handleQuery();
};
const removeCurrentFilterCondition = (index) => {
    currentFilterConditions.value.splice(index, 1);
    ant_design_vue_1.message.info('筛选条件已移除');
};
const handleFilterConditionChange = (condition) => {
    console.log('Filter condition changed:', condition.key, condition.checked);
    // 这里可以添加实际的筛选逻辑
};
const handleClearFilters = () => {
    filterConditions.value.forEach(condition => {
        condition.checked = false;
    });
    ant_design_vue_1.message.info('筛选条件已清空');
};
// 新建筛选弹窗相关方法
const handleCancel = () => {
    showFilterModal.value = false;
};
const handleReset = () => {
    // 重置表单数据
    Object.keys(filterForm).forEach(key => {
        if (key === 'selectionMode') {
            filterForm[key] = 'single';
        }
        else if (key === 'filterName' || key === 'scoreValue') {
            filterForm[key] = '';
        }
        else {
            filterForm[key] = undefined;
        }
    });
    ant_design_vue_1.message.info('表单已清空');
};
const handleConfirm = () => {
    // 验证必填字段
    if (!filterForm.filterName.trim()) {
        ant_design_vue_1.message.error('请输入筛选条件名称');
        return;
    }
    // 收集已选择的筛选条件
    const selectedConditions = [];
    Object.keys(filterForm).forEach(key => {
        if (filterForm[key] !== undefined && filterForm[key] !== '' && key !== 'selectionMode' && key !== 'filterName') {
            selectedConditions.push({
                key,
                value: filterForm[key],
                label: getFieldLabel(key)
            });
        }
    });
    if (selectedConditions.length === 0) {
        ant_design_vue_1.message.error('请至少选择一个筛选条件');
        return;
    }
    // 应用筛选条件
    console.log('应用筛选条件:', {
        name: filterForm.filterName,
        mode: filterForm.selectionMode,
        conditions: selectedConditions
    });
    ant_design_vue_1.message.success(`筛选条件"${filterForm.filterName}"已创建`);
    showFilterModal.value = false;
};
// 获取字段标签
const getFieldLabel = (key) => {
    const labelMap = {
        department: '病历科室',
        recordStatus: '病历状态',
        gender: '患者性别',
        staffType: '人员类型',
        hospitalStatus: '在院状态',
        dischargeDept: '出院科室',
        admissionDept: '入院科室',
        dischargeDate: '出院时间',
        admissionStartDate: '入院开始时间',
        admissionEndDate: '入院结束时间',
        submitMethod: '提交方式',
        scoreContent: '评分内容',
        scoreItem: '评分项目',
        testCategory: '检验大类',
        qcType: '质控类型',
        testType: '检验类型',
        coreQcCategory: '核心质控分类',
        qcResultType: '质控结果类型',
        comprehensiveName: '综合名称',
        scoreValue: '分值',
        testName: '检验名称'
    };
    return labelMap[key] || key;
};
const handleViewChange = (checked) => {
    console.log('View changed:', checked);
};
const handleBatchUrge = () => {
    ant_design_vue_1.message.info(`批量催办 ${selectedRowKeys.value.length} 条记录`);
};
const handleBatchRecheck = () => {
    ant_design_vue_1.message.info(`批量重新质控 ${selectedRowKeys.value.length} 条记录`);
};
const handleBatchPass = () => {
    ant_design_vue_1.message.info(`批量通过 ${selectedRowKeys.value.length} 条记录`);
};
const handleExportAll = () => {
    exportLoading.value = true;
    setTimeout(() => {
        exportLoading.value = false;
        ant_design_vue_1.message.success('导出完成');
    }, 2000);
};
const handleExportQCDetails = () => {
    exportLoading.value = true;
    setTimeout(() => {
        exportLoading.value = false;
        ant_design_vue_1.message.success('质控详情导出完成');
    }, 2000);
};
const handleRefresh = () => {
    loading.value = true;
    setTimeout(() => {
        loading.value = false;
        ant_design_vue_1.message.success('刷新完成');
    }, 1000);
};
const handleTableChange = (pag, filters: any,  sorter: any) => {
    pagination.current = pag.current;
    pagination.pageSize = pag.pageSize;
    handleQuery();
};
const handleViewDetail = (record) => {
    console.log('View detail:', record);
    ant_design_vue_1.message.info('查看详情');
};
const handleUrgeRecord = (record) => {
    console.log('Urge record:', record);
    ant_design_vue_1.message.info('催办成功');
};
const getAuditStatusColor = (status) => {
    const colorMap = {
        pending: 'orange',
        approved: 'green',
        rejected: 'red',
        reviewing: 'blue'
    };
    return colorMap[status] || 'default';
};
const getAuditStatusText = (status) => {
    const textMap = {
        pending: '待审核',
        approved: '已通过',
        rejected: '已拒绝',
        reviewing: '审核中'
    };
    return textMap[status] || '未知';
};
// 生命周期
(0, vue_1.onMounted)(() => {
    handleQuery();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag-compact']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag-compact']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag-compact']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag-compact']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag-blue']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-checkbox-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-checkbox-inner']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['w-80']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['w-40']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-group']} */ ;
/** @type {__VLS_StyleScopedClasses['w-80']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['action-section']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tabs-tab']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag-compact']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-name-input']} */ ;
/** @type {__VLS_StyleScopedClasses['date-range-row']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date-range']} */ ;
/** @type {__VLS_StyleScopedClasses['comprehensive-select']} */ ;
/** @type {__VLS_StyleScopedClasses['score-input']} */ ;
/** @type {__VLS_StyleScopedClasses['test-name-select']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['cancel-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['reset-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['confirm-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['action-section']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "running-records-page bg-gray-50 min-h-screen" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white border-b border-gray-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-section px-6 py-4 border-b border-gray-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-wrap items-end justify-between gap-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-wrap items-end gap-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-item flex-shrink-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-gray-700 mb-2" },
});
const __VLS_0 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.timeRange),
    placeholder: "选择时间周期",
    ...{ class: "w-40" },
    size: "middle",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.timeRange),
    placeholder: "选择时间周期",
    ...{ class: "w-40" },
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onChange: (__VLS_ctx.handleTimeRangeChange)
};
__VLS_3.slots.default;
const __VLS_8 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    value: "all",
}));
const __VLS_10 = __VLS_9({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
var __VLS_11;
const __VLS_12 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    value: "recent7",
}));
const __VLS_14 = __VLS_13({
    value: "recent7",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
const __VLS_16 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    value: "month",
}));
const __VLS_18 = __VLS_17({
    value: "month",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
var __VLS_19;
const __VLS_20 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    value: "quarter",
}));
const __VLS_22 = __VLS_21({
    value: "quarter",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
var __VLS_23;
const __VLS_24 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    value: "year",
}));
const __VLS_26 = __VLS_25({
    value: "year",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
var __VLS_27;
const __VLS_28 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    value: "custom",
}));
const __VLS_30 = __VLS_29({
    value: "custom",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
var __VLS_31;
var __VLS_3;
if (__VLS_ctx.queryConditions.timeRange === 'custom') {
    const __VLS_32 = {}.ARangePicker;
    /** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.customTimeRange),
        ...{ class: "w-64 mt-2" },
        size: "middle",
    }));
    const __VLS_34 = __VLS_33({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.customTimeRange),
        ...{ class: "w-64 mt-2" },
        size: "middle",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    let __VLS_36;
    let __VLS_37;
    let __VLS_38;
    const __VLS_39 = {
        onChange: (__VLS_ctx.handleCustomTimeChange)
    };
    var __VLS_35;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-item flex-shrink-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-gray-700 mb-2" },
});
const __VLS_40 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.scoringStandard),
    placeholder: "选择评分标准",
    ...{ class: "w-40" },
    size: "middle",
}));
const __VLS_42 = __VLS_41({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.scoringStandard),
    placeholder: "选择评分标准",
    ...{ class: "w-40" },
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onChange: (__VLS_ctx.handleQuery)
};
__VLS_43.slots.default;
const __VLS_48 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    value: "all",
}));
const __VLS_50 = __VLS_49({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
var __VLS_51;
const __VLS_52 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    value: "standard1",
}));
const __VLS_54 = __VLS_53({
    value: "standard1",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
var __VLS_55;
const __VLS_56 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    value: "standard2",
}));
const __VLS_58 = __VLS_57({
    value: "standard2",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
var __VLS_59;
const __VLS_60 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    value: "standard3",
}));
const __VLS_62 = __VLS_61({
    value: "standard3",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
var __VLS_63;
var __VLS_43;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-item flex-shrink-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-gray-700 mb-2" },
});
const __VLS_64 = {}.AInputGroup;
/** @type {[typeof __VLS_components.AInputGroup, typeof __VLS_components.aInputGroup, typeof __VLS_components.AInputGroup, typeof __VLS_components.aInputGroup, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    compact: true,
    ...{ class: "w-80" },
}));
const __VLS_66 = __VLS_65({
    compact: true,
    ...{ class: "w-80" },
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
const __VLS_68 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    value: (__VLS_ctx.queryConditions.searchType),
    ...{ style: {} },
    size: "middle",
}));
const __VLS_70 = __VLS_69({
    value: (__VLS_ctx.queryConditions.searchType),
    ...{ style: {} },
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    value: "registrationNo",
}));
const __VLS_74 = __VLS_73({
    value: "registrationNo",
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
var __VLS_75;
const __VLS_76 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    value: "serialNo",
}));
const __VLS_78 = __VLS_77({
    value: "serialNo",
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
var __VLS_79;
const __VLS_80 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    value: "caseNo",
}));
const __VLS_82 = __VLS_81({
    value: "caseNo",
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
var __VLS_83;
const __VLS_84 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    value: "patientName",
}));
const __VLS_86 = __VLS_85({
    value: "patientName",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
var __VLS_87;
const __VLS_88 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    value: "doctorName",
}));
const __VLS_90 = __VLS_89({
    value: "doctorName",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
var __VLS_91;
var __VLS_71;
const __VLS_92 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.queryConditions.searchValue),
    ...{ style: {} },
    placeholder: "输入查询内容",
    size: "middle",
}));
const __VLS_94 = __VLS_93({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.queryConditions.searchValue),
    ...{ style: {} },
    placeholder: "输入查询内容",
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
let __VLS_96;
let __VLS_97;
let __VLS_98;
const __VLS_99 = {
    onPressEnter: (__VLS_ctx.handleQuery)
};
__VLS_95.slots.default;
{
    const { suffix: __VLS_thisSlot } = __VLS_95.slots;
    const __VLS_100 = {}.SearchOutlined;
    /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        ...{ 'onClick': {} },
        ...{ class: "cursor-pointer text-gray-400 hover:text-blue-500" },
    }));
    const __VLS_102 = __VLS_101({
        ...{ 'onClick': {} },
        ...{ class: "cursor-pointer text-gray-400 hover:text-blue-500" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    let __VLS_104;
    let __VLS_105;
    let __VLS_106;
    const __VLS_107 = {
        onClick: (__VLS_ctx.handleQuery)
    };
    var __VLS_103;
}
var __VLS_95;
var __VLS_67;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "defect-filter-section bg-white border-b border-gray-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "px-6 py-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center mb-2" },
});
const __VLS_108 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "defect-tabs" },
    size: "default",
}));
const __VLS_110 = __VLS_109({
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "defect-tabs" },
    size: "default",
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
const __VLS_112 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    key: "defects",
    tab: "缺陷列表",
}));
const __VLS_114 = __VLS_113({
    key: "defects",
    tab: "缺陷列表",
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
const __VLS_116 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    key: "records",
    tab: "病历列表",
}));
const __VLS_118 = __VLS_117({
    key: "records",
    tab: "病历列表",
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
var __VLS_111;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-wrap items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm font-medium text-gray-700" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-wrap gap-1" },
});
for (const [filter] of __VLS_getVForSourceType((__VLS_ctx.quickFilters))) {
    const __VLS_120 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        ...{ 'onClick': {} },
        key: (filter.key),
        color: (filter.active ? 'blue' : ''),
        ...{ class: "quick-filter-tag-compact" },
    }));
    const __VLS_122 = __VLS_121({
        ...{ 'onClick': {} },
        key: (filter.key),
        color: (filter.active ? 'blue' : ''),
        ...{ class: "quick-filter-tag-compact" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
    let __VLS_124;
    let __VLS_125;
    let __VLS_126;
    const __VLS_127 = {
        onClick: (...[$event]) => {
            __VLS_ctx.handleQuickFilterClick(filter);
        }
    };
    __VLS_123.slots.default;
    (filter.label);
    var __VLS_123;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-section px-6 py-3 bg-gray-50 border-b border-gray-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm font-medium text-gray-700" },
});
const __VLS_128 = {}.ADropdown;
/** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    placement: "bottomLeft",
}));
const __VLS_130 = __VLS_129({
    placement: "bottomLeft",
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
const __VLS_132 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}));
const __VLS_134 = __VLS_133({
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_133));
__VLS_135.slots.default;
const __VLS_136 = {}.FilterOutlined;
/** @type {[typeof __VLS_components.FilterOutlined, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    ...{ class: "mr-1" },
}));
const __VLS_138 = __VLS_137({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
const __VLS_140 = {}.DownOutlined;
/** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    ...{ class: "ml-1 text-xs" },
}));
const __VLS_142 = __VLS_141({
    ...{ class: "ml-1 text-xs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
var __VLS_135;
{
    const { overlay: __VLS_thisSlot } = __VLS_131.slots;
    const __VLS_144 = {}.AMenu;
    /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        ...{ 'onClick': {} },
        ...{ class: "min-w-[160px]" },
    }));
    const __VLS_146 = __VLS_145({
        ...{ 'onClick': {} },
        ...{ class: "min-w-[160px]" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    let __VLS_148;
    let __VLS_149;
    let __VLS_150;
    const __VLS_151 = {
        onClick: (__VLS_ctx.handleQuickFilter)
    };
    __VLS_147.slots.default;
    for (const [template] of __VLS_getVForSourceType((__VLS_ctx.filterTemplates))) {
        const __VLS_152 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
            key: (template.id),
            ...{ class: "text-sm" },
        }));
        const __VLS_154 = __VLS_153({
            key: (template.id),
            ...{ class: "text-sm" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_153));
        __VLS_155.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_155.slots;
            const __VLS_156 = {}.TagOutlined;
            /** @type {[typeof __VLS_components.TagOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
                ...{ class: "text-xs" },
            }));
            const __VLS_158 = __VLS_157({
                ...{ class: "text-xs" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_157));
        }
        (template.name);
        var __VLS_155;
    }
    var __VLS_147;
}
var __VLS_131;
const __VLS_160 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
    ...{ 'onClick': {} },
    size: "small",
    type: "primary",
    ...{ class: "bg-blue-600 border-blue-600" },
}));
const __VLS_162 = __VLS_161({
    ...{ 'onClick': {} },
    size: "small",
    type: "primary",
    ...{ class: "bg-blue-600 border-blue-600" },
}, ...__VLS_functionalComponentArgsRest(__VLS_161));
let __VLS_164;
let __VLS_165;
let __VLS_166;
const __VLS_167 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showFilterModal = true;
    }
};
__VLS_163.slots.default;
const __VLS_168 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    ...{ class: "mr-1" },
}));
const __VLS_170 = __VLS_169({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
var __VLS_163;
const __VLS_172 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}));
const __VLS_174 = __VLS_173({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
let __VLS_176;
let __VLS_177;
let __VLS_178;
const __VLS_179 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showFilterModal = true;
    }
};
__VLS_175.slots.default;
const __VLS_180 = {}.EditOutlined;
/** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
// @ts-ignore
const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
    ...{ class: "mr-1" },
}));
const __VLS_182 = __VLS_181({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_181));
var __VLS_175;
const __VLS_184 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-red-600 hover:border-red-300" },
}));
const __VLS_186 = __VLS_185({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-red-600 hover:border-red-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_185));
let __VLS_188;
let __VLS_189;
let __VLS_190;
const __VLS_191 = {
    onClick: (__VLS_ctx.handleResetFilter)
};
__VLS_187.slots.default;
const __VLS_192 = {}.ClearOutlined;
/** @type {[typeof __VLS_components.ClearOutlined, ]} */ ;
// @ts-ignore
const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
    ...{ class: "mr-1" },
}));
const __VLS_194 = __VLS_193({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_193));
var __VLS_187;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm text-gray-500" },
});
(__VLS_ctx.currentView === 'defects' ? '缺陷列表' : '病历列表');
const __VLS_196 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    ...{ 'onChange': {} },
    checked: (__VLS_ctx.currentView),
    checkedValue: "records",
    unCheckedValue: "defects",
    size: "small",
}));
const __VLS_198 = __VLS_197({
    ...{ 'onChange': {} },
    checked: (__VLS_ctx.currentView),
    checkedValue: "records",
    unCheckedValue: "defects",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
let __VLS_200;
let __VLS_201;
let __VLS_202;
const __VLS_203 = {
    onChange: (__VLS_ctx.handleViewChange)
};
__VLS_199.slots.default;
{
    const { checkedChildren: __VLS_thisSlot } = __VLS_199.slots;
    const __VLS_204 = {}.FileTextOutlined;
    /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        ...{ class: "text-xs" },
    }));
    const __VLS_206 = __VLS_205({
        ...{ class: "text-xs" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
}
{
    const { unCheckedChildren: __VLS_thisSlot } = __VLS_199.slots;
    const __VLS_208 = {}.ExclamationCircleOutlined;
    /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        ...{ class: "text-xs" },
    }));
    const __VLS_210 = __VLS_209({
        ...{ class: "text-xs" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
}
var __VLS_199;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-tags-container" },
});
if (__VLS_ctx.activeFilterConditions.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex flex-wrap gap-2" },
    });
    for (const [condition, index] of __VLS_getVForSourceType((__VLS_ctx.activeFilterConditions))) {
        const __VLS_212 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
            ...{ 'onClose': {} },
            key: (index),
            closable: true,
            color: "blue",
            ...{ class: "px-2 py-1 text-xs" },
        }));
        const __VLS_214 = __VLS_213({
            ...{ 'onClose': {} },
            key: (index),
            closable: true,
            color: "blue",
            ...{ class: "px-2 py-1 text-xs" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_213));
        let __VLS_216;
        let __VLS_217;
        let __VLS_218;
        const __VLS_219 = {
            onClose: (...[$event]) => {
                if (!(__VLS_ctx.activeFilterConditions.length > 0))
                    return;
                __VLS_ctx.removeFilterCondition(index);
            }
        };
        __VLS_215.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "font-medium" },
        });
        (condition.label);
        (condition.value);
        var __VLS_215;
    }
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-gray-400 py-1" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "action-section px-6 py-4 border-b border-gray-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-3" },
});
if (__VLS_ctx.selectedRowKeys.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center space-x-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-sm text-gray-600" },
    });
    (__VLS_ctx.selectedRowKeys.length);
    const __VLS_220 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
        type: "vertical",
        ...{ class: "mx-2" },
    }));
    const __VLS_222 = __VLS_221({
        type: "vertical",
        ...{ class: "mx-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_221));
}
if (__VLS_ctx.selectedRowKeys.length > 0) {
    const __VLS_224 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
        ...{ 'onClick': {} },
        type: "primary",
        size: "small",
        disabled: (!__VLS_ctx.canBatchUrge),
        ...{ class: "bg-blue-600 border-blue-600" },
    }));
    const __VLS_226 = __VLS_225({
        ...{ 'onClick': {} },
        type: "primary",
        size: "small",
        disabled: (!__VLS_ctx.canBatchUrge),
        ...{ class: "bg-blue-600 border-blue-600" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_225));
    let __VLS_228;
    let __VLS_229;
    let __VLS_230;
    const __VLS_231 = {
        onClick: (__VLS_ctx.handleBatchUrge)
    };
    __VLS_227.slots.default;
    const __VLS_232 = {}.SendOutlined;
    /** @type {[typeof __VLS_components.SendOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
        ...{ class: "mr-1" },
    }));
    const __VLS_234 = __VLS_233({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_233));
    (__VLS_ctx.selectedRowKeys.length);
    var __VLS_227;
}
if (__VLS_ctx.selectedRowKeys.length > 0 && __VLS_ctx.currentView === 'records') {
    const __VLS_236 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-orange-300 text-orange-600 hover:text-orange-700 hover:border-orange-400" },
    }));
    const __VLS_238 = __VLS_237({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-orange-300 text-orange-600 hover:text-orange-700 hover:border-orange-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_237));
    let __VLS_240;
    let __VLS_241;
    let __VLS_242;
    const __VLS_243 = {
        onClick: (__VLS_ctx.handleBatchRecheck)
    };
    __VLS_239.slots.default;
    const __VLS_244 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
        ...{ class: "mr-1" },
    }));
    const __VLS_246 = __VLS_245({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_245));
    var __VLS_239;
}
if (__VLS_ctx.selectedRowKeys.length > 0 && __VLS_ctx.currentView === 'records') {
    const __VLS_248 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-green-300 text-green-600 hover:text-green-700 hover:border-green-400" },
    }));
    const __VLS_250 = __VLS_249({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-green-300 text-green-600 hover:text-green-700 hover:border-green-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_249));
    let __VLS_252;
    let __VLS_253;
    let __VLS_254;
    const __VLS_255 = {
        onClick: (__VLS_ctx.handleBatchPass)
    };
    __VLS_251.slots.default;
    const __VLS_256 = {}.CheckOutlined;
    /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
        ...{ class: "mr-1" },
    }));
    const __VLS_258 = __VLS_257({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_257));
    var __VLS_251;
}
if (__VLS_ctx.selectedRowKeys.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-gray-400" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-2" },
});
const __VLS_260 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.exportLoading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}));
const __VLS_262 = __VLS_261({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.exportLoading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_261));
let __VLS_264;
let __VLS_265;
let __VLS_266;
const __VLS_267 = {
    onClick: (__VLS_ctx.handleExportAll)
};
__VLS_263.slots.default;
const __VLS_268 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
    ...{ class: "mr-1" },
}));
const __VLS_270 = __VLS_269({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_269));
var __VLS_263;
if (__VLS_ctx.currentView === 'records') {
    const __VLS_272 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
        ...{ 'onClick': {} },
        size: "small",
        loading: (__VLS_ctx.exportLoading),
        ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
    }));
    const __VLS_274 = __VLS_273({
        ...{ 'onClick': {} },
        size: "small",
        loading: (__VLS_ctx.exportLoading),
        ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_273));
    let __VLS_276;
    let __VLS_277;
    let __VLS_278;
    const __VLS_279 = {
        onClick: (__VLS_ctx.handleExportQCDetails)
    };
    __VLS_275.slots.default;
    const __VLS_280 = {}.FileExcelOutlined;
    /** @type {[typeof __VLS_components.FileExcelOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
        ...{ class: "mr-1" },
    }));
    const __VLS_282 = __VLS_281({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_281));
    var __VLS_275;
}
const __VLS_284 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.loading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-green-600 hover:border-green-300" },
}));
const __VLS_286 = __VLS_285({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.loading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-green-600 hover:border-green-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_285));
let __VLS_288;
let __VLS_289;
let __VLS_290;
const __VLS_291 = {
    onClick: (__VLS_ctx.handleRefresh)
};
__VLS_287.slots.default;
const __VLS_292 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
    ...{ class: "mr-1" },
}));
const __VLS_294 = __VLS_293({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_293));
var __VLS_287;
const __VLS_296 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-purple-600 hover:border-purple-300" },
}));
const __VLS_298 = __VLS_297({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-purple-600 hover:border-purple-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_297));
let __VLS_300;
let __VLS_301;
let __VLS_302;
const __VLS_303 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showColumnSettings = true;
    }
};
__VLS_299.slots.default;
const __VLS_304 = {}.SettingOutlined;
/** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
// @ts-ignore
const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({}));
const __VLS_306 = __VLS_305({}, ...__VLS_functionalComponentArgsRest(__VLS_305));
var __VLS_299;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "data-section p-6" },
});
const __VLS_308 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.recordColumns),
    dataSource: (__VLS_ctx.records),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    size: "small",
}));
const __VLS_310 = __VLS_309({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.recordColumns),
    dataSource: (__VLS_ctx.records),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_309));
let __VLS_312;
let __VLS_313;
let __VLS_314;
const __VLS_315 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_311.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_311.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'registrationNo') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
            ...{ onClick: (...[$event]) => {
                    if (!(column.key === 'registrationNo'))
                        return;
                    __VLS_ctx.handleViewDetail(record);
                } },
            ...{ class: "text-blue-600 hover:text-blue-800" },
        });
        (record.registrationNo);
    }
    if (column.key === 'serialNo') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
            ...{ onClick: (...[$event]) => {
                    if (!(column.key === 'serialNo'))
                        return;
                    __VLS_ctx.handleViewDetail(record);
                } },
            ...{ class: "text-blue-600 hover:text-blue-800" },
        });
        (record.serialNo);
    }
    if (column.key === 'caseNo') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
            ...{ onClick: (...[$event]) => {
                    if (!(column.key === 'caseNo'))
                        return;
                    __VLS_ctx.handleViewDetail(record);
                } },
            ...{ class: "text-blue-600 hover:text-blue-800" },
        });
        (record.caseNo);
    }
    if (column.key === 'auditStatus') {
        const __VLS_316 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
            color: (__VLS_ctx.getAuditStatusColor(record.auditStatus)),
        }));
        const __VLS_318 = __VLS_317({
            color: (__VLS_ctx.getAuditStatusColor(record.auditStatus)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_317));
        __VLS_319.slots.default;
        (__VLS_ctx.getAuditStatusText(record.auditStatus));
        var __VLS_319;
    }
    if (column.key === 'action') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex space-x-1" },
        });
        const __VLS_320 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_322 = __VLS_321({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_321));
        let __VLS_324;
        let __VLS_325;
        let __VLS_326;
        const __VLS_327 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleViewDetail(record);
            }
        };
        __VLS_323.slots.default;
        var __VLS_323;
        if (!record.isUrgent) {
            const __VLS_328 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_330 = __VLS_329({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_329));
            let __VLS_332;
            let __VLS_333;
            let __VLS_334;
            const __VLS_335 = {
                onClick: (...[$event]) => {
                    if (!(column.key === 'action'))
                        return;
                    if (!(!record.isUrgent))
                        return;
                    __VLS_ctx.handleUrgeRecord(record);
                }
            };
            __VLS_331.slots.default;
            var __VLS_331;
        }
    }
}
var __VLS_311;
const __VLS_336 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({
    open: (__VLS_ctx.showFilterModal),
    title: "新建筛选",
    width: "900px",
    footer: (null),
    ...{ class: "filter-modal" },
    maskClosable: (false),
}));
const __VLS_338 = __VLS_337({
    open: (__VLS_ctx.showFilterModal),
    title: "新建筛选",
    width: "900px",
    footer: (null),
    ...{ class: "filter-modal" },
    maskClosable: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_337));
__VLS_339.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-form-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-section mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "section-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-row" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "form-label" },
});
const __VLS_340 = {}.ARadioGroup;
/** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_341 = __VLS_asFunctionalComponent(__VLS_340, new __VLS_340({
    value: (__VLS_ctx.filterForm.selectionMode),
    ...{ class: "ml-2" },
}));
const __VLS_342 = __VLS_341({
    value: (__VLS_ctx.filterForm.selectionMode),
    ...{ class: "ml-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_341));
__VLS_343.slots.default;
const __VLS_344 = {}.ARadio;
/** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
// @ts-ignore
const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
    value: "single",
}));
const __VLS_346 = __VLS_345({
    value: "single",
}, ...__VLS_functionalComponentArgsRest(__VLS_345));
__VLS_347.slots.default;
var __VLS_347;
const __VLS_348 = {}.ARadio;
/** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
// @ts-ignore
const __VLS_349 = __VLS_asFunctionalComponent(__VLS_348, new __VLS_348({
    value: "multiple",
}));
const __VLS_350 = __VLS_349({
    value: "multiple",
}, ...__VLS_functionalComponentArgsRest(__VLS_349));
__VLS_351.slots.default;
var __VLS_351;
const __VLS_352 = {}.ARadio;
/** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
// @ts-ignore
const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({
    value: "multipleSupported",
}));
const __VLS_354 = __VLS_353({
    value: "multipleSupported",
}, ...__VLS_functionalComponentArgsRest(__VLS_353));
__VLS_355.slots.default;
var __VLS_355;
var __VLS_343;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-row" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "form-label" },
});
const __VLS_356 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_357 = __VLS_asFunctionalComponent(__VLS_356, new __VLS_356({
    value: (__VLS_ctx.filterForm.filterName),
    placeholder: "请输入",
    ...{ class: "filter-name-input" },
    maxlength: (50),
}));
const __VLS_358 = __VLS_357({
    value: (__VLS_ctx.filterForm.filterName),
    placeholder: "请输入",
    ...{ class: "filter-name-input" },
    maxlength: (50),
}, ...__VLS_functionalComponentArgsRest(__VLS_357));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-section mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "section-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-grid" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-column" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_360 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_361 = __VLS_asFunctionalComponent(__VLS_360, new __VLS_360({
    value: (__VLS_ctx.filterForm.department),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}));
const __VLS_362 = __VLS_361({
    value: (__VLS_ctx.filterForm.department),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_361));
__VLS_363.slots.default;
const __VLS_364 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({
    value: "internal",
}));
const __VLS_366 = __VLS_365({
    value: "internal",
}, ...__VLS_functionalComponentArgsRest(__VLS_365));
__VLS_367.slots.default;
var __VLS_367;
const __VLS_368 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_369 = __VLS_asFunctionalComponent(__VLS_368, new __VLS_368({
    value: "surgery",
}));
const __VLS_370 = __VLS_369({
    value: "surgery",
}, ...__VLS_functionalComponentArgsRest(__VLS_369));
__VLS_371.slots.default;
var __VLS_371;
const __VLS_372 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_373 = __VLS_asFunctionalComponent(__VLS_372, new __VLS_372({
    value: "pediatrics",
}));
const __VLS_374 = __VLS_373({
    value: "pediatrics",
}, ...__VLS_functionalComponentArgsRest(__VLS_373));
__VLS_375.slots.default;
var __VLS_375;
var __VLS_363;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_376 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_377 = __VLS_asFunctionalComponent(__VLS_376, new __VLS_376({
    value: (__VLS_ctx.filterForm.gender),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}));
const __VLS_378 = __VLS_377({
    value: (__VLS_ctx.filterForm.gender),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_377));
__VLS_379.slots.default;
const __VLS_380 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_381 = __VLS_asFunctionalComponent(__VLS_380, new __VLS_380({
    value: "male",
}));
const __VLS_382 = __VLS_381({
    value: "male",
}, ...__VLS_functionalComponentArgsRest(__VLS_381));
__VLS_383.slots.default;
var __VLS_383;
const __VLS_384 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_385 = __VLS_asFunctionalComponent(__VLS_384, new __VLS_384({
    value: "female",
}));
const __VLS_386 = __VLS_385({
    value: "female",
}, ...__VLS_functionalComponentArgsRest(__VLS_385));
__VLS_387.slots.default;
var __VLS_387;
var __VLS_379;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_388 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_389 = __VLS_asFunctionalComponent(__VLS_388, new __VLS_388({
    value: (__VLS_ctx.filterForm.admissionDept),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}));
const __VLS_390 = __VLS_389({
    value: (__VLS_ctx.filterForm.admissionDept),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_389));
__VLS_391.slots.default;
const __VLS_392 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_393 = __VLS_asFunctionalComponent(__VLS_392, new __VLS_392({
    value: "emergency",
}));
const __VLS_394 = __VLS_393({
    value: "emergency",
}, ...__VLS_functionalComponentArgsRest(__VLS_393));
__VLS_395.slots.default;
var __VLS_395;
const __VLS_396 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_397 = __VLS_asFunctionalComponent(__VLS_396, new __VLS_396({
    value: "internal",
}));
const __VLS_398 = __VLS_397({
    value: "internal",
}, ...__VLS_functionalComponentArgsRest(__VLS_397));
__VLS_399.slots.default;
var __VLS_399;
var __VLS_391;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-column" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_400 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_401 = __VLS_asFunctionalComponent(__VLS_400, new __VLS_400({
    value: (__VLS_ctx.filterForm.recordStatus),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}));
const __VLS_402 = __VLS_401({
    value: (__VLS_ctx.filterForm.recordStatus),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_401));
__VLS_403.slots.default;
const __VLS_404 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_405 = __VLS_asFunctionalComponent(__VLS_404, new __VLS_404({
    value: "draft",
}));
const __VLS_406 = __VLS_405({
    value: "draft",
}, ...__VLS_functionalComponentArgsRest(__VLS_405));
__VLS_407.slots.default;
var __VLS_407;
const __VLS_408 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_409 = __VLS_asFunctionalComponent(__VLS_408, new __VLS_408({
    value: "completed",
}));
const __VLS_410 = __VLS_409({
    value: "completed",
}, ...__VLS_functionalComponentArgsRest(__VLS_409));
__VLS_411.slots.default;
var __VLS_411;
var __VLS_403;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_412 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_413 = __VLS_asFunctionalComponent(__VLS_412, new __VLS_412({
    value: (__VLS_ctx.filterForm.staffType),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}));
const __VLS_414 = __VLS_413({
    value: (__VLS_ctx.filterForm.staffType),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_413));
__VLS_415.slots.default;
const __VLS_416 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_417 = __VLS_asFunctionalComponent(__VLS_416, new __VLS_416({
    value: "doctor",
}));
const __VLS_418 = __VLS_417({
    value: "doctor",
}, ...__VLS_functionalComponentArgsRest(__VLS_417));
__VLS_419.slots.default;
var __VLS_419;
const __VLS_420 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_421 = __VLS_asFunctionalComponent(__VLS_420, new __VLS_420({
    value: "nurse",
}));
const __VLS_422 = __VLS_421({
    value: "nurse",
}, ...__VLS_functionalComponentArgsRest(__VLS_421));
__VLS_423.slots.default;
var __VLS_423;
var __VLS_415;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_424 = {}.ADatePicker;
/** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
// @ts-ignore
const __VLS_425 = __VLS_asFunctionalComponent(__VLS_424, new __VLS_424({
    value: (__VLS_ctx.filterForm.dischargeDate),
    placeholder: "请选择日期",
    ...{ class: "filter-date" },
}));
const __VLS_426 = __VLS_425({
    value: (__VLS_ctx.filterForm.dischargeDate),
    placeholder: "请选择日期",
    ...{ class: "filter-date" },
}, ...__VLS_functionalComponentArgsRest(__VLS_425));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-column" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_428 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_429 = __VLS_asFunctionalComponent(__VLS_428, new __VLS_428({
    value: (__VLS_ctx.filterForm.hospitalStatus),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}));
const __VLS_430 = __VLS_429({
    value: (__VLS_ctx.filterForm.hospitalStatus),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_429));
__VLS_431.slots.default;
const __VLS_432 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_433 = __VLS_asFunctionalComponent(__VLS_432, new __VLS_432({
    value: "inpatient",
}));
const __VLS_434 = __VLS_433({
    value: "inpatient",
}, ...__VLS_functionalComponentArgsRest(__VLS_433));
__VLS_435.slots.default;
var __VLS_435;
const __VLS_436 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_437 = __VLS_asFunctionalComponent(__VLS_436, new __VLS_436({
    value: "outpatient",
}));
const __VLS_438 = __VLS_437({
    value: "outpatient",
}, ...__VLS_functionalComponentArgsRest(__VLS_437));
__VLS_439.slots.default;
var __VLS_439;
var __VLS_431;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_440 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_441 = __VLS_asFunctionalComponent(__VLS_440, new __VLS_440({
    value: (__VLS_ctx.filterForm.dischargeDept),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}));
const __VLS_442 = __VLS_441({
    value: (__VLS_ctx.filterForm.dischargeDept),
    placeholder: "请选择",
    ...{ class: "filter-select" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_441));
__VLS_443.slots.default;
const __VLS_444 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_445 = __VLS_asFunctionalComponent(__VLS_444, new __VLS_444({
    value: "internal",
}));
const __VLS_446 = __VLS_445({
    value: "internal",
}, ...__VLS_functionalComponentArgsRest(__VLS_445));
__VLS_447.slots.default;
var __VLS_447;
const __VLS_448 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_449 = __VLS_asFunctionalComponent(__VLS_448, new __VLS_448({
    value: "surgery",
}));
const __VLS_450 = __VLS_449({
    value: "surgery",
}, ...__VLS_functionalComponentArgsRest(__VLS_449));
__VLS_451.slots.default;
var __VLS_451;
var __VLS_443;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "date-range-row" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "filter-label" },
});
const __VLS_452 = {}.ADatePicker;
/** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
// @ts-ignore
const __VLS_453 = __VLS_asFunctionalComponent(__VLS_452, new __VLS_452({
    value: (__VLS_ctx.filterForm.admissionStartDate),
    placeholder: "开始日期",
    ...{ class: "filter-date-range" },
}));
const __VLS_454 = __VLS_453({
    value: (__VLS_ctx.filterForm.admissionStartDate),
    placeholder: "开始日期",
    ...{ class: "filter-date-range" },
}, ...__VLS_functionalComponentArgsRest(__VLS_453));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "date-separator" },
});
const __VLS_456 = {}.ADatePicker;
/** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
// @ts-ignore
const __VLS_457 = __VLS_asFunctionalComponent(__VLS_456, new __VLS_456({
    value: (__VLS_ctx.filterForm.admissionEndDate),
    placeholder: "结束日期",
    ...{ class: "filter-date-range" },
}));
const __VLS_458 = __VLS_457({
    value: (__VLS_ctx.filterForm.admissionEndDate),
    placeholder: "结束日期",
    ...{ class: "filter-date-range" },
}, ...__VLS_functionalComponentArgsRest(__VLS_457));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "modal-footer" },
});
const __VLS_460 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_461 = __VLS_asFunctionalComponent(__VLS_460, new __VLS_460({
    ...{ 'onClick': {} },
    ...{ class: "cancel-btn" },
}));
const __VLS_462 = __VLS_461({
    ...{ 'onClick': {} },
    ...{ class: "cancel-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_461));
let __VLS_464;
let __VLS_465;
let __VLS_466;
const __VLS_467 = {
    onClick: (__VLS_ctx.handleCancel)
};
__VLS_463.slots.default;
var __VLS_463;
const __VLS_468 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_469 = __VLS_asFunctionalComponent(__VLS_468, new __VLS_468({
    ...{ 'onClick': {} },
    ...{ class: "reset-btn" },
}));
const __VLS_470 = __VLS_469({
    ...{ 'onClick': {} },
    ...{ class: "reset-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_469));
let __VLS_472;
let __VLS_473;
let __VLS_474;
const __VLS_475 = {
    onClick: (__VLS_ctx.handleReset)
};
__VLS_471.slots.default;
var __VLS_471;
const __VLS_476 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_477 = __VLS_asFunctionalComponent(__VLS_476, new __VLS_476({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "confirm-btn" },
}));
const __VLS_478 = __VLS_477({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "confirm-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_477));
let __VLS_480;
let __VLS_481;
let __VLS_482;
const __VLS_483 = {
    onClick: (__VLS_ctx.handleConfirm)
};
__VLS_479.slots.default;
var __VLS_479;
var __VLS_339;
/** @type {__VLS_StyleScopedClasses['running-records-page']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['items-end']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['items-end']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-40']} */ ;
/** @type {__VLS_StyleScopedClasses['w-64']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-40']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-80']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-filter-tag-compact']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-[160px]']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-red-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-tags-container']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['action-section']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['border-orange-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-orange-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-orange-700']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-orange-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['border-green-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-green-700']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-green-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-green-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-green-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-purple-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-purple-300']} */ ;
/** @type {__VLS_StyleScopedClasses['data-section']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-800']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-1']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-form-container']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-name-input']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-column']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-column']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-column']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['date-range-row']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date-range']} */ ;
/** @type {__VLS_StyleScopedClasses['date-separator']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-date-range']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['cancel-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['reset-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['confirm-btn']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            SearchOutlined: icons_vue_1.SearchOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            FilterOutlined: icons_vue_1.FilterOutlined,
            TagOutlined: icons_vue_1.TagOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            ClearOutlined: icons_vue_1.ClearOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            SendOutlined: icons_vue_1.SendOutlined,
            CheckOutlined: icons_vue_1.CheckOutlined,
            FileExcelOutlined: icons_vue_1.FileExcelOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            loading: loading,
            exportLoading: exportLoading,
            showFilterModal: showFilterModal,
            showColumnSettings: showColumnSettings,
            currentView: currentView,
            selectedRowKeys: selectedRowKeys,
            customTimeRange: customTimeRange,
            activeTab: activeTab,
            queryConditions: queryConditions,
            activeFilterConditions: activeFilterConditions,
            filterTemplates: filterTemplates,
            quickFilters: quickFilters,
            filterForm: filterForm,
            records: records,
            recordColumns: recordColumns,
            pagination: pagination,
            rowSelection: rowSelection,
            canBatchUrge: canBatchUrge,
            handleTimeRangeChange: handleTimeRangeChange,
            handleCustomTimeChange: handleCustomTimeChange,
            handleQuery: handleQuery,
            handleQuickFilter: handleQuickFilter,
            handleResetFilter: handleResetFilter,
            removeFilterCondition: removeFilterCondition,
            handleQuickFilterClick: handleQuickFilterClick,
            handleCancel: handleCancel,
            handleReset: handleReset,
            handleConfirm: handleConfirm,
            handleViewChange: handleViewChange,
            handleBatchUrge: handleBatchUrge,
            handleBatchRecheck: handleBatchRecheck,
            handleBatchPass: handleBatchPass,
            handleExportAll: handleExportAll,
            handleExportQCDetails: handleExportQCDetails,
            handleRefresh: handleRefresh,
            handleTableChange: handleTableChange,
            handleViewDetail: handleViewDetail,
            handleUrgeRecord: handleUrgeRecord,
            getAuditStatusColor: getAuditStatusColor,
            getAuditStatusText: getAuditStatusText,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
