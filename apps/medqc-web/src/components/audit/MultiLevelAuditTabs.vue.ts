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
import auth_1 from '@/stores/auth';
import audit_result_service_1 from '@/services/audit-result-service';
const props = defineProps();
const emit = defineEmits();
// 状态管理
const authStore = (0, auth_1.useAuthStore)();
const activeTab = (0, vue_1.ref)('department');
const loading = (0, vue_1.ref)(false);
// 审核结果数据
const auditResults = (0, vue_1.ref)({
    department: null,
    hospital: null,
    expert: null
});
const auditHistory = (0, vue_1.ref)(: any[]);
// 修改下级结果相关
const modifyModalVisible = (0, vue_1.ref)(false);
const modifyTarget = (0, vue_1.ref)(null);
const modifyFormRef = (0, vue_1.ref)();
// 审核员信息
const departmentReviewer = (0, vue_1.computed)(() => auditResults.value.department?.reviewer_name);
const hospitalReviewer = (0, vue_1.computed)(() => auditResults.value.hospital?.reviewer_name);
const expertReviewer = (0, vue_1.computed)(() => auditResults.value.expert?.reviewer_name);
// 权限控制
const canEditDepartmentLevel = (0, vue_1.computed)(() => authStore.hasRole('qc_reviewer_dept') &&
    (!auditResults.value.department?.is_final || auditResults.value.department?.status === 'draft'));
const canEditHospitalLevel = (0, vue_1.computed)(() => authStore.hasRole('qc_reviewer_hospital') &&
    auditResults.value.department?.is_final &&
    (!auditResults.value.hospital?.is_final || auditResults.value.hospital?.status === 'draft'));
const canEditExpertLevel = (0, vue_1.computed)(() => authStore.hasRole('qc_reviewer_expert') &&
    auditResults.value.hospital?.is_final &&
    (!auditResults.value.expert?.is_final || auditResults.value.expert?.status === 'draft'));
// 方法
const loadAuditResults = async () => {
    try {
        loading.value = true;
        const results = await audit_result_service_1.auditResultService.getAuditResults(props.taskItemId, true);
        // 按级别分组
        auditResults.value = {
            department: results.find(r => r.audit_level === 'department') || null,
            hospital: results.find(r => r.audit_level === 'hospital') || null,
            expert: results.find(r => r.audit_level === 'expert') || null
        };
        // 构建审核历史
        auditHistory.value = results.map(result => ({
            level: result.audit_level,
            reviewer: result.reviewer_name,
            score: result.audit_score,
            status: result.status,
            submitted_at: result.submitted_at,
            review_duration: result.review_duration
        })).sort((a, b) => new Date(a.submitted_at || '').getTime() - new Date(b.submitted_at || '').getTime());
    }
    catch (error) {
        ant_design_vue_1.message.error(`加载审核结果失败: ${error.message}`);
    }
    finally {
        loading.value = false;
    }
};
const handleTabChange = (key) => {
    activeTab.value = key;
};
const handleDepartmentUpdate = async (resultData) => {
    try {
        const result = await audit_result_service_1.auditResultService.createAuditResult(props.taskItemId, 'department', authStore.user.id, resultData);
        auditResults.value.department = result;
        emit('result-updated', 'department', result);
        ant_design_vue_1.message.success('科室级审核结果已保存');
    }
    catch (error) {
        ant_design_vue_1.message.error(`保存失败: ${error.message}`);
    }
};
const handleHospitalUpdate = async (resultData) => {
    try {
        const result = await audit_result_service_1.auditResultService.createAuditResult(props.taskItemId, 'hospital', authStore.user.id, resultData);
        auditResults.value.hospital = result;
        emit('result-updated', 'hospital', result);
        ant_design_vue_1.message.success('院级审核结果已保存');
    }
    catch (error) {
        ant_design_vue_1.message.error(`保存失败: ${error.message}`);
    }
};
const handleExpertUpdate = async (resultData) => {
    try {
        const result = await audit_result_service_1.auditResultService.createAuditResult(props.taskItemId, 'expert', authStore.user.id, resultData);
        auditResults.value.expert = result;
        emit('result-updated', 'expert', result);
        ant_design_vue_1.message.success('专家级审核结果已保存');
    }
    catch (error) {
        ant_design_vue_1.message.error(`保存失败: ${error.message}`);
    }
};
const handleSubmitResult = async (level, auditResultId) => {
    try {
        await audit_result_service_1.auditResultService.submitAuditResult(auditResultId);
        // 刷新数据
        await loadAuditResults();
        emit('result-submitted', level, auditResults.value[level]);
        ant_design_vue_1.message.success(`${level}级审核结果已提交`);
    }
    catch (error) {
        ant_design_vue_1.message.error(`提交失败: ${error.message}`);
    }
};
const handleModifyLowerLevel = (targetResult) => {
    modifyTarget.value = targetResult;
    modifyModalVisible.value = true;
};
const handleConfirmModification = async () => {
    try {
        const formData = await modifyFormRef.value?.validateAndGetData();
        if (!formData || !modifyTarget.value) {
            return;
        }
        await audit_result_service_1.auditResultService.modifyLowerLevelResult(modifyTarget.value.id, authStore.user.id, formData);
        modifyModalVisible.value = false;
        await loadAuditResults();
        ant_design_vue_1.message.success('下级审核结果修改成功');
    }
    catch (error) {
        ant_design_vue_1.message.error(`修改失败: ${error.message}`);
    }
};
const handleModificationChange = (data) => {
    // 处理修改表单数据变化
};
const handleViewHistoryDetail = (historyItem) => {
    // 查看历史详情
    console.log('查看历史详情:', historyItem);
};
// 监听任务项变化
(0, vue_1.watch)(() => props.taskItemId, () => {
    if (props.taskItemId) {
        loadAuditResults();
    }
}, { immediate: true });
(0, vue_1.onMounted)(() => {
    if (props.taskItemId) {
        loadAuditResults();
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['audit-level-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-level-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-level-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-level-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-timeline-section']} */ ;
/** @type {__VLS_StyleScopedClasses['multi-level-audit']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-level-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tabs-tab']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-title']} */ ;
/** @type {__VLS_StyleScopedClasses['multi-level-audit']} */ ;
/** @type {__VLS_StyleScopedClasses['multi-level-audit']} */ ;
/** @type {__VLS_StyleScopedClasses['loading']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-level-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-timeline-section']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "multi-level-audit" },
});
const __VLS_0 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onChange': {} },
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "audit-level-tabs" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onChange': {} },
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "audit-level-tabs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onChange: (__VLS_ctx.handleTabChange)
};
__VLS_3.slots.default;
const __VLS_8 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    key: "department",
    tab: "科室级审核",
}));
const __VLS_10 = __VLS_9({
    key: "department",
    tab: "科室级审核",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_11.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tab-title" },
    });
    const __VLS_12 = {}.TeamOutlined;
    /** @type {[typeof __VLS_components.TeamOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
    if (__VLS_ctx.auditResults.department?.status === 'completed') {
        const __VLS_16 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            status: "success",
            ...{ class: "tab-badge" },
        }));
        const __VLS_18 = __VLS_17({
            status: "success",
            ...{ class: "tab-badge" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    }
    else if (__VLS_ctx.auditResults.department?.status === 'in_progress') {
        const __VLS_20 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
            status: "processing",
            ...{ class: "tab-badge" },
        }));
        const __VLS_22 = __VLS_21({
            status: "processing",
            ...{ class: "tab-badge" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    }
}
const __VLS_24 = {}.AuditResultPanel;
/** @type {[typeof __VLS_components.AuditResultPanel, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onUpdate': {} },
    ...{ 'onSubmit': {} },
    auditResult: (__VLS_ctx.auditResults.department),
    editable: (__VLS_ctx.canEditDepartmentLevel),
    reviewerInfo: (__VLS_ctx.departmentReviewer),
    auditLevel: "department",
}));
const __VLS_26 = __VLS_25({
    ...{ 'onUpdate': {} },
    ...{ 'onSubmit': {} },
    auditResult: (__VLS_ctx.auditResults.department),
    editable: (__VLS_ctx.canEditDepartmentLevel),
    reviewerInfo: (__VLS_ctx.departmentReviewer),
    auditLevel: "department",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onUpdate: (__VLS_ctx.handleDepartmentUpdate)
};
const __VLS_32 = {
    onSubmit: (__VLS_ctx.handleSubmitResult)
};
var __VLS_27;
var __VLS_11;
const __VLS_33 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
    key: "hospital",
    tab: "院级审核",
    disabled: (!__VLS_ctx.auditResults.department?.is_final),
}));
const __VLS_35 = __VLS_34({
    key: "hospital",
    tab: "院级审核",
    disabled: (!__VLS_ctx.auditResults.department?.is_final),
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
__VLS_36.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_36.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tab-title" },
    });
    const __VLS_37 = {}.BankOutlined;
    /** @type {[typeof __VLS_components.BankOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_38 = __VLS_asFunctionalComponent(__VLS_37, new __VLS_37({}));
    const __VLS_39 = __VLS_38({}, ...__VLS_functionalComponentArgsRest(__VLS_38));
    if (__VLS_ctx.auditResults.hospital?.status === 'completed') {
        const __VLS_41 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({
            status: "success",
            ...{ class: "tab-badge" },
        }));
        const __VLS_43 = __VLS_42({
            status: "success",
            ...{ class: "tab-badge" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_42));
    }
    else if (__VLS_ctx.auditResults.hospital?.status === 'in_progress') {
        const __VLS_45 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({
            status: "processing",
            ...{ class: "tab-badge" },
        }));
        const __VLS_47 = __VLS_46({
            status: "processing",
            ...{ class: "tab-badge" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_46));
    }
}
const __VLS_49 = {}.AuditResultPanel;
/** @type {[typeof __VLS_components.AuditResultPanel, ]} */ ;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
    ...{ 'onUpdate': {} },
    ...{ 'onSubmit': {} },
    ...{ 'onModifyLower': {} },
    auditResult: (__VLS_ctx.auditResults.hospital),
    editable: (__VLS_ctx.canEditHospitalLevel),
    reviewerInfo: (__VLS_ctx.hospitalReviewer),
    canModifyLowerLevel: (true),
    lowerLevelResults: ([__VLS_ctx.auditResults.department]),
    auditLevel: "hospital",
}));
const __VLS_51 = __VLS_50({
    ...{ 'onUpdate': {} },
    ...{ 'onSubmit': {} },
    ...{ 'onModifyLower': {} },
    auditResult: (__VLS_ctx.auditResults.hospital),
    editable: (__VLS_ctx.canEditHospitalLevel),
    reviewerInfo: (__VLS_ctx.hospitalReviewer),
    canModifyLowerLevel: (true),
    lowerLevelResults: ([__VLS_ctx.auditResults.department]),
    auditLevel: "hospital",
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
let __VLS_53;
let __VLS_54;
let __VLS_55;
const __VLS_56 = {
    onUpdate: (__VLS_ctx.handleHospitalUpdate)
};
const __VLS_57 = {
    onSubmit: (__VLS_ctx.handleSubmitResult)
};
const __VLS_58 = {
    onModifyLower: (__VLS_ctx.handleModifyLowerLevel)
};
var __VLS_52;
var __VLS_36;
const __VLS_59 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_60 = __VLS_asFunctionalComponent(__VLS_59, new __VLS_59({
    key: "expert",
    tab: "专家级审核",
    disabled: (!__VLS_ctx.auditResults.hospital?.is_final),
}));
const __VLS_61 = __VLS_60({
    key: "expert",
    tab: "专家级审核",
    disabled: (!__VLS_ctx.auditResults.hospital?.is_final),
}, ...__VLS_functionalComponentArgsRest(__VLS_60));
__VLS_62.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_62.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "tab-title" },
    });
    const __VLS_63 = {}.CrownOutlined;
    /** @type {[typeof __VLS_components.CrownOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_64 = __VLS_asFunctionalComponent(__VLS_63, new __VLS_63({}));
    const __VLS_65 = __VLS_64({}, ...__VLS_functionalComponentArgsRest(__VLS_64));
    if (__VLS_ctx.auditResults.expert?.status === 'completed') {
        const __VLS_67 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_68 = __VLS_asFunctionalComponent(__VLS_67, new __VLS_67({
            status: "success",
            ...{ class: "tab-badge" },
        }));
        const __VLS_69 = __VLS_68({
            status: "success",
            ...{ class: "tab-badge" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_68));
    }
    else if (__VLS_ctx.auditResults.expert?.status === 'in_progress') {
        const __VLS_71 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_72 = __VLS_asFunctionalComponent(__VLS_71, new __VLS_71({
            status: "processing",
            ...{ class: "tab-badge" },
        }));
        const __VLS_73 = __VLS_72({
            status: "processing",
            ...{ class: "tab-badge" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_72));
    }
}
const __VLS_75 = {}.AuditResultPanel;
/** @type {[typeof __VLS_components.AuditResultPanel, ]} */ ;
// @ts-ignore
const __VLS_76 = __VLS_asFunctionalComponent(__VLS_75, new __VLS_75({
    ...{ 'onUpdate': {} },
    ...{ 'onSubmit': {} },
    ...{ 'onModifyLower': {} },
    auditResult: (__VLS_ctx.auditResults.expert),
    editable: (__VLS_ctx.canEditExpertLevel),
    reviewerInfo: (__VLS_ctx.expertReviewer),
    canModifyLowerLevel: (true),
    lowerLevelResults: ([__VLS_ctx.auditResults.department, __VLS_ctx.auditResults.hospital]),
    isFinalLevel: (true),
    auditLevel: "expert",
}));
const __VLS_77 = __VLS_76({
    ...{ 'onUpdate': {} },
    ...{ 'onSubmit': {} },
    ...{ 'onModifyLower': {} },
    auditResult: (__VLS_ctx.auditResults.expert),
    editable: (__VLS_ctx.canEditExpertLevel),
    reviewerInfo: (__VLS_ctx.expertReviewer),
    canModifyLowerLevel: (true),
    lowerLevelResults: ([__VLS_ctx.auditResults.department, __VLS_ctx.auditResults.hospital]),
    isFinalLevel: (true),
    auditLevel: "expert",
}, ...__VLS_functionalComponentArgsRest(__VLS_76));
let __VLS_79;
let __VLS_80;
let __VLS_81;
const __VLS_82 = {
    onUpdate: (__VLS_ctx.handleExpertUpdate)
};
const __VLS_83 = {
    onSubmit: (__VLS_ctx.handleSubmitResult)
};
const __VLS_84 = {
    onModifyLower: (__VLS_ctx.handleModifyLowerLevel)
};
var __VLS_78;
var __VLS_62;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "audit-timeline-section" },
});
const __VLS_85 = {}.ADivider;
/** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
// @ts-ignore
const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({}));
const __VLS_87 = __VLS_86({}, ...__VLS_functionalComponentArgsRest(__VLS_86));
__VLS_88.slots.default;
var __VLS_88;
const __VLS_89 = {}.AuditTimeline;
/** @type {[typeof __VLS_components.AuditTimeline, ]} */ ;
// @ts-ignore
const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({
    ...{ 'onViewDetail': {} },
    auditHistory: (__VLS_ctx.auditHistory),
    currentLevel: (__VLS_ctx.activeTab),
}));
const __VLS_91 = __VLS_90({
    ...{ 'onViewDetail': {} },
    auditHistory: (__VLS_ctx.auditHistory),
    currentLevel: (__VLS_ctx.activeTab),
}, ...__VLS_functionalComponentArgsRest(__VLS_90));
let __VLS_93;
let __VLS_94;
let __VLS_95;
const __VLS_96 = {
    onViewDetail: (__VLS_ctx.handleViewHistoryDetail)
};
var __VLS_92;
const __VLS_97 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.modifyModalVisible),
    title: "修改下级审核结果",
    width: "800px",
}));
const __VLS_99 = __VLS_98({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.modifyModalVisible),
    title: "修改下级审核结果",
    width: "800px",
}, ...__VLS_functionalComponentArgsRest(__VLS_98));
let __VLS_101;
let __VLS_102;
let __VLS_103;
const __VLS_104 = {
    onOk: (__VLS_ctx.handleConfirmModification)
};
__VLS_100.slots.default;
if (__VLS_ctx.modifyModalVisible) {
    const __VLS_105 = {}.ModifyLowerLevelForm;
    /** @type {[typeof __VLS_components.ModifyLowerLevelForm, ]} */ ;
    // @ts-ignore
    const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
        ...{ 'onChange': {} },
        ref: "modifyFormRef",
        originalResult: (__VLS_ctx.modifyTarget),
        currentLevel: (__VLS_ctx.activeTab),
    }));
    const __VLS_107 = __VLS_106({
        ...{ 'onChange': {} },
        ref: "modifyFormRef",
        originalResult: (__VLS_ctx.modifyTarget),
        currentLevel: (__VLS_ctx.activeTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_106));
    let __VLS_109;
    let __VLS_110;
    let __VLS_111;
    const __VLS_112 = {
        onChange: (__VLS_ctx.handleModificationChange)
    };
    /** @type {typeof __VLS_ctx.modifyFormRef} */ ;
    var __VLS_113 = {};
    var __VLS_108;
}
var __VLS_100;
/** @type {__VLS_StyleScopedClasses['multi-level-audit']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-level-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['tab-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['audit-timeline-section']} */ ;
// @ts-ignore
var __VLS_114 = __VLS_113;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            TeamOutlined: icons_vue_1.TeamOutlined,
            BankOutlined: icons_vue_1.BankOutlined,
            CrownOutlined: icons_vue_1.CrownOutlined,
            activeTab: activeTab,
            auditResults: auditResults,
            auditHistory: auditHistory,
            modifyModalVisible: modifyModalVisible,
            modifyTarget: modifyTarget,
            modifyFormRef: modifyFormRef,
            departmentReviewer: departmentReviewer,
            hospitalReviewer: hospitalReviewer,
            expertReviewer: expertReviewer,
            canEditDepartmentLevel: canEditDepartmentLevel,
            canEditHospitalLevel: canEditHospitalLevel,
            canEditExpertLevel: canEditExpertLevel,
            handleTabChange: handleTabChange,
            handleDepartmentUpdate: handleDepartmentUpdate,
            handleHospitalUpdate: handleHospitalUpdate,
            handleExpertUpdate: handleExpertUpdate,
            handleSubmitResult: handleSubmitResult,
            handleModifyLowerLevel: handleModifyLowerLevel,
            handleConfirmModification: handleConfirmModification,
            handleModificationChange: handleModificationChange,
            handleViewHistoryDetail: handleViewHistoryDetail,
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
