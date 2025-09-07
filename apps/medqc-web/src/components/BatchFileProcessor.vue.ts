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
const LLMResultModal_vue_1 = __importDefault(require("./LLMResultModal.vue"));
// 文件状态枚举
var FileStatus;
(function (FileStatus) {
    FileStatus["PENDING"] = "pending";
    FileStatus["PROCESSING"] = "processing";
    FileStatus["COMPLETED"] = "completed";
    FileStatus["FAILED"] = "failed";
})(FileStatus || (FileStatus = {}));
const props = withDefaults(defineProps(), {
    maxFileSize: 50,
    maxFileCount: 20,
    allowedTypes: () => ['.pdf', '.doc', '.docx', '.txt']
});
const emit = defineEmits();
// 响应式数据
const fileList = (0, vue_1.ref)(: any[]);
const uploadedFiles = (0, vue_1.ref)(: any[]);
const selectedFileIndex = (0, vue_1.ref)(-1);
const batchProcessing = (0, vue_1.ref)(false);
const isPaused = (0, vue_1.ref)(false);
const canPause = (0, vue_1.ref)(true);
const completedFiles = (0, vue_1.ref)(0);
const currentProcessingFile = (0, vue_1.ref)('');
const batchResults = (0, vue_1.ref)(: any[]);
const batchResultsModalVisible = (0, vue_1.ref)(false);
const activeResultTab = (0, vue_1.ref)(0);
const saving = (0, vue_1.ref)(false);
// 计算属性
const totalSize = (0, vue_1.computed)(() => {
    return uploadedFiles.value.reduce((total, file) => total + file.size, 0) / (1024 * 1024);
});
const parsedCount = (0, vue_1.computed)(() => {
    return uploadedFiles.value.filter(file => file.parsed).length;
});
const successRate = (0, vue_1.computed)(() => {
    if (uploadedFiles.value.length === 0)
        return 0;
    const successCount = uploadedFiles.value.filter(file => file.status === FileStatus.COMPLETED).length;
    return (successCount / uploadedFiles.value.length) * 100;
});
const overallProgress = (0, vue_1.computed)(() => {
    if (uploadedFiles.value.length === 0)
        return 0;
    return (completedFiles.value / uploadedFiles.value.length) * 100;
});
const hasErrors = (0, vue_1.computed)(() => {
    return uploadedFiles.value.some(file => file.status === FileStatus.FAILED);
});
// 方法
const beforeUpload = (file) => {
    // 检查文件大小
    if (file.size > props.maxFileSize * 1024 * 1024) {
        ant_design_vue_1.message.error(`文件 ${file.name} 超过 ${props.maxFileSize}MB 限制`);
        return false;
    }
    // 检查文件数量
    if (uploadedFiles.value.length >= props.maxFileCount) {
        ant_design_vue_1.message.error(`最多只能上传 ${props.maxFileCount} 个文件`);
        return false;
    }
    // 检查文件类型
    const fileExt = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!props.allowedTypes.includes(fileExt)) {
        ant_design_vue_1.message.error(`不支持的文件类型: ${fileExt}`);
        return false;
    }
    return false; // 阻止自动上传
};
const handleFileUpload = (options) => {
    const { file } = options;
    const processingFile = {
        id: Date.now() + Math.random().toString(),
        name: file.name,
        size: file.size,
        type: file.type,
        file: file,
        status: FileStatus.PENDING,
        processing: false,
        parsed: false,
        progress: 0
    };
    uploadedFiles.value.push(processingFile);
    ant_design_vue_1.message.success(`文件 ${file.name} 添加成功`);
};
const getFileIcon = (type) => {
    if (type.includes('pdf'))
        return icons_vue_1.FilePdfOutlined;
    if (type.includes('word') || type.includes('document'))
        return icons_vue_1.FileWordOutlined;
    if (type.includes('text'))
        return icons_vue_1.FileTextOutlined;
    return icons_vue_1.FileOutlined;
};
const getStatusColor = (status) => {
    const colorMap = {
        [FileStatus.PENDING]: 'default',
        [FileStatus.PROCESSING]: 'processing',
        [FileStatus.COMPLETED]: 'success',
        [FileStatus.FAILED]: 'error'
    };
    return colorMap[status];
};
const getStatusText = (status) => {
    const textMap = {
        [FileStatus.PENDING]: '等待中',
        [FileStatus.PROCESSING]: '解析中',
        [FileStatus.COMPLETED]: '已完成',
        [FileStatus.FAILED]: '失败'
    };
    return textMap[status];
};
const formatFileSize = (bytes) => {
    if (bytes === 0)
        return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};
const selectFile = (index) => {
    selectedFileIndex.value = index;
};
const removeFile = (index) => {
    uploadedFiles.value.splice(index, 1);
    if (selectedFileIndex.value === index) {
        selectedFileIndex.value = -1;
    }
    else if (selectedFileIndex.value > index) {
        selectedFileIndex.value--;
    }
};
const clearAllFiles = () => {
    uploadedFiles.value = [];
    selectedFileIndex.value = -1;
    batchResults.value = [];
    completedFiles.value = 0;
};
// 单个文件处理
const processSingleFile = async (index) => {
    const file = uploadedFiles.value[index];
    if (!file || file.processing)
        return;
    try {
        file.processing = true;
        file.status = FileStatus.PROCESSING;
        file.progress = 0;
        // 模拟处理进度
        const progressInterval = setInterval(() => {
            if (file.progress < 90) {
                file.progress += Math.random() * 20;
            }
        }, 500);
        // 这里调用实际的LLM解析API
        const result = await callLLMParseAPI(file.file);
        clearInterval(progressInterval);
        file.progress = 100;
        file.processing = false;
        file.parsed = true;
        file.status = FileStatus.COMPLETED;
        file.result = result;
        file.confidence = result.data?.confidence || 0;
        emit('single-file-processed', result);
        ant_design_vue_1.message.success(`文件 ${file.name} 解析完成`);
    }
    catch (error) {
        file.processing = false;
        file.status = FileStatus.FAILED;
        file.error = error.message;
        ant_design_vue_1.message.error(`文件 ${file.name} 解析失败: ${error.message}`);
    }
};
// 批量处理
const startBatchProcessing = async () => {
    if (uploadedFiles.value.length === 0)
        return;
    batchProcessing.value = true;
    isPaused.value = false;
    completedFiles.value = 0;
    batchResults.value = [];
    try {
        for (let i = 0; i < uploadedFiles.value.length; i++) {
            if (!batchProcessing.value)
                break; // 用户取消
            while (isPaused.value) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            const file = uploadedFiles.value[i];
            if (file.parsed) {
                completedFiles.value++;
                continue;
            }
            currentProcessingFile.value = file.name;
            await processSingleFile(i);
            if (file.result) {
                batchResults.value.push({
                    fileName: file.name,
                    ...file.result,
                    originalText: file.result.data?.content
                });
            }
            completedFiles.value++;
        }
        ant_design_vue_1.message.success('批量解析完成!');
        emit('batch-completed', batchResults.value);
    }
    catch (error) {
        ant_design_vue_1.message.error(`批量处理失败: ${error.message}`);
    }
    finally {
        batchProcessing.value = false;
        currentProcessingFile.value = '';
    }
};
const pauseProcessing = () => {
    isPaused.value = !isPaused.value;
};
const cancelProcessing = () => {
    batchProcessing.value = false;
    isPaused.value = false;
    currentProcessingFile.value = '';
};
// 结果处理
const showBatchResultsModal = () => {
    batchResultsModalVisible.value = true;
};
const exportBatchResults = () => {
    if (batchResults.value.length === 0)
        return;
    const dataStr = JSON.stringify(batchResults.value, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `batch_results_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
};
const saveBatchToDatabase = async () => {
    saving.value = true;
    try {
        // 这里实现批量保存逻辑
        await new Promise(resolve => setTimeout(resolve, 2000)); // 模拟保存
        ant_design_vue_1.message.success('批量保存成功!');
    }
    catch (error) {
        ant_design_vue_1.message.error(`批量保存失败: ${error.message}`);
    }
    finally {
        saving.value = false;
    }
};
const handleSingleSave = (result) => {
    ant_design_vue_1.message.success(`保存文件 ${result.fileName} 成功`);
};
const handleSingleExport = (result) => {
    const dataStr = JSON.stringify(result, null, 2);
    const blob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${result.fileName}_result.json`;
    a.click();
    URL.revokeObjectURL(url);
};
const handleSingleExportPDF = (result) => {
    ant_design_vue_1.message.info('PDF导出功能开发中...');
};
// 模拟LLM解析API调用
const callLLMParseAPI = async (file) => {
    // 这里应该调用实际的LLM解析API
    return new Promise((resolve: any,  reject: any) => {
        setTimeout(() => {
            if (Math.random() > 0.1) { // 90%成功率
                resolve({
                    success: true,
                    data: {
                        patientName: '测试患者',
                        content: '模拟解析内容...',
                        confidence: Math.random() * 40 + 60, // 60-100%
                        documents: []
                    }
                });
            }
            else {
                reject(new Error('模拟解析失败'));
            }
        }, 2000 + Math.random() * 3000); // 2-5秒
    });
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    maxFileSize: 50,
    maxFileCount: 20,
    allowedTypes: () => ['.pdf', '.doc', '.docx', '.txt']
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['enhanced-upload-dragger']} */ ;
/** @type {__VLS_StyleScopedClasses['file-item']} */ ;
/** @type {__VLS_StyleScopedClasses['file-item']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-file-processor']} */ ;
/** @type {__VLS_StyleScopedClasses['file-management-section']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['file-details']} */ ;
/** @type {__VLS_StyleScopedClasses['file-item']} */ ;
/** @type {__VLS_StyleScopedClasses['overall-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['file-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-progress-bg']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-file-processor" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "upload-section" },
});
const __VLS_0 = {}.AUploadDragger;
/** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    fileList: (__VLS_ctx.fileList),
    beforeUpload: (__VLS_ctx.beforeUpload),
    customRequest: (__VLS_ctx.handleFileUpload),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
    showUploadList: (false),
    ...{ class: "enhanced-upload-dragger" },
}));
const __VLS_2 = __VLS_1({
    fileList: (__VLS_ctx.fileList),
    beforeUpload: (__VLS_ctx.beforeUpload),
    customRequest: (__VLS_ctx.handleFileUpload),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
    showUploadList: (false),
    ...{ class: "enhanced-upload-dragger" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-drag-icon" },
});
const __VLS_4 = {}.InboxOutlined;
/** @type {[typeof __VLS_components.InboxOutlined, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-hint" },
});
var __VLS_3;
if (__VLS_ctx.uploadedFiles.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-management-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-stats" },
    });
    const __VLS_8 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        gutter: (16),
    }));
    const __VLS_10 = __VLS_9({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    const __VLS_12 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        span: (6),
    }));
    const __VLS_14 = __VLS_13({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    const __VLS_16 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        title: "总文件数",
        value: (__VLS_ctx.uploadedFiles.length),
    }));
    const __VLS_18 = __VLS_17({
        title: "总文件数",
        value: (__VLS_ctx.uploadedFiles.length),
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    var __VLS_15;
    const __VLS_20 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        span: (6),
    }));
    const __VLS_22 = __VLS_21({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    const __VLS_24 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        title: "总大小",
        value: (__VLS_ctx.totalSize),
        suffix: "MB",
        precision: (2),
    }));
    const __VLS_26 = __VLS_25({
        title: "总大小",
        value: (__VLS_ctx.totalSize),
        suffix: "MB",
        precision: (2),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    var __VLS_23;
    const __VLS_28 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        span: (6),
    }));
    const __VLS_30 = __VLS_29({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_31.slots.default;
    const __VLS_32 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        title: "已解析",
        value: (__VLS_ctx.parsedCount),
        suffix: (`/ ${__VLS_ctx.uploadedFiles.length}`),
    }));
    const __VLS_34 = __VLS_33({
        title: "已解析",
        value: (__VLS_ctx.parsedCount),
        suffix: (`/ ${__VLS_ctx.uploadedFiles.length}`),
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    var __VLS_31;
    const __VLS_36 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        span: (6),
    }));
    const __VLS_38 = __VLS_37({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    const __VLS_40 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        title: "成功率",
        value: (__VLS_ctx.successRate),
        suffix: "%",
        precision: (1),
    }));
    const __VLS_42 = __VLS_41({
        title: "成功率",
        value: (__VLS_ctx.successRate),
        suffix: "%",
        precision: (1),
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    var __VLS_39;
    var __VLS_11;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-actions" },
    });
    const __VLS_44 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        size: "large",
    }));
    const __VLS_46 = __VLS_45({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    const __VLS_48 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ 'onClick': {} },
        type: "primary",
        size: "large",
        loading: (__VLS_ctx.batchProcessing),
        disabled: (__VLS_ctx.uploadedFiles.length === 0),
    }));
    const __VLS_50 = __VLS_49({
        ...{ 'onClick': {} },
        type: "primary",
        size: "large",
        loading: (__VLS_ctx.batchProcessing),
        disabled: (__VLS_ctx.uploadedFiles.length === 0),
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    let __VLS_52;
    let __VLS_53;
    let __VLS_54;
    const __VLS_55 = {
        onClick: (__VLS_ctx.startBatchProcessing)
    };
    __VLS_51.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_51.slots;
        const __VLS_56 = {}.ThunderboltOutlined;
        /** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
        const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
    }
    (__VLS_ctx.batchProcessing ? '解析中...' : '一键解析所有文件');
    var __VLS_51;
    if (__VLS_ctx.batchProcessing) {
        const __VLS_60 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
            ...{ 'onClick': {} },
            disabled: (!__VLS_ctx.canPause),
        }));
        const __VLS_62 = __VLS_61({
            ...{ 'onClick': {} },
            disabled: (!__VLS_ctx.canPause),
        }, ...__VLS_functionalComponentArgsRest(__VLS_61));
        let __VLS_64;
        let __VLS_65;
        let __VLS_66;
        const __VLS_67 = {
            onClick: (__VLS_ctx.pauseProcessing)
        };
        __VLS_63.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_63.slots;
            const __VLS_68 = {}.PauseCircleOutlined;
            /** @type {[typeof __VLS_components.PauseCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({}));
            const __VLS_70 = __VLS_69({}, ...__VLS_functionalComponentArgsRest(__VLS_69));
        }
        (__VLS_ctx.isPaused ? '继续' : '暂停');
        var __VLS_63;
    }
    if (__VLS_ctx.batchProcessing) {
        const __VLS_72 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            ...{ 'onClick': {} },
            danger: true,
        }));
        const __VLS_74 = __VLS_73({
            ...{ 'onClick': {} },
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        let __VLS_76;
        let __VLS_77;
        let __VLS_78;
        const __VLS_79 = {
            onClick: (__VLS_ctx.cancelProcessing)
        };
        __VLS_75.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_75.slots;
            const __VLS_80 = {}.StopOutlined;
            /** @type {[typeof __VLS_components.StopOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
            const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
        }
        var __VLS_75;
    }
    const __VLS_84 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        ...{ 'onClick': {} },
        danger: true,
    }));
    const __VLS_86 = __VLS_85({
        ...{ 'onClick': {} },
        danger: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    let __VLS_88;
    let __VLS_89;
    let __VLS_90;
    const __VLS_91 = {
        onClick: (__VLS_ctx.clearAllFiles)
    };
    __VLS_87.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_87.slots;
        const __VLS_92 = {}.DeleteOutlined;
        /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({}));
        const __VLS_94 = __VLS_93({}, ...__VLS_functionalComponentArgsRest(__VLS_93));
    }
    var __VLS_87;
    var __VLS_47;
    if (__VLS_ctx.batchProcessing || __VLS_ctx.completedFiles > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "overall-progress" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "progress-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "progress-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "progress-info" },
        });
        (__VLS_ctx.completedFiles);
        (__VLS_ctx.uploadedFiles.length);
        (__VLS_ctx.currentProcessingFile ? `正在处理: ${__VLS_ctx.currentProcessingFile}` : '等待中');
        const __VLS_96 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
            percent: (__VLS_ctx.overallProgress),
            status: (__VLS_ctx.batchProcessing ? 'active' : (__VLS_ctx.hasErrors ? 'exception' : 'success')),
            showInfo: (false),
        }));
        const __VLS_98 = __VLS_97({
            percent: (__VLS_ctx.overallProgress),
            status: (__VLS_ctx.batchProcessing ? 'active' : (__VLS_ctx.hasErrors ? 'exception' : 'success')),
            showInfo: (false),
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-list" },
    });
    const __VLS_100 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        dataSource: (__VLS_ctx.uploadedFiles),
        pagination: ({ pageSize: 10, showSizeChanger: true }),
    }));
    const __VLS_102 = __VLS_101({
        dataSource: (__VLS_ctx.uploadedFiles),
        pagination: ({ pageSize: 10, showSizeChanger: true }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    __VLS_103.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_103.slots;
        const [{ item, index }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_104 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
            ...{ 'onClick': {} },
            ...{ class: (['file-item', { 'selected': __VLS_ctx.selectedFileIndex === index }]) },
        }));
        const __VLS_106 = __VLS_105({
            ...{ 'onClick': {} },
            ...{ class: (['file-item', { 'selected': __VLS_ctx.selectedFileIndex === index }]) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_105));
        let __VLS_108;
        let __VLS_109;
        let __VLS_110;
        const __VLS_111 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.uploadedFiles.length > 0))
                    return;
                __VLS_ctx.selectFile(index);
            }
        };
        __VLS_107.slots.default;
        {
            const { actions: __VLS_thisSlot } = __VLS_107.slots;
            const __VLS_112 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
            const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
            __VLS_115.slots.default;
            if (!item.processing && !item.parsed) {
                const __VLS_116 = {}.AButton;
                /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
                // @ts-ignore
                const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
                    ...{ 'onClick': {} },
                    size: "small",
                    loading: (item.processing),
                }));
                const __VLS_118 = __VLS_117({
                    ...{ 'onClick': {} },
                    size: "small",
                    loading: (item.processing),
                }, ...__VLS_functionalComponentArgsRest(__VLS_117));
                let __VLS_120;
                let __VLS_121;
                let __VLS_122;
                const __VLS_123 = {
                    onClick: (...[$event]) => {
                        if (!(__VLS_ctx.uploadedFiles.length > 0))
                            return;
                        if (!(!item.processing && !item.parsed))
                            return;
                        __VLS_ctx.processSingleFile(index);
                    }
                };
                __VLS_119.slots.default;
                var __VLS_119;
            }
            const __VLS_124 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
                ...{ 'onClick': {} },
                size: "small",
                danger: true,
            }));
            const __VLS_126 = __VLS_125({
                ...{ 'onClick': {} },
                size: "small",
                danger: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_125));
            let __VLS_128;
            let __VLS_129;
            let __VLS_130;
            const __VLS_131 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.uploadedFiles.length > 0))
                        return;
                    __VLS_ctx.removeFile(index);
                }
            };
            __VLS_127.slots.default;
            var __VLS_127;
            var __VLS_115;
        }
        const __VLS_132 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({}));
        const __VLS_134 = __VLS_133({}, ...__VLS_functionalComponentArgsRest(__VLS_133));
        __VLS_135.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_135.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-title" },
            });
            const __VLS_136 = ((__VLS_ctx.getFileIcon(item.type)));
            // @ts-ignore
            const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
                ...{ class: "file-icon" },
            }));
            const __VLS_138 = __VLS_137({
                ...{ class: "file-icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_137));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "file-name" },
            });
            (item.name);
            const __VLS_140 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
                color: (__VLS_ctx.getStatusColor(item.status)),
                size: "small",
            }));
            const __VLS_142 = __VLS_141({
                color: (__VLS_ctx.getStatusColor(item.status)),
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_141));
            __VLS_143.slots.default;
            (__VLS_ctx.getStatusText(item.status));
            var __VLS_143;
        }
        {
            const { description: __VLS_thisSlot } = __VLS_135.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-details" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.formatFileSize(item.size));
            if (item.processing) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                const __VLS_144 = {}.ASpin;
                /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
                // @ts-ignore
                const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
                    size: "small",
                }));
                const __VLS_146 = __VLS_145({
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_145));
            }
            else if (item.parsed && item.confidence) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (Math.round(item.confidence));
            }
            else if (item.error) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "error-text" },
                });
                (item.error);
            }
        }
        var __VLS_135;
        if (item.processing) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-progress" },
            });
            const __VLS_148 = {}.AProgress;
            /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
            // @ts-ignore
            const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
                percent: (item.progress || 0),
                size: "small",
                status: "active",
                showInfo: (false),
            }));
            const __VLS_150 = __VLS_149({
                percent: (item.progress || 0),
                size: "small",
                status: "active",
                showInfo: (false),
            }, ...__VLS_functionalComponentArgsRest(__VLS_149));
        }
        var __VLS_107;
    }
    var __VLS_103;
    if (__VLS_ctx.batchResults.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "batch-results" },
        });
        const __VLS_152 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({}));
        const __VLS_154 = __VLS_153({}, ...__VLS_functionalComponentArgsRest(__VLS_153));
        __VLS_155.slots.default;
        var __VLS_155;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "results-actions" },
        });
        const __VLS_156 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({}));
        const __VLS_158 = __VLS_157({}, ...__VLS_functionalComponentArgsRest(__VLS_157));
        __VLS_159.slots.default;
        const __VLS_160 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
            ...{ 'onClick': {} },
            type: "primary",
            disabled: (__VLS_ctx.batchResults.length === 0),
        }));
        const __VLS_162 = __VLS_161({
            ...{ 'onClick': {} },
            type: "primary",
            disabled: (__VLS_ctx.batchResults.length === 0),
        }, ...__VLS_functionalComponentArgsRest(__VLS_161));
        let __VLS_164;
        let __VLS_165;
        let __VLS_166;
        const __VLS_167 = {
            onClick: (__VLS_ctx.showBatchResultsModal)
        };
        __VLS_163.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_163.slots;
            const __VLS_168 = {}.EyeOutlined;
            /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({}));
            const __VLS_170 = __VLS_169({}, ...__VLS_functionalComponentArgsRest(__VLS_169));
        }
        var __VLS_163;
        const __VLS_172 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
            ...{ 'onClick': {} },
        }));
        const __VLS_174 = __VLS_173({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_173));
        let __VLS_176;
        let __VLS_177;
        let __VLS_178;
        const __VLS_179 = {
            onClick: (__VLS_ctx.exportBatchResults)
        };
        __VLS_175.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_175.slots;
            const __VLS_180 = {}.DownloadOutlined;
            /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({}));
            const __VLS_182 = __VLS_181({}, ...__VLS_functionalComponentArgsRest(__VLS_181));
        }
        var __VLS_175;
        const __VLS_184 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
            ...{ 'onClick': {} },
            loading: (__VLS_ctx.saving),
        }));
        const __VLS_186 = __VLS_185({
            ...{ 'onClick': {} },
            loading: (__VLS_ctx.saving),
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
        let __VLS_188;
        let __VLS_189;
        let __VLS_190;
        const __VLS_191 = {
            onClick: (__VLS_ctx.saveBatchToDatabase)
        };
        __VLS_187.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_187.slots;
            const __VLS_192 = {}.DatabaseOutlined;
            /** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({}));
            const __VLS_194 = __VLS_193({}, ...__VLS_functionalComponentArgsRest(__VLS_193));
        }
        var __VLS_187;
        var __VLS_159;
    }
}
const __VLS_196 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    open: (__VLS_ctx.batchResultsModalVisible),
    title: "批量解析结果",
    width: "1200px",
    footer: (null),
    ...{ class: "batch-results-modal" },
}));
const __VLS_198 = __VLS_197({
    open: (__VLS_ctx.batchResultsModalVisible),
    title: "批量解析结果",
    width: "1200px",
    footer: (null),
    ...{ class: "batch-results-modal" },
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
__VLS_199.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-results-content" },
});
const __VLS_200 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
    activeKey: (__VLS_ctx.activeResultTab),
}));
const __VLS_202 = __VLS_201({
    activeKey: (__VLS_ctx.activeResultTab),
}, ...__VLS_functionalComponentArgsRest(__VLS_201));
__VLS_203.slots.default;
for (const [result, index] of __VLS_getVForSourceType((__VLS_ctx.batchResults))) {
    const __VLS_204 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        key: (index),
        tab: (result.fileName),
    }));
    const __VLS_206 = __VLS_205({
        key: (index),
        tab: (result.fileName),
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
    __VLS_207.slots.default;
    /** @type {[typeof LLMResultModal, ]} */ ;
    // @ts-ignore
    const __VLS_208 = __VLS_asFunctionalComponent(LLMResultModal_vue_1.default, new LLMResultModal_vue_1.default({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (true),
        data: (result.data),
        result: (result),
        originalText: (result.originalText),
    }));
    const __VLS_209 = __VLS_208({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (true),
        data: (result.data),
        result: (result),
        originalText: (result.originalText),
    }, ...__VLS_functionalComponentArgsRest(__VLS_208));
    let __VLS_211;
    let __VLS_212;
    let __VLS_213;
    const __VLS_214 = {
        'onUpdate:visible': (() => { })
    };
    const __VLS_215 = {
        onSaveAndRedirect: (() => __VLS_ctx.handleSingleSave(result))
    };
    const __VLS_216 = {
        onSaveOnly: (() => __VLS_ctx.handleSingleSave(result))
    };
    const __VLS_217 = {
        onExportResult: (() => __VLS_ctx.handleSingleExport(result))
    };
    const __VLS_218 = {
        onExportPdf: (() => __VLS_ctx.handleSingleExportPDF(result))
    };
    const __VLS_219 = {
        onGoToImport: (() => { })
    };
    var __VLS_210;
    var __VLS_207;
}
var __VLS_203;
var __VLS_199;
/** @type {__VLS_StyleScopedClasses['batch-file-processor']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-section']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-upload-dragger']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['file-management-section']} */ ;
/** @type {__VLS_StyleScopedClasses['file-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['overall-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-header']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-title']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-info']} */ ;
/** @type {__VLS_StyleScopedClasses['file-list']} */ ;
/** @type {__VLS_StyleScopedClasses['file-item']} */ ;
/** @type {__VLS_StyleScopedClasses['selected']} */ ;
/** @type {__VLS_StyleScopedClasses['file-title']} */ ;
/** @type {__VLS_StyleScopedClasses['file-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['file-name']} */ ;
/** @type {__VLS_StyleScopedClasses['file-details']} */ ;
/** @type {__VLS_StyleScopedClasses['error-text']} */ ;
/** @type {__VLS_StyleScopedClasses['file-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-results']} */ ;
/** @type {__VLS_StyleScopedClasses['results-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-results-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-results-content']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            InboxOutlined: icons_vue_1.InboxOutlined,
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            PauseCircleOutlined: icons_vue_1.PauseCircleOutlined,
            StopOutlined: icons_vue_1.StopOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            LLMResultModal: LLMResultModal_vue_1.default,
            fileList: fileList,
            uploadedFiles: uploadedFiles,
            selectedFileIndex: selectedFileIndex,
            batchProcessing: batchProcessing,
            isPaused: isPaused,
            canPause: canPause,
            completedFiles: completedFiles,
            currentProcessingFile: currentProcessingFile,
            batchResults: batchResults,
            batchResultsModalVisible: batchResultsModalVisible,
            activeResultTab: activeResultTab,
            saving: saving,
            totalSize: totalSize,
            parsedCount: parsedCount,
            successRate: successRate,
            overallProgress: overallProgress,
            hasErrors: hasErrors,
            beforeUpload: beforeUpload,
            handleFileUpload: handleFileUpload,
            getFileIcon: getFileIcon,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
            formatFileSize: formatFileSize,
            selectFile: selectFile,
            removeFile: removeFile,
            clearAllFiles: clearAllFiles,
            processSingleFile: processSingleFile,
            startBatchProcessing: startBatchProcessing,
            pauseProcessing: pauseProcessing,
            cancelProcessing: cancelProcessing,
            showBatchResultsModal: showBatchResultsModal,
            exportBatchResults: exportBatchResults,
            saveBatchToDatabase: saveBatchToDatabase,
            handleSingleSave: handleSingleSave,
            handleSingleExport: handleSingleExport,
            handleSingleExportPDF: handleSingleExportPDF,
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
