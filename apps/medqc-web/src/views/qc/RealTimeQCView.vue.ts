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
import useRealTimeQC_1 from '@/composables/useRealTimeQC';
const RealTimeQCDashboard_vue_1 = __importDefault(require("@/components/qc/RealTimeQCDashboard.vue"));
const RealTimeQCAlert_vue_1 = __importDefault(require("@/components/qc/RealTimeQCAlert.vue"));
const PageHeaderComponent_vue_1 = __importDefault(require("@/components/common/PageHeaderComponent.vue"));
import ant_design_vue_1 from 'ant-design-vue';
// 使用实时质控组合式函数
const { isMonitoring, recentResults, qcRules, startRealTimeMonitoring, stopRealTimeMonitoring, loadQCRules } = (0, useRealTimeQC_1.useRealTimeQC)();
// 组件状态
const isStarting = (0, vue_1.ref)(false);
const isStopping = (0, vue_1.ref)(false);
const isRefreshingRules = (0, vue_1.ref)(false);
const logFilter = (0, vue_1.ref)('all');
const showRuleDialog = (0, vue_1.ref)(false);
const editingRule = (0, vue_1.ref)(null);
// 规则表单
const ruleForm = (0, vue_1.ref)({
    name: '',
    description: '',
    type: 'content',
    severity: 'warning',
    priority: 5,
    isActive: true,
    pattern: ''
});
// 计算属性
const filteredLogs = (0, vue_1.computed)(() => {
    if (logFilter.value === 'all') {
        return recentResults.value;
    }
    return recentResults.value.filter(log => log.alertLevel === logFilter.value);
});
const isRuleFormValid = (0, vue_1.computed)(() => {
    return ruleForm.value.name.trim() !== '' && ruleForm.value.description.trim() !== '';
});
// 方法
const startMonitoring = async () => {
    isStarting.value = true;
    try {
        await startRealTimeMonitoring();
        ant_design_vue_1.message.success('实时质控监控已启动');
    }
    catch (error) {
        console.error('启动监控失败:', error);
        ant_design_vue_1.message.error('启动监控失败');
    }
    finally {
        isStarting.value = false;
    }
};
const stopMonitoring = async () => {
    isStopping.value = true;
    try {
        stopRealTimeMonitoring();
        ant_design_vue_1.message.success('实时质控监控已停止');
    }
    catch (error) {
        console.error('停止监控失败:', error);
        ant_design_vue_1.message.error('停止监控失败');
    }
    finally {
        isStopping.value = false;
    }
};
const refreshRules = async () => {
    isRefreshingRules.value = true;
    try {
        await loadQCRules();
        ant_design_vue_1.message.success('质控规则已刷新');
    }
    catch (error) {
        console.error('刷新规则失败:', error);
        ant_design_vue_1.message.error('刷新规则失败');
    }
    finally {
        isRefreshingRules.value = false;
    }
};
const showAddRule = () => {
    editingRule.value = null;
    ruleForm.value = {
        name: '',
        description: '',
        type: 'content',
        severity: 'warning',
        priority: 5,
        isActive: true,
        pattern: ''
    };
    showRuleDialog.value = true;
};
const editRule = (rule) => {
    editingRule.value = rule;
    ruleForm.value = { ...rule };
    showRuleDialog.value = true;
};
const closeRuleDialog = () => {
    showRuleDialog.value = false;
    editingRule.value = null;
};
const saveRule = async () => {
    try {
        // 这里应该调用API保存规则
        console.log('保存规则:', ruleForm.value);
        ant_design_vue_1.message.success('规则保存成功');
        closeRuleDialog();
        await refreshRules();
    }
    catch (error) {
        console.error('保存规则失败:', error);
        ant_design_vue_1.message.error('保存规则失败');
    }
};
const toggleRule = async (rule) => {
    try {
        // 这里应该调用API切换规则状态
        rule.isActive = !rule.isActive;
        ant_design_vue_1.message.success(`规则已${rule.isActive ? '启用' : '禁用'}`);
    }
    catch (error) {
        console.error('切换规则状态失败:', error);
        ant_design_vue_1.message.error('操作失败');
    }
};
const deleteRule = async (rule) => {
    try {
        // 这里应该调用API删除规则
        const index = qcRules.value.findIndex(r => r.id === rule.id);
        if (index !== -1) {
            qcRules.value.splice(index, 1);
        }
        ant_design_vue_1.message.success('规则已删除');
    }
    catch (error) {
        console.error('删除规则失败:', error);
        ant_design_vue_1.message.error('删除失败');
    }
};
const loadDefaultRules = async () => {
    try {
        await loadQCRules();
        ant_design_vue_1.message.success('默认规则已加载');
    }
    catch (error) {
        console.error('加载默认规则失败:', error);
        ant_design_vue_1.message.error('加载失败');
    }
};
const clearLogs = () => {
    recentResults.value.splice(0);
    ant_design_vue_1.message.success('日志已清空');
};
// 工具函数
const getRuleTypeText = (type) => {
    const texts = {
        content: '内容',
        format: '格式',
        logic: '逻辑',
        completeness: '完整性'
    };
    return texts[type] || type;
};
const getSeverityText = (severity) => {
    const texts = {
        critical: '严重',
        error: '错误',
        warning: '警告',
        info: '信息'
    };
    return texts[severity];
};
const getLevelText = (level) => {
    return getSeverityText(level);
};
const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};
// 生命周期
(0, vue_1.onMounted)(async () => {
    console.log('实时质控监控页面已加载');
    await refreshRules();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['form-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-item']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-header']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['realtime-qc-view']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['status-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['status-active']} */ ;
/** @type {__VLS_StyleScopedClasses['status-inactive']} */ ;
/** @type {__VLS_StyleScopedClasses['status-text']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['section-card']} */ ;
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
/** @type {__VLS_StyleScopedClasses['card-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-refresh']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-add']} */ ;
/** @type {__VLS_StyleScopedClasses['card-content']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-load-default']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-list']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-item']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-inactive']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-info']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-header']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-name']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-type']} */ ;
/** @type {__VLS_StyleScopedClasses['type-content']} */ ;
/** @type {__VLS_StyleScopedClasses['type-format']} */ ;
/** @type {__VLS_StyleScopedClasses['type-logic']} */ ;
/** @type {__VLS_StyleScopedClasses['type-completeness']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-severity']} */ ;
/** @type {__VLS_StyleScopedClasses['severity-critical']} */ ;
/** @type {__VLS_StyleScopedClasses['severity-error']} */ ;
/** @type {__VLS_StyleScopedClasses['severity-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['severity-info']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-description']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-enable']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-disable']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-edit']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-delete']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-clear']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-list']} */ ;
/** @type {__VLS_StyleScopedClasses['log-item']} */ ;
/** @type {__VLS_StyleScopedClasses['log-critical']} */ ;
/** @type {__VLS_StyleScopedClasses['log-error']} */ ;
/** @type {__VLS_StyleScopedClasses['log-warning']} */ ;
/** @type {__VLS_StyleScopedClasses['log-info']} */ ;
/** @type {__VLS_StyleScopedClasses['log-info']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-dialog-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-dialog']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-header']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-close']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-input']} */ ;
/** @type {__VLS_StyleScopedClasses['form-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['form-select']} */ ;
/** @type {__VLS_StyleScopedClasses['form-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-cancel']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-save']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-item']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-header']} */ ;
/** @type {__VLS_StyleScopedClasses['log-header']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "realtime-qc-view" },
});
/** @type {[typeof PageHeaderComponent, typeof PageHeaderComponent, ]} */ ;
// @ts-ignore
const __VLS_0 = __VLS_asFunctionalComponent(PageHeaderComponent_vue_1.default, new PageHeaderComponent_vue_1.default({
    title: "实时质控监控",
    subtitle: "病案录入过程中的实时质控分析和预警系统",
}));
const __VLS_1 = __VLS_0({
    title: "实时质控监控",
    subtitle: "病案录入过程中的实时质控分析和预警系统",
}, ...__VLS_functionalComponentArgsRest(__VLS_0));
__VLS_2.slots.default;
{
    const { actions: __VLS_thisSlot } = __VLS_2.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-indicator" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-dot" },
        ...{ class: ({
                'status-active': __VLS_ctx.isMonitoring,
                'status-inactive': !__VLS_ctx.isMonitoring
            }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "status-text" },
    });
    (__VLS_ctx.isMonitoring ? '监控中' : '已停止');
    if (!__VLS_ctx.isMonitoring) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.startMonitoring) },
            ...{ class: "btn-primary" },
            disabled: (__VLS_ctx.isStarting),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-play mr-2" },
        });
        (__VLS_ctx.isStarting ? '启动中...' : '启动监控');
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (__VLS_ctx.stopMonitoring) },
            ...{ class: "btn-secondary" },
            disabled: (__VLS_ctx.isStopping),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-stop mr-2" },
        });
        (__VLS_ctx.isStopping ? '停止中...' : '停止监控');
    }
}
var __VLS_2;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "main-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "dashboard-section" },
});
/** @type {[typeof RealTimeQCDashboard, ]} */ ;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent(RealTimeQCDashboard_vue_1.default, new RealTimeQCDashboard_vue_1.default({}));
const __VLS_4 = __VLS_3({}, ...__VLS_functionalComponentArgsRest(__VLS_3));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rules-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "card-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "card-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-rules mr-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "card-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.refreshRules) },
    ...{ class: "btn-refresh" },
    disabled: (__VLS_ctx.isRefreshingRules),
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-sync-alt" },
    ...{ class: ({ 'fa-spin': __VLS_ctx.isRefreshingRules }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.showAddRule) },
    ...{ class: "btn-add" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-plus mr-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "card-content" },
});
if (__VLS_ctx.qcRules.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-clipboard-list text-gray-400 text-4xl mb-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-600" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.loadDefaultRules) },
        ...{ class: "btn-load-default" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rules-list" },
    });
    for (const [rule] of __VLS_getVForSourceType((__VLS_ctx.qcRules))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (rule.id),
            ...{ class: "rule-item" },
            ...{ class: ({ 'rule-inactive': !rule.isActive }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "rule-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "rule-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
            ...{ class: "rule-name" },
        });
        (rule.name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "rule-badges" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "rule-type" },
            ...{ class: (`type-${rule.type}`) },
        });
        (__VLS_ctx.getRuleTypeText(rule.type));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "rule-severity" },
            ...{ class: (`severity-${rule.severity}`) },
        });
        (__VLS_ctx.getSeverityText(rule.severity));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "rule-description" },
        });
        (rule.description);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "rule-meta" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "rule-priority" },
        });
        (rule.priority);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "rule-status" },
        });
        (rule.isActive ? '启用' : '禁用');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "rule-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.qcRules.length === 0))
                        return;
                    __VLS_ctx.toggleRule(rule);
                } },
            ...{ class: "btn-toggle" },
            ...{ class: (rule.isActive ? 'btn-disable' : 'btn-enable') },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: (rule.isActive ? 'fas fa-pause' : 'fas fa-play') },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.qcRules.length === 0))
                        return;
                    __VLS_ctx.editRule(rule);
                } },
            ...{ class: "btn-edit" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-edit" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.qcRules.length === 0))
                        return;
                    __VLS_ctx.deleteRule(rule);
                } },
            ...{ class: "btn-delete" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
            ...{ class: "fas fa-trash" },
        });
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "logs-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "card-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "card-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-file-alt mr-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "card-actions" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
    value: (__VLS_ctx.logFilter),
    ...{ class: "filter-select" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "all",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "critical",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "error",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "warning",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
    value: "info",
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.clearLogs) },
    ...{ class: "btn-clear" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
    ...{ class: "fas fa-trash mr-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "card-content" },
});
if (__VLS_ctx.filteredLogs.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-file-alt text-gray-400 text-4xl mb-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-600" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "logs-list" },
    });
    for (const [log] of __VLS_getVForSourceType((__VLS_ctx.filteredLogs.slice(0, 50)))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (log.id),
            ...{ class: "log-item" },
            ...{ class: (`log-${log.alertLevel}`) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "log-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "log-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "log-time" },
        });
        (__VLS_ctx.formatTime(log.timestamp));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "log-record" },
        });
        (log.recordId.slice(-8));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "log-level" },
            ...{ class: (`level-${log.alertLevel}`) },
        });
        (__VLS_ctx.getLevelText(log.alertLevel));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "log-metrics" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "log-duration" },
        });
        (log.processingTime);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "log-confidence" },
        });
        (Math.round(log.confidence * 100));
        if (log.issues.length > 0) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "log-content" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "log-issues" },
            });
            for (const [issue, idx] of __VLS_getVForSourceType((log.issues.slice(0, 3)))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    key: (idx),
                    ...{ class: "issue-tag" },
                    ...{ class: (`issue-${issue.severity}`) },
                });
                (issue.message);
            }
            if (log.issues.length > 3) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "more-issues" },
                });
                (log.issues.length - 3);
            }
        }
    }
}
/** @type {[typeof RealTimeQCAlert, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(RealTimeQCAlert_vue_1.default, new RealTimeQCAlert_vue_1.default({}));
const __VLS_7 = __VLS_6({}, ...__VLS_functionalComponentArgsRest(__VLS_6));
if (__VLS_ctx.showRuleDialog) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rule-dialog-overlay" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rule-dialog" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "dialog-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "dialog-title" },
    });
    (__VLS_ctx.editingRule ? '编辑规则' : '新增规则');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeRuleDialog) },
        ...{ class: "btn-close" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.i, __VLS_intrinsicElements.i)({
        ...{ class: "fas fa-times" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "dialog-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        value: (__VLS_ctx.ruleForm.name),
        type: "text",
        ...{ class: "form-input" },
        placeholder: "请输入规则名称",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea, __VLS_intrinsicElements.textarea)({
        value: (__VLS_ctx.ruleForm.description),
        ...{ class: "form-textarea" },
        placeholder: "请输入规则描述",
        rows: "3",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        value: (__VLS_ctx.ruleForm.type),
        ...{ class: "form-select" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "content",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "format",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "logic",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "completeness",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.select, __VLS_intrinsicElements.select)({
        value: (__VLS_ctx.ruleForm.severity),
        ...{ class: "form-select" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "info",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "warning",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "error",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.option, __VLS_intrinsicElements.option)({
        value: "critical",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-row" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "number",
        ...{ class: "form-input" },
        min: "1",
        max: "10",
    });
    (__VLS_ctx.ruleForm.priority);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-group" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "checkbox-label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        type: "checkbox",
        ...{ class: "form-checkbox" },
    });
    (__VLS_ctx.ruleForm.isActive);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    if (__VLS_ctx.ruleForm.type === 'content') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "form-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
            ...{ class: "form-label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
            value: (__VLS_ctx.ruleForm.pattern),
            type: "text",
            ...{ class: "form-input" },
            placeholder: "请输入正则表达式",
        });
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "dialog-actions" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.closeRuleDialog) },
        ...{ class: "btn-cancel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.saveRule) },
        ...{ class: "btn-save" },
        disabled: (!__VLS_ctx.isRuleFormValid),
    });
}
/** @type {__VLS_StyleScopedClasses['realtime-qc-view']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['status-indicator']} */ ;
/** @type {__VLS_StyleScopedClasses['status-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['status-active']} */ ;
/** @type {__VLS_StyleScopedClasses['status-inactive']} */ ;
/** @type {__VLS_StyleScopedClasses['status-text']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-primary']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-play']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-secondary']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-stop']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['dashboard-section']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-card']} */ ;
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-rules']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['card-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-refresh']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-sync-alt']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-spin']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-add']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-plus']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['card-content']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-clipboard-list']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-load-default']} */ ;
/** @type {__VLS_StyleScopedClasses['rules-list']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-item']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-inactive']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-info']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-header']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-name']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-badges']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-type']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-severity']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-description']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-priority']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-status']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-toggle']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-edit']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-edit']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-delete']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-card']} */ ;
/** @type {__VLS_StyleScopedClasses['card-header']} */ ;
/** @type {__VLS_StyleScopedClasses['card-title']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-file-alt']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['card-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-select']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-clear']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-trash']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['card-content']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-file-alt']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['logs-list']} */ ;
/** @type {__VLS_StyleScopedClasses['log-item']} */ ;
/** @type {__VLS_StyleScopedClasses['log-header']} */ ;
/** @type {__VLS_StyleScopedClasses['log-info']} */ ;
/** @type {__VLS_StyleScopedClasses['log-time']} */ ;
/** @type {__VLS_StyleScopedClasses['log-record']} */ ;
/** @type {__VLS_StyleScopedClasses['log-level']} */ ;
/** @type {__VLS_StyleScopedClasses['log-metrics']} */ ;
/** @type {__VLS_StyleScopedClasses['log-duration']} */ ;
/** @type {__VLS_StyleScopedClasses['log-confidence']} */ ;
/** @type {__VLS_StyleScopedClasses['log-content']} */ ;
/** @type {__VLS_StyleScopedClasses['log-issues']} */ ;
/** @type {__VLS_StyleScopedClasses['issue-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['more-issues']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-dialog-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-dialog']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-header']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-title']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-close']} */ ;
/** @type {__VLS_StyleScopedClasses['fas']} */ ;
/** @type {__VLS_StyleScopedClasses['fa-times']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-content']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-input']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-select']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-select']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-input']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['checkbox-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-checkbox']} */ ;
/** @type {__VLS_StyleScopedClasses['form-group']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['form-input']} */ ;
/** @type {__VLS_StyleScopedClasses['dialog-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-cancel']} */ ;
/** @type {__VLS_StyleScopedClasses['btn-save']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            RealTimeQCDashboard: RealTimeQCDashboard_vue_1.default,
            RealTimeQCAlert: RealTimeQCAlert_vue_1.default,
            PageHeaderComponent: PageHeaderComponent_vue_1.default,
            isMonitoring: isMonitoring,
            qcRules: qcRules,
            isStarting: isStarting,
            isStopping: isStopping,
            isRefreshingRules: isRefreshingRules,
            logFilter: logFilter,
            showRuleDialog: showRuleDialog,
            editingRule: editingRule,
            ruleForm: ruleForm,
            filteredLogs: filteredLogs,
            isRuleFormValid: isRuleFormValid,
            startMonitoring: startMonitoring,
            stopMonitoring: stopMonitoring,
            refreshRules: refreshRules,
            showAddRule: showAddRule,
            editRule: editRule,
            closeRuleDialog: closeRuleDialog,
            saveRule: saveRule,
            toggleRule: toggleRule,
            deleteRule: deleteRule,
            loadDefaultRules: loadDefaultRules,
            clearLogs: clearLogs,
            getRuleTypeText: getRuleTypeText,
            getSeverityText: getSeverityText,
            getLevelText: getLevelText,
            formatTime: formatTime,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
