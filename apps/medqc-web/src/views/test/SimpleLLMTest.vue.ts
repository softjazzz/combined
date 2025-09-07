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
import initLLMDatabase_1 from '@/utils/initLLMDatabase';
const loading = (0, vue_1.ref)(false);
const parsing = (0, vue_1.ref)(false);
const testResult = (0, vue_1.ref)('');
const parseResult = (0, vue_1.ref)('');
const showConfigModal = (0, vue_1.ref)(false);
const currentConfig = (0, vue_1.ref)(null);
const testText = (0, vue_1.ref)(`患者张三，男，65岁，因头晕、头痛3天入院。
患者3天前无明显诱因出现头晕、头痛，伴恶心，无呕吐，无发热，无胸闷气短。
既往有高血压病史10年，平时服用降压药物治疗，血压控制尚可。
入院诊断：高血压病
主要手术：无`);
const initDatabase = async () => {
    loading.value = true;
    try {
        await (0, initLLMDatabase_1.initLLMDatabase)();
        testResult.value = '✅ 数据库初始化成功！\n已创建提供商、模型和默认配置。';
        ant_design_vue_1.message.success('数据库初始化成功');
    }
    catch (error) {
        testResult.value = `❌ 数据库初始化失败: ${error}`;
        ant_design_vue_1.message.error('数据库初始化失败');
    }
    finally {
        loading.value = false;
    }
};
const cleanupDuplicates = async () => {
    loading.value = true;
    try {
        const { supabase } = await Promise.resolve().then(() => __importStar(require('@/lib/supabase')));
        // 查询所有default配置
        const { data: configs } = await supabase
            .from('user_llm_configs')
            .select('*')
            .eq('config_name', 'default')
            .is('user_id', null)
            .order('created_at', { ascending: true });
        if (configs && configs.length > 1) {
            // 保留第一个，删除其他的
            const toDelete = configs.slice(1).map(c => c.id);
            const { error } = await supabase
                .from('user_llm_configs')
                .delete()
                .in('id', toDelete);
            if (error) {
                throw error;
            }
            testResult.value = `✅ 清理完成！删除了 ${toDelete.length} 个重复配置`;
            ant_design_vue_1.message.success(`删除了 ${toDelete.length} 个重复配置`);
        }
        else {
            testResult.value = '✅ 没有发现重复配置';
            ant_design_vue_1.message.info('没有发现重复配置');
        }
    }
    catch (error) {
        testResult.value = `❌ 清理失败: ${error}`;
        ant_design_vue_1.message.error('清理失败');
    }
    finally {
        loading.value = false;
    }
};
const debugDatabase = async () => {
    loading.value = true;
    try {
        // 直接查询数据库
        const { supabase } = await Promise.resolve().then(() => __importStar(require('@/lib/supabase')));
        // 查询所有配置
        const { data: configs, error: configError } = await supabase
            .from('user_llm_configs')
            .select('*');
        // 查询所有提供商
        const { data: providers, error: providerError } = await supabase
            .from('llm_api_providers')
            .select('*');
        // 查询所有模型
        const { data: models, error: modelError } = await supabase
            .from('llm_models')
            .select('*');
        testResult.value = `🔍 数据库调试信息:

配置数量: ${configs?.length || 0}
提供商数量: ${providers?.length || 0}
模型数量: ${models?.length || 0}

配置详情:
${JSON.stringify(configs, null, 2)}

错误信息:
配置错误: ${configError?.message || '无'}
提供商错误: ${providerError?.message || '无'}
模型错误: ${modelError?.message || '无'}`;
        ant_design_vue_1.message.success('数据库调试完成');
    }
    catch (error) {
        testResult.value = `❌ 调试失败: ${error}`;
        ant_design_vue_1.message.error('调试失败');
    }
    finally {
        loading.value = false;
    }
};
const loadDefaultConfig = async () => {
    loading.value = true;
    try {
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        const success = await llmService.loadConfigFromDatabase('default');
        if (success) {
            currentConfig.value = llmService.getCurrentConfig();
            testResult.value = '✅ 默认配置加载成功！';
            ant_design_vue_1.message.success('默认配置加载成功');
        }
        else {
            testResult.value = '⚠️ 未找到默认配置，请先初始化数据库';
            ant_design_vue_1.message.warning('未找到默认配置');
        }
    }
    catch (error) {
        testResult.value = `❌ 加载配置失败: ${error}`;
        ant_design_vue_1.message.error('加载配置失败');
    }
    finally {
        loading.value = false;
    }
};
const testLLMService = async () => {
    loading.value = true;
    try {
        // 动态导入llmService
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        const config = llmService.getCurrentConfig();
        if (!config) {
            testResult.value = '⚠️ 请先加载配置';
            ant_design_vue_1.message.warning('请先加载配置');
            return;
        }
        testResult.value = `✅ LLM服务配置信息:
配置名称: ${config.config_name}
提供商: ${config.provider?.provider_name}
模型: ${config.model?.model_name}
端点: ${config.provider?.base_endpoint}
是否有API密钥: ${config.api_key_encrypted ? '是' : '否'}`;
        ant_design_vue_1.message.success('LLM服务测试成功');
    }
    catch (error) {
        testResult.value = `❌ LLM服务测试失败: ${error}`;
        ant_design_vue_1.message.error('LLM服务测试失败');
    }
    finally {
        loading.value = false;
    }
};
const parseText = async () => {
    if (!testText.value.trim()) {
        ant_design_vue_1.message.warning('请输入测试文本');
        return;
    }
    parsing.value = true;
    try {
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        const result = await llmService.extractMedicalData(testText.value);
        parseResult.value = JSON.stringify(result, null, 2);
        if (result.success) {
            ant_design_vue_1.message.success('文本解析成功');
        }
        else {
            ant_design_vue_1.message.error(`文本解析失败: ${result.error}`);
        }
    }
    catch (error) {
        parseResult.value = `解析失败: ${error}`;
        ant_design_vue_1.message.error('文本解析失败');
    }
    finally {
        parsing.value = false;
    }
};
const handleConfigUpdated = async (config) => {
    try {
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        const success = await llmService.loadConfigFromDatabase(config.config_name);
        if (success) {
            currentConfig.value = llmService.getCurrentConfig();
            testResult.value = `✅ 配置已更新: ${config.config_name}`;
            ant_design_vue_1.message.success(`配置已更新: ${config.config_name}`);
            showConfigModal.value = false;
        }
    }
    catch (error) {
        testResult.value = `❌ 应用配置失败: ${error}`;
        ant_design_vue_1.message.error('应用配置失败');
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "simple-llm-test" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "简化版LLM配置测试",
}));
const __VLS_2 = __VLS_1({
    title: "简化版LLM配置测试",
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
if (__VLS_ctx.currentConfig) {
    const __VLS_8 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
        message: (`当前配置: ${__VLS_ctx.currentConfig.config_name}`),
        description: (`${__VLS_ctx.currentConfig.provider?.provider_name} - ${__VLS_ctx.currentConfig.model?.model_name}`),
        type: "info",
        showIcon: true,
    }));
    const __VLS_10 = __VLS_9({
        message: (`当前配置: ${__VLS_ctx.currentConfig.config_name}`),
        description: (`${__VLS_ctx.currentConfig.provider?.provider_name} - ${__VLS_ctx.currentConfig.model?.model_name}`),
        type: "info",
        showIcon: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
const __VLS_12 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    type: "primary",
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.initDatabase)
};
__VLS_19.slots.default;
var __VLS_19;
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.loadDefaultConfig)
};
__VLS_27.slots.default;
var __VLS_27;
const __VLS_32 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_34 = __VLS_33({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showConfigModal = true;
    }
};
__VLS_35.slots.default;
var __VLS_35;
const __VLS_40 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    type: "dashed",
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    type: "dashed",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (__VLS_ctx.testLLMService)
};
__VLS_43.slots.default;
var __VLS_43;
const __VLS_48 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_50 = __VLS_49({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onClick: (__VLS_ctx.debugDatabase)
};
__VLS_51.slots.default;
var __VLS_51;
const __VLS_56 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    type: "default",
}));
const __VLS_58 = __VLS_57({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
    type: "default",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onClick: (__VLS_ctx.cleanupDuplicates)
};
__VLS_59.slots.default;
var __VLS_59;
var __VLS_15;
const __VLS_64 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    size: "small",
    title: "操作结果",
}));
const __VLS_66 = __VLS_65({
    size: "small",
    title: "操作结果",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
(__VLS_ctx.testResult);
var __VLS_67;
const __VLS_68 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    size: "small",
    title: "文本解析测试",
}));
const __VLS_70 = __VLS_69({
    size: "small",
    title: "文本解析测试",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
const __VLS_72 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    value: (__VLS_ctx.testText),
    rows: (4),
    placeholder: "输入医疗文本进行测试解析...",
}));
const __VLS_74 = __VLS_73({
    value: (__VLS_ctx.testText),
    rows: (4),
    placeholder: "输入医疗文本进行测试解析...",
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mt-2" },
});
const __VLS_76 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.parsing),
    type: "primary",
}));
const __VLS_78 = __VLS_77({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.parsing),
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
let __VLS_80;
let __VLS_81;
let __VLS_82;
const __VLS_83 = {
    onClick: (__VLS_ctx.parseText)
};
__VLS_79.slots.default;
var __VLS_79;
var __VLS_71;
if (__VLS_ctx.parseResult) {
    const __VLS_84 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
        size: "small",
        title: "解析结果",
    }));
    const __VLS_86 = __VLS_85({
        size: "small",
        title: "解析结果",
    }, ...__VLS_functionalComponentArgsRest(__VLS_85));
    __VLS_87.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({});
    (__VLS_ctx.parseResult);
    var __VLS_87;
}
var __VLS_7;
var __VLS_3;
const __VLS_88 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showConfigModal),
    title: "LLM配置管理",
    width: "600px",
}));
const __VLS_90 = __VLS_89({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showConfigModal),
    title: "LLM配置管理",
    width: "600px",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
let __VLS_92;
let __VLS_93;
let __VLS_94;
const __VLS_95 = {
    onOk: (...[$event]) => {
        __VLS_ctx.showConfigModal = false;
    }
};
__VLS_91.slots.default;
const __VLS_96 = {}.AAlert;
/** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    message: "配置管理功能暂时禁用，请使用其他测试功能",
    type: "info",
}));
const __VLS_98 = __VLS_97({
    message: "配置管理功能暂时禁用，请使用其他测试功能",
    type: "info",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
var __VLS_91;
/** @type {__VLS_StyleScopedClasses['simple-llm-test']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            loading: loading,
            parsing: parsing,
            testResult: testResult,
            parseResult: parseResult,
            showConfigModal: showConfigModal,
            currentConfig: currentConfig,
            testText: testText,
            initDatabase: initDatabase,
            cleanupDuplicates: cleanupDuplicates,
            debugDatabase: debugDatabase,
            loadDefaultConfig: loadDefaultConfig,
            testLLMService: testLLMService,
            parseText: parseText,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
