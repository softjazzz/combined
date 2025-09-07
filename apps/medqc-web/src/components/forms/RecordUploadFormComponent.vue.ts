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
import medical_records_1 from '../../types/medical-records';
import useFileUpload_1 from '../../composables/useFileUpload';
import validation_1 from '../../utils/validation';
import error_handler_1 from '../../utils/error-handler';
const props = withDefaults(defineProps(), {
    loading: false
});
const emit = defineEmits();
// 响应式数据
const formRef = (0, vue_1.ref)();
const inputMode = (0, vue_1.ref)('text');
const isSubmitting = (0, vue_1.ref)(false);
const fileContent = (0, vue_1.ref)('');
const fileList = (0, vue_1.ref)(: any[]);
// 表单数据
const formData = (0, vue_1.reactive)({
    patient_name: '',
    patient_age: undefined,
    patient_gender: undefined,
    department: undefined,
    admission_date: undefined,
    record_type: 'inpatient',
    content: ''
});
// 表单验证规则
const formRules = {
    patient_name: validation_1.AntdValidationRules.patientName,
    patient_age: validation_1.AntdValidationRules.patientAge,
    patient_gender: validation_1.AntdValidationRules.required('患者性别'),
    department: validation_1.AntdValidationRules.department,
    admission_date: validation_1.AntdValidationRules.required('入院日期'),
    record_type: validation_1.AntdValidationRules.required('记录类型'),
    content: validation_1.AntdValidationRules.medicalContent
};
// 文件上传相关
const { formatFileSize } = (0, useFileUpload_1.useFileUpload)();
// 计算属性
const hasContent = (0, vue_1.computed)(() => {
    return formData.content.trim().length > 0 || fileContent.value.length > 0;
});
const hasValidContent = (0, vue_1.computed)(() => {
    const content = inputMode.value === 'text' ? formData.content : fileContent.value;
    return content.trim().length >= 50; // 至少50个字符
});
// 监听输入模式变化
(0, vue_1.watch)(inputMode: any,  (newMode: any) => {
    if (newMode === 'text') {
        fileList.value = [];
        fileContent.value = '';
    }
    else {
        formData.content = '';
    }
});
// 文件上传处理
const handleBeforeUpload = async (file) => {
    // 验证文件类型
    const allowedTypes = [
        'text/plain',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];
    if (!allowedTypes.includes(file.type)) {
        ant_design_vue_1.message.error('不支持的文件格式');
        return false;
    }
    // 验证文件大小
    if (file.size > 10 * 1024 * 1024) {
        ant_design_vue_1.message.error('文件大小不能超过 10MB');
        return false;
    }
    // 根据文件类型显示不同的信息
    if (file.type === 'text/plain' || file.name.endsWith('.txt')) {
        // 文本文件可以预览
        const reader = new FileReader();
        reader.onload = (e) => {
            const content = e.target?.result;
            fileContent.value = content.substring(0, 1000) + (content.length > 1000 ? '\n\n...(内容已截断)' : '');
        };
        reader.onerror = () => {
            ant_design_vue_1.message.error('文件读取失败');
            fileContent.value = `文件读取失败: ${file.name}`;
        };
        reader.readAsText(file, 'UTF-8');
    }
    else if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        // PDF文件需要调用后端解析
        fileContent.value = `📄 PDF文件已选择: ${file.name}
文件大小: ${formatFileSize(file.size)}

正在解析PDF内容，请稍候...`;
        // 调用后端PDF解析API
        await parsePDFFile(file);
    }
    else if (file.type.includes('msword') || file.name.endsWith('.doc') || file.name.endsWith('.docx')) {
        fileContent.value = `📝 Word文件已选择: ${file.name}
文件大小: ${formatFileSize(file.size)}

Word文件将在提交后由AI系统自动解析提取文本内容。
预览功能暂不支持Word格式。

💡 提示：系统支持从Word文档中提取病历文本、患者信息、诊断结果等结构化数据。`;
    }
    else {
        fileContent.value = `已选择文件: ${file.name}
文件大小: ${formatFileSize(file.size)}
文件类型: ${file.type}

注意: 文件内容将在提交时处理`;
    }
    fileList.value = [file];
    return false; // 阻止自动上传
};
const handleFileRemove = () => {
    fileList.value = [];
    fileContent.value = '';
};
// PDF解析函数
const parsePDFFile = async (file) => {
    try {
        const formData = new FormData();
        formData.append('file', file);
        // 调用后端PDF解析API
        const response = await fetch('/api/parse-medical-file', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        if (result.success && result.data) {
            // 显示解析结果
            const content = result.data.content || '';
            const medicalInfo = result.data.medical_info || {};
            fileContent.value = `📄 PDF文件解析完成: ${file.name}
文件大小: ${formatFileSize(file.size)}
解析方法: ${result.data.method || '未知'}
页数: ${result.data.pages || 0}

📋 解析内容预览:
${content.substring(0, 2000)}${content.length > 2000 ? '\n\n...(内容已截断，完整内容将在提交时使用)' : ''}

${medicalInfo.patient_name ? `\n🏥 提取的医疗信息:
患者姓名: ${medicalInfo.patient_name}
年龄: ${medicalInfo.age || '未识别'}
性别: ${medicalInfo.gender || '未识别'}
科室: ${medicalInfo.department || '未识别'}
诊断: ${medicalInfo.diagnosis || '未识别'}` : ''}`;
            ant_design_vue_1.message.success('PDF文件解析成功');
        }
        else {
            throw new Error(result.message || 'PDF解析失败');
        }
    }
    catch (error) {
        console.error('PDF解析失败:', error);
        fileContent.value = `📄 PDF文件解析失败: ${file.name}
文件大小: ${formatFileSize(file.size)}

❌ 解析错误: ${error.message}

💡 提示：
1. 请确保PDF文件没有密码保护
2. 请确保PDF文件内容清晰可读
3. 系统支持标准的医疗病历PDF格式

文件仍可提交，系统将在后台重试解析。`;
        ant_design_vue_1.message.error(`PDF解析失败: ${error.message}`);
    }
};
// 表单提交
const handleSubmit = async () => {
    try {
        // 1. Ant Design 表单验证
        await formRef.value?.validate();
        isSubmitting.value = true;
        const submitData = {
            patient_name: formData.patient_name,
            patient_age: formData.patient_age,
            patient_gender: formData.patient_gender,
            department: formData.department,
            admission_date: formData.admission_date.format('YYYY-MM-DD'),
            record_type: formData.record_type,
            content: inputMode.value === 'text' ? formData.content : fileContent.value,
            file: inputMode.value === 'file' ? fileList.value[0] : undefined
        };
        // 2. 业务逻辑验证
        const validation = (0, validation_1.validateMedicalRecord)(submitData);
        if (!validation.isValid) {
            validation.errors.forEach(error => {
                (0, error_handler_1.handleValidationError)(error, { field: 'medical_record' });
            });
            return;
        }
        // 3. 显示警告信息（如果有）
        if (validation.warnings && validation.warnings.length > 0) {
            validation.warnings.forEach(warning => {
                console.warn('表单警告:', warning);
            });
        }
        emit('submit', submitData);
    }
    catch (error) {
        console.error('表单验证失败:', error);
        if (error instanceof Error) {
            (0, error_handler_1.handleValidationError)(error.message, { operation: 'form_submit' });
        }
    }
    finally {
        isSubmitting.value = false;
    }
};
// 重置表单
const resetForm = () => {
    formRef.value?.resetFields();
    Object.assign(formData, {
        patient_name: '',
        patient_age: undefined,
        patient_gender: undefined,
        department: undefined,
        admission_date: undefined,
        record_type: 'inpatient',
        content: ''
    });
    inputMode.value = 'text';
    fileList.value = [];
    fileContent.value = '';
    emit('cancel');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    loading: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-picker']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "record-upload-form" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "病案上传",
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    bordered: (false),
}));
const __VLS_2 = __VLS_1({
    title: "病案上传",
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_3.slots;
    if (__VLS_ctx.hasContent) {
        const __VLS_4 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
            ...{ 'onClick': {} },
            type: "text",
            ...{ class: "text-gray-500" },
        }));
        const __VLS_6 = __VLS_5({
            ...{ 'onClick': {} },
            type: "text",
            ...{ class: "text-gray-500" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_5));
        let __VLS_8;
        let __VLS_9;
        let __VLS_10;
        const __VLS_11 = {
            onClick: (__VLS_ctx.resetForm)
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
    }
}
const __VLS_16 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
    ...{ class: "space-y-6" },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
    ...{ class: "space-y-6" },
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
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-3 gap-4" },
});
const __VLS_26 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
    label: "患者姓名",
    name: "patient_name",
    ...{ class: "mb-4" },
}));
const __VLS_28 = __VLS_27({
    label: "患者姓名",
    name: "patient_name",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_29.slots.default;
const __VLS_30 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
    value: (__VLS_ctx.formData.patient_name),
    placeholder: "请输入患者姓名",
    ...{ class: "h-10" },
}));
const __VLS_32 = __VLS_31({
    value: (__VLS_ctx.formData.patient_name),
    placeholder: "请输入患者姓名",
    ...{ class: "h-10" },
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
var __VLS_29;
const __VLS_34 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
    label: "年龄",
    name: "patient_age",
    ...{ class: "mb-4" },
}));
const __VLS_36 = __VLS_35({
    label: "年龄",
    name: "patient_age",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_35));
__VLS_37.slots.default;
const __VLS_38 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
    value: (__VLS_ctx.formData.patient_age),
    min: (0),
    max: (150),
    placeholder: "年龄",
    ...{ class: "w-full h-10" },
}));
const __VLS_40 = __VLS_39({
    value: (__VLS_ctx.formData.patient_age),
    min: (0),
    max: (150),
    placeholder: "年龄",
    ...{ class: "w-full h-10" },
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
var __VLS_37;
const __VLS_42 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
    label: "性别",
    name: "patient_gender",
    ...{ class: "mb-4" },
}));
const __VLS_44 = __VLS_43({
    label: "性别",
    name: "patient_gender",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_43));
__VLS_45.slots.default;
const __VLS_46 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
    value: (__VLS_ctx.formData.patient_gender),
    placeholder: "请选择性别",
    ...{ class: "h-10" },
}));
const __VLS_48 = __VLS_47({
    value: (__VLS_ctx.formData.patient_gender),
    placeholder: "请选择性别",
    ...{ class: "h-10" },
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
__VLS_49.slots.default;
const __VLS_50 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
    value: "M",
}));
const __VLS_52 = __VLS_51({
    value: "M",
}, ...__VLS_functionalComponentArgsRest(__VLS_51));
__VLS_53.slots.default;
var __VLS_53;
const __VLS_54 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    value: "F",
}));
const __VLS_56 = __VLS_55({
    value: "F",
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_57.slots.default;
var __VLS_57;
const __VLS_58 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
    value: "U",
}));
const __VLS_60 = __VLS_59({
    value: "U",
}, ...__VLS_functionalComponentArgsRest(__VLS_59));
__VLS_61.slots.default;
var __VLS_61;
var __VLS_49;
var __VLS_45;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-3 gap-4" },
});
const __VLS_62 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    label: "科室",
    name: "department",
    ...{ class: "mb-4" },
}));
const __VLS_64 = __VLS_63({
    label: "科室",
    name: "department",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
__VLS_65.slots.default;
const __VLS_66 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
    value: (__VLS_ctx.formData.department),
    placeholder: "请选择科室",
    showSearch: true,
    ...{ class: "h-10" },
}));
const __VLS_68 = __VLS_67({
    value: (__VLS_ctx.formData.department),
    placeholder: "请选择科室",
    showSearch: true,
    ...{ class: "h-10" },
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
__VLS_69.slots.default;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.DEPARTMENTS))) {
    const __VLS_70 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
        key: (dept),
        value: (dept),
    }));
    const __VLS_72 = __VLS_71({
        key: (dept),
        value: (dept),
    }, ...__VLS_functionalComponentArgsRest(__VLS_71));
    __VLS_73.slots.default;
    (dept);
    var __VLS_73;
}
var __VLS_69;
var __VLS_65;
const __VLS_74 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    label: "入院日期",
    name: "admission_date",
    ...{ class: "mb-4" },
}));
const __VLS_76 = __VLS_75({
    label: "入院日期",
    name: "admission_date",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
__VLS_77.slots.default;
const __VLS_78 = {}.ADatePicker;
/** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
// @ts-ignore
const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
    value: (__VLS_ctx.formData.admission_date),
    placeholder: "选择入院日期",
    ...{ class: "w-full h-10" },
    format: "YYYY-MM-DD",
}));
const __VLS_80 = __VLS_79({
    value: (__VLS_ctx.formData.admission_date),
    placeholder: "选择入院日期",
    ...{ class: "w-full h-10" },
    format: "YYYY-MM-DD",
}, ...__VLS_functionalComponentArgsRest(__VLS_79));
var __VLS_77;
const __VLS_82 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    label: "记录类型",
    name: "record_type",
    ...{ class: "mb-4" },
}));
const __VLS_84 = __VLS_83({
    label: "记录类型",
    name: "record_type",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
__VLS_85.slots.default;
const __VLS_86 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
    value: (__VLS_ctx.formData.record_type),
    placeholder: "请选择记录类型",
    ...{ class: "h-10" },
}));
const __VLS_88 = __VLS_87({
    value: (__VLS_ctx.formData.record_type),
    placeholder: "请选择记录类型",
    ...{ class: "h-10" },
}, ...__VLS_functionalComponentArgsRest(__VLS_87));
__VLS_89.slots.default;
for (const [type] of __VLS_getVForSourceType((__VLS_ctx.RECORD_TYPES))) {
    const __VLS_90 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
        key: (type.value),
        value: (type.value),
    }));
    const __VLS_92 = __VLS_91({
        key: (type.value),
        value: (type.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    __VLS_93.slots.default;
    (type.label);
    var __VLS_93;
}
var __VLS_89;
var __VLS_85;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-gray-50 rounded-lg p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold mb-4 text-gray-800" },
});
const __VLS_94 = {}.ARadioGroup;
/** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
    value: (__VLS_ctx.inputMode),
    buttonStyle: "solid",
    ...{ class: "mb-4" },
}));
const __VLS_96 = __VLS_95({
    value: (__VLS_ctx.inputMode),
    buttonStyle: "solid",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_95));
__VLS_97.slots.default;
const __VLS_98 = {}.ARadioButton;
/** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
// @ts-ignore
const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
    value: "text",
}));
const __VLS_100 = __VLS_99({
    value: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_99));
__VLS_101.slots.default;
var __VLS_101;
const __VLS_102 = {}.ARadioButton;
/** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
// @ts-ignore
const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
    value: "file",
}));
const __VLS_104 = __VLS_103({
    value: "file",
}, ...__VLS_functionalComponentArgsRest(__VLS_103));
__VLS_105.slots.default;
var __VLS_105;
var __VLS_97;
if (__VLS_ctx.inputMode === 'text') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_106 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
        name: "content",
        rules: ([{ required: true, message: '请输入病案内容' }]),
    }));
    const __VLS_108 = __VLS_107({
        name: "content",
        rules: ([{ required: true, message: '请输入病案内容' }]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_107));
    __VLS_109.slots.default;
    const __VLS_110 = {}.ATextarea;
    /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
    // @ts-ignore
    const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
        value: (__VLS_ctx.formData.content),
        placeholder: "请输入病案内容...",
        rows: (12),
        showCount: true,
        maxlength: (10000),
        ...{ class: "font-mono text-sm" },
    }));
    const __VLS_112 = __VLS_111({
        value: (__VLS_ctx.formData.content),
        placeholder: "请输入病案内容...",
        rows: (12),
        showCount: true,
        maxlength: (10000),
        ...{ class: "font-mono text-sm" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_111));
    var __VLS_109;
}
else if (__VLS_ctx.inputMode === 'file') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_114 = {}.AUploadDragger;
    /** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
    // @ts-ignore
    const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
        ...{ 'onRemove': {} },
        fileList: (__VLS_ctx.fileList),
        beforeUpload: (__VLS_ctx.handleBeforeUpload),
        multiple: (false),
        ...{ class: "!bg-white border-2 border-dashed border-blue-300 hover:border-blue-500 transition-colors" },
    }));
    const __VLS_116 = __VLS_115({
        ...{ 'onRemove': {} },
        fileList: (__VLS_ctx.fileList),
        beforeUpload: (__VLS_ctx.handleBeforeUpload),
        multiple: (false),
        ...{ class: "!bg-white border-2 border-dashed border-blue-300 hover:border-blue-500 transition-colors" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_115));
    let __VLS_118;
    let __VLS_119;
    let __VLS_120;
    const __VLS_121 = {
        onRemove: (__VLS_ctx.handleFileRemove)
    };
    __VLS_117.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "p-8" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-drag-icon" },
    });
    const __VLS_122 = {}.InboxOutlined;
    /** @type {[typeof __VLS_components.InboxOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
        ...{ class: "text-4xl text-blue-500" },
    }));
    const __VLS_124 = __VLS_123({
        ...{ class: "text-4xl text-blue-500" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_123));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-text text-gray-700" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-hint text-gray-500" },
    });
    var __VLS_117;
    if (__VLS_ctx.fileContent) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-4" },
        });
        const __VLS_126 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
            orientation: "left",
        }));
        const __VLS_128 = __VLS_127({
            orientation: "left",
        }, ...__VLS_functionalComponentArgsRest(__VLS_127));
        __VLS_129.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-600" },
        });
        var __VLS_129;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "bg-white p-4 rounded border min-h-[400px] max-h-[600px] overflow-y-auto" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "whitespace-pre-wrap text-sm text-gray-800" },
        });
        (__VLS_ctx.fileContent.substring(0, 2000));
        (__VLS_ctx.fileContent.length > 2000 ? '...' : '');
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-end space-x-4 pt-6 border-t" },
});
const __VLS_130 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
    ...{ 'onClick': {} },
    size: "large",
}));
const __VLS_132 = __VLS_131({
    ...{ 'onClick': {} },
    size: "large",
}, ...__VLS_functionalComponentArgsRest(__VLS_131));
let __VLS_134;
let __VLS_135;
let __VLS_136;
const __VLS_137 = {
    onClick: (__VLS_ctx.resetForm)
};
__VLS_133.slots.default;
var __VLS_133;
const __VLS_138 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({
    type: "primary",
    htmlType: "submit",
    size: "large",
    loading: (__VLS_ctx.isSubmitting),
    disabled: (!__VLS_ctx.hasValidContent),
    ...{ class: "min-w-32" },
}));
const __VLS_140 = __VLS_139({
    type: "primary",
    htmlType: "submit",
    size: "large",
    loading: (__VLS_ctx.isSubmitting),
    disabled: (!__VLS_ctx.hasValidContent),
    ...{ class: "min-w-32" },
}, ...__VLS_functionalComponentArgsRest(__VLS_139));
__VLS_141.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_141.slots;
    const __VLS_142 = {}.CloudUploadOutlined;
    /** @type {[typeof __VLS_components.CloudUploadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({}));
    const __VLS_144 = __VLS_143({}, ...__VLS_functionalComponentArgsRest(__VLS_143));
}
(__VLS_ctx.isSubmitting ? '上传中...' : '开始分析');
var __VLS_141;
var __VLS_19;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['record-upload-form']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['!bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-[400px]']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-[600px]']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-32']} */ ;
// @ts-ignore
var __VLS_25 = __VLS_24;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            InboxOutlined: icons_vue_1.InboxOutlined,
            CloudUploadOutlined: icons_vue_1.CloudUploadOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            DEPARTMENTS: medical_records_1.DEPARTMENTS,
            RECORD_TYPES: medical_records_1.RECORD_TYPES,
            formRef: formRef,
            inputMode: inputMode,
            isSubmitting: isSubmitting,
            fileContent: fileContent,
            fileList: fileList,
            formData: formData,
            formRules: formRules,
            hasContent: hasContent,
            hasValidContent: hasValidContent,
            handleBeforeUpload: handleBeforeUpload,
            handleFileRemove: handleFileRemove,
            handleSubmit: handleSubmit,
            resetForm: resetForm,
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
