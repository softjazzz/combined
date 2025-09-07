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
import ant_design_vue_1 from 'ant-design-vue';
const dayjs_1 = __importDefault(require("dayjs"));
const props = defineProps();
const emit = defineEmits();
// 辅助函数
const getScoreColor = (score) => {
    if (score >= 90)
        return '#52c41a';
    if (score >= 75)
        return '#faad14';
    return '#ff4d4f';
};
const getGradeColor = (grade) => {
    switch (grade) {
        case '甲级': return '#52c41a';
        case '乙级': return '#faad14';
        case '丙级': return '#ff4d4f';
        default: return '#666';
    }
};
const getRiskColor = (level) => {
    switch (level) {
        case 'low': return '#52c41a';
        case 'medium': return '#faad14';
        case 'high': return '#ff7875';
        case 'critical': return '#ff4d4f';
        default: return '#666';
    }
};
const getRiskText = (level) => {
    switch (level) {
        case 'low': return '低风险';
        case 'medium': return '中风险';
        case 'high': return '高风险';
        case 'critical': return '严重风险';
        default: return '未知';
    }
};
const getSeverityColor = (severity) => {
    switch (severity) {
        case 'low': return 'default';
        case 'medium': return 'orange';
        case 'high': return 'red';
        case 'critical': return 'red';
        default: return 'default';
    }
};
const getSeverityText = (severity) => {
    switch (severity) {
        case 'low': return '轻微';
        case 'medium': return '中等';
        case 'high': return '严重';
        case 'critical': return '危急';
        default: return '未知';
    }
};
const getCheckTypeText = (checkType) => {
    switch (checkType) {
        case 'admission_record': return '入院记录';
        case 'progress_note': return '病程记录';
        case 'surgery_record': return '手术记录';
        case 'discharge_record': return '出院记录';
        default: return '未知检查';
    }
};
const getAnalysisTypeText = (analysisType) => {
    switch (analysisType) {
        case 'real-time': return '实时分析';
        case 'scheduled': return '定时分析';
        case 'triggered': return '触发分析';
        default: return '未知';
    }
};
const formatTime = (timeString) => {
    return (0, dayjs_1.default)(timeString).format('YYYY-MM-DD HH:mm:ss');
};
// 操作方法
const exportReport = () => {
    // 实现导出报告功能
    ant_design_vue_1.message.success('报告导出功能开发中...');
};
const scheduleRecheck = () => {
    // 实现安排复查功能
    ant_design_vue_1.message.success('复查安排功能开发中...');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "running-qc-result" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "质控概览",
    ...{ class: "mb-4" },
}));
const __VLS_2 = __VLS_1({
    title: "质控概览",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    gutter: (24),
}));
const __VLS_6 = __VLS_5({
    gutter: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    span: (6),
}));
const __VLS_10 = __VLS_9({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    title: "总体评分",
    value: (__VLS_ctx.result.summary.totalScore),
    suffix: "分",
    valueStyle: ({ color: __VLS_ctx.getScoreColor(__VLS_ctx.result.summary.totalScore) }),
}));
const __VLS_14 = __VLS_13({
    title: "总体评分",
    value: (__VLS_ctx.result.summary.totalScore),
    suffix: "分",
    valueStyle: ({ color: __VLS_ctx.getScoreColor(__VLS_ctx.result.summary.totalScore) }),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
var __VLS_11;
const __VLS_16 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    span: (6),
}));
const __VLS_18 = __VLS_17({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
const __VLS_20 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    title: "质控等级",
    value: (__VLS_ctx.result.summary.grade),
    valueStyle: ({ color: __VLS_ctx.getGradeColor(__VLS_ctx.result.summary.grade) }),
}));
const __VLS_22 = __VLS_21({
    title: "质控等级",
    value: (__VLS_ctx.result.summary.grade),
    valueStyle: ({ color: __VLS_ctx.getGradeColor(__VLS_ctx.result.summary.grade) }),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
var __VLS_19;
const __VLS_24 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    span: (6),
}));
const __VLS_26 = __VLS_25({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    title: "风险等级",
    value: (__VLS_ctx.getRiskText(__VLS_ctx.result.summary.riskLevel)),
    valueStyle: ({ color: __VLS_ctx.getRiskColor(__VLS_ctx.result.summary.riskLevel) }),
}));
const __VLS_30 = __VLS_29({
    title: "风险等级",
    value: (__VLS_ctx.getRiskText(__VLS_ctx.result.summary.riskLevel)),
    valueStyle: ({ color: __VLS_ctx.getRiskColor(__VLS_ctx.result.summary.riskLevel) }),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
var __VLS_27;
const __VLS_32 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    span: (6),
}));
const __VLS_34 = __VLS_33({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    title: "下次检查",
    value: (__VLS_ctx.formatTime(__VLS_ctx.result.nextCheckTime)),
    valueStyle: ({ fontSize: '14px' }),
}));
const __VLS_38 = __VLS_37({
    title: "下次检查",
    value: (__VLS_ctx.formatTime(__VLS_ctx.result.nextCheckTime)),
    valueStyle: ({ fontSize: '14px' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
var __VLS_35;
var __VLS_7;
var __VLS_3;
if (__VLS_ctx.result.realTimeIssues.length > 0) {
    const __VLS_40 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        title: "实时质控问题",
        ...{ class: "mb-4" },
    }));
    const __VLS_42 = __VLS_41({
        title: "实时质控问题",
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    const __VLS_44 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        dataSource: (__VLS_ctx.result.realTimeIssues),
        itemLayout: "horizontal",
    }));
    const __VLS_46 = __VLS_45({
        dataSource: (__VLS_ctx.result.realTimeIssues),
        itemLayout: "horizontal",
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_47.slots;
        const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_48 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
        const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
        __VLS_51.slots.default;
        const __VLS_52 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
        const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
        __VLS_55.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_55.slots;
            const __VLS_56 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
            const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
            __VLS_59.slots.default;
            const __VLS_60 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
                color: (__VLS_ctx.getSeverityColor(item.severity)),
            }));
            const __VLS_62 = __VLS_61({
                color: (__VLS_ctx.getSeverityColor(item.severity)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_61));
            __VLS_63.slots.default;
            (__VLS_ctx.getSeverityText(item.severity));
            var __VLS_63;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.qualityPointName);
            if (item.isUrgent) {
                const __VLS_64 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
                    color: "red",
                }));
                const __VLS_66 = __VLS_65({
                    color: "red",
                }, ...__VLS_functionalComponentArgsRest(__VLS_65));
                __VLS_67.slots.default;
                var __VLS_67;
            }
            if (item.requiresImmediateAction) {
                const __VLS_68 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
                    color: "orange",
                }));
                const __VLS_70 = __VLS_69({
                    color: "orange",
                }, ...__VLS_functionalComponentArgsRest(__VLS_69));
                __VLS_71.slots.default;
                var __VLS_71;
            }
            var __VLS_59;
        }
        {
            const { description: __VLS_thisSlot } = __VLS_55.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "mb-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.content);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "mb-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.suggestion);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.deductionScore);
            const __VLS_72 = {}.ADivider;
            /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
            // @ts-ignore
            const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
                type: "vertical",
            }));
            const __VLS_74 = __VLS_73({
                type: "vertical",
            }, ...__VLS_functionalComponentArgsRest(__VLS_73));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.department);
            const __VLS_76 = {}.ADivider;
            /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
            // @ts-ignore
            const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
                type: "vertical",
            }));
            const __VLS_78 = __VLS_77({
                type: "vertical",
            }, ...__VLS_functionalComponentArgsRest(__VLS_77));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.qualityPointId);
        }
        var __VLS_55;
        var __VLS_51;
    }
    var __VLS_47;
    var __VLS_43;
}
if (__VLS_ctx.result.departmentSpecificIssues.length > 0) {
    const __VLS_80 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        title: "科室特定问题",
        ...{ class: "mb-4" },
    }));
    const __VLS_82 = __VLS_81({
        title: "科室特定问题",
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    const __VLS_84 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        dataSource: (__VLS_ctx.result.departmentSpecificIssues),
        itemLayout: "horizontal",
    }));
    const __VLS_86 = __VLS_85({
        dataSource: (__VLS_ctx.result.departmentSpecificIssues),
        itemLayout: "horizontal",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_87.slots;
        const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_88 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
        const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
        __VLS_91.slots.default;
        const __VLS_92 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({}));
        const __VLS_94 = __VLS_93({}, ...__VLS_functionalComponentArgsRest(__VLS_93));
        __VLS_95.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_95.slots;
            const __VLS_96 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({}));
            const __VLS_98 = __VLS_97({}, ...__VLS_functionalComponentArgsRest(__VLS_97));
            __VLS_99.slots.default;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.qualityPointName);
            if (item.isEffectiveToDoctor) {
                const __VLS_100 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
                    color: "blue",
                }));
                const __VLS_102 = __VLS_101({
                    color: "blue",
                }, ...__VLS_functionalComponentArgsRest(__VLS_101));
                __VLS_103.slots.default;
                var __VLS_103;
            }
            var __VLS_99;
        }
        {
            const { description: __VLS_thisSlot } = __VLS_95.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "mb-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.content);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.suggestion);
        }
        var __VLS_95;
        var __VLS_91;
    }
    var __VLS_87;
    var __VLS_83;
}
if (__VLS_ctx.result.timelinessChecks.length > 0) {
    const __VLS_104 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        title: "时效性检查",
        ...{ class: "mb-4" },
    }));
    const __VLS_106 = __VLS_105({
        title: "时效性检查",
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    __VLS_107.slots.default;
    const __VLS_108 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        dataSource: (__VLS_ctx.result.timelinessChecks),
        itemLayout: "horizontal",
    }));
    const __VLS_110 = __VLS_109({
        dataSource: (__VLS_ctx.result.timelinessChecks),
        itemLayout: "horizontal",
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    __VLS_111.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_111.slots;
        const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_112 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
        const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        const __VLS_116 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
        const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
        __VLS_119.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_119.slots;
            const __VLS_120 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({}));
            const __VLS_122 = __VLS_121({}, ...__VLS_functionalComponentArgsRest(__VLS_121));
            __VLS_123.slots.default;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.getCheckTypeText(item.checkType));
            if (item.isOverdue) {
                const __VLS_124 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
                    color: "red",
                }));
                const __VLS_126 = __VLS_125({
                    color: "red",
                }, ...__VLS_functionalComponentArgsRest(__VLS_125));
                __VLS_127.slots.default;
                var __VLS_127;
            }
            else {
                const __VLS_128 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
                    color: "green",
                }));
                const __VLS_130 = __VLS_129({
                    color: "green",
                }, ...__VLS_functionalComponentArgsRest(__VLS_129));
                __VLS_131.slots.default;
                var __VLS_131;
            }
            var __VLS_123;
        }
        {
            const { description: __VLS_thisSlot } = __VLS_119.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "mb-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (__VLS_ctx.formatTime(item.expectedTime));
            if (item.actualTime) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "ml-4" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (__VLS_ctx.formatTime(item.actualTime));
            }
            if (item.isOverdue) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "mb-2" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
                (item.overdueHours);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
            (item.suggestion);
        }
        var __VLS_119;
        var __VLS_115;
    }
    var __VLS_111;
    var __VLS_107;
}
if (__VLS_ctx.result.recommendations.length > 0) {
    const __VLS_132 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        title: "改进建议",
        ...{ class: "mb-4" },
    }));
    const __VLS_134 = __VLS_133({
        title: "改进建议",
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    const __VLS_136 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        dataSource: (__VLS_ctx.result.recommendations),
        size: "small",
    }));
    const __VLS_138 = __VLS_137({
        dataSource: (__VLS_ctx.result.recommendations),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_139.slots;
        const [{ item, index }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_140 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({}));
        const __VLS_142 = __VLS_141({}, ...__VLS_functionalComponentArgsRest(__VLS_141));
        __VLS_143.slots.default;
        const __VLS_144 = {}.ATypographyText;
        /** @type {[typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({}));
        const __VLS_146 = __VLS_145({}, ...__VLS_functionalComponentArgsRest(__VLS_145));
        __VLS_147.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (index + 1);
        (item);
        var __VLS_147;
        var __VLS_143;
    }
    var __VLS_139;
    var __VLS_135;
}
const __VLS_148 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    title: "分析信息",
    ...{ class: "mb-4" },
}));
const __VLS_150 = __VLS_149({
    title: "分析信息",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
__VLS_151.slots.default;
const __VLS_152 = {}.ADescriptions;
/** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
    column: (2),
    size: "small",
}));
const __VLS_154 = __VLS_153({
    column: (2),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_153));
__VLS_155.slots.default;
const __VLS_156 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    label: "病历ID",
}));
const __VLS_158 = __VLS_157({
    label: "病历ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
__VLS_159.slots.default;
(__VLS_ctx.result.recordId);
var __VLS_159;
const __VLS_160 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
    label: "患者ID",
}));
const __VLS_162 = __VLS_161({
    label: "患者ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_161));
__VLS_163.slots.default;
(__VLS_ctx.result.patientId);
var __VLS_163;
const __VLS_164 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    label: "分析类型",
}));
const __VLS_166 = __VLS_165({
    label: "分析类型",
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
__VLS_167.slots.default;
(__VLS_ctx.getAnalysisTypeText(__VLS_ctx.result.analysisType));
var __VLS_167;
const __VLS_168 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
    label: "分析时间",
}));
const __VLS_170 = __VLS_169({
    label: "分析时间",
}, ...__VLS_functionalComponentArgsRest(__VLS_169));
__VLS_171.slots.default;
(__VLS_ctx.formatTime(__VLS_ctx.result.analysisTime));
var __VLS_171;
const __VLS_172 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    label: "总体评估",
    span: (2),
}));
const __VLS_174 = __VLS_173({
    label: "总体评估",
    span: (2),
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
__VLS_175.slots.default;
(__VLS_ctx.result.summary.overallAssessment);
var __VLS_175;
var __VLS_155;
var __VLS_151;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center" },
});
const __VLS_176 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({}));
const __VLS_178 = __VLS_177({}, ...__VLS_functionalComponentArgsRest(__VLS_177));
__VLS_179.slots.default;
const __VLS_180 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
    ...{ 'onClick': {} },
}));
const __VLS_182 = __VLS_181({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_181));
let __VLS_184;
let __VLS_185;
let __VLS_186;
const __VLS_187 = {
    onClick: (...[$event]) => {
        __VLS_ctx.$emit('close');
    }
};
__VLS_183.slots.default;
var __VLS_183;
const __VLS_188 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_190 = __VLS_189({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_189));
let __VLS_192;
let __VLS_193;
let __VLS_194;
const __VLS_195 = {
    onClick: (__VLS_ctx.exportReport)
};
__VLS_191.slots.default;
var __VLS_191;
const __VLS_196 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    ...{ 'onClick': {} },
}));
const __VLS_198 = __VLS_197({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
let __VLS_200;
let __VLS_201;
let __VLS_202;
const __VLS_203 = {
    onClick: (__VLS_ctx.scheduleRecheck)
};
__VLS_199.slots.default;
var __VLS_199;
var __VLS_179;
/** @type {__VLS_StyleScopedClasses['running-qc-result']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            getScoreColor: getScoreColor,
            getGradeColor: getGradeColor,
            getRiskColor: getRiskColor,
            getRiskText: getRiskText,
            getSeverityColor: getSeverityColor,
            getSeverityText: getSeverityText,
            getCheckTypeText: getCheckTypeText,
            getAnalysisTypeText: getAnalysisTypeText,
            formatTime: formatTime,
            exportReport: exportReport,
            scheduleRecheck: scheduleRecheck,
        };
    },
    __typeEmits: {},
    __typeProps: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
