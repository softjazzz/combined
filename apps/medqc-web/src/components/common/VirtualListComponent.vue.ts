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
const props = withDefaults(defineProps(), {
    buffer: 5,
    keyField: 'id',
    loading: false,
    hasMore: false
});
const emit = defineEmits();
// 响应式数据
const containerRef = (0, vue_1.ref)();
const scrollTop = (0, vue_1.ref)(0);
const isLoadingMore = (0, vue_1.ref)(false);
// 计算属性
const totalHeight = (0, vue_1.computed)(() => props.items.length * props.itemHeight);
const visibleCount = (0, vue_1.computed)(() => Math.ceil(props.containerHeight / props.itemHeight) + props.buffer * 2);
const startIndex = (0, vue_1.computed)(() => Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - props.buffer));
const endIndex = (0, vue_1.computed)(() => Math.min(props.items.length, startIndex.value + visibleCount.value));
const visibleItems = (0, vue_1.computed)(() => {
    const items = [];
    for (let i = startIndex.value; i < endIndex.value; i++) {
        if (props.items[i]) {
            items.push({
                index: i,
                data: props.items[i]
            });
        }
    }
    return items;
});
const offsetY = (0, vue_1.computed)(() => startIndex.value * props.itemHeight);
// 方法
const getItemKey = (item) => {
    if (typeof item === 'object' && item !== null) {
        return item[props.keyField] || item.id || JSON.stringify(item);
    }
    return item;
};
const handleScroll = async (event) => {
    const target = event.target;
    scrollTop.value = target.scrollTop;
    emit('scroll', {
        scrollTop: target.scrollTop,
        scrollLeft: target.scrollLeft
    });
    // 检查是否需要加载更多
    if (props.hasMore &&
        !props.loading &&
        !isLoadingMore.value &&
        props.loadMore &&
        target.scrollTop + target.clientHeight >= target.scrollHeight - 100) {
        isLoadingMore.value = true;
        try {
            await props.loadMore();
        }
        finally {
            isLoadingMore.value = false;
        }
        emit('loadMore');
    }
};
const scrollTo = (index) => {
    if (containerRef.value) {
        const targetScrollTop = index * props.itemHeight;
        containerRef.value.scrollTop = targetScrollTop;
        scrollTop.value = targetScrollTop;
    }
};
const scrollToTop = () => {
    scrollTo(0);
};
const scrollToBottom = () => {
    scrollTo(props.items.length - 1);
};
// 监听数据变化
(0, vue_1.watch)(() => props.items.length, async () => {
    await (0, vue_1.nextTick)();
    // 数据变化后重新计算可视区域
});
// 暴露方法给父组件
const __VLS_exposed = {
    scrollTo,
    scrollToTop,
    scrollToBottom
};
defineExpose(__VLS_exposed);
// 生命周期
(0, vue_1.onMounted)(() => {
    // 初始化时确保容器正确设置
    if (containerRef.value) {
        containerRef.value.scrollTop = 0;
    }
});
(0, vue_1.onUnmounted)(() => {
    // 清理工作
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    buffer: 5,
    keyField: 'id',
    loading: false,
    hasMore: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['virtual-list-container']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-container']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-container']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-container']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-container']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-loading']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ onScroll: (__VLS_ctx.handleScroll) },
    ref: "containerRef",
    ...{ class: "virtual-list-container" },
    ...{ style: ({ height: __VLS_ctx.containerHeight + 'px' }) },
});
/** @type {typeof __VLS_ctx.containerRef} */ ;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "virtual-list-spacer" },
    ...{ style: ({ height: __VLS_ctx.totalHeight + 'px' }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "virtual-list-content" },
    ...{ style: ({
            transform: `translateY(${__VLS_ctx.offsetY}px)`,
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0
        }) },
});
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.visibleItems))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (__VLS_ctx.getItemKey(item.data)),
        ...{ class: "virtual-list-item" },
        ...{ style: ({ height: __VLS_ctx.itemHeight + 'px' }) },
    });
    var __VLS_0 = {
        item: (item.data),
        index: (item.index),
    };
}
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "virtual-list-loading" },
        ...{ style: ({
                position: 'absolute',
                bottom: '10px',
                left: '50%',
                transform: 'translateX(-50%)'
            }) },
    });
    const __VLS_2 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_3 = __VLS_asFunctionalComponent(__VLS_2, new __VLS_2({
        size: "small",
    }));
    const __VLS_4 = __VLS_3({
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_3));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "ml-2" },
    });
}
/** @type {__VLS_StyleScopedClasses['virtual-list-container']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-spacer']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-content']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-item']} */ ;
/** @type {__VLS_StyleScopedClasses['virtual-list-loading']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
// @ts-ignore
var __VLS_1 = __VLS_0;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            containerRef: containerRef,
            totalHeight: totalHeight,
            visibleItems: visibleItems,
            offsetY: offsetY,
            getItemKey: getItemKey,
            handleScroll: handleScroll,
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
