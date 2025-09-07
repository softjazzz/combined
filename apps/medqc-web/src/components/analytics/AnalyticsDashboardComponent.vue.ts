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
const dayjs_1 = __importDefault(require("dayjs"));
import icons_vue_1 from '@ant-design/icons-vue';
const LineChartComponent_vue_1 = __importDefault(require("../charts/LineChartComponent.vue"));
const BarChartComponent_vue_1 = __importDefault(require("../charts/BarChartComponent.vue"));
const RadarChartEchartsComponent_vue_1 = __importDefault(require("../charts/RadarChartEchartsComponent.vue"));
import analytics_engine_1 from '../../lib/analytics-engine';
import report_engine_1 from '../../lib/report-engine';
// 响应式数据
const loading = (0, vue_1.ref)(false);
const dateRange = (0, vue_1.ref)([(0, dayjs_1.default)().subtract(30, 'days'), (0, dayjs_1.default)()]);
const selectedDepartment = (0, vue_1.ref)('');
const trendGranularity = (0, vue_1.ref)('day');
const comparisonMetric = (0, vue_1.ref)('avg_score');
const selectedDoctor = (0, vue_1.ref)('');
// 数据状态
const coreMetrics = (0, vue_1.ref)(: any[]);
const insights = (0, vue_1.ref)(: any[]);
const trendChartData = (0, vue_1.ref)(: any[]);
const comparisonChartData = (0, vue_1.ref)(: any[]);
const radarChartData = (0, vue_1.ref)({});
const departments = (0, vue_1.ref)(: any[]);
const topDoctors = (0, vue_1.ref)(: any[]);
const reportTemplates = (0, vue_1.ref)(: any[]);
const recentReports = (0, vue_1.ref)(: any[]);
// ECharts 雷达图数据
const radarChartEchartsData = (0, vue_1.ref)(: any[]);
const radarChartIndicators = (0, vue_1.ref)([
    { name: '质量评分', max: 100, min: 0 },
    { name: '工作效率', max: 100, min: 0 },
    { name: '生产力', max: 100, min: 0 },
    { name: '一致性', max: 100, min: 0 },
    { name: '及时性', max: 100, min: 0 }
]);
// 报表相关
const showReportModal = (0, vue_1.ref)(false);
const generatingReport = (0, vue_1.ref)(false);
const reportForm = (0, vue_1.ref)({
    template_id: '',
    date_range: null,
    department: '',
    output_format: 'pdf'
});
// 计算属性
const timeRange = (0, vue_1.computed)(() => ({
    start: dateRange.value[0].format('YYYY-MM-DD'),
    end: dateRange.value[1].format('YYYY-MM-DD'),
    granularity: trendGranularity.value
}));
const dateRanges = (0, vue_1.computed)(() => ({
    '今天': [(0, dayjs_1.default)(), (0, dayjs_1.default)()],
    '昨天': [(0, dayjs_1.default)().subtract(1, 'day'), (0, dayjs_1.default)().subtract(1, 'day')],
    '最近7天': [(0, dayjs_1.default)().subtract(7, 'days'), (0, dayjs_1.default)()],
    '最近30天': [(0, dayjs_1.default)().subtract(30, 'days'), (0, dayjs_1.default)()],
    '本月': [(0, dayjs_1.default)().startOf('month'), (0, dayjs_1.default)().endOf('month')],
    '上月': [(0, dayjs_1.default)().subtract(1, 'month').startOf('month'), (0, dayjs_1.default)().subtract(1, 'month').endOf('month')]
}));
// 图表配置
const trendChartOptions = (0, vue_1.computed)(() => ({
    responsive: true,
    maintainAspectRatio: false,
    scales: {
        y: {
            beginAtZero: true,
            max: 100
        }
    },
    plugins: {
        legend: {
            display: true,
            position: 'top'
        },
        tooltip: {
            mode: 'index',
            intersect: false
        }
    }
}));
const comparisonChartOptions = (0, vue_1.computed)(() => ({
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    scales: {
        x: {
            beginAtZero: true
        }
    },
    plugins: {
        legend: {
            display: false
        }
    }
}));
// radarChartOptions 已移除，ECharts 组件不需要这些选项
// 方法
const refreshData = async () => {
    loading.value = true;
    try {
        await Promise.all([
            loadCoreMetrics(),
            loadTrendData(),
            loadComparisonData(),
            loadRadarData(),
            loadInsights(),
            loadReportTemplates(),
            loadRecentReports()
        ]);
    }
    catch (error) {
        console.error('刷新数据失败:', error);
        ant_design_vue_1.message.error('刷新数据失败');
    }
    finally {
        loading.value = false;
    }
};
const loadCoreMetrics = async () => {
    // 模拟核心指标数据
    coreMetrics.value = [
        {
            key: 'total_records',
            label: '总病案数',
            value: 1247,
            unit: '份',
            change: 12.5,
            trend: 'up',
            color: '#1890ff',
            icon: 'FileTextOutlined'
        },
        {
            key: 'avg_score',
            label: '平均评分',
            value: 87.5,
            unit: '分',
            change: 3.2,
            trend: 'up',
            color: '#52c41a',
            icon: 'TrophyOutlined'
        },
        {
            key: 'grade_a_rate',
            label: '优秀率',
            value: 65.2,
            unit: '%',
            change: 2.8,
            trend: 'up',
            color: '#722ed1',
            icon: 'CheckCircleOutlined'
        },
        {
            key: 'avg_processing_time',
            label: '平均处理时间',
            value: 4.2,
            unit: '小时',
            change: -8.5,
            trend: 'down',
            color: '#faad14',
            icon: 'ClockCircleOutlined'
        }
    ];
};
const loadTrendData = async () => {
    try {
        // 临时使用模拟数据来测试图表显示
        const mockTrends = [
            { period: '2024-01-01', recordCount: 45, averageScore: 82.5, passRate: 65.2 },
            { period: '2024-01-02', recordCount: 52, averageScore: 84.1, passRate: 67.8 },
            { period: '2024-01-03', recordCount: 48, averageScore: 86.3, passRate: 70.1 },
            { period: '2024-01-04', recordCount: 55, averageScore: 85.7, passRate: 68.9 },
            { period: '2024-01-05', recordCount: 49, averageScore: 87.2, passRate: 72.3 },
            { period: '2024-01-06', recordCount: 51, averageScore: 88.5, passRate: 74.1 },
            { period: '2024-01-07', recordCount: 47, averageScore: 86.8, passRate: 71.5 }
        ];
        trendChartData.value = mockTrends;
        console.log('趋势数据已加载:', trendChartData.value);
    }
    catch (error) {
        console.error('加载趋势数据失败:', error);
        trendChartData.value = [];
    }
};
const loadComparisonData = async () => {
    try {
        // 临时使用模拟数据来测试图表显示
        const mockComparison = [
            { department: '内科', total_records: 120, avg_score: 85.5, grade_a_rate: 68.2 },
            { department: '外科', total_records: 98, avg_score: 82.3, grade_a_rate: 65.1 },
            { department: '儿科', total_records: 75, avg_score: 88.7, grade_a_rate: 72.4 },
            { department: '妇产科', total_records: 88, avg_score: 86.9, grade_a_rate: 70.5 },
            { department: '急诊科', total_records: 156, avg_score: 79.8, grade_a_rate: 58.9 }
        ];
        // 转换为 ECharts BarChartComponent 组件期望的格式
        comparisonChartData.value = mockComparison.map((dept, index) => ({
            department: dept.department,
            recordCount: dept.total_records || 0,
            averageScore: dept.avg_score || 0,
            passRate: dept.grade_a_rate || 0,
            color: `hsla(${200 + index * 30}, 70%, 50%, 0.8)`
        }));
        console.log('科室对比数据已加载:', comparisonChartData.value);
    }
    catch (error) {
        console.error('加载对比数据失败:', error);
        comparisonChartData.value = [];
    }
};
const loadRadarData = async () => {
    try {
        // 临时使用模拟数据来测试图表显示
        const mockPerformance = [
            { doctor_name: '张医生', quality_score: 85, efficiency_score: 78, productivity_score: 92, avg_score: 86, overall_score: 85 },
            { doctor_name: '李医生', quality_score: 78, efficiency_score: 85, productivity_score: 88, avg_score: 82, overall_score: 83 },
            { doctor_name: '王医生', quality_score: 92, efficiency_score: 76, productivity_score: 85, avg_score: 88, overall_score: 85 },
            { doctor_name: '刘医生', quality_score: 88, efficiency_score: 82, productivity_score: 79, avg_score: 85, overall_score: 84 }
        ];
        radarChartData.value = {
            labels: ['质量评分', '工作效率', '生产力', '一致性', '及时性'],
            datasets: mockPerformance.map((doctor, index) => ({
                label: doctor.doctor_name,
                data: [
                    doctor.quality_score,
                    doctor.efficiency_score,
                    doctor.productivity_score,
                    doctor.avg_score,
                    doctor.overall_score
                ],
                borderColor: `hsla(${index * 72}, 70%, 50%, 1)`,
                backgroundColor: `hsla(${index * 72}, 70%, 50%, 0.2)`,
                pointBackgroundColor: `hsla(${index * 72}, 70%, 50%, 1)`
            }))
        };
        // 同时更新 ECharts 格式的数据
        radarChartEchartsData.value = mockPerformance.map((doctor, index) => ({
            name: doctor.doctor_name,
            value: [
                doctor.quality_score,
                doctor.efficiency_score,
                doctor.productivity_score,
                doctor.avg_score,
                doctor.overall_score
            ],
            color: `hsla(${index * 72}, 70%, 50%, 1)`
        }));
        console.log('雷达图数据已加载:', radarChartEchartsData.value);
    }
    catch (error) {
        console.error('加载雷达数据失败:', error);
        radarChartEchartsData.value = [];
    }
};
const loadInsights = async () => {
    try {
        insights.value = await analytics_engine_1.analyticsEngine.generateInsights(timeRange.value, selectedDepartment.value);
    }
    catch (error) {
        console.error('加载洞察数据失败:', error);
    }
};
const loadReportTemplates = async () => {
    try {
        reportTemplates.value = await report_engine_1.reportEngine.getReportTemplates();
    }
    catch (error) {
        console.error('加载报表模板失败:', error);
    }
};
const loadRecentReports = async () => {
    try {
        recentReports.value = await report_engine_1.reportEngine.getReportInstances({ limit: 10 });
    }
    catch (error) {
        console.error('加载最近报表失败:', error);
    }
};
// 事件处理
const onDateRangeChange = () => {
    refreshData();
};
const onDepartmentChange = () => {
    refreshData();
};
const onTrendGranularityChange = () => {
    loadTrendData();
};
const onComparisonMetricChange = () => {
    loadComparisonData();
};
const onDoctorChange = () => {
    loadRadarData();
};
// 报表相关方法
const generateReport = async (templateId) => {
    reportForm.value.template_id = templateId;
    reportForm.value.date_range = dateRange.value;
    reportForm.value.department = selectedDepartment.value;
    showReportModal.value = true;
};
const handleGenerateReport = async () => {
    if (!reportForm.value.template_id || !reportForm.value.date_range) {
        ant_design_vue_1.message.error('请填写必要信息');
        return;
    }
    generatingReport.value = true;
    try {
        await report_engine_1.reportEngine.generateReport(reportForm.value.template_id, {
            period_start: reportForm.value.date_range[0].format('YYYY-MM-DD'),
            period_end: reportForm.value.date_range[1].format('YYYY-MM-DD'),
            filters: reportForm.value.department ? { department: reportForm.value.department } : undefined,
            output_format: reportForm.value.output_format
        });
        ant_design_vue_1.message.success('报表生成任务已提交，请稍后查看');
        showReportModal.value = false;
        loadRecentReports();
    }
    catch (error) {
        console.error('生成报表失败:', error);
        ant_design_vue_1.message.error('生成报表失败');
    }
    finally {
        generatingReport.value = false;
    }
};
const downloadReport = async (reportId) => {
    try {
        // 实现报表下载逻辑
        ant_design_vue_1.message.success('报表下载已开始');
    }
    catch (error) {
        console.error('下载报表失败:', error);
        ant_design_vue_1.message.error('下载报表失败');
    }
};
const viewReport = async (reportId) => {
    try {
        // 实现报表查看逻辑
        ant_design_vue_1.message.info('报表查看功能开发中');
    }
    catch (error) {
        console.error('查看报表失败:', error);
        ant_design_vue_1.message.error('查看报表失败');
    }
};
const deleteReport = async (reportId) => {
    try {
        await report_engine_1.reportEngine.deleteReportInstance(reportId);
        ant_design_vue_1.message.success('报表已删除');
        loadRecentReports();
    }
    catch (error) {
        console.error('删除报表失败:', error);
        ant_design_vue_1.message.error('删除报表失败');
    }
};
// 辅助方法
const formatMetricValue = (value, unit) => {
    if (unit === '%') {
        return `${value.toFixed(1)}%`;
    }
    if (unit === '分') {
        return `${value.toFixed(1)}分`;
    }
    if (unit === '小时') {
        return `${value.toFixed(1)}h`;
    }
    return value.toLocaleString();
};
const getTrendClass = (trend) => {
    if (trend === 'up')
        return 'text-green-500';
    if (trend === 'down')
        return 'text-red-500';
    return 'text-gray-500';
};
const getMetricCardClass = (metric) => {
    if (metric.trend === 'up')
        return 'border-l-4 border-green-500';
    if (metric.trend === 'down')
        return 'border-l-4 border-red-500';
    return 'border-l-4 border-gray-300';
};
const getInsightClass = (type) => {
    const classes = {
        achievement: 'border-green-200 bg-green-50',
        warning: 'border-yellow-200 bg-yellow-50',
        opportunity: 'border-blue-200 bg-blue-50',
        risk: 'border-red-200 bg-red-50'
    };
    return classes[type] || 'border-gray-200 bg-gray-50';
};
const getInsightIcon = (type) => {
    const icons = {
        achievement: 'CheckCircleOutlined',
        warning: 'ExclamationCircleOutlined',
        opportunity: 'BulbOutlined',
        risk: 'ExclamationCircleOutlined'
    };
    return icons[type] || 'BulbOutlined';
};
const getInsightIconClass = (type) => {
    const classes = {
        achievement: 'text-green-500',
        warning: 'text-yellow-500',
        opportunity: 'text-blue-500',
        risk: 'text-red-500'
    };
    return classes[type] || 'text-gray-500';
};
const getReportTypeColor = (type) => {
    const colors = {
        qc_summary: 'blue',
        performance: 'green',
        trend: 'purple',
        comparison: 'orange'
    };
    return colors[type] || 'default';
};
const getReportTypeLabel = (type) => {
    const labels = {
        qc_summary: '质控总结',
        performance: '绩效分析',
        trend: '趋势分析',
        comparison: '对比分析'
    };
    return labels[type] || type;
};
const getReportStatusColor = (status) => {
    const colors = {
        pending: 'default',
        generating: 'processing',
        completed: 'success',
        failed: 'error'
    };
    return colors[status] || 'default';
};
const getReportStatusLabel = (status) => {
    const labels = {
        pending: '待生成',
        generating: '生成中',
        completed: '已完成',
        failed: '失败'
    };
    return labels[status] || status;
};
const getComparisonMetricLabel = (metric) => {
    const labels = {
        avg_score: '平均评分',
        grade_a_rate: '优秀率',
        total_records: '病案数量'
    };
    return labels[metric] || metric;
};
const getBarChartType = (metric) => {
    switch (metric) {
        case 'avg_score':
            return 'averageScore';
        case 'grade_a_rate':
            return 'passRate';
        case 'total_records':
            return 'recordCount';
        default:
            return 'recordCount';
    }
};
const formatDate = (dateString) => {
    return (0, dayjs_1.default)(dateString).format('YYYY-MM-DD HH:mm');
};
// 生命周期
(0, vue_1.onMounted)(() => {
    refreshData();
});
// 监听器
(0, vue_1.watch)(dateRange: any, () => {
    refreshData();
});
(0, vue_1.watch)(selectedDepartment: any, () => {
    refreshData();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['insight-item']} */ ;
/** @type {__VLS_StyleScopedClasses['report-template-item']} */ ;
/** @type {__VLS_StyleScopedClasses['report-item']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "analytics-dashboard" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "dashboard-header mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-2xl font-bold text-gray-900" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 mt-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex space-x-3" },
});
const __VLS_0 = {}.ARangePicker;
/** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.dateRange),
    ranges: (__VLS_ctx.dateRanges),
    ...{ class: "w-80" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.dateRange),
    ranges: (__VLS_ctx.dateRanges),
    ...{ class: "w-80" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onChange: (__VLS_ctx.onDateRangeChange)
};
var __VLS_3;
const __VLS_8 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "选择科室",
    ...{ class: "w-40" },
    allowClear: true,
}));
const __VLS_10 = __VLS_9({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "选择科室",
    ...{ class: "w-40" },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_12;
let __VLS_13;
let __VLS_14;
const __VLS_15 = {
    onChange: (__VLS_ctx.onDepartmentChange)
};
__VLS_11.slots.default;
const __VLS_16 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    value: "",
}));
const __VLS_18 = __VLS_17({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
var __VLS_19;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_20 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        key: (dept),
        value: (dept),
    }));
    const __VLS_22 = __VLS_21({
        key: (dept),
        value: (dept),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    (dept);
    var __VLS_23;
}
var __VLS_11;
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.refreshData)
};
__VLS_27.slots.default;
const __VLS_32 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
var __VLS_27;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "metrics-overview mb-6" },
});
const __VLS_36 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    gutter: ([16, 16]),
}));
const __VLS_38 = __VLS_37({
    gutter: ([16, 16]),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
for (const [metric] of __VLS_getVForSourceType((__VLS_ctx.coreMetrics))) {
    const __VLS_40 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        xs: (24),
        sm: (12),
        md: (8),
        lg: (6),
        key: (metric.key),
    }));
    const __VLS_42 = __VLS_41({
        xs: (24),
        sm: (12),
        md: (8),
        lg: (6),
        key: (metric.key),
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    const __VLS_44 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        ...{ class: "metric-card" },
        ...{ class: (__VLS_ctx.getMetricCardClass(metric)) },
    }));
    const __VLS_46 = __VLS_45({
        ...{ class: "metric-card" },
        ...{ class: (__VLS_ctx.getMetricCardClass(metric)) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "metric-label text-gray-600 text-sm" },
    });
    (metric.label);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "metric-value text-2xl font-bold mt-1" },
        ...{ style: ({ color: metric.color }) },
    });
    (__VLS_ctx.formatMetricValue(metric.value, metric.unit));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "metric-change flex items-center mt-2" },
    });
    const __VLS_48 = ((metric.trend === 'up' ? 'ArrowUpOutlined' : metric.trend === 'down' ? 'ArrowDownOutlined' : 'MinusOutlined'));
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ class: (__VLS_ctx.getTrendClass(metric.trend)) },
        ...{ class: "text-xs mr-1" },
    }));
    const __VLS_50 = __VLS_49({
        ...{ class: (__VLS_ctx.getTrendClass(metric.trend)) },
        ...{ class: "text-xs mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: (__VLS_ctx.getTrendClass(metric.trend)) },
        ...{ class: "text-xs" },
    });
    (Math.abs(metric.change || 0).toFixed(1));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-500 text-xs ml-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "metric-icon p-3 rounded-lg" },
        ...{ style: ({ backgroundColor: metric.color + '20' }) },
    });
    const __VLS_52 = ((metric.icon));
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        ...{ style: ({ color: metric.color }) },
        ...{ class: "text-xl" },
    }));
    const __VLS_54 = __VLS_53({
        ...{ style: ({ color: metric.color }) },
        ...{ class: "text-xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    var __VLS_47;
    var __VLS_43;
}
var __VLS_39;
const __VLS_56 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    gutter: ([24, 24]),
}));
const __VLS_58 = __VLS_57({
    gutter: ([24, 24]),
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    xs: (24),
    lg: (16),
}));
const __VLS_62 = __VLS_61({
    xs: (24),
    lg: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
const __VLS_64 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    title: "质量趋势分析",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}));
const __VLS_66 = __VLS_65({
    title: "质量趋势分析",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_67.slots;
    const __VLS_68 = {}.ARadioGroup;
    /** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.trendGranularity),
    }));
    const __VLS_70 = __VLS_69({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.trendGranularity),
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    let __VLS_72;
    let __VLS_73;
    let __VLS_74;
    const __VLS_75 = {
        onChange: (__VLS_ctx.onTrendGranularityChange)
    };
    __VLS_71.slots.default;
    const __VLS_76 = {}.ARadioButton;
    /** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        value: "day",
    }));
    const __VLS_78 = __VLS_77({
        value: "day",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    var __VLS_79;
    const __VLS_80 = {}.ARadioButton;
    /** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        value: "week",
    }));
    const __VLS_82 = __VLS_81({
        value: "week",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    var __VLS_83;
    const __VLS_84 = {}.ARadioButton;
    /** @type {[typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, typeof __VLS_components.ARadioButton, typeof __VLS_components.aRadioButton, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        value: "month",
    }));
    const __VLS_86 = __VLS_85({
        value: "month",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    var __VLS_87;
    var __VLS_71;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "h-80" },
});
if (!__VLS_ctx.loading && __VLS_ctx.trendChartData.length > 0) {
    /** @type {[typeof LineChartComponent, ]} */ ;
    // @ts-ignore
    const __VLS_88 = __VLS_asFunctionalComponent(LineChartComponent_vue_1.default, new LineChartComponent_vue_1.default({
        data: (__VLS_ctx.trendChartData),
        options: (__VLS_ctx.trendChartOptions),
        height: "300px",
    }));
    const __VLS_89 = __VLS_88({
        data: (__VLS_ctx.trendChartData),
        options: (__VLS_ctx.trendChartOptions),
        height: "300px",
    }, ...__VLS_functionalComponentArgsRest(__VLS_88));
}
else if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center h-full" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-500 text-sm" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center h-full" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-500" },
    });
}
var __VLS_67;
const __VLS_91 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_92 = __VLS_asFunctionalComponent(__VLS_91, new __VLS_91({
    title: "科室对比分析",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}));
const __VLS_93 = __VLS_92({
    title: "科室对比分析",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_92));
__VLS_94.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_94.slots;
    const __VLS_95 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_96 = __VLS_asFunctionalComponent(__VLS_95, new __VLS_95({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.comparisonMetric),
        ...{ class: "w-32" },
    }));
    const __VLS_97 = __VLS_96({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.comparisonMetric),
        ...{ class: "w-32" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_96));
    let __VLS_99;
    let __VLS_100;
    let __VLS_101;
    const __VLS_102 = {
        onChange: (__VLS_ctx.onComparisonMetricChange)
    };
    __VLS_98.slots.default;
    const __VLS_103 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_104 = __VLS_asFunctionalComponent(__VLS_103, new __VLS_103({
        value: "avg_score",
    }));
    const __VLS_105 = __VLS_104({
        value: "avg_score",
    }, ...__VLS_functionalComponentArgsRest(__VLS_104));
    __VLS_106.slots.default;
    var __VLS_106;
    const __VLS_107 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_108 = __VLS_asFunctionalComponent(__VLS_107, new __VLS_107({
        value: "grade_a_rate",
    }));
    const __VLS_109 = __VLS_108({
        value: "grade_a_rate",
    }, ...__VLS_functionalComponentArgsRest(__VLS_108));
    __VLS_110.slots.default;
    var __VLS_110;
    const __VLS_111 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_112 = __VLS_asFunctionalComponent(__VLS_111, new __VLS_111({
        value: "total_records",
    }));
    const __VLS_113 = __VLS_112({
        value: "total_records",
    }, ...__VLS_functionalComponentArgsRest(__VLS_112));
    __VLS_114.slots.default;
    var __VLS_114;
    var __VLS_98;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "h-80" },
});
if (!__VLS_ctx.loading && __VLS_ctx.comparisonChartData.length > 0) {
    /** @type {[typeof BarChartComponent, ]} */ ;
    // @ts-ignore
    const __VLS_115 = __VLS_asFunctionalComponent(BarChartComponent_vue_1.default, new BarChartComponent_vue_1.default({
        data: (__VLS_ctx.comparisonChartData),
        type: (__VLS_ctx.getBarChartType(__VLS_ctx.comparisonMetric)),
        height: "300px",
    }));
    const __VLS_116 = __VLS_115({
        data: (__VLS_ctx.comparisonChartData),
        type: (__VLS_ctx.getBarChartType(__VLS_ctx.comparisonMetric)),
        height: "300px",
    }, ...__VLS_functionalComponentArgsRest(__VLS_115));
}
else if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center h-full" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-500 text-sm" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center h-full" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-500" },
    });
}
var __VLS_94;
const __VLS_118 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
    title: "绩效雷达分析",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}));
const __VLS_120 = __VLS_119({
    title: "绩效雷达分析",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_119));
__VLS_121.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_121.slots;
    const __VLS_122 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.selectedDoctor),
        placeholder: "选择医生",
        ...{ class: "w-40" },
        allowClear: true,
    }));
    const __VLS_124 = __VLS_123({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.selectedDoctor),
        placeholder: "选择医生",
        ...{ class: "w-40" },
        allowClear: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_123));
    let __VLS_126;
    let __VLS_127;
    let __VLS_128;
    const __VLS_129 = {
        onChange: (__VLS_ctx.onDoctorChange)
    };
    __VLS_125.slots.default;
    const __VLS_130 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({
        value: "",
    }));
    const __VLS_132 = __VLS_131({
        value: "",
    }, ...__VLS_functionalComponentArgsRest(__VLS_131));
    __VLS_133.slots.default;
    var __VLS_133;
    for (const [doctor] of __VLS_getVForSourceType((__VLS_ctx.topDoctors))) {
        const __VLS_134 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
            key: (doctor.id),
            value: (doctor.id),
        }));
        const __VLS_136 = __VLS_135({
            key: (doctor.id),
            value: (doctor.id),
        }, ...__VLS_functionalComponentArgsRest(__VLS_135));
        __VLS_137.slots.default;
        (doctor.name);
        var __VLS_137;
    }
    var __VLS_125;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "h-80" },
});
if (!__VLS_ctx.loading && __VLS_ctx.radarChartEchartsData.length > 0) {
    /** @type {[typeof RadarChartEchartsComponent, ]} */ ;
    // @ts-ignore
    const __VLS_138 = __VLS_asFunctionalComponent(RadarChartEchartsComponent_vue_1.default, new RadarChartEchartsComponent_vue_1.default({
        data: (__VLS_ctx.radarChartEchartsData),
        indicators: (__VLS_ctx.radarChartIndicators),
        height: (300),
        title: "医生绩效对比",
    }));
    const __VLS_139 = __VLS_138({
        data: (__VLS_ctx.radarChartEchartsData),
        indicators: (__VLS_ctx.radarChartIndicators),
        height: (300),
        title: "医生绩效对比",
    }, ...__VLS_functionalComponentArgsRest(__VLS_138));
}
else if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center h-full" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-500 text-sm" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center h-full" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-500" },
    });
}
var __VLS_121;
var __VLS_63;
const __VLS_141 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_142 = __VLS_asFunctionalComponent(__VLS_141, new __VLS_141({
    xs: (24),
    lg: (8),
}));
const __VLS_143 = __VLS_142({
    xs: (24),
    lg: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_142));
__VLS_144.slots.default;
const __VLS_145 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
    title: "智能洞察",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}));
const __VLS_147 = __VLS_146({
    title: "智能洞察",
    ...{ class: "mb-6" },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_146));
__VLS_148.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_148.slots;
    const __VLS_149 = {}.ATooltip;
    /** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
    // @ts-ignore
    const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
        title: "AI自动分析生成",
    }));
    const __VLS_151 = __VLS_150({
        title: "AI自动分析生成",
    }, ...__VLS_functionalComponentArgsRest(__VLS_150));
    __VLS_152.slots.default;
    const __VLS_153 = {}.BulbOutlined;
    /** @type {[typeof __VLS_components.BulbOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({
        ...{ class: "text-yellow-500" },
    }));
    const __VLS_155 = __VLS_154({
        ...{ class: "text-yellow-500" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_154));
    var __VLS_152;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
for (const [insight] of __VLS_getVForSourceType((__VLS_ctx.insights))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (insight.title),
        ...{ class: "insight-item p-4 rounded-lg border" },
        ...{ class: (__VLS_ctx.getInsightClass(insight.type)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-start" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "insight-icon mr-3 mt-1" },
    });
    const __VLS_157 = ((__VLS_ctx.getInsightIcon(insight.type)));
    // @ts-ignore
    const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
        ...{ class: (__VLS_ctx.getInsightIconClass(insight.type)) },
    }));
    const __VLS_159 = __VLS_158({
        ...{ class: (__VLS_ctx.getInsightIconClass(insight.type)) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_158));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "font-semibold text-sm mb-1" },
    });
    (insight.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-xs text-gray-600 mb-2" },
    });
    (insight.description);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "recommendation bg-gray-50 p-2 rounded text-xs" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (insight.recommendation);
}
if (__VLS_ctx.insights.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center text-gray-500 py-8" },
    });
    const __VLS_161 = {}.BulbOutlined;
    /** @type {[typeof __VLS_components.BulbOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
        ...{ class: "text-2xl mb-2" },
    }));
    const __VLS_163 = __VLS_162({
        ...{ class: "text-2xl mb-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_162));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
var __VLS_148;
const __VLS_165 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
    title: "智能报表",
    ...{ class: "mb-6" },
}));
const __VLS_167 = __VLS_166({
    title: "智能报表",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_166));
__VLS_168.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_168.slots;
    const __VLS_169 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({
        ...{ 'onClick': {} },
        type: "link",
        size: "small",
    }));
    const __VLS_171 = __VLS_170({
        ...{ 'onClick': {} },
        type: "link",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_170));
    let __VLS_173;
    let __VLS_174;
    let __VLS_175;
    const __VLS_176 = {
        onClick: (...[$event]) => {
            __VLS_ctx.showReportModal = true;
        }
    };
    __VLS_172.slots.default;
    const __VLS_177 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_178 = __VLS_asFunctionalComponent(__VLS_177, new __VLS_177({}));
    const __VLS_179 = __VLS_178({}, ...__VLS_functionalComponentArgsRest(__VLS_178));
    var __VLS_172;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-3" },
});
for (const [template] of __VLS_getVForSourceType((__VLS_ctx.reportTemplates))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.generateReport(template.id);
            } },
        key: (template.id),
        ...{ class: "report-template-item p-3 border rounded-lg hover:bg-gray-50 cursor-pointer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "font-medium text-sm" },
    });
    (template.template_name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-xs text-gray-500 mt-1" },
    });
    (template.description);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center space-x-2" },
    });
    const __VLS_181 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
        color: (__VLS_ctx.getReportTypeColor(template.template_type)),
        size: "small",
    }));
    const __VLS_183 = __VLS_182({
        color: (__VLS_ctx.getReportTypeColor(template.template_type)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_182));
    __VLS_184.slots.default;
    (__VLS_ctx.getReportTypeLabel(template.template_type));
    var __VLS_184;
    const __VLS_185 = {}.FileTextOutlined;
    /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_186 = __VLS_asFunctionalComponent(__VLS_185, new __VLS_185({
        ...{ class: "text-gray-400" },
    }));
    const __VLS_187 = __VLS_186({
        ...{ class: "text-gray-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_186));
}
var __VLS_168;
const __VLS_189 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_190 = __VLS_asFunctionalComponent(__VLS_189, new __VLS_189({
    title: "最近报表",
}));
const __VLS_191 = __VLS_190({
    title: "最近报表",
}, ...__VLS_functionalComponentArgsRest(__VLS_190));
__VLS_192.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-3" },
});
for (const [report] of __VLS_getVForSourceType((__VLS_ctx.recentReports))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (report.id),
        ...{ class: "report-item p-3 border rounded-lg" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "font-medium text-sm" },
    });
    (report.report_name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-xs text-gray-500 mt-1" },
    });
    (__VLS_ctx.formatDate(report.created_at));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center space-x-2" },
    });
    const __VLS_193 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_194 = __VLS_asFunctionalComponent(__VLS_193, new __VLS_193({
        color: (__VLS_ctx.getReportStatusColor(report.status)),
        size: "small",
    }));
    const __VLS_195 = __VLS_194({
        color: (__VLS_ctx.getReportStatusColor(report.status)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_194));
    __VLS_196.slots.default;
    (__VLS_ctx.getReportStatusLabel(report.status));
    var __VLS_196;
    const __VLS_197 = {}.ADropdown;
    /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
    // @ts-ignore
    const __VLS_198 = __VLS_asFunctionalComponent(__VLS_197, new __VLS_197({}));
    const __VLS_199 = __VLS_198({}, ...__VLS_functionalComponentArgsRest(__VLS_198));
    __VLS_200.slots.default;
    const __VLS_201 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_202 = __VLS_asFunctionalComponent(__VLS_201, new __VLS_201({
        type: "text",
        size: "small",
    }));
    const __VLS_203 = __VLS_202({
        type: "text",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_202));
    __VLS_204.slots.default;
    const __VLS_205 = {}.MoreOutlined;
    /** @type {[typeof __VLS_components.MoreOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_206 = __VLS_asFunctionalComponent(__VLS_205, new __VLS_205({}));
    const __VLS_207 = __VLS_206({}, ...__VLS_functionalComponentArgsRest(__VLS_206));
    var __VLS_204;
    {
        const { overlay: __VLS_thisSlot } = __VLS_200.slots;
        const __VLS_209 = {}.AMenu;
        /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
        // @ts-ignore
        const __VLS_210 = __VLS_asFunctionalComponent(__VLS_209, new __VLS_209({}));
        const __VLS_211 = __VLS_210({}, ...__VLS_functionalComponentArgsRest(__VLS_210));
        __VLS_212.slots.default;
        const __VLS_213 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_214 = __VLS_asFunctionalComponent(__VLS_213, new __VLS_213({
            ...{ 'onClick': {} },
            disabled: (report.status !== 'completed'),
        }));
        const __VLS_215 = __VLS_214({
            ...{ 'onClick': {} },
            disabled: (report.status !== 'completed'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_214));
        let __VLS_217;
        let __VLS_218;
        let __VLS_219;
        const __VLS_220 = {
            onClick: (...[$event]) => {
                __VLS_ctx.downloadReport(report.id);
            }
        };
        __VLS_216.slots.default;
        const __VLS_221 = {}.DownloadOutlined;
        /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_222 = __VLS_asFunctionalComponent(__VLS_221, new __VLS_221({}));
        const __VLS_223 = __VLS_222({}, ...__VLS_functionalComponentArgsRest(__VLS_222));
        var __VLS_216;
        const __VLS_225 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_226 = __VLS_asFunctionalComponent(__VLS_225, new __VLS_225({
            ...{ 'onClick': {} },
            disabled: (report.status !== 'completed'),
        }));
        const __VLS_227 = __VLS_226({
            ...{ 'onClick': {} },
            disabled: (report.status !== 'completed'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_226));
        let __VLS_229;
        let __VLS_230;
        let __VLS_231;
        const __VLS_232 = {
            onClick: (...[$event]) => {
                __VLS_ctx.viewReport(report.id);
            }
        };
        __VLS_228.slots.default;
        const __VLS_233 = {}.EyeOutlined;
        /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_234 = __VLS_asFunctionalComponent(__VLS_233, new __VLS_233({}));
        const __VLS_235 = __VLS_234({}, ...__VLS_functionalComponentArgsRest(__VLS_234));
        var __VLS_228;
        const __VLS_237 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_238 = __VLS_asFunctionalComponent(__VLS_237, new __VLS_237({
            ...{ 'onClick': {} },
        }));
        const __VLS_239 = __VLS_238({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_238));
        let __VLS_241;
        let __VLS_242;
        let __VLS_243;
        const __VLS_244 = {
            onClick: (...[$event]) => {
                __VLS_ctx.deleteReport(report.id);
            }
        };
        __VLS_240.slots.default;
        const __VLS_245 = {}.DeleteOutlined;
        /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_246 = __VLS_asFunctionalComponent(__VLS_245, new __VLS_245({}));
        const __VLS_247 = __VLS_246({}, ...__VLS_functionalComponentArgsRest(__VLS_246));
        var __VLS_240;
        var __VLS_212;
    }
    var __VLS_200;
    if (report.status === 'generating') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-2" },
        });
        const __VLS_249 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_250 = __VLS_asFunctionalComponent(__VLS_249, new __VLS_249({
            percent: (report.progress),
            size: "small",
        }));
        const __VLS_251 = __VLS_250({
            percent: (report.progress),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_250));
    }
}
if (__VLS_ctx.recentReports.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center text-gray-500 py-8" },
    });
    const __VLS_253 = {}.FileTextOutlined;
    /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_254 = __VLS_asFunctionalComponent(__VLS_253, new __VLS_253({
        ...{ class: "text-2xl mb-2" },
    }));
    const __VLS_255 = __VLS_254({
        ...{ class: "text-2xl mb-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_254));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
var __VLS_192;
var __VLS_144;
var __VLS_59;
const __VLS_257 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_258 = __VLS_asFunctionalComponent(__VLS_257, new __VLS_257({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showReportModal),
    title: "生成报表",
    width: "600px",
    confirmLoading: (__VLS_ctx.generatingReport),
}));
const __VLS_259 = __VLS_258({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showReportModal),
    title: "生成报表",
    width: "600px",
    confirmLoading: (__VLS_ctx.generatingReport),
}, ...__VLS_functionalComponentArgsRest(__VLS_258));
let __VLS_261;
let __VLS_262;
let __VLS_263;
const __VLS_264 = {
    onOk: (__VLS_ctx.handleGenerateReport)
};
__VLS_260.slots.default;
const __VLS_265 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_266 = __VLS_asFunctionalComponent(__VLS_265, new __VLS_265({
    model: (__VLS_ctx.reportForm),
    layout: "vertical",
}));
const __VLS_267 = __VLS_266({
    model: (__VLS_ctx.reportForm),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_266));
__VLS_268.slots.default;
const __VLS_269 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_270 = __VLS_asFunctionalComponent(__VLS_269, new __VLS_269({
    label: "报表模板",
    required: true,
}));
const __VLS_271 = __VLS_270({
    label: "报表模板",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_270));
__VLS_272.slots.default;
const __VLS_273 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_274 = __VLS_asFunctionalComponent(__VLS_273, new __VLS_273({
    value: (__VLS_ctx.reportForm.template_id),
    placeholder: "选择报表模板",
}));
const __VLS_275 = __VLS_274({
    value: (__VLS_ctx.reportForm.template_id),
    placeholder: "选择报表模板",
}, ...__VLS_functionalComponentArgsRest(__VLS_274));
__VLS_276.slots.default;
for (const [template] of __VLS_getVForSourceType((__VLS_ctx.reportTemplates))) {
    const __VLS_277 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_278 = __VLS_asFunctionalComponent(__VLS_277, new __VLS_277({
        key: (template.id),
        value: (template.id),
    }));
    const __VLS_279 = __VLS_278({
        key: (template.id),
        value: (template.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_278));
    __VLS_280.slots.default;
    (template.template_name);
    var __VLS_280;
}
var __VLS_276;
var __VLS_272;
const __VLS_281 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_282 = __VLS_asFunctionalComponent(__VLS_281, new __VLS_281({
    label: "时间范围",
    required: true,
}));
const __VLS_283 = __VLS_282({
    label: "时间范围",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_282));
__VLS_284.slots.default;
const __VLS_285 = {}.ARangePicker;
/** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
// @ts-ignore
const __VLS_286 = __VLS_asFunctionalComponent(__VLS_285, new __VLS_285({
    value: (__VLS_ctx.reportForm.date_range),
    ...{ style: {} },
    ranges: (__VLS_ctx.dateRanges),
}));
const __VLS_287 = __VLS_286({
    value: (__VLS_ctx.reportForm.date_range),
    ...{ style: {} },
    ranges: (__VLS_ctx.dateRanges),
}, ...__VLS_functionalComponentArgsRest(__VLS_286));
var __VLS_284;
const __VLS_289 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_290 = __VLS_asFunctionalComponent(__VLS_289, new __VLS_289({
    label: "科室筛选",
}));
const __VLS_291 = __VLS_290({
    label: "科室筛选",
}, ...__VLS_functionalComponentArgsRest(__VLS_290));
__VLS_292.slots.default;
const __VLS_293 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_294 = __VLS_asFunctionalComponent(__VLS_293, new __VLS_293({
    value: (__VLS_ctx.reportForm.department),
    placeholder: "选择科室（可选）",
    allowClear: true,
}));
const __VLS_295 = __VLS_294({
    value: (__VLS_ctx.reportForm.department),
    placeholder: "选择科室（可选）",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_294));
__VLS_296.slots.default;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_297 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_298 = __VLS_asFunctionalComponent(__VLS_297, new __VLS_297({
        key: (dept),
        value: (dept),
    }));
    const __VLS_299 = __VLS_298({
        key: (dept),
        value: (dept),
    }, ...__VLS_functionalComponentArgsRest(__VLS_298));
    __VLS_300.slots.default;
    (dept);
    var __VLS_300;
}
var __VLS_296;
var __VLS_292;
const __VLS_301 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_302 = __VLS_asFunctionalComponent(__VLS_301, new __VLS_301({
    label: "输出格式",
}));
const __VLS_303 = __VLS_302({
    label: "输出格式",
}, ...__VLS_functionalComponentArgsRest(__VLS_302));
__VLS_304.slots.default;
const __VLS_305 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_306 = __VLS_asFunctionalComponent(__VLS_305, new __VLS_305({
    value: (__VLS_ctx.reportForm.output_format),
    placeholder: "选择输出格式",
}));
const __VLS_307 = __VLS_306({
    value: (__VLS_ctx.reportForm.output_format),
    placeholder: "选择输出格式",
}, ...__VLS_functionalComponentArgsRest(__VLS_306));
__VLS_308.slots.default;
const __VLS_309 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_310 = __VLS_asFunctionalComponent(__VLS_309, new __VLS_309({
    value: "pdf",
}));
const __VLS_311 = __VLS_310({
    value: "pdf",
}, ...__VLS_functionalComponentArgsRest(__VLS_310));
__VLS_312.slots.default;
var __VLS_312;
const __VLS_313 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_314 = __VLS_asFunctionalComponent(__VLS_313, new __VLS_313({
    value: "excel",
}));
const __VLS_315 = __VLS_314({
    value: "excel",
}, ...__VLS_functionalComponentArgsRest(__VLS_314));
__VLS_316.slots.default;
var __VLS_316;
const __VLS_317 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_318 = __VLS_asFunctionalComponent(__VLS_317, new __VLS_317({
    value: "word",
}));
const __VLS_319 = __VLS_318({
    value: "word",
}, ...__VLS_functionalComponentArgsRest(__VLS_318));
__VLS_320.slots.default;
var __VLS_320;
var __VLS_308;
var __VLS_304;
var __VLS_268;
var __VLS_260;
/** @type {__VLS_StyleScopedClasses['analytics-dashboard']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-80']} */ ;
/** @type {__VLS_StyleScopedClasses['w-40']} */ ;
/** @type {__VLS_StyleScopedClasses['metrics-overview']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-card']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-label']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-change']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
/** @type {__VLS_StyleScopedClasses['metric-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-80']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t-transparent']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['w-32']} */ ;
/** @type {__VLS_StyleScopedClasses['h-80']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-orange-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t-transparent']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['w-40']} */ ;
/** @type {__VLS_StyleScopedClasses['h-80']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-purple-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t-transparent']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-yellow-500']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['insight-item']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['insight-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['recommendation']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['report-template-item']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['report-item']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            BulbOutlined: icons_vue_1.BulbOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            MoreOutlined: icons_vue_1.MoreOutlined,
            LineChartComponent: LineChartComponent_vue_1.default,
            BarChartComponent: BarChartComponent_vue_1.default,
            RadarChartEchartsComponent: RadarChartEchartsComponent_vue_1.default,
            loading: loading,
            dateRange: dateRange,
            selectedDepartment: selectedDepartment,
            trendGranularity: trendGranularity,
            comparisonMetric: comparisonMetric,
            selectedDoctor: selectedDoctor,
            coreMetrics: coreMetrics,
            insights: insights,
            trendChartData: trendChartData,
            comparisonChartData: comparisonChartData,
            departments: departments,
            topDoctors: topDoctors,
            reportTemplates: reportTemplates,
            recentReports: recentReports,
            radarChartEchartsData: radarChartEchartsData,
            radarChartIndicators: radarChartIndicators,
            showReportModal: showReportModal,
            generatingReport: generatingReport,
            reportForm: reportForm,
            dateRanges: dateRanges,
            trendChartOptions: trendChartOptions,
            refreshData: refreshData,
            onDateRangeChange: onDateRangeChange,
            onDepartmentChange: onDepartmentChange,
            onTrendGranularityChange: onTrendGranularityChange,
            onComparisonMetricChange: onComparisonMetricChange,
            onDoctorChange: onDoctorChange,
            generateReport: generateReport,
            handleGenerateReport: handleGenerateReport,
            downloadReport: downloadReport,
            viewReport: viewReport,
            deleteReport: deleteReport,
            formatMetricValue: formatMetricValue,
            getTrendClass: getTrendClass,
            getMetricCardClass: getMetricCardClass,
            getInsightClass: getInsightClass,
            getInsightIcon: getInsightIcon,
            getInsightIconClass: getInsightIconClass,
            getReportTypeColor: getReportTypeColor,
            getReportTypeLabel: getReportTypeLabel,
            getReportStatusColor: getReportStatusColor,
            getReportStatusLabel: getReportStatusLabel,
            getBarChartType: getBarChartType,
            formatDate: formatDate,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
