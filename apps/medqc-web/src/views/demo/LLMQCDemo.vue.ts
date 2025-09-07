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
import llm_qc_demo_1 from '@/services/llm-qc-demo';
// 响应式数据
const initialized = (0, vue_1.ref)(false);
const initializing = (0, vue_1.ref)(false);
const analyzing = (0, vue_1.ref)(false);
const managingRules = (0, vue_1.ref)(false);
const runningFullDemo = (0, vue_1.ref)(false);
const qcResult = (0, vue_1.ref)(null);
const logs = (0, vue_1.ref)(: any[]);
const cacheStats = (0, vue_1.reactive)({
    hitRate: 0,
    totalRequests: 0,
    cacheSize: 0
});
const executionMetrics = (0, vue_1.reactive)({
    totalExecutions: 0,
    successfulExecutions: 0,
    averageExecutionTime: 0
});
// 日志记录函数
const addLog = (message) => {
    const timestamp = new Date().toLocaleTimeString();
    logs.value.push(`[${timestamp}] ${message}`);
    // 保持最新的50条日志
    if (logs.value.length > 50) {
        logs.value = logs.value.slice(-50);
    }
};
// 重写console.log来捕获日志
const originalConsoleLog = console.log;
console.log = (...args) => {
    originalConsoleLog(...args);
    addLog(args.join(' '));
};
// 方法实现
const initializeDemo = async () => {
    try {
        initializing.value = true;
        addLog('开始初始化演示环境...');
        await llm_qc_demo_1.llmQCDemoService.initializeDemo();
        initialized.value = true;
        // 更新统计信息
        await updateStats();
        addLog('✅ 演示环境初始化完成');
        ant_design_vue_1.message.success('演示环境初始化成功');
    }
    catch (error) {
        addLog(`❌ 初始化失败: ${error.message}`);
        ant_design_vue_1.message.error('初始化失败');
    }
    finally {
        initializing.value = false;
    }
};
const runQCDemo = async () => {
    try {
        analyzing.value = true;
        addLog('开始执行质控分析演示...');
        const result = await llm_qc_demo_1.llmQCDemoService.runQCDemo();
        qcResult.value = result;
        // 更新统计信息
        await updateStats();
        addLog('✅ 质控分析演示完成');
        ant_design_vue_1.message.success('质控分析完成');
    }
    catch (error) {
        addLog(`❌ 质控分析失败: ${error.message}`);
        ant_design_vue_1.message.error('质控分析失败');
    }
    finally {
        analyzing.value = false;
    }
};
const demonstrateRuleManagement = async () => {
    try {
        managingRules.value = true;
        addLog('开始规则管理演示...');
        await llm_qc_demo_1.llmQCDemoService.demonstrateRuleManagement();
        // 更新统计信息
        await updateStats();
        addLog('✅ 规则管理演示完成');
        ant_design_vue_1.message.success('规则管理演示完成');
    }
    catch (error) {
        addLog(`❌ 规则管理演示失败: ${error.message}`);
        ant_design_vue_1.message.error('规则管理演示失败');
    }
    finally {
        managingRules.value = false;
    }
};
const runFullDemo = async () => {
    try {
        runningFullDemo.value = true;
        addLog('开始完整功能演示...');
        const result = await llm_qc_demo_1.llmQCDemoService.runFullDemo();
        qcResult.value = result;
        initialized.value = true;
        // 更新统计信息
        await updateStats();
        addLog('✅ 完整功能演示完成');
        ant_design_vue_1.message.success('完整功能演示完成');
    }
    catch (error) {
        addLog(`❌ 完整功能演示失败: ${error.message}`);
        ant_design_vue_1.message.error('完整功能演示失败');
    }
    finally {
        runningFullDemo.value = false;
    }
};
const updateStats = async () => {
    try {
        const cacheStatsData = await llm_qc_demo_1.llmQCDemoService.getCacheStats();
        Object.assign(cacheStats, cacheStatsData.overall);
        const execMetricsData = await llm_qc_demo_1.llmQCDemoService.getExecutionMetrics();
        Object.assign(executionMetrics, execMetricsData);
    }
    catch (error) {
        console.error('Failed to update stats:', error);
    }
};
const clearLogs = () => {
    logs.value = [];
    addLog('日志已清空');
};
// 生命周期
(0, vue_1.onMounted)(() => {
    addLog('LLM集成质控系统演示页面已加载');
    addLog('请点击"初始化演示环境"开始体验');
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['demo-header']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-panel']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "llm-qc-demo" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "demo-description" },
});
const __VLS_0 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    gutter: (24),
}));
const __VLS_2 = __VLS_1({
    gutter: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    span: (8),
}));
const __VLS_6 = __VLS_5({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    title: "控制面板",
    ...{ class: "control-panel" },
}));
const __VLS_10 = __VLS_9({
    title: "控制面板",
    ...{ class: "control-panel" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    direction: "vertical",
    ...{ style: {} },
}));
const __VLS_14 = __VLS_13({
    direction: "vertical",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    type: "primary",
    block: true,
    loading: (__VLS_ctx.initializing),
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    type: "primary",
    block: true,
    loading: (__VLS_ctx.initializing),
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.initializeDemo)
};
__VLS_19.slots.default;
var __VLS_19;
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    block: true,
    loading: (__VLS_ctx.analyzing),
    disabled: (!__VLS_ctx.initialized),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    block: true,
    loading: (__VLS_ctx.analyzing),
    disabled: (!__VLS_ctx.initialized),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.runQCDemo)
};
__VLS_27.slots.default;
var __VLS_27;
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onClick': {} },
    block: true,
    loading: (__VLS_ctx.managingRules),
    disabled: (!__VLS_ctx.initialized),
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    block: true,
    loading: (__VLS_ctx.managingRules),
    disabled: (!__VLS_ctx.initialized),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (__VLS_ctx.demonstrateRuleManagement)
};
__VLS_35.slots.default;
var __VLS_35;
const __VLS_40 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
    block: true,
    loading: (__VLS_ctx.runningFullDemo),
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
    block: true,
    loading: (__VLS_ctx.runningFullDemo),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (__VLS_ctx.runFullDemo)
};
__VLS_43.slots.default;
var __VLS_43;
const __VLS_48 = {}.ADivider;
/** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
const __VLS_52 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    ...{ 'onClick': {} },
    block: true,
    type: "dashed",
}));
const __VLS_54 = __VLS_53({
    ...{ 'onClick': {} },
    block: true,
    type: "dashed",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
let __VLS_56;
let __VLS_57;
let __VLS_58;
const __VLS_59 = {
    onClick: (__VLS_ctx.clearLogs)
};
__VLS_55.slots.default;
var __VLS_55;
var __VLS_15;
var __VLS_11;
const __VLS_60 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    title: "系统状态",
    ...{ class: "status-panel" },
    ...{ style: {} },
}));
const __VLS_62 = __VLS_61({
    title: "系统状态",
    ...{ class: "status-panel" },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
const __VLS_64 = {}.ADescriptions;
/** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    column: (1),
    size: "small",
}));
const __VLS_66 = __VLS_65({
    column: (1),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
const __VLS_68 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    label: "初始化状态",
}));
const __VLS_70 = __VLS_69({
    label: "初始化状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.ATag;
/** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    color: (__VLS_ctx.initialized ? 'green' : 'orange'),
}));
const __VLS_74 = __VLS_73({
    color: (__VLS_ctx.initialized ? 'green' : 'orange'),
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
(__VLS_ctx.initialized ? '已初始化' : '未初始化');
var __VLS_75;
var __VLS_71;
const __VLS_76 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    label: "缓存命中率",
}));
const __VLS_78 = __VLS_77({
    label: "缓存命中率",
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
(__VLS_ctx.cacheStats.hitRate ? (__VLS_ctx.cacheStats.hitRate * 100).toFixed(1) + '%' : 'N/A');
var __VLS_79;
const __VLS_80 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    label: "执行次数",
}));
const __VLS_82 = __VLS_81({
    label: "执行次数",
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
(__VLS_ctx.executionMetrics.totalExecutions || 0);
var __VLS_83;
const __VLS_84 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    label: "成功率",
}));
const __VLS_86 = __VLS_85({
    label: "成功率",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
(__VLS_ctx.executionMetrics.totalExecutions ?
    ((__VLS_ctx.executionMetrics.successfulExecutions / __VLS_ctx.executionMetrics.totalExecutions) * 100).toFixed(1) + '%' : 'N/A');
var __VLS_87;
var __VLS_67;
var __VLS_63;
var __VLS_7;
const __VLS_88 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    span: (16),
}));
const __VLS_90 = __VLS_89({
    span: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
const __VLS_92 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    title: "执行结果",
    ...{ class: "results-panel" },
}));
const __VLS_94 = __VLS_93({
    title: "执行结果",
    ...{ class: "results-panel" },
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
if (__VLS_ctx.qcResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "qc-results" },
    });
    const __VLS_96 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        message: (`质控分析完成 - 总分: ${__VLS_ctx.qcResult.overallScore}/100`),
        description: (__VLS_ctx.qcResult.summary),
        type: (__VLS_ctx.qcResult.riskLevel === 'low' ? 'success' :
            __VLS_ctx.qcResult.riskLevel === 'medium' ? 'warning' : 'error'),
        showIcon: true,
        ...{ style: {} },
    }));
    const __VLS_98 = __VLS_97({
        message: (`质控分析完成 - 总分: ${__VLS_ctx.qcResult.overallScore}/100`),
        description: (__VLS_ctx.qcResult.summary),
        type: (__VLS_ctx.qcResult.riskLevel === 'low' ? 'success' :
            __VLS_ctx.qcResult.riskLevel === 'medium' ? 'warning' : 'error'),
        showIcon: true,
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    const __VLS_100 = {}.ATabs;
    /** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({}));
    const __VLS_102 = __VLS_101({}, ...__VLS_functionalComponentArgsRest(__VLS_101));
    __VLS_103.slots.default;
    const __VLS_104 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        key: "rules",
        tab: "规则结果",
    }));
    const __VLS_106 = __VLS_105({
        key: "rules",
        tab: "规则结果",
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    __VLS_107.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rule-results" },
    });
    const __VLS_108 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        dataSource: (__VLS_ctx.qcResult.ruleResults),
        itemLayout: "vertical",
    }));
    const __VLS_110 = __VLS_109({
        dataSource: (__VLS_ctx.qcResult.ruleResults),
        itemLayout: "vertical",
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    __VLS_111.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_111.slots;
        const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_112 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
        const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        const __VLS_116 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
        const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
        __VLS_119.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_119.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.ruleName);
            (item.ruleCode);
            const __VLS_120 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
                color: (item.isCompliant ? 'green' : 'red'),
                ...{ style: {} },
            }));
            const __VLS_122 = __VLS_121({
                color: (item.isCompliant ? 'green' : 'red'),
                ...{ style: {} },
            }, ...__VLS_functionalComponentArgsRest(__VLS_121));
            __VLS_123.slots.default;
            (item.isCompliant ? '合规' : '不合规');
            var __VLS_123;
        }
        {
            const { description: __VLS_thisSlot } = __VLS_119.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
            (item.score);
            (item.confidence);
            (item.executionTime);
            if (item.findings.length > 0) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
                for (const [finding] of __VLS_getVForSourceType((item.findings))) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                        key: (finding.description),
                    });
                    const __VLS_124 = {}.ATag;
                    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                    // @ts-ignore
                    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
                        color: (finding.severity === 'critical' ? 'red' :
                            finding.severity === 'major' ? 'orange' : 'blue'),
                    }));
                    const __VLS_126 = __VLS_125({
                        color: (finding.severity === 'critical' ? 'red' :
                            finding.severity === 'major' ? 'orange' : 'blue'),
                    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
                    __VLS_127.slots.default;
                    (finding.severity);
                    var __VLS_127;
                    (finding.description);
                    if (finding.recommendation) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                            ...{ style: {} },
                        });
                        (finding.recommendation);
                    }
                }
            }
            if (item.medicalReasoning) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ style: {} },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (item.medicalReasoning);
            }
        }
        var __VLS_119;
        var __VLS_115;
    }
    var __VLS_111;
    var __VLS_107;
    const __VLS_128 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        key: "analysis",
        tab: "交叉分析",
    }));
    const __VLS_130 = __VLS_129({
        key: "analysis",
        tab: "交叉分析",
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    __VLS_131.slots.default;
    if (__VLS_ctx.qcResult.crossRuleAnalysis) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "cross-analysis" },
        });
        const __VLS_132 = {}.ADescriptions;
        /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
            column: (1),
        }));
        const __VLS_134 = __VLS_133({
            column: (1),
        }, ...__VLS_functionalComponentArgsRest(__VLS_133));
        __VLS_135.slots.default;
        const __VLS_136 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
            label: "关联问题",
        }));
        const __VLS_138 = __VLS_137({
            label: "关联问题",
        }, ...__VLS_functionalComponentArgsRest(__VLS_137));
        __VLS_139.slots.default;
        (__VLS_ctx.qcResult.crossRuleAnalysis.correlatedIssues);
        var __VLS_139;
        const __VLS_140 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
            label: "系统性问题",
        }));
        const __VLS_142 = __VLS_141({
            label: "系统性问题",
        }, ...__VLS_functionalComponentArgsRest(__VLS_141));
        __VLS_143.slots.default;
        (__VLS_ctx.qcResult.crossRuleAnalysis.systemicProblems);
        var __VLS_143;
        const __VLS_144 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
            label: "优先建议",
        }));
        const __VLS_146 = __VLS_145({
            label: "优先建议",
        }, ...__VLS_functionalComponentArgsRest(__VLS_145));
        __VLS_147.slots.default;
        (__VLS_ctx.qcResult.crossRuleAnalysis.priorityRecommendations);
        var __VLS_147;
        var __VLS_135;
    }
    var __VLS_131;
    const __VLS_148 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        key: "metrics",
        tab: "性能指标",
    }));
    const __VLS_150 = __VLS_149({
        key: "metrics",
        tab: "性能指标",
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    __VLS_151.slots.default;
    const __VLS_152 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        gutter: (16),
    }));
    const __VLS_154 = __VLS_153({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    const __VLS_156 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        span: (12),
    }));
    const __VLS_158 = __VLS_157({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    const __VLS_160 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        title: "总执行时间",
        value: (__VLS_ctx.qcResult.executionTime),
        suffix: "ms",
    }));
    const __VLS_162 = __VLS_161({
        title: "总执行时间",
        value: (__VLS_ctx.qcResult.executionTime),
        suffix: "ms",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    var __VLS_159;
    const __VLS_164 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        span: (12),
    }));
    const __VLS_166 = __VLS_165({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    const __VLS_168 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        title: "检查规则数",
        value: (__VLS_ctx.qcResult.ruleResults.length),
    }));
    const __VLS_170 = __VLS_169({
        title: "检查规则数",
        value: (__VLS_ctx.qcResult.ruleResults.length),
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    var __VLS_167;
    var __VLS_155;
    var __VLS_151;
    var __VLS_103;
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "no-results" },
    });
    const __VLS_172 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        description: "暂无执行结果，请点击上方按钮开始演示",
    }));
    const __VLS_174 = __VLS_173({
        description: "暂无执行结果，请点击上方按钮开始演示",
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
}
var __VLS_95;
var __VLS_91;
var __VLS_3;
const __VLS_176 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
    title: "执行日志",
    ...{ class: "logs-panel" },
    ...{ style: {} },
}));
const __VLS_178 = __VLS_177({
    title: "执行日志",
    ...{ class: "logs-panel" },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_177));
__VLS_179.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "logs-container" },
});
if (__VLS_ctx.logs.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
        ...{ class: "logs-content" },
    });
    (__VLS_ctx.logs.join('\n'));
}
else {
    const __VLS_180 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        description: "暂无日志",
    }));
    const __VLS_182 = __VLS_181({
        description: "暂无日志",
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
}
var __VLS_179;
/** @type {__VLS_StyleScopedClasses['llm-qc-demo']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-header']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-description']} */ ;
/** @type {__VLS_StyleScopedClasses['control-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['status-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['results-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['qc-results']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-results']} */ ;
/** @type {__VLS_StyleScopedClasses['cross-analysis']} */ ;
/** @type {__VLS_StyleScopedClasses['no-results']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-container']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-content']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            initialized: initialized,
            initializing: initializing,
            analyzing: analyzing,
            managingRules: managingRules,
            runningFullDemo: runningFullDemo,
            qcResult: qcResult,
            logs: logs,
            cacheStats: cacheStats,
            executionMetrics: executionMetrics,
            initializeDemo: initializeDemo,
            runQCDemo: runQCDemo,
            demonstrateRuleManagement: demonstrateRuleManagement,
            runFullDemo: runFullDemo,
            clearLogs: clearLogs,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
