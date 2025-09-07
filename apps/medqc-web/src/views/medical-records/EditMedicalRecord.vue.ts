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
import vue_router_1 from 'vue-router';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const dayjs_1 = __importDefault(require("dayjs"));
import supabaseMedicalRecordService_1 from '@/services/supabaseMedicalRecordService';
const router = (0, vue_router_1.useRouter)();
const route = (0, vue_router_1.useRoute)();
const formRef = (0, vue_1.ref)();
const loading = (0, vue_1.ref)(true);
const submitting = (0, vue_1.ref)(false);
const originalData = (0, vue_1.ref)(null); // 用于并发编辑检测
// 表单数据
const formData = (0, vue_1.reactive)({ recordNumber: '',
    recordName: '',
    patientName: '',
    patientAge: null,
    patientGender: '',
    department: '',
    primaryDiagnosis: '',
    secondaryDiagnosis:  [],
    majorSurgery: '',
    status: 'active',
    documents: []
});
// 修改历史
const modificationHistory = (0, vue_1.ref)([
    {
        timestamp: '2024-08-27T10:30:00Z',
        user: '张医生',
        action: '创建病历'
    },
    {
        timestamp: '2024-08-27T14:20:00Z',
        user: '李医生',
        action: '修改主诊断信息'
    },
    {
        timestamp: '2024-08-27T16:45:00Z',
        user: '王医生',
        action: '添加出院记录'
    }
]);
// 表单验证规则
const formRules = {
    recordName: [
        { required: true, message: '请输入病历名称', trigger: 'blur' }
    ],
    patientName: [
        { required: true, message: '请输入患者姓名', trigger: 'blur' }
    ],
    patientAge: [
        { required: true, message: '请输入患者年龄', trigger: 'blur' },
        { type: 'number', min: 0, max: 150, message: '年龄必须在0-150之间', trigger: 'blur' }
    ],
    patientGender: [
        { required: true, message: '请选择患者性别', trigger: 'change' }
    ],
    department: [
        { required: true, message: '请选择出院科室', trigger: 'change' }
    ],
    primaryDiagnosis: [
        { required: true, message: '请输入主诊断', trigger: 'blur' }
    ],
    status: [
        { required: true, message: '请选择状态', trigger: 'change' }
    ]
};
// 生命周期
(0, vue_1.onMounted)(async () => {
    await loadRecordData();
});
// 加载病历数据
const loadRecordData = async () => { try {
        loading.value = true;
        const recordId = route.params.id;
        console.log('正在加载病历数据，ID:', recordId);
        // 从数据库加载真实数据
        const record = await supabaseMedicalRecordService_1.supabaseMedicalRecordService.getMedicalRecordById(recordId);
        console.log('加载的病历数据:', record);
        // 转换数据格式以适配表单
        const formattedData = {
            recordNumber: record.record_number,
            recordName: record.record_name,
            patientName: record.patient_info?.name || '',
            patientAge: record.patient_info?.age || null,
            patientGender: record.patient_info?.gender || '',
            department: record.department,
            primaryDiagnosis: record.primary_diagnosis,
            secondaryDiagnosis: record.secondary_diagnosis || [],
            majorSurgery: record.major_surgery || '',
            status: record.status || 'active',
            documents: record.documents?.map(doc => ({
                id: doc.id,
                type: doc.type,
                title: doc.title,
                content: doc.content
            })) || []
        };
        console.log('转换后的表单数据:', formattedData);
        console.log('文书数量:', formattedData.documents.length);
        Object.assign(formData, formattedData);
        // 保存原始数据用于并发编辑检测
        originalData.value = JSON.parse(JSON.stringify(record));
        ant_design_vue_1.message.success(`成功加载病历数据，包含 ${formattedData.documents.length} 个文书`);
    }
    catch (error) {
        console.error('加载病历数据失败:', error);
        ant_design_vue_1.message.error('加载病历数据失败，请检查病历ID是否正确');
        // 如果加载失败，返回列表页面
        setTimeout(() => {
            router.push('/dashboard/medical-records');
        }, 2000);
    }
    finally {
        loading.value = false;
    }
};
// 格式化时间
const formatDateTime = (dateString) => {
    return (0, dayjs_1.default)(dateString).format('YYYY-MM-DD HH:mm:ss');
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
        // 表单验证
        await formRef.value?.validate();
        submitting.value = true;
        const recordId = route.params.id;
        console.log('正在保存病历数据:', formData);
        // 并发编辑检测
        if (originalData.value) {
            try {
                const currentRecord = await supabaseMedicalRecordService_1.supabaseMedicalRecordService.getMedicalRecordById(recordId);
                if (currentRecord.updated_at !== originalData.value.updated_at) {
                    const confirmed = window.confirm('检测到此病历已被其他用户修改。\n\n' +
                        '继续保存将覆盖其他用户的修改。\n\n' +
                        '是否继续保存？');
                    if (!confirmed) {
                        submitting.value = false;
                        return;
                    }
                }
            }
            catch (error) {
                console.warn('并发编辑检测失败:', error);
            }
        }
        // 准备文书数据
        const documents = formData.documents.map((doc, index) => ({
            id: doc.id,
            type: doc.type,
            title: doc.title,
            content: doc.content,
            ai_classified: false, // 手动编辑的文书
            ai_confidence: 0,
            sort_order: index
        }));
        // 准备更新数据
        const updateData = {
            record_name: formData.recordName,
            patient_info: {
                name: formData.patientName,
                age: formData.patientAge,
                gender: formData.patientGender
            },
            department: formData.department,
            primary_diagnosis: formData.primaryDiagnosis,
            secondary_diagnosis: formData.secondaryDiagnosis,
            major_surgery: formData.majorSurgery,
            status: formData.status,
            documents: documents // 包含文书数据
        };
        // 更新病历基本信息和文书
        await supabaseMedicalRecordService_1.supabaseMedicalRecordService.updateMedicalRecord(recordId, updateData);
        console.log('病历保存成功，包含', documents.length, '个文书');
        ant_design_vue_1.message.success(`病历保存成功，包含 ${documents.length} 个文书`);
        // 延迟跳转，让用户看到成功消息
        setTimeout(() => {
            router.push('/dashboard/medical-records');
        }, 1500);
    }
    catch (error) {
        console.error('保存失败:', error);
        // 根据错误类型显示不同的错误消息
        if (error.message?.includes('validation')) {
            ant_design_vue_1.message.error('数据验证失败，请检查输入内容');
        }
        else if (error.message?.includes('network')) {
            ant_design_vue_1.message.error('网络连接失败，请检查网络后重试');
        }
        else if (error.message?.includes('permission')) {
            ant_design_vue_1.message.error('权限不足，无法保存病历');
        }
        else {
            ant_design_vue_1.message.error(error.message || '保存失败，请重试');
        }
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
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "record-info" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "record-number" },
});
(__VLS_ctx.formData.recordNumber);
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    const __VLS_16 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        size: "large",
        tip: "加载病历数据中...",
    }));
    const __VLS_18 = __VLS_17({
        size: "large",
        tip: "加载病历数据中...",
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
}
else {
    const __VLS_20 = {}.AForm;
    /** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        ...{ 'onFinish': {} },
        ref: "formRef",
        model: (__VLS_ctx.formData),
        rules: (__VLS_ctx.formRules),
        layout: "vertical",
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onFinish': {} },
        ref: "formRef",
        model: (__VLS_ctx.formData),
        rules: (__VLS_ctx.formRules),
        layout: "vertical",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_24;
    let __VLS_25;
    let __VLS_26;
    const __VLS_27 = {
        onFinish: (__VLS_ctx.handleSubmit)
    };
    /** @type {typeof __VLS_ctx.formRef} */ ;
    var __VLS_28 = {};
    __VLS_23.slots.default;
    const __VLS_30 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
        title: "病历基本信息",
        ...{ class: "form-card" },
    }));
    const __VLS_32 = __VLS_31({
        title: "病历基本信息",
        ...{ class: "form-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    __VLS_33.slots.default;
    const __VLS_34 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
        gutter: (16),
    }));
    const __VLS_36 = __VLS_35({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_35));
    __VLS_37.slots.default;
    const __VLS_38 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
        span: (12),
    }));
    const __VLS_40 = __VLS_39({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_39));
    __VLS_41.slots.default;
    const __VLS_42 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
        label: "病历编号",
        name: "recordNumber",
    }));
    const __VLS_44 = __VLS_43({
        label: "病历编号",
        name: "recordNumber",
    }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    __VLS_45.slots.default;
    const __VLS_46 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
        value: (__VLS_ctx.formData.recordNumber),
        disabled: true,
    }));
    const __VLS_48 = __VLS_47({
        value: (__VLS_ctx.formData.recordNumber),
        disabled: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_47));
    var __VLS_45;
    var __VLS_41;
    const __VLS_50 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
        span: (12),
    }));
    const __VLS_52 = __VLS_51({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_51));
    __VLS_53.slots.default;
    const __VLS_54 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
        label: "病历名称",
        name: "recordName",
    }));
    const __VLS_56 = __VLS_55({
        label: "病历名称",
        name: "recordName",
    }, ...__VLS_functionalComponentArgsRest(__VLS_55));
    __VLS_57.slots.default;
    const __VLS_58 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
        value: (__VLS_ctx.formData.recordName),
        placeholder: "请输入病历名称",
    }));
    const __VLS_60 = __VLS_59({
        value: (__VLS_ctx.formData.recordName),
        placeholder: "请输入病历名称",
    }, ...__VLS_functionalComponentArgsRest(__VLS_59));
    var __VLS_57;
    var __VLS_53;
    var __VLS_37;
    var __VLS_33;
    const __VLS_62 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
        title: "患者信息",
        ...{ class: "form-card" },
    }));
    const __VLS_64 = __VLS_63({
        title: "患者信息",
        ...{ class: "form-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_63));
    __VLS_65.slots.default;
    const __VLS_66 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
        gutter: (16),
    }));
    const __VLS_68 = __VLS_67({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_67));
    __VLS_69.slots.default;
    const __VLS_70 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
        span: (8),
    }));
    const __VLS_72 = __VLS_71({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_71));
    __VLS_73.slots.default;
    const __VLS_74 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
        label: "患者姓名",
        name: "patientName",
    }));
    const __VLS_76 = __VLS_75({
        label: "患者姓名",
        name: "patientName",
    }, ...__VLS_functionalComponentArgsRest(__VLS_75));
    __VLS_77.slots.default;
    const __VLS_78 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
        value: (__VLS_ctx.formData.patientName),
        placeholder: "请输入患者姓名",
    }));
    const __VLS_80 = __VLS_79({
        value: (__VLS_ctx.formData.patientName),
        placeholder: "请输入患者姓名",
    }, ...__VLS_functionalComponentArgsRest(__VLS_79));
    var __VLS_77;
    var __VLS_73;
    const __VLS_82 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
        span: (8),
    }));
    const __VLS_84 = __VLS_83({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_83));
    __VLS_85.slots.default;
    const __VLS_86 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
        label: "年龄",
        name: "patientAge",
    }));
    const __VLS_88 = __VLS_87({
        label: "年龄",
        name: "patientAge",
    }, ...__VLS_functionalComponentArgsRest(__VLS_87));
    __VLS_89.slots.default;
    const __VLS_90 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
        value: (__VLS_ctx.formData.patientAge),
        placeholder: "请输入年龄",
        min: (0),
        max: (150),
        ...{ style: {} },
    }));
    const __VLS_92 = __VLS_91({
        value: (__VLS_ctx.formData.patientAge),
        placeholder: "请输入年龄",
        min: (0),
        max: (150),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    var __VLS_89;
    var __VLS_85;
    const __VLS_94 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
        span: (8),
    }));
    const __VLS_96 = __VLS_95({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_95));
    __VLS_97.slots.default;
    const __VLS_98 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
        label: "性别",
        name: "patientGender",
    }));
    const __VLS_100 = __VLS_99({
        label: "性别",
        name: "patientGender",
    }, ...__VLS_functionalComponentArgsRest(__VLS_99));
    __VLS_101.slots.default;
    const __VLS_102 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
        value: (__VLS_ctx.formData.patientGender),
        placeholder: "请选择性别",
    }));
    const __VLS_104 = __VLS_103({
        value: (__VLS_ctx.formData.patientGender),
        placeholder: "请选择性别",
    }, ...__VLS_functionalComponentArgsRest(__VLS_103));
    __VLS_105.slots.default;
    const __VLS_106 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
        value: "男",
    }));
    const __VLS_108 = __VLS_107({
        value: "男",
    }, ...__VLS_functionalComponentArgsRest(__VLS_107));
    __VLS_109.slots.default;
    var __VLS_109;
    const __VLS_110 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
        value: "女",
    }));
    const __VLS_112 = __VLS_111({
        value: "女",
    }, ...__VLS_functionalComponentArgsRest(__VLS_111));
    __VLS_113.slots.default;
    var __VLS_113;
    const __VLS_114 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
        value: "未知",
    }));
    const __VLS_116 = __VLS_115({
        value: "未知",
    }, ...__VLS_functionalComponentArgsRest(__VLS_115));
    __VLS_117.slots.default;
    var __VLS_117;
    var __VLS_105;
    var __VLS_101;
    var __VLS_97;
    var __VLS_69;
    var __VLS_65;
    const __VLS_118 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
        title: "诊断信息",
        ...{ class: "form-card" },
    }));
    const __VLS_120 = __VLS_119({
        title: "诊断信息",
        ...{ class: "form-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_119));
    __VLS_121.slots.default;
    const __VLS_122 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
        gutter: (16),
    }));
    const __VLS_124 = __VLS_123({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_123));
    __VLS_125.slots.default;
    const __VLS_126 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
        span: (12),
    }));
    const __VLS_128 = __VLS_127({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    __VLS_129.slots.default;
    const __VLS_130 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
        label: "出院科室",
        name: "department",
    }));
    const __VLS_132 = __VLS_131({
        label: "出院科室",
        name: "department",
    }, ...__VLS_functionalComponentArgsRest(__VLS_131));
    __VLS_133.slots.default;
    const __VLS_134 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
        value: (__VLS_ctx.formData.department),
        placeholder: "请选择出院科室",
    }));
    const __VLS_136 = __VLS_135({
        value: (__VLS_ctx.formData.department),
        placeholder: "请选择出院科室",
    }, ...__VLS_functionalComponentArgsRest(__VLS_135));
    __VLS_137.slots.default;
    const __VLS_138 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({
        value: "内科",
    }));
    const __VLS_140 = __VLS_139({
        value: "内科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_139));
    __VLS_141.slots.default;
    var __VLS_141;
    const __VLS_142 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({
        value: "外科",
    }));
    const __VLS_144 = __VLS_143({
        value: "外科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_143));
    __VLS_145.slots.default;
    var __VLS_145;
    const __VLS_146 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_147 = __VLS_asFunctionalComponent(__VLS_146, new __VLS_146({
        value: "外一科",
    }));
    const __VLS_148 = __VLS_147({
        value: "外一科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_147));
    __VLS_149.slots.default;
    var __VLS_149;
    const __VLS_150 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_151 = __VLS_asFunctionalComponent(__VLS_150, new __VLS_150({
        value: "外二科",
    }));
    const __VLS_152 = __VLS_151({
        value: "外二科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_151));
    __VLS_153.slots.default;
    var __VLS_153;
    const __VLS_154 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({
        value: "妇产科",
    }));
    const __VLS_156 = __VLS_155({
        value: "妇产科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_155));
    __VLS_157.slots.default;
    var __VLS_157;
    const __VLS_158 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_159 = __VLS_asFunctionalComponent(__VLS_158, new __VLS_158({
        value: "儿科",
    }));
    const __VLS_160 = __VLS_159({
        value: "儿科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_159));
    __VLS_161.slots.default;
    var __VLS_161;
    const __VLS_162 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_163 = __VLS_asFunctionalComponent(__VLS_162, new __VLS_162({
        value: "急诊科",
    }));
    const __VLS_164 = __VLS_163({
        value: "急诊科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_163));
    __VLS_165.slots.default;
    var __VLS_165;
    const __VLS_166 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_167 = __VLS_asFunctionalComponent(__VLS_166, new __VLS_166({
        value: "骨科",
    }));
    const __VLS_168 = __VLS_167({
        value: "骨科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_167));
    __VLS_169.slots.default;
    var __VLS_169;
    const __VLS_170 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_171 = __VLS_asFunctionalComponent(__VLS_170, new __VLS_170({
        value: "神经科",
    }));
    const __VLS_172 = __VLS_171({
        value: "神经科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_171));
    __VLS_173.slots.default;
    var __VLS_173;
    const __VLS_174 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_175 = __VLS_asFunctionalComponent(__VLS_174, new __VLS_174({
        value: "心内科",
    }));
    const __VLS_176 = __VLS_175({
        value: "心内科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_175));
    __VLS_177.slots.default;
    var __VLS_177;
    const __VLS_178 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_179 = __VLS_asFunctionalComponent(__VLS_178, new __VLS_178({
        value: "内科",
    }));
    const __VLS_180 = __VLS_179({
        value: "内科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_179));
    __VLS_181.slots.default;
    var __VLS_181;
    var __VLS_137;
    var __VLS_133;
    var __VLS_129;
    const __VLS_182 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_183 = __VLS_asFunctionalComponent(__VLS_182, new __VLS_182({
        span: (12),
    }));
    const __VLS_184 = __VLS_183({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_183));
    __VLS_185.slots.default;
    const __VLS_186 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_187 = __VLS_asFunctionalComponent(__VLS_186, new __VLS_186({
        label: "状态",
        name: "status",
    }));
    const __VLS_188 = __VLS_187({
        label: "状态",
        name: "status",
    }, ...__VLS_functionalComponentArgsRest(__VLS_187));
    __VLS_189.slots.default;
    const __VLS_190 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_191 = __VLS_asFunctionalComponent(__VLS_190, new __VLS_190({
        value: (__VLS_ctx.formData.status),
        placeholder: "请选择状态",
    }));
    const __VLS_192 = __VLS_191({
        value: (__VLS_ctx.formData.status),
        placeholder: "请选择状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_191));
    __VLS_193.slots.default;
    const __VLS_194 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_195 = __VLS_asFunctionalComponent(__VLS_194, new __VLS_194({
        value: "draft",
    }));
    const __VLS_196 = __VLS_195({
        value: "draft",
    }, ...__VLS_functionalComponentArgsRest(__VLS_195));
    __VLS_197.slots.default;
    var __VLS_197;
    const __VLS_198 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_199 = __VLS_asFunctionalComponent(__VLS_198, new __VLS_198({
        value: "active",
    }));
    const __VLS_200 = __VLS_199({
        value: "active",
    }, ...__VLS_functionalComponentArgsRest(__VLS_199));
    __VLS_201.slots.default;
    var __VLS_201;
    const __VLS_202 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_203 = __VLS_asFunctionalComponent(__VLS_202, new __VLS_202({
        value: "archived",
    }));
    const __VLS_204 = __VLS_203({
        value: "archived",
    }, ...__VLS_functionalComponentArgsRest(__VLS_203));
    __VLS_205.slots.default;
    var __VLS_205;
    var __VLS_193;
    var __VLS_189;
    var __VLS_185;
    var __VLS_125;
    const __VLS_206 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_207 = __VLS_asFunctionalComponent(__VLS_206, new __VLS_206({
        gutter: (16),
    }));
    const __VLS_208 = __VLS_207({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_207));
    __VLS_209.slots.default;
    const __VLS_210 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_211 = __VLS_asFunctionalComponent(__VLS_210, new __VLS_210({
        span: (24),
    }));
    const __VLS_212 = __VLS_211({
        span: (24),
    }, ...__VLS_functionalComponentArgsRest(__VLS_211));
    __VLS_213.slots.default;
    const __VLS_214 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_215 = __VLS_asFunctionalComponent(__VLS_214, new __VLS_214({
        label: "主诊断",
        name: "primaryDiagnosis",
    }));
    const __VLS_216 = __VLS_215({
        label: "主诊断",
        name: "primaryDiagnosis",
    }, ...__VLS_functionalComponentArgsRest(__VLS_215));
    __VLS_217.slots.default;
    const __VLS_218 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_219 = __VLS_asFunctionalComponent(__VLS_218, new __VLS_218({
        value: (__VLS_ctx.formData.primaryDiagnosis),
        placeholder: "请输入主诊断",
    }));
    const __VLS_220 = __VLS_219({
        value: (__VLS_ctx.formData.primaryDiagnosis),
        placeholder: "请输入主诊断",
    }, ...__VLS_functionalComponentArgsRest(__VLS_219));
    var __VLS_217;
    var __VLS_213;
    var __VLS_209;
    const __VLS_222 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_223 = __VLS_asFunctionalComponent(__VLS_222, new __VLS_222({
        gutter: (16),
    }));
    const __VLS_224 = __VLS_223({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_223));
    __VLS_225.slots.default;
    const __VLS_226 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_227 = __VLS_asFunctionalComponent(__VLS_226, new __VLS_226({
        span: (24),
    }));
    const __VLS_228 = __VLS_227({
        span: (24),
    }, ...__VLS_functionalComponentArgsRest(__VLS_227));
    __VLS_229.slots.default;
    const __VLS_230 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_231 = __VLS_asFunctionalComponent(__VLS_230, new __VLS_230({
        label: "次要诊断",
        name: "secondaryDiagnosis",
    }));
    const __VLS_232 = __VLS_231({
        label: "次要诊断",
        name: "secondaryDiagnosis",
    }, ...__VLS_functionalComponentArgsRest(__VLS_231));
    __VLS_233.slots.default;
    const __VLS_234 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_235 = __VLS_asFunctionalComponent(__VLS_234, new __VLS_234({
        value: (__VLS_ctx.formData.secondaryDiagnosis),
        mode: "tags",
        placeholder: "请输入次要诊断（可多个）",
        ...{ style: {} },
    }));
    const __VLS_236 = __VLS_235({
        value: (__VLS_ctx.formData.secondaryDiagnosis),
        mode: "tags",
        placeholder: "请输入次要诊断（可多个）",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_235));
    var __VLS_233;
    var __VLS_229;
    var __VLS_225;
    const __VLS_238 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_239 = __VLS_asFunctionalComponent(__VLS_238, new __VLS_238({
        gutter: (16),
    }));
    const __VLS_240 = __VLS_239({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_239));
    __VLS_241.slots.default;
    const __VLS_242 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_243 = __VLS_asFunctionalComponent(__VLS_242, new __VLS_242({
        span: (24),
    }));
    const __VLS_244 = __VLS_243({
        span: (24),
    }, ...__VLS_functionalComponentArgsRest(__VLS_243));
    __VLS_245.slots.default;
    const __VLS_246 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_247 = __VLS_asFunctionalComponent(__VLS_246, new __VLS_246({
        label: "主要手术及操作",
        name: "majorSurgery",
    }));
    const __VLS_248 = __VLS_247({
        label: "主要手术及操作",
        name: "majorSurgery",
    }, ...__VLS_functionalComponentArgsRest(__VLS_247));
    __VLS_249.slots.default;
    const __VLS_250 = {}.ATextarea;
    /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
    // @ts-ignore
    const __VLS_251 = __VLS_asFunctionalComponent(__VLS_250, new __VLS_250({
        value: (__VLS_ctx.formData.majorSurgery),
        placeholder: "请输入主要手术及操作（可选）",
        rows: (3),
    }));
    const __VLS_252 = __VLS_251({
        value: (__VLS_ctx.formData.majorSurgery),
        placeholder: "请输入主要手术及操作（可选）",
        rows: (3),
    }, ...__VLS_functionalComponentArgsRest(__VLS_251));
    var __VLS_249;
    var __VLS_245;
    var __VLS_241;
    var __VLS_121;
    const __VLS_254 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_255 = __VLS_asFunctionalComponent(__VLS_254, new __VLS_254({
        title: "文书信息",
        ...{ class: "form-card" },
    }));
    const __VLS_256 = __VLS_255({
        title: "文书信息",
        ...{ class: "form-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_255));
    __VLS_257.slots.default;
    if (__VLS_ctx.formData.documents.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-documents" },
        });
        const __VLS_258 = {}.AEmpty;
        /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
        // @ts-ignore
        const __VLS_259 = __VLS_asFunctionalComponent(__VLS_258, new __VLS_258({
            description: "暂无文书，请添加文书信息",
        }));
        const __VLS_260 = __VLS_259({
            description: "暂无文书，请添加文书信息",
        }, ...__VLS_functionalComponentArgsRest(__VLS_259));
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
            const __VLS_262 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_263 = __VLS_asFunctionalComponent(__VLS_262, new __VLS_262({
                ...{ 'onClick': {} },
                type: "text",
                danger: true,
                size: "small",
            }));
            const __VLS_264 = __VLS_263({
                ...{ 'onClick': {} },
                type: "text",
                danger: true,
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_263));
            let __VLS_266;
            let __VLS_267;
            let __VLS_268;
            const __VLS_269 = {
                onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.loading))
                        return;
                    if (!!(__VLS_ctx.formData.documents.length === 0))
                        return;
                    __VLS_ctx.removeDocument(index);
                }
            };
            __VLS_265.slots.default;
            var __VLS_265;
            const __VLS_270 = {}.ARow;
            /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
            // @ts-ignore
            const __VLS_271 = __VLS_asFunctionalComponent(__VLS_270, new __VLS_270({
                gutter: (16),
            }));
            const __VLS_272 = __VLS_271({
                gutter: (16),
            }, ...__VLS_functionalComponentArgsRest(__VLS_271));
            __VLS_273.slots.default;
            const __VLS_274 = {}.ACol;
            /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
            // @ts-ignore
            const __VLS_275 = __VLS_asFunctionalComponent(__VLS_274, new __VLS_274({
                span: (8),
            }));
            const __VLS_276 = __VLS_275({
                span: (8),
            }, ...__VLS_functionalComponentArgsRest(__VLS_275));
            __VLS_277.slots.default;
            const __VLS_278 = {}.AFormItem;
            /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
            // @ts-ignore
            const __VLS_279 = __VLS_asFunctionalComponent(__VLS_278, new __VLS_278({
                name: (['documents', index, 'type']),
                label: "文书类型",
            }));
            const __VLS_280 = __VLS_279({
                name: (['documents', index, 'type']),
                label: "文书类型",
            }, ...__VLS_functionalComponentArgsRest(__VLS_279));
            __VLS_281.slots.default;
            const __VLS_282 = {}.ASelect;
            /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
            // @ts-ignore
            const __VLS_283 = __VLS_asFunctionalComponent(__VLS_282, new __VLS_282({
                value: (document.type),
                placeholder: "请选择文书类型",
            }));
            const __VLS_284 = __VLS_283({
                value: (document.type),
                placeholder: "请选择文书类型",
            }, ...__VLS_functionalComponentArgsRest(__VLS_283));
            __VLS_285.slots.default;
            const __VLS_286 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_287 = __VLS_asFunctionalComponent(__VLS_286, new __VLS_286({
                value: "入院记录",
            }));
            const __VLS_288 = __VLS_287({
                value: "入院记录",
            }, ...__VLS_functionalComponentArgsRest(__VLS_287));
            __VLS_289.slots.default;
            var __VLS_289;
            const __VLS_290 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_291 = __VLS_asFunctionalComponent(__VLS_290, new __VLS_290({
                value: "病程记录",
            }));
            const __VLS_292 = __VLS_291({
                value: "病程记录",
            }, ...__VLS_functionalComponentArgsRest(__VLS_291));
            __VLS_293.slots.default;
            var __VLS_293;
            const __VLS_294 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_295 = __VLS_asFunctionalComponent(__VLS_294, new __VLS_294({
                value: "出院记录",
            }));
            const __VLS_296 = __VLS_295({
                value: "出院记录",
            }, ...__VLS_functionalComponentArgsRest(__VLS_295));
            __VLS_297.slots.default;
            var __VLS_297;
            const __VLS_298 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_299 = __VLS_asFunctionalComponent(__VLS_298, new __VLS_298({
                value: "手术记录",
            }));
            const __VLS_300 = __VLS_299({
                value: "手术记录",
            }, ...__VLS_functionalComponentArgsRest(__VLS_299));
            __VLS_301.slots.default;
            var __VLS_301;
            const __VLS_302 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_303 = __VLS_asFunctionalComponent(__VLS_302, new __VLS_302({
                value: "会诊记录",
            }));
            const __VLS_304 = __VLS_303({
                value: "会诊记录",
            }, ...__VLS_functionalComponentArgsRest(__VLS_303));
            __VLS_305.slots.default;
            var __VLS_305;
            const __VLS_306 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_307 = __VLS_asFunctionalComponent(__VLS_306, new __VLS_306({
                value: "检查报告",
            }));
            const __VLS_308 = __VLS_307({
                value: "检查报告",
            }, ...__VLS_functionalComponentArgsRest(__VLS_307));
            __VLS_309.slots.default;
            var __VLS_309;
            const __VLS_310 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_311 = __VLS_asFunctionalComponent(__VLS_310, new __VLS_310({
                value: "化验报告",
            }));
            const __VLS_312 = __VLS_311({
                value: "化验报告",
            }, ...__VLS_functionalComponentArgsRest(__VLS_311));
            __VLS_313.slots.default;
            var __VLS_313;
            var __VLS_285;
            var __VLS_281;
            var __VLS_277;
            const __VLS_314 = {}.ACol;
            /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
            // @ts-ignore
            const __VLS_315 = __VLS_asFunctionalComponent(__VLS_314, new __VLS_314({
                span: (16),
            }));
            const __VLS_316 = __VLS_315({
                span: (16),
            }, ...__VLS_functionalComponentArgsRest(__VLS_315));
            __VLS_317.slots.default;
            const __VLS_318 = {}.AFormItem;
            /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
            // @ts-ignore
            const __VLS_319 = __VLS_asFunctionalComponent(__VLS_318, new __VLS_318({
                name: (['documents', index, 'title']),
                label: "文书标题",
            }));
            const __VLS_320 = __VLS_319({
                name: (['documents', index, 'title']),
                label: "文书标题",
            }, ...__VLS_functionalComponentArgsRest(__VLS_319));
            __VLS_321.slots.default;
            const __VLS_322 = {}.AInput;
            /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
            // @ts-ignore
            const __VLS_323 = __VLS_asFunctionalComponent(__VLS_322, new __VLS_322({
                value: (document.title),
                placeholder: "请输入文书标题",
            }));
            const __VLS_324 = __VLS_323({
                value: (document.title),
                placeholder: "请输入文书标题",
            }, ...__VLS_functionalComponentArgsRest(__VLS_323));
            var __VLS_321;
            var __VLS_317;
            var __VLS_273;
            const __VLS_326 = {}.AFormItem;
            /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
            // @ts-ignore
            const __VLS_327 = __VLS_asFunctionalComponent(__VLS_326, new __VLS_326({
                name: (['documents', index, 'content']),
                label: "文书内容",
            }));
            const __VLS_328 = __VLS_327({
                name: (['documents', index, 'content']),
                label: "文书内容",
            }, ...__VLS_functionalComponentArgsRest(__VLS_327));
            __VLS_329.slots.default;
            const __VLS_330 = {}.ATextarea;
            /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
            // @ts-ignore
            const __VLS_331 = __VLS_asFunctionalComponent(__VLS_330, new __VLS_330({
                value: (document.content),
                placeholder: "请输入文书内容",
                rows: (6),
            }));
            const __VLS_332 = __VLS_331({
                value: (document.content),
                placeholder: "请输入文书内容",
                rows: (6),
            }, ...__VLS_functionalComponentArgsRest(__VLS_331));
            var __VLS_329;
        }
    }
    var __VLS_257;
    const __VLS_334 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_335 = __VLS_asFunctionalComponent(__VLS_334, new __VLS_334({
        title: "修改历史",
        ...{ class: "form-card" },
    }));
    const __VLS_336 = __VLS_335({
        title: "修改历史",
        ...{ class: "form-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_335));
    __VLS_337.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history-list" },
    });
    for (const [history, index] of __VLS_getVForSourceType((__VLS_ctx.modificationHistory))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (index),
            ...{ class: "history-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "history-time" },
        });
        (__VLS_ctx.formatDateTime(history.timestamp));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "history-user" },
        });
        (history.user);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "history-action" },
        });
        (history.action);
    }
    var __VLS_337;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "left-actions" },
    });
    const __VLS_338 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_339 = __VLS_asFunctionalComponent(__VLS_338, new __VLS_338({
        ...{ 'onClick': {} },
        type: "dashed",
    }));
    const __VLS_340 = __VLS_339({
        ...{ 'onClick': {} },
        type: "dashed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_339));
    let __VLS_342;
    let __VLS_343;
    let __VLS_344;
    const __VLS_345 = {
        onClick: (__VLS_ctx.addDocument)
    };
    __VLS_341.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_341.slots;
        const __VLS_346 = {}.PlusOutlined;
        /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_347 = __VLS_asFunctionalComponent(__VLS_346, new __VLS_346({}));
        const __VLS_348 = __VLS_347({}, ...__VLS_functionalComponentArgsRest(__VLS_347));
    }
    var __VLS_341;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "right-actions" },
    });
    const __VLS_350 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_351 = __VLS_asFunctionalComponent(__VLS_350, new __VLS_350({}));
    const __VLS_352 = __VLS_351({}, ...__VLS_functionalComponentArgsRest(__VLS_351));
    __VLS_353.slots.default;
    const __VLS_354 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_355 = __VLS_asFunctionalComponent(__VLS_354, new __VLS_354({
        ...{ 'onClick': {} },
    }));
    const __VLS_356 = __VLS_355({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_355));
    let __VLS_358;
    let __VLS_359;
    let __VLS_360;
    const __VLS_361 = {
        onClick: (__VLS_ctx.handleCancel)
    };
    __VLS_357.slots.default;
    var __VLS_357;
    const __VLS_362 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_363 = __VLS_asFunctionalComponent(__VLS_362, new __VLS_362({
        type: "primary",
        htmlType: "submit",
        loading: (__VLS_ctx.submitting),
    }));
    const __VLS_364 = __VLS_363({
        type: "primary",
        htmlType: "submit",
        loading: (__VLS_ctx.submitting),
    }, ...__VLS_functionalComponentArgsRest(__VLS_363));
    __VLS_365.slots.default;
    var __VLS_365;
    var __VLS_353;
    var __VLS_23;
}
/** @type {__VLS_StyleScopedClasses['page-container']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['record-info']} */ ;
/** @type {__VLS_StyleScopedClasses['record-number']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['no-documents']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-list']} */ ;
/** @type {__VLS_StyleScopedClasses['document-item']} */ ;
/** @type {__VLS_StyleScopedClasses['document-header']} */ ;
/** @type {__VLS_StyleScopedClasses['form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['history-list']} */ ;
/** @type {__VLS_StyleScopedClasses['history-item']} */ ;
/** @type {__VLS_StyleScopedClasses['history-time']} */ ;
/** @type {__VLS_StyleScopedClasses['history-user']} */ ;
/** @type {__VLS_StyleScopedClasses['history-action']} */ ;
/** @type {__VLS_StyleScopedClasses['form-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['left-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['right-actions']} */ ;
// @ts-ignore
var __VLS_29 = __VLS_28;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            PlusOutlined: icons_vue_1.PlusOutlined,
            formRef: formRef,
            loading: loading,
            submitting: submitting,
            formData: formData,
            modificationHistory: modificationHistory,
            formRules: formRules,
            formatDateTime: formatDateTime,
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
