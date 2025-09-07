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
import vue_router_1 from 'vue-router';
import ant_design_vue_1 from 'ant-design-vue';
const LLMResultModal_vue_1 = __importDefault(require("@/components/LLMResultModal.vue"));
import llmParse_1 from '@/stores/llmParse';
const router = (0, vue_router_1.useRouter)();
const store = (0, llmParse_1.useLLMParseStore)();
// 响应式数据
const testing = (0, vue_1.ref)(false);
const mergedResult = (0, vue_1.ref)(null);
const showModal = (0, vue_1.ref)(false);
// 模拟的多文档解析结果
const mockResults = [
    {
        documentType: '手术记录',
        sourceFile: '手术记录_张三_20231201.pdf',
        parseTime: '2023-12-01 10:30:00',
        data: {
            patientName: '张三',
            department: '外科',
            primaryDiagnosis: '阑尾炎',
            content: '患者张三，男，35岁，因急性阑尾炎入院。手术过程：在全麻下行腹腔镜阑尾切除术，手术顺利，术后恢复良好。术中见阑尾充血水肿，周围有少量渗出。',
            confidence: 0.95,
            pages: 2,
            method: 'PDF解析'
        }
    },
    {
        documentType: '入院记录',
        sourceFile: '入院记录_张三_20231130.pdf',
        parseTime: '2023-11-30 14:20:00',
        data: {
            patientName: '张三',
            department: '外科',
            primaryDiagnosis: '急性阑尾炎',
            content: '患者张三，男，35岁，主诉右下腹痛2天。现病史：患者2天前无明显诱因出现右下腹痛，呈持续性钝痛。体格检查：右下腹压痛明显，反跳痛阳性。',
            confidence: 0.92,
            pages: 3,
            method: 'PDF解析'
        }
    },
    {
        documentType: '检验报告',
        sourceFile: '血常规_张三_20231130.pdf',
        parseTime: '2023-11-30 16:45:00',
        data: {
            patientName: '张三',
            department: '检验科',
            content: '血常规检查结果：白细胞计数：12.5×10^9/L（升高），中性粒细胞比例：85%（升高），血红蛋白：135g/L（正常），血小板计数：280×10^9/L（正常）。',
            confidence: 0.88,
            pages: 1,
            method: 'PDF解析'
        }
    }
];
// 映射文档类型到标准类型
const mapDocumentType = (docType) => {
    const typeMapping = {
        '手术记录': 'operation_record',
        '入院记录': 'admission_record',
        '病程记录': 'progress_note',
        '出院记录': 'discharge_record',
        '检验报告': 'auxiliary_examination',
        '检查报告': 'auxiliary_examination',
        '知情同意书': 'informed_consent',
        '医嘱': 'medical_order',
        '护理记录': 'nursing_record'
    };
    return typeMapping[docType] || 'other';
};
// 合并多个解析结果
const mergeMultipleResults = (results) => {
    if (results.length === 0)
        return null;
    if (results.length === 1)
        return results[0];
    // 收集所有患者信息，取最完整的
    const allPatientNames = results.map(r => r.data?.patientName).filter(Boolean);
    const allDepartments = results.map(r => r.data?.department).filter(Boolean);
    const allDiagnoses = results.map(r => r.data?.primaryDiagnosis).filter(Boolean);
    // 按文档类型分组
    const documentsByType = {};
    const allDocuments = [];
    results.forEach((result, index) => {
        const docType = result.documentType;
        const sourceFile = result.sourceFile;
        if (!documentsByType[docType]) {
            documentsByType[docType] = [];
        }
        // 创建符合 ExtractedDocument 接口的文档对象
        const docInfo = {
            id: `doc_${index}`,
            type: mapDocumentType(docType), // 映射到标准文档类型
            title: `${sourceFile} - ${docType}`,
            content: result.data?.content || '',
            confidence: result.data?.confidence || 0.8,
            extractedAt: new Date().toISOString(),
            position: {
                startIndex: 0,
                endIndex: (result.data?.content || '').length,
                fullContent: result.data?.content || ''
            },
            metadata: {
                sourceFile: sourceFile,
                parseTime: result.parseTime,
                method: result.data?.method || '文件解析',
                pages: result.data?.pages || 1
            }
        };
        documentsByType[docType].push(docInfo);
        allDocuments.push(docInfo);
    });
    // 合并内容
    const mergedContent = results.map(r => {
        const content = r.data?.content || '';
        return `=== ${r.sourceFile} (${r.documentType}) ===\n${content}\n`;
    }).join('\n');
    return {
        success: true,
        data: {
            patientName: allPatientNames[0] || '未识别',
            department: allDepartments[0] || '未识别',
            primaryDiagnosis: allDiagnoses[0] || '未识别',
            content: mergedContent,
            method: '批量文件解析',
            pages: results.reduce((sum, r) => sum + (r.data?.pages || 1), 0),
            documents: allDocuments, // 符合 ExtractedDocument[] 格式
            documentsByType: documentsByType,
            sourceFiles: results.map(r => r.sourceFile),
            totalFiles: results.length,
            confidence: results.reduce((sum, r) => sum + (r.data?.confidence || 0.8), 0) / results.length
        },
        isMerged: true,
        mergeTime: new Date().toLocaleString()
    };
};
// 运行合并测试
const runMergeTest = async () => {
    testing.value = true;
    try {
        await new Promise(resolve => setTimeout(resolve, 500)); // 模拟异步处理
        mergedResult.value = mergeMultipleResults(mockResults);
        ant_design_vue_1.message.success('合并测试完成');
    }
    catch (error) {
        ant_design_vue_1.message.error('合并测试失败: ' + error);
    }
    finally {
        testing.value = false;
    }
};
// 显示LLM结果页面
const showLLMResult = () => {
    if (!mergedResult.value)
        return;
    // 保存到store并跳转
    store.setResult(mergedResult.value);
    router.push('/dashboard/llm-result');
};
// 显示Modal
const showModalTest = () => {
    if (!mergedResult.value)
        return;
    showModal.value = true;
};
// 清除结果
const clearResults = () => {
    mergedResult.value = null;
    ant_design_vue_1.message.info('结果已清除');
};
// 事件处理
const handleSave = () => {
    ant_design_vue_1.message.success('保存功能测试');
};
const handleExport = () => {
    ant_design_vue_1.message.success('导出功能测试');
};
const handleExportPDF = () => {
    ant_design_vue_1.message.success('PDF导出功能测试');
};
const handleGoToImport = () => {
    router.push('/dashboard/medical-records/smart-import-simple');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "test-page" },
});
const __VLS_0 = {}.APageHeader;
/** @type {[typeof __VLS_components.APageHeader, typeof __VLS_components.aPageHeader, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "多文档合并测试",
    subTitle: "测试多文档解析结果的合并和展示功能",
}));
const __VLS_2 = __VLS_1({
    title: "多文档合并测试",
    subTitle: "测试多文档解析结果的合并和展示功能",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
const __VLS_4 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    title: "测试控制面板",
    ...{ class: "mb-4" },
}));
const __VLS_6 = __VLS_5({
    title: "测试控制面板",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.testing),
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.testing),
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (__VLS_ctx.runMergeTest)
};
__VLS_15.slots.default;
var __VLS_15;
const __VLS_20 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    disabled: (!__VLS_ctx.mergedResult),
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    disabled: (!__VLS_ctx.mergedResult),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.showLLMResult)
};
__VLS_23.slots.default;
var __VLS_23;
const __VLS_28 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ 'onClick': {} },
}));
const __VLS_30 = __VLS_29({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
let __VLS_32;
let __VLS_33;
let __VLS_34;
const __VLS_35 = {
    onClick: (__VLS_ctx.clearResults)
};
__VLS_31.slots.default;
var __VLS_31;
var __VLS_11;
var __VLS_7;
const __VLS_36 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    gutter: (16),
}));
const __VLS_38 = __VLS_37({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
const __VLS_40 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    span: (12),
}));
const __VLS_42 = __VLS_41({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
const __VLS_44 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    title: "模拟原始解析结果",
    size: "small",
}));
const __VLS_46 = __VLS_45({
    title: "模拟原始解析结果",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
    ...{ class: "json-display" },
});
(JSON.stringify(__VLS_ctx.mockResults, null, 2));
var __VLS_47;
var __VLS_43;
const __VLS_48 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    span: (12),
}));
const __VLS_50 = __VLS_49({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    title: "合并后结果",
    size: "small",
}));
const __VLS_54 = __VLS_53({
    title: "合并后结果",
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
if (__VLS_ctx.mergedResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_56 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        size: "small",
        bordered: true,
    }));
    const __VLS_58 = __VLS_57({
        size: "small",
        bordered: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    const __VLS_60 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        label: "患者姓名",
    }));
    const __VLS_62 = __VLS_61({
        label: "患者姓名",
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    (__VLS_ctx.mergedResult.data.patientName);
    var __VLS_63;
    const __VLS_64 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        label: "科室",
    }));
    const __VLS_66 = __VLS_65({
        label: "科室",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    (__VLS_ctx.mergedResult.data.department);
    var __VLS_67;
    const __VLS_68 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        label: "主要诊断",
    }));
    const __VLS_70 = __VLS_69({
        label: "主要诊断",
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_71.slots.default;
    (__VLS_ctx.mergedResult.data.primaryDiagnosis);
    var __VLS_71;
    const __VLS_72 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        label: "文档总数",
    }));
    const __VLS_74 = __VLS_73({
        label: "文档总数",
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    __VLS_75.slots.default;
    (__VLS_ctx.mergedResult.data.totalFiles);
    var __VLS_75;
    const __VLS_76 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        label: "合并时间",
    }));
    const __VLS_78 = __VLS_77({
        label: "合并时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    (__VLS_ctx.mergedResult.mergeTime);
    var __VLS_79;
    var __VLS_59;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "mt-3" },
    });
    (__VLS_ctx.mergedResult.data.documents.length);
    const __VLS_80 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        size: "small",
        dataSource: (__VLS_ctx.mergedResult.data.documents),
    }));
    const __VLS_82 = __VLS_81({
        size: "small",
        dataSource: (__VLS_ctx.mergedResult.data.documents),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_83.slots;
        const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_84 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
        const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
        __VLS_87.slots.default;
        const __VLS_88 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
            title: (item.title),
            description: (`类型: ${item.type} | 置信度: ${Math.round(item.confidence * 100)}% | 源文件: ${item.metadata.sourceFile}`),
        }));
        const __VLS_90 = __VLS_89({
            title: (item.title),
            description: (`类型: ${item.type} | 置信度: ${Math.round(item.confidence * 100)}% | 源文件: ${item.metadata.sourceFile}`),
        }, ...__VLS_functionalComponentArgsRest(__VLS_89));
        var __VLS_87;
    }
    var __VLS_83;
}
else {
    const __VLS_92 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        description: "暂无合并结果",
    }));
    const __VLS_94 = __VLS_93({
        description: "暂无合并结果",
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
}
var __VLS_55;
var __VLS_51;
var __VLS_39;
if (__VLS_ctx.showModal) {
    /** @type {[typeof LLMResultModal, ]} */ ;
    // @ts-ignore
    const __VLS_96 = __VLS_asFunctionalComponent(LLMResultModal_vue_1.default, new LLMResultModal_vue_1.default({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (__VLS_ctx.showModal),
        data: (__VLS_ctx.mergedResult?.data),
        result: (__VLS_ctx.mergedResult),
        originalText: (__VLS_ctx.mergedResult?.data?.content),
    }));
    const __VLS_97 = __VLS_96({
        ...{ 'onUpdate:visible': {} },
        ...{ 'onSaveAndRedirect': {} },
        ...{ 'onSaveOnly': {} },
        ...{ 'onExportResult': {} },
        ...{ 'onExportPdf': {} },
        ...{ 'onGoToImport': {} },
        visible: (__VLS_ctx.showModal),
        data: (__VLS_ctx.mergedResult?.data),
        result: (__VLS_ctx.mergedResult),
        originalText: (__VLS_ctx.mergedResult?.data?.content),
    }, ...__VLS_functionalComponentArgsRest(__VLS_96));
    let __VLS_99;
    let __VLS_100;
    let __VLS_101;
    const __VLS_102 = {
        'onUpdate:visible': (...[$event]) => {
            if (!(__VLS_ctx.showModal))
                return;
            __VLS_ctx.showModal = false;
        }
    };
    const __VLS_103 = {
        onSaveAndRedirect: (__VLS_ctx.handleSave)
    };
    const __VLS_104 = {
        onSaveOnly: (__VLS_ctx.handleSave)
    };
    const __VLS_105 = {
        onExportResult: (__VLS_ctx.handleExport)
    };
    const __VLS_106 = {
        onExportPdf: (__VLS_ctx.handleExportPDF)
    };
    const __VLS_107 = {
        onGoToImport: (__VLS_ctx.handleGoToImport)
    };
    var __VLS_98;
}
/** @type {__VLS_StyleScopedClasses['test-page']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['json-display']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            LLMResultModal: LLMResultModal_vue_1.default,
            testing: testing,
            mergedResult: mergedResult,
            showModal: showModal,
            mockResults: mockResults,
            runMergeTest: runMergeTest,
            showLLMResult: showLLMResult,
            clearResults: clearResults,
            handleSave: handleSave,
            handleExport: handleExport,
            handleExportPDF: handleExportPDF,
            handleGoToImport: handleGoToImport,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
