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
const props = withDefaults(defineProps(), {
    activeIssue: null
});
const emit = defineEmits();
// 状态
const contentRef = (0, vue_1.ref)();
const highlightEnabled = (0, vue_1.ref)(true);
const selectedSeverity = (0, vue_1.ref)('all');
const currentHighlightIndex = (0, vue_1.ref)(0);
const isFullscreen = (0, vue_1.ref)(false);
const selectedIssue = (0, vue_1.ref)(null);
const tooltipStyle = (0, vue_1.ref)({});
// 计算属性
const visibleHighlights = (0, vue_1.computed)(() => {
    if (selectedSeverity.value === 'all') {
        return props.issues;
    }
    return props.issues.filter(issue => issue.severity === selectedSeverity.value);
});
const highlightedContent = (0, vue_1.computed)(() => {
    if (!highlightEnabled.value || !props.content) {
        return props.content.replace(/\n/g, '<br>');
    }
    let content = props.content;
    const highlights = [];
    // 模拟问题位置检测（实际应用中应该由后端提供精确位置）
    visibleHighlights.value.forEach((issue, index) => {
        const keywords = extractKeywords(issue.description, issue.location);
        keywords.forEach(keyword => {
            const regex = new RegExp(keyword, 'gi');
            let match;
            while ((match = regex.exec(content)) !== null) {
                highlights.push({
                    issue,
                    start: match.index,
                    end: match.index + match[0].length,
                    text: match[0]
                });
            }
        });
    });
    // 按位置排序，从后往前处理避免位置偏移
    highlights.sort((a, b) => b.start - a.start);
    // 应用高亮
    highlights.forEach((highlight: any,  index: any) => {
        const className = `highlight-${highlight.issue.severity}`;
        const dataAttrs = `data-issue-id="${highlight.issue.id}" data-highlight-index="${index}"`;
        const highlightHtml = `<span class="${className} highlight-text" ${dataAttrs}>${highlight.text}</span>`;
        content = content.substring(0, highlight.start) +
            highlightHtml +
            content.substring(highlight.end);
    });
    return content.replace(/\n/g, '<br>');
});
// 方法
const extractKeywords = (description, location) => {
    // 简单的关键词提取逻辑，实际应用中应该更智能
    const keywords = [];
    // 从描述中提取关键词
    const descWords = description.match(/[\u4e00-\u9fa5]{2,}/g) || [];
    keywords.push(...descWords.slice(0, 3));
    // 从位置中提取关键词
    const locationWords = location.match(/[\u4e00-\u9fa5]{2,}/g) || [];
    keywords.push(...locationWords);
    return [...new Set(keywords)].filter(word => word.length >= 2);
};
const toggleHighlight = () => {
    updateHighlights();
};
const updateHighlights = () => {
    currentHighlightIndex.value = 0;
    (0, vue_1.nextTick)(() => {
        setupHighlightEvents();
    });
};
const setupHighlightEvents = () => {
    if (!contentRef.value)
        return;
    const highlightElements = contentRef.value.querySelectorAll('.highlight-text');
    highlightElements.forEach((element, index) => {
        element.addEventListener('mouseenter',  (e: any) => {
            const issueId = e.target.getAttribute('data-issue-id');
            const issue = props.issues.find(i => i.id === issueId);
            if (issue) {
                selectedIssue.value = issue;
                updateTooltipPosition(e);
            }
        });
        element.addEventListener('mouseleave', () => {
            selectedIssue.value = null;
        });
        element.addEventListener('click',  (e) => {
            const issueId = e.target.getAttribute('data-issue-id');
            const issue = props.issues.find(i => i.id === issueId);
            if (issue) {
                emit('issue-click', issue);
            }
        });
    });
};
const updateTooltipPosition = (event) => {
    const rect = event.target.getBoundingClientRect();
    const containerRect = contentRef.value?.getBoundingClientRect();
    if (containerRect) {
        tooltipStyle.value = {
            top: `${rect.bottom - containerRect.top + 10}px`,
            left: `${rect.left - containerRect.left}px`
        };
    }
};
const previousHighlight = () => {
    if (currentHighlightIndex.value > 0) {
        currentHighlightIndex.value--;
        scrollToHighlight();
    }
};
const nextHighlight = () => {
    if (currentHighlightIndex.value < visibleHighlights.value.length - 1) {
        currentHighlightIndex.value++;
        scrollToHighlight();
    }
};
const scrollToHighlight = () => {
    if (!contentRef.value)
        return;
    const highlightElements = contentRef.value.querySelectorAll('.highlight-text');
    const targetElement = highlightElements[currentHighlightIndex.value];
    if (targetElement) {
        targetElement.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
        // 临时高亮当前项
        targetElement.classList.add('current-highlight');
        setTimeout(() => {
            targetElement.classList.remove('current-highlight');
        }, 2000);
    }
};
const toggleFullscreen = () => {
    isFullscreen.value = !isFullscreen.value;
};
const getSeverityColor = (severity) => {
    const colors = {
        critical: 'red',
        major: 'orange',
        minor: 'yellow',
        low: 'blue'
    };
    return colors[severity] || 'default';
};
const getSeverityLabel = (severity) => {
    const labels = {
        critical: '严重',
        major: '重要',
        minor: '轻微',
        low: '提示'
    };
    return labels[severity] || severity;
};
const getSeverityIconClass = (severity) => {
    const classes = {
        critical: 'bg-red-500 text-white',
        major: 'bg-orange-500 text-white',
        minor: 'bg-yellow-500 text-white',
        low: 'bg-blue-500 text-white'
    };
    return classes[severity] || 'bg-gray-500 text-white';
};
const getSeverityCount = (severity) => {
    return props.issues.filter(issue => issue.severity === severity).length;
};
// 监听 activeIssue 变化
(0, vue_1.watch)(() => props.activeIssue, (newIssue: any) => {
    if (newIssue) {
        const index = visibleHighlights.value.findIndex(issue => issue.id === newIssue.id);
        if (index !== -1) {
            currentHighlightIndex.value = index;
            (0, vue_1.nextTick)(() => {
                scrollToHighlight();
            });
        }
    }
});
// 生命周期
(0, vue_1.onMounted)(() => {
    (0, vue_1.nextTick)(() => {
        setupHighlightEvents();
    });
});
(0, vue_1.onUnmounted)(() => {
    selectedIssue.value = null;
});
// 监听内容变化
(0, vue_1.watch)(() => props.content, () => {
    (0, vue_1.nextTick)(() => {
        setupHighlightEvents();
    });
});
(0, vue_1.watch)(() => props.issues, () => {
    (0, vue_1.nextTick)(() => {
        setupHighlightEvents();
    });
}, { deep: true });
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    activeIssue: null
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['highlight-text']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['fullscreen']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "content-highlighter" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-4 p-3 rounded-lg bg-slate-700/30 border border-slate-600/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-sm font-medium text-slate-200 flex items-center gap-2" },
});
const __VLS_0 = {}.HighlightOutlined;
/** @type {[typeof __VLS_components.HighlightOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-cyan-400" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-xs text-slate-400" },
});
const __VLS_4 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onChange': {} },
    checked: (__VLS_ctx.highlightEnabled),
    size: "small",
}));
const __VLS_6 = __VLS_5({
    ...{ 'onChange': {} },
    checked: (__VLS_ctx.highlightEnabled),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onChange: (__VLS_ctx.toggleHighlight)
};
var __VLS_7;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
const __VLS_12 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedSeverity),
    size: "small",
    ...{ style: {} },
    ...{ class: "severity-filter" },
}));
const __VLS_14 = __VLS_13({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedSeverity),
    size: "small",
    ...{ style: {} },
    ...{ class: "severity-filter" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onChange: (__VLS_ctx.updateHighlights)
};
__VLS_15.slots.default;
const __VLS_20 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    value: "all",
}));
const __VLS_22 = __VLS_21({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
var __VLS_23;
const __VLS_24 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    value: "critical",
}));
const __VLS_26 = __VLS_25({
    value: "critical",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
var __VLS_27;
const __VLS_28 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    value: "major",
}));
const __VLS_30 = __VLS_29({
    value: "major",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
var __VLS_31;
const __VLS_32 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: "minor",
}));
const __VLS_34 = __VLS_33({
    value: "minor",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
var __VLS_15;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-1" },
});
const __VLS_36 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onClick': {} },
    size: "small",
    disabled: (__VLS_ctx.currentHighlightIndex <= 0),
    ...{ class: "nav-btn" },
}));
const __VLS_38 = __VLS_37({
    ...{ 'onClick': {} },
    size: "small",
    disabled: (__VLS_ctx.currentHighlightIndex <= 0),
    ...{ class: "nav-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onClick: (__VLS_ctx.previousHighlight)
};
__VLS_39.slots.default;
const __VLS_44 = {}.UpOutlined;
/** @type {[typeof __VLS_components.UpOutlined, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
var __VLS_39;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-xs text-slate-400 px-2" },
});
(__VLS_ctx.currentHighlightIndex + 1);
(__VLS_ctx.visibleHighlights.length);
const __VLS_48 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onClick': {} },
    size: "small",
    disabled: (__VLS_ctx.currentHighlightIndex >= __VLS_ctx.visibleHighlights.length - 1),
    ...{ class: "nav-btn" },
}));
const __VLS_50 = __VLS_49({
    ...{ 'onClick': {} },
    size: "small",
    disabled: (__VLS_ctx.currentHighlightIndex >= __VLS_ctx.visibleHighlights.length - 1),
    ...{ class: "nav-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onClick: (__VLS_ctx.nextHighlight)
};
__VLS_51.slots.default;
const __VLS_56 = {}.DownOutlined;
/** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
var __VLS_51;
const __VLS_60 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "nav-btn" },
}));
const __VLS_62 = __VLS_61({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "nav-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
let __VLS_64;
let __VLS_65;
let __VLS_66;
const __VLS_67 = {
    onClick: (__VLS_ctx.toggleFullscreen)
};
__VLS_63.slots.default;
if (!__VLS_ctx.isFullscreen) {
    const __VLS_68 = {}.ExpandOutlined;
    /** @type {[typeof __VLS_components.ExpandOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({}));
    const __VLS_70 = __VLS_69({}, ...__VLS_functionalComponentArgsRest(__VLS_69));
}
else {
    const __VLS_72 = {}.CompressOutlined;
    /** @type {[typeof __VLS_components.CompressOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({}));
    const __VLS_74 = __VLS_73({}, ...__VLS_functionalComponentArgsRest(__VLS_73));
}
var __VLS_63;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "relative content-container" },
    ...{ class: ({ 'fullscreen': __VLS_ctx.isFullscreen }) },
});
if (__VLS_ctx.isFullscreen) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "absolute top-4 right-4 z-10" },
    });
    const __VLS_76 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        ...{ 'onClick': {} },
        size: "large",
        ...{ class: "bg-slate-800/80 border-slate-600/50 text-slate-300" },
    }));
    const __VLS_78 = __VLS_77({
        ...{ 'onClick': {} },
        size: "large",
        ...{ class: "bg-slate-800/80 border-slate-600/50 text-slate-300" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    let __VLS_80;
    let __VLS_81;
    let __VLS_82;
    const __VLS_83 = {
        onClick: (__VLS_ctx.toggleFullscreen)
    };
    __VLS_79.slots.default;
    const __VLS_84 = {}.CompressOutlined;
    /** @type {[typeof __VLS_components.CompressOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
    const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
    var __VLS_79;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "contentRef",
    ...{ class: "content-text" },
    ...{ class: ({ 'fullscreen-content': __VLS_ctx.isFullscreen }) },
});
__VLS_asFunctionalDirective(__VLS_directives.vHtml)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.highlightedContent) }, null, null);
/** @type {typeof __VLS_ctx.contentRef} */ ;
if (__VLS_ctx.selectedIssue) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "absolute z-20 p-4 rounded-lg bg-slate-800 border border-slate-600 shadow-xl max-w-sm" },
        ...{ style: (__VLS_ctx.tooltipStyle) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-start gap-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0" },
        ...{ class: (__VLS_ctx.getSeverityIconClass(__VLS_ctx.selectedIssue.severity)) },
    });
    const __VLS_88 = {}.ExclamationOutlined;
    /** @type {[typeof __VLS_components.ExclamationOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        ...{ class: "text-xs" },
    }));
    const __VLS_90 = __VLS_89({
        ...{ class: "text-xs" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1 min-w-0" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-2 mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
        ...{ class: "font-medium text-slate-100 text-sm" },
    });
    (__VLS_ctx.selectedIssue.rule_name);
    const __VLS_92 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        color: (__VLS_ctx.getSeverityColor(__VLS_ctx.selectedIssue.severity)),
        size: "small",
    }));
    const __VLS_94 = __VLS_93({
        color: (__VLS_ctx.getSeverityColor(__VLS_ctx.selectedIssue.severity)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    __VLS_95.slots.default;
    (__VLS_ctx.getSeverityLabel(__VLS_ctx.selectedIssue.severity));
    var __VLS_95;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-xs text-slate-300 mb-2" },
    });
    (__VLS_ctx.selectedIssue.description);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-slate-400 mb-2" },
    });
    (__VLS_ctx.selectedIssue.location);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "p-2 rounded bg-blue-500/10 border border-blue-500/20" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-blue-200 font-medium mb-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-blue-300" },
    });
    (__VLS_ctx.selectedIssue.suggestion);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "absolute -bottom-2 left-6 w-4 h-4 bg-slate-800 border-r border-b border-slate-600 transform rotate-45" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-4 flex items-center justify-between p-3 rounded-lg bg-slate-700/20 border border-slate-600/20" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-4 text-xs" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-3 h-3 rounded-full bg-red-500" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-400" },
});
(__VLS_ctx.getSeverityCount('critical'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-3 h-3 rounded-full bg-orange-500" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-400" },
});
(__VLS_ctx.getSeverityCount('major'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-3 h-3 rounded-full bg-yellow-500" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-400" },
});
(__VLS_ctx.getSeverityCount('minor'));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
(__VLS_ctx.issues.length);
/** @type {__VLS_StyleScopedClasses['content-highlighter']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['severity-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['px-2']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['nav-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['relative']} */ ;
/** @type {__VLS_StyleScopedClasses['content-container']} */ ;
/** @type {__VLS_StyleScopedClasses['fullscreen']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['top-4']} */ ;
/** @type {__VLS_StyleScopedClasses['right-4']} */ ;
/** @type {__VLS_StyleScopedClasses['z-10']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/80']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['fullscreen-content']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['z-20']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['absolute']} */ ;
/** @type {__VLS_StyleScopedClasses['-bottom-2']} */ ;
/** @type {__VLS_StyleScopedClasses['left-6']} */ ;
/** @type {__VLS_StyleScopedClasses['w-4']} */ ;
/** @type {__VLS_StyleScopedClasses['h-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800']} */ ;
/** @type {__VLS_StyleScopedClasses['border-r']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600']} */ ;
/** @type {__VLS_StyleScopedClasses['transform']} */ ;
/** @type {__VLS_StyleScopedClasses['rotate-45']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/20']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-orange-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-yellow-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            HighlightOutlined: icons_vue_1.HighlightOutlined,
            UpOutlined: icons_vue_1.UpOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            ExpandOutlined: icons_vue_1.ExpandOutlined,
            CompressOutlined: icons_vue_1.CompressOutlined,
            ExclamationOutlined: icons_vue_1.ExclamationOutlined,
            contentRef: contentRef,
            highlightEnabled: highlightEnabled,
            selectedSeverity: selectedSeverity,
            currentHighlightIndex: currentHighlightIndex,
            isFullscreen: isFullscreen,
            selectedIssue: selectedIssue,
            tooltipStyle: tooltipStyle,
            visibleHighlights: visibleHighlights,
            highlightedContent: highlightedContent,
            toggleHighlight: toggleHighlight,
            updateHighlights: updateHighlights,
            previousHighlight: previousHighlight,
            nextHighlight: nextHighlight,
            toggleFullscreen: toggleFullscreen,
            getSeverityColor: getSeverityColor,
            getSeverityLabel: getSeverityLabel,
            getSeverityIconClass: getSeverityIconClass,
            getSeverityCount: getSeverityCount,
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
