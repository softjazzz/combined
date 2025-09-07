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
import ant_design_vue_1 from 'ant-design-vue';
import llmConfigService_1 from '@/services/llmConfigService';
import initLLMDatabase_1 from '@/utils/initLLMDatabase';
const LLMApiConfigDatabase_vue_1 = __importDefault(require("@/components/LLMApiConfigDatabase.vue"));
const loading = (0, vue_1.ref)(false);
const testResult = (0, vue_1.ref)('');
const initDatabase = async () => {
    loading.value = true;
    try {
        await (0, initLLMDatabase_1.initLLMDatabase)();
        testResult.value = '数据库初始化成功！\n已创建提供商、模型和默认配置。';
        ant_design_vue_1.message.success('数据库初始化成功');
    }
    catch (error) {
        testResult.value = `数据库初始化失败: ${error}`;
        ant_design_vue_1.message.error('数据库初始化失败');
    }
    finally {
        loading.value = false;
    }
};
const testLoadProviders = async () => {
    loading.value = true;
    try {
        const providers = await llmConfigService_1.llmConfigService.getProviders();
        testResult.value = JSON.stringify(providers, null, 2);
        ant_design_vue_1.message.success(`成功加载 ${providers.length} 个提供商`);
    }
    catch (error) {
        testResult.value = `错误: ${error}`;
        ant_design_vue_1.message.error('加载提供商失败');
    }
    finally {
        loading.value = false;
    }
};
const testLoadConfigs = async () => {
    loading.value = true;
    try {
        const configs = await llmConfigService_1.llmConfigService.getUserConfigs();
        testResult.value = JSON.stringify(configs, null, 2);
        ant_design_vue_1.message.success(`成功加载 ${configs.length} 个配置`);
    }
    catch (error) {
        testResult.value = `错误: ${error}`;
        ant_design_vue_1.message.error('加载配置失败');
    }
    finally {
        loading.value = false;
    }
};
const testCreateConfig = async () => {
    loading.value = true;
    try {
        // 首先获取提供商和模型
        const providers = await llmConfigService_1.llmConfigService.getProviders();
        if (providers.length === 0) {
            throw new Error('没有可用的提供商');
        }
        const models = await llmConfigService_1.llmConfigService.getModelsByProvider(providers[0].id);
        if (models.length === 0) {
            throw new Error('没有可用的模型');
        }
        // 创建测试配置
        const config = await llmConfigService_1.llmConfigService.saveConfig({
            config_name: 'test_config',
            provider_id: providers[0].id,
            model_id: models[0].id,
            api_key: 'test-api-key',
            custom_parameters: { temperature: 0.7 }
        });
        testResult.value = JSON.stringify(config, null, 2);
        ant_design_vue_1.message.success('成功创建测试配置');
    }
    catch (error) {
        testResult.value = `错误: ${error}`;
        ant_design_vue_1.message.error('创建配置失败');
    }
    finally {
        loading.value = false;
    }
};
const handleConfigUpdated = (config) => {
    testResult.value = `配置已更新: ${JSON.stringify(config, null, 2)}`;
    ant_design_vue_1.message.success(`配置已更新: ${config.config_name}`);
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "llm-config-test" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "LLM配置系统测试",
}));
const __VLS_2 = __VLS_1({
    title: "LLM配置系统测试",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    direction: "vertical",
    ...{ style: {} },
}));
const __VLS_6 = __VLS_5({
    direction: "vertical",
    ...{ style: {} },
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
    loading: (__VLS_ctx.loading),
    type: "primary",
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (__VLS_ctx.initDatabase)
};
__VLS_15.slots.default;
var __VLS_15;
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
    onClick: (__VLS_ctx.testLoadProviders)
};
__VLS_23.slots.default;
var __VLS_23;
const __VLS_28 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_30 = __VLS_29({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
let __VLS_32;
let __VLS_33;
let __VLS_34;
const __VLS_35 = {
    onClick: (__VLS_ctx.testLoadConfigs)
};
__VLS_31.slots.default;
var __VLS_31;
const __VLS_36 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_38 = __VLS_37({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onClick: (__VLS_ctx.testCreateConfig)
};
__VLS_39.slots.default;
var __VLS_39;
var __VLS_11;
const __VLS_44 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    size: "small",
    title: "测试结果",
}));
const __VLS_46 = __VLS_45({
    size: "small",
    title: "测试结果",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
(__VLS_ctx.testResult);
var __VLS_47;
const __VLS_48 = {}.ADivider;
/** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({}));
const __VLS_50 = __VLS_49({}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
var __VLS_51;
/** @type {[typeof LLMApiConfigDatabase, ]} */ ;
// @ts-ignore
const __VLS_52 = __VLS_asFunctionalComponent(LLMApiConfigDatabase_vue_1.default, new LLMApiConfigDatabase_vue_1.default({
    ...{ 'onConfigUpdated': {} },
}));
const __VLS_53 = __VLS_52({
    ...{ 'onConfigUpdated': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_52));
let __VLS_55;
let __VLS_56;
let __VLS_57;
const __VLS_58 = {
    onConfigUpdated: (__VLS_ctx.handleConfigUpdated)
};
var __VLS_54;
var __VLS_7;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['llm-config-test']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            LLMApiConfigDatabase: LLMApiConfigDatabase_vue_1.default,
            loading: loading,
            testResult: testResult,
            initDatabase: initDatabase,
            testLoadProviders: testLoadProviders,
            testLoadConfigs: testLoadConfigs,
            testCreateConfig: testCreateConfig,
            handleConfigUpdated: handleConfigUpdated,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
