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
const props = withDefaults(defineProps(), { backText: '返回',
    showBack: false,
    showBreadcrumb: true,
    breadcrumbs: () => [],
    actions: () => [],
    tabs: () => [],
    stats: () => [],
    size: 'medium',
    ghost: false
});
const emit = defineEmits();
const router = (0, vue_router_1.useRouter)();
// 当前激活的标签页
const activeTab = (0, vue_1.computed)({
    get: () => props.tabs.find(tab => !tab.disabled)?.key || '',
    set: (value: any) => {
        emit('tab-change', value);
    }
});
// 头部样式类
const headerClass = (0, vue_1.computed)(() => [
    'page-header-container',
    `page-header-${props.size}`,
    {
        'page-header-ghost': props.ghost
    }
]);
// 处理返回操作
const handleBack = () => {
    emit('back');
    // 默认返回上一页
    router.back();
};
// 处理操作按钮点击
const handleAction = (action) => {
    if (action.onClick) {
        action.onClick();
    }
    emit('action', action);
};
// 处理标签页切换
const handleTabChange = (key) => {
    emit('tab-change', key);
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({ backText: '返回',
    showBack: false,
    showBreadcrumb: true,
    breadcrumbs: () => [],
    actions: () => [],
    tabs: () => [],
    stats: () => [],
    size: 'medium',
    ghost: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['back-button']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-breadcrumb-link']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['header-main']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-section']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header-container']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
    ...{ class: (__VLS_ctx.headerClass) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-main" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-left" },
});
if (__VLS_ctx.showBack) {
    const __VLS_0 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        ...{ 'onClick': {} },
        type: "text",
        icon: (__VLS_ctx.h(__VLS_ctx.ArrowLeftOutlined)),
        ...{ class: "back-button" },
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClick': {} },
        type: "text",
        icon: (__VLS_ctx.h(__VLS_ctx.ArrowLeftOutlined)),
        ...{ class: "back-button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_4;
    let __VLS_5;
    let __VLS_6;
    const __VLS_7 = {
        onClick: (__VLS_ctx.handleBack)
    };
    __VLS_3.slots.default;
    (__VLS_ctx.backText);
    var __VLS_3;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "title-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
if (__VLS_ctx.icon) {
    const __VLS_8 = ((__VLS_ctx.icon));
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ...{ class: "title-icon" },
    }));
    const __VLS_10 = __VLS_9({
        ...{ class: "title-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
(__VLS_ctx.title);
if (__VLS_ctx.subtitle) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "page-subtitle" },
    });
    (__VLS_ctx.subtitle);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-right" },
});
var __VLS_12 = {};
const __VLS_14 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
    size: (12),
}));
const __VLS_16 = __VLS_15({
    size: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
__VLS_17.slots.default;
for (const [action] of __VLS_getVForSourceType((__VLS_ctx.actions))) {
    const __VLS_18 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
        ...{ 'onClick': {} },
        key: (action.key),
        type: (action.type || 'default'),
        icon: (action.icon ? __VLS_ctx.h(action.icon) : undefined),
        loading: (action.loading),
        disabled: (action.disabled),
    }));
    const __VLS_20 = __VLS_19({
        ...{ 'onClick': {} },
        key: (action.key),
        type: (action.type || 'default'),
        icon: (action.icon ? __VLS_ctx.h(action.icon) : undefined),
        loading: (action.loading),
        disabled: (action.disabled),
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
    let __VLS_22;
    let __VLS_23;
    let __VLS_24;
    const __VLS_25 = {
        onClick: (...[$event]) => {
            __VLS_ctx.handleAction(action);
        }
    };
    __VLS_21.slots.default;
    (action.text);
    var __VLS_21;
}
var __VLS_17;
if (__VLS_ctx.showBreadcrumb && __VLS_ctx.breadcrumbs.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "breadcrumb-section" },
    });
    const __VLS_26 = {}.ABreadcrumb;
    /** @type {[typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, ]} */ ;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({}));
    const __VLS_28 = __VLS_27({}, ...__VLS_functionalComponentArgsRest(__VLS_27));
    __VLS_29.slots.default;
    for (const [item] of __VLS_getVForSourceType((__VLS_ctx.breadcrumbs))) {
        const __VLS_30 = {}.ABreadcrumbItem;
        /** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
        // @ts-ignore
        const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
            key: (item.path),
        }));
        const __VLS_32 = __VLS_31({
            key: (item.path),
        }, ...__VLS_functionalComponentArgsRest(__VLS_31));
        __VLS_33.slots.default;
        if (item.icon) {
            const __VLS_34 = ((item.icon));
            // @ts-ignore
            const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
                ...{ class: "breadcrumb-icon" },
            }));
            const __VLS_36 = __VLS_35({
                ...{ class: "breadcrumb-icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_35));
        }
        if (item.path && !item.disabled) {
            const __VLS_38 = {}.RouterLink;
            /** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
            // @ts-ignore
            const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
                to: (item.path),
            }));
            const __VLS_40 = __VLS_39({
                to: (item.path),
            }, ...__VLS_functionalComponentArgsRest(__VLS_39));
            __VLS_41.slots.default;
            (item.name);
            var __VLS_41;
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.name);
        }
        var __VLS_33;
    }
    var __VLS_29;
}
if (__VLS_ctx.tabs.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tabs-section" },
    });
    const __VLS_42 = {}.ATabs;
    /** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
    // @ts-ignore
    const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
        ...{ 'onChange': {} },
        activeKey: (__VLS_ctx.activeTab),
    }));
    const __VLS_44 = __VLS_43({
        ...{ 'onChange': {} },
        activeKey: (__VLS_ctx.activeTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    let __VLS_46;
    let __VLS_47;
    let __VLS_48;
    const __VLS_49 = {
        onChange: (__VLS_ctx.handleTabChange)
    };
    __VLS_45.slots.default;
    for (const [tab] of __VLS_getVForSourceType((__VLS_ctx.tabs))) {
        const __VLS_50 = {}.ATabPane;
        /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
        // @ts-ignore
        const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
            key: (tab.key),
            tab: (tab.label),
            disabled: (tab.disabled),
        }));
        const __VLS_52 = __VLS_51({
            key: (tab.key),
            tab: (tab.label),
            disabled: (tab.disabled),
        }, ...__VLS_functionalComponentArgsRest(__VLS_51));
        __VLS_53.slots.default;
        {
            const { tab: __VLS_thisSlot } = __VLS_53.slots;
            if (tab.icon) {
                const __VLS_54 = ((tab.icon));
                // @ts-ignore
                const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
                    ...{ class: "tab-icon" },
                }));
                const __VLS_56 = __VLS_55({
                    ...{ class: "tab-icon" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_55));
            }
            (tab.label);
            if (tab.badge) {
                const __VLS_58 = {}.ABadge;
                /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
                // @ts-ignore
                const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
                    count: (tab.badge),
                    ...{ class: "tab-badge" },
                }));
                const __VLS_60 = __VLS_59({
                    count: (tab.badge),
                    ...{ class: "tab-badge" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_59));
            }
        }
        var __VLS_53;
    }
    var __VLS_45;
}
if (__VLS_ctx.stats.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stats-section" },
    });
    const __VLS_62 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
        gutter: ([16, 16]),
    }));
    const __VLS_64 = __VLS_63({
        gutter: ([16, 16]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_63));
    __VLS_65.slots.default;
    for (const [stat] of __VLS_getVForSourceType((__VLS_ctx.stats))) {
        const __VLS_66 = {}.ACol;
        /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
        // @ts-ignore
        const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
            key: (stat.key),
            xs: (12),
            sm: (8),
            md: (6),
            lg: (4),
        }));
        const __VLS_68 = __VLS_67({
            key: (stat.key),
            xs: (12),
            sm: (8),
            md: (6),
            lg: (4),
        }, ...__VLS_functionalComponentArgsRest(__VLS_67));
        __VLS_69.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stat-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stat-icon" },
            ...{ style: ({ color: stat.color }) },
        });
        if (stat.icon) {
            const __VLS_70 = ((stat.icon));
            // @ts-ignore
            const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({}));
            const __VLS_72 = __VLS_71({}, ...__VLS_functionalComponentArgsRest(__VLS_71));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stat-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stat-value" },
        });
        (stat.value);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "stat-label" },
        });
        (stat.label);
        var __VLS_69;
    }
    var __VLS_65;
}
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-main']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['back-button']} */ ;
/** @type {__VLS_StyleScopedClasses['title-section']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['title-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb-section']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['tabs-section']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-section']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-content']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
// @ts-ignore
var __VLS_13 = __VLS_12;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            ArrowLeftOutlined: icons_vue_1.ArrowLeftOutlined,
            activeTab: activeTab,
            headerClass: headerClass,
            handleBack: handleBack,
            handleAction: handleAction,
            handleTabChange: handleTabChange,
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
