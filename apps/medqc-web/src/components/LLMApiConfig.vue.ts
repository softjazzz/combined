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
import llmConfigService_1 from '@/services/llmConfigService';
import icons_vue_1 from '@ant-design/icons-vue';
import llmApiConfig_1 from '@/services/llmApiConfig';
import llmServiceNew_1 from '@/services/llmServiceNew';
const emit = defineEmits();
// 响应式数据
const selectedConfig = (0, vue_1.ref)('mock');
const selectedModel = (0, vue_1.ref)('');
const apiKey = (0, vue_1.ref)('');
const customEndpoint = (0, vue_1.ref)('');
const testing = (0, vue_1.ref)(false);
const testResult = (0, vue_1.ref)(null);
// 配置管理器
const configManager = new llmApiConfig_1.EnhancedLLMApiConfigManager();
// 可用配置
const availableConfigs = (0, vue_1.computed)(() => Object.values(llmApiConfig_1.ENHANCED_LLM_API_CONFIGS));
// 当前配置
const currentConfig = (0, vue_1.computed)(() => llmApiConfig_1.ENHANCED_LLM_API_CONFIGS[selectedConfig.value]);
// 可用模型
const availableModels = (0, vue_1.computed)(() => {
    return currentConfig.value?.availableModels || [];
});
// 当前模型信息
const currentModelInfo = (0, vue_1.computed)(() => {
    if (!currentConfig.value || !selectedModel.value)
        return null;
    return currentConfig.value.availableModels.find(m => m.value === selectedModel.value);
});
// 配置状态
const configStatus = (0, vue_1.computed)(() => {
    const config = currentConfig.value;
    if (!config) {
        return { valid: false, type: 'error', message: '未选择配置' };
    }
    if (config.requiresApiKey && !apiKey.value) {
        return {
            valid: false,
            type: 'warning',
            message: `${config.displayName} 需要配置API密钥`
        };
    }
    return {
        valid: true,
        type: 'success',
        message: `${config.displayName} 配置完成`
    };
});
// 方法
const handleConfigChange = () => {
    configManager.switchConfig(selectedConfig.value, apiKey.value);
    // 重置模型选择为默认模型
    selectedModel.value = currentConfig.value?.defaultModel || '';
    testResult.value = null;
};
const handleModelChange = () => {
    if (selectedModel.value) {
        configManager.switchModel(selectedModel.value);
    }
    testResult.value = null;
};
const handleApiKeyChange = () => {
    configManager.setApiKey(apiKey.value);
};
const handleEndpointChange = () => {
    // 更新本地配置的端点
    if (selectedConfig.value === 'local') {
        llmApiConfig_1.ENHANCED_LLM_API_CONFIGS.local.endpoint = customEndpoint.value;
    }
};
const getFeatureColor = (feature) => {
    const colorMap = {
        '高准确率': 'green',
        '中文优化': 'blue',
        '企业级': 'purple',
        '医疗专业': 'red',
        '开源友好': 'orange',
        '数据私有': 'cyan',
        '开发测试': 'default',
        '高并发': 'purple',
        '多模态': 'geekblue',
        '安全合规': 'green',
        '可本地部署': 'orange'
    };
    return colorMap[feature] || 'default';
};
const getPricingColor = (pricing) => {
    const colorMap = {
        '免费': 'green',
        '很低': 'cyan',
        '低': 'blue',
        '中': 'orange',
        '高': 'red',
        '很高': 'magenta'
    };
    return colorMap[pricing || ''] || 'default';
};
const getApiKeyHelp = () => {
    const helpMap = {
        'openai': '在 OpenAI 官网获取 API Key',
        'baidu': '在百度智能云控制台获取 Access Token',
        'alibaba': '在阿里云控制台获取 API Key',
        'tencent': '在腾讯云控制台获取 SecretId 和 SecretKey',
        'zhipu': '在智谱AI开放平台获取 API Key'
    };
    return helpMap[selectedConfig.value] || '请联系服务提供商获取API密钥';
};
const testConnection = async () => {
    testing.value = true;
    testResult.value = null;
    try {
        // 创建LLM服务实例
        const llmService = new llmServiceNew_1.LLMService({
            apiEndpoint: currentConfig.value.endpoint,
            apiKey: apiKey.value,
            model: selectedModel.value || currentConfig.value.defaultModel
        });
        // 发送测试请求
        const testPrompt = '请回复"连接测试成功"';
        const result = await llmService.parseMedicalText(testPrompt, {
            confidenceThreshold: 0.5
        });
        if (result.success) {
            testResult.value = {
                success: true,
                message: '连接测试成功',
                details: `响应时间: ${result.processingTime}ms`
            };
            ant_design_vue_1.message.success('API连接测试成功');
        }
        else {
            throw new Error(result.error || '未知错误');
        }
    }
    catch (error) {
        testResult.value = {
            success: false,
            message: '连接测试失败',
            details: error instanceof Error ? error.message : '未知错误'
        };
        ant_design_vue_1.message.error('API连接测试失败');
    }
    finally {
        testing.value = false;
    }
};
const saveConfig = async () => {
    try {
        // 将当前选择映射到数据库的 provider/model，再保存为默认配置
        // 1) 获取提供商列表，定位所选 provider_code 对应的记录
        const providers = await llmConfigService_1.llmConfigService.getProviders();
        const provider = providers.find(p => p.provider_code === selectedConfig.value);
        if (!provider) {
            ant_design_vue_1.message.error('未找到所选提供商');
            return;
        }
        // 2) 获取该提供商下的模型，按选中的 model code 定位
        const models = await llmConfigService_1.llmConfigService.getModelsByProvider(provider.id);
        // 兼容：UI里 selectedModel 是模型 code（如 qwen-plus）
        const model = models.find(m => m.model_code === (selectedModel.value || (currentConfig.value?.defaultModel || '')));
        if (!model) {
            ant_design_vue_1.message.error('未找到所选模型');
            return;
        }
        // 3) 组织数据并保存到 Supabase（config_name 统一为 default）
        const saved = await llmConfigService_1.llmConfigService.saveConfig({
            config_name: 'default',
            provider_id: provider.id,
            model_id: model.id,
            api_key: apiKey.value || undefined,
            custom_endpoint: customEndpoint.value || undefined,
            custom_parameters: {},
            is_active: true
        });
        // 同步到运行时（可立即测试）
        const endpoint = saved.custom_endpoint || (saved.provider?.base_endpoint || '');
        if (endpoint) {
            const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
            llmService.updateConfig({ apiEndpoint: endpoint, apiKey: apiKey.value || '', model: saved.model?.model_code || '' });
        }
        ant_design_vue_1.message.success('配置已保存到数据库');
        // 通知外部和全局
        const payload = { selectedConfig: selectedConfig.value, selectedModel: selectedModel.value, apiKey: apiKey.value, customEndpoint: customEndpoint.value, timestamp: Date.now() };
        window.dispatchEvent(new CustomEvent('llm-config-updated', { detail: payload }));
        emit('config-updated', payload);
    }
    catch (e) {
        console.error(e);
        ant_design_vue_1.message.error('保存失败：' + (e?.message || e));
    }
};
const loadConfig = async () => {
    try {
        // 1) 优先从数据库读取默认配置
        // 优先加载用户默认，其次全局默认
        let dbConfig = await llmConfigService_1.llmConfigService.getConfigByName('default');
        if (!dbConfig)
            dbConfig = await llmConfigService_1.llmConfigService.getConfigByName('default');
        if (dbConfig) {
            // 先设置提供商（provider_code），再设置模型，避免 watcher 覆盖
            selectedConfig.value = dbConfig.provider?.provider_code || 'alibaba';
            selectedModel.value = dbConfig.model?.model_code || '';
            apiKey.value = dbConfig.api_key_decrypted || '';
            customEndpoint.value = dbConfig.custom_endpoint || '';
            // 同步到本地管理器（用于测试连接等）
            configManager.switchConfig(selectedConfig.value, apiKey.value);
            if (selectedModel.value)
                configManager.switchModel(selectedModel.value);
            return;
        }
        // 2) 向后兼容：无数据库记录时，尝试从 localStorage 恢复
        const savedConfig = typeof localStorage !== 'undefined' ? localStorage.getItem('llm-api-config') : null;
        if (savedConfig) {
            const configData = JSON.parse(savedConfig);
            selectedConfig.value = configData.selectedConfig || 'mock';
            selectedModel.value = configData.selectedModel || '';
            apiKey.value = configData.apiKey || '';
            customEndpoint.value = configData.customEndpoint || '';
            configManager.switchConfig(selectedConfig.value, apiKey.value);
            if (selectedModel.value)
                configManager.switchModel(selectedModel.value);
        }
        else {
            // 初始化默认模型
            selectedModel.value = currentConfig.value?.defaultModel || '';
        }
    }
    catch (error) {
        console.error('加载配置失败:', error);
        selectedModel.value = currentConfig.value?.defaultModel || '';
    }
};
// 监听配置变化
(0, vue_1.watch)([selectedConfig, selectedModel: any, apiKey], () => {
    testResult.value = null;
});
// 监听配置变化，自动设置默认模型
(0, vue_1.watch)(selectedConfig: any, () => {
    if (currentConfig.value) {
        selectedModel.value = currentConfig.value.defaultModel;
    }
});
// 组件挂载时加载配置
(0, vue_1.onMounted)(async () => {
    await loadConfig();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['config-section']} */ ;
/** @type {__VLS_StyleScopedClasses['config-option']} */ ;
/** @type {__VLS_StyleScopedClasses['test-result']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-affix-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-affix-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select-selector']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-affix-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-affix-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-affix-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-affix-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['model-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['model-summary-content']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-select']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-affix-wrapper']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "llm-api-config" },
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
    ...{ class: "config-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
const __VLS_4 = {}.ARadioGroup;
/** @type {[typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, typeof __VLS_components.ARadioGroup, typeof __VLS_components.aRadioGroup, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedConfig),
}));
const __VLS_6 = __VLS_5({
    ...{ 'onChange': {} },
    value: (__VLS_ctx.selectedConfig),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onChange: (__VLS_ctx.handleConfigChange)
};
__VLS_7.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "config-options" },
});
for (const [config] of __VLS_getVForSourceType((__VLS_ctx.availableConfigs))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (config.name),
        ...{ class: "config-option" },
    });
    const __VLS_12 = {}.ARadio;
    /** @type {[typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, typeof __VLS_components.ARadio, typeof __VLS_components.aRadio, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        value: (config.name),
    }));
    const __VLS_14 = __VLS_13({
        value: (config.name),
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "config-info" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "config-name" },
    });
    (config.displayName);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "config-desc" },
    });
    (config.description);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "config-features" },
    });
    for (const [feature] of __VLS_getVForSourceType((config.features))) {
        const __VLS_16 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
            key: (feature),
            size: "small",
            color: (__VLS_ctx.getFeatureColor(feature)),
        }));
        const __VLS_18 = __VLS_17({
            key: (feature),
            size: "small",
            color: (__VLS_ctx.getFeatureColor(feature)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_17));
        __VLS_19.slots.default;
        (feature);
        var __VLS_19;
    }
    var __VLS_15;
}
var __VLS_7;
if (__VLS_ctx.currentConfig && __VLS_ctx.availableModels.length > 1) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "config-section" },
    });
    const __VLS_20 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        gutter: (24),
        align: "top",
    }));
    const __VLS_22 = __VLS_21({
        gutter: (24),
        align: "top",
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    const __VLS_24 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        xs: (24),
        sm: (12),
        md: (8),
    }));
    const __VLS_26 = __VLS_25({
        xs: (24),
        sm: (12),
        md: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_27.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    const __VLS_28 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.selectedModel),
        ...{ style: {} },
        placeholder: "请选择模型",
        dropdownStyle: ({ maxHeight: '500px' }),
        optionLabelProp: ('label'),
        size: "large",
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.selectedModel),
        ...{ style: {} },
        placeholder: "请选择模型",
        dropdownStyle: ({ maxHeight: '500px' }),
        optionLabelProp: ('label'),
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_32;
    let __VLS_33;
    let __VLS_34;
    const __VLS_35 = {
        onChange: (__VLS_ctx.handleModelChange)
    };
    __VLS_31.slots.default;
    for (const [model] of __VLS_getVForSourceType((__VLS_ctx.availableModels))) {
        const __VLS_36 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
            key: (model.value),
            value: (model.value),
            label: (model.label),
        }));
        const __VLS_38 = __VLS_37({
            key: (model.value),
            value: (model.value),
            label: (model.label),
        }, ...__VLS_functionalComponentArgsRest(__VLS_37));
        __VLS_39.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "model-option" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "model-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "model-name" },
        });
        (model.label);
        if (model.value === __VLS_ctx.currentConfig.defaultModel) {
            const __VLS_40 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
                color: "blue",
                size: "small",
            }));
            const __VLS_42 = __VLS_41({
                color: "blue",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_41));
            __VLS_43.slots.default;
            var __VLS_43;
        }
        const __VLS_44 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
            color: (__VLS_ctx.getPricingColor(model.pricing)),
            size: "small",
        }));
        const __VLS_46 = __VLS_45({
            color: (__VLS_ctx.getPricingColor(model.pricing)),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_45));
        __VLS_47.slots.default;
        (model.pricing);
        var __VLS_47;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "model-desc" },
        });
        (model.description);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "model-features" },
        });
        for (const [feature] of __VLS_getVForSourceType((model.features))) {
            const __VLS_48 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
                key: (feature),
                size: "small",
                color: "default",
            }));
            const __VLS_50 = __VLS_49({
                key: (feature),
                size: "small",
                color: "default",
            }, ...__VLS_functionalComponentArgsRest(__VLS_49));
            __VLS_51.slots.default;
            (feature);
            var __VLS_51;
        }
        var __VLS_39;
    }
    var __VLS_31;
    var __VLS_27;
    const __VLS_52 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        xs: (24),
        sm: (12),
        md: (16),
    }));
    const __VLS_54 = __VLS_53({
        xs: (24),
        sm: (12),
        md: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "form-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({
        ...{ class: "form-label" },
    });
    const __VLS_56 = {}.AInputPassword;
    /** @type {[typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.apiKey),
        placeholder: "请输入API密钥",
        size: "large",
        ...{ style: {} },
        visibilityToggle: (true),
    }));
    const __VLS_58 = __VLS_57({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.apiKey),
        placeholder: "请输入API密钥",
        size: "large",
        ...{ style: {} },
        visibilityToggle: (true),
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    let __VLS_60;
    let __VLS_61;
    let __VLS_62;
    const __VLS_63 = {
        onChange: (__VLS_ctx.handleApiKeyChange)
    };
    __VLS_59.slots.default;
    {
        const { prefix: __VLS_thisSlot } = __VLS_59.slots;
        const __VLS_64 = {}.SearchOutlined;
        /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
            ...{ style: {} },
        }));
        const __VLS_66 = __VLS_65({
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    }
    var __VLS_59;
    var __VLS_55;
    var __VLS_23;
    if (__VLS_ctx.currentModelInfo) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "model-summary" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "model-summary-content" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "model-summary-name" },
        });
        (__VLS_ctx.currentModelInfo.label);
        if (__VLS_ctx.currentModelInfo.value === __VLS_ctx.currentConfig.defaultModel) {
            const __VLS_68 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
                color: "blue",
                size: "small",
            }));
            const __VLS_70 = __VLS_69({
                color: "blue",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_69));
            __VLS_71.slots.default;
            var __VLS_71;
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "model-summary-desc" },
        });
        (__VLS_ctx.currentModelInfo.description);
    }
}
if (__VLS_ctx.selectedConfig === 'local') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "config-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    const __VLS_72 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.customEndpoint),
        placeholder: "http://localhost:8001/v1/chat/completions",
    }));
    const __VLS_74 = __VLS_73({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.customEndpoint),
        placeholder: "http://localhost:8001/v1/chat/completions",
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    let __VLS_76;
    let __VLS_77;
    let __VLS_78;
    const __VLS_79 = {
        onChange: (__VLS_ctx.handleEndpointChange)
    };
    __VLS_75.slots.default;
    {
        const { prefix: __VLS_thisSlot } = __VLS_75.slots;
        const __VLS_80 = {}.LinkOutlined;
        /** @type {[typeof __VLS_components.LinkOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
        const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
    }
    var __VLS_75;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "config-status" },
});
const __VLS_84 = {}.AAlert;
/** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    type: (__VLS_ctx.configStatus.type),
    message: (__VLS_ctx.configStatus.message),
    showIcon: true,
    closable: (false),
}));
const __VLS_86 = __VLS_85({
    type: (__VLS_ctx.configStatus.type),
    message: (__VLS_ctx.configStatus.message),
    showIcon: true,
    closable: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "config-actions" },
});
const __VLS_88 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
const __VLS_92 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing),
    disabled: (!__VLS_ctx.configStatus.valid),
}));
const __VLS_94 = __VLS_93({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing),
    disabled: (!__VLS_ctx.configStatus.valid),
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
let __VLS_96;
let __VLS_97;
let __VLS_98;
const __VLS_99 = {
    onClick: (__VLS_ctx.testConnection)
};
__VLS_95.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_95.slots;
    const __VLS_100 = {}.ExperimentOutlined;
    /** @type {[typeof __VLS_components.ExperimentOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({}));
    const __VLS_102 = __VLS_101({}, ...__VLS_functionalComponentArgsRest(__VLS_101));
}
var __VLS_95;
const __VLS_104 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    ...{ 'onClick': {} },
    type: "primary",
    disabled: (!__VLS_ctx.configStatus.valid),
}));
const __VLS_106 = __VLS_105({
    ...{ 'onClick': {} },
    type: "primary",
    disabled: (!__VLS_ctx.configStatus.valid),
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
let __VLS_108;
let __VLS_109;
let __VLS_110;
const __VLS_111 = {
    onClick: (__VLS_ctx.saveConfig)
};
__VLS_107.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_107.slots;
    const __VLS_112 = {}.SaveOutlined;
    /** @type {[typeof __VLS_components.SaveOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
    const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
}
var __VLS_107;
var __VLS_91;
if (__VLS_ctx.testResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "test-result" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    const __VLS_116 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        type: (__VLS_ctx.testResult.success ? 'success' : 'error'),
        message: (__VLS_ctx.testResult.message),
        description: (__VLS_ctx.testResult.details),
        showIcon: true,
        closable: (false),
    }));
    const __VLS_118 = __VLS_117({
        type: (__VLS_ctx.testResult.success ? 'success' : 'error'),
        message: (__VLS_ctx.testResult.message),
        description: (__VLS_ctx.testResult.details),
        showIcon: true,
        closable: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
}
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['llm-api-config']} */ ;
/** @type {__VLS_StyleScopedClasses['config-content']} */ ;
/** @type {__VLS_StyleScopedClasses['config-section']} */ ;
/** @type {__VLS_StyleScopedClasses['config-options']} */ ;
/** @type {__VLS_StyleScopedClasses['config-option']} */ ;
/** @type {__VLS_StyleScopedClasses['config-info']} */ ;
/** @type {__VLS_StyleScopedClasses['config-name']} */ ;
/** @type {__VLS_StyleScopedClasses['config-desc']} */ ;
/** @type {__VLS_StyleScopedClasses['config-features']} */ ;
/** @type {__VLS_StyleScopedClasses['config-section']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['model-option']} */ ;
/** @type {__VLS_StyleScopedClasses['model-info']} */ ;
/** @type {__VLS_StyleScopedClasses['model-name']} */ ;
/** @type {__VLS_StyleScopedClasses['model-desc']} */ ;
/** @type {__VLS_StyleScopedClasses['model-features']} */ ;
/** @type {__VLS_StyleScopedClasses['form-item']} */ ;
/** @type {__VLS_StyleScopedClasses['form-label']} */ ;
/** @type {__VLS_StyleScopedClasses['model-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['model-summary-content']} */ ;
/** @type {__VLS_StyleScopedClasses['model-summary-name']} */ ;
/** @type {__VLS_StyleScopedClasses['model-summary-desc']} */ ;
/** @type {__VLS_StyleScopedClasses['config-section']} */ ;
/** @type {__VLS_StyleScopedClasses['config-status']} */ ;
/** @type {__VLS_StyleScopedClasses['config-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['test-result']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            LinkOutlined: icons_vue_1.LinkOutlined,
            ExperimentOutlined: icons_vue_1.ExperimentOutlined,
            SaveOutlined: icons_vue_1.SaveOutlined,
            SearchOutlined: icons_vue_1.SearchOutlined,
            selectedConfig: selectedConfig,
            selectedModel: selectedModel,
            apiKey: apiKey,
            customEndpoint: customEndpoint,
            testing: testing,
            testResult: testResult,
            availableConfigs: availableConfigs,
            currentConfig: currentConfig,
            availableModels: availableModels,
            currentModelInfo: currentModelInfo,
            configStatus: configStatus,
            handleConfigChange: handleConfigChange,
            handleModelChange: handleModelChange,
            handleApiKeyChange: handleApiKeyChange,
            handleEndpointChange: handleEndpointChange,
            getFeatureColor: getFeatureColor,
            getPricingColor: getPricingColor,
            testConnection: testConnection,
            saveConfig: saveConfig,
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
