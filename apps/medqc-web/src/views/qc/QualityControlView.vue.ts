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
const QCResultDisplay_vue_1 = __importDefault(require("@/components/qc/QCResultDisplay.vue"));
const ContentHighlighter_vue_1 = __importDefault(require("@/components/qc/ContentHighlighter.vue"));
const SuggestionPanel_vue_1 = __importDefault(require("@/components/qc/SuggestionPanel.vue"));
const RuleConfiguration_vue_1 = __importDefault(require("@/components/qc/RuleConfiguration.vue"));
const AnalysisProgress_vue_1 = __importDefault(require("@/components/qc/AnalysisProgress.vue"));
import apiService_1 from '@/services/apiService';
// 组件引用
const analysisProgressRef = (0, vue_1.ref)();
// 状态
const isAnalyzing = (0, vue_1.ref)(false);
const showRuleConfig = (0, vue_1.ref)(false);
const showRecordSelector = (0, vue_1.ref)(false);
const activeIssue = (0, vue_1.ref)(null);
// 当前分析任务
const currentAnalysis = (0, vue_1.ref)(null);
// 分析结果
const analysisResult = (0, vue_1.ref)(null);
// 记录内容
const recordContent = (0, vue_1.ref)('');
// 质控规则
const qcRules = (0, vue_1.ref)(: any[]);
// 历史记录
const historyRecords = (0, vue_1.ref)(: any[]);
// 可用记录
const availableRecords = (0, vue_1.ref)(: any[]);
// 初始化页面
(0, vue_1.onMounted)(async () => {
    await loadHistoryRecords();
    await loadAvailableRecords();
    await loadQCRules();
});
// 加载历史记录
const loadHistoryRecords = async () => {
    try {
        const response = await apiService_1.ApiService.getQCHistory();
        if (response.success && response.data) {
            historyRecords.value = response.data;
        }
    }
    catch (error) {
        console.error('加载历史记录失败:', error);
    }
};
// 加载可用记录
const loadAvailableRecords = async () => {
    try {
        const response = await apiService_1.ApiService.getMedicalRecords();
        if (response.success && response.data) {
            availableRecords.value = response.data.data;
        }
    }
    catch (error) {
        console.error('加载可用记录失败:', error);
    }
};
// 加载质控规则
const loadQCRules = async () => {
    try {
        const response = await apiService_1.ApiService.getQCRules();
        if (response.success && response.data) {
            qcRules.value = response.data;
        }
    }
    catch (error) {
        console.error('加载质控规则失败:', error);
    }
};
// 开始新分析
const startNewAnalysis = () => {
    showRecordSelector.value = true;
};
// 选择记录进行分析
const selectRecord = async (record) => {
    showRecordSelector.value = false;
    currentAnalysis.value = {
        recordId: record.id,
        recordName: record.patient_name
    };
    recordContent.value = record.content;
    isAnalyzing.value = true;
    // 开始分析进度
    analysisProgressRef.value?.startAnalysis();
};
// 处理分析完成
const handleAnalysisCompleted = async (result) => {
    try {
        // 获取分析结果
        const response = await apiService_1.ApiService.getQCResult(currentAnalysis.value.recordId);
        if (response.success && response.data) {
            analysisResult.value = response.data;
            ant_design_vue_1.message.success('质控分析完成');
        }
    }
    catch (error) {
        console.error('获取分析结果失败:', error);
        ant_design_vue_1.message.error('获取分析结果失败');
    }
    finally {
        isAnalyzing.value = false;
        currentAnalysis.value = null;
    }
};
// 处理分析失败
const handleAnalysisFailed = (error) => {
    ant_design_vue_1.message.error(`分析失败: ${error}`);
    isAnalyzing.value = false;
    currentAnalysis.value = null;
};
// 处理分析暂停
const handleAnalysisPaused = () => {
    ant_design_vue_1.message.info('分析已暂停');
};
// 处理分析恢复
const handleAnalysisResumed = () => {
    ant_design_vue_1.message.info('分析已恢复');
};
// 处理分析停止
const handleAnalysisStopped = () => {
    ant_design_vue_1.message.warning('分析已停止');
    isAnalyzing.value = false;
    currentAnalysis.value = null;
};
// 处理问题高亮
const handleHighlightIssue = (issue) => {
    activeIssue.value = issue;
};
// 处理问题点击
const handleIssueClick = (issue) => {
    activeIssue.value = issue;
    ant_design_vue_1.message.info(`已定位到问题: ${issue.rule_name}`);
};
// 处理建议实施
const handleSuggestionImplemented = (suggestionId) => {
    // 更新建议状态
    console.log('建议已实施:', suggestionId);
};
// 处理建议保存
const handleSuggestionSaved = (suggestionId) => {
    // 保存建议
    console.log('建议已保存:', suggestionId);
};
// 处理规则更新
const handleRuleUpdated = (rule) => {
    const index = qcRules.value.findIndex(r => r.id === rule.id);
    if (index > -1) {
        qcRules.value[index] = rule;
    }
};
// 处理规则创建
const handleRuleCreated = (rule) => {
    qcRules.value.unshift(rule);
};
// 处理规则删除
const handleRuleDeleted = (ruleId) => {
    const index = qcRules.value.findIndex(r => r.id === ruleId);
    if (index > -1) {
        qcRules.value.splice(index, 1);
    }
};
// 加载历史记录
const loadHistoryRecord = async (record) => {
    try {
        const response = await apiService_1.ApiService.getQCResult(record.id);
        if (response.success && response.data) {
            analysisResult.value = response.data;
            recordContent.value = record.content || '历史记录内容...';
            activeIssue.value = null;
            ant_design_vue_1.message.success(`已加载 ${record.patient_name} 的分析结果`);
        }
    }
    catch (error) {
        console.error('加载历史记录失败:', error);
        ant_design_vue_1.message.error('加载历史记录失败');
    }
};
// 样式相关方法
const getScoreColor = (score) => {
    if (score >= 90)
        return 'text-emerald-400';
    if (score >= 80)
        return 'text-blue-400';
    if (score >= 70)
        return 'text-amber-400';
    return 'text-red-400';
};
const getGradeColor = (grade) => {
    const colors = {
        A: 'green',
        B: 'blue',
        C: 'orange'
    };
    return colors[grade] || 'default';
};
const getRecordStatusColor = (status) => {
    const colors = {
        pending: 'orange',
        analyzing: 'blue',
        completed: 'green',
        failed: 'red'
    };
    return colors[status] || 'default';
};
const getRecordStatusLabel = (status) => {
    const labels = {
        pending: '待处理',
        analyzing: '分析中',
        completed: '已完成',
        failed: '失败'
    };
    return labels[status] || status;
};
const formatDate = (dateString) => {
    try {
        return new Date(dateString).toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        });
    }
    catch {
        return dateString;
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['rule-config-drawer']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-config-drawer']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-config-drawer']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-config-drawer']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-drawer-close']} */ ;
/** @type {__VLS_StyleScopedClasses['record-selector-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['record-selector-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['record-selector-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['record-selector-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-modal-close']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "quality-control-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-7xl mx-auto p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-8 h-8 rounded-lg bg-gradient-to-br from-purple-400 to-indigo-600 flex items-center justify-center" },
});
const __VLS_0 = {}.ThunderboltOutlined;
/** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-white text-sm" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-white text-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-2xl font-bold text-slate-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-slate-400 text-sm" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3" },
});
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30" },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showRuleConfig = true;
    }
};
__VLS_7.slots.default;
const __VLS_12 = {}.SettingOutlined;
/** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
var __VLS_7;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.isAnalyzing),
    ...{ class: "bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-400 hover:to-indigo-500 border-none" },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.isAnalyzing),
    ...{ class: "bg-gradient-to-r from-purple-500 to-indigo-600 hover:from-purple-400 hover:to-indigo-500 border-none" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.startNewAnalysis)
};
__VLS_19.slots.default;
const __VLS_24 = {}.ThunderboltOutlined;
/** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
var __VLS_19;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-8" },
});
if (__VLS_ctx.currentAnalysis) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "analysis-section" },
    });
    /** @type {[typeof AnalysisProgress, ]} */ ;
    // @ts-ignore
    const __VLS_28 = __VLS_asFunctionalComponent(AnalysisProgress_vue_1.default, new AnalysisProgress_vue_1.default({
        ...{ 'onAnalysisCompleted': {} },
        ...{ 'onAnalysisFailed': {} },
        ...{ 'onAnalysisPaused': {} },
        ...{ 'onAnalysisResumed': {} },
        ...{ 'onAnalysisStopped': {} },
        ref: "analysisProgressRef",
        recordId: (__VLS_ctx.currentAnalysis.recordId),
    }));
    const __VLS_29 = __VLS_28({
        ...{ 'onAnalysisCompleted': {} },
        ...{ 'onAnalysisFailed': {} },
        ...{ 'onAnalysisPaused': {} },
        ...{ 'onAnalysisResumed': {} },
        ...{ 'onAnalysisStopped': {} },
        ref: "analysisProgressRef",
        recordId: (__VLS_ctx.currentAnalysis.recordId),
    }, ...__VLS_functionalComponentArgsRest(__VLS_28));
    let __VLS_31;
    let __VLS_32;
    let __VLS_33;
    const __VLS_34 = {
        onAnalysisCompleted: (__VLS_ctx.handleAnalysisCompleted)
    };
    const __VLS_35 = {
        onAnalysisFailed: (__VLS_ctx.handleAnalysisFailed)
    };
    const __VLS_36 = {
        onAnalysisPaused: (__VLS_ctx.handleAnalysisPaused)
    };
    const __VLS_37 = {
        onAnalysisResumed: (__VLS_ctx.handleAnalysisResumed)
    };
    const __VLS_38 = {
        onAnalysisStopped: (__VLS_ctx.handleAnalysisStopped)
    };
    /** @type {typeof __VLS_ctx.analysisProgressRef} */ ;
    var __VLS_39 = {};
    var __VLS_30;
}
if (__VLS_ctx.analysisResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "results-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
        ...{ class: "text-xl font-semibold text-slate-100 flex items-center gap-2 mb-2" },
    });
    const __VLS_41 = {}.TrophyOutlined;
    /** @type {[typeof __VLS_components.TrophyOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({
        ...{ class: "text-cyan-400" },
    }));
    const __VLS_43 = __VLS_42({
        ...{ class: "text-cyan-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_42));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-slate-400" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid grid-cols-1 xl:grid-cols-3 gap-8" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "xl:col-span-2 space-y-6" },
    });
    /** @type {[typeof QCResultDisplay, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(QCResultDisplay_vue_1.default, new QCResultDisplay_vue_1.default({
        ...{ 'onHighlightIssue': {} },
        result: (__VLS_ctx.analysisResult),
    }));
    const __VLS_46 = __VLS_45({
        ...{ 'onHighlightIssue': {} },
        result: (__VLS_ctx.analysisResult),
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    let __VLS_48;
    let __VLS_49;
    let __VLS_50;
    const __VLS_51 = {
        onHighlightIssue: (__VLS_ctx.handleHighlightIssue)
    };
    var __VLS_47;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "space-y-6" },
    });
    /** @type {[typeof ContentHighlighter, ]} */ ;
    // @ts-ignore
    const __VLS_52 = __VLS_asFunctionalComponent(ContentHighlighter_vue_1.default, new ContentHighlighter_vue_1.default({
        ...{ 'onIssueClick': {} },
        content: (__VLS_ctx.recordContent),
        issues: (__VLS_ctx.analysisResult.issues),
        activeIssue: (__VLS_ctx.activeIssue),
    }));
    const __VLS_53 = __VLS_52({
        ...{ 'onIssueClick': {} },
        content: (__VLS_ctx.recordContent),
        issues: (__VLS_ctx.analysisResult.issues),
        activeIssue: (__VLS_ctx.activeIssue),
    }, ...__VLS_functionalComponentArgsRest(__VLS_52));
    let __VLS_55;
    let __VLS_56;
    let __VLS_57;
    const __VLS_58 = {
        onIssueClick: (__VLS_ctx.handleIssueClick)
    };
    var __VLS_54;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-8" },
    });
    /** @type {[typeof SuggestionPanel, ]} */ ;
    // @ts-ignore
    const __VLS_59 = __VLS_asFunctionalComponent(SuggestionPanel_vue_1.default, new SuggestionPanel_vue_1.default({
        ...{ 'onSuggestionImplemented': {} },
        ...{ 'onSuggestionSaved': {} },
        suggestions: (__VLS_ctx.analysisResult.suggestions),
    }));
    const __VLS_60 = __VLS_59({
        ...{ 'onSuggestionImplemented': {} },
        ...{ 'onSuggestionSaved': {} },
        suggestions: (__VLS_ctx.analysisResult.suggestions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_59));
    let __VLS_62;
    let __VLS_63;
    let __VLS_64;
    const __VLS_65 = {
        onSuggestionImplemented: (__VLS_ctx.handleSuggestionImplemented)
    };
    const __VLS_66 = {
        onSuggestionSaved: (__VLS_ctx.handleSuggestionSaved)
    };
    var __VLS_61;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "history-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "text-xl font-semibold text-slate-100 flex items-center gap-2 mb-2" },
});
const __VLS_67 = {}.HistoryOutlined;
/** @type {[typeof __VLS_components.HistoryOutlined, ]} */ ;
// @ts-ignore
const __VLS_68 = __VLS_asFunctionalComponent(__VLS_67, new __VLS_67({
    ...{ class: "text-emerald-400" },
}));
const __VLS_69 = __VLS_68({
    ...{ class: "text-emerald-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_68));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-sm text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
for (const [record] of __VLS_getVForSourceType((__VLS_ctx.historyRecords))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.loadHistoryRecord(record);
            } },
        key: (record.id),
        ...{ class: "p-4 rounded-lg border border-slate-600/30 bg-slate-700/20 hover:border-slate-500/50 hover:bg-slate-700/30 transition-all duration-300 cursor-pointer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-12 h-12 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-bold" },
    });
    (record.patient_name.charAt(0));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "font-medium text-slate-100" },
    });
    (record.patient_name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-3 text-sm text-slate-400" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (record.department);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.formatDate(record.analysis_date));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-lg font-bold" },
        ...{ class: (__VLS_ctx.getScoreColor(record.overall_score)) },
    });
    (record.overall_score);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-slate-400" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-lg font-bold text-red-400" },
    });
    (record.issue_count);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-slate-400" },
    });
    const __VLS_71 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_72 = __VLS_asFunctionalComponent(__VLS_71, new __VLS_71({
        color: (__VLS_ctx.getGradeColor(record.overall_grade)),
        size: "small",
    }));
    const __VLS_73 = __VLS_72({
        color: (__VLS_ctx.getGradeColor(record.overall_grade)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_72));
    __VLS_74.slots.default;
    (record.overall_grade);
    var __VLS_74;
}
if (__VLS_ctx.historyRecords.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-8" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-3" },
    });
    const __VLS_75 = {}.HistoryOutlined;
    /** @type {[typeof __VLS_components.HistoryOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_76 = __VLS_asFunctionalComponent(__VLS_75, new __VLS_75({
        ...{ class: "text-slate-400 text-2xl" },
    }));
    const __VLS_77 = __VLS_76({
        ...{ class: "text-slate-400 text-2xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_76));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-slate-400" },
    });
}
const __VLS_79 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_80 = __VLS_asFunctionalComponent(__VLS_79, new __VLS_79({
    open: (__VLS_ctx.showRuleConfig),
    title: "质控规则配置",
    width: "80%",
    placement: "right",
    ...{ class: "rule-config-drawer" },
}));
const __VLS_81 = __VLS_80({
    open: (__VLS_ctx.showRuleConfig),
    title: "质控规则配置",
    width: "80%",
    placement: "right",
    ...{ class: "rule-config-drawer" },
}, ...__VLS_functionalComponentArgsRest(__VLS_80));
__VLS_82.slots.default;
/** @type {[typeof RuleConfiguration, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(RuleConfiguration_vue_1.default, new RuleConfiguration_vue_1.default({
    ...{ 'onRuleUpdated': {} },
    ...{ 'onRuleCreated': {} },
    ...{ 'onRuleDeleted': {} },
    rules: (__VLS_ctx.qcRules),
}));
const __VLS_84 = __VLS_83({
    ...{ 'onRuleUpdated': {} },
    ...{ 'onRuleCreated': {} },
    ...{ 'onRuleDeleted': {} },
    rules: (__VLS_ctx.qcRules),
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
let __VLS_86;
let __VLS_87;
let __VLS_88;
const __VLS_89 = {
    onRuleUpdated: (__VLS_ctx.handleRuleUpdated)
};
const __VLS_90 = {
    onRuleCreated: (__VLS_ctx.handleRuleCreated)
};
const __VLS_91 = {
    onRuleDeleted: (__VLS_ctx.handleRuleDeleted)
};
var __VLS_85;
var __VLS_82;
const __VLS_92 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    open: (__VLS_ctx.showRecordSelector),
    title: "选择要分析的记录",
    footer: (null),
    width: "800px",
    ...{ class: "record-selector-modal" },
}));
const __VLS_94 = __VLS_93({
    open: (__VLS_ctx.showRecordSelector),
    title: "选择要分析的记录",
    footer: (null),
    width: "800px",
    ...{ class: "record-selector-modal" },
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-h-96 overflow-y-auto" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-3" },
});
for (const [record] of __VLS_getVForSourceType((__VLS_ctx.availableRecords))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.selectRecord(record);
            } },
        key: (record.id),
        ...{ class: "p-4 rounded-lg border border-slate-600/30 bg-slate-700/20 hover:border-cyan-500/50 hover:bg-cyan-500/10 transition-all duration-300 cursor-pointer" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-10 h-10 rounded-full bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-white font-semibold" },
    });
    (record.patient_name.charAt(0));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "font-medium text-slate-100" },
    });
    (record.patient_name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-slate-400" },
    });
    (record.department);
    (record.record_type);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-2" },
    });
    const __VLS_96 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        color: (__VLS_ctx.getRecordStatusColor(record.status)),
        size: "small",
    }));
    const __VLS_98 = __VLS_97({
        color: (__VLS_ctx.getRecordStatusColor(record.status)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    __VLS_99.slots.default;
    (__VLS_ctx.getRecordStatusLabel(record.status));
    var __VLS_99;
}
var __VLS_95;
/** @type {__VLS_StyleScopedClasses['quality-control-view']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-purple-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-purple-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-purple-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-r']} */ ;
/** @type {__VLS_StyleScopedClasses['from-purple-500']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:from-purple-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:to-indigo-500']} */ ;
/** @type {__VLS_StyleScopedClasses['border-none']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-8']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-section']} */ ;
/** @type {__VLS_StyleScopedClasses['results-section']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['xl:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-8']} */ ;
/** @type {__VLS_StyleScopedClasses['xl:col-span-2']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-8']} */ ;
/** @type {__VLS_StyleScopedClasses['history-section']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/20']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-slate-500/50']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['w-16']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['rule-config-drawer']} */ ;
/** @type {__VLS_StyleScopedClasses['record-selector-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-96']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-3']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/20']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-cyan-500/50']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-cyan-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-10']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
// @ts-ignore
var __VLS_40 = __VLS_39;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            TrophyOutlined: icons_vue_1.TrophyOutlined,
            HistoryOutlined: icons_vue_1.HistoryOutlined,
            QCResultDisplay: QCResultDisplay_vue_1.default,
            ContentHighlighter: ContentHighlighter_vue_1.default,
            SuggestionPanel: SuggestionPanel_vue_1.default,
            RuleConfiguration: RuleConfiguration_vue_1.default,
            AnalysisProgress: AnalysisProgress_vue_1.default,
            analysisProgressRef: analysisProgressRef,
            isAnalyzing: isAnalyzing,
            showRuleConfig: showRuleConfig,
            showRecordSelector: showRecordSelector,
            activeIssue: activeIssue,
            currentAnalysis: currentAnalysis,
            analysisResult: analysisResult,
            recordContent: recordContent,
            qcRules: qcRules,
            historyRecords: historyRecords,
            availableRecords: availableRecords,
            startNewAnalysis: startNewAnalysis,
            selectRecord: selectRecord,
            handleAnalysisCompleted: handleAnalysisCompleted,
            handleAnalysisFailed: handleAnalysisFailed,
            handleAnalysisPaused: handleAnalysisPaused,
            handleAnalysisResumed: handleAnalysisResumed,
            handleAnalysisStopped: handleAnalysisStopped,
            handleHighlightIssue: handleHighlightIssue,
            handleIssueClick: handleIssueClick,
            handleSuggestionImplemented: handleSuggestionImplemented,
            handleSuggestionSaved: handleSuggestionSaved,
            handleRuleUpdated: handleRuleUpdated,
            handleRuleCreated: handleRuleCreated,
            handleRuleDeleted: handleRuleDeleted,
            loadHistoryRecord: loadHistoryRecord,
            getScoreColor: getScoreColor,
            getGradeColor: getGradeColor,
            getRecordStatusColor: getRecordStatusColor,
            getRecordStatusLabel: getRecordStatusLabel,
            formatDate: formatDate,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
