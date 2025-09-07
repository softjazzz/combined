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
const selectedStatus = (0, vue_1.ref)(undefined);
const selectedPriority = (0, vue_1.ref)(undefined);
const dateRange = (0, vue_1.ref)(: any[]);
const tasks = (0, vue_1.ref)(: any[]);
// 分页配置
const pagination = (0, vue_1.ref)({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total) => `共 ${total} 条任务`
});
// 状态选项
const statusOptions = [
    { value: 'pending', label: '待处理' },
    { value: 'in_progress', label: '进行中' },
    { value: 'completed', label: '已完成' },
    { value: 'overdue', label: '已逾期' }
];
// 优先级选项
const priorityOptions = [
    { value: 'high', label: '高' },
    { value: 'medium', label: '中' },
    { value: 'low', label: '低' }
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
        title: '截止时间',
        dataIndex: 'deadline',
        key: 'deadline',
        width: 150
    },
    {
        title: '操作',
        key: 'action',
        width: 200,
        fixed: 'right'
    }
];
// 获取优先级颜色和文本
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
// 获取状态颜色和文本
const getStatusColor = (status) => {
    const colorMap = {
        pending: 'orange',
        in_progress: 'blue',
        completed: 'green',
        overdue: 'red'
    };
    return colorMap[status] || 'default';
};
const getStatusText = (status) => {
    const textMap = {
        pending: '待处理',
        in_progress: '进行中',
        completed: '已完成',
        overdue: '已逾期'
    };
    return textMap[status] || status;
};
// 事件处理函数
const handleStartTask = () => {
    ant_design_vue_1.message.info('开始新任务');
};
const handleViewPending = () => {
    selectedStatus.value = 'pending';
    handleFilter();
};
const handleViewCompleted = () => {
    selectedStatus.value = 'completed';
    handleFilter();
};
const handleTaskReport = () => {
    ant_design_vue_1.message.info('查看任务报告');
};
const handleFilter = () => {
    pagination.value.current = 1;
    fetchTasks();
};
const handleResetFilter = () => {
    selectedStatus.value = undefined;
    selectedPriority.value = undefined;
    dateRange.value = [];
    pagination.value.current = 1;
    fetchTasks();
};
const handleRefresh = () => {
    fetchTasks();
};
const handleStartWork = (record) => {
    ant_design_vue_1.message.info(`开始任务: ${record.taskName}`);
};
const handleContinueWork = (record) => {
    ant_design_vue_1.message.info(`继续任务: ${record.taskName}`);
};
const handleViewDetail = (record) => {
    ant_design_vue_1.message.info(`查看任务详情: ${record.taskName}`);
};
const handleSubmit = (record) => {
    ant_design_vue_1.message.info(`提交任务: ${record.taskName}`);
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
                priority: 'high',
                status: 'pending',
                progress: 0,
                deadline: '2024-01-20 18:00:00'
            },
            {
                id: 2,
                taskNumber: 'T2024002',
                taskName: '外科病历审核',
                recordNumber: 'R2024002',
                priority: 'medium',
                status: 'in_progress',
                progress: 65,
                deadline: '2024-01-22 18:00:00'
            }
        ];
        pagination.value.total = 50;
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
    ...{ class: "my-tasks-container p-8 bg-gray-50 min-h-screen" },
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
    ...{ class: "grid grid-cols-1 md:grid-cols-4 gap-6 mb-8" },
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
    ...{ class: "text-3xl font-bold text-orange-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center" },
});
const __VLS_0 = {}.ClockCircleOutlined;
/** @type {[typeof __VLS_components.ClockCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-orange-600 text-xl" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-orange-600 text-xl" },
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
    ...{ class: "text-3xl font-bold text-blue-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center" },
});
const __VLS_4 = {}.SyncOutlined;
/** @type {[typeof __VLS_components.SyncOutlined, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "text-blue-600 text-xl" },
}));
const __VLS_6 = __VLS_5({
    ...{ class: "text-blue-600 text-xl" },
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
    ...{ class: "text-3xl font-bold text-green-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center" },
});
const __VLS_8 = {}.CheckCircleOutlined;
/** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ class: "text-green-600 text-xl" },
}));
const __VLS_10 = __VLS_9({
    ...{ class: "text-green-600 text-xl" },
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
    ...{ class: "text-3xl font-bold text-purple-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center" },
});
const __VLS_12 = {}.TrophyOutlined;
/** @type {[typeof __VLS_components.TrophyOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ class: "text-purple-600 text-xl" },
}));
const __VLS_14 = __VLS_13({
    ...{ class: "text-purple-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "text-xl font-semibold text-gray-800 mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 md:grid-cols-4 gap-4" },
});
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.handleStartTask)
};
__VLS_19.slots.default;
const __VLS_24 = {}.PlayCircleOutlined;
/** @type {[typeof __VLS_components.PlayCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ class: "text-lg" },
}));
const __VLS_26 = __VLS_25({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_19;
const __VLS_28 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_30 = __VLS_29({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
let __VLS_32;
let __VLS_33;
let __VLS_34;
const __VLS_35 = {
    onClick: (__VLS_ctx.handleViewPending)
};
__VLS_31.slots.default;
const __VLS_36 = {}.ClockCircleOutlined;
/** @type {[typeof __VLS_components.ClockCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ class: "text-lg" },
}));
const __VLS_38 = __VLS_37({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_31;
const __VLS_40 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (__VLS_ctx.handleViewCompleted)
};
__VLS_43.slots.default;
const __VLS_48 = {}.CheckCircleOutlined;
/** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ class: "text-lg" },
}));
const __VLS_50 = __VLS_49({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_43;
const __VLS_52 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}));
const __VLS_54 = __VLS_53({
    ...{ 'onClick': {} },
    size: "large",
    ...{ class: "rounded-lg h-16" },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
let __VLS_56;
let __VLS_57;
let __VLS_58;
const __VLS_59 = {
    onClick: (__VLS_ctx.handleTaskReport)
};
__VLS_55.slots.default;
const __VLS_60 = {}.BarChartOutlined;
/** @type {[typeof __VLS_components.BarChartOutlined, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    ...{ class: "text-lg" },
}));
const __VLS_62 = __VLS_61({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "ml-2" },
});
var __VLS_55;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6 mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-4 gap-4" },
});
const __VLS_64 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    value: (__VLS_ctx.selectedStatus),
    placeholder: "选择状态",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.statusOptions),
}));
const __VLS_66 = __VLS_65({
    value: (__VLS_ctx.selectedStatus),
    placeholder: "选择状态",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.statusOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
const __VLS_68 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    value: (__VLS_ctx.selectedPriority),
    placeholder: "选择优先级",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.priorityOptions),
}));
const __VLS_70 = __VLS_69({
    value: (__VLS_ctx.selectedPriority),
    placeholder: "选择优先级",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.priorityOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
const __VLS_72 = {}.ARangePicker;
/** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    value: (__VLS_ctx.dateRange),
    placeholder: "选择日期范围",
    ...{ class: "rounded-lg" },
}));
const __VLS_74 = __VLS_73({
    value: (__VLS_ctx.dateRange),
    placeholder: "选择日期范围",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex space-x-2" },
});
const __VLS_76 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}));
const __VLS_78 = __VLS_77({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
let __VLS_80;
let __VLS_81;
let __VLS_82;
const __VLS_83 = {
    onClick: (__VLS_ctx.handleFilter)
};
__VLS_79.slots.default;
const __VLS_84 = {}.FilterOutlined;
/** @type {[typeof __VLS_components.FilterOutlined, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
var __VLS_79;
const __VLS_88 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}));
const __VLS_90 = __VLS_89({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
let __VLS_92;
let __VLS_93;
let __VLS_94;
const __VLS_95 = {
    onClick: (__VLS_ctx.handleResetFilter)
};
__VLS_91.slots.default;
const __VLS_96 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({}));
const __VLS_98 = __VLS_97({}, ...__VLS_functionalComponentArgsRest(__VLS_97));
var __VLS_91;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "text-xl font-semibold text-gray-800" },
});
const __VLS_100 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    ...{ class: "rounded-lg" },
}));
const __VLS_102 = __VLS_101({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
let __VLS_104;
let __VLS_105;
let __VLS_106;
const __VLS_107 = {
    onClick: (__VLS_ctx.handleRefresh)
};
__VLS_103.slots.default;
const __VLS_108 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({}));
const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
var __VLS_103;
const __VLS_112 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.tasks),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}));
const __VLS_114 = __VLS_113({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.tasks),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
let __VLS_116;
let __VLS_117;
let __VLS_118;
const __VLS_119 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_115.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_115.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'priority') {
        const __VLS_120 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }));
        const __VLS_122 = __VLS_121({
            color: (__VLS_ctx.getPriorityColor(record.priority)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        (__VLS_ctx.getPriorityText(record.priority));
        var __VLS_123;
    }
    if (column.key === 'status') {
        const __VLS_124 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
            color: (__VLS_ctx.getStatusColor(record.status)),
        }));
        const __VLS_126 = __VLS_125({
            color: (__VLS_ctx.getStatusColor(record.status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_125));
        __VLS_127.slots.default;
        (__VLS_ctx.getStatusText(record.status));
        var __VLS_127;
    }
    if (column.key === 'progress') {
        const __VLS_128 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
            percent: (record.progress),
            size: "small",
        }));
        const __VLS_130 = __VLS_129({
            percent: (record.progress),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    }
    if (column.key === 'action') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex space-x-2" },
        });
        if (record.status === 'pending') {
            const __VLS_132 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_134 = __VLS_133({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_133));
            let __VLS_136;
            let __VLS_137;
            let __VLS_138;
            const __VLS_139 = {
                onClick: (...[$event]) => {
                    if (!(column.key === 'action'))
                        return;
                    if (!(record.status === 'pending'))
                        return;
                    __VLS_ctx.handleStartWork(record);
                }
            };
            __VLS_135.slots.default;
            const __VLS_140 = {}.PlayCircleOutlined;
            /** @type {[typeof __VLS_components.PlayCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({}));
            const __VLS_142 = __VLS_141({}, ...__VLS_functionalComponentArgsRest(__VLS_141));
            var __VLS_135;
        }
        if (record.status === 'in_progress') {
            const __VLS_144 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_146 = __VLS_145({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_145));
            let __VLS_148;
            let __VLS_149;
            let __VLS_150;
            const __VLS_151 = {
                onClick: (...[$event]) => {
                    if (!(column.key === 'action'))
                        return;
                    if (!(record.status === 'in_progress'))
                        return;
                    __VLS_ctx.handleContinueWork(record);
                }
            };
            __VLS_147.slots.default;
            const __VLS_152 = {}.EditOutlined;
            /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({}));
            const __VLS_154 = __VLS_153({}, ...__VLS_functionalComponentArgsRest(__VLS_153));
            var __VLS_147;
        }
        const __VLS_156 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_158 = __VLS_157({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_157));
        let __VLS_160;
        let __VLS_161;
        let __VLS_162;
        const __VLS_163 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleViewDetail(record);
            }
        };
        __VLS_159.slots.default;
        const __VLS_164 = {}.EyeOutlined;
        /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({}));
        const __VLS_166 = __VLS_165({}, ...__VLS_functionalComponentArgsRest(__VLS_165));
        var __VLS_159;
        if (record.status === 'in_progress') {
            const __VLS_168 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_170 = __VLS_169({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_169));
            let __VLS_172;
            let __VLS_173;
            let __VLS_174;
            const __VLS_175 = {
                onClick: (...[$event]) => {
                    if (!(column.key === 'action'))
                        return;
                    if (!(record.status === 'in_progress'))
                        return;
                    __VLS_ctx.handleSubmit(record);
                }
            };
            __VLS_171.slots.default;
            const __VLS_176 = {}.CheckOutlined;
            /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({}));
            const __VLS_178 = __VLS_177({}, ...__VLS_functionalComponentArgsRest(__VLS_177));
            var __VLS_171;
        }
    }
}
var __VLS_115;
/** @type {__VLS_StyleScopedClasses['my-tasks-container']} */ ;
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
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
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
/** @type {__VLS_StyleScopedClasses['text-purple-600']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-600']} */ ;
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
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
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
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ClockCircleOutlined: icons_vue_1.ClockCircleOutlined,
            SyncOutlined: icons_vue_1.SyncOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            TrophyOutlined: icons_vue_1.TrophyOutlined,
            PlayCircleOutlined: icons_vue_1.PlayCircleOutlined,
            BarChartOutlined: icons_vue_1.BarChartOutlined,
            FilterOutlined: icons_vue_1.FilterOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            CheckOutlined: icons_vue_1.CheckOutlined,
            loading: loading,
            selectedStatus: selectedStatus,
            selectedPriority: selectedPriority,
            dateRange: dateRange,
            tasks: tasks,
            pagination: pagination,
            statusOptions: statusOptions,
            priorityOptions: priorityOptions,
            columns: columns,
            getPriorityColor: getPriorityColor,
            getPriorityText: getPriorityText,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
            handleStartTask: handleStartTask,
            handleViewPending: handleViewPending,
            handleViewCompleted: handleViewCompleted,
            handleTaskReport: handleTaskReport,
            handleFilter: handleFilter,
            handleResetFilter: handleResetFilter,
            handleRefresh: handleRefresh,
            handleStartWork: handleStartWork,
            handleContinueWork: handleContinueWork,
            handleViewDetail: handleViewDetail,
            handleSubmit: handleSubmit,
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
