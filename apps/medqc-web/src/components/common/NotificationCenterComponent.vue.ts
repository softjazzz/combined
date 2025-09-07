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
import notification_1 from '../../stores/notification';
import icons_vue_1 from '@ant-design/icons-vue';
// 使用通知store
const notificationStore = (0, notification_1.useNotificationStore)();
// 计算属性
const notifications = (0, vue_1.computed)(() => notificationStore.notifications);
const unreadCount = (0, vue_1.computed)(() => notificationStore.unreadCount);
const hasNotifications = (0, vue_1.computed)(() => notificationStore.hasNotifications);
// 获取通知图标
const getNotificationIcon = (type) => {
    const iconMap = {
        'success': icons_vue_1.CheckCircleOutlined,
        'error': icons_vue_1.CloseCircleOutlined,
        'warning': icons_vue_1.ExclamationCircleOutlined,
        'info': icons_vue_1.InfoCircleOutlined
    };
    return iconMap[type] || icons_vue_1.InfoCircleOutlined;
};
// 获取通知颜色
const getNotificationColor = (type) => {
    const colorMap = {
        'success': '#52c41a',
        'error': '#ff4d4f',
        'warning': '#faad14',
        'info': '#1890ff'
    };
    return colorMap[type] || '#1890ff';
};
// 处理通知点击
const handleNotificationClick = (notificationItem) => {
    notificationStore.markAsRead(notificationItem.id);
};
// 关闭通知
const handleCloseNotification = (notificationItem) => {
    notificationStore.removeNotification(notificationItem.id);
};
// 清空所有通知
const handleClearAll = () => {
    notificationStore.clearAll();
};
// 标记所有为已读
const handleMarkAllRead = () => {
    notificationStore.markAllAsRead();
};
// 格式化时间
const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    if (diff < 60000) { // 1分钟内
        return '刚刚';
    }
    else if (diff < 3600000) { // 1小时内
        return `${Math.floor(diff / 60000)}分钟前`;
    }
    else if (diff < 86400000) { // 1天内
        return `${Math.floor(diff / 3600000)}小时前`;
    }
    else {
        return date.toLocaleDateString();
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['notification-trigger']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "notification-center" },
});
const __VLS_0 = {}.ADropdown;
/** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    trigger: (['click']),
    placement: "bottomRight",
    overlayStyle: ({ width: '400px', maxHeight: '500px' }),
}));
const __VLS_2 = __VLS_1({
    trigger: (['click']),
    placement: "bottomRight",
    overlayStyle: ({ width: '400px', maxHeight: '500px' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    type: "text",
    shape: "circle",
    size: "large",
    ...{ class: "notification-trigger" },
    ...{ class: ({ 'has-notifications': __VLS_ctx.hasNotifications }) },
}));
const __VLS_6 = __VLS_5({
    type: "text",
    shape: "circle",
    size: "large",
    ...{ class: "notification-trigger" },
    ...{ class: ({ 'has-notifications': __VLS_ctx.hasNotifications }) },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_7.slots;
    const __VLS_8 = {}.ABadge;
    /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        count: (__VLS_ctx.unreadCount),
        offset: ([0, 0]),
    }));
    const __VLS_10 = __VLS_9({
        count: (__VLS_ctx.unreadCount),
        offset: ([0, 0]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    const __VLS_12 = {}.BellOutlined;
    /** @type {[typeof __VLS_components.BellOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
    var __VLS_11;
}
var __VLS_7;
{
    const { overlay: __VLS_thisSlot } = __VLS_3.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "notification-dropdown" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "notification-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-base font-semibold text-gray-900" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center space-x-2" },
    });
    if (__VLS_ctx.unreadCount > 0) {
        const __VLS_16 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "text-xs" },
        }));
        const __VLS_18 = __VLS_17({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "text-xs" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        let __VLS_20;
        let __VLS_21;
        let __VLS_22;
        const __VLS_23 = {
            onClick: (__VLS_ctx.handleMarkAllRead)
        };
        __VLS_19.slots.default;
        var __VLS_19;
    }
    if (__VLS_ctx.hasNotifications) {
        const __VLS_24 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "text-xs text-red-500" },
        }));
        const __VLS_26 = __VLS_25({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "text-xs text-red-500" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
        let __VLS_28;
        let __VLS_29;
        let __VLS_30;
        const __VLS_31 = {
            onClick: (__VLS_ctx.handleClearAll)
        };
        __VLS_27.slots.default;
        var __VLS_27;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "notification-list" },
    });
    if (!__VLS_ctx.hasNotifications) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "notification-empty" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-center py-8" },
        });
        const __VLS_32 = {}.BellOutlined;
        /** @type {[typeof __VLS_components.BellOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
            ...{ class: "text-4xl text-gray-300 mb-2" },
        }));
        const __VLS_34 = __VLS_33({
            ...{ class: "text-4xl text-gray-300 mb-2" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-500" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "max-h-96 overflow-y-auto" },
        });
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.notifications))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ onClick: (...[$event]) => {
                        if (!!(!__VLS_ctx.hasNotifications))
                            return;
                        __VLS_ctx.handleNotificationClick(item);
                    } },
                key: (item.id),
                ...{ class: "notification-item" },
                ...{ class: ({ 'unread': !item.read }) },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "notification-content" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "notification-icon" },
            });
            const __VLS_36 = ((__VLS_ctx.getNotificationIcon(item.type)));
            // @ts-ignore
            const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
                ...{ style: ({ color: __VLS_ctx.getNotificationColor(item.type) }) },
            }));
            const __VLS_38 = __VLS_37({
                ...{ style: ({ color: __VLS_ctx.getNotificationColor(item.type) }) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_37));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "notification-body" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "notification-title" },
            });
            (item.title);
            if (item.message) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "notification-message" },
                });
                (item.message);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "notification-time" },
            });
            (__VLS_ctx.formatTime(item.timestamp));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "notification-actions" },
            });
            const __VLS_40 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
                ...{ 'onClick': {} },
                type: "text",
                size: "small",
                shape: "circle",
                ...{ class: "text-gray-400 hover:text-gray-600" },
            }));
            const __VLS_42 = __VLS_41({
                ...{ 'onClick': {} },
                type: "text",
                size: "small",
                shape: "circle",
                ...{ class: "text-gray-400 hover:text-gray-600" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_41));
            let __VLS_44;
            let __VLS_45;
            let __VLS_46;
            const __VLS_47 = {
                onClick: (...[$event]) => {
                    if (!!(!__VLS_ctx.hasNotifications))
                        return;
                    __VLS_ctx.handleCloseNotification(item);
                }
            };
            __VLS_43.slots.default;
            {
                const { icon: __VLS_thisSlot } = __VLS_43.slots;
                const __VLS_48 = {}.CloseOutlined;
                /** @type {[typeof __VLS_components.CloseOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
                const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
            }
            var __VLS_43;
        }
    }
}
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['notification-center']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-trigger']} */ ;
/** @type {__VLS_StyleScopedClasses['has-notifications']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-dropdown']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-header']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-500']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-96']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-item']} */ ;
/** @type {__VLS_StyleScopedClasses['unread']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-content']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-body']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-title']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-message']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-time']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-gray-600']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            BellOutlined: icons_vue_1.BellOutlined,
            CloseOutlined: icons_vue_1.CloseOutlined,
            notifications: notifications,
            unreadCount: unreadCount,
            hasNotifications: hasNotifications,
            getNotificationIcon: getNotificationIcon,
            getNotificationColor: getNotificationColor,
            handleNotificationClick: handleNotificationClick,
            handleCloseNotification: handleCloseNotification,
            handleClearAll: handleClearAll,
            handleMarkAllRead: handleMarkAllRead,
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
