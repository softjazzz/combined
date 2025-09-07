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
// 当前步骤
const currentStep = (0, vue_1.ref)(0);
// 表单引用
const formRef = (0, vue_1.ref)();
// 表单数据
const formData = (0, vue_1.reactive)({
    name: '',
    category: '',
    type: '',
    document: '',
    coreSystemCategory: '',
    infoCategory: '',
    managementSystem: '',
    source: '',
    significance: '',
    errorExample: ''
});
// 表单验证规则
const formRules = {
    name: [
        { required: true, message: '请输入质控点名称', trigger: 'blur' },
        { max: 100, message: '质控点名称不能超过100个字符', trigger: 'blur' }
    ],
    category: [
        { required: true, message: '请选择质控大类', trigger: 'change' }
    ],
    type: [
        { required: true, message: '请选择质控类型', trigger: 'change' }
    ],
    document: [
        { required: true, message: '请选择质控文书', trigger: 'change' }
    ]
};
// 下一步处理
const handleNextStep = async () => {
    try {
        await formRef.value?.validate();
        if (currentStep.value < 2) {
            currentStep.value++;
            ant_design_vue_1.message.success('信息保存成功，进入下一步');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('请完善必填信息');
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-form-item-label']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-control-point-create']} */ ;
/** @type {__VLS_StyleScopedClasses['steps-container']} */ ;
/** @type {__VLS_StyleScopedClasses['step-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['form-container']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-point-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-grid']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "quality-control-point-create" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "breadcrumb-nav mb-4" },
});
const __VLS_0 = {}.ABreadcrumb;
/** @type {[typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    to: "/dashboard",
}));
const __VLS_10 = __VLS_9({
    to: "/dashboard",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
var __VLS_11;
var __VLS_7;
const __VLS_12 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    to: "/dashboard/quality-control",
}));
const __VLS_18 = __VLS_17({
    to: "/dashboard/quality-control",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
var __VLS_19;
var __VLS_15;
const __VLS_20 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
var __VLS_23;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "steps-container mb-8" },
});
const __VLS_24 = {}.ASteps;
/** @type {[typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    current: (__VLS_ctx.currentStep),
    ...{ class: "custom-steps" },
}));
const __VLS_26 = __VLS_25({
    current: (__VLS_ctx.currentStep),
    ...{ class: "custom-steps" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    title: "填写信息",
}));
const __VLS_30 = __VLS_29({
    title: "填写信息",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
const __VLS_32 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    title: "配置规则",
}));
const __VLS_34 = __VLS_33({
    title: "配置规则",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
const __VLS_36 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    title: "测试",
}));
const __VLS_38 = __VLS_37({
    title: "测试",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
var __VLS_27;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "step-actions" },
});
const __VLS_40 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "next-btn" },
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "next-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (__VLS_ctx.handleNextStep)
};
__VLS_43.slots.default;
var __VLS_43;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-container" },
});
const __VLS_48 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    ref: "formRef",
    layout: "vertical",
    ...{ class: "quality-point-form" },
}));
const __VLS_50 = __VLS_49({
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    ref: "formRef",
    layout: "vertical",
    ...{ class: "quality-point-form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
/** @type {typeof __VLS_ctx.formRef} */ ;
var __VLS_52 = {};
__VLS_51.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-grid" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-column" },
});
const __VLS_54 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    label: "质控点名称",
    name: "name",
    ...{ class: "required-field" },
}));
const __VLS_56 = __VLS_55({
    label: "质控点名称",
    name: "name",
    ...{ class: "required-field" },
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_57.slots.default;
const __VLS_58 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
    value: (__VLS_ctx.formData.name),
    placeholder: "请输入，最多100字",
    maxlength: (100),
    showCount: true,
}));
const __VLS_60 = __VLS_59({
    value: (__VLS_ctx.formData.name),
    placeholder: "请输入，最多100字",
    maxlength: (100),
    showCount: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_59));
var __VLS_57;
const __VLS_62 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    label: "质控类型",
    name: "type",
    ...{ class: "required-field" },
}));
const __VLS_64 = __VLS_63({
    label: "质控类型",
    name: "type",
    ...{ class: "required-field" },
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
__VLS_65.slots.default;
const __VLS_66 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
    value: (__VLS_ctx.formData.type),
    placeholder: "请选择",
    allowClear: true,
}));
const __VLS_68 = __VLS_67({
    value: (__VLS_ctx.formData.type),
    placeholder: "请选择",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
__VLS_69.slots.default;
const __VLS_70 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    value: "规范性",
}));
const __VLS_72 = __VLS_71({
    value: "规范性",
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
__VLS_73.slots.default;
var __VLS_73;
const __VLS_74 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    value: "完整性",
}));
const __VLS_76 = __VLS_75({
    value: "完整性",
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
__VLS_77.slots.default;
var __VLS_77;
const __VLS_78 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
    value: "及时性",
}));
const __VLS_80 = __VLS_79({
    value: "及时性",
}, ...__VLS_functionalComponentArgsRest(__VLS_79));
__VLS_81.slots.default;
var __VLS_81;
var __VLS_69;
var __VLS_65;
const __VLS_82 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    label: "质控文书",
    name: "document",
    ...{ class: "required-field" },
}));
const __VLS_84 = __VLS_83({
    label: "质控文书",
    name: "document",
    ...{ class: "required-field" },
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
__VLS_85.slots.default;
const __VLS_86 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
    value: (__VLS_ctx.formData.document),
    placeholder: "请选择",
    allowClear: true,
}));
const __VLS_88 = __VLS_87({
    value: (__VLS_ctx.formData.document),
    placeholder: "请选择",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_87));
__VLS_89.slots.default;
const __VLS_90 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
    value: "入院记录",
}));
const __VLS_92 = __VLS_91({
    value: "入院记录",
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
__VLS_93.slots.default;
var __VLS_93;
const __VLS_94 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
    value: "病案首页",
}));
const __VLS_96 = __VLS_95({
    value: "病案首页",
}, ...__VLS_functionalComponentArgsRest(__VLS_95));
__VLS_97.slots.default;
var __VLS_97;
const __VLS_98 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
    value: "出院记录",
}));
const __VLS_100 = __VLS_99({
    value: "出院记录",
}, ...__VLS_functionalComponentArgsRest(__VLS_99));
__VLS_101.slots.default;
var __VLS_101;
var __VLS_89;
var __VLS_85;
const __VLS_102 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
    label: "质量管理制度",
    name: "managementSystem",
}));
const __VLS_104 = __VLS_103({
    label: "质量管理制度",
    name: "managementSystem",
}, ...__VLS_functionalComponentArgsRest(__VLS_103));
__VLS_105.slots.default;
const __VLS_106 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
    value: (__VLS_ctx.formData.managementSystem),
    placeholder: "请选择",
    allowClear: true,
}));
const __VLS_108 = __VLS_107({
    value: (__VLS_ctx.formData.managementSystem),
    placeholder: "请选择",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_107));
__VLS_109.slots.default;
const __VLS_110 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
    value: "核心制度",
}));
const __VLS_112 = __VLS_111({
    value: "核心制度",
}, ...__VLS_functionalComponentArgsRest(__VLS_111));
__VLS_113.slots.default;
var __VLS_113;
const __VLS_114 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
    value: "一般制度",
}));
const __VLS_116 = __VLS_115({
    value: "一般制度",
}, ...__VLS_functionalComponentArgsRest(__VLS_115));
__VLS_117.slots.default;
var __VLS_117;
var __VLS_109;
var __VLS_105;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-column" },
});
const __VLS_118 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
    label: "质控大类",
    name: "category",
    ...{ class: "required-field" },
}));
const __VLS_120 = __VLS_119({
    label: "质控大类",
    name: "category",
    ...{ class: "required-field" },
}, ...__VLS_functionalComponentArgsRest(__VLS_119));
__VLS_121.slots.default;
const __VLS_122 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
    value: (__VLS_ctx.formData.category),
    placeholder: "请选择",
    allowClear: true,
}));
const __VLS_124 = __VLS_123({
    value: (__VLS_ctx.formData.category),
    placeholder: "请选择",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_123));
__VLS_125.slots.default;
const __VLS_126 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
    value: "病历书写与管理基本规范",
}));
const __VLS_128 = __VLS_127({
    value: "病历书写与管理基本规范",
}, ...__VLS_functionalComponentArgsRest(__VLS_127));
__VLS_129.slots.default;
var __VLS_129;
const __VLS_130 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
    value: "诊疗规范",
}));
const __VLS_132 = __VLS_131({
    value: "诊疗规范",
}, ...__VLS_functionalComponentArgsRest(__VLS_131));
__VLS_133.slots.default;
var __VLS_133;
const __VLS_134 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
    value: "医疗安全",
}));
const __VLS_136 = __VLS_135({
    value: "医疗安全",
}, ...__VLS_functionalComponentArgsRest(__VLS_135));
__VLS_137.slots.default;
var __VLS_137;
var __VLS_125;
var __VLS_121;
const __VLS_138 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({
    label: "核心制度分类",
    name: "coreSystemCategory",
}));
const __VLS_140 = __VLS_139({
    label: "核心制度分类",
    name: "coreSystemCategory",
}, ...__VLS_functionalComponentArgsRest(__VLS_139));
__VLS_141.slots.default;
const __VLS_142 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({
    value: (__VLS_ctx.formData.coreSystemCategory),
    placeholder: "请选择",
    allowClear: true,
}));
const __VLS_144 = __VLS_143({
    value: (__VLS_ctx.formData.coreSystemCategory),
    placeholder: "请选择",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_143));
__VLS_145.slots.default;
const __VLS_146 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_147 = __VLS_asFunctionalComponent(__VLS_146, new __VLS_146({
    value: "首诊负责制",
}));
const __VLS_148 = __VLS_147({
    value: "首诊负责制",
}, ...__VLS_functionalComponentArgsRest(__VLS_147));
__VLS_149.slots.default;
var __VLS_149;
const __VLS_150 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_151 = __VLS_asFunctionalComponent(__VLS_150, new __VLS_150({
    value: "三级查房制",
}));
const __VLS_152 = __VLS_151({
    value: "三级查房制",
}, ...__VLS_functionalComponentArgsRest(__VLS_151));
__VLS_153.slots.default;
var __VLS_153;
const __VLS_154 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({
    value: "疑难病例讨论制",
}));
const __VLS_156 = __VLS_155({
    value: "疑难病例讨论制",
}, ...__VLS_functionalComponentArgsRest(__VLS_155));
__VLS_157.slots.default;
var __VLS_157;
var __VLS_145;
var __VLS_141;
const __VLS_158 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_159 = __VLS_asFunctionalComponent(__VLS_158, new __VLS_158({
    label: "质控信息分类",
    name: "infoCategory",
}));
const __VLS_160 = __VLS_159({
    label: "质控信息分类",
    name: "infoCategory",
}, ...__VLS_functionalComponentArgsRest(__VLS_159));
__VLS_161.slots.default;
const __VLS_162 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_163 = __VLS_asFunctionalComponent(__VLS_162, new __VLS_162({
    value: (__VLS_ctx.formData.infoCategory),
    placeholder: "请选择",
    allowClear: true,
}));
const __VLS_164 = __VLS_163({
    value: (__VLS_ctx.formData.infoCategory),
    placeholder: "请选择",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_163));
__VLS_165.slots.default;
const __VLS_166 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_167 = __VLS_asFunctionalComponent(__VLS_166, new __VLS_166({
    value: "基础信息",
}));
const __VLS_168 = __VLS_167({
    value: "基础信息",
}, ...__VLS_functionalComponentArgsRest(__VLS_167));
__VLS_169.slots.default;
var __VLS_169;
const __VLS_170 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_171 = __VLS_asFunctionalComponent(__VLS_170, new __VLS_170({
    value: "诊疗信息",
}));
const __VLS_172 = __VLS_171({
    value: "诊疗信息",
}, ...__VLS_functionalComponentArgsRest(__VLS_171));
__VLS_173.slots.default;
var __VLS_173;
const __VLS_174 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_175 = __VLS_asFunctionalComponent(__VLS_174, new __VLS_174({
    value: "管理信息",
}));
const __VLS_176 = __VLS_175({
    value: "管理信息",
}, ...__VLS_functionalComponentArgsRest(__VLS_175));
__VLS_177.slots.default;
var __VLS_177;
var __VLS_165;
var __VLS_161;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "textarea-fields" },
});
const __VLS_178 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_179 = __VLS_asFunctionalComponent(__VLS_178, new __VLS_178({
    label: "质控点来源",
    name: "source",
}));
const __VLS_180 = __VLS_179({
    label: "质控点来源",
    name: "source",
}, ...__VLS_functionalComponentArgsRest(__VLS_179));
__VLS_181.slots.default;
const __VLS_182 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_183 = __VLS_asFunctionalComponent(__VLS_182, new __VLS_182({
    value: (__VLS_ctx.formData.source),
    placeholder: "请输入内容",
    rows: (4),
    maxlength: (500),
    showCount: true,
}));
const __VLS_184 = __VLS_183({
    value: (__VLS_ctx.formData.source),
    placeholder: "请输入内容",
    rows: (4),
    maxlength: (500),
    showCount: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_183));
var __VLS_181;
const __VLS_186 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_187 = __VLS_asFunctionalComponent(__VLS_186, new __VLS_186({
    label: "质控点意义说明",
    name: "significance",
}));
const __VLS_188 = __VLS_187({
    label: "质控点意义说明",
    name: "significance",
}, ...__VLS_functionalComponentArgsRest(__VLS_187));
__VLS_189.slots.default;
const __VLS_190 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_191 = __VLS_asFunctionalComponent(__VLS_190, new __VLS_190({
    value: (__VLS_ctx.formData.significance),
    placeholder: "请输入内容",
    rows: (4),
    maxlength: (500),
    showCount: true,
}));
const __VLS_192 = __VLS_191({
    value: (__VLS_ctx.formData.significance),
    placeholder: "请输入内容",
    rows: (4),
    maxlength: (500),
    showCount: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_191));
var __VLS_189;
const __VLS_194 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_195 = __VLS_asFunctionalComponent(__VLS_194, new __VLS_194({
    label: "质控点错误示例",
    name: "errorExample",
}));
const __VLS_196 = __VLS_195({
    label: "质控点错误示例",
    name: "errorExample",
}, ...__VLS_functionalComponentArgsRest(__VLS_195));
__VLS_197.slots.default;
const __VLS_198 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_199 = __VLS_asFunctionalComponent(__VLS_198, new __VLS_198({
    value: (__VLS_ctx.formData.errorExample),
    placeholder: "请输入内容",
    rows: (4),
    maxlength: (500),
    showCount: true,
}));
const __VLS_200 = __VLS_199({
    value: (__VLS_ctx.formData.errorExample),
    placeholder: "请输入内容",
    rows: (4),
    maxlength: (500),
    showCount: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_199));
var __VLS_197;
var __VLS_51;
/** @type {__VLS_StyleScopedClasses['quality-control-point-create']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb-nav']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['steps-container']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-steps']} */ ;
/** @type {__VLS_StyleScopedClasses['step-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['next-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['form-container']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-point-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['form-column']} */ ;
/** @type {__VLS_StyleScopedClasses['required-field']} */ ;
/** @type {__VLS_StyleScopedClasses['required-field']} */ ;
/** @type {__VLS_StyleScopedClasses['required-field']} */ ;
/** @type {__VLS_StyleScopedClasses['form-column']} */ ;
/** @type {__VLS_StyleScopedClasses['required-field']} */ ;
/** @type {__VLS_StyleScopedClasses['textarea-fields']} */ ;
// @ts-ignore
var __VLS_53 = __VLS_52;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            currentStep: currentStep,
            formRef: formRef,
            formData: formData,
            formRules: formRules,
            handleNextStep: handleNextStep,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
