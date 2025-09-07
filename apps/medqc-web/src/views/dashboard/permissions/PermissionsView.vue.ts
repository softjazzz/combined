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
// 响应式数据
const activeTab = (0, vue_1.ref)('users');
const loading = (0, vue_1.ref)(false);
const logLoading = (0, vue_1.ref)(false);
// 用户管理相关
const userSearch = (0, vue_1.ref)('');
const selectedRole = (0, vue_1.ref)(undefined);
const selectedDepartment = (0, vue_1.ref)(undefined);
const users = (0, vue_1.ref)(: any[]);
const userPagination = (0, vue_1.ref)({
    current: 1,
    pageSize: 10,
    total: 0
});
// 角色管理相关
const roles = (0, vue_1.ref)(: any[]);
// 权限管理相关
const checkedPermissions = (0, vue_1.ref)(: any[]);
const permissionTree = (0, vue_1.ref)(: any[]);
// 日志管理相关
const logSearch = (0, vue_1.ref)('');
const selectedLogType = (0, vue_1.ref)(undefined);
const logDateRange = (0, vue_1.ref)(: any[]);
const logs = (0, vue_1.ref)(: any[]);
const logPagination = (0, vue_1.ref)({
    current: 1,
    pageSize: 10,
    total: 0
});
// 选项配置
const roleOptions = [
    { value: 'admin', label: '系统管理员' },
    { value: 'qc_manager', label: '质控管理员' },
    { value: 'doctor', label: '医生' },
    { value: 'nurse', label: '护士' }
];
const departmentOptions = [
    { value: 'internal', label: '内科' },
    { value: 'surgery', label: '外科' },
    { value: 'pediatrics', label: '儿科' }
];
const logTypeOptions = [
    { value: 'login', label: '登录' },
    { value: 'logout', label: '登出' },
    { value: 'view', label: '查看' },
    { value: 'edit', label: '编辑' },
    { value: 'delete', label: '删除' }
];
// 表格列配置
const userColumns = [
    { title: '用户名', dataIndex: 'username', key: 'username', width: 120 },
    { title: '姓名', dataIndex: 'name', key: 'name', width: 100 },
    { title: '科室', dataIndex: 'department', key: 'department', width: 100 },
    { title: '角色', dataIndex: 'roles', key: 'roles', width: 150 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 80 },
    { title: '最后登录', dataIndex: 'lastLogin', key: 'lastLogin', width: 150 },
    { title: '操作', key: 'action', width: 200, fixed: 'right' }
];
const logColumns = [
    { title: '用户', dataIndex: 'username', key: 'username', width: 120 },
    { title: '操作类型', dataIndex: 'type', key: 'type', width: 100 },
    { title: '操作描述', dataIndex: 'description', key: 'description', width: 200 },
    { title: '结果', dataIndex: 'result', key: 'result', width: 80 },
    { title: 'IP地址', dataIndex: 'ip', key: 'ip', width: 120 },
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', width: 150 }
];
// 工具函数
const getRoleText = (role) => {
    const roleMap = {
        admin: '系统管理员',
        qc_manager: '质控管理员',
        doctor: '医生',
        nurse: '护士'
    };
    return roleMap[role] || role;
};
const getPermissionText = (permission) => {
    const permissionMap = {
        'user.view': '查看用户',
        'user.edit': '编辑用户',
        'record.view': '查看病历',
        'record.edit': '编辑病历'
    };
    return permissionMap[permission] || permission;
};
const getPermissionTypeColor = (type) => {
    const colorMap = {
        module: 'blue',
        action: 'green',
        resource: 'orange'
    };
    return colorMap[type] || 'default';
};
const getPermissionTypeText = (type) => {
    const textMap = {
        module: '模块',
        action: '操作',
        resource: '资源'
    };
    return textMap[type] || type;
};
const getLogTypeColor = (type) => {
    const colorMap = {
        login: 'green',
        logout: 'blue',
        view: 'cyan',
        edit: 'orange',
        delete: 'red'
    };
    return colorMap[type] || 'default';
};
const getLogTypeText = (type) => {
    const textMap = {
        login: '登录',
        logout: '登出',
        view: '查看',
        edit: '编辑',
        delete: '删除'
    };
    return textMap[type] || type;
};
// 事件处理函数
const handleAddUser = () => {
    ant_design_vue_1.message.info('添加用户');
};
const handleUserSearch = () => {
    fetchUsers();
};
const handleEditUser = (record) => {
    ant_design_vue_1.message.info(`编辑用户: ${record.name}`);
};
const handleUserPermissions = (record) => {
    ant_design_vue_1.message.info(`设置用户权限: ${record.name}`);
};
const handleToggleUserStatus = (record) => {
    const action = record.status === 'active' ? '禁用' : '启用';
    ant_design_vue_1.message.info(`${action}用户: ${record.name}`);
};
const handleUserTableChange = (pag) => {
    userPagination.value = { ...userPagination.value, ...pag };
    fetchUsers();
};
const handleAddRole = () => {
    ant_design_vue_1.message.info('添加角色');
};
const handleEditRole = (role) => {
    ant_design_vue_1.message.info(`编辑角色: ${role.name}`);
};
const handleRolePermissions = (role) => {
    ant_design_vue_1.message.info(`设置角色权限: ${role.name}`);
};
const handleDeleteRole = (role) => {
    ant_design_vue_1.message.info(`删除角色: ${role.name}`);
};
const handleAddPermission = () => {
    ant_design_vue_1.message.info('添加权限');
};
const handleEditPermission = (key) => {
    ant_design_vue_1.message.info(`编辑权限: ${key}`);
};
const handleLogSearch = () => {
    fetchLogs();
};
const handleExportLogs = () => {
    ant_design_vue_1.message.info('导出日志');
};
const handleLogTableChange = (pag) => {
    logPagination.value = { ...logPagination.value, ...pag };
    fetchLogs();
};
// 数据获取函数
const fetchUsers = async () => {
    loading.value = true;
    try {
        await new Promise(resolve => setTimeout(resolve, 1000));
        users.value = [
            {
                id: 1,
                username: 'zhangsan',
                name: '张三',
                department: '内科',
                roles: ['doctor'],
                status: 'active',
                lastLogin: '2024-01-16 10:30:00'
            },
            {
                id: 2,
                username: 'lisi',
                name: '李四',
                department: '外科',
                roles: ['qc_manager'],
                status: 'active',
                lastLogin: '2024-01-16 09:15:00'
            }
        ];
        userPagination.value.total = 50;
    }
    catch (error) {
        ant_design_vue_1.message.error('获取用户数据失败');
    }
    finally {
        loading.value = false;
    }
};
const fetchRoles = async () => {
    try {
        roles.value = [
            {
                id: 1,
                name: '系统管理员',
                description: '拥有系统所有权限',
                userCount: 5,
                permissions: ['user.view', 'user.edit', 'record.view', 'record.edit']
            },
            {
                id: 2,
                name: '质控管理员',
                description: '负责质控相关功能',
                userCount: 12,
                permissions: ['record.view', 'record.edit']
            }
        ];
    }
    catch (error) {
        ant_design_vue_1.message.error('获取角色数据失败');
    }
};
const fetchPermissions = async () => {
    try {
        permissionTree.value = [
            {
                title: '用户管理',
                key: 'user',
                type: 'module',
                children: [
                    { title: '查看用户', key: 'user.view', type: 'action' },
                    { title: '编辑用户', key: 'user.edit', type: 'action' }
                ]
            },
            {
                title: '病历管理',
                key: 'record',
                type: 'module',
                children: [
                    { title: '查看病历', key: 'record.view', type: 'action' },
                    { title: '编辑病历', key: 'record.edit', type: 'action' }
                ]
            }
        ];
    }
    catch (error) {
        ant_design_vue_1.message.error('获取权限数据失败');
    }
};
const fetchLogs = async () => {
    logLoading.value = true;
    try {
        await new Promise(resolve => setTimeout(resolve, 1000));
        logs.value = [
            {
                id: 1,
                username: '张三',
                type: 'login',
                description: '用户登录系统',
                result: 'success',
                ip: '192.168.1.100',
                timestamp: '2024-01-16 10:30:00'
            },
            {
                id: 2,
                username: '李四',
                type: 'view',
                description: '查看病历 R2024001',
                result: 'success',
                ip: '192.168.1.101',
                timestamp: '2024-01-16 10:25:00'
            }
        ];
        logPagination.value.total = 200;
    }
    catch (error) {
        ant_design_vue_1.message.error('获取日志数据失败');
    }
    finally {
        logLoading.value = false;
    }
};
(0, vue_1.onMounted)(() => {
    fetchUsers();
    fetchRoles();
    fetchPermissions();
    fetchLogs();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "permissions-container p-8 bg-gray-50 min-h-screen" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-3xl font-bold text-gray-800 mb-2" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-4 gap-6 mb-8" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center" },
});
const __VLS_0 = {}.UserOutlined;
/** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-blue-600 text-xl" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-blue-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center" },
});
const __VLS_4 = {}.TeamOutlined;
/** @type {[typeof __VLS_components.TeamOutlined, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "text-green-600 text-xl" },
}));
const __VLS_6 = __VLS_5({
    ...{ class: "text-green-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-purple-100 rounded-xl flex items-center justify-center" },
});
const __VLS_8 = {}.SafetyCertificateOutlined;
/** @type {[typeof __VLS_components.SafetyCertificateOutlined, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    ...{ class: "text-purple-600 text-xl" },
}));
const __VLS_10 = __VLS_9({
    ...{ class: "text-purple-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-gray-600 text-sm mb-1" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-3xl font-bold text-gray-800" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-12 h-12 bg-orange-100 rounded-xl flex items-center justify-center" },
});
const __VLS_12 = {}.CheckCircleOutlined;
/** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ class: "text-orange-600 text-xl" },
}));
const __VLS_14 = __VLS_13({
    ...{ class: "text-orange-600 text-xl" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "bg-white rounded-2xl shadow-lg border border-gray-100 p-6" },
});
const __VLS_16 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
    ...{ class: "custom-tabs" },
}));
const __VLS_18 = __VLS_17({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
    ...{ class: "custom-tabs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
const __VLS_20 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    key: "users",
    tab: "用户权限",
}));
const __VLS_22 = __VLS_21({
    key: "users",
    tab: "用户权限",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-gray-800" },
});
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.handleAddUser)
};
__VLS_27.slots.default;
const __VLS_32 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
var __VLS_27;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-4 gap-4 mb-6" },
});
const __VLS_36 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: (__VLS_ctx.userSearch),
    placeholder: "搜索用户名、姓名",
    ...{ class: "rounded-lg" },
}));
const __VLS_38 = __VLS_37({
    value: (__VLS_ctx.userSearch),
    placeholder: "搜索用户名、姓名",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_39.slots;
    const __VLS_40 = {}.SearchOutlined;
    /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        ...{ class: "text-gray-400" },
    }));
    const __VLS_42 = __VLS_41({
        ...{ class: "text-gray-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
}
var __VLS_39;
const __VLS_44 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    value: (__VLS_ctx.selectedRole),
    placeholder: "选择角色",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.roleOptions),
}));
const __VLS_46 = __VLS_45({
    value: (__VLS_ctx.selectedRole),
    placeholder: "选择角色",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.roleOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
const __VLS_48 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "选择科室",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.departmentOptions),
}));
const __VLS_50 = __VLS_49({
    value: (__VLS_ctx.selectedDepartment),
    placeholder: "选择科室",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.departmentOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
const __VLS_52 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}));
const __VLS_54 = __VLS_53({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
let __VLS_56;
let __VLS_57;
let __VLS_58;
const __VLS_59 = {
    onClick: (__VLS_ctx.handleUserSearch)
};
__VLS_55.slots.default;
const __VLS_60 = {}.SearchOutlined;
/** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({}));
const __VLS_62 = __VLS_61({}, ...__VLS_functionalComponentArgsRest(__VLS_61));
var __VLS_55;
const __VLS_64 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.userColumns),
    dataSource: (__VLS_ctx.users),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.userPagination),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}));
const __VLS_66 = __VLS_65({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.userColumns),
    dataSource: (__VLS_ctx.users),
    loading: (__VLS_ctx.loading),
    pagination: (__VLS_ctx.userPagination),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
let __VLS_68;
let __VLS_69;
let __VLS_70;
const __VLS_71 = {
    onChange: (__VLS_ctx.handleUserTableChange)
};
__VLS_67.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_67.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'status') {
        const __VLS_72 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            color: (record.status === 'active' ? 'green' : 'red'),
        }));
        const __VLS_74 = __VLS_73({
            color: (record.status === 'active' ? 'green' : 'red'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        __VLS_75.slots.default;
        (record.status === 'active' ? '活跃' : '禁用');
        var __VLS_75;
    }
    if (column.key === 'roles') {
        for (const [role] of __VLS_getVForSourceType((record.roles))) {
            const __VLS_76 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
                key: (role),
                color: "blue",
                ...{ class: "mb-1" },
            }));
            const __VLS_78 = __VLS_77({
                key: (role),
                color: "blue",
                ...{ class: "mb-1" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_77));
            __VLS_79.slots.default;
            (__VLS_ctx.getRoleText(role));
            var __VLS_79;
        }
    }
    if (column.key === 'action') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex space-x-2" },
        });
        const __VLS_80 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_82 = __VLS_81({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_81));
        let __VLS_84;
        let __VLS_85;
        let __VLS_86;
        const __VLS_87 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleEditUser(record);
            }
        };
        __VLS_83.slots.default;
        const __VLS_88 = {}.EditOutlined;
        /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
        const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
        var __VLS_83;
        const __VLS_92 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }));
        const __VLS_94 = __VLS_93({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        let __VLS_96;
        let __VLS_97;
        let __VLS_98;
        const __VLS_99 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleUserPermissions(record);
            }
        };
        __VLS_95.slots.default;
        const __VLS_100 = {}.SafetyCertificateOutlined;
        /** @type {[typeof __VLS_components.SafetyCertificateOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({}));
        const __VLS_102 = __VLS_101({}, ...__VLS_functionalComponentArgsRest(__VLS_101));
        var __VLS_95;
        const __VLS_104 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            danger: (record.status === 'active'),
        }));
        const __VLS_106 = __VLS_105({
            ...{ 'onClick': {} },
            type: "link",
            size: "small",
            danger: (record.status === 'active'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_105));
        let __VLS_108;
        let __VLS_109;
        let __VLS_110;
        const __VLS_111 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'action'))
                    return;
                __VLS_ctx.handleToggleUserStatus(record);
            }
        };
        __VLS_107.slots.default;
        (record.status === 'active' ? '禁用' : '启用');
        var __VLS_107;
    }
}
var __VLS_67;
var __VLS_23;
const __VLS_112 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    key: "roles",
    tab: "角色权限",
}));
const __VLS_114 = __VLS_113({
    key: "roles",
    tab: "角色权限",
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-gray-800" },
});
const __VLS_116 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}));
const __VLS_118 = __VLS_117({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
let __VLS_120;
let __VLS_121;
let __VLS_122;
const __VLS_123 = {
    onClick: (__VLS_ctx.handleAddRole)
};
__VLS_119.slots.default;
const __VLS_124 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
var __VLS_119;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" },
});
for (const [role] of __VLS_getVForSourceType((__VLS_ctx.roles))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (role.id),
        ...{ class: "bg-gray-50 rounded-xl border border-gray-200 p-6 hover:shadow-md transition-shadow duration-300" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3" },
    });
    const __VLS_128 = {}.TeamOutlined;
    /** @type {[typeof __VLS_components.TeamOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        ...{ class: "text-blue-600" },
    }));
    const __VLS_130 = __VLS_129({
        ...{ class: "text-blue-600" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "font-semibold text-gray-800" },
    });
    (role.name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-600" },
    });
    (role.description);
    const __VLS_132 = {}.ADropdown;
    /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({}));
    const __VLS_134 = __VLS_133({}, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    const __VLS_136 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        type: "text",
        size: "small",
    }));
    const __VLS_138 = __VLS_137({
        type: "text",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    const __VLS_140 = {}.MoreOutlined;
    /** @type {[typeof __VLS_components.MoreOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({}));
    const __VLS_142 = __VLS_141({}, ...__VLS_functionalComponentArgsRest(__VLS_141));
    var __VLS_139;
    {
        const { overlay: __VLS_thisSlot } = __VLS_135.slots;
        const __VLS_144 = {}.AMenu;
        /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({}));
        const __VLS_146 = __VLS_145({}, ...__VLS_functionalComponentArgsRest(__VLS_145));
        __VLS_147.slots.default;
        const __VLS_148 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
            ...{ 'onClick': {} },
        }));
        const __VLS_150 = __VLS_149({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_149));
        let __VLS_152;
        let __VLS_153;
        let __VLS_154;
        const __VLS_155 = {
            onClick: (...[$event]) => {
                __VLS_ctx.handleEditRole(role);
            }
        };
        __VLS_151.slots.default;
        const __VLS_156 = {}.EditOutlined;
        /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({}));
        const __VLS_158 = __VLS_157({}, ...__VLS_functionalComponentArgsRest(__VLS_157));
        var __VLS_151;
        const __VLS_160 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
            ...{ 'onClick': {} },
        }));
        const __VLS_162 = __VLS_161({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_161));
        let __VLS_164;
        let __VLS_165;
        let __VLS_166;
        const __VLS_167 = {
            onClick: (...[$event]) => {
                __VLS_ctx.handleRolePermissions(role);
            }
        };
        __VLS_163.slots.default;
        const __VLS_168 = {}.SafetyCertificateOutlined;
        /** @type {[typeof __VLS_components.SafetyCertificateOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({}));
        const __VLS_170 = __VLS_169({}, ...__VLS_functionalComponentArgsRest(__VLS_169));
        var __VLS_163;
        const __VLS_172 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
            ...{ 'onClick': {} },
            danger: true,
        }));
        const __VLS_174 = __VLS_173({
            ...{ 'onClick': {} },
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_173));
        let __VLS_176;
        let __VLS_177;
        let __VLS_178;
        const __VLS_179 = {
            onClick: (...[$event]) => {
                __VLS_ctx.handleDeleteRole(role);
            }
        };
        __VLS_175.slots.default;
        const __VLS_180 = {}.DeleteOutlined;
        /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({}));
        const __VLS_182 = __VLS_181({}, ...__VLS_functionalComponentArgsRest(__VLS_181));
        var __VLS_175;
        var __VLS_147;
    }
    var __VLS_135;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-600 mb-2" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "font-medium" },
    });
    (role.userCount);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-sm text-gray-600" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "font-medium" },
    });
    (role.permissions?.length || 0);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex flex-wrap gap-1" },
    });
    for (const [permission] of __VLS_getVForSourceType((role.permissions?.slice(0, 3)))) {
        const __VLS_184 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
            key: (permission),
            size: "small",
        }));
        const __VLS_186 = __VLS_185({
            key: (permission),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
        __VLS_187.slots.default;
        (__VLS_ctx.getPermissionText(permission));
        var __VLS_187;
    }
    if (role.permissions?.length > 3) {
        const __VLS_188 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
            size: "small",
        }));
        const __VLS_190 = __VLS_189({
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_189));
        __VLS_191.slots.default;
        (role.permissions.length - 3);
        var __VLS_191;
    }
}
var __VLS_115;
const __VLS_192 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
    key: "permissions",
    tab: "权限规则",
}));
const __VLS_194 = __VLS_193({
    key: "permissions",
    tab: "权限规则",
}, ...__VLS_functionalComponentArgsRest(__VLS_193));
__VLS_195.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex justify-between items-center mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-gray-800" },
});
const __VLS_196 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}));
const __VLS_198 = __VLS_197({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_197));
let __VLS_200;
let __VLS_201;
let __VLS_202;
const __VLS_203 = {
    onClick: (__VLS_ctx.handleAddPermission)
};
__VLS_199.slots.default;
const __VLS_204 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({}));
const __VLS_206 = __VLS_205({}, ...__VLS_functionalComponentArgsRest(__VLS_205));
var __VLS_199;
const __VLS_208 = {}.ATree;
/** @type {[typeof __VLS_components.ATree, typeof __VLS_components.aTree, typeof __VLS_components.ATree, typeof __VLS_components.aTree, ]} */ ;
// @ts-ignore
const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
    checkedKeys: (__VLS_ctx.checkedPermissions),
    treeData: (__VLS_ctx.permissionTree),
    checkable: true,
    defaultExpandAll: (true),
    ...{ class: "bg-gray-50 p-4 rounded-lg" },
}));
const __VLS_210 = __VLS_209({
    checkedKeys: (__VLS_ctx.checkedPermissions),
    treeData: (__VLS_ctx.permissionTree),
    checkable: true,
    defaultExpandAll: (true),
    ...{ class: "bg-gray-50 p-4 rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_209));
__VLS_211.slots.default;
{
    const { title: __VLS_thisSlot } = __VLS_211.slots;
    const [{ title, key, type }] = __VLS_getSlotParams(__VLS_thisSlot);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-between" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex space-x-2" },
    });
    const __VLS_212 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
        color: (__VLS_ctx.getPermissionTypeColor(type)),
        size: "small",
    }));
    const __VLS_214 = __VLS_213({
        color: (__VLS_ctx.getPermissionTypeColor(type)),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_213));
    __VLS_215.slots.default;
    (__VLS_ctx.getPermissionTypeText(type));
    var __VLS_215;
    const __VLS_216 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
        ...{ 'onClick': {} },
        type: "text",
        size: "small",
    }));
    const __VLS_218 = __VLS_217({
        ...{ 'onClick': {} },
        type: "text",
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_217));
    let __VLS_220;
    let __VLS_221;
    let __VLS_222;
    const __VLS_223 = {
        onClick: (...[$event]) => {
            __VLS_ctx.handleEditPermission(key);
        }
    };
    __VLS_219.slots.default;
    const __VLS_224 = {}.EditOutlined;
    /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({}));
    const __VLS_226 = __VLS_225({}, ...__VLS_functionalComponentArgsRest(__VLS_225));
    var __VLS_219;
}
var __VLS_211;
var __VLS_195;
const __VLS_228 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({
    key: "logs",
    tab: "访问日志",
}));
const __VLS_230 = __VLS_229({
    key: "logs",
    tab: "访问日志",
}, ...__VLS_functionalComponentArgsRest(__VLS_229));
__VLS_231.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "mb-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ class: "text-lg font-semibold text-gray-800 mb-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "grid grid-cols-1 md:grid-cols-5 gap-4 mb-6" },
});
const __VLS_232 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
    value: (__VLS_ctx.logSearch),
    placeholder: "搜索用户、操作",
    ...{ class: "rounded-lg" },
}));
const __VLS_234 = __VLS_233({
    value: (__VLS_ctx.logSearch),
    placeholder: "搜索用户、操作",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_233));
__VLS_235.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_235.slots;
    const __VLS_236 = {}.SearchOutlined;
    /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
        ...{ class: "text-gray-400" },
    }));
    const __VLS_238 = __VLS_237({
        ...{ class: "text-gray-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_237));
}
var __VLS_235;
const __VLS_240 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
    value: (__VLS_ctx.selectedLogType),
    placeholder: "操作类型",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.logTypeOptions),
}));
const __VLS_242 = __VLS_241({
    value: (__VLS_ctx.selectedLogType),
    placeholder: "操作类型",
    ...{ class: "rounded-lg" },
    options: (__VLS_ctx.logTypeOptions),
}, ...__VLS_functionalComponentArgsRest(__VLS_241));
const __VLS_244 = {}.ARangePicker;
/** @type {[typeof __VLS_components.ARangePicker, typeof __VLS_components.aRangePicker, ]} */ ;
// @ts-ignore
const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
    value: (__VLS_ctx.logDateRange),
    placeholder: "选择日期范围",
    ...{ class: "rounded-lg" },
}));
const __VLS_246 = __VLS_245({
    value: (__VLS_ctx.logDateRange),
    placeholder: "选择日期范围",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_245));
const __VLS_248 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}));
const __VLS_250 = __VLS_249({
    ...{ 'onClick': {} },
    type: "primary",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_249));
let __VLS_252;
let __VLS_253;
let __VLS_254;
const __VLS_255 = {
    onClick: (__VLS_ctx.handleLogSearch)
};
__VLS_251.slots.default;
const __VLS_256 = {}.SearchOutlined;
/** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
// @ts-ignore
const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({}));
const __VLS_258 = __VLS_257({}, ...__VLS_functionalComponentArgsRest(__VLS_257));
var __VLS_251;
const __VLS_260 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}));
const __VLS_262 = __VLS_261({
    ...{ 'onClick': {} },
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_261));
let __VLS_264;
let __VLS_265;
let __VLS_266;
const __VLS_267 = {
    onClick: (__VLS_ctx.handleExportLogs)
};
__VLS_263.slots.default;
const __VLS_268 = {}.DownloadOutlined;
/** @type {[typeof __VLS_components.DownloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({}));
const __VLS_270 = __VLS_269({}, ...__VLS_functionalComponentArgsRest(__VLS_269));
var __VLS_263;
const __VLS_272 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.logColumns),
    dataSource: (__VLS_ctx.logs),
    loading: (__VLS_ctx.logLoading),
    pagination: (__VLS_ctx.logPagination),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}));
const __VLS_274 = __VLS_273({
    ...{ 'onChange': {} },
    columns: (__VLS_ctx.logColumns),
    dataSource: (__VLS_ctx.logs),
    loading: (__VLS_ctx.logLoading),
    pagination: (__VLS_ctx.logPagination),
    rowKey: "id",
    ...{ class: "rounded-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_273));
let __VLS_276;
let __VLS_277;
let __VLS_278;
const __VLS_279 = {
    onChange: (__VLS_ctx.handleLogTableChange)
};
__VLS_275.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_275.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'type') {
        const __VLS_280 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
            color: (__VLS_ctx.getLogTypeColor(record.type)),
        }));
        const __VLS_282 = __VLS_281({
            color: (__VLS_ctx.getLogTypeColor(record.type)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_281));
        __VLS_283.slots.default;
        (__VLS_ctx.getLogTypeText(record.type));
        var __VLS_283;
    }
    if (column.key === 'result') {
        const __VLS_284 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
            color: (record.result === 'success' ? 'green' : 'red'),
        }));
        const __VLS_286 = __VLS_285({
            color: (record.result === 'success' ? 'green' : 'red'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_285));
        __VLS_287.slots.default;
        (record.result === 'success' ? '成功' : '失败');
        var __VLS_287;
    }
}
var __VLS_275;
var __VLS_231;
var __VLS_19;
/** @type {__VLS_StyleScopedClasses['permissions-container']} */ ;
/** @type {__VLS_StyleScopedClasses['p-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-green-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-green-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-purple-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-purple-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-3xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-bold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['w-12']} */ ;
/** @type {__VLS_StyleScopedClasses['h-12']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-orange-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['text-orange-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['custom-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-4']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-1']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:grid-cols-3']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-6']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-10']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['md:grid-cols-5']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            UserOutlined: icons_vue_1.UserOutlined,
            TeamOutlined: icons_vue_1.TeamOutlined,
            SafetyCertificateOutlined: icons_vue_1.SafetyCertificateOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            SearchOutlined: icons_vue_1.SearchOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            MoreOutlined: icons_vue_1.MoreOutlined,
            DownloadOutlined: icons_vue_1.DownloadOutlined,
            activeTab: activeTab,
            loading: loading,
            logLoading: logLoading,
            userSearch: userSearch,
            selectedRole: selectedRole,
            selectedDepartment: selectedDepartment,
            users: users,
            userPagination: userPagination,
            roles: roles,
            checkedPermissions: checkedPermissions,
            permissionTree: permissionTree,
            logSearch: logSearch,
            selectedLogType: selectedLogType,
            logDateRange: logDateRange,
            logs: logs,
            logPagination: logPagination,
            roleOptions: roleOptions,
            departmentOptions: departmentOptions,
            logTypeOptions: logTypeOptions,
            userColumns: userColumns,
            logColumns: logColumns,
            getRoleText: getRoleText,
            getPermissionText: getPermissionText,
            getPermissionTypeColor: getPermissionTypeColor,
            getPermissionTypeText: getPermissionTypeText,
            getLogTypeColor: getLogTypeColor,
            getLogTypeText: getLogTypeText,
            handleAddUser: handleAddUser,
            handleUserSearch: handleUserSearch,
            handleEditUser: handleEditUser,
            handleUserPermissions: handleUserPermissions,
            handleToggleUserStatus: handleToggleUserStatus,
            handleUserTableChange: handleUserTableChange,
            handleAddRole: handleAddRole,
            handleEditRole: handleEditRole,
            handleRolePermissions: handleRolePermissions,
            handleDeleteRole: handleDeleteRole,
            handleAddPermission: handleAddPermission,
            handleEditPermission: handleEditPermission,
            handleLogSearch: handleLogSearch,
            handleExportLogs: handleExportLogs,
            handleLogTableChange: handleLogTableChange,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
