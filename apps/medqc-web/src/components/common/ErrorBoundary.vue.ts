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
import vue_router_1 from 'vue-router';
import icons_vue_1 from '@ant-design/icons-vue';
import ant_design_vue_1 from 'ant-design-vue';
import error_handler_1 from '@/lib/error-handler';
import useBreakpoints_1 from '@/composables/useBreakpoints';
const props = withDefaults(defineProps(), {
    fallback: true,
    showDetails: process.env.NODE_ENV === 'development',
    showReportButton: true,
    showRefreshButton: true,
    showContactInfo: true,
    canGoBack: true,
    maxRetries: 3,
    autoRetry: false,
    autoRetryDelay: 3000
});
const emit = defineEmits();
// 响应式数据
const router = (0, vue_router_1.useRouter)();
const { isMobile } = (0, useBreakpoints_1.useBreakpoints)();
const hasError = (0, vue_1.ref)(false);
const currentError = (0, vue_1.ref)(null);
const retrying = (0, vue_1.ref)(false);
const retryCount = (0, vue_1.ref)(0);
const errorType = (0, vue_1.ref)(error_handler_1.ErrorType.UNKNOWN);
const errorSeverity = (0, vue_1.ref)(error_handler_1.ErrorSeverity.MEDIUM);
// 计算属性
const errorIcon = (0, vue_1.computed)(() => {
    switch (errorSeverity.value) {
        case error_handler_1.ErrorSeverity.CRITICAL:
            return icons_vue_1.CloseCircleOutlined;
        case error_handler_1.ErrorSeverity.HIGH:
            return icons_vue_1.ExclamationCircleOutlined;
        case error_handler_1.ErrorSeverity.MEDIUM:
            return icons_vue_1.WarningOutlined;
        default:
            return icons_vue_1.InfoCircleOutlined;
    }
});
const errorTitle = (0, vue_1.computed)(() => {
    if (!currentError.value)
        return '发生错误';
    const titleMap = {
        [error_handler_1.ErrorType.NETWORK]: '网络连接错误',
        [error_handler_1.ErrorType.API]: '服务请求失败',
        [error_handler_1.ErrorType.VALIDATION]: '数据验证错误',
        [error_handler_1.ErrorType.PERMISSION]: '权限不足',
        [error_handler_1.ErrorType.BUSINESS]: '业务逻辑错误',
        [error_handler_1.ErrorType.SYSTEM]: '系统错误',
        [error_handler_1.ErrorType.TIMEOUT]: '请求超时',
        [error_handler_1.ErrorType.UNKNOWN]: '未知错误'
    };
    return titleMap[errorType.value] || '发生错误';
});
const errorMessage = (0, vue_1.computed)(() => {
    if (!currentError.value)
        return '系统遇到了一个问题';
    // 用户友好的错误消息
    const messageMap = {
        [error_handler_1.ErrorType.NETWORK]: '网络连接异常，请检查网络设置后重试',
        [error_handler_1.ErrorType.API]: '服务暂时不可用，请稍后重试',
        [error_handler_1.ErrorType.VALIDATION]: '输入的数据格式不正确，请检查后重新提交',
        [error_handler_1.ErrorType.PERMISSION]: '您没有执行此操作的权限，请联系管理员',
        [error_handler_1.ErrorType.BUSINESS]: '操作无法完成，请检查输入信息',
        [error_handler_1.ErrorType.SYSTEM]: '系统内部错误，我们正在处理这个问题',
        [error_handler_1.ErrorType.TIMEOUT]: '操作超时，请重试或检查网络连接',
        [error_handler_1.ErrorType.UNKNOWN]: '系统遇到了未知问题，请重试或联系技术支持'
    };
    return messageMap[errorType.value] || currentError.value.message || '系统遇到了一个问题';
});
const errorDetails = (0, vue_1.computed)(() => {
    if (!currentError.value || !props.showDetails)
        return null;
    return {
        message: currentError.value.message,
        stack: currentError.value.stack,
        type: errorType.value,
        severity: errorSeverity.value,
        timestamp: new Date().toISOString(),
        userAgent: navigator.userAgent,
        url: window.location.href
    };
});
const suggestions = (0, vue_1.computed)(() => {
    const baseSuggestions = {
        [error_handler_1.ErrorType.NETWORK]: [
            '检查网络连接是否正常',
            '尝试刷新页面',
            '如果使用VPN，请尝试断开后重试'
        ],
        [error_handler_1.ErrorType.API]: [
            '稍后重试',
            '检查输入的数据是否正确',
            '如果问题持续，请联系技术支持'
        ],
        [error_handler_1.ErrorType.VALIDATION]: [
            '检查输入格式是否正确',
            '确保必填字段已填写',
            '参考提示信息修正输入'
        ],
        [error_handler_1.ErrorType.PERMISSION]: [
            '联系管理员获取相应权限',
            '确认您的账户状态正常',
            '尝试重新登录'
        ],
        [error_handler_1.ErrorType.BUSINESS]: [
            '检查操作步骤是否正确',
            '确认数据状态符合要求',
            '参考帮助文档'
        ],
        [error_handler_1.ErrorType.SYSTEM]: [
            '稍后重试',
            '刷新页面',
            '联系技术支持'
        ],
        [error_handler_1.ErrorType.TIMEOUT]: [
            '检查网络连接速度',
            '重试操作',
            '如果文件较大，请耐心等待'
        ],
        [error_handler_1.ErrorType.UNKNOWN]: [
            '刷新页面重试',
            '清除浏览器缓存',
            '联系技术支持并提供错误详情'
        ]
    };
    return baseSuggestions[errorType.value] || baseSuggestions[error_handler_1.ErrorType.UNKNOWN];
});
// 方法
const handleError = (error) => {
    console.error('ErrorBoundary捕获错误:', error);
    hasError.value = true;
    currentError.value = error;
    retryCount.value = 0;
    // 分析错误类型和严重程度
    analyzeError(error);
    // 上报错误
    error_handler_1.globalErrorHandler.handleError(error, {
        component: 'ErrorBoundary',
        props: props
    });
    emit('error', error);
    // 自动重试
    if (props.autoRetry && retryCount.value < props.maxRetries) {
        setTimeout(() => {
            handleRetry();
        }, props.autoRetryDelay);
    }
};
const analyzeError = (error) => {
    const message = error.message?.toLowerCase() || '';
    // 分析错误类型
    if (message.includes('network') || message.includes('fetch')) {
        errorType.value = error_handler_1.ErrorType.NETWORK;
        errorSeverity.value = error_handler_1.ErrorSeverity.HIGH;
    }
    else if (message.includes('timeout')) {
        errorType.value = error_handler_1.ErrorType.TIMEOUT;
        errorSeverity.value = error_handler_1.ErrorSeverity.MEDIUM;
    }
    else if (message.includes('permission') || message.includes('unauthorized')) {
        errorType.value = error_handler_1.ErrorType.PERMISSION;
        errorSeverity.value = error_handler_1.ErrorSeverity.MEDIUM;
    }
    else if (message.includes('validation') || message.includes('invalid')) {
        errorType.value = error_handler_1.ErrorType.VALIDATION;
        errorSeverity.value = error_handler_1.ErrorSeverity.LOW;
    }
    else if (message.includes('api') || message.includes('server')) {
        errorType.value = error_handler_1.ErrorType.API;
        errorSeverity.value = error_handler_1.ErrorSeverity.HIGH;
    }
    else {
        errorType.value = error_handler_1.ErrorType.UNKNOWN;
        errorSeverity.value = error_handler_1.ErrorSeverity.MEDIUM;
    }
};
const handleRetry = async () => {
    if (retryCount.value >= props.maxRetries) {
        ant_design_vue_1.message.warning(`已达到最大重试次数 (${props.maxRetries})`);
        return;
    }
    retrying.value = true;
    retryCount.value++;
    try {
        // 等待一段时间后重试
        await new Promise(resolve => setTimeout(resolve, 1000));
        // 重置错误状态
        hasError.value = false;
        currentError.value = null;
        emit('retry');
        emit('recover');
        ant_design_vue_1.message.success('重试成功');
    }
    catch (error) {
        console.error('重试失败:', error);
        ant_design_vue_1.message.error('重试失败，请稍后再试');
    }
    finally {
        retrying.value = false;
    }
};
const handleGoBack = () => {
    if (window.history.length > 1) {
        router.go(-1);
    }
    else {
        router.push('/');
    }
};
const handleReport = () => {
    // 实现错误报告功能
    const errorReport = {
        error: currentError.value?.message,
        stack: currentError.value?.stack,
        url: window.location.href,
        userAgent: navigator.userAgent,
        timestamp: new Date().toISOString()
    };
    console.log('错误报告:', errorReport);
    ant_design_vue_1.message.success('错误报告已提交，感谢您的反馈');
};
const handleRefresh = () => {
    window.location.reload();
};
// 错误捕获
(0, vue_1.onErrorCaptured)((error) => {
    handleError(error);
    return false; // 阻止错误继续传播
});
// 监听全局错误
window.addEventListener('error',  (event) => {
    if (event.error) {
        handleError(event.error);
    }
});
window.addEventListener('unhandledrejection',  (event: any) => {
    handleError(new Error(event.reason));
});
// 暴露方法给父组件
const __VLS_exposed = {
    handleError,
    reset: () => {
        hasError.value = false;
        currentError.value = null;
        retryCount.value = 0;
    }
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    fallback: true,
    showDetails: process.env.NODE_ENV === 'development',
    showReportButton: true,
    showRefreshButton: true,
    showContactInfo: true,
    canGoBack: true,
    maxRetries: 3,
    autoRetry: false,
    autoRetryDelay: 3000
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['error-critical']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-high']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-low']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-suggestions']} */ ;
/** @type {__VLS_StyleScopedClasses['error-suggestions']} */ ;
/** @type {__VLS_StyleScopedClasses['error-suggestions']} */ ;
/** @type {__VLS_StyleScopedClasses['contact-text']} */ ;
/** @type {__VLS_StyleScopedClasses['contact-text']} */ ;
/** @type {__VLS_StyleScopedClasses['error-content']} */ ;
/** @type {__VLS_StyleScopedClasses['error-container']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-title']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['error-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['error-container']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-title']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "error-boundary" },
});
if (!__VLS_ctx.hasError) {
    var __VLS_0 = {};
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-container" },
        ...{ class: (`error-${__VLS_ctx.errorSeverity}`) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-icon" },
    });
    const __VLS_2 = ((__VLS_ctx.errorIcon));
    // @ts-ignore
    const __VLS_3 = __VLS_asFunctionalComponent(__VLS_2, new __VLS_2({}));
    const __VLS_4 = __VLS_3({}, ...__VLS_functionalComponentArgsRest(__VLS_3));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "error-title" },
    });
    (__VLS_ctx.errorTitle);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "error-message" },
    });
    (__VLS_ctx.errorMessage);
    if (__VLS_ctx.showDetails && __VLS_ctx.errorDetails) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "error-details" },
        });
        const __VLS_6 = {}.ACollapse;
        /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_7 = __VLS_asFunctionalComponent(__VLS_6, new __VLS_6({
            ghost: true,
        }));
        const __VLS_8 = __VLS_7({
            ghost: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_7));
        __VLS_9.slots.default;
        const __VLS_10 = {}.ACollapsePanel;
        /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
        // @ts-ignore
        const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
            key: "details",
            header: "错误详情",
        }));
        const __VLS_12 = __VLS_11({
            key: "details",
            header: "错误详情",
        }, ...__VLS_functionalComponentArgsRest(__VLS_11));
        __VLS_13.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
            ...{ class: "error-stack" },
        });
        (__VLS_ctx.errorDetails);
        var __VLS_13;
        var __VLS_9;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-actions" },
    });
    const __VLS_14 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
        direction: (__VLS_ctx.isMobile ? 'vertical' : 'horizontal'),
        size: (12),
    }));
    const __VLS_16 = __VLS_15({
        direction: (__VLS_ctx.isMobile ? 'vertical' : 'horizontal'),
        size: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    __VLS_17.slots.default;
    const __VLS_18 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.retrying),
    }));
    const __VLS_20 = __VLS_19({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.retrying),
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
    let __VLS_22;
    let __VLS_23;
    let __VLS_24;
    const __VLS_25 = {
        onClick: (__VLS_ctx.handleRetry)
    };
    __VLS_21.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_21.slots;
        const __VLS_26 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({}));
        const __VLS_28 = __VLS_27({}, ...__VLS_functionalComponentArgsRest(__VLS_27));
    }
    var __VLS_21;
    if (__VLS_ctx.canGoBack) {
        const __VLS_30 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
            ...{ 'onClick': {} },
        }));
        const __VLS_32 = __VLS_31({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_31));
        let __VLS_34;
        let __VLS_35;
        let __VLS_36;
        const __VLS_37 = {
            onClick: (__VLS_ctx.handleGoBack)
        };
        __VLS_33.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_33.slots;
            const __VLS_38 = {}.ArrowLeftOutlined;
            /** @type {[typeof __VLS_components.ArrowLeftOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({}));
            const __VLS_40 = __VLS_39({}, ...__VLS_functionalComponentArgsRest(__VLS_39));
        }
        var __VLS_33;
    }
    if (__VLS_ctx.showReportButton) {
        const __VLS_42 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
            ...{ 'onClick': {} },
        }));
        const __VLS_44 = __VLS_43({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_43));
        let __VLS_46;
        let __VLS_47;
        let __VLS_48;
        const __VLS_49 = {
            onClick: (__VLS_ctx.handleReport)
        };
        __VLS_45.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_45.slots;
            const __VLS_50 = {}.BugOutlined;
            /** @type {[typeof __VLS_components.BugOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({}));
            const __VLS_52 = __VLS_51({}, ...__VLS_functionalComponentArgsRest(__VLS_51));
        }
        var __VLS_45;
    }
    if (__VLS_ctx.showRefreshButton) {
        const __VLS_54 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
            ...{ 'onClick': {} },
        }));
        const __VLS_56 = __VLS_55({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_55));
        let __VLS_58;
        let __VLS_59;
        let __VLS_60;
        const __VLS_61 = {
            onClick: (__VLS_ctx.handleRefresh)
        };
        __VLS_57.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_57.slots;
            const __VLS_62 = {}.SyncOutlined;
            /** @type {[typeof __VLS_components.SyncOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({}));
            const __VLS_64 = __VLS_63({}, ...__VLS_functionalComponentArgsRest(__VLS_63));
        }
        var __VLS_57;
    }
    var __VLS_17;
    if (__VLS_ctx.suggestions.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "error-suggestions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
        for (const [suggestion, index] of __VLS_getVForSourceType((__VLS_ctx.suggestions))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                key: (index),
            });
            (suggestion);
        }
    }
    if (__VLS_ctx.showContactInfo) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "error-contact" },
        });
        const __VLS_66 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({}));
        const __VLS_68 = __VLS_67({}, ...__VLS_functionalComponentArgsRest(__VLS_67));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "contact-text" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
            href: "mailto:support@example.com",
        });
    }
}
/** @type {__VLS_StyleScopedClasses['error-boundary']} */ ;
/** @type {__VLS_StyleScopedClasses['error-content']} */ ;
/** @type {__VLS_StyleScopedClasses['error-container']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-info']} */ ;
/** @type {__VLS_StyleScopedClasses['error-title']} */ ;
/** @type {__VLS_StyleScopedClasses['error-message']} */ ;
/** @type {__VLS_StyleScopedClasses['error-details']} */ ;
/** @type {__VLS_StyleScopedClasses['error-stack']} */ ;
/** @type {__VLS_StyleScopedClasses['error-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['error-suggestions']} */ ;
/** @type {__VLS_StyleScopedClasses['error-contact']} */ ;
/** @type {__VLS_StyleScopedClasses['contact-text']} */ ;
// @ts-ignore
var __VLS_1 = __VLS_0;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            ArrowLeftOutlined: icons_vue_1.ArrowLeftOutlined,
            BugOutlined: icons_vue_1.BugOutlined,
            SyncOutlined: icons_vue_1.SyncOutlined,
            isMobile: isMobile,
            hasError: hasError,
            retrying: retrying,
            errorSeverity: errorSeverity,
            errorIcon: errorIcon,
            errorTitle: errorTitle,
            errorMessage: errorMessage,
            errorDetails: errorDetails,
            suggestions: suggestions,
            handleRetry: handleRetry,
            handleGoBack: handleGoBack,
            handleReport: handleReport,
            handleRefresh: handleRefresh,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
const __VLS_component = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ...__VLS_exposed,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = {};
; /* PartiallyEnd: #4569/main.vue */
