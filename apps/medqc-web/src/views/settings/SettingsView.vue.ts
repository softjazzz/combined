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
// 导入组件
const UserEditModal_vue_1 = __importDefault(require("@/components/settings/UserEditModal.vue"));
const RoleEditModal_vue_1 = __importDefault(require("@/components/settings/RoleEditModal.vue"));
// 页面状态
const activeTab = (0, vue_1.ref)('users');
const loading = (0, vue_1.reactive)({
    users: false,
    roles: false,
    permissions: false,
    systemConfig: false
});
// 模态框状态
const modals = (0, vue_1.reactive)({
    userEdit: false,
    roleEdit: false
});
// 选中的数据
const selectedUser = (0, vue_1.ref)(null);
const selectedRole = (0, vue_1.ref)(null);
// 用户管理相关
const users = (0, vue_1.ref)([
    {
        id: '1',
        email: 'admin@demo.com',
        display_name: '系统管理员',
        roles: ['admin'],
        department: '信息科',
        hospital_name: '示例医院',
        is_active: true,
        last_login: new Date().toISOString(),
        created_at: new Date().toISOString()
    },
    {
        id: '2',
        email: 'qc@demo.com',
        display_name: '质控管理员',
        roles: ['qc_manager'],
        department: '质控科',
        hospital_name: '示例医院',
        is_active: true,
        last_login: new Date(Date.now() - 86400000).toISOString(),
        created_at: new Date().toISOString()
    },
    {
        id: '3',
        email: 'doctor@demo.com',
        display_name: '医务人员',
        roles: ['doctor'],
        department: '内科',
        hospital_name: '示例医院',
        is_active: true,
        last_login: new Date(Date.now() - 3600000).toISOString(),
        created_at: new Date().toISOString()
    }
]);
const userSearch = (0, vue_1.reactive)({
    email: '',
    role: '',
    status: ''
});
// 角色管理相关
const roles = (0, vue_1.ref)([
    {
        key: 'admin',
        name: '系统管理员',
        description: '拥有系统全部权限，可以管理用户、角色和系统配置',
        icon: icons_vue_1.CrownOutlined,
        color: 'text-orange-500',
        userCount: 2,
        permissionCount: 25
    },
    {
        key: 'qc_manager',
        name: '质控管理员',
        description: '负责质控规则管理和质控流程监督',
        icon: icons_vue_1.SafetyOutlined,
        color: 'text-blue-500',
        userCount: 5,
        permissionCount: 18
    },
    {
        key: 'qc_staff',
        name: '质控人员',
        description: '执行质控分析和审核工作',
        icon: icons_vue_1.SafetyCertificateOutlined,
        color: 'text-green-500',
        userCount: 12,
        permissionCount: 10
    },
    {
        key: 'doctor',
        name: '医务人员',
        description: '上传和管理自己的病案记录',
        icon: icons_vue_1.MedicineBoxOutlined,
        color: 'text-purple-500',
        userCount: 45,
        permissionCount: 6
    }
]);
// 权限配置相关
const permissionMatrix = (0, vue_1.ref)([
    {
        resource: '病案记录',
        admin: true,
        qc_manager: true,
        qc_staff: true,
        doctor: true
    },
    {
        resource: '质控结果',
        admin: true,
        qc_manager: true,
        qc_staff: true,
        doctor: false
    },
    {
        resource: '质控规则',
        admin: true,
        qc_manager: true,
        qc_staff: false,
        doctor: false
    },
    {
        resource: '用户管理',
        admin: true,
        qc_manager: false,
        qc_staff: false,
        doctor: false
    },
    {
        resource: '统计报表',
        admin: true,
        qc_manager: true,
        qc_staff: true,
        doctor: false
    },
    {
        resource: '系统设置',
        admin: true,
        qc_manager: false,
        qc_staff: false,
        doctor: false
    }
]);
// 系统配置
const systemConfig = (0, vue_1.reactive)({
    systemName: '病案质控系统',
    version: '1.0.0',
    sessionTimeout: 30,
    passwordMinLength: 6,
    enableMFA: false,
    enableAuditLog: true,
    llmPointerMode: true,
    llmSummaryMaxLen: 80
});
// 用户表格列配置
const userColumns = [
    {
        title: '用户信息',
        key: 'user_info',
        width: 250
    },
    {
        title: '角色',
        key: 'roles',
        width: 150
    },
    {
        title: '部门',
        key: 'department',
        width: 150
    },
    {
        title: '状态',
        key: 'status',
        width: 100
    },
    {
        title: '最后登录',
        key: 'last_login',
        width: 150
    },
    {
        title: '操作',
        key: 'actions',
        width: 200,
        fixed: 'right'
    }
];
// 权限表格列配置
const permissionColumns = [
    {
        title: '资源',
        dataIndex: 'resource',
        key: 'resource',
        width: 150
    },
    {
        title: '管理员',
        key: 'admin',
        width: 100,
        align: 'center'
    },
    {
        title: '质控管理员',
        key: 'qc_manager',
        width: 120,
        align: 'center'
    },
    {
        title: '质控人员',
        key: 'qc_staff',
        width: 100,
        align: 'center'
    },
    {
        title: '医务人员',
        key: 'doctor',
        width: 100,
        align: 'center'
    }
];
// 计算属性
const filteredUsers = (0, vue_1.computed)(() => {
    return users.value.filter(user => {
        const emailMatch = !userSearch.email || user.email?.toLowerCase().includes(userSearch.email.toLowerCase());
        const roleMatch = !userSearch.role || user.roles?.includes(userSearch.role);
        const statusMatch = !userSearch.status || (userSearch.status === 'active' ? user.is_active : !user.is_active);
        return emailMatch && roleMatch && statusMatch;
    });
});
// 方法
const refreshUsers = async () => {
    loading.users = true;
    try {
        // TODO: 从数据库获取用户列表
        await new Promise(resolve => setTimeout(resolve, 1000));
        ant_design_vue_1.message.success('用户列表已刷新');
    }
    catch (error) {
        ant_design_vue_1.message.error('获取用户列表失败');
    }
    finally {
        loading.users = false;
    }
};
const handleUserSearch = () => {
    // 搜索逻辑在computed中处理
};
const showCreateUserModal = () => {
    selectedUser.value = null;
    modals.userEdit = true;
};
const editUser = (user) => {
    selectedUser.value = user;
    modals.userEdit = true;
};
const editRole = (role) => {
    selectedRole.value = role;
    modals.roleEdit = true;
};
const toggleUserStatus = async (user) => {
    try {
        user.is_active = !user.is_active;
        ant_design_vue_1.message.success(`用户已${user.is_active ? '激活' : '停用'}`);
    }
    catch (error) {
        ant_design_vue_1.message.error('操作失败');
    }
};
const deleteUser = (user) => {
    ant_design_vue_1.message.info('删除用户功能开发中');
};
const handleUserSubmit = async (userData) => {
    try {
        ant_design_vue_1.message.success('用户保存成功');
        modals.userEdit = false;
        refreshUsers();
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
};
const handleRoleSubmit = async (roleData) => {
    try {
        ant_design_vue_1.message.success('角色保存成功');
        modals.roleEdit = false;
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
};
const handlePermissionChange = (resource, role: any,  checked: any) => {
    ant_design_vue_1.message.info(`${resource} - ${role}: ${checked ? '授权' : '取消授权'}`);
};
const saveSystemConfig = async () => {
    loading.systemConfig = true;
    try {
        // 将配置同步到运行时 LLM 服务
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        const pointerMode = !!systemConfig.llmPointerMode;
        const summaryMaxLength = Number(systemConfig.llmSummaryMaxLen) || 0;
        llmService.updateConfig({ pointerMode, summaryMaxLength  });
        // 全局持久化到 Supabase（user_id=null）
        const { llmConfigService } = await Promise.resolve().then(() => __importStar(require('@/services/llmConfigService')));
        await llmConfigService.saveUserPointerPrefs({ pointerMode, summaryMaxLength   });
        await new Promise(resolve => setTimeout(resolve, 600));
        ant_design_vue_1.message.success('系统配置保存成功（已全局持久化至数据库）');
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
    finally {
        loading.systemConfig = false;
    }
};
const exportConfig = () => {
    ant_design_vue_1.message.info('导出配置功能开发中');
};
const importConfig = () => {
    ant_design_vue_1.message.info('导入配置功能开发中');
};
// 工具函数
const getUserAvatarColor = (email) => {
    const colors = ['#f56a00', '#7265e6', '#ffbf00', '#00a2ae', '#f56a00'];
    const index = email.charCodeAt(0) % colors.length;
    return colors[index];
};
const getRoleColor = (role) => {
    const colorMap = {
        'admin': 'orange',
        'qc_manager': 'blue',
        'qc_staff': 'green',
        'doctor': 'purple'
    };
    return colorMap[role] || 'default';
};
const getRoleText = (role) => {
    const textMap = {
        'admin': '管理员',
        'qc_manager': '质控管理员',
        'qc_staff': '质控人员',
        'doctor': '医务人员'
    };
    return textMap[role] || role;
};
const formatDateTime = (dateString) => {
    return new Date(dateString).toLocaleString();
};
// 组件挂载
(0, vue_1.onMounted)(async () => {
    // 启动时尝试从全局持久化中恢复配置
    try {
        const { llmConfigService } = await Promise.resolve().then(() => __importStar(require('@/services/llmConfigService')));
        const prefs = await llmConfigService.getUserPointerPrefs();
        if (prefs) {
            systemConfig.llmPointerMode = !!prefs.pointerMode;
            systemConfig.llmSummaryMaxLen = Number(prefs.summaryMaxLength) || 0;
            const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
            llmService.updateConfig(prefs);
        }
    }
    catch (e) {
        console.warn('加载全局LLM解析优化配置失败（可忽略）:', e);
    }
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['settings-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['role-card']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-matrix']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-matrix']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "settings-container min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "max-w-7xl mx-auto px-6 py-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-4" },
});
const __VLS_0 = {}.SettingOutlined;
/** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-3xl text-blue-600" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-3xl text-blue-600" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-2xl font-bold text-gray-900" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex space-x-3" },
});
const __VLS_4 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (__VLS_ctx.exportConfig)
};
__VLS_7.slots.default;
const __VLS_12 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
var __VLS_7;
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (__VLS_ctx.importConfig)
};
__VLS_19.slots.default;
const __VLS_24 = {}.UploadOutlined;
/** @type {[typeof __VLS_components.UploadOutlined, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
var __VLS_19;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
const __VLS_28 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
}));
const __VLS_30 = __VLS_29({
    ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
    ...{ class: "settings-tabs" },
}));
const __VLS_34 = __VLS_33({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
    ...{ class: "settings-tabs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    key: "users",
    tab: "用户管理",
}));
const __VLS_38 = __VLS_37({
    key: "users",
    tab: "用户管理",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_39.slots;
    const __VLS_40 = {}.UserOutlined;
    /** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        ...{ class: "mr-2" },
    }));
    const __VLS_42 = __VLS_41({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
var __VLS_39;
const __VLS_44 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    key: "roles",
    tab: "角色管理",
}));
const __VLS_46 = __VLS_45({
    key: "roles",
    tab: "角色管理",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_47.slots;
    const __VLS_48 = {}.TeamOutlined;
    /** @type {[typeof __VLS_components.TeamOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ class: "mr-2" },
    }));
    const __VLS_50 = __VLS_49({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
}
var __VLS_47;
const __VLS_52 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    key: "permissions",
    tab: "权限配置",
}));
const __VLS_54 = __VLS_53({
    key: "permissions",
    tab: "权限配置",
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_55.slots;
    const __VLS_56 = {}.SafetyCertificateOutlined;
    /** @type {[typeof __VLS_components.SafetyCertificateOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        ...{ class: "mr-2" },
    }));
    const __VLS_58 = __VLS_57({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
}
var __VLS_55;
const __VLS_60 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    key: "system",
    tab: "系统配置",
}));
const __VLS_62 = __VLS_61({
    key: "system",
    tab: "系统配置",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_63.slots;
    const __VLS_64 = {}.SettingOutlined;
    /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        ...{ class: "mr-2" },
    }));
    const __VLS_66 = __VLS_65({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
}
var __VLS_63;
const __VLS_68 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    key: "llm",
    tab: "LLM配置",
}));
const __VLS_70 = __VLS_69({
    key: "llm",
    tab: "LLM配置",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
{
    const { tab: __VLS_thisSlot } = __VLS_71.slots;
    const __VLS_72 = {}.ApiOutlined;
    /** @type {[typeof __VLS_components.ApiOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ class: "mr-2" },
    }));
    const __VLS_74 = __VLS_73({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
}
var __VLS_71;
var __VLS_35;
var __VLS_31;
if (__VLS_ctx.activeTab === 'users') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_76 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        title: "用户管理",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }));
    const __VLS_78 = __VLS_77({
        title: "用户管理",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_79.slots;
        const __VLS_80 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
        const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
        __VLS_83.slots.default;
        const __VLS_84 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
            ...{ 'onClick': {} },
            type: "primary",
            icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
        }));
        const __VLS_86 = __VLS_85({
            ...{ 'onClick': {} },
            type: "primary",
            icon: (__VLS_ctx.h(__VLS_ctx.PlusOutlined)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_85));
        let __VLS_88;
        let __VLS_89;
        let __VLS_90;
        const __VLS_91 = {
            onClick: (__VLS_ctx.showCreateUserModal)
        };
        __VLS_87.slots.default;
        var __VLS_87;
        const __VLS_92 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            ...{ 'onClick': {} },
            loading: (__VLS_ctx.loading.users),
            icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
        }));
        const __VLS_94 = __VLS_93({
            ...{ 'onClick': {} },
            loading: (__VLS_ctx.loading.users),
            icon: (__VLS_ctx.h(__VLS_ctx.ReloadOutlined)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        let __VLS_96;
        let __VLS_97;
        let __VLS_98;
        const __VLS_99 = {
            onClick: (__VLS_ctx.refreshUsers)
        };
        __VLS_95.slots.default;
        var __VLS_95;
        var __VLS_83;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-4" },
    });
    const __VLS_100 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        gutter: (16),
    }));
    const __VLS_102 = __VLS_101({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    __VLS_103.slots.default;
    const __VLS_104 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        span: (8),
    }));
    const __VLS_106 = __VLS_105({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    __VLS_107.slots.default;
    const __VLS_108 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.userSearch.email),
        placeholder: "搜索邮箱",
        allowClear: true,
    }));
    const __VLS_110 = __VLS_109({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.userSearch.email),
        placeholder: "搜索邮箱",
        allowClear: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    let __VLS_112;
    let __VLS_113;
    let __VLS_114;
    const __VLS_115 = {
        onChange: (__VLS_ctx.handleUserSearch)
    };
    __VLS_111.slots.default;
    {
        const { prefix: __VLS_thisSlot } = __VLS_111.slots;
        const __VLS_116 = {}.SearchOutlined;
        /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
            ...{ class: "text-gray-400" },
        }));
        const __VLS_118 = __VLS_117({
            ...{ class: "text-gray-400" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    }
    var __VLS_111;
    var __VLS_107;
    const __VLS_120 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
        span: (6),
    }));
    const __VLS_122 = __VLS_121({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_121));
    __VLS_123.slots.default;
    const __VLS_124 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.userSearch.role),
        placeholder: "筛选角色",
        allowClear: true,
    }));
    const __VLS_126 = __VLS_125({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.userSearch.role),
        placeholder: "筛选角色",
        allowClear: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
    let __VLS_128;
    let __VLS_129;
    let __VLS_130;
    const __VLS_131 = {
        onChange: (__VLS_ctx.handleUserSearch)
    };
    __VLS_127.slots.default;
    const __VLS_132 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        value: "",
    }));
    const __VLS_134 = __VLS_133({
        value: "",
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    var __VLS_135;
    const __VLS_136 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        value: "admin",
    }));
    const __VLS_138 = __VLS_137({
        value: "admin",
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    var __VLS_139;
    const __VLS_140 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
        value: "qc_manager",
    }));
    const __VLS_142 = __VLS_141({
        value: "qc_manager",
    }, ...__VLS_functionalComponentArgsRest(__VLS_141));
    __VLS_143.slots.default;
    var __VLS_143;
    const __VLS_144 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        value: "qc_staff",
    }));
    const __VLS_146 = __VLS_145({
        value: "qc_staff",
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    __VLS_147.slots.default;
    var __VLS_147;
    const __VLS_148 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        value: "doctor",
    }));
    const __VLS_150 = __VLS_149({
        value: "doctor",
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    __VLS_151.slots.default;
    var __VLS_151;
    var __VLS_127;
    var __VLS_123;
    const __VLS_152 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        span: (6),
    }));
    const __VLS_154 = __VLS_153({
        span: (6),
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    const __VLS_156 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.userSearch.status),
        placeholder: "筛选状态",
        allowClear: true,
    }));
    const __VLS_158 = __VLS_157({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.userSearch.status),
        placeholder: "筛选状态",
        allowClear: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    let __VLS_160;
    let __VLS_161;
    let __VLS_162;
    const __VLS_163 = {
        onChange: (__VLS_ctx.handleUserSearch)
    };
    __VLS_159.slots.default;
    const __VLS_164 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        value: "",
    }));
    const __VLS_166 = __VLS_165({
        value: "",
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    __VLS_167.slots.default;
    var __VLS_167;
    const __VLS_168 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
        value: "active",
    }));
    const __VLS_170 = __VLS_169({
        value: "active",
    }, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_171.slots.default;
    var __VLS_171;
    const __VLS_172 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        value: "inactive",
    }));
    const __VLS_174 = __VLS_173({
        value: "inactive",
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
    __VLS_175.slots.default;
    var __VLS_175;
    var __VLS_159;
    var __VLS_155;
    var __VLS_103;
    const __VLS_176 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
        columns: (__VLS_ctx.userColumns),
        dataSource: (__VLS_ctx.filteredUsers),
        loading: (__VLS_ctx.loading.users),
        pagination: ({ pageSize: 10 }),
        rowKey: "id",
    }));
    const __VLS_178 = __VLS_177({
        columns: (__VLS_ctx.userColumns),
        dataSource: (__VLS_ctx.filteredUsers),
        loading: (__VLS_ctx.loading.users),
        pagination: ({ pageSize: 10 }),
        rowKey: "id",
    }, ...__VLS_functionalComponentArgsRest(__VLS_177));
    __VLS_179.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_179.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key === 'user_info') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "flex items-center space-x-3" },
            });
            const __VLS_180 = {}.AAvatar;
            /** @type {[typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, ]} */ ;
            // @ts-ignore
            const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
                size: (40),
                ...{ style: ({ backgroundColor: __VLS_ctx.getUserAvatarColor(record.email) }) },
            }));
            const __VLS_182 = __VLS_181({
                size: (40),
                ...{ style: ({ backgroundColor: __VLS_ctx.getUserAvatarColor(record.email) }) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_181));
            __VLS_183.slots.default;
            (record.display_name?.charAt(0) || record.email?.charAt(0));
            var __VLS_183;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "font-medium" },
            });
            (record.display_name || record.email);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-sm text-gray-500" },
            });
            (record.email);
        }
        else if (column.key === 'roles') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "space-y-1" },
            });
            for (const [role] of __VLS_getVForSourceType((record.roles))) {
                const __VLS_184 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
                    key: (role),
                    color: (__VLS_ctx.getRoleColor(role)),
                    ...{ class: "mb-1" },
                }));
                const __VLS_186 = __VLS_185({
                    key: (role),
                    color: (__VLS_ctx.getRoleColor(role)),
                    ...{ class: "mb-1" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_185));
                __VLS_187.slots.default;
                (__VLS_ctx.getRoleText(role));
                var __VLS_187;
            }
        }
        else if (column.key === 'department') {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "font-medium" },
            });
            (record.department || '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-sm text-gray-500" },
            });
            (record.hospital_name || '全院');
        }
        else if (column.key === 'status') {
            const __VLS_188 = {}.ABadge;
            /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
            // @ts-ignore
            const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
                status: (record.is_active ? 'success' : 'default'),
                text: (record.is_active ? '激活' : '停用'),
            }));
            const __VLS_190 = __VLS_189({
                status: (record.is_active ? 'success' : 'default'),
                text: (record.is_active ? '激活' : '停用'),
            }, ...__VLS_functionalComponentArgsRest(__VLS_189));
        }
        else if (column.key === 'last_login') {
            if (record.last_login) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
                (__VLS_ctx.formatDateTime(record.last_login));
            }
            else {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "text-gray-400" },
                });
            }
        }
        else if (column.key === 'actions') {
            const __VLS_192 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
                size: "small",
            }));
            const __VLS_194 = __VLS_193({
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_193));
            __VLS_195.slots.default;
            const __VLS_196 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }));
            const __VLS_198 = __VLS_197({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
            }, ...__VLS_functionalComponentArgsRest(__VLS_197));
            let __VLS_200;
            let __VLS_201;
            let __VLS_202;
            const __VLS_203 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activeTab === 'users'))
                        return;
                    if (!!(column.key === 'user_info'))
                        return;
                    if (!!(column.key === 'roles'))
                        return;
                    if (!!(column.key === 'department'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'last_login'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.editUser(record);
                }
            };
            __VLS_199.slots.default;
            var __VLS_199;
            const __VLS_204 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
                ...{ class: (record.is_active ? 'text-red-500' : 'text-green-500') },
            }));
            const __VLS_206 = __VLS_205({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
                ...{ class: (record.is_active ? 'text-red-500' : 'text-green-500') },
            }, ...__VLS_functionalComponentArgsRest(__VLS_205));
            let __VLS_208;
            let __VLS_209;
            let __VLS_210;
            const __VLS_211 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activeTab === 'users'))
                        return;
                    if (!!(column.key === 'user_info'))
                        return;
                    if (!!(column.key === 'roles'))
                        return;
                    if (!!(column.key === 'department'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'last_login'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.toggleUserStatus(record);
                }
            };
            __VLS_207.slots.default;
            (record.is_active ? '停用' : '激活');
            var __VLS_207;
            const __VLS_212 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
                danger: true,
            }));
            const __VLS_214 = __VLS_213({
                ...{ 'onClick': {} },
                type: "link",
                size: "small",
                danger: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_213));
            let __VLS_216;
            let __VLS_217;
            let __VLS_218;
            const __VLS_219 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.activeTab === 'users'))
                        return;
                    if (!!(column.key === 'user_info'))
                        return;
                    if (!!(column.key === 'roles'))
                        return;
                    if (!!(column.key === 'department'))
                        return;
                    if (!!(column.key === 'status'))
                        return;
                    if (!!(column.key === 'last_login'))
                        return;
                    if (!(column.key === 'actions'))
                        return;
                    __VLS_ctx.deleteUser(record);
                }
            };
            __VLS_215.slots.default;
            var __VLS_215;
            var __VLS_195;
        }
    }
    var __VLS_179;
    var __VLS_79;
}
if (__VLS_ctx.activeTab === 'roles') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_220 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
        title: "角色管理",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }));
    const __VLS_222 = __VLS_221({
        title: "角色管理",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_221));
    __VLS_223.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6" },
    });
    for (const [role] of __VLS_getVForSourceType((__VLS_ctx.roles))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (role.key),
            ...{ class: "role-card" },
        });
        const __VLS_224 = {}.ACard;
        /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
        // @ts-ignore
        const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
            ...{ 'onClick': {} },
            ...{ class: (['h-full', 'transition-all', 'duration-300', 'hover:shadow-lg', 'cursor-pointer']) },
        }));
        const __VLS_226 = __VLS_225({
            ...{ 'onClick': {} },
            ...{ class: (['h-full', 'transition-all', 'duration-300', 'hover:shadow-lg', 'cursor-pointer']) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_225));
        let __VLS_228;
        let __VLS_229;
        let __VLS_230;
        const __VLS_231 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.activeTab === 'roles'))
                    return;
                __VLS_ctx.editRole(role);
            }
        };
        __VLS_227.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-center" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mb-4" },
        });
        const __VLS_232 = ((role.icon));
        // @ts-ignore
        const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
            ...{ class: (['text-4xl', role.color]) },
        }));
        const __VLS_234 = __VLS_233({
            ...{ class: (['text-4xl', role.color]) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_233));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
            ...{ class: "text-lg font-semibold mb-2" },
        });
        (role.name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-gray-600 text-sm mb-4" },
        });
        (role.description);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "space-y-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex justify-between text-sm" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "font-medium" },
        });
        (role.userCount);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex justify-between text-sm" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "font-medium" },
        });
        (role.permissionCount);
        var __VLS_227;
    }
    var __VLS_223;
}
if (__VLS_ctx.activeTab === 'permissions') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_236 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
        title: "权限配置",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }));
    const __VLS_238 = __VLS_237({
        title: "权限配置",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_237));
    __VLS_239.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-6" },
    });
    const __VLS_240 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
        message: "权限配置说明",
        description: "以下是系统各角色的权限配置矩阵，您可以根据需要调整各角色的权限设置。",
        type: "info",
        showIcon: true,
        ...{ class: "mb-4" },
    }));
    const __VLS_242 = __VLS_241({
        message: "权限配置说明",
        description: "以下是系统各角色的权限配置矩阵，您可以根据需要调整各角色的权限设置。",
        type: "info",
        showIcon: true,
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_241));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "permission-matrix" },
    });
    const __VLS_244 = {}.ATable;
    /** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
    // @ts-ignore
    const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
        columns: (__VLS_ctx.permissionColumns),
        dataSource: (__VLS_ctx.permissionMatrix),
        pagination: (false),
        bordered: true,
        size: "small",
    }));
    const __VLS_246 = __VLS_245({
        columns: (__VLS_ctx.permissionColumns),
        dataSource: (__VLS_ctx.permissionMatrix),
        pagination: (false),
        bordered: true,
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_245));
    __VLS_247.slots.default;
    {
        const { bodyCell: __VLS_thisSlot } = __VLS_247.slots;
        const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
        if (column.key !== 'resource') {
            const __VLS_248 = {}.ACheckbox;
            /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
            // @ts-ignore
            const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
                ...{ 'onChange': {} },
                checked: (record[column.key]),
            }));
            const __VLS_250 = __VLS_249({
                ...{ 'onChange': {} },
                checked: (record[column.key]),
            }, ...__VLS_functionalComponentArgsRest(__VLS_249));
            let __VLS_252;
            let __VLS_253;
            let __VLS_254;
            const __VLS_255 = {
                onChange: (...[$event]) => {
                    if (!(__VLS_ctx.activeTab === 'permissions'))
                        return;
                    if (!(column.key !== 'resource'))
                        return;
                    __VLS_ctx.handlePermissionChange(record.resource, column.key, $event);
                }
            };
            var __VLS_251;
        }
    }
    var __VLS_247;
    var __VLS_239;
}
if (__VLS_ctx.activeTab === 'system') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    const __VLS_256 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
        title: "系统配置",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }));
    const __VLS_258 = __VLS_257({
        title: "系统配置",
        ...{ class: "bg-white/80 backdrop-blur-sm border-0 shadow-xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_257));
    __VLS_259.slots.default;
    const __VLS_260 = {}.AForm;
    /** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
    // @ts-ignore
    const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
        model: (__VLS_ctx.systemConfig),
        layout: "vertical",
    }));
    const __VLS_262 = __VLS_261({
        model: (__VLS_ctx.systemConfig),
        layout: "vertical",
    }, ...__VLS_functionalComponentArgsRest(__VLS_261));
    __VLS_263.slots.default;
    const __VLS_264 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
        gutter: (24),
    }));
    const __VLS_266 = __VLS_265({
        gutter: (24),
    }, ...__VLS_functionalComponentArgsRest(__VLS_265));
    __VLS_267.slots.default;
    const __VLS_268 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
        span: (12),
    }));
    const __VLS_270 = __VLS_269({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_269));
    __VLS_271.slots.default;
    const __VLS_272 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
        label: "系统名称",
    }));
    const __VLS_274 = __VLS_273({
        label: "系统名称",
    }, ...__VLS_functionalComponentArgsRest(__VLS_273));
    __VLS_275.slots.default;
    const __VLS_276 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({
        value: (__VLS_ctx.systemConfig.systemName),
    }));
    const __VLS_278 = __VLS_277({
        value: (__VLS_ctx.systemConfig.systemName),
    }, ...__VLS_functionalComponentArgsRest(__VLS_277));
    var __VLS_275;
    var __VLS_271;
    const __VLS_280 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
        span: (12),
    }));
    const __VLS_282 = __VLS_281({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_281));
    __VLS_283.slots.default;
    const __VLS_284 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
        label: "系统版本",
    }));
    const __VLS_286 = __VLS_285({
        label: "系统版本",
    }, ...__VLS_functionalComponentArgsRest(__VLS_285));
    __VLS_287.slots.default;
    const __VLS_288 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
        value: (__VLS_ctx.systemConfig.version),
        readonly: true,
    }));
    const __VLS_290 = __VLS_289({
        value: (__VLS_ctx.systemConfig.version),
        readonly: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_289));
    var __VLS_287;
    var __VLS_283;
    var __VLS_267;
    const __VLS_292 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
        gutter: (24),
    }));
    const __VLS_294 = __VLS_293({
        gutter: (24),
    }, ...__VLS_functionalComponentArgsRest(__VLS_293));
    __VLS_295.slots.default;
    const __VLS_296 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
        span: (12),
    }));
    const __VLS_298 = __VLS_297({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_297));
    __VLS_299.slots.default;
    const __VLS_300 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({
        label: "会话超时时间(分钟)",
    }));
    const __VLS_302 = __VLS_301({
        label: "会话超时时间(分钟)",
    }, ...__VLS_functionalComponentArgsRest(__VLS_301));
    __VLS_303.slots.default;
    const __VLS_304 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
        value: (__VLS_ctx.systemConfig.sessionTimeout),
        min: (5),
        max: (1440),
        ...{ style: {} },
    }));
    const __VLS_306 = __VLS_305({
        value: (__VLS_ctx.systemConfig.sessionTimeout),
        min: (5),
        max: (1440),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_305));
    var __VLS_303;
    var __VLS_299;
    const __VLS_308 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({
        span: (12),
    }));
    const __VLS_310 = __VLS_309({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_309));
    __VLS_311.slots.default;
    const __VLS_312 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_313 = __VLS_asFunctionalComponent(__VLS_312, new __VLS_312({
        label: "密码最小长度",
    }));
    const __VLS_314 = __VLS_313({
        label: "密码最小长度",
    }, ...__VLS_functionalComponentArgsRest(__VLS_313));
    __VLS_315.slots.default;
    const __VLS_316 = {}.AInputNumber;
    /** @type {[typeof __VLS_components.AInputNumber, typeof __VLS_components.aInputNumber, ]} */ ;
    // @ts-ignore
    const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
        value: (__VLS_ctx.systemConfig.passwordMinLength),
        min: (6),
        max: (20),
        ...{ style: {} },
    }));
    const __VLS_318 = __VLS_317({
        value: (__VLS_ctx.systemConfig.passwordMinLength),
        min: (6),
        max: (20),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_317));
    var __VLS_315;
    var __VLS_311;
    var __VLS_295;
    const __VLS_320 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
        gutter: (24),
    }));
    const __VLS_322 = __VLS_321({
        gutter: (24),
    }, ...__VLS_functionalComponentArgsRest(__VLS_321));
    __VLS_323.slots.default;
    const __VLS_324 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_325 = __VLS_asFunctionalComponent(__VLS_324, new __VLS_324({
        span: (12),
    }));
    const __VLS_326 = __VLS_325({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_325));
    __VLS_327.slots.default;
    const __VLS_328 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
        label: "启用多因素认证",
    }));
    const __VLS_330 = __VLS_329({
        label: "启用多因素认证",
    }, ...__VLS_functionalComponentArgsRest(__VLS_329));
    __VLS_331.slots.default;
    const __VLS_332 = {}.ASwitch;
    /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
    // @ts-ignore
    const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({
        checked: (__VLS_ctx.systemConfig.enableMFA),
    }));
    const __VLS_334 = __VLS_333({
        checked: (__VLS_ctx.systemConfig.enableMFA),
    }, ...__VLS_functionalComponentArgsRest(__VLS_333));
    var __VLS_331;
    var __VLS_327;
    const __VLS_336 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({
        span: (12),
    }));
    const __VLS_338 = __VLS_337({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_337));
    __VLS_339.slots.default;
    const __VLS_340 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_341 = __VLS_asFunctionalComponent(__VLS_340, new __VLS_340({
        label: "启用审计日志",
    }));
    const __VLS_342 = __VLS_341({
        label: "启用审计日志",
    }, ...__VLS_functionalComponentArgsRest(__VLS_341));
    __VLS_343.slots.default;
    const __VLS_344 = {}.ASwitch;
    /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
    // @ts-ignore
    const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
        checked: (__VLS_ctx.systemConfig.enableAuditLog),
    }));
    const __VLS_346 = __VLS_345({
        checked: (__VLS_ctx.systemConfig.enableAuditLog),
    }, ...__VLS_functionalComponentArgsRest(__VLS_345));
    var __VLS_343;
    var __VLS_339;
    const __VLS_348 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_349 = __VLS_asFunctionalComponent(__VLS_348, new __VLS_348({
        orientation: "left",
    }));
    const __VLS_350 = __VLS_349({
        orientation: "left",
    }, ...__VLS_functionalComponentArgsRest(__VLS_349));
    __VLS_351.slots.default;
    var __VLS_351;
    const __VLS_352 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({
        gutter: (24),
    }));
    const __VLS_354 = __VLS_353({
        gutter: (24),
    }, ...__VLS_functionalComponentArgsRest(__VLS_353));
    __VLS_355.slots.default;
    const __VLS_356 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_357 = __VLS_asFunctionalComponent(__VLS_356, new __VLS_356({
        span: (12),
    }));
    const __VLS_358 = __VLS_357({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_357));
    __VLS_359.slots.default;
    const __VLS_360 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_361 = __VLS_asFunctionalComponent(__VLS_360, new __VLS_360({
        label: "启用指针模式（Pointer Mode）",
    }));
    const __VLS_362 = __VLS_361({
        label: "启用指针模式（Pointer Mode）",
    }, ...__VLS_functionalComponentArgsRest(__VLS_361));
    __VLS_363.slots.default;
    const __VLS_364 = {}.ASwitch;
    /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
    // @ts-ignore
    const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({
        checked: (__VLS_ctx.systemConfig.llmPointerMode),
    }));
    const __VLS_366 = __VLS_365({
        checked: (__VLS_ctx.systemConfig.llmPointerMode),
    }, ...__VLS_functionalComponentArgsRest(__VLS_365));
    var __VLS_363;
    var __VLS_359;
    const __VLS_368 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_369 = __VLS_asFunctionalComponent(__VLS_368, new __VLS_368({
        span: (12),
    }));
    const __VLS_370 = __VLS_369({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_369));
    __VLS_371.slots.default;
    const __VLS_372 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_373 = __VLS_asFunctionalComponent(__VLS_372, new __VLS_372({
        label: "摘要长度上限",
    }));
    const __VLS_374 = __VLS_373({
        label: "摘要长度上限",
    }, ...__VLS_functionalComponentArgsRest(__VLS_373));
    __VLS_375.slots.default;
    const __VLS_376 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_377 = __VLS_asFunctionalComponent(__VLS_376, new __VLS_376({
        value: (__VLS_ctx.systemConfig.llmSummaryMaxLen),
        ...{ style: {} },
    }));
    const __VLS_378 = __VLS_377({
        value: (__VLS_ctx.systemConfig.llmSummaryMaxLen),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_377));
    __VLS_379.slots.default;
    const __VLS_380 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_381 = __VLS_asFunctionalComponent(__VLS_380, new __VLS_380({
        value: (0),
    }));
    const __VLS_382 = __VLS_381({
        value: (0),
    }, ...__VLS_functionalComponentArgsRest(__VLS_381));
    __VLS_383.slots.default;
    var __VLS_383;
    const __VLS_384 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_385 = __VLS_asFunctionalComponent(__VLS_384, new __VLS_384({
        value: (40),
    }));
    const __VLS_386 = __VLS_385({
        value: (40),
    }, ...__VLS_functionalComponentArgsRest(__VLS_385));
    __VLS_387.slots.default;
    var __VLS_387;
    const __VLS_388 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_389 = __VLS_asFunctionalComponent(__VLS_388, new __VLS_388({
        value: (80),
    }));
    const __VLS_390 = __VLS_389({
        value: (80),
    }, ...__VLS_functionalComponentArgsRest(__VLS_389));
    __VLS_391.slots.default;
    var __VLS_391;
    var __VLS_379;
    var __VLS_375;
    var __VLS_371;
    var __VLS_355;
    var __VLS_323;
    const __VLS_392 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_393 = __VLS_asFunctionalComponent(__VLS_392, new __VLS_392({}));
    const __VLS_394 = __VLS_393({}, ...__VLS_functionalComponentArgsRest(__VLS_393));
    __VLS_395.slots.default;
    const __VLS_396 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_397 = __VLS_asFunctionalComponent(__VLS_396, new __VLS_396({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.loading.systemConfig),
    }));
    const __VLS_398 = __VLS_397({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.loading.systemConfig),
    }, ...__VLS_functionalComponentArgsRest(__VLS_397));
    let __VLS_400;
    let __VLS_401;
    let __VLS_402;
    const __VLS_403 = {
        onClick: (__VLS_ctx.saveSystemConfig)
    };
    __VLS_399.slots.default;
    var __VLS_399;
    var __VLS_395;
    var __VLS_263;
    var __VLS_259;
}
/** @type {[typeof UserEditModal, ]} */ ;
// @ts-ignore
const __VLS_404 = __VLS_asFunctionalComponent(UserEditModal_vue_1.default, new UserEditModal_vue_1.default({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modals.userEdit),
    user: (__VLS_ctx.selectedUser),
}));
const __VLS_405 = __VLS_404({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modals.userEdit),
    user: (__VLS_ctx.selectedUser),
}, ...__VLS_functionalComponentArgsRest(__VLS_404));
let __VLS_407;
let __VLS_408;
let __VLS_409;
const __VLS_410 = {
    onSubmit: (__VLS_ctx.handleUserSubmit)
};
const __VLS_411 = {
    onCancel: (...[$event]) => {
        __VLS_ctx.modals.userEdit = false;
    }
};
const __VLS_412 = {
    'onUpdate:visible': ((val) => __VLS_ctx.modals.userEdit = val)
};
var __VLS_406;
/** @type {[typeof RoleEditModal, ]} */ ;
// @ts-ignore
const __VLS_413 = __VLS_asFunctionalComponent(RoleEditModal_vue_1.default, new RoleEditModal_vue_1.default({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modals.roleEdit),
    role: (__VLS_ctx.selectedRole),
}));
const __VLS_414 = __VLS_413({
    ...{ 'onSubmit': {} },
    ...{ 'onCancel': {} },
    ...{ 'onUpdate:visible': {} },
    visible: (__VLS_ctx.modals.roleEdit),
    role: (__VLS_ctx.selectedRole),
}, ...__VLS_functionalComponentArgsRest(__VLS_413));
let __VLS_416;
let __VLS_417;
let __VLS_418;
const __VLS_419 = {
    onSubmit: (__VLS_ctx.handleRoleSubmit)
};
const __VLS_420 = {
    onCancel: (...[$event]) => {
        __VLS_ctx.modals.roleEdit = false;
    }
};
const __VLS_421 = {
    'onUpdate:visible': ((val) => __VLS_ctx.modals.roleEdit = val)
};
var __VLS_415;
/** @type {__VLS_StyleScopedClasses['settings-container']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-50']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-100']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['settings-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['role-card']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-matrix']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/80']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-0']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-xl']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            SettingOutlined: icons_vue_1.SettingOutlined,
            UserOutlined: icons_vue_1.UserOutlined,
            TeamOutlined: icons_vue_1.TeamOutlined,
            SafetyCertificateOutlined: icons_vue_1.SafetyCertificateOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            SearchOutlined: icons_vue_1.SearchOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            UploadOutlined: icons_vue_1.UploadOutlined,
            UserEditModal: UserEditModal_vue_1.default,
            RoleEditModal: RoleEditModal_vue_1.default,
            activeTab: activeTab,
            loading: loading,
            modals: modals,
            selectedUser: selectedUser,
            selectedRole: selectedRole,
            userSearch: userSearch,
            roles: roles,
            permissionMatrix: permissionMatrix,
            systemConfig: systemConfig,
            userColumns: userColumns,
            permissionColumns: permissionColumns,
            filteredUsers: filteredUsers,
            refreshUsers: refreshUsers,
            handleUserSearch: handleUserSearch,
            showCreateUserModal: showCreateUserModal,
            editUser: editUser,
            editRole: editRole,
            toggleUserStatus: toggleUserStatus,
            deleteUser: deleteUser,
            handleUserSubmit: handleUserSubmit,
            handleRoleSubmit: handleRoleSubmit,
            handlePermissionChange: handlePermissionChange,
            saveSystemConfig: saveSystemConfig,
            exportConfig: exportConfig,
            importConfig: importConfig,
            getUserAvatarColor: getUserAvatarColor,
            getRoleColor: getRoleColor,
            getRoleText: getRoleText,
            formatDateTime: formatDateTime,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
