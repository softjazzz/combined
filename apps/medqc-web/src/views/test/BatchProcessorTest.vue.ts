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
import ant_design_vue_1 from 'ant-design-vue';
const BatchFileProcessor_vue_1 = __importDefault(require("@/components/BatchFileProcessor.vue"));
// 响应式数据
const logs = (0, vue_1.ref)(: any[]);
// 方法
const addLog = (message, type = 'info') => {
    logs.value.unshift({
        timestamp: new Date(),
        message,
        type
    });
    // 限制日志数量
    if (logs.value.length > 50) {
        logs.value = logs.value.slice(0, 50);
    }
};
const formatTime = (timestamp) => {
    return timestamp.toLocaleTimeString();
};
const clearLogs = () => {
    logs.value = [];
};
// 事件处理
const handleFilesProcessed = (results) => {
    addLog(`处理了 ${results.length} 个文件`, 'info');
    ant_design_vue_1.message.info(`处理了 ${results.length} 个文件`);
};
const handleSingleFileProcessed = (result) => {
    if (result.success) {
        addLog(`文件解析成功: ${result.fileName || '未知文件'}`, 'success');
    }
    else {
        addLog(`文件解析失败: ${result.fileName || '未知文件'}`, 'error');
    }
};
const handleBatchCompleted = (results) => {
    const successCount = results.filter(r => r.success).length;
    const failCount = results.length - successCount;
    addLog(`批量处理完成: 成功 ${successCount} 个，失败 ${failCount} 个`, 'success');
    ant_design_vue_1.message.success(`批量处理完成: 成功 ${successCount} 个，失败 ${failCount} 个`);
};
// 初始化
addLog('批量文件处理测试页面已加载', 'info');
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-processor-test" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "test-content" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "批量文件处理组件测试",
}));
const __VLS_2 = __VLS_1({
    title: "批量文件处理组件测试",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
/** @type {[typeof BatchFileProcessor, ]} */ ;
// @ts-ignore
const __VLS_4 = __VLS_asFunctionalComponent(BatchFileProcessor_vue_1.default, new BatchFileProcessor_vue_1.default({
    ...{ 'onFilesProcessed': {} },
    ...{ 'onSingleFileProcessed': {} },
    ...{ 'onBatchCompleted': {} },
    maxFileSize: (50),
    maxFileCount: (10),
    allowedTypes: (['.pdf', '.doc', '.docx', '.txt']),
}));
const __VLS_5 = __VLS_4({
    ...{ 'onFilesProcessed': {} },
    ...{ 'onSingleFileProcessed': {} },
    ...{ 'onBatchCompleted': {} },
    maxFileSize: (50),
    maxFileCount: (10),
    allowedTypes: (['.pdf', '.doc', '.docx', '.txt']),
}, ...__VLS_functionalComponentArgsRest(__VLS_4));
let __VLS_7;
let __VLS_8;
let __VLS_9;
const __VLS_10 = {
    onFilesProcessed: (__VLS_ctx.handleFilesProcessed)
};
const __VLS_11 = {
    onSingleFileProcessed: (__VLS_ctx.handleSingleFileProcessed)
};
const __VLS_12 = {
    onBatchCompleted: (__VLS_ctx.handleBatchCompleted)
};
var __VLS_6;
var __VLS_3;
const __VLS_13 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent(__VLS_13, new __VLS_13({
    title: "处理日志",
    ...{ class: "mt-4" },
}));
const __VLS_15 = __VLS_14({
    title: "处理日志",
    ...{ class: "mt-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
__VLS_16.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "log-container" },
});
for (const [log, index] of __VLS_getVForSourceType((__VLS_ctx.logs))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (index),
        ...{ class: (['log-item', `log-${log.type}`]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "log-time" },
    });
    (__VLS_ctx.formatTime(log.timestamp));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "log-message" },
    });
    (log.message);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "log-actions mt-2" },
});
const __VLS_17 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_19 = __VLS_18({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
let __VLS_21;
let __VLS_22;
let __VLS_23;
const __VLS_24 = {
    onClick: (__VLS_ctx.clearLogs)
};
__VLS_20.slots.default;
var __VLS_20;
var __VLS_16;
/** @type {__VLS_StyleScopedClasses['batch-processor-test']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['test-content']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
/** @type {__VLS_StyleScopedClasses['log-item']} */ ;
/** @type {__VLS_StyleScopedClasses['log-time']} */ ;
/** @type {__VLS_StyleScopedClasses['log-message']} */ ;
/** @type {__VLS_StyleScopedClasses['log-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            BatchFileProcessor: BatchFileProcessor_vue_1.default,
            logs: logs,
            formatTime: formatTime,
            clearLogs: clearLogs,
            handleFilesProcessed: handleFilesProcessed,
            handleSingleFileProcessed: handleSingleFileProcessed,
            handleBatchCompleted: handleBatchCompleted,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
