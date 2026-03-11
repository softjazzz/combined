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
import apiService_1 from '@/services/apiService';
import auth_1 from '@/stores/auth';
// 状态
const connectionStatus = (0, vue_1.ref)('disconnected');
const apiBaseUrl = (0, vue_1.ref)(apiService_1.ApiService.getBaseURL());
const authStore = (0, auth_1.useAuthStore)();
// 测试状态
const testing = (0, vue_1.ref)({
    connection: false,
    auth: false,
    all: false
});
const testResults = (0, vue_1.ref)(: any[]);
// 计算属性
const isAuthenticated = computed(() => apiService_1.ApiService.isAuthenticated());
// 方法
const getStatusText = (status) => {
    const texts = {
        connected: '已连接',
        connecting: '连接中',
        disconnected: '未连接'
    };
    return texts[status] || '未知';
};
const addTestResult = (result) => {
    testResults.value.unshift({
        ...result,
        id: Date.now().toString()
    });
    // 限制结果数量
    if (testResults.value.length > 10) {
        testResults.value = testResults.value.slice(0, 10);
    }
};
const testConnection = async () => {
    testing.value.connection = true;
    connectionStatus.value = 'connecting';
    const startTime = Date.now();
    try {
        const isConnected = await apiService_1.ApiService.checkConnection();
        const duration = Date.now() - startTime;
        if (isConnected) {
            connectionStatus.value = 'connected';
            addTestResult({
                name: 'API连接测试',
                description: '成功连接到后端API服务',
                status: 'success',
                duration,
                details: `GET ${apiBaseUrl.value}/api/v1/health`
            });
            ant_design_vue_1.message.success('API连接正常');
        }
        else {
            connectionStatus.value = 'disconnected';
            addTestResult({
                name: 'API连接测试',
                description: '无法连接到后端API服务',
                status: 'error',
                duration,
                error: '连接失败，请检查后端服务是否启动'
            });
            ant_design_vue_1.message.error('API连接失败');
        }
    }
    catch (error) {
        connectionStatus.value = 'disconnected';
        const duration = Date.now() - startTime;
        addTestResult({
            name: 'API连接测试',
            description: '连接测试过程中发生错误',
            status: 'error',
            duration,
            error: error.message || '未知错误'
        });
        ant_design_vue_1.message.error('连接测试失败');
    }
    finally {
        testing.value.connection = false;
    }
};
const testAuth = async () => {
    testing.value.auth = true;
    const startTime = Date.now();
    try {
        if (!isAuthenticated.value) {
            // 尝试使用演示账户登录
            const response = await apiService_1.ApiService.login({
                email: 'admin@medqc.com',
                password: 'admin123'
            });
            const duration = Date.now() - startTime;
            if (response.success) {
                addTestResult({
                    name: '认证测试',
                    description: '使用演示账户登录成功',
                    status: 'success',
                    duration,
                    details: 'POST /api/auth/login'
                });
                ant_design_vue_1.message.success('认证测试成功');
            }
            else {
                addTestResult({
                    name: '认证测试',
                    description: '登录失败',
                    status: 'error',
                    duration,
                    error: response.error || '登录失败'
                });
                ant_design_vue_1.message.error('认证测试失败');
            }
        }
        else {
            // 测试获取用户信息
            const response = await apiService_1.ApiService.getCurrentUser();
            const duration = Date.now() - startTime;
            if (response.success) {
                addTestResult({
                    name: '认证测试',
                    description: '成功获取当前用户信息',
                    status: 'success',
                    duration,
                    details: `GET /api/auth/me - 用户: ${response.data?.display_name}`
                });
                ant_design_vue_1.message.success('认证测试成功');
            }
            else {
                addTestResult({
                    name: '认证测试',
                    description: '获取用户信息失败',
                    status: 'error',
                    duration,
                    error: response.error || '获取用户信息失败'
                });
                ant_design_vue_1.message.error('认证测试失败');
            }
        }
    }
    catch (error) {
        const duration = Date.now() - startTime;
        addTestResult({
            name: '认证测试',
            description: '认证测试过程中发生错误',
            status: 'error',
            duration,
            error: error.message || '未知错误'
        });
        ant_design_vue_1.message.error('认证测试失败');
    }
    finally {
        testing.value.auth = false;
    }
};
const testAllApis = async () => {
    testing.value.all = true;
    testResults.value = [];
    // 依次测试各个API模块
    await testConnection();
    await new Promise(resolve => setTimeout(resolve, 500));
    await testAuth();
    await new Promise(resolve => setTimeout(resolve, 500));
    // 测试其他API接口
    await testMedicalRecordsApi();
    await new Promise(resolve => setTimeout(resolve, 500));
    await testQCApi();
    testing.value.all = false;
    ant_design_vue_1.message.info('全面API测试完成');
};
const testMedicalRecordsApi = async () => {
    const startTime = Date.now();
    try {
        const response = await apiService_1.ApiService.getMedicalRecords({ pagination: { page: 1, pageSize: 5 } });
        const duration = Date.now() - startTime;
        if (response.success) {
            addTestResult({
                name: '医疗记录API测试',
                description: '成功获取医疗记录列表',
                status: 'success',
                duration,
                details: `GET /api/records - 返回 ${response.data?.data?.length || 0} 条记录`
            });
        }
        else {
            addTestResult({
                name: '医疗记录API测试',
                description: '获取医疗记录失败',
                status: 'error',
                duration,
                error: response.error || '获取记录失败'
            });
        }
    }
    catch (error) {
        const duration = Date.now() - startTime;
        addTestResult({
            name: '医疗记录API测试',
            description: '医疗记录API测试失败',
            status: 'error',
            duration,
            error: error.message || '未知错误'
        });
    }
};
const testQCApi = async () => {
    const startTime = Date.now();
    try {
        const response = await apiService_1.ApiService.getQCRules();
        const duration = Date.now() - startTime;
        if (response.success) {
            addTestResult({
                name: '质控API测试',
                description: '成功获取质控规则列表',
                status: 'success',
                duration,
                details: `GET /api/qc/rules - 返回 ${response.data?.length || 0} 条规则`
            });
        }
        else {
            addTestResult({
                name: '质控API测试',
                description: '获取质控规则失败',
                status: 'error',
                duration,
                error: response.error || '获取规则失败'
            });
        }
    }
    catch (error) {
        const duration = Date.now() - startTime;
        addTestResult({
            name: '质控API测试',
            description: '质控API测试失败',
            status: 'error',
            duration,
            error: error.message || '未知错误'
        });
    }
};
// 样式相关方法
const getResultCardClass = (status) => {
    const classes = {
        success: 'border-emerald-500/30 bg-emerald-500/5',
        error: 'border-red-500/30 bg-red-500/5',
        warning: 'border-amber-500/30 bg-amber-500/5',
        loading: 'border-blue-500/30 bg-blue-500/5'
    };
    return classes[status] || 'border-slate-600/30 bg-slate-700/5';
};
const getResultIcon = (status) => {
    const icons = {
        success: icons_vue_1.CheckCircleOutlined,
        error: icons_vue_1.CloseCircleOutlined,
        warning: icons_vue_1.ExclamationCircleOutlined,
        loading: icons_vue_1.LoadingOutlined
    };
    return icons[status] || icons_vue_1.ExclamationCircleOutlined;
};
const getResultIconClass = (status) => {
    const classes = {
        success: 'text-emerald-400',
        error: 'text-red-400',
        warning: 'text-amber-400',
        loading: 'text-blue-400'
    };
    return classes[status] || 'text-slate-400';
};
const getResultTagColor = (status) => {
    const colors = {
        success: 'green',
        error: 'red',
        warning: 'orange',
        loading: 'blue'
    };
    return colors[status] || 'default';
};
const getResultStatusText = (status) => {
    const texts = {
        success: '成功',
        error: '失败',
        warning: '警告',
        loading: '进行中'
    };
    return texts[status] || '未知';
};
// 生命周期
(0, vue_1.onMounted)(() => {
    // 初始连接测试
    testConnection();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "api-connection-test" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "p-6 rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2" },
});
const __VLS_0 = {}.ApiOutlined;
/** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-cyan-400" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-cyan-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-3 h-3 rounded-full" },
    ...{ class: (__VLS_ctx.connectionStatus === 'connected' ? 'bg-emerald-400' : __VLS_ctx.connectionStatus === 'connecting' ? 'bg-amber-400' : 'bg-red-400') },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-sm font-medium" },
    ...{ class: (__VLS_ctx.connectionStatus === 'connected' ? 'text-emerald-400' : __VLS_ctx.connectionStatus === 'connecting' ? 'text-amber-400' : 'text-red-400') },
});
(__VLS_ctx.getStatusText(__VLS_ctx.connectionStatus));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6 p-4 rounded-lg bg-slate-700/30 border border-slate-600/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-sm font-medium text-slate-200 mb-3" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-2 text-sm" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-200 font-mono" },
});
(__VLS_ctx.apiBaseUrl);
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-200" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: (__VLS_ctx.isAuthenticated ? 'text-emerald-400' : 'text-red-400') },
});
(__VLS_ctx.isAuthenticated ? '已认证' : '未认证');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-3 gap-4 mb-6" },
});
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing.connection),
    ...{ class: "h-12 bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30" },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing.connection),
    ...{ class: "h-12 bg-blue-500/20 border-blue-400/30 text-blue-300 hover:bg-blue-500/30" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (__VLS_ctx.testConnection)
};
__VLS_7.slots.default;
const __VLS_12 = {}.ApiOutlined;
/** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
var __VLS_7;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing.auth),
    ...{ class: "h-12 bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30" },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing.auth),
    ...{ class: "h-12 bg-emerald-500/20 border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.testAuth)
};
__VLS_19.slots.default;
const __VLS_24 = {}.UserOutlined;
/** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
var __VLS_19;
const __VLS_28 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing.all),
    ...{ class: "h-12 bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30" },
}));
const __VLS_30 = __VLS_29({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.testing.all),
    ...{ class: "h-12 bg-purple-500/20 border-purple-400/30 text-purple-300 hover:bg-purple-500/30" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
let __VLS_32;
let __VLS_33;
let __VLS_34;
const __VLS_35 = {
    onClick: (__VLS_ctx.testAllApis)
};
__VLS_31.slots.default;
const __VLS_36 = {}.ThunderboltOutlined;
/** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({}));
const __VLS_38 = __VLS_37({}, ...__VLS_functionalComponentArgsRest(__VLS_37));
var __VLS_31;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
for (const [result] of __VLS_getVForSourceType((__VLS_ctx.testResults))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (result.id),
        ...{ class: "p-4 rounded-lg border transition-all duration-200" },
        ...{ class: (__VLS_ctx.getResultCardClass(result.status)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-2" },
    });
    const __VLS_40 = ((__VLS_ctx.getResultIcon(result.status)));
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        ...{ class: (__VLS_ctx.getResultIconClass(result.status)) },
    }));
    const __VLS_42 = __VLS_41({
        ...{ class: (__VLS_ctx.getResultIconClass(result.status)) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "font-medium text-slate-100" },
    });
    (result.name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-xs text-slate-400" },
    });
    (result.duration);
    const __VLS_44 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        color: (__VLS_ctx.getResultTagColor(result.status)),
        size: "small",
    }));
    const __VLS_46 = __VLS_45({
        color: (__VLS_ctx.getResultTagColor(result.status)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    (__VLS_ctx.getResultStatusText(result.status));
    var __VLS_47;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-sm text-slate-300 mb-2" },
    });
    (result.description);
    if (result.details) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-slate-400 font-mono bg-slate-900/50 p-2 rounded border border-slate-600/20" },
        });
        (result.details);
    }
    if (result.error) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-red-300 bg-red-500/10 p-2 rounded border border-red-500/20 mt-2" },
        });
        (result.error);
    }
}
if (__VLS_ctx.testResults.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-8" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-16 h-16 rounded-full bg-slate-700/50 flex items-center justify-center mx-auto mb-3" },
    });
    const __VLS_48 = {}.ApiOutlined;
    /** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ class: "text-slate-400 text-2xl" },
    }));
    const __VLS_50 = __VLS_49({
        ...{ class: "text-slate-400 text-2xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-slate-400" },
    });
}
/** @type {__VLS_StyleScopedClasses['api-connection-test']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-3']} */ ;
/** @type {__VLS_StyleScopedClasses['h-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-blue-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-emerald-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-purple-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-purple-500/30']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-200']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-900/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/20']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-500/10']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-red-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['w-16']} */ ;
/** @type {__VLS_StyleScopedClasses['h-16']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-full']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ApiOutlined: icons_vue_1.ApiOutlined,
            UserOutlined: icons_vue_1.UserOutlined,
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            connectionStatus: connectionStatus,
            apiBaseUrl: apiBaseUrl,
            testing: testing,
            testResults: testResults,
            isAuthenticated: isAuthenticated,
            getStatusText: getStatusText,
            testConnection: testConnection,
            testAuth: testAuth,
            testAllApis: testAllApis,
            getResultCardClass: getResultCardClass,
            getResultIcon: getResultIcon,
            getResultIconClass: getResultIconClass,
            getResultTagColor: getResultTagColor,
            getResultStatusText: getResultStatusText,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
