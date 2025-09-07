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
const AvatarUpload_vue_1 = __importDefault(require("./AvatarUpload.vue"));
const props = withDefaults(defineProps(), {
    loading: false
});
const emit = defineEmits();
// Form reference
const formRef = (0, vue_1.ref)();
// Form data
const profileForm = (0, vue_1.reactive)({
    avatar: '',
    display_name: '',
    email: '',
    department: '',
    phone: '',
    bio: '',
    notifications: {
        email: true,
        sms: false,
        push: true
    }
});
// 科室列表（复用注册表单的）
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
// 用户角色
const userRoles = (0, vue_1.computed)(() => props.user?.roles || []);
// Form validation rules
const profileRules = {
    display_name: [
        { required: true, message: '请输入姓名', trigger: 'blur' },
        { min: 2, message: '姓名至少2个字符', trigger: 'blur' },
        { max: 20, message: '姓名不能超过20个字符', trigger: 'blur' }
    ],
    department: [
        { required: true, message: '请选择科室', trigger: 'change' }
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
    bio: [
        { max: 200, message: '个人简介不能超过200个字符', trigger: 'blur' }
    ]
};
// 初始化表单数据
const initializeForm = () => {
    if (props.user) {
        Object.assign(profileForm, {
            avatar: props.user.avatar || '',
            display_name: props.user.display_name || '',
            email: props.user.email || '',
            department: props.user.department || '',
            phone: props.user.phone || '',
            bio: props.user.bio || '',
            notifications: {
                email: props.user.notifications?.email ?? true,
                sms: props.user.notifications?.sms ?? false,
                push: props.user.notifications?.push ?? true
            }
        });
    }
};
// Handle form submit
const handleSubmit = async () => {
    try {
        await formRef.value?.validate();
        emit('update-profile', { ...profileForm });
    }
    catch (error) {
        if (error?.errorFields) {
            ant_design_vue_1.message.warning('请检查输入信息');
        }
    }
};
// Handle form reset
const handleReset = () => {
    initializeForm();
    ant_design_vue_1.message.info('表单已重置');
};
// Handle avatar upload success
const handleAvatarSuccess = (url) => {
    profileForm.avatar = url;
};
// Handle avatar upload error
const handleAvatarError = (error) => {
    console.error('头像上传失败:', error);
};
// Filter department options
const filterDepartment = (input, option) => {
    return option.children.toLowerCase().includes(input.toLowerCase());
};
// Get role color
const getRoleColor = (role) => {
    const colors = {
        admin: 'from-orange-400 to-amber-500',
        qc_manager: 'from-blue-400 to-indigo-500',
        qc_staff: 'from-cyan-400 to-teal-500',
        doctor: 'from-emerald-400 to-teal-500',
        viewer: 'from-purple-400 to-pink-500'
    };
    return colors[role] || 'from-gray-400 to-gray-500';
};
// Get role initial
const getRoleInitial = (role) => {
    const initials = {
        admin: 'A',
        qc_manager: 'Q',
        qc_staff: 'S',
        doctor: 'D',
        viewer: 'V'
    };
    return initials[role] || 'U';
};
// Get role label
const getRoleLabel = (role) => {
    const labels = {
        admin: '系统管理员',
        qc_manager: '质控管理员',
        qc_staff: '质控员',
        doctor: '医生',
        viewer: '查看者'
    };
    return labels[role] || '未知角色';
};
// Initialize on mount
(0, vue_1.onMounted)(() => {
    initializeForm();
});
// Watch user changes
(0, vue_1.watch)(() => props.user, () => {
    initializeForm();
}, { deep: true });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    loading: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['department-select']} */ ;
/** @type {__VLS_StyleScopedClasses['department-select']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "profile-form" },
});
const __VLS_0 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.profileForm),
    rules: (__VLS_ctx.profileRules),
    layout: "vertical",
    size: "large",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onFinish': {} },
    ref: "formRef",
    model: (__VLS_ctx.profileForm),
    rules: (__VLS_ctx.profileRules),
    layout: "vertical",
    size: "large",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onFinish: (__VLS_ctx.handleSubmit)
};
/** @type {typeof __VLS_ctx.formRef} */ ;
var __VLS_8 = {};
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
/** @type {[typeof AvatarUpload, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(AvatarUpload_vue_1.default, new AvatarUpload_vue_1.default({
    ...{ 'onUploadSuccess': {} },
    ...{ 'onUploadError': {} },
    modelValue: (__VLS_ctx.profileForm.avatar),
    userName: (__VLS_ctx.profileForm.display_name),
}));
const __VLS_11 = __VLS_10({
    ...{ 'onUploadSuccess': {} },
    ...{ 'onUploadError': {} },
    modelValue: (__VLS_ctx.profileForm.avatar),
    userName: (__VLS_ctx.profileForm.display_name),
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
let __VLS_13;
let __VLS_14;
let __VLS_15;
const __VLS_16 = {
    onUploadSuccess: (__VLS_ctx.handleAvatarSuccess)
};
const __VLS_17 = {
    onUploadError: (__VLS_ctx.handleAvatarError)
};
var __VLS_12;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-6" },
});
const __VLS_18 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
    name: "display_name",
    ...{ class: "mb-4" },
}));
const __VLS_20 = __VLS_19({
    name: "display_name",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_19));
__VLS_21.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
const __VLS_22 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_23 = __VLS_asFunctionalComponent(__VLS_22, new __VLS_22({
    value: (__VLS_ctx.profileForm.display_name),
    placeholder: "请输入真实姓名",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}));
const __VLS_24 = __VLS_23({
    value: (__VLS_ctx.profileForm.display_name),
    placeholder: "请输入真实姓名",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_23));
var __VLS_21;
const __VLS_26 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
    name: "email",
    ...{ class: "mb-4" },
}));
const __VLS_28 = __VLS_27({
    name: "email",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_27));
__VLS_29.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
const __VLS_30 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
    value: (__VLS_ctx.profileForm.email),
    placeholder: "邮箱地址",
    disabled: true,
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500" },
}));
const __VLS_32 = __VLS_31({
    value: (__VLS_ctx.profileForm.email),
    placeholder: "邮箱地址",
    disabled: true,
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500" },
}, ...__VLS_functionalComponentArgsRest(__VLS_31));
var __VLS_29;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-2 gap-4 mb-6" },
});
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
    value: (__VLS_ctx.profileForm.department),
    placeholder: "选择所属科室",
    size: "large",
    ...{ class: "department-select" },
    showSearch: true,
    filterOption: (__VLS_ctx.filterDepartment),
}));
const __VLS_40 = __VLS_39({
    value: (__VLS_ctx.profileForm.department),
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
    name: "phone",
    ...{ class: "mb-4" },
}));
const __VLS_48 = __VLS_47({
    name: "phone",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
__VLS_49.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
const __VLS_50 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
    value: (__VLS_ctx.profileForm.phone),
    placeholder: "请输入手机号",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}));
const __VLS_52 = __VLS_51({
    value: (__VLS_ctx.profileForm.phone),
    placeholder: "请输入手机号",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_51));
var __VLS_49;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-wrap gap-2" },
});
for (const [role] of __VLS_getVForSourceType((__VLS_ctx.userRoles))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (role),
        ...{ class: "inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-gradient-to-r from-cyan-500/20 to-blue-500/20 border border-cyan-400/30" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-5 h-5 rounded bg-gradient-to-br flex items-center justify-center text-white text-xs font-bold" },
        ...{ class: (__VLS_ctx.getRoleColor(role)) },
    });
    (__VLS_ctx.getRoleInitial(role));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-cyan-200 text-sm font-medium" },
    });
    (__VLS_ctx.getRoleLabel(role));
}
const __VLS_54 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    name: "bio",
    ...{ class: "mb-6" },
}));
const __VLS_56 = __VLS_55({
    name: "bio",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
__VLS_57.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-2" },
});
const __VLS_58 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
    value: (__VLS_ctx.profileForm.bio),
    placeholder: "简单介绍一下自己...",
    rows: (4),
    maxLength: (200),
    showCount: true,
    ...{ class: "rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}));
const __VLS_60 = __VLS_59({
    value: (__VLS_ctx.profileForm.bio),
    placeholder: "简单介绍一下自己...",
    rows: (4),
    maxLength: (200),
    showCount: true,
    ...{ class: "rounded-xl bg-white/5 border border-white/10 text-slate-100 placeholder:text-slate-500 focus:border-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_59));
var __VLS_57;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
    ...{ class: "block text-xs font-medium text-slate-300 mb-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-slate-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
const __VLS_62 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    checked: (__VLS_ctx.profileForm.notifications.email),
    ...{ class: "bg-slate-600" },
}));
const __VLS_64 = __VLS_63({
    checked: (__VLS_ctx.profileForm.notifications.email),
    ...{ class: "bg-slate-600" },
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-slate-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
const __VLS_66 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
    checked: (__VLS_ctx.profileForm.notifications.sms),
    ...{ class: "bg-slate-600" },
}));
const __VLS_68 = __VLS_67({
    checked: (__VLS_ctx.profileForm.notifications.sms),
    ...{ class: "bg-slate-600" },
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-slate-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
const __VLS_70 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    checked: (__VLS_ctx.profileForm.notifications.push),
    ...{ class: "bg-slate-600" },
}));
const __VLS_72 = __VLS_71({
    checked: (__VLS_ctx.profileForm.notifications.push),
    ...{ class: "bg-slate-600" },
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex gap-3" },
});
const __VLS_74 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.loading),
    size: "large",
    ...{ class: "flex-1 h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none font-semibold shadow-lg hover:shadow-xl" },
}));
const __VLS_76 = __VLS_75({
    type: "primary",
    htmlType: "submit",
    loading: (__VLS_ctx.loading),
    size: "large",
    ...{ class: "flex-1 h-12 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 border-none font-semibold shadow-lg hover:shadow-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
__VLS_77.slots.default;
if (!__VLS_ctx.loading) {
    const __VLS_78 = {}.SaveOutlined;
    /** @type {[typeof __VLS_components.SaveOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
        ...{ class: "mr-2" },
    }));
    const __VLS_80 = __VLS_79({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_79));
}
var __VLS_77;
const __VLS_82 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20" },
}));
const __VLS_84 = __VLS_83({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "h-12 rounded-xl bg-white/5 border border-white/10 text-slate-300 hover:bg-white/10 hover:border-white/20" },
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
let __VLS_86;
let __VLS_87;
let __VLS_88;
const __VLS_89 = {
    onClick: (__VLS_ctx.handleReset)
};
__VLS_85.slots.default;
const __VLS_90 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
    ...{ class: "mr-2" },
}));
const __VLS_92 = __VLS_91({
    ...{ class: "mr-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
var __VLS_85;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-8 p-4 rounded-xl bg-amber-500/10 border border-amber-500/20" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-sm font-medium text-amber-200 mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-xs text-amber-200/80" },
});
const __VLS_94 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300 hover:bg-amber-500/30" },
}));
const __VLS_96 = __VLS_95({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300 hover:bg-amber-500/30" },
}, ...__VLS_functionalComponentArgsRest(__VLS_95));
let __VLS_98;
let __VLS_99;
let __VLS_100;
const __VLS_101 = {
    onClick: (...[$event]) => {
        __VLS_ctx.$emit('change-password');
    }
};
__VLS_97.slots.default;
const __VLS_102 = {}.LockOutlined;
/** @type {[typeof __VLS_components.LockOutlined, ]} */ ;
// @ts-ignore
const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
    ...{ class: "mr-1" },
}));
const __VLS_104 = __VLS_103({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_103));
var __VLS_97;
/** @type {__VLS_StyleScopedClasses['profile-form']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
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
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['inline-flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-r']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-cyan-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['w-5']} */ ;
/** @type {__VLS_StyleScopedClasses['h-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-200']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['placeholder:text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['focus:border-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-r']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-500']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:to-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-none']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/5']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-white/10']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-white/20']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-8']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-amber-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-amber-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-200/80']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-amber-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-amber-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-amber-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
// @ts-ignore
var __VLS_9 = __VLS_8;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            SaveOutlined: icons_vue_1.SaveOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            LockOutlined: icons_vue_1.LockOutlined,
            AvatarUpload: AvatarUpload_vue_1.default,
            formRef: formRef,
            profileForm: profileForm,
            departments: departments,
            userRoles: userRoles,
            profileRules: profileRules,
            handleSubmit: handleSubmit,
            handleReset: handleReset,
            handleAvatarSuccess: handleAvatarSuccess,
            handleAvatarError: handleAvatarError,
            filterDepartment: filterDepartment,
            getRoleColor: getRoleColor,
            getRoleInitial: getRoleInitial,
            getRoleLabel: getRoleLabel,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
