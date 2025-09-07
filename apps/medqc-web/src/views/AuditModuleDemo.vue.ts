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
import audit_task_service_1 from '@/services/audit-task-service';
import notification_service_1 from '@/services/notification-service';
const MultiLevelAuditTabs_vue_1 = __importDefault(require("@/components/audit/MultiLevelAuditTabs.vue"));
const NotificationCenter_vue_1 = __importDefault(require("@/components/notification/NotificationCenter.vue"));
// 状态管理
const activeTab = (0, vue_1.ref)('task-management');
const initializing = (0, vue_1.ref)(false);
const selectedTaskItem = (0, vue_1.ref)('');
// 演示数据
const demoTasks = (0, vue_1.ref)(: any[]);
const demoTaskItems = (0, vue_1.ref)(: any[]);
const demoNotificationCount = (0, vue_1.ref)(0);
const aiAnalysisCount = (0, vue_1.ref)(0);
// 计算属性
const getCurrentTaskItem = () => {
    return demoTaskItems.value.find(item => item.id === selectedTaskItem.value);
};
// 方法
const initializeDemoData = async () => {
    try {
        initializing.value = true;
        ant_design_vue_1.message.loading('正在初始化演示数据...', 0);
        // 1. 创建演示审核任务
        await createDemoAuditTasks();
        // 2. 生成演示任务项目
        await generateDemoTaskItems();
        // 3. 创建演示通知
        await createDemoNotifications();
        ant_design_vue_1.message.destroy();
        ant_design_vue_1.message.success('演示数据初始化完成！');
    }
    catch (error) {
        ant_design_vue_1.message.destroy();
        ant_design_vue_1.message.error(`初始化失败: ${error.message}`);
    }
    finally {
        initializing.value = false;
    }
};
const createDemoAuditTasks = async () => {
    const demoTaskConfigs = [
        {
            task_name: '2024年第四季度常规质控',
            task_type: 'routine',
            audit_level: 'department',
            audit_scope: {
                departments: ['dept_001', 'dept_002'],
                document_types: ['admission_record', 'discharge_summary'],
                date_range: {
                    start: '2024-10-01',
                    end: '2024-12-31'
                }
            },
            sampling_config: {
                sampling_method: 'stratified',
                sampling_ratio: 0.1,
                stratification_rules: [
                    {
                        stratum_name: 'A',
                        criteria: { risk_level: 'A' },
                        sample_ratio: 0.3,
                        min_sample_size: 5
                    },
                    {
                        stratum_name: 'B',
                        criteria: { risk_level: 'B' },
                        sample_ratio: 0.2,
                        min_sample_size: 3
                    }
                ]
            },
            planned_start_date: '2024-12-01',
            planned_end_date: '2024-12-31',
            assigned_reviewers: ['reviewer_001', 'reviewer_002'],
            description: '第四季度常规质控任务，重点关注病历完整性和规范性'
        },
        {
            task_name: '专项质控-重症医学科',
            task_type: 'special',
            audit_level: 'expert',
            audit_scope: {
                departments: ['icu_001'],
                document_types: ['icu_record', 'critical_care_record'],
                date_range: {
                    start: '2024-11-01',
                    end: '2024-12-31'
                }
            },
            sampling_config: {
                sampling_method: 'risk_based',
                total_sample_size: 50,
                risk_based_weights: {
                    risk_A_weight: 0.6,
                    risk_B_weight: 0.3,
                    risk_C_weight: 0.1
                }
            },
            planned_start_date: '2024-12-15',
            planned_end_date: '2025-01-15',
            assigned_reviewers: ['expert_001'],
            description: '重症医学科专项质控，关注危重患者病历质量'
        }
    ];
    for (const config of demoTaskConfigs) {
        try {
            const task = await audit_task_service_1.auditTaskService.createAuditTask(config);
            demoTasks.value.push(task);
        }
        catch (error) {
            console.warn('创建演示任务失败:', error);
        }
    }
};
const generateDemoTaskItems = () => {
    const demoItems = [
        {
            id: 'item_001',
            task_id: demoTasks.value[0]?.id || 'task_001',
            patient_id: 'patient_001',
            medical_record_id: 'record_001',
            patient_name: '张三',
            admission_date: '2024-11-15',
            discharge_date: '2024-11-20',
            department_id: 'dept_001',
            department_name: '内科',
            risk_level: 'B',
            complexity_score: 75,
            audit_status: 'pending',
            defect_count: 0,
            has_critical_defects: false,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
        },
        {
            id: 'item_002',
            task_id: demoTasks.value[0]?.id || 'task_001',
            patient_id: 'patient_002',
            medical_record_id: 'record_002',
            patient_name: '李四',
            admission_date: '2024-11-18',
            discharge_date: '2024-11-25',
            department_id: 'dept_002',
            department_name: '外科',
            risk_level: 'A',
            complexity_score: 90,
            audit_status: 'in_review',
            defect_count: 2,
            has_critical_defects: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
        }
    ];
    demoTaskItems.value = demoItems;
    // 默认选择第一个项目
    if (demoItems.length > 0) {
        selectedTaskItem.value = demoItems[0].id;
    }
};
const createDemoNotifications = async () => {
    const demoNotifications = [
        {
            type: 'rectification_required',
            recipientType: 'clinician',
            relatedData: {
                patient_id: 'patient_001',
                medical_record_id: 'record_001',
                defect_id: 'defect_001'
            },
            customContent: {
                title: '病历整改通知',
                content: '您的患者张三的病历存在完整性问题，请及时整改。',
                priority: 'high'
            }
        },
        {
            type: 'task_assigned',
            recipientType: 'reviewer',
            relatedData: {
                audit_task_id: demoTasks.value[0]?.id || 'task_001'
            },
            customContent: {
                title: '新审核任务分配',
                content: '您有新的审核任务需要处理，请及时查看。',
                priority: 'normal'
            }
        }
    ];
    for (const notificationConfig of demoNotifications) {
        try {
            await notification_service_1.notificationService.sendNotification('demo_user_001', notificationConfig.recipientType, notificationConfig.type, notificationConfig.relatedData, notificationConfig.customContent);
            demoNotificationCount.value++;
        }
        catch (error) {
            console.warn('创建演示通知失败:', error);
        }
    }
};
const resetDemo = () => {
    demoTasks.value = [];
    demoTaskItems.value = [];
    demoNotificationCount.value = 0;
    aiAnalysisCount.value = 0;
    selectedTaskItem.value = '';
    ant_design_vue_1.message.success('演示已重置');
};
const handleTaskCreated = (task) => {
    demoTasks.value.push(task);
    ant_design_vue_1.message.success('演示任务创建成功');
};
const handleTaskSelected = (task) => {
    activeTab.value = 'multi-level-audit';
    ant_design_vue_1.message.info(`已选择任务: ${task.task_name}`);
};
const handleTaskItemChange = (itemId) => {
    selectedTaskItem.value = itemId;
};
const handleAuditResultUpdated = (level: any,  result: any) => {
    ant_design_vue_1.message.success(`${level}级审核结果已更新`);
};
const handleAuditResultSubmitted = (level, result) => {
    ant_design_vue_1.message.success(`${level}级审核结果已提交`);
};
const handleNotificationSent = (notification) => {
    demoNotificationCount.value++;
    ant_design_vue_1.message.success('演示通知已发送');
};
const handleDefectsDetected = (defects) => {
    aiAnalysisCount.value++;
    ant_design_vue_1.message.success(`AI检测到 ${defects.length} 个潜在缺陷`);
};
const handleMessageGenerated = (message) => {
    aiAnalysisCount.value++;
    message.success('智能消息生成成功');
};
const handleIntegrationTested = (result) => {
    ant_design_vue_1.message.success('LLM集成测试完成');
};
const handleRealtimeTested = (result) => {
    ant_design_vue_1.message.success('实时功能测试完成');
};
const exportDemoData = () => {
    const demoData = {
        tasks: demoTasks.value,
        taskItems: demoTaskItems.value,
        notificationCount: demoNotificationCount.value,
        aiAnalysisCount: aiAnalysisCount.value,
        timestamp: new Date().toISOString()
    };
    const blob = new Blob([JSON.stringify(demoData, null, 2)], {
        type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `audit-module-demo-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
    ant_design_vue_1.message.success('演示数据已导出');
};
const viewDemoLogs = () => {
    ant_design_vue_1.message.info('演示日志功能开发中...');
};
// 生命周期
(0, vue_1.onMounted)(() => {
    // 自动初始化一些基础演示数据
    generateDemoTaskItems();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['demo-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-section']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-header']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-module-demo']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-content']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-section']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "audit-module-demo" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
const __VLS_0 = {}.AuditOutlined;
/** @type {[typeof __VLS_components.AuditOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "page-description" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-actions" },
});
const __VLS_4 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.initializing),
}));
const __VLS_10 = __VLS_9({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.initializing),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
let __VLS_12;
let __VLS_13;
let __VLS_14;
const __VLS_15 = {
    onClick: (__VLS_ctx.initializeDemoData)
};
__VLS_11.slots.default;
const __VLS_16 = {}.DatabaseOutlined;
/** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
var __VLS_11;
const __VLS_20 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    type: "dashed",
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    type: "dashed",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.resetDemo)
};
__VLS_23.slots.default;
const __VLS_28 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
var __VLS_23;
var __VLS_7;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-content" },
});
const __VLS_32 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    activeKey: (__VLS_ctx.activeTab),
    size: "large",
    ...{ class: "demo-tabs" },
}));
const __VLS_34 = __VLS_33({
    activeKey: (__VLS_ctx.activeTab),
    size: "large",
    ...{ class: "demo-tabs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    key: "task-management",
    tab: "审核任务管理",
}));
const __VLS_38 = __VLS_37({
    key: "task-management",
    tab: "审核任务管理",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_39.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_40 = {}.ProjectOutlined;
    /** @type {[typeof __VLS_components.ProjectOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
    const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_44 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ class: "demo-card" },
}));
const __VLS_46 = __VLS_45({
    ...{ class: "demo-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.CreateAuditTaskForm;
/** @type {[typeof __VLS_components.CreateAuditTaskForm, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onTaskCreated': {} },
    ...{ 'onDemoMode': {} },
}));
const __VLS_50 = __VLS_49({
    ...{ 'onTaskCreated': {} },
    ...{ 'onDemoMode': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onTaskCreated: (__VLS_ctx.handleTaskCreated)
};
const __VLS_56 = {
    onDemoMode: (...[$event]) => {
        true;
    }
};
var __VLS_51;
var __VLS_47;
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_57 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
    ...{ class: "demo-card" },
}));
const __VLS_59 = __VLS_58({
    ...{ class: "demo-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_58));
__VLS_60.slots.default;
const __VLS_61 = {}.AuditTaskList;
/** @type {[typeof __VLS_components.AuditTaskList, ]} */ ;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
    ...{ 'onTaskSelected': {} },
    tasks: (__VLS_ctx.demoTasks),
    demoMode: true,
}));
const __VLS_63 = __VLS_62({
    ...{ 'onTaskSelected': {} },
    tasks: (__VLS_ctx.demoTasks),
    demoMode: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
let __VLS_65;
let __VLS_66;
let __VLS_67;
const __VLS_68 = {
    onTaskSelected: (__VLS_ctx.handleTaskSelected)
};
var __VLS_64;
var __VLS_60;
var __VLS_39;
const __VLS_69 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
    key: "multi-level-audit",
    tab: "多级审核",
}));
const __VLS_71 = __VLS_70({
    key: "multi-level-audit",
    tab: "多级审核",
}, ...__VLS_functionalComponentArgsRest(__VLS_70));
__VLS_72.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_72.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_73 = {}.TeamOutlined;
    /** @type {[typeof __VLS_components.TeamOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({}));
    const __VLS_75 = __VLS_74({}, ...__VLS_functionalComponentArgsRest(__VLS_74));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_77 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedTaskItem),
    placeholder: "选择审核项目",
    ...{ style: {} },
}));
const __VLS_79 = __VLS_78({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedTaskItem),
    placeholder: "选择审核项目",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_78));
let __VLS_81;
let __VLS_82;
let __VLS_83;
const __VLS_84 = {
    onChange: (__VLS_ctx.handleTaskItemChange)
};
__VLS_80.slots.default;
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.demoTaskItems))) {
    const __VLS_85 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
        key: (item.id),
        value: (item.id),
    }));
    const __VLS_87 = __VLS_86({
        key: (item.id),
        value: (item.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_86));
    __VLS_88.slots.default;
    (item.patient_name);
    (item.department_name);
    var __VLS_88;
}
var __VLS_80;
if (__VLS_ctx.selectedTaskItem) {
    const __VLS_89 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({
        ...{ class: "demo-card" },
    }));
    const __VLS_91 = __VLS_90({
        ...{ class: "demo-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_90));
    __VLS_92.slots.default;
    /** @type {[typeof MultiLevelAuditTabs, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(MultiLevelAuditTabs_vue_1.default, new MultiLevelAuditTabs_vue_1.default({
        ...{ 'onResultUpdated': {} },
        ...{ 'onResultSubmitted': {} },
        taskItemId: (__VLS_ctx.selectedTaskItem),
        taskItem: (__VLS_ctx.getCurrentTaskItem()),
    }));
    const __VLS_94 = __VLS_93({
        ...{ 'onResultUpdated': {} },
        ...{ 'onResultSubmitted': {} },
        taskItemId: (__VLS_ctx.selectedTaskItem),
        taskItem: (__VLS_ctx.getCurrentTaskItem()),
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    let __VLS_96;
    let __VLS_97;
    let __VLS_98;
    const __VLS_99 = {
        onResultUpdated: (__VLS_ctx.handleAuditResultUpdated)
    };
    const __VLS_100 = {
        onResultSubmitted: (__VLS_ctx.handleAuditResultSubmitted)
    };
    var __VLS_95;
    var __VLS_92;
}
var __VLS_72;
const __VLS_101 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({
    key: "notifications",
    tab: "消息通知",
}));
const __VLS_103 = __VLS_102({
    key: "notifications",
    tab: "消息通知",
}, ...__VLS_functionalComponentArgsRest(__VLS_102));
__VLS_104.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_104.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_105 = {}.BellOutlined;
    /** @type {[typeof __VLS_components.BellOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({}));
    const __VLS_107 = __VLS_106({}, ...__VLS_functionalComponentArgsRest(__VLS_106));
    const __VLS_109 = {}.ABadge;
    /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
    // @ts-ignore
    const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
        count: (__VLS_ctx.demoNotificationCount),
        offset: ([10, -5]),
    }));
    const __VLS_111 = __VLS_110({
        count: (__VLS_ctx.demoNotificationCount),
        offset: ([10, -5]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_110));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-section" },
});
const __VLS_113 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
    gutter: (24),
}));
const __VLS_115 = __VLS_114({
    gutter: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
__VLS_116.slots.default;
const __VLS_117 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({
    span: (16),
}));
const __VLS_119 = __VLS_118({
    span: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_118));
__VLS_120.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_121 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
    ...{ class: "demo-card notification-demo" },
}));
const __VLS_123 = __VLS_122({
    ...{ class: "demo-card notification-demo" },
}, ...__VLS_functionalComponentArgsRest(__VLS_122));
__VLS_124.slots.default;
/** @type {[typeof NotificationCenter, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(NotificationCenter_vue_1.default, new NotificationCenter_vue_1.default({}));
const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
var __VLS_124;
var __VLS_120;
const __VLS_128 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    span: (8),
}));
const __VLS_130 = __VLS_129({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_132 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
    ...{ class: "demo-card" },
}));
const __VLS_134 = __VLS_133({
    ...{ class: "demo-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_133));
__VLS_135.slots.default;
const __VLS_136 = {}.NotificationTestPanel;
/** @type {[typeof __VLS_components.NotificationTestPanel, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    ...{ 'onNotificationSent': {} },
}));
const __VLS_138 = __VLS_137({
    ...{ 'onNotificationSent': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
let __VLS_140;
let __VLS_141;
let __VLS_142;
const __VLS_143 = {
    onNotificationSent: (__VLS_ctx.handleNotificationSent)
};
var __VLS_139;
var __VLS_135;
var __VLS_131;
var __VLS_116;
var __VLS_104;
const __VLS_144 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
    key: "ai-assistance",
    tab: "AI辅助",
}));
const __VLS_146 = __VLS_145({
    key: "ai-assistance",
    tab: "AI辅助",
}, ...__VLS_functionalComponentArgsRest(__VLS_145));
__VLS_147.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_147.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_148 = {}.RobotOutlined;
    /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({}));
    const __VLS_150 = __VLS_149({}, ...__VLS_functionalComponentArgsRest(__VLS_149));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_152 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
    ...{ class: "demo-card" },
}));
const __VLS_154 = __VLS_153({
    ...{ class: "demo-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_153));
__VLS_155.slots.default;
const __VLS_156 = {}.AIDefectDetectionDemo;
/** @type {[typeof __VLS_components.AIDefectDetectionDemo, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    ...{ 'onDefectsDetected': {} },
}));
const __VLS_158 = __VLS_157({
    ...{ 'onDefectsDetected': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
let __VLS_160;
let __VLS_161;
let __VLS_162;
const __VLS_163 = {
    onDefectsDetected: (__VLS_ctx.handleDefectsDetected)
};
var __VLS_159;
var __VLS_155;
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_164 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    ...{ class: "demo-card" },
}));
const __VLS_166 = __VLS_165({
    ...{ class: "demo-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
__VLS_167.slots.default;
const __VLS_168 = {}.SmartMessageGeneratorDemo;
/** @type {[typeof __VLS_components.SmartMessageGeneratorDemo, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    ...{ 'onMessageGenerated': {} },
}));
const __VLS_170 = __VLS_169({
    ...{ 'onMessageGenerated': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
let __VLS_172;
let __VLS_173;
let __VLS_174;
const __VLS_175 = {
    onMessageGenerated: (__VLS_ctx.handleMessageGenerated)
};
var __VLS_171;
var __VLS_167;
var __VLS_147;
const __VLS_176 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
    key: "integration",
    tab: "系统集成",
}));
const __VLS_178 = __VLS_177({
    key: "integration",
    tab: "系统集成",
}, ...__VLS_functionalComponentArgsRest(__VLS_177));
__VLS_179.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_179.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_180 = {}.ApiOutlined;
    /** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({}));
    const __VLS_182 = __VLS_181({}, ...__VLS_functionalComponentArgsRest(__VLS_181));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_184 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
    ...{ class: "demo-card" },
}));
const __VLS_186 = __VLS_185({
    ...{ class: "demo-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_185));
__VLS_187.slots.default;
const __VLS_188 = {}.LLMIntegrationDemo;
/** @type {[typeof __VLS_components.LLMIntegrationDemo, ]} */ ;
// @ts-ignore
const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
    ...{ 'onIntegrationTested': {} },
}));
const __VLS_190 = __VLS_189({
    ...{ 'onIntegrationTested': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_189));
let __VLS_192;
let __VLS_193;
let __VLS_194;
const __VLS_195 = {
    onIntegrationTested: (__VLS_ctx.handleIntegrationTested)
};
var __VLS_191;
var __VLS_187;
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
const __VLS_196 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    ...{ class: "demo-card" },
}));
const __VLS_198 = __VLS_197({
    ...{ class: "demo-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
__VLS_199.slots.default;
const __VLS_200 = {}.SupabaseRealtimeDemo;
/** @type {[typeof __VLS_components.SupabaseRealtimeDemo, ]} */ ;
// @ts-ignore
const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
    ...{ 'onRealtimeTested': {} },
}));
const __VLS_202 = __VLS_201({
    ...{ 'onRealtimeTested': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_201));
let __VLS_204;
let __VLS_205;
let __VLS_206;
const __VLS_207 = {
    onRealtimeTested: (__VLS_ctx.handleRealtimeTested)
};
var __VLS_203;
var __VLS_199;
var __VLS_179;
var __VLS_35;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "demo-status" },
});
const __VLS_208 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
    title: "演示状态",
    size: "small",
}));
const __VLS_210 = __VLS_209({
    title: "演示状态",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_209));
__VLS_211.slots.default;
const __VLS_212 = {}.ADescriptions;
/** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
// @ts-ignore
const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
    column: (2),
    size: "small",
}));
const __VLS_214 = __VLS_213({
    column: (2),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_213));
__VLS_215.slots.default;
const __VLS_216 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
    label: "演示任务数",
}));
const __VLS_218 = __VLS_217({
    label: "演示任务数",
}, ...__VLS_functionalComponentArgsRest(__VLS_217));
__VLS_219.slots.default;
(__VLS_ctx.demoTasks.length);
var __VLS_219;
const __VLS_220 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
    label: "审核项目数",
}));
const __VLS_222 = __VLS_221({
    label: "审核项目数",
}, ...__VLS_functionalComponentArgsRest(__VLS_221));
__VLS_223.slots.default;
(__VLS_ctx.demoTaskItems.length);
var __VLS_223;
const __VLS_224 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
    label: "消息通知数",
}));
const __VLS_226 = __VLS_225({
    label: "消息通知数",
}, ...__VLS_functionalComponentArgsRest(__VLS_225));
__VLS_227.slots.default;
(__VLS_ctx.demoNotificationCount);
var __VLS_227;
const __VLS_228 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
    label: "AI分析次数",
}));
const __VLS_230 = __VLS_229({
    label: "AI分析次数",
}, ...__VLS_functionalComponentArgsRest(__VLS_229));
__VLS_231.slots.default;
(__VLS_ctx.aiAnalysisCount);
var __VLS_231;
var __VLS_215;
const __VLS_232 = {}.ADivider;
/** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
// @ts-ignore
const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({}));
const __VLS_234 = __VLS_233({}, ...__VLS_functionalComponentArgsRest(__VLS_233));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "status-actions" },
});
const __VLS_236 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({}));
const __VLS_238 = __VLS_237({}, ...__VLS_functionalComponentArgsRest(__VLS_237));
__VLS_239.slots.default;
const __VLS_240 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_242 = __VLS_241({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_241));
let __VLS_244;
let __VLS_245;
let __VLS_246;
const __VLS_247 = {
    onClick: (__VLS_ctx.exportDemoData)
};
__VLS_243.slots.default;
const __VLS_248 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({}));
const __VLS_250 = __VLS_249({}, ...__VLS_functionalComponentArgsRest(__VLS_249));
var __VLS_243;
const __VLS_252 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_254 = __VLS_253({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_253));
let __VLS_256;
let __VLS_257;
let __VLS_258;
const __VLS_259 = {
    onClick: (__VLS_ctx.viewDemoLogs)
};
__VLS_255.slots.default;
const __VLS_260 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({}));
const __VLS_262 = __VLS_261({}, ...__VLS_functionalComponentArgsRest(__VLS_261));
var __VLS_255;
var __VLS_239;
var __VLS_211;
/** @type {__VLS_StyleScopedClasses['audit-module-demo']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['page-description']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-content']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-section']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-section']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-demo']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-section']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-section']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['demo-status']} */ ;
/** @type {__VLS_StyleScopedClasses['status-actions']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            AuditOutlined: icons_vue_1.AuditOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            ProjectOutlined: icons_vue_1.ProjectOutlined,
            TeamOutlined: icons_vue_1.TeamOutlined,
            BellOutlined: icons_vue_1.BellOutlined,
            RobotOutlined: icons_vue_1.RobotOutlined,
            ApiOutlined: icons_vue_1.ApiOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            MultiLevelAuditTabs: MultiLevelAuditTabs_vue_1.default,
            NotificationCenter: NotificationCenter_vue_1.default,
            activeTab: activeTab,
            initializing: initializing,
            selectedTaskItem: selectedTaskItem,
            demoTasks: demoTasks,
            demoTaskItems: demoTaskItems,
            demoNotificationCount: demoNotificationCount,
            aiAnalysisCount: aiAnalysisCount,
            getCurrentTaskItem: getCurrentTaskItem,
            initializeDemoData: initializeDemoData,
            resetDemo: resetDemo,
            handleTaskCreated: handleTaskCreated,
            handleTaskSelected: handleTaskSelected,
            handleTaskItemChange: handleTaskItemChange,
            handleAuditResultUpdated: handleAuditResultUpdated,
            handleAuditResultSubmitted: handleAuditResultSubmitted,
            handleNotificationSent: handleNotificationSent,
            handleDefectsDetected: handleDefectsDetected,
            handleMessageGenerated: handleMessageGenerated,
            handleIntegrationTested: handleIntegrationTested,
            handleRealtimeTested: handleRealtimeTested,
            exportDemoData: exportDemoData,
            viewDemoLogs: viewDemoLogs,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
