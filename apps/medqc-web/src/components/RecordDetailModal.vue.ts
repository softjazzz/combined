"use strict";
/// <reference types="../../node_modules/.vue-global-types/vue_3.5_0_0_0.d.ts" />
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
const props = withDefaults(defineProps(), {
    visible: false,
    viewType: 'records'
});
const emit = defineEmits();
const activeTab = (0, vue_1.ref)('basic');
const activeSections = (0, vue_1.ref)(['1', '2']);
// 模态框标题
const modalTitle = (0, vue_1.computed)(() => {
    if (!props.record)
        return '详情';
    return `${props.viewType === 'records' ? '病历' : '缺陷'}详情 - ${props.record.registrationNo}`;
});
// 缺陷列表列配置
const defectColumns = [
    { title: '缺陷类型', dataIndex: 'defectType', key: 'defectType', width: 120 },
    { title: '缺陷描述', dataIndex: 'defectDescription', key: 'defectDescription' },
    { title: '优先级', dataIndex: 'priority', key: 'priority', width: 80 },
    { title: '状态', dataIndex: 'defectStatus', key: 'defectStatus', width: 100 },
    { title: '创建时间', dataIndex: 'createTime', key: 'createTime', width: 150 },
    { title: '操作', key: 'action', width: 100 }
];
// 模拟数据
const defectList = (0, vue_1.ref)([
    {
        id: '1',
        defectType: '诊断不完整',
        defectDescription: '主要诊断缺少具体分型',
        priority: 'high',
        defectStatus: 'pending',
        createTime: '2024-01-15 10:30:00'
    },
    {
        id: '2',
        defectType: '用药记录',
        defectDescription: '抗生素使用未记录过敏史',
        priority: 'medium',
        defectStatus: 'rectified',
        createTime: '2024-01-15 11:00:00'
    }
]);
const documentSections = (0, vue_1.ref)([
    {
        id: '1',
        name: '入院记录',
        type: 'admission',
        content: '<p>患者因"胸痛3小时"入院...</p><p>既往史：高血压病史5年...</p>',
        defects: [defectList.value[0]]
    },
    {
        id: '2',
        name: '病程记录',
        type: 'progress',
        content: '<p>2024-01-15 入院第1天...</p><p>患者一般情况可...</p>',
        defects: [defectList.value[1]]
    }
]);
const operationHistory = (0, vue_1.ref)([
    {
        id: '1',
        type: 'audit',
        operator: '质控医生A',
        operateTime: '2024-01-15 14:30:00',
        description: '进行质控审核',
        result: '发现2处缺陷'
    },
    {
        id: '2',
        type: 'urge',
        operator: '质控医生A',
        operateTime: '2024-01-15 15:00:00',
        description: '催办整改',
        result: '已通知临床医生'
    }
]);
// 状态颜色和文本映射
const getAuditStatusColor = (status) => {
    const colorMap = {
        pending: 'orange',
        reviewing: 'blue',
        passed: 'green',
        questioned: 'red'
    };
    return colorMap[status] || 'default';
};
const getAuditStatusText = (status) => {
    const textMap = {
        pending: '待审核',
        reviewing: '审核中',
        passed: '已通过',
        questioned: '存疑'
    };
    return textMap[status] || status;
};
const getPriorityColor = (priority) => {
    const colorMap = {
        high: 'red',
        medium: 'orange',
        low: 'green'
    };
    return colorMap[priority] || 'default';
};
const getPriorityText = (priority) => {
    const textMap = {
        high: '高',
        medium: '中',
        low: '低'
    };
    return textMap[priority] || priority;
};
const getDefectStatusColor = (status) => {
    const colorMap = {
        pending: 'orange',
        urged: 'red',
        rectified: 'green',
        appealed: 'purple'
    };
    return colorMap[status] || 'default';
};
const getDefectStatusText = (status) => {
    const textMap = {
        pending: '待整改',
        urged: '已催办',
        rectified: '已整改',
        appealed: '已申诉'
    };
    return textMap[status] || status;
};
const getOperationColor = (type) => {
    const colorMap = {
        audit: 'blue',
        urge: 'orange',
        rectify: 'green',
        comment: 'purple'
    };
    return colorMap[type] || 'gray';
};
const getOperationText = (type) => {
    const textMap = {
        audit: '质控审核',
        urge: '催办整改',
        rectify: '缺陷整改',
        comment: '添加备注'
    };
    return textMap[type] || type;
};
// 事件处理
const handleCancel = () => {
    emit('update:visible', false);
};
const handleDefectDetail = (defect) => {
    ant_design_vue_1.message.info(`查看缺陷详情: ${defect.defectType}`);
};
const handleViewFullDocument = () => {
    ant_design_vue_1.message.info('打开完整病历查看器');
};
const handlePrintDocument = () => {
    ant_design_vue_1.message.info('打印病历');
};
const handleDownloadDocument = () => {
    ant_design_vue_1.message.info('下载病历文档');
};
const handleAudit = () => {
    ant_design_vue_1.message.info('进入审核流程');
};
const handleUrge = () => {
    ant_design_vue_1.message.info('发送催办通知');
};
const handleExportDetail = () => {
    ant_design_vue_1.message.info('导出详情报告');
};
// 监听visible变化，重置activeTab
(0, vue_1.watch)(() => props.visible, (newVal) => {
    if (newVal) {
        activeTab.value = 'basic';
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    visible: false,
    viewType: 'records'
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['defect-item']} */ ;
// CSS variable injection 
// CSS variable injection end 
const __VLS_0 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onCancel': {} },
    visible: (props.visible),
    title: (__VLS_ctx.modalTitle),
    width: "1200px",
    footer: (null),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onCancel': {} },
    visible: (props.visible),
    title: (__VLS_ctx.modalTitle),
    width: "1200px",
    footer: (null),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onCancel: (__VLS_ctx.handleCancel)
};
var __VLS_8 = {};
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "record-detail-content" },
});
const __VLS_9 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(__VLS_9, new __VLS_9({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
}));
const __VLS_11 = __VLS_10({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
__VLS_12.slots.default;
const __VLS_13 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent(__VLS_13, new __VLS_13({
    key: "basic",
    tab: "基本信息",
}));
const __VLS_15 = __VLS_14({
    key: "basic",
    tab: "基本信息",
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
__VLS_16.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "basic-info" },
});
const __VLS_17 = {}.ADescriptions;
/** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
// @ts-ignore
const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({
    column: (2),
    bordered: true,
}));
const __VLS_19 = __VLS_18({
    column: (2),
    bordered: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_18));
__VLS_20.slots.default;
const __VLS_21 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_22 = __VLS_asFunctionalComponent(__VLS_21, new __VLS_21({
    label: "登记号",
}));
const __VLS_23 = __VLS_22({
    label: "登记号",
}, ...__VLS_functionalComponentArgsRest(__VLS_22));
__VLS_24.slots.default;
(__VLS_ctx.record?.registrationNo);
var __VLS_24;
const __VLS_25 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent(__VLS_25, new __VLS_25({
    label: "流水号",
}));
const __VLS_27 = __VLS_26({
    label: "流水号",
}, ...__VLS_functionalComponentArgsRest(__VLS_26));
__VLS_28.slots.default;
(__VLS_ctx.record?.serialNo);
var __VLS_28;
const __VLS_29 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({
    label: "病案号",
}));
const __VLS_31 = __VLS_30({
    label: "病案号",
}, ...__VLS_functionalComponentArgsRest(__VLS_30));
__VLS_32.slots.default;
(__VLS_ctx.record?.caseNo);
var __VLS_32;
const __VLS_33 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
    label: "患者姓名",
}));
const __VLS_35 = __VLS_34({
    label: "患者姓名",
}, ...__VLS_functionalComponentArgsRest(__VLS_34));
__VLS_36.slots.default;
(__VLS_ctx.record?.patientName);
var __VLS_36;
const __VLS_37 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_38 = __VLS_asFunctionalComponent(__VLS_37, new __VLS_37({
    label: "科室",
}));
const __VLS_39 = __VLS_38({
    label: "科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_38));
__VLS_40.slots.default;
(__VLS_ctx.record?.department);
var __VLS_40;
const __VLS_41 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({
    label: "临床医生",
}));
const __VLS_43 = __VLS_42({
    label: "临床医生",
}, ...__VLS_functionalComponentArgsRest(__VLS_42));
__VLS_44.slots.default;
(__VLS_ctx.record?.doctor);
var __VLS_44;
const __VLS_45 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({
    label: "审核状态",
}));
const __VLS_47 = __VLS_46({
    label: "审核状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_46));
__VLS_48.slots.default;
const __VLS_49 = {}.ATag;
/** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
// @ts-ignore
const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
    color: (__VLS_ctx.getAuditStatusColor(__VLS_ctx.record?.auditStatus)),
}));
const __VLS_51 = __VLS_50({
    color: (__VLS_ctx.getAuditStatusColor(__VLS_ctx.record?.auditStatus)),
}, ...__VLS_functionalComponentArgsRest(__VLS_50));
__VLS_52.slots.default;
(__VLS_ctx.getAuditStatusText(__VLS_ctx.record?.auditStatus));
var __VLS_52;
var __VLS_48;
const __VLS_53 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_54 = __VLS_asFunctionalComponent(__VLS_53, new __VLS_53({
    label: "评分",
}));
const __VLS_55 = __VLS_54({
    label: "评分",
}, ...__VLS_functionalComponentArgsRest(__VLS_54));
__VLS_56.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "score-value" },
});
(__VLS_ctx.record?.score);
var __VLS_56;
const __VLS_57 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
    label: "评分标准",
}));
const __VLS_59 = __VLS_58({
    label: "评分标准",
}, ...__VLS_functionalComponentArgsRest(__VLS_58));
__VLS_60.slots.default;
(__VLS_ctx.record?.scoringStandard);
var __VLS_60;
const __VLS_61 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_62 = __VLS_asFunctionalComponent(__VLS_61, new __VLS_61({
    label: "缺陷数量",
}));
const __VLS_63 = __VLS_62({
    label: "缺陷数量",
}, ...__VLS_functionalComponentArgsRest(__VLS_62));
__VLS_64.slots.default;
const __VLS_65 = {}.ABadge;
/** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
// @ts-ignore
const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({
    count: (__VLS_ctx.record?.defectCount),
    numberStyle: ({ backgroundColor: '#f50' }),
}));
const __VLS_67 = __VLS_66({
    count: (__VLS_ctx.record?.defectCount),
    numberStyle: ({ backgroundColor: '#f50' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_66));
var __VLS_64;
const __VLS_69 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({
    label: "创建时间",
}));
const __VLS_71 = __VLS_70({
    label: "创建时间",
}, ...__VLS_functionalComponentArgsRest(__VLS_70));
__VLS_72.slots.default;
(__VLS_ctx.record?.createTime);
var __VLS_72;
const __VLS_73 = {}.ADescriptionsItem;
/** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
// @ts-ignore
const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({
    label: "更新时间",
}));
const __VLS_75 = __VLS_74({
    label: "更新时间",
}, ...__VLS_functionalComponentArgsRest(__VLS_74));
__VLS_76.slots.default;
(__VLS_ctx.record?.updateTime);
var __VLS_76;
var __VLS_20;
var __VLS_16;
const __VLS_77 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
    key: "defects",
    tab: "缺陷列表",
}));
const __VLS_79 = __VLS_78({
    key: "defects",
    tab: "缺陷列表",
}, ...__VLS_functionalComponentArgsRest(__VLS_78));
__VLS_80.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "defects-list" },
});
const __VLS_81 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_82 = __VLS_asFunctionalComponent(__VLS_81, new __VLS_81({
    columns: (__VLS_ctx.defectColumns),
    dataSource: (__VLS_ctx.defectList),
    pagination: (false),
    size: "small",
    rowKey: "id",
}));
const __VLS_83 = __VLS_82({
    columns: (__VLS_ctx.defectColumns),
    dataSource: (__VLS_ctx.defectList),
    pagination: (false),
    size: "small",
    rowKey: "id",
}, ...__VLS_functionalComponentArgsRest(__VLS_82));
__VLS_84.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_84.slots;
    const { column, record: defect } = __VLS_getSlotParam(__VLS_thisSlot);
    if (column.key === 'defectType') {
        const __VLS_85 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
            color: "blue",
        }));
        const __VLS_87 = __VLS_86({
            color: "blue",
        }, ...__VLS_functionalComponentArgsRest(__VLS_86));
        __VLS_88.slots.default;
        (defect.defectType);
        var __VLS_88;
    }
    if (column.key === 'priority') {
        const __VLS_89 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({
            color: (__VLS_ctx.getPriorityColor(defect.priority)),
        }));
        const __VLS_91 = __VLS_90({
            color: (__VLS_ctx.getPriorityColor(defect.priority)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_90));
        __VLS_92.slots.default;
        (__VLS_ctx.getPriorityText(defect.priority));
        var __VLS_92;
    }
    if (column.key === 'defectStatus') {
        const __VLS_93 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({
            color: (__VLS_ctx.getDefectStatusColor(defect.defectStatus)),
        }));
        const __VLS_95 = __VLS_94({
            color: (__VLS_ctx.getDefectStatusColor(defect.defectStatus)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_94));
        __VLS_96.slots.default;
        (__VLS_ctx.getDefectStatusText(defect.defectStatus));
        var __VLS_96;
    }
    if (column.key === 'action') {
        const __VLS_97 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_99 = __VLS_98({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_98));
        let __VLS_101;
        let __VLS_102;
        let __VLS_103;
        const __VLS_104 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleDefectDetail(defect);
            }
        };
        __VLS_100.slots.default;
        var __VLS_100;
    }
}
var __VLS_84;
var __VLS_80;
const __VLS_105 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({
    key: "document",
    tab: "电子病历",
}));
const __VLS_107 = __VLS_106({
    key: "document",
    tab: "电子病历",
}, ...__VLS_functionalComponentArgsRest(__VLS_106));
__VLS_108.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "document-viewer" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "document-toolbar mb-4" },
});
const __VLS_109 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({}));
const __VLS_111 = __VLS_110({}, ...__VLS_functionalComponentArgsRest(__VLS_110));
__VLS_112.slots.default;
const __VLS_113 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_115 = __VLS_114({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_114));
let __VLS_117;
let __VLS_118;
let __VLS_119;
const __VLS_120 = {
    onClick: (__VLS_ctx.handleViewFullDocument)
};
__VLS_116.slots.default;
const __VLS_121 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({}));
const __VLS_123 = __VLS_122({}, ...__VLS_functionalComponentArgsRest(__VLS_122));
var __VLS_116;
const __VLS_125 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({
    ...{ 'onClick': {} },
}));
const __VLS_127 = __VLS_126({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_126));
let __VLS_129;
let __VLS_130;
let __VLS_131;
const __VLS_132 = {
    onClick: (__VLS_ctx.handlePrintDocument)
};
__VLS_128.slots.default;
const __VLS_133 = {}.PrinterOutlined;
/** @type {[typeof __VLS_components.PrinterOutlined, ]} */ ;
// @ts-ignore
const __VLS_134 = __VLS_asFunctionalComponent(__VLS_133, new __VLS_133({}));
const __VLS_135 = __VLS_134({}, ...__VLS_functionalComponentArgsRest(__VLS_134));
var __VLS_128;
const __VLS_137 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_138 = __VLS_asFunctionalComponent(__VLS_137, new __VLS_137({
    ...{ 'onClick': {} },
}));
const __VLS_139 = __VLS_138({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_138));
let __VLS_141;
let __VLS_142;
let __VLS_143;
const __VLS_144 = {
    onClick: (__VLS_ctx.handleDownloadDocument)
};
__VLS_140.slots.default;
const __VLS_145 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({}));
const __VLS_147 = __VLS_146({}, ...__VLS_functionalComponentArgsRest(__VLS_146));
var __VLS_140;
var __VLS_112;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "document-sections" },
});
const __VLS_149 = {}.ACollapse;
/** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
// @ts-ignore
const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
    activeKey: (__VLS_ctx.activeSections),
    ghost: true,
}));
const __VLS_151 = __VLS_150({
    activeKey: (__VLS_ctx.activeSections),
    ghost: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_150));
__VLS_152.slots.default;
for (const [section] of __VLS_getVForSourceType((__VLS_ctx.documentSections))) {
    const __VLS_153 = {}.ACollapsePanel;
    /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
    // @ts-ignore
    const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({
        key: (section.id),
        header: (section.name),
    }));
    const __VLS_155 = __VLS_154({
        key: (section.id),
        header: (section.name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_154));
    __VLS_156.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "section-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "section-text" },
    });
    __VLS_asFunctionalDirective(__VLS_directives.vHtml)(null, { ...__VLS_directiveBindingRestFields, value: (section.content) }, null, null);
    if (section.defects && section.defects.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-defects mt-4" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
            ...{ class: "text-red-600 mb-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "defect-items" },
        });
        for (const [defect] of __VLS_getVForSourceType((section.defects))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (defect.id),
                ...{ class: "defect-item p-3 bg-red-50 border border-red-200 rounded mb-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "defect-header flex justify-between items-center mb-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "defect-type font-medium" },
            });
            (defect.defectType);
            const __VLS_157 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
                color: (__VLS_ctx.getPriorityColor(defect.priority)),
            }));
            const __VLS_159 = __VLS_158({
                color: (__VLS_ctx.getPriorityColor(defect.priority)),
            }, ...__VLS_functionalComponentArgsRest(__VLS_158));
            __VLS_160.slots.default;
            (__VLS_ctx.getPriorityText(defect.priority));
            var __VLS_160;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "defect-description text-gray-700" },
            });
            (defect.defectDescription);
        }
    }
    var __VLS_156;
}
var __VLS_152;
var __VLS_108;
const __VLS_161 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
    key: "history",
    tab: "操作历史",
}));
const __VLS_163 = __VLS_162({
    key: "history",
    tab: "操作历史",
}, ...__VLS_functionalComponentArgsRest(__VLS_162));
__VLS_164.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "operation-history" },
});
const __VLS_165 = {}.ATimeline;
/** @type {[typeof __VLS_components.ATimeline, typeof __VLS_components.aTimeline, typeof __VLS_components.ATimeline, typeof __VLS_components.aTimeline, ]} */ ;
// @ts-ignore
const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({}));
const __VLS_167 = __VLS_166({}, ...__VLS_functionalComponentArgsRest(__VLS_166));
__VLS_168.slots.default;
for (const [operation] of __VLS_getVForSourceType((__VLS_ctx.operationHistory))) {
    const __VLS_169 = {}.ATimelineItem;
    /** @type {[typeof __VLS_components.ATimelineItem, typeof __VLS_components.aTimelineItem, typeof __VLS_components.ATimelineItem, typeof __VLS_components.aTimelineItem, ]} */ ;
    // @ts-ignore
    const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({
        key: (operation.id),
        color: (__VLS_ctx.getOperationColor(operation.type)),
    }));
    const __VLS_171 = __VLS_170({
        key: (operation.id),
        color: (__VLS_ctx.getOperationColor(operation.type)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_170));
    __VLS_172.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "operation-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "operation-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "operation-type font-medium" },
    });
    (__VLS_ctx.getOperationText(operation.type));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "operation-time text-gray-500 ml-2" },
    });
    (operation.operateTime);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "operation-operator text-sm text-gray-600" },
    });
    (operation.operator);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "operation-description text-sm mt-1" },
    });
    (operation.description);
    if (operation.result) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "operation-result text-sm text-green-600 mt-1" },
        });
        (operation.result);
    }
    var __VLS_172;
}
var __VLS_168;
var __VLS_164;
var __VLS_12;
{
    const { footer: __VLS_thisSlot } = __VLS_3.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    if (__VLS_ctx.viewType === 'records') {
        const __VLS_173 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_174 = __VLS_asFunctionalComponent(__VLS_173, new __VLS_173({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_175 = __VLS_174({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_174));
        let __VLS_177;
        let __VLS_178;
        let __VLS_179;
        const __VLS_180 = {
            onClick: (__VLS_ctx.handleAudit)
        };
        __VLS_176.slots.default;
        var __VLS_176;
    }
    if (__VLS_ctx.viewType === 'records') {
        const __VLS_181 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
            ...{ 'onClick': {} },
        }));
        const __VLS_183 = __VLS_182({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_182));
        let __VLS_185;
        let __VLS_186;
        let __VLS_187;
        const __VLS_188 = {
            onClick: (__VLS_ctx.handleUrge)
        };
        __VLS_184.slots.default;
        var __VLS_184;
    }
    const __VLS_189 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_190 = __VLS_asFunctionalComponent(__VLS_189, new __VLS_189({
        ...{ 'onClick': {} },
    }));
    const __VLS_191 = __VLS_190({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_190));
    let __VLS_193;
    let __VLS_194;
    let __VLS_195;
    const __VLS_196 = {
        onClick: (__VLS_ctx.handleExportDetail)
    };
    __VLS_192.slots.default;
    var __VLS_192;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_197 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_198 = __VLS_asFunctionalComponent(__VLS_197, new __VLS_197({
        ...{ 'onClick': {} },
    }));
    const __VLS_199 = __VLS_198({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_198));
    let __VLS_201;
    let __VLS_202;
    let __VLS_203;
    const __VLS_204 = {
        onClick: (__VLS_ctx.handleCancel)
    };
    __VLS_200.slots.default;
    var __VLS_200;
}
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['record-detail-content']} */ ;
/** @type {__VLS_StyleScopedClasses['basic-info']} */ ;
/** @type {__VLS_StyleScopedClasses['score-value']} */ ;
/** @type {__VLS_StyleScopedClasses['defects-list']} */ ;
/** @type {__VLS_StyleScopedClasses['document-viewer']} */ ;
/** @type {__VLS_StyleScopedClasses['document-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['document-sections']} */ ;
/** @type {__VLS_StyleScopedClasses['section-content']} */ ;
/** @type {__VLS_StyleScopedClasses['section-text']} */ ;
/** @type {__VLS_StyleScopedClasses['section-defects']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-items']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-item']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-50']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-red-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-header']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-type']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['defect-description']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-history']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-item']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-header']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-type']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-time']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-operator']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-description']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['operation-result']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            PrinterOutlined: icons_vue_1.PrinterOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            activeTab: activeTab,
            activeSections: activeSections,
            modalTitle: modalTitle,
            defectColumns: defectColumns,
            defectList: defectList,
            documentSections: documentSections,
            operationHistory: operationHistory,
            getAuditStatusColor: getAuditStatusColor,
            getAuditStatusText: getAuditStatusText,
            getPriorityColor: getPriorityColor,
            getPriorityText: getPriorityText,
            getDefectStatusColor: getDefectStatusColor,
            getDefectStatusText: getDefectStatusText,
            getOperationColor: getOperationColor,
            getOperationText: getOperationText,
            handleCancel: handleCancel,
            handleDefectDetail: handleDefectDetail,
            handleViewFullDocument: handleViewFullDocument,
            handlePrintDocument: handlePrintDocument,
            handleDownloadDocument: handleDownloadDocument,
            handleAudit: handleAudit,
            handleUrge: handleUrge,
            handleExportDetail: handleExportDetail,
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
