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
import icons_vue_1 from '@ant-design/icons-vue';
import ant_design_vue_1 from 'ant-design-vue';
import error_handler_1 from '@/lib/error-handler';
import api_fallback_1 from '@/lib/api-fallback';
import qc_analysis_optimized_1 from '@/lib/qc-analysis-optimized';
import date_1 from '@/utils/date';
// 响应式数据
const loading = (0, vue_1.ref)(false);
const autoRefresh = (0, vue_1.ref)(true);
const refreshTimer = (0, vue_1.ref)(null);
// 系统状态数据
const systemStatus = (0, vue_1.ref)('正常');
const performanceStats = (0, vue_1.ref)({
    averageResponseTime: 0,
    cacheHitRate: 0,
    totalRequests: 0
});
const errorStats = (0, vue_1.ref)({
    totalErrors: 0,
    errorRate: 0,
    errorsByType: {},
    errorsBySeverity: {}
});
const serviceHealth = (0, vue_1.ref)(: any[]);
const recentErrors = (0, vue_1.ref)(: any[]);
// 图表相关
const responseTimeChart = (0, vue_1.ref)();
const errorChart = (0, vue_1.ref)();
// 错误详情
const showErrorModal = (0, vue_1.ref)(false);
const selectedError = (0, vue_1.ref)(null);
// 表格列定义
const errorColumns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 180 },
    { title: '类型', dataIndex: 'type', key: 'type', width: 120 },
    { title: '严重程度', dataIndex: 'severity', key: 'severity', width: 100 },
    { title: '消息', dataIndex: 'message', key: 'message', ellipsis: true },
    { title: '操作', key: 'actions', width: 80 }
];
// 方法
const refreshData = async () => {
    loading.value = true;
    try {
        // 获取性能统计
        const perfStats = qc_analysis_optimized_1.optimizedQCAnalysisService.getPerformanceStats();
        performanceStats.value = {
            averageResponseTime: perfStats.optimizer.averageResponseTime,
            cacheHitRate: perfStats.optimizer.cacheHitRate,
            totalRequests: perfStats.optimizer.totalRequests
        };
        // 获取错误统计
        const errStats = error_handler_1.globalErrorHandler.getStats();
        errorStats.value = {
            totalErrors: errStats.totalErrors,
            errorRate: errStats.totalErrors > 0 ? errStats.totalErrors / (errStats.totalErrors + performanceStats.value.totalRequests) : 0,
            errorsByType: errStats.errorsByType,
            errorsBySeverity: errStats.errorsBySeverity
        };
        // 获取服务健康状态
        const healthMap = api_fallback_1.apiFallbackManager.getServiceHealth();
        serviceHealth.value = Array.from(healthMap.values()).map(health => ({
            name: getServiceDisplayName(health.service),
            status: health.status,
            responseTime: health.responseTime,
            lastCheck: health.lastCheck,
            error: health.error
        }));
        // 获取最近错误
        recentErrors.value = errStats.recentErrors.slice(0, 20).map((error, index) => ({
            key: index,
            ...error
        }));
        // 更新系统状态
        updateSystemStatus();
        console.log('📊 系统监控数据已更新');
    }
    catch (error) {
        console.error('获取监控数据失败:', error);
        ant_design_vue_1.message.error('获取监控数据失败');
    }
    finally {
        loading.value = false;
    }
};
const updateSystemStatus = () => {
    const hasUnhealthyServices = serviceHealth.value.some(s => s.status !== 'healthy');
    const highErrorRate = errorStats.value.errorRate > 0.1;
    const slowResponse = performanceStats.value.averageResponseTime > 5000;
    if (hasUnhealthyServices || highErrorRate || slowResponse) {
        systemStatus.value = '异常';
    }
    else {
        systemStatus.value = '正常';
    }
};
const getServiceDisplayName = (serviceName) => {
    const nameMap = {
        'deepseek-api': 'AI分析服务',
        'supabase-db': '数据库服务',
        'file-storage': '文件存储服务'
    };
    return nameMap[serviceName] || serviceName;
};
const getServiceStatusColor = (status) => {
    const colorMap = {
        healthy: 'green',
        degraded: 'orange',
        unavailable: 'red'
    };
    return colorMap[status] || 'default';
};
const getServiceStatusText = (status) => {
    const textMap = {
        healthy: '正常',
        degraded: '降级',
        unavailable: '不可用'
    };
    return textMap[status] || status;
};
const getErrorSeverityColor = (severity) => {
    const colorMap = {
        critical: 'red',
        high: 'orange',
        medium: 'gold',
        low: 'blue'
    };
    return colorMap[severity] || 'default';
};
const formatTime = (timestamp) => {
    if (!timestamp)
        return '未知';
    const now = Date.now();
    const diff = now - timestamp;
    if (diff < 60000)
        return '刚刚';
    if (diff < 3600000)
        return `${Math.floor(diff / 60000)}分钟前`;
    if (diff < 86400000)
        return `${Math.floor(diff / 3600000)}小时前`;
    return `${Math.floor(diff / 86400000)}天前`;
};
const viewErrorDetails = (error) => {
    selectedError.value = error;
    showErrorModal.value = true;
};
const startAutoRefresh = () => {
    if (refreshTimer.value) {
        clearInterval(refreshTimer.value);
    }
    if (autoRefresh.value) {
        refreshTimer.value = setInterval(() => {
            refreshData();
        }, 30000); // 每30秒刷新一次
    }
};
// 生命周期
(0, vue_1.onMounted)(() => {
    refreshData();
    startAutoRefresh();
});
(0, vue_1.onUnmounted)(() => {
    if (refreshTimer.value) {
        clearInterval(refreshTimer.value);
    }
});
// 监听自动刷新开关
watch(() => autoRefresh.value, () => {
    startAutoRefresh();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['monitor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['system-monitor']} */ ;
/** @type {__VLS_StyleScopedClasses['monitor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['monitor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['service-metrics']} */ ;
/** @type {__VLS_StyleScopedClasses['metric']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "system-monitor" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "monitor-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-actions" },
});
const __VLS_0 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onClick: (__VLS_ctx.refreshData)
};
__VLS_3.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
    const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
const __VLS_12 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    checked: (__VLS_ctx.autoRefresh),
    checkedChildren: "自动刷新",
    unCheckedChildren: "手动刷新",
}));
const __VLS_14 = __VLS_13({
    checked: (__VLS_ctx.autoRefresh),
    checkedChildren: "自动刷新",
    unCheckedChildren: "手动刷新",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-section" },
});
const __VLS_16 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    gutter: ([16, 16]),
}));
const __VLS_18 = __VLS_17({
    gutter: ([16, 16]),
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
const __VLS_20 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    xs: (24),
    sm: (12),
    md: (6),
}));
const __VLS_22 = __VLS_21({
    xs: (24),
    sm: (12),
    md: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
const __VLS_24 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ class: "metric-card" },
}));
const __VLS_26 = __VLS_25({
    ...{ class: "metric-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    title: "系统状态",
    value: (__VLS_ctx.systemStatus),
    valueStyle: ({ color: __VLS_ctx.systemStatus === '正常' ? '#3f8600' : '#cf1322' }),
}));
const __VLS_30 = __VLS_29({
    title: "系统状态",
    value: (__VLS_ctx.systemStatus),
    valueStyle: ({ color: __VLS_ctx.systemStatus === '正常' ? '#3f8600' : '#cf1322' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_31.slots;
    const __VLS_32 = ((__VLS_ctx.systemStatus === '正常' ? __VLS_ctx.CheckCircleOutlined : __VLS_ctx.ExclamationCircleOutlined));
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
    const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
}
var __VLS_31;
var __VLS_27;
var __VLS_23;
const __VLS_36 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    xs: (24),
    sm: (12),
    md: (6),
}));
const __VLS_38 = __VLS_37({
    xs: (24),
    sm: (12),
    md: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
const __VLS_40 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ class: "metric-card" },
}));
const __VLS_42 = __VLS_41({
    ...{ class: "metric-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
const __VLS_44 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    title: "平均响应时间",
    value: (__VLS_ctx.performanceStats.averageResponseTime),
    suffix: "ms",
    valueStyle: ({ color: __VLS_ctx.performanceStats.averageResponseTime < 2000 ? '#3f8600' : '#faad14' }),
}));
const __VLS_46 = __VLS_45({
    title: "平均响应时间",
    value: (__VLS_ctx.performanceStats.averageResponseTime),
    suffix: "ms",
    valueStyle: ({ color: __VLS_ctx.performanceStats.averageResponseTime < 2000 ? '#3f8600' : '#faad14' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_47.slots;
    const __VLS_48 = {}.ClockCircleOutlined;
    /** @type {[typeof __VLS_components.ClockCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
    const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
}
var __VLS_47;
var __VLS_43;
var __VLS_39;
const __VLS_52 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    xs: (24),
    sm: (12),
    md: (6),
}));
const __VLS_54 = __VLS_53({
    xs: (24),
    sm: (12),
    md: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ class: "metric-card" },
}));
const __VLS_58 = __VLS_57({
    ...{ class: "metric-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    title: "缓存命中率",
    value: (__VLS_ctx.performanceStats.cacheHitRate * 100),
    suffix: "%",
    precision: (1),
    valueStyle: ({ color: __VLS_ctx.performanceStats.cacheHitRate > 0.7 ? '#3f8600' : '#faad14' }),
}));
const __VLS_62 = __VLS_61({
    title: "缓存命中率",
    value: (__VLS_ctx.performanceStats.cacheHitRate * 100),
    suffix: "%",
    precision: (1),
    valueStyle: ({ color: __VLS_ctx.performanceStats.cacheHitRate > 0.7 ? '#3f8600' : '#faad14' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_63.slots;
    const __VLS_64 = {}.DatabaseOutlined;
    /** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({}));
    const __VLS_66 = __VLS_65({}, ...__VLS_functionalComponentArgsRest(__VLS_65));
}
var __VLS_63;
var __VLS_59;
var __VLS_55;
const __VLS_68 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    xs: (24),
    sm: (12),
    md: (6),
}));
const __VLS_70 = __VLS_69({
    xs: (24),
    sm: (12),
    md: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    ...{ class: "metric-card" },
}));
const __VLS_74 = __VLS_73({
    ...{ class: "metric-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
const __VLS_76 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    title: "错误率",
    value: (__VLS_ctx.errorStats.errorRate * 100),
    suffix: "%",
    precision: (2),
    valueStyle: ({ color: __VLS_ctx.errorStats.errorRate < 0.05 ? '#3f8600' : '#cf1322' }),
}));
const __VLS_78 = __VLS_77({
    title: "错误率",
    value: (__VLS_ctx.errorStats.errorRate * 100),
    suffix: "%",
    precision: (2),
    valueStyle: ({ color: __VLS_ctx.errorStats.errorRate < 0.05 ? '#3f8600' : '#cf1322' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_79.slots;
    const __VLS_80 = {}.WarningOutlined;
    /** @type {[typeof __VLS_components.WarningOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
    const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
}
var __VLS_79;
var __VLS_75;
var __VLS_71;
var __VLS_19;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "services-section" },
});
const __VLS_84 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    title: "服务健康状态",
    ...{ class: "section-card" },
}));
const __VLS_86 = __VLS_85({
    title: "服务健康状态",
    ...{ class: "section-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
const __VLS_88 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    gutter: ([16, 16]),
}));
const __VLS_90 = __VLS_89({
    gutter: ([16, 16]),
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
for (const [service] of __VLS_getVForSourceType((__VLS_ctx.serviceHealth))) {
    const __VLS_92 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        key: (service.name),
        xs: (24),
        sm: (12),
        lg: (8),
    }));
    const __VLS_94 = __VLS_93({
        key: (service.name),
        xs: (24),
        sm: (12),
        lg: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    __VLS_95.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "service-item" },
        ...{ class: (`service-${service.status}`) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "service-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "service-name" },
    });
    (service.name);
    const __VLS_96 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        color: (__VLS_ctx.getServiceStatusColor(service.status)),
    }));
    const __VLS_98 = __VLS_97({
        color: (__VLS_ctx.getServiceStatusColor(service.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    __VLS_99.slots.default;
    (__VLS_ctx.getServiceStatusText(service.status));
    var __VLS_99;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "service-metrics" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "metric" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "metric-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "metric-value" },
    });
    (service.responseTime);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "metric" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "metric-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "metric-value" },
    });
    (__VLS_ctx.formatTime(service.lastCheck));
    if (service.error) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "service-error" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "error-label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "error-message" },
        });
        (service.error);
    }
    var __VLS_95;
}
var __VLS_91;
var __VLS_87;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "charts-section" },
});
const __VLS_100 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    gutter: ([16, 16]),
}));
const __VLS_102 = __VLS_101({
    gutter: ([16, 16]),
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
__VLS_103.slots.default;
const __VLS_104 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    xs: (24),
    lg: (12),
}));
const __VLS_106 = __VLS_105({
    xs: (24),
    lg: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
__VLS_107.slots.default;
const __VLS_108 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    title: "响应时间趋势",
    ...{ class: "chart-card" },
}));
const __VLS_110 = __VLS_109({
    title: "响应时间趋势",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "responseTimeChart",
    ...{ class: "chart-container" },
});
/** @type {typeof __VLS_ctx.responseTimeChart} */ ;
var __VLS_111;
var __VLS_107;
const __VLS_112 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    xs: (24),
    lg: (12),
}));
const __VLS_114 = __VLS_113({
    xs: (24),
    lg: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
const __VLS_116 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    title: "错误统计",
    ...{ class: "chart-card" },
}));
const __VLS_118 = __VLS_117({
    title: "错误统计",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "errorChart",
    ...{ class: "chart-container" },
});
/** @type {typeof __VLS_ctx.errorChart} */ ;
var __VLS_119;
var __VLS_115;
var __VLS_103;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "errors-section" },
});
const __VLS_120 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
    title: "最近错误",
    ...{ class: "section-card" },
}));
const __VLS_122 = __VLS_121({
    title: "最近错误",
    ...{ class: "section-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_121));
__VLS_123.slots.default;
const __VLS_124 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    columns: (__VLS_ctx.errorColumns),
    dataSource: (__VLS_ctx.recentErrors),
    pagination: ({ pageSize: 10 }),
    size: "small",
}));
const __VLS_126 = __VLS_125({
    columns: (__VLS_ctx.errorColumns),
    dataSource: (__VLS_ctx.recentErrors),
    pagination: ({ pageSize: 10 }),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_127.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'severity') {
        const __VLS_128 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
            color: (__VLS_ctx.getErrorSeverityColor(record.severity)),
        }));
        const __VLS_130 = __VLS_129({
            color: (__VLS_ctx.getErrorSeverityColor(record.severity)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_129));
        __VLS_131.slots.default;
        (record.severity);
        var __VLS_131;
    }
    else if (column.key === 'timestamp') {
        (__VLS_ctx.formatDateTime(record.timestamp));
    }
    else if (column.key === 'actions') {
        const __VLS_132 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_134 = __VLS_133({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_133));
        let __VLS_136;
        let __VLS_137;
        let __VLS_138;
        const __VLS_139 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'severity'))
                    return;
                if (!!(column.key === 'timestamp'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.viewErrorDetails(record);
            }
        };
        __VLS_135.slots.default;
        var __VLS_135;
    }
}
var __VLS_127;
var __VLS_123;
const __VLS_140 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    open: (__VLS_ctx.showErrorModal),
    title: "错误详情",
    width: (800),
    footer: (null),
}));
const __VLS_142 = __VLS_141({
    open: (__VLS_ctx.showErrorModal),
    title: "错误详情",
    width: (800),
    footer: (null),
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
__VLS_143.slots.default;
if (__VLS_ctx.selectedError) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-details" },
    });
    const __VLS_144 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        column: (1),
        bordered: true,
    }));
    const __VLS_146 = __VLS_145({
        column: (1),
        bordered: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    __VLS_147.slots.default;
    const __VLS_148 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        label: "错误类型",
    }));
    const __VLS_150 = __VLS_149({
        label: "错误类型",
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    __VLS_151.slots.default;
    const __VLS_152 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        color: (__VLS_ctx.getErrorSeverityColor(__VLS_ctx.selectedError.severity)),
    }));
    const __VLS_154 = __VLS_153({
        color: (__VLS_ctx.getErrorSeverityColor(__VLS_ctx.selectedError.severity)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    (__VLS_ctx.selectedError.type);
    var __VLS_155;
    var __VLS_151;
    const __VLS_156 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        label: "严重程度",
    }));
    const __VLS_158 = __VLS_157({
        label: "严重程度",
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    (__VLS_ctx.selectedError.severity);
    var __VLS_159;
    const __VLS_160 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        label: "错误消息",
    }));
    const __VLS_162 = __VLS_161({
        label: "错误消息",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    __VLS_163.slots.default;
    (__VLS_ctx.selectedError.message);
    var __VLS_163;
    const __VLS_164 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        label: "用户消息",
    }));
    const __VLS_166 = __VLS_165({
        label: "用户消息",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    (__VLS_ctx.selectedError.userMessage);
    var __VLS_167;
    const __VLS_168 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        label: "发生时间",
    }));
    const __VLS_170 = __VLS_169({
        label: "发生时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    (__VLS_ctx.formatDateTime(__VLS_ctx.selectedError.timestamp));
    var __VLS_171;
    const __VLS_172 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        label: "页面URL",
    }));
    const __VLS_174 = __VLS_173({
        label: "页面URL",
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
    __VLS_175.slots.default;
    (__VLS_ctx.selectedError.url);
    var __VLS_175;
    if (__VLS_ctx.selectedError.stack) {
        const __VLS_176 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
            label: "错误堆栈",
        }));
        const __VLS_178 = __VLS_177({
            label: "错误堆栈",
        }, ...__VLS_functionalComponentArgsRest(__VLS_177));
        __VLS_179.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "error-stack" },
        });
        (__VLS_ctx.selectedError.stack);
        var __VLS_179;
    }
    var __VLS_147;
}
var __VLS_143;
/** @type {__VLS_StyleScopedClasses['system-monitor']} */ ;
/** @type {__VLS_StyleScopedClasses['monitor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-section']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['services-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-card']} */ ;
/** @type {__VLS_StyleScopedClasses['service-item']} */ ;
/** @type {__VLS_StyleScopedClasses['service-header']} */ ;
/** @type {__VLS_StyleScopedClasses['service-name']} */ ;
/** @type {__VLS_StyleScopedClasses['service-metrics']} */ ;
/** @type {__VLS_StyleScopedClasses['metric']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-label']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-value']} */ ;
/** @type {__VLS_StyleScopedClasses['metric']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-label']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-value']} */ ;
/** @type {__VLS_StyleScopedClasses['service-error']} */ ;
/** @type {__VLS_StyleScopedClasses['error-label']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['charts-section']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-container']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-container']} */ ;
/** @type {__VLS_StyleScopedClasses['errors-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-card']} */ ;
/** @type {__VLS_StyleScopedClasses['error-details']} */ ;
/** @type {__VLS_StyleScopedClasses['error-stack']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            ClockCircleOutlined: icons_vue_1.ClockCircleOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            WarningOutlined: icons_vue_1.WarningOutlined,
            formatDateTime: date_1.formatDateTime,
            loading: loading,
            autoRefresh: autoRefresh,
            systemStatus: systemStatus,
            performanceStats: performanceStats,
            errorStats: errorStats,
            serviceHealth: serviceHealth,
            recentErrors: recentErrors,
            responseTimeChart: responseTimeChart,
            errorChart: errorChart,
            showErrorModal: showErrorModal,
            selectedError: selectedError,
            errorColumns: errorColumns,
            refreshData: refreshData,
            getServiceStatusColor: getServiceStatusColor,
            getServiceStatusText: getServiceStatusText,
            getErrorSeverityColor: getErrorSeverityColor,
            formatTime: formatTime,
            viewErrorDetails: viewErrorDetails,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
