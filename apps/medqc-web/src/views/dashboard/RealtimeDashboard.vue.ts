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
import notification_1 from '../../stores/notification';
import realtime_service_1 from '../../lib/realtime/realtime-service';
import supabase_1 from '../../lib/supabase';
import icons_vue_1 from '@ant-design/icons-vue';
// 状态管理
const notificationStore = (0, notification_1.useNotificationStore)();
const realtimeService = (0, realtime_service_1.getRealtimeService)();
// 响应式数据
const realtimeEvents = (0, vue_1.ref)(: any[]);
const isConnected = (0, vue_1.ref)(false);
const connectionStatus = (0, vue_1.ref)('未连接');
const autoScroll = (0, vue_1.ref)(true);
const maxEvents = (0, vue_1.ref)(50);
// 统计数据
const eventStats = (0, vue_1.ref)({
    total: 0,
    inserts: 0,
    updates: 0,
    deletes: 0
});
// 检查连接状态
const checkConnection = () => {
    isConnected.value = realtimeService.getConnectionStatus();
    connectionStatus.value = isConnected.value ? '已连接' : '未连接';
};
// 处理实时事件
const handleRealtimeEvent = (event) => {
    console.log('收到实时事件:', event);
    // 添加到事件列表
    realtimeEvents.value.unshift({
        ...event,
        timestamp: new Date().toISOString()
    });
    // 限制事件数量
    if (realtimeEvents.value.length > maxEvents.value) {
        realtimeEvents.value = realtimeEvents.value.slice(0, maxEvents.value);
    }
    // 更新统计
    eventStats.value.total++;
    switch (event.eventType) {
        case 'INSERT':
            eventStats.value.inserts++;
            break;
        case 'UPDATE':
            eventStats.value.updates++;
            break;
        case 'DELETE':
            eventStats.value.deletes++;
            break;
    }
    // 自动滚动
    if (autoScroll.value) {
        setTimeout(() => {
            const container = document.querySelector('.events-container');
            if (container) {
                container.scrollTop = 0;
            }
        }, 100);
    }
};
// 清空事件日志
const clearEvents = () => {
    realtimeEvents.value = [];
    eventStats.value = {
        total: 0,
        inserts: 0,
        updates: 0,
        deletes: 0
    };
    ant_design_vue_1.message.success('事件日志已清空');
};
// 创建测试记录
const createTestRecord = async () => {
    try {
        const { data, error } = await supabase_1.supabase
            .from('medical_records')
            .insert({
            patient_name: `测试患者${Date.now()}`,
            patient_age: Math.floor(Math.random() * 50) + 20,
            patient_gender: Math.random() > 0.5 ? 'M' : 'F',
            department: ['内科', '外科', '儿科', '妇科'][Math.floor(Math.random() * 4)],
            admission_date: new Date().toISOString().split('T')[0],
            record_type: 'inpatient',
            content: `这是一条测试记录，创建时间：${new Date().toLocaleString()}`,
            status: 'pending'
        })
            .select()
            .single();
        if (error) {
            throw error;
        }
        ant_design_vue_1.message.success('测试记录创建成功');
    }
    catch (error) {
        console.error('创建测试记录失败:', error);
        ant_design_vue_1.message.error('创建测试记录失败');
    }
};
// 更新最近的记录
const updateLatestRecord = async () => {
    try {
        const { data: records, error: fetchError } = await supabase_1.supabase
            .from('medical_records')
            .select('id')
            .order('created_at', { ascending: false })
            .limit(1);
        if (fetchError || !records || records.length === 0) {
            ant_design_vue_1.message.warning('没有找到可更新的记录');
            return;
        }
        const { error: updateError } = await supabase_1.supabase
            .from('medical_records')
            .update({
            status: ['pending', 'analyzing', 'completed'][Math.floor(Math.random() * 3)],
            qc_score: Math.floor(Math.random() * 100)
        })
            .eq('id', records[0].id);
        if (updateError) {
            throw updateError;
        }
        ant_design_vue_1.message.success('记录更新成功');
    }
    catch (error) {
        console.error('更新记录失败:', error);
        ant_design_vue_1.message.error('更新记录失败');
    }
};
// 删除测试记录
const deleteTestRecord = async () => {
    try {
        const { data: records, error: fetchError } = await supabase_1.supabase
            .from('medical_records')
            .select('id, patient_name')
            .ilike('patient_name', '%测试患者%')
            .order('created_at', { ascending: false })
            .limit(1);
        if (fetchError || !records || records.length === 0) {
            ant_design_vue_1.message.warning('没有找到测试记录');
            return;
        }
        const { error: deleteError } = await supabase_1.supabase
            .from('medical_records')
            .delete()
            .eq('id', records[0].id);
        if (deleteError) {
            throw deleteError;
        }
        ant_design_vue_1.message.success('测试记录删除成功');
    }
    catch (error) {
        console.error('删除记录失败:', error);
        ant_design_vue_1.message.error('删除记录失败');
    }
};
// 重新连接
const reconnect = async () => {
    try {
        await realtimeService.reconnect();
        ant_design_vue_1.message.success('重新连接成功');
    }
    catch (error) {
        console.error('重新连接失败:', error);
        ant_design_vue_1.message.error('重新连接失败');
    }
};
// 格式化时间
const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleString();
};
// 获取事件类型颜色
const getEventTypeColor = (eventType) => {
    const colorMap = {
        'INSERT': '#52c41a',
        'UPDATE': '#faad14',
        'DELETE': '#ff4d4f'
    };
    return colorMap[eventType] || '#1890ff';
};
// 获取事件类型文本
const getEventTypeText = (eventType) => {
    const textMap = {
        'INSERT': '新增',
        'UPDATE': '更新',
        'DELETE': '删除'
    };
    return textMap[eventType] || eventType;
};
// 生命周期
(0, vue_1.onMounted)(() => {
    checkConnection();
    // 添加实时事件监听器
    realtimeService.addEventListener('medical_records', handleRealtimeEvent);
    realtimeService.addEventListener('qc_results', handleRealtimeEvent);
    // 定时检查连接状态
    const statusInterval = setInterval(checkConnection, 5000);
    (0, vue_1.onUnmounted)(() => {
        clearInterval(statusInterval);
        realtimeService.removeEventListener('medical_records', handleRealtimeEvent);
        realtimeService.removeEventListener('qc_results', handleRealtimeEvent);
    });
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['event-item']} */ ;
/** @type {__VLS_StyleScopedClasses['events-container']} */ ;
/** @type {__VLS_StyleScopedClasses['events-container']} */ ;
/** @type {__VLS_StyleScopedClasses['events-container']} */ ;
/** @type {__VLS_StyleScopedClasses['events-container']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "realtime-dashboard" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "dashboard-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center" },
});
const __VLS_0 = {}.ThunderboltOutlined;
/** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-2xl text-blue-500 mr-3" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-2xl text-blue-500 mr-3" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-2xl font-bold text-gray-900" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-sm text-gray-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-3 h-3 rounded-full" },
    ...{ class: (__VLS_ctx.isConnected ? 'bg-green-500' : 'bg-red-500') },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm font-medium" },
});
(__VLS_ctx.connectionStatus);
if (!__VLS_ctx.isConnected) {
    const __VLS_4 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        ...{ 'onClick': {} },
        type: "primary",
        icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
    }));
    const __VLS_6 = __VLS_5({
        ...{ 'onClick': {} },
        type: "primary",
        icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    let __VLS_8;
    let __VLS_9;
    let __VLS_10;
    const __VLS_11 = {
        onClick: (__VLS_ctx.reconnect)
    };
    __VLS_7.slots.default;
    var __VLS_7;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-4 gap-6 mb-6" },
});
const __VLS_12 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ class: "text-center" },
}));
const __VLS_14 = __VLS_13({
    ...{ class: "text-center" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-2xl font-bold text-blue-600" },
});
(__VLS_ctx.eventStats.total);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-gray-600" },
});
var __VLS_15;
const __VLS_16 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ class: "text-center" },
}));
const __VLS_18 = __VLS_17({
    ...{ class: "text-center" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-2xl font-bold text-green-600" },
});
(__VLS_ctx.eventStats.inserts);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-gray-600" },
});
var __VLS_19;
const __VLS_20 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ class: "text-center" },
}));
const __VLS_22 = __VLS_21({
    ...{ class: "text-center" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-2xl font-bold text-yellow-600" },
});
(__VLS_ctx.eventStats.updates);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-gray-600" },
});
var __VLS_23;
const __VLS_24 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ class: "text-center" },
}));
const __VLS_26 = __VLS_25({
    ...{ class: "text-center" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-2xl font-bold text-red-600" },
});
(__VLS_ctx.eventStats.deletes);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-gray-600" },
});
var __VLS_27;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 lg:grid-cols-2 gap-6" },
});
const __VLS_28 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    title: "测试操作",
    ...{ class: "mb-6" },
}));
const __VLS_30 = __VLS_29({
    title: "测试操作",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex flex-wrap gap-2" },
});
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onClick': {} },
    type: "primary",
    icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    type: "primary",
    icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (__VLS_ctx.createTestRecord)
};
__VLS_35.slots.default;
var __VLS_35;
const __VLS_40 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (__VLS_ctx.updateLatestRecord)
};
__VLS_43.slots.default;
var __VLS_43;
const __VLS_48 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onClick': {} },
    danger: true,
    icon: (__VLS_ctx.h(__VLS_ctx.DeleteOutlined)),
}));
const __VLS_50 = __VLS_49({
    ...{ 'onClick': {} },
    danger: true,
    icon: (__VLS_ctx.h(__VLS_ctx.DeleteOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onClick: (__VLS_ctx.deleteTestRecord)
};
__VLS_51.slots.default;
var __VLS_51;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm text-gray-600" },
});
var __VLS_31;
const __VLS_56 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    title: "事件控制",
    ...{ class: "mb-6" },
}));
const __VLS_58 = __VLS_57({
    title: "事件控制",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm" },
});
const __VLS_60 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    checked: (__VLS_ctx.autoScroll),
}));
const __VLS_62 = __VLS_61({
    checked: (__VLS_ctx.autoScroll),
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm" },
});
const __VLS_64 = {}.AInputNumber;
/** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    value: (__VLS_ctx.maxEvents),
    min: (10),
    max: (200),
    step: (10),
    size: "small",
}));
const __VLS_66 = __VLS_65({
    value: (__VLS_ctx.maxEvents),
    min: (10),
    max: (200),
    step: (10),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
const __VLS_68 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    ...{ 'onClick': {} },
    block: true,
    disabled: (__VLS_ctx.realtimeEvents.length === 0),
}));
const __VLS_70 = __VLS_69({
    ...{ 'onClick': {} },
    block: true,
    disabled: (__VLS_ctx.realtimeEvents.length === 0),
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
let __VLS_72;
let __VLS_73;
let __VLS_74;
const __VLS_75 = {
    onClick: (__VLS_ctx.clearEvents)
};
__VLS_71.slots.default;
var __VLS_71;
var __VLS_59;
const __VLS_76 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    title: "实时事件日志",
    ...{ class: "mb-6" },
}));
const __VLS_78 = __VLS_77({
    title: "实时事件日志",
    ...{ class: "mb-6" },
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "events-container" },
    ...{ style: {} },
});
if (__VLS_ctx.realtimeEvents.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-8 text-gray-500" },
    });
    const __VLS_80 = {}.BellOutlined;
    /** @type {[typeof __VLS_components.BellOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        ...{ class: "text-4xl mb-2" },
    }));
    const __VLS_82 = __VLS_81({
        ...{ class: "text-4xl mb-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "space-y-2" },
    });
    for (const [event] of __VLS_getVForSourceType((__VLS_ctx.realtimeEvents))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (`${event.timestamp}-${Math.random()}`),
            ...{ class: "event-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-start space-x-3 p-3 bg-gray-50 rounded-lg" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "w-3 h-3 rounded-full mt-1 flex-shrink-0" },
            ...{ style: ({ backgroundColor: __VLS_ctx.getEventTypeColor(event.eventType) }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex-1 min-w-0" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center justify-between" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center space-x-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-sm font-medium px-2 py-1 rounded" },
            ...{ style: ({
                    color: __VLS_ctx.getEventTypeColor(event.eventType),
                    backgroundColor: __VLS_ctx.getEventTypeColor(event.eventType) + '20'
                }) },
        });
        (__VLS_ctx.getEventTypeText(event.eventType));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-sm text-gray-600" },
        });
        (event.table);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-xs text-gray-400" },
        });
        (__VLS_ctx.formatTime(event.timestamp));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-2 text-sm text-gray-700" },
        });
        if (event.new && event.new.patient_name) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (event.new.patient_name);
            if (event.new.status) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "ml-2" },
                });
                (event.new.status);
            }
        }
        else if (event.old && event.old.patient_name) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (event.old.patient_name);
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            (event.eventType);
        }
    }
}
var __VLS_79;
/** @type {__VLS_StyleScopedClasses['realtime-dashboard']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-header']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-yellow-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['events-container']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['event-item']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['py-1']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            BellOutlined: icons_vue_1.BellOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            realtimeEvents: realtimeEvents,
            isConnected: isConnected,
            connectionStatus: connectionStatus,
            autoScroll: autoScroll,
            maxEvents: maxEvents,
            eventStats: eventStats,
            clearEvents: clearEvents,
            createTestRecord: createTestRecord,
            updateLatestRecord: updateLatestRecord,
            deleteTestRecord: deleteTestRecord,
            reconnect: reconnect,
            formatTime: formatTime,
            getEventTypeColor: getEventTypeColor,
            getEventTypeText: getEventTypeText,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
