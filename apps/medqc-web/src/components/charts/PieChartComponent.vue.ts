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
    charts_1.PieChart,
    components_1.TitleComponent,
    components_1.TooltipComponent,
    components_1.LegendComponent,
    renderers_1.CanvasRenderer
]);
const props = defineProps({
    data: {
        type: Array,
        required: true,
        default: () => []
    },
    title: {
        type: String,
        default: '分布统计'
    },
    height: {
        type: String,
        default: '400px'
    },
    showPercentage: {
        type: Boolean,
        default: true
    },
    radius: {
        type: Array,
        default: () => ['40%', '70%']
    }
});
const chartOption = (0, vue_1.computed)(() => {
    const colors = ['#1890ff', '#52c41a', '#faad14', '#f5222d', '#722ed1', '#13c2c2', '#eb2f96'];
    const seriesData = props.data.map((item, index) => ({
        name: item.name,
        value: item.value,
        itemStyle: {
            color: item.color || colors[index % colors.length]
        }
    }));
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
            trigger: 'item',
            formatter: (params: any) => {
                const percentage = params.percent || 0;
                return `
          <div style="font-weight: bold; margin-bottom: 8px;">${params.name}</div>
          <div style="margin-bottom: 4px;">
            <span style="display: inline-block; width: 10px; height: 10px; background-color: ${params.color}; border-radius: 50%; margin-right: 6px;"></span>
            数量: ${params.value}
          </div>
          <div>
            <span style="display: inline-block; width: 10px; height: 10px; background-color: ${params.color}; border-radius: 50%; margin-right: 6px;"></span>
            占比: ${percentage.toFixed(1)}%
          </div>
        `;
            }
        },
        legend: {
            type: 'scroll',
            orient: 'vertical',
            right: 10,
            top: 'middle',
            textStyle: {
                fontSize: 12
            },
            data: props.data.map(item => item.name)
        },
        series: [
            {
                name: props.title,
                type: 'pie',
                radius: props.radius,
                center: ['40%', '50%'],
                data: seriesData,
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                },
                label: {
                    show: true,
                    position: 'outside',
                    formatter: (params: any) => {
                        if (props.showPercentage) {
                            return `${params.name}\n${params.percent}%`;
                        }
                        return params.name;
                    },
                    fontSize: 11,
                    color: '#666'
                },
                labelLine: {
                    show: true,
                    length: 15,
                    length2: 10,
                    smooth: true
                },
                animationType: 'scale',
                animationEasing: 'elasticOut',
                animationDelay: (idx) => Math.random() * 200
            }
        ]
    };
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
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
    props: {
        data: {
            type: Array,
            required: true,
            default: () => []
        },
        title: {
            type: String,
            default: '分布统计'
        },
        height: {
            type: String,
            default: '400px'
        },
        showPercentage: {
            type: Boolean,
            default: true
        },
        radius: {
            type: Array,
            default: () => ['40%', '70%']
        }
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    props: {
        data: {
            type: Array,
            required: true,
            default: () => []
        },
        title: {
            type: String,
            default: '分布统计'
        },
        height: {
            type: String,
            default: '400px'
        },
        showPercentage: {
            type: Boolean,
            default: true
        },
        radius: {
            type: Array,
            default: () => ['40%', '70%']
        }
    },
});
; /* PartiallyEnd: #4569/main.vue */
