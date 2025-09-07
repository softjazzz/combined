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
// 新增状态
const testing = (0, vue_1.ref)(false);
const emit = defineEmits();
// 响应式数据
const loading = (0, vue_1.ref)(false);
const saving = (0, vue_1.ref)(false);
const showCreateModal = (0, vue_1.ref)(false);
const editingConfig = (0, vue_1.ref)(null);
const providers = (0, vue_1.ref)(: any[]);
const availableModels = (0, vue_1.ref)(: any[]);
const userConfigs = (0, vue_1.ref)(: any[]);
const currentConfig = (0, vue_1.ref)(null);
// 表单数据
const configForm = (0, vue_1.reactive)({
    config_name: '',
    provider_id: '',
    model_id: '',
    api_key: '',
    custom_endpoint: '',
    custom_parameters: {},
    is_active: true
});
const customParametersText = (0, vue_1.ref)('');
// 计算属性
const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleString('zh-CN');
};
// 方法
const loadProviders = async () => {
    try {
        providers.value = await llmConfigService_1.llmConfigService.getProviders();
    }
    catch (error) {
        ant_design_vue_1.message.error('加载API提供商失败');
        console.error(error);
    }
};
const loadConfigs = async () => {
    loading.value = true;
    try {
        userConfigs.value = await llmConfigService_1.llmConfigService.getUserConfigs();
        // 尝试加载默认配置
        const defaultConfig = userConfigs.value.find(c => c.config_name === 'default');
        if (defaultConfig) {
            currentConfig.value = defaultConfig;
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('加载配置失败');
        console.error(error);
    }
    finally {
        loading.value = false;
    }
};
const onProviderChange = async (providerId) => {
    try {
        availableModels.value = await llmConfigService_1.llmConfigService.getModelsByProvider(providerId);
        configForm.model_id = ''; // 重置模型选择
    }
    catch (error) {
        ant_design_vue_1.message.error('加载模型失败');
        console.error(error);
    }
};
const loadConfig = (config) => {
    currentConfig.value = config;
    emit('config-updated', config);
    // 同步到运行时服务，便于立即使用
    llmServiceNew_1.llmService.updateConfig({
        apiEndpoint: config.custom_endpoint || (config.provider?.base_endpoint || ''),
        apiKey: config.api_key_decrypted || '',
        model: config.model?.model_code || ''
    });
    ant_design_vue_1.message.success(`已切换到配置: ${config.config_name}`);
};
const editConfig = (config) => {
    editingConfig.value = config;
    Object.assign(configForm, {
        config_name: config.config_name,
        provider_id: config.provider_id,
        model_id: config.model_id,
        api_key: '', // 不显示已保存的密钥
        custom_endpoint: config.custom_endpoint || '',
        custom_parameters: config.custom_parameters || {},
        is_active: config.is_active
    });
    customParametersText.value = JSON.stringify(config.custom_parameters || {}, null, 2);
    // 加载对应的模型
    if (config.provider_id) {
        onProviderChange(config.provider_id);
    }
    showCreateModal.value = true;
};
const deleteConfig = async (configId) => {
    try {
        await llmConfigService_1.llmConfigService.deleteConfig(configId);
        ant_design_vue_1.message.success('配置已删除');
        await loadConfigs();
    }
    catch (error) {
        ant_design_vue_1.message.error('删除配置失败');
        console.error(error);
    }
};
const saveConfig = async () => {
    if (!configForm.config_name || !configForm.provider_id || !configForm.model_id) {
        ant_design_vue_1.message.error('请填写必填字段');
        return;
    }
    saving.value = true;
    try {
        // 解析自定义参数
        let customParams = {};
        if (customParametersText.value.trim()) {
            try {
                customParams = JSON.parse(customParametersText.value);
            }
            catch (e) {
                ant_design_vue_1.message.error('自定义参数格式错误，请检查JSON格式');
                saving.value = false;
                return;
            }
        }
        const configData = {
            ...configForm,
            custom_parameters: customParams
        };
        const savedConfig = await llmConfigService_1.llmConfigService.saveConfig(configData);
        ant_design_vue_1.message.success(editingConfig.value ? '配置已更新' : '配置已创建');
        showCreateModal.value = false;
        await loadConfigs();
        // 如果是默认配置，自动加载
        if (savedConfig.config_name === 'default') {
            loadConfig(savedConfig);
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('保存配置失败');
        console.error(error);
    }
    finally {
        saving.value = false;
    }
};
const cancelEdit = () => {
    editingConfig.value = null;
    Object.assign(configForm, {
        config_name: '',
        provider_id: '',
        model_id: '',
        api_key: '',
        custom_endpoint: '',
        custom_parameters: {},
        is_active: true
    });
    customParametersText.value = '';
    showCreateModal.value = false;
};
const quickConfig = (type) => {
    // 快速配置逻辑
    const quickConfigs = {
        alibaba: {
            config_name: 'alibaba_quick',
            provider_code: 'alibaba'
        },
        baidu: {
            config_name: 'baidu_quick',
            provider_code: 'baidu'
        },
        local: {
            config_name: 'local_quick',
            provider_code: 'local'
        }
    };
    const config = quickConfigs[type];
    if (config) {
        const provider = providers.value.find(p => p.provider_code === config.provider_code);
        if (provider) {
            configForm.config_name = config.config_name;
            configForm.provider_id = provider.id;
            onProviderChange(provider.id);
            showCreateModal.value = true;
        }
    }
};
// 工具函数：导入/导出/测试
const exportConfig = () => {
    const data = JSON.stringify(configForm, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${configForm.config_name || 'llm_config'}.json`;
    a.click();
    URL.revokeObjectURL(url);
    ant_design_vue_1.message.success('配置已导出');
};
const handleImportConfig = async (file) => {
    try {
        const text = await file.text();
        const data = JSON.parse(text);
        Object.assign(configForm, {
            config_name: data.config_name || '',
            provider_id: data.provider_id || '',
            model_id: data.model_id || '',
            api_key: data.api_key || '',
            custom_endpoint: data.custom_endpoint || '',
            custom_parameters: data.custom_parameters || {},
            is_active: data.is_active !== false
        });
        customParametersText.value = JSON.stringify(configForm.custom_parameters || {}, null, 2);
        if (configForm.provider_id)
            await onProviderChange(configForm.provider_id);
        ant_design_vue_1.message.success('配置已导入');
    }
    catch (e) {
        ant_design_vue_1.message.error('导入失败：JSON格式不正确');
    }
    return false;
};
const testConnection = async () => {
    try {
        testing.value = true;
        // 将当前表单应用到 llmService，仅用于测试
        llmServiceNew_1.llmService.updateConfig({
            apiEndpoint: configForm.custom_endpoint || (currentConfig.value?.provider?.base_endpoint || ''),
            apiKey: configForm.api_key,
            model: availableModels.value.find(m => m.id === configForm.model_id)?.model_code || ''
        });
        // 调用一个轻量 probe（使用已有 parseMedicalText 的最小请求）
        const result = await llmServiceNew_1.llmService.parseMedicalText('ping', { maxTokens: 5, temperature: 0 });
        if (result.success) {
            ant_design_vue_1.message.success('连接正常');
        }
        else {
            ant_design_vue_1.message.error(result.error || '连接失败');
        }
    }
    catch (e) {
        ant_design_vue_1.message.error(`连接失败：${e.message || e}`);
    }
    finally {
        testing.value = false;
    }
};
// 生命周期
(0, vue_1.onMounted)(async () => {
    await loadProviders();
    await loadConfigs();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['quick-config']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-card']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "llm-api-config-database" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    size: "small",
}));
const __VLS_2 = __VLS_1({
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "config-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "config-header mb-4" },
});
const __VLS_4 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    gutter: (16),
    align: "middle",
}));
const __VLS_6 = __VLS_5({
    gutter: (16),
    align: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    flex: "auto",
}));
const __VLS_10 = __VLS_9({
    flex: "auto",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "mb-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-sm text-gray-500 mb-0" },
});
var __VLS_11;
const __VLS_12 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
const __VLS_20 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.loadConfigs)
};
__VLS_23.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_23.slots;
    const __VLS_28 = {}.ReloadOutlined;
    /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
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
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showCreateModal = true;
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
var __VLS_19;
var __VLS_15;
var __VLS_7;
if (__VLS_ctx.userConfigs.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "config-list mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({});
    const __VLS_44 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        size: "small",
        dataSource: (__VLS_ctx.userConfigs),
    }));
    const __VLS_46 = __VLS_45({
        size: "small",
        dataSource: (__VLS_ctx.userConfigs),
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_47.slots;
        const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_48 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
        const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
        __VLS_51.slots.default;
        {
            const { actions: __VLS_thisSlot } = __VLS_51.slots;
            const __VLS_52 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
                ...{ 'onClick': {} },
                size: "small",
            }));
            const __VLS_54 = __VLS_53({
                ...{ 'onClick': {} },
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_53));
            let __VLS_56;
            let __VLS_57;
            let __VLS_58;
            const __VLS_59 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.userConfigs.length > 0))
                        return;
                    __VLS_ctx.loadConfig(item);
                }
            };
            __VLS_55.slots.default;
            var __VLS_55;
            const __VLS_60 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
                ...{ 'onClick': {} },
                size: "small",
            }));
            const __VLS_62 = __VLS_61({
                ...{ 'onClick': {} },
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_61));
            let __VLS_64;
            let __VLS_65;
            let __VLS_66;
            const __VLS_67 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.userConfigs.length > 0))
                        return;
                    __VLS_ctx.editConfig(item);
                }
            };
            __VLS_63.slots.default;
            var __VLS_63;
            const __VLS_68 = {}.APopconfirm;
            /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
            // @ts-ignore
            const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
                ...{ 'onConfirm': {} },
                title: "确定要删除这个配置吗？",
            }));
            const __VLS_70 = __VLS_69({
                ...{ 'onConfirm': {} },
                title: "确定要删除这个配置吗？",
            }, ...__VLS_functionalComponentArgsRest(__VLS_69));
            let __VLS_72;
            let __VLS_73;
            let __VLS_74;
            const __VLS_75 = {
                onConfirm: (...[$event]) => {
                    if (!(__VLS_ctx.userConfigs.length > 0))
                        return;
                    __VLS_ctx.deleteConfig(item.id);
                }
            };
            __VLS_71.slots.default;
            const __VLS_76 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
                size: "small",
                danger: true,
            }));
            const __VLS_78 = __VLS_77({
                size: "small",
                danger: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_77));
            __VLS_79.slots.default;
            var __VLS_79;
            var __VLS_71;
        }
        const __VLS_80 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
        const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
        __VLS_83.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_83.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.config_name);
            if (item.config_name === 'default') {
                const __VLS_84 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
                    color: "blue",
                    size: "small",
                    ...{ class: "ml-2" },
                }));
                const __VLS_86 = __VLS_85({
                    color: "blue",
                    size: "small",
                    ...{ class: "ml-2" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_85));
                __VLS_87.slots.default;
                var __VLS_87;
            }
        }
        {
            const { description: __VLS_thisSlot } = __VLS_83.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-xs" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.provider?.provider_name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "mx-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.model?.model_name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "mx-2" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-gray-400" },
            });
            (__VLS_ctx.formatDate(item.updated_at));
        }
        var __VLS_83;
        var __VLS_51;
    }
    var __VLS_47;
}
if (__VLS_ctx.currentConfig) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "current-config" },
    });
    const __VLS_88 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        message: (`当前使用配置: ${__VLS_ctx.currentConfig.config_name}`),
        description: (`${__VLS_ctx.currentConfig.provider?.provider_name} - ${__VLS_ctx.currentConfig.model?.model_name}`),
        type: "info",
        showIcon: true,
        ...{ class: "mb-4" },
    }));
    const __VLS_90 = __VLS_89({
        message: (`当前使用配置: ${__VLS_ctx.currentConfig.config_name}`),
        description: (`${__VLS_ctx.currentConfig.provider?.provider_name} - ${__VLS_ctx.currentConfig.model?.model_name}`),
        type: "info",
        showIcon: true,
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "quick-config" },
});
const __VLS_92 = {}.ADivider;
/** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({}));
const __VLS_94 = __VLS_93({}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
var __VLS_95;
const __VLS_96 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    gutter: (16),
}));
const __VLS_98 = __VLS_97({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
__VLS_99.slots.default;
const __VLS_100 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    span: (8),
}));
const __VLS_102 = __VLS_101({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
__VLS_103.slots.default;
const __VLS_104 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    ...{ 'onClick': {} },
    size: "small",
    hoverable: true,
}));
const __VLS_106 = __VLS_105({
    ...{ 'onClick': {} },
    size: "small",
    hoverable: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
let __VLS_108;
let __VLS_109;
let __VLS_110;
const __VLS_111 = {
    onClick: (...[$event]) => {
        __VLS_ctx.quickConfig('alibaba');
    }
};
__VLS_107.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "font-medium" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-gray-500" },
});
var __VLS_107;
var __VLS_103;
const __VLS_112 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    span: (8),
}));
const __VLS_114 = __VLS_113({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
const __VLS_116 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    ...{ 'onClick': {} },
    size: "small",
    hoverable: true,
}));
const __VLS_118 = __VLS_117({
    ...{ 'onClick': {} },
    size: "small",
    hoverable: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
let __VLS_120;
let __VLS_121;
let __VLS_122;
const __VLS_123 = {
    onClick: (...[$event]) => {
        __VLS_ctx.quickConfig('baidu');
    }
};
__VLS_119.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "font-medium" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-gray-500" },
});
var __VLS_119;
var __VLS_115;
const __VLS_124 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    span: (8),
}));
const __VLS_126 = __VLS_125({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
const __VLS_128 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    ...{ 'onClick': {} },
    size: "small",
    hoverable: true,
}));
const __VLS_130 = __VLS_129({
    ...{ 'onClick': {} },
    size: "small",
    hoverable: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
let __VLS_132;
let __VLS_133;
let __VLS_134;
const __VLS_135 = {
    onClick: (...[$event]) => {
        __VLS_ctx.quickConfig('local');
    }
};
__VLS_131.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-lg mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "font-medium" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-gray-500" },
});
var __VLS_131;
var __VLS_127;
var __VLS_99;
var __VLS_3;
const __VLS_136 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showCreateModal),
    title: (__VLS_ctx.editingConfig ? '编辑配置' : '创建新配置'),
    width: "900px",
    confirmLoading: (__VLS_ctx.saving),
}));
const __VLS_138 = __VLS_137({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.showCreateModal),
    title: (__VLS_ctx.editingConfig ? '编辑配置' : '创建新配置'),
    width: "900px",
    confirmLoading: (__VLS_ctx.saving),
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
let __VLS_140;
let __VLS_141;
let __VLS_142;
const __VLS_143 = {
    onOk: (__VLS_ctx.saveConfig)
};
const __VLS_144 = {
    onCancel: (__VLS_ctx.cancelEdit)
};
__VLS_139.slots.default;
const __VLS_145 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
    model: (__VLS_ctx.configForm),
    layout: "vertical",
}));
const __VLS_147 = __VLS_146({
    model: (__VLS_ctx.configForm),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_146));
__VLS_148.slots.default;
const __VLS_149 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
    size: "small",
    ...{ class: "mb-3" },
    bordered: (false),
}));
const __VLS_151 = __VLS_150({
    size: "small",
    ...{ class: "mb-3" },
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_150));
__VLS_152.slots.default;
{
    const { title: __VLS_thisSlot } = __VLS_152.slots;
    const __VLS_153 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({}));
    const __VLS_155 = __VLS_154({}, ...__VLS_functionalComponentArgsRest(__VLS_154));
    __VLS_156.slots.default;
    const __VLS_157 = {}.ApiOutlined;
    /** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({}));
    const __VLS_159 = __VLS_158({}, ...__VLS_functionalComponentArgsRest(__VLS_158));
    var __VLS_156;
}
const __VLS_161 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
    gutter: (16),
}));
const __VLS_163 = __VLS_162({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_162));
__VLS_164.slots.default;
const __VLS_165 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
    span: (12),
}));
const __VLS_167 = __VLS_166({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_166));
__VLS_168.slots.default;
const __VLS_169 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({
    label: "配置名称",
    required: true,
    rules: ([{ required: true, message: '请输入配置名称' }]),
}));
const __VLS_171 = __VLS_170({
    label: "配置名称",
    required: true,
    rules: ([{ required: true, message: '请输入配置名称' }]),
}, ...__VLS_functionalComponentArgsRest(__VLS_170));
__VLS_172.slots.default;
const __VLS_173 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_174 = __VLS_asFunctionalComponent(__VLS_173, new __VLS_173({
    value: (__VLS_ctx.configForm.config_name),
    placeholder: "如: default, medical_analysis",
}));
const __VLS_175 = __VLS_174({
    value: (__VLS_ctx.configForm.config_name),
    placeholder: "如: default, medical_analysis",
}, ...__VLS_functionalComponentArgsRest(__VLS_174));
var __VLS_172;
var __VLS_168;
const __VLS_177 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_178 = __VLS_asFunctionalComponent(__VLS_177, new __VLS_177({
    span: (12),
}));
const __VLS_179 = __VLS_178({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_178));
__VLS_180.slots.default;
const __VLS_181 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
    label: "API提供商",
    required: true,
    rules: ([{ required: true, message: '请选择提供商' }]),
}));
const __VLS_183 = __VLS_182({
    label: "API提供商",
    required: true,
    rules: ([{ required: true, message: '请选择提供商' }]),
}, ...__VLS_functionalComponentArgsRest(__VLS_182));
__VLS_184.slots.default;
const __VLS_185 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_186 = __VLS_asFunctionalComponent(__VLS_185, new __VLS_185({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.configForm.provider_id),
    placeholder: "请选择提供商",
}));
const __VLS_187 = __VLS_186({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.configForm.provider_id),
    placeholder: "请选择提供商",
}, ...__VLS_functionalComponentArgsRest(__VLS_186));
let __VLS_189;
let __VLS_190;
let __VLS_191;
const __VLS_192 = {
    onChange: (__VLS_ctx.onProviderChange)
};
__VLS_188.slots.default;
for (const [provider] of __VLS_getVForSourceType((__VLS_ctx.providers))) {
    const __VLS_193 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_194 = __VLS_asFunctionalComponent(__VLS_193, new __VLS_193({
        key: (provider.id),
        value: (provider.id),
    }));
    const __VLS_195 = __VLS_194({
        key: (provider.id),
        value: (provider.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_194));
    __VLS_196.slots.default;
    (provider.provider_name);
    var __VLS_196;
}
var __VLS_188;
var __VLS_184;
var __VLS_180;
var __VLS_164;
const __VLS_197 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_198 = __VLS_asFunctionalComponent(__VLS_197, new __VLS_197({
    gutter: (16),
}));
const __VLS_199 = __VLS_198({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_198));
__VLS_200.slots.default;
const __VLS_201 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_202 = __VLS_asFunctionalComponent(__VLS_201, new __VLS_201({
    span: (12),
}));
const __VLS_203 = __VLS_202({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_202));
__VLS_204.slots.default;
const __VLS_205 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_206 = __VLS_asFunctionalComponent(__VLS_205, new __VLS_205({
    label: "模型",
    required: true,
    rules: ([{ required: true, message: '请选择模型' }]),
}));
const __VLS_207 = __VLS_206({
    label: "模型",
    required: true,
    rules: ([{ required: true, message: '请选择模型' }]),
}, ...__VLS_functionalComponentArgsRest(__VLS_206));
__VLS_208.slots.default;
const __VLS_209 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_210 = __VLS_asFunctionalComponent(__VLS_209, new __VLS_209({
    value: (__VLS_ctx.configForm.model_id),
    disabled: (!__VLS_ctx.availableModels.length),
    placeholder: "请选择模型",
}));
const __VLS_211 = __VLS_210({
    value: (__VLS_ctx.configForm.model_id),
    disabled: (!__VLS_ctx.availableModels.length),
    placeholder: "请选择模型",
}, ...__VLS_functionalComponentArgsRest(__VLS_210));
__VLS_212.slots.default;
for (const [model] of __VLS_getVForSourceType((__VLS_ctx.availableModels))) {
    const __VLS_213 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_214 = __VLS_asFunctionalComponent(__VLS_213, new __VLS_213({
        key: (model.id),
        value: (model.id),
    }));
    const __VLS_215 = __VLS_214({
        key: (model.id),
        value: (model.id),
    }, ...__VLS_functionalComponentArgsRest(__VLS_214));
    __VLS_216.slots.default;
    (model.display_name || model.model_name);
    var __VLS_216;
}
var __VLS_212;
var __VLS_208;
var __VLS_204;
const __VLS_217 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_218 = __VLS_asFunctionalComponent(__VLS_217, new __VLS_217({
    span: (12),
}));
const __VLS_219 = __VLS_218({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_218));
__VLS_220.slots.default;
const __VLS_221 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_222 = __VLS_asFunctionalComponent(__VLS_221, new __VLS_221({
    label: "API密钥",
    extra: ('部分提供商必填，保存时将加密存储'),
}));
const __VLS_223 = __VLS_222({
    label: "API密钥",
    extra: ('部分提供商必填，保存时将加密存储'),
}, ...__VLS_functionalComponentArgsRest(__VLS_222));
__VLS_224.slots.default;
const __VLS_225 = {}.AInputPassword;
/** @type {[typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, ]} */ ;
// @ts-ignore
const __VLS_226 = __VLS_asFunctionalComponent(__VLS_225, new __VLS_225({
    value: (__VLS_ctx.configForm.api_key),
    placeholder: "输入API密钥",
    visibilityToggle: (true),
}));
const __VLS_227 = __VLS_226({
    value: (__VLS_ctx.configForm.api_key),
    placeholder: "输入API密钥",
    visibilityToggle: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_226));
var __VLS_224;
var __VLS_220;
var __VLS_200;
var __VLS_152;
const __VLS_229 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_230 = __VLS_asFunctionalComponent(__VLS_229, new __VLS_229({
    size: "small",
    ...{ class: "mb-3" },
    bordered: (false),
}));
const __VLS_231 = __VLS_230({
    size: "small",
    ...{ class: "mb-3" },
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_230));
__VLS_232.slots.default;
{
    const { title: __VLS_thisSlot } = __VLS_232.slots;
    const __VLS_233 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_234 = __VLS_asFunctionalComponent(__VLS_233, new __VLS_233({}));
    const __VLS_235 = __VLS_234({}, ...__VLS_functionalComponentArgsRest(__VLS_234));
    __VLS_236.slots.default;
    const __VLS_237 = {}.CloudOutlined;
    /** @type {[typeof __VLS_components.CloudOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_238 = __VLS_asFunctionalComponent(__VLS_237, new __VLS_237({}));
    const __VLS_239 = __VLS_238({}, ...__VLS_functionalComponentArgsRest(__VLS_238));
    var __VLS_236;
}
const __VLS_241 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_242 = __VLS_asFunctionalComponent(__VLS_241, new __VLS_241({
    label: "自定义端点 (可选)",
}));
const __VLS_243 = __VLS_242({
    label: "自定义端点 (可选)",
}, ...__VLS_functionalComponentArgsRest(__VLS_242));
__VLS_244.slots.default;
const __VLS_245 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_246 = __VLS_asFunctionalComponent(__VLS_245, new __VLS_245({
    value: (__VLS_ctx.configForm.custom_endpoint),
    placeholder: "如: https://api.example.com/v1/chat/completions",
}));
const __VLS_247 = __VLS_246({
    value: (__VLS_ctx.configForm.custom_endpoint),
    placeholder: "如: https://api.example.com/v1/chat/completions",
}, ...__VLS_functionalComponentArgsRest(__VLS_246));
var __VLS_244;
const __VLS_249 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_250 = __VLS_asFunctionalComponent(__VLS_249, new __VLS_249({
    label: "自定义参数 (JSON格式，可选)",
}));
const __VLS_251 = __VLS_250({
    label: "自定义参数 (JSON格式，可选)",
}, ...__VLS_functionalComponentArgsRest(__VLS_250));
__VLS_252.slots.default;
const __VLS_253 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_254 = __VLS_asFunctionalComponent(__VLS_253, new __VLS_253({
    value: (__VLS_ctx.customParametersText),
    rows: (4),
    placeholder: '{"temperature": 0.7, "max_tokens": 2000}',
}));
const __VLS_255 = __VLS_254({
    value: (__VLS_ctx.customParametersText),
    rows: (4),
    placeholder: '{"temperature": 0.7, "max_tokens": 2000}',
}, ...__VLS_functionalComponentArgsRest(__VLS_254));
var __VLS_252;
var __VLS_232;
const __VLS_257 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_258 = __VLS_asFunctionalComponent(__VLS_257, new __VLS_257({}));
const __VLS_259 = __VLS_258({}, ...__VLS_functionalComponentArgsRest(__VLS_258));
__VLS_260.slots.default;
const __VLS_261 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_262 = __VLS_asFunctionalComponent(__VLS_261, new __VLS_261({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing),
}));
const __VLS_263 = __VLS_262({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing),
}, ...__VLS_functionalComponentArgsRest(__VLS_262));
let __VLS_265;
let __VLS_266;
let __VLS_267;
const __VLS_268 = {
    onClick: (__VLS_ctx.testConnection)
};
__VLS_264.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_264.slots;
    const __VLS_269 = {}.ApiOutlined;
    /** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_270 = __VLS_asFunctionalComponent(__VLS_269, new __VLS_269({}));
    const __VLS_271 = __VLS_270({}, ...__VLS_functionalComponentArgsRest(__VLS_270));
}
var __VLS_264;
const __VLS_273 = {}.AUpload;
/** @type {[typeof __VLS_components.AUpload, typeof __VLS_components.aUpload, typeof __VLS_components.AUpload, typeof __VLS_components.aUpload, ]} */ ;
// @ts-ignore
const __VLS_274 = __VLS_asFunctionalComponent(__VLS_273, new __VLS_273({
    beforeUpload: (__VLS_ctx.handleImportConfig),
    showUploadList: (false),
}));
const __VLS_275 = __VLS_274({
    beforeUpload: (__VLS_ctx.handleImportConfig),
    showUploadList: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_274));
__VLS_276.slots.default;
const __VLS_277 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_278 = __VLS_asFunctionalComponent(__VLS_277, new __VLS_277({}));
const __VLS_279 = __VLS_278({}, ...__VLS_functionalComponentArgsRest(__VLS_278));
__VLS_280.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_280.slots;
    const __VLS_281 = {}.UploadOutlined;
    /** @type {[typeof __VLS_components.UploadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_282 = __VLS_asFunctionalComponent(__VLS_281, new __VLS_281({}));
    const __VLS_283 = __VLS_282({}, ...__VLS_functionalComponentArgsRest(__VLS_282));
}
var __VLS_280;
var __VLS_276;
const __VLS_285 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_286 = __VLS_asFunctionalComponent(__VLS_285, new __VLS_285({
    ...{ 'onClick': {} },
}));
const __VLS_287 = __VLS_286({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_286));
let __VLS_289;
let __VLS_290;
let __VLS_291;
const __VLS_292 = {
    onClick: (__VLS_ctx.exportConfig)
};
__VLS_288.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_288.slots;
    const __VLS_293 = {}.DownloadOutlined;
    /** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_294 = __VLS_asFunctionalComponent(__VLS_293, new __VLS_293({}));
    const __VLS_295 = __VLS_294({}, ...__VLS_functionalComponentArgsRest(__VLS_294));
}
var __VLS_288;
var __VLS_260;
var __VLS_148;
var __VLS_139;
/** @type {__VLS_StyleScopedClasses['llm-api-config-database']} */ ;
/** @type {__VLS_StyleScopedClasses['config-content']} */ ;
/** @type {__VLS_StyleScopedClasses['config-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-0']} */ ;
/** @type {__VLS_StyleScopedClasses['config-list']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['current-config']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['quick-config']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            CloudOutlined: icons_vue_1.CloudOutlined,
            UploadOutlined: icons_vue_1.UploadOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            ApiOutlined: icons_vue_1.ApiOutlined,
            testing: testing,
            loading: loading,
            saving: saving,
            showCreateModal: showCreateModal,
            editingConfig: editingConfig,
            providers: providers,
            availableModels: availableModels,
            userConfigs: userConfigs,
            currentConfig: currentConfig,
            configForm: configForm,
            customParametersText: customParametersText,
            formatDate: formatDate,
            loadConfigs: loadConfigs,
            onProviderChange: onProviderChange,
            loadConfig: loadConfig,
            editConfig: editConfig,
            deleteConfig: deleteConfig,
            saveConfig: saveConfig,
            cancelEdit: cancelEdit,
            quickConfig: quickConfig,
            exportConfig: exportConfig,
            handleImportConfig: handleImportConfig,
            testConnection: testConnection,
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
