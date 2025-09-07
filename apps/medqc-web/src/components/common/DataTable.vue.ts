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
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
import vue_1 from 'vue';
import icons_vue_1 from '@ant-design/icons-vue';
const EmptyState_vue_1 = __importDefault(require("./EmptyState.vue"));
const props = withDefaults(defineProps(), { loading: false,
    size: 'middle',
    bordered: false,
    showToolbar: true,
    showSearch: true,
    searchPlaceholder: '请输入关键词搜索',
    showColumnSettings: true,
    showExport: false,
    filters: () => [],
    batchActions: () => [],
    emptyType: 'empty',
    emptyTitle: '暂无数据',
    emptyDescription: '当前没有可显示的内容',
    emptyActions: () => [],
    tableProps: () => ({})
});
const emit = defineEmits();
// 响应式数据
const searchValue = (0, vue_1.ref)('');
const searchLoading = (0, vue_1.ref)(false);
const refreshing = (0, vue_1.ref)(false);
const exporting = (0, vue_1.ref)(false);
const selectedRowKeys = (0, vue_1.ref)(: any[]);
const filterValues = (0, vue_1.ref)({});
const visibleColumns = (0, vue_1.ref)(: any[]);
// 初始化可见列
(0, vue_1.onMounted)(() => {
    visibleColumns.value = props.columns.map(col => {
        const column = col;
        return column.key || column.dataIndex;
    }).filter(Boolean);
});
// 计算属性
const configurableColumns = (0, vue_1.computed)(() => {
    return props.columns.filter(col => col.key !== 'actions' && !col.fixed);
});
const visibleTableColumns = (0, vue_1.computed)(() => {
    return props.columns.filter(col => {
        const column = col;
        if (column.key === 'actions' || column.fixed)
            return true;
        return visibleColumns.value.includes(column.key || column.dataIndex);
    });
});
const activeFilters = (0, vue_1.computed)(() => {
    return Object.entries(filterValues.value)
        .filter(([_, value]) => value !== undefined && value !== null && value !== '')
        .map(([key, _]) => key);
});
const processedDataSource = (0, vue_1.computed)(() => {
    let data = [...props.dataSource];
    // 搜索过滤
    if (searchValue.value) {
        const searchLower = searchValue.value.toLowerCase();
        data = data.filter(item => {
            return Object.values(item).some(value => String(value).toLowerCase().includes(searchLower));
        });
    }
    // 筛选器过滤
    if (activeFilters.value.length > 0) {
        data = data.filter(item => {
            return activeFilters.value.every(key => {
                const filterValue = filterValues.value[key];
                const itemValue = item[key];
                if (filterValue === undefined || filterValue === null || filterValue === '') {
                    return true;
                }
                return String(itemValue).includes(String(filterValue));
            });
        });
    }
    return data;
});
const paginationConfig = (0, vue_1.computed)(() => {
    if (props.pagination === false)
        return false;
    return {
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: (total, range) => `显示 ${range[0]}-${range[1]} 条，共 ${total} 条`,
        ...props.pagination
    };
});
const rowSelection = (0, vue_1.computed)(() => {
    if (!props.rowSelection)
        return undefined;
    return {
        selectedRowKeys: selectedRowKeys.value,
        onChange: (keys: any) => {
            selectedRowKeys.value = keys;
        },
        ...props.rowSelection
    };
});
const tableClass = (0, vue_1.computed)(() => [
    'enhanced-table',
    {
        'table-small': props.size === 'small',
        'table-large': props.size === 'large',
        'table-bordered': props.bordered
    }
]);
// 事件处理
const handleSearch = (value) => {
    searchLoading.value = true;
    emit('search', value);
    // 模拟搜索延迟
    setTimeout(() => {
        searchLoading.value = false;
    }, 300);
};
const handleSearchChange = (e) => {
    searchValue.value = e.target.value;
};
const handleFilterChange = () => {
    emit('filter-change', filterValues.value);
};
const handleBatchAction = (action) => {
    if (action.onClick) {
        action.onClick(selectedRowKeys.value);
    }
    emit('batch-action', action, selectedRowKeys.value);
};
const handleRefresh = () => {
    refreshing.value = true;
    emit('refresh');
    // 模拟刷新延迟
    setTimeout(() => {
        refreshing.value = false;
    }, 500);
};
const handleExport = () => {
    exporting.value = true;
    emit('export');
    // 模拟导出延迟
    setTimeout(() => {
        exporting.value = false;
    }, 1000);
};
const handleTableChange = (pagination, filters: any,  sorter: any) => {
    emit('change', pagination, filters, sorter);
};
const handleEmptyAction = (action) => {
    if (action.onClick) {
        action.onClick();
    }
    emit('empty-action', action);
};
// 清空选择
const clearSelection = () => {
    selectedRowKeys.value = [];
};
// 重置筛选
const resetFilters = () => {
    filterValues.value = {};
    searchValue.value = '';
};
// 暴露方法
const __VLS_exposed = {
    clearSelection,
    resetFilters,
    selectedRowKeys: selectedRowKeys.value
};
defineExpose(__VLS_exposed);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({ loading: false,
    size: 'middle',
    bordered: false,
    showToolbar: true,
    showSearch: true,
    searchPlaceholder: '请输入关键词搜索',
    showColumnSettings: true,
    showExport: false,
    filters: () => [],
    batchActions: () => [],
    emptyType: 'empty',
    emptyTitle: '暂无数据',
    emptyDescription: '当前没有可显示的内容',
    emptyActions: () => [],
    tableProps: () => ({})
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['column-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-row-selected']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-thead']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-thead']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-thead']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['table-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-body']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-body']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-body']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-table-body']} */ ;
/** @type {__VLS_StyleScopedClasses['data-table-container']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "data-table-container" },
});
if (__VLS_ctx.showToolbar) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "table-toolbar" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "toolbar-left" },
    });
    var __VLS_0 = {};
    if (__VLS_ctx.selectedRowKeys.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "batch-actions" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "batch-info" },
        });
        (__VLS_ctx.selectedRowKeys.length);
        const __VLS_2 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_3 = __VLS_asFunctionalComponent(__VLS_2, new __VLS_2({
            size: "small",
        }));
        const __VLS_4 = __VLS_3({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_3));
        __VLS_5.slots.default;
        for (const [action] of __VLS_getVForSourceType((__VLS_ctx.batchActions))) {
            const __VLS_6 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_7 = __VLS_asFunctionalComponent(__VLS_6, new __VLS_6({
                ...{ 'onClick': {} },
                key: (action.key),
                type: (action.type || 'default'),
                danger: (action.danger),
                loading: (action.loading),
                disabled: (action.disabled),
            }));
            const __VLS_8 = __VLS_7({
                ...{ 'onClick': {} },
                key: (action.key),
                type: (action.type || 'default'),
                danger: (action.danger),
                loading: (action.loading),
                disabled: (action.disabled),
            }, ...__VLS_functionalComponentArgsRest(__VLS_7));
            let __VLS_10;
            let __VLS_11;
            let __VLS_12;
            const __VLS_13 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.showToolbar))
                        return;
                    if (!(__VLS_ctx.selectedRowKeys.length > 0))
                        return;
                    __VLS_ctx.handleBatchAction(action);
                }
            };
            __VLS_9.slots.default;
            if (action.icon) {
                const __VLS_14 = ((action.icon));
                // @ts-ignore
                const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({}));
                const __VLS_16 = __VLS_15({}, ...__VLS_functionalComponentArgsRest(__VLS_15));
            }
            (action.text);
            var __VLS_9;
        }
        var __VLS_5;
    }
    if (__VLS_ctx.showSearch) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "search-box" },
        });
        const __VLS_18 = {}.AInputSearch;
        /** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
        // @ts-ignore
        const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
            ...{ 'onSearch': {} },
            ...{ 'onChange': {} },
            value: (__VLS_ctx.searchValue),
            placeholder: (__VLS_ctx.searchPlaceholder),
            loading: (__VLS_ctx.searchLoading),
            ...{ style: {} },
        }));
        const __VLS_20 = __VLS_19({
            ...{ 'onSearch': {} },
            ...{ 'onChange': {} },
            value: (__VLS_ctx.searchValue),
            placeholder: (__VLS_ctx.searchPlaceholder),
            loading: (__VLS_ctx.searchLoading),
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_19));
        let __VLS_22;
        let __VLS_23;
        let __VLS_24;
        const __VLS_25 = {
            onSearch: (__VLS_ctx.handleSearch)
        };
        const __VLS_26 = {
            onChange: (__VLS_ctx.handleSearchChange)
        };
        var __VLS_21;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "toolbar-right" },
    });
    var __VLS_27 = {};
    const __VLS_29 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({
        size: "small",
    }));
    const __VLS_31 = __VLS_30({
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_30));
    __VLS_32.slots.default;
    if (__VLS_ctx.filters.length > 0) {
        const __VLS_33 = {}.ADropdown;
        /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
        // @ts-ignore
        const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
            trigger: "click",
        }));
        const __VLS_35 = __VLS_34({
            trigger: "click",
        }, ...__VLS_functionalComponentArgsRest(__VLS_34));
        __VLS_36.slots.default;
        const __VLS_37 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_38 = __VLS_asFunctionalComponent(__VLS_37, new __VLS_37({}));
        const __VLS_39 = __VLS_38({}, ...__VLS_functionalComponentArgsRest(__VLS_38));
        __VLS_40.slots.default;
        const __VLS_41 = {}.FilterOutlined;
        /** @type {[typeof __VLS_components.FilterOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({}));
        const __VLS_43 = __VLS_42({}, ...__VLS_functionalComponentArgsRest(__VLS_42));
        if (__VLS_ctx.activeFilters.length > 0) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "filter-count" },
            });
            (__VLS_ctx.activeFilters.length);
        }
        var __VLS_40;
        {
            const { overlay: __VLS_thisSlot } = __VLS_36.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "filter-dropdown" },
            });
            for (const [filter] of __VLS_getVForSourceType((__VLS_ctx.filters))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (filter.key),
                    ...{ class: "filter-item" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "filter-label" },
                });
                (filter.label);
                if (filter.type === 'select') {
                    const __VLS_45 = {}.ASelect;
                    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
                    // @ts-ignore
                    const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({
                        ...{ 'onChange': {} },
                        value: (__VLS_ctx.filterValues[filter.key]),
                        placeholder: (filter.placeholder),
                        options: (filter.options),
                        ...{ style: {} },
                        allowClear: true,
                    }));
                    const __VLS_47 = __VLS_46({
                        ...{ 'onChange': {} },
                        value: (__VLS_ctx.filterValues[filter.key]),
                        placeholder: (filter.placeholder),
                        options: (filter.options),
                        ...{ style: {} },
                        allowClear: true,
                    }, ...__VLS_functionalComponentArgsRest(__VLS_46));
                    let __VLS_49;
                    let __VLS_50;
                    let __VLS_51;
                    const __VLS_52 = {
                        onChange: (__VLS_ctx.handleFilterChange)
                    };
                    var __VLS_48;
                }
                else if (filter.type === 'date') {
                    const __VLS_53 = {}.ADatePicker;
                    /** @type {[typeof __VLS_components.ADatePicker, typeof __VLS_components.aDatePicker, ]} */ ;
                    // @ts-ignore
                    const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
                        ...{ 'onChange': {} },
                        value: (__VLS_ctx.filterValues[filter.key]),
                        placeholder: (filter.placeholder),
                        ...{ style: {} },
                    }));
                    const __VLS_55 = __VLS_54({
                        ...{ 'onChange': {} },
                        value: (__VLS_ctx.filterValues[filter.key]),
                        placeholder: (filter.placeholder),
                        ...{ style: {} },
                    }, ...__VLS_functionalComponentArgsRest(__VLS_54));
                    let __VLS_57;
                    let __VLS_58;
                    let __VLS_59;
                    const __VLS_60 = {
                        onChange: (__VLS_ctx.handleFilterChange)
                    };
                    var __VLS_56;
                }
                else {
                    const __VLS_61 = {}.AInput;
                    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
                    // @ts-ignore
                    const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
                        ...{ 'onChange': {} },
                        value: (__VLS_ctx.filterValues[filter.key]),
                        placeholder: (filter.placeholder),
                        ...{ style: {} },
                    }));
                    const __VLS_63 = __VLS_62({
                        ...{ 'onChange': {} },
                        value: (__VLS_ctx.filterValues[filter.key]),
                        placeholder: (filter.placeholder),
                        ...{ style: {} },
                    }, ...__VLS_functionalComponentArgsRest(__VLS_62));
                    let __VLS_65;
                    let __VLS_66;
                    let __VLS_67;
                    const __VLS_68 = {
                        onChange: (__VLS_ctx.handleFilterChange)
                    };
                    var __VLS_64;
                }
            }
        }
        var __VLS_36;
    }
    if (__VLS_ctx.showColumnSettings) {
        const __VLS_69 = {}.ADropdown;
        /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
        // @ts-ignore
        const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
            trigger: "click",
        }));
        const __VLS_71 = __VLS_70({
            trigger: "click",
        }, ...__VLS_functionalComponentArgsRest(__VLS_70));
        __VLS_72.slots.default;
        const __VLS_73 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({}));
        const __VLS_75 = __VLS_74({}, ...__VLS_functionalComponentArgsRest(__VLS_74));
        __VLS_76.slots.default;
        const __VLS_77 = {}.SettingOutlined;
        /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({}));
        const __VLS_79 = __VLS_78({}, ...__VLS_functionalComponentArgsRest(__VLS_78));
        var __VLS_76;
        {
            const { overlay: __VLS_thisSlot } = __VLS_72.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "column-settings" },
            });
            const __VLS_81 = {}.ACheckboxGroup;
            /** @type {[typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, typeof __VLS_components.ACheckboxGroup, typeof __VLS_components.aCheckboxGroup, ]} */ ;
            // @ts-ignore
            const __VLS_82 = __VLS_asFunctionalComponent(__VLS_81, new __VLS_81({
                value: (__VLS_ctx.visibleColumns),
            }));
            const __VLS_83 = __VLS_82({
                value: (__VLS_ctx.visibleColumns),
            }, ...__VLS_functionalComponentArgsRest(__VLS_82));
            __VLS_84.slots.default;
            for (const [column] of __VLS_getVForSourceType((__VLS_ctx.configurableColumns))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (column.key),
                    ...{ class: "column-item" },
                });
                const __VLS_85 = {}.ACheckbox;
                /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
                // @ts-ignore
                const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
                    value: (column.key),
                }));
                const __VLS_87 = __VLS_86({
                    value: (column.key),
                }, ...__VLS_functionalComponentArgsRest(__VLS_86));
                __VLS_88.slots.default;
                (column.title);
                var __VLS_88;
            }
            var __VLS_84;
        }
        var __VLS_72;
    }
    const __VLS_89 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.refreshing),
    }));
    const __VLS_91 = __VLS_90({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.refreshing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_90));
    let __VLS_93;
    let __VLS_94;
    let __VLS_95;
    const __VLS_96 = {
        onClick: (__VLS_ctx.handleRefresh)
    };
    __VLS_92.slots.default;
    const __VLS_97 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({}));
    const __VLS_99 = __VLS_98({}, ...__VLS_functionalComponentArgsRest(__VLS_98));
    var __VLS_92;
    if (__VLS_ctx.showExport) {
        const __VLS_101 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({
            ...{ 'onClick': {} },
            loading: (__VLS_ctx.exporting),
        }));
        const __VLS_103 = __VLS_102({
            ...{ 'onClick': {} },
            loading: (__VLS_ctx.exporting),
        }, ...__VLS_functionalComponentArgsRest(__VLS_102));
        let __VLS_105;
        let __VLS_106;
        let __VLS_107;
        const __VLS_108 = {
            onClick: (__VLS_ctx.handleExport)
        };
        __VLS_104.slots.default;
        const __VLS_109 = {}.DownloadOutlined;
        /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({}));
        const __VLS_111 = __VLS_110({}, ...__VLS_functionalComponentArgsRest(__VLS_110));
        var __VLS_104;
    }
    var __VLS_32;
}
const __VLS_113 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
    ...{ 'onChange': {} },
    ...(__VLS_ctx.tableProps),
    columns: (__VLS_ctx.visibleTableColumns),
    dataSource: (__VLS_ctx.processedDataSource),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.paginationConfig),
    rowSelection: (__VLS_ctx.rowSelection),
    scroll: (__VLS_ctx.scroll),
    size: (__VLS_ctx.size),
    bordered: (__VLS_ctx.bordered),
    ...{ class: (__VLS_ctx.tableClass) },
}));
const __VLS_115 = __VLS_114({
    ...{ 'onChange': {} },
    ...(__VLS_ctx.tableProps),
    columns: (__VLS_ctx.visibleTableColumns),
    dataSource: (__VLS_ctx.processedDataSource),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.paginationConfig),
    rowSelection: (__VLS_ctx.rowSelection),
    scroll: (__VLS_ctx.scroll),
    size: (__VLS_ctx.size),
    bordered: (__VLS_ctx.bordered),
    ...{ class: (__VLS_ctx.tableClass) },
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
let __VLS_117;
let __VLS_118;
let __VLS_119;
const __VLS_120 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_116.slots.default;
for (const [_, name] of __VLS_getVForSourceType((__VLS_ctx.$slots))) {
    {
        const { [__VLS_tryAsConstant(name)]: __VLS_thisSlot } = __VLS_116.slots;
        const [slotProps] = __VLS_getSlotParams(__VLS_thisSlot);
        var __VLS_121 = {
            ...(slotProps),
        };
        var __VLS_122 = __VLS_tryAsConstant(name);
    }
}
var __VLS_116;
if (!__VLS_ctx.loading && __VLS_ctx.processedDataSource.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty-state" },
    });
    var __VLS_125 = {};
    /** @type {[typeof EmptyState, ]} */ ;
    // @ts-ignore
    const __VLS_127 = __VLS_asFunctionalComponent(EmptyState_vue_1.default, new EmptyState_vue_1.default({
        ...{ 'onAction': {} },
        type: (__VLS_ctx.emptyType),
        title: (__VLS_ctx.emptyTitle),
        description: (__VLS_ctx.emptyDescription),
        actions: (__VLS_ctx.emptyActions),
    }));
    const __VLS_128 = __VLS_127({
        ...{ 'onAction': {} },
        type: (__VLS_ctx.emptyType),
        title: (__VLS_ctx.emptyTitle),
        description: (__VLS_ctx.emptyDescription),
        actions: (__VLS_ctx.emptyActions),
    }, ...__VLS_functionalComponentArgsRest(__VLS_127));
    let __VLS_130;
    let __VLS_131;
    let __VLS_132;
    const __VLS_133 = {
        onAction: (__VLS_ctx.handleEmptyAction)
    };
    var __VLS_129;
}
/** @type {__VLS_StyleScopedClasses['data-table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['table-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-info']} */ ;
/** @type {__VLS_StyleScopedClasses['search-box']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-count']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-dropdown']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-item']} */ ;
/** @type {__VLS_StyleScopedClasses['filter-label']} */ ;
/** @type {__VLS_StyleScopedClasses['column-settings']} */ ;
/** @type {__VLS_StyleScopedClasses['column-item']} */ ;
/** @type {__VLS_StyleScopedClasses['empty-state']} */ ;
// @ts-ignore
var __VLS_1 = __VLS_0, __VLS_28 = __VLS_27, __VLS_123 = __VLS_122, __VLS_124 = __VLS_121, __VLS_126 = __VLS_125;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            FilterOutlined: icons_vue_1.FilterOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            EmptyState: EmptyState_vue_1.default,
            searchValue: searchValue,
            searchLoading: searchLoading,
            refreshing: refreshing,
            exporting: exporting,
            selectedRowKeys: selectedRowKeys,
            filterValues: filterValues,
            visibleColumns: visibleColumns,
            configurableColumns: configurableColumns,
            visibleTableColumns: visibleTableColumns,
            activeFilters: activeFilters,
            processedDataSource: processedDataSource,
            paginationConfig: paginationConfig,
            rowSelection: rowSelection,
            tableClass: tableClass,
            handleSearch: handleSearch,
            handleSearchChange: handleSearchChange,
            handleFilterChange: handleFilterChange,
            handleBatchAction: handleBatchAction,
            handleRefresh: handleRefresh,
            handleExport: handleExport,
            handleTableChange: handleTableChange,
            handleEmptyAction: handleEmptyAction,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
const __VLS_component = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ...__VLS_exposed,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export const default = {};
; /* PartiallyEnd: #4569/main.vue */
