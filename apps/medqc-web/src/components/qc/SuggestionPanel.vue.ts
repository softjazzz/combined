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
const props = defineProps();
const emit = defineEmits();
// 状态
const selectedCategory = (0, vue_1.ref)('all');
const selectedPriority = (0, vue_1.ref)('all');
const sortBy = (0, vue_1.ref)('priority');
const expandedSuggestions = (0, vue_1.ref)(: any[]);
// 计算属性
const categories = (0, vue_1.computed)(() => {
    const cats = [...new Set(props.suggestions.map(s => s.category))];
    return cats.sort();
});
const highPrioritySuggestions = (0, vue_1.computed)(() => props.suggestions.filter(s => s.priority === 'high'));
const mediumPrioritySuggestions = (0, vue_1.computed)(() => props.suggestions.filter(s => s.priority === 'medium'));
const lowPrioritySuggestions = (0, vue_1.computed)(() => props.suggestions.filter(s => s.priority === 'low'));
const filteredSuggestions = (0, vue_1.computed)(() => {
    let filtered = props.suggestions;
    // 按类别筛选
    if (selectedCategory.value !== 'all') {
        filtered = filtered.filter(s => s.category === selectedCategory.value);
    }
    // 按优先级筛选
    if (selectedPriority.value !== 'all') {
        filtered = filtered.filter(s => s.priority === selectedPriority.value);
    }
    // 排序
    filtered.sort((a, b) => {
        switch (sortBy.value) {
            case 'priority':
                const priorityOrder = { high: 3, medium: 2, low: 1 };
                return priorityOrder[b.priority] - priorityOrder[a.priority];
            case 'category':
                return a.category.localeCompare(b.category);
            case 'title':
                return a.title.localeCompare(b.title);
            default:
                return 0;
        }
    });
    return filtered;
});
// 方法
const filterSuggestions = () => {
    // 筛选逻辑已在 computed 中处理
};
const sortSuggestions = () => {
    // 排序逻辑已在 computed 中处理
};
const toggleSuggestionExpand = (suggestionId) => {
    const index = expandedSuggestions.value.indexOf(suggestionId);
    if (index > -1) {
        expandedSuggestions.value.splice(index, 1);
    }
    else {
        expandedSuggestions.value.push(suggestionId);
    }
};
const expandAll = () => {
    expandedSuggestions.value = filteredSuggestions.value.map(s => s.id);
};
const collapseAll = () => {
    expandedSuggestions.value = [];
};
const getPriorityColor = (priority) => {
    const colors = {
        high: 'red',
        medium: 'orange',
        low: 'blue'
    };
    return colors[priority] || 'default';
};
const getPriorityLabel = (priority) => {
    const labels = {
        high: '高优先级',
        medium: '中优先级',
        low: '低优先级'
    };
    return labels[priority] || priority;
};
const getPriorityIcon = (priority) => {
    const icons = {
        high: icons_vue_1.ExclamationOutlined,
        medium: icons_vue_1.StarOutlined,
        low: icons_vue_1.FlagOutlined
    };
    return icons[priority] || icons_vue_1.FlagOutlined;
};
const getPriorityIconClass = (priority) => {
    const classes = {
        high: 'bg-red-500/20 text-red-400 border border-red-500/30',
        medium: 'bg-orange-500/20 text-orange-400 border border-orange-500/30',
        low: 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
    };
    return classes[priority] || 'bg-gray-500/20 text-gray-400';
};
const getSuggestionCardClass = (priority) => {
    const classes = {
        high: 'border-red-500/30 bg-red-500/5 hover:border-red-500/50 hover:bg-red-500/10',
        medium: 'border-orange-500/30 bg-orange-500/5 hover:border-orange-500/50 hover:bg-orange-500/10',
        low: 'border-blue-500/30 bg-blue-500/5 hover:border-blue-500/50 hover:bg-blue-500/10'
    };
    return classes[priority] || 'border-slate-600/30 bg-slate-700/5';
};
const getImplementationSteps = (suggestion) => {
    // 模拟实施步骤，实际应用中应该从后端获取
    const steps = [
        '仔细审查当前病案记录中的相关部分',
        '参考医疗标准和最佳实践指南',
        '与相关科室医生讨论具体改进方案',
        '更新病案记录并记录改进过程',
        '定期回顾改进效果并持续优化'
    ];
    return steps.slice(0, Math.floor(Math.random() * 3) + 3);
};
const getRelatedResources = (suggestion) => {
    // 模拟相关资源，实际应用中应该从后端获取
    return [
        { title: '医疗质量管理规范', url: '#' },
        { title: '病案书写基本规范', url: '#' },
        { title: '临床诊疗指南', url: '#' }
    ];
};
const getExpectedImprovement = (suggestion) => {
    const improvements = [
        '提高病案记录的完整性和准确性，预计质控评分提升5-10分',
        '减少医疗风险，提升患者安全保障水平',
        '优化诊疗流程，提高医疗服务质量和效率',
        '符合医疗质量标准要求，通过相关审核检查'
    ];
    return improvements[Math.floor(Math.random() * improvements.length)];
};
const markAsImplemented = (suggestion) => {
    ant_design_vue_1.message.success(`建议"${suggestion.title}"已标记为已实施`);
    emit('suggestion-implemented', suggestion.id);
};
const saveSuggestion = (suggestion) => {
    ant_design_vue_1.message.success(`建议"${suggestion.title}"已保存`);
    emit('suggestion-saved', suggestion.id);
};
const shareSuggestion = (suggestion) => {
    // 模拟分享功能
    if (navigator.share) {
        navigator.share({
            title: suggestion.title,
            text: suggestion.description,
            url: window.location.href
        });
    }
    else {
        // 复制到剪贴板
        navigator.clipboard.writeText(`${suggestion.title}\n${suggestion.description}`);
        ant_design_vue_1.message.success('建议内容已复制到剪贴板');
    }
};
const exportSuggestions = () => {
    ant_design_vue_1.message.info('导出功能开发中...');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['suggestion-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['suggestion-card']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "suggestion-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2 mb-2" },
});
const __VLS_0 = {}.BulbOutlined;
/** @type {[typeof __VLS_components.BulbOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-yellow-400" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-yellow-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-sm text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xl font-bold text-red-400" },
});
(__VLS_ctx.highPrioritySuggestions.length);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xl font-bold text-amber-400" },
});
(__VLS_ctx.mediumPrioritySuggestions.length);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xl font-bold text-blue-400" },
});
(__VLS_ctx.lowPrioritySuggestions.length);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between p-4 rounded-lg bg-slate-700/30 border border-slate-600/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm text-slate-300" },
});
const __VLS_4 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedCategory),
    size: "small",
    ...{ style: {} },
    ...{ class: "category-filter" },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedCategory),
    size: "small",
    ...{ style: {} },
    ...{ class: "category-filter" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onChange: (__VLS_ctx.filterSuggestions)
};
__VLS_7.slots.default;
const __VLS_12 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    value: "all",
}));
const __VLS_14 = __VLS_13({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
for (const [category] of __VLS_getVForSourceType((__VLS_ctx.categories))) {
    const __VLS_16 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        key: (category),
        value: (category),
    }));
    const __VLS_18 = __VLS_17({
        key: (category),
        value: (category),
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    (category);
    var __VLS_19;
}
var __VLS_7;
const __VLS_20 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedPriority),
    size: "small",
    ...{ style: {} },
    ...{ class: "priority-filter" },
}));
const __VLS_22 = __VLS_21({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedPriority),
    size: "small",
    ...{ style: {} },
    ...{ class: "priority-filter" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onChange: (__VLS_ctx.filterSuggestions)
};
__VLS_23.slots.default;
const __VLS_28 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    value: "all",
}));
const __VLS_30 = __VLS_29({
    value: "all",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
var __VLS_31;
const __VLS_32 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: "high",
}));
const __VLS_34 = __VLS_33({
    value: "high",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
const __VLS_36 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: "medium",
}));
const __VLS_38 = __VLS_37({
    value: "medium",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
var __VLS_39;
const __VLS_40 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    value: "low",
}));
const __VLS_42 = __VLS_41({
    value: "low",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
var __VLS_43;
var __VLS_23;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm text-slate-300" },
});
const __VLS_44 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.sortBy),
    size: "small",
    ...{ style: {} },
    ...{ class: "sort-filter" },
}));
const __VLS_46 = __VLS_45({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.sortBy),
    size: "small",
    ...{ style: {} },
    ...{ class: "sort-filter" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_48;
let __VLS_49;
let __VLS_50;
const __VLS_51 = {
    onChange: (__VLS_ctx.sortSuggestions)
};
__VLS_47.slots.default;
const __VLS_52 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    value: "priority",
}));
const __VLS_54 = __VLS_53({
    value: "priority",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
var __VLS_55;
const __VLS_56 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    value: "category",
}));
const __VLS_58 = __VLS_57({
    value: "category",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
var __VLS_59;
const __VLS_60 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    value: "title",
}));
const __VLS_62 = __VLS_61({
    value: "title",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
var __VLS_63;
var __VLS_47;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
for (const [suggestion, index] of __VLS_getVForSourceType((__VLS_ctx.filteredSuggestions))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.toggleSuggestionExpand(suggestion.id);
            } },
        key: (suggestion.id),
        ...{ class: "suggestion-card p-5 rounded-xl border transition-all duration-300 hover:shadow-lg cursor-pointer" },
        ...{ class: (__VLS_ctx.getSuggestionCardClass(suggestion.priority)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-start gap-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" },
        ...{ class: (__VLS_ctx.getPriorityIconClass(suggestion.priority)) },
    });
    const __VLS_64 = ((__VLS_ctx.getPriorityIcon(suggestion.priority)));
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        ...{ class: "text-sm" },
    }));
    const __VLS_66 = __VLS_65({
        ...{ class: "text-sm" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex-1 min-w-0" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between mb-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "font-semibold text-slate-100 text-base" },
    });
    (suggestion.title);
    const __VLS_68 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        color: (__VLS_ctx.getPriorityColor(suggestion.priority)),
        size: "small",
        ...{ class: "priority-tag" },
    }));
    const __VLS_70 = __VLS_69({
        color: (__VLS_ctx.getPriorityColor(suggestion.priority)),
        size: "small",
        ...{ class: "priority-tag" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_71.slots.default;
    (__VLS_ctx.getPriorityLabel(suggestion.priority));
    var __VLS_71;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-2" },
    });
    const __VLS_72 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        color: "blue",
        size: "small",
        ...{ class: "category-tag" },
    }));
    const __VLS_74 = __VLS_73({
        color: "blue",
        size: "small",
        ...{ class: "category-tag" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    __VLS_75.slots.default;
    (suggestion.category);
    var __VLS_75;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-6 h-6 rounded-full bg-slate-600/50 flex items-center justify-center cursor-pointer hover:bg-slate-600/70 transition-colors" },
        ...{ class: ({ 'rotate-180': __VLS_ctx.expandedSuggestions.includes(suggestion.id) }) },
    });
    const __VLS_76 = {}.DownOutlined;
    /** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        ...{ class: "text-xs text-slate-400" },
    }));
    const __VLS_78 = __VLS_77({
        ...{ class: "text-xs text-slate-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-slate-300 mb-4 leading-relaxed" },
    });
    (suggestion.description);
    if (__VLS_ctx.expandedSuggestions.includes(suggestion.id)) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "expanded-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mb-4 p-4 rounded-lg bg-slate-700/30 border border-slate-600/30" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
            ...{ class: "text-sm font-medium text-slate-200 mb-2 flex items-center gap-2" },
        });
        const __VLS_80 = {}.CheckCircleOutlined;
        /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
            ...{ class: "text-emerald-400" },
        }));
        const __VLS_82 = __VLS_81({
            ...{ class: "text-emerald-400" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_81));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-sm text-slate-300 space-y-2" },
        });
        for (const [step, stepIndex] of __VLS_getVForSourceType((__VLS_ctx.getImplementationSteps(suggestion)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (stepIndex),
                ...{ class: "flex items-start gap-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "w-5 h-5 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0 mt-0.5" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-xs text-cyan-400 font-medium" },
            });
            (stepIndex + 1);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (step);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mb-4 p-4 rounded-lg bg-blue-500/10 border border-blue-500/20" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
            ...{ class: "text-sm font-medium text-blue-200 mb-2 flex items-center gap-2" },
        });
        const __VLS_84 = {}.BookOutlined;
        /** @type {[typeof __VLS_components.BookOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
            ...{ class: "text-blue-400" },
        }));
        const __VLS_86 = __VLS_85({
            ...{ class: "text-blue-400" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_85));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "space-y-2" },
        });
        for (const [resource] of __VLS_getVForSourceType((__VLS_ctx.getRelatedResources(suggestion)))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (resource.title),
                ...{ class: "flex items-center gap-2" },
            });
            const __VLS_88 = {}.LinkOutlined;
            /** @type {[typeof __VLS_components.LinkOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
                ...{ class: "text-blue-400 text-xs" },
            }));
            const __VLS_90 = __VLS_89({
                ...{ class: "text-blue-400 text-xs" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_89));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
                href: "#",
                ...{ class: "text-sm text-blue-300 hover:text-blue-200 transition-colors" },
            });
            (resource.title);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/20" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
            ...{ class: "text-sm font-medium text-emerald-200 mb-2 flex items-center gap-2" },
        });
        const __VLS_92 = {}.TrophyOutlined;
        /** @type {[typeof __VLS_components.TrophyOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            ...{ class: "text-emerald-400" },
        }));
        const __VLS_94 = __VLS_93({
            ...{ class: "text-emerald-400" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-sm text-emerald-300" },
        });
        (__VLS_ctx.getExpectedImprovement(suggestion));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center justify-end gap-3 mt-4 pt-4 border-t border-slate-600/30" },
        });
        const __VLS_96 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
            ...{ 'onClick': {} },
            size: "small",
            ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30" },
        }));
        const __VLS_98 = __VLS_97({
            ...{ 'onClick': {} },
            size: "small",
            ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
        let __VLS_100;
        let __VLS_101;
        let __VLS_102;
        const __VLS_103 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.expandedSuggestions.includes(suggestion.id)))
                    return;
                __VLS_ctx.markAsImplemented(suggestion);
            }
        };
        __VLS_99.slots.default;
        const __VLS_104 = {}.CheckOutlined;
        /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({}));
        const __VLS_106 = __VLS_105({}, ...__VLS_functionalComponentArgsRest(__VLS_105));
        var __VLS_99;
        const __VLS_108 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
            ...{ 'onClick': {} },
            size: "small",
            ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30" },
        }));
        const __VLS_110 = __VLS_109({
            ...{ 'onClick': {} },
            size: "small",
            ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_109));
        let __VLS_112;
        let __VLS_113;
        let __VLS_114;
        const __VLS_115 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.expandedSuggestions.includes(suggestion.id)))
                    return;
                __VLS_ctx.saveSuggestion(suggestion);
            }
        };
        __VLS_111.slots.default;
        const __VLS_116 = {}.BookmarkOutlined;
        /** @type {[typeof __VLS_components.BookmarkOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
        const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
        var __VLS_111;
        const __VLS_120 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            ...{ 'onClick': {} },
            size: "small",
            ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30" },
        }));
        const __VLS_122 = __VLS_121({
            ...{ 'onClick': {} },
            size: "small",
            ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        let __VLS_124;
        let __VLS_125;
        let __VLS_126;
        const __VLS_127 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.expandedSuggestions.includes(suggestion.id)))
                    return;
                __VLS_ctx.shareSuggestion(suggestion);
            }
        };
        __VLS_123.slots.default;
        const __VLS_128 = {}.ShareAltOutlined;
        /** @type {[typeof __VLS_components.ShareAltOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({}));
        const __VLS_130 = __VLS_129({}, ...__VLS_functionalComponentArgsRest(__VLS_129));
        var __VLS_123;
    }
}
if (__VLS_ctx.filteredSuggestions.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-12" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-20 h-20 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-4" },
    });
    const __VLS_132 = {}.BulbOutlined;
    /** @type {[typeof __VLS_components.BulbOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        ...{ class: "text-slate-400 text-3xl" },
    }));
    const __VLS_134 = __VLS_133({
        ...{ class: "text-slate-400 text-3xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-slate-400 mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-slate-500" },
    });
}
if (__VLS_ctx.suggestions.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center gap-3 pt-6 border-t border-slate-700/50" },
    });
    const __VLS_136 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        ...{ 'onClick': {} },
        ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50" },
    }));
    const __VLS_138 = __VLS_137({
        ...{ 'onClick': {} },
        ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    let __VLS_140;
    let __VLS_141;
    let __VLS_142;
    const __VLS_143 = {
        onClick: (__VLS_ctx.expandAll)
    };
    __VLS_139.slots.default;
    const __VLS_144 = {}.ExpandOutlined;
    /** @type {[typeof __VLS_components.ExpandOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({}));
    const __VLS_146 = __VLS_145({}, ...__VLS_functionalComponentArgsRest(__VLS_145));
    var __VLS_139;
    const __VLS_148 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        ...{ 'onClick': {} },
        ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50" },
    }));
    const __VLS_150 = __VLS_149({
        ...{ 'onClick': {} },
        ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300 hover:bg-slate-600/50" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    let __VLS_152;
    let __VLS_153;
    let __VLS_154;
    const __VLS_155 = {
        onClick: (__VLS_ctx.collapseAll)
    };
    __VLS_151.slots.default;
    const __VLS_156 = {}.CompressOutlined;
    /** @type {[typeof __VLS_components.CompressOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({}));
    const __VLS_158 = __VLS_157({}, ...__VLS_functionalComponentArgsRest(__VLS_157));
    var __VLS_151;
    const __VLS_160 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        ...{ 'onClick': {} },
        ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30" },
    }));
    const __VLS_162 = __VLS_161({
        ...{ 'onClick': {} },
        ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    let __VLS_164;
    let __VLS_165;
    let __VLS_166;
    const __VLS_167 = {
        onClick: (__VLS_ctx.exportSuggestions)
    };
    __VLS_163.slots.default;
    const __VLS_168 = {}.ExportOutlined;
    /** @type {[typeof __VLS_components.ExportOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({}));
    const __VLS_170 = __VLS_169({}, ...__VLS_functionalComponentArgsRest(__VLS_169));
    var __VLS_163;
}
/** @type {__VLS_StyleScopedClasses['suggestion-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-yellow-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['category-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['priority-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['sort-filter']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['suggestion-card']} */ ;
/** @type {__VLS_StyleScopedClasses['p-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['w-10']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-0']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['priority-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['category-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['w-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-slate-600/70']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['rotate-180']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-relaxed']} */ ;
/** @type {__VLS_StyleScopedClasses['expanded-content']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-start']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-5']} */ ;
/** @type {__VLS_StyleScopedClasses['h-5']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-cyan-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-shrink-0']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:text-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-colors']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-emerald-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-blue-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-purple-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-purple-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-12']} */ ;
/** @type {__VLS_StyleScopedClasses['w-20']} */ ;
/** @type {__VLS_StyleScopedClasses['h-20']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-blue-500/30']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            BulbOutlined: icons_vue_1.BulbOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            BookOutlined: icons_vue_1.BookOutlined,
            LinkOutlined: icons_vue_1.LinkOutlined,
            TrophyOutlined: icons_vue_1.TrophyOutlined,
            CheckOutlined: icons_vue_1.CheckOutlined,
            BookmarkOutlined: icons_vue_1.BookmarkOutlined,
            ShareAltOutlined: icons_vue_1.ShareAltOutlined,
            ExpandOutlined: icons_vue_1.ExpandOutlined,
            CompressOutlined: icons_vue_1.CompressOutlined,
            ExportOutlined: icons_vue_1.ExportOutlined,
            selectedCategory: selectedCategory,
            selectedPriority: selectedPriority,
            sortBy: sortBy,
            expandedSuggestions: expandedSuggestions,
            categories: categories,
            highPrioritySuggestions: highPrioritySuggestions,
            mediumPrioritySuggestions: mediumPrioritySuggestions,
            lowPrioritySuggestions: lowPrioritySuggestions,
            filteredSuggestions: filteredSuggestions,
            filterSuggestions: filterSuggestions,
            sortSuggestions: sortSuggestions,
            toggleSuggestionExpand: toggleSuggestionExpand,
            expandAll: expandAll,
            collapseAll: collapseAll,
            getPriorityColor: getPriorityColor,
            getPriorityLabel: getPriorityLabel,
            getPriorityIcon: getPriorityIcon,
            getPriorityIconClass: getPriorityIconClass,
            getSuggestionCardClass: getSuggestionCardClass,
            getImplementationSteps: getImplementationSteps,
            getRelatedResources: getRelatedResources,
            getExpectedImprovement: getExpectedImprovement,
            markAsImplemented: markAsImplemented,
            saveSuggestion: saveSuggestion,
            shareSuggestion: shareSuggestion,
            exportSuggestions: exportSuggestions,
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
