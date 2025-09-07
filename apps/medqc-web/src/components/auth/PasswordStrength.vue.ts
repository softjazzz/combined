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
    showTips: true,
    minLength: 8
});
// 密码强度检查
const hasMinLength = (0, vue_1.computed)(() => props.password.length >= props.minLength);
const hasUppercase = (0, vue_1.computed)(() => /[A-Z]/.test(props.password));
const hasLowercase = (0, vue_1.computed)(() => /[a-z]/.test(props.password));
const hasNumbers = (0, vue_1.computed)(() => /\d/.test(props.password));
const hasSymbols = (0, vue_1.computed)(() => /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(props.password));
// 密码要求列表
const requirements = (0, vue_1.computed)(() => [
    {
        key: 'length',
        text: `至少${props.minLength}个字符`,
        met: hasMinLength.value
    },
    {
        key: 'uppercase',
        text: '包含大写字母',
        met: hasUppercase.value
    },
    {
        key: 'lowercase',
        text: '包含小写字母',
        met: hasLowercase.value
    },
    {
        key: 'numbers',
        text: '包含数字',
        met: hasNumbers.value
    },
    {
        key: 'symbols',
        text: '包含特殊符号',
        met: hasSymbols.value
    }
]);
// 计算密码强度等级 (1-4)
const strengthLevel = (0, vue_1.computed)(() => {
    let score = 0;
    if (hasMinLength.value)
        score++;
    if (hasUppercase.value)
        score++;
    if (hasLowercase.value)
        score++;
    if (hasNumbers.value)
        score++;
    if (hasSymbols.value)
        score++;
    // 额外加分项
    if (props.password.length >= 12)
        score += 0.5;
    if (props.password.length >= 16)
        score += 0.5;
    // 转换为1-4等级
    if (score >= 4.5)
        return 4;
    if (score >= 3.5)
        return 3;
    if (score >= 2)
        return 2;
    return 1;
});
// 强度文本
const strengthText = (0, vue_1.computed)(() => {
    switch (strengthLevel.value) {
        case 4: return '很强';
        case 3: return '强';
        case 2: return '中等';
        default: return '弱';
    }
});
// 强度文本颜色
const strengthTextClass = (0, vue_1.computed)(() => {
    switch (strengthLevel.value) {
        case 4: return 'text-emerald-400 font-medium';
        case 3: return 'text-blue-400 font-medium';
        case 2: return 'text-amber-400 font-medium';
        default: return 'text-red-400 font-medium';
    }
});
// 强度条颜色
const strengthColorClass = (0, vue_1.computed)(() => {
    switch (strengthLevel.value) {
        case 4: return 'bg-emerald-500';
        case 3: return 'bg-blue-500';
        case 2: return 'bg-amber-500';
        default: return 'bg-red-500';
    }
});
// 密码强度评分 (0-100)
const strengthScore = (0, vue_1.computed)(() => {
    return Math.min(100, (strengthLevel.value / 4) * 100);
});
// 是否为强密码
const isStrongPassword = (0, vue_1.computed)(() => strengthLevel.value >= 3);
// 暴露给父组件的属性和方法
const __VLS_exposed = {
    strengthLevel,
    strengthScore,
    isStrongPassword,
    requirements: requirements.value
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    showTips: true,
    minLength: 8
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['password-strength']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
// CSS variable injection 
// CSS variable injection end 
if (__VLS_ctx.password) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "password-strength" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between text-xs" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-slate-400" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: (__VLS_ctx.strengthTextClass) },
    });
    (__VLS_ctx.strengthText);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex gap-1 mt-1" },
    });
    for (const [i] of __VLS_getVForSourceType((4))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div)({
            key: (i),
            ...{ class: "h-1 flex-1 rounded-full transition-colors duration-300" },
            ...{ class: (i <= __VLS_ctx.strengthLevel ? __VLS_ctx.strengthColorClass : 'bg-slate-600') },
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "space-y-1" },
    });
    for (const [requirement] of __VLS_getVForSourceType((__VLS_ctx.requirements))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (requirement.key),
            ...{ class: "flex items-center gap-2 text-xs" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "w-3 h-3 rounded-full flex items-center justify-center" },
            ...{ class: (requirement.met ? 'bg-emerald-500' : 'bg-slate-600') },
        });
        if (requirement.met) {
            const __VLS_0 = {}.CheckOutlined;
            /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
                ...{ class: "text-white text-[8px]" },
            }));
            const __VLS_2 = __VLS_1({
                ...{ class: "text-white text-[8px]" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: (requirement.met ? 'text-emerald-400' : 'text-slate-400') },
        });
        (requirement.text);
    }
    if (__VLS_ctx.showTips && __VLS_ctx.strengthLevel < 3) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-3 p-2 rounded-lg bg-amber-500/10 border border-amber-500/20" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-start gap-2" },
        });
        const __VLS_4 = {}.WarningOutlined;
        /** @type {[typeof __VLS_components.WarningOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
            ...{ class: "text-amber-400 text-xs mt-0.5" },
        }));
        const __VLS_6 = __VLS_5({
            ...{ class: "text-amber-400 text-xs mt-0.5" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_5));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-amber-300" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "font-medium mb-1" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
            ...{ class: "space-y-0.5 text-amber-200/80" },
        });
        if (!__VLS_ctx.hasMinLength) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
        }
        if (!__VLS_ctx.hasUppercase) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
        }
        if (!__VLS_ctx.hasLowercase) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
        }
        if (!__VLS_ctx.hasNumbers) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
        }
        if (!__VLS_ctx.hasSymbols) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
        }
    }
}
/** @type {__VLS_StyleScopedClasses['password-strength']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['h-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[8px]']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-amber-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-amber-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-300']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-200/80']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            CheckOutlined: icons_vue_1.CheckOutlined,
            WarningOutlined: icons_vue_1.WarningOutlined,
            hasMinLength: hasMinLength,
            hasUppercase: hasUppercase,
            hasLowercase: hasLowercase,
            hasNumbers: hasNumbers,
            hasSymbols: hasSymbols,
            requirements: requirements,
            strengthLevel: strengthLevel,
            strengthText: strengthText,
            strengthTextClass: strengthTextClass,
            strengthColorClass: strengthColorClass,
        };
    },
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ...__VLS_exposed,
        };
    },
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
