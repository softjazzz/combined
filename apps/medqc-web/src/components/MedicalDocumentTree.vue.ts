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
import documentTypeUtils_1 from '@/utils/documentTypeUtils';
const props = (0, vue_1.defineProps)();
const groupedDocs = (0, vue_1.computed)(() => {
    const map = new Map();
    if (!props.documents)
        return map;
    for (const d of props.documents) {
        const cat = documentTypeUtils_1.DOCUMENT_TYPE_TO_CATEGORY[d.type];
        if (!map.has(cat))
            map.set(cat, : any[]);
        map.get(cat).push(d);
    }
    // 按时间顺序排序（优先）或标题排序（兜底）
    for (const [k, arr] of map) {
        arr.sort((a, b: any) => {
            const timeA = getDocumentTimestamp(a);
            const timeB = getDocumentTimestamp(b);
            // 如果都有时间戳，按时间排序
            if (timeA && timeB) {
                return timeA.localeCompare(timeB);
            }
            // 有时间戳的排在前面
            if (timeA && !timeB)
                return -1;
            if (!timeA && timeB)
                return 1;
            // 都没有时间戳，按标题排序
            return (a.title || '').localeCompare(b.title || '', 'zh');
        });
        map.set(k, arr);
    }
    return map;
});
const groupedArray = (0, vue_1.computed)(() => Array.from(groupedDocs.value.entries()));
function categoryLabel(cat) {
    return documentTypeUtils_1.DOCUMENT_CATEGORY_LABELS[cat] || String(cat);
}
// 获取文档时间戳
function getDocumentTimestamp(doc) {
    // 优先从标题中提取时间戳（格式：YYYY-MM-DD HH:MM）
    const titleMatch = doc.title?.match(/(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})/);
    if (titleMatch) {
        return titleMatch[1];
    }
    // 其次使用extractedAt字段
    if (doc.extractedAt) {
        return doc.extractedAt instanceof Date
            ? doc.extractedAt.toISOString()
            : String(doc.extractedAt);
    }
    return null;
}
// 格式化时间戳显示
function formatTimestamp(timestamp) {
    if (!timestamp)
        return '';
    try {
        // 如果是YYYY-MM-DD HH:MM格式，直接返回
        if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$/.test(timestamp)) {
            return timestamp;
        }
        // 否则解析为Date对象并格式化
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
}
function getFullContent(doc) {
    // 1) 优先：使用新的 fullContent 字段（来自确定性切片）
    if (doc.position?.fullContent && doc.position.fullContent.trim()) {
        return doc.position.fullContent;
    }
    // 2) 次选：按精确的指针切片（startIndex/endIndex）
    const source = props.originalText || '';
    if (source) {
        const si = doc.position?.startIndex;
        const ei = doc.position?.endIndex;
        if (typeof si === 'number' && typeof ei === 'number' && ei > si && si >= 0 && ei <= source.length) {
            return source.slice(si, ei);
        }
    }
    // 3) 兜底：使用摘要内容
    return doc.content || '暂无内容';
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['doc-main-info']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-meta-info']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "doc-tree glass-card" },
});
const __VLS_0 = {}.ATypographyTitle;
/** @type {[typeof __VLS_components.ATypographyTitle, typeof __VLS_components.aTypographyTitle, typeof __VLS_components.ATypographyTitle, typeof __VLS_components.aTypographyTitle, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    level: (5),
    ...{ class: "mb-3" },
}));
const __VLS_2 = __VLS_1({
    level: (5),
    ...{ class: "mb-3" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
var __VLS_3;
if (!__VLS_ctx.groupedDocs.size) {
    const __VLS_4 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        description: "暂无文书",
    }));
    const __VLS_6 = __VLS_5({
        description: "暂无文书",
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
}
else {
    const __VLS_8 = {}.ACollapse;
    /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        ghost: true,
        bordered: (false),
    }));
    const __VLS_10 = __VLS_9({
        ghost: true,
        bordered: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    for (const [[cat, items]] of __VLS_getVForSourceType((__VLS_ctx.groupedArray))) {
        const __VLS_12 = {}.ACollapsePanel;
        /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
            key: (cat),
            header: (__VLS_ctx.categoryLabel(cat)),
        }));
        const __VLS_14 = __VLS_13({
            key: (cat),
            header: (__VLS_ctx.categoryLabel(cat)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        __VLS_15.slots.default;
        const __VLS_16 = {}.ACollapse;
        /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            ghost: true,
            bordered: (false),
        }));
        const __VLS_18 = __VLS_17({
            ghost: true,
            bordered: (false),
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        __VLS_19.slots.default;
        for (const [doc] of __VLS_getVForSourceType((items))) {
            const __VLS_20 = {}.ACollapsePanel;
            /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
            // @ts-ignore
            const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
                key: (doc.id),
            }));
            const __VLS_22 = __VLS_21({
                key: (doc.id),
            }, ...__VLS_functionalComponentArgsRest(__VLS_21));
            __VLS_23.slots.default;
            {
                const { header: __VLS_thisSlot } = __VLS_23.slots;
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "doc-item-header" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "doc-main-info" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "doc-title" },
                });
                (doc.title || __VLS_ctx.getDocumentTypeLabel(doc.type));
                if (__VLS_ctx.getDocumentTimestamp(doc)) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "doc-timestamp" },
                    });
                    const __VLS_24 = {}.AIcon;
                    /** @type {[typeof __VLS_components.AIcon, typeof __VLS_components.aIcon, ]} */ ;
                    // @ts-ignore
                    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
                        type: "clock-circle",
                        ...{ class: "mr-1" },
                    }));
                    const __VLS_26 = __VLS_25({
                        type: "clock-circle",
                        ...{ class: "mr-1" },
                    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
                    (__VLS_ctx.formatTimestamp(__VLS_ctx.getDocumentTimestamp(doc)));
                }
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "doc-meta-info" },
                });
                const __VLS_28 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
                    color: (__VLS_ctx.getDocumentTypeColor(doc.type)),
                    ...{ class: "doc-type-tag" },
                }));
                const __VLS_30 = __VLS_29({
                    color: (__VLS_ctx.getDocumentTypeColor(doc.type)),
                    ...{ class: "doc-type-tag" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_29));
                __VLS_31.slots.default;
                (__VLS_ctx.getDocumentTypeLabel(doc.type));
                var __VLS_31;
                if (doc.confidence != null) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "doc-confidence" },
                    });
                    (Math.round(doc.confidence));
                }
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "doc-summary" },
                });
                (doc.content);
            }
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "doc-full" },
            });
            const __VLS_32 = {}.ATypographyText;
            /** @type {[typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, ]} */ ;
            // @ts-ignore
            const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
                type: "secondary",
                ...{ class: "block mb-2" },
            }));
            const __VLS_34 = __VLS_33({
                type: "secondary",
                ...{ class: "block mb-2" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_33));
            __VLS_35.slots.default;
            var __VLS_35;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
                ...{ class: "whitespace-pre-wrap leading-6" },
            });
            (__VLS_ctx.getFullContent(doc));
            var __VLS_23;
        }
        var __VLS_19;
        var __VLS_15;
    }
    var __VLS_11;
}
/** @type {__VLS_StyleScopedClasses['doc-tree']} */ ;
/** @type {__VLS_StyleScopedClasses['glass-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-item-header']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-main-info']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-title']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-timestamp']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-meta-info']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-type-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-confidence']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['doc-full']} */ ;
/** @type {__VLS_StyleScopedClasses['block']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-6']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            getDocumentTypeLabel: documentTypeUtils_1.getDocumentTypeLabel,
            getDocumentTypeColor: documentTypeUtils_1.getDocumentTypeColor,
            groupedDocs: groupedDocs,
            groupedArray: groupedArray,
            categoryLabel: categoryLabel,
            getDocumentTimestamp: getDocumentTimestamp,
            formatTimestamp: formatTimestamp,
            getFullContent: getFullContent,
        };
    },
    __typeProps: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
