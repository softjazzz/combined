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
import icons_vue_1 from '@ant-design/icons-vue';
import medical_records_1 from '@/types/medical-records';
const props = withDefaults(defineProps(), {
    loading: false
});
const emit = defineEmits();
// 状态
const loading = (0, vue_1.ref)(false);
const records = (0, vue_1.ref)(: any[]);
const selectedRowKeys = (0, vue_1.ref)(: any[]);
// 搜索参数
const searchParams = (0, vue_1.reactive)({
    keyword: '',
    filters: {
        department: undefined,
        status: undefined,
        record_type: undefined
    },
    sort: {
        field: 'created_at',
        order: 'desc'
    },
    pagination: {
        page: 1,
        pageSize: 20
    }
});
// 分页配置
const pagination = (0, vue_1.reactive)({
    page: 1,
    pageSize: 20,
    total: 0
});
// 科室列表
const departments = medical_records_1.DEPARTMENTS;
// 表格列配置
const columns = [
    {
        title: '患者信息',
        key: 'patient',
        width: 200,
        fixed: 'left'
    },
    {
        title: '科室',
        dataIndex: 'department',
        key: 'department',
        width: 120,
        filters: departments.map(dept => ({ text: dept, value: dept }))
    },
    {
        title: '记录类型',
        key: 'record_type',
        width: 100
    },
    {
        title: '状态',
        key: 'status',
        width: 100,
        filters: [
            { text: '待处理', value: 'pending' },
            { text: '分析中', value: 'analyzing' },
            { text: '已完成', value: 'completed' },
            { text: '失败', value: 'failed' }
        ]
    },
    {
        title: '质控评分',
        key: 'qc_score',
        width: 120,
        sorter: true
    },
    {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 160,
        sorter: true,
        render: (value) => new Date(value).toLocaleString('zh-CN')
    },
    {
        title: '操作',
        key: 'actions',
        width: 150,
        fixed: 'right'
    }
];
// 表格分页配置
const paginationConfig = (0, vue_1.computed)(() => ({
    current: pagination.page,
    pageSize: pagination.pageSize,
    total: pagination.total,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条记录`
}));
// 行选择配置
const rowSelection = (0, vue_1.computed)(() => ({
    selectedRowKeys: selectedRowKeys.value, onChange: (keys) => {
        selectedRowKeys.value = keys;
    },
    getCheckboxProps: (record) => ({
        disabled: record.status === 'analyzing'
    })
}));
// 处理搜索
const handleSearch = () => {
    searchParams.pagination.page = 1;
    emit('search', { ...searchParams });
};
// 处理筛选变化
const handleFilterChange = () => {
    handleSearch();
};
// 处理刷新
const handleRefresh = () => {
    emit('search', { ...searchParams });
};
// 处理表格变化
const handleTableChange = (pag, filters: any,  sorter: any) => {
    // 更新分页
    if (pag) {
        searchParams.pagination.page = pag.current;
        searchParams.pagination.pageSize = pag.pageSize;
    }
    // 更新排序
    if (sorter && sorter.field) {
        searchParams.sort = {
            field: sorter.field,
            order: sorter.order === 'ascend' ? 'asc' : 'desc'
        };
    }
    // 更新筛选
    if (filters) {
        Object.keys(filters).forEach(key => {
            if (filters[key]) {
                searchParams.filters[key] = filters[key][0];
            }
        });
    }
    emit('search', { ...searchParams });
};
// 处理批量操作
const handleBatchAction = ({ key }) => {
    const selectedRecords = records.value.filter(record => selectedRowKeys.value.includes(record.id));
    emit('batch-action', key, selectedRecords);
};
// 处理记录操作
const handleRecordAction = (action, record) => {
    emit('record-action', action, record);
};
// 获取状态颜色
const getStatusColor = (status) => {
    const colors = {
        pending: 'orange',
        analyzing: 'blue',
        completed: 'green',
        failed: 'red'
    };
    return colors[status] || 'default';
};
// 获取状态标签
const getStatusLabel = (status) => {
    const labels = {
        pending: '待处理',
        analyzing: '分析中',
        completed: '已完成',
        failed: '失败'
    };
    return labels[status] || status;
};
// 获取状态点样式
const getStatusDotClass = (status) => {
    const classes = {
        pending: 'bg-amber-400',
        analyzing: 'bg-blue-400 animate-pulse',
        completed: 'bg-emerald-400',
        failed: 'bg-red-400'
    };
    return classes[status] || 'bg-gray-400';
};
// 获取评分颜色
const getScoreColor = (score) => {
    if (score >= 90)
        return 'text-emerald-400';
    if (score >= 80)
        return 'text-blue-400';
    if (score >= 70)
        return 'text-amber-400';
    return 'text-red-400';
};
// 获取等级颜色
const getGradeColor = (grade) => {
    const colors = {
        A: 'green',
        B: 'blue',
        C: 'orange'
    };
    return colors[grade] || 'default';
};
// 获取记录类型颜色
const getRecordTypeColor = (type) => {
    const colors = {
        inpatient: 'blue',
        outpatient: 'green',
        emergency: 'red'
    };
    return colors[type] || 'default';
};
// 获取记录类型标签
const getRecordTypeLabel = (type) => {
    const labels = {
        inpatient: '住院',
        outpatient: '门诊',
        emergency: '急诊'
    };
    return labels[type] || type;
};
// 获取性别标签
const getGenderLabel = (gender) => {
    const labels = {
        M: '男',
        F: '女',
        U: '未知'
    };
    return labels[gender] || gender;
};
// 暴露方法给父组件
const __VLS_exposed = {
    refresh: handleRefresh,
    clearSelection: () => {
        selectedRowKeys.value = [];
    },
    updateRecords: (newRecords: any) => {
        records.value = newRecords;
    },
    updatePagination: (newPagination: any) => {
        Object.assign(pagination, newPagination);
    }
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    loading: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-records-table']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-records-table']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-records-table']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "record-list" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6 p-4 rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-col lg:flex-row gap-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex-1" },
});
const __VLS_0 = {}.AInputSearch;
/** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchParams.keyword),
    placeholder: "搜索患者姓名、科室或记录内容...",
    size: "large",
    ...{ class: "search-input" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchParams.keyword),
    placeholder: "搜索患者姓名、科室或记录内容...",
    size: "large",
    ...{ class: "search-input" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onSearch: (__VLS_ctx.handleSearch)
};
__VLS_3.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.SearchOutlined;
    /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ class: "text-slate-400" },
    }));
    const __VLS_10 = __VLS_9({
        ...{ class: "text-slate-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex gap-3" },
});
const __VLS_12 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchParams.filters.department),
    placeholder: "选择科室",
    size: "large",
    ...{ style: {} },
    allowClear: true,
    ...{ class: "filter-select" },
}));
const __VLS_14 = __VLS_13({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchParams.filters.department),
    placeholder: "选择科室",
    size: "large",
    ...{ style: {} },
    allowClear: true,
    ...{ class: "filter-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onChange: (__VLS_ctx.handleFilterChange)
};
__VLS_15.slots.default;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_20 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        key: (dept),
        value: (dept),
    }));
    const __VLS_22 = __VLS_21({
        key: (dept),
        value: (dept),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    (dept);
    var __VLS_23;
}
var __VLS_15;
const __VLS_24 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchParams.filters.status),
    placeholder: "记录状态",
    size: "large",
    ...{ style: {} },
    allowClear: true,
    ...{ class: "filter-select" },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchParams.filters.status),
    placeholder: "记录状态",
    size: "large",
    ...{ style: {} },
    allowClear: true,
    ...{ class: "filter-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onChange: (__VLS_ctx.handleFilterChange)
};
__VLS_27.slots.default;
const __VLS_32 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: "pending",
}));
const __VLS_34 = __VLS_33({
    value: "pending",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-2 h-2 rounded-full bg-amber-400" },
});
var __VLS_35;
const __VLS_36 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: "analyzing",
}));
const __VLS_38 = __VLS_37({
    value: "analyzing",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-2 h-2 rounded-full bg-blue-400" },
});
var __VLS_39;
const __VLS_40 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    value: "completed",
}));
const __VLS_42 = __VLS_41({
    value: "completed",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-2 h-2 rounded-full bg-emerald-400" },
});
var __VLS_43;
const __VLS_44 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    value: "failed",
}));
const __VLS_46 = __VLS_45({
    value: "failed",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-2 h-2 rounded-full bg-red-400" },
});
var __VLS_47;
var __VLS_27;
const __VLS_48 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchParams.filters.record_type),
    placeholder: "记录类型",
    size: "large",
    ...{ style: {} },
    allowClear: true,
    ...{ class: "filter-select" },
}));
const __VLS_50 = __VLS_49({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchParams.filters.record_type),
    placeholder: "记录类型",
    size: "large",
    ...{ style: {} },
    allowClear: true,
    ...{ class: "filter-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onChange: (__VLS_ctx.handleFilterChange)
};
__VLS_51.slots.default;
const __VLS_56 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    value: "inpatient",
}));
const __VLS_58 = __VLS_57({
    value: "inpatient",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
var __VLS_59;
const __VLS_60 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    value: "outpatient",
}));
const __VLS_62 = __VLS_61({
    value: "outpatient",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
var __VLS_63;
const __VLS_64 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    value: "emergency",
}));
const __VLS_66 = __VLS_65({
    value: "emergency",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
var __VLS_67;
var __VLS_51;
const __VLS_68 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    ...{ 'onClick': {} },
    size: "large",
    loading: (__VLS_ctx.loading),
    ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50" },
}));
const __VLS_70 = __VLS_69({
    ...{ 'onClick': {} },
    size: "large",
    loading: (__VLS_ctx.loading),
    ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
let __VLS_72;
let __VLS_73;
let __VLS_74;
const __VLS_75 = {
    onClick: (__VLS_ctx.handleRefresh)
};
__VLS_71.slots.default;
const __VLS_76 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({}));
const __VLS_78 = __VLS_77({}, ...__VLS_functionalComponentArgsRest(__VLS_77));
var __VLS_71;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-4 flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm font-normal text-slate-400 ml-2" },
});
(__VLS_ctx.pagination.total);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3" },
});
if (__VLS_ctx.selectedRowKeys.length > 0) {
    const __VLS_80 = {}.ADropdown;
    /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        trigger: (['click']),
    }));
    const __VLS_82 = __VLS_81({
        trigger: (['click']),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    const __VLS_84 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        size: "large",
        ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
    }));
    const __VLS_86 = __VLS_85({
        size: "large",
        ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    const __VLS_88 = {}.MoreOutlined;
    /** @type {[typeof __VLS_components.MoreOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
    const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
    (__VLS_ctx.selectedRowKeys.length);
    var __VLS_87;
    {
        const { overlay: __VLS_thisSlot } = __VLS_83.slots;
        const __VLS_92 = {}.AMenu;
        /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            ...{ 'onClick': {} },
        }));
        const __VLS_94 = __VLS_93({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        let __VLS_96;
        let __VLS_97;
        let __VLS_98;
        const __VLS_99 = {
            onClick: (__VLS_ctx.handleBatchAction)
        };
        __VLS_95.slots.default;
        const __VLS_100 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            key: "analyze",
        }));
        const __VLS_102 = __VLS_101({
            key: "analyze",
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        __VLS_103.slots.default;
        const __VLS_104 = {}.ThunderboltOutlined;
        /** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({}));
        const __VLS_106 = __VLS_105({}, ...__VLS_functionalComponentArgsRest(__VLS_105));
        var __VLS_103;
        const __VLS_108 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
            key: "export",
        }));
        const __VLS_110 = __VLS_109({
            key: "export",
        }, ...__VLS_functionalComponentArgsRest(__VLS_109));
        __VLS_111.slots.default;
        const __VLS_112 = {}.ExportOutlined;
        /** @type {[typeof __VLS_components.ExportOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
        const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
        var __VLS_111;
        const __VLS_116 = {}.AMenuDivider;
        /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
        const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
        const __VLS_120 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            key: "delete",
            ...{ class: "text-red-400" },
        }));
        const __VLS_122 = __VLS_121({
            key: "delete",
            ...{ class: "text-red-400" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        const __VLS_124 = {}.DeleteOutlined;
        /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
        const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
        var __VLS_123;
        var __VLS_95;
    }
    var __VLS_83;
}
const __VLS_128 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none" },
}));
const __VLS_130 = __VLS_129({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none" },
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
let __VLS_132;
let __VLS_133;
let __VLS_134;
const __VLS_135 = {
    onClick: (...[$event]) => {
        __VLS_ctx.$emit('create-record');
    }
};
__VLS_131.slots.default;
const __VLS_136 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({}));
const __VLS_138 = __VLS_137({}, ...__VLS_functionalComponentArgsRest(__VLS_137));
var __VLS_131;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 overflow-hidden" },
});
const __VLS_140 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.records),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.paginationConfig),
    rowSelection: (__VLS_ctx.rowSelection),
    scroll: ({ x: 1200 }),
    size: "middle",
    ...{ class: "medical-records-table" },
}));
const __VLS_142 = __VLS_141({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.records),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.paginationConfig),
    rowSelection: (__VLS_ctx.rowSelection),
    scroll: ({ x: 1200 }),
    size: "middle",
    ...{ class: "medical-records-table" },
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
let __VLS_144;
let __VLS_145;
let __VLS_146;
const __VLS_147 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_143.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_143.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'patient') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center gap-3" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-semibold" },
        });
        (record.patient_name.charAt(0));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "font-medium text-slate-100" },
        });
        (record.patient_name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-slate-400" },
        });
        (record.patient_age);
        (__VLS_ctx.getGenderLabel(record.patient_gender));
    }
    else if (column.key === 'status') {
        const __VLS_148 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
            color: (__VLS_ctx.getStatusColor(record.status)),
            ...{ class: "status-tag" },
        }));
        const __VLS_150 = __VLS_149({
            color: (__VLS_ctx.getStatusColor(record.status)),
            ...{ class: "status-tag" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_149));
        __VLS_151.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center gap-1" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "w-1.5 h-1.5 rounded-full" },
            ...{ class: (__VLS_ctx.getStatusDotClass(record.status)) },
        });
        (__VLS_ctx.getStatusLabel(record.status));
        var __VLS_151;
    }
    else if (column.key === 'qc_score') {
        if (record.qc_score !== null) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "flex items-center gap-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-lg font-bold" },
                ...{ class: (__VLS_ctx.getScoreColor(record.qc_score)) },
            });
            (record.qc_score);
            if (record.qc_grade) {
                const __VLS_152 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
                    color: (__VLS_ctx.getGradeColor(record.qc_grade)),
                    size: "small",
                }));
                const __VLS_154 = __VLS_153({
                    color: (__VLS_ctx.getGradeColor(record.qc_grade)),
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_153));
                __VLS_155.slots.default;
                (record.qc_grade);
                var __VLS_155;
            }
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-slate-400 text-sm" },
            });
        }
    }
    else if (column.key === 'record_type') {
        const __VLS_156 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
            color: (__VLS_ctx.getRecordTypeColor(record.record_type)),
        }));
        const __VLS_158 = __VLS_157({
            color: (__VLS_ctx.getRecordTypeColor(record.record_type)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_157));
        __VLS_159.slots.default;
        (__VLS_ctx.getRecordTypeLabel(record.record_type));
        var __VLS_159;
    }
    else if (column.key === 'actions') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center gap-2" },
        });
        const __VLS_160 = {}.ATooltip;
        /** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
        // @ts-ignore
        const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
            title: "查看详情",
        }));
        const __VLS_162 = __VLS_161({
            title: "查看详情",
        }, ...__VLS_functionalComponentArgsRest(__VLS_161));
        __VLS_163.slots.default;
        const __VLS_164 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
            ...{ 'onClick': {} },
            size: "small",
            type: "text",
            ...{ class: "text-blue-400 hover:text-blue-300" },
        }));
        const __VLS_166 = __VLS_165({
            ...{ 'onClick': {} },
            size: "small",
            type: "text",
            ...{ class: "text-blue-400 hover:text-blue-300" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_165));
        let __VLS_168;
        let __VLS_169;
        let __VLS_170;
        const __VLS_171 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'patient'))
                    return;
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'qc_score'))
                    return;
                if (!!(column.key === 'record_type'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.$emit('view-record', record);
            }
        };
        __VLS_167.slots.default;
        const __VLS_172 = {}.EyeOutlined;
        /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({}));
        const __VLS_174 = __VLS_173({}, ...__VLS_functionalComponentArgsRest(__VLS_173));
        var __VLS_167;
        var __VLS_163;
        const __VLS_176 = {}.ATooltip;
        /** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
            title: "编辑记录",
        }));
        const __VLS_178 = __VLS_177({
            title: "编辑记录",
        }, ...__VLS_functionalComponentArgsRest(__VLS_177));
        __VLS_179.slots.default;
        const __VLS_180 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
            ...{ 'onClick': {} },
            size: "small",
            type: "text",
            ...{ class: "text-emerald-400 hover:text-emerald-300" },
        }));
        const __VLS_182 = __VLS_181({
            ...{ 'onClick': {} },
            size: "small",
            type: "text",
            ...{ class: "text-emerald-400 hover:text-emerald-300" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_181));
        let __VLS_184;
        let __VLS_185;
        let __VLS_186;
        const __VLS_187 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'patient'))
                    return;
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'qc_score'))
                    return;
                if (!!(column.key === 'record_type'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.$emit('edit-record', record);
            }
        };
        __VLS_183.slots.default;
        const __VLS_188 = {}.EditOutlined;
        /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({}));
        const __VLS_190 = __VLS_189({}, ...__VLS_functionalComponentArgsRest(__VLS_189));
        var __VLS_183;
        var __VLS_179;
        if (record.status === 'pending') {
            const __VLS_192 = {}.ATooltip;
            /** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
            // @ts-ignore
            const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
                title: "质控分析",
            }));
            const __VLS_194 = __VLS_193({
                title: "质控分析",
            }, ...__VLS_functionalComponentArgsRest(__VLS_193));
            __VLS_195.slots.default;
            const __VLS_196 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
                ...{ 'onClick': {} },
                size: "small",
                type: "text",
                ...{ class: "text-amber-400 hover:text-amber-300" },
            }));
            const __VLS_198 = __VLS_197({
                ...{ 'onClick': {} },
                size: "small",
                type: "text",
                ...{ class: "text-amber-400 hover:text-amber-300" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_197));
            let __VLS_200;
            let __VLS_201;
            let __VLS_202;
            const __VLS_203 = {
                onClick: (...[$event]) => {
                    if (!!(column.key === 'patient'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'qc_score'))
                        return;
                    if (!!(column.key === 'record_type'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    if (!(record.status === 'pending'))
                        return;
                    __VLS_ctx.$emit('analyze-record', record);
                }
            };
            __VLS_199.slots.default;
            const __VLS_204 = {}.ThunderboltOutlined;
            /** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({}));
            const __VLS_206 = __VLS_205({}, ...__VLS_functionalComponentArgsRest(__VLS_205));
            var __VLS_199;
            var __VLS_195;
        }
        const __VLS_208 = {}.ADropdown;
        /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
        // @ts-ignore
        const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
            trigger: (['click']),
        }));
        const __VLS_210 = __VLS_209({
            trigger: (['click']),
        }, ...__VLS_functionalComponentArgsRest(__VLS_209));
        __VLS_211.slots.default;
        const __VLS_212 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
            size: "small",
            type: "text",
            ...{ class: "text-slate-400 hover:text-slate-300" },
        }));
        const __VLS_214 = __VLS_213({
            size: "small",
            type: "text",
            ...{ class: "text-slate-400 hover:text-slate-300" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_213));
        __VLS_215.slots.default;
        const __VLS_216 = {}.MoreOutlined;
        /** @type {[typeof __VLS_components.MoreOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({}));
        const __VLS_218 = __VLS_217({}, ...__VLS_functionalComponentArgsRest(__VLS_217));
        var __VLS_215;
        {
            const { overlay: __VLS_thisSlot } = __VLS_211.slots;
            const __VLS_220 = {}.AMenu;
            /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
            // @ts-ignore
            const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
                ...{ 'onClick': {} },
            }));
            const __VLS_222 = __VLS_221({
                ...{ 'onClick': {} },
            }, ...__VLS_functionalComponentArgsRest(__VLS_221));
            let __VLS_224;
            let __VLS_225;
            let __VLS_226;
            const __VLS_227 = { onClick: (({ key   }) => __VLS_ctx.handleRecordAction(key, record))
            };
            __VLS_223.slots.default;
            if (record.file_url) {
                const __VLS_228 = {}.AMenuItem;
                /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
                // @ts-ignore
                const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
                    key: "download",
                }));
                const __VLS_230 = __VLS_229({
                    key: "download",
                }, ...__VLS_functionalComponentArgsRest(__VLS_229));
                __VLS_231.slots.default;
                const __VLS_232 = {}.DownloadOutlined;
                /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({}));
                const __VLS_234 = __VLS_233({}, ...__VLS_functionalComponentArgsRest(__VLS_233));
                var __VLS_231;
            }
            const __VLS_236 = {}.AMenuItem;
            /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
            // @ts-ignore
            const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
                key: "duplicate",
            }));
            const __VLS_238 = __VLS_237({
                key: "duplicate",
            }, ...__VLS_functionalComponentArgsRest(__VLS_237));
            __VLS_239.slots.default;
            const __VLS_240 = {}.CopyOutlined;
            /** @type {[typeof __VLS_components.CopyOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({}));
            const __VLS_242 = __VLS_241({}, ...__VLS_functionalComponentArgsRest(__VLS_241));
            var __VLS_239;
            const __VLS_244 = {}.AMenuDivider;
            /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
            // @ts-ignore
            const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({}));
            const __VLS_246 = __VLS_245({}, ...__VLS_functionalComponentArgsRest(__VLS_245));
            const __VLS_248 = {}.AMenuItem;
            /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
            // @ts-ignore
            const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
                key: "delete",
                ...{ class: "text-red-400" },
            }));
            const __VLS_250 = __VLS_249({
                key: "delete",
                ...{ class: "text-red-400" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_249));
            __VLS_251.slots.default;
            const __VLS_252 = {}.DeleteOutlined;
            /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({}));
            const __VLS_254 = __VLS_253({}, ...__VLS_functionalComponentArgsRest(__VLS_253));
            var __VLS_251;
            var __VLS_223;
        }
        var __VLS_211;
    }
}
var __VLS_143;
/** @type {__VLS_StyleScopedClasses['record-list']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:flex-row']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-amber-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-normal']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-r']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-500']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:to-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-none']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-records-table']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-10']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['status-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['h-1.5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-amber-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            SearchOutlined: icons_vue_1.SearchOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            MoreOutlined: icons_vue_1.MoreOutlined,
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            ExportOutlined: icons_vue_1.ExportOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            CopyOutlined: icons_vue_1.CopyOutlined,
            loading: loading,
            records: records,
            selectedRowKeys: selectedRowKeys,
            searchParams: searchParams,
            pagination: pagination,
            departments: departments,
            columns: columns,
            paginationConfig: paginationConfig,
            rowSelection: rowSelection,
            handleSearch: handleSearch,
            handleFilterChange: handleFilterChange,
            handleRefresh: handleRefresh,
            handleTableChange: handleTableChange,
            handleBatchAction: handleBatchAction,
            handleRecordAction: handleRecordAction,
            getStatusColor: getStatusColor,
            getStatusLabel: getStatusLabel,
            getStatusDotClass: getStatusDotClass,
            getScoreColor: getScoreColor,
            getGradeColor: getGradeColor,
            getRecordTypeColor: getRecordTypeColor,
            getRecordTypeLabel: getRecordTypeLabel,
            getGenderLabel: getGenderLabel,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ...__VLS_exposed,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
