"use strict";
/// <reference types="../../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
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
import vue_router_1 from 'vue-router';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const router = (0, vue_router_1.useRouter)();
const formRef = (0, vue_1.ref)();
const submitting = (0, vue_1.ref)(false);
// 表单数据
const formData = (0, vue_1.reactive)({
    recordNumber: '',
    recordName: '',
    department: '',
    primaryDiagnosis: '',
    majorSurgery: '',
    documents: []
});
// 表单验证规则
const formRules = {
    recordName: [
        { required: true, message: '请输入病历名称', trigger: 'blur' }
    ],
    department: [
        { required: true, message: '请选择出院科室', trigger: 'change' }
    ],
    primaryDiagnosis: [
        { required: true, message: '请输入主诊断', trigger: 'blur' }
    ]
};
// 生命周期
(0, vue_1.onMounted)(() => {
    generateRecordNumber();
});
// 生成病历编号
const generateRecordNumber = () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
    formData.recordNumber = `MR${year}${month}${day}${random}`;
};
// 添加文书
const addDocument = () => {
    const newDocument = {
        id: `doc_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: '入院记录',
        title: '',
        content: ''
    };
    formData.documents.push(newDocument);
};
// 删除文书
const removeDocument = (index) => {
    formData.documents.splice(index, 1);
};
// 提交表单
const handleSubmit = async () => {
    try {
        submitting.value = true;
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1500));
        ant_design_vue_1.message.success('病历创建成功');
        router.push('/dashboard/medical-records');
    }
    catch (error) {
        ant_design_vue_1.message.error('创建失败，请重试');
    }
    finally {
        submitting.value = false;
    }
};
// 取消操作
const handleCancel = () => {
    router.back();
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['document-header']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-breadcrumb']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-breadcrumb']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-container" },
});
const __VLS_0 = {}.ABreadcrumb;
/** @type {[typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "breadcrumb" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "breadcrumb" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
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
    to: "/dashboard/medical-records",
}));
const __VLS_10 = __VLS_9({
    to: "/dashboard/medical-records",
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
var __VLS_15;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
const __VLS_16 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
}));
const __VLS_18 = __VLS_17({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onFinish: (__VLS_ctx.handleSubmit)
};
/** @type {typeof __VLS_ctx.formRef} */ ;
var __VLS_24 = {};
__VLS_19.slots.default;
const __VLS_26 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
    title: "病历基本信息",
    ...{ class: "form-card" },
}));
const __VLS_28 = __VLS_27({
    title: "病历基本信息",
    ...{ class: "form-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_29.slots.default;
const __VLS_30 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
    gutter: (16),
}));
const __VLS_32 = __VLS_31({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
__VLS_33.slots.default;
const __VLS_34 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
    span: (12),
}));
const __VLS_36 = __VLS_35({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_35));
__VLS_37.slots.default;
const __VLS_38 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
    label: "病历编号",
    name: "recordNumber",
}));
const __VLS_40 = __VLS_39({
    label: "病历编号",
    name: "recordNumber",
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
__VLS_41.slots.default;
const __VLS_42 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
    value: (__VLS_ctx.formData.recordNumber),
    placeholder: "自动生成",
    disabled: true,
}));
const __VLS_44 = __VLS_43({
    value: (__VLS_ctx.formData.recordNumber),
    placeholder: "自动生成",
    disabled: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
var __VLS_41;
var __VLS_37;
const __VLS_46 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
    span: (12),
}));
const __VLS_48 = __VLS_47({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
__VLS_49.slots.default;
const __VLS_50 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
    label: "病历名称",
    name: "recordName",
}));
const __VLS_52 = __VLS_51({
    label: "病历名称",
    name: "recordName",
}, ...__VLS_functionalComponentArgsRest(__VLS_51));
__VLS_53.slots.default;
const __VLS_54 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    value: (__VLS_ctx.formData.recordName),
    placeholder: "请输入病历名称",
}));
const __VLS_56 = __VLS_55({
    value: (__VLS_ctx.formData.recordName),
    placeholder: "请输入病历名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
var __VLS_53;
var __VLS_49;
var __VLS_33;
const __VLS_58 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
    gutter: (16),
}));
const __VLS_60 = __VLS_59({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_59));
__VLS_61.slots.default;
const __VLS_62 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    span: (12),
}));
const __VLS_64 = __VLS_63({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
__VLS_65.slots.default;
const __VLS_66 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
    label: "出院科室",
    name: "department",
}));
const __VLS_68 = __VLS_67({
    label: "出院科室",
    name: "department",
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
__VLS_69.slots.default;
const __VLS_70 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    value: (__VLS_ctx.formData.department),
    placeholder: "请选择出院科室",
}));
const __VLS_72 = __VLS_71({
    value: (__VLS_ctx.formData.department),
    placeholder: "请选择出院科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
__VLS_73.slots.default;
const __VLS_74 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    value: "内科",
}));
const __VLS_76 = __VLS_75({
    value: "内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
__VLS_77.slots.default;
var __VLS_77;
const __VLS_78 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
    value: "外科",
}));
const __VLS_80 = __VLS_79({
    value: "外科",
}, ...__VLS_functionalComponentArgsRest(__VLS_79));
__VLS_81.slots.default;
var __VLS_81;
const __VLS_82 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    value: "妇产科",
}));
const __VLS_84 = __VLS_83({
    value: "妇产科",
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
__VLS_85.slots.default;
var __VLS_85;
const __VLS_86 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
    value: "儿科",
}));
const __VLS_88 = __VLS_87({
    value: "儿科",
}, ...__VLS_functionalComponentArgsRest(__VLS_87));
__VLS_89.slots.default;
var __VLS_89;
const __VLS_90 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
    value: "急诊科",
}));
const __VLS_92 = __VLS_91({
    value: "急诊科",
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
__VLS_93.slots.default;
var __VLS_93;
const __VLS_94 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
    value: "骨科",
}));
const __VLS_96 = __VLS_95({
    value: "骨科",
}, ...__VLS_functionalComponentArgsRest(__VLS_95));
__VLS_97.slots.default;
var __VLS_97;
const __VLS_98 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
    value: "神经科",
}));
const __VLS_100 = __VLS_99({
    value: "神经科",
}, ...__VLS_functionalComponentArgsRest(__VLS_99));
__VLS_101.slots.default;
var __VLS_101;
const __VLS_102 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
    value: "心内科",
}));
const __VLS_104 = __VLS_103({
    value: "心内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_103));
__VLS_105.slots.default;
var __VLS_105;
var __VLS_73;
var __VLS_69;
var __VLS_65;
const __VLS_106 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
    span: (12),
}));
const __VLS_108 = __VLS_107({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_107));
__VLS_109.slots.default;
const __VLS_110 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
    label: "主诊断",
    name: "primaryDiagnosis",
}));
const __VLS_112 = __VLS_111({
    label: "主诊断",
    name: "primaryDiagnosis",
}, ...__VLS_functionalComponentArgsRest(__VLS_111));
__VLS_113.slots.default;
const __VLS_114 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
    value: (__VLS_ctx.formData.primaryDiagnosis),
    placeholder: "请输入主诊断",
}));
const __VLS_116 = __VLS_115({
    value: (__VLS_ctx.formData.primaryDiagnosis),
    placeholder: "请输入主诊断",
}, ...__VLS_functionalComponentArgsRest(__VLS_115));
var __VLS_113;
var __VLS_109;
var __VLS_61;
const __VLS_118 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
    gutter: (16),
}));
const __VLS_120 = __VLS_119({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_119));
__VLS_121.slots.default;
const __VLS_122 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
    span: (24),
}));
const __VLS_124 = __VLS_123({
    span: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_123));
__VLS_125.slots.default;
const __VLS_126 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
    label: "主要手术及操作",
    name: "majorSurgery",
}));
const __VLS_128 = __VLS_127({
    label: "主要手术及操作",
    name: "majorSurgery",
}, ...__VLS_functionalComponentArgsRest(__VLS_127));
__VLS_129.slots.default;
const __VLS_130 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
    value: (__VLS_ctx.formData.majorSurgery),
    placeholder: "请输入主要手术及操作（可选）",
    rows: (3),
}));
const __VLS_132 = __VLS_131({
    value: (__VLS_ctx.formData.majorSurgery),
    placeholder: "请输入主要手术及操作（可选）",
    rows: (3),
}, ...__VLS_functionalComponentArgsRest(__VLS_131));
var __VLS_129;
var __VLS_125;
var __VLS_121;
var __VLS_29;
const __VLS_134 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
    title: "文书信息",
    ...{ class: "form-card" },
}));
const __VLS_136 = __VLS_135({
    title: "文书信息",
    ...{ class: "form-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_135));
__VLS_137.slots.default;
if (__VLS_ctx.formData.documents.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-documents" },
    });
    const __VLS_138 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({
        description: "暂无文书，请添加文书信息",
    }));
    const __VLS_140 = __VLS_139({
        description: "暂无文书，请添加文书信息",
    }, ...__VLS_functionalComponentArgsRest(__VLS_139));
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "documents-list" },
    });
    for (const [document, index] of __VLS_getVForSourceType((__VLS_ctx.formData.documents))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (document.id),
            ...{ class: "document-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        (index + 1);
        (document.type);
        const __VLS_142 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({
            ...{ 'onClick': {} },
            type: "text",
            danger: true,
            size: "small",
        }));
        const __VLS_144 = __VLS_143({
            ...{ 'onClick': {} },
            type: "text",
            danger: true,
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_143));
        let __VLS_146;
        let __VLS_147;
        let __VLS_148;
        const __VLS_149 = {
            onClick: (...[$event]) => {
                if (!!(__VLS_ctx.formData.documents.length === 0))
                    return;
                __VLS_ctx.removeDocument(index);
            }
        };
        __VLS_145.slots.default;
        var __VLS_145;
        const __VLS_150 = {}.ARow;
        /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
        // @ts-ignore
        const __VLS_151 = __VLS_asFunctionalComponent(__VLS_150, new __VLS_150({
            gutter: (16),
        }));
        const __VLS_152 = __VLS_151({
            gutter: (16),
        }, ...__VLS_functionalComponentArgsRest(__VLS_151));
        __VLS_153.slots.default;
        const __VLS_154 = {}.ACol;
        /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
        // @ts-ignore
        const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({
            span: (8),
        }));
        const __VLS_156 = __VLS_155({
            span: (8),
        }, ...__VLS_functionalComponentArgsRest(__VLS_155));
        __VLS_157.slots.default;
        const __VLS_158 = {}.AFormItem;
        /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
        // @ts-ignore
        const __VLS_159 = __VLS_asFunctionalComponent(__VLS_158, new __VLS_158({
            name: (['documents', index, 'type']),
            label: "文书类型",
        }));
        const __VLS_160 = __VLS_159({
            name: (['documents', index, 'type']),
            label: "文书类型",
        }, ...__VLS_functionalComponentArgsRest(__VLS_159));
        __VLS_161.slots.default;
        const __VLS_162 = {}.ASelect;
        /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
        // @ts-ignore
        const __VLS_163 = __VLS_asFunctionalComponent(__VLS_162, new __VLS_162({
            value: (document.type),
            placeholder: "请选择文书类型",
        }));
        const __VLS_164 = __VLS_163({
            value: (document.type),
            placeholder: "请选择文书类型",
        }, ...__VLS_functionalComponentArgsRest(__VLS_163));
        __VLS_165.slots.default;
        const __VLS_166 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_167 = __VLS_asFunctionalComponent(__VLS_166, new __VLS_166({
            value: "入院记录",
        }));
        const __VLS_168 = __VLS_167({
            value: "入院记录",
        }, ...__VLS_functionalComponentArgsRest(__VLS_167));
        __VLS_169.slots.default;
        var __VLS_169;
        const __VLS_170 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_171 = __VLS_asFunctionalComponent(__VLS_170, new __VLS_170({
            value: "病程记录",
        }));
        const __VLS_172 = __VLS_171({
            value: "病程记录",
        }, ...__VLS_functionalComponentArgsRest(__VLS_171));
        __VLS_173.slots.default;
        var __VLS_173;
        const __VLS_174 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_175 = __VLS_asFunctionalComponent(__VLS_174, new __VLS_174({
            value: "出院记录",
        }));
        const __VLS_176 = __VLS_175({
            value: "出院记录",
        }, ...__VLS_functionalComponentArgsRest(__VLS_175));
        __VLS_177.slots.default;
        var __VLS_177;
        const __VLS_178 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_179 = __VLS_asFunctionalComponent(__VLS_178, new __VLS_178({
            value: "手术记录",
        }));
        const __VLS_180 = __VLS_179({
            value: "手术记录",
        }, ...__VLS_functionalComponentArgsRest(__VLS_179));
        __VLS_181.slots.default;
        var __VLS_181;
        const __VLS_182 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_183 = __VLS_asFunctionalComponent(__VLS_182, new __VLS_182({
            value: "会诊记录",
        }));
        const __VLS_184 = __VLS_183({
            value: "会诊记录",
        }, ...__VLS_functionalComponentArgsRest(__VLS_183));
        __VLS_185.slots.default;
        var __VLS_185;
        const __VLS_186 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_187 = __VLS_asFunctionalComponent(__VLS_186, new __VLS_186({
            value: "检查报告",
        }));
        const __VLS_188 = __VLS_187({
            value: "检查报告",
        }, ...__VLS_functionalComponentArgsRest(__VLS_187));
        __VLS_189.slots.default;
        var __VLS_189;
        const __VLS_190 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_191 = __VLS_asFunctionalComponent(__VLS_190, new __VLS_190({
            value: "化验报告",
        }));
        const __VLS_192 = __VLS_191({
            value: "化验报告",
        }, ...__VLS_functionalComponentArgsRest(__VLS_191));
        __VLS_193.slots.default;
        var __VLS_193;
        var __VLS_165;
        var __VLS_161;
        var __VLS_157;
        const __VLS_194 = {}.ACol;
        /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
        // @ts-ignore
        const __VLS_195 = __VLS_asFunctionalComponent(__VLS_194, new __VLS_194({
            span: (16),
        }));
        const __VLS_196 = __VLS_195({
            span: (16),
        }, ...__VLS_functionalComponentArgsRest(__VLS_195));
        __VLS_197.slots.default;
        const __VLS_198 = {}.AFormItem;
        /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
        // @ts-ignore
        const __VLS_199 = __VLS_asFunctionalComponent(__VLS_198, new __VLS_198({
            name: (['documents', index, 'title']),
            label: "文书标题",
        }));
        const __VLS_200 = __VLS_199({
            name: (['documents', index, 'title']),
            label: "文书标题",
        }, ...__VLS_functionalComponentArgsRest(__VLS_199));
        __VLS_201.slots.default;
        const __VLS_202 = {}.AInput;
        /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
        // @ts-ignore
        const __VLS_203 = __VLS_asFunctionalComponent(__VLS_202, new __VLS_202({
            value: (document.title),
            placeholder: "请输入文书标题",
        }));
        const __VLS_204 = __VLS_203({
            value: (document.title),
            placeholder: "请输入文书标题",
        }, ...__VLS_functionalComponentArgsRest(__VLS_203));
        var __VLS_201;
        var __VLS_197;
        var __VLS_153;
        const __VLS_206 = {}.AFormItem;
        /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
        // @ts-ignore
        const __VLS_207 = __VLS_asFunctionalComponent(__VLS_206, new __VLS_206({
            name: (['documents', index, 'content']),
            label: "文书内容",
        }));
        const __VLS_208 = __VLS_207({
            name: (['documents', index, 'content']),
            label: "文书内容",
        }, ...__VLS_functionalComponentArgsRest(__VLS_207));
        __VLS_209.slots.default;
        const __VLS_210 = {}.ATextarea;
        /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
        // @ts-ignore
        const __VLS_211 = __VLS_asFunctionalComponent(__VLS_210, new __VLS_210({
            value: (document.content),
            placeholder: "请输入文书内容",
            rows: (6),
        }));
        const __VLS_212 = __VLS_211({
            value: (document.content),
            placeholder: "请输入文书内容",
            rows: (6),
        }, ...__VLS_functionalComponentArgsRest(__VLS_211));
        var __VLS_209;
    }
}
var __VLS_137;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "left-actions" },
});
const __VLS_214 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_215 = __VLS_asFunctionalComponent(__VLS_214, new __VLS_214({
    ...{ 'onClick': {} },
    type: "dashed",
}));
const __VLS_216 = __VLS_215({
    ...{ 'onClick': {} },
    type: "dashed",
}, ...__VLS_functionalComponentArgsRest(__VLS_215));
let __VLS_218;
let __VLS_219;
let __VLS_220;
const __VLS_221 = {
    onClick: (__VLS_ctx.addDocument)
};
__VLS_217.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_217.slots;
    const __VLS_222 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_223 = __VLS_asFunctionalComponent(__VLS_222, new __VLS_222({}));
    const __VLS_224 = __VLS_223({}, ...__VLS_functionalComponentArgsRest(__VLS_223));
}
var __VLS_217;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "right-actions" },
});
const __VLS_226 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_227 = __VLS_asFunctionalComponent(__VLS_226, new __VLS_226({}));
const __VLS_228 = __VLS_227({}, ...__VLS_functionalComponentArgsRest(__VLS_227));
__VLS_229.slots.default;
const __VLS_230 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_231 = __VLS_asFunctionalComponent(__VLS_230, new __VLS_230({
    ...{ 'onClick': {} },
}));
const __VLS_232 = __VLS_231({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_231));
let __VLS_234;
let __VLS_235;
let __VLS_236;
const __VLS_237 = {
    onClick: (__VLS_ctx.handleCancel)
};
__VLS_233.slots.default;
var __VLS_233;
const __VLS_238 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_239 = __VLS_asFunctionalComponent(__VLS_238, new __VLS_238({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.submitting),
}));
const __VLS_240 = __VLS_239({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.submitting),
}, ...__VLS_functionalComponentArgsRest(__VLS_239));
__VLS_241.slots.default;
var __VLS_241;
var __VLS_229;
var __VLS_19;
/** @type {__VLS_StyleScopedClasses['page-container']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['no-documents']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-list']} */ ;
/** @type {__VLS_StyleScopedClasses['document-item']} */ ;
/** @type {__VLS_StyleScopedClasses['document-header']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['left-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['right-actions']} */ ;
// @ts-ignore
var __VLS_25 = __VLS_24;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            PlusOutlined: icons_vue_1.PlusOutlined,
            formRef: formRef,
            submitting: submitting,
            formData: formData,
            formRules: formRules,
            addDocument: addDocument,
            removeDocument: removeDocument,
            handleSubmit: handleSubmit,
            handleCancel: handleCancel,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
