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
const props = withDefaults(defineProps(), {
    visible: false,
    columns: () => []
});
const emit = defineEmits();
// 列配置列表
const columnList = (0, vue_1.ref)(: any[]);
const schemeName = (0, vue_1.ref)('');
// 监听visible变化，初始化列配置
(0, vue_1.watch)(() => props.visible, (newVal) => {
    if (newVal) {
        initColumnList();
    }
});
// 初始化列配置
const initColumnList = () => {
    columnList.value = props.columns.map(col => ({
        key: col.key || col.dataIndex,
        title: col.title,
        width: col.width || 120,
        visible: true,
        fixed: col.fixed || false,
        sorter: !!col.sorter,
        sortable: col.sortable !== false
    }));
};
// 应用预设方案
const applyScheme = (scheme) => {
    switch (scheme) {
        case 'default':
            columnList.value.forEach(col => {
                col.visible = true;
                col.width = getDefaultWidth(col.key);
                col.fixed = col.key === 'action' ? 'right' : false;
            });
            break;
        case 'compact':
            columnList.value.forEach(col => {
                col.visible = isCompactColumn(col.key);
                col.width = Math.max(80, (col.width || 120) * 0.8);
                col.fixed = col.key === 'action' ? 'right' : false;
            });
            break;
        case 'detailed':
            columnList.value.forEach(col => {
                col.visible = true;
                col.width = Math.min(200, (col.width || 120) * 1.2);
                col.fixed = ['registrationNo', 'action'].includes(col.key) ?
                    (col.key === 'registrationNo' ? 'left' : 'right') : false;
            });
            break;
    }
    ant_design_vue_1.message.success(`已应用${scheme === 'default' ? '默认' : scheme === 'compact' ? '紧凑' : '详细'}方案`);
};
// 获取默认宽度
const getDefaultWidth = (key) => {
    const widthMap = {
        registrationNo: 120,
        serialNo: 120,
        caseNo: 120,
        patientName: 100,
        department: 100,
        doctor: 100,
        auditStatus: 100,
        score: 80,
        scoringStandard: 120,
        defectCount: 80,
        createTime: 150,
        action: 150
    };
    return widthMap[key] || 120;
};
// 判断是否为紧凑模式显示的列
const isCompactColumn = (key) => {
    const compactColumns = [
        'registrationNo', 'patientName', 'department',
        'auditStatus', 'score', 'defectCount', 'action'
    ];
    return compactColumns.includes(key);
};
// 保存方案
const saveScheme = () => {
    if (!schemeName.value.trim()) {
        ant_design_vue_1.message.error('请输入方案名称');
        return;
    }
    // 这里可以保存到本地存储或发送到服务器
    const scheme = {
        name: schemeName.value,
        columns: [...columnList.value]
    };
    // 模拟保存
    localStorage.setItem(`column-scheme-${schemeName.value}`, JSON.stringify(scheme));
    ant_design_vue_1.message.success(`方案"${schemeName.value}"保存成功`);
    schemeName.value = '';
};
// 确认
const handleConfirm = () => {
    emit('confirm', [...columnList.value]);
    emit('update:visible', false);
};
// 取消
const handleCancel = () => {
    emit('update:visible', false);
};
// 重置
const handleReset = () => {
    initColumnList();
    ant_design_vue_1.message.success('已重置为默认配置');
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    visible: false,
    columns: () => []
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['column-item']} */ ;
/** @type {__VLS_StyleScopedClasses['column-item']} */ ;
// CSS variable injection 
// CSS variable injection end 
const __VLS_0 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    visible: (props.visible),
    title: "列设置",
    width: "600px",
}));
const __VLS_2 = __VLS_1({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    visible: (props.visible),
    title: "列设置",
    width: "600px",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onOk: (__VLS_ctx.handleConfirm)
};
const __VLS_8 = {
    onCancel: (__VLS_ctx.handleCancel)
};
var __VLS_9 = {};
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "column-settings-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-4" },
});
const __VLS_10 = {}.AAlert;
/** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
// @ts-ignore
const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
    message: "拖拽调整列顺序，勾选控制列显示",
    type: "info",
    showIcon: true,
    ...{ class: "mb-4" },
}));
const __VLS_12 = __VLS_11({
    message: "拖拽调整列顺序，勾选控制列显示",
    type: "info",
    showIcon: true,
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_11));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "column-list" },
});
for (const [column, index] of __VLS_getVForSourceType((__VLS_ctx.columnList))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (column.key),
        ...{ class: "column-item" },
        ...{ class: ({ 'column-item-disabled': !column.visible }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "column-item-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "drag-handle" },
    });
    const __VLS_14 = {}.HolderOutlined;
    /** @type {[typeof __VLS_components.HolderOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({}));
    const __VLS_16 = __VLS_15({}, ...__VLS_functionalComponentArgsRest(__VLS_15));
    const __VLS_18 = {}.ACheckbox;
    /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
        checked: (column.visible),
        disabled: (column.fixed),
    }));
    const __VLS_20 = __VLS_19({
        checked: (column.visible),
        disabled: (column.fixed),
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
    __VLS_21.slots.default;
    (column.title);
    var __VLS_21;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "column-width-setting" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "width-label" },
    });
    const __VLS_22 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_23 = __VLS_asFunctionalComponent(__VLS_22, new __VLS_22({
        value: (column.width),
        min: (80),
        max: (500),
        step: (10),
        size: "small",
        ...{ style: {} },
    }));
    const __VLS_24 = __VLS_23({
        value: (column.width),
        min: (80),
        max: (500),
        step: (10),
        size: "small",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_23));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "width-unit" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "column-fixed-setting" },
    });
    const __VLS_26 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
        value: (column.fixed),
        size: "small",
        ...{ style: {} },
        disabled: (column.key === 'action'),
    }));
    const __VLS_28 = __VLS_27({
        value: (column.fixed),
        size: "small",
        ...{ style: {} },
        disabled: (column.key === 'action'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    __VLS_29.slots.default;
    const __VLS_30 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
        value: (false),
    }));
    const __VLS_32 = __VLS_31({
        value: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    __VLS_33.slots.default;
    var __VLS_33;
    const __VLS_34 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
        value: "left",
    }));
    const __VLS_36 = __VLS_35({
        value: "left",
    }, ...__VLS_functionalComponentArgsRest(__VLS_35));
    __VLS_37.slots.default;
    var __VLS_37;
    const __VLS_38 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
        value: "right",
    }));
    const __VLS_40 = __VLS_39({
        value: "right",
    }, ...__VLS_functionalComponentArgsRest(__VLS_39));
    __VLS_41.slots.default;
    var __VLS_41;
    var __VLS_29;
    if (column.sortable !== false) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "column-sort-setting" },
        });
        const __VLS_42 = {}.ACheckbox;
        /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
        // @ts-ignore
        const __VLS_43 = __VLS_asFunctionalComponent(__VLS_42, new __VLS_42({
            checked: (column.sorter),
            size: "small",
        }));
        const __VLS_44 = __VLS_43({
            checked: (column.sorter),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_43));
        __VLS_45.slots.default;
        var __VLS_45;
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "preset-schemes mt-6 pt-4 border-t border-gray-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "mb-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "scheme-buttons" },
});
const __VLS_46 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_48 = __VLS_47({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_47));
let __VLS_50;
let __VLS_51;
let __VLS_52;
const __VLS_53 = {
    onClick: (...[$event]) => {
        __VLS_ctx.applyScheme('default');
    }
};
__VLS_49.slots.default;
var __VLS_49;
const __VLS_54 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_56 = __VLS_55({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_55));
let __VLS_58;
let __VLS_59;
let __VLS_60;
const __VLS_61 = {
    onClick: (...[$event]) => {
        __VLS_ctx.applyScheme('compact');
    }
};
__VLS_57.slots.default;
var __VLS_57;
const __VLS_62 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_63 = __VLS_asFunctionalComponent(__VLS_62, new __VLS_62({
    ...{ 'onClick': {} },
    size: "small",
}));
const __VLS_64 = __VLS_63({
    ...{ 'onClick': {} },
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_63));
let __VLS_66;
let __VLS_67;
let __VLS_68;
const __VLS_69 = {
    onClick: (...[$event]) => {
        __VLS_ctx.applyScheme('detailed');
    }
};
__VLS_65.slots.default;
var __VLS_65;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "save-scheme mt-4" },
});
const __VLS_70 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
    value: (__VLS_ctx.schemeName),
    placeholder: "输入方案名称",
    ...{ style: {} },
}));
const __VLS_72 = __VLS_71({
    value: (__VLS_ctx.schemeName),
    placeholder: "输入方案名称",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_71));
const __VLS_74 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_75 = __VLS_asFunctionalComponent(__VLS_74, new __VLS_74({
    ...{ 'onClick': {} },
    type: "primary",
    size: "small",
    disabled: (!__VLS_ctx.schemeName.trim()),
    ...{ class: "ml-2" },
}));
const __VLS_76 = __VLS_75({
    ...{ 'onClick': {} },
    type: "primary",
    size: "small",
    disabled: (!__VLS_ctx.schemeName.trim()),
    ...{ class: "ml-2" },
}, ...__VLS_functionalComponentArgsRest(__VLS_75));
let __VLS_78;
let __VLS_79;
let __VLS_80;
const __VLS_81 = {
    onClick: (__VLS_ctx.saveScheme)
};
__VLS_77.slots.default;
var __VLS_77;
{
    const { footer: __VLS_thisSlot } = __VLS_3.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_82 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_83 = __VLS_asFunctionalComponent(__VLS_82, new __VLS_82({
        ...{ 'onClick': {} },
    }));
    const __VLS_84 = __VLS_83({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_83));
    let __VLS_86;
    let __VLS_87;
    let __VLS_88;
    const __VLS_89 = {
        onClick: (__VLS_ctx.handleReset)
    };
    __VLS_85.slots.default;
    var __VLS_85;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_90 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_91 = __VLS_asFunctionalComponent(__VLS_90, new __VLS_90({
        ...{ 'onClick': {} },
    }));
    const __VLS_92 = __VLS_91({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_91));
    let __VLS_94;
    let __VLS_95;
    let __VLS_96;
    const __VLS_97 = {
        onClick: (__VLS_ctx.handleCancel)
    };
    __VLS_93.slots.default;
    var __VLS_93;
    const __VLS_98 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_99 = __VLS_asFunctionalComponent(__VLS_98, new __VLS_98({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_100 = __VLS_99({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_99));
    let __VLS_102;
    let __VLS_103;
    let __VLS_104;
    const __VLS_105 = {
        onClick: (__VLS_ctx.handleConfirm)
    };
    __VLS_101.slots.default;
    var __VLS_101;
}
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['column-settings-content']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['column-list']} */ ;
/** @type {__VLS_StyleScopedClasses['column-item']} */ ;
/** @type {__VLS_StyleScopedClasses['column-item-disabled']} */ ;
/** @type {__VLS_StyleScopedClasses['column-item-content']} */ ;
/** @type {__VLS_StyleScopedClasses['drag-handle']} */ ;
/** @type {__VLS_StyleScopedClasses['column-width-setting']} */ ;
/** @type {__VLS_StyleScopedClasses['width-label']} */ ;
/** @type {__VLS_StyleScopedClasses['width-unit']} */ ;
/** @type {__VLS_StyleScopedClasses['column-fixed-setting']} */ ;
/** @type {__VLS_StyleScopedClasses['column-sort-setting']} */ ;
/** @type {__VLS_StyleScopedClasses['preset-schemes']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['scheme-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['save-scheme']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            HolderOutlined: icons_vue_1.HolderOutlined,
            columnList: columnList,
            schemeName: schemeName,
            applyScheme: applyScheme,
            saveScheme: saveScheme,
            handleConfirm: handleConfirm,
            handleCancel: handleCancel,
            handleReset: handleReset,
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
