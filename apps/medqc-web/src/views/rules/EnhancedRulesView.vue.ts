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
const showCreateModal = (0, vue_1.ref)(false);
const editingRule = (0, vue_1.ref)(null);
// 引擎状态
const engineStatus = (0, vue_1.reactive)({
    status: 'healthy',
    activeRules: 156,
    executionCount: 2847,
    avgResponseTime: 125
});
// 过滤器
const filters = (0, vue_1.reactive)({
    category: undefined,
    status: undefined,
    keyword: ''
});
// 规则表单
const ruleForm = (0, vue_1.reactive)({
    name: '',
    category: '',
    description: '',
    priority: 'medium',
    status: 'active',
    conditions: ''
});
// 表单验证规则
const ruleFormRules = {
    name: [{ required: true, message: '请输入规则名称' }],
    category: [{ required: true, message: '请选择规则类别' }],
    description: [{ required: true, message: '请输入规则描述' }]
};
// 模拟规则数据
const rules = (0, vue_1.ref)([
    {
        id: '1',
        name: '病历完整性检查',
        category: 'completeness',
        description: '检查病历必填字段是否完整',
        priority: 'high',
        status: 'active',
        createdAt: '2024-01-15',
        updatedAt: '2024-01-20'
    },
    {
        id: '2',
        name: '诊断一致性验证',
        category: 'consistency',
        description: '验证主诊断与辅助检查结果的一致性',
        priority: 'high',
        status: 'active',
        createdAt: '2024-01-16',
        updatedAt: '2024-01-21'
    },
    {
        id: '3',
        name: '用药合理性检查',
        category: 'accuracy',
        description: '检查用药剂量和配伍的合理性',
        priority: 'medium',
        status: 'active',
        createdAt: '2024-01-17',
        updatedAt: '2024-01-22'
    }
]);
// 表格列配置
const rulesColumns = [
    { title: '规则名称', dataIndex: 'name', key: 'name' },
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '优先级', dataIndex: 'priority', key: 'priority' },
    { title: '状态', dataIndex: 'status', key: 'status' },
    { title: '更新时间', dataIndex: 'updatedAt', key: 'updatedAt' },
    { title: '操作', key: 'actions', width: 200 }
];
// 分页配置
const pagination = (0, vue_1.reactive)({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true
});
// 计算属性
const filteredRules = (0, vue_1.computed)(() => {
    let result = rules.value;
    if (filters.category) {
        result = result.filter(rule => rule.category === filters.category);
    }
    if (filters.status) {
        result = result.filter(rule => rule.status === filters.status);
    }
    if (filters.keyword) {
        result = result.filter(rule => rule.name.includes(filters.keyword) ||
            rule.description.includes(filters.keyword));
    }
    pagination.total = result.length;
    return result;
});
// 方法
const getCategoryColor = (category) => {
    const colors = {
        completeness: 'blue',
        consistency: 'green',
        timeliness: 'orange',
        accuracy: 'red'
    };
    return colors[category] || 'default';
};
const getCategoryName = (category) => {
    const names = {
        completeness: '完整性',
        consistency: '一致性',
        timeliness: '及时性',
        accuracy: '准确性'
    };
    return names[category] || category;
};
const getPriorityColor = (priority) => {
    const colors = {
        high: 'red',
        medium: 'orange',
        low: 'green'
    };
    return colors[priority] || 'default';
};
const handleFilterChange = () => {
    pagination.current = 1;
};
const handleTableChange = (pag) => {
    pagination.current = pag.current;
    pagination.pageSize = pag.pageSize;
};
const refreshRules = async () => {
    loading.value = true;
    try {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1000));
        ant_design_vue_1.message.success('规则列表已刷新');
    }
    catch (error) {
        ant_design_vue_1.message.error('刷新失败');
    }
    finally {
        loading.value = false;
    }
};
const toggleRuleStatus = async (rule, checked) => {
    try {
        rule.status = checked ? 'active' : 'inactive';
        ant_design_vue_1.message.success(`规则已${checked ? '启用' : '禁用'}`);
    }
    catch (error) {
        ant_design_vue_1.message.error('状态更新失败');
    }
};
const editRule = (rule) => {
    editingRule.value = rule;
    Object.assign(ruleForm, rule);
    showCreateModal.value = true;
};
const testRule = (rule) => {
    ant_design_vue_1.message.info(`正在测试规则: ${rule.name}`);
};
const deleteRule = async (rule) => {
    try {
        const index = rules.value.findIndex(r => r.id === rule.id);
        if (index > -1) {
            rules.value.splice(index, 1);
            ant_design_vue_1.message.success('规则已删除');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('删除失败');
    }
};
const handleSaveRule = async () => {
    try {
        if (editingRule.value) {
            // 编辑模式
            Object.assign(editingRule.value, ruleForm);
            ant_design_vue_1.message.success('规则已更新');
        }
        else {
            // 创建模式
            const newRule = {
                ...ruleForm,
                id: Date.now().toString(),
                createdAt: new Date().toISOString().split('T')[0],
                updatedAt: new Date().toISOString().split('T')[0]
            };
            rules.value.unshift(newRule);
            ant_design_vue_1.message.success('规则已创建');
        }
        handleCancelEdit();
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
};
const handleCancelEdit = () => {
    showCreateModal.value = false;
    editingRule.value = null;
    Object.assign(ruleForm, {
        name: '',
        category: '',
        description: '',
        priority: 'medium',
        status: 'active',
        conditions: ''
    });
};
// 生命周期
(0, vue_1.onMounted)(() => {
    refreshRules();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['status-value']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "enhanced-rules-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-wrapper" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "规则引擎状态",
    ...{ class: "status-card" },
    loading: (__VLS_ctx.loading),
}));
const __VLS_2 = __VLS_1({
    title: "规则引擎状态",
    ...{ class: "status-card" },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-grid" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-value" },
    ...{ class: (__VLS_ctx.engineStatus.status) },
});
const __VLS_4 = {}.ABadge;
/** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    status: (__VLS_ctx.engineStatus.status === 'healthy' ? 'success' : 'error'),
}));
const __VLS_6 = __VLS_5({
    status: (__VLS_ctx.engineStatus.status === 'healthy' ? 'success' : 'error'),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
(__VLS_ctx.engineStatus.status === 'healthy' ? '运行正常' : '异常');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-value" },
});
(__VLS_ctx.engineStatus.activeRules);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-value" },
});
(__VLS_ctx.engineStatus.executionCount);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-value" },
});
(__VLS_ctx.engineStatus.avgResponseTime);
var __VLS_3;
const __VLS_8 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    title: "规则管理",
    ...{ class: "rules-card" },
}));
const __VLS_10 = __VLS_9({
    title: "规则管理",
    ...{ class: "rules-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_11.slots;
    const __VLS_12 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    const __VLS_16 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_18 = __VLS_17({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    let __VLS_20;
    let __VLS_21;
    let __VLS_22;
    const __VLS_23 = {
        onClick: (...[$event]) => {
            __VLS_ctx.showCreateModal = true;
        }
    };
    __VLS_19.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_19.slots;
        const __VLS_24 = {}.PlusOutlined;
        /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
        const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
    }
    var __VLS_19;
    const __VLS_28 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        ...{ 'onClick': {} },
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_32;
    let __VLS_33;
    let __VLS_34;
    const __VLS_35 = {
        onClick: (__VLS_ctx.refreshRules)
    };
    __VLS_31.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_31.slots;
        const __VLS_36 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({}));
        const __VLS_38 = __VLS_37({}, ...__VLS_functionalComponentArgsRest(__VLS_37));
    }
    var __VLS_31;
    var __VLS_15;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rules-filters" },
});
const __VLS_40 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    gutter: (16),
}));
const __VLS_42 = __VLS_41({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
const __VLS_44 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    span: (6),
}));
const __VLS_46 = __VLS_45({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filters.category),
    placeholder: "规则类别",
    allowClear: true,
}));
const __VLS_50 = __VLS_49({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filters.category),
    placeholder: "规则类别",
    allowClear: true,
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
    value: "completeness",
}));
const __VLS_58 = __VLS_57({
    value: "completeness",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
var __VLS_59;
const __VLS_60 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    value: "consistency",
}));
const __VLS_62 = __VLS_61({
    value: "consistency",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
var __VLS_63;
const __VLS_64 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    value: "timeliness",
}));
const __VLS_66 = __VLS_65({
    value: "timeliness",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
var __VLS_67;
const __VLS_68 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    value: "accuracy",
}));
const __VLS_70 = __VLS_69({
    value: "accuracy",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
var __VLS_71;
var __VLS_51;
var __VLS_47;
const __VLS_72 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    span: (6),
}));
const __VLS_74 = __VLS_73({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
const __VLS_76 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filters.status),
    placeholder: "规则状态",
    allowClear: true,
}));
const __VLS_78 = __VLS_77({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.filters.status),
    placeholder: "规则状态",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
let __VLS_80;
let __VLS_81;
let __VLS_82;
const __VLS_83 = {
    onChange: (__VLS_ctx.handleFilterChange)
};
__VLS_79.slots.default;
const __VLS_84 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    value: "active",
}));
const __VLS_86 = __VLS_85({
    value: "active",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
var __VLS_87;
const __VLS_88 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    value: "inactive",
}));
const __VLS_90 = __VLS_89({
    value: "inactive",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
var __VLS_91;
var __VLS_79;
var __VLS_75;
const __VLS_92 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    span: (8),
}));
const __VLS_94 = __VLS_93({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
const __VLS_96 = {}.AInputSearch;
/** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.filters.keyword),
    placeholder: "搜索规则名称或描述",
}));
const __VLS_98 = __VLS_97({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.filters.keyword),
    placeholder: "搜索规则名称或描述",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
let __VLS_100;
let __VLS_101;
let __VLS_102;
const __VLS_103 = {
    onSearch: (__VLS_ctx.handleFilterChange)
};
var __VLS_99;
var __VLS_95;
var __VLS_43;
const __VLS_104 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.rulesColumns),
    dataSource: (__VLS_ctx.filteredRules),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
}));
const __VLS_106 = __VLS_105({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.rulesColumns),
    dataSource: (__VLS_ctx.filteredRules),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
let __VLS_108;
let __VLS_109;
let __VLS_110;
const __VLS_111 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_107.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_107.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'status') {
        const __VLS_112 = {}.ASwitch;
        /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            ...{ 'onChange': {} },
            checked: (record.status === 'active'),
        }));
        const __VLS_114 = __VLS_113({
            ...{ 'onChange': {} },
            checked: (record.status === 'active'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        let __VLS_116;
        let __VLS_117;
        let __VLS_118;
        const __VLS_119 = {
            onChange: ((checked) => __VLS_ctx.toggleRuleStatus(record, checked))
        };
        var __VLS_115;
    }
    else if (column.key === 'category') {
        const __VLS_120 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            color: (__VLS_ctx.getCategoryColor(record.category)),
        }));
        const __VLS_122 = __VLS_121({
            color: (__VLS_ctx.getCategoryColor(record.category)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        (__VLS_ctx.getCategoryName(record.category));
        var __VLS_123;
    }
    else if (column.key === 'priority') {
        const __VLS_124 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }));
        const __VLS_126 = __VLS_125({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_125));
        __VLS_127.slots.default;
        (record.priority);
        var __VLS_127;
    }
    else if (column.key === 'actions') {
        const __VLS_128 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({}));
        const __VLS_130 = __VLS_129({}, ...__VLS_functionalComponentArgsRest(__VLS_129));
        __VLS_131.slots.default;
        const __VLS_132 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_134 = __VLS_133({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_133));
        let __VLS_136;
        let __VLS_137;
        let __VLS_138;
        const __VLS_139 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'category'))
                    return;
                if (!!(column.key === 'priority'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.editRule(record);
            }
        };
        __VLS_135.slots.default;
        var __VLS_135;
        const __VLS_140 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_142 = __VLS_141({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_141));
        let __VLS_144;
        let __VLS_145;
        let __VLS_146;
        const __VLS_147 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'category'))
                    return;
                if (!!(column.key === 'priority'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.testRule(record);
            }
        };
        __VLS_143.slots.default;
        var __VLS_143;
        const __VLS_148 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
            ...{ 'onConfirm': {} },
            title: "确定要删除这个规则吗？",
        }));
        const __VLS_150 = __VLS_149({
            ...{ 'onConfirm': {} },
            title: "确定要删除这个规则吗？",
        }, ...__VLS_functionalComponentArgsRest(__VLS_149));
        let __VLS_152;
        let __VLS_153;
        let __VLS_154;
        const __VLS_155 = {
            onConfirm: (...[$event]) => {
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'category'))
                    return;
                if (!!(column.key === 'priority'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.deleteRule(record);
            }
        };
        __VLS_151.slots.default;
        const __VLS_156 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
            type: "link",
            size: "small",
            danger: true,
        }));
        const __VLS_158 = __VLS_157({
            type: "link",
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_157));
        __VLS_159.slots.default;
        var __VLS_159;
        var __VLS_151;
        var __VLS_131;
    }
}
var __VLS_107;
var __VLS_11;
const __VLS_160 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showCreateModal),
    title: (__VLS_ctx.editingRule ? '编辑规则' : '创建规则'),
    width: "800px",
}));
const __VLS_162 = __VLS_161({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showCreateModal),
    title: (__VLS_ctx.editingRule ? '编辑规则' : '创建规则'),
    width: "800px",
}, ...__VLS_functionalComponentArgsRest(__VLS_161));
let __VLS_164;
let __VLS_165;
let __VLS_166;
const __VLS_167 = {
    onOk: (__VLS_ctx.handleSaveRule)
};
const __VLS_168 = {
    onCancel: (__VLS_ctx.handleCancelEdit)
};
__VLS_163.slots.default;
const __VLS_169 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({
    ref: "ruleFormRef",
    model: (__VLS_ctx.ruleForm),
    rules: (__VLS_ctx.ruleFormRules),
    layout: "vertical",
}));
const __VLS_171 = __VLS_170({
    ref: "ruleFormRef",
    model: (__VLS_ctx.ruleForm),
    rules: (__VLS_ctx.ruleFormRules),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_170));
/** @type {typeof __VLS_ctx.ruleFormRef} */ ;
var __VLS_173 = {};
__VLS_172.slots.default;
const __VLS_175 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_176 = __VLS_asFunctionalComponent(__VLS_175, new __VLS_175({
    gutter: (16),
}));
const __VLS_177 = __VLS_176({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_176));
__VLS_178.slots.default;
const __VLS_179 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_180 = __VLS_asFunctionalComponent(__VLS_179, new __VLS_179({
    span: (12),
}));
const __VLS_181 = __VLS_180({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_180));
__VLS_182.slots.default;
const __VLS_183 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_184 = __VLS_asFunctionalComponent(__VLS_183, new __VLS_183({
    label: "规则名称",
    name: "name",
}));
const __VLS_185 = __VLS_184({
    label: "规则名称",
    name: "name",
}, ...__VLS_functionalComponentArgsRest(__VLS_184));
__VLS_186.slots.default;
const __VLS_187 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_188 = __VLS_asFunctionalComponent(__VLS_187, new __VLS_187({
    value: (__VLS_ctx.ruleForm.name),
    placeholder: "请输入规则名称",
}));
const __VLS_189 = __VLS_188({
    value: (__VLS_ctx.ruleForm.name),
    placeholder: "请输入规则名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_188));
var __VLS_186;
var __VLS_182;
const __VLS_191 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_192 = __VLS_asFunctionalComponent(__VLS_191, new __VLS_191({
    span: (12),
}));
const __VLS_193 = __VLS_192({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_192));
__VLS_194.slots.default;
const __VLS_195 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_196 = __VLS_asFunctionalComponent(__VLS_195, new __VLS_195({
    label: "规则类别",
    name: "category",
}));
const __VLS_197 = __VLS_196({
    label: "规则类别",
    name: "category",
}, ...__VLS_functionalComponentArgsRest(__VLS_196));
__VLS_198.slots.default;
const __VLS_199 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_200 = __VLS_asFunctionalComponent(__VLS_199, new __VLS_199({
    value: (__VLS_ctx.ruleForm.category),
    placeholder: "请选择规则类别",
}));
const __VLS_201 = __VLS_200({
    value: (__VLS_ctx.ruleForm.category),
    placeholder: "请选择规则类别",
}, ...__VLS_functionalComponentArgsRest(__VLS_200));
__VLS_202.slots.default;
const __VLS_203 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_204 = __VLS_asFunctionalComponent(__VLS_203, new __VLS_203({
    value: "completeness",
}));
const __VLS_205 = __VLS_204({
    value: "completeness",
}, ...__VLS_functionalComponentArgsRest(__VLS_204));
__VLS_206.slots.default;
var __VLS_206;
const __VLS_207 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_208 = __VLS_asFunctionalComponent(__VLS_207, new __VLS_207({
    value: "consistency",
}));
const __VLS_209 = __VLS_208({
    value: "consistency",
}, ...__VLS_functionalComponentArgsRest(__VLS_208));
__VLS_210.slots.default;
var __VLS_210;
const __VLS_211 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_212 = __VLS_asFunctionalComponent(__VLS_211, new __VLS_211({
    value: "timeliness",
}));
const __VLS_213 = __VLS_212({
    value: "timeliness",
}, ...__VLS_functionalComponentArgsRest(__VLS_212));
__VLS_214.slots.default;
var __VLS_214;
const __VLS_215 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_216 = __VLS_asFunctionalComponent(__VLS_215, new __VLS_215({
    value: "accuracy",
}));
const __VLS_217 = __VLS_216({
    value: "accuracy",
}, ...__VLS_functionalComponentArgsRest(__VLS_216));
__VLS_218.slots.default;
var __VLS_218;
var __VLS_202;
var __VLS_198;
var __VLS_194;
var __VLS_178;
const __VLS_219 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_220 = __VLS_asFunctionalComponent(__VLS_219, new __VLS_219({
    label: "规则描述",
    name: "description",
}));
const __VLS_221 = __VLS_220({
    label: "规则描述",
    name: "description",
}, ...__VLS_functionalComponentArgsRest(__VLS_220));
__VLS_222.slots.default;
const __VLS_223 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_224 = __VLS_asFunctionalComponent(__VLS_223, new __VLS_223({
    value: (__VLS_ctx.ruleForm.description),
    placeholder: "请输入规则描述",
    rows: (3),
}));
const __VLS_225 = __VLS_224({
    value: (__VLS_ctx.ruleForm.description),
    placeholder: "请输入规则描述",
    rows: (3),
}, ...__VLS_functionalComponentArgsRest(__VLS_224));
var __VLS_222;
const __VLS_227 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_228 = __VLS_asFunctionalComponent(__VLS_227, new __VLS_227({
    gutter: (16),
}));
const __VLS_229 = __VLS_228({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_228));
__VLS_230.slots.default;
const __VLS_231 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_232 = __VLS_asFunctionalComponent(__VLS_231, new __VLS_231({
    span: (12),
}));
const __VLS_233 = __VLS_232({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_232));
__VLS_234.slots.default;
const __VLS_235 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_236 = __VLS_asFunctionalComponent(__VLS_235, new __VLS_235({
    label: "优先级",
    name: "priority",
}));
const __VLS_237 = __VLS_236({
    label: "优先级",
    name: "priority",
}, ...__VLS_functionalComponentArgsRest(__VLS_236));
__VLS_238.slots.default;
const __VLS_239 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_240 = __VLS_asFunctionalComponent(__VLS_239, new __VLS_239({
    value: (__VLS_ctx.ruleForm.priority),
    placeholder: "请选择优先级",
}));
const __VLS_241 = __VLS_240({
    value: (__VLS_ctx.ruleForm.priority),
    placeholder: "请选择优先级",
}, ...__VLS_functionalComponentArgsRest(__VLS_240));
__VLS_242.slots.default;
const __VLS_243 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_244 = __VLS_asFunctionalComponent(__VLS_243, new __VLS_243({
    value: "high",
}));
const __VLS_245 = __VLS_244({
    value: "high",
}, ...__VLS_functionalComponentArgsRest(__VLS_244));
__VLS_246.slots.default;
var __VLS_246;
const __VLS_247 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_248 = __VLS_asFunctionalComponent(__VLS_247, new __VLS_247({
    value: "medium",
}));
const __VLS_249 = __VLS_248({
    value: "medium",
}, ...__VLS_functionalComponentArgsRest(__VLS_248));
__VLS_250.slots.default;
var __VLS_250;
const __VLS_251 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_252 = __VLS_asFunctionalComponent(__VLS_251, new __VLS_251({
    value: "low",
}));
const __VLS_253 = __VLS_252({
    value: "low",
}, ...__VLS_functionalComponentArgsRest(__VLS_252));
__VLS_254.slots.default;
var __VLS_254;
var __VLS_242;
var __VLS_238;
var __VLS_234;
const __VLS_255 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_256 = __VLS_asFunctionalComponent(__VLS_255, new __VLS_255({
    span: (12),
}));
const __VLS_257 = __VLS_256({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_256));
__VLS_258.slots.default;
const __VLS_259 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_260 = __VLS_asFunctionalComponent(__VLS_259, new __VLS_259({
    label: "规则状态",
    name: "status",
}));
const __VLS_261 = __VLS_260({
    label: "规则状态",
    name: "status",
}, ...__VLS_functionalComponentArgsRest(__VLS_260));
__VLS_262.slots.default;
const __VLS_263 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_264 = __VLS_asFunctionalComponent(__VLS_263, new __VLS_263({
    value: (__VLS_ctx.ruleForm.status),
    placeholder: "请选择状态",
}));
const __VLS_265 = __VLS_264({
    value: (__VLS_ctx.ruleForm.status),
    placeholder: "请选择状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_264));
__VLS_266.slots.default;
const __VLS_267 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_268 = __VLS_asFunctionalComponent(__VLS_267, new __VLS_267({
    value: "active",
}));
const __VLS_269 = __VLS_268({
    value: "active",
}, ...__VLS_functionalComponentArgsRest(__VLS_268));
__VLS_270.slots.default;
var __VLS_270;
const __VLS_271 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_272 = __VLS_asFunctionalComponent(__VLS_271, new __VLS_271({
    value: "inactive",
}));
const __VLS_273 = __VLS_272({
    value: "inactive",
}, ...__VLS_functionalComponentArgsRest(__VLS_272));
__VLS_274.slots.default;
var __VLS_274;
var __VLS_266;
var __VLS_262;
var __VLS_258;
var __VLS_230;
const __VLS_275 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_276 = __VLS_asFunctionalComponent(__VLS_275, new __VLS_275({
    label: "规则条件",
    name: "conditions",
}));
const __VLS_277 = __VLS_276({
    label: "规则条件",
    name: "conditions",
}, ...__VLS_functionalComponentArgsRest(__VLS_276));
__VLS_278.slots.default;
const __VLS_279 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_280 = __VLS_asFunctionalComponent(__VLS_279, new __VLS_279({
    value: (__VLS_ctx.ruleForm.conditions),
    placeholder: "请输入规则条件（JSON格式）",
    rows: (4),
}));
const __VLS_281 = __VLS_280({
    value: (__VLS_ctx.ruleForm.conditions),
    placeholder: "请输入规则条件（JSON格式）",
    rows: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_280));
var __VLS_278;
var __VLS_172;
var __VLS_163;
/** @type {__VLS_StyleScopedClasses['enhanced-rules-view']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['content-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['status-card']} */ ;
/** @type {__VLS_StyleScopedClasses['status-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['status-item']} */ ;
/** @type {__VLS_StyleScopedClasses['status-label']} */ ;
/** @type {__VLS_StyleScopedClasses['status-value']} */ ;
/** @type {__VLS_StyleScopedClasses['status-item']} */ ;
/** @type {__VLS_StyleScopedClasses['status-label']} */ ;
/** @type {__VLS_StyleScopedClasses['status-value']} */ ;
/** @type {__VLS_StyleScopedClasses['status-item']} */ ;
/** @type {__VLS_StyleScopedClasses['status-label']} */ ;
/** @type {__VLS_StyleScopedClasses['status-value']} */ ;
/** @type {__VLS_StyleScopedClasses['status-item']} */ ;
/** @type {__VLS_StyleScopedClasses['status-label']} */ ;
/** @type {__VLS_StyleScopedClasses['status-value']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-card']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-filters']} */ ;
// @ts-ignore
var __VLS_174 = __VLS_173;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            PlusOutlined: icons_vue_1.PlusOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            loading: loading,
            showCreateModal: showCreateModal,
            editingRule: editingRule,
            engineStatus: engineStatus,
            filters: filters,
            ruleForm: ruleForm,
            ruleFormRules: ruleFormRules,
            rulesColumns: rulesColumns,
            pagination: pagination,
            filteredRules: filteredRules,
            getCategoryColor: getCategoryColor,
            getCategoryName: getCategoryName,
            getPriorityColor: getPriorityColor,
            handleFilterChange: handleFilterChange,
            handleTableChange: handleTableChange,
            refreshRules: refreshRules,
            toggleRuleStatus: toggleRuleStatus,
            editRule: editRule,
            testRule: testRule,
            deleteRule: deleteRule,
            handleSaveRule: handleSaveRule,
            handleCancelEdit: handleCancelEdit,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
