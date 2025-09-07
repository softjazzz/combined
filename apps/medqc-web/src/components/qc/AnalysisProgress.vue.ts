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
const props = withDefaults(defineProps(), {
    autoStart: false
});
const emit = defineEmits();
// 状态
const status = (0, vue_1.ref)('idle');
const currentStep = (0, vue_1.ref)(0);
const totalSteps = (0, vue_1.ref)(5);
const overallProgress = (0, vue_1.ref)(0);
const processedRecords = (0, vue_1.ref)(0);
const totalRecords = (0, vue_1.ref)(100);
const completedAnalyses = (0, vue_1.ref)(0);
const foundIssues = (0, vue_1.ref)(0);
const autoScroll = (0, vue_1.ref)(true);
const logContainer = (0, vue_1.ref)();
// 分析步骤
const analysisSteps = (0, vue_1.ref)([
    {
        id: '1',
        name: '数据预处理',
        description: '清理和标准化病案数据，准备分析环境',
        status: 'pending',
        progress: 0,
        current_task: '',
        duration: 0,
        details: null,
        error: ''
    },
    {
        id: '2',
        name: '规则引擎初始化',
        description: '加载质控规则，初始化分析引擎',
        status: 'pending',
        progress: 0,
        current_task: '',
        duration: 0,
        details: null,
        error: ''
    },
    {
        id: '3',
        name: 'AI模型分析',
        description: '使用大语言模型进行深度质控分析',
        status: 'pending',
        progress: 0,
        current_task: '',
        duration: 0,
        details: null,
        error: ''
    },
    {
        id: '4',
        name: '问题识别与分类',
        description: '识别质控问题并进行严重程度分类',
        status: 'pending',
        progress: 0,
        current_task: '',
        duration: 0,
        details: null,
        error: ''
    },
    {
        id: '5',
        name: '生成分析报告',
        description: '生成详细的质控分析报告和改进建议',
        status: 'pending',
        progress: 0,
        current_task: '',
        duration: 0,
        details: null,
        error: ''
    }
]);
// 日志
const logs = (0, vue_1.ref)(: any[]);
// 定时器
let progressTimer = null;
let logTimer = null;
// 计算属性
const isAnalyzing = (0, vue_1.computed)(() => status.value === 'running');
// 方法
const startAnalysis = () => {
    status.value = 'running';
    currentStep.value = 1;
    overallProgress.value = 0;
    // 重置步骤状态
    analysisSteps.value.forEach(step => {
        step.status = 'pending';
        step.progress = 0;
        step.current_task = '';
        step.duration = 0;
        step.details = null;
        step.error = '';
    });
    addLog('info', '开始质控分析...');
    simulateAnalysis();
};
const simulateAnalysis = () => {
    let stepIndex = 0;
    const processStep = () => {
        if (stepIndex >= analysisSteps.value.length) {
            // 分析完成
            status.value = 'completed';
            overallProgress.value = 100;
            addLog('info', '质控分析完成');
            emit('analysis-completed', { /* 分析结果 */});
            return;
        }
        const step = analysisSteps.value[stepIndex];
        step.status = 'running';
        currentStep.value = stepIndex + 1;
        addLog('info', `开始执行: ${step.name}`);
        // 模拟步骤进度
        let progress = 0;
        const stepTimer = setInterval(() => {
            if (status.value !== 'running') {
                clearInterval(stepTimer);
                return;
            }
            progress += Math.random() * 15;
            if (progress > 100)
                progress = 100;
            step.progress = Math.floor(progress);
            step.current_task = getRandomTask(step.name);
            // 更新总体进度
            const completedSteps = stepIndex;
            const currentStepProgress = progress / 100;
            overallProgress.value = Math.floor(((completedSteps + currentStepProgress) / totalSteps.value) * 100);
            // 更新统计数据
            processedRecords.value = Math.floor((overallProgress.value / 100) * totalRecords.value);
            completedAnalyses.value = Math.floor(processedRecords.value * 0.8);
            foundIssues.value = Math.floor(processedRecords.value * 0.15);
            // 添加随机日志
            if (Math.random() < 0.3) {
                addLog('debug', `${step.name}: ${step.current_task}`);
            }
            if (progress >= 100) {
                clearInterval(stepTimer);
                step.status = 'completed';
                step.duration = Math.floor(Math.random() * 30) + 10;
                step.details = {
                    processed: Math.floor(Math.random() * 50) + 20,
                    errors: Math.floor(Math.random() * 3),
                    warnings: Math.floor(Math.random() * 8),
                    time_remaining: `${Math.floor(Math.random() * 5) + 1}分钟`
                };
                addLog('info', `完成: ${step.name} (${step.duration}秒)`);
                stepIndex++;
                setTimeout(processStep, 1000);
            }
        }, 500);
    };
    processStep();
};
const getRandomTask = (stepName) => {
    const tasks = {
        '数据预处理': [
            '清理文本格式...',
            '标准化医学术语...',
            '验证数据完整性...',
            '构建分析索引...'
        ],
        '规则引擎初始化': [
            '加载质控规则库...',
            '编译规则表达式...',
            '初始化评分权重...',
            '验证规则完整性...'
        ],
        'AI模型分析': [
            '调用大语言模型...',
            '分析病案语义...',
            '识别关键信息...',
            '计算相似度得分...'
        ],
        '问题识别与分类': [
            '检测质控问题...',
            '分析问题严重程度...',
            '归类问题类型...',
            '生成问题报告...'
        ],
        '生成分析报告': [
            '汇总分析结果...',
            '生成改进建议...',
            '格式化报告内容...',
            '保存分析数据...'
        ]
    };
    const stepTasks = tasks[stepName] || ['处理中...'];
    return stepTasks[Math.floor(Math.random() * stepTasks.length)];
};
const addLog = (level, message) => {
    logs.value.push({
        timestamp: new Date(),
        level,
        message
    });
    // 限制日志数量
    if (logs.value.length > 100) {
        logs.value.shift();
    }
    // 自动滚动到底部
    if (autoScroll.value) {
        (0, vue_1.nextTick)(() => {
            if (logContainer.value) {
                logContainer.value.scrollTop = logContainer.value.scrollHeight;
            }
        });
    }
};
const pauseAnalysis = () => {
    status.value = 'paused';
    addLog('warn', '分析已暂停');
    emit('analysis-paused');
};
const resumeAnalysis = () => {
    status.value = 'running';
    addLog('info', '分析已恢复');
    emit('analysis-resumed');
};
const stopAnalysis = () => {
    status.value = 'idle';
    addLog('warn', '分析已停止');
    emit('analysis-stopped');
};
const restartAnalysis = () => {
    logs.value = [];
    startAnalysis();
};
const clearLogs = () => {
    logs.value = [];
};
// 样式相关方法
const getStatusColor = (status) => {
    const colors = {
        idle: 'text-slate-400',
        running: 'text-blue-400',
        paused: 'text-amber-400',
        completed: 'text-emerald-400',
        failed: 'text-red-400'
    };
    return colors[status] || 'text-slate-400';
};
const getStatusLabel = (status) => {
    const labels = {
        idle: '待开始',
        running: '分析中',
        paused: '已暂停',
        completed: '已完成',
        failed: '分析失败'
    };
    return labels[status] || status;
};
const getProgressColor = (status) => {
    const colors = {
        idle: '#64748b',
        running: '#3b82f6',
        paused: '#f59e0b',
        completed: '#10b981',
        failed: '#ef4444'
    };
    return colors[status] || '#64748b';
};
const getStepCardClass = (stepStatus: any,  index: any) => {
    if (stepStatus === 'running') {
        return 'border-blue-500/50 bg-blue-500/10';
    }
    else if (stepStatus === 'completed') {
        return 'border-emerald-500/30 bg-emerald-500/5';
    }
    else if (stepStatus === 'failed') {
        return 'border-red-500/30 bg-red-500/5';
    }
    else if (index < currentStep.value - 1) {
        return 'border-slate-600/30 bg-slate-700/20';
    }
    return 'border-slate-600/20 bg-slate-700/10';
};
const getStepIconClass = (stepStatus, index) => {
    if (stepStatus === 'running') {
        return 'bg-blue-500/20 text-blue-400 border border-blue-500/30';
    }
    else if (stepStatus === 'completed') {
        return 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30';
    }
    else if (stepStatus === 'failed') {
        return 'bg-red-500/20 text-red-400 border border-red-500/30';
    }
    return 'bg-slate-600/20 text-slate-400 border border-slate-600/30';
};
const getStepIcon = (stepStatus) => {
    const icons = {
        pending: icons_vue_1.ClockCircleOutlined,
        running: icons_vue_1.LoadingOutlined,
        completed: icons_vue_1.CheckOutlined,
        failed: icons_vue_1.CloseOutlined
    };
    return icons[stepStatus] || icons_vue_1.ClockCircleOutlined;
};
const getStepStatusColor = (stepStatus) => {
    const colors = {
        pending: 'default',
        running: 'blue',
        completed: 'green',
        failed: 'red'
    };
    return colors[stepStatus] || 'default';
};
const getStepStatusLabel = (stepStatus) => {
    const labels = {
        pending: '等待中',
        running: '执行中',
        completed: '已完成',
        failed: '失败'
    };
    return labels[stepStatus] || stepStatus;
};
const getStepProgressColor = (stepStatus) => {
    return stepStatus === 'completed' ? '#10b981' : '#3b82f6';
};
const getLogLevelClass = (level) => {
    const classes = {
        info: 'text-slate-300',
        warn: 'text-amber-300',
        error: 'text-red-300',
        debug: 'text-slate-400'
    };
    return classes[level] || 'text-slate-300';
};
const getLogLevelColor = (level) => {
    const colors = {
        info: 'text-blue-400',
        warn: 'text-amber-400',
        error: 'text-red-400',
        debug: 'text-slate-500'
    };
    return colors[level] || 'text-slate-400';
};
const formatDuration = (seconds) => {
    if (seconds < 60) {
        return `${seconds}秒`;
    }
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}分${remainingSeconds}秒`;
};
const formatTime = (timestamp) => {
    return timestamp.toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};
// 生命周期
(0, vue_1.onMounted)(() => {
    if (props.autoStart) {
        startAnalysis();
    }
});
(0, vue_1.onUnmounted)(() => {
    if (progressTimer) {
        clearInterval(progressTimer);
    }
    if (logTimer) {
        clearInterval(logTimer);
    }
});
// 暴露方法
const __VLS_exposed = {
    startAnalysis,
    pauseAnalysis,
    resumeAnalysis,
    stopAnalysis,
    restartAnalysis
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    autoStart: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "analysis-progress" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2" },
});
const __VLS_0 = {}.ThunderboltOutlined;
/** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-amber-400" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-amber-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-slate-400" },
});
(__VLS_ctx.currentStep);
(__VLS_ctx.totalSteps);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm font-medium" },
    ...{ class: (__VLS_ctx.getStatusColor(__VLS_ctx.status)) },
});
(__VLS_ctx.getStatusLabel(__VLS_ctx.status));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm text-slate-300" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm font-medium text-slate-200" },
});
(__VLS_ctx.overallProgress);
const __VLS_4 = {}.AProgress;
/** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    percent: (__VLS_ctx.overallProgress),
    showInfo: (false),
    strokeColor: (__VLS_ctx.getProgressColor(__VLS_ctx.status)),
    strokeWidth: "8",
    ...{ class: "overall-progress" },
}));
const __VLS_6 = __VLS_5({
    percent: (__VLS_ctx.overallProgress),
    showInfo: (false),
    strokeColor: (__VLS_ctx.getProgressColor(__VLS_ctx.status)),
    strokeWidth: "8",
    ...{ class: "overall-progress" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 md:grid-cols-4 gap-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center p-3 rounded-lg bg-slate-700/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg font-bold text-blue-400" },
});
(__VLS_ctx.processedRecords);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center p-3 rounded-lg bg-slate-700/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg font-bold text-amber-400" },
});
(__VLS_ctx.totalRecords);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center p-3 rounded-lg bg-slate-700/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg font-bold text-emerald-400" },
});
(__VLS_ctx.completedAnalyses);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center p-3 rounded-lg bg-slate-700/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg font-bold text-red-400" },
});
(__VLS_ctx.foundIssues);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-base font-semibold text-slate-100 flex items-center gap-2 mb-4" },
});
const __VLS_8 = {}.OrderedListOutlined;
/** @type {[typeof __VLS_components.OrderedListOutlined, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ class: "text-cyan-400" },
}));
const __VLS_10 = __VLS_9({
    ...{ class: "text-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
for (const [step, index] of __VLS_getVForSourceType((__VLS_ctx.analysisSteps))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (step.id),
        ...{ class: "step-item p-4 rounded-lg border transition-all duration-300" },
        ...{ class: (__VLS_ctx.getStepCardClass(step.status, index)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" },
        ...{ class: (__VLS_ctx.getStepIconClass(step.status, index)) },
    });
    const __VLS_12 = ((__VLS_ctx.getStepIcon(step.status)));
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        ...{ class: "text-sm" },
        ...{ class: ({ 'animate-spin': step.status === 'running' }) },
    }));
    const __VLS_14 = __VLS_13({
        ...{ class: "text-sm" },
        ...{ class: ({ 'animate-spin': step.status === 'running' }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1 min-w-0" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
        ...{ class: "font-medium text-slate-100" },
    });
    (step.name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-2" },
    });
    const __VLS_16 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        color: (__VLS_ctx.getStepStatusColor(step.status)),
        size: "small",
        ...{ class: "step-status-tag" },
    }));
    const __VLS_18 = __VLS_17({
        color: (__VLS_ctx.getStepStatusColor(step.status)),
        size: "small",
        ...{ class: "step-status-tag" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    (__VLS_ctx.getStepStatusLabel(step.status));
    var __VLS_19;
    if (step.duration) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-xs text-slate-400" },
        });
        (__VLS_ctx.formatDuration(step.duration));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-slate-300 mb-3" },
    });
    (step.description);
    if (step.status === 'running' || step.status === 'completed') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mb-3" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center justify-between mb-1" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-xs text-slate-400" },
        });
        (step.current_task || '处理中...');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-xs text-slate-400" },
        });
        (step.progress);
        const __VLS_20 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
            percent: (step.progress),
            showInfo: (false),
            strokeColor: (__VLS_ctx.getStepProgressColor(step.status)),
            size: "small",
        }));
        const __VLS_22 = __VLS_21({
            percent: (step.progress),
            showInfo: (false),
            strokeColor: (__VLS_ctx.getStepProgressColor(step.status)),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    }
    if (step.details) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "grid grid-cols-2 md:grid-cols-4 gap-3 text-xs" },
        });
        if (step.details.processed) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "flex items-center gap-1" },
            });
            const __VLS_24 = {}.CheckCircleOutlined;
            /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
                ...{ class: "text-emerald-400" },
            }));
            const __VLS_26 = __VLS_25({
                ...{ class: "text-emerald-400" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_25));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-slate-400" },
            });
            (step.details.processed);
        }
        if (step.details.errors) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "flex items-center gap-1" },
            });
            const __VLS_28 = {}.ExclamationCircleOutlined;
            /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
                ...{ class: "text-red-400" },
            }));
            const __VLS_30 = __VLS_29({
                ...{ class: "text-red-400" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_29));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-slate-400" },
            });
            (step.details.errors);
        }
        if (step.details.warnings) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "flex items-center gap-1" },
            });
            const __VLS_32 = {}.WarningOutlined;
            /** @type {[typeof __VLS_components.WarningOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
                ...{ class: "text-amber-400" },
            }));
            const __VLS_34 = __VLS_33({
                ...{ class: "text-amber-400" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_33));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-slate-400" },
            });
            (step.details.warnings);
        }
        if (step.details.time_remaining) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "flex items-center gap-1" },
            });
            const __VLS_36 = {}.ClockCircleOutlined;
            /** @type {[typeof __VLS_components.ClockCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
                ...{ class: "text-blue-400" },
            }));
            const __VLS_38 = __VLS_37({
                ...{ class: "text-blue-400" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_37));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-slate-400" },
            });
            (step.details.time_remaining);
        }
    }
    if (step.status === 'failed' && step.error) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-start gap-2" },
        });
        const __VLS_40 = {}.ExclamationCircleOutlined;
        /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
            ...{ class: "text-red-400 text-sm mt-0.5" },
        }));
        const __VLS_42 = __VLS_41({
            ...{ class: "text-red-400 text-sm mt-0.5" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_41));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-sm font-medium text-red-300 mb-1" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-red-200" },
        });
        (step.error);
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-base font-semibold text-slate-100 flex items-center gap-2" },
});
const __VLS_44 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ class: "text-green-400" },
}));
const __VLS_46 = __VLS_45({
    ...{ class: "text-green-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
const __VLS_48 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    checked: (__VLS_ctx.autoScroll),
    size: "small",
}));
const __VLS_50 = __VLS_49({
    checked: (__VLS_ctx.autoScroll),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-xs text-slate-400" },
});
const __VLS_52 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300" },
}));
const __VLS_54 = __VLS_53({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
let __VLS_56;
let __VLS_57;
let __VLS_58;
const __VLS_59 = {
    onClick: (__VLS_ctx.clearLogs)
};
__VLS_55.slots.default;
const __VLS_60 = {}.ClearOutlined;
/** @type {[typeof __VLS_components.ClearOutlined, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({}));
const __VLS_62 = __VLS_61({}, ...__VLS_functionalComponentArgsRest(__VLS_61));
var __VLS_55;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "logContainer",
    ...{ class: "log-container h-64 overflow-y-auto p-4 rounded-lg bg-slate-900/50 border border-slate-600/30 font-mono text-sm" },
});
/** @type {typeof __VLS_ctx.logContainer} */ ;
for (const [log, index] of __VLS_getVForSourceType((__VLS_ctx.logs))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (index),
        ...{ class: "log-entry mb-1 flex items-start gap-2" },
        ...{ class: (__VLS_ctx.getLogLevelClass(log.level)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-xs text-slate-500 flex-shrink-0 w-20" },
    });
    (__VLS_ctx.formatTime(log.timestamp));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-xs flex-shrink-0 w-12" },
        ...{ class: (__VLS_ctx.getLogLevelColor(log.level)) },
    });
    (log.level.toUpperCase());
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-slate-300 flex-1" },
    });
    (log.message);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-center gap-4" },
});
if (__VLS_ctx.status === 'running') {
    const __VLS_64 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        ...{ 'onClick': {} },
        ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300 hover:bg-amber-500/30" },
    }));
    const __VLS_66 = __VLS_65({
        ...{ 'onClick': {} },
        ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300 hover:bg-amber-500/30" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    let __VLS_68;
    let __VLS_69;
    let __VLS_70;
    const __VLS_71 = {
        onClick: (__VLS_ctx.pauseAnalysis)
    };
    __VLS_67.slots.default;
    const __VLS_72 = {}.PauseCircleOutlined;
    /** @type {[typeof __VLS_components.PauseCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({}));
    const __VLS_74 = __VLS_73({}, ...__VLS_functionalComponentArgsRest(__VLS_73));
    var __VLS_67;
}
if (__VLS_ctx.status === 'paused') {
    const __VLS_76 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        ...{ 'onClick': {} },
        ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30" },
    }));
    const __VLS_78 = __VLS_77({
        ...{ 'onClick': {} },
        ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    let __VLS_80;
    let __VLS_81;
    let __VLS_82;
    const __VLS_83 = {
        onClick: (__VLS_ctx.resumeAnalysis)
    };
    __VLS_79.slots.default;
    const __VLS_84 = {}.PlayCircleOutlined;
    /** @type {[typeof __VLS_components.PlayCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
    const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
    var __VLS_79;
}
if (__VLS_ctx.status === 'running' || __VLS_ctx.status === 'paused') {
    const __VLS_88 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        ...{ 'onClick': {} },
        danger: true,
        ...{ class: "bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30" },
    }));
    const __VLS_90 = __VLS_89({
        ...{ 'onClick': {} },
        danger: true,
        ...{ class: "bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    let __VLS_92;
    let __VLS_93;
    let __VLS_94;
    const __VLS_95 = {
        onClick: (__VLS_ctx.stopAnalysis)
    };
    __VLS_91.slots.default;
    const __VLS_96 = {}.StopOutlined;
    /** @type {[typeof __VLS_components.StopOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({}));
    const __VLS_98 = __VLS_97({}, ...__VLS_functionalComponentArgsRest(__VLS_97));
    var __VLS_91;
}
if (__VLS_ctx.status === 'completed' || __VLS_ctx.status === 'failed') {
    const __VLS_100 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        ...{ 'onClick': {} },
        type: "primary",
        ...{ class: "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none" },
    }));
    const __VLS_102 = __VLS_101({
        ...{ 'onClick': {} },
        type: "primary",
        ...{ class: "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    let __VLS_104;
    let __VLS_105;
    let __VLS_106;
    const __VLS_107 = {
        onClick: (__VLS_ctx.restartAnalysis)
    };
    __VLS_103.slots.default;
    const __VLS_108 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({}));
    const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
    var __VLS_103;
}
/** @type {__VLS_StyleScopedClasses['analysis-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['overall-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['w-10']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['step-status-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-red-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['log-container']} */ ;
/** @type {__VLS_StyleScopedClasses['h-64']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-900/50']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['log-entry']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['w-20']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-amber-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-amber-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-amber-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-emerald-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-red-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-r']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-500']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:to-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-none']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            OrderedListOutlined: icons_vue_1.OrderedListOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            WarningOutlined: icons_vue_1.WarningOutlined,
            ClockCircleOutlined: icons_vue_1.ClockCircleOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            ClearOutlined: icons_vue_1.ClearOutlined,
            PauseCircleOutlined: icons_vue_1.PauseCircleOutlined,
            PlayCircleOutlined: icons_vue_1.PlayCircleOutlined,
            StopOutlined: icons_vue_1.StopOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            status: status,
            currentStep: currentStep,
            totalSteps: totalSteps,
            overallProgress: overallProgress,
            processedRecords: processedRecords,
            totalRecords: totalRecords,
            completedAnalyses: completedAnalyses,
            foundIssues: foundIssues,
            autoScroll: autoScroll,
            logContainer: logContainer,
            analysisSteps: analysisSteps,
            logs: logs,
            pauseAnalysis: pauseAnalysis,
            resumeAnalysis: resumeAnalysis,
            stopAnalysis: stopAnalysis,
            restartAnalysis: restartAnalysis,
            clearLogs: clearLogs,
            getStatusColor: getStatusColor,
            getStatusLabel: getStatusLabel,
            getProgressColor: getProgressColor,
            getStepCardClass: getStepCardClass,
            getStepIconClass: getStepIconClass,
            getStepIcon: getStepIcon,
            getStepStatusColor: getStepStatusColor,
            getStepStatusLabel: getStepStatusLabel,
            getStepProgressColor: getStepProgressColor,
            getLogLevelClass: getLogLevelClass,
            getLogLevelColor: getLogLevelColor,
            formatDuration: formatDuration,
            formatTime: formatTime,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ...__VLS_exposed,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
