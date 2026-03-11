"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function (o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
        desc = { enumerable: true, get: function () { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function (o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function (o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function (o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function (o) {
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
const LLMResultModal_vue_1 = __importDefault(require("@/components/LLMResultModal.vue"));
import llmParse_1 from '@/stores/llmParse';
import llmServiceNew_1 from '@/services/llmServiceNew';
const router = (0, vue_router_1.useRouter)();
const store = (0, llmParse_1.useLLMParseStore)();
// 响应式变量
const saving = (0, vue_1.ref)(false);
// API配置
const API_BASE_URL = 'http://localhost:8001';
(0, vue_1.onMounted)(() => {
    if (!store.lastResult)
        store.loadFromSession();
});
const result = (0, vue_1.computed)(() => store.lastResult);
const data = (0, vue_1.computed)(() => result.value?.data);
// 获取当前LLM配置信息
const currentLLMConfig = (0, vue_1.computed)(() => llmServiceNew_1.llmService.getCurrentConfig());
const providerName = (0, vue_1.computed)(() => currentLLMConfig.value?.provider?.provider_name || '未知提供商');
const modelCode = (0, vue_1.computed)(() => currentLLMConfig.value?.model?.model_code || '未知模型');
const modelName = (0, vue_1.computed)(() => currentLLMConfig.value?.model?.model_name || '未知模型');
// 从解析结果中获取统计信息
const tokensUsed = (0, vue_1.computed)(() => result.value?.tokensUsed || 0);
const confidencePct = (0, vue_1.computed)(() => result.value?.confidence || 0);
// Modal关闭处理
const handleModalClose = () => {
    router.push('/dashboard');
};
const exportResult = () => {
    if (!result.value) {
        ant_design_vue_1.message.warning('没有可导出的结果');
        return;
    }
    const str = JSON.stringify(result.value, null, 2);
    const blob = new Blob([str], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `llm_parse_result_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
};
// 保存并跳转到详情页面
const saveAndRedirect = async () => {
    const savedRecordId = await saveToDatabase();
    if (savedRecordId) {
        ant_design_vue_1.message.success('保存成功，正在跳转到详情页面...');
        setTimeout(() => {
            router.push(`/dashboard/medical-records/${savedRecordId}`);
        }, 1500);
    }
};
// 仅保存到数据库
const saveOnly = async () => {
    const savedRecordId = await saveToDatabase();
    if (savedRecordId) {
        ant_design_vue_1.message.success('解析结果已保存到数据库');
    }
};
// 保存到数据库的核心方法
const saveToDatabase = async () => {
    if (!data.value) {
        ant_design_vue_1.message.error('没有可保存的数据');
        return null;
    }
    try {
        saving.value = true;
        // 使用测试部门ID和用户ID（实际应用中应该从认证信息获取）
        const defaultDepartmentId = "11111111-1111-1111-1111-111111111111";
        const defaultUserId = "22222222-2222-2222-2222-222222222222";
        // 构建保存数据，符合后端API期望的结构
        const saveData = {
            record_number: data.value.recordNumber || `LLM_${Date.now()}`,
            patient_name: data.value.patientName || '未识别',
            patient_age: data.value.patientAge || null,
            patient_gender: data.value.patientGender || null,
            department_id: defaultDepartmentId,
            doctor_id: null,
            admission_date: null,
            discharge_date: null,
            record_type: "inpatient",
            diagnosis_primary: data.value.primaryDiagnosis || '未识别',
            diagnosis_secondary: data.value.secondaryDiagnosis || [],
            content: data.value.content || '',
            content_sections: {
                documents: data.value.documents || [],
                major_surgery: data.value.majorSurgery || '无',
                department: data.value.department || '未识别'
            },
            file_attachments: [],
            total_pages: 1,
            word_count: (data.value.content || '').length,
            priority_level: 1,
            tags: ["LLM精准解析"],
            metadata: {
                method: 'LLM精准解析',
                confidence: data.value.confidence || 0,
                parse_metadata: {
                    provider: providerName.value,
                    model: modelCode.value,
                    model_name: modelName.value,
                    tokens_used: tokensUsed.value,
                    processing_time: result.value?.processingTime || 0,
                    confidence: confidencePct.value
                },
                import_time: new Date().toISOString()
            },
            created_by: defaultUserId
        };
        // 创建FormData，因为后端API期望Form数据
        const formData = new FormData();
        formData.append('patient_name', saveData.patient_name);
        formData.append('patient_age', saveData.patient_age?.toString() || '0');
        formData.append('patient_gender', saveData.patient_gender || 'U');
        formData.append('department', saveData.content_sections?.department || '未识别');
        formData.append('admission_date', new Date().toISOString().split('T')[0]);
        formData.append('record_type', saveData.record_type);
        formData.append('content', saveData.content);
        // 获取认证token
        const token = localStorage.getItem('medqc_access_token');
        // 使用认证的API客户端发送请求
        const response = await fetch(`${API_BASE_URL}/api/records`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token || ''}`,
            },
            body: formData
        });
        if (!response.ok) {
            throw new Error(`保存失败: ${response.status}`);
        }
        const savedRecord = await response.json();
        return savedRecord.id;
    }
    catch (error) {
        console.error('保存失败:', error);
        ant_design_vue_1.message.error(`保存失败: ${error.message}`);
        return null;
    }
    finally {
        saving.value = false;
    }
};
// 导出PDF报告
const exportPDF = () => {
    ant_design_vue_1.message.info('PDF导出功能开发中...');
    // TODO: 实现PDF导出功能
};
// 跳转到导入页面
const goToImport = () => {
    router.push('/dashboard/medical-records/smart-import');
};
const goBack = () => {
    router.push('/dashboard');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "result-page" },
});
if (!__VLS_ctx.result || !__VLS_ctx.result.success || !__VLS_ctx.data) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-result-container" },
    });
    const __VLS_0 = {}.APageHeader;
    /** @type {[typeof __VLS_components.APageHeader, typeof __VLS_components.aPageHeader, ]} */;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        title: "LLM 精准解析结果",
        subTitle: "结构化信息与文书目录",
    }));
    const __VLS_2 = __VLS_1({
        title: "LLM 精准解析结果",
        subTitle: "结构化信息与文书目录",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    const __VLS_4 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        type: "warning",
        showIcon: true,
        ...{ class: "mb-3" },
        message: "没有可展示的结果",
        description: "请先在智能导入或简易导入中运行一次 LLM 精准解析。",
    }));
    const __VLS_6 = __VLS_5({
        type: "warning",
        showIcon: true,
        ...{ class: "mb-3" },
        message: "没有可展示的结果",
        description: "请先在智能导入或简易导入中运行一次 LLM 精准解析。",
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "back-button" },
    });
    const __VLS_8 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_12;
    let __VLS_13;
    let __VLS_14;
    const __VLS_15 = {
        onClick: (__VLS_ctx.goBack)
    };
    __VLS_11.slots.default;
    var __VLS_11;
}
else {
    /** @type {[typeof LLMResultModal, ]} */;
    // @ts-ignore
    const __VLS_16 = __VLS_asFunctionalComponent(LLMResultModal_vue_1.default, new LLMResultModal_vue_1.default({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (true),
        data: (__VLS_ctx.data),
        result: (__VLS_ctx.result),
        originalText: (__VLS_ctx.data?.content),
    }));
    const __VLS_17 = __VLS_16({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (true),
        data: (__VLS_ctx.data),
        result: (__VLS_ctx.result),
        originalText: (__VLS_ctx.data?.content),
    }, ...__VLS_functionalComponentArgsRest(__VLS_16));
    let __VLS_19;
    let __VLS_20;
    let __VLS_21;
    const __VLS_22 = {
        'onUpdate:visible': (__VLS_ctx.handleModalClose)
    };
    const __VLS_23 = {
        onSaveAndRedirect: (__VLS_ctx.saveAndRedirect)
    };
    const __VLS_24 = {
        onSaveOnly: (__VLS_ctx.saveOnly)
    };
    const __VLS_25 = {
        onExportResult: (__VLS_ctx.exportResult)
    };
    const __VLS_26 = {
        onExportPdf: (__VLS_ctx.exportPDF)
    };
    const __VLS_27 = {
        onGoToImport: (__VLS_ctx.goToImport)
    };
    var __VLS_18;
}
/** @type {__VLS_StyleScopedClasses['result-page']} */;
/** @type {__VLS_StyleScopedClasses['no-result-container']} */;
/** @type {__VLS_StyleScopedClasses['mb-3']} */;
/** @type {__VLS_StyleScopedClasses['back-button']} */;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            LLMResultModal: LLMResultModal_vue_1.default,
            result: result,
            data: data,
            handleModalClose: handleModalClose,
            exportResult: exportResult,
            saveAndRedirect: saveAndRedirect,
            saveOnly: saveOnly,
            exportPDF: exportPDF,
            goToImport: goToImport,
            goBack: goBack,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */

