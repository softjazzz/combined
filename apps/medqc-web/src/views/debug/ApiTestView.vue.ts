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
import icons_vue_1 from '@ant-design/icons-vue';
const ApiConnectionTest_vue_1 = __importDefault(require("@/components/debug/ApiConnectionTest.vue"));
import apiService_1 from '@/services/apiService';
// 测试状态
const authTesting = (0, vue_1.reactive)({
    login: false,
    getUser: false,
    updateProfile: false,
    logout: false
});
const recordTesting = (0, vue_1.reactive)({
    getRecords: false,
    createRecord: false,
    uploadFile: false,
    getStatistics: false
});
const qcTesting = (0, vue_1.reactive)({
    getRules: false,
    startAnalysis: false,
    getResult: false,
    getHistory: false
});
const testLogs = (0, vue_1.ref)(: any[]);
// 添加日志
const addLog = (log) => {
    testLogs.value.unshift({
        ...log,
        id: Date.now().toString(),
        timestamp: new Date()
    });
    // 限制日志数量
    if (testLogs.value.length > 50) {
        testLogs.value = testLogs.value.slice(0, 50);
    }
};
// 认证API测试
const testLogin = async () => {
    authTesting.login = true;
    try {
        const response = await apiService_1.ApiService.login({
            email: 'admin@medqc.com',
            password: 'admin123'
        });
        if (response.success) {
            addLog({
                title: '登录测试',
                message: '登录成功',
                details: `POST /api/auth/login - Token已获取`,
                type: 'success'
            });
            ant_design_vue_1.message.success('登录测试成功');
        }
        else {
            addLog({
                title: '登录测试',
                message: '登录失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('登录测试失败');
        }
    }
    catch (error) {
        addLog({
            title: '登录测试',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
        ant_design_vue_1.message.error('登录测试异常');
    }
    finally {
        authTesting.login = false;
    }
};
const testGetUser = async () => {
    authTesting.getUser = true;
    try {
        const response = await apiService_1.ApiService.getCurrentUser();
        if (response.success) {
            addLog({
                title: '获取用户信息',
                message: '获取成功',
                details: `GET /api/auth/me - 用户: ${response.data?.display_name}`,
                type: 'success'
            });
            ant_design_vue_1.message.success('获取用户信息成功');
        }
        else {
            addLog({
                title: '获取用户信息',
                message: '获取失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('获取用户信息失败');
        }
    }
    catch (error) {
        addLog({
            title: '获取用户信息',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        authTesting.getUser = false;
    }
};
const testUpdateProfile = async () => {
    authTesting.updateProfile = true;
    try {
        const response = await apiService_1.ApiService.updateProfile({
            bio: '测试更新资料 - ' + new Date().toLocaleString()
        });
        if (response.success) {
            addLog({
                title: '更新用户资料',
                message: '更新成功',
                details: 'PUT /api/auth/profile',
                type: 'success'
            });
            ant_design_vue_1.message.success('更新资料成功');
        }
        else {
            addLog({
                title: '更新用户资料',
                message: '更新失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('更新资料失败');
        }
    }
    catch (error) {
        addLog({
            title: '更新用户资料',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        authTesting.updateProfile = false;
    }
};
const testLogout = async () => {
    authTesting.logout = true;
    try {
        const response = await apiService_1.ApiService.logout();
        if (response.success) {
            addLog({
                title: '用户登出',
                message: '登出成功',
                details: 'POST /api/auth/logout',
                type: 'success'
            });
            ant_design_vue_1.message.success('登出成功');
        }
        else {
            addLog({
                title: '用户登出',
                message: '登出失败',
                details: response.error,
                type: 'error'
            });
        }
    }
    catch (error) {
        addLog({
            title: '用户登出',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        authTesting.logout = false;
    }
};
// 医疗记录API测试
const testGetRecords = async () => {
    recordTesting.getRecords = true;
    try {
        const response = await apiService_1.ApiService.getMedicalRecords({
            pagination: { page: 1, pageSize: 10 }
        });
        if (response.success) {
            addLog({
                title: '获取医疗记录',
                message: '获取成功',
                details: `GET /api/records - 返回 ${response.data?.data?.length || 0} 条记录`,
                type: 'success'
            });
            ant_design_vue_1.message.success('获取记录成功');
        }
        else {
            addLog({
                title: '获取医疗记录',
                message: '获取失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('获取记录失败');
        }
    }
    catch (error) {
        addLog({
            title: '获取医疗记录',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        recordTesting.getRecords = false;
    }
};
const testCreateRecord = async () => {
    recordTesting.createRecord = true;
    try {
        const response = await apiService_1.ApiService.createMedicalRecord({
            patient_name: '测试患者',
            patient_age: 30,
            patient_gender: 'male',
            department: '内科',
            admission_date: new Date().toISOString().split('T')[0],
            record_type: 'inpatient',
            content: '这是一个测试病案记录，用于API测试。'
        });
        if (response.success) {
            addLog({
                title: '创建医疗记录',
                message: '创建成功',
                details: `POST /api/records - 记录ID: ${response.data?.id}`,
                type: 'success'
            });
            ant_design_vue_1.message.success('创建记录成功');
        }
        else {
            addLog({
                title: '创建医疗记录',
                message: '创建失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('创建记录失败');
        }
    }
    catch (error) {
        addLog({
            title: '创建医疗记录',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        recordTesting.createRecord = false;
    }
};
const testUploadFile = async () => {
    recordTesting.uploadFile = true;
    try {
        // 创建一个测试文件
        const testContent = '这是一个测试文件内容，用于API测试。';
        const blob = new Blob([testContent], { type: 'text/plain' });
        const file = new File([blob], 'test.txt', { type: 'text/plain' });
        const response = await apiService_1.ApiService.uploadRecordFile(file);
        if (response.success) {
            addLog({
                title: '文件上传',
                message: '上传成功',
                details: `POST /api/records/upload - 文件: ${response.data?.file_name}`,
                type: 'success'
            });
            ant_design_vue_1.message.success('文件上传成功');
        }
        else {
            addLog({
                title: '文件上传',
                message: '上传失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('文件上传失败');
        }
    }
    catch (error) {
        addLog({
            title: '文件上传',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        recordTesting.uploadFile = false;
    }
};
const testGetStatistics = async () => {
    recordTesting.getStatistics = true;
    try {
        const response = await apiService_1.ApiService.getMedicalRecordsStatistics();
        if (response.success) {
            addLog({
                title: '获取统计信息',
                message: '获取成功',
                details: 'GET /api/records/statistics',
                type: 'success'
            });
            ant_design_vue_1.message.success('获取统计成功');
        }
        else {
            addLog({
                title: '获取统计信息',
                message: '获取失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('获取统计失败');
        }
    }
    catch (error) {
        addLog({
            title: '获取统计信息',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        recordTesting.getStatistics = false;
    }
};
// 质控API测试
const testGetQCRules = async () => {
    qcTesting.getRules = true;
    try {
        const response = await apiService_1.ApiService.getQCRules();
        if (response.success) {
            addLog({
                title: '获取质控规则',
                message: '获取成功',
                details: `GET /api/qc/rules - 返回 ${response.data?.length || 0} 条规则`,
                type: 'success'
            });
            ant_design_vue_1.message.success('获取规则成功');
        }
        else {
            addLog({
                title: '获取质控规则',
                message: '获取失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('获取规则失败');
        }
    }
    catch (error) {
        addLog({
            title: '获取质控规则',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        qcTesting.getRules = false;
    }
};
const testStartAnalysis = async () => {
    qcTesting.startAnalysis = true;
    try {
        const response = await apiService_1.ApiService.analyzeRecord('test-record-id');
        if (response.success) {
            addLog({
                title: '开始质控分析',
                message: '分析已开始',
                details: `POST /api/qc/analyze - 分析ID: ${response.data?.analysis_id}`,
                type: 'success'
            });
            ant_design_vue_1.message.success('开始分析成功');
        }
        else {
            addLog({
                title: '开始质控分析',
                message: '开始失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('开始分析失败');
        }
    }
    catch (error) {
        addLog({
            title: '开始质控分析',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        qcTesting.startAnalysis = false;
    }
};
const testGetQCResult = async () => {
    qcTesting.getResult = true;
    try {
        const response = await apiService_1.ApiService.getQCResult('test-record-id');
        if (response.success) {
            addLog({
                title: '获取质控结果',
                message: '获取成功',
                details: `GET /api/qc/result - 评分: ${response.data?.overall_score}`,
                type: 'success'
            });
            ant_design_vue_1.message.success('获取结果成功');
        }
        else {
            addLog({
                title: '获取质控结果',
                message: '获取失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('获取结果失败');
        }
    }
    catch (error) {
        addLog({
            title: '获取质控结果',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        qcTesting.getResult = false;
    }
};
const testGetQCHistory = async () => {
    qcTesting.getHistory = true;
    try {
        const response = await apiService_1.ApiService.getQCHistory({ page: 1, pageSize: 10 });
        if (response.success) {
            addLog({
                title: '获取质控历史',
                message: '获取成功',
                details: `GET /api/qc/history - 返回 ${response.data?.length || 0} 条记录`,
                type: 'success'
            });
            ant_design_vue_1.message.success('获取历史成功');
        }
        else {
            addLog({
                title: '获取质控历史',
                message: '获取失败',
                details: response.error,
                type: 'error'
            });
            ant_design_vue_1.message.error('获取历史失败');
        }
    }
    catch (error) {
        addLog({
            title: '获取质控历史',
            message: '测试异常',
            details: error.message,
            type: 'error'
        });
    }
    finally {
        qcTesting.getHistory = false;
    }
};
// 工具方法
const clearLogs = () => {
    testLogs.value = [];
    ant_design_vue_1.message.info('日志已清空');
};
const getLogClass = (type) => {
    const classes = {
        success: 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300',
        error: 'bg-red-500/10 border border-red-500/20 text-red-300',
        warning: 'bg-amber-500/10 border border-amber-500/20 text-amber-300',
        info: 'bg-blue-500/10 border border-blue-500/20 text-blue-300'
    };
    return classes[type] || classes.info;
};
const formatTime = (date) => {
    return date.toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "api-test-view min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-6xl mx-auto" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center gap-3 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-8 h-8 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center" },
});
const __VLS_0 = {}.ApiOutlined;
/** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-white text-sm" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-white text-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-2xl font-bold text-slate-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-slate-400 text-sm" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-8" },
});
/** @type {[typeof ApiConnectionTest, ]} */ ;
// @ts-ignore
const __VLS_4 = __VLS_asFunctionalComponent(ApiConnectionTest_vue_1.default, new ApiConnectionTest_vue_1.default({}));
const __VLS_5 = __VLS_4({}, ...__VLS_functionalComponentArgsRest(__VLS_4));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 lg:grid-cols-2 gap-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4" },
});
const __VLS_7 = {}.UserOutlined;
/** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
// @ts-ignore
const __VLS_8 = __VLS_asFunctionalComponent(__VLS_7, new __VLS_7({
    ...{ class: "text-emerald-400" },
}));
const __VLS_9 = __VLS_8({
    ...{ class: "text-emerald-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_8));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "p-4 rounded-lg bg-slate-700/30 border border-slate-600/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-sm font-medium text-slate-200 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-2 text-xs" },
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
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-slate-200 font-mono" },
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
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 gap-3" },
});
const __VLS_11 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_12 = __VLS_asFunctionalComponent(__VLS_11, new __VLS_11({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.login),
    size: "small",
    ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" },
}));
const __VLS_13 = __VLS_12({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.login),
    size: "small",
    ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_12));
let __VLS_15;
let __VLS_16;
let __VLS_17;
const __VLS_18 = {
    onClick: (__VLS_ctx.testLogin)
};
__VLS_14.slots.default;
var __VLS_14;
const __VLS_19 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_20 = __VLS_asFunctionalComponent(__VLS_19, new __VLS_19({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.getUser),
    size: "small",
    ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
}));
const __VLS_21 = __VLS_20({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.getUser),
    size: "small",
    ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_20));
let __VLS_23;
let __VLS_24;
let __VLS_25;
const __VLS_26 = {
    onClick: (__VLS_ctx.testGetUser)
};
__VLS_22.slots.default;
var __VLS_22;
const __VLS_27 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_28 = __VLS_asFunctionalComponent(__VLS_27, new __VLS_27({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.updateProfile),
    size: "small",
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300" },
}));
const __VLS_29 = __VLS_28({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.updateProfile),
    size: "small",
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_28));
let __VLS_31;
let __VLS_32;
let __VLS_33;
const __VLS_34 = {
    onClick: (__VLS_ctx.testUpdateProfile)
};
__VLS_30.slots.default;
var __VLS_30;
const __VLS_35 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_36 = __VLS_asFunctionalComponent(__VLS_35, new __VLS_35({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.logout),
    size: "small",
    ...{ class: "bg-red-500/20 border-red-400/30 text-red-300" },
}));
const __VLS_37 = __VLS_36({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.authTesting.logout),
    size: "small",
    ...{ class: "bg-red-500/20 border-red-400/30 text-red-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_36));
let __VLS_39;
let __VLS_40;
let __VLS_41;
const __VLS_42 = {
    onClick: (__VLS_ctx.testLogout)
};
__VLS_38.slots.default;
var __VLS_38;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4" },
});
const __VLS_43 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_44 = __VLS_asFunctionalComponent(__VLS_43, new __VLS_43({
    ...{ class: "text-blue-400" },
}));
const __VLS_45 = __VLS_44({
    ...{ class: "text-blue-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_44));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "p-4 rounded-lg bg-slate-700/30 border border-slate-600/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-sm font-medium text-slate-200 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-1 text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 gap-3" },
});
const __VLS_47 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_48 = __VLS_asFunctionalComponent(__VLS_47, new __VLS_47({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.getRecords),
    size: "small",
    ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
}));
const __VLS_49 = __VLS_48({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.getRecords),
    size: "small",
    ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_48));
let __VLS_51;
let __VLS_52;
let __VLS_53;
const __VLS_54 = {
    onClick: (__VLS_ctx.testGetRecords)
};
__VLS_50.slots.default;
var __VLS_50;
const __VLS_55 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_56 = __VLS_asFunctionalComponent(__VLS_55, new __VLS_55({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.createRecord),
    size: "small",
    ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" },
}));
const __VLS_57 = __VLS_56({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.createRecord),
    size: "small",
    ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_56));
let __VLS_59;
let __VLS_60;
let __VLS_61;
const __VLS_62 = {
    onClick: (__VLS_ctx.testCreateRecord)
};
__VLS_58.slots.default;
var __VLS_58;
const __VLS_63 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_64 = __VLS_asFunctionalComponent(__VLS_63, new __VLS_63({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.uploadFile),
    size: "small",
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300" },
}));
const __VLS_65 = __VLS_64({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.uploadFile),
    size: "small",
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_64));
let __VLS_67;
let __VLS_68;
let __VLS_69;
const __VLS_70 = {
    onClick: (__VLS_ctx.testUploadFile)
};
__VLS_66.slots.default;
var __VLS_66;
const __VLS_71 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_72 = __VLS_asFunctionalComponent(__VLS_71, new __VLS_71({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.getStatistics),
    size: "small",
    ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300" },
}));
const __VLS_73 = __VLS_72({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.recordTesting.getStatistics),
    size: "small",
    ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_72));
let __VLS_75;
let __VLS_76;
let __VLS_77;
const __VLS_78 = {
    onClick: (__VLS_ctx.testGetStatistics)
};
__VLS_74.slots.default;
var __VLS_74;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2 mb-4" },
});
const __VLS_79 = {}.ThunderboltOutlined;
/** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
// @ts-ignore
const __VLS_80 = __VLS_asFunctionalComponent(__VLS_79, new __VLS_79({
    ...{ class: "text-purple-400" },
}));
const __VLS_81 = __VLS_80({
    ...{ class: "text-purple-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_80));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "p-4 rounded-lg bg-slate-700/30 border border-slate-600/30" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
    ...{ class: "text-sm font-medium text-slate-200 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "space-y-1 text-xs text-slate-400" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-2 gap-3" },
});
const __VLS_83 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_84 = __VLS_asFunctionalComponent(__VLS_83, new __VLS_83({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.getRules),
    size: "small",
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300" },
}));
const __VLS_85 = __VLS_84({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.getRules),
    size: "small",
    ...{ class: "bg-purple-500/20 border-purple-400/30 text-purple-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_84));
let __VLS_87;
let __VLS_88;
let __VLS_89;
const __VLS_90 = {
    onClick: (__VLS_ctx.testGetQCRules)
};
__VLS_86.slots.default;
var __VLS_86;
const __VLS_91 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_92 = __VLS_asFunctionalComponent(__VLS_91, new __VLS_91({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.startAnalysis),
    size: "small",
    ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" },
}));
const __VLS_93 = __VLS_92({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.startAnalysis),
    size: "small",
    ...{ class: "bg-emerald-500/20 border-emerald-400/30 text-emerald-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_92));
let __VLS_95;
let __VLS_96;
let __VLS_97;
const __VLS_98 = {
    onClick: (__VLS_ctx.testStartAnalysis)
};
__VLS_94.slots.default;
var __VLS_94;
const __VLS_99 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_100 = __VLS_asFunctionalComponent(__VLS_99, new __VLS_99({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.getResult),
    size: "small",
    ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
}));
const __VLS_101 = __VLS_100({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.getResult),
    size: "small",
    ...{ class: "bg-blue-500/20 border-blue-400/30 text-blue-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_100));
let __VLS_103;
let __VLS_104;
let __VLS_105;
const __VLS_106 = {
    onClick: (__VLS_ctx.testGetQCResult)
};
__VLS_102.slots.default;
var __VLS_102;
const __VLS_107 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_108 = __VLS_asFunctionalComponent(__VLS_107, new __VLS_107({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.getHistory),
    size: "small",
    ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300" },
}));
const __VLS_109 = __VLS_108({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.qcTesting.getHistory),
    size: "small",
    ...{ class: "bg-amber-500/20 border-amber-400/30 text-amber-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_108));
let __VLS_111;
let __VLS_112;
let __VLS_113;
const __VLS_114 = {
    onClick: (__VLS_ctx.testGetQCHistory)
};
__VLS_110.slots.default;
var __VLS_110;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-xl bg-slate-800/50 backdrop-blur-sm border border-slate-700/50 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-slate-100 flex items-center gap-2" },
});
const __VLS_115 = {}.FileTextOutlined;
/** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
// @ts-ignore
const __VLS_116 = __VLS_asFunctionalComponent(__VLS_115, new __VLS_115({
    ...{ class: "text-green-400" },
}));
const __VLS_117 = __VLS_116({
    ...{ class: "text-green-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_116));
const __VLS_119 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_120 = __VLS_asFunctionalComponent(__VLS_119, new __VLS_119({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300" },
}));
const __VLS_121 = __VLS_120({
    ...{ 'onClick': {} },
    size: "small",
    ...{ class: "bg-slate-700/50 border-slate-600/50 text-slate-300" },
}, ...__VLS_functionalComponentArgsRest(__VLS_120));
let __VLS_123;
let __VLS_124;
let __VLS_125;
const __VLS_126 = {
    onClick: (__VLS_ctx.clearLogs)
};
__VLS_122.slots.default;
var __VLS_122;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-h-64 overflow-y-auto space-y-2" },
});
for (const [log] of __VLS_getVForSourceType((__VLS_ctx.testLogs))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (log.id),
        ...{ class: "p-2 rounded text-xs font-mono" },
        ...{ class: (__VLS_ctx.getLogClass(log.type)) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between mb-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "font-medium" },
    });
    (log.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-slate-500" },
    });
    (__VLS_ctx.formatTime(log.timestamp));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    (log.message);
    if (log.details) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-1 text-slate-400" },
        });
        (log.details);
    }
}
if (__VLS_ctx.testLogs.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-center py-8" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-slate-400 text-sm" },
    });
}
/** @type {__VLS_StyleScopedClasses['api-test-view']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-slate-900']} */ ;
/** @type {__VLS_StyleScopedClasses['via-slate-800']} */ ;
/** @type {__VLS_StyleScopedClasses['to-slate-900']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-6xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-cyan-400']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-8']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-400']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-purple-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-red-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-red-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-red-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-purple-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-amber-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-amber-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-400']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/30']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-purple-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-emerald-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-emerald-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-emerald-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-amber-500/20']} */ ;
/** @type {__VLS_StyleScopedClasses['border-amber-400/30']} */ ;
/** @type {__VLS_StyleScopedClasses['text-amber-300']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-800/50']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-100']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-slate-700/50']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-600/50']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-300']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-64']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-400']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            ApiOutlined: icons_vue_1.ApiOutlined,
            UserOutlined: icons_vue_1.UserOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            ApiConnectionTest: ApiConnectionTest_vue_1.default,
            authTesting: authTesting,
            recordTesting: recordTesting,
            qcTesting: qcTesting,
            testLogs: testLogs,
            testLogin: testLogin,
            testGetUser: testGetUser,
            testUpdateProfile: testUpdateProfile,
            testLogout: testLogout,
            testGetRecords: testGetRecords,
            testCreateRecord: testCreateRecord,
            testUploadFile: testUploadFile,
            testGetStatistics: testGetStatistics,
            testGetQCRules: testGetQCRules,
            testStartAnalysis: testStartAnalysis,
            testGetQCResult: testGetQCResult,
            testGetQCHistory: testGetQCHistory,
            clearLogs: clearLogs,
            getLogClass: getLogClass,
            formatTime: formatTime,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
