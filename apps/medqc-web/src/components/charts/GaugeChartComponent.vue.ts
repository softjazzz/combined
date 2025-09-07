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
    charts_1.GaugeChart,
    components_1.TitleComponent,
    components_1.TooltipComponent,
    renderers_1.CanvasRenderer
]);
const props = defineProps({
    value: {
        type: Number,
        required: true,
        default: 0
    },
    title: {
        type: String,
        default: '评分'
    },
    height: {
        type: String,
        default: '300px'
    },
    max: {
        type: Number,
        default: 100
    },
    unit: {
        type: String,
        default: '分'
    }
});
const chartOption = (0, vue_1.computed)(() => {
    // 根据分数确定颜色
    const getColor = (value) => {
        if (value >= 90)
            return '#52c41a';
        if (value >= 80)
            return '#faad14';
        if (value >= 60)
            return '#ff7875';
        return '#ff4d4f';
    };
    const color = getColor(props.value);
    return {
        title: {
            text: props.title,
            left: 'center',
            top: '10%',
            textStyle: {
                fontSize: 16,
                fontWeight: 'bold'
            }
        },
        tooltip: {
            formatter: `{a} <br/>{b} : {c}${props.unit}`
        },
        series: [
            {
                name: props.title,
                type: 'gauge',
                center: ['50%', '60%'],
                radius: '80%',
                min: 0,
                max: props.max,
                splitNumber: 5,
                axisLine: {
                    lineStyle: {
                        width: 20,
                        color: [
                            [0.6, '#ff4d4f'],
                            [0.8, '#ff7875'],
                            [0.9, '#faad14'],
                            [1, '#52c41a']
                        ]
                    }
                },
                pointer: {
                    itemStyle: {
                        color: color
                    }
                },
                axisTick: {
                    distance: -20,
                    length: 8,
                    lineStyle: {
                        color: '#fff',
                        width: 2
                    }
                },
                splitLine: {
                    distance: -20,
                    length: 20,
                    lineStyle: {
                        color: '#fff',
                        width: 4
                    }
                },
                axisLabel: {
                    color: '#666',
                    fontSize: 12,
                    distance: -40,
                    formatter: (value: any) => {
                        return value.toString();
                    }
                },
                detail: {
                    valueAnimation: true,
                    formatter: `{value}${props.unit}`,
                    color: color,
                    fontSize: 28,
                    fontWeight: 'bold',
                    offsetCenter: [0, '20%']
                },
                data: [
                    {
                        value: props.value,
                        name: props.title
                    }
                ]
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
        value: {
            type: Number,
            required: true,
            default: 0
        },
        title: {
            type: String,
            default: '评分'
        },
        height: {
            type: String,
            default: '300px'
        },
        max: {
            type: Number,
            default: 100
        },
        unit: {
            type: String,
            default: '分'
        }
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    props: {
        value: {
            type: Number,
            required: true,
            default: 0
        },
        title: {
            type: String,
            default: '评分'
        },
        height: {
            type: String,
            default: '300px'
        },
        max: {
            type: Number,
            default: 100
        },
        unit: {
            type: String,
            default: '分'
        }
    },
});
; /* PartiallyEnd: #4569/main.vue */
