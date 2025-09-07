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
// 响应式数据
const testing = (0, vue_1.ref)(false);
const showDetailsModal = (0, vue_1.ref)(false);
const selectedResult = (0, vue_1.ref)(null);
// 测试配置
const testConfig = (0, vue_1.reactive)({
    departmentId: '',
    testType: 'rules',
    dataSize: 100
});
// 科室列表
const departments = (0, vue_1.ref)([
    { id: '1', name: '心内科' },
    { id: '2', name: '神经外科' },
    { id: '3', name: '急诊科' },
    { id: '4', name: 'ICU' }
]);
// 测试结果
const testResults = (0, vue_1.ref)(: any[]);
// 测试日志
const testLogs = (0, vue_1.ref)(: any[]);
// 表格列配置
const resultsColumns = [
    { title: '测试ID', dataIndex: 'id', key: 'id', width: 120 },
    { title: '测试类型', dataIndex: 'testType', key: 'testType', width: 120 },
    { title: '科室', dataIndex: 'departmentId', key: 'departmentId', width: 120 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
    { title: '数据量', dataIndex: 'dataSize', key: 'dataSize', width: 100 },
    { title: '耗时', dataIndex: 'duration', key: 'duration', width: 100 },
    { title: '开始时间', dataIndex: 'startTime', key: 'startTime', width: 180 },
    { title: '操作', key: 'actions', width: 150, fixed: 'right' }
];
// 计算属性
const testSummary = (0, vue_1.computed)(() => {
    const total = testResults.value.length;
    const successful = testResults.value.filter(r => r.status === 'success').length;
    const failed = testResults.value.filter(r => r.status === 'failed').length;
    const totalTime = testResults.value.reduce((sum, r) => sum + r.duration, 0);
    return {
        totalTests: total,
        successRate: total > 0 ? Math.round((successful / total) * 100) : 0,
        avgTime: total > 0 ? Math.round(totalTime / total) : 0,
        errorCount: failed
    };
});
// 方法
const runTest = async () => {
    testing.value = true;
    testLogs.value = [];
    try {
        addLog('info', '开始执行测试...');
        addLog('info', `科室: ${getDepartmentName(testConfig.departmentId)}`);
        addLog('info', `测试类型: ${getTestTypeName(testConfig.testType)}`);
        addLog('info', `数据量: ${testConfig.dataSize}`);
        const startTime = new Date();
        // 模拟测试执行
        await simulateTest();
        const endTime = new Date();
        const duration = endTime.getTime() - startTime.getTime();
        // 添加测试结果
        const result = {
            id: `test_${Date.now()}`,
            testType: testConfig.testType,
            departmentId: testConfig.departmentId,
            status: Math.random() > 0.2 ? 'success' : 'failed',
            dataSize: testConfig.dataSize,
            duration,
            startTime: startTime.toLocaleString(),
            endTime: endTime.toLocaleString(),
            details: {
                rulesExecuted: Math.floor(Math.random() * 50) + 10,
                recordsProcessed: testConfig.dataSize,
                defectsFound: Math.floor(Math.random() * 20),
                averageScore: Math.floor(Math.random() * 30) + 70
            },
            error: Math.random() > 0.2 ? null : '模拟测试错误：配置参数不匹配'
        };
        testResults.value.unshift(result);
        addLog('success', `测试完成，耗时: ${duration}ms`);
        ant_design_vue_1.message.success('测试执行完成');
    }
    catch (error) {
        addLog('error', `测试失败: ${error.message}`);
        ant_design_vue_1.message.error('测试执行失败');
    }
    finally {
        testing.value = false;
    }
};
const simulateTest = async () => {
    const steps = [
        '初始化测试环境...',
        '加载科室配置...',
        '准备测试数据...',
        '执行质控规则...',
        '分析测试结果...',
        '生成测试报告...'
    ];
    for (const step of steps) {
        addLog('info', step);
        await new Promise(resolve => setTimeout(resolve, 500));
    }
};
const addLog = (level, message) => {
    testLogs.value.push({
        id: Date.now() + Math.random(),
        level,
        message,
        timestamp: new Date().toLocaleTimeString()
    });
};
const viewDetails = (record) => {
    selectedResult.value = record;
    showDetailsModal.value = true;
};
const retryTest = async (record) => {
    // 重新执行失败的测试
    testConfig.departmentId = record.departmentId;
    testConfig.testType = record.testType;
    testConfig.dataSize = record.dataSize;
    await runTest();
};
const exportResults = () => {
    const data = JSON.stringify(testResults.value, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `test_results_${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    ant_design_vue_1.message.success('测试结果已导出');
};
const clearResults = () => {
    testResults.value = [];
    ant_design_vue_1.message.success('测试结果已清空');
};
const getTestTypeName = (type) => {
    const names = {
        rules: '规则测试',
        sampling: '抽样测试',
        workflow: '工作流测试',
        performance: '性能测试'
    };
    return names[type] || type;
};
const getDepartmentName = (id) => {
    const dept = departments.value.find(d => d.id === id);
    return dept ? dept.name : id;
};
// 生命周期
(0, vue_1.onMounted)(() => {
    // 初始化
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['log-entry']} */ ;
/** @type {__VLS_StyleScopedClasses['log-entry']} */ ;
/** @type {__VLS_StyleScopedClasses['log-entry']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "department-config-test" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-wrapper" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "测试配置",
    ...{ class: "test-config-card" },
}));
const __VLS_2 = __VLS_1({
    title: "测试配置",
    ...{ class: "test-config-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onFinish': {} },
    layout: "inline",
}));
const __VLS_6 = __VLS_5({
    ...{ 'onFinish': {} },
    layout: "inline",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onFinish: (__VLS_ctx.runTest)
};
__VLS_7.slots.default;
const __VLS_12 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    label: "选择科室",
}));
const __VLS_14 = __VLS_13({
    label: "选择科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    value: (__VLS_ctx.testConfig.departmentId),
    placeholder: "请选择科室",
    ...{ style: {} },
}));
const __VLS_18 = __VLS_17({
    value: (__VLS_ctx.testConfig.departmentId),
    placeholder: "请选择科室",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_20 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        key: (dept.id),
        value: (dept.id),
    }));
    const __VLS_22 = __VLS_21({
        key: (dept.id),
        value: (dept.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    (dept.name);
    var __VLS_23;
}
var __VLS_19;
var __VLS_15;
const __VLS_24 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    label: "测试类型",
}));
const __VLS_26 = __VLS_25({
    label: "测试类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    value: (__VLS_ctx.testConfig.testType),
    placeholder: "请选择测试类型",
    ...{ style: {} },
}));
const __VLS_30 = __VLS_29({
    value: (__VLS_ctx.testConfig.testType),
    placeholder: "请选择测试类型",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: "rules",
}));
const __VLS_34 = __VLS_33({
    value: "rules",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
const __VLS_36 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: "sampling",
}));
const __VLS_38 = __VLS_37({
    value: "sampling",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
var __VLS_39;
const __VLS_40 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    value: "workflow",
}));
const __VLS_42 = __VLS_41({
    value: "workflow",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
var __VLS_43;
const __VLS_44 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    value: "performance",
}));
const __VLS_46 = __VLS_45({
    value: "performance",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
var __VLS_47;
var __VLS_31;
var __VLS_27;
const __VLS_48 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    label: "测试数据量",
}));
const __VLS_50 = __VLS_49({
    label: "测试数据量",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    value: (__VLS_ctx.testConfig.dataSize),
    min: (10),
    max: (1000),
    ...{ style: {} },
}));
const __VLS_54 = __VLS_53({
    value: (__VLS_ctx.testConfig.dataSize),
    min: (10),
    max: (1000),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
var __VLS_51;
const __VLS_56 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.testing),
    disabled: (!__VLS_ctx.testConfig.departmentId),
}));
const __VLS_62 = __VLS_61({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.testing),
    disabled: (!__VLS_ctx.testConfig.departmentId),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
var __VLS_63;
var __VLS_59;
var __VLS_7;
var __VLS_3;
if (__VLS_ctx.testResults.length > 0) {
    const __VLS_64 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        title: "测试结果",
        ...{ class: "test-results-card" },
    }));
    const __VLS_66 = __VLS_65({
        title: "测试结果",
        ...{ class: "test-results-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_67.slots;
        const __VLS_68 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({}));
        const __VLS_70 = __VLS_69({}, ...__VLS_functionalComponentArgsRest(__VLS_69));
        __VLS_71.slots.default;
        const __VLS_72 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            ...{ 'onClick': {} },
        }));
        const __VLS_74 = __VLS_73({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        let __VLS_76;
        let __VLS_77;
        let __VLS_78;
        const __VLS_79 = {
            onClick: (__VLS_ctx.exportResults)
        };
        __VLS_75.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_75.slots;
            const __VLS_80 = {}.DownloadOutlined;
            /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
            const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
        }
        var __VLS_75;
        const __VLS_84 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
            ...{ 'onClick': {} },
        }));
        const __VLS_86 = __VLS_85({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_85));
        let __VLS_88;
        let __VLS_89;
        let __VLS_90;
        const __VLS_91 = {
            onClick: (__VLS_ctx.clearResults)
        };
        __VLS_87.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_87.slots;
            const __VLS_92 = {}.ClearOutlined;
            /** @type {[typeof __VLS_components.ClearOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({}));
            const __VLS_94 = __VLS_93({}, ...__VLS_functionalComponentArgsRest(__VLS_93));
        }
        var __VLS_87;
        var __VLS_71;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "results-summary" },
    });
    const __VLS_96 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        gutter: (16),
    }));
    const __VLS_98 = __VLS_97({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    __VLS_99.slots.default;
    const __VLS_100 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        span: (6),
    }));
    const __VLS_102 = __VLS_101({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    __VLS_103.slots.default;
    const __VLS_104 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        title: "测试总数",
        value: (__VLS_ctx.testSummary.totalTests),
        valueStyle: ({ color: '#1890ff' }),
    }));
    const __VLS_106 = __VLS_105({
        title: "测试总数",
        value: (__VLS_ctx.testSummary.totalTests),
        valueStyle: ({ color: '#1890ff' }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    var __VLS_103;
    const __VLS_108 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        span: (6),
    }));
    const __VLS_110 = __VLS_109({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    __VLS_111.slots.default;
    const __VLS_112 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
        title: "成功率",
        value: (__VLS_ctx.testSummary.successRate),
        suffix: "%",
        valueStyle: ({ color: '#3f8600' }),
    }));
    const __VLS_114 = __VLS_113({
        title: "成功率",
        value: (__VLS_ctx.testSummary.successRate),
        suffix: "%",
        valueStyle: ({ color: '#3f8600' }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_113));
    var __VLS_111;
    const __VLS_116 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        span: (6),
    }));
    const __VLS_118 = __VLS_117({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    __VLS_119.slots.default;
    const __VLS_120 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        title: "平均耗时",
        value: (__VLS_ctx.testSummary.avgTime),
        suffix: "ms",
        valueStyle: ({ color: '#cf1322' }),
    }));
    const __VLS_122 = __VLS_121({
        title: "平均耗时",
        value: (__VLS_ctx.testSummary.avgTime),
        suffix: "ms",
        valueStyle: ({ color: '#cf1322' }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
    var __VLS_119;
    const __VLS_124 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
        span: (6),
    }));
    const __VLS_126 = __VLS_125({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
    __VLS_127.slots.default;
    const __VLS_128 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        title: "错误数量",
        value: (__VLS_ctx.testSummary.errorCount),
        valueStyle: ({ color: '#cf1322' }),
    }));
    const __VLS_130 = __VLS_129({
        title: "错误数量",
        value: (__VLS_ctx.testSummary.errorCount),
        valueStyle: ({ color: '#cf1322' }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    var __VLS_127;
    var __VLS_99;
    const __VLS_132 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({}));
    const __VLS_134 = __VLS_133({}, ...__VLS_functionalComponentArgsRest(__VLS_133));
    const __VLS_136 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        columns: (__VLS_ctx.resultsColumns),
        dataSource: (__VLS_ctx.testResults),
        pagination: ({ pageSize: 10 }),
        scroll: ({ x: 1200 }),
    }));
    const __VLS_138 = __VLS_137({
        columns: (__VLS_ctx.resultsColumns),
        dataSource: (__VLS_ctx.testResults),
        pagination: ({ pageSize: 10 }),
        scroll: ({ x: 1200 }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_139.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'status') {
            const __VLS_140 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
                color: (record.status === 'success' ? 'green' : 'red'),
            }));
            const __VLS_142 = __VLS_141({
                color: (record.status === 'success' ? 'green' : 'red'),
            }, ...__VLS_functionalComponentArgsRest(__VLS_141));
            __VLS_143.slots.default;
            (record.status === 'success' ? '成功' : '失败');
            var __VLS_143;
        }
        else if (column.key === 'duration') {
            (record.duration);
        }
        else if (column.key === 'actions') {
            const __VLS_144 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({}));
            const __VLS_146 = __VLS_145({}, ...__VLS_functionalComponentArgsRest(__VLS_145));
            __VLS_147.slots.default;
            const __VLS_148 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_150 = __VLS_149({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_149));
            let __VLS_152;
            let __VLS_153;
            let __VLS_154;
            const __VLS_155 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.testResults.length > 0))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'duration'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.viewDetails(record);
                }
            };
            __VLS_151.slots.default;
            var __VLS_151;
            if (record.status === 'failed') {
                const __VLS_156 = {}.AButton;
                /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
                // @ts-ignore
                const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
                    ...{ 'onClick': {} },
                    type: "link",
                    size: "small",
                }));
                const __VLS_158 = __VLS_157({
                    ...{ 'onClick': {} },
                    type: "link",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_157));
                let __VLS_160;
                let __VLS_161;
                let __VLS_162;
                const __VLS_163 = {
                    onClick: (...[$event]) => {
                        if (!(__VLS_ctx.testResults.length > 0))
                            return;
                        if (!!(column.key === 'status'))
                            return;
                        if (!!(column.key === 'duration'))
                            return;
                        if (!(column.key === 'actions'))
                            return;
                        if (!(record.status === 'failed'))
                            return;
                        __VLS_ctx.retryTest(record);
                    }
                };
                __VLS_159.slots.default;
                var __VLS_159;
            }
            var __VLS_147;
        }
    }
    var __VLS_139;
    var __VLS_67;
}
const __VLS_164 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    open: (__VLS_ctx.showDetailsModal),
    title: "测试详情",
    width: "800px",
    footer: (null),
}));
const __VLS_166 = __VLS_165({
    open: (__VLS_ctx.showDetailsModal),
    title: "测试详情",
    width: "800px",
    footer: (null),
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
__VLS_167.slots.default;
if (__VLS_ctx.selectedResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "test-details" },
    });
    const __VLS_168 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        column: (2),
        bordered: true,
    }));
    const __VLS_170 = __VLS_169({
        column: (2),
        bordered: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    const __VLS_172 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        label: "测试ID",
    }));
    const __VLS_174 = __VLS_173({
        label: "测试ID",
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
    __VLS_175.slots.default;
    (__VLS_ctx.selectedResult.id);
    var __VLS_175;
    const __VLS_176 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
        label: "测试类型",
    }));
    const __VLS_178 = __VLS_177({
        label: "测试类型",
    }, ...__VLS_functionalComponentArgsRest(__VLS_177));
    __VLS_179.slots.default;
    (__VLS_ctx.getTestTypeName(__VLS_ctx.selectedResult.testType));
    var __VLS_179;
    const __VLS_180 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        label: "科室",
    }));
    const __VLS_182 = __VLS_181({
        label: "科室",
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    __VLS_183.slots.default;
    (__VLS_ctx.getDepartmentName(__VLS_ctx.selectedResult.departmentId));
    var __VLS_183;
    const __VLS_184 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
        label: "状态",
    }));
    const __VLS_186 = __VLS_185({
        label: "状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    __VLS_187.slots.default;
    const __VLS_188 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        color: (__VLS_ctx.selectedResult.status === 'success' ? 'green' : 'red'),
    }));
    const __VLS_190 = __VLS_189({
        color: (__VLS_ctx.selectedResult.status === 'success' ? 'green' : 'red'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    __VLS_191.slots.default;
    (__VLS_ctx.selectedResult.status === 'success' ? '成功' : '失败');
    var __VLS_191;
    var __VLS_187;
    const __VLS_192 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
        label: "开始时间",
    }));
    const __VLS_194 = __VLS_193({
        label: "开始时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_193));
    __VLS_195.slots.default;
    (__VLS_ctx.selectedResult.startTime);
    var __VLS_195;
    const __VLS_196 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
        label: "结束时间",
    }));
    const __VLS_198 = __VLS_197({
        label: "结束时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_197));
    __VLS_199.slots.default;
    (__VLS_ctx.selectedResult.endTime);
    var __VLS_199;
    const __VLS_200 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
        label: "耗时",
    }));
    const __VLS_202 = __VLS_201({
        label: "耗时",
    }, ...__VLS_functionalComponentArgsRest(__VLS_201));
    __VLS_203.slots.default;
    (__VLS_ctx.selectedResult.duration);
    var __VLS_203;
    const __VLS_204 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        label: "数据量",
    }));
    const __VLS_206 = __VLS_205({
        label: "数据量",
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
    __VLS_207.slots.default;
    (__VLS_ctx.selectedResult.dataSize);
    var __VLS_207;
    var __VLS_171;
    const __VLS_208 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({}));
    const __VLS_210 = __VLS_209({}, ...__VLS_functionalComponentArgsRest(__VLS_209));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    const __VLS_212 = {}.ATextarea;
    /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
        value: (JSON.stringify(__VLS_ctx.selectedResult.details, null, 2)),
        rows: (10),
        readonly: true,
    }));
    const __VLS_214 = __VLS_213({
        value: (JSON.stringify(__VLS_ctx.selectedResult.details, null, 2)),
        rows: (10),
        readonly: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_213));
    if (__VLS_ctx.selectedResult.status === 'failed') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "error-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        const __VLS_216 = {}.AAlert;
        /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
        // @ts-ignore
        const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
            message: (__VLS_ctx.selectedResult.error),
            type: "error",
            showIcon: true,
        }));
        const __VLS_218 = __VLS_217({
            message: (__VLS_ctx.selectedResult.error),
            type: "error",
            showIcon: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_217));
    }
}
var __VLS_167;
if (__VLS_ctx.testing) {
    const __VLS_220 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
        title: "实时测试日志",
        ...{ class: "test-logs-card" },
    }));
    const __VLS_222 = __VLS_221({
        title: "实时测试日志",
        ...{ class: "test-logs-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_221));
    __VLS_223.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "logs-container" },
    });
    for (const [log] of __VLS_getVForSourceType((__VLS_ctx.testLogs))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (log.id),
            ...{ class: "log-entry" },
            ...{ class: (log.level) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "log-time" },
        });
        (log.timestamp);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "log-message" },
        });
        (log.message);
    }
    var __VLS_223;
}
/** @type {__VLS_StyleScopedClasses['department-config-test']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['content-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['test-config-card']} */ ;
/** @type {__VLS_StyleScopedClasses['test-results-card']} */ ;
/** @type {__VLS_StyleScopedClasses['results-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['test-details']} */ ;
/** @type {__VLS_StyleScopedClasses['error-section']} */ ;
/** @type {__VLS_StyleScopedClasses['test-logs-card']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-container']} */ ;
/** @type {__VLS_StyleScopedClasses['log-entry']} */ ;
/** @type {__VLS_StyleScopedClasses['log-time']} */ ;
/** @type {__VLS_StyleScopedClasses['log-message']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            ClearOutlined: icons_vue_1.ClearOutlined,
            testing: testing,
            showDetailsModal: showDetailsModal,
            selectedResult: selectedResult,
            testConfig: testConfig,
            departments: departments,
            testResults: testResults,
            testLogs: testLogs,
            resultsColumns: resultsColumns,
            testSummary: testSummary,
            runTest: runTest,
            viewDetails: viewDetails,
            retryTest: retryTest,
            exportResults: exportResults,
            clearResults: clearResults,
            getTestTypeName: getTestTypeName,
            getDepartmentName: getDepartmentName,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
