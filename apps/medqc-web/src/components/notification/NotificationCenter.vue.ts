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
import auth_1 from '@/stores/auth';
import notification_service_1 from '@/services/notification-service';
import date_utils_1 from '@/utils/date-utils';
// import MessageDetail from './MessageDetail.vue'
// 状态管理
const router = (0, vue_router_1.useRouter)();
const authStore = (0, auth_1.useAuthStore)();
const loading = (0, vue_1.ref)(false);
const messages = (0, vue_1.ref)(: any[]);
const currentFilter = (0, vue_1.ref)('all');
const currentPage = (0, vue_1.ref)(1);
const pageSize = (0, vue_1.ref)(20);
// 消息详情
const detailDrawerVisible = (0, vue_1.ref)(false);
const selectedMessage = (0, vue_1.ref)(null);
// 计算属性
const unreadCount = (0, vue_1.computed)(() => messages.value.filter(m => m.status !== 'read' && m.status !== 'processed').length);
const totalMessages = (0, vue_1.computed)(() => messages.value.length);
const filteredMessages = (0, vue_1.computed)(() => {
    let filtered = messages.value;
    switch (currentFilter.value) {
        case 'unread':
            filtered = filtered.filter(m => m.status !== 'read' && m.status !== 'processed');
            break;
        case 'urgent':
            filtered = filtered.filter(m => m.priority === 'urgent');
            break;
        case 'today':
            const today = new Date().toDateString();
            filtered = filtered.filter(m => new Date(m.created_at).toDateString() === today);
            break;
        default:
            if (currentFilter.value !== 'all') {
                // 按消息类型筛选
                filtered = filtered.filter(m => m.type === currentFilter.value);
            }
    }
    return filtered;
});
const paginationConfig = (0, vue_1.computed)(() => ({
    current: currentPage.value,
    pageSize: pageSize.value,
    total: filteredMessages.value.length,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
}));
// 方法
const loadMessages = async () => {
    try {
        loading.value = true;
        const userMessages = await notification_service_1.notificationService.getUserNotifications(authStore.user.id, {
            limit: 100,
            offset: 0
        });
        messages.value = userMessages;
    }
    catch (error) {
        ant_design_vue_1.message.error(`加载消息失败: ${error.message}`);
    }
    finally {
        loading.value = false;
    }
};
const refreshMessages = async () => {
    await loadMessages();
    ant_design_vue_1.message.success('消息已刷新');
};
const markAllAsRead = async () => {
    try {
        const unreadMessages = messages.value.filter(m => m.status !== 'read' && m.status !== 'processed');
        for (const msg of unreadMessages) {
            await notification_service_1.notificationService.markAsRead(msg.id);
        }
        await loadMessages();
        ant_design_vue_1.message.success('所有消息已标记为已读');
    }
    catch (error) {
        ant_design_vue_1.message.error(`操作失败: ${error.message}`);
    }
};
const markAsRead = async (messageId) => {
    try {
        await notification_service_1.notificationService.markAsRead(messageId);
        await loadMessages();
        ant_design_vue_1.message.success('已标记为已读');
    }
    catch (error) {
        ant_design_vue_1.message.error('操作失败');
    }
};
const markAsProcessed = async (messageId) => {
    try {
        await notification_service_1.notificationService.markAsProcessed(messageId);
        await loadMessages();
        ant_design_vue_1.message.success('已标记为已处理');
    }
    catch (error) {
        ant_design_vue_1.message.error('操作失败');
    }
};
const deleteMessage = async (messageId) => {
    ant_design_vue_1.Modal.confirm({
        title: '确认删除', content: '确定要删除这条消息吗？', onOk: async () => {
            try {
                // 实现删除逻辑
                messages.value = messages.value.filter(m => m.id !== messageId);
                ant_design_vue_1.message.success('消息已删除');
            }
            catch (error) {
                ant_design_vue_1.message.error('删除失败');
            }
        }
    });
};
const handleFilterChange = ({ key }) => {
    currentFilter.value = key;
    currentPage.value = 1;
};
const handlePageChange = (page: any,  size: any) => {
    currentPage.value = page;
    pageSize.value = size;
};
const handleMessageClick = (notification) => {
    selectedMessage.value = notification;
    detailDrawerVisible.value = true;
    // 自动标记为已读
    if (notification.status === 'pending' || notification.status === 'delivered') {
        markAsRead(notification.id);
    }
};
const executeAction = async (action, notification) => {
    try {
        switch (action.action) {
            case 'navigate':
                if (action.config.url) {
                    await router.push({
                        path: action.config.url,
                        query: action.config.params
                    });
                }
                break;
            case 'api_call':
                if (action.config.api_endpoint) {
                    // 实现API调用
                    ant_design_vue_1.message.success('操作已执行');
                }
                break;
            case 'modal':
                // 实现模态框打开
                break;
            case 'confirm':
                ant_design_vue_1.Modal.confirm({
                    title: '确认操作', content: action.config.confirm_message || '确定要执行此操作吗？', onOk: () => {
                        // 执行确认后的操作
                    }
                });
                break;
        }
        // 标记消息为已处理
        await markAsProcessed(notification.id);
    }
    catch (error) {
        ant_design_vue_1.message.error('操作失败');
    }
};
const getPrimaryActions = (notification) => {
    return (notification.actions || : any[]).filter(action => action.type === 'primary').slice(0, 2); // 最多显示2个主要操作
};
const getSecondaryActions = (notification) => {
    return (notification.actions || : any[]).filter(action => action.type !== 'primary');
};
const hasSecondaryActions = (notification) => {
    return getSecondaryActions(notification).length > 0;
};
const hasRelatedInfo = (notification) => {
    const data = notification.related_data;
    return !!(data.patient_id || data.medical_record_id || data.task_name);
};
const getMessageTypeColor = (type) => {
    const colorMap = {
        'qc_completed': 'green',
        'rectification_required': 'orange',
        'audit_result': 'blue',
        'appeal_result': 'purple',
        'deadline_reminder': 'red',
        'system_announcement': 'cyan',
        'rectification_submitted': 'geekblue',
        'appeal_submitted': 'magenta',
        'task_assigned': 'volcano',
        'task_overdue': 'red',
        'batch_completed': 'lime',
        'expert_consultation': 'gold'
    };
    return colorMap[type] || 'default';
};
const getMessageTypeLabel = (type) => {
    const labelMap = {
        'qc_completed': '质控完成',
        'rectification_required': '整改要求',
        'audit_result': '审核结果',
        'appeal_result': '申诉结果',
        'deadline_reminder': '截止提醒',
        'system_announcement': '系统公告',
        'rectification_submitted': '整改提交',
        'appeal_submitted': '申诉提交',
        'task_assigned': '任务分配',
        'task_overdue': '任务超期',
        'batch_completed': '批量完成',
        'expert_consultation': '专家会诊'
    };
    return labelMap[type] || type;
};
const handleActionExecuted = () => {
    loadMessages();
};
// 实时消息监听
const setupRealTimeListener = () => {
    // 监听新消息事件
    window.addEventListener('new-notification', (event) => {
        const newNotification = event.detail;
        messages.value.unshift(newNotification);
        // 显示通知提示
        if (newNotification.priority === 'urgent') {
            ant_design_vue_1.message.warning({
                content: `紧急消息：${newNotification.title}`,
                duration: 5
            });
        }
    });
    // 监听消息更新事件
    window.addEventListener('notification-updated',  (event: any) => {
        const updatedNotification = event.detail;
        const index = messages.value.findIndex(m => m.id === updatedNotification.id);
        if (index !== -1) {
            messages.value[index] = updatedNotification;
        }
    });
};
const cleanupRealTimeListener = () => {
    window.removeEventListener('new-notification', () => { });
    window.removeEventListener('notification-updated', () => { });
};
// 生命周期
(0, vue_1.onMounted)(async () => {
    await loadMessages();
    setupRealTimeListener();
    // 初始化实时通信
    await notification_service_1.notificationService.initializeRealTime(authStore.user.id, authStore.user.type);
});
(0, vue_1.onUnmounted)(() => {
    cleanupRealTimeListener();
    notification_service_1.notificationService.cleanup();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['message-item']} */ ;
/** @type {__VLS_StyleScopedClasses['message-item']} */ ;
/** @type {__VLS_StyleScopedClasses['message-item']} */ ;
/** @type {__VLS_StyleScopedClasses['message-item']} */ ;
/** @type {__VLS_StyleScopedClasses['priority-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['priority-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['priority-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['priority-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['message-title']} */ ;
/** @type {__VLS_StyleScopedClasses['message-meta']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "notification-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "notification-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-left" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "header-title" },
});
const __VLS_0 = {}.BellOutlined;
/** @type {[typeof __VLS_components.BellOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const __VLS_4 = {}.ABadge;
/** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    count: (__VLS_ctx.unreadCount),
    offset: ([10, 0]),
}));
const __VLS_6 = __VLS_5({
    count: (__VLS_ctx.unreadCount),
    offset: ([10, 0]),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-stats" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
(__VLS_ctx.totalMessages);
if (__VLS_ctx.unreadCount > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.unreadCount);
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-actions" },
});
const __VLS_8 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.unreadCount === 0),
    size: "small",
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.unreadCount === 0),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (__VLS_ctx.markAllAsRead)
};
__VLS_15.slots.default;
var __VLS_15;
const __VLS_20 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    size: "small",
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.refreshMessages)
};
__VLS_23.slots.default;
const __VLS_28 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
var __VLS_23;
const __VLS_32 = {}.ADropdown;
/** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    size: "small",
}));
const __VLS_38 = __VLS_37({
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
const __VLS_40 = {}.FilterOutlined;
/** @type {[typeof __VLS_components.FilterOutlined, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
const __VLS_44 = {}.DownOutlined;
/** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
var __VLS_39;
{
    const { overlay: __VLS_thisSlot } = __VLS_35.slots;
    const __VLS_48 = {}.AMenu;
    /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ 'onClick': {} },
    }));
    const __VLS_50 = __VLS_49({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    let __VLS_52;
    let __VLS_53;
    let __VLS_54;
    const __VLS_55 = {
        onClick: (__VLS_ctx.handleFilterChange)
    };
    __VLS_51.slots.default;
    const __VLS_56 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        key: "all",
    }));
    const __VLS_58 = __VLS_57({
        key: "all",
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    var __VLS_59;
    const __VLS_60 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        key: "unread",
    }));
    const __VLS_62 = __VLS_61({
        key: "unread",
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    var __VLS_63;
    const __VLS_64 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        key: "urgent",
    }));
    const __VLS_66 = __VLS_65({
        key: "urgent",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    var __VLS_67;
    const __VLS_68 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        key: "today",
    }));
    const __VLS_70 = __VLS_69({
        key: "today",
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_71.slots.default;
    var __VLS_71;
    const __VLS_72 = {}.AMenuDivider;
    /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({}));
    const __VLS_74 = __VLS_73({}, ...__VLS_functionalComponentArgsRest(__VLS_73));
    const __VLS_76 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        key: "rectification_required",
    }));
    const __VLS_78 = __VLS_77({
        key: "rectification_required",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    var __VLS_79;
    const __VLS_80 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        key: "audit_result",
    }));
    const __VLS_82 = __VLS_81({
        key: "audit_result",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    var __VLS_83;
    const __VLS_84 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        key: "task_assigned",
    }));
    const __VLS_86 = __VLS_85({
        key: "task_assigned",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    var __VLS_87;
    var __VLS_51;
}
var __VLS_35;
var __VLS_11;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "notification-list" },
});
const __VLS_88 = {}.ASpin;
/** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    spinning: (__VLS_ctx.loading),
}));
const __VLS_90 = __VLS_89({
    spinning: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
const __VLS_92 = {}.AList;
/** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    ...{ 'onChange': {} },
    dataSource: (__VLS_ctx.filteredMessages),
    itemLayout: "vertical",
    pagination: (__VLS_ctx.paginationConfig),
}));
const __VLS_94 = __VLS_93({
    ...{ 'onChange': {} },
    dataSource: (__VLS_ctx.filteredMessages),
    itemLayout: "vertical",
    pagination: (__VLS_ctx.paginationConfig),
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
let __VLS_96;
let __VLS_97;
let __VLS_98;
const __VLS_99 = {
    onChange: (__VLS_ctx.handlePageChange)
};
__VLS_95.slots.default;
{
    const { renderItem: __VLS_thisSlot } = __VLS_95.slots;
    const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_100 = {}.AListItem;
    /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        ...{ 'onClick': {} },
        ...{ class: ([
                'message-item',
                `priority-${item.priority}`,
                {
                    'unread': item.status !== 'read' && item.status !== 'processed',
                    'processed': item.status === 'processed',
                    'urgent': item.priority === 'urgent'
                }
            ]) },
    }));
    const __VLS_102 = __VLS_101({
        ...{ 'onClick': {} },
        ...{ class: ([
                'message-item',
                `priority-${item.priority}`,
                {
                    'unread': item.status !== 'read' && item.status !== 'processed',
                    'processed': item.status === 'processed',
                    'urgent': item.priority === 'urgent'
                }
            ]) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    let __VLS_104;
    let __VLS_105;
    let __VLS_106;
    const __VLS_107 = {
        onClick: (...[$event]) => {
            __VLS_ctx.handleMessageClick(item);
        }
    };
    __VLS_103.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "priority-indicator" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: (`priority-dot priority-${item.priority}`) },
    });
    const __VLS_108 = {}.AListItemMeta;
    /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({}));
    const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
    __VLS_111.slots.default;
    {
        const { title: __VLS_thisSlot } = __VLS_111.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "message-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "title-text" },
        });
        (item.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "message-meta" },
        });
        const __VLS_112 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            color: (__VLS_ctx.getMessageTypeColor(item.type)),
            size: "small",
        }));
        const __VLS_114 = __VLS_113({
            color: (__VLS_ctx.getMessageTypeColor(item.type)),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        (__VLS_ctx.getMessageTypeLabel(item.type));
        var __VLS_115;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "message-time" },
        });
        (__VLS_ctx.formatRelativeTime(item.created_at));
    }
    {
        const { description: __VLS_thisSlot } = __VLS_111.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "message-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "content-text" },
        });
        (item.summary || item.content.substring(0, 120) + '...');
        if (__VLS_ctx.hasRelatedInfo(item)) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "related-info" },
            });
            const __VLS_116 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
                size: "small",
            }));
            const __VLS_118 = __VLS_117({
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_117));
            __VLS_119.slots.default;
            if (item.related_data.patient_id) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                const __VLS_120 = {}.UserOutlined;
                /** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({}));
                const __VLS_122 = __VLS_121({}, ...__VLS_functionalComponentArgsRest(__VLS_121));
                (item.related_data.patient_name || item.related_data.patient_id);
            }
            if (item.related_data.medical_record_id) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                const __VLS_124 = {}.FileTextOutlined;
                /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
                const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
                (item.related_data.medical_record_id.substring(0, 8));
            }
            if (item.related_data.task_name) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                const __VLS_128 = {}.ProjectOutlined;
                /** @type {[typeof __VLS_components.ProjectOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({}));
                const __VLS_130 = __VLS_129({}, ...__VLS_functionalComponentArgsRest(__VLS_129));
                (item.related_data.task_name);
            }
            var __VLS_119;
        }
    }
    var __VLS_111;
    {
        const { actions: __VLS_thisSlot } = __VLS_103.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "message-actions" },
        });
        const __VLS_132 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
            size: "small",
        }));
        const __VLS_134 = __VLS_133({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_133));
        __VLS_135.slots.default;
        for (const [action] of __VLS_getVForSourceType((__VLS_ctx.getPrimaryActions(item)))) {
            const __VLS_136 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
                ...{ 'onClick': {} },
                key: (action.id),
                type: (action.type),
                size: "small",
            }));
            const __VLS_138 = __VLS_137({
                ...{ 'onClick': {} },
                key: (action.id),
                type: (action.type),
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_137));
            let __VLS_140;
            let __VLS_141;
            let __VLS_142;
            const __VLS_143 = {
                onClick: (...[$event]) => {
                    __VLS_ctx.executeAction(action, item);
                }
            };
            __VLS_139.slots.default;
            (action.label);
            var __VLS_139;
        }
        if (__VLS_ctx.hasSecondaryActions(item)) {
            const __VLS_144 = {}.ADropdown;
            /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
            // @ts-ignore
            const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({}));
            const __VLS_146 = __VLS_145({}, ...__VLS_functionalComponentArgsRest(__VLS_145));
            __VLS_147.slots.default;
            const __VLS_148 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
                size: "small",
                type: "text",
            }));
            const __VLS_150 = __VLS_149({
                size: "small",
                type: "text",
            }, ...__VLS_functionalComponentArgsRest(__VLS_149));
            __VLS_151.slots.default;
            const __VLS_152 = {}.MoreOutlined;
            /** @type {[typeof __VLS_components.MoreOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({}));
            const __VLS_154 = __VLS_153({}, ...__VLS_functionalComponentArgsRest(__VLS_153));
            var __VLS_151;
            {
                const { overlay: __VLS_thisSlot } = __VLS_147.slots;
                const __VLS_156 = {}.AMenu;
                /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
                // @ts-ignore
                const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({}));
                const __VLS_158 = __VLS_157({}, ...__VLS_functionalComponentArgsRest(__VLS_157));
                __VLS_159.slots.default;
                for (const [action] of __VLS_getVForSourceType((__VLS_ctx.getSecondaryActions(item)))) {
                    const __VLS_160 = {}.AMenuItem;
                    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
                    // @ts-ignore
                    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
                        ...{ 'onClick': {} },
                        key: (action.id),
                    }));
                    const __VLS_162 = __VLS_161({
                        ...{ 'onClick': {} },
                        key: (action.id),
                    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
                    let __VLS_164;
                    let __VLS_165;
                    let __VLS_166;
                    const __VLS_167 = {
                        onClick: (...[$event]) => {
                            if (!(__VLS_ctx.hasSecondaryActions(item)))
                                return;
                            __VLS_ctx.executeAction(action, item);
                        }
                    };
                    __VLS_163.slots.default;
                    (action.label);
                    var __VLS_163;
                }
                const __VLS_168 = {}.AMenuDivider;
                /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
                // @ts-ignore
                const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({}));
                const __VLS_170 = __VLS_169({}, ...__VLS_functionalComponentArgsRest(__VLS_169));
                if (item.status !== 'read') {
                    const __VLS_172 = {}.AMenuItem;
                    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
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
                        onClick: (...[$event]) => {
                            if (!(__VLS_ctx.hasSecondaryActions(item)))
                                return;
                            if (!(item.status !== 'read'))
                                return;
                            __VLS_ctx.markAsRead(item.id);
                        }
                    };
                    __VLS_175.slots.default;
                    const __VLS_180 = {}.CheckOutlined;
                    /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
                    // @ts-ignore
                    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({}));
                    const __VLS_182 = __VLS_181({}, ...__VLS_functionalComponentArgsRest(__VLS_181));
                    var __VLS_175;
                }
                if (item.status !== 'processed') {
                    const __VLS_184 = {}.AMenuItem;
                    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
                    // @ts-ignore
                    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
                        ...{ 'onClick': {} },
                    }));
                    const __VLS_186 = __VLS_185({
                        ...{ 'onClick': {} },
                    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
                    let __VLS_188;
                    let __VLS_189;
                    let __VLS_190;
                    const __VLS_191 = {
                        onClick: (...[$event]) => {
                            if (!(__VLS_ctx.hasSecondaryActions(item)))
                                return;
                            if (!(item.status !== 'processed'))
                                return;
                            __VLS_ctx.markAsProcessed(item.id);
                        }
                    };
                    __VLS_187.slots.default;
                    const __VLS_192 = {}.CheckCircleOutlined;
                    /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
                    // @ts-ignore
                    const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({}));
                    const __VLS_194 = __VLS_193({}, ...__VLS_functionalComponentArgsRest(__VLS_193));
                    var __VLS_187;
                }
                const __VLS_196 = {}.AMenuItem;
                /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
                // @ts-ignore
                const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
                    ...{ 'onClick': {} },
                    danger: true,
                }));
                const __VLS_198 = __VLS_197({
                    ...{ 'onClick': {} },
                    danger: true,
                }, ...__VLS_functionalComponentArgsRest(__VLS_197));
                let __VLS_200;
                let __VLS_201;
                let __VLS_202;
                const __VLS_203 = {
                    onClick: (...[$event]) => {
                        if (!(__VLS_ctx.hasSecondaryActions(item)))
                            return;
                        __VLS_ctx.deleteMessage(item.id);
                    }
                };
                __VLS_199.slots.default;
                const __VLS_204 = {}.DeleteOutlined;
                /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({}));
                const __VLS_206 = __VLS_205({}, ...__VLS_functionalComponentArgsRest(__VLS_205));
                var __VLS_199;
                var __VLS_159;
            }
            var __VLS_147;
        }
        var __VLS_135;
    }
    var __VLS_103;
}
{
    const { empty: __VLS_thisSlot } = __VLS_95.slots;
    const __VLS_208 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        description: "暂无消息",
    }));
    const __VLS_210 = __VLS_209({
        description: "暂无消息",
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
    __VLS_211.slots.default;
    const __VLS_212 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_214 = __VLS_213({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_213));
    let __VLS_216;
    let __VLS_217;
    let __VLS_218;
    const __VLS_219 = {
        onClick: (__VLS_ctx.refreshMessages)
    };
    __VLS_215.slots.default;
    var __VLS_215;
    var __VLS_211;
}
var __VLS_95;
var __VLS_91;
const __VLS_220 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
    open: (__VLS_ctx.detailDrawerVisible),
    title: "消息详情",
    width: "600",
    placement: "right",
}));
const __VLS_222 = __VLS_221({
    open: (__VLS_ctx.detailDrawerVisible),
    title: "消息详情",
    width: "600",
    placement: "right",
}, ...__VLS_functionalComponentArgsRest(__VLS_221));
__VLS_223.slots.default;
if (__VLS_ctx.selectedMessage) {
    const __VLS_224 = {}.MessageDetail;
    /** @type {[typeof __VLS_components.MessageDetail, ]} */ ;
    // @ts-ignore
    const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
        ...{ 'onActionExecuted': {} },
        ...{ 'onClose': {} },
        message: (__VLS_ctx.selectedMessage),
    }));
    const __VLS_226 = __VLS_225({
        ...{ 'onActionExecuted': {} },
        ...{ 'onClose': {} },
        message: (__VLS_ctx.selectedMessage),
    }, ...__VLS_functionalComponentArgsRest(__VLS_225));
    let __VLS_228;
    let __VLS_229;
    let __VLS_230;
    const __VLS_231 = {
        onActionExecuted: (__VLS_ctx.handleActionExecuted)
    };
    const __VLS_232 = {
        onClose: (...[$event]) => {
            if (!(__VLS_ctx.selectedMessage))
                return;
            __VLS_ctx.detailDrawerVisible = false;
        }
    };
    var __VLS_227;
}
var __VLS_223;
/** @type {__VLS_StyleScopedClasses['notification-center']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['notification-list']} */ ;
/** @type {__VLS_StyleScopedClasses['message-item']} */ ;
/** @type {__VLS_StyleScopedClasses['unread']} */ ;
/** @type {__VLS_StyleScopedClasses['processed']} */ ;
/** @type {__VLS_StyleScopedClasses['urgent']} */ ;
/** @type {__VLS_StyleScopedClasses['priority-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['message-title']} */ ;
/** @type {__VLS_StyleScopedClasses['title-text']} */ ;
/** @type {__VLS_StyleScopedClasses['message-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['message-time']} */ ;
/** @type {__VLS_StyleScopedClasses['message-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['related-info']} */ ;
/** @type {__VLS_StyleScopedClasses['message-actions']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            BellOutlined: icons_vue_1.BellOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            FilterOutlined: icons_vue_1.FilterOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            UserOutlined: icons_vue_1.UserOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            ProjectOutlined: icons_vue_1.ProjectOutlined,
            MoreOutlined: icons_vue_1.MoreOutlined,
            CheckOutlined: icons_vue_1.CheckOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            formatRelativeTime: date_utils_1.formatRelativeTime,
            loading: loading,
            detailDrawerVisible: detailDrawerVisible,
            selectedMessage: selectedMessage,
            unreadCount: unreadCount,
            totalMessages: totalMessages,
            filteredMessages: filteredMessages,
            paginationConfig: paginationConfig,
            refreshMessages: refreshMessages,
            markAllAsRead: markAllAsRead,
            markAsRead: markAsRead,
            markAsProcessed: markAsProcessed,
            deleteMessage: deleteMessage,
            handleFilterChange: handleFilterChange,
            handlePageChange: handlePageChange,
            handleMessageClick: handleMessageClick,
            executeAction: executeAction,
            getPrimaryActions: getPrimaryActions,
            getSecondaryActions: getSecondaryActions,
            hasSecondaryActions: hasSecondaryActions,
            hasRelatedInfo: hasRelatedInfo,
            getMessageTypeColor: getMessageTypeColor,
            getMessageTypeLabel: getMessageTypeLabel,
            handleActionExecuted: handleActionExecuted,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
