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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import ant_design_vue_1 from 'ant-design-vue';
const dayjs_1 = __importDefault(require("dayjs"));
import icons_vue_1 from '@ant-design/icons-vue';
import medical_records_1 from '@/types/medical-records';
const props = withDefaults(defineProps(), {
    loading: false
});
const emit = defineEmits();
// 表单引用
const formRef = (0, vue_1.ref)();
// 是否为编辑模式
const isEdit = (0, vue_1.computed)(() => !!props.record);
// 表单数据
const formData = (0, vue_1.reactive)({
    patient_name: '',
    patient_age: 0,
    patient_gender: 'U',
    department: '',
    admission_date: '',
    record_type: 'inpatient',
    content: '',
    file: undefined
});
// 文件列表
const fileList = (0, vue_1.ref)(: any[]);
// 上传进度
const uploadProgress = (0, vue_1.reactive)({
    show: false,
    percentage: 0
});
// 科室列表
const departments = medical_records_1.DEPARTMENTS;
// 表单验证规则
const formRules = {
    patient_name: [
        { required: true, message: '请输入患者姓名', trigger: 'blur' },
        { min: 2, message: '患者姓名至少2个字符', trigger: 'blur' },
        { max: 50, message: '患者姓名不能超过50个字符', trigger: 'blur' }
    ],
    patient_age: [
        { required: true, message: '请输入患者年龄', trigger: 'blur' },
        { type: 'number', min: 0, max: 150, message: '年龄必须在0-150之间', trigger: 'blur' }
    ],
    patient_gender: [
        { required: true, message: '请选择患者性别', trigger: 'change' }
    ],
    department: [
        { required: true, message: '请选择科室', trigger: 'change' }
    ],
    admission_date: [
        { required: true, message: '请选择入院时间', trigger: 'change' }
    ],
    record_type: [
        { required: true, message: '请选择记录类型', trigger: 'change' }
    ],
    content: [
        { required: true, message: '请输入病案内容', trigger: 'blur' },
        { min: 50, message: '病案内容至少50个字符', trigger: 'blur' },
        { max: 10000, message: '病案内容不能超过10000个字符', trigger: 'blur' }
    ]
};
// 初始化表单数据
const initializeForm = () => {
    if (props.record) {
        Object.assign(formData, {
            patient_name: props.record.patient_name,
            patient_age: props.record.patient_age,
            patient_gender: props.record.patient_gender,
            department: props.record.department,
            admission_date: props.record.admission_date,
            record_type: props.record.record_type,
            content: props.record.content
        });
        // 如果有文件，添加到文件列表
        if (props.record.file_url) {
            fileList.value = [{
                    uid: '1',
                    name: props.record.file_name || '病案文件',
                    status: 'done',
                    url: props.record.file_url
                }];
        }
    }
};
// 监听record变化
(0, vue_1.watch)(() => props.record, () => {
    initializeForm();
}, { immediate: true, deep: true });
// 处理表单提交
const handleSubmit = async () => {
    try {
        await formRef.value?.validate();
        // 转换日期格式
        const submitData = {
            ...formData,
            admission_date: (0, dayjs_1.default)(formData.admission_date).format('YYYY-MM-DD')
        };
        emit('submit', submitData);
    }
    catch (error) {
        if (error?.errorFields) {
            ant_design_vue_1.message.warning('请检查输入信息');
        }
    }
};
// 处理取消
const handleCancel = () => {
    emit('cancel');
};
// 文件上传前验证
const beforeUpload = (file) => {
    // 检查文件类型
    const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
    if (!allowedTypes.includes(file.type)) {
        ant_design_vue_1.message.error('只支持 PDF、Word、TXT 格式的文件');
        return false;
    }
    // 检查文件大小（10MB）
    const isLt10M = file.size / 1024 / 1024 < 10;
    if (!isLt10M) {
        ant_design_vue_1.message.error('文件大小不能超过 10MB');
        return false;
    }
    return true;
};
// 处理文件上传
const handleFileUpload = async (options) => {
    const { file, onProgress, onSuccess, onError } = options;
    try {
        uploadProgress.show = true;
        uploadProgress.percentage = 0;
        // 模拟上传进度
        const interval = setInterval(() => {
            uploadProgress.percentage += 10;
            onProgress?.({ percent: uploadProgress.percentage });
            if (uploadProgress.percentage >= 100) {
                clearInterval(interval);
                // 模拟上传完成
                setTimeout(() => {
                    formData.file = file;
                    uploadProgress.show = false;
                    onSuccess?.('上传成功');
                    ant_design_vue_1.message.success('文件上传成功');
                }, 500);
            }
        }, 200);
    }
    catch (error) {
        uploadProgress.show = false;
        onError?.(error);
        ant_design_vue_1.message.error('文件上传失败');
    }
};
// 筛选科室选项
const filterDepartment = (input, option) => {
    return option.children.toLowerCase().includes(input.toLowerCase());
};
// 重置表单
const resetForm = () => {
    formRef.value?.resetFields();
    fileList.value = [];
    uploadProgress.show = false;
    uploadProgress.percentage = 0;
    Object.assign(formData, {
        patient_name: '',
        patient_age: 0,
        patient_gender: 'U',
        department: '',
        admission_date: '',
        record_type: 'inpatient',
        content: '',
        file: undefined
    });
};
// 暴露方法给父组件
const __VLS_exposed = {
    resetForm,
    validateForm: () => formRef.value?.validate()
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    loading: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-number']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-picker']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-dragger']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-dragger']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "record-form" },
});
const __VLS_0 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
    size: "large",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
    size: "large",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onFinish: (__VLS_ctx.handleSubmit)
};
/** @type {typeof __VLS_ctx.formRef} */ ;
var __VLS_8 = {};
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 lg:grid-cols-2 gap-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4" },
});
const __VLS_10 = {}.UserOutlined;
/** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
    ...{ class: "text-cyan-400" },
}));
const __VLS_12 = __VLS_11({
    ...{ class: "text-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
const __VLS_14 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
    name: "patient_name",
    ...{ class: "mb-4" },
}));
const __VLS_16 = __VLS_15({
    name: "patient_name",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
__VLS_17.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
const __VLS_18 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
    value: (__VLS_ctx.formData.patient_name),
    placeholder: "请输入患者姓名",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}));
const __VLS_20 = __VLS_19({
    value: (__VLS_ctx.formData.patient_name),
    placeholder: "请输入患者姓名",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
var __VLS_17;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 gap-4" },
});
const __VLS_22 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_23 = __VLS_asFunctionalComponent(__VLS_22, new __VLS_22({
    name: "patient_age",
    ...{ class: "mb-4" },
}));
const __VLS_24 = __VLS_23({
    name: "patient_age",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_23));
__VLS_25.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
const __VLS_26 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
    value: (__VLS_ctx.formData.patient_age),
    placeholder: "年龄",
    min: (0),
    max: (150),
    ...{ class: "w-full h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 focus:border-cyan-400" },
}));
const __VLS_28 = __VLS_27({
    value: (__VLS_ctx.formData.patient_age),
    placeholder: "年龄",
    min: (0),
    max: (150),
    ...{ class: "w-full h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
var __VLS_25;
const __VLS_30 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
    name: "patient_gender",
    ...{ class: "mb-4" },
}));
const __VLS_32 = __VLS_31({
    name: "patient_gender",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
__VLS_33.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
const __VLS_34 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
    value: (__VLS_ctx.formData.patient_gender),
    placeholder: "选择性别",
    ...{ class: "gender-select" },
}));
const __VLS_36 = __VLS_35({
    value: (__VLS_ctx.formData.patient_gender),
    placeholder: "选择性别",
    ...{ class: "gender-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_35));
__VLS_37.slots.default;
const __VLS_38 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
    value: "M",
}));
const __VLS_40 = __VLS_39({
    value: "M",
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
__VLS_41.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-4 h-4 rounded bg-blue-500 flex items-center justify-center text-white text-xs" },
});
var __VLS_41;
const __VLS_42 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
    value: "F",
}));
const __VLS_44 = __VLS_43({
    value: "F",
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
__VLS_45.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-4 h-4 rounded bg-pink-500 flex items-center justify-center text-white text-xs" },
});
var __VLS_45;
const __VLS_46 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
    value: "U",
}));
const __VLS_48 = __VLS_47({
    value: "U",
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
__VLS_49.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-4 h-4 rounded bg-gray-500 flex items-center justify-center text-white text-xs" },
});
var __VLS_49;
var __VLS_37;
var __VLS_33;
const __VLS_50 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
    name: "department",
    ...{ class: "mb-4" },
}));
const __VLS_52 = __VLS_51({
    name: "department",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_51));
__VLS_53.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
const __VLS_54 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    value: (__VLS_ctx.formData.department),
    placeholder: "选择科室",
    showSearch: true,
    filterOption: (__VLS_ctx.filterDepartment),
    ...{ class: "department-select" },
}));
const __VLS_56 = __VLS_55({
    value: (__VLS_ctx.formData.department),
    placeholder: "选择科室",
    showSearch: true,
    filterOption: (__VLS_ctx.filterDepartment),
    ...{ class: "department-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_57.slots.default;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_58 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
        key: (dept),
        value: (dept),
    }));
    const __VLS_60 = __VLS_59({
        key: (dept),
        value: (dept),
    }, ...__VLS_functionalComponentArgsRest(__VLS_59));
    __VLS_61.slots.default;
    (dept);
    var __VLS_61;
}
var __VLS_57;
var __VLS_53;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 gap-4" },
});
const __VLS_62 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    name: "admission_date",
    ...{ class: "mb-4" },
}));
const __VLS_64 = __VLS_63({
    name: "admission_date",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
__VLS_65.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
const __VLS_66 = {}.ADatePicker;
/** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
    value: (__VLS_ctx.formData.admission_date),
    placeholder: "选择入院时间",
    ...{ class: "w-full h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 focus:border-cyan-400" },
    format: "YYYY-MM-DD",
}));
const __VLS_68 = __VLS_67({
    value: (__VLS_ctx.formData.admission_date),
    placeholder: "选择入院时间",
    ...{ class: "w-full h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 focus:border-cyan-400" },
    format: "YYYY-MM-DD",
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
var __VLS_65;
const __VLS_70 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    name: "record_type",
    ...{ class: "mb-4" },
}));
const __VLS_72 = __VLS_71({
    name: "record_type",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
__VLS_73.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
const __VLS_74 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    value: (__VLS_ctx.formData.record_type),
    placeholder: "选择记录类型",
    ...{ class: "record-type-select" },
}));
const __VLS_76 = __VLS_75({
    value: (__VLS_ctx.formData.record_type),
    placeholder: "选择记录类型",
    ...{ class: "record-type-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
__VLS_77.slots.default;
const __VLS_78 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
    value: "inpatient",
}));
const __VLS_80 = __VLS_79({
    value: "inpatient",
}, ...__VLS_functionalComponentArgsRest(__VLS_79));
__VLS_81.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-4 h-4 rounded bg-blue-500" },
});
var __VLS_81;
const __VLS_82 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    value: "outpatient",
}));
const __VLS_84 = __VLS_83({
    value: "outpatient",
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
__VLS_85.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-4 h-4 rounded bg-green-500" },
});
var __VLS_85;
const __VLS_86 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
    value: "emergency",
}));
const __VLS_88 = __VLS_87({
    value: "emergency",
}, ...__VLS_functionalComponentArgsRest(__VLS_87));
__VLS_89.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-4 h-4 rounded bg-red-500" },
});
var __VLS_89;
var __VLS_77;
var __VLS_73;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4" },
});
const __VLS_90 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
    ...{ class: "text-cyan-400" },
}));
const __VLS_92 = __VLS_91({
    ...{ class: "text-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
const __VLS_94 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
    name: "file",
    ...{ class: "mb-4" },
}));
const __VLS_96 = __VLS_95({
    name: "file",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_95));
__VLS_97.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
const __VLS_98 = {}.AUploadDragger;
/** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
// @ts-ignore
const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
    fileList: (__VLS_ctx.fileList),
    customRequest: (__VLS_ctx.handleFileUpload),
    beforeUpload: (__VLS_ctx.beforeUpload),
    showUploadList: (true),
    accept: ".pdf,.doc,.docx,.txt",
    ...{ class: "upload-dragger" },
}));
const __VLS_100 = __VLS_99({
    fileList: (__VLS_ctx.fileList),
    customRequest: (__VLS_ctx.handleFileUpload),
    beforeUpload: (__VLS_ctx.beforeUpload),
    showUploadList: (true),
    accept: ".pdf,.doc,.docx,.txt",
    ...{ class: "upload-dragger" },
}, ...__VLS_functionalComponentArgsRest(__VLS_99));
__VLS_101.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-4" },
});
const __VLS_102 = {}.CloudUploadOutlined;
/** @type {[typeof __VLS_components.CloudUploadOutlined, ]} */ ;
// @ts-ignore
const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
    ...{ class: "text-4xl text-cyan-400" },
}));
const __VLS_104 = __VLS_103({
    ...{ class: "text-4xl text-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_103));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg text-slate-200 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-slate-400" },
});
var __VLS_101;
var __VLS_97;
if (__VLS_ctx.uploadProgress.show) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-sm text-slate-300" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-sm text-slate-400" },
    });
    (__VLS_ctx.uploadProgress.percentage);
    const __VLS_106 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
        percent: (__VLS_ctx.uploadProgress.percentage),
        showInfo: (false),
        strokeColor: "#06b6d4",
    }));
    const __VLS_108 = __VLS_107({
        percent: (__VLS_ctx.uploadProgress.percentage),
        showInfo: (false),
        strokeColor: "#06b6d4",
    }, ...__VLS_functionalComponentArgsRest(__VLS_107));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-6" },
});
const __VLS_110 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
    name: "content",
    ...{ class: "mb-6" },
}));
const __VLS_112 = __VLS_111({
    name: "content",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_111));
__VLS_113.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-sm font-medium text-slate-300 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-red-400 ml-1" },
});
const __VLS_114 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
    value: (__VLS_ctx.formData.content),
    placeholder: "请输入详细的病案内容，包括主诉、现病史、既往史、体格检查、辅助检查、诊断、治疗方案等...",
    rows: (12),
    maxLength: (10000),
    showCount: true,
    ...{ class: "rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}));
const __VLS_116 = __VLS_115({
    value: (__VLS_ctx.formData.content),
    placeholder: "请输入详细的病案内容，包括主诉、现病史、既往史、体格检查、辅助检查、诊断、治疗方案等...",
    rows: (12),
    maxLength: (10000),
    showCount: true,
    ...{ class: "rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_115));
var __VLS_113;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-end gap-4 pt-6 border-t border-slate-700/50" },
});
const __VLS_118 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "h-12 px-8 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20" },
}));
const __VLS_120 = __VLS_119({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "h-12 px-8 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20" },
}, ...__VLS_functionalComponentArgsRest(__VLS_119));
let __VLS_122;
let __VLS_123;
let __VLS_124;
const __VLS_125 = {
    onClick: (__VLS_ctx.handleCancel)
};
__VLS_121.slots.default;
var __VLS_121;
const __VLS_126 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.loading),
    size: "large",
    ...{ class: "h-12 px-8 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none font-semibold shadow-lg hover:shadow-xl" },
}));
const __VLS_128 = __VLS_127({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.loading),
    size: "large",
    ...{ class: "h-12 px-8 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none font-semibold shadow-lg hover:shadow-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_127));
__VLS_129.slots.default;
if (!__VLS_ctx.loading) {
    const __VLS_130 = {}.SaveOutlined;
    /** @type {[typeof __VLS_components.SaveOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
        ...{ class: "mr-2" },
    }));
    const __VLS_132 = __VLS_131({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_131));
}
(__VLS_ctx.isEdit ? '更新记录' : '创建记录');
var __VLS_129;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['record-form']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gender-select']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-pink-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['department-select']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['record-type-select']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-green-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-500']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-dragger']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['px-8']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-white/20']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['px-8']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-r']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-500']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:to-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-none']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
// @ts-ignore
var __VLS_9 = __VLS_8;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            UserOutlined: icons_vue_1.UserOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            CloudUploadOutlined: icons_vue_1.CloudUploadOutlined,
            SaveOutlined: icons_vue_1.SaveOutlined,
            formRef: formRef,
            isEdit: isEdit,
            formData: formData,
            fileList: fileList,
            uploadProgress: uploadProgress,
            departments: departments,
            formRules: formRules,
            handleSubmit: handleSubmit,
            handleCancel: handleCancel,
            beforeUpload: beforeUpload,
            handleFileUpload: handleFileUpload,
            filterDepartment: filterDepartment,
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
