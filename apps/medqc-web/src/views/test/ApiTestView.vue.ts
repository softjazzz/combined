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
import medicalQcApi_1 from '@/services/medicalQcApi';
// 响应式数据
const systemStatus = (0, vue_1.ref)(null);
const healthStatus = (0, vue_1.ref)(null);
const demoData = (0, vue_1.ref)(null);
const analysisResult = (0, vue_1.ref)(null);
// 加载状态
const statusLoading = (0, vue_1.ref)(false);
const demoLoading = (0, vue_1.ref)(false);
const analysisLoading = (0, vue_1.ref)(false);
// 测试请求数据
const testRequest = (0, vue_1.ref)({
    record_id: 'MR_20241223_001',
    record_text: '',
    rule_ids: ['S3.5.1'],
    max_tokens: 500,
    enable_optimization: true
});
// 表格列定义
const resultColumns = [
    { title: '规则ID', dataIndex: 'rule_id', key: 'rule_id' },
    { title: '规则名称', dataIndex: 'rule_name', key: 'rule_name' },
    { title: '结果', dataIndex: 'result', key: 'result' },
    { title: '置信度', dataIndex: 'confidence', key: 'confidence' },
    { title: '缺陷等级', dataIndex: 'defect_level', key: 'defect_level' },
    { title: '推理过程', dataIndex: 'reasoning', key: 'reasoning' },
];
// 检查系统状态
const checkSystemStatus = async () => {
    statusLoading.value = true;
    try {
        const [status, health] = await Promise.all([
            medicalQcApi_1.medicalQcApi.getSystemStatus(),
            medicalQcApi_1.medicalQcApi.healthCheck()
        ]);
        systemStatus.value = status;
        healthStatus.value = health;
        ant_design_vue_1.message.success('系统状态检查完成');
    }
    catch (error) {
        ant_design_vue_1.message.error('系统状态检查失败');
        console.error(error);
    }
    finally {
        statusLoading.value = false;
    }
};
// 加载演示数据
const loadDemo = async () => {
    demoLoading.value = true;
    try {
        const demo = await medicalQcApi_1.medicalQcApi.getOptimizationDemo();
        demoData.value = demo;
        ant_design_vue_1.message.success('演示数据加载完成');
    }
    catch (error) {
        ant_design_vue_1.message.error('演示数据加载失败');
        console.error(error);
    }
    finally {
        demoLoading.value = false;
    }
};
// 运行质控分析
const runAnalysis = async () => {
    if (!testRequest.value.record_text.trim()) {
        ant_design_vue_1.message.warning('请输入病历内容');
        return;
    }
    analysisLoading.value = true;
    try {
        const result = await medicalQcApi_1.medicalQcApi.analyzeRecord(testRequest.value);
        analysisResult.value = result;
        ant_design_vue_1.message.success('质控分析完成');
    }
    catch (error) {
        ant_design_vue_1.message.error('质控分析失败');
        console.error(error);
    }
    finally {
        analysisLoading.value = false;
    }
};
// 加载示例数据
const loadSampleData = () => {
    testRequest.value = {
        record_id: 'MR_20241223_001',
        record_text: `患者张某，男，45岁，因胸痛3小时入院。
    
主诉：胸痛3小时。

现病史：患者于3小时前无明显诱因出现胸痛，呈压榨性，伴有出汗、恶心，无放射痛。疼痛持续不缓解，遂来我院就诊。

既往史：高血压病史5年，规律服药控制。

体格检查：T 36.5℃，P 88次/分，R 20次/分，BP 150/90mmHg。神志清楚，精神可，心率88次/分，律齐，各瓣膜听诊区未闻及病理性杂音。

辅助检查：心电图示：V1-V4导联ST段抬高。

诊断：急性前壁心肌梗死

治疗：给予阿司匹林、氯吡格雷双抗血小板，阿托伐他汀调脂，美托洛尔控制心率等治疗。`,
        rule_ids: ['S3.5.1', 'S4.13.2b', 'S5.10.1'],
        max_tokens: 500,
        enable_optimization: true
    };
    ant_design_vue_1.message.success('示例数据已加载');
};
// 组件挂载时检查系统状态
(0, vue_1.onMounted)(() => {
    checkSystemStatus();
    loadDemo();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['real-world-impact']} */ ;
/** @type {__VLS_StyleScopedClasses['real-world-impact']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "api-test-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "系统状态",
    ...{ class: "mb-4" },
}));
const __VLS_2 = __VLS_1({
    title: "系统状态",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-grid" },
});
const __VLS_4 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    title: "服务状态",
    value: (__VLS_ctx.systemStatus?.status || '未知'),
    valueStyle: ({ color: __VLS_ctx.systemStatus?.status === 'running' ? '#3f8600' : '#cf1322' }),
}));
const __VLS_6 = __VLS_5({
    title: "服务状态",
    value: (__VLS_ctx.systemStatus?.status || '未知'),
    valueStyle: ({ color: __VLS_ctx.systemStatus?.status === 'running' ? '#3f8600' : '#cf1322' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
const __VLS_8 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    title: "服务版本",
    value: (__VLS_ctx.systemStatus?.version || '未知'),
}));
const __VLS_10 = __VLS_9({
    title: "服务版本",
    value: (__VLS_ctx.systemStatus?.version || '未知'),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
const __VLS_12 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    title: "健康状态",
    value: (__VLS_ctx.healthStatus?.status || '未知'),
    valueStyle: ({ color: __VLS_ctx.healthStatus?.status === 'healthy' ? '#3f8600' : '#cf1322' }),
}));
const __VLS_14 = __VLS_13({
    title: "健康状态",
    value: (__VLS_ctx.healthStatus?.status || '未知'),
    valueStyle: ({ color: __VLS_ctx.healthStatus?.status === 'healthy' ? '#3f8600' : '#cf1322' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.statusLoading),
    ...{ class: "mt-4" },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.statusLoading),
    ...{ class: "mt-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.checkSystemStatus)
};
__VLS_19.slots.default;
var __VLS_19;
var __VLS_3;
const __VLS_24 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    title: "三层漏斗优化演示",
    ...{ class: "mb-4" },
}));
const __VLS_26 = __VLS_25({
    title: "三层漏斗优化演示",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
if (__VLS_ctx.demoData) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "demo-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "optimization-stats" },
    });
    const __VLS_28 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        gutter: (16),
    }));
    const __VLS_30 = __VLS_29({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_31.slots.default;
    const __VLS_32 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        span: (6),
    }));
    const __VLS_34 = __VLS_33({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_35.slots.default;
    const __VLS_36 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        title: "压缩比例",
        value: (__VLS_ctx.demoData.benefits?.average_compression_ratio || '未知'),
    }));
    const __VLS_38 = __VLS_37({
        title: "压缩比例",
        value: (__VLS_ctx.demoData.benefits?.average_compression_ratio || '未知'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    var __VLS_35;
    const __VLS_40 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        span: (6),
    }));
    const __VLS_42 = __VLS_41({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    const __VLS_44 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        title: "Token节省率",
        value: (__VLS_ctx.demoData.benefits?.token_savings_rate || '未知'),
    }));
    const __VLS_46 = __VLS_45({
        title: "Token节省率",
        value: (__VLS_ctx.demoData.benefits?.token_savings_rate || '未知'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    var __VLS_43;
    const __VLS_48 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        span: (6),
    }));
    const __VLS_50 = __VLS_49({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_51.slots.default;
    const __VLS_52 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        title: "成本降低",
        value: (__VLS_ctx.demoData.benefits?.cost_reduction || '未知'),
    }));
    const __VLS_54 = __VLS_53({
        title: "成本降低",
        value: (__VLS_ctx.demoData.benefits?.cost_reduction || '未知'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    var __VLS_51;
    const __VLS_56 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        span: (6),
    }));
    const __VLS_58 = __VLS_57({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    const __VLS_60 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        title: "处理时间减少",
        value: (__VLS_ctx.demoData.benefits?.processing_time_reduction || '未知'),
    }));
    const __VLS_62 = __VLS_61({
        title: "处理时间减少",
        value: (__VLS_ctx.demoData.benefits?.processing_time_reduction || '未知'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    var __VLS_59;
    var __VLS_31;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "workflow-steps mt-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    const __VLS_64 = {}.ASteps;
    /** @type {[typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        direction: "vertical",
        size: "small",
    }));
    const __VLS_66 = __VLS_65({
        direction: "vertical",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    for (const [step, index] of __VLS_getVForSourceType((__VLS_ctx.demoData.workflow))) {
        const __VLS_68 = {}.AStep;
        /** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
            key: (index),
            title: (step),
            status: "finish",
        }));
        const __VLS_70 = __VLS_69({
            key: (index),
            title: (step),
            status: "finish",
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    }
    var __VLS_67;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "real-world-impact mt-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.demoData.real_world_impact?.annual_cost_savings);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.demoData.real_world_impact?.token_usage_reduction);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.demoData.real_world_impact?.accuracy_maintained);
}
const __VLS_72 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.demoLoading),
    ...{ class: "mt-4" },
}));
const __VLS_74 = __VLS_73({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.demoLoading),
    ...{ class: "mt-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
let __VLS_76;
let __VLS_77;
let __VLS_78;
const __VLS_79 = {
    onClick: (__VLS_ctx.loadDemo)
};
__VLS_75.slots.default;
var __VLS_75;
var __VLS_27;
const __VLS_80 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    title: "质控分析测试",
    ...{ class: "mb-4" },
}));
const __VLS_82 = __VLS_81({
    title: "质控分析测试",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
const __VLS_84 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    layout: "vertical",
}));
const __VLS_86 = __VLS_85({
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
const __VLS_88 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    label: "病历ID",
}));
const __VLS_90 = __VLS_89({
    label: "病历ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
const __VLS_92 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    value: (__VLS_ctx.testRequest.record_id),
    placeholder: "例如：MR_20241223_001",
}));
const __VLS_94 = __VLS_93({
    value: (__VLS_ctx.testRequest.record_id),
    placeholder: "例如：MR_20241223_001",
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
var __VLS_91;
const __VLS_96 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    label: "病历内容",
}));
const __VLS_98 = __VLS_97({
    label: "病历内容",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
__VLS_99.slots.default;
const __VLS_100 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    value: (__VLS_ctx.testRequest.record_text),
    rows: (6),
    placeholder: "请输入病历内容进行质控分析...",
}));
const __VLS_102 = __VLS_101({
    value: (__VLS_ctx.testRequest.record_text),
    rows: (6),
    placeholder: "请输入病历内容进行质控分析...",
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
var __VLS_99;
const __VLS_104 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    label: "质控规则",
}));
const __VLS_106 = __VLS_105({
    label: "质控规则",
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
__VLS_107.slots.default;
const __VLS_108 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    value: (__VLS_ctx.testRequest.rule_ids),
    mode: "multiple",
    placeholder: "选择要应用的质控规则",
}));
const __VLS_110 = __VLS_109({
    value: (__VLS_ctx.testRequest.rule_ids),
    mode: "multiple",
    placeholder: "选择要应用的质控规则",
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
const __VLS_112 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    value: "S3.5.1",
}));
const __VLS_114 = __VLS_113({
    value: "S3.5.1",
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
var __VLS_115;
const __VLS_116 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    value: "S4.13.2b",
}));
const __VLS_118 = __VLS_117({
    value: "S4.13.2b",
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
var __VLS_119;
const __VLS_120 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
    value: "S5.10.1",
}));
const __VLS_122 = __VLS_121({
    value: "S5.10.1",
}, ...__VLS_functionalComponentArgsRest(__VLS_121));
__VLS_123.slots.default;
var __VLS_123;
var __VLS_111;
var __VLS_107;
const __VLS_124 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
const __VLS_128 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    checked: (__VLS_ctx.testRequest.enable_optimization),
}));
const __VLS_130 = __VLS_129({
    checked: (__VLS_ctx.testRequest.enable_optimization),
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
var __VLS_131;
var __VLS_127;
const __VLS_132 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({}));
const __VLS_134 = __VLS_133({}, ...__VLS_functionalComponentArgsRest(__VLS_133));
__VLS_135.slots.default;
const __VLS_136 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.analysisLoading),
}));
const __VLS_138 = __VLS_137({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.analysisLoading),
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
let __VLS_140;
let __VLS_141;
let __VLS_142;
const __VLS_143 = {
    onClick: (__VLS_ctx.runAnalysis)
};
__VLS_139.slots.default;
var __VLS_139;
const __VLS_144 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
    ...{ 'onClick': {} },
    ...{ class: "ml-2" },
}));
const __VLS_146 = __VLS_145({
    ...{ 'onClick': {} },
    ...{ class: "ml-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_145));
let __VLS_148;
let __VLS_149;
let __VLS_150;
const __VLS_151 = {
    onClick: (__VLS_ctx.loadSampleData)
};
__VLS_147.slots.default;
var __VLS_147;
var __VLS_135;
var __VLS_87;
if (__VLS_ctx.analysisResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "analysis-result mt-4" },
    });
    const __VLS_152 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({}));
    const __VLS_154 = __VLS_153({}, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    var __VLS_155;
    if (__VLS_ctx.analysisResult.optimization_stats) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "optimization-stats mb-4" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        const __VLS_156 = {}.ARow;
        /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
            gutter: (16),
        }));
        const __VLS_158 = __VLS_157({
            gutter: (16),
        }, ...__VLS_functionalComponentArgsRest(__VLS_157));
        __VLS_159.slots.default;
        const __VLS_160 = {}.ACol;
        /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
        // @ts-ignore
        const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
            span: (8),
        }));
        const __VLS_162 = __VLS_161({
            span: (8),
        }, ...__VLS_functionalComponentArgsRest(__VLS_161));
        __VLS_163.slots.default;
        const __VLS_164 = {}.AStatistic;
        /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
        // @ts-ignore
        const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
            title: "原始Token数",
            value: (__VLS_ctx.analysisResult.optimization_stats.original_tokens),
        }));
        const __VLS_166 = __VLS_165({
            title: "原始Token数",
            value: (__VLS_ctx.analysisResult.optimization_stats.original_tokens),
        }, ...__VLS_functionalComponentArgsRest(__VLS_165));
        var __VLS_163;
        const __VLS_168 = {}.ACol;
        /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
        // @ts-ignore
        const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
            span: (8),
        }));
        const __VLS_170 = __VLS_169({
            span: (8),
        }, ...__VLS_functionalComponentArgsRest(__VLS_169));
        __VLS_171.slots.default;
        const __VLS_172 = {}.AStatistic;
        /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
            title: "优化后Token数",
            value: (__VLS_ctx.analysisResult.optimization_stats.optimized_tokens),
        }));
        const __VLS_174 = __VLS_173({
            title: "优化后Token数",
            value: (__VLS_ctx.analysisResult.optimization_stats.optimized_tokens),
        }, ...__VLS_functionalComponentArgsRest(__VLS_173));
        var __VLS_171;
        const __VLS_176 = {}.ACol;
        /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
            span: (8),
        }));
        const __VLS_178 = __VLS_177({
            span: (8),
        }, ...__VLS_functionalComponentArgsRest(__VLS_177));
        __VLS_179.slots.default;
        const __VLS_180 = {}.AStatistic;
        /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
        // @ts-ignore
        const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
            title: "压缩率",
            value: ((__VLS_ctx.analysisResult.optimization_stats.compression_ratio * 100).toFixed(1)),
            suffix: "%",
        }));
        const __VLS_182 = __VLS_181({
            title: "压缩率",
            value: ((__VLS_ctx.analysisResult.optimization_stats.compression_ratio * 100).toFixed(1)),
            suffix: "%",
        }, ...__VLS_functionalComponentArgsRest(__VLS_181));
        var __VLS_179;
        var __VLS_159;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "qc-results" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    const __VLS_184 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
        dataSource: (__VLS_ctx.analysisResult.rule_results),
        columns: (__VLS_ctx.resultColumns),
        pagination: (false),
        size: "small",
    }));
    const __VLS_186 = __VLS_185({
        dataSource: (__VLS_ctx.analysisResult.rule_results),
        columns: (__VLS_ctx.resultColumns),
        pagination: (false),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "total-stats mt-4" },
    });
    const __VLS_188 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        gutter: (16),
    }));
    const __VLS_190 = __VLS_189({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    __VLS_191.slots.default;
    const __VLS_192 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
        span: (8),
    }));
    const __VLS_194 = __VLS_193({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_193));
    __VLS_195.slots.default;
    const __VLS_196 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
        title: "总处理时间",
        value: (__VLS_ctx.analysisResult.total_processing_time),
        suffix: "秒",
        precision: (2),
    }));
    const __VLS_198 = __VLS_197({
        title: "总处理时间",
        value: (__VLS_ctx.analysisResult.total_processing_time),
        suffix: "秒",
        precision: (2),
    }, ...__VLS_functionalComponentArgsRest(__VLS_197));
    var __VLS_195;
    const __VLS_200 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
        span: (8),
    }));
    const __VLS_202 = __VLS_201({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_201));
    __VLS_203.slots.default;
    const __VLS_204 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        title: "总Token使用",
        value: (__VLS_ctx.analysisResult.total_tokens_used),
    }));
    const __VLS_206 = __VLS_205({
        title: "总Token使用",
        value: (__VLS_ctx.analysisResult.total_tokens_used),
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
    var __VLS_203;
    const __VLS_208 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        span: (8),
    }));
    const __VLS_210 = __VLS_209({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
    __VLS_211.slots.default;
    const __VLS_212 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
        title: "预估成本",
        value: (__VLS_ctx.analysisResult.total_cost_estimate),
        prefix: "$",
        precision: (3),
    }));
    const __VLS_214 = __VLS_213({
        title: "预估成本",
        value: (__VLS_ctx.analysisResult.total_cost_estimate),
        prefix: "$",
        precision: (3),
    }, ...__VLS_functionalComponentArgsRest(__VLS_213));
    var __VLS_211;
    var __VLS_191;
}
var __VLS_83;
/** @type {__VLS_StyleScopedClasses['api-test-container']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['status-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-content']} */ ;
/** @type {__VLS_StyleScopedClasses['optimization-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-steps']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['real-world-impact']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-result']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['optimization-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['qc-results']} */ ;
/** @type {__VLS_StyleScopedClasses['total-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            systemStatus: systemStatus,
            healthStatus: healthStatus,
            demoData: demoData,
            analysisResult: analysisResult,
            statusLoading: statusLoading,
            demoLoading: demoLoading,
            analysisLoading: analysisLoading,
            testRequest: testRequest,
            resultColumns: resultColumns,
            checkSystemStatus: checkSystemStatus,
            loadDemo: loadDemo,
            runAnalysis: runAnalysis,
            loadSampleData: loadSampleData,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
