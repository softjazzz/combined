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
// import { usePermissions } from '@/composables/usePermissions'
// 临时权限检查函数
const checkPermission = (resource, action: any,  context: any) => {
    // 临时实现，始终返回允许
    return { allowed: true, reason: '' };
};
const props = withDefaults(defineProps(), {
    type: 'default',
    size: 'middle',
    shape: 'default',
    danger: false,
    ghost: false,
    block: false,
    disabled: false,
    loading: false,
    noPermissionText: '暂无权限'
});
// const { checkPermission, hasAnyRole } = usePermissions()
// 权限检查结果
const permissionResult = (0, vue_1.computed)(() => {
    // 如果指定了角色，进行角色检查
    if (props.roles && props.roles.length > 0) {
        // const roleEnums = props.roles.map(role => role as any)
        // return hasAnyRole(roleEnums) ? { allowed: true } : { allowed: false, reason: '用户角色不足' }
        return { allowed: true, reason: '' }; // 临时允许
    }
    // 如果指定了资源和操作，进行权限检查
    if (props.resource && props.action) {
        return checkPermission(props.resource, props.action, props.context);
    }
    // 默认允许
    return { allowed: true };
});
// 是否显示按钮
const shouldShow = (0, vue_1.computed)(() => {
    return permissionResult.value.allowed;
});
// 按钮是否禁用
const isDisabled = (0, vue_1.computed)(() => {
    return props.disabled || !permissionResult.value.allowed;
});
// 按钮提示文本
const buttonTitle = (0, vue_1.computed)(() => {
    if (!permissionResult.value.allowed) {
        return permissionResult.value.reason || props.noPermissionText;
    }
    return undefined;
});
const emit = defineEmits();
const handleClick = (event) => {
    if (permissionResult.value.allowed) {
        emit('click', event);
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    type: 'default',
    size: 'middle',
    shape: 'default',
    danger: false,
    ghost: false,
    block: false,
    disabled: false,
    loading: false,
    noPermissionText: '暂无权限'
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
if (__VLS_ctx.shouldShow) {
    const __VLS_0 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        ...{ 'onClick': {} },
        type: (__VLS_ctx.type),
        size: (__VLS_ctx.size),
        shape: (__VLS_ctx.shape),
        danger: (__VLS_ctx.danger),
        ghost: (__VLS_ctx.ghost),
        block: (__VLS_ctx.block),
        disabled: (__VLS_ctx.isDisabled),
        loading: (__VLS_ctx.loading),
        title: (__VLS_ctx.buttonTitle),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onClick': {} },
        type: (__VLS_ctx.type),
        size: (__VLS_ctx.size),
        shape: (__VLS_ctx.shape),
        danger: (__VLS_ctx.danger),
        ghost: (__VLS_ctx.ghost),
        block: (__VLS_ctx.block),
        disabled: (__VLS_ctx.isDisabled),
        loading: (__VLS_ctx.loading),
        title: (__VLS_ctx.buttonTitle),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_4;
    let __VLS_5;
    let __VLS_6;
    const __VLS_7 = {
        onClick: (__VLS_ctx.handleClick)
    };
    var __VLS_8 = {};
    __VLS_3.slots.default;
    var __VLS_9 = {};
    var __VLS_3;
}
// @ts-ignore
var __VLS_10 = __VLS_9;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            shouldShow: shouldShow,
            isDisabled: isDisabled,
            buttonTitle: buttonTitle,
            handleClick: handleClick,
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
