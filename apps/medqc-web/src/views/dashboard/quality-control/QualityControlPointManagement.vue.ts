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
import vue_router_1 from 'vue-router';
const router = (0, vue_router_1.useRouter)();
// 响应式数据
const loading = (0, vue_1.ref)(false);
const activeTab = (0, vue_1.ref)('online');
const selectedRowKeys = (0, vue_1.ref)(: any[]);
const searchType = (0, vue_1.ref)('id');
const searchKeyword = (0, vue_1.ref)('');
// 表格数据
const tableData = (0, vue_1.ref)([
    {
        id: 'Q2120',
        name: '专病-乳腺癌-乳腺癌...',
        source: '病历书写与管理基本规...',
        category: '内涵质控',
        type: '规范性',
        coreSystem: '',
        document: '入院记录',
        onlineDate: '2024-03-11 16:46',
        lastOperator: '王某',
        enabled: true,
        status: 'online'
    },
    {
        id: 'Q2121',
        name: '专病-乳腺癌-乳腺癌...',
        source: '病历书写与管理基本规...',
        category: '内涵质控',
        type: '规范性',
        coreSystem: '',
        document: '入院记录',
        onlineDate: '2024-03-11 16:46',
        lastOperator: '王某',
        enabled: true,
        status: 'online'
    },
    {
        id: 'Q2122',
        name: '专病-乳腺癌-乳腺癌...',
        source: '病历书写与管理基本规...',
        category: '内涵质控',
        type: '规范性',
        coreSystem: '',
        document: '入院记录',
        onlineDate: '2024-03-11 16:46',
        lastOperator: '王某',
        enabled: true,
        status: 'online'
    }
]);
// 表格列配置
const tableColumns = (0, vue_1.computed)(() => {
    const baseColumns = [
        {
            title: '质控点ID',
            dataIndex: 'id',
            key: 'id',
            width: 100,
            sorter: true
        },
        {
            title: '质控点名称',
            dataIndex: 'name',
            key: 'name',
            width: 200,
            sorter: true
        },
        {
            title: '质控点来源',
            dataIndex: 'source',
            key: 'source',
            width: 150,
            sorter: true
        },
        {
            title: '质控大类',
            dataIndex: 'category',
            key: 'category',
            width: 120,
            sorter: true
        },
        {
            title: '质控类型',
            dataIndex: 'type',
            key: 'type',
            width: 100,
            sorter: true
        },
        {
            title: '核心制度分类',
            dataIndex: 'coreSystem',
            key: 'coreSystem',
            width: 120,
            sorter: true
        },
        {
            title: '质控文书',
            dataIndex: 'document',
            key: 'document',
            width: 100,
            sorter: true
        }
    ];
    if (activeTab.value === 'online') {
        baseColumns.push({
            title: '上线日期',
            dataIndex: 'onlineDate',
            key: 'onlineDate',
            width: 150,
            sorter: true
        }, {
            title: '最后操作人',
            dataIndex: 'lastOperator',
            key: 'lastOperator',
            width: 100,
            sorter: true
        }, {
            title: '启用状态',
            dataIndex: 'enabled',
            key: 'enabled',
            width: 100
        });
    }
    else {
        baseColumns.push({
            title: '最后状态',
            dataIndex: 'status',
            key: 'status',
            width: 100,
            sorter: true
        }, {
            title: '上线日期',
            dataIndex: 'onlineDate',
            key: 'onlineDate',
            width: 150,
            sorter: true
        });
    }
    baseColumns.push({
        title: '操作',
        key: 'action',
        width: 150,
        fixed: 'right'
    });
    return baseColumns;
});
// 行选择配置
const rowSelection = {
    selectedRowKeys: selectedRowKeys,
    onChange: (keys: any) => {
        selectedRowKeys.value = keys;
    }
};
// 分页配置
const paginationConfig = (0, vue_1.reactive)({
    current: 1,
    pageSize: 10,
    total: 2093,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total, range) => `共 ${total} 条`,
    pageSizeOptions: ['10', '20', '50', '100']
});
// 事件处理函数
const handleBatchEnable = () => {
    ant_design_vue_1.message.success(`已批量开启 ${selectedRowKeys.value.length} 个质控点`);
    selectedRowKeys.value = [];
};
const handleBatchDisable = () => {
    ant_design_vue_1.message.success(`已批量关闭 ${selectedRowKeys.value.length} 个质控点`);
    selectedRowKeys.value = [];
};
const handleBatchOffline = () => {
    ant_design_vue_1.message.success(`已批量下线 ${selectedRowKeys.value.length} 个质控点`);
    selectedRowKeys.value = [];
};
const handleBatchDelete = () => {
    ant_design_vue_1.message.success(`已批量删除 ${selectedRowKeys.value.length} 个质控点`);
    selectedRowKeys.value = [];
};
const handleBatchOnline = () => {
    ant_design_vue_1.message.success(`已批量上线 ${selectedRowKeys.value.length} 个质控点`);
    selectedRowKeys.value = [];
};
const handleImport = () => {
    ant_design_vue_1.message.info('导入质控点功能');
};
const handleExport = () => {
    ant_design_vue_1.message.info('导出质控点功能');
};
const handleCreateNew = () => {
    router.push('/dashboard/quality-control/create');
};
const handleSearch = () => {
    ant_design_vue_1.message.info(`搜索: ${searchType.value} - ${searchKeyword.value}`);
};
const handleToggleEnable = (record, checked) => {
    ant_design_vue_1.message.success(`质控点 ${record.id} 已${checked ? '启用' : '禁用'}`);
};
const handleView = (record) => {
    ant_design_vue_1.message.info(`查看质控点: ${record.id}`);
};
const handleEdit = (record) => {
    ant_design_vue_1.message.info(`编辑质控点: ${record.id}`);
};
const handleDelete = (record) => {
    ant_design_vue_1.message.info(`删除质控点: ${record.id}`);
};
(0, vue_1.onMounted)(() => {
    // 初始化数据加载
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-table-tbody']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-control-point-management']} */ ;
/** @type {__VLS_StyleScopedClasses['action-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['search-area']} */ ;
/** @type {__VLS_StyleScopedClasses['search-type-select']} */ ;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "quality-control-point-management" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "tabs-container mb-6" },
});
const __VLS_0 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "custom-tabs" },
}));
const __VLS_2 = __VLS_1({
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "custom-tabs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    key: "online",
    tab: "已上线",
}));
const __VLS_6 = __VLS_5({
    key: "online",
    tab: "已上线",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
const __VLS_8 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    key: "offline",
    tab: "未上线",
}));
const __VLS_10 = __VLS_9({
    key: "offline",
    tab: "未上线",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "action-bar mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "batch-actions" },
});
if (__VLS_ctx.activeTab === 'online') {
    const __VLS_12 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }));
    const __VLS_14 = __VLS_13({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    let __VLS_16;
    let __VLS_17;
    let __VLS_18;
    const __VLS_19 = {
        onClick: (__VLS_ctx.handleBatchEnable)
    };
    __VLS_15.slots.default;
    var __VLS_15;
    const __VLS_20 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }));
    const __VLS_22 = __VLS_21({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    let __VLS_24;
    let __VLS_25;
    let __VLS_26;
    const __VLS_27 = {
        onClick: (__VLS_ctx.handleBatchDisable)
    };
    __VLS_23.slots.default;
    var __VLS_23;
    const __VLS_28 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_32;
    let __VLS_33;
    let __VLS_34;
    const __VLS_35 = {
        onClick: (__VLS_ctx.handleBatchOffline)
    };
    __VLS_31.slots.default;
    var __VLS_31;
}
else {
    const __VLS_36 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }));
    const __VLS_38 = __VLS_37({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    let __VLS_40;
    let __VLS_41;
    let __VLS_42;
    const __VLS_43 = {
        onClick: (__VLS_ctx.handleBatchDelete)
    };
    __VLS_39.slots.default;
    var __VLS_39;
    const __VLS_44 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }));
    const __VLS_46 = __VLS_45({
        ...{ 'onClick': {} },
        disabled: (__VLS_ctx.selectedRowKeys.length === 0),
        ...{ class: "batch-btn" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    let __VLS_48;
    let __VLS_49;
    let __VLS_50;
    const __VLS_51 = {
        onClick: (__VLS_ctx.handleBatchOnline)
    };
    __VLS_47.slots.default;
    var __VLS_47;
}
const __VLS_52 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    ...{ 'onClick': {} },
    ...{ class: "action-btn" },
}));
const __VLS_54 = __VLS_53({
    ...{ 'onClick': {} },
    ...{ class: "action-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
let __VLS_56;
let __VLS_57;
let __VLS_58;
const __VLS_59 = {
    onClick: (__VLS_ctx.handleImport)
};
__VLS_55.slots.default;
var __VLS_55;
const __VLS_60 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    ...{ 'onClick': {} },
    ...{ class: "action-btn" },
}));
const __VLS_62 = __VLS_61({
    ...{ 'onClick': {} },
    ...{ class: "action-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
let __VLS_64;
let __VLS_65;
let __VLS_66;
const __VLS_67 = {
    onClick: (__VLS_ctx.handleExport)
};
__VLS_63.slots.default;
var __VLS_63;
const __VLS_68 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "create-btn" },
}));
const __VLS_70 = __VLS_69({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "create-btn" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
let __VLS_72;
let __VLS_73;
let __VLS_74;
const __VLS_75 = {
    onClick: (__VLS_ctx.handleCreateNew)
};
__VLS_71.slots.default;
var __VLS_71;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "search-area" },
});
const __VLS_76 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    value: (__VLS_ctx.searchType),
    ...{ class: "search-type-select" },
    placeholder: "质控点ID",
}));
const __VLS_78 = __VLS_77({
    value: (__VLS_ctx.searchType),
    ...{ class: "search-type-select" },
    placeholder: "质控点ID",
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
const __VLS_80 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    value: "id",
}));
const __VLS_82 = __VLS_81({
    value: "id",
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
var __VLS_83;
const __VLS_84 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    value: "name",
}));
const __VLS_86 = __VLS_85({
    value: "name",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
var __VLS_87;
var __VLS_79;
const __VLS_88 = {}.AInputSearch;
/** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchKeyword),
    placeholder: "请输入",
    ...{ class: "search-input" },
    enterButton: true,
}));
const __VLS_90 = __VLS_89({
    ...{ 'onSearch': {} },
    value: (__VLS_ctx.searchKeyword),
    placeholder: "请输入",
    ...{ class: "search-input" },
    enterButton: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
let __VLS_92;
let __VLS_93;
let __VLS_94;
const __VLS_95 = {
    onSearch: (__VLS_ctx.handleSearch)
};
var __VLS_91;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "table-container" },
});
const __VLS_96 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    columns: (__VLS_ctx.tableColumns),
    dataSource: (__VLS_ctx.tableData),
    rowSelection: (__VLS_ctx.rowSelection),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    rowKey: "id",
    size: "middle",
    ...{ class: "quality-point-table" },
}));
const __VLS_98 = __VLS_97({
    columns: (__VLS_ctx.tableColumns),
    dataSource: (__VLS_ctx.tableData),
    rowSelection: (__VLS_ctx.rowSelection),
    pagination: (__VLS_ctx.paginationConfig),
    loading: (__VLS_ctx.loading),
    rowKey: "id",
    size: "middle",
    ...{ class: "quality-point-table" },
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
__VLS_99.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_99.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'name') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "name-cell" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "name-text" },
        });
        (record.name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-text" },
        });
        (record.source);
    }
    if (column.key === 'enabled' && __VLS_ctx.activeTab === 'online') {
        const __VLS_100 = {}.ASwitch;
        /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            ...{ 'onChange': {} },
            checked: (record.enabled),
            size: "small",
        }));
        const __VLS_102 = __VLS_101({
            ...{ 'onChange': {} },
            checked: (record.enabled),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        let __VLS_104;
        let __VLS_105;
        let __VLS_106;
        const __VLS_107 = {
            onChange: ((checked) => __VLS_ctx.handleToggleEnable(record, checked))
        };
        var __VLS_103;
    }
    if (column.key === 'action') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "action-buttons" },
        });
        const __VLS_108 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_110 = __VLS_109({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_109));
        let __VLS_112;
        let __VLS_113;
        let __VLS_114;
        const __VLS_115 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleView(record);
            }
        };
        __VLS_111.slots.default;
        var __VLS_111;
        const __VLS_116 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_118 = __VLS_117({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_117));
        let __VLS_120;
        let __VLS_121;
        let __VLS_122;
        const __VLS_123 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleEdit(record);
            }
        };
        __VLS_119.slots.default;
        var __VLS_119;
        const __VLS_124 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            danger: true,
        }));
        const __VLS_126 = __VLS_125({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_125));
        let __VLS_128;
        let __VLS_129;
        let __VLS_130;
        const __VLS_131 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleDelete(record);
            }
        };
        __VLS_127.slots.default;
        var __VLS_127;
    }
}
var __VLS_99;
/** @type {__VLS_StyleScopedClasses['quality-control-point-management']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['tabs-container']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['action-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['action-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['create-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['search-area']} */ ;
/** @type {__VLS_StyleScopedClasses['search-type-select']} */ ;
/** @type {__VLS_StyleScopedClasses['search-input']} */ ;
/** @type {__VLS_StyleScopedClasses['table-container']} */ ;
/** @type {__VLS_StyleScopedClasses['quality-point-table']} */ ;
/** @type {__VLS_StyleScopedClasses['name-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['name-text']} */ ;
/** @type {__VLS_StyleScopedClasses['source-text']} */ ;
/** @type {__VLS_StyleScopedClasses['action-buttons']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            loading: loading,
            activeTab: activeTab,
            selectedRowKeys: selectedRowKeys,
            searchType: searchType,
            searchKeyword: searchKeyword,
            tableData: tableData,
            tableColumns: tableColumns,
            rowSelection: rowSelection,
            paginationConfig: paginationConfig,
            handleBatchEnable: handleBatchEnable,
            handleBatchDisable: handleBatchDisable,
            handleBatchOffline: handleBatchOffline,
            handleBatchDelete: handleBatchDelete,
            handleBatchOnline: handleBatchOnline,
            handleImport: handleImport,
            handleExport: handleExport,
            handleCreateNew: handleCreateNew,
            handleSearch: handleSearch,
            handleToggleEnable: handleToggleEnable,
            handleView: handleView,
            handleEdit: handleEdit,
            handleDelete: handleDelete,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
