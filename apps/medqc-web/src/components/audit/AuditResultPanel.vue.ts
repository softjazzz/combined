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
const props = withDefaults(defineProps(), {
    editable: false,
    canModifyLowerLevel: false,
    isFinalLevel: false
});
const emit = defineEmits();
// 状态管理
const auditFormRef = (0, vue_1.ref)();
const defectFormRef = (0, vue_1.ref)();
const saving = (0, vue_1.ref)(false);
const submitting = (0, vue_1.ref)(false);
const aiAnalyzing = (0, vue_1.ref)(false);
// 表单数据
const formData = (0, vue_1.ref)({
    audit_score: 85,
    audit_conclusion: '',
    defects: []
});
// 对话框状态
const aiSuggestionsVisible = (0, vue_1.ref)(false);
const addDefectVisible = (0, vue_1.ref)(false);
const aiSuggestions = (0, vue_1.ref)(: any[]);
const selectedSuggestions = (0, vue_1.ref)(: any[]);
// 表单验证规则
const formRules = {
    audit_score: [
        { required: true, message: '请设置审核评分' },
        { type: 'number', min: 0, max: 100, message: '评分范围为0-100' }
    ]
};
// 评分标记
const scoreMarks = {
    0: '0',
    60: '60',
    80: '80',
    90: '90',
    100: '100'
};
// 计算属性
const criticalDefectsCount = (0, vue_1.computed)(() => formData.value.defects.filter(d => d.severity === 'critical').length);
const totalScoreDeduction = (0, vue_1.computed)(() => formData.value.defects.reduce((sum, d) => sum + (d.score_deduction || 0), 0));
// 方法
const getLevelTitle = (level) => {
    const titles = {
        department: '科室级',
        hospital: '院级',
        expert: '专家级'
    };
    return titles[level];
};
const getStatusColor = (status) => {
    const colors = {
        draft: 'default',
        submitted: 'processing',
        approved: 'success',
        rejected: 'error',
        modified: 'warning'
    };
    return colors[status || 'draft'] || 'default';
};
const getStatusText = (status) => {
    const texts = {
        draft: '草稿',
        submitted: '已提交',
        approved: '已通过',
        rejected: '已拒绝',
        modified: '已修改'
    };
    return texts[status || 'draft'] || '未知';
};
const getScoreLevel = (score) => {
    if (score >= 90)
        return '优秀';
    if (score >= 80)
        return '良好';
    if (score >= 70)
        return '合格';
    if (score >= 60)
        return '基本合格';
    return '不合格';
};
const handleScoreChange = (value) => {
    // 根据评分自动调整结论
    if (value >= 90) {
        formData.value.audit_conclusion = '病历质量优秀，符合规范要求。';
    }
    else if (value >= 80) {
        formData.value.audit_conclusion = '病历质量良好，存在少量问题。';
    }
    else if (value >= 70) {
        formData.value.audit_conclusion = '病历质量合格，需要改进。';
    }
    else {
        formData.value.audit_conclusion = '病历质量不合格，存在严重问题。';
    }
};
const handleSave = async () => {
    try {
        saving.value = true;
        const formValid = await auditFormRef.value?.validate();
        if (!formValid)
            return;
        emit('update', {
            audit_score: formData.value.audit_score,
            audit_conclusion: formData.value.audit_conclusion,
            defects: formData.value.defects
        });
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
    finally {
        saving.value = false;
    }
};
const handleSubmit = async () => {
    try {
        submitting.value = true;
        if (!props.auditResult?.id) {
            ant_design_vue_1.message.error('请先保存审核结果');
            return;
        }
        emit('submit', props.auditResult.id);
    }
    catch (error) {
        ant_design_vue_1.message.error('提交失败');
    }
    finally {
        submitting.value = false;
    }
};
const triggerAIAssistance = async () => {
    try {
        aiAnalyzing.value = true;
        // 调用AI辅助缺陷识别
        // const suggestions = await auditResultService.getAIDefectSuggestions(...)
        // aiSuggestions.value = suggestions
        // 模拟AI建议
        aiSuggestions.value = [
            {
                suggested_type: '内容缺失',
                suggested_category: '完整性',
                suggested_severity: 'major',
                suggested_title: '缺少出院小结',
                suggested_description: '患者病历中未发现出院小结文档',
                confidence: 85,
                supporting_evidence: ['文档列表检查'],
                rectification_suggestions: ['请补充完整的出院小结']
            }
        ];
        aiSuggestionsVisible.value = true;
    }
    catch (error) {
        ant_design_vue_1.message.error('AI分析失败');
    }
    finally {
        aiAnalyzing.value = false;
    }
};
const applyAISuggestions = () => {
    formData.value.defects.push(...selectedSuggestions.value.map(s => ({
        defect_type: s.suggested_type,
        defect_category: s.suggested_category,
        severity: s.suggested_severity,
        title: s.suggested_title,
        description: s.suggested_description,
        ai_assisted: true,
        ai_confidence: s.confidence,
        score_deduction: s.suggested_severity === 'critical' ? 20 :
            s.suggested_severity === 'major' ? 10 : 5
    })));
    aiSuggestionsVisible.value = false;
    ant_design_vue_1.message.success(`已添加 ${selectedSuggestions.value.length} 个AI建议的缺陷`);
};
const addManualDefect = () => {
    addDefectVisible.value = true;
};
const confirmAddDefect = async () => {
    try {
        const defectData = await defectFormRef.value?.validateAndGetData();
        if (defectData) {
            formData.value.defects.push(defectData);
            addDefectVisible.value = false;
            ant_design_vue_1.message.success('缺陷添加成功');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('请完善缺陷信息');
    }
};
const handleDefectUpdate = (index, defectData) => {
    formData.value.defects[index] = { ...formData.value.defects[index], ...defectData };
};
const handleDefectRemove = (index) => {
    formData.value.defects.splice(index, 1);
    ant_design_vue_1.message.success('缺陷已删除');
};
const modifyLowerResult = (result) => {
    emit('modify-lower', result);
};
const showModifyLowerModal = () => {
    // 显示修改下级结果的选择
};
const handleAISelectionChange = (selected) => {
    selectedSuggestions.value = selected;
};
const handleNewDefectChange = (data) => {
    // 处理新缺陷数据变化
};
const handleFormSubmit = () => {
    handleSave();
};
// 监听审核结果变化
(0, vue_1.watch)(() => props.auditResult, (newResult) => {
    if (newResult) {
        formData.value = {
            audit_score: newResult.audit_score,
            audit_conclusion: newResult.audit_conclusion || '',
            defects: newResult.defects_found || []
        };
    }
}, { immediate: true, deep: true });
(0, vue_1.onMounted)(() => {
    // 初始化
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    editable: false,
    canModifyLowerLevel: false,
    isFinalLevel: false
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['defect-item']} */ ;
/** @type {__VLS_StyleScopedClasses['lower-result-item']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "audit-result-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "panel-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-left" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "panel-title" },
});
(__VLS_ctx.getLevelTitle(__VLS_ctx.auditLevel));
const __VLS_0 = {}.ATag;
/** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    color: (__VLS_ctx.getStatusColor(__VLS_ctx.auditResult?.status)),
}));
const __VLS_2 = __VLS_1({
    color: (__VLS_ctx.getStatusColor(__VLS_ctx.auditResult?.status)),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
(__VLS_ctx.getStatusText(__VLS_ctx.auditResult?.status));
var __VLS_3;
if (__VLS_ctx.reviewerInfo) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "reviewer-info" },
    });
    const __VLS_4 = {}.UserOutlined;
    /** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
    const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.reviewerInfo);
    if (__VLS_ctx.auditResult?.review_duration) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "duration" },
        });
        (__VLS_ctx.auditResult.review_duration);
    }
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
if (__VLS_ctx.canModifyLowerLevel && __VLS_ctx.lowerLevelResults?.length) {
    const __VLS_12 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        ...{ 'onClick': {} },
        type: "dashed",
        size: "small",
    }));
    const __VLS_14 = __VLS_13({
        ...{ 'onClick': {} },
        type: "dashed",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    let __VLS_16;
    let __VLS_17;
    let __VLS_18;
    const __VLS_19 = {
        onClick: (__VLS_ctx.showModifyLowerModal)
    };
    __VLS_15.slots.default;
    const __VLS_20 = {}.EditOutlined;
    /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
    const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
    var __VLS_15;
}
if (__VLS_ctx.editable && __VLS_ctx.auditResult?.status === 'draft') {
    const __VLS_24 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.saving),
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.saving),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_28;
    let __VLS_29;
    let __VLS_30;
    const __VLS_31 = {
        onClick: (__VLS_ctx.handleSave)
    };
    __VLS_27.slots.default;
    const __VLS_32 = {}.SaveOutlined;
    /** @type {[typeof __VLS_components.SaveOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
    const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
    var __VLS_27;
}
if (__VLS_ctx.editable && __VLS_ctx.auditResult?.status === 'draft') {
    const __VLS_36 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.submitting),
    }));
    const __VLS_38 = __VLS_37({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.submitting),
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    let __VLS_40;
    let __VLS_41;
    let __VLS_42;
    const __VLS_43 = {
        onClick: (__VLS_ctx.handleSubmit)
    };
    __VLS_39.slots.default;
    const __VLS_44 = {}.CheckOutlined;
    /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
    const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
    var __VLS_39;
}
var __VLS_11;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "panel-content" },
});
const __VLS_48 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    gutter: (24),
}));
const __VLS_50 = __VLS_49({
    gutter: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    span: (16),
}));
const __VLS_54 = __VLS_53({
    span: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    title: "审核评分",
    ...{ class: "audit-form-card" },
}));
const __VLS_58 = __VLS_57({
    title: "审核评分",
    ...{ class: "audit-form-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    ...{ 'onFinish': {} },
    ref: "auditFormRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
}));
const __VLS_62 = __VLS_61({
    ...{ 'onFinish': {} },
    ref: "auditFormRef",
    model: (__VLS_ctx.formData),
    rules: (__VLS_ctx.formRules),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
let __VLS_64;
let __VLS_65;
let __VLS_66;
const __VLS_67 = {
    onFinish: (__VLS_ctx.handleFormSubmit)
};
/** @type {typeof __VLS_ctx.auditFormRef} */ ;
var __VLS_68 = {};
__VLS_63.slots.default;
const __VLS_70 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    label: "总体评分",
    name: "audit_score",
}));
const __VLS_72 = __VLS_71({
    label: "总体评分",
    name: "audit_score",
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
__VLS_73.slots.default;
const __VLS_74 = {}.ASlider;
/** @type {[typeof __VLS_components.ASlider, typeof __VLS_components.aSlider, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.formData.audit_score),
    min: (0),
    max: (100),
    marks: (__VLS_ctx.scoreMarks),
    disabled: (!__VLS_ctx.editable),
}));
const __VLS_76 = __VLS_75({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.formData.audit_score),
    min: (0),
    max: (100),
    marks: (__VLS_ctx.scoreMarks),
    disabled: (!__VLS_ctx.editable),
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
let __VLS_78;
let __VLS_79;
let __VLS_80;
const __VLS_81 = {
    onChange: (__VLS_ctx.handleScoreChange)
};
var __VLS_77;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "score-display" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "score-value" },
});
(__VLS_ctx.formData.audit_score);
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "score-level" },
});
(__VLS_ctx.getScoreLevel(__VLS_ctx.formData.audit_score));
var __VLS_73;
const __VLS_82 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
    label: "审核结论",
    name: "audit_conclusion",
}));
const __VLS_84 = __VLS_83({
    label: "审核结论",
    name: "audit_conclusion",
}, ...__VLS_functionalComponentArgsRest(__VLS_83));
__VLS_85.slots.default;
const __VLS_86 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
    value: (__VLS_ctx.formData.audit_conclusion),
    rows: (4),
    disabled: (!__VLS_ctx.editable),
    placeholder: "请输入审核结论...",
}));
const __VLS_88 = __VLS_87({
    value: (__VLS_ctx.formData.audit_conclusion),
    rows: (4),
    disabled: (!__VLS_ctx.editable),
    placeholder: "请输入审核结论...",
}, ...__VLS_functionalComponentArgsRest(__VLS_87));
var __VLS_85;
const __VLS_90 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
    label: "缺陷识别",
}));
const __VLS_92 = __VLS_91({
    label: "缺陷识别",
}, ...__VLS_functionalComponentArgsRest(__VLS_91));
__VLS_93.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "defect-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
const __VLS_94 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({}));
const __VLS_96 = __VLS_95({}, ...__VLS_functionalComponentArgsRest(__VLS_95));
__VLS_97.slots.default;
const __VLS_98 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.aiAnalyzing),
    size: "small",
    type: "dashed",
}));
const __VLS_100 = __VLS_99({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.aiAnalyzing),
    size: "small",
    type: "dashed",
}, ...__VLS_functionalComponentArgsRest(__VLS_99));
let __VLS_102;
let __VLS_103;
let __VLS_104;
const __VLS_105 = {
    onClick: (__VLS_ctx.triggerAIAssistance)
};
__VLS_101.slots.default;
const __VLS_106 = {}.RobotOutlined;
/** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
// @ts-ignore
const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({}));
const __VLS_108 = __VLS_107({}, ...__VLS_functionalComponentArgsRest(__VLS_107));
var __VLS_101;
const __VLS_110 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_111 = __VLS_asFunctionalComponent(__VLS_110, new __VLS_110({
    ...{ 'onClick': {} },
    size: "small",
    type: "primary",
    ghost: true,
}));
const __VLS_112 = __VLS_111({
    ...{ 'onClick': {} },
    size: "small",
    type: "primary",
    ghost: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_111));
let __VLS_114;
let __VLS_115;
let __VLS_116;
const __VLS_117 = {
    onClick: (__VLS_ctx.addManualDefect)
};
__VLS_113.slots.default;
const __VLS_118 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_119 = __VLS_asFunctionalComponent(__VLS_118, new __VLS_118({}));
const __VLS_120 = __VLS_119({}, ...__VLS_functionalComponentArgsRest(__VLS_119));
var __VLS_113;
var __VLS_97;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "defects-list" },
});
if (__VLS_ctx.formData.defects.length === 0) {
    const __VLS_122 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({
        description: "暂无发现缺陷",
    }));
    const __VLS_124 = __VLS_123({
        description: "暂无发现缺陷",
    }, ...__VLS_functionalComponentArgsRest(__VLS_123));
}
for (const [defect, index] of __VLS_getVForSourceType((__VLS_ctx.formData.defects))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (index),
        ...{ class: "defect-item" },
    });
    const __VLS_126 = {}.DefectCard;
    /** @type {[typeof __VLS_components.DefectCard, ]} */ ;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
        ...{ 'onUpdate': {} },
        ...{ 'onRemove': {} },
        defect: (defect),
        editable: (__VLS_ctx.editable),
    }));
    const __VLS_128 = __VLS_127({
        ...{ 'onUpdate': {} },
        ...{ 'onRemove': {} },
        defect: (defect),
        editable: (__VLS_ctx.editable),
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    let __VLS_130;
    let __VLS_131;
    let __VLS_132;
    const __VLS_133 = {
        onUpdate: (...[$event]) => {
            __VLS_ctx.handleDefectUpdate(index, $event);
        }
    };
    const __VLS_134 = {
        onRemove: (...[$event]) => {
            __VLS_ctx.handleDefectRemove(index);
        }
    };
    var __VLS_129;
}
var __VLS_93;
var __VLS_63;
var __VLS_59;
var __VLS_55;
const __VLS_135 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_136 = __VLS_asFunctionalComponent(__VLS_135, new __VLS_135({
    span: (8),
}));
const __VLS_137 = __VLS_136({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_136));
__VLS_138.slots.default;
const __VLS_139 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_140 = __VLS_asFunctionalComponent(__VLS_139, new __VLS_139({
    title: "审核统计",
    ...{ class: "stats-card" },
    size: "small",
}));
const __VLS_141 = __VLS_140({
    title: "审核统计",
    ...{ class: "stats-card" },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_140));
__VLS_142.slots.default;
const __VLS_143 = {}.AStatisticGroup;
/** @type {[typeof __VLS_components.AStatisticGroup, typeof __VLS_components.aStatisticGroup, typeof __VLS_components.AStatisticGroup, typeof __VLS_components.aStatisticGroup, ]} */ ;
// @ts-ignore
const __VLS_144 = __VLS_asFunctionalComponent(__VLS_143, new __VLS_143({}));
const __VLS_145 = __VLS_144({}, ...__VLS_functionalComponentArgsRest(__VLS_144));
__VLS_146.slots.default;
const __VLS_147 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_148 = __VLS_asFunctionalComponent(__VLS_147, new __VLS_147({
    title: "缺陷数量",
    value: (__VLS_ctx.formData.defects.length),
    suffix: "个",
}));
const __VLS_149 = __VLS_148({
    title: "缺陷数量",
    value: (__VLS_ctx.formData.defects.length),
    suffix: "个",
}, ...__VLS_functionalComponentArgsRest(__VLS_148));
const __VLS_151 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_152 = __VLS_asFunctionalComponent(__VLS_151, new __VLS_151({
    title: "严重缺陷",
    value: (__VLS_ctx.criticalDefectsCount),
    suffix: "个",
    valueStyle: ({ color: __VLS_ctx.criticalDefectsCount > 0 ? '#cf1322' : '#52c41a' }),
}));
const __VLS_153 = __VLS_152({
    title: "严重缺陷",
    value: (__VLS_ctx.criticalDefectsCount),
    suffix: "个",
    valueStyle: ({ color: __VLS_ctx.criticalDefectsCount > 0 ? '#cf1322' : '#52c41a' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_152));
const __VLS_155 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_156 = __VLS_asFunctionalComponent(__VLS_155, new __VLS_155({
    title: "扣分总计",
    value: (__VLS_ctx.totalScoreDeduction),
    suffix: "分",
    valueStyle: ({ color: '#faad14' }),
}));
const __VLS_157 = __VLS_156({
    title: "扣分总计",
    value: (__VLS_ctx.totalScoreDeduction),
    suffix: "分",
    valueStyle: ({ color: '#faad14' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_156));
var __VLS_146;
var __VLS_142;
if (__VLS_ctx.lowerLevelResults?.length) {
    const __VLS_159 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_160 = __VLS_asFunctionalComponent(__VLS_159, new __VLS_159({
        title: "下级审核结果",
        ...{ class: "lower-results-card" },
        size: "small",
    }));
    const __VLS_161 = __VLS_160({
        title: "下级审核结果",
        ...{ class: "lower-results-card" },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_160));
    __VLS_162.slots.default;
    for (const [lowerResult] of __VLS_getVForSourceType((__VLS_ctx.lowerLevelResults))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (lowerResult.id),
            ...{ class: "lower-result-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "level-name" },
        });
        (__VLS_ctx.getLevelTitle(lowerResult.audit_level));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "result-score" },
        });
        (lowerResult.audit_score);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-summary" },
        });
        (lowerResult.audit_conclusion || '无结论');
        if (__VLS_ctx.canModifyLowerLevel) {
            const __VLS_163 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_164 = __VLS_asFunctionalComponent(__VLS_163, new __VLS_163({
                ...{ 'onClick': {} },
                size: "small",
                type: "link",
            }));
            const __VLS_165 = __VLS_164({
                ...{ 'onClick': {} },
                size: "small",
                type: "link",
            }, ...__VLS_functionalComponentArgsRest(__VLS_164));
            let __VLS_167;
            let __VLS_168;
            let __VLS_169;
            const __VLS_170 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.lowerLevelResults?.length))
                        return;
                    if (!(__VLS_ctx.canModifyLowerLevel))
                        return;
                    __VLS_ctx.modifyLowerResult(lowerResult);
                }
            };
            __VLS_166.slots.default;
            var __VLS_166;
        }
    }
    var __VLS_162;
}
var __VLS_138;
var __VLS_51;
const __VLS_171 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_172 = __VLS_asFunctionalComponent(__VLS_171, new __VLS_171({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.aiSuggestionsVisible),
    title: "AI缺陷识别建议",
    width: "800px",
}));
const __VLS_173 = __VLS_172({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.aiSuggestionsVisible),
    title: "AI缺陷识别建议",
    width: "800px",
}, ...__VLS_functionalComponentArgsRest(__VLS_172));
let __VLS_175;
let __VLS_176;
let __VLS_177;
const __VLS_178 = {
    onOk: (__VLS_ctx.applyAISuggestions)
};
__VLS_174.slots.default;
if (__VLS_ctx.aiSuggestionsVisible) {
    const __VLS_179 = {}.AISuggestionsPanel;
    /** @type {[typeof __VLS_components.AISuggestionsPanel, ]} */ ;
    // @ts-ignore
    const __VLS_180 = __VLS_asFunctionalComponent(__VLS_179, new __VLS_179({
        ...{ 'onSelectionChange': {} },
        suggestions: (__VLS_ctx.aiSuggestions),
    }));
    const __VLS_181 = __VLS_180({
        ...{ 'onSelectionChange': {} },
        suggestions: (__VLS_ctx.aiSuggestions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_180));
    let __VLS_183;
    let __VLS_184;
    let __VLS_185;
    const __VLS_186 = {
        onSelectionChange: (__VLS_ctx.handleAISelectionChange)
    };
    var __VLS_182;
}
var __VLS_174;
const __VLS_187 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_188 = __VLS_asFunctionalComponent(__VLS_187, new __VLS_187({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.addDefectVisible),
    title: "添加缺陷",
}));
const __VLS_189 = __VLS_188({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.addDefectVisible),
    title: "添加缺陷",
}, ...__VLS_functionalComponentArgsRest(__VLS_188));
let __VLS_191;
let __VLS_192;
let __VLS_193;
const __VLS_194 = {
    onOk: (__VLS_ctx.confirmAddDefect)
};
__VLS_190.slots.default;
if (__VLS_ctx.addDefectVisible) {
    const __VLS_195 = {}.DefectForm;
    /** @type {[typeof __VLS_components.DefectForm, ]} */ ;
    // @ts-ignore
    const __VLS_196 = __VLS_asFunctionalComponent(__VLS_195, new __VLS_195({
        ...{ 'onChange': {} },
        ref: "defectFormRef",
    }));
    const __VLS_197 = __VLS_196({
        ...{ 'onChange': {} },
        ref: "defectFormRef",
    }, ...__VLS_functionalComponentArgsRest(__VLS_196));
    let __VLS_199;
    let __VLS_200;
    let __VLS_201;
    const __VLS_202 = {
        onChange: (__VLS_ctx.handleNewDefectChange)
    };
    /** @type {typeof __VLS_ctx.defectFormRef} */ ;
    var __VLS_203 = {};
    var __VLS_198;
}
var __VLS_190;
/** @type {__VLS_StyleScopedClasses['audit-result-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-title']} */ ;
/** @type {__VLS_StyleScopedClasses['reviewer-info']} */ ;
/** @type {__VLS_StyleScopedClasses['duration']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-content']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-form-card']} */ ;
/** @type {__VLS_StyleScopedClasses['score-display']} */ ;
/** @type {__VLS_StyleScopedClasses['score-value']} */ ;
/** @type {__VLS_StyleScopedClasses['score-level']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['defects-list']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stats-card']} */ ;
/** @type {__VLS_StyleScopedClasses['lower-results-card']} */ ;
/** @type {__VLS_StyleScopedClasses['lower-result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-header']} */ ;
/** @type {__VLS_StyleScopedClasses['level-name']} */ ;
/** @type {__VLS_StyleScopedClasses['result-score']} */ ;
/** @type {__VLS_StyleScopedClasses['result-summary']} */ ;
// @ts-ignore
var __VLS_69 = __VLS_68, __VLS_204 = __VLS_203;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            UserOutlined: icons_vue_1.UserOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            SaveOutlined: icons_vue_1.SaveOutlined,
            CheckOutlined: icons_vue_1.CheckOutlined,
            RobotOutlined: icons_vue_1.RobotOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            auditFormRef: auditFormRef,
            defectFormRef: defectFormRef,
            saving: saving,
            submitting: submitting,
            aiAnalyzing: aiAnalyzing,
            formData: formData,
            aiSuggestionsVisible: aiSuggestionsVisible,
            addDefectVisible: addDefectVisible,
            aiSuggestions: aiSuggestions,
            formRules: formRules,
            scoreMarks: scoreMarks,
            criticalDefectsCount: criticalDefectsCount,
            totalScoreDeduction: totalScoreDeduction,
            getLevelTitle: getLevelTitle,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
            getScoreLevel: getScoreLevel,
            handleScoreChange: handleScoreChange,
            handleSave: handleSave,
            handleSubmit: handleSubmit,
            triggerAIAssistance: triggerAIAssistance,
            applyAISuggestions: applyAISuggestions,
            addManualDefect: addManualDefect,
            confirmAddDefect: confirmAddDefect,
            handleDefectUpdate: handleDefectUpdate,
            handleDefectRemove: handleDefectRemove,
            modifyLowerResult: modifyLowerResult,
            showModifyLowerModal: showModifyLowerModal,
            handleAISelectionChange: handleAISelectionChange,
            handleNewDefectChange: handleNewDefectChange,
            handleFormSubmit: handleFormSubmit,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
; /* PartiallyEnd: #4569/main.vue */
