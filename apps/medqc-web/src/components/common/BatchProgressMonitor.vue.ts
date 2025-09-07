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
import useBatchMonitor_1 from '@/composables/useBatchMonitor';
const props = defineProps();
// 默认配置
const autoRefresh = props.autoRefresh ?? true;
const refreshInterval = props.refreshInterval ?? 5000; // 5秒
const showRecentTasks = props.showRecentTasks ?? true;
const maxRecentTasks = props.maxRecentTasks ?? 5;
// 响应式数据
const isMinimized = (0, vue_1.ref)(false);
const isRefreshing = (0, vue_1.ref)(false);
const isRetrying = (0, vue_1.ref)(false);
const isCancelling = (0, vue_1.ref)(false);
// 使用批量监控组合式函数
const { activeTasks, recentTasks, refreshTasks: refreshTasksComposable, subscribeToTasks, retryTask: retryTaskComposable, cancelTask: cancelTaskComposable } = (0, useBatchMonitor_1.useBatchMonitor)();
// 自动刷新定时器
let refreshTimer = null;
// 计算属性
const totalActiveTasks = (0, vue_1.computed)(() => activeTasks.value.length);
// 方法
const toggleMinimize = () => {
    isMinimized.value = !isMinimized.value;
};
const refreshTasks = async () => {
    if (isRefreshing.value)
        return;
    isRefreshing.value = true;
    try {
        await refreshTasksComposable();
    }
    finally {
        isRefreshing.value = false;
    }
};
const retryTask = async (taskId) => {
    if (isRetrying.value)
        return;
    isRetrying.value = true;
    try {
        await retryTaskComposable(taskId);
    }
    finally {
        isRetrying.value = false;
    }
};
const cancelTask = async (taskId) => {
    if (isCancelling.value)
        return;
    isCancelling.value = true;
    try {
        await cancelTaskComposable(taskId);
    }
    finally {
        isCancelling.value = false;
    }
};
const viewTaskDetails = (task) => {
    // 触发事件，让父组件处理详情显示
    emit('view-details', task);
};
const viewAllTasks = () => {
    // 触发事件，让父组件处理全部任务显示
    emit('view-all-tasks');
};
// 工具函数
const getTaskIcon = (taskType) => {
    const icons = {
        upload: 'fas fa-upload text-blue-500',
        analysis: 'fas fa-brain text-purple-500',
        export: 'fas fa-download text-green-500'
    };
    return icons[taskType] || 'fas fa-tasks text-gray-500';
};
const getTaskName = (taskType) => {
    const names = {
        upload: '批量上传',
        analysis: '批量分析',
        export: '批量导出'
    };
    return names[taskType] || '未知任务';
};
const getStatusText = (status) => {
    const texts = {
        pending: '等待中',
        processing: '处理中',
        completed: '已完成',
        failed: '失败'
    };
    return texts[status] || status;
};
const getStatusClass = (status) => {
    const classes = {
        pending: 'status-pending',
        processing: 'status-processing',
        completed: 'status-completed',
        failed: 'status-failed'
    };
    return classes[status] || '';
};
const getProgressClass = (status) => {
    const classes = {
        pending: 'progress-pending',
        processing: 'progress-processing',
        completed: 'progress-completed',
        failed: 'progress-failed'
    };
    return classes[status] || '';
};
const formatTime = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleTimeString('zh-CN', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};
const formatRelativeTime = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now.getTime() - date.getTime());
    const diffMinutes = Math.ceil(diffTime / (1000 * 60));
    const diffHours = Math.ceil(diffTime / (1000 * 60 * 60));
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    if (diffMinutes < 60) {
        return `${diffMinutes}分钟前`;
    }
    else if (diffHours < 24) {
        return `${diffHours}小时前`;
    }
    else {
        return `${diffDays}天前`;
    }
};
const formatDuration = (startTime, endTime) => {
    const start = new Date(startTime);
    const end = endTime ? new Date(endTime) : new Date();
    const duration = Math.floor((end.getTime() - start.getTime()) / 1000);
    if (duration < 60)
        return `${duration}秒`;
    if (duration < 3600)
        return `${Math.floor(duration / 60)}分钟`;
    return `${Math.floor(duration / 3600)}小时${Math.floor((duration % 3600) / 60)}分钟`;
};
const estimateRemainingTime = (task) => {
    if (!task.started_at || task.processed_items === 0)
        return '计算中...';
    const elapsed = Date.now() - new Date(task.started_at).getTime();
    const avgTimePerItem = elapsed / task.processed_items;
    const remainingItems = task.total_items - task.processed_items;
    const remainingTime = Math.floor((avgTimePerItem * remainingItems) / 1000);
    if (remainingTime < 60)
        return `约${remainingTime}秒`;
    if (remainingTime < 3600)
        return `约${Math.floor(remainingTime / 60)}分钟`;
    return `约${Math.floor(remainingTime / 3600)}小时`;
};
const formatErrorDetails = (errorDetails) => {
    if (typeof errorDetails === 'string')
        return errorDetails;
    if (typeof errorDetails === 'object') {
        return errorDetails.message || JSON.stringify(errorDetails, null, 2);
    }
    return '未知错误';
};
const emit = defineEmits();
// 生命周期
(0, vue_1.onMounted)(async () => {
    // 初始加载任务
    await refreshTasks();
    // 订阅实时更新
    subscribeToTasks();
    // 设置自动刷新
    if (autoRefresh) {
        refreshTimer = setInterval(refreshTasks, refreshInterval);
    }
});
(0, vue_1.onUnmounted)(() => {
    if (refreshTimer) {
        clearInterval(refreshTimer);
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-retry']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-cancel']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-details']} */ ;
/** @type {__VLS_StyleScopedClasses['monitor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['task-header']} */ ;
/** @type {__VLS_StyleScopedClasses['task-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['task-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-retry']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-cancel']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-details']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-progress-monitor" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "monitor-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-left" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-tasks text-xl text-blue-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "task-count" },
});
(__VLS_ctx.activeTasks.length);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-right" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.refreshTasks) },
    ...{ class: "btn-refresh" },
    disabled: (__VLS_ctx.isRefreshing),
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-sync-alt" },
    ...{ class: ({ 'fa-spin': __VLS_ctx.isRefreshing }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleMinimize) },
    ...{ class: "btn-minimize" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas" },
    ...{ class: (__VLS_ctx.isMinimized ? 'fa-chevron-down' : 'fa-chevron-up') },
});
if (!__VLS_ctx.isMinimized) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "task-list" },
    });
    if (__VLS_ctx.activeTasks.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty-state" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-check-circle text-4xl text-green-500 mb-3" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-600" },
        });
    }
    for (const [task] of __VLS_getVForSourceType((__VLS_ctx.activeTasks))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (task.id),
            ...{ class: "task-item" },
            ...{ class: ({
                    'task-pending': task.status === 'pending',
                    'task-processing': task.status === 'processing',
                    'task-completed': task.status === 'completed',
                    'task-failed': task.status === 'failed'
                }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: (__VLS_ctx.getTaskIcon(task.task_type)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "task-name" },
        });
        (__VLS_ctx.getTaskName(task.task_type));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "task-status-badge" },
            ...{ class: (__VLS_ctx.getStatusClass(task.status)) },
        });
        (__VLS_ctx.getStatusText(task.status));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-meta" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "task-time" },
        });
        (__VLS_ctx.formatTime(task.created_at));
        if (task.started_at) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "task-duration" },
            });
            (__VLS_ctx.formatDuration(task.started_at, task.completed_at));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "progress-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "progress-bar" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "progress-fill" },
            ...{ class: (__VLS_ctx.getProgressClass(task.status)) },
            ...{ style: ({ width: task.progress_percentage + '%' }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "progress-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "progress-percentage" },
        });
        (Math.round(task.progress_percentage));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "progress-items" },
        });
        (task.processed_items);
        (task.total_items);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-stats" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stat-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-value" },
        });
        (task.total_items);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stat-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-value text-blue-600" },
        });
        (task.processed_items);
        if (task.failed_items > 0) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "stat-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "stat-label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "stat-value text-red-600" },
            });
            (task.failed_items);
        }
        if (task.status === 'processing') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "stat-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "stat-label" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "stat-value" },
            });
            (__VLS_ctx.estimateRemainingTime(task));
        }
        if (task.error_details && task.status === 'failed') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "error-section" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "error-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-exclamation-triangle text-red-500" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "error-title" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "error-content" },
            });
            (__VLS_ctx.formatErrorDetails(task.error_details));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "task-actions" },
        });
        if (task.status === 'failed') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(!__VLS_ctx.isMinimized))
                            return;
                        if (!(task.status === 'failed'))
                            return;
                        __VLS_ctx.retryTask(task.id);
                    } },
                ...{ class: "btn-retry" },
                disabled: (__VLS_ctx.isRetrying),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-redo" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        if (task.status === 'processing') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(!__VLS_ctx.isMinimized))
                            return;
                        if (!(task.status === 'processing'))
                            return;
                        __VLS_ctx.cancelTask(task.id);
                    } },
                ...{ class: "btn-cancel" },
                disabled: (__VLS_ctx.isCancelling),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-stop" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isMinimized))
                        return;
                    __VLS_ctx.viewTaskDetails(task);
                } },
            ...{ class: "btn-details" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-info-circle" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    }
}
if (!__VLS_ctx.isMinimized && __VLS_ctx.recentTasks.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "recent-tasks" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "recent-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "text-sm font-medium text-gray-700" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.viewAllTasks) },
        ...{ class: "btn-view-all" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "recent-list" },
    });
    for (const [task] of __VLS_getVForSourceType((__VLS_ctx.recentTasks.slice(0, 3)))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isMinimized && __VLS_ctx.recentTasks.length > 0))
                        return;
                    __VLS_ctx.viewTaskDetails(task);
                } },
            key: (task.id),
            ...{ class: "recent-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "recent-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: (__VLS_ctx.getTaskIcon(task.task_type)) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "recent-name" },
        });
        (__VLS_ctx.getTaskName(task.task_type));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "recent-time" },
        });
        (__VLS_ctx.formatRelativeTime(task.completed_at));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "recent-result" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "recent-success" },
        });
        (task.total_items - task.failed_items);
        if (task.failed_items > 0) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "recent-failed" },
            });
            (task.failed_items);
        }
    }
}
/** @type {__VLS_StyleScopedClasses['batch-progress-monitor']} */ ;
/** @type {__VLS_StyleScopedClasses['monitor-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-tasks']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['task-count']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-refresh']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-sync-alt']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-minimize']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['task-list']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-check-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['task-item']} */ ;
/** @type {__VLS_StyleScopedClasses['task-pending']} */ ;
/** @type {__VLS_StyleScopedClasses['task-processing']} */ ;
/** @type {__VLS_StyleScopedClasses['task-completed']} */ ;
/** @type {__VLS_StyleScopedClasses['task-failed']} */ ;
/** @type {__VLS_StyleScopedClasses['task-info']} */ ;
/** @type {__VLS_StyleScopedClasses['task-header']} */ ;
/** @type {__VLS_StyleScopedClasses['task-title']} */ ;
/** @type {__VLS_StyleScopedClasses['task-name']} */ ;
/** @type {__VLS_StyleScopedClasses['task-status-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['task-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['task-time']} */ ;
/** @type {__VLS_StyleScopedClasses['task-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-section']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-fill']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-text']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-percentage']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-items']} */ ;
/** @type {__VLS_StyleScopedClasses['task-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['error-section']} */ ;
/** @type {__VLS_StyleScopedClasses['error-header']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-exclamation-triangle']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
/** @type {__VLS_StyleScopedClasses['error-title']} */ ;
/** @type {__VLS_StyleScopedClasses['error-content']} */ ;
/** @type {__VLS_StyleScopedClasses['task-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-retry']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-redo']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-cancel']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-stop']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-details']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-info-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-tasks']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-header']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-view-all']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-list']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-item']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-info']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-name']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-time']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-result']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-success']} */ ;
/** @type {__VLS_StyleScopedClasses['recent-failed']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            isMinimized: isMinimized,
            isRefreshing: isRefreshing,
            isRetrying: isRetrying,
            isCancelling: isCancelling,
            activeTasks: activeTasks,
            recentTasks: recentTasks,
            toggleMinimize: toggleMinimize,
            refreshTasks: refreshTasks,
            retryTask: retryTask,
            cancelTask: cancelTask,
            viewTaskDetails: viewTaskDetails,
            viewAllTasks: viewAllTasks,
            getTaskIcon: getTaskIcon,
            getTaskName: getTaskName,
            getStatusText: getStatusText,
            getStatusClass: getStatusClass,
            getProgressClass: getProgressClass,
            formatTime: formatTime,
            formatRelativeTime: formatRelativeTime,
            formatDuration: formatDuration,
            estimateRemainingTime: estimateRemainingTime,
            formatErrorDetails: formatErrorDetails,
        };
    },
    __typeEmits: {},
    __typeProps: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
