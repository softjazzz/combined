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
// 响应式数据
const loading = (0, vue_1.ref)(false);
const searchKeyword = (0, vue_1.ref)('');
const selectedStatus = (0, vue_1.ref)(undefined);
const selectedAssignee = (0, vue_1.ref)(undefined);
const selectedDepartment = (0, vue_1.ref)(undefined);
const dateRange = (0, vue_1.ref)(: any[]);
const tasks = (0, vue_1.ref)(: any[]);
const selectedRowKeys = (0, vue_1.ref)(: any[]);
// 分页配置
const pagination = (0, vue_1.ref)({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total) => `共 ${total} 条任务`
});
// 行选择配置
const rowSelection = {
    selectedRowKeys: selectedRowKeys,
    onChange: (keys: any) => {
        selectedRowKeys.value = keys;
    }
};
// 选项配置
const statusOptions = [
    { value: 'unassigned', label: '待分配' },
    { value: 'pending', label: '待处理' },
    { value: 'in_progress', label: '进行中' },
    { value: 'completed', label: '已完成' },
    { value: 'overdue', label: '已逾期' }
];
const assigneeOptions = [
    { value: 'zhang_san', label: '张三' },
    { value: 'li_si', label: '李四' },
    { value: 'wang_wu', label: '王五' }
];
const departmentOptions = [
    { value: 'internal', label: '内科' },
    { value: 'surgery', label: '外科' },
    { value: 'pediatrics', label: '儿科' },
    { value: 'obstetrics', label: '妇产科' }
];
// 表格列配置
const columns = [
    {
        title: '任务编号',
        dataIndex: 'taskNumber',
        key: 'taskNumber',
        width: 120
    },
    {
        title: '任务名称',
        dataIndex: 'taskName',
        key: 'taskName',
        width: 200
    },
    {
        title: '病历号',
        dataIndex: 'recordNumber',
        key: 'recordNumber',
        width: 120
    },
    {
        title: '科室',
        dataIndex: 'department',
        key: 'department',
        width: 100
    },
    {
        title: '负责人',
        dataIndex: 'assignee',
        key: 'assignee',
        width: 120
    },
    {
        title: '优先级',
        dataIndex: 'priority',
        key: 'priority',
        width: 80
    },
    {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100
    },
    {
        title: '进度',
        dataIndex: 'progress',
        key: 'progress',
        width: 120
    },
    {
        title: '创建时间',
        dataIndex: 'createTime',
        key: 'createTime',
        width: 150
    },
    {
        title: '截止时间',
        dataIndex: 'deadline',
        key: 'deadline',
        width: 150
    },
    {
        title: '操作',
        key: 'action',
        width: 250,
        fixed: 'right'
    }
];
// 工具函数
const getPriorityColor = (priority) => {
    const colorMap = {
        high: 'red',
        medium: 'orange',
        low: 'green'
    };
    return colorMap[priority] || 'default';
};
const getPriorityText = (priority) => {
    const textMap = {
        high: '高',
        medium: '中',
        low: '低'
    };
    return textMap[priority] || priority;
};
const getStatusColor = (status) => {
    const colorMap = {
        unassigned: 'gray',
        pending: 'orange',
        in_progress: 'blue',
        completed: 'green',
        overdue: 'red'
    };
    return colorMap[status] || 'default';
};
const getStatusText = (status) => {
    const textMap = {
        unassigned: '待分配',
        pending: '待处理',
        in_progress: '进行中',
        completed: '已完成',
        overdue: '已逾期'
    };
    return textMap[status] || status;
};
// 事件处理函数
const handleCreateTask = () => {
    ant_design_vue_1.message.info('创建新任务');
};
const handleBatchAssign = () => {
    if (selectedRowKeys.value.length === 0) {
        ant_design_vue_1.message.warning('请选择要分配的任务');
        return;
    }
    ant_design_vue_1.message.info(`批量分配 ${selectedRowKeys.value.length} 个任务`);
};
const handleTaskTemplate = () => {
    ant_design_vue_1.message.info('管理任务模板');
};
const handleTaskAnalysis = () => {
    ant_design_vue_1.message.info('查看任务分析');
};
const handleSearch = () => {
    pagination.value.current = 1;
    fetchTasks();
};
const handleReset = () => {
    searchKeyword.value = '';
    selectedStatus.value = undefined;
    selectedAssignee.value = undefined;
    selectedDepartment.value = undefined;
    dateRange.value = [];
    pagination.value.current = 1;
    fetchTasks();
};
const handleRefresh = () => {
    fetchTasks();
};
const handleExport = () => {
    ant_design_vue_1.message.info('导出任务数据');
};
const handleViewDetail = (record) => {
    ant_design_vue_1.message.info(`查看任务详情: ${record.taskName}`);
};
const handleAssign = (record) => {
    ant_design_vue_1.message.info(`分配任务: ${record.taskName}`);
};
const handleEdit = (record) => {
    ant_design_vue_1.message.info(`编辑任务: ${record.taskName}`);
};
const handleDelete = (record) => {
    ant_design_vue_1.message.info(`删除任务: ${record.taskName}`);
};
const handleTableChange = (pag) => {
    pagination.value = { ...pagination.value, ...pag };
    fetchTasks();
};
// 获取数据
const fetchTasks = async () => {
    loading.value = true;
    try {
        await new Promise(resolve => setTimeout(resolve, 1000));
        // 模拟数据
        tasks.value = [
            {
                id: 1,
                taskNumber: 'T2024001',
                taskName: '内科病历质控',
                recordNumber: 'R2024001',
                department: '内科',
                assignee: '张三',
                priority: 'high',
                status: 'in_progress',
                progress: 75,
                createTime: '2024-01-15 09:00:00',
                deadline: '2024-01-20 18:00:00'
            },
            {
                id: 2,
                taskNumber: 'T2024002',
                taskName: '外科病历审核',
                recordNumber: 'R2024002',
                department: '外科',
                assignee: null,
                priority: 'medium',
                status: 'unassigned',
                progress: 0,
                createTime: '2024-01-16 10:00:00',
                deadline: '2024-01-22 18:00:00'
            }
        ];
        pagination.value.total = 100;
    }
    catch (error) {
        ant_design_vue_1.message.error('获取数据失败');
    }
    finally {
        loading.value = false;
    }
};
(0, vue_1.onMounted)(() => {
    fetchTasks();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "all-tasks-container p-8 bg-gray-50 min-h-screen" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-3xl font-bold text-gray-800 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-5 gap-6 mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center" },
});
const __VLS_0 = {}.ProjectOutlined;
/** @type {[typeof __VLS_components.ProjectOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-gray-600 text-xl" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-gray-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-orange-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center" },
});
const __VLS_4 = {}.ClockCircleOutlined;
/** @type {[typeof __VLS_components.ClockCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "text-orange-600 text-xl" },
}));
const __VLS_6 = __VLS_5({
    ...{ class: "text-orange-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-blue-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center" },
});
const __VLS_8 = {}.SyncOutlined;
/** @type {[typeof __VLS_components.SyncOutlined, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ class: "text-blue-600 text-xl" },
}));
const __VLS_10 = __VLS_9({
    ...{ class: "text-blue-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-green-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center" },
});
const __VLS_12 = {}.CheckCircleOutlined;
/** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ class: "text-green-600 text-xl" },
}));
const __VLS_14 = __VLS_13({
    ...{ class: "text-green-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-red-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-red-100 rounded-xl flex items-center justify-center" },
});
const __VLS_16 = {}.ExclamationCircleOutlined;
/** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ class: "text-red-600 text-xl" },
}));
const __VLS_18 = __VLS_17({
    ...{ class: "text-red-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "text-xl font-semibold text-gray-800 mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 md:grid-cols-4 gap-4" },
});
const __VLS_20 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.handleCreateTask)
};
__VLS_23.slots.default;
const __VLS_28 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ class: "text-lg" },
}));
const __VLS_30 = __VLS_29({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_23;
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (__VLS_ctx.handleBatchAssign)
};
__VLS_35.slots.default;
const __VLS_40 = {}.TeamOutlined;
/** @type {[typeof __VLS_components.TeamOutlined, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ class: "text-lg" },
}));
const __VLS_42 = __VLS_41({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_35;
const __VLS_44 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_46 = __VLS_45({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_48;
let __VLS_49;
let __VLS_50;
const __VLS_51 = {
    onClick: (__VLS_ctx.handleTaskTemplate)
};
__VLS_47.slots.default;
const __VLS_52 = {}.FileOutlined;
/** @type {[typeof __VLS_components.FileOutlined, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    ...{ class: "text-lg" },
}));
const __VLS_54 = __VLS_53({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_47;
const __VLS_56 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_58 = __VLS_57({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onClick: (__VLS_ctx.handleTaskAnalysis)
};
__VLS_59.slots.default;
const __VLS_64 = {}.BarChartOutlined;
/** @type {[typeof __VLS_components.BarChartOutlined, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    ...{ class: "text-lg" },
}));
const __VLS_66 = __VLS_65({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_59;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-6 gap-4" },
});
const __VLS_68 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    value: (__VLS_ctx.searchKeyword),
    placeholder: "搜索任务名称、编号",
    ...{ class: "rounded-lg" },
}));
const __VLS_70 = __VLS_69({
    value: (__VLS_ctx.searchKeyword),
    placeholder: "搜索任务名称、编号",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_71.slots;
    const __VLS_72 = {}.SearchOutlined;
    /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ class: "text-gray-400" },
    }));
    const __VLS_74 = __VLS_73({
        ...{ class: "text-gray-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
}
var __VLS_71;
const __VLS_76 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    value: (__VLS_ctx.selectedStatus),
    placeholder: "选择状态",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.statusOptions),
}));
const __VLS_78 = __VLS_77({
    value: (__VLS_ctx.selectedStatus),
    placeholder: "选择状态",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.statusOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
const __VLS_80 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    value: (__VLS_ctx.selectedAssignee),
    placeholder: "选择负责人",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.assigneeOptions),
}));
const __VLS_82 = __VLS_81({
    value: (__VLS_ctx.selectedAssignee),
    placeholder: "选择负责人",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.assigneeOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
const __VLS_84 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "选择科室",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.departmentOptions),
}));
const __VLS_86 = __VLS_85({
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "选择科室",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.departmentOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
const __VLS_88 = {}.ARangePicker;
/** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    value: (__VLS_ctx.dateRange),
    placeholder: "选择日期范围",
    ...{ class: "rounded-lg" },
}));
const __VLS_90 = __VLS_89({
    value: (__VLS_ctx.dateRange),
    placeholder: "选择日期范围",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex space-x-2" },
});
const __VLS_92 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}));
const __VLS_94 = __VLS_93({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
let __VLS_96;
let __VLS_97;
let __VLS_98;
const __VLS_99 = {
    onClick: (__VLS_ctx.handleSearch)
};
__VLS_95.slots.default;
const __VLS_100 = {}.SearchOutlined;
/** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({}));
const __VLS_102 = __VLS_101({}, ...__VLS_functionalComponentArgsRest(__VLS_101));
var __VLS_95;
const __VLS_104 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}));
const __VLS_106 = __VLS_105({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
let __VLS_108;
let __VLS_109;
let __VLS_110;
const __VLS_111 = {
    onClick: (__VLS_ctx.handleReset)
};
__VLS_107.slots.default;
const __VLS_112 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
var __VLS_107;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "text-xl font-semibold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex space-x-2" },
});
const __VLS_116 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    ...{ class: "rounded-lg" },
}));
const __VLS_118 = __VLS_117({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
let __VLS_120;
let __VLS_121;
let __VLS_122;
const __VLS_123 = {
    onClick: (__VLS_ctx.handleRefresh)
};
__VLS_119.slots.default;
const __VLS_124 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
var __VLS_119;
const __VLS_128 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}));
const __VLS_130 = __VLS_129({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
let __VLS_132;
let __VLS_133;
let __VLS_134;
const __VLS_135 = {
    onClick: (__VLS_ctx.handleExport)
};
__VLS_131.slots.default;
const __VLS_136 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({}));
const __VLS_138 = __VLS_137({}, ...__VLS_functionalComponentArgsRest(__VLS_137));
var __VLS_131;
const __VLS_140 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.tasks),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}));
const __VLS_142 = __VLS_141({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.tasks),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowSelection: (__VLS_ctx.rowSelection),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
let __VLS_144;
let __VLS_145;
let __VLS_146;
const __VLS_147 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_143.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_143.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'priority') {
        const __VLS_148 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }));
        const __VLS_150 = __VLS_149({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_149));
        __VLS_151.slots.default;
        (__VLS_ctx.getPriorityText(record.priority));
        var __VLS_151;
    }
    if (column.key === 'status') {
        const __VLS_152 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
            color: (__VLS_ctx.getStatusColor(record.status)),
        }));
        const __VLS_154 = __VLS_153({
            color: (__VLS_ctx.getStatusColor(record.status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_153));
        __VLS_155.slots.default;
        (__VLS_ctx.getStatusText(record.status));
        var __VLS_155;
    }
    if (column.key === 'progress') {
        const __VLS_156 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
            percent: (record.progress),
            size: "small",
        }));
        const __VLS_158 = __VLS_157({
            percent: (record.progress),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    }
    if (column.key === 'assignee') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center" },
        });
        const __VLS_160 = {}.AAvatar;
        /** @type {[typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, ]} */ ;
        // @ts-ignore
        const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
            size: "small",
            ...{ class: "mr-2" },
        }));
        const __VLS_162 = __VLS_161({
            size: "small",
            ...{ class: "mr-2" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_161));
        __VLS_163.slots.default;
        (record.assignee?.charAt(0));
        var __VLS_163;
        (record.assignee || '未分配');
    }
    if (column.key === 'action') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex space-x-2" },
        });
        const __VLS_164 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_166 = __VLS_165({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_165));
        let __VLS_168;
        let __VLS_169;
        let __VLS_170;
        const __VLS_171 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleViewDetail(record);
            }
        };
        __VLS_167.slots.default;
        const __VLS_172 = {}.EyeOutlined;
        /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({}));
        const __VLS_174 = __VLS_173({}, ...__VLS_functionalComponentArgsRest(__VLS_173));
        var __VLS_167;
        if (!record.assignee) {
            const __VLS_176 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_178 = __VLS_177({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_177));
            let __VLS_180;
            let __VLS_181;
            let __VLS_182;
            const __VLS_183 = {
                onClick: (...[$event]) => {
                    if (!(column.key === 'action'))
                        return;
                    if (!(!record.assignee))
                        return;
                    __VLS_ctx.handleAssign(record);
                }
            };
            __VLS_179.slots.default;
            const __VLS_184 = {}.UserAddOutlined;
            /** @type {[typeof __VLS_components.UserAddOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({}));
            const __VLS_186 = __VLS_185({}, ...__VLS_functionalComponentArgsRest(__VLS_185));
            var __VLS_179;
        }
        const __VLS_188 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_190 = __VLS_189({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_189));
        let __VLS_192;
        let __VLS_193;
        let __VLS_194;
        const __VLS_195 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleEdit(record);
            }
        };
        __VLS_191.slots.default;
        const __VLS_196 = {}.EditOutlined;
        /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({}));
        const __VLS_198 = __VLS_197({}, ...__VLS_functionalComponentArgsRest(__VLS_197));
        var __VLS_191;
        const __VLS_200 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            danger: true,
        }));
        const __VLS_202 = __VLS_201({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_201));
        let __VLS_204;
        let __VLS_205;
        let __VLS_206;
        const __VLS_207 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleDelete(record);
            }
        };
        __VLS_203.slots.default;
        const __VLS_208 = {}.DeleteOutlined;
        /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({}));
        const __VLS_210 = __VLS_209({}, ...__VLS_functionalComponentArgsRest(__VLS_209));
        var __VLS_203;
    }
}
var __VLS_143;
/** @type {__VLS_StyleScopedClasses['all-tasks-container']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-5']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-orange-600']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-orange-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-orange-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-green-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-6']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ProjectOutlined: icons_vue_1.ProjectOutlined,
            ClockCircleOutlined: icons_vue_1.ClockCircleOutlined,
            SyncOutlined: icons_vue_1.SyncOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            TeamOutlined: icons_vue_1.TeamOutlined,
            FileOutlined: icons_vue_1.FileOutlined,
            BarChartOutlined: icons_vue_1.BarChartOutlined,
            SearchOutlined: icons_vue_1.SearchOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            UserAddOutlined: icons_vue_1.UserAddOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            loading: loading,
            searchKeyword: searchKeyword,
            selectedStatus: selectedStatus,
            selectedAssignee: selectedAssignee,
            selectedDepartment: selectedDepartment,
            dateRange: dateRange,
            tasks: tasks,
            pagination: pagination,
            rowSelection: rowSelection,
            statusOptions: statusOptions,
            assigneeOptions: assigneeOptions,
            departmentOptions: departmentOptions,
            columns: columns,
            getPriorityColor: getPriorityColor,
            getPriorityText: getPriorityText,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
            handleCreateTask: handleCreateTask,
            handleBatchAssign: handleBatchAssign,
            handleTaskTemplate: handleTaskTemplate,
            handleTaskAnalysis: handleTaskAnalysis,
            handleSearch: handleSearch,
            handleReset: handleReset,
            handleRefresh: handleRefresh,
            handleExport: handleExport,
            handleViewDetail: handleViewDetail,
            handleAssign: handleAssign,
            handleEdit: handleEdit,
            handleDelete: handleDelete,
            handleTableChange: handleTableChange,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
