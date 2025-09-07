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
const props = withDefaults(defineProps(), {
    visible: false,
    currentConditions: () => ({})
});
const emit = defineEmits();
// 表单数据
const formData = (0, vue_1.reactive)({ defectStatus: [],
    auditStatus: [],
    department: [],
    doctor: [],
    priority:  [],
    scoreRange: [0, 100],
    defectCountMin: undefined,
    defectCountMax: undefined,
    timeRange: undefined,
    isUrgent: undefined
});
// 模板相关
const saveAsTemplate = (0, vue_1.ref)(false);
const templateName = (0, vue_1.ref)('');
// 选项数据
const departmentOptions = [
    { label: '内科', value: 'internal' },
    { label: '外科', value: 'surgery' },
    { label: '儿科', value: 'pediatrics' },
    { label: '妇产科', value: 'obstetrics' },
    { label: '急诊科', value: 'emergency' },
    { label: '骨科', value: 'orthopedics' },
    { label: '神经科', value: 'neurology' },
    { label: '心内科', value: 'cardiology' }
];
const doctorOptions = [
    { label: '张医生', value: 'doctor1' },
    { label: '李医生', value: 'doctor2' },
    { label: '王医生', value: 'doctor3' },
    { label: '刘医生', value: 'doctor4' },
    { label: '陈医生', value: 'doctor5' },
    { label: '杨医生', value: 'doctor6' }
];
// 搜索过滤
const filterOption = (input: any,  option: any) => {
    return option.label.toLowerCase().indexOf(input.toLowerCase()) >= 0;
};
// 监听visible变化，初始化表单数据
(0, vue_1.watch)(() => props.visible, (newVal: any) => {
    if (newVal) {
        // 初始化表单数据
        Object.assign(formData, props.currentConditions);
    }
});
// 确认
const handleConfirm = () => {
    // 验证模板名称
    if (saveAsTemplate.value && !templateName.value.trim()) {
        ant_design_vue_1.message.error('请输入模板名称');
        return;
    }
    // 构建筛选条件
    const conditions = { ...formData };
    // 清理空值
    Object.keys(conditions).forEach(key => {
        const value = conditions[key];
        if (Array.isArray(value) && value.length === 0) {
            delete conditions[key];
        }
        else if (value === undefined || value === null || value === '') {
            delete conditions[key];
        }
    });
    emit('confirm', conditions, saveAsTemplate.value ? templateName.value : undefined);
    emit('update:visible', false);
    // 重置模板相关状态
    saveAsTemplate.value = false;
    templateName.value = '';
};
// 取消
const handleCancel = () => {
    emit('update:visible', false);
    saveAsTemplate.value = false;
    templateName.value = '';
};
// 重置
const handleReset = () => { Object.assign(formData, {
        defectStatus: [],
        auditStatus: [],
        department: [],
        doctor: [],
        priority:  [],
        scoreRange: [0, 100],
        defectCountMin: undefined,
        defectCountMax: undefined,
        timeRange: undefined,
        isUrgent: undefined
    });
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    visible: false,
    currentConditions: () => ({})
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
const __VLS_0 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    visible: (props.visible),
    title: "筛选条件设置",
    width: "800px",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    visible: (props.visible),
    title: "筛选条件设置",
    width: "800px",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onOk: (__VLS_ctx.handleConfirm)
};
const __VLS_8 = {
    onCancel: (__VLS_ctx.handleCancel)
};
var __VLS_9 = {};
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "filter-modal-content" },
});
const __VLS_10 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
    model: (__VLS_ctx.formData),
    labelCol: ({ span: 6 }),
    wrapperCol: ({ span: 18 }),
}));
const __VLS_12 = __VLS_11({
    model: (__VLS_ctx.formData),
    labelCol: ({ span: 6 }),
    wrapperCol: ({ span: 18 }),
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
__VLS_13.slots.default;
const __VLS_14 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
    label: "缺陷状态",
}));
const __VLS_16 = __VLS_15({
    label: "缺陷状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
__VLS_17.slots.default;
const __VLS_18 = {}.ACheckboxGroup;
/** @type {[typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, ]} */ ;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
    value: (__VLS_ctx.formData.defectStatus),
}));
const __VLS_20 = __VLS_19({
    value: (__VLS_ctx.formData.defectStatus),
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
__VLS_21.slots.default;
const __VLS_22 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_23 = __VLS_asFunctionalComponent(__VLS_22, new __VLS_22({
    value: "pending",
}));
const __VLS_24 = __VLS_23({
    value: "pending",
}, ...__VLS_functionalComponentArgsRest(__VLS_23));
__VLS_25.slots.default;
var __VLS_25;
const __VLS_26 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
    value: "urged",
}));
const __VLS_28 = __VLS_27({
    value: "urged",
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_29.slots.default;
var __VLS_29;
const __VLS_30 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
    value: "rectified",
}));
const __VLS_32 = __VLS_31({
    value: "rectified",
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
__VLS_33.slots.default;
var __VLS_33;
const __VLS_34 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
    value: "appealed",
}));
const __VLS_36 = __VLS_35({
    value: "appealed",
}, ...__VLS_functionalComponentArgsRest(__VLS_35));
__VLS_37.slots.default;
var __VLS_37;
var __VLS_21;
var __VLS_17;
const __VLS_38 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
    label: "审核状态",
}));
const __VLS_40 = __VLS_39({
    label: "审核状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
__VLS_41.slots.default;
const __VLS_42 = {}.ACheckboxGroup;
/** @type {[typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, ]} */ ;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
    value: (__VLS_ctx.formData.auditStatus),
}));
const __VLS_44 = __VLS_43({
    value: (__VLS_ctx.formData.auditStatus),
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
__VLS_45.slots.default;
const __VLS_46 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
    value: "pending",
}));
const __VLS_48 = __VLS_47({
    value: "pending",
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
__VLS_49.slots.default;
var __VLS_49;
const __VLS_50 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
    value: "reviewing",
}));
const __VLS_52 = __VLS_51({
    value: "reviewing",
}, ...__VLS_functionalComponentArgsRest(__VLS_51));
__VLS_53.slots.default;
var __VLS_53;
const __VLS_54 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    value: "passed",
}));
const __VLS_56 = __VLS_55({
    value: "passed",
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_57.slots.default;
var __VLS_57;
const __VLS_58 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
    value: "questioned",
}));
const __VLS_60 = __VLS_59({
    value: "questioned",
}, ...__VLS_functionalComponentArgsRest(__VLS_59));
__VLS_61.slots.default;
var __VLS_61;
var __VLS_45;
var __VLS_41;
const __VLS_62 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    label: "科室",
}));
const __VLS_64 = __VLS_63({
    label: "科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
__VLS_65.slots.default;
const __VLS_66 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
    value: (__VLS_ctx.formData.department),
    mode: "multiple",
    placeholder: "选择科室",
    options: (__VLS_ctx.departmentOptions),
    ...{ style: {} },
}));
const __VLS_68 = __VLS_67({
    value: (__VLS_ctx.formData.department),
    mode: "multiple",
    placeholder: "选择科室",
    options: (__VLS_ctx.departmentOptions),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
var __VLS_65;
const __VLS_70 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    label: "医生",
}));
const __VLS_72 = __VLS_71({
    label: "医生",
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
__VLS_73.slots.default;
const __VLS_74 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    value: (__VLS_ctx.formData.doctor),
    mode: "multiple",
    placeholder: "选择医生",
    options: (__VLS_ctx.doctorOptions),
    ...{ style: {} },
    showSearch: true,
    filterOption: (__VLS_ctx.filterOption),
}));
const __VLS_76 = __VLS_75({
    value: (__VLS_ctx.formData.doctor),
    mode: "multiple",
    placeholder: "选择医生",
    options: (__VLS_ctx.doctorOptions),
    ...{ style: {} },
    showSearch: true,
    filterOption: (__VLS_ctx.filterOption),
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
var __VLS_73;
const __VLS_78 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
    label: "优先级",
}));
const __VLS_80 = __VLS_79({
    label: "优先级",
}, ...__VLS_functionalComponentArgsRest(__VLS_79));
__VLS_81.slots.default;
const __VLS_82 = {}.ACheckboxGroup;
/** @type {[typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    value: (__VLS_ctx.formData.priority),
}));
const __VLS_84 = __VLS_83({
    value: (__VLS_ctx.formData.priority),
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
__VLS_85.slots.default;
const __VLS_86 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
    value: "high",
}));
const __VLS_88 = __VLS_87({
    value: "high",
}, ...__VLS_functionalComponentArgsRest(__VLS_87));
__VLS_89.slots.default;
var __VLS_89;
const __VLS_90 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
    value: "medium",
}));
const __VLS_92 = __VLS_91({
    value: "medium",
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
__VLS_93.slots.default;
var __VLS_93;
const __VLS_94 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
    value: "low",
}));
const __VLS_96 = __VLS_95({
    value: "low",
}, ...__VLS_functionalComponentArgsRest(__VLS_95));
__VLS_97.slots.default;
var __VLS_97;
var __VLS_85;
var __VLS_81;
const __VLS_98 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
    label: "评分范围",
}));
const __VLS_100 = __VLS_99({
    label: "评分范围",
}, ...__VLS_functionalComponentArgsRest(__VLS_99));
__VLS_101.slots.default;
const __VLS_102 = {}.ASlider;
/** @type {[typeof __VLS_components.ASlider, typeof __VLS_components.aSlider, ]} */ ;
// @ts-ignore
const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
    value: (__VLS_ctx.formData.scoreRange),
    range: true,
    min: (0),
    max: (100),
    marks: ({ 0: '0', 60: '60', 80: '80', 100: '100' }),
}));
const __VLS_104 = __VLS_103({
    value: (__VLS_ctx.formData.scoreRange),
    range: true,
    min: (0),
    max: (100),
    marks: ({ 0: '0', 60: '60', 80: '80', 100: '100' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_103));
var __VLS_101;
const __VLS_106 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
    label: "缺陷数量",
}));
const __VLS_108 = __VLS_107({
    label: "缺陷数量",
}, ...__VLS_functionalComponentArgsRest(__VLS_107));
__VLS_109.slots.default;
const __VLS_110 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
    value: (__VLS_ctx.formData.defectCountMin),
    placeholder: "最小值",
    min: (0),
    ...{ style: {} },
}));
const __VLS_112 = __VLS_111({
    value: (__VLS_ctx.formData.defectCountMin),
    placeholder: "最小值",
    min: (0),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_111));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ style: {} },
});
const __VLS_114 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
    value: (__VLS_ctx.formData.defectCountMax),
    placeholder: "最大值",
    min: (0),
    ...{ style: {} },
}));
const __VLS_116 = __VLS_115({
    value: (__VLS_ctx.formData.defectCountMax),
    placeholder: "最大值",
    min: (0),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_115));
var __VLS_109;
const __VLS_118 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
    label: "时间范围",
}));
const __VLS_120 = __VLS_119({
    label: "时间范围",
}, ...__VLS_functionalComponentArgsRest(__VLS_119));
__VLS_121.slots.default;
const __VLS_122 = {}.ARangePicker;
/** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
// @ts-ignore
const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
    value: (__VLS_ctx.formData.timeRange),
    ...{ style: {} },
    placeholder: (['开始时间', '结束时间']),
}));
const __VLS_124 = __VLS_123({
    value: (__VLS_ctx.formData.timeRange),
    ...{ style: {} },
    placeholder: (['开始时间', '结束时间']),
}, ...__VLS_functionalComponentArgsRest(__VLS_123));
var __VLS_121;
const __VLS_126 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
    label: "催办状态",
}));
const __VLS_128 = __VLS_127({
    label: "催办状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_127));
__VLS_129.slots.default;
const __VLS_130 = {}.ARadioGroup;
/** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
    value: (__VLS_ctx.formData.isUrgent),
}));
const __VLS_132 = __VLS_131({
    value: (__VLS_ctx.formData.isUrgent),
}, ...__VLS_functionalComponentArgsRest(__VLS_131));
__VLS_133.slots.default;
const __VLS_134 = {}.ARadio;
/** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
// @ts-ignore
const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
    value: (undefined),
}));
const __VLS_136 = __VLS_135({
    value: (undefined),
}, ...__VLS_functionalComponentArgsRest(__VLS_135));
__VLS_137.slots.default;
var __VLS_137;
const __VLS_138 = {}.ARadio;
/** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
// @ts-ignore
const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({
    value: (true),
}));
const __VLS_140 = __VLS_139({
    value: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_139));
__VLS_141.slots.default;
var __VLS_141;
const __VLS_142 = {}.ARadio;
/** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
// @ts-ignore
const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({
    value: (false),
}));
const __VLS_144 = __VLS_143({
    value: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_143));
__VLS_145.slots.default;
var __VLS_145;
var __VLS_133;
var __VLS_129;
var __VLS_13;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "template-section mt-4 pt-4 border-t border-gray-200" },
});
const __VLS_146 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_147 = __VLS_asFunctionalComponent(__VLS_146, new __VLS_146({
    checked: (__VLS_ctx.saveAsTemplate),
}));
const __VLS_148 = __VLS_147({
    checked: (__VLS_ctx.saveAsTemplate),
}, ...__VLS_functionalComponentArgsRest(__VLS_147));
__VLS_149.slots.default;
var __VLS_149;
if (__VLS_ctx.saveAsTemplate) {
    const __VLS_150 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_151 = __VLS_asFunctionalComponent(__VLS_150, new __VLS_150({
        value: (__VLS_ctx.templateName),
        placeholder: "输入模板名称",
        ...{ class: "mt-2" },
        ...{ style: {} },
    }));
    const __VLS_152 = __VLS_151({
        value: (__VLS_ctx.templateName),
        placeholder: "输入模板名称",
        ...{ class: "mt-2" },
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_151));
}
{
    const { footer: __VLS_thisSlot } = __VLS_3.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_154 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({
        ...{ 'onClick': {} },
    }));
    const __VLS_156 = __VLS_155({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_155));
    let __VLS_158;
    let __VLS_159;
    let __VLS_160;
    const __VLS_161 = {
        onClick: (__VLS_ctx.handleReset)
    };
    __VLS_157.slots.default;
    var __VLS_157;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_162 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_163 = __VLS_asFunctionalComponent(__VLS_162, new __VLS_162({
        ...{ 'onClick': {} },
    }));
    const __VLS_164 = __VLS_163({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_163));
    let __VLS_166;
    let __VLS_167;
    let __VLS_168;
    const __VLS_169 = {
        onClick: (__VLS_ctx.handleCancel)
    };
    __VLS_165.slots.default;
    var __VLS_165;
    const __VLS_170 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_171 = __VLS_asFunctionalComponent(__VLS_170, new __VLS_170({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_172 = __VLS_171({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_171));
    let __VLS_174;
    let __VLS_175;
    let __VLS_176;
    const __VLS_177 = {
        onClick: (__VLS_ctx.handleConfirm)
    };
    __VLS_173.slots.default;
    var __VLS_173;
}
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['filter-modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['template-section']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            formData: formData,
            saveAsTemplate: saveAsTemplate,
            templateName: templateName,
            departmentOptions: departmentOptions,
            doctorOptions: doctorOptions,
            filterOption: filterOption,
            handleConfirm: handleConfirm,
            handleCancel: handleCancel,
            handleReset: handleReset,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
