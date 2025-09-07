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
    alt: '',
    fit: 'cover',
    loading: 'lazy',
    threshold: 0.1,
    rootMargin: '50px',
    showSkeleton: true,
    retryCount: 3,
    retryDelay: 1000,
    preload: false
});
const emit = defineEmits();
// 响应式数据
const containerRef = (0, vue_1.ref)();
const imageRef = (0, vue_1.ref)();
const isLoading = (0, vue_1.ref)(true);
const hasError = (0, vue_1.ref)(false);
const isIntersecting = (0, vue_1.ref)(false);
const currentRetryCount = (0, vue_1.ref)(0);
const currentSrc = (0, vue_1.ref)('');
// 计算属性
const containerStyle = (0, vue_1.computed)(() => ({
    width: typeof props.width === 'number' ? `${props.width}px` : props.width,
    height: typeof props.height === 'number' ? `${props.height}px` : props.height,
}));
const imageStyle = (0, vue_1.computed)(() => ({
    objectFit: props.fit,
    width: '100%',
    height: '100%',
}));
// IntersectionObserver 实例
let observer = null;
// 方法
const loadImage = () => {
    if (hasError.value && currentRetryCount.value >= props.retryCount) {
        return;
    }
    isLoading.value = true;
    hasError.value = false;
    currentSrc.value = props.src;
};
const handleLoad = (event) => {
    isLoading.value = false;
    hasError.value = false;
    currentRetryCount.value = 0;
    emit('load', event);
};
const handleError = (event) => {
    isLoading.value = false;
    hasError.value = true;
    // 如果有fallback图片且还没尝试过，则使用fallback
    if (props.fallback && currentSrc.value !== props.fallback) {
        currentSrc.value = props.fallback;
        return;
    }
    emit('error', event);
    // 自动重试
    if (currentRetryCount.value < props.retryCount) {
        setTimeout(() => {
            currentRetryCount.value++;
            loadImage();
        }, props.retryDelay);
    }
};
const handleClick = (event) => {
    emit('click', event);
};
const retry = () => {
    currentRetryCount.value = 0;
    loadImage();
};
const setupIntersectionObserver = () => {
    if (!containerRef.value || props.loading === 'eager' || props.preload) {
        loadImage();
        return;
    }
    observer = new IntersectionObserver((entries) => {
        const entry = entries[0];
        isIntersecting.value = entry.isIntersecting;
        emit('intersect', entry);
        if (entry.isIntersecting && !currentSrc.value) {
            loadImage();
            observer?.unobserve(containerRef.value);
        }
    }, {
        threshold: props.threshold,
        rootMargin: props.rootMargin
    });
    observer.observe(containerRef.value);
};
const cleanup = () => {
    if (observer && containerRef.value) {
        observer.unobserve(containerRef.value);
        observer.disconnect();
        observer = null;
    }
};
// 监听 src 变化
(0, vue_1.watch)(() => props.src, () => {
    currentRetryCount.value = 0;
    hasError.value = false;
    if (props.loading === 'eager' || props.preload || isIntersecting.value) {
        loadImage();
    }
    else {
        currentSrc.value = '';
        isLoading.value = true;
    }
});
// 生命周期
(0, vue_1.onMounted)(() => {
    setupIntersectionObserver();
});
(0, vue_1.onUnmounted)(() => {
    cleanup();
});
// 暴露方法给父组件
const __VLS_exposed = {
    retry,
    reload: loadImage
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    alt: '',
    fit: 'cover',
    loading: 'lazy',
    threshold: 0.1,
    rootMargin: '50px',
    showSkeleton: true,
    retryCount: 3,
    retryDelay: 1000,
    preload: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['lazy-image-error-content']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-container']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-text']} */ ;
/** @type {__VLS_StyleScopedClasses['error-text']} */ ;
/** @type {__VLS_StyleScopedClasses['overlay-content']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "containerRef",
    ...{ class: "lazy-image-container" },
    ...{ class: ({ 'lazy-image-loading': __VLS_ctx.isLoading, 'lazy-image-error': __VLS_ctx.hasError }) },
    ...{ style: (__VLS_ctx.containerStyle) },
});
/** @type {typeof __VLS_ctx.containerRef} */ ;
if (__VLS_ctx.isLoading && !__VLS_ctx.hasError) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "lazy-image-placeholder" },
    });
    if (__VLS_ctx.showSkeleton) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "lazy-image-skeleton" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "skeleton-content" },
        });
    }
    else {
        const __VLS_0 = {}.ASpin;
        /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
            size: "small",
        }));
        const __VLS_2 = __VLS_1({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    }
    if (__VLS_ctx.loadingText) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "lazy-image-text" },
        });
        (__VLS_ctx.loadingText);
    }
}
else if (__VLS_ctx.hasError) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.retry) },
        ...{ class: "lazy-image-error-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "error-icon" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
        width: "24",
        height: "24",
        viewBox: "0 0 24 24",
        fill: "currentColor",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
        d: "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "error-text" },
    });
    (__VLS_ctx.errorText || '加载失败，点击重试');
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
        ...{ onLoad: (__VLS_ctx.handleLoad) },
        ...{ onError: (__VLS_ctx.handleError) },
        ...{ onClick: (__VLS_ctx.handleClick) },
        ref: "imageRef",
        src: (__VLS_ctx.currentSrc),
        alt: (__VLS_ctx.alt),
        ...{ class: (__VLS_ctx.imageClass) },
        ...{ style: (__VLS_ctx.imageStyle) },
    });
    /** @type {typeof __VLS_ctx.imageRef} */ ;
}
if (__VLS_ctx.overlay && !__VLS_ctx.isLoading && !__VLS_ctx.hasError) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "lazy-image-overlay" },
        ...{ class: (__VLS_ctx.overlayClass) },
    });
    var __VLS_4 = {};
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overlay-content" },
    });
    (__VLS_ctx.overlay);
}
/** @type {__VLS_StyleScopedClasses['lazy-image-container']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-loading']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-error']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-skeleton']} */ ;
/** @type {__VLS_StyleScopedClasses['skeleton-content']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-text']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-error-content']} */ ;
/** @type {__VLS_StyleScopedClasses['error-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['error-text']} */ ;
/** @type {__VLS_StyleScopedClasses['lazy-image-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['overlay-content']} */ ;
// @ts-ignore
var __VLS_5 = __VLS_4;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            containerRef: containerRef,
            imageRef: imageRef,
            isLoading: isLoading,
            hasError: hasError,
            currentSrc: currentSrc,
            containerStyle: containerStyle,
            imageStyle: imageStyle,
            handleLoad: handleLoad,
            handleError: handleError,
            handleClick: handleClick,
            retry: retry,
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
