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
const props = withDefaults(defineProps(), {
    type: 'spinner',
    size: 'medium',
    color: 'primary',
    text: '加载中...',
    showText: true,
    center: true
});
const containerClass = (0, vue_1.computed)(() => [
    'loading-container',
    `loading-${props.size}`,
    `loading-${props.color}`,
    {
        'loading-center': props.center
    }
]);
const spinnerClass = (0, vue_1.computed)(() => [
    'spinner-animation',
    `spinner-${props.size}`,
    `spinner-${props.color}`
]);
const pulseClass = (0, vue_1.computed)(() => [
    'pulse-animation',
    `pulse-${props.size}`,
    `pulse-${props.color}`
]);
const waveClass = (0, vue_1.computed)(() => [
    'wave-animation',
    `wave-${props.size}`,
    `wave-${props.color}`
]);
const medicalClass = (0, vue_1.computed)(() => [
    'medical-animation',
    `medical-${props.size}`,
    `medical-${props.color}`
]);
const textClass = (0, vue_1.computed)(() => [
    'text-animation',
    `text-${props.size}`,
    `text-${props.color}`
]);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    type: 'spinner',
    size: 'medium',
    color: 'primary',
    text: '加载中...',
    showText: true,
    center: true
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['cross-horizontal']} */ ;
/** @type {__VLS_StyleScopedClasses['cross-vertical']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-large']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "loading-spinner" },
    ...{ class: (__VLS_ctx.containerClass) },
});
if (__VLS_ctx.type === 'spinner') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner" },
        ...{ class: (__VLS_ctx.spinnerClass) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "spinner-circle" },
    });
}
else if (__VLS_ctx.type === 'pulse') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "pulse-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "pulse-dot" },
        ...{ class: (__VLS_ctx.pulseClass) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "pulse-dot" },
        ...{ class: (__VLS_ctx.pulseClass) },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "pulse-dot" },
        ...{ class: (__VLS_ctx.pulseClass) },
        ...{ style: {} },
    });
}
else if (__VLS_ctx.type === 'wave') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "wave-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "wave-bar" },
        ...{ class: (__VLS_ctx.waveClass) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "wave-bar" },
        ...{ class: (__VLS_ctx.waveClass) },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "wave-bar" },
        ...{ class: (__VLS_ctx.waveClass) },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "wave-bar" },
        ...{ class: (__VLS_ctx.waveClass) },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "wave-bar" },
        ...{ class: (__VLS_ctx.waveClass) },
        ...{ style: {} },
    });
}
else if (__VLS_ctx.type === 'medical') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "medical-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "medical-cross" },
        ...{ class: (__VLS_ctx.medicalClass) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "cross-horizontal" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "cross-vertical" },
    });
}
if (__VLS_ctx.showText) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-text" },
        ...{ class: (__VLS_ctx.textClass) },
    });
    (__VLS_ctx.text);
}
/** @type {__VLS_StyleScopedClasses['loading-spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner']} */ ;
/** @type {__VLS_StyleScopedClasses['spinner-circle']} */ ;
/** @type {__VLS_StyleScopedClasses['pulse-container']} */ ;
/** @type {__VLS_StyleScopedClasses['pulse-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['pulse-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['pulse-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['wave-container']} */ ;
/** @type {__VLS_StyleScopedClasses['wave-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['wave-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['wave-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['wave-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['wave-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-container']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-cross']} */ ;
/** @type {__VLS_StyleScopedClasses['cross-horizontal']} */ ;
/** @type {__VLS_StyleScopedClasses['cross-vertical']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-text']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            containerClass: containerClass,
            spinnerClass: spinnerClass,
            pulseClass: pulseClass,
            waveClass: waveClass,
            medicalClass: medicalClass,
            textClass: textClass,
        };
    },
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
