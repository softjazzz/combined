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
const MedicalDocumentResultModal_vue_1 = __importDefault(require("@/components/MedicalDocumentResultModal.vue"));
const visible = (0, vue_1.ref)(false);
const originalText = (0, vue_1.ref)(`
入院记录
患者姓名：张三
性别：男
年龄：65岁
主诉：胸痛3天

现病史：
患者3天前无明显诱因出现胸痛，呈压榨性，持续性，伴有气短、出汗。

首次病程记录 2024-01-15 08:30
患者入院后完善相关检查，心电图示：ST段抬高，考虑急性心肌梗死。
给予阿司匹林、氯吡格雷抗血小板聚集治疗。

手术记录 2024-01-15 14:00
在局麻下行冠状动脉造影术，发现前降支近段完全闭塞。
成功植入支架1枚，术后血流恢复良好。

出院记录 2024-01-20 10:00
患者经治疗后症状明显改善，心电图复查正常。
诊断：急性ST段抬高型心肌梗死
建议：定期复查，按时服药。
`);
const testData = (0, vue_1.ref)({
    recordNumber: 'TEST_20240115_001',
    patientName: '张三',
    patientAge: 65,
    patientGender: '男',
    department: '心内科',
    primaryDiagnosis: '急性ST段抬高型心肌梗死',
    secondaryDiagnosis: ['高血压病', '糖尿病'],
    majorSurgery: '冠状动脉造影术+支架植入术',
    confidence: 92,
    documents: [
        {
            id: 'doc_1',
            type: 'admission_record',
            title: '入院记录',
            content: '患者张三，男，65岁，因胸痛3天入院。患者3天前无明显诱因出现胸痛，呈压榨性，持续性，伴有气短、出汗。',
            confidence: 95,
            extractedAt: new Date('2024-01-15T08:00:00'),
            position: {
                startMarker: '入院记录',
                endMarker: '现病史',
                startIndex: 0,
                endIndex: 120
            }
        },
        {
            id: 'doc_2',
            type: 'first_progress_note',
            title: '首次病程记录',
            content: '患者入院后完善相关检查，心电图示：ST段抬高，考虑急性心肌梗死。给予阿司匹林、氯吡格雷抗血小板聚集治疗。',
            confidence: 88,
            extractedAt: new Date('2024-01-15T08:30:00'),
            position: {
                startMarker: '首次病程记录 2024-01-15 08:30',
                endMarker: '手术记录',
                startIndex: 121,
                endIndex: 250
            }
        },
        {
            id: 'doc_3',
            type: 'operation_record',
            title: '手术记录',
            content: '在局麻下行冠状动脉造影术，发现前降支近段完全闭塞。成功植入支架1枚，术后血流恢复良好。',
            confidence: 90,
            extractedAt: new Date('2024-01-15T14:00:00'),
            position: {
                startMarker: '手术记录 2024-01-15 14:00',
                endMarker: '出院记录',
                startIndex: 251,
                endIndex: 380
            }
        },
        {
            id: 'doc_4',
            type: 'discharge_record',
            title: '出院记录',
            content: '患者经治疗后症状明显改善，心电图复查正常。诊断：急性ST段抬高型心肌梗死。建议：定期复查，按时服药。',
            confidence: 93,
            extractedAt: new Date('2024-01-20T10:00:00'),
            position: {
                startMarker: '出院记录 2024-01-20 10:00',
                endMarker: '',
                startIndex: 381,
                endIndex: 500
            }
        },
        {
            id: 'doc_5',
            type: 'lab_report',
            title: '实验室检查报告',
            content: '血常规：WBC 8.5×10⁹/L，RBC 4.2×10¹²/L，Hb 135g/L。心肌酶：CK-MB 85U/L，cTnI 8.5ng/ml。',
            confidence: 96,
            extractedAt: new Date('2024-01-15T09:00:00'),
            position: {
                startMarker: '实验室检查报告',
                endMarker: '影像检查报告',
                startIndex: 501,
                endIndex: 600
            }
        },
        {
            id: 'doc_6',
            type: 'imaging_report',
            title: '影像检查报告',
            content: '心电图：窦性心律，ST段抬高，V1-V4导联明显。胸片：心影轻度增大，肺野清晰。',
            confidence: 94,
            extractedAt: new Date('2024-01-15T09:30:00'),
            position: {
                startMarker: '影像检查报告',
                endMarker: '手术知情同意书',
                startIndex: 601,
                endIndex: 700
            }
        },
        {
            id: 'doc_7',
            type: 'surgery_consent',
            title: '手术知情同意书',
            content: '冠状动脉造影+支架植入术知情同意书。手术风险：出血、血管损伤、心律失常等。患者及家属同意手术。',
            confidence: 89,
            extractedAt: new Date('2024-01-15T13:00:00'),
            position: {
                startMarker: '手术知情同意书',
                endMarker: '',
                startIndex: 701,
                endIndex: 800
            }
        }
    ]
});
const showTestModal = () => {
    visible.value = true;
};
const showEmptyModal = () => {
    testData.value = {
        recordNumber: '',
        patientName: '',
        department: '',
        primaryDiagnosis: '',
        majorSurgery: '',
        confidence: 0,
        documents: []
    };
    visible.value = true;
};
const handleConfirm = (data) => {
    ant_design_vue_1.message.success('用户确认了解析结果');
    console.log('确认的数据:', data);
};
const handleExport = (data) => {
    ant_design_vue_1.message.success('导出解析结果');
    console.log('导出的数据:', data);
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "modal-test-page" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "医疗文书解析结果Modal测试",
}));
const __VLS_2 = __VLS_1({
    title: "医疗文书解析结果Modal测试",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
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
    onClick: (__VLS_ctx.showTestModal)
};
__VLS_11.slots.default;
var __VLS_11;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.showEmptyModal)
};
__VLS_19.slots.default;
var __VLS_19;
var __VLS_7;
var __VLS_3;
/** @type {[typeof MedicalDocumentResultModal, ]} */ ;
// @ts-ignore
const __VLS_24 = __VLS_asFunctionalComponent(MedicalDocumentResultModal_vue_1.default, new MedicalDocumentResultModal_vue_1.default({
    ...{ 'onConfirm': {} },
    ...{ 'onExport': {} },
    visible: (__VLS_ctx.visible),
    data: (__VLS_ctx.testData),
    originalText: (__VLS_ctx.originalText),
}));
const __VLS_25 = __VLS_24({
    ...{ 'onConfirm': {} },
    ...{ 'onExport': {} },
    visible: (__VLS_ctx.visible),
    data: (__VLS_ctx.testData),
    originalText: (__VLS_ctx.originalText),
}, ...__VLS_functionalComponentArgsRest(__VLS_24));
let __VLS_27;
let __VLS_28;
let __VLS_29;
const __VLS_30 = {
    onConfirm: (__VLS_ctx.handleConfirm)
};
const __VLS_31 = {
    onExport: (__VLS_ctx.handleExport)
};
var __VLS_26;
/** @type {__VLS_StyleScopedClasses['modal-test-page']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            MedicalDocumentResultModal: MedicalDocumentResultModal_vue_1.default,
            visible: visible,
            originalText: originalText,
            testData: testData,
            showTestModal: showTestModal,
            showEmptyModal: showEmptyModal,
            handleConfirm: handleConfirm,
            handleExport: handleExport,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
