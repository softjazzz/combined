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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const LineChart_vue_1 = __importDefault(require("@/components/charts/LineChart.vue"));
const BarChart_vue_1 = __importDefault(require("@/components/charts/BarChart.vue"));
const PieChart_vue_1 = __importDefault(require("@/components/charts/PieChart.vue"));
const GaugeChart_vue_1 = __importDefault(require("@/components/charts/GaugeChart.vue"));
import statistics_api_1 from '@/api/statistics-api';
// 响应式数据
const loading = (0, vue_1.ref)(true);
const exporting = (0, vue_1.ref)(false);
const selectedPeriod = (0, vue_1.ref)('month');
const trendType = (0, vue_1.ref)('all');
const departmentChartType = (0, vue_1.ref)('recordCount');
// 统计数据
const overview = (0, vue_1.ref)({
    totalRecords: 0,
    pendingRecords: 0,
    analyzingRecords: 0,
    completedRecords: 0,
    averageScore: 0,
    passRate: 0,
    todayUploads: 0,
    weeklyTrend: '+0%'
});
const trendData = (0, vue_1.ref)(: any[]);
const departmentStats = (0, vue_1.ref)(: any[]);
const scoreDistribution = (0, vue_1.ref)(: any[]);
const issueStats = (0, vue_1.ref)(: any[]);
// 计算属性
const overviewCards = (0, vue_1.computed)(() => [
    {
        title: '总病案数',
        value: overview.value.totalRecords.toLocaleString(),
        change: {
            value: parseFloat(overview.value.weeklyTrend.replace(/[+%]/g, '')),
            type: overview.value.weeklyTrend.startsWith('+') ? 'increase' : 'decrease'
        },
        icon: 'FileTextOutlined',
        color: '#1890ff'
    },
    {
        title: '待分析',
        value: overview.value.pendingRecords,
        change: {
            value: 2.1,
            type: 'decrease'
        },
        icon: 'ClockCircleOutlined',
        color: '#faad14'
    },
    {
        title: '分析中',
        value: overview.value.analyzingRecords,
        change: {
            value: 1.8,
            type: 'increase'
        },
        icon: 'SyncOutlined',
        color: '#13c2c2'
    },
    {
        title: '平均评分',
        value: `${overview.value.averageScore}分`,
        change: {
            value: 3.2,
            type: 'increase'
        },
        icon: 'TrophyOutlined',
        color: '#52c41a'
    },
    {
        title: '通过率',
        value: `${overview.value.passRate}%`,
        change: {
            value: 1.5,
            type: 'increase'
        },
        icon: 'CheckCircleOutlined',
        color: '#722ed1'
    },
    {
        title: '今日新增',
        value: overview.value.todayUploads,
        change: {
            value: 8.3,
            type: 'increase'
        },
        icon: 'PlusOutlined',
        color: '#f5222d'
    }
]);
const scoreDistributionData = (0, vue_1.computed)(() => scoreDistribution.value.map(item => ({
    name: item.scoreRange,
    value: item.count,
    percentage: item.percentage
})));
const issueStatsData = (0, vue_1.computed)(() => issueStats.value.map(item => ({
    name: item.category,
    value: item.issueCount,
    percentage: item.percentage
})));
// 表格列配置
const tableColumns = [
    {
        title: '科室',
        dataIndex: 'department',
        key: 'department',
        width: 100
    },
    {
        title: '病案数',
        dataIndex: 'recordCount',
        key: 'recordCount',
        width: 80,
        sorter: (a, b) => a.recordCount - b.recordCount
    },
    {
        title: '平均评分',
        dataIndex: 'averageScore',
        key: 'averageScore',
        width: 120,
        sorter: (a, b) => a.averageScore - b.averageScore
    },
    {
        title: '通过率',
        dataIndex: 'passRate',
        key: 'passRate',
        width: 100,
        sorter: (a, b) => a.passRate - b.passRate
    }
];
// 图标映射
const getIcon = (iconName) => {
    const iconMap = {
        FileTextOutlined: icons_vue_1.FileTextOutlined,
        ClockCircleOutlined: icons_vue_1.ClockCircleOutlined,
        SyncOutlined: icons_vue_1.SyncOutlined,
        TrophyOutlined: icons_vue_1.TrophyOutlined,
        CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
        PlusOutlined: icons_vue_1.PlusOutlined
    };
    return iconMap[iconName] || icons_vue_1.FileTextOutlined;
};
// 方法
const loadData = async () => {
    try {
        loading.value = true;
        const [overviewData, trendDataResult, departmentStatsResult, scoreDistributionResult, issueStatsResult] = await Promise.all([
            (0, statistics_api_1.getStatisticsOverview)(),
            (0, statistics_api_1.getTrendData)(selectedPeriod.value),
            (0, statistics_api_1.getDepartmentStats)(),
            (0, statistics_api_1.getQCScoreDistribution)(),
            (0, statistics_api_1.getQCIssueStats)()
        ]);
        overview.value = overviewData;
        trendData.value = trendDataResult;
        departmentStats.value = departmentStatsResult;
        scoreDistribution.value = scoreDistributionResult;
        issueStats.value = issueStatsResult;
    }
    catch (error) {
        console.error('加载统计数据失败:', error);
        ant_design_vue_1.message.error('加载统计数据失败');
    }
    finally {
        loading.value = false;
    }
};
const refreshData = () => {
    loadData();
};
const onPeriodChange = () => {
    loadData();
};
const onTrendTypeChange = () => {
    // 可以根据趋势类型过滤数据
    console.log('趋势类型变更:', trendType.value);
};
const onDepartmentChartTypeChange = () => {
    // 图表类型变更时的处理
    console.log('部门图表类型变更:', departmentChartType.value);
};
const exportReport = async () => {
    try {
        exporting.value = true;
        // 准备导出数据
        const exportData = {
            overview: overview.value,
            trendData: trendData.value,
            departmentStats: departmentStats.value,
            scoreDistribution: scoreDistribution.value,
            issueStats: issueStats.value,
            exportTime: new Date().toISOString()
        };
        // 导入导出工具
        const { exportToExcel } = await Promise.resolve().then(() => __importStar(require('@/utils/export')));
        await exportToExcel(exportData);
        ant_design_vue_1.message.success('报表导出成功');
    }
    catch (error) {
        console.error('导出报表失败:', error);
        ant_design_vue_1.message.error('导出报表失败');
    }
    finally {
        exporting.value = false;
    }
};
// 生命周期
(0, vue_1.onMounted)(() => {
    loadData();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['stats-change']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-change']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-actions" },
});
const __VLS_0 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedPeriod),
    ...{ style: {} },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedPeriod),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onChange: (__VLS_ctx.onPeriodChange)
};
__VLS_7.slots.default;
const __VLS_12 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    value: "week",
}));
const __VLS_14 = __VLS_13({
    value: "week",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
const __VLS_16 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    value: "month",
}));
const __VLS_18 = __VLS_17({
    value: "month",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
var __VLS_19;
const __VLS_20 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    value: "quarter",
}));
const __VLS_22 = __VLS_21({
    value: "quarter",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
var __VLS_23;
var __VLS_7;
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    type: "primary",
    icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
    loading: (__VLS_ctx.loading),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    type: "primary",
    icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.refreshData)
};
__VLS_27.slots.default;
var __VLS_27;
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
    loading: (__VLS_ctx.exporting),
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
    loading: (__VLS_ctx.exporting),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (__VLS_ctx.exportReport)
};
__VLS_35.slots.default;
var __VLS_35;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stats-overview mb-6" },
});
const __VLS_40 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    gutter: ([16, 16]),
}));
const __VLS_42 = __VLS_41({
    gutter: ([16, 16]),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
for (const [card] of __VLS_getVForSourceType((__VLS_ctx.overviewCards))) {
    const __VLS_44 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        xs: (24),
        sm: (12),
        md: (8),
        lg: (6),
        key: (card.title),
    }));
    const __VLS_46 = __VLS_45({
        xs: (24),
        sm: (12),
        md: (8),
        lg: (6),
        key: (card.title),
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    const __VLS_48 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ class: "stats-card" },
    }));
    const __VLS_50 = __VLS_49({
        ...{ class: "stats-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_51.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-card-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-icon" },
        ...{ style: ({ backgroundColor: card.color + '20' }) },
    });
    const __VLS_52 = ((__VLS_ctx.getIcon(card.icon)));
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        ...{ style: ({ color: card.color }) },
    }));
    const __VLS_54 = __VLS_53({
        ...{ style: ({ color: card.color }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-title" },
    });
    (card.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-value" },
    });
    (card.value);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-change" },
        ...{ class: (card.change?.type) },
    });
    const __VLS_56 = ((card.change?.type === 'increase' ? __VLS_ctx.ArrowUpOutlined : __VLS_ctx.ArrowDownOutlined));
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
    const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
    (card.change?.value);
    var __VLS_51;
    var __VLS_47;
}
var __VLS_43;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "charts-section" },
});
const __VLS_60 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    gutter: ([24, 24]),
}));
const __VLS_62 = __VLS_61({
    gutter: ([24, 24]),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
const __VLS_64 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    xs: (24),
    lg: (16),
}));
const __VLS_66 = __VLS_65({
    xs: (24),
    lg: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
const __VLS_68 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    title: "质控趋势分析",
    ...{ class: "chart-card" },
}));
const __VLS_70 = __VLS_69({
    title: "质控趋势分析",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_71.slots;
    const __VLS_72 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({}));
    const __VLS_74 = __VLS_73({}, ...__VLS_functionalComponentArgsRest(__VLS_73));
    __VLS_75.slots.default;
    const __VLS_76 = {}.ARadioGroup;
    /** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.trendType),
        size: "small",
    }));
    const __VLS_78 = __VLS_77({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.trendType),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    let __VLS_80;
    let __VLS_81;
    let __VLS_82;
    const __VLS_83 = {
        onChange: (__VLS_ctx.onTrendTypeChange)
    };
    __VLS_79.slots.default;
    const __VLS_84 = {}.ARadioButton;
    /** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        value: "all",
    }));
    const __VLS_86 = __VLS_85({
        value: "all",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    var __VLS_87;
    const __VLS_88 = {}.ARadioButton;
    /** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        value: "score",
    }));
    const __VLS_90 = __VLS_89({
        value: "score",
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    __VLS_91.slots.default;
    var __VLS_91;
    const __VLS_92 = {}.ARadioButton;
    /** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        value: "count",
    }));
    const __VLS_94 = __VLS_93({
        value: "count",
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    __VLS_95.slots.default;
    var __VLS_95;
    var __VLS_79;
    var __VLS_75;
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    const __VLS_96 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        size: "large",
    }));
    const __VLS_98 = __VLS_97({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
}
else {
    /** @type {[typeof LineChart, ]} */ ;
    // @ts-ignore
    const __VLS_100 = __VLS_asFunctionalComponent(LineChart_vue_1.default, new LineChart_vue_1.default({
        data: (__VLS_ctx.trendData),
        title: "",
        height: "350px",
        showDataZoom: (__VLS_ctx.trendData.length > 10),
    }));
    const __VLS_101 = __VLS_100({
        data: (__VLS_ctx.trendData),
        title: "",
        height: "350px",
        showDataZoom: (__VLS_ctx.trendData.length > 10),
    }, ...__VLS_functionalComponentArgsRest(__VLS_100));
}
var __VLS_71;
var __VLS_67;
const __VLS_103 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_104 = __VLS_asFunctionalComponent(__VLS_103, new __VLS_103({
    xs: (24),
    lg: (8),
}));
const __VLS_105 = __VLS_104({
    xs: (24),
    lg: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_104));
__VLS_106.slots.default;
const __VLS_107 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_108 = __VLS_asFunctionalComponent(__VLS_107, new __VLS_107({
    title: "总体评分",
    ...{ class: "chart-card" },
}));
const __VLS_109 = __VLS_108({
    title: "总体评分",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_108));
__VLS_110.slots.default;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    const __VLS_111 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_112 = __VLS_asFunctionalComponent(__VLS_111, new __VLS_111({
        size: "large",
    }));
    const __VLS_113 = __VLS_112({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_112));
}
else {
    /** @type {[typeof GaugeChart, ]} */ ;
    // @ts-ignore
    const __VLS_115 = __VLS_asFunctionalComponent(GaugeChart_vue_1.default, new GaugeChart_vue_1.default({
        value: (__VLS_ctx.overview.averageScore),
        title: "",
        height: "350px",
    }));
    const __VLS_116 = __VLS_115({
        value: (__VLS_ctx.overview.averageScore),
        title: "",
        height: "350px",
    }, ...__VLS_functionalComponentArgsRest(__VLS_115));
}
var __VLS_110;
var __VLS_106;
const __VLS_118 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
    xs: (24),
    lg: (12),
}));
const __VLS_120 = __VLS_119({
    xs: (24),
    lg: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_119));
__VLS_121.slots.default;
const __VLS_122 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
    title: "部门对比分析",
    ...{ class: "chart-card" },
}));
const __VLS_124 = __VLS_123({
    title: "部门对比分析",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_123));
__VLS_125.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_125.slots;
    const __VLS_126 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.departmentChartType),
        size: "small",
        ...{ style: {} },
    }));
    const __VLS_128 = __VLS_127({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.departmentChartType),
        size: "small",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    let __VLS_130;
    let __VLS_131;
    let __VLS_132;
    const __VLS_133 = {
        onChange: (__VLS_ctx.onDepartmentChartTypeChange)
    };
    __VLS_129.slots.default;
    const __VLS_134 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
        value: "recordCount",
    }));
    const __VLS_136 = __VLS_135({
        value: "recordCount",
    }, ...__VLS_functionalComponentArgsRest(__VLS_135));
    __VLS_137.slots.default;
    var __VLS_137;
    const __VLS_138 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({
        value: "averageScore",
    }));
    const __VLS_140 = __VLS_139({
        value: "averageScore",
    }, ...__VLS_functionalComponentArgsRest(__VLS_139));
    __VLS_141.slots.default;
    var __VLS_141;
    const __VLS_142 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({
        value: "passRate",
    }));
    const __VLS_144 = __VLS_143({
        value: "passRate",
    }, ...__VLS_functionalComponentArgsRest(__VLS_143));
    __VLS_145.slots.default;
    var __VLS_145;
    var __VLS_129;
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    const __VLS_146 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_147 = __VLS_asFunctionalComponent(__VLS_146, new __VLS_146({
        size: "large",
    }));
    const __VLS_148 = __VLS_147({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_147));
}
else {
    /** @type {[typeof BarChart, ]} */ ;
    // @ts-ignore
    const __VLS_150 = __VLS_asFunctionalComponent(BarChart_vue_1.default, new BarChart_vue_1.default({
        data: (__VLS_ctx.departmentStats),
        type: (__VLS_ctx.departmentChartType),
        title: "",
        height: "350px",
    }));
    const __VLS_151 = __VLS_150({
        data: (__VLS_ctx.departmentStats),
        type: (__VLS_ctx.departmentChartType),
        title: "",
        height: "350px",
    }, ...__VLS_functionalComponentArgsRest(__VLS_150));
}
var __VLS_125;
var __VLS_121;
const __VLS_153 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({
    xs: (24),
    lg: (12),
}));
const __VLS_155 = __VLS_154({
    xs: (24),
    lg: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_154));
__VLS_156.slots.default;
const __VLS_157 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
    title: "评分分布",
    ...{ class: "chart-card" },
}));
const __VLS_159 = __VLS_158({
    title: "评分分布",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_158));
__VLS_160.slots.default;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    const __VLS_161 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
        size: "large",
    }));
    const __VLS_163 = __VLS_162({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_162));
}
else {
    /** @type {[typeof PieChart, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(PieChart_vue_1.default, new PieChart_vue_1.default({
        data: (__VLS_ctx.scoreDistributionData),
        title: "",
        height: "350px",
    }));
    const __VLS_166 = __VLS_165({
        data: (__VLS_ctx.scoreDistributionData),
        title: "",
        height: "350px",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
}
var __VLS_160;
var __VLS_156;
const __VLS_168 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    xs: (24),
    lg: (12),
}));
const __VLS_170 = __VLS_169({
    xs: (24),
    lg: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
const __VLS_172 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    title: "问题类型统计",
    ...{ class: "chart-card" },
}));
const __VLS_174 = __VLS_173({
    title: "问题类型统计",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
__VLS_175.slots.default;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    const __VLS_176 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
        size: "large",
    }));
    const __VLS_178 = __VLS_177({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_177));
}
else {
    /** @type {[typeof PieChart, ]} */ ;
    // @ts-ignore
    const __VLS_180 = __VLS_asFunctionalComponent(PieChart_vue_1.default, new PieChart_vue_1.default({
        data: (__VLS_ctx.issueStatsData),
        title: "",
        height: "350px",
        radius: (['30%', '60%']),
    }));
    const __VLS_181 = __VLS_180({
        data: (__VLS_ctx.issueStatsData),
        title: "",
        height: "350px",
        radius: (['30%', '60%']),
    }, ...__VLS_functionalComponentArgsRest(__VLS_180));
}
var __VLS_175;
var __VLS_171;
const __VLS_183 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_184 = __VLS_asFunctionalComponent(__VLS_183, new __VLS_183({
    xs: (24),
    lg: (12),
}));
const __VLS_185 = __VLS_184({
    xs: (24),
    lg: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_184));
__VLS_186.slots.default;
const __VLS_187 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_188 = __VLS_asFunctionalComponent(__VLS_187, new __VLS_187({
    title: "部门详细统计",
    ...{ class: "chart-card" },
}));
const __VLS_189 = __VLS_188({
    title: "部门详细统计",
    ...{ class: "chart-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_188));
__VLS_190.slots.default;
const __VLS_191 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_192 = __VLS_asFunctionalComponent(__VLS_191, new __VLS_191({
    columns: (__VLS_ctx.tableColumns),
    dataSource: (__VLS_ctx.departmentStats),
    pagination: (false),
    size: "small",
    loading: (__VLS_ctx.loading),
}));
const __VLS_193 = __VLS_192({
    columns: (__VLS_ctx.tableColumns),
    dataSource: (__VLS_ctx.departmentStats),
    pagination: (false),
    size: "small",
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_192));
__VLS_194.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_194.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'averageScore') {
        const __VLS_195 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_196 = __VLS_asFunctionalComponent(__VLS_195, new __VLS_195({
            percent: (record.averageScore),
            strokeColor: (record.averageScore >= 80 ? '#52c41a' : record.averageScore >= 60 ? '#faad14' : '#ff4d4f'),
            size: "small",
        }));
        const __VLS_197 = __VLS_196({
            percent: (record.averageScore),
            strokeColor: (record.averageScore >= 80 ? '#52c41a' : record.averageScore >= 60 ? '#faad14' : '#ff4d4f'),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_196));
    }
    else if (column.key === 'passRate') {
        const __VLS_199 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_200 = __VLS_asFunctionalComponent(__VLS_199, new __VLS_199({
            color: (record.passRate >= 80 ? 'green' : record.passRate >= 60 ? 'orange' : 'red'),
        }));
        const __VLS_201 = __VLS_200({
            color: (record.passRate >= 80 ? 'green' : record.passRate >= 60 ? 'orange' : 'red'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_200));
        __VLS_202.slots.default;
        (record.passRate);
        var __VLS_202;
    }
}
var __VLS_194;
var __VLS_190;
var __VLS_186;
var __VLS_63;
/** @type {__VLS_StyleScopedClasses['page-container']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-overview']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-card-content']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-info']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-change']} */ ;
/** @type {__VLS_StyleScopedClasses['charts-section']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['chart-card']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            ArrowUpOutlined: icons_vue_1.ArrowUpOutlined,
            ArrowDownOutlined: icons_vue_1.ArrowDownOutlined,
            LineChart: LineChart_vue_1.default,
            BarChart: BarChart_vue_1.default,
            PieChart: PieChart_vue_1.default,
            GaugeChart: GaugeChart_vue_1.default,
            loading: loading,
            exporting: exporting,
            selectedPeriod: selectedPeriod,
            trendType: trendType,
            departmentChartType: departmentChartType,
            overview: overview,
            trendData: trendData,
            departmentStats: departmentStats,
            overviewCards: overviewCards,
            scoreDistributionData: scoreDistributionData,
            issueStatsData: issueStatsData,
            tableColumns: tableColumns,
            getIcon: getIcon,
            refreshData: refreshData,
            onPeriodChange: onPeriodChange,
            onTrendTypeChange: onTrendTypeChange,
            onDepartmentChartTypeChange: onDepartmentChartTypeChange,
            exportReport: exportReport,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
