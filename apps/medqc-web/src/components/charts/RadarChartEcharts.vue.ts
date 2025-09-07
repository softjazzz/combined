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
import renderers_1 from 'echarts/renderers';
import charts_1 from 'echarts/charts';
import components_1 from 'echarts/components';
const vue_echarts_1 = __importDefault(require("vue-echarts"));
// 注册必要的组件
(0, core_1.use)([
    renderers_1.CanvasRenderer,
    charts_1.RadarChart,
    components_1.TitleComponent,
    components_1.TooltipComponent,
    components_1.LegendComponent,
    components_1.GridComponent
]);
const props = withDefaults(defineProps(), {
    width: 400,
    height: 400,
    title: '',
    showLegend: true,
    theme: 'light'
});
// 计算图表配置
const chartOption = (0, vue_1.computed)(() => {
    const isDark = props.theme === 'dark';
    return {
        title: props.title ? {
            text: props.title,
            left: 'center',
            textStyle: {
                color: isDark ? '#fff' : '#333',
                fontSize: 16,
                fontWeight: 'bold'
            }
        } : undefined,
        tooltip: {
            trigger: 'item',
            formatter: (params: any) => {
                const { name, value } = params;
                let content = `<div style="font-weight: bold; margin-bottom: 8px;">${name}</div>`;
                value.forEach((val: any,  index: any) => {
                    const indicator = props.indicators[index];
                    content += `<div style="margin: 4px 0;">
            <span style="color: ${params.color};">●</span> 
            ${indicator.name}: ${val}
          </div>`;
                });
                return content;
            },
            backgroundColor: isDark ? 'rgba(0, 0, 0, 0.8)' : 'rgba(255, 255, 255, 0.9)',
            borderColor: isDark ? '#333' : '#ddd',
            textStyle: {
                color: isDark ? '#fff' : '#333'
            }
        },
        legend: props.showLegend ? {
            bottom: 20,
            data: props.data.map(item => item.name),
            textStyle: {
                color: isDark ? '#fff' : '#333'
            }
        } : undefined,
        radar: {
            indicator: props.indicators.map(indicator => ({
                name: indicator.name,
                max: indicator.max,
                min: indicator.min || 0
            })),
            radius: '65%',
            center: ['50%', '50%'],
            splitNumber: 5,
            name: {
                textStyle: {
                    color: isDark ? '#fff' : '#333',
                    fontSize: 12
                }
            },
            splitLine: {
                lineStyle: {
                    color: isDark ? '#333' : '#e0e0e0'
                }
            },
            splitArea: {
                show: true,
                areaStyle: {
                    color: isDark
                        ? ['rgba(255, 255, 255, 0.02)', 'rgba(255, 255, 255, 0.05)']
                        : ['rgba(0, 0, 0, 0.02)', 'rgba(0, 0, 0, 0.05)']
                }
            },
            axisLine: {
                lineStyle: {
                    color: isDark ? '#333' : '#e0e0e0'
                }
            }
        },
        series: [{
                type: 'radar',
                data: props.data.map(item => ({
                    name: item.name,
                    value: item.value,
                    itemStyle: {
                        color: item.color || '#1890ff'
                    },
                    lineStyle: {
                        color: item.color || '#1890ff',
                        width: 2
                    },
                    areaStyle: {
                        color: item.color || '#1890ff',
                        opacity: 0.1
                    }
                }))
            }]
    };
});
// 监听数据变化
(0, vue_1.watch)(() => props.data, () => {
    // 数据更新时会自动重新渲染
}, { deep: true });
// 暴露组件实例方法
const __VLS_exposed = {
    // 可以暴露一些方法供父组件调用
    refresh: () => {
        // 刷新图表
    }
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    width: 400,
    height: 400,
    title: '',
    showLegend: true,
    theme: 'light'
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['radar-chart-container']} */ ;
/** @type {__VLS_StyleScopedClasses['radar-chart-container']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "radar-chart-container" },
});
const __VLS_0 = {}.VChart;
/** @type {[typeof __VLS_components.VChart, typeof __VLS_components.vChart, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    option: (__VLS_ctx.chartOption),
    ...{ style: ({ width: __VLS_ctx.width + 'px', height: __VLS_ctx.height + 'px' }) },
    autoresize: true,
}));
const __VLS_2 = __VLS_1({
    option: (__VLS_ctx.chartOption),
    ...{ style: ({ width: __VLS_ctx.width + 'px', height: __VLS_ctx.height + 'px' }) },
    autoresize: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
/** @type {__VLS_StyleScopedClasses['radar-chart-container']} */ ;
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
        return {
            ...__VLS_exposed,
        };
    },
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
