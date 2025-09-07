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
import documentTypeUtils_1 from '@/utils/documentTypeUtils';
const props = (0, vue_1.defineProps)();
const emit = (0, vue_1.defineEmits)();
// 响应式数据
const showDetailModal = (0, vue_1.ref)(false);
const selectedDocument = (0, vue_1.ref)(null);
// 计算属性
const documents = (0, vue_1.computed)(() => props.data?.documents || []);
// 方法
const handleClose = () => {
    emit('update:visible', false);
};
const handleConfirm = () => {
    if (props.data) {
        emit('confirm', props.data);
    }
    handleClose();
};
const handleConfirmOnly = () => {
    if (props.data) {
        emit('confirmOnly', props.data);
    }
    handleClose();
};
const handleExport = () => {
    if (props.data) {
        emit('export', props.data);
    }
};
const showDocumentDetail = (doc) => {
    selectedDocument.value = doc;
    showDetailModal.value = true;
};
// 获取文档图标
const getDocumentIcon = (type) => {
    const iconMap = {
        admission_record: icons_vue_1.FileOutlined,
        first_progress_note: icons_vue_1.ScheduleOutlined,
        daily_progress_note: icons_vue_1.ScheduleOutlined,
        attending_progress: icons_vue_1.ScheduleOutlined,
        stage_summary: icons_vue_1.ScheduleOutlined,
        operation_record: icons_vue_1.ScissorOutlined,
        preoperative_summary: icons_vue_1.HeartOutlined,
        discharge_record: icons_vue_1.FileOutlined,
        imaging_report: icons_vue_1.ExperimentOutlined,
        lab_report: icons_vue_1.ExperimentOutlined,
        other_examination: icons_vue_1.ExperimentOutlined,
        surgery_consent: icons_vue_1.SafetyOutlined,
        anesthesia_consent: icons_vue_1.SafetyOutlined,
        blood_transfusion_consent: icons_vue_1.SafetyOutlined,
        special_treatment_consent: icons_vue_1.SafetyOutlined,
        critical_illness_notice: icons_vue_1.SafetyOutlined
    };
    return iconMap[type] || icons_vue_1.FileOutlined;
};
// 获取文档时间戳
const getDocumentTimestamp = (doc) => {
    const titleMatch = doc.title?.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/);
    if (titleMatch) {
        return titleMatch[1];
    }
    if (doc.extractedAt) {
        return doc.extractedAt instanceof Date
            ? doc.extractedAt.toISOString()
            : String(doc.extractedAt);
    }
    return null;
};
// 格式化时间戳
const formatTimestamp = (timestamp) => {
    if (!timestamp)
        return '';
    try {
        if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$/.test(timestamp)) {
            return timestamp;
        }
        const date = new Date(timestamp);
        if (isNaN(date.getTime()))
            return timestamp;
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        }).replace(/\//g, '-');
    }
    catch {
        return timestamp;
    }
};
// 获取完整内容
const getFullContent = (doc) => {
    if (doc.position?.fullContent && doc.position.fullContent.trim()) {
        return doc.position.fullContent;
    }
    const source = props.originalText || '';
    if (source) {
        const si = doc.position?.startIndex;
        const ei = doc.position?.endIndex;
        if (typeof si === 'number' && typeof ei === 'number' && ei > si && si >= 0 && ei <= source.length) {
            return source.slice(si, ei);
        }
    }
    return doc.content || '暂无内容';
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['document-card']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['result-overview']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-info']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-col']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
// CSS variable injection 
// CSS variable injection end 
const __VLS_0 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onUpdate:open': {} },
    open: (__VLS_ctx.visible),
    title: "LLM智能解析结果",
    width: "1200px",
    footer: (null),
    destroyOnClose: (true),
    ...{ class: "medical-document-result-modal" },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onUpdate:open': {} },
    open: (__VLS_ctx.visible),
    title: "LLM智能解析结果",
    width: "1200px",
    footer: (null),
    destroyOnClose: (true),
    ...{ class: "medical-document-result-modal" },
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
    ...{ class: "result-overview glass-card mb-4" },
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
    span: (6),
}));
const __VLS_15 = __VLS_14({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
__VLS_16.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-value" },
});
(__VLS_ctx.data?.patientName || '未识别');
var __VLS_16;
const __VLS_17 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
    span: (6),
}));
const __VLS_19 = __VLS_18({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
__VLS_20.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-value" },
});
(__VLS_ctx.data?.department || '未识别');
var __VLS_20;
const __VLS_21 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent(__VLS_21, new __VLS_21({
    span: (6),
}));
const __VLS_23 = __VLS_22({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
__VLS_24.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-value" },
});
(__VLS_ctx.documents.length);
var __VLS_24;
const __VLS_25 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent(__VLS_25, new __VLS_25({
    span: (6),
}));
const __VLS_27 = __VLS_26({
    span: (6),
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
__VLS_28.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-label" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "overview-value confidence-score" },
});
(Math.round(__VLS_ctx.data?.confidence || 0));
var __VLS_28;
var __VLS_12;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-info glass-card mb-4" },
});
const __VLS_29 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({
    gutter: (16),
}));
const __VLS_31 = __VLS_30({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_30));
__VLS_32.slots.default;
const __VLS_33 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
    span: (12),
}));
const __VLS_35 = __VLS_34({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
__VLS_36.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-label" },
});
const __VLS_37 = {}.MedicineBoxOutlined;
/** @type {[typeof __VLS_components.MedicineBoxOutlined, ]} */ ;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent(__VLS_37, new __VLS_37({
    ...{ class: "mr-2" },
}));
const __VLS_39 = __VLS_38({
    ...{ class: "mr-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-value" },
});
(__VLS_ctx.data?.primaryDiagnosis || '未识别');
var __VLS_36;
const __VLS_41 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({
    span: (12),
}));
const __VLS_43 = __VLS_42({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
__VLS_44.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-item" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-label" },
});
const __VLS_45 = {}.ScissorOutlined;
/** @type {[typeof __VLS_components.ScissorOutlined, ]} */ ;
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({
    ...{ class: "mr-2" },
}));
const __VLS_47 = __VLS_46({
    ...{ class: "mr-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_46));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "diagnosis-value" },
});
(__VLS_ctx.data?.majorSurgery || '无');
var __VLS_44;
var __VLS_32;
if (__VLS_ctx.data?.secondaryDiagnosis && __VLS_ctx.data.secondaryDiagnosis.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "secondary-diagnosis mt-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "diagnosis-label mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "diagnosis-tags" },
    });
    for (const [diagnosis, index] of __VLS_getVForSourceType((__VLS_ctx.data.secondaryDiagnosis))) {
        const __VLS_49 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
            key: (index),
            color: "blue",
        }));
        const __VLS_51 = __VLS_50({
            key: (index),
            color: "blue",
        }, ...__VLS_functionalComponentArgsRest(__VLS_50));
        __VLS_52.slots.default;
        (diagnosis);
        var __VLS_52;
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "documents-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "section-header" },
});
const __VLS_53 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
    ...{ class: "mr-2" },
}));
const __VLS_55 = __VLS_54({
    ...{ class: "mr-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_54));
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "section-title" },
});
const __VLS_57 = {}.ATag;
/** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
// @ts-ignore
const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
    color: "green",
    ...{ class: "ml-2" },
}));
const __VLS_59 = __VLS_58({
    color: "green",
    ...{ class: "ml-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_58));
__VLS_60.slots.default;
(__VLS_ctx.documents.length);
var __VLS_60;
if (__VLS_ctx.documents.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    const __VLS_61 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
        description: "未识别到任何文书",
    }));
    const __VLS_63 = __VLS_62({
        description: "未识别到任何文书",
    }, ...__VLS_functionalComponentArgsRest(__VLS_62));
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "documents-grid" },
    });
    for (const [doc, index] of __VLS_getVForSourceType((__VLS_ctx.documents))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!!(__VLS_ctx.documents.length === 0))
                        return;
                    __VLS_ctx.showDocumentDetail(doc);
                } },
            key: (doc.id),
            ...{ class: "document-card glass-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-title" },
        });
        const __VLS_65 = ((__VLS_ctx.getDocumentIcon(doc.type)));
        // @ts-ignore
        const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({
            ...{ class: "document-icon mr-2" },
        }));
        const __VLS_67 = __VLS_66({
            ...{ class: "document-icon mr-2" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_66));
        (doc.title || __VLS_ctx.getDocumentTypeLabel(doc.type));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-meta" },
        });
        const __VLS_69 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
            color: (__VLS_ctx.getDocumentTypeColor(doc.type)),
            size: "small",
        }));
        const __VLS_71 = __VLS_70({
            color: (__VLS_ctx.getDocumentTypeColor(doc.type)),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_70));
        __VLS_72.slots.default;
        (__VLS_ctx.getDocumentTypeLabel(doc.type));
        var __VLS_72;
        if (doc.confidence != null) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "confidence-badge" },
            });
            (Math.round(doc.confidence));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-summary" },
        });
        (doc.content || '暂无摘要');
        if (__VLS_ctx.getDocumentTimestamp(doc)) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "document-timestamp" },
            });
            const __VLS_73 = {}.ClockCircleOutlined;
            /** @type {[typeof __VLS_components.ClockCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({
                ...{ class: "mr-1" },
            }));
            const __VLS_75 = __VLS_74({
                ...{ class: "mr-1" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_74));
            (__VLS_ctx.formatTimestamp(__VLS_ctx.getDocumentTimestamp(doc)));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-actions" },
        });
        const __VLS_77 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_79 = __VLS_78({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_78));
        let __VLS_81;
        let __VLS_82;
        let __VLS_83;
        const __VLS_84 = {
            onClick: (...[$event]) => {
                if (!!(__VLS_ctx.documents.length === 0))
                    return;
                __VLS_ctx.showDocumentDetail(doc);
            }
        };
        __VLS_80.slots.default;
        var __VLS_80;
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "modal-actions" },
});
const __VLS_85 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({}));
const __VLS_87 = __VLS_86({}, ...__VLS_functionalComponentArgsRest(__VLS_86));
__VLS_88.slots.default;
const __VLS_89 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({
    ...{ 'onClick': {} },
}));
const __VLS_91 = __VLS_90({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_90));
let __VLS_93;
let __VLS_94;
let __VLS_95;
const __VLS_96 = {
    onClick: (__VLS_ctx.handleClose)
};
__VLS_92.slots.default;
var __VLS_92;
const __VLS_97 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_99 = __VLS_98({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_98));
let __VLS_101;
let __VLS_102;
let __VLS_103;
const __VLS_104 = {
    onClick: (__VLS_ctx.handleConfirm)
};
__VLS_100.slots.default;
const __VLS_105 = {}.DatabaseOutlined;
/** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
// @ts-ignore
const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
    ...{ class: "mr-1" },
}));
const __VLS_107 = __VLS_106({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_106));
var __VLS_100;
const __VLS_109 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
    ...{ 'onClick': {} },
}));
const __VLS_111 = __VLS_110({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_110));
let __VLS_113;
let __VLS_114;
let __VLS_115;
const __VLS_116 = {
    onClick: (__VLS_ctx.handleConfirmOnly)
};
__VLS_112.slots.default;
var __VLS_112;
const __VLS_117 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({
    ...{ 'onClick': {} },
}));
const __VLS_119 = __VLS_118({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_118));
let __VLS_121;
let __VLS_122;
let __VLS_123;
const __VLS_124 = {
    onClick: (__VLS_ctx.handleExport)
};
__VLS_120.slots.default;
const __VLS_125 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({
    ...{ class: "mr-1" },
}));
const __VLS_127 = __VLS_126({
    ...{ class: "mr-1" },
}, ...__VLS_functionalComponentArgsRest(__VLS_126));
var __VLS_120;
var __VLS_88;
const __VLS_129 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_130 = __VLS_asFunctionalComponent(__VLS_129, new __VLS_129({
    open: (__VLS_ctx.showDetailModal),
    title: (__VLS_ctx.selectedDocument?.title || '文书详情'),
    width: "800px",
    footer: (null),
    destroyOnClose: (true),
    ...{ class: "document-detail-modal" },
}));
const __VLS_131 = __VLS_130({
    open: (__VLS_ctx.showDetailModal),
    title: (__VLS_ctx.selectedDocument?.title || '文书详情'),
    width: "800px",
    footer: (null),
    destroyOnClose: (true),
    ...{ class: "document-detail-modal" },
}, ...__VLS_functionalComponentArgsRest(__VLS_130));
__VLS_132.slots.default;
if (__VLS_ctx.selectedDocument) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "document-detail" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "detail-header mb-4" },
    });
    const __VLS_133 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_134 = __VLS_asFunctionalComponent(__VLS_133, new __VLS_133({
        color: (__VLS_ctx.getDocumentTypeColor(__VLS_ctx.selectedDocument.type)),
    }));
    const __VLS_135 = __VLS_134({
        color: (__VLS_ctx.getDocumentTypeColor(__VLS_ctx.selectedDocument.type)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_134));
    __VLS_136.slots.default;
    (__VLS_ctx.getDocumentTypeLabel(__VLS_ctx.selectedDocument.type));
    var __VLS_136;
    if (__VLS_ctx.selectedDocument.confidence != null) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "confidence-badge ml-2" },
        });
        (Math.round(__VLS_ctx.selectedDocument.confidence));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "detail-content" },
    });
    const __VLS_137 = {}.ATypographyTitle;
    /** @type {[typeof __VLS_components.ATypographyTitle, typeof __VLS_components.aTypographyTitle, typeof __VLS_components.ATypographyTitle, typeof __VLS_components.aTypographyTitle, ]} */ ;
    // @ts-ignore
    const __VLS_138 = __VLS_asFunctionalComponent(__VLS_137, new __VLS_137({
        level: (5),
    }));
    const __VLS_139 = __VLS_138({
        level: (5),
    }, ...__VLS_functionalComponentArgsRest(__VLS_138));
    __VLS_140.slots.default;
    var __VLS_140;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "content-container" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
        ...{ class: "document-content" },
    });
    (__VLS_ctx.getFullContent(__VLS_ctx.selectedDocument));
}
var __VLS_132;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['medical-document-result-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-content']} */ ;
/** @type {__VLS_StyleScopedClasses['result-overview']} */ ;
/** @type {__VLS_StyleScopedClasses['glass-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-item']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-value']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-item']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-value']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-item']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-value']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-item']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-value']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-score']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-info']} */ ;
/** @type {__VLS_StyleScopedClasses['glass-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-item']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-label']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-value']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-item']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-label']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-value']} */ ;
/** @type {__VLS_StyleScopedClasses['secondary-diagnosis']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-label']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['diagnosis-tags']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-section']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['document-card']} */ ;
/** @type {__VLS_StyleScopedClasses['glass-card']} */ ;
/** @type {__VLS_StyleScopedClasses['document-header']} */ ;
/** @type {__VLS_StyleScopedClasses['document-title']} */ ;
/** @type {__VLS_StyleScopedClasses['document-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['document-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['document-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['document-timestamp']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['document-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['modal-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['document-detail-modal']} */ ;
/** @type {__VLS_StyleScopedClasses['document-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-badge']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['document-content']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            MedicineBoxOutlined: icons_vue_1.MedicineBoxOutlined,
            ScissorOutlined: icons_vue_1.ScissorOutlined,
            ClockCircleOutlined: icons_vue_1.ClockCircleOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            getDocumentTypeLabel: documentTypeUtils_1.getDocumentTypeLabel,
            getDocumentTypeColor: documentTypeUtils_1.getDocumentTypeColor,
            showDetailModal: showDetailModal,
            selectedDocument: selectedDocument,
            documents: documents,
            handleClose: handleClose,
            handleConfirm: handleConfirm,
            handleConfirmOnly: handleConfirmOnly,
            handleExport: handleExport,
            showDocumentDetail: showDocumentDetail,
            getDocumentIcon: getDocumentIcon,
            getDocumentTimestamp: getDocumentTimestamp,
            formatTimestamp: formatTimestamp,
            getFullContent: getFullContent,
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
