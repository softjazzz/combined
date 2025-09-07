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
import unstructured_documents_1 from '@/api/unstructured-documents';
// 响应式数据
const documents = (0, vue_1.ref)(: any[]);
const loading = (0, vue_1.ref)(false);
const saving = (0, vue_1.ref)(false);
const searchTerm = (0, vue_1.ref)('');
const documentModalVisible = (0, vue_1.ref)(false);
const currentDocument = (0, vue_1.ref)(null);
// 新文档表单
const newDocument = (0, vue_1.reactive)({
    title: '',
    content: '',
    category: ''
});
// 筛选条件
const filters = (0, vue_1.reactive)({
    processing_status: undefined,
    qc_status: undefined,
    category: undefined
});
// 分页配置
const pagination = (0, vue_1.reactive)({
    current: 1,
    pageSize: 10,
    total: 0,
    showSizeChanger: true,
    showQuickJumper: true,
    showTotal: (total) => `共 ${total} 条记录`
});
// 表格列配置
const columns = [
    {
        title: '文档信息',
        key: 'title',
        width: 300
    },
    {
        title: '分类',
        dataIndex: 'category',
        key: 'category',
        width: 120
    },
    {
        title: '处理状态',
        key: 'processing_status',
        width: 100
    },
    {
        title: '质控状态',
        key: 'qc_status',
        width: 100
    },
    {
        title: '创建时间',
        key: 'created_at',
        width: 150
    },
    {
        title: '操作',
        key: 'actions',
        width: 200
    }
];
// 方法
const loadDocuments = async () => {
    loading.value = true;
    try {
        const response = await (0, unstructured_documents_1.getUnstructuredDocuments)({
            ...filters,
            limit: pagination.pageSize,
            offset: (pagination.current - 1) * pagination.pageSize
        });
        if (response.success && response.data) {
            documents.value = response.data;
            // 这里应该从API获取总数，暂时使用数据长度
            pagination.total = response.data.length;
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '加载文档失败');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('加载文档失败');
    }
    finally {
        loading.value = false;
    }
};
const saveDocument = async () => {
    if (!newDocument.content.trim()) {
        ant_design_vue_1.message.warning('请输入文档内容');
        return;
    }
    saving.value = true;
    try {
        const response = await (0, unstructured_documents_1.saveRawMedicalText)(newDocument.content, newDocument.title || undefined, newDocument.category || undefined);
        if (response.success) {
            ant_design_vue_1.message.success('文档保存成功');
            // 重置表单
            newDocument.title = '';
            newDocument.content = '';
            newDocument.category = '';
            // 重新加载列表
            await loadDocuments();
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '保存失败');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
    finally {
        saving.value = false;
    }
};
const handleSearch = async () => {
    if (!searchTerm.value.trim()) {
        await loadDocuments();
        return;
    }
    loading.value = true;
    try {
        const response = await (0, unstructured_documents_1.searchUnstructuredDocuments)(searchTerm.value, {
            limit: pagination.pageSize,
            offset: (pagination.current - 1) * pagination.pageSize
        });
        if (response.success && response.data) {
            documents.value = response.data;
            pagination.total = response.data.length;
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '搜索失败');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('搜索失败');
    }
    finally {
        loading.value = false;
    }
};
const viewDocument = (document) => {
    currentDocument.value = document;
    documentModalVisible.value = true;
};
const editDocument = (document) => {
    // TODO: 实现编辑功能
    ant_design_vue_1.message.info('编辑功能开发中...');
};
const deleteDocument = async (document) => {
    try {
        const response = await (0, unstructured_documents_1.deleteUnstructuredDocument)(document.id);
        if (response.success) {
            ant_design_vue_1.message.success('删除成功');
            await loadDocuments();
        }
        else {
            ant_design_vue_1.message.error(response.error?.message || '删除失败');
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('删除失败');
    }
};
const handleTableChange = (pag) => {
    pagination.current = pag.current;
    pagination.pageSize = pag.pageSize;
    loadDocuments();
};
// 工具方法
const getDocumentTypeColor = (type) => {
    const colors = {
        'raw_text': 'blue',
        'copied_record': 'green',
        'uploaded_file': 'orange',
        'scanned_document': 'purple'
    };
    return colors[type] || 'default';
};
const getDocumentTypeText = (type) => {
    const texts = {
        'raw_text': '原始文本',
        'copied_record': '复制记录',
        'uploaded_file': '上传文件',
        'scanned_document': '扫描文档'
    };
    return texts[type] || type;
};
const getStatusColor = (status) => {
    const colors = {
        'pending': 'orange',
        'processing': 'blue',
        'completed': 'green',
        'failed': 'red',
        'skipped': 'gray'
    };
    return colors[status] || 'default';
};
const getStatusText = (status) => {
    const texts = {
        'pending': '待处理',
        'processing': '处理中',
        'completed': '已完成',
        'failed': '失败',
        'skipped': '跳过'
    };
    return texts[status] || status;
};
const getQCStatusColor = (status) => {
    const colors = {
        'not_analyzed': 'gray',
        'analyzing': 'blue',
        'completed': 'green',
        'failed': 'red'
    };
    return colors[status] || 'default';
};
const getQCStatusText = (status) => {
    const texts = {
        'not_analyzed': '未分析',
        'analyzing': '分析中',
        'completed': '已完成',
        'failed': '失败'
    };
    return texts[status] || status;
};
const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('zh-CN');
};
// 生命周期
(0, vue_1.onMounted)(() => {
    loadDocuments();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-add-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['document-content']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "unstructured-documents-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
const __VLS_0 = {}.Card;
/** @type {[typeof __VLS_components.Card, typeof __VLS_components.Card, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "quick-add-card" },
    title: "快速添加文档",
}));
const __VLS_2 = __VLS_1({
    ...{ class: "quick-add-card" },
    title: "快速添加文档",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "quick-add-form" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-row" },
});
const __VLS_4 = {}.Input;
/** @type {[typeof __VLS_components.Input, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    value: (__VLS_ctx.newDocument.title),
    placeholder: "文档标题（可选）",
    ...{ style: {} },
}));
const __VLS_6 = __VLS_5({
    value: (__VLS_ctx.newDocument.title),
    placeholder: "文档标题（可选）",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
const __VLS_8 = {}.Select;
/** @type {[typeof __VLS_components.Select, typeof __VLS_components.Select, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    value: (__VLS_ctx.newDocument.category),
    placeholder: "选择分类",
    ...{ style: {} },
}));
const __VLS_10 = __VLS_9({
    value: (__VLS_ctx.newDocument.category),
    placeholder: "选择分类",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.SelectOption;
/** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    value: "心血管内科",
}));
const __VLS_14 = __VLS_13({
    value: "心血管内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
const __VLS_16 = {}.SelectOption;
/** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    value: "呼吸内科",
}));
const __VLS_18 = __VLS_17({
    value: "呼吸内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
var __VLS_19;
const __VLS_20 = {}.SelectOption;
/** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    value: "消化内科",
}));
const __VLS_22 = __VLS_21({
    value: "消化内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
var __VLS_23;
const __VLS_24 = {}.SelectOption;
/** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    value: "神经内科",
}));
const __VLS_26 = __VLS_25({
    value: "神经内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
var __VLS_27;
const __VLS_28 = {}.SelectOption;
/** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    value: "妇产科",
}));
const __VLS_30 = __VLS_29({
    value: "妇产科",
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
var __VLS_31;
const __VLS_32 = {}.SelectOption;
/** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: "外科",
}));
const __VLS_34 = __VLS_33({
    value: "外科",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
const __VLS_36 = {}.SelectOption;
/** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: "其他",
}));
const __VLS_38 = __VLS_37({
    value: "其他",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
var __VLS_39;
var __VLS_11;
const __VLS_40 = {}.Button;
/** @type {[typeof __VLS_components.Button, typeof __VLS_components.Button, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (__VLS_ctx.saveDocument)
};
__VLS_43.slots.default;
var __VLS_43;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-row" },
});
const __VLS_48 = {}.TextArea;
/** @type {[typeof __VLS_components.Textarea, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    value: (__VLS_ctx.newDocument.content),
    placeholder: "在此粘贴病历文本内容...",
    rows: (8),
    ...{ style: {} },
}));
const __VLS_50 = __VLS_49({
    value: (__VLS_ctx.newDocument.content),
    placeholder: "在此粘贴病历文本内容...",
    rows: (8),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
var __VLS_3;
const __VLS_52 = {}.Card;
/** @type {[typeof __VLS_components.Card, typeof __VLS_components.Card, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    ...{ class: "documents-list-card" },
    title: "文档列表",
}));
const __VLS_54 = __VLS_53({
    ...{ class: "documents-list-card" },
    title: "文档列表",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_55.slots;
    const __VLS_56 = {}.Space;
    /** @type {[typeof __VLS_components.Space, typeof __VLS_components.Space, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
    const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    const __VLS_60 = ((__VLS_ctx.Input.Search));
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        ...{ 'onSearch': {} },
        value: (__VLS_ctx.searchTerm),
        placeholder: "搜索文档...",
        ...{ style: {} },
    }));
    const __VLS_62 = __VLS_61({
        ...{ 'onSearch': {} },
        value: (__VLS_ctx.searchTerm),
        placeholder: "搜索文档...",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    let __VLS_64;
    let __VLS_65;
    let __VLS_66;
    const __VLS_67 = {
        onSearch: (__VLS_ctx.handleSearch)
    };
    var __VLS_63;
    const __VLS_68 = {}.Select;
    /** @type {[typeof __VLS_components.Select, typeof __VLS_components.Select, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filters.processing_status),
        placeholder: "处理状态",
        ...{ style: {} },
        allowClear: true,
    }));
    const __VLS_70 = __VLS_69({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.filters.processing_status),
        placeholder: "处理状态",
        ...{ style: {} },
        allowClear: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    let __VLS_72;
    let __VLS_73;
    let __VLS_74;
    const __VLS_75 = {
        onChange: (__VLS_ctx.loadDocuments)
    };
    __VLS_71.slots.default;
    const __VLS_76 = {}.SelectOption;
    /** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        value: "pending",
    }));
    const __VLS_78 = __VLS_77({
        value: "pending",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    var __VLS_79;
    const __VLS_80 = {}.SelectOption;
    /** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        value: "processing",
    }));
    const __VLS_82 = __VLS_81({
        value: "processing",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    var __VLS_83;
    const __VLS_84 = {}.SelectOption;
    /** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        value: "completed",
    }));
    const __VLS_86 = __VLS_85({
        value: "completed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    var __VLS_87;
    const __VLS_88 = {}.SelectOption;
    /** @type {[typeof __VLS_components.SelectOption, typeof __VLS_components.SelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        value: "failed",
    }));
    const __VLS_90 = __VLS_89({
        value: "failed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    __VLS_91.slots.default;
    var __VLS_91;
    var __VLS_71;
    const __VLS_92 = {}.Button;
    /** @type {[typeof __VLS_components.Button, typeof __VLS_components.Button, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
    }));
    const __VLS_94 = __VLS_93({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.loading),
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    let __VLS_96;
    let __VLS_97;
    let __VLS_98;
    const __VLS_99 = {
        onClick: (__VLS_ctx.loadDocuments)
    };
    __VLS_95.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_95.slots;
        const __VLS_100 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({}));
        const __VLS_102 = __VLS_101({}, ...__VLS_functionalComponentArgsRest(__VLS_101));
    }
    var __VLS_95;
    var __VLS_59;
}
const __VLS_104 = {}.Table;
/** @type {[typeof __VLS_components.Table, typeof __VLS_components.Table, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.documents),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowKey: "id",
}));
const __VLS_106 = __VLS_105({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.documents),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.pagination),
    rowKey: "id",
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
let __VLS_108;
let __VLS_109;
let __VLS_110;
const __VLS_111 = {
    onChange: (__VLS_ctx.handleTableChange)
};
__VLS_107.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_107.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'title') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (record.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "document-meta" },
        });
        const __VLS_112 = {}.Tag;
        /** @type {[typeof __VLS_components.Tag, typeof __VLS_components.Tag, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            color: (__VLS_ctx.getDocumentTypeColor(record.document_type)),
        }));
        const __VLS_114 = __VLS_113({
            color: (__VLS_ctx.getDocumentTypeColor(record.document_type)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        (__VLS_ctx.getDocumentTypeText(record.document_type));
        var __VLS_115;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "content-length" },
        });
        (record.content_length);
    }
    if (column.key === 'processing_status') {
        const __VLS_116 = {}.Tag;
        /** @type {[typeof __VLS_components.Tag, typeof __VLS_components.Tag, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
            color: (__VLS_ctx.getStatusColor(record.processing_status)),
        }));
        const __VLS_118 = __VLS_117({
            color: (__VLS_ctx.getStatusColor(record.processing_status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_117));
        __VLS_119.slots.default;
        (__VLS_ctx.getStatusText(record.processing_status));
        var __VLS_119;
    }
    if (column.key === 'qc_status') {
        const __VLS_120 = {}.Tag;
        /** @type {[typeof __VLS_components.Tag, typeof __VLS_components.Tag, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            color: (__VLS_ctx.getQCStatusColor(record.qc_status)),
        }));
        const __VLS_122 = __VLS_121({
            color: (__VLS_ctx.getQCStatusColor(record.qc_status)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        (__VLS_ctx.getQCStatusText(record.qc_status));
        var __VLS_123;
    }
    if (column.key === 'created_at') {
        (__VLS_ctx.formatDate(record.created_at));
    }
    if (column.key === 'actions') {
        const __VLS_124 = {}.Space;
        /** @type {[typeof __VLS_components.Space, typeof __VLS_components.Space, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
        const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
        __VLS_127.slots.default;
        const __VLS_128 = {}.Button;
        /** @type {[typeof __VLS_components.Button, typeof __VLS_components.Button, ]} */ ;
        // @ts-ignore
        const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_130 = __VLS_129({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_129));
        let __VLS_132;
        let __VLS_133;
        let __VLS_134;
        const __VLS_135 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.viewDocument(record);
            }
        };
        __VLS_131.slots.default;
        var __VLS_131;
        const __VLS_136 = {}.Button;
        /** @type {[typeof __VLS_components.Button, typeof __VLS_components.Button, ]} */ ;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_138 = __VLS_137({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_137));
        let __VLS_140;
        let __VLS_141;
        let __VLS_142;
        const __VLS_143 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.editDocument(record);
            }
        };
        __VLS_139.slots.default;
        var __VLS_139;
        const __VLS_144 = {}.Button;
        /** @type {[typeof __VLS_components.Button, typeof __VLS_components.Button, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
            ...{ 'onClick': {} },
            size: "small",
            danger: true,
        }));
        const __VLS_146 = __VLS_145({
            ...{ 'onClick': {} },
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_145));
        let __VLS_148;
        let __VLS_149;
        let __VLS_150;
        const __VLS_151 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.deleteDocument(record);
            }
        };
        __VLS_147.slots.default;
        var __VLS_147;
        var __VLS_127;
    }
}
var __VLS_107;
var __VLS_55;
const __VLS_152 = {}.Modal;
/** @type {[typeof __VLS_components.Modal, typeof __VLS_components.Modal, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
    open: (__VLS_ctx.documentModalVisible),
    title: (__VLS_ctx.currentDocument?.title || '文档详情'),
    width: "80%",
    footer: (null),
}));
const __VLS_154 = __VLS_153({
    open: (__VLS_ctx.documentModalVisible),
    title: (__VLS_ctx.currentDocument?.title || '文档详情'),
    width: "80%",
    footer: (null),
}, ...__VLS_functionalComponentArgsRest(__VLS_153));
__VLS_155.slots.default;
if (__VLS_ctx.currentDocument) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "document-detail" },
    });
    const __VLS_156 = {}.Descriptions;
    /** @type {[typeof __VLS_components.Descriptions, typeof __VLS_components.Descriptions, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        column: (2),
        bordered: true,
    }));
    const __VLS_158 = __VLS_157({
        column: (2),
        bordered: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    const __VLS_160 = {}.DescriptionsItem;
    /** @type {[typeof __VLS_components.DescriptionsItem, typeof __VLS_components.DescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        label: "文档类型",
    }));
    const __VLS_162 = __VLS_161({
        label: "文档类型",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    __VLS_163.slots.default;
    const __VLS_164 = {}.Tag;
    /** @type {[typeof __VLS_components.Tag, typeof __VLS_components.Tag, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        color: (__VLS_ctx.getDocumentTypeColor(__VLS_ctx.currentDocument.document_type)),
    }));
    const __VLS_166 = __VLS_165({
        color: (__VLS_ctx.getDocumentTypeColor(__VLS_ctx.currentDocument.document_type)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    (__VLS_ctx.getDocumentTypeText(__VLS_ctx.currentDocument.document_type));
    var __VLS_167;
    var __VLS_163;
    const __VLS_168 = {}.DescriptionsItem;
    /** @type {[typeof __VLS_components.DescriptionsItem, typeof __VLS_components.DescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        label: "处理状态",
    }));
    const __VLS_170 = __VLS_169({
        label: "处理状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    const __VLS_172 = {}.Tag;
    /** @type {[typeof __VLS_components.Tag, typeof __VLS_components.Tag, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        color: (__VLS_ctx.getStatusColor(__VLS_ctx.currentDocument.processing_status)),
    }));
    const __VLS_174 = __VLS_173({
        color: (__VLS_ctx.getStatusColor(__VLS_ctx.currentDocument.processing_status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
    __VLS_175.slots.default;
    (__VLS_ctx.getStatusText(__VLS_ctx.currentDocument.processing_status));
    var __VLS_175;
    var __VLS_171;
    const __VLS_176 = {}.DescriptionsItem;
    /** @type {[typeof __VLS_components.DescriptionsItem, typeof __VLS_components.DescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
        label: "质控状态",
    }));
    const __VLS_178 = __VLS_177({
        label: "质控状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_177));
    __VLS_179.slots.default;
    const __VLS_180 = {}.Tag;
    /** @type {[typeof __VLS_components.Tag, typeof __VLS_components.Tag, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        color: (__VLS_ctx.getQCStatusColor(__VLS_ctx.currentDocument.qc_status)),
    }));
    const __VLS_182 = __VLS_181({
        color: (__VLS_ctx.getQCStatusColor(__VLS_ctx.currentDocument.qc_status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    __VLS_183.slots.default;
    (__VLS_ctx.getQCStatusText(__VLS_ctx.currentDocument.qc_status));
    var __VLS_183;
    var __VLS_179;
    const __VLS_184 = {}.DescriptionsItem;
    /** @type {[typeof __VLS_components.DescriptionsItem, typeof __VLS_components.DescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
        label: "分类",
    }));
    const __VLS_186 = __VLS_185({
        label: "分类",
    }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    __VLS_187.slots.default;
    (__VLS_ctx.currentDocument.category || '未分类');
    var __VLS_187;
    const __VLS_188 = {}.DescriptionsItem;
    /** @type {[typeof __VLS_components.DescriptionsItem, typeof __VLS_components.DescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        label: "内容长度",
    }));
    const __VLS_190 = __VLS_189({
        label: "内容长度",
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    __VLS_191.slots.default;
    (__VLS_ctx.currentDocument.content_length);
    var __VLS_191;
    const __VLS_192 = {}.DescriptionsItem;
    /** @type {[typeof __VLS_components.DescriptionsItem, typeof __VLS_components.DescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
        label: "创建时间",
    }));
    const __VLS_194 = __VLS_193({
        label: "创建时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_193));
    __VLS_195.slots.default;
    (__VLS_ctx.formatDate(__VLS_ctx.currentDocument.created_at));
    var __VLS_195;
    var __VLS_159;
    const __VLS_196 = {}.Divider;
    /** @type {[typeof __VLS_components.Divider, typeof __VLS_components.Divider, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({}));
    const __VLS_198 = __VLS_197({}, ...__VLS_functionalComponentArgsRest(__VLS_197));
    __VLS_199.slots.default;
    var __VLS_199;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "document-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
    (__VLS_ctx.currentDocument.raw_content);
    if (__VLS_ctx.currentDocument.extracted_data && Object.keys(__VLS_ctx.currentDocument.extracted_data).length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        const __VLS_200 = {}.Divider;
        /** @type {[typeof __VLS_components.Divider, typeof __VLS_components.Divider, ]} */ ;
        // @ts-ignore
        const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({}));
        const __VLS_202 = __VLS_201({}, ...__VLS_functionalComponentArgsRest(__VLS_201));
        __VLS_203.slots.default;
        var __VLS_203;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
        (JSON.stringify(__VLS_ctx.currentDocument.extracted_data, null, 2));
    }
}
var __VLS_155;
/** @type {__VLS_StyleScopedClasses['unstructured-documents-view']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-add-card']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-add-form']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['form-row']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-list-card']} */ ;
/** @type {__VLS_StyleScopedClasses['document-title']} */ ;
/** @type {__VLS_StyleScopedClasses['document-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['content-length']} */ ;
/** @type {__VLS_StyleScopedClasses['document-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['document-content']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            Card: ant_design_vue_1.Card,
            Table: ant_design_vue_1.Table,
            Button: ant_design_vue_1.Button,
            Input: ant_design_vue_1.Input,
            TextArea: ant_design_vue_1.Textarea,
            Select: ant_design_vue_1.Select,
            SelectOption: ant_design_vue_1.SelectOption,
            Space: ant_design_vue_1.Space,
            Tag: ant_design_vue_1.Tag,
            Modal: ant_design_vue_1.Modal,
            Descriptions: ant_design_vue_1.Descriptions,
            DescriptionsItem: ant_design_vue_1.DescriptionsItem,
            Divider: ant_design_vue_1.Divider,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            documents: documents,
            loading: loading,
            saving: saving,
            searchTerm: searchTerm,
            documentModalVisible: documentModalVisible,
            currentDocument: currentDocument,
            newDocument: newDocument,
            filters: filters,
            pagination: pagination,
            columns: columns,
            loadDocuments: loadDocuments,
            saveDocument: saveDocument,
            handleSearch: handleSearch,
            viewDocument: viewDocument,
            editDocument: editDocument,
            deleteDocument: deleteDocument,
            handleTableChange: handleTableChange,
            getDocumentTypeColor: getDocumentTypeColor,
            getDocumentTypeText: getDocumentTypeText,
            getStatusColor: getStatusColor,
            getStatusText: getStatusText,
            getQCStatusColor: getQCStatusColor,
            getQCStatusText: getQCStatusText,
            formatDate: formatDate,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
