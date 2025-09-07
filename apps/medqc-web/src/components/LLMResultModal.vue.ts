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
import icons_vue_1 from '@ant-design/icons-vue';
import llmService_1 from '@/services/llmService';
import documentTypeUtils_1 from '@/utils/documentTypeUtils';
const props = (0, vue_1.defineProps)();
const emit = (0, vue_1.defineEmits)();
// 响应式数据
const loading = (0, vue_1.ref)(false);
const saving = (0, vue_1.ref)(false);
const selectedKeys = (0, vue_1.ref)(: any[]);
const expandedKeys = (0, vue_1.ref)(: any[]);
const selectedDocument = (0, vue_1.ref)(null);
// 计算属性
const providerName = (0, vue_1.computed)(() => props.result?.provider || '未知');
const modelCode = (0, vue_1.computed)(() => props.result?.model || '未知');
const endpoint = (0, vue_1.computed)(() => props.result?.endpoint || '-');
const tokensUsed = (0, vue_1.computed)(() => props.result?.tokensUsed || 0);
const processingTime = (0, vue_1.computed)(() => props.result?.processingTime || 0);
const confidencePct = (0, vue_1.computed)(() => {
    const c = props.data?.confidence;
    if (typeof c === 'number')
        return Math.max(0, Math.min(100, Math.round(c)));
    return 0;
});
const savedPct = (0, vue_1.computed)(() => {
    try {
        const text = props.data?.content || '';
        const baseline = (text ? Math.round(text.length / 4) : 0) + 1000;
        const used = tokensUsed.value || 0;
        if (baseline <= 0)
            return null;
        return Math.max(0, Math.round((Math.max(0, baseline - used) / baseline) * 100));
    }
    catch {
        return null;
    }
});
// 构建树形数据
const treeData = (0, vue_1.computed)(() => {
    const documents = props.data?.documents || [];
    // 按分类分组文书
    const groupedDocs = new Map();
    documents.forEach((doc, index) => {
        const category = (0, documentTypeUtils_1.getDocumentCategory)(doc.type);
        if (!groupedDocs.has(category)) {
            groupedDocs.set(category, : any[]);
        }
        groupedDocs.get(category).push({
            key: doc.id || `doc_${index}`,
            title: doc.title || (0, documentTypeUtils_1.getDocumentTypeLabel)(doc.type),
            confidence: doc.confidence,
            type: doc.type,
            document: doc,
            isLeaf: true
        });
    });
    // 构建树形结构
    const treeNodes = [];
    // 定义分类顺序和标签
    const categoryOrder = [
        { key: 'admission_record', label: '入院记录', icon: 'FileTextOutlined' },
        { key: 'progress_note', label: '病程记录', icon: 'EditOutlined' },
        { key: 'operation_record', label: '手术记录', icon: 'ScissorOutlined' },
        { key: 'discharge_record', label: '出院记录', icon: 'ExportOutlined' },
        { key: 'auxiliary_examination', label: '检验检查报告', icon: 'ExperimentOutlined' },
        { key: 'informed_consent', label: '知情同意书', icon: 'SafetyOutlined' }
    ];
    categoryOrder.forEach(category => {
        const categoryDocs = groupedDocs.get(category.key) || [];
        if (categoryDocs.length > 0) {
            treeNodes.push({
                key: category.key,
                title: category.label,
                icon: category.icon,
                children: categoryDocs,
                isLeaf: false,
                selectable: false // 分类节点不可选择
            });
        }
    });
    return treeNodes;
});
// 监听数据变化，自动选择第一个文书
(0, vue_1.watch)(() => props.data, (newData: any) => {
    if (newData?.documents?.length > 0) {
        const firstDoc = newData.documents[0];
        const firstKey = firstDoc.id || 'doc_0';
        selectedKeys.value = [firstKey];
        selectedDocument.value = firstDoc;
        // 展开所有分类节点
        const categoryKeys = ['admission_record', 'progress_note', 'operation_record', 'discharge_record', 'auxiliary_examination', 'informed_consent'];
        expandedKeys.value = categoryKeys;
    }
}, { immediate: true });
// 方法
const handleClose = () => {
    emit('update:visible', false);
};
const onDocumentSelect = (keys, info) => {
    if (keys.length > 0) {
        const selectedNode = info.node;
        // 只有文书节点（叶子节点）才能被选中
        if (selectedNode.isLeaf && selectedNode.document) {
            selectedKeys.value = keys;
            selectedDocument.value = selectedNode.document;
        }
        else {
            // 如果选中的是分类节点，清除选择
            selectedKeys.value = [];
            selectedDocument.value = null;
        }
    }
    else {
        selectedKeys.value = [];
        selectedDocument.value = null;
    }
};
const onTreeExpand = (keys) => {
    expandedKeys.value = keys;
};
const getCategoryIcon = (iconName) => {
    const iconMap = {
        FileTextOutlined: icons_vue_1.FileTextOutlined,
        EditOutlined: icons_vue_1.EditOutlined,
        ScissorOutlined: icons_vue_1.ScissorOutlined,
        ExportOutlined: icons_vue_1.ExportOutlined,
        ExperimentOutlined: icons_vue_1.ExperimentOutlined,
        SafetyOutlined: icons_vue_1.SafetyOutlined
    };
    return iconMap[iconName] || icons_vue_1.FolderOutlined;
};
const getDocumentIcon = (type) => {
    const iconMap = {
        [llmService_1.DocumentType.ADMISSION_RECORD]: icons_vue_1.FileTextOutlined,
        [llmService_1.DocumentType.ADMISSION_RECORD_24H_IN]: icons_vue_1.FileTextOutlined,
        [llmService_1.DocumentType.ADMISSION_RECORD_24H_OUT]: icons_vue_1.FileTextOutlined,
        [llmService_1.DocumentType.FIRST_PROGRESS_NOTE]: icons_vue_1.EditOutlined,
        [llmService_1.DocumentType.DAILY_PROGRESS_NOTE]: icons_vue_1.EditOutlined,
        [llmService_1.DocumentType.ATTENDING_FIRST_PROGRESS]: icons_vue_1.EditOutlined,
        [llmService_1.DocumentType.ATTENDING_PROGRESS]: icons_vue_1.EditOutlined,
        [llmService_1.DocumentType.CONSULTATION_RECORD]: icons_vue_1.EditOutlined,
        [llmService_1.DocumentType.HANDOVER_RECORD]: icons_vue_1.EditOutlined,
        [llmService_1.DocumentType.STAGE_SUMMARY]: icons_vue_1.EditOutlined,
        [llmService_1.DocumentType.OPERATION_RECORD]: icons_vue_1.ScissorOutlined,
        [llmService_1.DocumentType.PREOPERATIVE_SUMMARY]: icons_vue_1.ScissorOutlined,
        [llmService_1.DocumentType.DISCHARGE_RECORD]: icons_vue_1.ExportOutlined,
        [llmService_1.DocumentType.DEATH_RECORD]: icons_vue_1.ExportOutlined,
        [llmService_1.DocumentType.DEATH_CASE_DISCUSSION]: icons_vue_1.ExportOutlined,
        [llmService_1.DocumentType.IMAGING_REPORT]: icons_vue_1.ExperimentOutlined,
        [llmService_1.DocumentType.LAB_REPORT]: icons_vue_1.ExperimentOutlined,
        [llmService_1.DocumentType.OTHER_EXAMINATION]: icons_vue_1.ExperimentOutlined,
        [llmService_1.DocumentType.SURGERY_CONSENT]: icons_vue_1.SafetyOutlined,
        [llmService_1.DocumentType.ANESTHESIA_CONSENT]: icons_vue_1.SafetyOutlined,
        [llmService_1.DocumentType.BLOOD_TRANSFUSION_CONSENT]: icons_vue_1.SafetyOutlined,
        [llmService_1.DocumentType.SPECIAL_TREATMENT_CONSENT]: icons_vue_1.SafetyOutlined,
        [llmService_1.DocumentType.CRITICAL_ILLNESS_NOTICE]: icons_vue_1.SafetyOutlined
    };
    return iconMap[type] || icons_vue_1.FileOutlined;
};
const getDocumentContent = (doc) => {
    if (doc.position?.fullContent && doc.position.fullContent.trim()) {
        return doc.position.fullContent;
    }
    const source = props.originalText || props.data?.content || '';
    if (source) {
        const si = doc.position?.startIndex;
        const ei = doc.position?.endIndex;
        if (typeof si === 'number' && typeof ei === 'number' && ei > si && si >= 0 && ei <= source.length) {
            return source.slice(si, ei);
        }
    }
    return doc.content || '暂无内容';
};
// 事件处理
const saveAndRedirect = () => {
    emit('save-and-redirect');
};
const saveOnly = () => {
    emit('save-only');
};
const exportResult = () => {
    emit('export-result');
};
const exportPDF = () => {
    emit('export-pdf');
};
const goToImport = () => {
    emit('go-to-import');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['llm-result-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-content']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-tags']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tree-node-content-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tree-node-content-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tree-treenode']} */ ;
/** @type {__VLS_StyleScopedClasses['category-node']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tree-treenode']} */ ;
/** @type {__VLS_StyleScopedClasses['category-node']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tree-treenode']} */ ;
/** @type {__VLS_StyleScopedClasses['node-title']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-tree-treenode']} */ ;
/** @type {__VLS_StyleScopedClasses['document-node']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['node-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['node-title']} */ ;
/** @type {__VLS_StyleScopedClasses['right-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-title']} */ ;
/** @type {__VLS_StyleScopedClasses['left-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['content-body']} */ ;
/** @type {__VLS_StyleScopedClasses['left-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['right-panel']} */ ;
// CSS variable injection 
// CSS variable injection end 
const __VLS_0 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:open': {} },
    open: (__VLS_ctx.visible),
    title: "LLM 精准解析结果",
    width: "1400px",
    footer: (null),
    destroyOnClose: (true),
    maskClosable: (false),
    ...{ class: "llm-result-modal" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:open': {} },
    open: (__VLS_ctx.visible),
    title: "LLM 精准解析结果",
    width: "1400px",
    footer: (null),
    destroyOnClose: (true),
    maskClosable: (false),
    ...{ class: "llm-result-modal" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    'onUpdate:open': (...[$event]) => {
        __VLS_ctx.$emit('update:visible', $event);
    }
};
var __VLS_8 = {};
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "modal-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "top-stats mb-4" },
});
const __VLS_9 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(__VLS_9, new __VLS_9({
    gutter: (16),
}));
const __VLS_11 = __VLS_10({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
__VLS_12.slots.default;
const __VLS_13 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent(__VLS_13, new __VLS_13({
    span: (8),
}));
const __VLS_15 = __VLS_14({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
__VLS_16.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.providerName || '未知');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.modelCode || '未知');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.endpoint || '-');
var __VLS_16;
const __VLS_17 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
    span: (8),
}));
const __VLS_19 = __VLS_18({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
__VLS_20.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.tokensUsed || 0);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
(__VLS_ctx.processingTime || 0);
if (__VLS_ctx.savedPct != null) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    (__VLS_ctx.savedPct);
}
var __VLS_20;
const __VLS_21 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent(__VLS_21, new __VLS_21({
    span: (8),
}));
const __VLS_23 = __VLS_22({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
__VLS_24.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "stat-content" },
});
const __VLS_25 = {}.AProgress;
/** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent(__VLS_25, new __VLS_25({
    percent: (__VLS_ctx.confidencePct),
    status: (__VLS_ctx.confidencePct >= 80 ? 'success' : (__VLS_ctx.confidencePct >= 60 ? 'active' : 'normal')),
    size: "small",
}));
const __VLS_27 = __VLS_26({
    percent: (__VLS_ctx.confidencePct),
    status: (__VLS_ctx.confidencePct >= 80 ? 'success' : (__VLS_ctx.confidencePct >= 60 ? 'active' : 'normal')),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
var __VLS_24;
var __VLS_12;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "patient-info mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "info-title" },
});
const __VLS_29 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({
    gutter: (24),
}));
const __VLS_31 = __VLS_30({
    gutter: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_30));
__VLS_32.slots.default;
const __VLS_33 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
    span: (6),
}));
const __VLS_35 = __VLS_34({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
__VLS_36.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "info-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-value" },
});
(__VLS_ctx.data?.patientName || '-');
var __VLS_36;
const __VLS_37 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent(__VLS_37, new __VLS_37({
    span: (6),
}));
const __VLS_39 = __VLS_38({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
__VLS_40.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "info-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-value" },
});
(__VLS_ctx.data?.department || '-');
var __VLS_40;
const __VLS_41 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({
    span: (6),
}));
const __VLS_43 = __VLS_42({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
__VLS_44.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "info-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-value" },
});
(__VLS_ctx.data?.patientAge ?? '-');
var __VLS_44;
const __VLS_45 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({
    span: (6),
}));
const __VLS_47 = __VLS_46({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_46));
__VLS_48.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "info-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "info-value" },
});
(__VLS_ctx.data?.patientGender || '-');
var __VLS_48;
var __VLS_32;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-info mb-4" },
});
const __VLS_49 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
    gutter: (16),
}));
const __VLS_51 = __VLS_50({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
__VLS_52.slots.default;
const __VLS_53 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
    span: (12),
}));
const __VLS_55 = __VLS_54({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_54));
__VLS_56.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "diagnosis-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "diagnosis-value" },
});
(__VLS_ctx.data?.primaryDiagnosis || '-');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "diagnosis-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-tags" },
});
for (const [d, i] of __VLS_getVForSourceType(((__VLS_ctx.data?.secondaryDiagnosis || : any[])))) {
    const __VLS_57 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
        key: (i),
        color: "blue",
    }));
    const __VLS_59 = __VLS_58({
        key: (i),
        color: "blue",
    }, ...__VLS_functionalComponentArgsRest(__VLS_58));
    __VLS_60.slots.default;
    (d);
    var __VLS_60;
}
if (!(__VLS_ctx.data?.secondaryDiagnosis || : any[]).length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
}
var __VLS_56;
const __VLS_61 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
    span: (12),
}));
const __VLS_63 = __VLS_62({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
__VLS_64.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "diagnosis-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "diagnosis-value" },
});
(__VLS_ctx.data?.majorSurgery || '-');
var __VLS_64;
var __VLS_52;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "main-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-body" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "left-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "panel-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "document-tree" },
});
if (__VLS_ctx.treeData.length > 0) {
    const __VLS_65 = {}.ATree;
    /** @type {[typeof __VLS_components.ATree, typeof __VLS_components.aTree, typeof __VLS_components.ATree, typeof __VLS_components.aTree, ]} */ ;
    // @ts-ignore
    const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({
        ...{ 'onSelect': {} },
        ...{ 'onExpand': {} },
        treeData: (__VLS_ctx.treeData),
        selectedKeys: (__VLS_ctx.selectedKeys),
        expandedKeys: (__VLS_ctx.expandedKeys),
        defaultExpandAll: (true),
        ...{ class: "custom-tree" },
    }));
    const __VLS_67 = __VLS_66({
        ...{ 'onSelect': {} },
        ...{ 'onExpand': {} },
        treeData: (__VLS_ctx.treeData),
        selectedKeys: (__VLS_ctx.selectedKeys),
        expandedKeys: (__VLS_ctx.expandedKeys),
        defaultExpandAll: (true),
        ...{ class: "custom-tree" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_66));
    let __VLS_69;
    let __VLS_70;
    let __VLS_71;
    const __VLS_72 = {
        onSelect: (__VLS_ctx.onDocumentSelect)
    };
    const __VLS_73 = {
        onExpand: (__VLS_ctx.onTreeExpand)
    };
    __VLS_68.slots.default;
    {
        const { title: __VLS_thisSlot } = __VLS_68.slots;
        const [{ title, confidence, type, icon, isLeaf }] = __VLS_getSlotParams(__VLS_thisSlot);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "tree-node" },
            ...{ class: ({ 'category-node': !isLeaf, 'document-node': isLeaf }) },
        });
        const __VLS_74 = ((isLeaf ? __VLS_ctx.getDocumentIcon(type) : __VLS_ctx.getCategoryIcon(icon)));
        // @ts-ignore
        const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
            ...{ class: "node-icon" },
            ...{ class: ({ 'category-icon': !isLeaf }) },
        }));
        const __VLS_76 = __VLS_75({
            ...{ class: "node-icon" },
            ...{ class: ({ 'category-icon': !isLeaf }) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_75));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "node-title" },
        });
        (title);
        if (confidence != null && isLeaf) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "node-confidence" },
            });
            (Math.round(confidence));
        }
    }
    {
        const { switcherIcon: __VLS_thisSlot } = __VLS_68.slots;
        const [{ expanded }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_78 = ((expanded ? __VLS_ctx.FolderOpenOutlined : __VLS_ctx.FolderOutlined));
        // @ts-ignore
        const __VLS_79 = __VLS_asFunctionalComponent(__VLS_78, new __VLS_78({}));
        const __VLS_80 = __VLS_79({}, ...__VLS_functionalComponentArgsRest(__VLS_79));
    }
    var __VLS_68;
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-tree" },
    });
    const __VLS_82 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
        description: "暂无文书数据",
    }));
    const __VLS_84 = __VLS_83({
        description: "暂无文书数据",
    }, ...__VLS_functionalComponentArgsRest(__VLS_83));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "right-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "panel-title" },
});
(__VLS_ctx.selectedDocument?.title || '文书内容');
if (__VLS_ctx.selectedDocument) {
    const __VLS_86 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_87 = __VLS_asFunctionalComponent(__VLS_86, new __VLS_86({
        color: (__VLS_ctx.getDocumentTypeColor(__VLS_ctx.selectedDocument.type)),
        size: "small",
    }));
    const __VLS_88 = __VLS_87({
        color: (__VLS_ctx.getDocumentTypeColor(__VLS_ctx.selectedDocument.type)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_87));
    __VLS_89.slots.default;
    (__VLS_ctx.getDocumentTypeLabel(__VLS_ctx.selectedDocument.type));
    var __VLS_89;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "document-content" },
});
if (__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "content-loading" },
    });
    const __VLS_90 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
        size: "large",
    }));
    const __VLS_92 = __VLS_91({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "loading-text" },
    });
}
else if (__VLS_ctx.selectedDocument) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "content-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
        ...{ class: "document-text" },
    });
    (__VLS_ctx.getDocumentContent(__VLS_ctx.selectedDocument));
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "content-empty" },
    });
    const __VLS_94 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_95 = __VLS_asFunctionalComponent(__VLS_94, new __VLS_94({
        description: "请选择左侧文书查看内容",
    }));
    const __VLS_96 = __VLS_95({
        description: "请选择左侧文书查看内容",
    }, ...__VLS_functionalComponentArgsRest(__VLS_95));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "modal-actions" },
});
const __VLS_98 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
    size: "large",
}));
const __VLS_100 = __VLS_99({
    size: "large",
}, ...__VLS_functionalComponentArgsRest(__VLS_99));
__VLS_101.slots.default;
const __VLS_102 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_103 = __VLS_asFunctionalComponent(__VLS_102, new __VLS_102({}));
const __VLS_104 = __VLS_103({}, ...__VLS_functionalComponentArgsRest(__VLS_103));
__VLS_105.slots.default;
const __VLS_106 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_107 = __VLS_asFunctionalComponent(__VLS_106, new __VLS_106({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
    icon: (__VLS_ctx.h(__VLS_ctx.DatabaseOutlined)),
}));
const __VLS_108 = __VLS_107({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
    icon: (__VLS_ctx.h(__VLS_ctx.DatabaseOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_107));
let __VLS_110;
let __VLS_111;
let __VLS_112;
const __VLS_113 = {
    onClick: (__VLS_ctx.saveAndRedirect)
};
__VLS_109.slots.default;
var __VLS_109;
const __VLS_114 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_115 = __VLS_asFunctionalComponent(__VLS_114, new __VLS_114({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.saving),
    icon: (__VLS_ctx.h(__VLS_ctx.SaveOutlined)),
}));
const __VLS_116 = __VLS_115({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.saving),
    icon: (__VLS_ctx.h(__VLS_ctx.SaveOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_115));
let __VLS_118;
let __VLS_119;
let __VLS_120;
const __VLS_121 = {
    onClick: (__VLS_ctx.saveOnly)
};
__VLS_117.slots.default;
var __VLS_117;
var __VLS_105;
const __VLS_122 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_123 = __VLS_asFunctionalComponent(__VLS_122, new __VLS_122({}));
const __VLS_124 = __VLS_123({}, ...__VLS_functionalComponentArgsRest(__VLS_123));
__VLS_125.slots.default;
const __VLS_126 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_127 = __VLS_asFunctionalComponent(__VLS_126, new __VLS_126({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
}));
const __VLS_128 = __VLS_127({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.DownloadOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_127));
let __VLS_130;
let __VLS_131;
let __VLS_132;
const __VLS_133 = {
    onClick: (__VLS_ctx.exportResult)
};
__VLS_129.slots.default;
var __VLS_129;
const __VLS_134 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_135 = __VLS_asFunctionalComponent(__VLS_134, new __VLS_134({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.FilePdfOutlined)),
}));
const __VLS_136 = __VLS_135({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.FilePdfOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_135));
let __VLS_138;
let __VLS_139;
let __VLS_140;
const __VLS_141 = {
    onClick: (__VLS_ctx.exportPDF)
};
__VLS_137.slots.default;
var __VLS_137;
var __VLS_125;
const __VLS_142 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({}));
const __VLS_144 = __VLS_143({}, ...__VLS_functionalComponentArgsRest(__VLS_143));
__VLS_145.slots.default;
const __VLS_146 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_147 = __VLS_asFunctionalComponent(__VLS_146, new __VLS_146({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
}));
const __VLS_148 = __VLS_147({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_147));
let __VLS_150;
let __VLS_151;
let __VLS_152;
const __VLS_153 = {
    onClick: (__VLS_ctx.goToImport)
};
__VLS_149.slots.default;
var __VLS_149;
const __VLS_154 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.CloseOutlined)),
}));
const __VLS_156 = __VLS_155({
    ...{ 'onClick': {} },
    icon: (__VLS_ctx.h(__VLS_ctx.CloseOutlined)),
}, ...__VLS_functionalComponentArgsRest(__VLS_155));
let __VLS_158;
let __VLS_159;
let __VLS_160;
const __VLS_161 = {
    onClick: (__VLS_ctx.handleClose)
};
__VLS_157.slots.default;
var __VLS_157;
var __VLS_145;
var __VLS_101;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['llm-result-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['top-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-content']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-content']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-card']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-title']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-content']} */ ;
/** @type {__VLS_StyleScopedClasses['patient-info']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['info-title']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-label']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-label']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-label']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['info-item']} */ ;
/** @type {__VLS_StyleScopedClasses['info-label']} */ ;
/** @type {__VLS_StyleScopedClasses['info-value']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-info']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-card']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-title']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-content']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-item']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-label']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-value']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-item']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-label']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-tags']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-card']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-title']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-content']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-item']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-label']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-value']} */ ;
/** @type {__VLS_StyleScopedClasses['main-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-title']} */ ;
/** @type {__VLS_StyleScopedClasses['content-body']} */ ;
/** @type {__VLS_StyleScopedClasses['left-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-title']} */ ;
/** @type {__VLS_StyleScopedClasses['document-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['tree-node']} */ ;
/** @type {__VLS_StyleScopedClasses['category-node']} */ ;
/** @type {__VLS_StyleScopedClasses['document-node']} */ ;
/** @type {__VLS_StyleScopedClasses['node-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['category-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['node-title']} */ ;
/** @type {__VLS_StyleScopedClasses['node-confidence']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['right-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-title']} */ ;
/** @type {__VLS_StyleScopedClasses['document-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-loading']} */ ;
/** @type {__VLS_StyleScopedClasses['loading-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['document-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            SaveOutlined: icons_vue_1.SaveOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            FilePdfOutlined: icons_vue_1.FilePdfOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            CloseOutlined: icons_vue_1.CloseOutlined,
            FolderOutlined: icons_vue_1.FolderOutlined,
            FolderOpenOutlined: icons_vue_1.FolderOpenOutlined,
            getDocumentTypeLabel: documentTypeUtils_1.getDocumentTypeLabel,
            getDocumentTypeColor: documentTypeUtils_1.getDocumentTypeColor,
            loading: loading,
            saving: saving,
            selectedKeys: selectedKeys,
            expandedKeys: expandedKeys,
            selectedDocument: selectedDocument,
            providerName: providerName,
            modelCode: modelCode,
            endpoint: endpoint,
            tokensUsed: tokensUsed,
            processingTime: processingTime,
            confidencePct: confidencePct,
            savedPct: savedPct,
            treeData: treeData,
            handleClose: handleClose,
            onDocumentSelect: onDocumentSelect,
            onTreeExpand: onTreeExpand,
            getCategoryIcon: getCategoryIcon,
            getDocumentIcon: getDocumentIcon,
            getDocumentContent: getDocumentContent,
            saveAndRedirect: saveAndRedirect,
            saveOnly: saveOnly,
            exportResult: exportResult,
            exportPDF: exportPDF,
            goToImport: goToImport,
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
