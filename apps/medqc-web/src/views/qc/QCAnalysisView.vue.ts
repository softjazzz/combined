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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import vue_router_1 from 'vue-router';
import icons_vue_1 from '@ant-design/icons-vue';
const QCAnalysisPanel_vue_1 = __importDefault(require("@/components/medical/QCAnalysisPanel.vue"));
const router = (0, vue_router_1.useRouter)();
const route = (0, vue_router_1.useRoute)();
// 响应式数据
const recordId = (0, vue_1.ref)(route.params.id || 'demo-record-1');
const recordContent = (0, vue_1.ref)('');
// 示例病历内容
const sampleRecord = `病案首页
患者姓名：张三    性别：男    年龄：45岁
入院日期：2024-01-15    出院日期：2024-01-22
科室：心内科

主诉：胸闷气短3天

现病史：
患者3天前无明显诱因出现胸闷气短，活动后加重，伴有心慌，无胸痛、晕厥等症状。既往有高血压病史5年，规律服用降压药物。吸烟史20年，每日1包。

体格检查：
T：36.5℃  P：96次/分  R：20次/分  BP：150/90mmHg
心界稍向左扩大，心律齐，心率96次/分，各瓣膜听诊区未闻及明显杂音。
双肺呼吸音清，未闻及干湿性啰音。

辅助检查：
心电图：窦性心律，ST-T改变
胸片：心影稍增大
血常规：WBC 6.2×10⁹/L，RBC 4.5×10¹²/L，Hb 140g/L
肌钙蛋白I：0.15ng/ml（正常<0.04）

入院诊断：
1. 急性心肌梗死？
2. 高血压病3级 极高危

诊疗经过：
入院后完善相关检查，心电图示ST段抬高，结合临床症状及肌钙蛋白升高，诊断急性ST段抬高型心肌梗死。立即给予双联抗血小板、抗凝、调脂稳定斑块等治疗。

出院诊断：
1. 急性ST段抬高型心肌梗死
2. 高血压病3级 极高危

出院医嘱：
1. 低盐低脂饮食
2. 戒烟戒酒
3. 口服阿司匹林100mg qd
4. 口服氯吡格雷75mg qd
5. 口服美托洛尔25mg bid
6. 定期复查`;
// 方法
const goBack = () => {
    router.back();
};
// 生命周期
(0, vue_1.onMounted)(() => {
    recordContent.value = sampleRecord;
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-4" },
});
const __VLS_0 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ArrowLeftOutlined)),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ArrowLeftOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onClick: (__VLS_ctx.goBack)
};
__VLS_3.slots.default;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-12 gap-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "col-span-5" },
});
const __VLS_8 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    title: "病历内容",
    ...{ class: "h-full" },
}));
const __VLS_10 = __VLS_9({
    title: "病历内容",
    ...{ class: "h-full" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    value: (__VLS_ctx.recordContent),
    placeholder: "请输入或粘贴病历内容...",
    rows: (20),
    ...{ class: "font-mono text-sm" },
}));
const __VLS_14 = __VLS_13({
    value: (__VLS_ctx.recordContent),
    placeholder: "请输入或粘贴病历内容...",
    rows: (20),
    ...{ class: "font-mono text-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
var __VLS_11;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "col-span-7" },
});
/** @type {[typeof QCAnalysisPanel, ]} */ ;
// @ts-ignore
const __VLS_16 = __VLS_asFunctionalComponent(QCAnalysisPanel_vue_1.default, new QCAnalysisPanel_vue_1.default({
    recordId: (__VLS_ctx.recordId),
    recordContent: (__VLS_ctx.recordContent),
}));
const __VLS_17 = __VLS_16({
    recordId: (__VLS_ctx.recordId),
    recordContent: (__VLS_ctx.recordContent),
}, ...__VLS_functionalComponentArgsRest(__VLS_16));
/** @type {__VLS_StyleScopedClasses['page-container']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-12']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['col-span-5']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['col-span-7']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            ArrowLeftOutlined: icons_vue_1.ArrowLeftOutlined,
            QCAnalysisPanel: QCAnalysisPanel_vue_1.default,
            recordId: recordId,
            recordContent: recordContent,
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
