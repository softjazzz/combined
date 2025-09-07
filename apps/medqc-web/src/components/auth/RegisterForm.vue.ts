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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const PasswordStrength_vue_1 = __importDefault(require("./PasswordStrength.vue"));
const props = withDefaults(defineProps(), {
    loading: false
});
const emit = defineEmits();
// Form reference
const formRef = (0, vue_1.ref)();
// Form data
const registerForm = (0, vue_1.reactive)({
    display_name: '',
    email: '',
    department: '',
    role: undefined,
    password: '',
    confirmPassword: '',
    phone: '',
    agreeTerms: false
});
// 科室列表
const departments = [
    { value: '内科', label: '内科' },
    { value: '外科', label: '外科' },
    { value: '妇产科', label: '妇产科' },
    { value: '儿科', label: '儿科' },
    { value: '急诊科', label: '急诊科' },
    { value: '骨科', label: '骨科' },
    { value: '神经科', label: '神经科' },
    { value: '心血管科', label: '心血管科' },
    { value: '呼吸科', label: '呼吸科' },
    { value: '消化科', label: '消化科' },
    { value: '泌尿科', label: '泌尿科' },
    { value: '眼科', label: '眼科' },
    { value: '耳鼻喉科', label: '耳鼻喉科' },
    { value: '皮肤科', label: '皮肤科' },
    { value: '精神科', label: '精神科' },
    { value: '康复科', label: '康复科' },
    { value: '影像科', label: '影像科' },
    { value: '检验科', label: '检验科' },
    { value: '药剂科', label: '药剂科' },
    { value: '质控科', label: '质控科' },
    { value: '信息科', label: '信息科' },
    { value: '其他', label: '其他' }
];
// Form validation rules
const registerRules = {
    display_name: [
        { required: true, message: '请输入姓名', trigger: 'blur' },
        { min: 2, message: '姓名至少2个字符', trigger: 'blur' },
        { max: 20, message: '姓名不能超过20个字符', trigger: 'blur' }
    ],
    email: [
        { required: true, message: '请输入邮箱', trigger: 'blur' },
        { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }
    ],
    department: [
        { required: true, message: '请选择科室', trigger: 'change' }
    ],
    role: [
        { required: true, message: '请选择申请角色', trigger: 'change' }
    ],
    password: [
        { required: true, message: '请输入密码', trigger: 'blur' },
        { min: 8, message: '密码至少8位字符', trigger: 'blur' },
        {
            validator: (_: any,  value: any) => {
                if (!value)
                    return Promise.resolve();
                const hasUpper = /[A-Z]/.test(value);
                const hasLower = /[a-z]/.test(value);
                const hasNumber = /\d/.test(value);
                if (!hasUpper || !hasLower || !hasNumber) {
                    return Promise.reject('密码必须包含大小写字母和数字');
                }
                return Promise.resolve();
            },
            trigger: 'blur'
        }
    ],
    confirmPassword: [
        { required: true, message: '请确认密码', trigger: 'blur' },
        {
            validator: (_: any,  value: any) => {
                if (!value)
                    return Promise.resolve();
                if (value !== registerForm.password) {
                    return Promise.reject('两次输入的密码不一致');
                }
                return Promise.resolve();
            },
            trigger: 'blur'
        }
    ],
    phone: [
        {
            validator: (_: any,  value: any) => {
                if (!value)
                    return Promise.resolve();
                if (!/^1[3-9]\d{9}$/.test(value)) {
                    return Promise.reject('手机号格式不正确');
                }
                return Promise.resolve();
            },
            trigger: 'blur'
        }
    ],
    agreeTerms: [
        {
            validator: (_: any,  value: any) => {
                if (!value) {
                    return Promise.reject('请阅读并同意服务条款');
                }
                return Promise.resolve();
            },
            trigger: 'change'
        }
    ]
};
// Handle register
const handleRegister = async () => {
    try {
        await formRef.value?.validate();
        const { confirmPassword, agreeTerms, ...registerData } = registerForm;
        emit('register', registerData);
    }
    catch (error) {
        if (error?.errorFields) {
            ant_design_vue_1.message.warning('请检查输入信息');
        }
    }
};
// Filter department options
const filterDepartment = (input, option) => {
    return option.children.toLowerCase().includes(input.toLowerCase());
};
// Show terms and privacy
const showTerms = () => emit('show-terms');
const showPrivacy = () => emit('show-privacy');
// Expose methods
const __VLS_exposed = {
    resetForm: () => {
        formRef.value?.resetFields();
        Object.assign(registerForm, {
            display_name: '',
            email: '',
            department: '',
            role: undefined,
            password: '',
            confirmPassword: '',
            phone: '',
            agreeTerms: false
        });
    },
    validateForm: () => formRef.value?.validate()
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    loading: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-password']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-checkbox-inner']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-dropdown']} */ ;
/** @type {__VLS_StyleScopedClasses['department-select']} */ ;
/** @type {__VLS_StyleScopedClasses['role-select']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-item']} */ ;
/** @type {__VLS_StyleScopedClasses['department-select']} */ ;
/** @type {__VLS_StyleScopedClasses['role-select']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-item-option-selected']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "register-form" },
});
const __VLS_0 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.registerForm),
    rules: (__VLS_ctx.registerRules),
    layout: "vertical",
    size: "large",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.registerForm),
    rules: (__VLS_ctx.registerRules),
    layout: "vertical",
    size: "large",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onFinish: (__VLS_ctx.handleRegister)
};
/** @type {typeof __VLS_ctx.formRef} */ ;
var __VLS_8 = {};
__VLS_3.slots.default;
const __VLS_10 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
    name: "display_name",
    ...{ class: "mb-4" },
}));
const __VLS_12 = __VLS_11({
    name: "display_name",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
__VLS_13.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative" },
});
const __VLS_14 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
    value: (__VLS_ctx.registerForm.display_name),
    placeholder: "请输入真实姓名",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}));
const __VLS_16 = __VLS_15({
    value: (__VLS_ctx.registerForm.display_name),
    placeholder: "请输入真实姓名",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_15));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" },
});
const __VLS_18 = {}.UserOutlined;
/** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({}));
const __VLS_20 = __VLS_19({}, ...__VLS_functionalComponentArgsRest(__VLS_19));
var __VLS_13;
const __VLS_22 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_23 = __VLS_asFunctionalComponent(__VLS_22, new __VLS_22({
    name: "email",
    ...{ class: "mb-4" },
}));
const __VLS_24 = __VLS_23({
    name: "email",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_23));
__VLS_25.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative" },
});
const __VLS_26 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
    value: (__VLS_ctx.registerForm.email),
    placeholder: "请输入工作邮箱",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}));
const __VLS_28 = __VLS_27({
    value: (__VLS_ctx.registerForm.email),
    placeholder: "请输入工作邮箱",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" },
});
const __VLS_30 = {}.MailOutlined;
/** @type {[typeof __VLS_components.MailOutlined, ]} */ ;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({}));
const __VLS_32 = __VLS_31({}, ...__VLS_functionalComponentArgsRest(__VLS_31));
var __VLS_25;
const __VLS_34 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
    name: "department",
    ...{ class: "mb-4" },
}));
const __VLS_36 = __VLS_35({
    name: "department",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_35));
__VLS_37.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
const __VLS_38 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
    value: (__VLS_ctx.registerForm.department),
    placeholder: "选择所属科室",
    size: "large",
    ...{ class: "department-select" },
    showSearch: true,
    filterOption: (__VLS_ctx.filterDepartment),
}));
const __VLS_40 = __VLS_39({
    value: (__VLS_ctx.registerForm.department),
    placeholder: "选择所属科室",
    size: "large",
    ...{ class: "department-select" },
    showSearch: true,
    filterOption: (__VLS_ctx.filterDepartment),
}, ...__VLS_functionalComponentArgsRest(__VLS_39));
__VLS_41.slots.default;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_42 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
        key: (dept.value),
        value: (dept.value),
    }));
    const __VLS_44 = __VLS_43({
        key: (dept.value),
        value: (dept.value),
    }, ...__VLS_functionalComponentArgsRest(__VLS_43));
    __VLS_45.slots.default;
    (dept.label);
    var __VLS_45;
}
var __VLS_41;
var __VLS_37;
const __VLS_46 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
    name: "role",
    ...{ class: "mb-4" },
}));
const __VLS_48 = __VLS_47({
    name: "role",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
__VLS_49.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
const __VLS_50 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
    value: (__VLS_ctx.registerForm.role),
    placeholder: "选择申请角色",
    size: "large",
    ...{ class: "role-select" },
}));
const __VLS_52 = __VLS_51({
    value: (__VLS_ctx.registerForm.role),
    placeholder: "选择申请角色",
    size: "large",
    ...{ class: "role-select" },
}, ...__VLS_functionalComponentArgsRest(__VLS_51));
__VLS_53.slots.default;
const __VLS_54 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    value: "doctor",
}));
const __VLS_56 = __VLS_55({
    value: "doctor",
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_57.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-6 h-6 rounded bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center text-white text-xs font-bold" },
});
var __VLS_57;
const __VLS_58 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
    value: "qc_staff",
}));
const __VLS_60 = __VLS_59({
    value: "qc_staff",
}, ...__VLS_functionalComponentArgsRest(__VLS_59));
__VLS_61.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-6 h-6 rounded bg-gradient-to-br from-blue-400 to-indigo-500 flex items-center justify-center text-white text-xs font-bold" },
});
var __VLS_61;
const __VLS_62 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    value: "viewer",
}));
const __VLS_64 = __VLS_63({
    value: "viewer",
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
__VLS_65.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-6 h-6 rounded bg-gradient-to-br from-purple-400 to-pink-500 flex items-center justify-center text-white text-xs font-bold" },
});
var __VLS_65;
var __VLS_53;
var __VLS_49;
const __VLS_66 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
    name: "password",
    ...{ class: "mb-4" },
}));
const __VLS_68 = __VLS_67({
    name: "password",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
__VLS_69.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative" },
});
const __VLS_70 = {}.AInputPassword;
/** @type {[typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    value: (__VLS_ctx.registerForm.password),
    placeholder: "请设置登录密码",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}));
const __VLS_72 = __VLS_71({
    value: (__VLS_ctx.registerForm.password),
    placeholder: "请设置登录密码",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" },
});
const __VLS_74 = {}.LockOutlined;
/** @type {[typeof __VLS_components.LockOutlined, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({}));
const __VLS_76 = __VLS_75({}, ...__VLS_functionalComponentArgsRest(__VLS_75));
var __VLS_69;
const __VLS_78 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
    name: "confirmPassword",
    ...{ class: "mb-4" },
}));
const __VLS_80 = __VLS_79({
    name: "confirmPassword",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_79));
__VLS_81.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative" },
});
const __VLS_82 = {}.AInputPassword;
/** @type {[typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    value: (__VLS_ctx.registerForm.confirmPassword),
    placeholder: "请再次输入密码",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}));
const __VLS_84 = __VLS_83({
    value: (__VLS_ctx.registerForm.confirmPassword),
    placeholder: "请再次输入密码",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" },
});
const __VLS_86 = {}.SafetyCertificateOutlined;
/** @type {[typeof __VLS_components.SafetyCertificateOutlined, ]} */ ;
// @ts-ignore
const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({}));
const __VLS_88 = __VLS_87({}, ...__VLS_functionalComponentArgsRest(__VLS_87));
var __VLS_81;
if (__VLS_ctx.registerForm.password) {
    /** @type {[typeof PasswordStrength, ]} */ ;
    // @ts-ignore
    const __VLS_90 = __VLS_asFunctionalComponent(PasswordStrength_vue_1.default, new PasswordStrength_vue_1.default({
        password: (__VLS_ctx.registerForm.password),
        ...{ class: "mb-4" },
    }));
    const __VLS_91 = __VLS_90({
        password: (__VLS_ctx.registerForm.password),
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_90));
}
const __VLS_93 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({
    name: "phone",
    ...{ class: "mb-4" },
}));
const __VLS_95 = __VLS_94({
    name: "phone",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_94));
__VLS_96.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative" },
});
const __VLS_97 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
    value: (__VLS_ctx.registerForm.phone),
    placeholder: "用于接收验证码",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}));
const __VLS_99 = __VLS_98({
    value: (__VLS_ctx.registerForm.phone),
    placeholder: "用于接收验证码",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 pl-11 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_98));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" },
});
const __VLS_101 = {}.PhoneOutlined;
/** @type {[typeof __VLS_components.PhoneOutlined, ]} */ ;
// @ts-ignore
const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({}));
const __VLS_103 = __VLS_102({}, ...__VLS_functionalComponentArgsRest(__VLS_102));
var __VLS_96;
const __VLS_105 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
    name: "agreeTerms",
    ...{ class: "mb-6" },
}));
const __VLS_107 = __VLS_106({
    name: "agreeTerms",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_106));
__VLS_108.slots.default;
const __VLS_109 = {}.ACheckbox;
/** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
// @ts-ignore
const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
    checked: (__VLS_ctx.registerForm.agreeTerms),
    ...{ class: "text-xs text-slate-300" },
}));
const __VLS_111 = __VLS_110({
    checked: (__VLS_ctx.registerForm.agreeTerms),
    ...{ class: "text-xs text-slate-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_110));
__VLS_112.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
    ...{ onClick: (__VLS_ctx.showTerms) },
    ...{ class: "text-cyan-300 hover:text-cyan-200 mx-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
    ...{ onClick: (__VLS_ctx.showPrivacy) },
    ...{ class: "text-cyan-300 hover:text-cyan-200 mx-1" },
});
var __VLS_112;
var __VLS_108;
const __VLS_113 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.loading),
    block: true,
    size: "large",
    ...{ class: "h-12 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 border-none font-semibold shadow-lg hover:shadow-xl" },
}));
const __VLS_115 = __VLS_114({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.loading),
    block: true,
    size: "large",
    ...{ class: "h-12 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 border-none font-semibold shadow-lg hover:shadow-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
__VLS_116.slots.default;
if (!__VLS_ctx.loading) {
    const __VLS_117 = {}.UserAddOutlined;
    /** @type {[typeof __VLS_components.UserAddOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({
        ...{ class: "mr-2" },
    }));
    const __VLS_119 = __VLS_118({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_118));
}
var __VLS_116;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-6 p-4 rounded-xl bg-blue-500/10 border border-blue-500/20" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-start gap-3" },
});
const __VLS_121 = {}.InfoCircleOutlined;
/** @type {[typeof __VLS_components.InfoCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
    ...{ class: "text-blue-400 text-sm mt-0.5" },
}));
const __VLS_123 = __VLS_122({
    ...{ class: "text-blue-400 text-sm mt-0.5" },
}, ...__VLS_functionalComponentArgsRest(__VLS_122));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-blue-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "font-medium mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
    ...{ class: "space-y-1 text-blue-200/80" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({});
/** @type {__VLS_StyleScopedClasses['register-form']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['pl-11']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['left-3.5']} */ ;
/** @type {__VLS_StyleScopedClasses['top-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['-translate-y-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['pl-11']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['left-3.5']} */ ;
/** @type {__VLS_StyleScopedClasses['top-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['-translate-y-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['department-select']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['role-select']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-teal-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-purple-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-pink-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['pl-11']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['left-3.5']} */ ;
/** @type {__VLS_StyleScopedClasses['top-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['-translate-y-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['pl-11']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['left-3.5']} */ ;
/** @type {__VLS_StyleScopedClasses['top-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['-translate-y-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['pl-11']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['left-3.5']} */ ;
/** @type {__VLS_StyleScopedClasses['top-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['-translate-y-1/2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-cyan-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-cyan-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-1']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-r']} */ ;
/** @type {__VLS_StyleScopedClasses['from-emerald-500']} */ ;
/** @type {__VLS_StyleScopedClasses['to-teal-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:from-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:to-teal-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-none']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-200/80']} */ ;
// @ts-ignore
var __VLS_9 = __VLS_8;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            UserOutlined: icons_vue_1.UserOutlined,
            MailOutlined: icons_vue_1.MailOutlined,
            LockOutlined: icons_vue_1.LockOutlined,
            SafetyCertificateOutlined: icons_vue_1.SafetyCertificateOutlined,
            PhoneOutlined: icons_vue_1.PhoneOutlined,
            UserAddOutlined: icons_vue_1.UserAddOutlined,
            InfoCircleOutlined: icons_vue_1.InfoCircleOutlined,
            PasswordStrength: PasswordStrength_vue_1.default,
            formRef: formRef,
            registerForm: registerForm,
            departments: departments,
            registerRules: registerRules,
            handleRegister: handleRegister,
            filterDepartment: filterDepartment,
            showTerms: showTerms,
            showPrivacy: showPrivacy,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ...__VLS_exposed,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
