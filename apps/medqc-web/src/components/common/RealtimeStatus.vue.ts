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
import realtime_service_1 from '../../lib/realtime/realtime-service';
import icons_vue_1 from '@ant-design/icons-vue';
// 连接状态
const isConnected = (0, vue_1.ref)(false);
const isConnecting = (0, vue_1.ref)(false);
const connectionAttempts = (0, vue_1.ref)(0);
// 实时服务实例
const realtimeService = (0, realtime_service_1.getRealtimeService)();
// 检查连接状态
const checkConnectionStatus = () => {
    isConnected.value = realtimeService.getConnectionStatus();
};
// 手动重连
const handleReconnect = async () => {
    try {
        isConnecting.value = true;
        connectionAttempts.value++;
        await realtimeService.reconnect();
        isConnected.value = true;
    }
    catch (error) {
        console.error('重连失败:', error);
    }
    finally {
        isConnecting.value = false;
    }
};
// 获取状态文本
const getStatusText = () => {
    if (isConnecting.value) {
        return '连接中...';
    }
    if (isConnected.value) {
        return '实时连接正常';
    }
    return '连接已断开';
};
// 获取状态颜色
const getStatusColor = () => {
    if (isConnecting.value) {
        return '#faad14';
    }
    if (isConnected.value) {
        return '#52c41a';
    }
    return '#ff4d4f';
};
// 获取状态图标
const getStatusIcon = () => {
    if (isConnecting.value) {
        return icons_vue_1.LoadingOutlined;
    }
    if (isConnected.value) {
        return icons_vue_1.CheckCircleOutlined;
    }
    return icons_vue_1.DisconnectOutlined;
};
// 定时检查连接状态
let statusCheckInterval = null;
(0, vue_1.onMounted)(() => {
    checkConnectionStatus();
    // 每5秒检查一次连接状态
    statusCheckInterval = setInterval(checkConnectionStatus, 5000);
});
(0, vue_1.onUnmounted)(() => {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['connected']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['connecting']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['disconnected']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "realtime-status" },
});
const __VLS_0 = {}.ATooltip;
/** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: (__VLS_ctx.getStatusText()),
}));
const __VLS_2 = __VLS_1({
    title: (__VLS_ctx.getStatusText()),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ onClick: (...[$event]) => {
            !__VLS_ctx.isConnected && !__VLS_ctx.isConnecting ? __VLS_ctx.handleReconnect() : null;
        } },
    ...{ class: "status-indicator" },
    ...{ class: ({
            'connected': __VLS_ctx.isConnected,
            'connecting': __VLS_ctx.isConnecting,
            'disconnected': !__VLS_ctx.isConnected && !__VLS_ctx.isConnecting
        }) },
});
const __VLS_4 = ((__VLS_ctx.getStatusIcon()));
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ style: ({ color: __VLS_ctx.getStatusColor() }) },
    spin: (__VLS_ctx.isConnecting),
}));
const __VLS_6 = __VLS_5({
    ...{ style: ({ color: __VLS_ctx.getStatusColor() }) },
    spin: (__VLS_ctx.isConnecting),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "status-text" },
});
(__VLS_ctx.getStatusText());
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['realtime-status']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['connected']} */ ;
/** @type {__VLS_StyleScopedClasses['connecting']} */ ;
/** @type {__VLS_StyleScopedClasses['disconnected']} */ ;
/** @type {__VLS_StyleScopedClasses['status-text']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            isConnected: isConnected,
            isConnecting: isConnecting,
            handleReconnect: handleReconnect,
            getStatusText: getStatusText,
            getStatusColor: getStatusColor,
            getStatusIcon: getStatusIcon,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
