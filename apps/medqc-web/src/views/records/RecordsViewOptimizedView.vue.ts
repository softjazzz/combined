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
import vue_router_1 from 'vue-router';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
// 组件导入
const VirtualListComponent_vue_1 = __importDefault(require("@/components/common/VirtualListComponent.vue"));
const LazyImageComponent_vue_1 = __importDefault(require("@/components/common/LazyImageComponent.vue"));
const BatchOperationsComponent_vue_1 = __importDefault(require("@/components/common/BatchOperationsComponent.vue"));
const RecordUploadFormComponent_vue_1 = __importDefault(require("@/components/forms/RecordUploadFormComponent.vue"));
const QCResultDisplay_vue_1 = __importDefault(require("@/components/qc/QCResultDisplay.vue"));
// API导入
import medical_records_1 from '@/api/medical-records';
import qc_analysis_optimized_1 from '@/api/qc-analysis-optimized';
// 工具函数导入
import date_1 from '@/utils/date';
import useBreakpoints_1 from '@/composables/useBreakpoints';
// 响应式数据
const router = (0, vue_router_1.useRouter)();
const { isMobile } = (0, useBreakpoints_1.useBreakpoints)();
const records = (0, vue_1.ref)(: any[]);
const selectedRecords = (0, vue_1.ref)(: any[]);
const loading = (0, vue_1.ref)(false);
const uploading = (0, vue_1.ref)(false);
const batchAnalyzing = (0, vue_1.ref)(false);
const analyzingRecords = (0, vue_1.ref)(: any[]);
const hasMore = (0, vue_1.ref)(true);
const currentPage = (0, vue_1.ref)(1);
const pageSize = (0, vue_1.ref)(20);
// 筛选和搜索
const searchKeyword = (0, vue_1.ref)('');
const statusFilter = (0, vue_1.ref)('');
const departmentFilter = (0, vue_1.ref)('');
// 模态框状态
const showUploadModal = (0, vue_1.ref)(false);
const showAnalysisModal = (0, vue_1.ref)(false);
const currentAnalysisResult = (0, vue_1.ref)(null);
// 统计数据
const stats = (0, vue_1.computed)(() => [
    { key: 'total', label: '总病案数', value: records.value.length },
    { key: 'pending', label: '待分析', value: records.value.filter(r => r.status === 'pending').length },
    { key: 'completed', label: '已完成', value: records.value.filter(r => r.status === 'completed').length },
    { key: 'analyzing', label: '分析中', value: records.value.filter(r => r.status === 'analyzing').length }
]);
// 科室列表
const departments = (0, vue_1.computed)(() => {
    const depts = new Set(records.value.map(r => r.department).filter(Boolean));
    return Array.from(depts).sort();
});
// 过滤后的记录
const filteredRecords = (0, vue_1.computed)(() => {
    let filtered = records.value;
    // 搜索过滤
    if (searchKeyword.value) {
        const keyword = searchKeyword.value.toLowerCase();
        filtered = filtered.filter(record => record.patient_name?.toLowerCase().includes(keyword) ||
            record.department?.toLowerCase().includes(keyword) ||
            record.record_type?.toLowerCase().includes(keyword));
    }
    // 状态过滤
    if (statusFilter.value) {
        filtered = filtered.filter(record => record.status === statusFilter.value);
    }
    // 科室过滤
    if (departmentFilter.value) {
        filtered = filtered.filter(record => record.department === departmentFilter.value);
    }
    return filtered;
});
// 批量操作配置
const batchActions = (0, vue_1.computed)(() => [
    {
        key: 'analyze',
        label: '批量分析',
        shortLabel: '分析',
        icon: icons_vue_1.AnalysisOutlined,
        type: 'primary',
        minSelection: 1,
        maxSelection: 10,
        validator: (items: any) => {
            const analyzingCount = items.filter(item => item.status === 'analyzing').length;
            if (analyzingCount > 0) {
                return '选中的病案中包含正在分析的记录';
            }
            return true;
        }
    },
    {
        key: 'export',
        label: '批量导出',
        shortLabel: '导出',
        icon: icons_vue_1.ExportOutlined,
        minSelection: 1,
        maxSelection: 50
    },
    {
        key: 'delete',
        label: '批量删除',
        shortLabel: '删除',
        icon: icons_vue_1.DeleteOutlined,
        danger: true,
        requireConfirm: true,
        confirmTitle: '确认删除',
        confirmContent: '删除后无法恢复，确定要删除选中的病案吗？',
        minSelection: 1,
        validator: (items: any) => {
            const analyzingCount = items.filter(item => item.status === 'analyzing').length;
            if (analyzingCount > 0) {
                return '无法删除正在分析的病案';
            }
            return true;
        }
    }
]);
// 方法
const loadRecords = async (page = 1, append = false) => {
    try {
        loading.value = true;
        const response = await (0, medical_records_1.getMedicalRecords)({
            page,
            pageSize: pageSize.value,
            status: statusFilter.value || undefined,
            department: departmentFilter.value || undefined,
            search: searchKeyword.value || undefined
        });
        if (response.success && response.data) {
            if (append) {
                records.value.push(...response.data.data);
            }
            else {
                records.value = response.data.data;
            }
            hasMore.value = response.data.hasMore;
            currentPage.value = page;
        }
    }
    catch (error) {
        console.error('加载病案列表失败:', error);
        ant_design_vue_1.message.error('加载病案列表失败');
    }
    finally {
        loading.value = false;
    }
};
const loadMore = async () => {
    if (hasMore.value && !loading.value) {
        await loadRecords(currentPage.value + 1, true);
    }
};
const handleSearch = () => {
    currentPage.value = 1;
    loadRecords(1, false);
};
const handleRecordSubmit = async (formData) => {
    try {
        uploading.value = true;
        const response = await (0, medical_records_1.createMedicalRecord)(formData);
        if (response.success) {
            ant_design_vue_1.message.success('病案上传成功');
            showUploadModal.value = false;
            await loadRecords(1, false); // 重新加载列表
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '上传失败');
        }
    }
    catch (error) {
        console.error('上传病案失败:', error);
        ant_design_vue_1.message.error('上传病案失败');
    }
    finally {
        uploading.value = false;
    }
};
const analyzeRecord = async (record) => {
    try {
        analyzingRecords.value.push(record.id);
        const response = await (0, qc_analysis_optimized_1.analyzeRecord)({
            recordId: record.id,
            content: record.content,
            options: {
                analysisMode: 'comprehensive',
                enableCache: true,
                priority: 'normal'
            }
        });
        if (response.success && response.data) {
            ant_design_vue_1.message.success('分析完成');
            currentAnalysisResult.value = response.data;
            showAnalysisModal.value = true;
            // 更新记录状态
            const index = records.value.findIndex(r => r.id === record.id);
            if (index !== -1) {
                records.value[index].status = 'completed';
            }
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '分析失败');
        }
    }
    catch (error) {
        console.error('分析失败:', error);
        ant_design_vue_1.message.error('分析失败');
    }
    finally {
        analyzingRecords.value = analyzingRecords.value.filter(id => id !== record.id);
    }
};
const handleBatchAnalysis = async () => {
    if (selectedRecords.value.length === 0) {
        ant_design_vue_1.message.warning('请先选择要分析的病案');
        return;
    }
    try {
        batchAnalyzing.value = true;
        const response = await (0, qc_analysis_optimized_1.batchAnalyzeRecords)({
            records: selectedRecords.value.map(record => ({
                recordId: record.id,
                content: record.content,
                priority: 'normal'
            })),
            options: {
                analysisMode: 'comprehensive',
                enableCache: true,
                maxConcurrency: 3
            }
        });
        if (response.success && response.data) {
            const { summary } = response.data;
            ant_design_vue_1.message.success(`批量分析完成：成功 ${summary.successful} 项，失败 ${summary.failed} 项`);
            // 更新记录状态
            selectedRecords.value.forEach(record => {
                const index = records.value.findIndex(r => r.id === record.id);
                if (index !== -1) {
                    records.value[index].status = 'completed';
                }
            });
            selectedRecords.value = [];
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '批量分析失败');
        }
    }
    catch (error) {
        console.error('批量分析失败:', error);
        ant_design_vue_1.message.error('批量分析失败');
    }
    finally {
        batchAnalyzing.value = false;
    }
};
const handleRecordSelect = (record, selected) => {
    if (selected) {
        if (!selectedRecords.value.find(r => r.id === record.id)) {
            selectedRecords.value.push(record);
        }
    }
    else {
        selectedRecords.value = selectedRecords.value.filter(r => r.id !== record.id);
    }
};
const handleSelectAll = (selected) => {
    if (selected) {
        selectedRecords.value = [...filteredRecords.value];
    }
    else {
        selectedRecords.value = [];
    }
};
const handleBatchAction = async (action, items) => {
    switch (action.key) {
        case 'analyze':
            await handleBatchAnalysis();
            break;
        case 'export':
            await handleBatchExport(items);
            break;
        case 'delete':
            await handleBatchDelete(items);
            break;
    }
};
const handleBatchExport = async (items) => {
    try {
        // 实现批量导出逻辑
        ant_design_vue_1.message.success(`导出 ${items.length} 条记录`);
    }
    catch (error) {
        ant_design_vue_1.message.error('导出失败');
    }
};
const handleBatchDelete = async (items) => {
    try {
        const deletePromises = items.map(item => (0, medical_records_1.deleteMedicalRecord)(item.id));
        await Promise.all(deletePromises);
        ant_design_vue_1.message.success(`删除 ${items.length} 条记录`);
        await loadRecords(1, false);
        selectedRecords.value = [];
    }
    catch (error) {
        ant_design_vue_1.message.error('删除失败');
    }
};
const viewRecord = (record) => {
    router.push(`/records/${record.id}`);
};
const handleRecordAction = async (action, record) => {
    switch (action) {
        case 'edit':
            // 实现编辑逻辑
            break;
        case 'download':
            // 实现下载逻辑
            break;
        case 'history':
            router.push(`/records/${record.id}/history`);
            break;
        case 'delete':
            await handleDeleteRecord(record);
            break;
    }
};
const handleDeleteRecord = async (record) => {
    try {
        const response = await (0, medical_records_1.deleteMedicalRecord)(record.id);
        if (response.success) {
            ant_design_vue_1.message.success('删除成功');
            await loadRecords(1, false);
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '删除失败');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('删除失败');
    }
};
// 工具方法
const isSelected = (record) => {
    return selectedRecords.value.some(r => r.id === record.id);
};
const getPatientAvatar = (record) => {
    // 返回患者头像URL，这里使用占位符
    return `https://api.dicebear.com/7.x/avataaars/svg?seed=${record.patient_name}`;
};
const getDefaultAvatar = (gender) => {
    return gender === '女'
        ? 'https://api.dicebear.com/7.x/avataaars/svg?seed=female'
        : 'https://api.dicebear.com/7.x/avataaars/svg?seed=male';
};
const getGenderColor = (gender) => {
    return gender === '女' ? 'pink' : 'blue';
};
const getStatusColor = (status) => {
    const colors = {
        pending: 'orange',
        analyzing: 'blue',
        completed: 'green',
        failed: 'red'
    };
    return colors[status] || 'default';
};
const getStatusText = (status) => {
    const texts = {
        pending: '待分析',
        analyzing: '分析中',
        completed: '已完成',
        failed: '失败'
    };
    return texts[status] || status;
};
// 监听筛选条件变化
(0, vue_1.watch)([statusFilter: any, departmentFilter], () => {
    currentPage.value = 1;
    loadRecords(1, false);
});
// 生命周期
(0, vue_1.onMounted)(() => {
    loadRecords();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['record-item']} */ ;
/** @type {__VLS_StyleScopedClasses['record-item']} */ ;
/** @type {__VLS_StyleScopedClasses['record-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['record-item']} */ ;
/** @type {__VLS_StyleScopedClasses['record-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['record-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['record-content']} */ ;
/** @type {__VLS_StyleScopedClasses['record-header']} */ ;
/** @type {__VLS_StyleScopedClasses['record-info']} */ ;
/** @type {__VLS_StyleScopedClasses['record-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['records-container']} */ ;
/** @type {__VLS_StyleScopedClasses['record-item']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "records-view-optimized" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-stats" },
});
for (const [stat] of __VLS_getVForSourceType((__VLS_ctx.stats))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-card" },
        key: (stat.key),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-value" },
    });
    (stat.value);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "stat-label" },
    });
    (stat.label);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar-left" },
});
const __VLS_0 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.uploading),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.uploading),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showUploadModal = true;
    }
};
__VLS_3.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
    const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
const __VLS_12 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.selectedRecords.length === 0),
    loading: (__VLS_ctx.batchAnalyzing),
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.selectedRecords.length === 0),
    loading: (__VLS_ctx.batchAnalyzing),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (__VLS_ctx.handleBatchAnalysis)
};
__VLS_15.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_15.slots;
    const __VLS_20 = {}.ThunderboltOutlined;
    /** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
    const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
var __VLS_15;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar-right" },
});
const __VLS_24 = {}.AInputSearch;
/** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchKeyword),
    placeholder: "搜索患者姓名、科室...",
    ...{ style: {} },
    allowClear: true,
}));
const __VLS_26 = __VLS_25({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchKeyword),
    placeholder: "搜索患者姓名、科室...",
    ...{ style: {} },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onSearch: (__VLS_ctx.handleSearch)
};
var __VLS_27;
const __VLS_32 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: (__VLS_ctx.statusFilter),
    placeholder: "状态筛选",
    ...{ style: {} },
    allowClear: true,
}));
const __VLS_34 = __VLS_33({
    value: (__VLS_ctx.statusFilter),
    placeholder: "状态筛选",
    ...{ style: {} },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: "",
}));
const __VLS_38 = __VLS_37({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
var __VLS_39;
const __VLS_40 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    value: "pending",
}));
const __VLS_42 = __VLS_41({
    value: "pending",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
var __VLS_43;
const __VLS_44 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    value: "analyzing",
}));
const __VLS_46 = __VLS_45({
    value: "analyzing",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
var __VLS_47;
const __VLS_48 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    value: "completed",
}));
const __VLS_50 = __VLS_49({
    value: "completed",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
var __VLS_51;
const __VLS_52 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    value: "failed",
}));
const __VLS_54 = __VLS_53({
    value: "failed",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
var __VLS_55;
var __VLS_35;
const __VLS_56 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    value: (__VLS_ctx.departmentFilter),
    placeholder: "科室筛选",
    ...{ style: {} },
    allowClear: true,
}));
const __VLS_58 = __VLS_57({
    value: (__VLS_ctx.departmentFilter),
    placeholder: "科室筛选",
    ...{ style: {} },
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    value: "",
}));
const __VLS_62 = __VLS_61({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
var __VLS_63;
for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
    const __VLS_64 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        key: (dept),
        value: (dept),
    }));
    const __VLS_66 = __VLS_65({
        key: (dept),
        value: (dept),
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    (dept);
    var __VLS_67;
}
var __VLS_59;
/** @type {[typeof BatchOperationsComponent, ]} */ ;
// @ts-ignore
const __VLS_68 = __VLS_asFunctionalComponent(BatchOperationsComponent_vue_1.default, new BatchOperationsComponent_vue_1.default({
    ...{ 'onSelectAll': {} },
    ...{ 'onExecuteAction': {} },
    selectedItems: (__VLS_ctx.selectedRecords),
    totalItems: (__VLS_ctx.filteredRecords.length),
    actions: (__VLS_ctx.batchActions),
    isMobile: (__VLS_ctx.isMobile),
}));
const __VLS_69 = __VLS_68({
    ...{ 'onSelectAll': {} },
    ...{ 'onExecuteAction': {} },
    selectedItems: (__VLS_ctx.selectedRecords),
    totalItems: (__VLS_ctx.filteredRecords.length),
    actions: (__VLS_ctx.batchActions),
    isMobile: (__VLS_ctx.isMobile),
}, ...__VLS_functionalComponentArgsRest(__VLS_68));
let __VLS_71;
let __VLS_72;
let __VLS_73;
const __VLS_74 = {
    onSelectAll: (__VLS_ctx.handleSelectAll)
};
const __VLS_75 = {
    onExecuteAction: (__VLS_ctx.handleBatchAction)
};
var __VLS_70;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "records-container" },
});
/** @type {[typeof VirtualListComponent, typeof VirtualListComponent, ]} */ ;
// @ts-ignore
const __VLS_76 = __VLS_asFunctionalComponent(VirtualListComponent_vue_1.default, new VirtualListComponent_vue_1.default({
    items: (__VLS_ctx.filteredRecords),
    itemHeight: (120),
    containerHeight: (600),
    loading: (__VLS_ctx.loading),
    hasMore: (__VLS_ctx.hasMore),
    loadMore: (__VLS_ctx.loadMore),
    keyField: "id",
}));
const __VLS_77 = __VLS_76({
    items: (__VLS_ctx.filteredRecords),
    itemHeight: (120),
    containerHeight: (600),
    loading: (__VLS_ctx.loading),
    hasMore: (__VLS_ctx.hasMore),
    loadMore: (__VLS_ctx.loadMore),
    keyField: "id",
}, ...__VLS_functionalComponentArgsRest(__VLS_76));
__VLS_78.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_78.slots;
    const { item: record, index } = __VLS_getSlotParam(__VLS_thisSlot);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-item" },
        ...{ class: ({ 'record-selected': __VLS_ctx.isSelected(record) }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-checkbox" },
    });
    const __VLS_79 = {}.ACheckbox;
    /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
    // @ts-ignore
    const __VLS_80 = __VLS_asFunctionalComponent(__VLS_79, new __VLS_79({
        ...{ 'onChange': {} },
        checked: (__VLS_ctx.isSelected(record)),
    }));
    const __VLS_81 = __VLS_80({
        ...{ 'onChange': {} },
        checked: (__VLS_ctx.isSelected(record)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_80));
    let __VLS_83;
    let __VLS_84;
    let __VLS_85;
    const __VLS_86 = {
        onChange: ((e) => __VLS_ctx.handleRecordSelect(record, e.target.checked))
    };
    var __VLS_82;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-avatar" },
    });
    /** @type {[typeof LazyImageComponent, ]} */ ;
    // @ts-ignore
    const __VLS_87 = __VLS_asFunctionalComponent(LazyImageComponent_vue_1.default, new LazyImageComponent_vue_1.default({
        src: (__VLS_ctx.getPatientAvatar(record)),
        width: (60),
        height: (60),
        alt: (record.patient_name),
        fit: "cover",
        showSkeleton: (true),
        fallback: (__VLS_ctx.getDefaultAvatar(record.patient_gender)),
    }));
    const __VLS_88 = __VLS_87({
        src: (__VLS_ctx.getPatientAvatar(record)),
        width: (60),
        height: (60),
        alt: (record.patient_name),
        fit: "cover",
        showSkeleton: (true),
        fallback: (__VLS_ctx.getDefaultAvatar(record.patient_gender)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_87));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    (record.patient_name);
    const __VLS_90 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
        color: (__VLS_ctx.getGenderColor(record.patient_gender)),
    }));
    const __VLS_92 = __VLS_91({
        color: (__VLS_ctx.getGenderColor(record.patient_gender)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    __VLS_93.slots.default;
    (record.patient_gender);
    var __VLS_93;
    const __VLS_94 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({}));
    const __VLS_96 = __VLS_95({}, ...__VLS_functionalComponentArgsRest(__VLS_95));
    __VLS_97.slots.default;
    (record.patient_age);
    var __VLS_97;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-status" },
    });
    const __VLS_98 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
        color: (__VLS_ctx.getStatusColor(record.status)),
    }));
    const __VLS_100 = __VLS_99({
        color: (__VLS_ctx.getStatusColor(record.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_99));
    __VLS_101.slots.default;
    (__VLS_ctx.getStatusText(record.status));
    var __VLS_101;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "info-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "info-value" },
    });
    (record.department);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "info-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "info-value" },
    });
    (__VLS_ctx.formatDate(record.admission_date));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "info-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "info-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "info-value" },
    });
    (record.record_type);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-footer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-time" },
    });
    (__VLS_ctx.formatDateTime(record.created_at));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "record-actions" },
    });
    const __VLS_102 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
        size: "small",
    }));
    const __VLS_104 = __VLS_103({
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_103));
    __VLS_105.slots.default;
    const __VLS_106 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_108 = __VLS_107({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_107));
    let __VLS_110;
    let __VLS_111;
    let __VLS_112;
    const __VLS_113 = {
        onClick: (...[$event]) => {
            __VLS_ctx.viewRecord(record);
        }
    };
    __VLS_109.slots.default;
    var __VLS_109;
    const __VLS_114 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
        ...{ 'onClick': {} },
        size: "small",
        type: "primary",
        loading: (__VLS_ctx.analyzingRecords.includes(record.id)),
        disabled: (record.status === 'analyzing'),
    }));
    const __VLS_116 = __VLS_115({
        ...{ 'onClick': {} },
        size: "small",
        type: "primary",
        loading: (__VLS_ctx.analyzingRecords.includes(record.id)),
        disabled: (record.status === 'analyzing'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_115));
    let __VLS_118;
    let __VLS_119;
    let __VLS_120;
    const __VLS_121 = {
        onClick: (...[$event]) => {
            __VLS_ctx.analyzeRecord(record);
        }
    };
    __VLS_117.slots.default;
    (record.status === 'completed' ? '重新分析' : '分析');
    var __VLS_117;
    const __VLS_122 = {}.ADropdown;
    /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
    // @ts-ignore
    const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({}));
    const __VLS_124 = __VLS_123({}, ...__VLS_functionalComponentArgsRest(__VLS_123));
    __VLS_125.slots.default;
    const __VLS_126 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
        size: "small",
    }));
    const __VLS_128 = __VLS_127({
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    __VLS_129.slots.default;
    const __VLS_130 = {}.DownOutlined;
    /** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_131 = __VLS_asFunctionalComponent(__VLS_130, new __VLS_130({}));
    const __VLS_132 = __VLS_131({}, ...__VLS_functionalComponentArgsRest(__VLS_131));
    var __VLS_129;
    {
        const { overlay: __VLS_thisSlot } = __VLS_125.slots;
        const __VLS_134 = {}.AMenu;
        /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
        // @ts-ignore
        const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
            ...{ 'onClick': {} },
        }));
        const __VLS_136 = __VLS_135({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_135));
        let __VLS_138;
        let __VLS_139;
        let __VLS_140;
        const __VLS_141 = { onClick: (({ key   }) => __VLS_ctx.handleRecordAction(key, record))
        };
        __VLS_137.slots.default;
        const __VLS_142 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({
            key: "edit",
        }));
        const __VLS_144 = __VLS_143({
            key: "edit",
        }, ...__VLS_functionalComponentArgsRest(__VLS_143));
        __VLS_145.slots.default;
        var __VLS_145;
        const __VLS_146 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_147 = __VLS_asFunctionalComponent(__VLS_146, new __VLS_146({
            key: "download",
        }));
        const __VLS_148 = __VLS_147({
            key: "download",
        }, ...__VLS_functionalComponentArgsRest(__VLS_147));
        __VLS_149.slots.default;
        var __VLS_149;
        const __VLS_150 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_151 = __VLS_asFunctionalComponent(__VLS_150, new __VLS_150({
            key: "history",
        }));
        const __VLS_152 = __VLS_151({
            key: "history",
        }, ...__VLS_functionalComponentArgsRest(__VLS_151));
        __VLS_153.slots.default;
        var __VLS_153;
        const __VLS_154 = {}.AMenuDivider;
        /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
        // @ts-ignore
        const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({}));
        const __VLS_156 = __VLS_155({}, ...__VLS_functionalComponentArgsRest(__VLS_155));
        const __VLS_158 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_159 = __VLS_asFunctionalComponent(__VLS_158, new __VLS_158({
            key: "delete",
            danger: true,
        }));
        const __VLS_160 = __VLS_159({
            key: "delete",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_159));
        __VLS_161.slots.default;
        var __VLS_161;
        var __VLS_137;
    }
    var __VLS_125;
    var __VLS_105;
}
var __VLS_78;
const __VLS_162 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_163 = __VLS_asFunctionalComponent(__VLS_162, new __VLS_162({
    open: (__VLS_ctx.showUploadModal),
    title: "上传病案",
    width: (800),
    footer: (null),
    destroyOnClose: (true),
}));
const __VLS_164 = __VLS_163({
    open: (__VLS_ctx.showUploadModal),
    title: "上传病案",
    width: (800),
    footer: (null),
    destroyOnClose: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_163));
__VLS_165.slots.default;
/** @type {[typeof RecordUploadFormComponent, ]} */ ;
// @ts-ignore
const __VLS_166 = __VLS_asFunctionalComponent(RecordUploadFormComponent_vue_1.default, new RecordUploadFormComponent_vue_1.default({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    loading: (__VLS_ctx.uploading),
}));
const __VLS_167 = __VLS_166({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    loading: (__VLS_ctx.uploading),
}, ...__VLS_functionalComponentArgsRest(__VLS_166));
let __VLS_169;
let __VLS_170;
let __VLS_171;
const __VLS_172 = {
    onSubmit: (__VLS_ctx.handleRecordSubmit)
};
const __VLS_173 = {
    onCancel: (...[$event]) => {
        __VLS_ctx.showUploadModal = false;
    }
};
var __VLS_168;
var __VLS_165;
const __VLS_174 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_175 = __VLS_asFunctionalComponent(__VLS_174, new __VLS_174({
    open: (__VLS_ctx.showAnalysisModal),
    title: "质控分析结果",
    width: (1000),
    footer: (null),
    destroyOnClose: (true),
}));
const __VLS_176 = __VLS_175({
    open: (__VLS_ctx.showAnalysisModal),
    title: "质控分析结果",
    width: (1000),
    footer: (null),
    destroyOnClose: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_175));
__VLS_177.slots.default;
if (__VLS_ctx.currentAnalysisResult) {
    /** @type {[typeof QCResultDisplay, ]} */ ;
    // @ts-ignore
    const __VLS_178 = __VLS_asFunctionalComponent(QCResultDisplay_vue_1.default, new QCResultDisplay_vue_1.default({
        result: (__VLS_ctx.currentAnalysisResult),
        showDetails: (true),
    }));
    const __VLS_179 = __VLS_178({
        result: (__VLS_ctx.currentAnalysisResult),
        showDetails: (true),
    }, ...__VLS_functionalComponentArgsRest(__VLS_178));
}
var __VLS_177;
/** @type {__VLS_StyleScopedClasses['records-view-optimized']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['records-container']} */ ;
/** @type {__VLS_StyleScopedClasses['record-item']} */ ;
/** @type {__VLS_StyleScopedClasses['record-selected']} */ ;
/** @type {__VLS_StyleScopedClasses['record-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['record-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['record-content']} */ ;
/** @type {__VLS_StyleScopedClasses['record-header']} */ ;
/** @type {__VLS_StyleScopedClasses['record-title']} */ ;
/** @type {__VLS_StyleScopedClasses['record-status']} */ ;
/** @type {__VLS_StyleScopedClasses['record-info']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-label']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-label']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-label']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['record-footer']} */ ;
/** @type {__VLS_StyleScopedClasses['record-time']} */ ;
/** @type {__VLS_StyleScopedClasses['record-actions']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            PlusOutlined: icons_vue_1.PlusOutlined,
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            VirtualListComponent: VirtualListComponent_vue_1.default,
            LazyImageComponent: LazyImageComponent_vue_1.default,
            BatchOperationsComponent: BatchOperationsComponent_vue_1.default,
            RecordUploadFormComponent: RecordUploadFormComponent_vue_1.default,
            QCResultDisplay: QCResultDisplay_vue_1.default,
            formatDate: date_1.formatDate,
            formatDateTime: date_1.formatDateTime,
            isMobile: isMobile,
            selectedRecords: selectedRecords,
            loading: loading,
            uploading: uploading,
            batchAnalyzing: batchAnalyzing,
            analyzingRecords: analyzingRecords,
            hasMore: hasMore,
            searchKeyword: searchKeyword,
            statusFilter: statusFilter,
            departmentFilter: departmentFilter,
            showUploadModal: showUploadModal,
            showAnalysisModal: showAnalysisModal,
            currentAnalysisResult: currentAnalysisResult,
            stats: stats,
            departments: departments,
            filteredRecords: filteredRecords,
            batchActions: batchActions,
            loadMore: loadMore,
            handleSearch: handleSearch,
            handleRecordSubmit: handleRecordSubmit,
            analyzeRecord: analyzeRecord,
            handleBatchAnalysis: handleBatchAnalysis,
            handleRecordSelect: handleRecordSelect,
            handleSelectAll: handleSelectAll,
            handleBatchAction: handleBatchAction,
            viewRecord: viewRecord,
            handleRecordAction: handleRecordAction,
            isSelected: isSelected,
            getPatientAvatar: getPatientAvatar,
            getDefaultAvatar: getDefaultAvatar,
            getGenderColor: getGenderColor,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
