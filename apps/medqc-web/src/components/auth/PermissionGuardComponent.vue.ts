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
import usePermissions_1 from '@/composables/usePermissions';
const props = withDefaults(defineProps(), {
    mode: 'all',
    fallback: 'hide',
    placeholder: '暂无权限访问此内容'
});
const { hasPermission, checkPermission, hasRole, hasAnyRole, ResourceType, PermissionAction } = (0, usePermissions_1.usePermissions)();
// 权限检查结果
const permissionResult = (0, vue_1.computed)(() => {
    // 如果指定了角色，进行角色检查
    if (props.roles && props.roles.length > 0) {
        const roleEnums = props.roles.map(role => role);
        return hasAnyRole(roleEnums) ? { allowed: true } : { allowed: false, reason: '用户角色不足' };
    }
    // 如果指定了资源和操作，进行权限检查
    if (props.resource && props.action) {
        const resource = props.resource;
        const action = props.action;
        return checkPermission(resource, action, props.context);
    }
    // 默认允许
    return { allowed: true };
});
// 是否显示内容
const shouldShow = (0, vue_1.computed)(() => {
    return permissionResult.value.allowed;
});
// 是否禁用
const isDisabled = (0, vue_1.computed)(() => {
    return !permissionResult.value.allowed && props.fallback === 'disabled';
});
// 是否显示占位符
const showPlaceholder = (0, vue_1.computed)(() => {
    return !permissionResult.value.allowed && props.fallback === 'placeholder';
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    mode: 'all',
    fallback: 'hide',
    placeholder: '暂无权限访问此内容'
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
if (__VLS_ctx.shouldShow || __VLS_ctx.showPlaceholder) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "permission-guard" },
    });
    if (__VLS_ctx.shouldShow) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: ({ 'permission-disabled': __VLS_ctx.isDisabled }) },
        });
        var __VLS_0 = {};
    }
    else if (__VLS_ctx.showPlaceholder) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "permission-placeholder" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "permission-placeholder-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "permission-placeholder-icon" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.svg, __VLS_intrinsicElements.svg)({
            width: "48",
            height: "48",
            viewBox: "0 0 24 24",
            fill: "none",
            stroke: "currentColor",
            'stroke-width': "2",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
            d: "M12 15v2",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.path)({
            d: "M12 7v2",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.circle)({
            cx: "12",
            cy: "12",
            r: "10",
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "permission-placeholder-text" },
        });
        (__VLS_ctx.placeholder);
        if (__VLS_ctx.permissionResult.reason) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
                ...{ class: "permission-placeholder-reason" },
            });
            (__VLS_ctx.permissionResult.reason);
        }
    }
}
/** @type {__VLS_StyleScopedClasses['permission-guard']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-disabled']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-placeholder']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-placeholder-content']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-placeholder-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-placeholder-text']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-placeholder-reason']} */ ;
// @ts-ignore
var __VLS_1 = __VLS_0;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            permissionResult: permissionResult,
            shouldShow: shouldShow,
            isDisabled: isDisabled,
            showPlaceholder: showPlaceholder,
        };
    },
    __typeProps: {},
    props: {},
});
const __VLS_component = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
    props: {},
});
export const default = {};
; /* PartiallyEnd: #4569/main.vue */
