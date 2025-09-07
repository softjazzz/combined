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
import icons_vue_1 from '@ant-design/icons-vue';
const props = withDefaults(defineProps(), {
    type: 'empty',
    title: '',
    description: '',
    iconColor: '#d9d9d9',
    size: 'medium',
    actions: () => []
});
const emit = defineEmits();
// 默认配置
const defaultConfig = {
    empty: {
        title: '暂无数据',
        description: '当前没有可显示的内容',
        icon: icons_vue_1.InboxOutlined
    },
    error: {
        title: '加载失败',
        description: '数据加载过程中发生错误，请稍后重试',
        icon: icons_vue_1.ExclamationCircleOutlined,
        iconColor: '#ff4d4f'
    },
    network: {
        title: '网络连接失败',
        description: '请检查网络连接后重试',
        icon: icons_vue_1.DisconnectOutlined,
        iconColor: '#faad14'
    },
    search: {
        title: '无搜索结果',
        description: '未找到符合条件的内容，请尝试其他关键词',
        icon: icons_vue_1.SearchOutlined
    },
    permission: {
        title: '无访问权限',
        description: '您没有权限查看此内容，请联系管理员',
        icon: icons_vue_1.UserOutlined,
        iconColor: '#faad14'
    },
    maintenance: {
        title: '系统维护中',
        description: '系统正在维护，请稍后再试',
        icon: icons_vue_1.SettingOutlined,
        iconColor: '#1890ff'
    },
    custom: {
        title: '自定义状态',
        description: '',
        icon: icons_vue_1.CloudServerOutlined
    }
};
// 计算样式类
const containerClass = (0, vue_1.computed)(() => [
    'empty-state-container',
    `empty-state-${props.size}`,
    `empty-state-${props.type}`
]);
const iconClass = (0, vue_1.computed)(() => [
    'empty-icon-wrapper',
    `empty-icon-${props.size}`,
    `empty-icon-${props.type}`
]);
// 获取配置
const config = (0, vue_1.computed)(() => defaultConfig[props.type]);
// 获取标题
const title = (0, vue_1.computed)(() => props.title || config.value.title);
// 获取描述
const description = (0, vue_1.computed)(() => props.description || config.value.description);
// 获取图标颜色
const iconColor = (0, vue_1.computed)(() => {
    const configValue = config.value;
    return props.iconColor || configValue.iconColor || '#d9d9d9';
});
// 获取默认图标
const getDefaultIcon = () => {
    return props.icon || config.value.icon || icons_vue_1.InboxOutlined;
};
// 处理操作按钮点击
const handleAction = (action) => {
    if (action.onClick) {
        action.onClick();
    }
    emit('action', action);
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    type: 'empty',
    title: '',
    description: '',
    iconColor: '#d9d9d9',
    size: 'medium',
    actions: () => []
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['empty-image']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-component']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-component']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-component']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-container']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-component']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-container']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-content']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-large']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-container']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-title']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-description']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-component']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state-interactive']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "empty-state" },
    ...{ class: (__VLS_ctx.containerClass) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "empty-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "empty-icon" },
    ...{ class: (__VLS_ctx.iconClass) },
});
if (__VLS_ctx.icon) {
    const __VLS_0 = ((__VLS_ctx.icon));
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        ...{ class: "icon-component" },
        ...{ style: ({ color: __VLS_ctx.iconColor }) },
    }));
    const __VLS_2 = __VLS_1({
        ...{ class: "icon-component" },
        ...{ style: ({ color: __VLS_ctx.iconColor }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
}
else if (__VLS_ctx.image) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-image" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
        src: (__VLS_ctx.image),
        alt: (__VLS_ctx.title),
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "default-icon" },
    });
    const __VLS_4 = ((__VLS_ctx.getDefaultIcon()));
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        ...{ class: "icon-component" },
        ...{ style: ({ color: __VLS_ctx.iconColor }) },
    }));
    const __VLS_6 = __VLS_5({
        ...{ class: "icon-component" },
        ...{ style: ({ color: __VLS_ctx.iconColor }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "empty-title" },
});
(__VLS_ctx.title);
if (__VLS_ctx.description) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "empty-description" },
    });
    (__VLS_ctx.description);
}
if (__VLS_ctx.actions.length > 0 || __VLS_ctx.$slots.actions) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-actions" },
    });
    var __VLS_8 = {};
    const __VLS_10 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
        size: (12),
    }));
    const __VLS_12 = __VLS_11({
        size: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_13.slots.default;
    for (const [action] of __VLS_getVForSourceType((__VLS_ctx.actions))) {
        const __VLS_14 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
            ...{ 'onClick': {} },
            key: (action.key),
            type: (action.type || 'primary'),
            size: (action.size || 'large'),
            icon: (action.icon ? __VLS_ctx.h(action.icon) : undefined),
            loading: (action.loading),
            disabled: (action.disabled),
        }));
        const __VLS_16 = __VLS_15({
            ...{ 'onClick': {} },
            key: (action.key),
            type: (action.type || 'primary'),
            size: (action.size || 'large'),
            icon: (action.icon ? __VLS_ctx.h(action.icon) : undefined),
            loading: (action.loading),
            disabled: (action.disabled),
        }, ...__VLS_functionalComponentArgsRest(__VLS_15));
        let __VLS_18;
        let __VLS_19;
        let __VLS_20;
        const __VLS_21 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.actions.length > 0 || __VLS_ctx.$slots.actions))
                    return;
                __VLS_ctx.handleAction(action);
            }
        };
        __VLS_17.slots.default;
        (action.text);
        var __VLS_17;
    }
    var __VLS_13;
}
if (__VLS_ctx.$slots.extra) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-extra" },
    });
    var __VLS_22 = {};
}
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-content']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-component']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-image']} */ ;
/** @type {__VLS_StyleScopedClasses['default-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['icon-component']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-title']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-description']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-extra']} */ ;
// @ts-ignore
var __VLS_9 = __VLS_8, __VLS_23 = __VLS_22;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            containerClass: containerClass,
            iconClass: iconClass,
            title: title,
            description: description,
            iconColor: iconColor,
            getDefaultIcon: getDefaultIcon,
            handleAction: handleAction,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
const __VLS_component = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = {};
; /* PartiallyEnd: #4569/main.vue */
