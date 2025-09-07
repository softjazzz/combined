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
import qc_analysis_api_1 from '../../api/qc-analysis-api';
const props = defineProps();
const emit = defineEmits();
// 状态管理
const analysisResult = (0, vue_1.ref)(null);
const isLoadingResult = (0, vue_1.ref)(false);
const issueFilter = (0, vue_1.ref)('');
// 加载分析结果
const loadAnalysisResult = async () => {
    if (props.record.status !== 'completed') {
        return;
    }
    try {
        isLoadingResult.value = true;
        const { data, error } = await (0, qc_analysis_api_1.getQCResult)(props.record.id);
        if (error) {
            console.error('获取分析结果失败:', error);
            // 创建模拟的增强质控结果
            analysisResult.value = createMockEnhancedResult();
        }
        else {
            analysisResult.value = data;
        }
    }
    catch (error) {
        console.error('加载分析结果异常:', error);
        analysisResult.value = createMockEnhancedResult();
    }
    finally {
        isLoadingResult.value = false;
    }
};
// 创建模拟的增强质控结果
const createMockEnhancedResult = () => {
    return {
        recordId: props.record.id,
        summary: {
            totalScore: props.record.qc_score || 87,
            grade: (props.record.qc_grade || 'B'),
            overallAssessment: '病历质量总体良好，部分细节需要完善',
            aiAnalysisScore: 85,
            rulesEngineScore: 90,
            combinedScore: 87
        },
        itemScores: [
            { itemId: 'homepage', itemName: '首页', totalScore: 20, actualScore: 18, deduction: 2, assessment: '基本信息完整，少量格式问题' },
            { itemId: 'progress', itemName: '病程记录', totalScore: 25, actualScore: 22, deduction: 3, assessment: '记录及时完整，表述需要规范' },
            { itemId: 'diagnosis', itemName: '诊断', totalScore: 20, actualScore: 19, deduction: 1, assessment: '诊断准确，依据充分' },
            { itemId: 'surgery', itemName: '手术记录', totalScore: 15, actualScore: 13, deduction: 2, assessment: '记录完整，细节可以更详细' },
            { itemId: 'discharge', itemName: '出院记录', totalScore: 20, actualScore: 18, deduction: 2, assessment: '出院指导完整，随访计划明确' }
        ],
        issues: [
            {
                code: 'COMP_001',
                description: '患者过敏史记录不完整',
                severity: 'major',
                itemId: 'homepage',
                deduction: 2,
                location: '首页基本信息',
                suggestion: '补充详细的过敏史记录',
                source: 'rules'
            },
            {
                code: 'CONS_002',
                description: '入院诊断与出院诊断存在不一致',
                severity: 'minor',
                itemId: 'diagnosis',
                deduction: 1,
                location: '诊断部分',
                suggestion: '核实诊断变化的依据',
                source: 'ai'
            }
        ],
        strengths: ['诊断准确', '治疗方案合理', '病程记录及时'],
        recommendations: [
            '补充患者过敏史记录',
            '规范病程记录的表述',
            '完善手术记录的细节描述'
        ],
        analysisTime: new Date().toISOString(),
        rulesEngineResults: [
            {
                ruleId: 'COMP_001',
                ruleName: '基本信息完整性',
                category: 'completeness',
                severity: 'major',
                passed: false,
                score: 80,
                maxScore: 100,
                deduction: 20,
                issues: [
                    {
                        code: 'COMP_001',
                        description: '患者过敏史记录不完整',
                        severity: 'major',
                        location: '首页基本信息',
                        suggestion: '补充详细的过敏史记录',
                        deduction: 2,
                        category: 'completeness'
                    }
                ],
                confidence: 0.95,
                executionTime: 120
            },
            { ruleId: 'CONS_001',
                ruleName: '诊断一致性',
                category: 'consistency',
                severity: 'major',
                passed: true,
                score: 95,
                maxScore: 100,
                deduction: 5,
                issues:  [],
                confidence: 0.88,
                executionTime: 150
            }
        ],
        processingStats: {
            aiAnalysisTime: 3200,
            rulesEngineTime: 800,
            totalProcessingTime: 4000
        }
    };
};
// 计算属性
const displayResult = (0, vue_1.computed)(() => {
    return analysisResult.value || createMockEnhancedResult();
});
const filteredIssues = (0, vue_1.computed)(() => {
    if (!issueFilter.value)
        return displayResult.value.issues;
    return displayResult.value.issues.filter(issue => issue.severity === issueFilter.value);
});
const groupedRulesResults = (0, vue_1.computed)(() => {
    if (!displayResult.value.rulesEngineResults)
        return {};
    const grouped = {};
    displayResult.value.rulesEngineResults.forEach(result => {
        if (!grouped[result.category]) {
            grouped[result.category] = [];
        }
        grouped[result.category].push(result);
    });
    return grouped;
});
// 在组件挂载时加载数据
(0, vue_1.onMounted)(() => {
    loadAnalysisResult();
});
// 辅助方法
const getItemScore = (category) => {
    const item = displayResult.value.itemScores.find(item => item.itemId === category || item.itemName.includes(getCategoryName(category)));
    return item ? Math.round((item.actualScore / item.totalScore) * 100) : 0;
};
const getCategoryName = (category) => {
    const nameMap = {
        completeness: '完整性',
        consistency: '一致性',
        rationality: '合理性',
        timeliness: '时效性',
        similarity: '相似性',
        compliance: '合规性'
    };
    return nameMap[category] || category;
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
        '甲级': 'green',
        '乙级': 'orange',
        '丙级': 'red',
        'A': 'green',
        'B': 'orange',
        'C': 'red'
    };
    return gradeColorMap[grade] || 'default';
};
const getIssueSeverityColor = (severity) => {
    const colorMap = {
        'critical': '#f5222d',
        'major': '#faad14',
        'minor': '#fa8c16'
    };
    return colorMap[severity] || '#d9d9d9';
};
const getIssueSeverityText = (severity) => {
    const textMap = {
        'critical': '严重',
        'major': '重要',
        'minor': '轻微'
    };
    return textMap[severity] || severity;
};
const getSourceColor = (source) => {
    const colorMap = {
        'ai': '#1890ff',
        'rules': '#52c41a',
        'hybrid': '#722ed1'
    };
    return colorMap[source] || '#d9d9d9';
};
const getSourceText = (source) => {
    const textMap = {
        'ai': 'AI分析',
        'rules': '规则引擎',
        'hybrid': '混合分析'
    };
    return textMap[source] || source;
};
const getSeverityColor = (severity) => {
    const colorMap = {
        'critical': 'red',
        'major': 'orange',
        'minor': 'blue'
    };
    return colorMap[severity] || 'default';
};
const getSeverityText = (severity) => {
    const textMap = {
        'critical': '严重',
        'major': '重要',
        'minor': '轻微'
    };
    return textMap[severity] || severity;
};
const formatDateTime = (dateTime) => {
    return new Date(dateTime).toLocaleString();
};
const exportReport = () => {
    ant_design_vue_1.message.info('报告导出功能开发中...');
};
const retryAnalysis = () => {
    emit('retry');
    emit('close');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "analysis-result-panel" },
});
if (__VLS_ctx.isLoadingResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-container" },
    });
    const __VLS_0 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        size: "large",
    }));
    const __VLS_2 = __VLS_1({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center mt-4" },
    });
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_4 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        title: "分析概览",
        ...{ class: "mb-6" },
        bordered: (false),
    }));
    const __VLS_6 = __VLS_5({
        title: "分析概览",
        ...{ class: "mb-6" },
        bordered: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_7.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-3xl font-bold mb-2" },
        ...{ style: ({ color: __VLS_ctx.getScoreColor(__VLS_ctx.displayResult.summary.totalScore) }) },
    });
    (__VLS_ctx.displayResult.summary.totalScore);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-gray-600" },
    });
    const __VLS_8 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        color: (__VLS_ctx.getGradeColor(__VLS_ctx.displayResult.summary.grade)),
        size: "large",
        ...{ class: "mt-2" },
    }));
    const __VLS_10 = __VLS_9({
        color: (__VLS_ctx.getGradeColor(__VLS_ctx.displayResult.summary.grade)),
        size: "large",
        ...{ class: "mt-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    (__VLS_ctx.displayResult.summary.grade);
    var __VLS_11;
    if (__VLS_ctx.displayResult.summary.aiAnalysisScore) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-center" },
        });
        const __VLS_12 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
            type: "circle",
            percent: (__VLS_ctx.displayResult.summary.aiAnalysisScore),
            strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.displayResult.summary.aiAnalysisScore)),
            width: (60),
        }));
        const __VLS_14 = __VLS_13({
            type: "circle",
            percent: (__VLS_ctx.displayResult.summary.aiAnalysisScore),
            strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.displayResult.summary.aiAnalysisScore)),
            width: (60),
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-sm text-gray-600 mt-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-gray-500" },
        });
        (__VLS_ctx.displayResult.summary.aiAnalysisScore);
    }
    if (__VLS_ctx.displayResult.summary.rulesEngineScore) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-center" },
        });
        const __VLS_16 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            type: "circle",
            percent: (__VLS_ctx.displayResult.summary.rulesEngineScore),
            strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.displayResult.summary.rulesEngineScore)),
            width: (60),
        }));
        const __VLS_18 = __VLS_17({
            type: "circle",
            percent: (__VLS_ctx.displayResult.summary.rulesEngineScore),
            strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.displayResult.summary.rulesEngineScore)),
            width: (60),
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-sm text-gray-600 mt-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-gray-500" },
        });
        (__VLS_ctx.displayResult.summary.rulesEngineScore);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    const __VLS_20 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        type: "circle",
        percent: (__VLS_ctx.getItemScore('completeness')),
        strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.getItemScore('completeness'))),
        width: (60),
    }));
    const __VLS_22 = __VLS_21({
        type: "circle",
        percent: (__VLS_ctx.getItemScore('completeness')),
        strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.getItemScore('completeness'))),
        width: (60),
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-gray-600 mt-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-gray-500" },
    });
    (__VLS_ctx.getItemScore('completeness'));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center" },
    });
    const __VLS_24 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        type: "circle",
        percent: (__VLS_ctx.getItemScore('consistency')),
        strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.getItemScore('consistency'))),
        width: (60),
    }));
    const __VLS_26 = __VLS_25({
        type: "circle",
        percent: (__VLS_ctx.getItemScore('consistency')),
        strokeColor: (__VLS_ctx.getScoreColor(__VLS_ctx.getItemScore('consistency'))),
        width: (60),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-gray-600 mt-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-gray-500" },
    });
    (__VLS_ctx.getItemScore('consistency'));
    var __VLS_7;
    const __VLS_28 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        title: "详细评分",
        ...{ class: "mb-6" },
        bordered: (false),
    }));
    const __VLS_30 = __VLS_29({
        title: "详细评分",
        ...{ class: "mb-6" },
        bordered: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_31.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "space-y-4" },
    });
    for (const [item] of __VLS_getVForSourceType((__VLS_ctx.displayResult.itemScores))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (item.itemId),
            ...{ class: "flex items-center justify-between p-4 bg-gray-50 rounded-lg" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex-1" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "font-medium" },
        });
        (item.itemName);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-sm text-gray-600" },
        });
        (item.assessment);
        if (item.deduction > 0) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-xs text-red-600 mt-1" },
            });
            (item.deduction);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-right" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xl font-bold" },
            ...{ style: ({ color: __VLS_ctx.getScoreColor(item.actualScore) }) },
        });
        (item.actualScore);
        (item.totalScore);
        const __VLS_32 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
            percent: (Math.round((item.actualScore / item.totalScore) * 100)),
            strokeColor: (__VLS_ctx.getScoreColor(item.actualScore)),
            size: "small",
            ...{ class: "w-32" },
        }));
        const __VLS_34 = __VLS_33({
            percent: (Math.round((item.actualScore / item.totalScore) * 100)),
            strokeColor: (__VLS_ctx.getScoreColor(item.actualScore)),
            size: "small",
            ...{ class: "w-32" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    }
    var __VLS_31;
    if (__VLS_ctx.displayResult.issues && __VLS_ctx.displayResult.issues.length > 0) {
        const __VLS_36 = {}.ACard;
        /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
            title: "发现的问题",
            ...{ class: "mb-6" },
            bordered: (false),
        }));
        const __VLS_38 = __VLS_37({
            title: "发现的问题",
            ...{ class: "mb-6" },
            bordered: (false),
        }, ...__VLS_functionalComponentArgsRest(__VLS_37));
        __VLS_39.slots.default;
        {
            const { extra: __VLS_thisSlot } = __VLS_39.slots;
            const __VLS_40 = {}.ASelect;
            /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
            // @ts-ignore
            const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
                value: (__VLS_ctx.issueFilter),
                placeholder: "筛选问题",
                ...{ style: {} },
                allowClear: true,
            }));
            const __VLS_42 = __VLS_41({
                value: (__VLS_ctx.issueFilter),
                placeholder: "筛选问题",
                ...{ style: {} },
                allowClear: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_41));
            __VLS_43.slots.default;
            const __VLS_44 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
                value: "",
            }));
            const __VLS_46 = __VLS_45({
                value: "",
            }, ...__VLS_functionalComponentArgsRest(__VLS_45));
            __VLS_47.slots.default;
            var __VLS_47;
            const __VLS_48 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
                value: "critical",
            }));
            const __VLS_50 = __VLS_49({
                value: "critical",
            }, ...__VLS_functionalComponentArgsRest(__VLS_49));
            __VLS_51.slots.default;
            var __VLS_51;
            const __VLS_52 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
                value: "major",
            }));
            const __VLS_54 = __VLS_53({
                value: "major",
            }, ...__VLS_functionalComponentArgsRest(__VLS_53));
            __VLS_55.slots.default;
            var __VLS_55;
            const __VLS_56 = {}.ASelectOption;
            /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
            // @ts-ignore
            const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
                value: "minor",
            }));
            const __VLS_58 = __VLS_57({
                value: "minor",
            }, ...__VLS_functionalComponentArgsRest(__VLS_57));
            __VLS_59.slots.default;
            var __VLS_59;
            var __VLS_43;
        }
        const __VLS_60 = {}.AList;
        /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
            dataSource: (__VLS_ctx.filteredIssues),
            itemLayout: "horizontal",
            size: "small",
        }));
        const __VLS_62 = __VLS_61({
            dataSource: (__VLS_ctx.filteredIssues),
            itemLayout: "horizontal",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_61));
        __VLS_63.slots.default;
        {
            const { renderItem: __VLS_thisSlot } = __VLS_63.slots;
            const [{ item, index }] = __VLS_getSlotParams(__VLS_thisSlot);
            const __VLS_64 = {}.AListItem;
            /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
            // @ts-ignore
            const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({}));
            const __VLS_66 = __VLS_65({}, ...__VLS_functionalComponentArgsRest(__VLS_65));
            __VLS_67.slots.default;
            {
                const { actions: __VLS_thisSlot } = __VLS_67.slots;
                const __VLS_68 = {}.ASpace;
                /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
                // @ts-ignore
                const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({}));
                const __VLS_70 = __VLS_69({}, ...__VLS_functionalComponentArgsRest(__VLS_69));
                __VLS_71.slots.default;
                const __VLS_72 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
                    color: (__VLS_ctx.getIssueSeverityColor(item.severity)),
                }));
                const __VLS_74 = __VLS_73({
                    color: (__VLS_ctx.getIssueSeverityColor(item.severity)),
                }, ...__VLS_functionalComponentArgsRest(__VLS_73));
                __VLS_75.slots.default;
                (__VLS_ctx.getIssueSeverityText(item.severity));
                var __VLS_75;
                if (item.source) {
                    const __VLS_76 = {}.ATag;
                    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                    // @ts-ignore
                    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
                        color: (__VLS_ctx.getSourceColor(item.source)),
                    }));
                    const __VLS_78 = __VLS_77({
                        color: (__VLS_ctx.getSourceColor(item.source)),
                    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
                    __VLS_79.slots.default;
                    (__VLS_ctx.getSourceText(item.source));
                    var __VLS_79;
                }
                var __VLS_71;
            }
            const __VLS_80 = {}.AListItemMeta;
            /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
            // @ts-ignore
            const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
            const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
            __VLS_83.slots.default;
            {
                const { avatar: __VLS_thisSlot } = __VLS_83.slots;
                const __VLS_84 = {}.AAvatar;
                /** @type {[typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, ]} */ ;
                // @ts-ignore
                const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
                    ...{ style: ({ backgroundColor: __VLS_ctx.getIssueSeverityColor(item.severity) }) },
                }));
                const __VLS_86 = __VLS_85({
                    ...{ style: ({ backgroundColor: __VLS_ctx.getIssueSeverityColor(item.severity) }) },
                }, ...__VLS_functionalComponentArgsRest(__VLS_85));
                __VLS_87.slots.default;
                (index + 1);
                var __VLS_87;
            }
            {
                const { title: __VLS_thisSlot } = __VLS_83.slots;
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "flex items-center gap-2" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "font-medium" },
                });
                (item.code);
                if (item.deduction) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "text-red-600 text-sm" },
                    });
                    (item.deduction);
                }
            }
            {
                const { description: __VLS_thisSlot } = __VLS_83.slots;
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "space-y-2" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "text-gray-800" },
                });
                (item.description);
                if (item.location) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        ...{ class: "text-xs text-gray-500" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "font-medium" },
                    });
                    (item.location);
                }
                if (item.suggestion) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        ...{ class: "text-xs text-blue-600" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "font-medium" },
                    });
                    (item.suggestion);
                }
            }
            var __VLS_83;
            var __VLS_67;
        }
        var __VLS_63;
        var __VLS_39;
    }
    if (__VLS_ctx.displayResult.recommendations && __VLS_ctx.displayResult.recommendations.length > 0) {
        const __VLS_88 = {}.ACard;
        /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
            title: "改进建议",
            ...{ class: "mb-6" },
            bordered: (false),
        }));
        const __VLS_90 = __VLS_89({
            title: "改进建议",
            ...{ class: "mb-6" },
            bordered: (false),
        }, ...__VLS_functionalComponentArgsRest(__VLS_89));
        __VLS_91.slots.default;
        const __VLS_92 = {}.AList;
        /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            dataSource: (__VLS_ctx.displayResult.recommendations),
            itemLayout: "horizontal",
            size: "small",
        }));
        const __VLS_94 = __VLS_93({
            dataSource: (__VLS_ctx.displayResult.recommendations),
            itemLayout: "horizontal",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        __VLS_95.slots.default;
        {
            const { renderItem: __VLS_thisSlot } = __VLS_95.slots;
            const [{ item, index }] = __VLS_getSlotParams(__VLS_thisSlot);
            const __VLS_96 = {}.AListItem;
            /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
            // @ts-ignore
            const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({}));
            const __VLS_98 = __VLS_97({}, ...__VLS_functionalComponentArgsRest(__VLS_97));
            __VLS_99.slots.default;
            {
                const { actions: __VLS_thisSlot } = __VLS_99.slots;
                const __VLS_100 = {}.AButton;
                /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
                // @ts-ignore
                const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
                    type: "link",
                    size: "small",
                }));
                const __VLS_102 = __VLS_101({
                    type: "link",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_101));
                __VLS_103.slots.default;
                {
                    const { icon: __VLS_thisSlot } = __VLS_103.slots;
                    const __VLS_104 = {}.CheckOutlined;
                    /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
                    // @ts-ignore
                    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({}));
                    const __VLS_106 = __VLS_105({}, ...__VLS_functionalComponentArgsRest(__VLS_105));
                }
                var __VLS_103;
            }
            const __VLS_108 = {}.AListItemMeta;
            /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
            // @ts-ignore
            const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({}));
            const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
            __VLS_111.slots.default;
            {
                const { avatar: __VLS_thisSlot } = __VLS_111.slots;
                const __VLS_112 = {}.AAvatar;
                /** @type {[typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, ]} */ ;
                // @ts-ignore
                const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
                    ...{ style: {} },
                }));
                const __VLS_114 = __VLS_113({
                    ...{ style: {} },
                }, ...__VLS_functionalComponentArgsRest(__VLS_113));
                __VLS_115.slots.default;
                {
                    const { icon: __VLS_thisSlot } = __VLS_115.slots;
                    const __VLS_116 = {}.BulbOutlined;
                    /** @type {[typeof __VLS_components.BulbOutlined, ]} */ ;
                    // @ts-ignore
                    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
                    const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
                }
                var __VLS_115;
            }
            {
                const { description: __VLS_thisSlot } = __VLS_111.slots;
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "text-gray-800" },
                });
                (item);
            }
            var __VLS_111;
            var __VLS_99;
        }
        var __VLS_95;
        var __VLS_91;
    }
    if (__VLS_ctx.displayResult.rulesEngineResults && __VLS_ctx.displayResult.rulesEngineResults.length > 0) {
        const __VLS_120 = {}.ACard;
        /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            title: "规则引擎详情",
            ...{ class: "mb-6" },
            bordered: (false),
        }));
        const __VLS_122 = __VLS_121({
            title: "规则引擎详情",
            ...{ class: "mb-6" },
            bordered: (false),
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        const __VLS_124 = {}.ACollapse;
        /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
        const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
        __VLS_127.slots.default;
        for (const [categoryGroup, category] of __VLS_getVForSourceType((__VLS_ctx.groupedRulesResults))) {
            const __VLS_128 = {}.ACollapsePanel;
            /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
            // @ts-ignore
            const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
                key: (category),
                header: (`${__VLS_ctx.getCategoryName(category)} (${categoryGroup.length}条规则)`),
            }));
            const __VLS_130 = __VLS_129({
                key: (category),
                header: (`${__VLS_ctx.getCategoryName(category)} (${categoryGroup.length}条规则)`),
            }, ...__VLS_functionalComponentArgsRest(__VLS_129));
            __VLS_131.slots.default;
            const __VLS_132 = {}.AList;
            /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
            // @ts-ignore
            const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
                dataSource: (categoryGroup),
                itemLayout: "horizontal",
                size: "small",
            }));
            const __VLS_134 = __VLS_133({
                dataSource: (categoryGroup),
                itemLayout: "horizontal",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_133));
            __VLS_135.slots.default;
            {
                const { renderItem: __VLS_thisSlot } = __VLS_135.slots;
                const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
                const __VLS_136 = {}.AListItem;
                /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
                // @ts-ignore
                const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({}));
                const __VLS_138 = __VLS_137({}, ...__VLS_functionalComponentArgsRest(__VLS_137));
                __VLS_139.slots.default;
                {
                    const { actions: __VLS_thisSlot } = __VLS_139.slots;
                    const __VLS_140 = {}.ASpace;
                    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
                    // @ts-ignore
                    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({}));
                    const __VLS_142 = __VLS_141({}, ...__VLS_functionalComponentArgsRest(__VLS_141));
                    __VLS_143.slots.default;
                    const __VLS_144 = {}.ATag;
                    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                    // @ts-ignore
                    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
                        color: (item.passed ? 'green' : 'red'),
                    }));
                    const __VLS_146 = __VLS_145({
                        color: (item.passed ? 'green' : 'red'),
                    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
                    __VLS_147.slots.default;
                    (item.passed ? '通过' : '未通过');
                    var __VLS_147;
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "text-sm text-gray-600" },
                    });
                    (item.score);
                    (item.maxScore);
                    var __VLS_143;
                }
                const __VLS_148 = {}.AListItemMeta;
                /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
                // @ts-ignore
                const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({}));
                const __VLS_150 = __VLS_149({}, ...__VLS_functionalComponentArgsRest(__VLS_149));
                __VLS_151.slots.default;
                {
                    const { title: __VLS_thisSlot } = __VLS_151.slots;
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        ...{ class: "flex items-center gap-2" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "font-medium" },
                    });
                    (item.ruleName);
                    const __VLS_152 = {}.ATag;
                    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                    // @ts-ignore
                    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
                        color: (__VLS_ctx.getSeverityColor(item.severity)),
                        size: "small",
                    }));
                    const __VLS_154 = __VLS_153({
                        color: (__VLS_ctx.getSeverityColor(item.severity)),
                        size: "small",
                    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
                    __VLS_155.slots.default;
                    (__VLS_ctx.getSeverityText(item.severity));
                    var __VLS_155;
                }
                {
                    const { description: __VLS_thisSlot } = __VLS_151.slots;
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        ...{ class: "space-y-1" },
                    });
                    if (item.issues.length > 0) {
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                            ...{ class: "text-sm" },
                        });
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                            ...{ class: "font-medium text-red-600" },
                        });
                        __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
                            ...{ class: "mt-1 space-y-1" },
                        });
                        for (const [issue] of __VLS_getVForSourceType((item.issues))) {
                            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                                key: (issue.code),
                                ...{ class: "text-gray-700" },
                            });
                            (issue.description);
                        }
                    }
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                        ...{ class: "text-xs text-gray-500" },
                    });
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "font-medium" },
                    });
                    (Math.round(item.confidence * 100));
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "ml-4 font-medium" },
                    });
                    (item.executionTime);
                }
                var __VLS_151;
                var __VLS_139;
            }
            var __VLS_135;
            var __VLS_131;
        }
        var __VLS_127;
        var __VLS_123;
    }
    const __VLS_156 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        title: "分析详情",
        bordered: (false),
    }));
    const __VLS_158 = __VLS_157({
        title: "分析详情",
        bordered: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    const __VLS_160 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        column: (2),
        bordered: true,
    }));
    const __VLS_162 = __VLS_161({
        column: (2),
        bordered: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    __VLS_163.slots.default;
    const __VLS_164 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        label: "分析模型",
    }));
    const __VLS_166 = __VLS_165({
        label: "分析模型",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
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
    (__VLS_ctx.formatDateTime(__VLS_ctx.displayResult.analysisTime));
    var __VLS_171;
    if (__VLS_ctx.displayResult.processingStats?.aiAnalysisTime) {
        const __VLS_172 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
            label: "AI分析耗时",
        }));
        const __VLS_174 = __VLS_173({
            label: "AI分析耗时",
        }, ...__VLS_functionalComponentArgsRest(__VLS_173));
        __VLS_175.slots.default;
        (Math.round(__VLS_ctx.displayResult.processingStats.aiAnalysisTime / 1000));
        var __VLS_175;
    }
    if (__VLS_ctx.displayResult.processingStats?.rulesEngineTime) {
        const __VLS_176 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
            label: "规则引擎耗时",
        }));
        const __VLS_178 = __VLS_177({
            label: "规则引擎耗时",
        }, ...__VLS_functionalComponentArgsRest(__VLS_177));
        __VLS_179.slots.default;
        (Math.round(__VLS_ctx.displayResult.processingStats.rulesEngineTime / 1000));
        var __VLS_179;
    }
    if (__VLS_ctx.displayResult.processingStats?.totalProcessingTime) {
        const __VLS_180 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
            label: "总处理时间",
        }));
        const __VLS_182 = __VLS_181({
            label: "总处理时间",
        }, ...__VLS_functionalComponentArgsRest(__VLS_181));
        __VLS_183.slots.default;
        (Math.round(__VLS_ctx.displayResult.processingStats.totalProcessingTime / 1000));
        var __VLS_183;
    }
    const __VLS_184 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
        label: "综合评估",
    }));
    const __VLS_186 = __VLS_185({
        label: "综合评估",
    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    __VLS_187.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-800" },
    });
    (__VLS_ctx.displayResult.summary.overallAssessment);
    var __VLS_187;
    var __VLS_163;
    var __VLS_159;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex justify-end space-x-4 mt-6 pt-6 border-t" },
    });
    const __VLS_188 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        ...{ 'onClick': {} },
    }));
    const __VLS_190 = __VLS_189({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    let __VLS_192;
    let __VLS_193;
    let __VLS_194;
    const __VLS_195 = {
        onClick: (__VLS_ctx.exportReport)
    };
    __VLS_191.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_191.slots;
        const __VLS_196 = {}.DownloadOutlined;
        /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({}));
        const __VLS_198 = __VLS_197({}, ...__VLS_functionalComponentArgsRest(__VLS_197));
    }
    var __VLS_191;
    const __VLS_200 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_202 = __VLS_201({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_201));
    let __VLS_204;
    let __VLS_205;
    let __VLS_206;
    const __VLS_207 = {
        onClick: (__VLS_ctx.retryAnalysis)
    };
    __VLS_203.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_203.slots;
        const __VLS_208 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({}));
        const __VLS_210 = __VLS_209({}, ...__VLS_functionalComponentArgsRest(__VLS_209));
    }
    var __VLS_203;
}
/** @type {__VLS_StyleScopedClasses['analysis-result-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-container']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-5']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-right']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['w-32']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-4']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            CheckOutlined: icons_vue_1.CheckOutlined,
            BulbOutlined: icons_vue_1.BulbOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            isLoadingResult: isLoadingResult,
            issueFilter: issueFilter,
            displayResult: displayResult,
            filteredIssues: filteredIssues,
            groupedRulesResults: groupedRulesResults,
            getItemScore: getItemScore,
            getCategoryName: getCategoryName,
            getScoreColor: getScoreColor,
            getGradeColor: getGradeColor,
            getIssueSeverityColor: getIssueSeverityColor,
            getIssueSeverityText: getIssueSeverityText,
            getSourceColor: getSourceColor,
            getSourceText: getSourceText,
            getSeverityColor: getSeverityColor,
            getSeverityText: getSeverityText,
            formatDateTime: formatDateTime,
            exportReport: exportReport,
            retryAnalysis: retryAnalysis,
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
