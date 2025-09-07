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
const echarts = __importStar(require("echarts"));
// 响应式数据
const loading = (0, vue_1.ref)(false);
const activeTab = (0, vue_1.ref)('learning');
const showLearningDialog = (0, vue_1.ref)(false);
const showKnowledgeDialog = (0, vue_1.ref)(false);
const showSettings = (0, vue_1.ref)(false);
const selectedCategory = (0, vue_1.ref)('');
const selectedTaskType = (0, vue_1.ref)('');
// 统计数据
const stats = (0, vue_1.reactive)({
    totalRecords: 1250,
    learningProgress: 85,
    knowledgeBaseSize: 156,
    activePatterns: 89,
    performanceScore: 88.5,
    pendingTasks: 12,
    runningTasks: 3,
    completedTasks: 145
});
// 学习记录
const learningRecords = (0, vue_1.ref)([
    {
        id: '1',
        recordId: 'REC001',
        originalScore: 85,
        reviewedScore: 92,
        improvement: 7,
        feedback: '诊断描述需要更详细',
        reviewerId: 'Dr. Zhang',
        timestamp: '2024-01-15 14:30:00'
    },
    {
        id: '2',
        recordId: 'REC002',
        originalScore: 78,
        reviewedScore: 75,
        improvement: -3,
        feedback: '治疗方案过于激进',
        reviewerId: 'Dr. Li',
        timestamp: '2024-01-15 13:45:00'
    }
]);
// 知识库
const knowledgeBase = (0, vue_1.ref)([
    {
        id: '1',
        category: 'completeness',
        pattern: '基本信息完整性检查',
        confidence: 0.95,
        usageCount: 120,
        successRate: 0.92,
        lastUpdated: '2024-01-15'
    },
    {
        id: '2',
        category: 'consistency',
        pattern: '诊断一致性验证',
        confidence: 0.88,
        usageCount: 85,
        successRate: 0.89,
        lastUpdated: '2024-01-14'
    }
]);
// 学习任务
const learningTasks = (0, vue_1.ref)([
    {
        id: '1',
        type: 'feedback_learning',
        status: 'pending',
        priority: 'high',
        createdAt: '2024-01-15 15:00:00',
        description: '处理用户反馈学习'
    },
    {
        id: '2',
        type: 'pattern_recognition',
        status: 'running',
        priority: 'medium',
        createdAt: '2024-01-15 14:30:00',
        description: '识别新的质控模式'
    }
]);
// 性能指标
const performanceMetrics = (0, vue_1.ref)([
    { name: '准确率', value: 0.885, type: 'percentage', trend: 2.3 },
    { name: '精确率', value: 0.862, type: 'percentage', trend: 1.8 },
    { name: '召回率', value: 0.841, type: 'percentage', trend: -0.5 },
    { name: '处理时间', value: 3200, type: 'time', trend: -5.2 },
    { name: '用户满意度', value: 0.875, type: 'percentage', trend: 3.1 }
]);
// 表单数据
const learningForm = (0, vue_1.reactive)({
    recordId: '',
    originalScore: 0,
    reviewedScore: 0,
    feedback: '',
    corrections: []
});
const knowledgeForm = (0, vue_1.reactive)({
    category: '',
    pattern: '',
    confidence: 0.8,
    metadata: ''
});
const settingsForm = (0, vue_1.reactive)({
    enableFeedbackLearning: true,
    enableContextualLearning: true,
    enablePatternRecognition: true,
    adaptiveScoring: true,
    personalizedRecommendations: true,
    learningFrequency: 'hourly'
});
// 表格列定义
const learningColumns = [
    { title: '记录ID', dataIndex: 'recordId', key: 'recordId' },
    { title: '原始评分', dataIndex: 'originalScore', key: 'originalScore' },
    { title: '修正评分', dataIndex: 'reviewedScore', key: 'reviewedScore' },
    { title: '改进幅度', key: 'improvement' },
    { title: '审核人', dataIndex: 'reviewerId', key: 'reviewerId' },
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp' },
    { title: '操作', key: 'actions' }
];
const knowledgeColumns = [
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '模式', dataIndex: 'pattern', key: 'pattern' },
    { title: '置信度', key: 'confidence' },
    { title: '使用情况', key: 'usage' },
    { title: '更新时间', dataIndex: 'lastUpdated', key: 'lastUpdated' },
    { title: '操作', key: 'actions' }
];
const tasksColumns = [
    { title: '任务类型', dataIndex: 'type', key: 'type' },
    { title: '状态', key: 'status' },
    { title: '优先级', key: 'priority' },
    { title: '创建时间', dataIndex: 'createdAt', key: 'createdAt' },
    { title: '描述', dataIndex: 'description', key: 'description' },
    { title: '操作', key: 'actions' }
];
const metricsColumns = [
    { title: '指标', dataIndex: 'name', key: 'name' },
    { title: '数值', key: 'value' },
    { title: '趋势', key: 'trend' }
];
// 分页配置
const paginationConfig = {
    pageSize: 10,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total) => `共 ${total} 条记录`
};
// 计算属性
const filteredKnowledgeBase = (0, vue_1.computed)(() => {
    if (!selectedCategory.value)
        return knowledgeBase.value;
    return knowledgeBase.value.filter(item => item.category === selectedCategory.value);
});
const filteredTasks = (0, vue_1.computed)(() => {
    if (!selectedTaskType.value)
        return learningTasks.value;
    return learningTasks.value.filter(task => task.type === selectedTaskType.value);
});
// 图表引用
const performanceChart = (0, vue_1.ref)();
const accuracyChart = (0, vue_1.ref)();
const timingChart = (0, vue_1.ref)();
const satisfactionChart = (0, vue_1.ref)();
// 方法
const refreshData = async () => {
    loading.value = true;
    try {
        // 模拟数据刷新
        await new Promise(resolve => setTimeout(resolve, 1000));
        ant_design_vue_1.message.success('数据刷新成功');
    }
    catch (error) {
        ant_design_vue_1.message.error('数据刷新失败');
    }
    finally {
        loading.value = false;
    }
};
const getPerformanceColor = (score) => {
    if (score >= 90)
        return '#52c41a';
    if (score >= 80)
        return '#faad14';
    return '#f5222d';
};
const getPerformanceStatus = (score) => {
    if (score >= 90)
        return 'success';
    if (score >= 80)
        return 'warning';
    return 'error';
};
const getPerformanceText = (score) => {
    if (score >= 90)
        return '优秀';
    if (score >= 80)
        return '良好';
    return '需改进';
};
const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8)
        return '#52c41a';
    if (confidence >= 0.6)
        return '#faad14';
    return '#f5222d';
};
const getTaskStatus = (status) => {
    const statusMap = {
        pending: 'default',
        running: 'processing',
        completed: 'success',
        failed: 'error'
    };
    return statusMap[status] || 'default';
};
const getTaskStatusText = (status) => {
    const textMap = {
        pending: '待处理',
        running: '运行中',
        completed: '已完成',
        failed: '失败'
    };
    return textMap[status] || status;
};
const getPriorityColor = (priority) => {
    const colorMap = {
        critical: 'red',
        high: 'orange',
        medium: 'blue',
        low: 'green'
    };
    return colorMap[priority] || 'default';
};
const getPriorityText = (priority) => {
    const textMap = {
        critical: '紧急',
        high: '高',
        medium: '中',
        low: '低'
    };
    return textMap[priority] || priority;
};
const getMetricPercent = (value: any,  type: any) => {
    if (type === 'percentage')
        return Math.round(value * 100);
    if (type === 'time')
        return Math.min(100, Math.max(0, 100 - (value - 1000) / 50));
    return Math.round(value * 100);
};
const getMetricColor = (value, type) => {
    const percent = getMetricPercent(value, type);
    if (percent >= 80)
        return '#52c41a';
    if (percent >= 60)
        return '#faad14';
    return '#f5222d';
};
const formatMetricValue = (value: any,  type: any) => {
    if (type === 'percentage')
        return `${Math.round(value * 100)}%`;
    if (type === 'time')
        return `${value}ms`;
    return value.toString();
};
// 学习记录相关方法
const submitLearningRecord = async () => {
    try {
        // 模拟提交学习记录
        console.log('提交学习记录:', learningForm);
        ant_design_vue_1.message.success('学习记录添加成功');
        showLearningDialog.value = false;
        resetLearningForm();
    }
    catch (error) {
        ant_design_vue_1.message.error('添加学习记录失败');
    }
};
const resetLearningForm = () => {
    Object.assign(learningForm, {
        recordId: '',
        originalScore: 0,
        reviewedScore: 0,
        feedback: '',
        corrections: []
    });
};
const viewLearningDetail = (record) => {
    console.log('查看学习详情:', record);
};
const analyzeLearningPattern = (record) => {
    console.log('分析学习模式:', record);
};
// 知识库相关方法
const submitKnowledgeEntry = async () => {
    try {
        // 模拟提交知识条目
        console.log('提交知识条目:', knowledgeForm);
        ant_design_vue_1.message.success('知识条目添加成功');
        showKnowledgeDialog.value = false;
        resetKnowledgeForm();
    }
    catch (error) {
        ant_design_vue_1.message.error('添加知识条目失败');
    }
};
const resetKnowledgeForm = () => {
    Object.assign(knowledgeForm, {
        category: '',
        pattern: '',
        confidence: 0.8,
        metadata: ''
    });
};
const filterKnowledgeBase = () => {
    // 过滤知识库已通过计算属性实现
};
const editKnowledgeEntry = (record) => {
    console.log('编辑知识条目:', record);
};
const testKnowledgeEntry = (record) => {
    console.log('测试知识条目:', record);
};
const deleteKnowledgeEntry = async (record) => {
    try {
        // 模拟删除知识条目
        console.log('删除知识条目:', record);
        ant_design_vue_1.message.success('知识条目删除成功');
    }
    catch (error) {
        ant_design_vue_1.message.error('删除知识条目失败');
    }
};
// 任务相关方法
const filterTasks = () => {
    // 过滤任务已通过计算属性实现
};
const createLearningTask = () => {
    console.log('创建学习任务');
};
const viewTaskDetail = (record) => {
    console.log('查看任务详情:', record);
};
const executeTask = async (record) => {
    try {
        // 模拟执行任务
        console.log('执行任务:', record);
        ant_design_vue_1.message.success('任务执行成功');
    }
    catch (error) {
        ant_design_vue_1.message.error('任务执行失败');
    }
};
const cancelTask = async (record) => {
    try {
        // 模拟取消任务
        console.log('取消任务:', record);
        ant_design_vue_1.message.success('任务取消成功');
    }
    catch (error) {
        ant_design_vue_1.message.error('任务取消失败');
    }
};
// 设置相关方法
const saveSettings = async () => {
    try {
        // 模拟保存设置
        console.log('保存设置:', settingsForm);
        ant_design_vue_1.message.success('设置保存成功');
        showSettings.value = false;
    }
    catch (error) {
        ant_design_vue_1.message.error('设置保存失败');
    }
};
const resetSettings = () => {
    // 重置设置表单
    Object.assign(settingsForm, {
        enableFeedbackLearning: true,
        enableContextualLearning: true,
        enablePatternRecognition: true,
        adaptiveScoring: true,
        personalizedRecommendations: true,
        learningFrequency: 'hourly'
    });
};
// 图表初始化
const initCharts = () => {
    (0, vue_1.nextTick)(() => {
        // 性能趋势图
        if (performanceChart.value) {
            const chart = echarts.init(performanceChart.value);
            chart.setOption({
                title: { text: '性能趋势', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: ['1月', '2月', '3月', '4月', '5月', '6月'] },
                yAxis: { type: 'value' },
                series: [{
                        name: '性能评分',
                        type: 'line',
                        data: [82, 85, 88, 87, 90, 88],
                        smooth: true
                    }]
            });
        }
        // 准确率分析图
        if (accuracyChart.value) {
            const chart = echarts.init(accuracyChart.value);
            chart.setOption({
                title: { text: '准确率分析', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'item' },
                series: [{
                        name: '准确率',
                        type: 'pie',
                        data: [
                            { value: 88.5, name: '准确识别' },
                            { value: 11.5, name: '误识别' }
                        ]
                    }]
            });
        }
        // 处理时间分析图
        if (timingChart.value) {
            const chart = echarts.init(timingChart.value);
            chart.setOption({
                title: { text: '处理时间分析', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: ['AI分析', '规则引擎', '结果合并', '后处理'] },
                yAxis: { type: 'value' },
                series: [{
                        name: '处理时间(ms)',
                        type: 'bar',
                        data: [3200, 800, 200, 100]
                    }]
            });
        }
        // 用户满意度图
        if (satisfactionChart.value) {
            const chart = echarts.init(satisfactionChart.value);
            chart.setOption({
                title: { text: '用户满意度', textStyle: { fontSize: 14 } },
                tooltip: { trigger: 'axis' },
                xAxis: { type: 'category', data: ['很满意', '满意', '一般', '不满意', '很不满意'] },
                yAxis: { type: 'value' },
                series: [{
                        name: '用户数量',
                        type: 'bar',
                        data: [45, 32, 15, 5, 3]
                    }]
            });
        }
    });
};
// 生命周期
(0, vue_1.onMounted)(() => {
    initCharts();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ai-enhancement-panel" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "AI增强功能管理",
    ...{ class: "mb-6" },
}));
const __VLS_2 = __VLS_1({
    title: "AI增强功能管理",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_4 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
    const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_7.slots.default;
    const __VLS_8 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_10 = __VLS_9({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    let __VLS_12;
    let __VLS_13;
    let __VLS_14;
    const __VLS_15 = {
        onClick: (__VLS_ctx.refreshData)
    };
    __VLS_11.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_11.slots;
        const __VLS_16 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
        const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
    }
    var __VLS_11;
    const __VLS_20 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        ...{ 'onClick': {} },
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_24;
    let __VLS_25;
    let __VLS_26;
    const __VLS_27 = {
        onClick: (...[$event]) => {
            __VLS_ctx.showSettings = true;
        }
    };
    __VLS_23.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_23.slots;
        const __VLS_28 = {}.SettingOutlined;
        /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
        const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
    }
    var __VLS_23;
    var __VLS_7;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6" },
});
const __VLS_32 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    size: "small",
    ...{ class: "stat-card" },
}));
const __VLS_34 = __VLS_33({
    size: "small",
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    title: "学习记录",
    value: (__VLS_ctx.stats.totalRecords),
    suffix: "条",
    valueStyle: ({ color: '#1890ff' }),
}));
const __VLS_38 = __VLS_37({
    title: "学习记录",
    value: (__VLS_ctx.stats.totalRecords),
    suffix: "条",
    valueStyle: ({ color: '#1890ff' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-2" },
});
const __VLS_40 = {}.AProgress;
/** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    percent: (__VLS_ctx.stats.learningProgress),
    size: "small",
}));
const __VLS_42 = __VLS_41({
    percent: (__VLS_ctx.stats.learningProgress),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
var __VLS_35;
const __VLS_44 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    size: "small",
    ...{ class: "stat-card" },
}));
const __VLS_46 = __VLS_45({
    size: "small",
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    title: "知识库条目",
    value: (__VLS_ctx.stats.knowledgeBaseSize),
    suffix: "个",
    valueStyle: ({ color: '#52c41a' }),
}));
const __VLS_50 = __VLS_49({
    title: "知识库条目",
    value: (__VLS_ctx.stats.knowledgeBaseSize),
    suffix: "个",
    valueStyle: ({ color: '#52c41a' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-2" },
});
const __VLS_52 = {}.ATag;
/** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    color: "green",
}));
const __VLS_54 = __VLS_53({
    color: "green",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
(__VLS_ctx.stats.activePatterns);
var __VLS_55;
var __VLS_47;
const __VLS_56 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    size: "small",
    ...{ class: "stat-card" },
}));
const __VLS_58 = __VLS_57({
    size: "small",
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    title: "性能评分",
    value: (__VLS_ctx.stats.performanceScore),
    suffix: "%",
    valueStyle: ({ color: __VLS_ctx.getPerformanceColor(__VLS_ctx.stats.performanceScore) }),
}));
const __VLS_62 = __VLS_61({
    title: "性能评分",
    value: (__VLS_ctx.stats.performanceScore),
    suffix: "%",
    valueStyle: ({ color: __VLS_ctx.getPerformanceColor(__VLS_ctx.stats.performanceScore) }),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-2" },
});
const __VLS_64 = {}.ABadge;
/** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    status: (__VLS_ctx.getPerformanceStatus(__VLS_ctx.stats.performanceScore)),
    text: (__VLS_ctx.getPerformanceText(__VLS_ctx.stats.performanceScore)),
}));
const __VLS_66 = __VLS_65({
    status: (__VLS_ctx.getPerformanceStatus(__VLS_ctx.stats.performanceScore)),
    text: (__VLS_ctx.getPerformanceText(__VLS_ctx.stats.performanceScore)),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
var __VLS_59;
const __VLS_68 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    size: "small",
    ...{ class: "stat-card" },
}));
const __VLS_70 = __VLS_69({
    size: "small",
    ...{ class: "stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    title: "学习任务",
    value: (__VLS_ctx.stats.pendingTasks),
    suffix: "个",
    valueStyle: ({ color: '#faad14' }),
}));
const __VLS_74 = __VLS_73({
    title: "学习任务",
    value: (__VLS_ctx.stats.pendingTasks),
    suffix: "个",
    valueStyle: ({ color: '#faad14' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-2" },
});
const __VLS_76 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({}));
const __VLS_78 = __VLS_77({}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
const __VLS_80 = {}.ATag;
/** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    color: "processing",
}));
const __VLS_82 = __VLS_81({
    color: "processing",
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
(__VLS_ctx.stats.runningTasks);
var __VLS_83;
const __VLS_84 = {}.ATag;
/** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    color: "success",
}));
const __VLS_86 = __VLS_85({
    color: "success",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
(__VLS_ctx.stats.completedTasks);
var __VLS_87;
var __VLS_79;
var __VLS_71;
const __VLS_88 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
}));
const __VLS_90 = __VLS_89({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
const __VLS_92 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    key: "learning",
    tab: "智能学习",
}));
const __VLS_94 = __VLS_93({
    key: "learning",
    tab: "智能学习",
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "learning-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold" },
});
const __VLS_96 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_98 = __VLS_97({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
let __VLS_100;
let __VLS_101;
let __VLS_102;
const __VLS_103 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showLearningDialog = true;
    }
};
__VLS_99.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_99.slots;
    const __VLS_104 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({}));
    const __VLS_106 = __VLS_105({}, ...__VLS_functionalComponentArgsRest(__VLS_105));
}
var __VLS_99;
const __VLS_108 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    columns: (__VLS_ctx.learningColumns),
    dataSource: (__VLS_ctx.learningRecords),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    size: "small",
}));
const __VLS_110 = __VLS_109({
    columns: (__VLS_ctx.learningColumns),
    dataSource: (__VLS_ctx.learningRecords),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_111.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'improvement') {
        const __VLS_112 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            color: (record.improvement > 0 ? 'green' : record.improvement < 0 ? 'red' : 'blue'),
        }));
        const __VLS_114 = __VLS_113({
            color: (record.improvement > 0 ? 'green' : record.improvement < 0 ? 'red' : 'blue'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        (record.improvement > 0 ? '+' : '');
        (record.improvement);
        var __VLS_115;
    }
    else if (column.key === 'actions') {
        const __VLS_116 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
        const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
        __VLS_119.slots.default;
        const __VLS_120 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_122 = __VLS_121({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        let __VLS_124;
        let __VLS_125;
        let __VLS_126;
        const __VLS_127 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'improvement'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.viewLearningDetail(record);
            }
        };
        __VLS_123.slots.default;
        var __VLS_123;
        const __VLS_128 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_130 = __VLS_129({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_129));
        let __VLS_132;
        let __VLS_133;
        let __VLS_134;
        const __VLS_135 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'improvement'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.analyzeLearningPattern(record);
            }
        };
        __VLS_131.slots.default;
        var __VLS_131;
        var __VLS_119;
    }
}
var __VLS_111;
var __VLS_95;
const __VLS_136 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    key: "knowledge",
    tab: "知识库",
}));
const __VLS_138 = __VLS_137({
    key: "knowledge",
    tab: "知识库",
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
__VLS_139.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "knowledge-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold" },
});
const __VLS_140 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({}));
const __VLS_142 = __VLS_141({}, ...__VLS_functionalComponentArgsRest(__VLS_141));
__VLS_143.slots.default;
const __VLS_144 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedCategory),
    placeholder: "选择类别",
    ...{ style: {} },
}));
const __VLS_146 = __VLS_145({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedCategory),
    placeholder: "选择类别",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_145));
let __VLS_148;
let __VLS_149;
let __VLS_150;
const __VLS_151 = {
    onChange: (__VLS_ctx.filterKnowledgeBase)
};
__VLS_147.slots.default;
const __VLS_152 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
    value: "",
}));
const __VLS_154 = __VLS_153({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_153));
__VLS_155.slots.default;
var __VLS_155;
const __VLS_156 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    value: "completeness",
}));
const __VLS_158 = __VLS_157({
    value: "completeness",
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
__VLS_159.slots.default;
var __VLS_159;
const __VLS_160 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
    value: "consistency",
}));
const __VLS_162 = __VLS_161({
    value: "consistency",
}, ...__VLS_functionalComponentArgsRest(__VLS_161));
__VLS_163.slots.default;
var __VLS_163;
const __VLS_164 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    value: "rationality",
}));
const __VLS_166 = __VLS_165({
    value: "rationality",
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
__VLS_167.slots.default;
var __VLS_167;
const __VLS_168 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    value: "timeliness",
}));
const __VLS_170 = __VLS_169({
    value: "timeliness",
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
var __VLS_171;
const __VLS_172 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    value: "compliance",
}));
const __VLS_174 = __VLS_173({
    value: "compliance",
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
__VLS_175.slots.default;
var __VLS_175;
var __VLS_147;
const __VLS_176 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_178 = __VLS_177({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_177));
let __VLS_180;
let __VLS_181;
let __VLS_182;
const __VLS_183 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showKnowledgeDialog = true;
    }
};
__VLS_179.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_179.slots;
    const __VLS_184 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({}));
    const __VLS_186 = __VLS_185({}, ...__VLS_functionalComponentArgsRest(__VLS_185));
}
var __VLS_179;
var __VLS_143;
const __VLS_188 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
    columns: (__VLS_ctx.knowledgeColumns),
    dataSource: (__VLS_ctx.filteredKnowledgeBase),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    size: "small",
}));
const __VLS_190 = __VLS_189({
    columns: (__VLS_ctx.knowledgeColumns),
    dataSource: (__VLS_ctx.filteredKnowledgeBase),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_189));
__VLS_191.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_191.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'confidence') {
        const __VLS_192 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
            percent: (Math.round(record.confidence * 100)),
            size: "small",
            strokeColor: (__VLS_ctx.getConfidenceColor(record.confidence)),
        }));
        const __VLS_194 = __VLS_193({
            percent: (Math.round(record.confidence * 100)),
            size: "small",
            strokeColor: (__VLS_ctx.getConfidenceColor(record.confidence)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_193));
    }
    else if (column.key === 'usage') {
        const __VLS_196 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({}));
        const __VLS_198 = __VLS_197({}, ...__VLS_functionalComponentArgsRest(__VLS_197));
        __VLS_199.slots.default;
        const __VLS_200 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
            color: "blue",
        }));
        const __VLS_202 = __VLS_201({
            color: "blue",
        }, ...__VLS_functionalComponentArgsRest(__VLS_201));
        __VLS_203.slots.default;
        (record.usageCount);
        var __VLS_203;
        const __VLS_204 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
            color: "green",
        }));
        const __VLS_206 = __VLS_205({
            color: "green",
        }, ...__VLS_functionalComponentArgsRest(__VLS_205));
        __VLS_207.slots.default;
        (Math.round(record.successRate * 100));
        var __VLS_207;
        var __VLS_199;
    }
    else if (column.key === 'actions') {
        const __VLS_208 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({}));
        const __VLS_210 = __VLS_209({}, ...__VLS_functionalComponentArgsRest(__VLS_209));
        __VLS_211.slots.default;
        const __VLS_212 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_214 = __VLS_213({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_213));
        let __VLS_216;
        let __VLS_217;
        let __VLS_218;
        const __VLS_219 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'confidence'))
                    return;
                if (!!(column.key === 'usage'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.editKnowledgeEntry(record);
            }
        };
        __VLS_215.slots.default;
        var __VLS_215;
        const __VLS_220 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_222 = __VLS_221({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_221));
        let __VLS_224;
        let __VLS_225;
        let __VLS_226;
        const __VLS_227 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'confidence'))
                    return;
                if (!!(column.key === 'usage'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.testKnowledgeEntry(record);
            }
        };
        __VLS_223.slots.default;
        var __VLS_223;
        const __VLS_228 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
            ...{ 'onConfirm': {} },
            title: "确定删除此知识条目吗？",
        }));
        const __VLS_230 = __VLS_229({
            ...{ 'onConfirm': {} },
            title: "确定删除此知识条目吗？",
        }, ...__VLS_functionalComponentArgsRest(__VLS_229));
        let __VLS_232;
        let __VLS_233;
        let __VLS_234;
        const __VLS_235 = {
            onConfirm: (...[$event]) => {
                if (!!(column.key === 'confidence'))
                    return;
                if (!!(column.key === 'usage'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.deleteKnowledgeEntry(record);
            }
        };
        __VLS_231.slots.default;
        const __VLS_236 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
            type: "link",
            size: "small",
            danger: true,
        }));
        const __VLS_238 = __VLS_237({
            type: "link",
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_237));
        __VLS_239.slots.default;
        var __VLS_239;
        var __VLS_231;
        var __VLS_211;
    }
}
var __VLS_191;
var __VLS_139;
const __VLS_240 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
    key: "performance",
    tab: "性能监控",
}));
const __VLS_242 = __VLS_241({
    key: "performance",
    tab: "性能监控",
}, ...__VLS_functionalComponentArgsRest(__VLS_241));
__VLS_243.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "performance-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 lg:grid-cols-2 gap-6" },
});
const __VLS_244 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
    title: "性能趋势",
    size: "small",
}));
const __VLS_246 = __VLS_245({
    title: "性能趋势",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_245));
__VLS_247.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "performanceChart",
    ...{ class: "h-64" },
});
/** @type {typeof __VLS_ctx.performanceChart} */ ;
var __VLS_247;
const __VLS_248 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
    title: "准确率分析",
    size: "small",
}));
const __VLS_250 = __VLS_249({
    title: "准确率分析",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_249));
__VLS_251.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "accuracyChart",
    ...{ class: "h-64" },
});
/** @type {typeof __VLS_ctx.accuracyChart} */ ;
var __VLS_251;
const __VLS_252 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({
    title: "处理时间分析",
    size: "small",
}));
const __VLS_254 = __VLS_253({
    title: "处理时间分析",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_253));
__VLS_255.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "timingChart",
    ...{ class: "h-64" },
});
/** @type {typeof __VLS_ctx.timingChart} */ ;
var __VLS_255;
const __VLS_256 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
    title: "用户满意度",
    size: "small",
}));
const __VLS_258 = __VLS_257({
    title: "用户满意度",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_257));
__VLS_259.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "satisfactionChart",
    ...{ class: "h-64" },
});
/** @type {typeof __VLS_ctx.satisfactionChart} */ ;
var __VLS_259;
const __VLS_260 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
    title: "详细指标",
    size: "small",
    ...{ class: "mt-6" },
}));
const __VLS_262 = __VLS_261({
    title: "详细指标",
    size: "small",
    ...{ class: "mt-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_261));
__VLS_263.slots.default;
const __VLS_264 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
    columns: (__VLS_ctx.metricsColumns),
    dataSource: (__VLS_ctx.performanceMetrics),
    pagination: (false),
    size: "small",
}));
const __VLS_266 = __VLS_265({
    columns: (__VLS_ctx.metricsColumns),
    dataSource: (__VLS_ctx.performanceMetrics),
    pagination: (false),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_265));
__VLS_267.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_267.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'value') {
        const __VLS_268 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
            percent: (__VLS_ctx.getMetricPercent(record.value, record.type)),
            size: "small",
            strokeColor: (__VLS_ctx.getMetricColor(record.value, record.type)),
        }));
        const __VLS_270 = __VLS_269({
            percent: (__VLS_ctx.getMetricPercent(record.value, record.type)),
            size: "small",
            strokeColor: (__VLS_ctx.getMetricColor(record.value, record.type)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_269));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "ml-2" },
        });
        (__VLS_ctx.formatMetricValue(record.value, record.type));
    }
    else if (column.key === 'trend') {
        const __VLS_272 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
            color: (record.trend > 0 ? 'green' : record.trend < 0 ? 'red' : 'blue'),
        }));
        const __VLS_274 = __VLS_273({
            color: (record.trend > 0 ? 'green' : record.trend < 0 ? 'red' : 'blue'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_273));
        __VLS_275.slots.default;
        (record.trend > 0 ? '↑' : record.trend < 0 ? '↓' : '→');
        (Math.abs(record.trend));
        var __VLS_275;
    }
}
var __VLS_267;
var __VLS_263;
var __VLS_243;
const __VLS_276 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({
    key: "tasks",
    tab: "学习任务",
}));
const __VLS_278 = __VLS_277({
    key: "tasks",
    tab: "学习任务",
}, ...__VLS_functionalComponentArgsRest(__VLS_277));
__VLS_279.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tasks-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold" },
});
const __VLS_280 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({}));
const __VLS_282 = __VLS_281({}, ...__VLS_functionalComponentArgsRest(__VLS_281));
__VLS_283.slots.default;
const __VLS_284 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedTaskType),
    placeholder: "任务类型",
    ...{ style: {} },
}));
const __VLS_286 = __VLS_285({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedTaskType),
    placeholder: "任务类型",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_285));
let __VLS_288;
let __VLS_289;
let __VLS_290;
const __VLS_291 = {
    onChange: (__VLS_ctx.filterTasks)
};
__VLS_287.slots.default;
const __VLS_292 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
    value: "",
}));
const __VLS_294 = __VLS_293({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_293));
__VLS_295.slots.default;
var __VLS_295;
const __VLS_296 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
    value: "feedback_learning",
}));
const __VLS_298 = __VLS_297({
    value: "feedback_learning",
}, ...__VLS_functionalComponentArgsRest(__VLS_297));
__VLS_299.slots.default;
var __VLS_299;
const __VLS_300 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({
    value: "pattern_recognition",
}));
const __VLS_302 = __VLS_301({
    value: "pattern_recognition",
}, ...__VLS_functionalComponentArgsRest(__VLS_301));
__VLS_303.slots.default;
var __VLS_303;
const __VLS_304 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
    value: "performance_optimization",
}));
const __VLS_306 = __VLS_305({
    value: "performance_optimization",
}, ...__VLS_functionalComponentArgsRest(__VLS_305));
__VLS_307.slots.default;
var __VLS_307;
var __VLS_287;
const __VLS_308 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_310 = __VLS_309({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_309));
let __VLS_312;
let __VLS_313;
let __VLS_314;
const __VLS_315 = {
    onClick: (__VLS_ctx.createLearningTask)
};
__VLS_311.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_311.slots;
    const __VLS_316 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({}));
    const __VLS_318 = __VLS_317({}, ...__VLS_functionalComponentArgsRest(__VLS_317));
}
var __VLS_311;
var __VLS_283;
const __VLS_320 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
    columns: (__VLS_ctx.tasksColumns),
    dataSource: (__VLS_ctx.filteredTasks),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    size: "small",
}));
const __VLS_322 = __VLS_321({
    columns: (__VLS_ctx.tasksColumns),
    dataSource: (__VLS_ctx.filteredTasks),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_321));
__VLS_323.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_323.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'status') {
        const __VLS_324 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_325 = __VLS_asFunctionalComponent(__VLS_324, new __VLS_324({
            status: (__VLS_ctx.getTaskStatus(record.status)),
            text: (__VLS_ctx.getTaskStatusText(record.status)),
        }));
        const __VLS_326 = __VLS_325({
            status: (__VLS_ctx.getTaskStatus(record.status)),
            text: (__VLS_ctx.getTaskStatusText(record.status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_325));
    }
    else if (column.key === 'priority') {
        const __VLS_328 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }));
        const __VLS_330 = __VLS_329({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_329));
        __VLS_331.slots.default;
        (__VLS_ctx.getPriorityText(record.priority));
        var __VLS_331;
    }
    else if (column.key === 'actions') {
        const __VLS_332 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({}));
        const __VLS_334 = __VLS_333({}, ...__VLS_functionalComponentArgsRest(__VLS_333));
        __VLS_335.slots.default;
        const __VLS_336 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_338 = __VLS_337({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_337));
        let __VLS_340;
        let __VLS_341;
        let __VLS_342;
        const __VLS_343 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'priority'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.viewTaskDetail(record);
            }
        };
        __VLS_339.slots.default;
        var __VLS_339;
        const __VLS_344 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            disabled: (record.status !== 'pending'),
        }));
        const __VLS_346 = __VLS_345({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            disabled: (record.status !== 'pending'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_345));
        let __VLS_348;
        let __VLS_349;
        let __VLS_350;
        const __VLS_351 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'priority'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.executeTask(record);
            }
        };
        __VLS_347.slots.default;
        var __VLS_347;
        const __VLS_352 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({
            ...{ 'onConfirm': {} },
            title: "确定取消此任务吗？",
        }));
        const __VLS_354 = __VLS_353({
            ...{ 'onConfirm': {} },
            title: "确定取消此任务吗？",
        }, ...__VLS_functionalComponentArgsRest(__VLS_353));
        let __VLS_356;
        let __VLS_357;
        let __VLS_358;
        const __VLS_359 = {
            onConfirm: (...[$event]) => {
                if (!!(column.key === 'status'))
                    return;
                if (!!(column.key === 'priority'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.cancelTask(record);
            }
        };
        __VLS_355.slots.default;
        const __VLS_360 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_361 = __VLS_asFunctionalComponent(__VLS_360, new __VLS_360({
            type: "link",
            size: "small",
            danger: true,
            disabled: (record.status !== 'pending'),
        }));
        const __VLS_362 = __VLS_361({
            type: "link",
            size: "small",
            danger: true,
            disabled: (record.status !== 'pending'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_361));
        __VLS_363.slots.default;
        var __VLS_363;
        var __VLS_355;
        var __VLS_335;
    }
}
var __VLS_323;
var __VLS_279;
var __VLS_91;
var __VLS_3;
const __VLS_364 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showLearningDialog),
    title: "添加学习记录",
}));
const __VLS_366 = __VLS_365({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showLearningDialog),
    title: "添加学习记录",
}, ...__VLS_functionalComponentArgsRest(__VLS_365));
let __VLS_368;
let __VLS_369;
let __VLS_370;
const __VLS_371 = {
    onOk: (__VLS_ctx.submitLearningRecord)
};
const __VLS_372 = {
    onCancel: (__VLS_ctx.resetLearningForm)
};
__VLS_367.slots.default;
const __VLS_373 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_374 = __VLS_asFunctionalComponent(__VLS_373, new __VLS_373({
    model: (__VLS_ctx.learningForm),
    layout: "vertical",
}));
const __VLS_375 = __VLS_374({
    model: (__VLS_ctx.learningForm),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_374));
__VLS_376.slots.default;
const __VLS_377 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_378 = __VLS_asFunctionalComponent(__VLS_377, new __VLS_377({
    label: "病案记录ID",
    required: true,
}));
const __VLS_379 = __VLS_378({
    label: "病案记录ID",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_378));
__VLS_380.slots.default;
const __VLS_381 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_382 = __VLS_asFunctionalComponent(__VLS_381, new __VLS_381({
    value: (__VLS_ctx.learningForm.recordId),
    placeholder: "请输入病案记录ID",
}));
const __VLS_383 = __VLS_382({
    value: (__VLS_ctx.learningForm.recordId),
    placeholder: "请输入病案记录ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_382));
var __VLS_380;
const __VLS_385 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_386 = __VLS_asFunctionalComponent(__VLS_385, new __VLS_385({
    label: "原始评分",
    required: true,
}));
const __VLS_387 = __VLS_386({
    label: "原始评分",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_386));
__VLS_388.slots.default;
const __VLS_389 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_390 = __VLS_asFunctionalComponent(__VLS_389, new __VLS_389({
    value: (__VLS_ctx.learningForm.originalScore),
    min: (0),
    max: (100),
    ...{ style: {} },
}));
const __VLS_391 = __VLS_390({
    value: (__VLS_ctx.learningForm.originalScore),
    min: (0),
    max: (100),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_390));
var __VLS_388;
const __VLS_393 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_394 = __VLS_asFunctionalComponent(__VLS_393, new __VLS_393({
    label: "修正评分",
    required: true,
}));
const __VLS_395 = __VLS_394({
    label: "修正评分",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_394));
__VLS_396.slots.default;
const __VLS_397 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_398 = __VLS_asFunctionalComponent(__VLS_397, new __VLS_397({
    value: (__VLS_ctx.learningForm.reviewedScore),
    min: (0),
    max: (100),
    ...{ style: {} },
}));
const __VLS_399 = __VLS_398({
    value: (__VLS_ctx.learningForm.reviewedScore),
    min: (0),
    max: (100),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_398));
var __VLS_396;
const __VLS_401 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_402 = __VLS_asFunctionalComponent(__VLS_401, new __VLS_401({
    label: "反馈内容",
}));
const __VLS_403 = __VLS_402({
    label: "反馈内容",
}, ...__VLS_functionalComponentArgsRest(__VLS_402));
__VLS_404.slots.default;
const __VLS_405 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_406 = __VLS_asFunctionalComponent(__VLS_405, new __VLS_405({
    value: (__VLS_ctx.learningForm.feedback),
    placeholder: "请输入反馈内容",
    rows: (4),
}));
const __VLS_407 = __VLS_406({
    value: (__VLS_ctx.learningForm.feedback),
    placeholder: "请输入反馈内容",
    rows: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_406));
var __VLS_404;
const __VLS_409 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_410 = __VLS_asFunctionalComponent(__VLS_409, new __VLS_409({
    label: "纠正项目",
}));
const __VLS_411 = __VLS_410({
    label: "纠正项目",
}, ...__VLS_functionalComponentArgsRest(__VLS_410));
__VLS_412.slots.default;
const __VLS_413 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_414 = __VLS_asFunctionalComponent(__VLS_413, new __VLS_413({
    value: (__VLS_ctx.learningForm.corrections),
    mode: "tags",
    placeholder: "选择或输入纠正项目",
    ...{ style: {} },
}));
const __VLS_415 = __VLS_414({
    value: (__VLS_ctx.learningForm.corrections),
    mode: "tags",
    placeholder: "选择或输入纠正项目",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_414));
__VLS_416.slots.default;
const __VLS_417 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_418 = __VLS_asFunctionalComponent(__VLS_417, new __VLS_417({
    value: "评分调整",
}));
const __VLS_419 = __VLS_418({
    value: "评分调整",
}, ...__VLS_functionalComponentArgsRest(__VLS_418));
__VLS_420.slots.default;
var __VLS_420;
const __VLS_421 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_422 = __VLS_asFunctionalComponent(__VLS_421, new __VLS_421({
    value: "问题识别",
}));
const __VLS_423 = __VLS_422({
    value: "问题识别",
}, ...__VLS_functionalComponentArgsRest(__VLS_422));
__VLS_424.slots.default;
var __VLS_424;
const __VLS_425 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_426 = __VLS_asFunctionalComponent(__VLS_425, new __VLS_425({
    value: "建议优化",
}));
const __VLS_427 = __VLS_426({
    value: "建议优化",
}, ...__VLS_functionalComponentArgsRest(__VLS_426));
__VLS_428.slots.default;
var __VLS_428;
var __VLS_416;
var __VLS_412;
var __VLS_376;
var __VLS_367;
const __VLS_429 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_430 = __VLS_asFunctionalComponent(__VLS_429, new __VLS_429({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showKnowledgeDialog),
    title: "添加知识条目",
}));
const __VLS_431 = __VLS_430({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showKnowledgeDialog),
    title: "添加知识条目",
}, ...__VLS_functionalComponentArgsRest(__VLS_430));
let __VLS_433;
let __VLS_434;
let __VLS_435;
const __VLS_436 = {
    onOk: (__VLS_ctx.submitKnowledgeEntry)
};
const __VLS_437 = {
    onCancel: (__VLS_ctx.resetKnowledgeForm)
};
__VLS_432.slots.default;
const __VLS_438 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_439 = __VLS_asFunctionalComponent(__VLS_438, new __VLS_438({
    model: (__VLS_ctx.knowledgeForm),
    layout: "vertical",
}));
const __VLS_440 = __VLS_439({
    model: (__VLS_ctx.knowledgeForm),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_439));
__VLS_441.slots.default;
const __VLS_442 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_443 = __VLS_asFunctionalComponent(__VLS_442, new __VLS_442({
    label: "类别",
    required: true,
}));
const __VLS_444 = __VLS_443({
    label: "类别",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_443));
__VLS_445.slots.default;
const __VLS_446 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_447 = __VLS_asFunctionalComponent(__VLS_446, new __VLS_446({
    value: (__VLS_ctx.knowledgeForm.category),
    placeholder: "选择类别",
}));
const __VLS_448 = __VLS_447({
    value: (__VLS_ctx.knowledgeForm.category),
    placeholder: "选择类别",
}, ...__VLS_functionalComponentArgsRest(__VLS_447));
__VLS_449.slots.default;
const __VLS_450 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_451 = __VLS_asFunctionalComponent(__VLS_450, new __VLS_450({
    value: "completeness",
}));
const __VLS_452 = __VLS_451({
    value: "completeness",
}, ...__VLS_functionalComponentArgsRest(__VLS_451));
__VLS_453.slots.default;
var __VLS_453;
const __VLS_454 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_455 = __VLS_asFunctionalComponent(__VLS_454, new __VLS_454({
    value: "consistency",
}));
const __VLS_456 = __VLS_455({
    value: "consistency",
}, ...__VLS_functionalComponentArgsRest(__VLS_455));
__VLS_457.slots.default;
var __VLS_457;
const __VLS_458 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_459 = __VLS_asFunctionalComponent(__VLS_458, new __VLS_458({
    value: "rationality",
}));
const __VLS_460 = __VLS_459({
    value: "rationality",
}, ...__VLS_functionalComponentArgsRest(__VLS_459));
__VLS_461.slots.default;
var __VLS_461;
const __VLS_462 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_463 = __VLS_asFunctionalComponent(__VLS_462, new __VLS_462({
    value: "timeliness",
}));
const __VLS_464 = __VLS_463({
    value: "timeliness",
}, ...__VLS_functionalComponentArgsRest(__VLS_463));
__VLS_465.slots.default;
var __VLS_465;
const __VLS_466 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_467 = __VLS_asFunctionalComponent(__VLS_466, new __VLS_466({
    value: "compliance",
}));
const __VLS_468 = __VLS_467({
    value: "compliance",
}, ...__VLS_functionalComponentArgsRest(__VLS_467));
__VLS_469.slots.default;
var __VLS_469;
var __VLS_449;
var __VLS_445;
const __VLS_470 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_471 = __VLS_asFunctionalComponent(__VLS_470, new __VLS_470({
    label: "模式描述",
    required: true,
}));
const __VLS_472 = __VLS_471({
    label: "模式描述",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_471));
__VLS_473.slots.default;
const __VLS_474 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_475 = __VLS_asFunctionalComponent(__VLS_474, new __VLS_474({
    value: (__VLS_ctx.knowledgeForm.pattern),
    placeholder: "请输入模式描述",
    rows: (4),
}));
const __VLS_476 = __VLS_475({
    value: (__VLS_ctx.knowledgeForm.pattern),
    placeholder: "请输入模式描述",
    rows: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_475));
var __VLS_473;
const __VLS_478 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_479 = __VLS_asFunctionalComponent(__VLS_478, new __VLS_478({
    label: "置信度",
    required: true,
}));
const __VLS_480 = __VLS_479({
    label: "置信度",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_479));
__VLS_481.slots.default;
const __VLS_482 = {}.ASlider;
/** @type {[typeof __VLS_components.ASlider, typeof __VLS_components.aSlider, ]} */ ;
// @ts-ignore
const __VLS_483 = __VLS_asFunctionalComponent(__VLS_482, new __VLS_482({
    value: (__VLS_ctx.knowledgeForm.confidence),
    min: (0),
    max: (1),
    step: (0.1),
    marks: ({ 0: '0%', 0.5: '50%', 1: '100%' }),
}));
const __VLS_484 = __VLS_483({
    value: (__VLS_ctx.knowledgeForm.confidence),
    min: (0),
    max: (1),
    step: (0.1),
    marks: ({ 0: '0%', 0.5: '50%', 1: '100%' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_483));
var __VLS_481;
const __VLS_486 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_487 = __VLS_asFunctionalComponent(__VLS_486, new __VLS_486({
    label: "元数据",
}));
const __VLS_488 = __VLS_487({
    label: "元数据",
}, ...__VLS_functionalComponentArgsRest(__VLS_487));
__VLS_489.slots.default;
const __VLS_490 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_491 = __VLS_asFunctionalComponent(__VLS_490, new __VLS_490({
    value: (__VLS_ctx.knowledgeForm.metadata),
    placeholder: "请输入JSON格式的元数据",
    rows: (3),
}));
const __VLS_492 = __VLS_491({
    value: (__VLS_ctx.knowledgeForm.metadata),
    placeholder: "请输入JSON格式的元数据",
    rows: (3),
}, ...__VLS_functionalComponentArgsRest(__VLS_491));
var __VLS_489;
var __VLS_441;
var __VLS_432;
const __VLS_494 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_495 = __VLS_asFunctionalComponent(__VLS_494, new __VLS_494({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showSettings),
    title: "AI增强功能设置",
}));
const __VLS_496 = __VLS_495({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showSettings),
    title: "AI增强功能设置",
}, ...__VLS_functionalComponentArgsRest(__VLS_495));
let __VLS_498;
let __VLS_499;
let __VLS_500;
const __VLS_501 = {
    onOk: (__VLS_ctx.saveSettings)
};
const __VLS_502 = {
    onCancel: (__VLS_ctx.resetSettings)
};
__VLS_497.slots.default;
const __VLS_503 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_504 = __VLS_asFunctionalComponent(__VLS_503, new __VLS_503({
    model: (__VLS_ctx.settingsForm),
    layout: "vertical",
}));
const __VLS_505 = __VLS_504({
    model: (__VLS_ctx.settingsForm),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_504));
__VLS_506.slots.default;
const __VLS_507 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_508 = __VLS_asFunctionalComponent(__VLS_507, new __VLS_507({
    label: "反馈学习",
}));
const __VLS_509 = __VLS_508({
    label: "反馈学习",
}, ...__VLS_functionalComponentArgsRest(__VLS_508));
__VLS_510.slots.default;
const __VLS_511 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_512 = __VLS_asFunctionalComponent(__VLS_511, new __VLS_511({
    checked: (__VLS_ctx.settingsForm.enableFeedbackLearning),
}));
const __VLS_513 = __VLS_512({
    checked: (__VLS_ctx.settingsForm.enableFeedbackLearning),
}, ...__VLS_functionalComponentArgsRest(__VLS_512));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_510;
const __VLS_515 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_516 = __VLS_asFunctionalComponent(__VLS_515, new __VLS_515({
    label: "上下文学习",
}));
const __VLS_517 = __VLS_516({
    label: "上下文学习",
}, ...__VLS_functionalComponentArgsRest(__VLS_516));
__VLS_518.slots.default;
const __VLS_519 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_520 = __VLS_asFunctionalComponent(__VLS_519, new __VLS_519({
    checked: (__VLS_ctx.settingsForm.enableContextualLearning),
}));
const __VLS_521 = __VLS_520({
    checked: (__VLS_ctx.settingsForm.enableContextualLearning),
}, ...__VLS_functionalComponentArgsRest(__VLS_520));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_518;
const __VLS_523 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_524 = __VLS_asFunctionalComponent(__VLS_523, new __VLS_523({
    label: "模式识别",
}));
const __VLS_525 = __VLS_524({
    label: "模式识别",
}, ...__VLS_functionalComponentArgsRest(__VLS_524));
__VLS_526.slots.default;
const __VLS_527 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_528 = __VLS_asFunctionalComponent(__VLS_527, new __VLS_527({
    checked: (__VLS_ctx.settingsForm.enablePatternRecognition),
}));
const __VLS_529 = __VLS_528({
    checked: (__VLS_ctx.settingsForm.enablePatternRecognition),
}, ...__VLS_functionalComponentArgsRest(__VLS_528));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_526;
const __VLS_531 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_532 = __VLS_asFunctionalComponent(__VLS_531, new __VLS_531({
    label: "自适应评分",
}));
const __VLS_533 = __VLS_532({
    label: "自适应评分",
}, ...__VLS_functionalComponentArgsRest(__VLS_532));
__VLS_534.slots.default;
const __VLS_535 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_536 = __VLS_asFunctionalComponent(__VLS_535, new __VLS_535({
    checked: (__VLS_ctx.settingsForm.adaptiveScoring),
}));
const __VLS_537 = __VLS_536({
    checked: (__VLS_ctx.settingsForm.adaptiveScoring),
}, ...__VLS_functionalComponentArgsRest(__VLS_536));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_534;
const __VLS_539 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_540 = __VLS_asFunctionalComponent(__VLS_539, new __VLS_539({
    label: "个性化建议",
}));
const __VLS_541 = __VLS_540({
    label: "个性化建议",
}, ...__VLS_functionalComponentArgsRest(__VLS_540));
__VLS_542.slots.default;
const __VLS_543 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_544 = __VLS_asFunctionalComponent(__VLS_543, new __VLS_543({
    checked: (__VLS_ctx.settingsForm.personalizedRecommendations),
}));
const __VLS_545 = __VLS_544({
    checked: (__VLS_ctx.settingsForm.personalizedRecommendations),
}, ...__VLS_functionalComponentArgsRest(__VLS_544));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_542;
const __VLS_547 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_548 = __VLS_asFunctionalComponent(__VLS_547, new __VLS_547({
    label: "学习频率",
}));
const __VLS_549 = __VLS_548({
    label: "学习频率",
}, ...__VLS_functionalComponentArgsRest(__VLS_548));
__VLS_550.slots.default;
const __VLS_551 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_552 = __VLS_asFunctionalComponent(__VLS_551, new __VLS_551({
    value: (__VLS_ctx.settingsForm.learningFrequency),
}));
const __VLS_553 = __VLS_552({
    value: (__VLS_ctx.settingsForm.learningFrequency),
}, ...__VLS_functionalComponentArgsRest(__VLS_552));
__VLS_554.slots.default;
const __VLS_555 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_556 = __VLS_asFunctionalComponent(__VLS_555, new __VLS_555({
    value: "realtime",
}));
const __VLS_557 = __VLS_556({
    value: "realtime",
}, ...__VLS_functionalComponentArgsRest(__VLS_556));
__VLS_558.slots.default;
var __VLS_558;
const __VLS_559 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_560 = __VLS_asFunctionalComponent(__VLS_559, new __VLS_559({
    value: "hourly",
}));
const __VLS_561 = __VLS_560({
    value: "hourly",
}, ...__VLS_functionalComponentArgsRest(__VLS_560));
__VLS_562.slots.default;
var __VLS_562;
const __VLS_563 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_564 = __VLS_asFunctionalComponent(__VLS_563, new __VLS_563({
    value: "daily",
}));
const __VLS_565 = __VLS_564({
    value: "daily",
}, ...__VLS_functionalComponentArgsRest(__VLS_564));
__VLS_566.slots.default;
var __VLS_566;
const __VLS_567 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_568 = __VLS_asFunctionalComponent(__VLS_567, new __VLS_567({
    value: "weekly",
}));
const __VLS_569 = __VLS_568({
    value: "weekly",
}, ...__VLS_functionalComponentArgsRest(__VLS_568));
__VLS_570.slots.default;
var __VLS_570;
var __VLS_554;
var __VLS_550;
var __VLS_506;
var __VLS_497;
/** @type {__VLS_StyleScopedClasses['ai-enhancement-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['learning-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['knowledge-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['performance-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-64']} */ ;
/** @type {__VLS_StyleScopedClasses['h-64']} */ ;
/** @type {__VLS_StyleScopedClasses['h-64']} */ ;
/** @type {__VLS_StyleScopedClasses['h-64']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['tasks-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            loading: loading,
            activeTab: activeTab,
            showLearningDialog: showLearningDialog,
            showKnowledgeDialog: showKnowledgeDialog,
            showSettings: showSettings,
            selectedCategory: selectedCategory,
            selectedTaskType: selectedTaskType,
            stats: stats,
            learningRecords: learningRecords,
            performanceMetrics: performanceMetrics,
            learningForm: learningForm,
            knowledgeForm: knowledgeForm,
            settingsForm: settingsForm,
            learningColumns: learningColumns,
            knowledgeColumns: knowledgeColumns,
            tasksColumns: tasksColumns,
            metricsColumns: metricsColumns,
            paginationConfig: paginationConfig,
            filteredKnowledgeBase: filteredKnowledgeBase,
            filteredTasks: filteredTasks,
            performanceChart: performanceChart,
            accuracyChart: accuracyChart,
            timingChart: timingChart,
            satisfactionChart: satisfactionChart,
            refreshData: refreshData,
            getPerformanceColor: getPerformanceColor,
            getPerformanceStatus: getPerformanceStatus,
            getPerformanceText: getPerformanceText,
            getConfidenceColor: getConfidenceColor,
            getTaskStatus: getTaskStatus,
            getTaskStatusText: getTaskStatusText,
            getPriorityColor: getPriorityColor,
            getPriorityText: getPriorityText,
            getMetricPercent: getMetricPercent,
            getMetricColor: getMetricColor,
            formatMetricValue: formatMetricValue,
            submitLearningRecord: submitLearningRecord,
            resetLearningForm: resetLearningForm,
            viewLearningDetail: viewLearningDetail,
            analyzeLearningPattern: analyzeLearningPattern,
            submitKnowledgeEntry: submitKnowledgeEntry,
            resetKnowledgeForm: resetKnowledgeForm,
            filterKnowledgeBase: filterKnowledgeBase,
            editKnowledgeEntry: editKnowledgeEntry,
            testKnowledgeEntry: testKnowledgeEntry,
            deleteKnowledgeEntry: deleteKnowledgeEntry,
            filterTasks: filterTasks,
            createLearningTask: createLearningTask,
            viewTaskDetail: viewTaskDetail,
            executeTask: executeTask,
            cancelTask: cancelTask,
            saveSettings: saveSettings,
            resetSettings: resetSettings,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
