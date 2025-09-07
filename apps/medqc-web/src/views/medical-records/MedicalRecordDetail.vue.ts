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
import vue_router_1 from 'vue-router';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
// 路由和状态
const route = (0, vue_router_1.useRoute)();
const router = (0, vue_router_1.useRouter)();
const loading = (0, vue_1.ref)(false);
const error = (0, vue_1.ref)('');
const record = (0, vue_1.ref)(null);
const contentExpanded = (0, vue_1.ref)(false);
// 操作状态
const editLoading = (0, vue_1.ref)(false);
const deleteLoading = (0, vue_1.ref)(false);
const exportLoading = (0, vue_1.ref)(false);
// API 配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ||
    `${window.location.protocol}//${window.location.hostname}:8002`;
// 加载医疗记录详情
const loadRecord = async () => {
    const recordId = route.params.id;
    if (!recordId) {
        error.value = '缺少记录ID参数';
        return;
    }
    loading.value = true;
    error.value = '';
    try {
        const response = await fetch(`${API_BASE_URL}/api/medical-records/${recordId}`);
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('医疗记录不存在');
            }
            else if (response.status === 400) {
                throw new Error('无效的记录ID格式');
            }
            else {
                throw new Error(`服务器错误: ${response.status}`);
            }
        }
        const data = await response.json();
        record.value = data;
        console.log('医疗记录详情加载成功:', data);
    }
    catch (err) {
        console.error('加载医疗记录失败:', err);
        error.value = err.message || '加载医疗记录失败';
        ant_design_vue_1.message.error(error.value);
    }
    finally {
        loading.value = false;
    }
};
// 返回上一页
const goBack = () => {
    router.back();
};
// 刷新数据
const refreshData = () => {
    loadRecord();
};
// 切换内容展开状态
const toggleContentExpanded = () => {
    contentExpanded.value = !contentExpanded.value;
};
// 复制成功回调
const handleCopySuccess = (type) => {
    ant_design_vue_1.message.success(`${type}已复制到剪贴板`);
};
// 编辑功能
const handleEdit = () => {
    editLoading.value = true;
    try {
        // 跳转到编辑页面
        router.push(`/medical-records/edit/${record.value.id}`);
    }
    catch (error) {
        ant_design_vue_1.message.error('跳转到编辑页面失败');
    }
    finally {
        editLoading.value = false;
    }
};
// 导出功能
const handleExport = async () => {
    exportLoading.value = true;
    try {
        // 创建导出内容
        const exportData = {
            基本信息: {
                患者姓名: record.value.patient_name,
                年龄: record.value.patient_age,
                性别: record.value.patient_gender,
                病历编号: record.value.record_number,
                记录ID: record.value.id,
                创建时间: formatDateTime(record.value.created_at)
            },
            诊断信息: {
                主要诊断: record.value.diagnosis_primary,
                次要诊断: record.value.diagnosis_secondary
            },
            病历内容: record.value.content,
            文件信息: record.value.file_attachments,
            质控信息: {
                状态: getStatusText(record.value.status),
                优先级: getPriorityText(record.value.priority_level),
                标签: record.value.tags,
                质控评分: record.value.qc_score,
                质控等级: record.value.qc_grade
            },
            元数据: record.value.metadata
        };
        // 创建并下载文件
        const dataStr = JSON.stringify(exportData, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `医疗记录_${record.value.patient_name}_${record.value.record_number}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        ant_design_vue_1.message.success('医疗记录导出成功');
    }
    catch (error) {
        console.error('导出失败:', error);
        ant_design_vue_1.message.error('导出医疗记录失败');
    }
    finally {
        exportLoading.value = false;
    }
};
// 删除功能
const handleDelete = () => {
    if (!record.value || !record.value.id) {
        ant_design_vue_1.message.error('记录尚未加载，无法删除');
        return;
    }
    console.log('删除按钮被点击，记录信息:', record.value);
    const confirmed = window.confirm(`确定要删除患者 "${record.value.patient_name}" 的医疗记录吗？\n\n` +
        `病历编号: ${record.value.record_number}\n` +
        `记录ID: ${record.value.id}\n\n` +
        `此操作不可撤销！`);
    if (confirmed) {
        console.log('用户确认删除');
        performDelete();
    }
    else {
        console.log('用户取消删除');
    }
};
// 执行删除操作
const performDelete = async () => {
    console.log('开始执行删除操作，记录ID:', record.value.id);
    deleteLoading.value = true;
    try {
        const deleteUrl = `${API_BASE_URL}/api/medical-records/${record.value.id}`;
        console.log('删除请求URL:', deleteUrl);
        const response = await fetch(deleteUrl, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        console.log('删除响应状态:', response.status);
        if (!response.ok) {
            const errorText = await response.text();
            console.error('删除请求失败:', response.status, errorText);
            if (response.status === 404) {
                throw new Error('医疗记录不存在');
            }
            else if (response.status === 400) {
                throw new Error('无效的记录ID格式');
            }
            else {
                throw new Error(`删除失败: ${response.status} - ${errorText}`);
            }
        }
        const result = await response.json();
        console.log('删除成功，服务器响应:', result);
        ant_design_vue_1.message.success('医疗记录删除成功');
        // 延迟跳转，让用户看到成功消息
        setTimeout(() => {
            console.log('准备跳转回上一页');
            router.back();
        }, 1500);
    }
    catch (err) {
        console.error('删除医疗记录失败:', err);
        ant_design_vue_1.message.error(err.message || '删除医疗记录失败');
    }
    finally {
        deleteLoading.value = false;
    }
};
// 格式化日期时间
const formatDateTime = (dateStr) => {
    if (!dateStr)
        return '未知';
    try {
        return new Date(dateStr).toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    catch {
        return dateStr;
    }
};
// 格式化文件大小
const formatFileSize = (bytes) => {
    if (bytes === 0)
        return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};
// 获取状态颜色
const getStatusColor = (status) => {
    const colors = {
        'pending': 'processing',
        'completed': 'success',
        'failed': 'error',
        'reviewing': 'warning'
    };
    return colors[status] || 'default';
};
// 获取状态文本
const getStatusText = (status) => {
    const texts = {
        'pending': '待处理',
        'completed': '已完成',
        'failed': '失败',
        'reviewing': '审核中'
    };
    return texts[status] || status;
};
// 获取优先级颜色
const getPriorityColor = (level) => {
    if (level >= 4)
        return 'red';
    if (level >= 3)
        return 'orange';
    if (level >= 2)
        return 'blue';
    return 'green';
};
// 获取优先级文本
const getPriorityText = (level) => {
    const texts = {
        1: '低',
        2: '普通',
        3: '高',
        4: '紧急',
        5: '特急'
    };
    return texts[level] || `级别${level}`;
};
// 获取质控评分颜色
const getQcScoreColor = (score) => {
    if (score >= 90)
        return 'green';
    if (score >= 80)
        return 'blue';
    if (score >= 70)
        return 'orange';
    return 'red';
};
// 获取质控等级颜色
const getQcGradeColor = (grade) => {
    const colors = {
        'A': 'green',
        'B': 'blue',
        'C': 'orange',
        'D': 'red'
    };
    return colors[grade] || 'default';
};
// 获取记录类型文本
const getRecordTypeText = (type) => {
    const texts = {
        'inpatient': '住院',
        'outpatient': '门诊',
        'emergency': '急诊'
    };
    return texts[type] || type;
};
// 组件挂载时加载数据
(0, vue_1.onMounted)(() => {
    loadRecord();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['content-collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-content']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-content']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-content']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 p-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-7xl mx-auto mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-4" },
});
const __VLS_0 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onClick: (__VLS_ctx.goBack)
};
__VLS_3.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.ArrowLeftOutlined;
    /** @type {[typeof __VLS_components.ArrowLeftOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
    const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-2xl font-bold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 mt-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-3" },
});
const __VLS_12 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.editLoading),
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.editLoading),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (__VLS_ctx.handleEdit)
};
__VLS_15.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_15.slots;
    const __VLS_20 = {}.EditOutlined;
    /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
    const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
var __VLS_15;
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.exportLoading),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.exportLoading),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.handleExport)
};
__VLS_27.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_27.slots;
    const __VLS_32 = {}.DownloadOutlined;
    /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
    const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
}
var __VLS_27;
const __VLS_36 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onClick': {} },
    danger: true,
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.deleteLoading),
}));
const __VLS_38 = __VLS_37({
    ...{ 'onClick': {} },
    danger: true,
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.deleteLoading),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onClick: (__VLS_ctx.handleDelete)
};
__VLS_39.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_39.slots;
    const __VLS_44 = {}.DeleteOutlined;
    /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
    const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
}
var __VLS_39;
const __VLS_48 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onClick': {} },
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.loading),
}));
const __VLS_50 = __VLS_49({
    ...{ 'onClick': {} },
    type: "default",
    size: "large",
    ...{ class: "hover:shadow-md" },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onClick: (__VLS_ctx.refreshData)
};
__VLS_51.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_51.slots;
    const __VLS_56 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
    const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
}
var __VLS_51;
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "max-w-7xl mx-auto" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-blue-400/50 via-indigo-400/40 to-purple-400/50" },
    });
    const __VLS_60 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        ...{ class: "ui-card" },
    }));
    const __VLS_62 = __VLS_61({
        ...{ class: "ui-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center py-12" },
    });
    const __VLS_64 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        size: "large",
    }));
    const __VLS_66 = __VLS_65({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    {
        const { indicator: __VLS_thisSlot } = __VLS_67.slots;
        const __VLS_68 = {}.LoadingOutlined;
        /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
            ...{ style: {} },
            spin: true,
        }));
        const __VLS_70 = __VLS_69({
            ...{ style: {} },
            spin: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    }
    var __VLS_67;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "ml-3 text-lg text-gray-600" },
    });
    var __VLS_63;
}
else if (__VLS_ctx.error) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "max-w-7xl mx-auto" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-red-400/50 via-pink-400/40 to-rose-400/50" },
    });
    const __VLS_72 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ class: "ui-card" },
    }));
    const __VLS_74 = __VLS_73({
        ...{ class: "ui-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    __VLS_75.slots.default;
    const __VLS_76 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        status: "error",
        title: (__VLS_ctx.error),
        subTitle: "请检查记录ID是否正确，或稍后重试",
    }));
    const __VLS_78 = __VLS_77({
        status: "error",
        title: (__VLS_ctx.error),
        subTitle: "请检查记录ID是否正确，或稍后重试",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_79.slots;
        const __VLS_80 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_82 = __VLS_81({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_81));
        let __VLS_84;
        let __VLS_85;
        let __VLS_86;
        const __VLS_87 = {
            onClick: (__VLS_ctx.loadRecord)
        };
        __VLS_83.slots.default;
        var __VLS_83;
        const __VLS_88 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
            ...{ 'onClick': {} },
        }));
        const __VLS_90 = __VLS_89({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_89));
        let __VLS_92;
        let __VLS_93;
        let __VLS_94;
        const __VLS_95 = {
            onClick: (__VLS_ctx.goBack)
        };
        __VLS_91.slots.default;
        var __VLS_91;
    }
    var __VLS_79;
    var __VLS_75;
}
else if (__VLS_ctx.record) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "max-w-7xl mx-auto space-y-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-emerald-400/50 via-green-400/40 to-teal-400/50" },
    });
    const __VLS_96 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        title: "患者基本信息",
        ...{ class: "ui-card ui-card-hover" },
    }));
    const __VLS_98 = __VLS_97({
        title: "患者基本信息",
        ...{ class: "ui-card ui-card-hover" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    __VLS_99.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_99.slots;
        const __VLS_100 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            color: (__VLS_ctx.getStatusColor(__VLS_ctx.record.status)),
            ...{ class: "shadow-sm" },
        }));
        const __VLS_102 = __VLS_101({
            color: (__VLS_ctx.getStatusColor(__VLS_ctx.record.status)),
            ...{ class: "shadow-sm" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        __VLS_103.slots.default;
        (__VLS_ctx.getStatusText(__VLS_ctx.record.status));
        var __VLS_103;
    }
    const __VLS_104 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        gutter: ([24, 16]),
    }));
    const __VLS_106 = __VLS_105({
        gutter: ([24, 16]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    __VLS_107.slots.default;
    const __VLS_108 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_110 = __VLS_109({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    __VLS_111.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.record.patient_name);
    var __VLS_111;
    const __VLS_112 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_114 = __VLS_113({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_113));
    __VLS_115.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.record.patient_age);
    (__VLS_ctx.record.patient_gender);
    var __VLS_115;
    const __VLS_116 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_118 = __VLS_117({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    __VLS_119.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    const __VLS_120 = {}.ATypographyText;
    /** @type {[typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        copyable: ({
            text: __VLS_ctx.record.record_number,
            onCopy: () => __VLS_ctx.handleCopySuccess('病历编号')
        }),
    }));
    const __VLS_122 = __VLS_121({
        copyable: ({
            text: __VLS_ctx.record.record_number,
            onCopy: () => __VLS_ctx.handleCopySuccess('病历编号')
        }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
    __VLS_123.slots.default;
    (__VLS_ctx.record.record_number);
    var __VLS_123;
    var __VLS_119;
    const __VLS_124 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_126 = __VLS_125({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
    __VLS_127.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    const __VLS_128 = {}.ATypographyText;
    /** @type {[typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        copyable: ({
            text: __VLS_ctx.record.id,
            onCopy: () => __VLS_ctx.handleCopySuccess('记录ID')
        }),
        ...{ class: "text-xs" },
    }));
    const __VLS_130 = __VLS_129({
        copyable: ({
            text: __VLS_ctx.record.id,
            onCopy: () => __VLS_ctx.handleCopySuccess('记录ID')
        }),
        ...{ class: "text-xs" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    __VLS_131.slots.default;
    (__VLS_ctx.record.id);
    var __VLS_131;
    var __VLS_127;
    const __VLS_132 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_134 = __VLS_133({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.formatDateTime(__VLS_ctx.record.created_at));
    var __VLS_135;
    const __VLS_136 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_138 = __VLS_137({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.formatDateTime(__VLS_ctx.record.updated_at));
    var __VLS_139;
    var __VLS_107;
    var __VLS_99;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-blue-400/50 via-indigo-400/40 to-purple-400/50" },
    });
    const __VLS_140 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
        title: "诊断信息",
        ...{ class: "ui-card ui-card-hover" },
    }));
    const __VLS_142 = __VLS_141({
        title: "诊断信息",
        ...{ class: "ui-card ui-card-hover" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_141));
    __VLS_143.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_143.slots;
        const __VLS_144 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
            color: "processing",
        }));
        const __VLS_146 = __VLS_145({
            color: "processing",
        }, ...__VLS_functionalComponentArgsRest(__VLS_145));
        __VLS_147.slots.default;
        const __VLS_148 = {}.MedicineBoxOutlined;
        /** @type {[typeof __VLS_components.MedicineBoxOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({}));
        const __VLS_150 = __VLS_149({}, ...__VLS_functionalComponentArgsRest(__VLS_149));
        var __VLS_147;
    }
    const __VLS_152 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        gutter: ([24, 16]),
    }));
    const __VLS_154 = __VLS_153({
        gutter: ([24, 16]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    const __VLS_156 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        xs: (24),
        md: (12),
    }));
    const __VLS_158 = __VLS_157({
        xs: (24),
        md: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.record.diagnosis_primary || '未填写');
    var __VLS_159;
    const __VLS_160 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        xs: (24),
        md: (12),
    }));
    const __VLS_162 = __VLS_161({
        xs: (24),
        md: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    __VLS_163.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    if (__VLS_ctx.record.diagnosis_secondary && __VLS_ctx.record.diagnosis_secondary.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "space-y-1" },
        });
        for (const [diagnosis, index] of __VLS_getVForSourceType((__VLS_ctx.record.diagnosis_secondary))) {
            const __VLS_164 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
                key: (index),
                color: "blue",
                ...{ class: "mb-1" },
            }));
            const __VLS_166 = __VLS_165({
                key: (index),
                color: "blue",
                ...{ class: "mb-1" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_165));
            __VLS_167.slots.default;
            (diagnosis);
            var __VLS_167;
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-500" },
        });
    }
    var __VLS_163;
    var __VLS_155;
    var __VLS_143;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-orange-400/50 via-amber-400/40 to-yellow-400/50" },
    });
    const __VLS_168 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        title: "病历内容",
        ...{ class: "ui-card ui-card-hover" },
    }));
    const __VLS_170 = __VLS_169({
        title: "病历内容",
        ...{ class: "ui-card ui-card-hover" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_171.slots;
        const __VLS_172 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({}));
        const __VLS_174 = __VLS_173({}, ...__VLS_functionalComponentArgsRest(__VLS_173));
        __VLS_175.slots.default;
        const __VLS_176 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
            color: "orange",
        }));
        const __VLS_178 = __VLS_177({
            color: "orange",
        }, ...__VLS_functionalComponentArgsRest(__VLS_177));
        __VLS_179.slots.default;
        const __VLS_180 = {}.FileTextOutlined;
        /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({}));
        const __VLS_182 = __VLS_181({}, ...__VLS_functionalComponentArgsRest(__VLS_181));
        (__VLS_ctx.record.word_count);
        var __VLS_179;
        const __VLS_184 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_186 = __VLS_185({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
        let __VLS_188;
        let __VLS_189;
        let __VLS_190;
        const __VLS_191 = {
            onClick: (__VLS_ctx.toggleContentExpanded)
        };
        __VLS_187.slots.default;
        (__VLS_ctx.contentExpanded ? '收起' : '展开全部');
        var __VLS_187;
        var __VLS_175;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "medical-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: ([
                'content-text',
                { 'content-collapsed': !__VLS_ctx.contentExpanded }
            ]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
        ...{ class: "whitespace-pre-wrap font-sans" },
    });
    (__VLS_ctx.record.content);
    if (!__VLS_ctx.contentExpanded && __VLS_ctx.record.content && __VLS_ctx.record.content.length > 1000) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "content-fade" },
        });
    }
    var __VLS_171;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-purple-400/50 via-pink-400/40 to-rose-400/50" },
    });
    const __VLS_192 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
        title: "文件信息",
        ...{ class: "ui-card ui-card-hover" },
    }));
    const __VLS_194 = __VLS_193({
        title: "文件信息",
        ...{ class: "ui-card ui-card-hover" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_193));
    __VLS_195.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_195.slots;
        const __VLS_196 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
            color: "purple",
        }));
        const __VLS_198 = __VLS_197({
            color: "purple",
        }, ...__VLS_functionalComponentArgsRest(__VLS_197));
        __VLS_199.slots.default;
        const __VLS_200 = {}.FolderOpenOutlined;
        /** @type {[typeof __VLS_components.FolderOpenOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({}));
        const __VLS_202 = __VLS_201({}, ...__VLS_functionalComponentArgsRest(__VLS_201));
        (__VLS_ctx.record.file_attachments?.length || 0);
        var __VLS_199;
    }
    if (__VLS_ctx.record.file_attachments && __VLS_ctx.record.file_attachments.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        for (const [file, index] of __VLS_getVForSourceType((__VLS_ctx.record.file_attachments))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (index),
                ...{ class: "file-item p-4 border border-gray-200 rounded-lg mb-3 last:mb-0" },
            });
            const __VLS_204 = {}.ARow;
            /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
            // @ts-ignore
            const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
                gutter: ([16, 8]),
            }));
            const __VLS_206 = __VLS_205({
                gutter: ([16, 8]),
            }, ...__VLS_functionalComponentArgsRest(__VLS_205));
            __VLS_207.slots.default;
            const __VLS_208 = {}.ACol;
            /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
            // @ts-ignore
            const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
                xs: (24),
                sm: (12),
                md: (6),
            }));
            const __VLS_210 = __VLS_209({
                xs: (24),
                sm: (12),
                md: (6),
            }, ...__VLS_functionalComponentArgsRest(__VLS_209));
            __VLS_211.slots.default;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-value" },
            });
            (file.filename);
            var __VLS_211;
            const __VLS_212 = {}.ACol;
            /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
            // @ts-ignore
            const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
                xs: (24),
                sm: (12),
                md: (6),
            }));
            const __VLS_214 = __VLS_213({
                xs: (24),
                sm: (12),
                md: (6),
            }, ...__VLS_functionalComponentArgsRest(__VLS_213));
            __VLS_215.slots.default;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-value" },
            });
            (__VLS_ctx.formatFileSize(file.size));
            var __VLS_215;
            const __VLS_216 = {}.ACol;
            /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
            // @ts-ignore
            const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
                xs: (24),
                sm: (12),
                md: (6),
            }));
            const __VLS_218 = __VLS_217({
                xs: (24),
                sm: (12),
                md: (6),
            }, ...__VLS_functionalComponentArgsRest(__VLS_217));
            __VLS_219.slots.default;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-value" },
            });
            (file.type);
            var __VLS_219;
            const __VLS_220 = {}.ACol;
            /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
            // @ts-ignore
            const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
                xs: (24),
                sm: (12),
                md: (6),
            }));
            const __VLS_222 = __VLS_221({
                xs: (24),
                sm: (12),
                md: (6),
            }, ...__VLS_functionalComponentArgsRest(__VLS_221));
            __VLS_223.slots.default;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "info-value" },
            });
            (file.pages || 1);
            var __VLS_223;
            var __VLS_207;
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-center py-8 text-gray-500" },
        });
        const __VLS_224 = {}.InboxOutlined;
        /** @type {[typeof __VLS_components.InboxOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
            ...{ class: "text-4xl mb-2" },
        }));
        const __VLS_226 = __VLS_225({
            ...{ class: "text-4xl mb-2" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_225));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    }
    var __VLS_195;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-cyan-400/50 via-blue-400/40 to-indigo-400/50" },
    });
    const __VLS_228 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
        title: "质控信息",
        ...{ class: "ui-card ui-card-hover" },
    }));
    const __VLS_230 = __VLS_229({
        title: "质控信息",
        ...{ class: "ui-card ui-card-hover" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_229));
    __VLS_231.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_231.slots;
        const __VLS_232 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({}));
        const __VLS_234 = __VLS_233({}, ...__VLS_functionalComponentArgsRest(__VLS_233));
        __VLS_235.slots.default;
        if (__VLS_ctx.record.qc_score) {
            const __VLS_236 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
                color: (__VLS_ctx.getQcScoreColor(__VLS_ctx.record.qc_score)),
            }));
            const __VLS_238 = __VLS_237({
                color: (__VLS_ctx.getQcScoreColor(__VLS_ctx.record.qc_score)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_237));
            __VLS_239.slots.default;
            (__VLS_ctx.record.qc_score);
            var __VLS_239;
        }
        if (__VLS_ctx.record.qc_grade) {
            const __VLS_240 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
                color: (__VLS_ctx.getQcGradeColor(__VLS_ctx.record.qc_grade)),
            }));
            const __VLS_242 = __VLS_241({
                color: (__VLS_ctx.getQcGradeColor(__VLS_ctx.record.qc_grade)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_241));
            __VLS_243.slots.default;
            (__VLS_ctx.record.qc_grade);
            var __VLS_243;
        }
        var __VLS_235;
    }
    const __VLS_244 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
        gutter: ([24, 16]),
    }));
    const __VLS_246 = __VLS_245({
        gutter: ([24, 16]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_245));
    __VLS_247.slots.default;
    const __VLS_248 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_250 = __VLS_249({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_249));
    __VLS_251.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    const __VLS_252 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({
        color: (__VLS_ctx.getPriorityColor(__VLS_ctx.record.priority_level)),
    }));
    const __VLS_254 = __VLS_253({
        color: (__VLS_ctx.getPriorityColor(__VLS_ctx.record.priority_level)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_253));
    __VLS_255.slots.default;
    (__VLS_ctx.getPriorityText(__VLS_ctx.record.priority_level));
    var __VLS_255;
    var __VLS_251;
    const __VLS_256 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_258 = __VLS_257({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_257));
    __VLS_259.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    if (__VLS_ctx.record.tags && __VLS_ctx.record.tags.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "space-y-1" },
        });
        for (const [tag, index] of __VLS_getVForSourceType((__VLS_ctx.record.tags))) {
            const __VLS_260 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
                key: (index),
                color: "cyan",
                ...{ class: "mb-1" },
            }));
            const __VLS_262 = __VLS_261({
                key: (index),
                color: "cyan",
                ...{ class: "mb-1" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_261));
            __VLS_263.slots.default;
            (tag);
            var __VLS_263;
        }
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-500" },
        });
    }
    var __VLS_259;
    const __VLS_264 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_266 = __VLS_265({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_265));
    __VLS_267.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.getRecordTypeText(__VLS_ctx.record.record_type));
    var __VLS_267;
    var __VLS_247;
    var __VLS_231;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "ui-gradient-wrap from-gray-400/50 via-slate-400/40 to-zinc-400/50" },
    });
    const __VLS_268 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
        title: "元数据信息",
        ...{ class: "ui-card ui-card-hover" },
    }));
    const __VLS_270 = __VLS_269({
        title: "元数据信息",
        ...{ class: "ui-card ui-card-hover" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_269));
    __VLS_271.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_271.slots;
        const __VLS_272 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
            color: "default",
        }));
        const __VLS_274 = __VLS_273({
            color: "default",
        }, ...__VLS_functionalComponentArgsRest(__VLS_273));
        __VLS_275.slots.default;
        const __VLS_276 = {}.DatabaseOutlined;
        /** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({}));
        const __VLS_278 = __VLS_277({}, ...__VLS_functionalComponentArgsRest(__VLS_277));
        var __VLS_275;
    }
    const __VLS_280 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
        gutter: ([24, 16]),
    }));
    const __VLS_282 = __VLS_281({
        gutter: ([24, 16]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_281));
    __VLS_283.slots.default;
    const __VLS_284 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_286 = __VLS_285({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_285));
    __VLS_287.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.record.metadata?.import_method || '未知');
    var __VLS_287;
    const __VLS_288 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_290 = __VLS_289({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_289));
    __VLS_291.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.record.metadata?.parse_result?.method || '未知');
    var __VLS_291;
    const __VLS_292 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_294 = __VLS_293({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_293));
    __VLS_295.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.formatDateTime(__VLS_ctx.record.metadata?.import_time));
    var __VLS_295;
    var __VLS_283;
    if (__VLS_ctx.record.metadata?.parse_result) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-6" },
        });
        const __VLS_296 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({}));
        const __VLS_298 = __VLS_297({}, ...__VLS_functionalComponentArgsRest(__VLS_297));
        __VLS_299.slots.default;
        var __VLS_299;
        const __VLS_300 = {}.ADescriptions;
        /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({
            bordered: true,
            size: "small",
            column: (1),
        }));
        const __VLS_302 = __VLS_301({
            bordered: true,
            size: "small",
            column: (1),
        }, ...__VLS_functionalComponentArgsRest(__VLS_301));
        __VLS_303.slots.default;
        if (__VLS_ctx.record.metadata.parse_result.medical_info?.department) {
            const __VLS_304 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
                label: "科室",
            }));
            const __VLS_306 = __VLS_305({
                label: "科室",
            }, ...__VLS_functionalComponentArgsRest(__VLS_305));
            __VLS_307.slots.default;
            (__VLS_ctx.record.metadata.parse_result.medical_info.department);
            var __VLS_307;
        }
        if (__VLS_ctx.record.metadata.parse_result.medical_info?.symptoms?.length) {
            const __VLS_308 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({
                label: "症状",
            }));
            const __VLS_310 = __VLS_309({
                label: "症状",
            }, ...__VLS_functionalComponentArgsRest(__VLS_309));
            __VLS_311.slots.default;
            for (const [symptom, index] of __VLS_getVForSourceType((__VLS_ctx.record.metadata.parse_result.medical_info.symptoms))) {
                const __VLS_312 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_313 = __VLS_asFunctionalComponent(__VLS_312, new __VLS_312({
                    key: (index),
                    color: "orange",
                    ...{ class: "mb-1 mr-1" },
                }));
                const __VLS_314 = __VLS_313({
                    key: (index),
                    color: "orange",
                    ...{ class: "mb-1 mr-1" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_313));
                __VLS_315.slots.default;
                (symptom);
                var __VLS_315;
            }
            var __VLS_311;
        }
        if (__VLS_ctx.record.metadata.parse_result.medical_info?.procedures?.length) {
            const __VLS_316 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
                label: "手术/操作",
            }));
            const __VLS_318 = __VLS_317({
                label: "手术/操作",
            }, ...__VLS_functionalComponentArgsRest(__VLS_317));
            __VLS_319.slots.default;
            for (const [procedure, index] of __VLS_getVForSourceType((__VLS_ctx.record.metadata.parse_result.medical_info.procedures))) {
                const __VLS_320 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
                    key: (index),
                    color: "purple",
                    ...{ class: "mb-1 mr-1" },
                }));
                const __VLS_322 = __VLS_321({
                    key: (index),
                    color: "purple",
                    ...{ class: "mb-1 mr-1" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_321));
                __VLS_323.slots.default;
                (procedure);
                var __VLS_323;
            }
            var __VLS_319;
        }
        if (__VLS_ctx.record.metadata.parse_result.medical_info?.medications?.length) {
            const __VLS_324 = {}.ADescriptionsItem;
            /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
            // @ts-ignore
            const __VLS_325 = __VLS_asFunctionalComponent(__VLS_324, new __VLS_324({
                label: "用药",
            }));
            const __VLS_326 = __VLS_325({
                label: "用药",
            }, ...__VLS_functionalComponentArgsRest(__VLS_325));
            __VLS_327.slots.default;
            for (const [medication, index] of __VLS_getVForSourceType((__VLS_ctx.record.metadata.parse_result.medical_info.medications))) {
                const __VLS_328 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
                    key: (index),
                    color: "green",
                    ...{ class: "mb-1 mr-1" },
                }));
                const __VLS_330 = __VLS_329({
                    key: (index),
                    color: "green",
                    ...{ class: "mb-1 mr-1" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_329));
                __VLS_331.slots.default;
                (medication);
                var __VLS_331;
            }
            var __VLS_327;
        }
        var __VLS_303;
    }
    var __VLS_271;
}
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-slate-50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-50']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-indigo-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-purple-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-12']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-red-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-pink-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-rose-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-emerald-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-green-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-teal-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-indigo-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-purple-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-orange-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-amber-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-yellow-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['font-sans']} */ ;
/** @type {__VLS_StyleScopedClasses['content-fade']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-purple-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-pink-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-rose-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['file-item']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['last:mb-0']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-gray-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-slate-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-zinc-400/50']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ArrowLeftOutlined: icons_vue_1.ArrowLeftOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            LoadingOutlined: icons_vue_1.LoadingOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            FolderOpenOutlined: icons_vue_1.FolderOpenOutlined,
            InboxOutlined: icons_vue_1.InboxOutlined,
            MedicineBoxOutlined: icons_vue_1.MedicineBoxOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            loading: loading,
            error: error,
            record: record,
            contentExpanded: contentExpanded,
            editLoading: editLoading,
            deleteLoading: deleteLoading,
            exportLoading: exportLoading,
            loadRecord: loadRecord,
            goBack: goBack,
            refreshData: refreshData,
            toggleContentExpanded: toggleContentExpanded,
            handleCopySuccess: handleCopySuccess,
            handleEdit: handleEdit,
            handleExport: handleExport,
            handleDelete: handleDelete,
            formatDateTime: formatDateTime,
            formatFileSize: formatFileSize,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
            getPriorityColor: getPriorityColor,
            getPriorityText: getPriorityText,
            getQcScoreColor: getQcScoreColor,
            getQcGradeColor: getQcGradeColor,
            getRecordTypeText: getRecordTypeText,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
