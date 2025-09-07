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
    charts_1.LineChart,
    components_1.TitleComponent,
    components_1.TooltipComponent,
    components_1.LegendComponent,
    components_1.GridComponent,
    components_1.DataZoomComponent,
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
        default: '趋势分析'
    },
    height: {
        type: String,
        default: '400px'
    },
    showDataZoom: {
        type: Boolean,
        default: false
    }
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
    const periods = dataArray.map(item => item.period);
    const recordCounts = dataArray.map(item => item.recordCount);
    const averageScores = dataArray.map(item => item.averageScore);
    const passRates = dataArray.map(item => item.passRate);
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
                type: 'cross',
                label: {
                    backgroundColor: '#6a7985'
                }
            },
            formatter: (params: any) => {
                let result = `<div style="font-weight: bold; margin-bottom: 8px;">${params[0].axisValue}</div>`;
                params.forEach((param: any) => {
                    const value = param.seriesName === '病案数量'
                        ? `${param.value}个`
                        : param.seriesName === '平均评分'
                            ? `${param.value}分`
                            : `${param.value}%`;
                    result += `
            <div style="margin-bottom: 4px;">
              <span style="display: inline-block; width: 10px; height: 10px; background-color: ${param.color}; border-radius: 50%; margin-right: 6px;"></span>
              ${param.seriesName}: ${value}
            </div>
          `;
                });
                return result;
            }
        },
        legend: {
            data: ['病案数量', '平均评分', '通过率'],
            top: 40,
            textStyle: {
                fontSize: 12
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: props.showDataZoom ? '15%' : '8%',
            top: '20%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: periods,
            axisLabel: {
                fontSize: 11,
                color: '#666'
            },
            axisLine: {
                lineStyle: {
                    color: '#e8e8e8'
                }
            }
        },
        yAxis: [
            {
                type: 'value',
                name: '病案数量',
                position: 'left',
                axisLabel: {
                    formatter: '{value}个',
                    fontSize: 11,
                    color: '#666'
                },
                axisLine: {
                    lineStyle: {
                        color: '#1890ff'
                    }
                },
                splitLine: {
                    lineStyle: {
                        color: '#f0f0f0'
                    }
                }
            },
            {
                type: 'value',
                name: '评分/通过率',
                position: 'right',
                axisLabel: {
                    formatter: '{value}',
                    fontSize: 11,
                    color: '#666'
                },
                axisLine: {
                    lineStyle: {
                        color: '#52c41a'
                    }
                },
                splitLine: {
                    show: false
                }
            }
        ],
        series: [
            {
                name: '病案数量',
                type: 'line',
                yAxisIndex: 0,
                data: recordCounts,
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: '#1890ff'
                },
                itemStyle: {
                    color: '#1890ff'
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(24, 144, 255, 0.3)' },
                            { offset: 1, color: 'rgba(24, 144, 255, 0.1)' }
                        ]
                    }
                }
            },
            {
                name: '平均评分',
                type: 'line',
                yAxisIndex: 1,
                data: averageScores,
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: '#52c41a'
                },
                itemStyle: {
                    color: '#52c41a'
                }
            },
            {
                name: '通过率',
                type: 'line',
                yAxisIndex: 1,
                data: passRates,
                smooth: true,
                lineStyle: {
                    width: 3,
                    color: '#faad14'
                },
                itemStyle: {
                    color: '#faad14'
                }
            }
        ],
        dataZoom: props.showDataZoom ? [
            {
                type: 'slider',
                start: 0,
                end: 100,
                height: 20,
                bottom: 20
            }
        ] : undefined
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
            default: '趋势分析'
        },
        height: {
            type: String,
            default: '400px'
        },
        showDataZoom: {
            type: Boolean,
            default: false
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
            default: '趋势分析'
        },
        height: {
            type: String,
            default: '400px'
        },
        showDataZoom: {
            type: Boolean,
            default: false
        }
    },
});
; /* PartiallyEnd: #4569/main.vue */
