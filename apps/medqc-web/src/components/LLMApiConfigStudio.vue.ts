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
import llmConfigService_1 from '@/services/llmConfigService';
import llmServiceNew_1 from '@/services/llmServiceNew';
const emit = defineEmits();
// state
const loading = (0, vue_1.ref)(false);
const saving = (0, vue_1.ref)(false);
const testing = (0, vue_1.ref)(false);
const providers = (0, vue_1.ref)(: any[]);
const configs = (0, vue_1.ref)(: any[]);
const selectedConfig = (0, vue_1.ref)(null);
const search = (0, vue_1.ref)('');
// drawer/form
const drawerOpen = (0, vue_1.ref)(false);
const formRef = (0, vue_1.ref)();
const form = (0, vue_1.reactive)({
    config_name: '', provider_id: '', model_id: '', api_key: '', custom_endpoint: '', custom_parameters: {}, is_active: true
});
const models = (0, vue_1.ref)(: any[]);
const customParamsText = (0, vue_1.ref)('');
const rules = {
    config_name: [{ required: true, message: '请输入配置名称' }],
    provider_id: [{ required: true, message: '请选择提供商' }],
    model_id: [{ required: true, message: '请选择模型' }]
};
// test status
const testStatus = (0, vue_1.reactive)({ status: 'default', text: '未测试' });
// quick presets
const quickPresets = (0, vue_1.computed)(() => [
    { provider_code: 'alibaba', name: '通义·阿里云' },
    { provider_code: 'baidu', name: '文心·百度' },
    { provider_code: 'local', name: '本地Ollama/推理服务' }
]);
const filteredConfigs = (0, vue_1.computed)(() => {
    if (!search.value)
        return configs.value;
    const q = search.value.toLowerCase();
    return configs.value.filter(c => c.config_name.toLowerCase().includes(q) ||
        (c.provider?.provider_name || '').toLowerCase().includes(q) ||
        (c.model?.model_name || '').toLowerCase().includes(q));
});
const formatDate = (s) => new Date(s).toLocaleString('zh-CN');
// actions
const loadAll = async () => {
    loading.value = true;
    try {
        providers.value = await llmConfigService_1.llmConfigService.getProviders();
        configs.value = await llmConfigService_1.llmConfigService.getUserConfigs();
        if (!selectedConfig.value)
            selectedConfig.value = configs.value[0] || null;
    }
    catch (e) {
        ant_design_vue_1.message.error('加载配置失败');
    }
    finally {
        loading.value = false;
    }
};
const select = (c) => {
    selectedConfig.value = c;
    emit('config-updated', c);
};
const setDefault = async (c) => {
    try {
        await llmConfigService_1.llmConfigService.setDefaultConfig(c.id);
        ant_design_vue_1.message.success('已设为默认配置');
        await loadAll();
    }
    catch (e) {
        ant_design_vue_1.message.error('设置默认失败');
    }
};
const remove = async (c) => {
    try {
        await llmConfigService_1.llmConfigService.deleteConfig(c.id);
        ant_design_vue_1.message.success('已删除');
        await loadAll();
    }
    catch (e) {
        ant_design_vue_1.message.error('删除失败');
    }
};
const openCreate = () => {
    drawerOpen.value = true;
    Object.assign(form, { config_name: '', provider_id: '', model_id: '', api_key: '', custom_endpoint: '', custom_parameters: {}, is_active: true });
    customParamsText.value = '';
    models.value = [];
};
const openEdit = (c) => {
    drawerOpen.value = true;
    Object.assign(form, {
        config_name: c.config_name,
        provider_id: c.provider_id,
        model_id: c.model_id,
        api_key: '',
        custom_endpoint: c.custom_endpoint || '',
        custom_parameters: c.custom_parameters || {},
        is_active: c.is_active
    });
    customParamsText.value = JSON.stringify(form.custom_parameters || {}, null, 2);
    if (form.provider_id)
        onProviderChanged(form.provider_id);
};
const onProviderChanged = async (providerId) => {
    models.value = await llmConfigService_1.llmConfigService.getModelsByProvider(providerId);
    form.model_id = '';
};
const submit = async () => {
    await formRef.value?.validate().catch(() => { throw new Error('表单校验失败'); });
    saving.value = true;
    try {
        let custom = {};
        if (customParamsText.value.trim()) {
            try {
                custom = JSON.parse(customParamsText.value);
            }
            catch {
                ant_design_vue_1.message.error('自定义参数 JSON 格式错误');
                saving.value = false;
                return;
            }
        }
        const data = { ...form, custom_parameters: custom };
        const saved = await llmConfigService_1.llmConfigService.saveConfig(data);
        ant_design_vue_1.message.success('配置已保存');
        drawerOpen.value = false;
        await loadAll();
        select(saved);
    }
    catch (e) {
        ant_design_vue_1.message.error('保存失败');
    }
    finally {
        saving.value = false;
    }
};
const test = async (c) => {
    testing.value = true;
    testStatus.status = 'processing';
    testStatus.text = '测试中...';
    try {
        llmServiceNew_1.llmService.updateConfig({
            apiEndpoint: c.custom_endpoint || (c.provider?.base_endpoint || ''),
            apiKey: c.api_key_decrypted || '',
            model: c.model?.model_code || ''
        });
        const r = await llmServiceNew_1.llmService.parseMedicalText('ping', { maxTokens: 5, temperature: 0 });
        if (r.success) {
            testStatus.status = 'success';
            testStatus.text = '连接正常';
        }
        else {
            testStatus.status = 'error';
            testStatus.text = r.error || '失败';
        }
    }
    catch (e) {
        testStatus.status = 'error';
        testStatus.text = e?.message || '失败';
    }
    finally {
        testing.value = false;
    }
};
const testTemp = async () => {
    testing.value = true;
    try {
        llmServiceNew_1.llmService.updateConfig({
            apiEndpoint: form.custom_endpoint || (selectedConfig.value?.provider?.base_endpoint || ''),
            apiKey: form.api_key,
            model: models.value.find(m => m.id === form.model_id)?.model_code || ''
        });
        const r = await llmServiceNew_1.llmService.parseMedicalText('ping', { maxTokens: 5, temperature: 0 });
        ant_design_vue_1.message[r.success ? 'success' : 'error'](r.success ? '连接正常' : (r.error || '连接失败'));
    }
    finally {
        testing.value = false;
    }
};
// import/export
const onImport = async (file) => {
    try {
        const data = JSON.parse(await file.text());
        Object.assign(form, {
            config_name: data.config_name || '',
            provider_id: data.provider_id || '',
            model_id: data.model_id || '',
            api_key: data.api_key || '',
            custom_endpoint: data.custom_endpoint || '',
            custom_parameters: data.custom_parameters || {},
            is_active: data.is_active !== false
        });
        customParamsText.value = JSON.stringify(form.custom_parameters || {}, null, 2);
        if (form.provider_id)
            await onProviderChanged(form.provider_id);
        drawerOpen.value = true;
        ant_design_vue_1.message.success('配置已导入');
    }
    catch {
        ant_design_vue_1.message.error('导入失败：JSON 无效');
    }
    return false;
};
const exportCurrent = () => {
    if (!selectedConfig.value)
        return;
    const content = JSON.stringify({
        config_name: selectedConfig.value.config_name,
        provider_id: selectedConfig.value.provider_id,
        model_id: selectedConfig.value.model_id,
        custom_endpoint: selectedConfig.value.custom_endpoint,
        custom_parameters: selectedConfig.value.custom_parameters,
        is_active: selectedConfig.value.is_active
    }, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedConfig.value.config_name}.json`;
    a.click();
    URL.revokeObjectURL(url);
    ant_design_vue_1.message.success('已导出');
};
const applyPreset = (preset) => {
    const p = providers.value.find(x => x.provider_code === preset.provider_code);
    if (!p)
        return ant_design_vue_1.message.warning('该预设不可用');
    openCreate();
    form.config_name = `${preset.provider_code}_preset`;
    form.provider_id = p.id;
    onProviderChanged(p.id);
};
const drawerTitle = (0, vue_1.computed)(() => form.config_name ? `编辑配置：${form.config_name}` : '新建配置');
(0, vue_1.onMounted)(loadAll);
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "studio min-h-[60vh] p-4 md:p-6 bg-gradient-to-br from-slate-50 to-blue-50" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "w-9 h-9 flex items-center justify-center rounded-xl bg-blue-100 text-blue-600 text-lg" },
});
const __VLS_0 = {}.ApiOutlined;
/** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg md:text-xl font-bold text-slate-900" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs md:text-sm text-slate-500" },
});
const __VLS_4 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.AUpload;
/** @type {[typeof __VLS_components.AUpload, typeof __VLS_components.aUpload, typeof __VLS_components.AUpload, typeof __VLS_components.aUpload, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    beforeUpload: (__VLS_ctx.onImport),
    showUploadList: (false),
}));
const __VLS_10 = __VLS_9({
    beforeUpload: (__VLS_ctx.onImport),
    showUploadList: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ class: "hover:shadow-sm" },
}));
const __VLS_14 = __VLS_13({
    ...{ class: "hover:shadow-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_15.slots;
    const __VLS_16 = {}.UploadOutlined;
    /** @type {[typeof __VLS_components.UploadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
    const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
}
var __VLS_15;
var __VLS_11;
const __VLS_20 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    disabled: (!__VLS_ctx.selectedConfig),
    ...{ class: "hover:shadow-sm" },
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    disabled: (!__VLS_ctx.selectedConfig),
    ...{ class: "hover:shadow-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.exportCurrent)
};
__VLS_23.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_23.slots;
    const __VLS_28 = {}.DownloadOutlined;
    /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
    const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
}
var __VLS_23;
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "shadow-sm hover:shadow" },
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "shadow-sm hover:shadow" },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (...[$event]) => {
        __VLS_ctx.openCreate();
    }
};
__VLS_35.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_35.slots;
    const __VLS_40 = {}.PlusOutlined;
    /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
    const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
var __VLS_35;
const __VLS_44 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    ...{ class: "hover:shadow-sm" },
}));
const __VLS_46 = __VLS_45({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    ...{ class: "hover:shadow-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_48;
let __VLS_49;
let __VLS_50;
const __VLS_51 = {
    onClick: (__VLS_ctx.loadAll)
};
__VLS_47.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_47.slots;
    const __VLS_52 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
    const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
}
var __VLS_47;
var __VLS_7;
const __VLS_56 = {}.ASpin;
/** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    spinning: (__VLS_ctx.loading),
    tip: "加载中...",
}));
const __VLS_58 = __VLS_57({
    spinning: (__VLS_ctx.loading),
    tip: "加载中...",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
const __VLS_60 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    gutter: ([16, 16]),
    ...{ class: "studio__main" },
}));
const __VLS_62 = __VLS_61({
    gutter: ([16, 16]),
    ...{ class: "studio__main" },
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
const __VLS_64 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    xs: (24),
    md: (9),
}));
const __VLS_66 = __VLS_65({
    xs: (24),
    md: (9),
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
const __VLS_68 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    size: "small",
    bordered: (true),
    loading: (__VLS_ctx.loading),
    ...{ class: "rounded-2xl shadow-sm" },
}));
const __VLS_70 = __VLS_69({
    size: "small",
    bordered: (true),
    loading: (__VLS_ctx.loading),
    ...{ class: "rounded-2xl shadow-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.AInputSearch;
/** @type {[typeof __VLS_components.AInputSearch, typeof __VLS_components.aInputSearch, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    value: (__VLS_ctx.search),
    placeholder: "搜索配置/提供商/模型",
    allowClear: true,
}));
const __VLS_74 = __VLS_73({
    value: (__VLS_ctx.search),
    placeholder: "搜索配置/提供商/模型",
    allowClear: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
const __VLS_76 = {}.AList;
/** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    ...{ class: "mt-2 max-h-[420px] overflow-auto" },
    dataSource: (__VLS_ctx.filteredConfigs),
    itemLayout: "horizontal",
    split: (false),
    locale: ({ emptyText: '暂无配置' }),
}));
const __VLS_78 = __VLS_77({
    ...{ class: "mt-2 max-h-[420px] overflow-auto" },
    dataSource: (__VLS_ctx.filteredConfigs),
    itemLayout: "horizontal",
    split: (false),
    locale: ({ emptyText: '暂无配置' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
{
    const { renderItem: __VLS_thisSlot } = __VLS_79.slots;
    const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_80 = {}.AListItem;
    /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        ...{ 'onClick': {} },
        ...{ class: (['rounded-xl transition-all', item.id === __VLS_ctx.selectedConfig?.id ? 'bg-blue-50' : 'hover:bg-slate-50']) },
    }));
    const __VLS_82 = __VLS_81({
        ...{ 'onClick': {} },
        ...{ class: (['rounded-xl transition-all', item.id === __VLS_ctx.selectedConfig?.id ? 'bg-blue-50' : 'hover:bg-slate-50']) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    let __VLS_84;
    let __VLS_85;
    let __VLS_86;
    const __VLS_87 = {
        onClick: (...[$event]) => {
            __VLS_ctx.select(item);
        }
    };
    __VLS_83.slots.default;
    {
        const { actions: __VLS_thisSlot } = __VLS_83.slots;
        const __VLS_88 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
        const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
        __VLS_91.slots.default;
        const __VLS_92 = {}.ATooltip;
        /** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            title: "设为默认",
        }));
        const __VLS_94 = __VLS_93({
            title: "设为默认",
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        __VLS_95.slots.default;
        const __VLS_96 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
            ...{ 'onClick': {} },
            type: "text",
            size: "small",
        }));
        const __VLS_98 = __VLS_97({
            ...{ 'onClick': {} },
            type: "text",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
        let __VLS_100;
        let __VLS_101;
        let __VLS_102;
        const __VLS_103 = {
            onClick: (...[$event]) => {
                __VLS_ctx.setDefault(item);
            }
        };
        __VLS_99.slots.default;
        var __VLS_99;
        var __VLS_95;
        const __VLS_104 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_106 = __VLS_105({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_105));
        let __VLS_108;
        let __VLS_109;
        let __VLS_110;
        const __VLS_111 = {
            onClick: (...[$event]) => {
                __VLS_ctx.openEdit(item);
            }
        };
        __VLS_107.slots.default;
        var __VLS_107;
        const __VLS_112 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            ...{ 'onConfirm': {} },
            title: "确认删除该配置？",
        }));
        const __VLS_114 = __VLS_113({
            ...{ 'onConfirm': {} },
            title: "确认删除该配置？",
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        let __VLS_116;
        let __VLS_117;
        let __VLS_118;
        const __VLS_119 = {
            onConfirm: (...[$event]) => {
                __VLS_ctx.remove(item);
            }
        };
        __VLS_115.slots.default;
        const __VLS_120 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            type: "text",
            danger: true,
            size: "small",
        }));
        const __VLS_122 = __VLS_121({
            type: "text",
            danger: true,
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        var __VLS_123;
        var __VLS_115;
        var __VLS_91;
    }
    const __VLS_124 = {}.AListItemMeta;
    /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
    const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
    __VLS_127.slots.default;
    {
        const { title: __VLS_thisSlot } = __VLS_127.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "font-semibold text-slate-900" },
        });
        (item.config_name);
        if (item.config_name === 'default') {
            const __VLS_128 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
                color: "blue",
                size: "small",
                ...{ class: "ml-1" },
            }));
            const __VLS_130 = __VLS_129({
                color: "blue",
                size: "small",
                ...{ class: "ml-1" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_129));
            __VLS_131.slots.default;
            var __VLS_131;
        }
    }
    {
        const { description: __VLS_thisSlot } = __VLS_127.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-slate-500" },
        });
        (item.provider?.provider_name || '未指定');
        (item.model?.model_name || '未指定模型');
    }
    var __VLS_127;
    var __VLS_83;
}
var __VLS_79;
var __VLS_71;
if (__VLS_ctx.providers.length) {
    const __VLS_132 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        size: "small",
        bordered: (false),
        ...{ class: "mt-3 rounded-xl" },
    }));
    const __VLS_134 = __VLS_133({
        size: "small",
        bordered: (false),
        ...{ class: "mt-3 rounded-xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs text-slate-500 mb-1" },
    });
    const __VLS_136 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        wrap: true,
    }));
    const __VLS_138 = __VLS_137({
        wrap: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    for (const [p] of __VLS_getVForSourceType((__VLS_ctx.quickPresets))) {
        const __VLS_140 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
            ...{ 'onClick': {} },
            key: (p.provider_code),
            ...{ class: "cursor-pointer bg-slate-50 border-slate-200" },
        }));
        const __VLS_142 = __VLS_141({
            ...{ 'onClick': {} },
            key: (p.provider_code),
            ...{ class: "cursor-pointer bg-slate-50 border-slate-200" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_141));
        let __VLS_144;
        let __VLS_145;
        let __VLS_146;
        const __VLS_147 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.providers.length))
                    return;
                __VLS_ctx.applyPreset(p);
            }
        };
        __VLS_143.slots.default;
        (p.name);
        var __VLS_143;
    }
    var __VLS_139;
    var __VLS_135;
}
var __VLS_67;
const __VLS_148 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    xs: (24),
    md: (15),
}));
const __VLS_150 = __VLS_149({
    xs: (24),
    md: (15),
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
__VLS_151.slots.default;
if (__VLS_ctx.selectedConfig) {
    const __VLS_152 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        bordered: (false),
        ...{ class: "rounded-2xl shadow-sm" },
    }));
    const __VLS_154 = __VLS_153({
        bordered: (false),
        ...{ class: "rounded-2xl shadow-sm" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-base font-bold text-slate-900" },
    });
    (__VLS_ctx.selectedConfig.config_name);
    const __VLS_156 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({}));
    const __VLS_158 = __VLS_157({}, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    (__VLS_ctx.selectedConfig.provider?.provider_name || '未指定提供商');
    var __VLS_159;
    const __VLS_160 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        color: "geekblue",
    }));
    const __VLS_162 = __VLS_161({
        color: "geekblue",
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    __VLS_163.slots.default;
    (__VLS_ctx.selectedConfig.model?.model_name || '未指定模型');
    var __VLS_163;
    const __VLS_164 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({}));
    const __VLS_166 = __VLS_165({}, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    const __VLS_168 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.testing),
    }));
    const __VLS_170 = __VLS_169({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.testing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    let __VLS_172;
    let __VLS_173;
    let __VLS_174;
    const __VLS_175 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.selectedConfig))
                return;
            __VLS_ctx.test(__VLS_ctx.selectedConfig);
        }
    };
    __VLS_171.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_171.slots;
        const __VLS_176 = {}.ApiOutlined;
        /** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({}));
        const __VLS_178 = __VLS_177({}, ...__VLS_functionalComponentArgsRest(__VLS_177));
    }
    var __VLS_171;
    const __VLS_180 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_182 = __VLS_181({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    let __VLS_184;
    let __VLS_185;
    let __VLS_186;
    const __VLS_187 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.selectedConfig))
                return;
            __VLS_ctx.openEdit(__VLS_ctx.selectedConfig);
        }
    };
    __VLS_183.slots.default;
    var __VLS_183;
    var __VLS_167;
    const __VLS_188 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        size: "small",
        column: (1),
        bordered: true,
        ...{ class: "mt-2" },
    }));
    const __VLS_190 = __VLS_189({
        size: "small",
        column: (1),
        bordered: true,
        ...{ class: "mt-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    __VLS_191.slots.default;
    const __VLS_192 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
        label: "API 端点",
    }));
    const __VLS_194 = __VLS_193({
        label: "API 端点",
    }, ...__VLS_functionalComponentArgsRest(__VLS_193));
    __VLS_195.slots.default;
    (__VLS_ctx.selectedConfig.custom_endpoint || __VLS_ctx.selectedConfig.provider?.base_endpoint || '-');
    var __VLS_195;
    const __VLS_196 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
        label: "模型代码",
    }));
    const __VLS_198 = __VLS_197({
        label: "模型代码",
    }, ...__VLS_functionalComponentArgsRest(__VLS_197));
    __VLS_199.slots.default;
    (__VLS_ctx.selectedConfig.model?.model_code || '-');
    var __VLS_199;
    const __VLS_200 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
        label: "状态",
    }));
    const __VLS_202 = __VLS_201({
        label: "状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_201));
    __VLS_203.slots.default;
    const __VLS_204 = {}.ABadge;
    /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        status: (__VLS_ctx.testStatus.status),
        text: (__VLS_ctx.testStatus.text),
    }));
    const __VLS_206 = __VLS_205({
        status: (__VLS_ctx.testStatus.status),
        text: (__VLS_ctx.testStatus.text),
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
    var __VLS_203;
    const __VLS_208 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        label: "更新时间",
    }));
    const __VLS_210 = __VLS_209({
        label: "更新时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
    __VLS_211.slots.default;
    (__VLS_ctx.formatDate(__VLS_ctx.selectedConfig.updated_at));
    var __VLS_211;
    var __VLS_191;
    var __VLS_155;
}
else {
    const __VLS_212 = {}.AEmpty;
    /** @type {[typeof __VLS_components.AEmpty, typeof __VLS_components.aEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
        description: "请选择左侧配置或新建配置",
    }));
    const __VLS_214 = __VLS_213({
        description: "请选择左侧配置或新建配置",
    }, ...__VLS_functionalComponentArgsRest(__VLS_213));
}
var __VLS_151;
var __VLS_63;
var __VLS_59;
const __VLS_216 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
    open: (__VLS_ctx.drawerOpen),
    title: (__VLS_ctx.drawerTitle),
    width: "520",
    destroyOnClose: (true),
}));
const __VLS_218 = __VLS_217({
    open: (__VLS_ctx.drawerOpen),
    title: (__VLS_ctx.drawerTitle),
    width: "520",
    destroyOnClose: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_217));
__VLS_219.slots.default;
const __VLS_220 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
    ref: "formRef",
    layout: "vertical",
    model: (__VLS_ctx.form),
    rules: (__VLS_ctx.rules),
}));
const __VLS_222 = __VLS_221({
    ref: "formRef",
    layout: "vertical",
    model: (__VLS_ctx.form),
    rules: (__VLS_ctx.rules),
}, ...__VLS_functionalComponentArgsRest(__VLS_221));
/** @type {typeof __VLS_ctx.formRef} */ ;
var __VLS_224 = {};
__VLS_223.slots.default;
const __VLS_226 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_227 = __VLS_asFunctionalComponent(__VLS_226, new __VLS_226({
    label: "配置名称",
    name: "config_name",
}));
const __VLS_228 = __VLS_227({
    label: "配置名称",
    name: "config_name",
}, ...__VLS_functionalComponentArgsRest(__VLS_227));
__VLS_229.slots.default;
const __VLS_230 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_231 = __VLS_asFunctionalComponent(__VLS_230, new __VLS_230({
    value: (__VLS_ctx.form.config_name),
    placeholder: "如：default 或 qwen_prod",
}));
const __VLS_232 = __VLS_231({
    value: (__VLS_ctx.form.config_name),
    placeholder: "如：default 或 qwen_prod",
}, ...__VLS_functionalComponentArgsRest(__VLS_231));
var __VLS_229;
const __VLS_234 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_235 = __VLS_asFunctionalComponent(__VLS_234, new __VLS_234({
    label: "API 提供商",
    name: "provider_id",
}));
const __VLS_236 = __VLS_235({
    label: "API 提供商",
    name: "provider_id",
}, ...__VLS_functionalComponentArgsRest(__VLS_235));
__VLS_237.slots.default;
const __VLS_238 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_239 = __VLS_asFunctionalComponent(__VLS_238, new __VLS_238({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.form.provider_id),
    placeholder: "选择提供商",
}));
const __VLS_240 = __VLS_239({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.form.provider_id),
    placeholder: "选择提供商",
}, ...__VLS_functionalComponentArgsRest(__VLS_239));
let __VLS_242;
let __VLS_243;
let __VLS_244;
const __VLS_245 = {
    onChange: (__VLS_ctx.onProviderChanged)
};
__VLS_241.slots.default;
for (const [p] of __VLS_getVForSourceType((__VLS_ctx.providers))) {
    const __VLS_246 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_247 = __VLS_asFunctionalComponent(__VLS_246, new __VLS_246({
        key: (p.id),
        value: (p.id),
    }));
    const __VLS_248 = __VLS_247({
        key: (p.id),
        value: (p.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_247));
    __VLS_249.slots.default;
    (p.provider_name);
    var __VLS_249;
}
var __VLS_241;
var __VLS_237;
const __VLS_250 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_251 = __VLS_asFunctionalComponent(__VLS_250, new __VLS_250({
    label: "模型",
    name: "model_id",
}));
const __VLS_252 = __VLS_251({
    label: "模型",
    name: "model_id",
}, ...__VLS_functionalComponentArgsRest(__VLS_251));
__VLS_253.slots.default;
const __VLS_254 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_255 = __VLS_asFunctionalComponent(__VLS_254, new __VLS_254({
    value: (__VLS_ctx.form.model_id),
    placeholder: "选择模型",
    disabled: (!__VLS_ctx.models.length),
}));
const __VLS_256 = __VLS_255({
    value: (__VLS_ctx.form.model_id),
    placeholder: "选择模型",
    disabled: (!__VLS_ctx.models.length),
}, ...__VLS_functionalComponentArgsRest(__VLS_255));
__VLS_257.slots.default;
for (const [m] of __VLS_getVForSourceType((__VLS_ctx.models))) {
    const __VLS_258 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_259 = __VLS_asFunctionalComponent(__VLS_258, new __VLS_258({
        key: (m.id),
        value: (m.id),
    }));
    const __VLS_260 = __VLS_259({
        key: (m.id),
        value: (m.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_259));
    __VLS_261.slots.default;
    (m.model_name);
    var __VLS_261;
}
var __VLS_257;
var __VLS_253;
const __VLS_262 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_263 = __VLS_asFunctionalComponent(__VLS_262, new __VLS_262({
    label: "API 密钥",
    name: "api_key",
    extra: "密钥仅用于保存时写入数据库，界面不回显历史值",
}));
const __VLS_264 = __VLS_263({
    label: "API 密钥",
    name: "api_key",
    extra: "密钥仅用于保存时写入数据库，界面不回显历史值",
}, ...__VLS_functionalComponentArgsRest(__VLS_263));
__VLS_265.slots.default;
const __VLS_266 = {}.AInputPassword;
/** @type {[typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, ]} */ ;
// @ts-ignore
const __VLS_267 = __VLS_asFunctionalComponent(__VLS_266, new __VLS_266({
    value: (__VLS_ctx.form.api_key),
    placeholder: "填写或留空保持不变",
}));
const __VLS_268 = __VLS_267({
    value: (__VLS_ctx.form.api_key),
    placeholder: "填写或留空保持不变",
}, ...__VLS_functionalComponentArgsRest(__VLS_267));
var __VLS_265;
const __VLS_270 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_271 = __VLS_asFunctionalComponent(__VLS_270, new __VLS_270({
    label: "自定义端点",
}));
const __VLS_272 = __VLS_271({
    label: "自定义端点",
}, ...__VLS_functionalComponentArgsRest(__VLS_271));
__VLS_273.slots.default;
const __VLS_274 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_275 = __VLS_asFunctionalComponent(__VLS_274, new __VLS_274({
    value: (__VLS_ctx.form.custom_endpoint),
    placeholder: "如 https://api.example.com/v1",
}));
const __VLS_276 = __VLS_275({
    value: (__VLS_ctx.form.custom_endpoint),
    placeholder: "如 https://api.example.com/v1",
}, ...__VLS_functionalComponentArgsRest(__VLS_275));
var __VLS_273;
const __VLS_278 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_279 = __VLS_asFunctionalComponent(__VLS_278, new __VLS_278({
    label: "自定义参数 (JSON)",
}));
const __VLS_280 = __VLS_279({
    label: "自定义参数 (JSON)",
}, ...__VLS_functionalComponentArgsRest(__VLS_279));
__VLS_281.slots.default;
const __VLS_282 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_283 = __VLS_asFunctionalComponent(__VLS_282, new __VLS_282({
    value: (__VLS_ctx.customParamsText),
    rows: (4),
    placeholder: '{"temperature":0.7,"max_tokens":2000}',
}));
const __VLS_284 = __VLS_283({
    value: (__VLS_ctx.customParamsText),
    rows: (4),
    placeholder: '{"temperature":0.7,"max_tokens":2000}',
}, ...__VLS_functionalComponentArgsRest(__VLS_283));
var __VLS_281;
const __VLS_286 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_287 = __VLS_asFunctionalComponent(__VLS_286, new __VLS_286({
    label: "启用",
}));
const __VLS_288 = __VLS_287({
    label: "启用",
}, ...__VLS_functionalComponentArgsRest(__VLS_287));
__VLS_289.slots.default;
const __VLS_290 = {}.ASwitch;
/** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
// @ts-ignore
const __VLS_291 = __VLS_asFunctionalComponent(__VLS_290, new __VLS_290({
    checked: (__VLS_ctx.form.is_active),
}));
const __VLS_292 = __VLS_291({
    checked: (__VLS_ctx.form.is_active),
}, ...__VLS_functionalComponentArgsRest(__VLS_291));
var __VLS_289;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-end mt-2" },
});
const __VLS_294 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_295 = __VLS_asFunctionalComponent(__VLS_294, new __VLS_294({}));
const __VLS_296 = __VLS_295({}, ...__VLS_functionalComponentArgsRest(__VLS_295));
__VLS_297.slots.default;
const __VLS_298 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_299 = __VLS_asFunctionalComponent(__VLS_298, new __VLS_298({
    ...{ 'onClick': {} },
}));
const __VLS_300 = __VLS_299({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_299));
let __VLS_302;
let __VLS_303;
let __VLS_304;
const __VLS_305 = {
    onClick: (...[$event]) => {
        __VLS_ctx.drawerOpen = false;
    }
};
__VLS_301.slots.default;
var __VLS_301;
const __VLS_306 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_307 = __VLS_asFunctionalComponent(__VLS_306, new __VLS_306({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing),
    ...{ class: "hover:shadow-sm" },
}));
const __VLS_308 = __VLS_307({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing),
    ...{ class: "hover:shadow-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_307));
let __VLS_310;
let __VLS_311;
let __VLS_312;
const __VLS_313 = {
    onClick: (__VLS_ctx.testTemp)
};
__VLS_309.slots.default;
const __VLS_314 = {}.ApiOutlined;
/** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
// @ts-ignore
const __VLS_315 = __VLS_asFunctionalComponent(__VLS_314, new __VLS_314({}));
const __VLS_316 = __VLS_315({}, ...__VLS_functionalComponentArgsRest(__VLS_315));
var __VLS_309;
const __VLS_318 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_319 = __VLS_asFunctionalComponent(__VLS_318, new __VLS_318({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
    ...{ class: "shadow-sm hover:shadow" },
}));
const __VLS_320 = __VLS_319({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.saving),
    ...{ class: "shadow-sm hover:shadow" },
}, ...__VLS_functionalComponentArgsRest(__VLS_319));
let __VLS_322;
let __VLS_323;
let __VLS_324;
const __VLS_325 = {
    onClick: (__VLS_ctx.submit)
};
__VLS_321.slots.default;
var __VLS_321;
var __VLS_297;
var __VLS_223;
var __VLS_219;
/** @type {__VLS_StyleScopedClasses['studio']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-[60vh]']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['md:p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-slate-50']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['w-9']} */ ;
/** @type {__VLS_StyleScopedClasses['h-9']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['md:text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['md:text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['studio__main']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-[420px]']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-900']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-900']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-end']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow']} */ ;
// @ts-ignore
var __VLS_225 = __VLS_224;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            UploadOutlined: icons_vue_1.UploadOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            ApiOutlined: icons_vue_1.ApiOutlined,
            loading: loading,
            saving: saving,
            testing: testing,
            providers: providers,
            selectedConfig: selectedConfig,
            search: search,
            drawerOpen: drawerOpen,
            formRef: formRef,
            form: form,
            models: models,
            customParamsText: customParamsText,
            rules: rules,
            testStatus: testStatus,
            quickPresets: quickPresets,
            filteredConfigs: filteredConfigs,
            formatDate: formatDate,
            loadAll: loadAll,
            select: select,
            setDefault: setDefault,
            remove: remove,
            openCreate: openCreate,
            openEdit: openEdit,
            onProviderChanged: onProviderChanged,
            submit: submit,
            test: test,
            testTemp: testTemp,
            onImport: onImport,
            exportCurrent: exportCurrent,
            applyPreset: applyPreset,
            drawerTitle: drawerTitle,
        };
    },
    __typeEmits: {},
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
});
; /* PartiallyEnd: #4569/main.vue */
