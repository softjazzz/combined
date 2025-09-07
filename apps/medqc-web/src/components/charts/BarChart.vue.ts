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
import core_1 from 'echarts/core';
import charts_1 from 'echarts/charts';
import components_1 from 'echarts/components';
import renderers_1 from 'echarts/renderers';
const vue_echarts_1 = __importDefault(require("vue-echarts"));
// 注册ECharts组件
(0, core_1.use)([
    charts_1.BarChart,
    components_1.TitleComponent,
    components_1.TooltipComponent,
    components_1.LegendComponent,
    components_1.GridComponent,
    renderers_1.CanvasRenderer
]);
const props = withDefaults(defineProps(), { data: () => [],
    title: '部门对比',
    height: '400px',
    type: 'recordCount'
});
const chartOption = (0, vue_1.computed)(() => {
    // 确保 data 是数组
    const dataArray = Array.isArray(props.data) ? props.data : [];
    if (dataArray.length === 0) {
        return {
            title: {
                text: props.title,
                left: 'center'
            },
            graphic: {
                type: 'text',
                left: 'center',
                top: 'middle',
                style: {
                    text: '暂无数据',
                    fontSize: 16,
                    fill: '#999'
                }
            }
        };
    }
    const departments = dataArray.map(item => item.department);
    const colors = dataArray.map(item => item.color);
    let data;
    let unit;
    let yAxisName;
    switch (props.type) {
        case 'recordCount':
            data = dataArray.map(item => item.recordCount);
            unit = '个';
            yAxisName = '病案数量';
            break;
        case 'averageScore':
            data = dataArray.map(item => item.averageScore);
            unit = '分';
            yAxisName = '平均评分';
            break;
        case 'passRate':
            data = dataArray.map(item => item.passRate);
            unit = '%';
            yAxisName = '通过率';
            break;
    }
    return {
        title: {
            text: props.title,
            left: 'center',
            textStyle: {
                fontSize: 16,
                fontWeight: 'bold'
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            },
            formatter: (params: any) => {
                const param = params[0];
                const dataItem = props.data.find(item => item.department === param.name);
                if (!dataItem)
                    return '';
                return `
          <div style="font-weight: bold; margin-bottom: 8px;">${param.name}</div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: ${param.color}; border-radius: 2px; margin-right: 6px;"></span>
            病案数量: ${dataItem.recordCount}个
          </div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: #52c41a; border-radius: 2px; margin-right: 6px;"></span>
            平均评分: ${dataItem.averageScore}分
          </div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: #faad14; border-radius: 2px; margin-right: 6px;"></span>
            通过率: ${dataItem.passRate}%
          </div>
        `;
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '10%',
            top: '15%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: departments,
            axisLabel: {
                fontSize: 11,
                color: '#666',
                rotate: departments.some(d => d.length > 4) ? 45 : 0
            },
            axisLine: {
                lineStyle: {
                    color: '#e8e8e8'
                }
            }
        },
        yAxis: {
            type: 'value',
            name: yAxisName,
            axisLabel: {
                formatter: `{value}${unit}`,
                fontSize: 11,
                color: '#666'
            },
            axisLine: {
                lineStyle: {
                    color: '#e8e8e8'
                }
            },
            splitLine: {
                lineStyle: {
                    color: '#f0f0f0'
                }
            }
        },
        series: [
            {
                name: yAxisName,
                type: 'bar',
                data: data.map((value, index) => ({
                    value,
                    itemStyle: {
                        color: colors[index]
                    }
                })),
                barWidth: '60%',
                itemStyle: {
                    borderRadius: [4, 4, 0, 0]
                },
                label: {
                    show: true,
                    position: 'top',
                    formatter: `{c}${unit}`,
                    fontSize: 11,
                    color: '#666'
                }
            }
        ]
    };
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({ data: () => [],
    title: '部门对比',
    height: '400px',
    type: 'recordCount'
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "chart-container" },
});
const __VLS_0 = {}.VChart;
/** @type {[typeof __VLS_components.VChart, typeof __VLS_components.vChart, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    option: (__VLS_ctx.chartOption),
    ...{ style: ({ width: '100%', height: __VLS_ctx.height }) },
    autoresize: true,
}));
const __VLS_2 = __VLS_1({
    option: (__VLS_ctx.chartOption),
    ...{ style: ({ width: '100%', height: __VLS_ctx.height }) },
    autoresize: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['chart-container']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            VChart: vue_echarts_1.default,
            chartOption: chartOption,
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
