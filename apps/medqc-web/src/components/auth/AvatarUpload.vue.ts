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
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const props = withDefaults(defineProps(), {
    showPresets: true,
    maxSize: 2
});
const emit = defineEmits();
// 状态
const uploading = (0, vue_1.ref)(false);
const uploadStatus = (0, vue_1.ref)(null);
// 当前头像
const currentAvatar = (0, vue_1.computed)({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value)
});
// 是否为默认头像
const isDefaultAvatar = (0, vue_1.computed)(() => {
    return !currentAvatar.value || presetAvatars.some(preset => preset.url === currentAvatar.value);
});
// 头像首字母
const avatarInitial = (0, vue_1.computed)(() => {
    if (props.userName) {
        return props.userName.charAt(0).toUpperCase();
    }
    return 'U';
});
// 预设头像列表
const presetAvatars = [
    { name: '医生1', url: '/avatars/doctor-1.png' },
    { name: '医生2', url: '/avatars/doctor-2.png' },
    { name: '护士1', url: '/avatars/nurse-1.png' },
    { name: '护士2', url: '/avatars/nurse-2.png' },
    { name: '管理员1', url: '/avatars/admin-1.png' },
    { name: '管理员2', url: '/avatars/admin-2.png' },
    { name: '质控员1', url: '/avatars/qc-1.png' },
    { name: '质控员2', url: '/avatars/qc-2.png' },
    { name: '通用1', url: '/avatars/generic-1.png' },
    { name: '通用2', url: '/avatars/generic-2.png' },
    { name: '通用3', url: '/avatars/generic-3.png' },
    { name: '通用4', url: '/avatars/generic-4.png' }
];
// 上传前验证
const beforeUpload = (file) => {
    // 检查文件类型
    const isValidType = ['image/jpeg', 'image/jpg', 'image/png'].includes(file.type);
    if (!isValidType) {
        ant_design_vue_1.message.error('只支持 JPG、PNG 格式的图片');
        return false;
    }
    // 检查文件大小
    const isValidSize = file.size / 1024 / 1024 < props.maxSize;
    if (!isValidSize) {
        ant_design_vue_1.message.error(`图片大小不能超过 ${props.maxSize}MB`);
        return false;
    }
    return true;
};
// 处理上传
const handleUpload = async (options) => {
    const { file } = options;
    try {
        uploading.value = true;
        uploadStatus.value = { type: 'info', message: '正在上传头像...' };
        // 模拟上传过程
        await new Promise(resolve => setTimeout(resolve, 2000));
        // 创建本地预览URL
        const reader = new FileReader();
        reader.onload = (e) => {
            const url = e.target?.result;
            currentAvatar.value = url;
            uploadStatus.value = { type: 'success', message: '头像上传成功' };
            emit('upload-success', url);
            // 3秒后清除状态提示
            setTimeout(() => {
                uploadStatus.value = null;
            }, 3000);
        };
        reader.readAsDataURL(file);
    }
    catch (error) {
        console.error('头像上传失败:', error);
        uploadStatus.value = { type: 'error', message: '头像上传失败，请重试' };
        emit('upload-error', error instanceof Error ? error.message : '上传失败');
        // 5秒后清除错误提示
        setTimeout(() => {
            uploadStatus.value = null;
        }, 5000);
    }
    finally {
        uploading.value = false;
    }
};
// 删除头像
const handleRemove = () => {
    currentAvatar.value = '';
    uploadStatus.value = { type: 'info', message: '头像已删除' };
    setTimeout(() => {
        uploadStatus.value = null;
    }, 2000);
};
// 重置为默认头像
const handleReset = () => {
    currentAvatar.value = '';
    uploadStatus.value = { type: 'info', message: '已重置为默认头像' };
    setTimeout(() => {
        uploadStatus.value = null;
    }, 2000);
};
// 选择预设头像
const selectPreset = (preset) => {
    currentAvatar.value = preset.url;
    uploadStatus.value = { type: 'success', message: `已选择 ${preset.name}` };
    setTimeout(() => {
        uploadStatus.value = null;
    }, 2000);
};
// 监听上传状态变化
(0, vue_1.watch)(uploadStatus: any,  (newStatus: any) => {
    if (newStatus?.type === 'error') {
        ant_design_vue_1.message.error(newStatus.message);
    }
    else if (newStatus?.type === 'success') {
        ant_design_vue_1.message.success(newStatus.message);
    }
}, { deep: true });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    showPresets: true,
    maxSize: 2
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['w-20']} */ ;
/** @type {__VLS_StyleScopedClasses['h-20']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "avatar-upload" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-20 h-20 rounded-full overflow-hidden bg-gradient-to-br from-cyan-400 via-blue-500 to-purple-600 flex items-center justify-center shadow-lg" },
    ...{ class: ({ 'ring-4 ring-cyan-400/30': __VLS_ctx.uploading }) },
});
if (__VLS_ctx.currentAvatar) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
        src: (__VLS_ctx.currentAvatar),
        alt: (__VLS_ctx.userName || '用户头像'),
        ...{ class: "w-full h-full object-cover" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-white text-2xl font-bold" },
    });
    (__VLS_ctx.avatarInitial);
}
if (__VLS_ctx.uploading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "absolute inset-0 flex items-center justify-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-24 h-24 rounded-full border-4 border-transparent border-t-cyan-400 animate-spin" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-sm font-medium text-slate-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex gap-2" },
});
const __VLS_0 = {}.AUpload;
/** @type {[typeof __VLS_components.AUpload, typeof __VLS_components.aUpload, typeof __VLS_components.AUpload, typeof __VLS_components.aUpload, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    customRequest: (__VLS_ctx.handleUpload),
    showUploadList: (false),
    beforeUpload: (__VLS_ctx.beforeUpload),
    accept: "image/jpeg,image/jpg,image/png",
}));
const __VLS_2 = __VLS_1({
    customRequest: (__VLS_ctx.handleUpload),
    showUploadList: (false),
    beforeUpload: (__VLS_ctx.beforeUpload),
    accept: "image/jpeg,image/jpg,image/png",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    size: "small",
    loading: (__VLS_ctx.uploading),
    ...{ class: "bg-cyan-500/20 border-cyan-400/30 text-cyan-300 hover:bg-cyan-500/30" },
}));
const __VLS_6 = __VLS_5({
    size: "small",
    loading: (__VLS_ctx.uploading),
    ...{ class: "bg-cyan-500/20 border-cyan-400/30 text-cyan-300 hover:bg-cyan-500/30" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.UploadOutlined;
/** @type {[typeof __VLS_components.UploadOutlined, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
(__VLS_ctx.uploading ? '上传中...' : '选择图片');
var __VLS_7;
var __VLS_3;
if (__VLS_ctx.currentAvatar && !__VLS_ctx.isDefaultAvatar) {
    const __VLS_12 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        ...{ 'onClick': {} },
        size: "small",
        danger: true,
        ...{ class: "bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30" },
    }));
    const __VLS_14 = __VLS_13({
        ...{ 'onClick': {} },
        size: "small",
        danger: true,
        ...{ class: "bg-red-500/20 border-red-400/30 text-red-300 hover:bg-red-500/30" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    let __VLS_16;
    let __VLS_17;
    let __VLS_18;
    const __VLS_19 = {
        onClick: (__VLS_ctx.handleRemove)
    };
    __VLS_15.slots.default;
    const __VLS_20 = {}.DeleteOutlined;
    /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
    const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
    var __VLS_15;
}
if (__VLS_ctx.currentAvatar && !__VLS_ctx.isDefaultAvatar) {
    const __VLS_24 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "bg-slate-500/20 border-slate-400/30 text-slate-300 hover:bg-slate-500/30" },
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onClick': {} },
        size: "small",
        ...{ class: "bg-slate-500/20 border-slate-400/30 text-slate-300 hover:bg-slate-500/30" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_28;
    let __VLS_29;
    let __VLS_30;
    const __VLS_31 = {
        onClick: (__VLS_ctx.handleReset)
    };
    __VLS_27.slots.default;
    const __VLS_32 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
    const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
    var __VLS_27;
}
if (__VLS_ctx.uploadStatus) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-2" },
    });
    if (__VLS_ctx.uploadStatus.type === 'success') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center gap-1 text-xs text-emerald-400" },
        });
        const __VLS_36 = {}.CheckCircleOutlined;
        /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({}));
        const __VLS_38 = __VLS_37({}, ...__VLS_functionalComponentArgsRest(__VLS_37));
        (__VLS_ctx.uploadStatus.message);
    }
    else if (__VLS_ctx.uploadStatus.type === 'error') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center gap-1 text-xs text-red-400" },
        });
        const __VLS_40 = {}.ExclamationCircleOutlined;
        /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
        const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
        (__VLS_ctx.uploadStatus.message);
    }
    else if (__VLS_ctx.uploadStatus.type === 'info') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center gap-1 text-xs text-blue-400" },
        });
        const __VLS_44 = {}.InfoCircleOutlined;
        /** @type {[typeof __VLS_components.InfoCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
        const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
        (__VLS_ctx.uploadStatus.message);
    }
}
if (__VLS_ctx.showPresets) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
        ...{ class: "text-sm font-medium text-slate-200 mb-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-xs text-slate-400" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid grid-cols-6 gap-3" },
    });
    for (const [preset, index] of __VLS_getVForSourceType((__VLS_ctx.presetAvatars))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showPresets))
                        return;
                    __VLS_ctx.selectPreset(preset);
                } },
            key: (index),
            ...{ class: "w-12 h-12 rounded-full overflow-hidden cursor-pointer transition-all duration-200 hover:scale-110 hover:ring-2 hover:ring-cyan-400/50" },
            ...{ class: ({ 'ring-2 ring-cyan-400': __VLS_ctx.currentAvatar === preset.url }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
            src: (preset.url),
            alt: (preset.name),
            ...{ class: "w-full h-full object-cover" },
        });
    }
}
/** @type {__VLS_StyleScopedClasses['avatar-upload']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['w-20']} */ ;
/** @type {__VLS_StyleScopedClasses['h-20']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['to-purple-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-4']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-cyan-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['object-cover']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-24']} */ ;
/** @type {__VLS_StyleScopedClasses['h-24']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['border-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-transparent']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['animate-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-cyan-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-cyan-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-cyan-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-red-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-red-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-slate-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-6']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-200']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:scale-110']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:ring-cyan-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['object-cover']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            UploadOutlined: icons_vue_1.UploadOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            InfoCircleOutlined: icons_vue_1.InfoCircleOutlined,
            uploading: uploading,
            uploadStatus: uploadStatus,
            currentAvatar: currentAvatar,
            isDefaultAvatar: isDefaultAvatar,
            avatarInitial: avatarInitial,
            presetAvatars: presetAvatars,
            beforeUpload: beforeUpload,
            handleUpload: handleUpload,
            handleRemove: handleRemove,
            handleReset: handleReset,
            selectPreset: selectPreset,
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
