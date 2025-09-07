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
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const props = withDefaults(defineProps(), {
    period: 'month',
    height: 400,
    autoRefresh: false
});
// 响应式数据
const loading = (0, vue_1.ref)(false);
const error = (0, vue_1.ref)('');
const detailDrawerVisible = (0, vue_1.ref)(false);
const selectedDataPoint = (0, vue_1.ref)(null);
// 图表配置
const chartType = (0, vue_1.ref)('line');
const selectedMetric = (0, vue_1.ref)('all');
// 模拟数据
const chartData = (0, vue_1.ref)([
    { date: '2024-01', count: 156, score: 85.2, pass_rate: 92.3 },
    { date: '2024-02', count: 189, score: 87.1, pass_rate: 94.1 },
    { date: '2024-03', count: 234, score: 88.5, pass_rate: 95.2 },
    { date: '2024-04', count: 198, score: 86.8, pass_rate: 93.7 },
    { date: '2024-05', count: 267, score: 89.2, pass_rate: 96.1 },
    { date: '2024-06', count: 301, score: 90.1, pass_rate: 97.2 },
    { date: '2024-07', count: 278, score: 88.9, pass_rate: 95.8 },
    { date: '2024-08', count: 245, score: 87.6, pass_rate: 94.5 },
    { date: '2024-09', count: 289, score: 89.8, pass_rate: 96.7 },
    { date: '2024-10', count: 324, score: 91.2, pass_rate: 98.1 },
    { date: '2024-11', count: 298, score: 90.5, pass_rate: 97.4 },
    { date: '2024-12', count: 312, score: 91.8, pass_rate: 98.6 }
]);
// 计算属性
const maxCount = (0, vue_1.computed)(() => Math.max(...chartData.value.map(item => item.count)));
// 图例数据
const legendItems = (0, vue_1.computed)(() => {
    const latest = chartData.value[chartData.value.length - 1];
    if (!latest)
        return [];
    return [
        { name: '病案数量', value: `${latest.count}`, color: '#1890ff' },
        { name: '平均评分', value: `${latest.score}分`, color: '#52c41a' },
        { name: '通过率', value: `${latest.pass_rate}%`, color: '#faad14' }
    ];
});
// 详情表格配置
const detailColumns = [
    { title: '时间', dataIndex: 'date', key: 'date' },
    { title: '病案数量', dataIndex: 'count', key: 'count' },
    { title: '平均评分', dataIndex: 'score', key: 'score' },
    { title: '通过率(%)', dataIndex: 'pass_rate', key: 'pass_rate' },
    { title: '趋势', key: 'trend' }
];
const detailData = (0, vue_1.computed)(() => {
    return chartData.value.map((item, index) => ({
        ...item,
        trend: index > 0 ?
            ((item.score - chartData.value[index - 1].score) / chartData.value[index - 1].score * 100).toFixed(1) : '0'
    }));
});
// 方法
const getDateRange = () => {
    const first = chartData.value[0]?.date;
    const last = chartData.value[chartData.value.length - 1]?.date;
    return `${first} 至 ${last}`;
};
const getLinePoints = (metric) => {
    const width = 100; // SVG宽度百分比
    const height = 100; // SVG高度
    const points = chartData.value.map((item: any,  index: any) => {
        const x = (index / (chartData.value.length - 1)) * width;
        let y = 0;
        if (metric === 'count') {
            y = height - (item.count / maxCount.value * height);
        }
        else if (metric === 'score') {
            y = height - (item.score / 100 * height);
        }
        else if (metric === 'pass_rate') {
            y = height - (item.pass_rate / 100 * height);
        }
        return `${x},${y}`;
    });
    return points.join(' ');
};
const selectDataPoint = (item) => {
    selectedDataPoint.value = item;
    ant_design_vue_1.message.info(`选中数据点: ${item.date}`);
};
const refreshData = async () => {
    loading.value = true;
    error.value = '';
    try {
        // 模拟API调用
        await new Promise(resolve => setTimeout(resolve, 1000));
        // 模拟数据变化
        chartData.value = chartData.value.map(item => ({
            ...item,
            count: item.count + Math.floor(Math.random() * 20 - 10),
            score: Math.min(100, Math.max(0, item.score + Math.random() * 4 - 2)),
            pass_rate: Math.min(100, Math.max(0, item.pass_rate + Math.random() * 2 - 1))
        }));
        ant_design_vue_1.message.success('数据刷新成功');
    }
    catch (err) {
        error.value = '数据加载失败';
        ant_design_vue_1.message.error('数据刷新失败');
    }
    finally {
        loading.value = false;
    }
};
const exportChart = () => {
    // 简化的导出功能
    const data = chartData.value.map(item => ({
        日期: item.date,
        病案数量: item.count,
        平均评分: item.score,
        通过率: item.pass_rate
    }));
    console.log('导出数据:', data);
    ant_design_vue_1.message.success('图表数据已导出到控制台');
};
const showDetail = () => {
    detailDrawerVisible.value = true;
};
const handleMetricChange = () => {
    // 指标变化处理
};
// 生命周期
(0, vue_1.onMounted)(() => {
    // 初始化
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    period: 'month',
    height: 400,
    autoRefresh: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "qc-trend-chart" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chart-controls mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-4" },
});
const __VLS_0 = {}.ARadioGroup;
/** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    value: (__VLS_ctx.chartType),
    buttonStyle: "solid",
    size: "small",
}));
const __VLS_2 = __VLS_1({
    value: (__VLS_ctx.chartType),
    buttonStyle: "solid",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ARadioButton;
/** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    value: "line",
}));
const __VLS_6 = __VLS_5({
    value: "line",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
var __VLS_7;
const __VLS_8 = {}.ARadioButton;
/** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    value: "bar",
}));
const __VLS_10 = __VLS_9({
    value: "bar",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
var __VLS_11;
const __VLS_12 = {}.ARadioButton;
/** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    value: "area",
}));
const __VLS_14 = __VLS_13({
    value: "area",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
var __VLS_3;
const __VLS_16 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedMetric),
    ...{ style: {} },
    size: "small",
}));
const __VLS_18 = __VLS_17({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedMetric),
    ...{ style: {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onChange: (__VLS_ctx.handleMetricChange)
};
__VLS_19.slots.default;
const __VLS_24 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    value: "all",
}));
const __VLS_26 = __VLS_25({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
var __VLS_27;
const __VLS_28 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    value: "count",
}));
const __VLS_30 = __VLS_29({
    value: "count",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
var __VLS_31;
const __VLS_32 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: "score",
}));
const __VLS_34 = __VLS_33({
    value: "score",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
const __VLS_36 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: "pass_rate",
}));
const __VLS_38 = __VLS_37({
    value: "pass_rate",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
var __VLS_39;
var __VLS_19;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-2" },
});
const __VLS_40 = {}.ATooltip;
/** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    title: "刷新数据",
}));
const __VLS_42 = __VLS_41({
    title: "刷新数据",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
const __VLS_44 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ 'onClick': {} },
    type: "text",
    size: "small",
    icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
    loading: (__VLS_ctx.loading),
}));
const __VLS_46 = __VLS_45({
    ...{ 'onClick': {} },
    type: "text",
    size: "small",
    icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_48;
let __VLS_49;
let __VLS_50;
const __VLS_51 = {
    onClick: (__VLS_ctx.refreshData)
};
var __VLS_47;
var __VLS_43;
const __VLS_52 = {}.ATooltip;
/** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    title: "导出图表",
}));
const __VLS_54 = __VLS_53({
    title: "导出图表",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onClick': {} },
    type: "text",
    size: "small",
    icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
}));
const __VLS_58 = __VLS_57({
    ...{ 'onClick': {} },
    type: "text",
    size: "small",
    icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onClick: (__VLS_ctx.exportChart)
};
var __VLS_59;
var __VLS_55;
const __VLS_64 = {}.ATooltip;
/** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    title: "查看详情",
}));
const __VLS_66 = __VLS_65({
    title: "查看详情",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
const __VLS_68 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    ...{ 'onClick': {} },
    type: "text",
    size: "small",
    icon: (__VLS_ctx.h(__VLS_ctx.EyeOutlined)),
}));
const __VLS_70 = __VLS_69({
    ...{ 'onClick': {} },
    type: "text",
    size: "small",
    icon: (__VLS_ctx.h(__VLS_ctx.EyeOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
let __VLS_72;
let __VLS_73;
let __VLS_74;
const __VLS_75 = {
    onClick: (__VLS_ctx.showDetail)
};
var __VLS_71;
var __VLS_67;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chart-container" },
    ...{ style: ({ height: props.height + 'px' }) },
});
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chart-loading" },
    });
    const __VLS_76 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        size: "large",
    }));
    const __VLS_78 = __VLS_77({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "mt-4 text-gray-500" },
    });
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chart-error" },
    });
    const __VLS_80 = {}.ExclamationCircleOutlined;
    /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        ...{ class: "text-4xl text-red-500 mb-4" },
    }));
    const __VLS_82 = __VLS_81({
        ...{ class: "text-4xl text-red-500 mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-600 mb-4" },
    });
    (__VLS_ctx.error);
    const __VLS_84 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_86 = __VLS_85({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    let __VLS_88;
    let __VLS_89;
    let __VLS_90;
    const __VLS_91 = {
        onClick: (__VLS_ctx.refreshData)
    };
    __VLS_87.slots.default;
    var __VLS_87;
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chart-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chart-display" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chart-header mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-lg font-semibold text-gray-800" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-600" },
    });
    (__VLS_ctx.getDateRange());
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "chart-visualization" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid grid-cols-12 gap-1 mb-4" },
    });
    for (const [item, index] of __VLS_getVForSourceType((__VLS_ctx.chartData))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.loading))
                        return;
                    if (!!(__VLS_ctx.error))
                        return;
                    __VLS_ctx.selectDataPoint(item);
                } },
            key: (index),
            ...{ class: "chart-bar" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "bar-container" },
        });
        if (__VLS_ctx.selectedMetric === 'all' || __VLS_ctx.selectedMetric === 'count') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "bar count-bar" },
                ...{ style: ({
                        height: (item.count / __VLS_ctx.maxCount * 100) + '%',
                        backgroundColor: '#1890ff'
                    }) },
                title: (`${item.date}: ${item.count}个病案`),
            });
        }
        if (__VLS_ctx.selectedMetric === 'all' || __VLS_ctx.selectedMetric === 'score') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "bar score-bar" },
                ...{ style: ({
                        height: (item.score / 100 * 100) + '%',
                        backgroundColor: '#52c41a'
                    }) },
                title: (`${item.date}: ${item.score}分`),
            });
        }
        if (__VLS_ctx.selectedMetric === 'all' || __VLS_ctx.selectedMetric === 'pass_rate') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "bar pass-rate-bar" },
                ...{ style: ({
                        height: (item.pass_rate / 100 * 100) + '%',
                        backgroundColor: '#faad14'
                    }) },
                title: (`${item.date}: ${item.pass_rate}%`),
            });
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "bar-label" },
        });
        (item.date.split('-')[1]);
    }
    if (__VLS_ctx.chartType === 'line') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "trend-lines" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
            width: "100%",
            height: "100",
            ...{ class: "trend-svg" },
        });
        if (__VLS_ctx.selectedMetric === 'all' || __VLS_ctx.selectedMetric === 'count') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.polyline)({
                points: (__VLS_ctx.getLinePoints('count')),
                stroke: "#1890ff",
                'stroke-width': "2",
                fill: "none",
            });
        }
        if (__VLS_ctx.selectedMetric === 'all' || __VLS_ctx.selectedMetric === 'score') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.polyline)({
                points: (__VLS_ctx.getLinePoints('score')),
                stroke: "#52c41a",
                'stroke-width': "2",
                fill: "none",
            });
        }
        if (__VLS_ctx.selectedMetric === 'all' || __VLS_ctx.selectedMetric === 'pass_rate') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.polyline)({
                points: (__VLS_ctx.getLinePoints('pass_rate')),
                stroke: "#faad14",
                'stroke-width': "2",
                fill: "none",
            });
        }
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chart-legend mt-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-wrap gap-4 text-sm" },
});
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.legendItems))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (item.name),
        ...{ class: "flex items-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-3 h-3 rounded-full mr-2" },
        ...{ style: ({ backgroundColor: item.color }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-600" },
    });
    (item.name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "ml-2 font-medium" },
    });
    (item.value);
}
const __VLS_92 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    open: (__VLS_ctx.detailDrawerVisible),
    title: "数据详情",
    placement: "right",
    width: "600",
}));
const __VLS_94 = __VLS_93({
    open: (__VLS_ctx.detailDrawerVisible),
    title: "数据详情",
    placement: "right",
    width: "600",
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "data-detail" },
});
const __VLS_96 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    columns: (__VLS_ctx.detailColumns),
    dataSource: (__VLS_ctx.detailData),
    pagination: (false),
    size: "small",
}));
const __VLS_98 = __VLS_97({
    columns: (__VLS_ctx.detailColumns),
    dataSource: (__VLS_ctx.detailData),
    pagination: (false),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
__VLS_99.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_99.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'trend') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center" },
        });
        const __VLS_100 = ((Number(record.trend) > 0 ? __VLS_ctx.ArrowUpOutlined : __VLS_ctx.ArrowDownOutlined));
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            ...{ class: (Number(record.trend) > 0 ? 'text-green-500' : 'text-red-500') },
            ...{ class: "mr-1" },
        }));
        const __VLS_102 = __VLS_101({
            ...{ class: (Number(record.trend) > 0 ? 'text-green-500' : 'text-red-500') },
            ...{ class: "mr-1" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: (Number(record.trend) > 0 ? 'text-green-500' : 'text-red-500') },
        });
        (Math.abs(Number(record.trend)));
    }
}
var __VLS_99;
var __VLS_95;
/** @type {__VLS_StyleScopedClasses['qc-trend-chart']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-container']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-loading']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-error']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-content']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-display']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-visualization']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-12']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['bar-container']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['count-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['score-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['bar']} */ ;
/** @type {__VLS_StyleScopedClasses['pass-rate-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['bar-label']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-lines']} */ ;
/** @type {__VLS_StyleScopedClasses['trend-svg']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-legend']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['data-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            ArrowUpOutlined: icons_vue_1.ArrowUpOutlined,
            ArrowDownOutlined: icons_vue_1.ArrowDownOutlined,
            loading: loading,
            error: error,
            detailDrawerVisible: detailDrawerVisible,
            chartType: chartType,
            selectedMetric: selectedMetric,
            chartData: chartData,
            maxCount: maxCount,
            legendItems: legendItems,
            detailColumns: detailColumns,
            detailData: detailData,
            getDateRange: getDateRange,
            getLinePoints: getLinePoints,
            selectDataPoint: selectDataPoint,
            refreshData: refreshData,
            exportChart: exportChart,
            showDetail: showDetail,
            handleMetricChange: handleMetricChange,
        };
    },
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
