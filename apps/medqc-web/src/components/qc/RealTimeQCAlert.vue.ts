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
import useRealTimeQC_1 from '@/composables/useRealTimeQC';
import ant_design_vue_1 from 'ant-design-vue';
// 使用实时质控组合式函数
const { alertQueue } = (0, useRealTimeQC_1.useRealTimeQC)();
// 组件状态
const showAlert = (0, vue_1.ref)(false);
const showHistory = (0, vue_1.ref)(false);
const showSettings = (0, vue_1.ref)(false);
const currentAlert = (0, vue_1.ref)(null);
const alertHistory = (0, vue_1.ref)(: any[]);
const historyFilter = (0, vue_1.ref)('all');
// 预警设置
const alertSettings = (0, vue_1.ref)({
    enableCritical: true,
    enableError: true,
    enableWarning: true,
    enableInfo: false,
    displayDuration: 5000,
    enableSound: true,
    position: 'top-right'
});
// 定时器
let alertTimer = null;
// 计算属性
const filteredHistory = (0, vue_1.computed)(() => {
    if (historyFilter.value === 'all') {
        return alertHistory.value;
    }
    return alertHistory.value.filter(alert => alert.severity === historyFilter.value);
});
// 监听预警队列变化
(0, vue_1.watch)(alertQueue, (newQueue) => {
    if (newQueue.length > 0) {
        const latestAlert = newQueue[0];
        showNewAlert(latestAlert);
    }
}, { deep: true });
// 方法
const showNewAlert = (alert) => {
    // 检查是否启用该级别的预警
    if (!isAlertEnabled(alert.severity)) {
        return;
    }
    // 创建扩展的预警对象
    const extendedAlert = {
        ...alert,
        timestamp: new Date().toISOString(),
        id: `alert_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    };
    // 添加到历史记录
    alertHistory.value.unshift(extendedAlert);
    // 保持历史记录大小
    if (alertHistory.value.length > 100) {
        alertHistory.value = alertHistory.value.slice(0, 100);
    }
    // 显示当前预警
    currentAlert.value = extendedAlert;
    showAlert.value = true;
    // 播放声音提醒
    if (alertSettings.value.enableSound) {
        playAlertSound(alert.severity);
    }
    // 设置自动关闭定时器
    if (alertSettings.value.displayDuration > 0) {
        if (alertTimer) {
            clearTimeout(alertTimer);
        }
        alertTimer = setTimeout(() => {
            dismissAlert();
        }, alertSettings.value.displayDuration);
    }
};
const isAlertEnabled = (severity) => {
    switch (severity) {
        case 'critical':
            return alertSettings.value.enableCritical;
        case 'error':
            return alertSettings.value.enableError;
        case 'warning':
            return alertSettings.value.enableWarning;
        case 'info':
            return alertSettings.value.enableInfo;
        default:
            return false;
    }
};
const dismissAlert = () => {
    showAlert.value = false;
    currentAlert.value = null;
    if (alertTimer) {
        clearTimeout(alertTimer);
        alertTimer = null;
    }
};
const showSuggestion = () => {
    if (currentAlert.value?.suggestion) {
        ant_design_vue_1.message.info(currentAlert.value.suggestion);
    }
};
const toggleHistory = () => {
    showHistory.value = !showHistory.value;
    if (showHistory.value) {
        showSettings.value = false;
    }
};
const toggleSettings = () => {
    showSettings.value = !showSettings.value;
    if (showSettings.value) {
        showHistory.value = false;
    }
};
const closeHistory = () => {
    showHistory.value = false;
};
const closeSettings = () => {
    showSettings.value = false;
};
const clearHistory = () => {
    alertHistory.value = [];
    ant_design_vue_1.message.success('预警历史已清空');
};
const replayAlert = (alert) => {
    currentAlert.value = alert;
    showAlert.value = true;
    if (alertSettings.value.displayDuration > 0) {
        if (alertTimer) {
            clearTimeout(alertTimer);
        }
        alertTimer = setTimeout(() => {
            dismissAlert();
        }, alertSettings.value.displayDuration);
    }
};
const saveSettings = () => {
    // 保存设置到本地存储
    localStorage.setItem('qc_alert_settings', JSON.stringify(alertSettings.value));
    ant_design_vue_1.message.success('预警设置已保存');
    closeSettings();
};
const resetSettings = () => {
    alertSettings.value = {
        enableCritical: true,
        enableError: true,
        enableWarning: true,
        enableInfo: false,
        displayDuration: 5000,
        enableSound: true,
        position: 'top-right'
    };
    ant_design_vue_1.message.success('预警设置已重置');
};
const loadSettings = () => {
    const saved = localStorage.getItem('qc_alert_settings');
    if (saved) {
        try {
            alertSettings.value = { ...alertSettings.value, ...JSON.parse(saved) };
        }
        catch (error) {
            console.error('加载预警设置失败:', error);
        }
    }
};
const playAlertSound = (severity) => {
    // 创建音频上下文播放提示音
    try {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        // 根据严重程度设置不同的音调
        const frequencies = {
            critical: 800,
            error: 600,
            warning: 400,
            info: 300
        };
        oscillator.frequency.setValueAtTime(frequencies[severity], audioContext.currentTime);
        oscillator.type = 'sine';
        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.3);
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.3);
    }
    catch (error) {
        console.warn('播放预警声音失败:', error);
    }
};
// 工具函数
const getAlertIcon = (severity) => {
    const icons = {
        critical: 'fas fa-exclamation-circle',
        error: 'fas fa-exclamation-triangle',
        warning: 'fas fa-exclamation',
        info: 'fas fa-info-circle'
    };
    return icons[severity];
};
const getAlertTitle = (severity) => {
    const titles = {
        critical: '严重质控问题',
        error: '质控错误',
        warning: '质控警告',
        info: '质控信息'
    };
    return titles[severity];
};
const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};
// 生命周期
(0, vue_1.onMounted)(() => {
    loadSettings();
    console.log('实时质控预警组件已加载');
});
(0, vue_1.onUnmounted)(() => {
    if (alertTimer) {
        clearTimeout(alertTimer);
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['alert-critical']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-error']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-info']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['history-critical']} */ ;
/** @type {__VLS_StyleScopedClasses['history-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['history-error']} */ ;
/** @type {__VLS_StyleScopedClasses['history-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['history-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['history-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['history-info']} */ ;
/** @type {__VLS_StyleScopedClasses['history-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['history-content']} */ ;
/** @type {__VLS_StyleScopedClasses['control-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-notification']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-history-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-settings-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['control-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-notification']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-notification']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-notification']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "realtime-qc-alert" },
});
const __VLS_0 = {}.Transition;
/** @type {[typeof __VLS_components.Transition, typeof __VLS_components.Transition, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    name: "alert-slide",
}));
const __VLS_2 = __VLS_1({
    name: "alert-slide",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
if (__VLS_ctx.showAlert && __VLS_ctx.currentAlert) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-notification" },
        ...{ class: (`alert-${__VLS_ctx.currentAlert.severity}`) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: (__VLS_ctx.getAlertIcon(__VLS_ctx.currentAlert.severity)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-title" },
    });
    (__VLS_ctx.getAlertTitle(__VLS_ctx.currentAlert.severity));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-message" },
    });
    (__VLS_ctx.currentAlert.message);
    if (__VLS_ctx.currentAlert.location) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-location" },
        });
        (__VLS_ctx.currentAlert.location);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-actions" },
    });
    if (__VLS_ctx.currentAlert.suggestion) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.showSuggestion) },
            ...{ class: "btn-suggestion" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-lightbulb mr-1" },
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.dismissAlert) },
        ...{ class: "btn-dismiss" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-times" },
    });
}
var __VLS_3;
if (__VLS_ctx.showHistory) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-history-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "history-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-history mr-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history-controls" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        value: (__VLS_ctx.historyFilter),
        ...{ class: "filter-select" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "all",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "critical",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "error",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "warning",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "info",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.clearHistory) },
        ...{ class: "btn-clear" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-trash mr-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeHistory) },
        ...{ class: "btn-close" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-times" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history-content" },
    });
    if (__VLS_ctx.filteredHistory.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-history" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-inbox text-gray-400 text-4xl mb-3" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-600" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "history-list" },
        });
        for (const [alert, index] of __VLS_getVForSourceType((__VLS_ctx.filteredHistory))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (index),
                ...{ class: "history-item" },
                ...{ class: (`history-${alert.severity}`) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "history-icon" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: (__VLS_ctx.getAlertIcon(alert.severity)) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "history-content" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "history-message" },
            });
            (alert.message);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "history-meta" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "history-type" },
            });
            (alert.type);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "history-time" },
            });
            (__VLS_ctx.formatTime(alert.timestamp));
            if (alert.location) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "history-location" },
                });
                (alert.location);
            }
            if (alert.suggestion) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "history-suggestion" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                    ...{ class: "fas fa-lightbulb text-yellow-500 mr-1" },
                });
                (alert.suggestion);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "history-actions" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
                ...{ onClick: (...[$event]) => {
                        if (!(__VLS_ctx.showHistory))
                            return;
                        if (!!(__VLS_ctx.filteredHistory.length === 0))
                            return;
                        __VLS_ctx.replayAlert(alert);
                    } },
                ...{ class: "btn-replay" },
                title: "重新显示",
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
                ...{ class: "fas fa-redo" },
            });
        }
    }
}
if (__VLS_ctx.showSettings) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alert-settings-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "settings-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-cog mr-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeSettings) },
        ...{ class: "btn-close" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-times" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "setting-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-options" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "checkbox",
        ...{ class: "option-checkbox" },
    });
    (__VLS_ctx.alertSettings.enableCritical);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "checkbox",
        ...{ class: "option-checkbox" },
    });
    (__VLS_ctx.alertSettings.enableError);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "checkbox",
        ...{ class: "option-checkbox" },
    });
    (__VLS_ctx.alertSettings.enableWarning);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "checkbox",
        ...{ class: "option-checkbox" },
    });
    (__VLS_ctx.alertSettings.enableInfo);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "setting-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        value: (__VLS_ctx.alertSettings.displayDuration),
        ...{ class: "setting-select" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: (3000),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: (5000),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: (10000),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: (0),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "setting-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-options" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "option-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "checkbox",
        ...{ class: "option-checkbox" },
    });
    (__VLS_ctx.alertSettings.enableSound);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "option-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "setting-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "setting-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        value: (__VLS_ctx.alertSettings.position),
        ...{ class: "setting-select" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "top-right",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "top-left",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "bottom-right",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "bottom-left",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "settings-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.saveSettings) },
        ...{ class: "btn-save" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-save mr-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.resetSettings) },
        ...{ class: "btn-reset" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-undo mr-2" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "alert-controls" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleHistory) },
    ...{ class: "control-btn" },
    ...{ class: ({ active: __VLS_ctx.showHistory }) },
    title: "预警历史",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-history" },
});
if (__VLS_ctx.alertHistory.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "control-badge" },
    });
    (__VLS_ctx.alertHistory.length);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleSettings) },
    ...{ class: "control-btn" },
    ...{ class: ({ active: __VLS_ctx.showSettings }) },
    title: "预警设置",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-cog" },
});
/** @type {__VLS_StyleScopedClasses['realtime-qc-alert']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-notification']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-content']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-text']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-title']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-message']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-location']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-suggestion']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-lightbulb']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-dismiss']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-times']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-history-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['history-header']} */ ;
/** @type {__VLS_StyleScopedClasses['history-title']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-history']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['history-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-clear']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-close']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-times']} */ ;
/** @type {__VLS_StyleScopedClasses['history-content']} */ ;
/** @type {__VLS_StyleScopedClasses['no-history']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-inbox']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['history-list']} */ ;
/** @type {__VLS_StyleScopedClasses['history-item']} */ ;
/** @type {__VLS_StyleScopedClasses['history-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['history-content']} */ ;
/** @type {__VLS_StyleScopedClasses['history-message']} */ ;
/** @type {__VLS_StyleScopedClasses['history-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['history-type']} */ ;
/** @type {__VLS_StyleScopedClasses['history-time']} */ ;
/** @type {__VLS_StyleScopedClasses['history-location']} */ ;
/** @type {__VLS_StyleScopedClasses['history-suggestion']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-lightbulb']} */ ;
/** @type {__VLS_StyleScopedClasses['text-yellow-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['history-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-replay']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-redo']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-settings-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-header']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-title']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-cog']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-close']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-times']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-content']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-group']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-label']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-options']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['option-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['option-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['option-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['option-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-group']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-label']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-select']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-group']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-label']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-options']} */ ;
/** @type {__VLS_StyleScopedClasses['option-item']} */ ;
/** @type {__VLS_StyleScopedClasses['option-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['option-text']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-group']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-label']} */ ;
/** @type {__VLS_StyleScopedClasses['setting-select']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-save']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-save']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-reset']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-undo']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-controls']} */ ;
/** @type {__VLS_StyleScopedClasses['control-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-history']} */ ;
/** @type {__VLS_StyleScopedClasses['control-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['control-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-cog']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            showAlert: showAlert,
            showHistory: showHistory,
            showSettings: showSettings,
            currentAlert: currentAlert,
            alertHistory: alertHistory,
            historyFilter: historyFilter,
            alertSettings: alertSettings,
            filteredHistory: filteredHistory,
            dismissAlert: dismissAlert,
            showSuggestion: showSuggestion,
            toggleHistory: toggleHistory,
            toggleSettings: toggleSettings,
            closeHistory: closeHistory,
            closeSettings: closeSettings,
            clearHistory: clearHistory,
            replayAlert: replayAlert,
            saveSettings: saveSettings,
            resetSettings: resetSettings,
            getAlertIcon: getAlertIcon,
            getAlertTitle: getAlertTitle,
            formatTime: formatTime,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
