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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const RecordUploadForm_vue_1 = __importDefault(require("../../components/forms/RecordUploadForm.vue"));
const RecordDetailPanel_vue_1 = __importDefault(require("../../components/medical/RecordDetailPanel.vue"));
const AnalysisResultPanel_vue_1 = __importDefault(require("../../components/medical/AnalysisResultPanel.vue"));
const PageHeader_vue_1 = __importDefault(require("../../components/common/PageHeader.vue"));
const LoadingSpinner_vue_1 = __importDefault(require("../../components/common/LoadingSpinner.vue"));
const EmptyState_vue_1 = __importDefault(require("../../components/common/EmptyState.vue"));
import medical_records_1 from '../../api/medical-records';
import qc_analysis_api_1 from '../../api/qc-analysis-api';
// 响应式数据
const records = (0, vue_1.ref)(: any[]);
const isLoading = (0, vue_1.ref)(false);
const isAnalyzing = (0, vue_1.ref)(false);
const statusFilter = (0, vue_1.ref)('');
const retryingId = (0, vue_1.ref)(null);
// 抽屉状态
const detailDrawerVisible = (0, vue_1.ref)(false);
const analysisDrawerVisible = (0, vue_1.ref)(false);
const selectedRecord = (0, vue_1.ref)(null);
// 页面头部配置
const headerActions = (0, vue_1.computed)(() => [
    {
        key: 'upload',
        text: '上传病案',
        type: 'primary',
        icon: icons_vue_1.PlusOutlined
    },
    {
        key: 'export',
        text: '导出数据',
        icon: icons_vue_1.DownloadOutlined
    },
    {
        key: 'statistics',
        text: '统计报表',
        icon: icons_vue_1.BarChartOutlined
    }
]);
const headerStats = (0, vue_1.computed)(() => [
    {
        key: 'total',
        label: '总记录数',
        value: records.value.length,
        icon: icons_vue_1.FileTextOutlined,
        color: '#1890ff'
    },
    {
        key: 'pending',
        label: '待分析',
        value: records.value.filter(r => r.status === 'pending').length,
        icon: icons_vue_1.FileTextOutlined,
        color: '#faad14'
    },
    {
        key: 'analyzing',
        label: '分析中',
        value: records.value.filter(r => r.status === 'analyzing').length,
        icon: icons_vue_1.FileTextOutlined,
        color: '#13c2c2'
    },
    {
        key: 'completed',
        label: '已完成',
        value: records.value.filter(r => r.status === 'completed').length,
        icon: icons_vue_1.FileTextOutlined,
        color: '#52c41a'
    }
]);
// 表格列定义
const tableColumns = [
    {
        title: '患者信息',
        key: 'patient',
        width: 150,
    },
    {
        title: '科室',
        dataIndex: 'department',
        key: 'department',
        width: 100,
    },
    { title: '记录类型',
        dataIndex: 'record_type',
        key: 'record_type',
        width: 100,
        customRender: ({ text  }) => {
            const typeMap = {
                'inpatient': '住院',
                'outpatient': '门诊',
                'emergency': '急诊'
            };
            return typeMap[text] || text;
        }
    },
    {
        title: '入院日期',
        dataIndex: 'admission_date',
        key: 'admission_date',
        width: 120,
    },
    {
        title: '状态',
        key: 'status',
        width: 100,
    },
    {
        title: '质控评分',
        key: 'qc_score',
        width: 150,
    },
    { title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 150,
        customRender: ({ text  }) => {
            return new Date(text).toLocaleString();
        }
    },
    {
        title: '操作',
        key: 'actions',
        width: 200,
        fixed: 'right'
    }
];
// 分页配置
const paginationConfig = {
    pageSize: 10,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total) => `共 ${total} 条记录`
};
// 计算属性
const filteredRecords = (0, vue_1.computed)(() => {
    if (!statusFilter.value)
        return records.value;
    return records.value.filter(record => record.status === statusFilter.value);
});
// 状态相关方法
const getStatusColor = (status) => {
    const colorMap = {
        'pending': 'orange',
        'analyzing': 'blue',
        'completed': 'green',
        'failed': 'red'
    };
    return colorMap[status] || 'default';
};
const getStatusText = (status) => {
    const textMap = {
        'pending': '待分析',
        'analyzing': '分析中',
        'completed': '已完成',
        'failed': '分析失败'
    };
    return textMap[status] || status;
};
const getScoreColor = (score) => {
    if (score >= 90)
        return '#52c41a';
    if (score >= 80)
        return '#faad14';
    if (score >= 70)
        return '#fa8c16';
    return '#f5222d';
};
const getGradeColor = (grade) => {
    const gradeColorMap = {
        'A': 'green',
        'B': 'orange',
        'C': 'red'
    };
    return gradeColorMap[grade] || 'default';
};
// 页面头部操作处理
const handleHeaderAction = (action) => {
    switch (action.key) {
        case 'upload':
            scrollToUpload();
            break;
        case 'export':
            // TODO: 导出功能
            ant_design_vue_1.message.info('导出功能开发中');
            break;
        case 'statistics':
            // TODO: 跳转到统计页面
            ant_design_vue_1.message.info('统计功能开发中');
            break;
    }
};
// 事件处理方法
const handleRecordSubmit = async (data) => {
    try {
        isAnalyzing.value = true;
        // 1. 创建医疗记录
        const createResult = await (0, medical_records_1.createMedicalRecord)(data);
        if (createResult.error || !createResult.data) {
            throw new Error(createResult.error?.message || '创建记录失败');
        }
        const newRecord = createResult.data;
        records.value.unshift(newRecord);
        ant_design_vue_1.message.success('病案上传成功，正在进行质控分析...');
        // 2. 异步进行AI分析
        (0, qc_analysis_api_1.analyzeRecord)(newRecord.id).then(analysisResult => {
            if (analysisResult.error) {
                console.error('分析失败:', analysisResult.error);
                ant_design_vue_1.message.error('质控分析失败');
                // 更新记录状态为失败
                const record = records.value.find(r => r.id === newRecord.id);
                if (record) {
                    record.status = 'failed';
                }
            }
            else {
                ant_design_vue_1.message.success('质控分析完成');
                // 更新记录信息
                const record = records.value.find(r => r.id === newRecord.id);
                if (record && analysisResult.data) {
                    record.status = 'completed';
                    record.qc_score = analysisResult.data.overallScore;
                    record.qc_grade = analysisResult.data.grade;
                    record.updated_at = new Date().toISOString();
                }
            }
        }).catch(error => {
            console.error('分析异常:', error);
            ant_design_vue_1.message.error('质控分析异常');
        });
    }
    catch (error) {
        console.error('提交失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '病案提交失败，请重试');
    }
    finally {
        isAnalyzing.value = false;
    }
};
const handleUploadCancel = () => {
    console.log('取消上传');
};
const viewRecord = (record) => {
    selectedRecord.value = record;
    detailDrawerVisible.value = true;
};
const viewAnalysis = (record) => {
    selectedRecord.value = record;
    analysisDrawerVisible.value = true;
};
const retryAnalysis = async (record) => {
    try {
        retryingId.value = record.id;
        record.status = 'analyzing';
        // 调用重新分析API
        const analysisResult = await (0, qc_analysis_api_1.analyzeRecord)(record.id);
        if (analysisResult.error) {
            throw new Error(analysisResult.error.message);
        }
        if (analysisResult.data) {
            record.status = 'completed';
            record.qc_score = analysisResult.data.overallScore;
            record.qc_grade = analysisResult.data.grade;
            record.updated_at = new Date().toISOString();
            ant_design_vue_1.message.success('重新分析完成');
        }
    }
    catch (error) {
        console.error('重新分析失败:', error);
        record.status = 'failed';
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '重新分析失败');
    }
    finally {
        retryingId.value = null;
    }
};
const deleteRecord = async (recordId) => {
    try {
        const result = await (0, medical_records_1.deleteMedicalRecord)(recordId);
        if (result.error) {
            throw new Error(result.error.message);
        }
        // 从列表中移除
        records.value = records.value.filter(r => r.id !== recordId);
        ant_design_vue_1.message.success('删除成功');
    }
    catch (error) {
        console.error('删除失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '删除失败');
    }
};
const refreshRecords = async () => {
    try {
        isLoading.value = true;
        const result = await (0, medical_records_1.getMedicalRecords)({
            limit: 50,
            offset: 0
        });
        if (result.error) {
            throw new Error(result.error.message);
        }
        records.value = result.data || [];
        ant_design_vue_1.message.success('刷新成功');
    }
    catch (error) {
        console.error('刷新失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '刷新失败');
    }
    finally {
        isLoading.value = false;
    }
};
const scrollToUpload = () => {
    // 滚动到页面顶部的上传表单
    console.log('滚动到上传表单');
};
// 组件挂载时获取数据
(0, vue_1.onMounted)(() => {
    refreshRecords();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['medical-records-table']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "records-view min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100" },
});
/** @type {[typeof PageHeader, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(PageHeader_vue_1.default, new PageHeader_vue_1.default({
    ...{ 'onAction': {} },
    title: "病案管理",
    subtitle: "上传、管理和分析医疗病案记录",
    icon: (__VLS_ctx.FileTextOutlined),
    actions: (__VLS_ctx.headerActions),
    stats: (__VLS_ctx.headerStats),
}));
const __VLS_1 = __VLS_0({
    ...{ 'onAction': {} },
    title: "病案管理",
    subtitle: "上传、管理和分析医疗病案记录",
    icon: (__VLS_ctx.FileTextOutlined),
    actions: (__VLS_ctx.headerActions),
    stats: (__VLS_ctx.headerStats),
}, ...__VLS_functionalComponentArgsRest(__VLS_0));
let __VLS_3;
let __VLS_4;
let __VLS_5;
const __VLS_6 = {
    onAction: (__VLS_ctx.handleHeaderAction)
};
var __VLS_2;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-7xl mx-auto px-6 pb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-8" },
});
const __VLS_7 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent(__VLS_7, new __VLS_7({
    title: "上传病案",
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    bordered: (false),
}));
const __VLS_9 = __VLS_8({
    title: "上传病案",
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
__VLS_10.slots.default;
/** @type {[typeof RecordUploadForm, ]} */ ;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent(RecordUploadForm_vue_1.default, new RecordUploadForm_vue_1.default({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    loading: (__VLS_ctx.isAnalyzing),
}));
const __VLS_12 = __VLS_11({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    loading: (__VLS_ctx.isAnalyzing),
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
let __VLS_14;
let __VLS_15;
let __VLS_16;
const __VLS_17 = {
    onSubmit: (__VLS_ctx.handleRecordSubmit)
};
const __VLS_18 = {
    onCancel: (__VLS_ctx.handleUploadCancel)
};
var __VLS_13;
var __VLS_10;
const __VLS_19 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_20 = __VLS_asFunctionalComponent(__VLS_19, new __VLS_19({
    title: "病案记录",
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    bordered: (false),
}));
const __VLS_21 = __VLS_20({
    title: "病案记录",
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_20));
__VLS_22.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_22.slots;
    const __VLS_23 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_24 = __VLS_asFunctionalComponent(__VLS_23, new __VLS_23({}));
    const __VLS_25 = __VLS_24({}, ...__VLS_functionalComponentArgsRest(__VLS_24));
    __VLS_26.slots.default;
    const __VLS_27 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent(__VLS_27, new __VLS_27({
        value: (__VLS_ctx.statusFilter),
        placeholder: "筛选状态",
        ...{ style: {} },
        allowClear: true,
    }));
    const __VLS_29 = __VLS_28({
        value: (__VLS_ctx.statusFilter),
        placeholder: "筛选状态",
        ...{ style: {} },
        allowClear: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
    __VLS_30.slots.default;
    const __VLS_31 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_32 = __VLS_asFunctionalComponent(__VLS_31, new __VLS_31({
        value: "",
    }));
    const __VLS_33 = __VLS_32({
        value: "",
    }, ...__VLS_functionalComponentArgsRest(__VLS_32));
    __VLS_34.slots.default;
    var __VLS_34;
    const __VLS_35 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_36 = __VLS_asFunctionalComponent(__VLS_35, new __VLS_35({
        value: "pending",
    }));
    const __VLS_37 = __VLS_36({
        value: "pending",
    }, ...__VLS_functionalComponentArgsRest(__VLS_36));
    __VLS_38.slots.default;
    var __VLS_38;
    const __VLS_39 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_40 = __VLS_asFunctionalComponent(__VLS_39, new __VLS_39({
        value: "analyzing",
    }));
    const __VLS_41 = __VLS_40({
        value: "analyzing",
    }, ...__VLS_functionalComponentArgsRest(__VLS_40));
    __VLS_42.slots.default;
    var __VLS_42;
    const __VLS_43 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_44 = __VLS_asFunctionalComponent(__VLS_43, new __VLS_43({
        value: "completed",
    }));
    const __VLS_45 = __VLS_44({
        value: "completed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_44));
    __VLS_46.slots.default;
    var __VLS_46;
    const __VLS_47 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_48 = __VLS_asFunctionalComponent(__VLS_47, new __VLS_47({
        value: "failed",
    }));
    const __VLS_49 = __VLS_48({
        value: "failed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_48));
    __VLS_50.slots.default;
    var __VLS_50;
    var __VLS_30;
    const __VLS_51 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_52 = __VLS_asFunctionalComponent(__VLS_51, new __VLS_51({
        ...{ 'onClick': {} },
        type: "primary",
        ghost: true,
        loading: (__VLS_ctx.isLoading),
    }));
    const __VLS_53 = __VLS_52({
        ...{ 'onClick': {} },
        type: "primary",
        ghost: true,
        loading: (__VLS_ctx.isLoading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_52));
    let __VLS_55;
    let __VLS_56;
    let __VLS_57;
    const __VLS_58 = {
        onClick: (__VLS_ctx.refreshRecords)
    };
    __VLS_54.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_54.slots;
        const __VLS_59 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_60 = __VLS_asFunctionalComponent(__VLS_59, new __VLS_59({}));
        const __VLS_61 = __VLS_60({}, ...__VLS_functionalComponentArgsRest(__VLS_60));
    }
    var __VLS_54;
    var __VLS_26;
}
if (__VLS_ctx.isLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "py-8" },
    });
    /** @type {[typeof LoadingSpinner, ]} */ ;
    // @ts-ignore
    const __VLS_63 = __VLS_asFunctionalComponent(LoadingSpinner_vue_1.default, new LoadingSpinner_vue_1.default({
        type: "medical",
        size: "large",
        text: "正在加载病案记录...",
    }));
    const __VLS_64 = __VLS_63({
        type: "medical",
        size: "large",
        text: "正在加载病案记录...",
    }, ...__VLS_functionalComponentArgsRest(__VLS_63));
}
else if (__VLS_ctx.records.length > 0) {
    const __VLS_66 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
        columns: (__VLS_ctx.tableColumns),
        dataSource: (__VLS_ctx.filteredRecords),
        pagination: (__VLS_ctx.paginationConfig),
        rowKey: "id",
        ...{ class: "medical-records-table" },
    }));
    const __VLS_68 = __VLS_67({
        columns: (__VLS_ctx.tableColumns),
        dataSource: (__VLS_ctx.filteredRecords),
        pagination: (__VLS_ctx.paginationConfig),
        rowKey: "id",
        ...{ class: "medical-records-table" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_67));
    __VLS_69.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_69.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'patient') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "patient-info" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "font-medium text-gray-900" },
            });
            (record.patient_name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-sm text-gray-500" },
            });
            (record.patient_age);
            (record.patient_gender === 'M' ? '男' : record.patient_gender === 'F' ? '女' : '未知');
        }
        else if (column.key === 'status') {
            const __VLS_70 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
                color: (__VLS_ctx.getStatusColor(record.status)),
                ...{ class: "status-tag" },
            }));
            const __VLS_72 = __VLS_71({
                color: (__VLS_ctx.getStatusColor(record.status)),
                ...{ class: "status-tag" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_71));
            __VLS_73.slots.default;
            (__VLS_ctx.getStatusText(record.status));
            var __VLS_73;
        }
        else if (column.key === 'qc_score') {
            if (record.qc_score !== null && record.qc_score !== undefined) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "score-display" },
                });
                const __VLS_74 = {}.AProgress;
                /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
                // @ts-ignore
                const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
                    percent: (record.qc_score),
                    strokeColor: (__VLS_ctx.getScoreColor(record.qc_score)),
                    size: "small",
                    showInfo: (false),
                    ...{ class: "mb-1" },
                }));
                const __VLS_76 = __VLS_75({
                    percent: (record.qc_score),
                    strokeColor: (__VLS_ctx.getScoreColor(record.qc_score)),
                    size: "small",
                    showInfo: (false),
                    ...{ class: "mb-1" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_75));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "text-xs text-center" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "font-medium" },
                });
                (record.qc_score);
                if (record.qc_grade) {
                    const __VLS_78 = {}.ATag;
                    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                    // @ts-ignore
                    const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({
                        color: (__VLS_ctx.getGradeColor(record.qc_grade)),
                        size: "small",
                        ...{ class: "ml-1" },
                    }));
                    const __VLS_80 = __VLS_79({
                        color: (__VLS_ctx.getGradeColor(record.qc_grade)),
                        size: "small",
                        ...{ class: "ml-1" },
                    }, ...__VLS_functionalComponentArgsRest(__VLS_79));
                    __VLS_81.slots.default;
                    (record.qc_grade);
                    var __VLS_81;
                }
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "text-gray-400" },
                });
            }
        }
        else if (column.key === 'actions') {
            const __VLS_82 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
                size: "small",
            }));
            const __VLS_84 = __VLS_83({
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_83));
            __VLS_85.slots.default;
            const __VLS_86 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
                ...{ class: "action-btn" },
            }));
            const __VLS_88 = __VLS_87({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
                ...{ class: "action-btn" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_87));
            let __VLS_90;
            let __VLS_91;
            let __VLS_92;
            const __VLS_93 = {
                onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!(__VLS_ctx.records.length > 0))
                        return;
                    if (!!(column.key === 'patient'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'qc_score'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.viewRecord(record);
                }
            };
            __VLS_89.slots.default;
            var __VLS_89;
            if (record.status === 'completed') {
                const __VLS_94 = {}.AButton;
                /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
                // @ts-ignore
                const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
                    ...{ 'onClick': {} },
                    type: "link",
                    size: "small",
                    ...{ class: "action-btn" },
                }));
                const __VLS_96 = __VLS_95({
                    ...{ 'onClick': {} },
                    type: "link",
                    size: "small",
                    ...{ class: "action-btn" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_95));
                let __VLS_98;
                let __VLS_99;
                let __VLS_100;
                const __VLS_101 = {
                    onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.isLoading))
                            return;
                        if (!(__VLS_ctx.records.length > 0))
                            return;
                        if (!!(column.key === 'patient'))
                            return;
                        if (!!(column.key === 'status'))
                            return;
                        if (!!(column.key === 'qc_score'))
                            return;
                        if (!(column.key === 'actions'))
                            return;
                        if (!(record.status === 'completed'))
                            return;
                        __VLS_ctx.viewAnalysis(record);
                    }
                };
                __VLS_97.slots.default;
                var __VLS_97;
            }
            if (record.status === 'failed') {
                const __VLS_102 = {}.AButton;
                /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
                // @ts-ignore
                const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({
                    ...{ 'onClick': {} },
                    type: "link",
                    size: "small",
                    loading: (__VLS_ctx.retryingId === record.id),
                    ...{ class: "action-btn" },
                }));
                const __VLS_104 = __VLS_103({
                    ...{ 'onClick': {} },
                    type: "link",
                    size: "small",
                    loading: (__VLS_ctx.retryingId === record.id),
                    ...{ class: "action-btn" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_103));
                let __VLS_106;
                let __VLS_107;
                let __VLS_108;
                const __VLS_109 = {
                    onClick: (...[$event]) => {
                        if (!!(__VLS_ctx.isLoading))
                            return;
                        if (!(__VLS_ctx.records.length > 0))
                            return;
                        if (!!(column.key === 'patient'))
                            return;
                        if (!!(column.key === 'status'))
                            return;
                        if (!!(column.key === 'qc_score'))
                            return;
                        if (!(column.key === 'actions'))
                            return;
                        if (!(record.status === 'failed'))
                            return;
                        __VLS_ctx.retryAnalysis(record);
                    }
                };
                __VLS_105.slots.default;
                var __VLS_105;
            }
            const __VLS_110 = {}.APopconfirm;
            /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
            // @ts-ignore
            const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
                ...{ 'onConfirm': {} },
                title: "确定要删除这条记录吗？",
                okText: "确定",
                cancelText: "取消",
            }));
            const __VLS_112 = __VLS_111({
                ...{ 'onConfirm': {} },
                title: "确定要删除这条记录吗？",
                okText: "确定",
                cancelText: "取消",
            }, ...__VLS_functionalComponentArgsRest(__VLS_111));
            let __VLS_114;
            let __VLS_115;
            let __VLS_116;
            const __VLS_117 = {
                onConfirm: (...[$event]) => {
                    if (!!(__VLS_ctx.isLoading))
                        return;
                    if (!(__VLS_ctx.records.length > 0))
                        return;
                    if (!!(column.key === 'patient'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'qc_score'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.deleteRecord(record.id);
                }
            };
            __VLS_113.slots.default;
            const __VLS_118 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({
                type: "link",
                size: "small",
                danger: true,
                ...{ class: "action-btn" },
            }));
            const __VLS_120 = __VLS_119({
                type: "link",
                size: "small",
                danger: true,
                ...{ class: "action-btn" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_119));
            __VLS_121.slots.default;
            var __VLS_121;
            var __VLS_113;
            var __VLS_85;
        }
    }
    var __VLS_69;
}
else {
    /** @type {[typeof EmptyState, ]} */ ;
    // @ts-ignore
    const __VLS_122 = __VLS_asFunctionalComponent(EmptyState_vue_1.default, new EmptyState_vue_1.default({
        type: "empty",
        title: "暂无病案记录",
        description: "还没有上传任何病案记录，立即开始上传吧！",
        actions: ([
            {
                key: 'upload',
                text: '立即上传病案',
                type: 'primary',
                icon: __VLS_ctx.UploadOutlined,
                onClick: __VLS_ctx.scrollToUpload
            }
        ]),
    }));
    const __VLS_123 = __VLS_122({
        type: "empty",
        title: "暂无病案记录",
        description: "还没有上传任何病案记录，立即开始上传吧！",
        actions: ([
            {
                key: 'upload',
                text: '立即上传病案',
                type: 'primary',
                icon: __VLS_ctx.UploadOutlined,
                onClick: __VLS_ctx.scrollToUpload
            }
        ]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_122));
}
var __VLS_22;
const __VLS_125 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({
    open: (__VLS_ctx.detailDrawerVisible),
    title: "病案详情",
    placement: "right",
    width: (800),
    ...{ class: "detail-drawer" },
}));
const __VLS_127 = __VLS_126({
    open: (__VLS_ctx.detailDrawerVisible),
    title: "病案详情",
    placement: "right",
    width: (800),
    ...{ class: "detail-drawer" },
}, ...__VLS_functionalComponentArgsRest(__VLS_126));
__VLS_128.slots.default;
if (__VLS_ctx.selectedRecord) {
    /** @type {[typeof RecordDetailPanel, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(RecordDetailPanel_vue_1.default, new RecordDetailPanel_vue_1.default({
        ...{ 'onClose': {} },
        record: (__VLS_ctx.selectedRecord),
    }));
    const __VLS_130 = __VLS_129({
        ...{ 'onClose': {} },
        record: (__VLS_ctx.selectedRecord),
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    let __VLS_132;
    let __VLS_133;
    let __VLS_134;
    const __VLS_135 = {
        onClose: (...[$event]) => {
            if (!(__VLS_ctx.selectedRecord))
                return;
            __VLS_ctx.detailDrawerVisible = false;
        }
    };
    var __VLS_131;
}
var __VLS_128;
const __VLS_136 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    open: (__VLS_ctx.analysisDrawerVisible),
    title: "质控分析结果",
    placement: "right",
    width: (900),
    ...{ class: "analysis-drawer" },
}));
const __VLS_138 = __VLS_137({
    open: (__VLS_ctx.analysisDrawerVisible),
    title: "质控分析结果",
    placement: "right",
    width: (900),
    ...{ class: "analysis-drawer" },
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
__VLS_139.slots.default;
if (__VLS_ctx.selectedRecord) {
    /** @type {[typeof AnalysisResultPanel, ]} */ ;
    // @ts-ignore
    const __VLS_140 = __VLS_asFunctionalComponent(AnalysisResultPanel_vue_1.default, new AnalysisResultPanel_vue_1.default({
        ...{ 'onClose': {} },
        record: (__VLS_ctx.selectedRecord),
    }));
    const __VLS_141 = __VLS_140({
        ...{ 'onClose': {} },
        record: (__VLS_ctx.selectedRecord),
    }, ...__VLS_functionalComponentArgsRest(__VLS_140));
    let __VLS_143;
    let __VLS_144;
    let __VLS_145;
    const __VLS_146 = {
        onClose: (...[$event]) => {
            if (!(__VLS_ctx.selectedRecord))
                return;
            __VLS_ctx.analysisDrawerVisible = false;
        }
    };
    var __VLS_142;
}
var __VLS_139;
/** @type {__VLS_StyleScopedClasses['records-view']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-50']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-100']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['pb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['medical-records-table']} */ ;
/** @type {__VLS_StyleScopedClasses['patient-info']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['status-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['score-display']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-drawer']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-drawer']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            UploadOutlined: icons_vue_1.UploadOutlined,
            RecordUploadForm: RecordUploadForm_vue_1.default,
            RecordDetailPanel: RecordDetailPanel_vue_1.default,
            AnalysisResultPanel: AnalysisResultPanel_vue_1.default,
            PageHeader: PageHeader_vue_1.default,
            LoadingSpinner: LoadingSpinner_vue_1.default,
            EmptyState: EmptyState_vue_1.default,
            records: records,
            isLoading: isLoading,
            isAnalyzing: isAnalyzing,
            statusFilter: statusFilter,
            retryingId: retryingId,
            detailDrawerVisible: detailDrawerVisible,
            analysisDrawerVisible: analysisDrawerVisible,
            selectedRecord: selectedRecord,
            headerActions: headerActions,
            headerStats: headerStats,
            tableColumns: tableColumns,
            paginationConfig: paginationConfig,
            filteredRecords: filteredRecords,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
            getScoreColor: getScoreColor,
            getGradeColor: getGradeColor,
            handleHeaderAction: handleHeaderAction,
            handleRecordSubmit: handleRecordSubmit,
            handleUploadCancel: handleUploadCancel,
            viewRecord: viewRecord,
            viewAnalysis: viewAnalysis,
            retryAnalysis: retryAnalysis,
            deleteRecord: deleteRecord,
            refreshRecords: refreshRecords,
            scrollToUpload: scrollToUpload,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
