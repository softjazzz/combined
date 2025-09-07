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
const selectedDepartment = (0, vue_1.ref)('');
const activeTab = (0, vue_1.ref)('basic');
const saving = (0, vue_1.ref)(false);
const showAddDepartmentModal = (0, vue_1.ref)(false);
const showAddRuleModal = (0, vue_1.ref)(false);
// 科室列表
const departments = (0, vue_1.ref)([
    { id: '1', name: '心内科', code: 'CARDIO', type: 'internal' },
    { id: '2', name: '神经外科', code: 'NEURO', type: 'surgical' },
    { id: '3', name: '急诊科', code: 'EMERG', type: 'emergency' },
    { id: '4', name: 'ICU', code: 'ICU', type: 'icu' }
]);
// 当前科室
const currentDepartment = (0, vue_1.computed)(() => departments.value.find(d => d.id === selectedDepartment.value));
// 科室配置
const departmentConfig = (0, vue_1.reactive)({
    name: '',
    code: '',
    description: '',
    type: '',
    riskLevel: 'medium',
    status: 'active',
    samplingRate: 10,
    auditCycle: 7,
    scoreThreshold: 80,
    specialConfigs: []
});
// 新科室表单
const newDepartment = (0, vue_1.reactive)({
    name: '',
    code: '',
    type: 'internal'
});
// 科室规则
const departmentRules = (0, vue_1.ref)([
    {
        id: '1',
        name: '心内科病历完整性检查',
        description: '检查心内科病历必填项',
        severity: 'high',
        enabled: true
    },
    {
        id: '2',
        name: '用药合理性验证',
        description: '验证心血管用药的合理性',
        severity: 'medium',
        enabled: true
    }
]);
// 规则表格列
const rulesColumns = [
    { title: '规则名称', dataIndex: 'name', key: 'name' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '严重程度', dataIndex: 'severity', key: 'severity' },
    { title: '启用状态', dataIndex: 'enabled', key: 'enabled' },
    { title: '操作', key: 'actions', width: 150 }
];
// 方法
const handleDepartmentChange = (value) => {
    const dept = departments.value.find(d => d.id === value);
    if (dept) {
        Object.assign(departmentConfig, {
            name: dept.name,
            code: dept.code,
            type: dept.type,
            description: `${dept.name}的专科化配置`,
            riskLevel: 'medium',
            status: 'active',
            samplingRate: 10,
            auditCycle: 7,
            scoreThreshold: 80,
            specialConfigs: []
        });
    }
};
const refreshDepartments = async () => {
    try {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1000));
        ant_design_vue_1.message.success('科室列表已刷新');
    }
    catch (error) {
        ant_design_vue_1.message.error('刷新失败');
    }
};
const saveDepartmentConfig = async () => {
    saving.value = true;
    try {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1000));
        ant_design_vue_1.message.success('科室配置已保存');
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
    finally {
        saving.value = false;
    }
};
const saveParameters = async () => {
    saving.value = true;
    try {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1000));
        ant_design_vue_1.message.success('参数配置已保存');
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
    finally {
        saving.value = false;
    }
};
const addDepartment = async () => {
    try {
        const newDept = {
            id: Date.now().toString(),
            ...newDepartment
        };
        departments.value.push(newDept);
        ant_design_vue_1.message.success('科室添加成功');
        showAddDepartmentModal.value = false;
        Object.assign(newDepartment, { name: '', code: '', type: 'internal' });
    }
    catch (error) {
        ant_design_vue_1.message.error('添加失败');
    }
};
const cancelAddDepartment = () => {
    showAddDepartmentModal.value = false;
    Object.assign(newDepartment, { name: '', code: '', type: 'internal' });
};
const toggleRule = (rule, checked) => {
    rule.enabled = checked;
    ant_design_vue_1.message.success(`规则已${checked ? '启用' : '禁用'}`);
};
const editRule = (rule) => {
    ant_design_vue_1.message.info(`编辑规则: ${rule.name}`);
};
const deleteRule = (rule) => {
    const index = departmentRules.value.findIndex(r => r.id === rule.id);
    if (index > -1) {
        departmentRules.value.splice(index, 1);
        ant_design_vue_1.message.success('规则已删除');
    }
};
const getSeverityColor = (severity) => {
    const colors = {
        high: 'red',
        medium: 'orange',
        low: 'green'
    };
    return colors[severity] || 'default';
};
// 生命周期
(0, vue_1.onMounted)(() => {
    refreshDepartments();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "department-config" },
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
    title: "科室选择",
    ...{ class: "department-selector" },
}));
const __VLS_2 = __VLS_1({
    title: "科室选择",
    ...{ class: "department-selector" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    gutter: (16),
}));
const __VLS_6 = __VLS_5({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    span: (8),
}));
const __VLS_10 = __VLS_9({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "请选择科室",
    ...{ style: {} },
}));
const __VLS_14 = __VLS_13({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "请选择科室",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onChange: (__VLS_ctx.handleDepartmentChange)
};
__VLS_15.slots.default;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_20 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        key: (dept.id),
        value: (dept.id),
    }));
    const __VLS_22 = __VLS_21({
        key: (dept.id),
        value: (dept.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    (dept.name);
    var __VLS_23;
}
var __VLS_15;
var __VLS_11;
const __VLS_24 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    span: (16),
}));
const __VLS_26 = __VLS_25({
    span: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showAddDepartmentModal = true;
    }
};
__VLS_35.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_35.slots;
    const __VLS_40 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
    const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
var __VLS_35;
const __VLS_44 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ 'onClick': {} },
}));
const __VLS_46 = __VLS_45({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_48;
let __VLS_49;
let __VLS_50;
const __VLS_51 = {
    onClick: (__VLS_ctx.refreshDepartments)
};
__VLS_47.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_47.slots;
    const __VLS_52 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
    const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
}
var __VLS_47;
var __VLS_31;
var __VLS_27;
var __VLS_7;
var __VLS_3;
if (__VLS_ctx.selectedDepartment) {
    const __VLS_56 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        title: (`${__VLS_ctx.currentDepartment?.name} - 专科化配置`),
        ...{ class: "config-details" },
    }));
    const __VLS_58 = __VLS_57({
        title: (`${__VLS_ctx.currentDepartment?.name} - 专科化配置`),
        ...{ class: "config-details" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    const __VLS_60 = {}.ATabs;
    /** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        activeKey: (__VLS_ctx.activeTab),
    }));
    const __VLS_62 = __VLS_61({
        activeKey: (__VLS_ctx.activeTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    const __VLS_64 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        key: "basic",
        tab: "基础信息",
    }));
    const __VLS_66 = __VLS_65({
        key: "basic",
        tab: "基础信息",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    const __VLS_68 = {}.AForm;
    /** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        ...{ 'onFinish': {} },
        model: (__VLS_ctx.departmentConfig),
        layout: "vertical",
    }));
    const __VLS_70 = __VLS_69({
        ...{ 'onFinish': {} },
        model: (__VLS_ctx.departmentConfig),
        layout: "vertical",
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    let __VLS_72;
    let __VLS_73;
    let __VLS_74;
    const __VLS_75 = {
        onFinish: (__VLS_ctx.saveDepartmentConfig)
    };
    __VLS_71.slots.default;
    const __VLS_76 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        gutter: (16),
    }));
    const __VLS_78 = __VLS_77({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    const __VLS_80 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        span: (12),
    }));
    const __VLS_82 = __VLS_81({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    const __VLS_84 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        label: "科室名称",
        name: "name",
    }));
    const __VLS_86 = __VLS_85({
        label: "科室名称",
        name: "name",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    const __VLS_88 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        value: (__VLS_ctx.departmentConfig.name),
    }));
    const __VLS_90 = __VLS_89({
        value: (__VLS_ctx.departmentConfig.name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    var __VLS_87;
    var __VLS_83;
    const __VLS_92 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        span: (12),
    }));
    const __VLS_94 = __VLS_93({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    __VLS_95.slots.default;
    const __VLS_96 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        label: "科室代码",
        name: "code",
    }));
    const __VLS_98 = __VLS_97({
        label: "科室代码",
        name: "code",
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    __VLS_99.slots.default;
    const __VLS_100 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        value: (__VLS_ctx.departmentConfig.code),
    }));
    const __VLS_102 = __VLS_101({
        value: (__VLS_ctx.departmentConfig.code),
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    var __VLS_99;
    var __VLS_95;
    var __VLS_79;
    const __VLS_104 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        label: "科室描述",
        name: "description",
    }));
    const __VLS_106 = __VLS_105({
        label: "科室描述",
        name: "description",
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    __VLS_107.slots.default;
    const __VLS_108 = {}.ATextarea;
    /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        value: (__VLS_ctx.departmentConfig.description),
        rows: (3),
    }));
    const __VLS_110 = __VLS_109({
        value: (__VLS_ctx.departmentConfig.description),
        rows: (3),
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    var __VLS_107;
    const __VLS_112 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
        gutter: (16),
    }));
    const __VLS_114 = __VLS_113({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_113));
    __VLS_115.slots.default;
    const __VLS_116 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        span: (8),
    }));
    const __VLS_118 = __VLS_117({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    __VLS_119.slots.default;
    const __VLS_120 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        label: "科室类型",
        name: "type",
    }));
    const __VLS_122 = __VLS_121({
        label: "科室类型",
        name: "type",
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
    __VLS_123.slots.default;
    const __VLS_124 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
        value: (__VLS_ctx.departmentConfig.type),
    }));
    const __VLS_126 = __VLS_125({
        value: (__VLS_ctx.departmentConfig.type),
    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
    __VLS_127.slots.default;
    const __VLS_128 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        value: "internal",
    }));
    const __VLS_130 = __VLS_129({
        value: "internal",
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    __VLS_131.slots.default;
    var __VLS_131;
    const __VLS_132 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        value: "surgical",
    }));
    const __VLS_134 = __VLS_133({
        value: "surgical",
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    var __VLS_135;
    const __VLS_136 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        value: "emergency",
    }));
    const __VLS_138 = __VLS_137({
        value: "emergency",
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    var __VLS_139;
    const __VLS_140 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
        value: "icu",
    }));
    const __VLS_142 = __VLS_141({
        value: "icu",
    }, ...__VLS_functionalComponentArgsRest(__VLS_141));
    __VLS_143.slots.default;
    var __VLS_143;
    const __VLS_144 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        value: "pediatric",
    }));
    const __VLS_146 = __VLS_145({
        value: "pediatric",
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    __VLS_147.slots.default;
    var __VLS_147;
    const __VLS_148 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        value: "obstetric",
    }));
    const __VLS_150 = __VLS_149({
        value: "obstetric",
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    __VLS_151.slots.default;
    var __VLS_151;
    var __VLS_127;
    var __VLS_123;
    var __VLS_119;
    const __VLS_152 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        span: (8),
    }));
    const __VLS_154 = __VLS_153({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    const __VLS_156 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        label: "风险等级",
        name: "riskLevel",
    }));
    const __VLS_158 = __VLS_157({
        label: "风险等级",
        name: "riskLevel",
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    const __VLS_160 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        value: (__VLS_ctx.departmentConfig.riskLevel),
    }));
    const __VLS_162 = __VLS_161({
        value: (__VLS_ctx.departmentConfig.riskLevel),
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    __VLS_163.slots.default;
    const __VLS_164 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        value: "high",
    }));
    const __VLS_166 = __VLS_165({
        value: "high",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    var __VLS_167;
    const __VLS_168 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        value: "medium",
    }));
    const __VLS_170 = __VLS_169({
        value: "medium",
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    var __VLS_171;
    const __VLS_172 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        value: "low",
    }));
    const __VLS_174 = __VLS_173({
        value: "low",
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
    __VLS_175.slots.default;
    var __VLS_175;
    var __VLS_163;
    var __VLS_159;
    var __VLS_155;
    const __VLS_176 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
        span: (8),
    }));
    const __VLS_178 = __VLS_177({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_177));
    __VLS_179.slots.default;
    const __VLS_180 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        label: "状态",
        name: "status",
    }));
    const __VLS_182 = __VLS_181({
        label: "状态",
        name: "status",
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    __VLS_183.slots.default;
    const __VLS_184 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
        value: (__VLS_ctx.departmentConfig.status),
    }));
    const __VLS_186 = __VLS_185({
        value: (__VLS_ctx.departmentConfig.status),
    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    __VLS_187.slots.default;
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
    var __VLS_187;
    var __VLS_183;
    var __VLS_179;
    var __VLS_115;
    const __VLS_196 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({}));
    const __VLS_198 = __VLS_197({}, ...__VLS_functionalComponentArgsRest(__VLS_197));
    __VLS_199.slots.default;
    const __VLS_200 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
        type: "primary",
        htmlType: "submit",
        loading: (__VLS_ctx.saving),
    }));
    const __VLS_202 = __VLS_201({
        type: "primary",
        htmlType: "submit",
        loading: (__VLS_ctx.saving),
    }, ...__VLS_functionalComponentArgsRest(__VLS_201));
    __VLS_203.slots.default;
    var __VLS_203;
    var __VLS_199;
    var __VLS_71;
    var __VLS_67;
    const __VLS_204 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        key: "rules",
        tab: "质控规则",
    }));
    const __VLS_206 = __VLS_205({
        key: "rules",
        tab: "质控规则",
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
    __VLS_207.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rules-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "section-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    const __VLS_208 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_210 = __VLS_209({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
    let __VLS_212;
    let __VLS_213;
    let __VLS_214;
    const __VLS_215 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.selectedDepartment))
                return;
            __VLS_ctx.showAddRuleModal = true;
        }
    };
    __VLS_211.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_211.slots;
        const __VLS_216 = {}.PlusOutlined;
        /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({}));
        const __VLS_218 = __VLS_217({}, ...__VLS_functionalComponentArgsRest(__VLS_217));
    }
    var __VLS_211;
    const __VLS_220 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
        columns: (__VLS_ctx.rulesColumns),
        dataSource: (__VLS_ctx.departmentRules),
        pagination: (false),
    }));
    const __VLS_222 = __VLS_221({
        columns: (__VLS_ctx.rulesColumns),
        dataSource: (__VLS_ctx.departmentRules),
        pagination: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_221));
    __VLS_223.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_223.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'enabled') {
            const __VLS_224 = {}.ASwitch;
            /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
            // @ts-ignore
            const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
                ...{ 'onChange': {} },
                checked: (record.enabled),
            }));
            const __VLS_226 = __VLS_225({
                ...{ 'onChange': {} },
                checked: (record.enabled),
            }, ...__VLS_functionalComponentArgsRest(__VLS_225));
            let __VLS_228;
            let __VLS_229;
            let __VLS_230;
            const __VLS_231 = {
                onChange: ((checked) => __VLS_ctx.toggleRule(record, checked))
            };
            var __VLS_227;
        }
        else if (column.key === 'severity') {
            const __VLS_232 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
                color: (__VLS_ctx.getSeverityColor(record.severity)),
            }));
            const __VLS_234 = __VLS_233({
                color: (__VLS_ctx.getSeverityColor(record.severity)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_233));
            __VLS_235.slots.default;
            (record.severity);
            var __VLS_235;
        }
        else if (column.key === 'actions') {
            const __VLS_236 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({}));
            const __VLS_238 = __VLS_237({}, ...__VLS_functionalComponentArgsRest(__VLS_237));
            __VLS_239.slots.default;
            const __VLS_240 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_242 = __VLS_241({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_241));
            let __VLS_244;
            let __VLS_245;
            let __VLS_246;
            const __VLS_247 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.selectedDepartment))
                        return;
                    if (!!(column.key === 'enabled'))
                        return;
                    if (!!(column.key === 'severity'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.editRule(record);
                }
            };
            __VLS_243.slots.default;
            var __VLS_243;
            const __VLS_248 = {}.APopconfirm;
            /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
            // @ts-ignore
            const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
                ...{ 'onConfirm': {} },
                title: "确定要删除这个规则吗？",
            }));
            const __VLS_250 = __VLS_249({
                ...{ 'onConfirm': {} },
                title: "确定要删除这个规则吗？",
            }, ...__VLS_functionalComponentArgsRest(__VLS_249));
            let __VLS_252;
            let __VLS_253;
            let __VLS_254;
            const __VLS_255 = {
                onConfirm: (...[$event]) => {
                    if (!(__VLS_ctx.selectedDepartment))
                        return;
                    if (!!(column.key === 'enabled'))
                        return;
                    if (!!(column.key === 'severity'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.deleteRule(record);
                }
            };
            __VLS_251.slots.default;
            const __VLS_256 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
                type: "link",
                size: "small",
                danger: true,
            }));
            const __VLS_258 = __VLS_257({
                type: "link",
                size: "small",
                danger: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_257));
            __VLS_259.slots.default;
            var __VLS_259;
            var __VLS_251;
            var __VLS_239;
        }
    }
    var __VLS_223;
    var __VLS_207;
    const __VLS_260 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
        key: "parameters",
        tab: "参数配置",
    }));
    const __VLS_262 = __VLS_261({
        key: "parameters",
        tab: "参数配置",
    }, ...__VLS_functionalComponentArgsRest(__VLS_261));
    __VLS_263.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parameters-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    const __VLS_264 = {}.AForm;
    /** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
    // @ts-ignore
    const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
        layout: "vertical",
    }));
    const __VLS_266 = __VLS_265({
        layout: "vertical",
    }, ...__VLS_functionalComponentArgsRest(__VLS_265));
    __VLS_267.slots.default;
    const __VLS_268 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
        gutter: (16),
    }));
    const __VLS_270 = __VLS_269({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_269));
    __VLS_271.slots.default;
    const __VLS_272 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
        span: (8),
    }));
    const __VLS_274 = __VLS_273({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_273));
    __VLS_275.slots.default;
    const __VLS_276 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({
        label: "抽样比例 (%)",
    }));
    const __VLS_278 = __VLS_277({
        label: "抽样比例 (%)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_277));
    __VLS_279.slots.default;
    const __VLS_280 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
        value: (__VLS_ctx.departmentConfig.samplingRate),
        min: (1),
        max: (100),
        ...{ style: {} },
    }));
    const __VLS_282 = __VLS_281({
        value: (__VLS_ctx.departmentConfig.samplingRate),
        min: (1),
        max: (100),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_281));
    var __VLS_279;
    var __VLS_275;
    const __VLS_284 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
        span: (8),
    }));
    const __VLS_286 = __VLS_285({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_285));
    __VLS_287.slots.default;
    const __VLS_288 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
        label: "审核周期 (天)",
    }));
    const __VLS_290 = __VLS_289({
        label: "审核周期 (天)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_289));
    __VLS_291.slots.default;
    const __VLS_292 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
        value: (__VLS_ctx.departmentConfig.auditCycle),
        min: (1),
        max: (30),
        ...{ style: {} },
    }));
    const __VLS_294 = __VLS_293({
        value: (__VLS_ctx.departmentConfig.auditCycle),
        min: (1),
        max: (30),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_293));
    var __VLS_291;
    var __VLS_287;
    const __VLS_296 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
        span: (8),
    }));
    const __VLS_298 = __VLS_297({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_297));
    __VLS_299.slots.default;
    const __VLS_300 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({
        label: "质控分数阈值",
    }));
    const __VLS_302 = __VLS_301({
        label: "质控分数阈值",
    }, ...__VLS_functionalComponentArgsRest(__VLS_301));
    __VLS_303.slots.default;
    const __VLS_304 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
        value: (__VLS_ctx.departmentConfig.scoreThreshold),
        min: (0),
        max: (100),
        ...{ style: {} },
    }));
    const __VLS_306 = __VLS_305({
        value: (__VLS_ctx.departmentConfig.scoreThreshold),
        min: (0),
        max: (100),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_305));
    var __VLS_303;
    var __VLS_299;
    var __VLS_271;
    const __VLS_308 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({
        label: "特殊配置",
    }));
    const __VLS_310 = __VLS_309({
        label: "特殊配置",
    }, ...__VLS_functionalComponentArgsRest(__VLS_309));
    __VLS_311.slots.default;
    const __VLS_312 = {}.ACheckboxGroup;
    /** @type {[typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, ]} */ ;
    // @ts-ignore
    const __VLS_313 = __VLS_asFunctionalComponent(__VLS_312, new __VLS_312({
        value: (__VLS_ctx.departmentConfig.specialConfigs),
    }));
    const __VLS_314 = __VLS_313({
        value: (__VLS_ctx.departmentConfig.specialConfigs),
    }, ...__VLS_functionalComponentArgsRest(__VLS_313));
    __VLS_315.slots.default;
    const __VLS_316 = {}.ACheckbox;
    /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
    // @ts-ignore
    const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
        value: "autoAssign",
    }));
    const __VLS_318 = __VLS_317({
        value: "autoAssign",
    }, ...__VLS_functionalComponentArgsRest(__VLS_317));
    __VLS_319.slots.default;
    var __VLS_319;
    const __VLS_320 = {}.ACheckbox;
    /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
    // @ts-ignore
    const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
        value: "priorityReview",
    }));
    const __VLS_322 = __VLS_321({
        value: "priorityReview",
    }, ...__VLS_functionalComponentArgsRest(__VLS_321));
    __VLS_323.slots.default;
    var __VLS_323;
    const __VLS_324 = {}.ACheckbox;
    /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
    // @ts-ignore
    const __VLS_325 = __VLS_asFunctionalComponent(__VLS_324, new __VLS_324({
        value: "doubleCheck",
    }));
    const __VLS_326 = __VLS_325({
        value: "doubleCheck",
    }, ...__VLS_functionalComponentArgsRest(__VLS_325));
    __VLS_327.slots.default;
    var __VLS_327;
    const __VLS_328 = {}.ACheckbox;
    /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
    // @ts-ignore
    const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
        value: "expertReview",
    }));
    const __VLS_330 = __VLS_329({
        value: "expertReview",
    }, ...__VLS_functionalComponentArgsRest(__VLS_329));
    __VLS_331.slots.default;
    var __VLS_331;
    var __VLS_315;
    var __VLS_311;
    const __VLS_332 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({}));
    const __VLS_334 = __VLS_333({}, ...__VLS_functionalComponentArgsRest(__VLS_333));
    __VLS_335.slots.default;
    const __VLS_336 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.saving),
    }));
    const __VLS_338 = __VLS_337({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.saving),
    }, ...__VLS_functionalComponentArgsRest(__VLS_337));
    let __VLS_340;
    let __VLS_341;
    let __VLS_342;
    const __VLS_343 = {
        onClick: (__VLS_ctx.saveParameters)
    };
    __VLS_339.slots.default;
    var __VLS_339;
    var __VLS_335;
    var __VLS_267;
    var __VLS_263;
    var __VLS_63;
    var __VLS_59;
}
else {
    const __VLS_344 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
        description: "请选择一个科室进行配置",
        image: (__VLS_ctx.Empty.PRESENTED_IMAGE_SIMPLE),
    }));
    const __VLS_346 = __VLS_345({
        description: "请选择一个科室进行配置",
        image: (__VLS_ctx.Empty.PRESENTED_IMAGE_SIMPLE),
    }, ...__VLS_functionalComponentArgsRest(__VLS_345));
}
const __VLS_348 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_349 = __VLS_asFunctionalComponent(__VLS_348, new __VLS_348({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showAddDepartmentModal),
    title: "添加科室",
}));
const __VLS_350 = __VLS_349({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showAddDepartmentModal),
    title: "添加科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_349));
let __VLS_352;
let __VLS_353;
let __VLS_354;
const __VLS_355 = {
    onOk: (__VLS_ctx.addDepartment)
};
const __VLS_356 = {
    onCancel: (__VLS_ctx.cancelAddDepartment)
};
__VLS_351.slots.default;
const __VLS_357 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_358 = __VLS_asFunctionalComponent(__VLS_357, new __VLS_357({
    model: (__VLS_ctx.newDepartment),
    layout: "vertical",
}));
const __VLS_359 = __VLS_358({
    model: (__VLS_ctx.newDepartment),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_358));
__VLS_360.slots.default;
const __VLS_361 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_362 = __VLS_asFunctionalComponent(__VLS_361, new __VLS_361({
    label: "科室名称",
    required: true,
}));
const __VLS_363 = __VLS_362({
    label: "科室名称",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_362));
__VLS_364.slots.default;
const __VLS_365 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_366 = __VLS_asFunctionalComponent(__VLS_365, new __VLS_365({
    value: (__VLS_ctx.newDepartment.name),
}));
const __VLS_367 = __VLS_366({
    value: (__VLS_ctx.newDepartment.name),
}, ...__VLS_functionalComponentArgsRest(__VLS_366));
var __VLS_364;
const __VLS_369 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_370 = __VLS_asFunctionalComponent(__VLS_369, new __VLS_369({
    label: "科室代码",
    required: true,
}));
const __VLS_371 = __VLS_370({
    label: "科室代码",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_370));
__VLS_372.slots.default;
const __VLS_373 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_374 = __VLS_asFunctionalComponent(__VLS_373, new __VLS_373({
    value: (__VLS_ctx.newDepartment.code),
}));
const __VLS_375 = __VLS_374({
    value: (__VLS_ctx.newDepartment.code),
}, ...__VLS_functionalComponentArgsRest(__VLS_374));
var __VLS_372;
const __VLS_377 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_378 = __VLS_asFunctionalComponent(__VLS_377, new __VLS_377({
    label: "科室类型",
}));
const __VLS_379 = __VLS_378({
    label: "科室类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_378));
__VLS_380.slots.default;
const __VLS_381 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_382 = __VLS_asFunctionalComponent(__VLS_381, new __VLS_381({
    value: (__VLS_ctx.newDepartment.type),
}));
const __VLS_383 = __VLS_382({
    value: (__VLS_ctx.newDepartment.type),
}, ...__VLS_functionalComponentArgsRest(__VLS_382));
__VLS_384.slots.default;
const __VLS_385 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_386 = __VLS_asFunctionalComponent(__VLS_385, new __VLS_385({
    value: "internal",
}));
const __VLS_387 = __VLS_386({
    value: "internal",
}, ...__VLS_functionalComponentArgsRest(__VLS_386));
__VLS_388.slots.default;
var __VLS_388;
const __VLS_389 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_390 = __VLS_asFunctionalComponent(__VLS_389, new __VLS_389({
    value: "surgical",
}));
const __VLS_391 = __VLS_390({
    value: "surgical",
}, ...__VLS_functionalComponentArgsRest(__VLS_390));
__VLS_392.slots.default;
var __VLS_392;
const __VLS_393 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_394 = __VLS_asFunctionalComponent(__VLS_393, new __VLS_393({
    value: "emergency",
}));
const __VLS_395 = __VLS_394({
    value: "emergency",
}, ...__VLS_functionalComponentArgsRest(__VLS_394));
__VLS_396.slots.default;
var __VLS_396;
const __VLS_397 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_398 = __VLS_asFunctionalComponent(__VLS_397, new __VLS_397({
    value: "icu",
}));
const __VLS_399 = __VLS_398({
    value: "icu",
}, ...__VLS_functionalComponentArgsRest(__VLS_398));
__VLS_400.slots.default;
var __VLS_400;
var __VLS_384;
var __VLS_380;
var __VLS_360;
var __VLS_351;
/** @type {__VLS_StyleScopedClasses['department-config']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['content-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['department-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['config-details']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['parameters-section']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            Empty: ant_design_vue_1.Empty,
            PlusOutlined: icons_vue_1.PlusOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            selectedDepartment: selectedDepartment,
            activeTab: activeTab,
            saving: saving,
            showAddDepartmentModal: showAddDepartmentModal,
            showAddRuleModal: showAddRuleModal,
            departments: departments,
            currentDepartment: currentDepartment,
            departmentConfig: departmentConfig,
            newDepartment: newDepartment,
            departmentRules: departmentRules,
            rulesColumns: rulesColumns,
            handleDepartmentChange: handleDepartmentChange,
            refreshDepartments: refreshDepartments,
            saveDepartmentConfig: saveDepartmentConfig,
            saveParameters: saveParameters,
            addDepartment: addDepartment,
            cancelAddDepartment: cancelAddDepartment,
            toggleRule: toggleRule,
            editRule: editRule,
            deleteRule: deleteRule,
            getSeverityColor: getSeverityColor,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
