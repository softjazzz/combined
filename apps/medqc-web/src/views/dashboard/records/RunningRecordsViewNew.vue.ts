"use strict";
/// <reference types="../../../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
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
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-breadcrumb-link']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['action-section']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['title-container']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb-container']} */ ;
/** @type {__VLS_StyleScopedClasses['title-container']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['action-section']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "running-records-page bg-gray-50 min-h-screen" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header bg-white border-b border-gray-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "breadcrumb-container px-6 py-3 bg-gray-50 border-b border-gray-100" },
});
const __VLS_0 = {}.ABreadcrumb;
/** @type {[typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-sm" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.HomeOutlined;
/** @type {[typeof __VLS_components.HomeOutlined, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ class: "mr-1" },
}));
const __VLS_10 = __VLS_9({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
const __VLS_12 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    to: "/dashboard",
    ...{ class: "text-gray-600 hover:text-blue-600" },
}));
const __VLS_14 = __VLS_13({
    to: "/dashboard",
    ...{ class: "text-gray-600 hover:text-blue-600" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
var __VLS_7;
const __VLS_16 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
const __VLS_20 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ class: "mr-1" },
}));
const __VLS_22 = __VLS_21({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_19;
const __VLS_24 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.PlayCircleOutlined;
/** @type {[typeof __VLS_components.PlayCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ class: "mr-1" },
}));
const __VLS_30 = __VLS_29({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-900 font-medium" },
});
var __VLS_27;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "title-container px-6 py-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center mr-3" },
});
const __VLS_32 = {}.PlayCircleOutlined;
/** @type {[typeof __VLS_components.PlayCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ class: "text-blue-600 text-lg" },
}));
const __VLS_34 = __VLS_33({
    ...{ class: "text-blue-600 text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-xl font-semibold text-gray-900 mb-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-sm text-gray-500 mt-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-2" },
});
const __VLS_36 = {}.ABadge;
/** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    count: (12),
    offset: ([10, 0]),
}));
const __VLS_38 = __VLS_37({
    count: (12),
    offset: ([10, 0]),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
const __VLS_40 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    type: "text",
    size: "small",
    ...{ class: "text-gray-500" },
}));
const __VLS_42 = __VLS_41({
    type: "text",
    size: "small",
    ...{ class: "text-gray-500" },
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
const __VLS_44 = {}.BellOutlined;
/** @type {[typeof __VLS_components.BellOutlined, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
var __VLS_43;
var __VLS_39;
const __VLS_48 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    type: "text",
    size: "small",
    ...{ class: "text-gray-500" },
}));
const __VLS_50 = __VLS_49({
    type: "text",
    size: "small",
    ...{ class: "text-gray-500" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.QuestionCircleOutlined;
/** @type {[typeof __VLS_components.QuestionCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
var __VLS_51;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-container p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-lg shadow-sm border border-gray-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-section px-6 py-4 border-b border-gray-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 lg:grid-cols-3 gap-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-gray-700 mb-2" },
});
const __VLS_56 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.timeRange),
    placeholder: "选择时间周期",
    ...{ class: "w-full" },
    size: "middle",
}));
const __VLS_58 = __VLS_57({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.timeRange),
    placeholder: "选择时间周期",
    ...{ class: "w-full" },
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onChange: (__VLS_ctx.handleTimeRangeChange)
};
__VLS_59.slots.default;
const __VLS_64 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    value: "all",
}));
const __VLS_66 = __VLS_65({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
var __VLS_67;
const __VLS_68 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    value: "recent7",
}));
const __VLS_70 = __VLS_69({
    value: "recent7",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
var __VLS_71;
const __VLS_72 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    value: "month",
}));
const __VLS_74 = __VLS_73({
    value: "month",
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
var __VLS_75;
const __VLS_76 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    value: "quarter",
}));
const __VLS_78 = __VLS_77({
    value: "quarter",
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
var __VLS_79;
const __VLS_80 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    value: "year",
}));
const __VLS_82 = __VLS_81({
    value: "year",
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
var __VLS_83;
const __VLS_84 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    value: "custom",
}));
const __VLS_86 = __VLS_85({
    value: "custom",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
var __VLS_87;
var __VLS_59;
if (__VLS_ctx.queryConditions.timeRange === 'custom') {
    const __VLS_88 = {}.ARangePicker;
    /** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.customTimeRange),
        ...{ class: "w-full mt-2" },
        size: "middle",
    }));
    const __VLS_90 = __VLS_89({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.customTimeRange),
        ...{ class: "w-full mt-2" },
        size: "middle",
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    let __VLS_92;
    let __VLS_93;
    let __VLS_94;
    const __VLS_95 = {
        onChange: (__VLS_ctx.handleCustomTimeChange)
    };
    var __VLS_91;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-gray-700 mb-2" },
});
const __VLS_96 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.scoringStandard),
    placeholder: "选择评分标准",
    ...{ class: "w-full" },
    size: "middle",
}));
const __VLS_98 = __VLS_97({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.queryConditions.scoringStandard),
    placeholder: "选择评分标准",
    ...{ class: "w-full" },
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
let __VLS_100;
let __VLS_101;
let __VLS_102;
const __VLS_103 = {
    onChange: (__VLS_ctx.handleQuery)
};
__VLS_99.slots.default;
const __VLS_104 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    value: "all",
}));
const __VLS_106 = __VLS_105({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
__VLS_107.slots.default;
var __VLS_107;
const __VLS_108 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    value: "standard1",
}));
const __VLS_110 = __VLS_109({
    value: "standard1",
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
var __VLS_111;
const __VLS_112 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    value: "standard2",
}));
const __VLS_114 = __VLS_113({
    value: "standard2",
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
var __VLS_115;
const __VLS_116 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    value: "standard3",
}));
const __VLS_118 = __VLS_117({
    value: "standard3",
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
var __VLS_119;
var __VLS_99;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "query-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-gray-700 mb-2" },
});
const __VLS_120 = {}.AInputGroup;
/** @type {[typeof __VLS_components.AInputGroup, typeof __VLS_components.aInputGroup, typeof __VLS_components.AInputGroup, typeof __VLS_components.aInputGroup, ]} */ ;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
    compact: true,
}));
const __VLS_122 = __VLS_121({
    compact: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_121));
__VLS_123.slots.default;
const __VLS_124 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    value: (__VLS_ctx.queryConditions.searchType),
    ...{ style: {} },
    size: "middle",
}));
const __VLS_126 = __VLS_125({
    value: (__VLS_ctx.queryConditions.searchType),
    ...{ style: {} },
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
const __VLS_128 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    value: "registrationNo",
}));
const __VLS_130 = __VLS_129({
    value: "registrationNo",
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
var __VLS_131;
const __VLS_132 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
    value: "serialNo",
}));
const __VLS_134 = __VLS_133({
    value: "serialNo",
}, ...__VLS_functionalComponentArgsRest(__VLS_133));
__VLS_135.slots.default;
var __VLS_135;
const __VLS_136 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    value: "caseNo",
}));
const __VLS_138 = __VLS_137({
    value: "caseNo",
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
__VLS_139.slots.default;
var __VLS_139;
const __VLS_140 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    value: "patientName",
}));
const __VLS_142 = __VLS_141({
    value: "patientName",
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
__VLS_143.slots.default;
var __VLS_143;
const __VLS_144 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
    value: "doctorName",
}));
const __VLS_146 = __VLS_145({
    value: "doctorName",
}, ...__VLS_functionalComponentArgsRest(__VLS_145));
__VLS_147.slots.default;
var __VLS_147;
var __VLS_127;
const __VLS_148 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.queryConditions.searchValue),
    ...{ style: {} },
    placeholder: "输入查询内容",
    size: "middle",
}));
const __VLS_150 = __VLS_149({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.queryConditions.searchValue),
    ...{ style: {} },
    placeholder: "输入查询内容",
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
let __VLS_152;
let __VLS_153;
let __VLS_154;
const __VLS_155 = {
    onPressEnter: (__VLS_ctx.handleQuery)
};
__VLS_151.slots.default;
{
    const { suffix: __VLS_thisSlot } = __VLS_151.slots;
    const __VLS_156 = {}.SearchOutlined;
    /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        ...{ 'onClick': {} },
        ...{ class: "cursor-pointer text-gray-400 hover:text-blue-500" },
    }));
    const __VLS_158 = __VLS_157({
        ...{ 'onClick': {} },
        ...{ class: "cursor-pointer text-gray-400 hover:text-blue-500" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    let __VLS_160;
    let __VLS_161;
    let __VLS_162;
    const __VLS_163 = {
        onClick: (__VLS_ctx.handleQuery)
    };
    var __VLS_159;
}
var __VLS_151;
var __VLS_123;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-section px-6 py-4 bg-gray-50 border-b border-gray-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm font-medium text-gray-700" },
});
const __VLS_164 = {}.ADropdown;
/** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    placement: "bottomLeft",
}));
const __VLS_166 = __VLS_165({
    placement: "bottomLeft",
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
__VLS_167.slots.default;
const __VLS_168 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}));
const __VLS_170 = __VLS_169({
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
const __VLS_172 = {}.FilterOutlined;
/** @type {[typeof __VLS_components.FilterOutlined, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    ...{ class: "mr-1" },
}));
const __VLS_174 = __VLS_173({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
const __VLS_176 = {}.DownOutlined;
/** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
    ...{ class: "ml-1 text-xs" },
}));
const __VLS_178 = __VLS_177({
    ...{ class: "ml-1 text-xs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_177));
var __VLS_171;
{
    const { overlay: __VLS_thisSlot } = __VLS_167.slots;
    const __VLS_180 = {}.AMenu;
    /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        ...{ 'onClick': {} },
        ...{ class: "min-w-[160px]" },
    }));
    const __VLS_182 = __VLS_181({
        ...{ 'onClick': {} },
        ...{ class: "min-w-[160px]" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    let __VLS_184;
    let __VLS_185;
    let __VLS_186;
    const __VLS_187 = {
        onClick: (__VLS_ctx.handleQuickFilter)
    };
    __VLS_183.slots.default;
    for (const [template] of __VLS_getVForSourceType((__VLS_ctx.filterTemplates))) {
        const __VLS_188 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
            key: (template.id),
            ...{ class: "text-sm" },
        }));
        const __VLS_190 = __VLS_189({
            key: (template.id),
            ...{ class: "text-sm" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_189));
        __VLS_191.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_191.slots;
            const __VLS_192 = {}.TagOutlined;
            /** @type {[typeof __VLS_components.TagOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
                ...{ class: "text-xs" },
            }));
            const __VLS_194 = __VLS_193({
                ...{ class: "text-xs" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_193));
        }
        (template.name);
        var __VLS_191;
    }
    var __VLS_183;
}
var __VLS_167;
const __VLS_196 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    ...{ 'onClick': {} },
    size: "small",
    type: "primary",
    ...{ class: "bg-blue-600 border-blue-600" },
}));
const __VLS_198 = __VLS_197({
    ...{ 'onClick': {} },
    size: "small",
    type: "primary",
    ...{ class: "bg-blue-600 border-blue-600" },
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
let __VLS_200;
let __VLS_201;
let __VLS_202;
const __VLS_203 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showFilterModal = true;
    }
};
__VLS_199.slots.default;
const __VLS_204 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
    ...{ class: "mr-1" },
}));
const __VLS_206 = __VLS_205({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_205));
var __VLS_199;
const __VLS_208 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}));
const __VLS_210 = __VLS_209({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_209));
let __VLS_212;
let __VLS_213;
let __VLS_214;
const __VLS_215 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showFilterModal = true;
    }
};
__VLS_211.slots.default;
const __VLS_216 = {}.EditOutlined;
/** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
// @ts-ignore
const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
    ...{ class: "mr-1" },
}));
const __VLS_218 = __VLS_217({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_217));
var __VLS_211;
const __VLS_220 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-red-600 hover:border-red-300" },
}));
const __VLS_222 = __VLS_221({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-red-600 hover:border-red-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_221));
let __VLS_224;
let __VLS_225;
let __VLS_226;
const __VLS_227 = {
    onClick: (__VLS_ctx.handleResetFilter)
};
__VLS_223.slots.default;
const __VLS_228 = {}.ClearOutlined;
/** @type {[typeof __VLS_components.ClearOutlined, ]} */ ;
// @ts-ignore
const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
    ...{ class: "mr-1" },
}));
const __VLS_230 = __VLS_229({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_229));
var __VLS_223;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm text-gray-500" },
});
(__VLS_ctx.currentView === 'defects' ? '缺陷列表' : '病历列表');
const __VLS_232 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
    ...{ 'onChange': {} },
    checked: (__VLS_ctx.currentView),
    checkedValue: "records",
    unCheckedValue: "defects",
    size: "small",
}));
const __VLS_234 = __VLS_233({
    ...{ 'onChange': {} },
    checked: (__VLS_ctx.currentView),
    checkedValue: "records",
    unCheckedValue: "defects",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_233));
let __VLS_236;
let __VLS_237;
let __VLS_238;
const __VLS_239 = {
    onChange: (__VLS_ctx.handleViewChange)
};
__VLS_235.slots.default;
{
    const { checkedChildren: __VLS_thisSlot } = __VLS_235.slots;
    const __VLS_240 = {}.FileTextOutlined;
    /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
        ...{ class: "text-xs" },
    }));
    const __VLS_242 = __VLS_241({
        ...{ class: "text-xs" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_241));
}
{
    const { unCheckedChildren: __VLS_thisSlot } = __VLS_235.slots;
    const __VLS_244 = {}.ExclamationCircleOutlined;
    /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
        ...{ class: "text-xs" },
    }));
    const __VLS_246 = __VLS_245({
        ...{ class: "text-xs" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_245));
}
var __VLS_235;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-tags-container" },
});
if (__VLS_ctx.activeFilterConditions.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex flex-wrap gap-2" },
    });
    for (const [condition, index] of __VLS_getVForSourceType((__VLS_ctx.activeFilterConditions))) {
        const __VLS_248 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
            ...{ 'onClose': {} },
            key: (index),
            closable: true,
            color: "blue",
            ...{ class: "px-2 py-1 text-xs" },
        }));
        const __VLS_250 = __VLS_249({
            ...{ 'onClose': {} },
            key: (index),
            closable: true,
            color: "blue",
            ...{ class: "px-2 py-1 text-xs" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_249));
        let __VLS_252;
        let __VLS_253;
        let __VLS_254;
        const __VLS_255 = {
            onClose: (...[$event]) => {
                if (!(__VLS_ctx.activeFilterConditions.length > 0))
                    return;
                __VLS_ctx.removeFilterCondition(index);
            }
        };
        __VLS_251.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "font-medium" },
        });
        (condition.label);
        (condition.value);
        var __VLS_251;
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
    const __VLS_256 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
        type: "vertical",
        ...{ class: "mx-2" },
    }));
    const __VLS_258 = __VLS_257({
        type: "vertical",
        ...{ class: "mx-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_257));
}
if (__VLS_ctx.selectedRowKeys.length > 0) {
    const __VLS_260 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
        ...{ 'onClick': {} },
        type: "primary",
        size: "small",
        disabled: (!__VLS_ctx.canBatchUrge),
        ...{ class: "bg-blue-600 border-blue-600" },
    }));
    const __VLS_262 = __VLS_261({
        ...{ 'onClick': {} },
        type: "primary",
        size: "small",
        disabled: (!__VLS_ctx.canBatchUrge),
        ...{ class: "bg-blue-600 border-blue-600" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_261));
    let __VLS_264;
    let __VLS_265;
    let __VLS_266;
    const __VLS_267 = {
        onClick: (__VLS_ctx.handleBatchUrge)
    };
    __VLS_263.slots.default;
    const __VLS_268 = {}.SendOutlined;
    /** @type {[typeof __VLS_components.SendOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
        ...{ class: "mr-1" },
    }));
    const __VLS_270 = __VLS_269({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_269));
    (__VLS_ctx.selectedRowKeys.length);
    var __VLS_263;
}
if (__VLS_ctx.selectedRowKeys.length > 0 && __VLS_ctx.currentView === 'records') {
    const __VLS_272 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-orange-300 text-orange-600 hover:text-orange-700 hover:border-orange-400" },
    }));
    const __VLS_274 = __VLS_273({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-orange-300 text-orange-600 hover:text-orange-700 hover:border-orange-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_273));
    let __VLS_276;
    let __VLS_277;
    let __VLS_278;
    const __VLS_279 = {
        onClick: (__VLS_ctx.handleBatchRecheck)
    };
    __VLS_275.slots.default;
    const __VLS_280 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
        ...{ class: "mr-1" },
    }));
    const __VLS_282 = __VLS_281({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_281));
    var __VLS_275;
}
if (__VLS_ctx.selectedRowKeys.length > 0 && __VLS_ctx.currentView === 'records') {
    const __VLS_284 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-green-300 text-green-600 hover:text-green-700 hover:border-green-400" },
    }));
    const __VLS_286 = __VLS_285({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "border-green-300 text-green-600 hover:text-green-700 hover:border-green-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_285));
    let __VLS_288;
    let __VLS_289;
    let __VLS_290;
    const __VLS_291 = {
        onClick: (__VLS_ctx.handleBatchPass)
    };
    __VLS_287.slots.default;
    const __VLS_292 = {}.CheckOutlined;
    /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
        ...{ class: "mr-1" },
    }));
    const __VLS_294 = __VLS_293({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_293));
    var __VLS_287;
}
if (__VLS_ctx.selectedRowKeys.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-gray-400" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-2" },
});
const __VLS_296 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.exportLoading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}));
const __VLS_298 = __VLS_297({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.exportLoading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_297));
let __VLS_300;
let __VLS_301;
let __VLS_302;
const __VLS_303 = {
    onClick: (__VLS_ctx.handleExportAll)
};
__VLS_299.slots.default;
const __VLS_304 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
    ...{ class: "mr-1" },
}));
const __VLS_306 = __VLS_305({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_305));
var __VLS_299;
if (__VLS_ctx.currentView === 'records') {
    const __VLS_308 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({
        ...{ 'onClick': {} },
        size: "small",
        loading: (__VLS_ctx.exportLoading),
        ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
    }));
    const __VLS_310 = __VLS_309({
        ...{ 'onClick': {} },
        size: "small",
        loading: (__VLS_ctx.exportLoading),
        ...{ class: "border-gray-300 text-gray-600 hover:text-blue-600 hover:border-blue-300" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_309));
    let __VLS_312;
    let __VLS_313;
    let __VLS_314;
    const __VLS_315 = {
        onClick: (__VLS_ctx.handleExportQCDetails)
    };
    __VLS_311.slots.default;
    const __VLS_316 = {}.FileExcelOutlined;
    /** @type {[typeof __VLS_components.FileExcelOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
        ...{ class: "mr-1" },
    }));
    const __VLS_318 = __VLS_317({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_317));
    var __VLS_311;
}
const __VLS_320 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.loading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-green-600 hover:border-green-300" },
}));
const __VLS_322 = __VLS_321({
    ...{ 'onClick': {} },
    size: "small",
    loading: (__VLS_ctx.loading),
    ...{ class: "border-gray-300 text-gray-600 hover:text-green-600 hover:border-green-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_321));
let __VLS_324;
let __VLS_325;
let __VLS_326;
const __VLS_327 = {
    onClick: (__VLS_ctx.handleRefresh)
};
__VLS_323.slots.default;
const __VLS_328 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
    ...{ class: "mr-1" },
}));
const __VLS_330 = __VLS_329({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_329));
var __VLS_323;
const __VLS_332 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-purple-600 hover:border-purple-300" },
}));
const __VLS_334 = __VLS_333({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "border-gray-300 text-gray-600 hover:text-purple-600 hover:border-purple-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_333));
let __VLS_336;
let __VLS_337;
let __VLS_338;
const __VLS_339 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showColumnSettings = true;
    }
};
__VLS_335.slots.default;
const __VLS_340 = {}.SettingOutlined;
/** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
// @ts-ignore
const __VLS_341 = __VLS_asFunctionalComponent(__VLS_340, new __VLS_340({}));
const __VLS_342 = __VLS_341({}, ...__VLS_functionalComponentArgsRest(__VLS_341));
var __VLS_335;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "data-section p-6" },
});
const __VLS_344 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.recordColumns),
    dataSource: (__VLS_ctx.records),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    size: "small",
}));
const __VLS_346 = __VLS_345({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.recordColumns),
    dataSource: (__VLS_ctx.records),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_345));
let __VLS_348;
let __VLS_349;
let __VLS_350;
const __VLS_351 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_347.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_347.slots;
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
        const __VLS_352 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({
            color: (__VLS_ctx.getAuditStatusColor(record.auditStatus)),
        }));
        const __VLS_354 = __VLS_353({
            color: (__VLS_ctx.getAuditStatusColor(record.auditStatus)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_353));
        __VLS_355.slots.default;
        (__VLS_ctx.getAuditStatusText(record.auditStatus));
        var __VLS_355;
    }
    if (column.key === 'action') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex space-x-1" },
        });
        const __VLS_356 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_357 = __VLS_asFunctionalComponent(__VLS_356, new __VLS_356({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_358 = __VLS_357({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_357));
        let __VLS_360;
        let __VLS_361;
        let __VLS_362;
        const __VLS_363 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleViewDetail(record);
            }
        };
        __VLS_359.slots.default;
        var __VLS_359;
        if (!record.isUrgent) {
            const __VLS_364 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_366 = __VLS_365({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_365));
            let __VLS_368;
            let __VLS_369;
            let __VLS_370;
            const __VLS_371 = {
                onClick: (...[$event]) => {
                    if (!(column.key === 'action'))
                        return;
                    if (!(!record.isUrgent))
                        return;
                    __VLS_ctx.handleUrgeRecord(record);
                }
            };
            __VLS_367.slots.default;
            var __VLS_367;
        }
    }
}
var __VLS_347;
/** @type {__VLS_StyleScopedClasses['running-records-page']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb-container']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['title-container']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['query-section']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['query-item']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-section']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
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
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            SearchOutlined: icons_vue_1.SearchOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            HomeOutlined: icons_vue_1.HomeOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            PlayCircleOutlined: icons_vue_1.PlayCircleOutlined,
            BellOutlined: icons_vue_1.BellOutlined,
            QuestionCircleOutlined: icons_vue_1.QuestionCircleOutlined,
            FilterOutlined: icons_vue_1.FilterOutlined,
            TagOutlined: icons_vue_1.TagOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            ClearOutlined: icons_vue_1.ClearOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            SendOutlined: icons_vue_1.SendOutlined,
            CheckOutlined: icons_vue_1.CheckOutlined,
            FileExcelOutlined: icons_vue_1.FileExcelOutlined,
            loading: loading,
            exportLoading: exportLoading,
            showFilterModal: showFilterModal,
            showColumnSettings: showColumnSettings,
            currentView: currentView,
            selectedRowKeys: selectedRowKeys,
            customTimeRange: customTimeRange,
            queryConditions: queryConditions,
            activeFilterConditions: activeFilterConditions,
            filterTemplates: filterTemplates,
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
