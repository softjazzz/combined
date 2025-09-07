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
import ant_design_vue_1 from 'ant-design-vue';
const props = withDefaults(defineProps(), {
    totalItems: 0,
    isMobile: false,
    maxConcurrency: 5
});
const emit = defineEmits();
// 响应式数据
const loadingActions = (0, vue_1.ref)(: any[]);
const showProgress = (0, vue_1.ref)(false);
const progressPercent = (0, vue_1.ref)(0);
const progressStatus = (0, vue_1.ref)('normal');
const progressText = (0, vue_1.ref)('');
const progressDetails = (0, vue_1.ref)(null);
const showResultModal = (0, vue_1.ref)(false);
const resultSummary = (0, vue_1.ref)({
    status: 'success',
    title: '',
    subtitle: '',
    success: 0,
    failed: 0
});
const resultDetails = (0, vue_1.ref)(: any[]);
// 计算属性
const isAllSelected = (0, vue_1.computed)(() => props.totalItems > 0 && props.selectedItems.length === props.totalItems);
const isIndeterminate = (0, vue_1.computed)(() => props.selectedItems.length > 0 && props.selectedItems.length < props.totalItems);
const availableActions = (0, vue_1.computed)(() => props.actions.filter(action => {
    if (action.minSelection && props.selectedItems.length < action.minSelection) {
        return false;
    }
    if (action.maxSelection && props.selectedItems.length > action.maxSelection) {
        return false;
    }
    return true;
}));
// 方法
const handleSelectAll = (e) => {
    emit('select-all', e.target.checked);
};
const clearSelection = () => {
    emit('update: selectedItems', : any[]);
};
const canExecuteAction = (action) => {
    if (loadingActions.value.includes(action.key)) {
        return false;
    }
    if (action.validator) {
        const result = action.validator(props.selectedItems);
        return result === true;
    }
    return true;
};
const handleAction = async (action) => {
    // 验证
    if (action.validator) {
        const result = action.validator(props.selectedItems);
        if (result !== true) {
            ant_design_vue_1.message.error(typeof result === 'string' ? result : '操作条件不满足');
            return;
        }
    }
    // 确认对话框
    if (action.requireConfirm) {
        const confirmed = await showConfirm(action);
        if (!confirmed)
            return;
    }
    // 开始执行
    loadingActions.value.push(action.key);
    showProgress.value = true;
    progressPercent.value = 0;
    progressStatus.value = 'active';
    progressText.value = '正在处理...';
    progressDetails.value = { success: 0, failed: 0, total: props.selectedItems.length };
    resultDetails.value = [];
    try {
        // 触发执行事件
        emit('execute-action', action, props.selectedItems);
        // 这里可以添加实际的批量处理逻辑
        await executeBatchOperation(action, props.selectedItems);
    }
    catch (error) {
        console.error('批量操作失败:', error);
        ant_design_vue_1.message.error('批量操作失败');
    }
    finally {
        loadingActions.value = loadingActions.value.filter(key => key !== action.key);
        showProgress.value = false;
    }
};
const executeBatchOperation = async (action, items) => {
    const results = [];
    let successCount = 0;
    let failedCount = 0;
    // 分批处理，避免并发过多
    const batches = [];
    for (let i = 0; i < items.length; i += props.maxConcurrency) {
        batches.push(items.slice(i, i + props.maxConcurrency));
    }
    for (const batch of batches) {
        const batchPromises = batch.map(async (item, index) => {
            try {
                // 这里应该调用实际的处理函数
                await new Promise(resolve => setTimeout(resolve, 1000)); // 模拟处理时间
                successCount++;
                results.push({
                    title: `项目 ${item.id || index + 1}`,
                });
            }
            catch (error) {
                failedCount++;
                results.push({
                    title: `项目 ${item.id || index + 1}`,
                    error: error instanceof Error ? error.message : '处理失败'
                });
            }
            // 更新进度
            const completed = successCount + failedCount;
            progressPercent.value = Math.round((completed / items.length) * 100);
            progressDetails.value = {
                success: successCount,
                failed: failedCount,
                total: items.length
            };
        });
        await Promise.all(batchPromises);
    }
    // 显示结果
    showResults(successCount, failedCount, results);
};
const showResults = (successCount, failedCount: any,  details: any) => {
    resultDetails.value = details;
    if (failedCount === 0) {
        resultSummary.value = {
            status: 'success',
            title: '批量操作完成',
            subtitle: `成功处理 ${successCount} 项`,
            success: successCount,
            failed: failedCount
        };
        progressStatus.value = 'success';
        progressText.value = '处理完成';
    }
    else if (successCount === 0) {
        resultSummary.value = {
            status: 'error',
            title: '批量操作失败',
            subtitle: `${failedCount} 项处理失败`,
            success: successCount,
            failed: failedCount
        };
        progressStatus.value = 'exception';
        progressText.value = '处理失败';
    }
    else {
        resultSummary.value = {
            status: 'warning',
            title: '批量操作部分成功',
            subtitle: `成功 ${successCount} 项，失败 ${failedCount} 项`,
            success: successCount,
            failed: failedCount
        };
        progressStatus.value = 'success';
        progressText.value = '处理完成';
    }
    showResultModal.value = true;
    // 清空选择
    setTimeout(() => {
        clearSelection();
    }, 1000);
};
const showConfirm = (action) => {
    return new Promise((resolve) => {
        // 这里应该显示确认对话框
        // 简化实现，直接返回 true
        resolve(true);
    });
};
const downloadErrorReport = () => {
    const errorItems = resultDetails.value.filter(item => item.error);
    const csvContent = 'data:text/csv;charset=utf-8,' +
        '项目,错误信息\n' +
        errorItems.map(item => `"${item.title}","${item.error}"`).join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `批量操作错误报告_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};
// 监听选择变化
(0, vue_1.watch)(() => props.selectedItems.length, (newLength) => {
    if (newLength === 0) {
        showProgress.value = false;
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    totalItems: 0,
    isMobile: false,
    maxConcurrency: 5
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-info']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-close']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-stats']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-operations" },
});
if (__VLS_ctx.selectedItems.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-toolbar" },
        ...{ class: ({ 'batch-toolbar-mobile': __VLS_ctx.isMobile }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-info" },
    });
    const __VLS_0 = {}.ACheckbox;
    /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
    // @ts-ignore
    const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
        ...{ 'onChange': {} },
        checked: (__VLS_ctx.isAllSelected),
        indeterminate: (__VLS_ctx.isIndeterminate),
    }));
    const __VLS_2 = __VLS_1({
        ...{ 'onChange': {} },
        checked: (__VLS_ctx.isAllSelected),
        indeterminate: (__VLS_ctx.isIndeterminate),
    }, ...__VLS_functionalComponentArgsRest(__VLS_1));
    let __VLS_4;
    let __VLS_5;
    let __VLS_6;
    const __VLS_7 = {
        onChange: (__VLS_ctx.handleSelectAll)
    };
    __VLS_3.slots.default;
    (__VLS_ctx.selectedItems.length);
    var __VLS_3;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-actions" },
    });
    const __VLS_8 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        size: (__VLS_ctx.isMobile ? 'small' : 'middle'),
    }));
    const __VLS_10 = __VLS_9({
        size: (__VLS_ctx.isMobile ? 'small' : 'middle'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    for (const [action] of __VLS_getVForSourceType((__VLS_ctx.availableActions))) {
        const __VLS_12 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
            ...{ 'onClick': {} },
            key: (action.key),
            type: (action.type || 'default'),
            danger: (action.danger),
            loading: (__VLS_ctx.loadingActions.includes(action.key)),
            disabled: (!__VLS_ctx.canExecuteAction(action)),
            size: (__VLS_ctx.isMobile ? 'small' : 'middle'),
        }));
        const __VLS_14 = __VLS_13({
            ...{ 'onClick': {} },
            key: (action.key),
            type: (action.type || 'default'),
            danger: (action.danger),
            loading: (__VLS_ctx.loadingActions.includes(action.key)),
            disabled: (!__VLS_ctx.canExecuteAction(action)),
            size: (__VLS_ctx.isMobile ? 'small' : 'middle'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        let __VLS_16;
        let __VLS_17;
        let __VLS_18;
        const __VLS_19 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.selectedItems.length > 0))
                    return;
                __VLS_ctx.handleAction(action);
            }
        };
        __VLS_15.slots.default;
        if (action.icon) {
            {
                const { icon: __VLS_thisSlot } = __VLS_15.slots;
                const __VLS_20 = ((action.icon));
                // @ts-ignore
                const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
                const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
            }
        }
        (__VLS_ctx.isMobile ? action.shortLabel || action.label : action.label);
        var __VLS_15;
    }
    var __VLS_11;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-close" },
    });
    const __VLS_24 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        ...{ 'onClick': {} },
        type: "text",
        size: "small",
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onClick': {} },
        type: "text",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_28;
    let __VLS_29;
    let __VLS_30;
    const __VLS_31 = {
        onClick: (__VLS_ctx.clearSelection)
    };
    __VLS_27.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_27.slots;
        const __VLS_32 = {}.CloseOutlined;
        /** @type {[typeof __VLS_components.CloseOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
        const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
    }
    var __VLS_27;
}
if (__VLS_ctx.showProgress) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-progress" },
    });
    const __VLS_36 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        percent: (__VLS_ctx.progressPercent),
        status: (__VLS_ctx.progressStatus),
        size: (__VLS_ctx.isMobile ? 'small' : 'default'),
    }));
    const __VLS_38 = __VLS_37({
        percent: (__VLS_ctx.progressPercent),
        status: (__VLS_ctx.progressStatus),
        size: (__VLS_ctx.isMobile ? 'small' : 'default'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    {
        const { format: __VLS_thisSlot } = __VLS_39.slots;
        const [percent] = __VLS_getSlotParams(__VLS_thisSlot);
        (__VLS_ctx.progressText || `${percent}%`);
    }
    var __VLS_39;
    if (__VLS_ctx.progressDetails) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "progress-details" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "progress-stats" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-value success" },
        });
        (__VLS_ctx.progressDetails.success);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-value error" },
        });
        (__VLS_ctx.progressDetails.failed);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "stat-value" },
        });
        (__VLS_ctx.progressDetails.total);
    }
}
const __VLS_40 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    open: (__VLS_ctx.showResultModal),
    title: "批量操作结果",
    width: (__VLS_ctx.isMobile ? '90%' : 600),
    footer: (null),
}));
const __VLS_42 = __VLS_41({
    open: (__VLS_ctx.showResultModal),
    title: "批量操作结果",
    width: (__VLS_ctx.isMobile ? '90%' : 600),
    footer: (null),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-result" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "result-summary" },
});
const __VLS_44 = {}.AResult;
/** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    status: (__VLS_ctx.resultSummary.status),
    title: (__VLS_ctx.resultSummary.title),
    subTitle: (__VLS_ctx.resultSummary.subtitle),
}));
const __VLS_46 = __VLS_45({
    status: (__VLS_ctx.resultSummary.status),
    title: (__VLS_ctx.resultSummary.title),
    subTitle: (__VLS_ctx.resultSummary.subtitle),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_47.slots;
    const __VLS_48 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
    const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_51.slots.default;
    const __VLS_52 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_54 = __VLS_53({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    let __VLS_56;
    let __VLS_57;
    let __VLS_58;
    const __VLS_59 = {
        onClick: (...[$event]) => {
            __VLS_ctx.showResultModal = false;
        }
    };
    __VLS_55.slots.default;
    var __VLS_55;
    if (__VLS_ctx.resultSummary.failed > 0) {
        const __VLS_60 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
            ...{ 'onClick': {} },
        }));
        const __VLS_62 = __VLS_61({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_61));
        let __VLS_64;
        let __VLS_65;
        let __VLS_66;
        const __VLS_67 = {
            onClick: (__VLS_ctx.downloadErrorReport)
        };
        __VLS_63.slots.default;
        var __VLS_63;
    }
    var __VLS_51;
}
var __VLS_47;
if (__VLS_ctx.resultDetails.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-details" },
    });
    const __VLS_68 = {}.ACollapse;
    /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({}));
    const __VLS_70 = __VLS_69({}, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_71.slots.default;
    const __VLS_72 = {}.ACollapsePanel;
    /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        key: "details",
        header: "详细结果",
    }));
    const __VLS_74 = __VLS_73({
        key: "details",
        header: "详细结果",
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    __VLS_75.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-list" },
    });
    for (const [result, index] of __VLS_getVForSourceType((__VLS_ctx.resultDetails))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (index),
            ...{ class: "result-item" },
            ...{ class: ({ 'result-error': result.error }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-item-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-item-title" },
        });
        (result.title);
        if (result.error) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "result-item-error" },
            });
            (result.error);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "result-item-status" },
        });
        const __VLS_76 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
            color: (result.error ? 'error' : 'success'),
        }));
        const __VLS_78 = __VLS_77({
            color: (result.error ? 'error' : 'success'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        __VLS_79.slots.default;
        (result.error ? '失败' : '成功');
        var __VLS_79;
    }
    var __VLS_75;
    var __VLS_71;
}
var __VLS_43;
/** @type {__VLS_StyleScopedClasses['batch-operations']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-toolbar-mobile']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-info']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-close']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-details']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['success']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['error']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-item']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-label']} */ ;
/** @type {__VLS_StyleScopedClasses['stat-value']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-result']} */ ;
/** @type {__VLS_StyleScopedClasses['result-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['result-details']} */ ;
/** @type {__VLS_StyleScopedClasses['result-list']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item']} */ ;
/** @type {__VLS_StyleScopedClasses['result-error']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item-content']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item-title']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item-error']} */ ;
/** @type {__VLS_StyleScopedClasses['result-item-status']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            CloseOutlined: icons_vue_1.CloseOutlined,
            loadingActions: loadingActions,
            showProgress: showProgress,
            progressPercent: progressPercent,
            progressStatus: progressStatus,
            progressText: progressText,
            progressDetails: progressDetails,
            showResultModal: showResultModal,
            resultSummary: resultSummary,
            resultDetails: resultDetails,
            isAllSelected: isAllSelected,
            isIndeterminate: isIndeterminate,
            availableActions: availableActions,
            handleSelectAll: handleSelectAll,
            clearSelection: clearSelection,
            canExecuteAction: canExecuteAction,
            handleAction: handleAction,
            downloadErrorReport: downloadErrorReport,
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
