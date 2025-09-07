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
const BatchFileProcessor_vue_1 = __importDefault(require("@/components/BatchFileProcessor.vue"));
const LLMApiConfig_vue_1 = __importDefault(require("@/components/LLMApiConfig.vue"));
const LLMResultModal_vue_1 = __importDefault(require("@/components/LLMResultModal.vue"));
const router = (0, vue_router_1.useRouter)();
// 响应式数据
const showLLMConfig = (0, vue_1.ref)(false);
const showHelp = (0, vue_1.ref)(false);
const showBatchResultsModal = (0, vue_1.ref)(false);
const activeResultTab = (0, vue_1.ref)(0);
const savingAll = (0, vue_1.ref)(false);
const batchResults = (0, vue_1.ref)(: any[]);
const operationLogs = (0, vue_1.ref)(: any[]);
const totalProcessed = (0, vue_1.ref)(0);
const successCount = (0, vue_1.ref)(0);
const failureCount = (0, vue_1.ref)(0);
// 计算属性
const averageConfidence = (0, vue_1.computed)(() => {
    if (batchResults.value.length === 0)
        return 0;
    const total = batchResults.value.reduce((sum, result) => {
        return sum + (result.data?.confidence || 0);
    }, 0);
    return Math.round(total / batchResults.value.length);
});
// 表格列定义
const resultColumns = [
    {
        title: '文件名',
        dataIndex: 'fileName',
        key: 'fileName',
        width: 200
    },
    {
        title: '状态',
        key: 'status',
        width: 80
    },
    {
        title: '患者姓名',
        dataIndex: ['data', 'patientName'],
        key: 'patientName',
        width: 120
    },
    {
        title: '科室',
        dataIndex: ['data', 'department'],
        key: 'department',
        width: 100
    },
    {
        title: '置信度',
        key: 'confidence',
        width: 120
    },
    {
        title: '操作',
        key: 'actions',
        width: 120
    }
];
// 方法
const addLog = (message: any, type = 'info') => {
    operationLogs.value.unshift({
        timestamp: new Date(),
        message,
        type
    });
    // 限制日志数量
    if (operationLogs.value.length > 100) {
        operationLogs.value = operationLogs.value.slice(0, 100);
    }
};
const formatTime = (timestamp) => {
    return timestamp.toLocaleTimeString();
};
const clearLogs = () => {
    operationLogs.value = [];
};
const exportLogs = () => {
    const logText = operationLogs.value
        .map(log => `[${formatTime(log.timestamp)}] ${log.type.toUpperCase()}: ${log.message}`)
        .join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `operation_logs_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
};
const getFileIcon = (fileName) => {
    const ext = fileName.split('.').pop()?.toLowerCase();
    if (ext === 'pdf')
        return icons_vue_1.FilePdfOutlined;
    if (['doc', 'docx'].includes(ext || ''))
        return icons_vue_1.FileWordOutlined;
    if (ext === 'txt')
        return icons_vue_1.FileTextOutlined;
    return icons_vue_1.FileOutlined;
};
// 事件处理
const handleFilesProcessed = (results) => {
    addLog(`处理了 ${results.length} 个文件`, 'info');
};
const handleSingleFileProcessed = (result) => {
    totalProcessed.value++;
    if (result.success) {
        successCount.value++;
        addLog(`文件解析成功: ${result.fileName || '未知文件'}`, 'success');
    }
    else {
        failureCount.value++;
        addLog(`文件解析失败: ${result.fileName || '未知文件'}`, 'error');
    }
};
const handleBatchCompleted = (results) => {
    batchResults.value = results;
    addLog(`批量处理完成，共处理 ${results.length} 个文件`, 'success');
    ant_design_vue_1.message.success('批量处理完成!');
};
const handleLLMConfigUpdated = (config) => {
    addLog('LLM配置已更新', 'info');
};
const viewSingleResult = (index) => {
    activeResultTab.value = index;
    showBatchResultsModal.value = true;
};
const saveSingleResult = async (result) => {
    try {
        // 这里实现单个结果保存逻辑
        await new Promise(resolve => setTimeout(resolve, 1000));
        ant_design_vue_1.message.success(`保存 ${result.fileName} 成功`);
        addLog(`保存文件结果: ${result.fileName}`, 'success');
    }
    catch (error) {
        ant_design_vue_1.message.error(`保存失败: ${error.message}`);
        addLog(`保存失败: ${result.fileName} - ${error.message}`, 'error');
    }
};
const exportAllResults = () => {
    const dataStr = JSON.stringify(batchResults.value, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `batch_results_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    addLog('导出所有结果完成', 'success');
};
const saveAllToDatabase = async () => {
    savingAll.value = true;
    try {
        // 这里实现批量保存逻辑
        await new Promise(resolve => setTimeout(resolve, 3000));
        ant_design_vue_1.message.success('批量保存成功!');
        addLog(`批量保存 ${batchResults.value.length} 个文件到数据库`, 'success');
    }
    catch (error) {
        ant_design_vue_1.message.error(`批量保存失败: ${error.message}`);
        addLog(`批量保存失败: ${error.message}`, 'error');
    }
    finally {
        savingAll.value = false;
    }
};
const handleResultSave = (result) => {
    saveSingleResult(result);
};
const handleResultExport = (result) => {
    const dataStr = JSON.stringify(result, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${result.fileName}_result.json`;
    a.click();
    URL.revokeObjectURL(url);
};
const handleResultExportPDF = (result) => {
    ant_design_vue_1.message.info('PDF导出功能开发中...');
};
// 初始化
addLog('批量智能导入系统已就绪', 'info');
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['help-content']} */ ;
/** @type {__VLS_StyleScopedClasses['help-content']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-smart-import-view']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-smart-import-view']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-processor-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-card']} */ ;
/** @type {__VLS_StyleScopedClasses['log-card']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-processor-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-card']} */ ;
/** @type {__VLS_StyleScopedClasses['log-card']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-smart-import-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "title-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "page-subtitle" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-actions" },
});
const __VLS_0 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.SettingOutlined)),
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.SettingOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showLLMConfig = true;
    }
};
__VLS_7.slots.default;
var __VLS_7;
const __VLS_12 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.QuestionCircleOutlined)),
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.QuestionCircleOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showHelp = true;
    }
};
__VLS_15.slots.default;
var __VLS_15;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "main-content" },
});
const __VLS_20 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    gutter: (24),
}));
const __VLS_22 = __VLS_21({
    gutter: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
const __VLS_24 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    span: (16),
}));
const __VLS_26 = __VLS_25({
    span: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    title: "批量文件处理",
    ...{ class: "batch-processor-card" },
}));
const __VLS_30 = __VLS_29({
    title: "批量文件处理",
    ...{ class: "batch-processor-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
/** @type {[typeof BatchFileProcessor, ]} */ ;
// @ts-ignore
const __VLS_32 = __VLS_asFunctionalComponent(BatchFileProcessor_vue_1.default, new BatchFileProcessor_vue_1.default({
    ...{ 'onFilesProcessed': {} },
    ...{ 'onSingleFileProcessed': {} },
    ...{ 'onBatchCompleted': {} },
    maxFileSize: (50),
    maxFileCount: (20),
    allowedTypes: (['.pdf', '.doc', '.docx', '.txt']),
}));
const __VLS_33 = __VLS_32({
    ...{ 'onFilesProcessed': {} },
    ...{ 'onSingleFileProcessed': {} },
    ...{ 'onBatchCompleted': {} },
    maxFileSize: (50),
    maxFileCount: (20),
    allowedTypes: (['.pdf', '.doc', '.docx', '.txt']),
}, ...__VLS_functionalComponentArgsRest(__VLS_32));
let __VLS_35;
let __VLS_36;
let __VLS_37;
const __VLS_38 = {
    onFilesProcessed: (__VLS_ctx.handleFilesProcessed)
};
const __VLS_39 = {
    onSingleFileProcessed: (__VLS_ctx.handleSingleFileProcessed)
};
const __VLS_40 = {
    onBatchCompleted: (__VLS_ctx.handleBatchCompleted)
};
var __VLS_34;
var __VLS_31;
var __VLS_27;
const __VLS_41 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({
    span: (8),
}));
const __VLS_43 = __VLS_42({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
__VLS_44.slots.default;
const __VLS_45 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({
    title: "处理统计",
    ...{ class: "stats-card mb-4" },
}));
const __VLS_47 = __VLS_46({
    title: "处理统计",
    ...{ class: "stats-card mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_46));
__VLS_48.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stats-grid" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.totalProcessed);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.successCount);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.failureCount);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-value" },
});
(__VLS_ctx.averageConfidence);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-label" },
});
var __VLS_48;
const __VLS_49 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
    title: "操作日志",
    ...{ class: "log-card" },
}));
const __VLS_51 = __VLS_50({
    title: "操作日志",
    ...{ class: "log-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
__VLS_52.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "log-container" },
});
for (const [log, index] of __VLS_getVForSourceType((__VLS_ctx.operationLogs))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (index),
        ...{ class: (['log-item', `log-${log.type}`]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "log-time" },
    });
    (__VLS_ctx.formatTime(log.timestamp));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "log-message" },
    });
    (log.message);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "log-actions" },
});
const __VLS_53 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_55 = __VLS_54({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_54));
let __VLS_57;
let __VLS_58;
let __VLS_59;
const __VLS_60 = {
    onClick: (__VLS_ctx.clearLogs)
};
__VLS_56.slots.default;
var __VLS_56;
const __VLS_61 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_63 = __VLS_62({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
let __VLS_65;
let __VLS_66;
let __VLS_67;
const __VLS_68 = {
    onClick: (__VLS_ctx.exportLogs)
};
__VLS_64.slots.default;
var __VLS_64;
var __VLS_52;
var __VLS_44;
var __VLS_23;
if (__VLS_ctx.batchResults.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-summary" },
    });
    const __VLS_69 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
        title: "批量处理结果汇总",
    }));
    const __VLS_71 = __VLS_70({
        title: "批量处理结果汇总",
    }, ...__VLS_functionalComponentArgsRest(__VLS_70));
    __VLS_72.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "summary-actions mb-4" },
    });
    const __VLS_73 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({
        size: "large",
    }));
    const __VLS_75 = __VLS_74({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_74));
    __VLS_76.slots.default;
    const __VLS_77 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
        ...{ 'onClick': {} },
        type: "primary",
        size: "large",
        icon: (__VLS_ctx.h(__VLS_ctx.EyeOutlined)),
    }));
    const __VLS_79 = __VLS_78({
        ...{ 'onClick': {} },
        type: "primary",
        size: "large",
        icon: (__VLS_ctx.h(__VLS_ctx.EyeOutlined)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_78));
    let __VLS_81;
    let __VLS_82;
    let __VLS_83;
    const __VLS_84 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.batchResults.length > 0))
                return;
            __VLS_ctx.showBatchResultsModal = true;
        }
    };
    __VLS_80.slots.default;
    (__VLS_ctx.batchResults.length);
    var __VLS_80;
    const __VLS_85 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
        ...{ 'onClick': {} },
        icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
    }));
    const __VLS_87 = __VLS_86({
        ...{ 'onClick': {} },
        icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    let __VLS_89;
    let __VLS_90;
    let __VLS_91;
    const __VLS_92 = {
        onClick: (__VLS_ctx.exportAllResults)
    };
    __VLS_88.slots.default;
    var __VLS_88;
    const __VLS_93 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.savingAll),
        icon: (__VLS_ctx.h(__VLS_ctx.DatabaseOutlined)),
    }));
    const __VLS_95 = __VLS_94({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.savingAll),
        icon: (__VLS_ctx.h(__VLS_ctx.DatabaseOutlined)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_94));
    let __VLS_97;
    let __VLS_98;
    let __VLS_99;
    const __VLS_100 = {
        onClick: (__VLS_ctx.saveAllToDatabase)
    };
    __VLS_96.slots.default;
    var __VLS_96;
    var __VLS_76;
    const __VLS_101 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({
        columns: (__VLS_ctx.resultColumns),
        dataSource: (__VLS_ctx.batchResults),
        pagination: ({ pageSize: 10 }),
        size: "small",
    }));
    const __VLS_103 = __VLS_102({
        columns: (__VLS_ctx.resultColumns),
        dataSource: (__VLS_ctx.batchResults),
        pagination: ({ pageSize: 10 }),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_102));
    __VLS_104.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_104.slots;
        const [{ column, record, index }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'fileName') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-name-cell" },
            });
            const __VLS_105 = ((__VLS_ctx.getFileIcon(record.fileName)));
            // @ts-ignore
            const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
                ...{ class: "file-icon" },
            }));
            const __VLS_107 = __VLS_106({
                ...{ class: "file-icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_106));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (record.fileName);
        }
        else if (column.key === 'status') {
            const __VLS_109 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
                color: (record.success ? 'success' : 'error'),
            }));
            const __VLS_111 = __VLS_110({
                color: (record.success ? 'success' : 'error'),
            }, ...__VLS_functionalComponentArgsRest(__VLS_110));
            __VLS_112.slots.default;
            (record.success ? '成功' : '失败');
            var __VLS_112;
        }
        else if (column.key === 'confidence') {
            const __VLS_113 = {}.AProgress;
            /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
            // @ts-ignore
            const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
                percent: (Math.round(record.data?.confidence || 0)),
                size: "small",
                status: (record.data?.confidence > 80 ? 'success' : 'normal'),
            }));
            const __VLS_115 = __VLS_114({
                percent: (Math.round(record.data?.confidence || 0)),
                size: "small",
                status: (record.data?.confidence > 80 ? 'success' : 'normal'),
            }, ...__VLS_functionalComponentArgsRest(__VLS_114));
        }
        else if (column.key === 'actions') {
            const __VLS_117 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({}));
            const __VLS_119 = __VLS_118({}, ...__VLS_functionalComponentArgsRest(__VLS_118));
            __VLS_120.slots.default;
            const __VLS_121 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
                ...{ 'onClick': {} },
                size: "small",
            }));
            const __VLS_123 = __VLS_122({
                ...{ 'onClick': {} },
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_122));
            let __VLS_125;
            let __VLS_126;
            let __VLS_127;
            const __VLS_128 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.batchResults.length > 0))
                        return;
                    if (!!(column.key === 'fileName'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'confidence'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.viewSingleResult(index);
                }
            };
            __VLS_124.slots.default;
            var __VLS_124;
            const __VLS_129 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_130 = __VLS_asFunctionalComponent(__VLS_129, new __VLS_129({
                ...{ 'onClick': {} },
                size: "small",
            }));
            const __VLS_131 = __VLS_130({
                ...{ 'onClick': {} },
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_130));
            let __VLS_133;
            let __VLS_134;
            let __VLS_135;
            const __VLS_136 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.batchResults.length > 0))
                        return;
                    if (!!(column.key === 'fileName'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'confidence'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.saveSingleResult(record);
                }
            };
            __VLS_132.slots.default;
            var __VLS_132;
            var __VLS_120;
        }
    }
    var __VLS_104;
    var __VLS_72;
}
const __VLS_137 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_138 = __VLS_asFunctionalComponent(__VLS_137, new __VLS_137({
    open: (__VLS_ctx.showLLMConfig),
    title: "LLM配置",
    width: "720px",
    placement: "right",
}));
const __VLS_139 = __VLS_138({
    open: (__VLS_ctx.showLLMConfig),
    title: "LLM配置",
    width: "720px",
    placement: "right",
}, ...__VLS_functionalComponentArgsRest(__VLS_138));
__VLS_140.slots.default;
/** @type {[typeof LLMApiConfig, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(LLMApiConfig_vue_1.default, new LLMApiConfig_vue_1.default({
    ...{ 'onConfigUpdated': {} },
}));
const __VLS_142 = __VLS_141({
    ...{ 'onConfigUpdated': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
let __VLS_144;
let __VLS_145;
let __VLS_146;
const __VLS_147 = {
    onConfigUpdated: (__VLS_ctx.handleLLMConfigUpdated)
};
var __VLS_143;
var __VLS_140;
const __VLS_148 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    open: (__VLS_ctx.showHelp),
    title: "使用帮助",
    width: "800px",
    footer: (null),
}));
const __VLS_150 = __VLS_149({
    open: (__VLS_ctx.showHelp),
    title: "使用帮助",
    width: "800px",
    footer: (null),
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
__VLS_151.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "help-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_152 = {}.ASteps;
/** @type {[typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
    direction: "vertical",
    size: "small",
}));
const __VLS_154 = __VLS_153({
    direction: "vertical",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_153));
__VLS_155.slots.default;
const __VLS_156 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    title: "上传文件",
}));
const __VLS_158 = __VLS_157({
    title: "上传文件",
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
__VLS_159.slots.default;
{
    const { description: __VLS_thisSlot } = __VLS_159.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
}
var __VLS_159;
const __VLS_160 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
    title: "批量解析",
}));
const __VLS_162 = __VLS_161({
    title: "批量解析",
}, ...__VLS_functionalComponentArgsRest(__VLS_161));
__VLS_163.slots.default;
{
    const { description: __VLS_thisSlot } = __VLS_163.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
}
var __VLS_163;
const __VLS_164 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    title: "查看结果",
}));
const __VLS_166 = __VLS_165({
    title: "查看结果",
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
__VLS_167.slots.default;
{
    const { description: __VLS_thisSlot } = __VLS_167.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
}
var __VLS_167;
const __VLS_168 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    title: "保存导出",
}));
const __VLS_170 = __VLS_169({
    title: "保存导出",
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
{
    const { description: __VLS_thisSlot } = __VLS_171.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
}
var __VLS_171;
var __VLS_155;
var __VLS_151;
const __VLS_172 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    open: (__VLS_ctx.showBatchResultsModal),
    title: "批量解析结果详情",
    width: "1400px",
    footer: (null),
    ...{ class: "batch-results-detail-modal" },
}));
const __VLS_174 = __VLS_173({
    open: (__VLS_ctx.showBatchResultsModal),
    title: "批量解析结果详情",
    width: "1400px",
    footer: (null),
    ...{ class: "batch-results-detail-modal" },
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
__VLS_175.slots.default;
const __VLS_176 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
    activeKey: (__VLS_ctx.activeResultTab),
    type: "card",
}));
const __VLS_178 = __VLS_177({
    activeKey: (__VLS_ctx.activeResultTab),
    type: "card",
}, ...__VLS_functionalComponentArgsRest(__VLS_177));
__VLS_179.slots.default;
for (const [result, index] of __VLS_getVForSourceType((__VLS_ctx.batchResults))) {
    const __VLS_180 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        key: (index),
        tab: (result.fileName),
    }));
    const __VLS_182 = __VLS_181({
        key: (index),
        tab: (result.fileName),
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    __VLS_183.slots.default;
    /** @type {[typeof LLMResultModal, ]} */ ;
    // @ts-ignore
    const __VLS_184 = __VLS_asFunctionalComponent(LLMResultModal_vue_1.default, new LLMResultModal_vue_1.default({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (true),
        data: (result.data),
        result: (result),
        originalText: (result.originalText),
    }));
    const __VLS_185 = __VLS_184({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (true),
        data: (result.data),
        result: (result),
        originalText: (result.originalText),
    }, ...__VLS_functionalComponentArgsRest(__VLS_184));
    let __VLS_187;
    let __VLS_188;
    let __VLS_189;
    const __VLS_190 = {
        'onUpdate:visible': (() => { })
    };
    const __VLS_191 = {
        onSaveAndRedirect: (() => __VLS_ctx.handleResultSave(result))
    };
    const __VLS_192 = {
        onSaveOnly: (() => __VLS_ctx.handleResultSave(result))
    };
    const __VLS_193 = {
        onExportResult: (() => __VLS_ctx.handleResultExport(result))
    };
    const __VLS_194 = {
        onExportPdf: (() => __VLS_ctx.handleResultExportPDF(result))
    };
    const __VLS_195 = {
        onGoToImport: (() => { })
    };
    var __VLS_186;
    var __VLS_183;
}
var __VLS_179;
var __VLS_175;
/** @type {__VLS_StyleScopedClasses['batch-smart-import-view']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['title-section']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-processor-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['log-card']} */ ;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
/** @type {__VLS_StyleScopedClasses['log-item']} */ ;
/** @type {__VLS_StyleScopedClasses['log-time']} */ ;
/** @type {__VLS_StyleScopedClasses['log-message']} */ ;
/** @type {__VLS_StyleScopedClasses['log-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['file-name-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['file-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['help-content']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-results-detail-modal']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            SettingOutlined: icons_vue_1.SettingOutlined,
            QuestionCircleOutlined: icons_vue_1.QuestionCircleOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            BatchFileProcessor: BatchFileProcessor_vue_1.default,
            LLMApiConfig: LLMApiConfig_vue_1.default,
            LLMResultModal: LLMResultModal_vue_1.default,
            showLLMConfig: showLLMConfig,
            showHelp: showHelp,
            showBatchResultsModal: showBatchResultsModal,
            activeResultTab: activeResultTab,
            savingAll: savingAll,
            batchResults: batchResults,
            operationLogs: operationLogs,
            totalProcessed: totalProcessed,
            successCount: successCount,
            failureCount: failureCount,
            averageConfidence: averageConfidence,
            resultColumns: resultColumns,
            formatTime: formatTime,
            clearLogs: clearLogs,
            exportLogs: exportLogs,
            getFileIcon: getFileIcon,
            handleFilesProcessed: handleFilesProcessed,
            handleSingleFileProcessed: handleSingleFileProcessed,
            handleBatchCompleted: handleBatchCompleted,
            handleLLMConfigUpdated: handleLLMConfigUpdated,
            viewSingleResult: viewSingleResult,
            saveSingleResult: saveSingleResult,
            exportAllResults: exportAllResults,
            saveAllToDatabase: saveAllToDatabase,
            handleResultSave: handleResultSave,
            handleResultExport: handleResultExport,
            handleResultExportPDF: handleResultExportPDF,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
