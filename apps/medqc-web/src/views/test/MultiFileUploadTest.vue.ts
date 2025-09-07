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
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
// 响应式数据
const uploadedFiles = (0, vue_1.ref)(: any[]);
const debugLog = (0, vue_1.ref)(: any[]);
// 添加调试日志
const addDebugLog = (message) => {
    const timestamp = new Date().toLocaleTimeString();
    debugLog.value.unshift(`[${timestamp}] ${message}`);
    // 限制日志数量
    if (debugLog.value.length > 20) {
        debugLog.value = debugLog.value.slice(0, 20);
    }
};
// 文件验证
const beforeUpload = (file) => {
    addDebugLog(`beforeUpload 被调用: ${file.name}`);
    // 检查文件数量限制
    if (uploadedFiles.value.length >= 10) {
        ant_design_vue_1.message.error('最多只能上传10个文件');
        addDebugLog('文件数量超过限制');
        return false;
    }
    // 检查文件类型
    const validTypes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
    ];
    const fileName = file.name.toLowerCase();
    const validExtensions = ['.pdf', '.doc', '.docx', '.txt'];
    const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext));
    const isValidType = validTypes.includes(file.type) || hasValidExtension;
    if (!isValidType) {
        ant_design_vue_1.message.error(`文件 ${file.name} 格式不支持`);
        addDebugLog(`文件格式不支持: ${file.name}`);
        return false;
    }
    // 检查文件大小
    const isLt50M = file.size / 1024 / 1024 < 50;
    if (!isLt50M) {
        ant_design_vue_1.message.error(`文件 ${file.name} 大小超过限制`);
        addDebugLog(`文件大小超过限制: ${file.name}`);
        return false;
    }
    addDebugLog(`文件验证通过: ${file.name}`);
    return false; // 返回false，阻止默认上传
};
// 处理文件上传变化
const handleUploadChange = (info) => {
    addDebugLog(`handleUploadChange 被调用，文件数量: ${info.fileList?.length || 0}`);
    const { fileList } = info;
    if (!fileList || fileList.length === 0) {
        addDebugLog('没有文件列表');
        return;
    }
    // 处理新添加的文件
    fileList.forEach((fileItem, index) => {
        const file = fileItem.originFileObj || fileItem;
        if (!file) {
            addDebugLog(`文件项 ${index} 没有文件对象`);
            return;
        }
        // 检查是否已经添加过这个文件
        const exists = uploadedFiles.value.some(existingFile => existingFile.name === file.name && existingFile.size === file.size);
        if (!exists) {
            addDebugLog(`添加新文件: ${file.name}`);
            addFileToList(file);
        }
        else {
            addDebugLog(`文件已存在，跳过: ${file.name}`);
        }
    });
};
// 添加文件到列表
const addFileToList = (file) => {
    try {
        const fileObj = {
            name: file.name,
            size: file.size,
            type: file.type,
            file: file,
            uploadTime: new Date().toLocaleString()
        };
        uploadedFiles.value.push(fileObj);
        addDebugLog(`文件已添加到列表: ${file.name}，当前总数: ${uploadedFiles.value.length}`);
        ant_design_vue_1.message.success(`文件 ${file.name} 上传成功`);
    }
    catch (error) {
        addDebugLog(`文件处理失败: ${file.name} - ${error.message}`);
        ant_design_vue_1.message.error(`文件处理失败: ${file.name}`);
    }
};
// 删除文件
const removeFile = (index) => {
    const file = uploadedFiles.value[index];
    uploadedFiles.value.splice(index, 1);
    addDebugLog(`删除文件: ${file.name}`);
    ant_design_vue_1.message.info(`已删除文件: ${file.name}`);
};
// 清空所有文件
const clearAllFiles = () => {
    const count = uploadedFiles.value.length;
    uploadedFiles.value = [];
    addDebugLog(`清空所有文件，共 ${count} 个`);
    ant_design_vue_1.message.info(`已清空 ${count} 个文件`);
};
// 处理文件
const processFiles = () => {
    addDebugLog(`开始处理 ${uploadedFiles.value.length} 个文件`);
    ant_design_vue_1.message.info(`开始处理 ${uploadedFiles.value.length} 个文件`);
};
// 格式化文件大小
const formatFileSize = (bytes) => {
    if (bytes === 0)
        return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};
// 初始化
addDebugLog('多文件上传测试页面已加载');
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-area']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "multi-file-upload-test" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "upload-section" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "文件上传测试",
}));
const __VLS_2 = __VLS_1({
    title: "文件上传测试",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AUploadDragger;
/** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onChange': {} }, fileList: (: any[]),
    beforeUpload: (__VLS_ctx.beforeUpload),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
    showUploadList: (false),
    ...{ class: "upload-area" },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onChange': {} }, fileList: (: any[]),
    beforeUpload: (__VLS_ctx.beforeUpload),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
    showUploadList: (false),
    ...{ class: "upload-area" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onChange: (__VLS_ctx.handleUploadChange)
};
__VLS_7.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-drag-icon" },
});
const __VLS_12 = {}.InboxOutlined;
/** @type {[typeof __VLS_components.InboxOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-hint" },
});
var __VLS_7;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "debug-info mt-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
(__VLS_ctx.uploadedFiles.length);
if (__VLS_ctx.debugLog.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "debug-log" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    for (const [log, index] of __VLS_getVForSourceType((__VLS_ctx.debugLog))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (index),
            ...{ class: "log-item" },
        });
        (log);
    }
}
if (__VLS_ctx.uploadedFiles.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-list mt-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (__VLS_ctx.uploadedFiles.length);
    const __VLS_16 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        dataSource: (__VLS_ctx.uploadedFiles),
        size: "small",
    }));
    const __VLS_18 = __VLS_17({
        dataSource: (__VLS_ctx.uploadedFiles),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_19.slots;
        const [{ item, index }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_20 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
        const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
        __VLS_23.slots.default;
        {
            const { actions: __VLS_thisSlot } = __VLS_23.slots;
            const __VLS_24 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
                ...{ 'onClick': {} },
                size: "small",
                danger: true,
            }));
            const __VLS_26 = __VLS_25({
                ...{ 'onClick': {} },
                size: "small",
                danger: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_25));
            let __VLS_28;
            let __VLS_29;
            let __VLS_30;
            const __VLS_31 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.uploadedFiles.length > 0))
                        return;
                    __VLS_ctx.removeFile(index);
                }
            };
            __VLS_27.slots.default;
            var __VLS_27;
        }
        const __VLS_32 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
        const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
        __VLS_35.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_35.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-title" },
            });
            const __VLS_36 = {}.FileOutlined;
            /** @type {[typeof __VLS_components.FileOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
                ...{ class: "file-icon" },
            }));
            const __VLS_38 = __VLS_37({
                ...{ class: "file-icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_37));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.name);
        }
        {
            const { description: __VLS_thisSlot } = __VLS_35.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-details" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.formatFileSize(item.size));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.type);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.uploadTime);
        }
        var __VLS_35;
        var __VLS_23;
    }
    var __VLS_19;
}
if (__VLS_ctx.uploadedFiles.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "actions mt-4" },
    });
    const __VLS_40 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
    const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    const __VLS_44 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_46 = __VLS_45({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    let __VLS_48;
    let __VLS_49;
    let __VLS_50;
    const __VLS_51 = {
        onClick: (__VLS_ctx.processFiles)
    };
    __VLS_47.slots.default;
    var __VLS_47;
    const __VLS_52 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        ...{ 'onClick': {} },
        danger: true,
    }));
    const __VLS_54 = __VLS_53({
        ...{ 'onClick': {} },
        danger: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    let __VLS_56;
    let __VLS_57;
    let __VLS_58;
    const __VLS_59 = {
        onClick: (__VLS_ctx.clearAllFiles)
    };
    __VLS_55.slots.default;
    var __VLS_55;
    var __VLS_43;
}
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['multi-file-upload-test']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-section']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-area']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['debug-info']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['debug-log']} */ ;
/** @type {__VLS_StyleScopedClasses['log-item']} */ ;
/** @type {__VLS_StyleScopedClasses['file-list']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['file-title']} */ ;
/** @type {__VLS_StyleScopedClasses['file-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['file-details']} */ ;
/** @type {__VLS_StyleScopedClasses['actions']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            InboxOutlined: icons_vue_1.InboxOutlined,
            FileOutlined: icons_vue_1.FileOutlined,
            uploadedFiles: uploadedFiles,
            debugLog: debugLog,
            beforeUpload: beforeUpload,
            handleUploadChange: handleUploadChange,
            removeFile: removeFile,
            clearAllFiles: clearAllFiles,
            processFiles: processFiles,
            formatFileSize: formatFileSize,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
