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
const dayjs_1 = __importDefault(require("dayjs"));
import supabaseMedicalRecordService_1 from '@/services/supabaseMedicalRecordService';
const router = (0, vue_router_1.useRouter)();
// 响应式数据
const loading = (0, vue_1.ref)(false);
const records = (0, vue_1.ref)(: any[]);
const selectedRowKeys = (0, vue_1.ref)(: any[]);
const qualityPointsModalVisible = (0, vue_1.ref)(false);
const selectedRecord = (0, vue_1.ref)(null);
const qualityPointsData = (0, vue_1.ref)(: any[]);
// 统计数据
const stats = (0, vue_1.reactive)({
    totalRecords: 156,
    monthlyNew: 23,
    pendingReview: 5,
    withQualityPoints: 89
});
// 搜索表单
const searchForm = (0, vue_1.reactive)({
    recordName: '',
    department: '',
    diagnosis: '',
    creator: '',
    dateRange: null
});
// 分页配置
const viewMode = (0, vue_1.ref)('card');
const pagination = (0, vue_1.reactive)({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
});
// 表格列配置
const columns = [
    {
        title: '病历编号',
        dataIndex: 'recordNumber',
        key: 'recordNumber',
        width: 100,
        sorter: true,
        slots: { customRender: 'recordNumber' }
    },
    {
        title: '患者姓名',
        dataIndex: 'patientName',
        key: 'patientName',
        width: 200,
        slots: { customRender: 'patientName' }
    },
    {
        title: '出院科室',
        dataIndex: 'department',
        key: 'department',
        width: 120
    },
    {
        title: '主诊断名称',
        dataIndex: 'primaryDiagnosis',
        key: 'primaryDiagnosis',
        width: 150
    },
    {
        title: '主要手术及操作',
        dataIndex: 'majorSurgery',
        key: 'majorSurgery',
        width: 180,
        ellipsis: true
    },
    {
        title: '文书数量',
        dataIndex: 'documentsCount',
        key: 'documentsCount',
        width: 80,
        align: 'center'
    },
    {
        title: '应用质控点',
        key: 'qualityPoints',
        width: 120,
        slots: { customRender: 'qualityPoints' }
    },
    {
        title: '病历创建人',
        dataIndex: 'createdBy',
        key: 'createdBy',
        width: 100
    },
    {
        title: '最后操作人',
        dataIndex: 'lastModifiedBy',
        key: 'lastModifiedBy',
        width: 100
    },
    {
        title: '创建时间',
        dataIndex: 'createdAt',
        key: 'createdAt',
        width: 120,
        sorter: true,
        slots: { customRender: 'createdAt' }
    },
    {
        title: '操作',
        key: 'action',
        width: 120,
        fixed: 'right',
        slots: { customRender: 'action' }
    }
];
// 行选择配置
const rowSelection = (0, vue_1.computed)(() => ({
    selectedRowKeys: selectedRowKeys.value, onChange: (keys) => {
        selectedRowKeys.value = keys;
    },
    onSelectAll: (selected: any,  selectedRows: any, changeRows: any) => {
        console.log('Select all:', selected, selectedRows, changeRows);
    }
}));
// 生命周期
(0, vue_1.onMounted)(() => {
    loadRecords();
    loadStats();
});
// 方法定义
const loadRecords = async () => {
    loading.value = true;
    try {
        // 构建搜索参数
        const searchParams = {
            search: searchForm.recordName || undefined,
            department: searchForm.department || undefined,
            page: pagination.current,
            page_size: pagination.pageSize,
            sort_by: 'created_at',
            sort_order: 'desc'
        };
        // 处理日期范围
        if (searchForm.dateRange && searchForm.dateRange.length === 2) {
            searchParams.date_range = [
                searchForm.dateRange[0].format('YYYY-MM-DD'),
                searchForm.dateRange[1].format('YYYY-MM-DD')
            ];
        }
        // 调用Supabase服务
        const result = await supabaseMedicalRecordService_1.supabaseMedicalRecordService.getMedicalRecords(searchParams);
        // 转换数据格式以适配现有UI - 适配测试表结构
        records.value = result.data.map(record => ({ id: record.id,
            recordNumber: record.record_number,
            recordName: record.record_name,
            patientName: record.patient_info?.name || '未知患者', // 提取患者姓名
            department: record.department,
            primaryDiagnosis: record.primary_diagnosis,
            majorSurgery: record.major_surgery,
            qualityPointIds:  [], // 暂时为空，后续可以从关联表获取
            createdBy: record.patient_info?.name || '系统',
            lastModifiedBy: record.patient_info?.name || '系统',
            createdAt: record.created_at,
            status: record.status,
            importMethod: record.import_method,
            aiConfidence: record.ai_confidence_score,
            documentsCount: Array.isArray(record.documents) ? record.documents.length : 0 // 显示文书数量
        }));
        pagination.total = result.total;
    }
    catch (error) { console.error('加载病历列表失败:', error);
        ant_design_vue_1.message.error('加载病历列表失败');
        // 如果Supabase调用失败，使用模拟数据作为后备
        const mockData = [
            {
                id: '1',
                recordNumber: 'TEST20240827001',
                recordName: '张三测试病历',
                patientName: '张三',
                department: '内科',
                primaryDiagnosis: '高血压病',
                majorSurgery: '无',
                qualityPointIds:  [],
                createdBy: '系统',
                lastModifiedBy: '系统',
                createdAt: '2024-08-27T10:30:00Z',
                status: 'active',
                importMethod: 'smart_import',
                aiConfidence: 89.5,
                documentsCount: 2
            }
        ];
        records.value = mockData;
        pagination.total = mockData.length;
    }
    finally {
        loading.value = false;
    }
};
const loadStats = async () => {
    try {
        const statsData = await supabaseMedicalRecordService_1.supabaseMedicalRecordService.getMedicalRecordStats();
        Object.assign(stats, {
            totalRecords: statsData.total_records,
            monthlyNew: statsData.monthly_new,
            pendingReview: statsData.pending_review,
            withQualityPoints: statsData.smart_imported // 使用智能导入数量作为质控点关联数量
        });
    }
    catch (error) {
        console.error('加载统计数据失败:', error);
        // 保持默认的模拟数据
    }
};
const formatDateTime = (dateString) => {
    return (0, dayjs_1.default)(dateString).format('YYYY-MM-DD HH:mm');
};
const getCategoryColor = (category) => {
    const colorMap = {
        '完整性': 'blue',
        '一致性': 'green',
        '合理性': 'orange',
        '及时性': 'purple'
    };
    return colorMap[category] || 'default';
};
const getSeverityColor = (severity) => {
    const colorMap = {
        '严重': 'red',
        '重要': 'orange',
        '轻微': 'green'
    };
    return colorMap[severity] || 'default';
};
// 事件处理
const handleSmartImport = () => {
    router.push('/dashboard/medical-records/smart-import');
};
const handleEdit = (id) => {
    router.push(`/dashboard/medical-records/edit/${id}`);
};
const handleCopy = async (id) => {
    try {
        // 模拟复制操作
        await new Promise(resolve => setTimeout(resolve, 500));
        ant_design_vue_1.message.success('病历复制成功');
        loadRecords();
    }
    catch (error) {
        ant_design_vue_1.message.error('复制失败');
    }
};
const handleDelete = async (id) => {
    try {
        // 调用 Supabase 删除 API
        await supabaseMedicalRecordService_1.supabaseMedicalRecordService.deleteMedicalRecord(id);
        ant_design_vue_1.message.success('删除成功');
        // 重新加载列表数据
        loadRecords();
    }
    catch (error) {
        console.error('删除失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '删除失败');
    }
};
const handleSearch = () => {
    pagination.current = 1;
    loadRecords();
};
const handleReset = () => {
    Object.assign(searchForm, {
        recordName: '',
        department: '',
        diagnosis: '',
        creator: '',
        dateRange: null
    });
    handleSearch();
};
const handleRefresh = () => {
    loadRecords();
};
const toggleViewMode = () => {
    viewMode.value = viewMode.value === 'card' ? 'table' : 'card';
};
const handleTableChange = (pag: any,  filters: any, sorter: any) => {
    pagination.current = pag?.current || 1;
    pagination.pageSize = pag?.pageSize || 10;
    loadRecords();
};
const showQualityPointsModal = async (record) => {
    selectedRecord.value = record;
    qualityPointsModalVisible.value = true;
    // 模拟加载质控点数据
    qualityPointsData.value = [
        {
            id: 'QC001',
            name: '完整性检查',
            category: '完整性',
            severity: '重要',
            appliedAt: '2024-08-27T10:30:00Z'
        },
        {
            id: 'QC002',
            name: '一致性检查',
            category: '一致性',
            severity: '严重',
            appliedAt: '2024-08-27T10:35:00Z'
        }
    ];
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['records-table-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['table-title']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-record-info']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['record-number-text']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['patient-name-text']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['record-number-text']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['patient-name-text']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-actions" },
});
const __VLS_0 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (__VLS_ctx.toggleViewMode)
};
__VLS_7.slots.default;
(__VLS_ctx.viewMode === 'card' ? '切换表格视图' : '切换卡片视图');
var __VLS_7;
const __VLS_12 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (__VLS_ctx.handleSmartImport)
};
__VLS_15.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_15.slots;
    const __VLS_20 = {}.RobotOutlined;
    /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
    const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
var __VLS_15;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stats-grid" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ui-gradient-wrap from-sky-400/40 via-blue-400/30 to-indigo-400/40" },
});
const __VLS_24 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}));
const __VLS_26 = __VLS_25({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    title: "总病历数",
    value: (__VLS_ctx.stats.totalRecords),
    valueStyle: ({ color: '#1890ff' }),
}));
const __VLS_30 = __VLS_29({
    title: "总病历数",
    value: (__VLS_ctx.stats.totalRecords),
    valueStyle: ({ color: '#1890ff' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_31.slots;
    const __VLS_32 = {}.FileTextOutlined;
    /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
    const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
}
var __VLS_31;
var __VLS_27;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ui-gradient-wrap from-emerald-400/40 via-teal-400/30 to-green-400/40" },
});
const __VLS_36 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}));
const __VLS_38 = __VLS_37({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
const __VLS_40 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    title: "本月新增",
    value: (__VLS_ctx.stats.monthlyNew),
    valueStyle: ({ color: '#52c41a' }),
}));
const __VLS_42 = __VLS_41({
    title: "本月新增",
    value: (__VLS_ctx.stats.monthlyNew),
    valueStyle: ({ color: '#52c41a' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_43.slots;
    const __VLS_44 = {}.PlusCircleOutlined;
    /** @type {[typeof __VLS_components.PlusCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
    const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
}
var __VLS_43;
var __VLS_39;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ui-gradient-wrap from-amber-400/40 via-orange-400/30 to-yellow-400/40" },
});
const __VLS_48 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}));
const __VLS_50 = __VLS_49({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    title: "待审核",
    value: (__VLS_ctx.stats.pendingReview),
    valueStyle: ({ color: '#faad14' }),
}));
const __VLS_54 = __VLS_53({
    title: "待审核",
    value: (__VLS_ctx.stats.pendingReview),
    valueStyle: ({ color: '#faad14' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_55.slots;
    const __VLS_56 = {}.ClockCircleOutlined;
    /** @type {[typeof __VLS_components.ClockCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
    const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
}
var __VLS_55;
var __VLS_51;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ui-gradient-wrap from-violet-400/40 via-purple-400/30 to-fuchsia-400/40" },
});
const __VLS_60 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}));
const __VLS_62 = __VLS_61({
    ...{ class: "ui-card ui-card-muted ui-card-hover stat-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
const __VLS_64 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    title: "已关联质控点",
    value: (__VLS_ctx.stats.withQualityPoints),
    valueStyle: ({ color: '#722ed1' }),
}));
const __VLS_66 = __VLS_65({
    title: "已关联质控点",
    value: (__VLS_ctx.stats.withQualityPoints),
    valueStyle: ({ color: '#722ed1' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_67.slots;
    const __VLS_68 = {}.CheckCircleOutlined;
    /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({}));
    const __VLS_70 = __VLS_69({}, ...__VLS_functionalComponentArgsRest(__VLS_69));
}
var __VLS_67;
var __VLS_63;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ui-gradient-wrap from-sky-400/30 via-blue-400/20 to-indigo-400/30" },
});
const __VLS_72 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    ...{ class: "ui-card ui-card-primary ui-card-hover filter-card" },
}));
const __VLS_74 = __VLS_73({
    ...{ class: "ui-card ui-card-primary ui-card-hover filter-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
const __VLS_76 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    gutter: (16),
}));
const __VLS_78 = __VLS_77({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
const __VLS_80 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    span: (6),
}));
const __VLS_82 = __VLS_81({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
const __VLS_84 = {}.AInputSearch;
/** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    ...{ 'onSearch': {} },
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.recordName),
    placeholder: "搜索患者姓名",
}));
const __VLS_86 = __VLS_85({
    ...{ 'onSearch': {} },
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.recordName),
    placeholder: "搜索患者姓名",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
let __VLS_88;
let __VLS_89;
let __VLS_90;
const __VLS_91 = {
    onSearch: (__VLS_ctx.handleSearch)
};
const __VLS_92 = {
    onChange: (__VLS_ctx.handleSearch)
};
var __VLS_87;
var __VLS_83;
const __VLS_93 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({
    span: (4),
}));
const __VLS_95 = __VLS_94({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_94));
__VLS_96.slots.default;
const __VLS_97 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.department),
    placeholder: "出院科室",
    allowClear: true,
}));
const __VLS_99 = __VLS_98({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.department),
    placeholder: "出院科室",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_98));
let __VLS_101;
let __VLS_102;
let __VLS_103;
const __VLS_104 = {
    onChange: (__VLS_ctx.handleSearch)
};
__VLS_100.slots.default;
const __VLS_105 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
    value: "",
}));
const __VLS_107 = __VLS_106({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_106));
__VLS_108.slots.default;
var __VLS_108;
const __VLS_109 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
    value: "内科",
}));
const __VLS_111 = __VLS_110({
    value: "内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_110));
__VLS_112.slots.default;
var __VLS_112;
const __VLS_113 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
    value: "外科",
}));
const __VLS_115 = __VLS_114({
    value: "外科",
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
__VLS_116.slots.default;
var __VLS_116;
const __VLS_117 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({
    value: "妇产科",
}));
const __VLS_119 = __VLS_118({
    value: "妇产科",
}, ...__VLS_functionalComponentArgsRest(__VLS_118));
__VLS_120.slots.default;
var __VLS_120;
const __VLS_121 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
    value: "儿科",
}));
const __VLS_123 = __VLS_122({
    value: "儿科",
}, ...__VLS_functionalComponentArgsRest(__VLS_122));
__VLS_124.slots.default;
var __VLS_124;
const __VLS_125 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({
    value: "急诊科",
}));
const __VLS_127 = __VLS_126({
    value: "急诊科",
}, ...__VLS_functionalComponentArgsRest(__VLS_126));
__VLS_128.slots.default;
var __VLS_128;
var __VLS_100;
var __VLS_96;
const __VLS_129 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_130 = __VLS_asFunctionalComponent(__VLS_129, new __VLS_129({
    span: (4),
}));
const __VLS_131 = __VLS_130({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_130));
__VLS_132.slots.default;
const __VLS_133 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_134 = __VLS_asFunctionalComponent(__VLS_133, new __VLS_133({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.diagnosis),
    placeholder: "主诊断",
    allowClear: true,
}));
const __VLS_135 = __VLS_134({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.diagnosis),
    placeholder: "主诊断",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_134));
let __VLS_137;
let __VLS_138;
let __VLS_139;
const __VLS_140 = {
    onChange: (__VLS_ctx.handleSearch)
};
__VLS_136.slots.default;
const __VLS_141 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_142 = __VLS_asFunctionalComponent(__VLS_141, new __VLS_141({
    value: "",
}));
const __VLS_143 = __VLS_142({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_142));
__VLS_144.slots.default;
var __VLS_144;
const __VLS_145 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
    value: "高血压",
}));
const __VLS_147 = __VLS_146({
    value: "高血压",
}, ...__VLS_functionalComponentArgsRest(__VLS_146));
__VLS_148.slots.default;
var __VLS_148;
const __VLS_149 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
    value: "糖尿病",
}));
const __VLS_151 = __VLS_150({
    value: "糖尿病",
}, ...__VLS_functionalComponentArgsRest(__VLS_150));
__VLS_152.slots.default;
var __VLS_152;
const __VLS_153 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({
    value: "冠心病",
}));
const __VLS_155 = __VLS_154({
    value: "冠心病",
}, ...__VLS_functionalComponentArgsRest(__VLS_154));
__VLS_156.slots.default;
var __VLS_156;
const __VLS_157 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
    value: "肺炎",
}));
const __VLS_159 = __VLS_158({
    value: "肺炎",
}, ...__VLS_functionalComponentArgsRest(__VLS_158));
__VLS_160.slots.default;
var __VLS_160;
const __VLS_161 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
    value: "阑尾炎",
}));
const __VLS_163 = __VLS_162({
    value: "阑尾炎",
}, ...__VLS_functionalComponentArgsRest(__VLS_162));
__VLS_164.slots.default;
var __VLS_164;
var __VLS_136;
var __VLS_132;
const __VLS_165 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
    span: (4),
}));
const __VLS_167 = __VLS_166({
    span: (4),
}, ...__VLS_functionalComponentArgsRest(__VLS_166));
__VLS_168.slots.default;
const __VLS_169 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.creator),
    placeholder: "创建人",
    allowClear: true,
}));
const __VLS_171 = __VLS_170({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.creator),
    placeholder: "创建人",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_170));
let __VLS_173;
let __VLS_174;
let __VLS_175;
const __VLS_176 = {
    onChange: (__VLS_ctx.handleSearch)
};
__VLS_172.slots.default;
const __VLS_177 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_178 = __VLS_asFunctionalComponent(__VLS_177, new __VLS_177({
    value: "",
}));
const __VLS_179 = __VLS_178({
    value: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_178));
__VLS_180.slots.default;
var __VLS_180;
const __VLS_181 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
    value: "张医生",
}));
const __VLS_183 = __VLS_182({
    value: "张医生",
}, ...__VLS_functionalComponentArgsRest(__VLS_182));
__VLS_184.slots.default;
var __VLS_184;
const __VLS_185 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_186 = __VLS_asFunctionalComponent(__VLS_185, new __VLS_185({
    value: "李医生",
}));
const __VLS_187 = __VLS_186({
    value: "李医生",
}, ...__VLS_functionalComponentArgsRest(__VLS_186));
__VLS_188.slots.default;
var __VLS_188;
const __VLS_189 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_190 = __VLS_asFunctionalComponent(__VLS_189, new __VLS_189({
    value: "王医生",
}));
const __VLS_191 = __VLS_190({
    value: "王医生",
}, ...__VLS_functionalComponentArgsRest(__VLS_190));
__VLS_192.slots.default;
var __VLS_192;
var __VLS_172;
var __VLS_168;
const __VLS_193 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_194 = __VLS_asFunctionalComponent(__VLS_193, new __VLS_193({
    span: (6),
}));
const __VLS_195 = __VLS_194({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_194));
__VLS_196.slots.default;
const __VLS_197 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_198 = __VLS_asFunctionalComponent(__VLS_197, new __VLS_197({}));
const __VLS_199 = __VLS_198({}, ...__VLS_functionalComponentArgsRest(__VLS_198));
__VLS_200.slots.default;
const __VLS_201 = {}.ARangePicker;
/** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
// @ts-ignore
const __VLS_202 = __VLS_asFunctionalComponent(__VLS_201, new __VLS_201({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.dateRange),
}));
const __VLS_203 = __VLS_202({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.searchForm.dateRange),
}, ...__VLS_functionalComponentArgsRest(__VLS_202));
let __VLS_205;
let __VLS_206;
let __VLS_207;
const __VLS_208 = {
    onChange: (__VLS_ctx.handleSearch)
};
var __VLS_204;
const __VLS_209 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_210 = __VLS_asFunctionalComponent(__VLS_209, new __VLS_209({
    ...{ 'onClick': {} },
}));
const __VLS_211 = __VLS_210({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_210));
let __VLS_213;
let __VLS_214;
let __VLS_215;
const __VLS_216 = {
    onClick: (__VLS_ctx.handleReset)
};
__VLS_212.slots.default;
var __VLS_212;
var __VLS_200;
var __VLS_196;
var __VLS_79;
var __VLS_75;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "ui-gradient-wrap from-slate-400/30 via-gray-400/20 to-zinc-400/30" },
});
const __VLS_217 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_218 = __VLS_asFunctionalComponent(__VLS_217, new __VLS_217({
    ...{ class: "ui-card ui-card-muted ui-card-hover records-table-card" },
}));
const __VLS_219 = __VLS_218({
    ...{ class: "ui-card ui-card-muted ui-card-hover records-table-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_218));
__VLS_220.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "table-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "table-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "record-count" },
});
(__VLS_ctx.pagination.total);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "table-actions" },
});
const __VLS_221 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_222 = __VLS_asFunctionalComponent(__VLS_221, new __VLS_221({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_223 = __VLS_222({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_222));
let __VLS_225;
let __VLS_226;
let __VLS_227;
const __VLS_228 = {
    onClick: (__VLS_ctx.handleRefresh)
};
__VLS_224.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_224.slots;
    const __VLS_229 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_230 = __VLS_asFunctionalComponent(__VLS_229, new __VLS_229({}));
    const __VLS_231 = __VLS_230({}, ...__VLS_functionalComponentArgsRest(__VLS_230));
}
var __VLS_224;
if (__VLS_ctx.viewMode === 'card') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-3" },
    });
    for (const [rec] of __VLS_getVForSourceType((__VLS_ctx.records))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (rec.id),
            ...{ class: "record-card ui-card ui-card-muted ui-card-hover p-3 transition-colors transition-shadow duration-200 ease-out hover:bg-[#e8f4fd] hover:shadow-md hover:border-blue-200" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-start justify-between" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-gray-500" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-sm font-semibold text-gray-900 record-number-text" },
        });
        (rec.recordNumber);
        const __VLS_233 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_234 = __VLS_asFunctionalComponent(__VLS_233, new __VLS_233({
            color: (rec.status === 'active' ? 'blue' : 'default'),
        }));
        const __VLS_235 = __VLS_234({
            color: (rec.status === 'active' ? 'blue' : 'default'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_234));
        __VLS_236.slots.default;
        (rec.status || '—');
        var __VLS_236;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-gray-500" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-gray-800 font-medium patient-name-text" },
        });
        (rec.patientName || rec.recordName);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-2 grid grid-cols-2 gap-2 text-xs text-gray-600" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-800" },
        });
        (rec.department || '—');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-800" },
        });
        (rec.documentsCount ?? 0);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "col-span-2 truncate" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-800" },
        });
        (rec.primaryDiagnosis || '—');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-3 flex items-center justify-between text-xs text-gray-500" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        (__VLS_ctx.formatDateTime(rec.createdAt));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center gap-2" },
        });
        const __VLS_237 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_238 = __VLS_asFunctionalComponent(__VLS_237, new __VLS_237({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "p-0" },
        }));
        const __VLS_239 = __VLS_238({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "p-0" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_238));
        let __VLS_241;
        let __VLS_242;
        let __VLS_243;
        const __VLS_244 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.viewMode === 'card'))
                    return;
                __VLS_ctx.handleEdit(rec.id);
            }
        };
        __VLS_240.slots.default;
        var __VLS_240;
        const __VLS_245 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_246 = __VLS_asFunctionalComponent(__VLS_245, new __VLS_245({
            type: "vertical",
        }));
        const __VLS_247 = __VLS_246({
            type: "vertical",
        }, ...__VLS_functionalComponentArgsRest(__VLS_246));
        const __VLS_249 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_250 = __VLS_asFunctionalComponent(__VLS_249, new __VLS_249({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "p-0" },
        }));
        const __VLS_251 = __VLS_250({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            ...{ class: "p-0" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_250));
        let __VLS_253;
        let __VLS_254;
        let __VLS_255;
        const __VLS_256 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.viewMode === 'card'))
                    return;
                __VLS_ctx.handleCopy(rec.id);
            }
        };
        __VLS_252.slots.default;
        var __VLS_252;
        const __VLS_257 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_258 = __VLS_asFunctionalComponent(__VLS_257, new __VLS_257({
            type: "vertical",
        }));
        const __VLS_259 = __VLS_258({
            type: "vertical",
        }, ...__VLS_functionalComponentArgsRest(__VLS_258));
        const __VLS_261 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_262 = __VLS_asFunctionalComponent(__VLS_261, new __VLS_261({
            ...{ 'onConfirm': {} },
            title: "确定要删除这条病历吗？",
            okText: "确定",
            cancelText: "取消",
        }));
        const __VLS_263 = __VLS_262({
            ...{ 'onConfirm': {} },
            title: "确定要删除这条病历吗？",
            okText: "确定",
            cancelText: "取消",
        }, ...__VLS_functionalComponentArgsRest(__VLS_262));
        let __VLS_265;
        let __VLS_266;
        let __VLS_267;
        const __VLS_268 = {
            onConfirm: (...[$event]) => {
                if (!(__VLS_ctx.viewMode === 'card'))
                    return;
                __VLS_ctx.handleDelete(rec.id);
            }
        };
        __VLS_264.slots.default;
        const __VLS_269 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_270 = __VLS_asFunctionalComponent(__VLS_269, new __VLS_269({
            type: "link",
            size: "small",
            danger: true,
            ...{ class: "p-0" },
        }));
        const __VLS_271 = __VLS_270({
            type: "link",
            size: "small",
            danger: true,
            ...{ class: "p-0" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_270));
        __VLS_272.slots.default;
        var __VLS_272;
        var __VLS_264;
    }
}
else {
    const __VLS_273 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_274 = __VLS_asFunctionalComponent(__VLS_273, new __VLS_273({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.records),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.pagination),
        rowSelection: (__VLS_ctx.rowSelection),
        size: "middle",
    }));
    const __VLS_275 = __VLS_274({
        ...{ 'onChange': {} },
        columns: (__VLS_ctx.columns),
        dataSource: (__VLS_ctx.records),
        loading: (__VLS_ctx.loading),
        pagination: (__VLS_ctx.pagination),
        rowSelection: (__VLS_ctx.rowSelection),
        size: "middle",
    }, ...__VLS_functionalComponentArgsRest(__VLS_274));
    let __VLS_277;
    let __VLS_278;
    let __VLS_279;
    const __VLS_280 = {
        onChange: (__VLS_ctx.handleTableChange)
    };
    __VLS_276.slots.default;
    {
        const { recordNumber: __VLS_thisSlot } = __VLS_276.slots;
        const [{ text }] = __VLS_getSlotParams(__VLS_thisSlot);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "record-number" },
        });
        (text);
    }
    {
        const { patientName: __VLS_thisSlot } = __VLS_276.slots;
        const [{ record }] = __VLS_getSlotParams(__VLS_thisSlot);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "patient-name" },
        });
        (record.patientName || record.recordName || '未知');
    }
    {
        const { qualityPoints: __VLS_thisSlot } = __VLS_276.slots;
        const [{ record }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_281 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_282 = __VLS_asFunctionalComponent(__VLS_281, new __VLS_281({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_283 = __VLS_282({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_282));
        let __VLS_285;
        let __VLS_286;
        let __VLS_287;
        const __VLS_288 = {
            onClick: (...[$event]) => {
                if (!!(__VLS_ctx.viewMode === 'card'))
                    return;
                __VLS_ctx.showQualityPointsModal(record);
            }
        };
        __VLS_284.slots.default;
        (record.qualityPointIds?.length || 0);
        var __VLS_284;
    }
    {
        const { createdAt: __VLS_thisSlot } = __VLS_276.slots;
        const [{ text }] = __VLS_getSlotParams(__VLS_thisSlot);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (__VLS_ctx.formatDateTime(text));
    }
    {
        const { action: __VLS_thisSlot } = __VLS_276.slots;
        const [{ record }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_289 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_290 = __VLS_asFunctionalComponent(__VLS_289, new __VLS_289({
            size: "small",
        }));
        const __VLS_291 = __VLS_290({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_290));
        __VLS_292.slots.default;
        const __VLS_293 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_294 = __VLS_asFunctionalComponent(__VLS_293, new __VLS_293({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_295 = __VLS_294({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_294));
        let __VLS_297;
        let __VLS_298;
        let __VLS_299;
        const __VLS_300 = {
            onClick: (...[$event]) => {
                if (!!(__VLS_ctx.viewMode === 'card'))
                    return;
                __VLS_ctx.handleEdit(record.id);
            }
        };
        __VLS_296.slots.default;
        var __VLS_296;
        const __VLS_301 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_302 = __VLS_asFunctionalComponent(__VLS_301, new __VLS_301({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_303 = __VLS_302({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_302));
        let __VLS_305;
        let __VLS_306;
        let __VLS_307;
        const __VLS_308 = {
            onClick: (...[$event]) => {
                if (!!(__VLS_ctx.viewMode === 'card'))
                    return;
                __VLS_ctx.handleCopy(record.id);
            }
        };
        __VLS_304.slots.default;
        var __VLS_304;
        const __VLS_309 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_310 = __VLS_asFunctionalComponent(__VLS_309, new __VLS_309({
            ...{ 'onConfirm': {} },
            title: "确定要删除这条病历吗？",
            okText: "确定",
            cancelText: "取消",
        }));
        const __VLS_311 = __VLS_310({
            ...{ 'onConfirm': {} },
            title: "确定要删除这条病历吗？",
            okText: "确定",
            cancelText: "取消",
        }, ...__VLS_functionalComponentArgsRest(__VLS_310));
        let __VLS_313;
        let __VLS_314;
        let __VLS_315;
        const __VLS_316 = {
            onConfirm: (...[$event]) => {
                if (!!(__VLS_ctx.viewMode === 'card'))
                    return;
                __VLS_ctx.handleDelete(record.id);
            }
        };
        __VLS_312.slots.default;
        const __VLS_317 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_318 = __VLS_asFunctionalComponent(__VLS_317, new __VLS_317({
            type: "link",
            size: "small",
            danger: true,
        }));
        const __VLS_319 = __VLS_318({
            type: "link",
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_318));
        __VLS_320.slots.default;
        var __VLS_320;
        var __VLS_312;
        var __VLS_292;
    }
    var __VLS_276;
}
var __VLS_220;
const __VLS_321 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_322 = __VLS_asFunctionalComponent(__VLS_321, new __VLS_321({
    open: (__VLS_ctx.qualityPointsModalVisible),
    title: "质控点详情",
    footer: (null),
    width: "600px",
}));
const __VLS_323 = __VLS_322({
    open: (__VLS_ctx.qualityPointsModalVisible),
    title: "质控点详情",
    footer: (null),
    width: "600px",
}, ...__VLS_functionalComponentArgsRest(__VLS_322));
__VLS_324.slots.default;
if (__VLS_ctx.selectedRecord) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "modal-record-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.selectedRecord.recordNumber);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.selectedRecord.patientName || __VLS_ctx.selectedRecord.recordName);
    const __VLS_325 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_326 = __VLS_asFunctionalComponent(__VLS_325, new __VLS_325({}));
    const __VLS_327 = __VLS_326({}, ...__VLS_functionalComponentArgsRest(__VLS_326));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "quality-points-list" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    if (__VLS_ctx.qualityPointsData.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "no-data" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        for (const [point] of __VLS_getVForSourceType((__VLS_ctx.qualityPointsData))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (point.id),
                ...{ class: "quality-point-item" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "point-header" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "point-id" },
            });
            (point.id);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "point-name" },
            });
            (point.name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "point-details" },
            });
            const __VLS_329 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_330 = __VLS_asFunctionalComponent(__VLS_329, new __VLS_329({
                color: (__VLS_ctx.getCategoryColor(point.category)),
            }));
            const __VLS_331 = __VLS_330({
                color: (__VLS_ctx.getCategoryColor(point.category)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_330));
            __VLS_332.slots.default;
            (point.category);
            var __VLS_332;
            const __VLS_333 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_334 = __VLS_asFunctionalComponent(__VLS_333, new __VLS_333({
                color: (__VLS_ctx.getSeverityColor(point.severity)),
            }));
            const __VLS_335 = __VLS_334({
                color: (__VLS_ctx.getSeverityColor(point.severity)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_334));
            __VLS_336.slots.default;
            (point.severity);
            var __VLS_336;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "applied-time" },
            });
            (__VLS_ctx.formatDateTime(point.appliedAt));
        }
    }
}
var __VLS_324;
/** @type {__VLS_StyleScopedClasses['page-container']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-sky-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-emerald-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['via-teal-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['to-green-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-amber-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['via-orange-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['to-yellow-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-violet-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['via-purple-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['to-fuchsia-400/40']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-sky-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-400/20']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-gradient-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['from-slate-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['via-gray-400/20']} */ ;
/** @type {__VLS_StyleScopedClasses['to-zinc-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['records-table-card']} */ ;
/** @type {__VLS_StyleScopedClasses['table-header']} */ ;
/** @type {__VLS_StyleScopedClasses['table-title']} */ ;
/** @type {__VLS_StyleScopedClasses['record-count']} */ ;
/** @type {__VLS_StyleScopedClasses['table-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['xl:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['record-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-hover']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-200']} */ ;
/** @type {__VLS_StyleScopedClasses['ease-out']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-[#e8f4fd]']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['record-number-text']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['patient-name-text']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['col-span-2']} */ ;
/** @type {__VLS_StyleScopedClasses['truncate']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['p-0']} */ ;
/** @type {__VLS_StyleScopedClasses['p-0']} */ ;
/** @type {__VLS_StyleScopedClasses['p-0']} */ ;
/** @type {__VLS_StyleScopedClasses['record-number']} */ ;
/** @type {__VLS_StyleScopedClasses['patient-name']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-record-info']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-points-list']} */ ;
/** @type {__VLS_StyleScopedClasses['no-data']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-point-item']} */ ;
/** @type {__VLS_StyleScopedClasses['point-header']} */ ;
/** @type {__VLS_StyleScopedClasses['point-id']} */ ;
/** @type {__VLS_StyleScopedClasses['point-name']} */ ;
/** @type {__VLS_StyleScopedClasses['point-details']} */ ;
/** @type {__VLS_StyleScopedClasses['applied-time']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            PlusCircleOutlined: icons_vue_1.PlusCircleOutlined,
            ClockCircleOutlined: icons_vue_1.ClockCircleOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            RobotOutlined: icons_vue_1.RobotOutlined,
            loading: loading,
            records: records,
            qualityPointsModalVisible: qualityPointsModalVisible,
            selectedRecord: selectedRecord,
            qualityPointsData: qualityPointsData,
            stats: stats,
            searchForm: searchForm,
            viewMode: viewMode,
            pagination: pagination,
            columns: columns,
            rowSelection: rowSelection,
            formatDateTime: formatDateTime,
            getCategoryColor: getCategoryColor,
            getSeverityColor: getSeverityColor,
            handleSmartImport: handleSmartImport,
            handleEdit: handleEdit,
            handleCopy: handleCopy,
            handleDelete: handleDelete,
            handleSearch: handleSearch,
            handleReset: handleReset,
            handleRefresh: handleRefresh,
            toggleViewMode: toggleViewMode,
            handleTableChange: handleTableChange,
            showQualityPointsModal: showQualityPointsModal,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
