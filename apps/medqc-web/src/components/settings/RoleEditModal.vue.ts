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
    role: null
});
const emit = defineEmits();
// 加载状态
const loading = (0, vue_1.ref)(false);
// 资源权限配置
const resources = (0, vue_1.ref)([
    {
        key: 'medical_records',
        name: '病案记录',
        description: '医疗病案的管理和操作',
        icon: icons_vue_1.FileTextOutlined,
        color: 'text-blue-500',
        enabled: true,
        actions: [
            { key: 'create', name: '创建', description: '创建新的病案记录', icon: icons_vue_1.PlusOutlined, enabled: true },
            { key: 'read', name: '查看', description: '查看病案记录详情', icon: icons_vue_1.EyeOutlined, enabled: true },
            { key: 'update', name: '修改', description: '修改病案记录信息', icon: icons_vue_1.EditOutlined, enabled: true },
            { key: 'delete', name: '删除', description: '删除病案记录', icon: icons_vue_1.DeleteOutlined, enabled: false },
            { key: 'export', name: '导出', description: '导出病案记录数据', icon: icons_vue_1.DownloadOutlined, enabled: true }
        ]
    },
    {
        key: 'qc_results',
        name: '质控结果',
        description: '质控分析结果的管理',
        icon: icons_vue_1.CheckCircleOutlined,
        color: 'text-green-500',
        enabled: true,
        actions: [
            { key: 'read', name: '查看', description: '查看质控结果', icon: icons_vue_1.EyeOutlined, enabled: true },
            { key: 'update', name: '修改', description: '修改质控结果', icon: icons_vue_1.EditOutlined, enabled: true },
            { key: 'review', name: '审核', description: '审核质控结果', icon: icons_vue_1.AuditOutlined, enabled: true },
            { key: 'export', name: '导出', description: '导出质控结果', icon: icons_vue_1.DownloadOutlined, enabled: true }
        ]
    },
    {
        key: 'qc_rules',
        name: '质控规则',
        description: '质控规则的配置和管理',
        icon: icons_vue_1.SettingOutlined,
        color: 'text-purple-500',
        enabled: true,
        actions: [
            { key: 'create', name: '创建', description: '创建质控规则', icon: icons_vue_1.PlusOutlined, enabled: true },
            { key: 'read', name: '查看', description: '查看质控规则', icon: icons_vue_1.EyeOutlined, enabled: true },
            { key: 'update', name: '修改', description: '修改质控规则', icon: icons_vue_1.EditOutlined, enabled: true },
            { key: 'delete', name: '删除', description: '删除质控规则', icon: icons_vue_1.DeleteOutlined, enabled: true },
            { key: 'manage', name: '管理', description: '管理质控规则', icon: icons_vue_1.ToolOutlined, enabled: true }
        ]
    },
    {
        key: 'users',
        name: '用户管理',
        description: '系统用户的管理',
        icon: icons_vue_1.UserOutlined,
        color: 'text-orange-500',
        enabled: false,
        actions: [
            { key: 'create', name: '创建', description: '创建新用户', icon: icons_vue_1.PlusOutlined, enabled: false },
            { key: 'read', name: '查看', description: '查看用户信息', icon: icons_vue_1.EyeOutlined, enabled: false },
            { key: 'update', name: '修改', description: '修改用户信息', icon: icons_vue_1.EditOutlined, enabled: false },
            { key: 'delete', name: '删除', description: '删除用户', icon: icons_vue_1.DeleteOutlined, enabled: false },
            { key: 'manage', name: '管理', description: '管理用户权限', icon: icons_vue_1.ToolOutlined, enabled: false }
        ]
    },
    {
        key: 'statistics',
        name: '统计报表',
        description: '系统统计数据和报表',
        icon: icons_vue_1.BarChartOutlined,
        color: 'text-indigo-500',
        enabled: true,
        actions: [
            { key: 'read', name: '查看', description: '查看统计数据', icon: icons_vue_1.EyeOutlined, enabled: true },
            { key: 'export', name: '导出', description: '导出统计报表', icon: icons_vue_1.DownloadOutlined, enabled: true }
        ]
    },
    {
        key: 'settings',
        name: '系统设置',
        description: '系统配置和设置',
        icon: icons_vue_1.SafetyCertificateOutlined,
        color: 'text-red-500',
        enabled: false,
        actions: [
            { key: 'read', name: '查看', description: '查看系统设置', icon: icons_vue_1.EyeOutlined, enabled: false },
            { key: 'update', name: '修改', description: '修改系统设置', icon: icons_vue_1.EditOutlined, enabled: false },
            { key: 'manage', name: '管理', description: '管理系统配置', icon: icons_vue_1.ToolOutlined, enabled: false }
        ]
    }
]);
// 角色用户列表
const roleUsers = (0, vue_1.ref)([
    {
        id: '1',
        email: 'admin@demo.com',
        display_name: '系统管理员',
        department: '信息科',
        is_active: true
    },
    {
        id: '2',
        email: 'qc@demo.com',
        display_name: '质控管理员',
        department: '质控科',
        is_active: true
    }
]);
// 监听角色变化
(0, vue_1.watch)(() => props.role, (newRole: any) => {
    if (newRole) {
        // 根据角色类型设置权限
        updatePermissionsByRole(newRole.key);
    }
}, { immediate: true });
// 方法
const updatePermissionsByRole = (roleKey) => {
    // 根据角色设置默认权限
    const rolePermissions = {
        admin: {
            medical_records: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'export'] },
            qc_results: { enabled: true, actions: ['read', 'update', 'review', 'export'] },
            qc_rules: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'manage'] },
            users: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'manage'] },
            statistics: { enabled: true, actions: ['read', 'export'] },
            settings: { enabled: true, actions: ['read', 'update', 'manage'] }
        },
        qc_manager: {
            medical_records: { enabled: true, actions: ['read', 'export'] },
            qc_results: { enabled: true, actions: ['read', 'update', 'review', 'export'] },
            qc_rules: { enabled: true, actions: ['create', 'read', 'update', 'delete', 'manage'] },
            users: { enabled: true, actions: ['read'] },
            statistics: { enabled: true, actions: ['read', 'export'] },
            settings: { enabled: false, actions: [] }
        },
        qc_staff: {
            medical_records: { enabled: true, actions: ['read'] },
            qc_results: { enabled: true, actions: ['read', 'update', 'review'] },
            qc_rules: { enabled: true, actions: ['read'] },
            users: { enabled: false, actions: [] },
            statistics: { enabled: true, actions: ['read'] },
            settings: { enabled: false, actions: [] }
        },
        doctor: {
            medical_records: { enabled: true, actions: ['create', 'read', 'update'] },
            qc_results: { enabled: true, actions: ['read'] },
            qc_rules: { enabled: false, actions: [] },
            users: { enabled: false, actions: [] },
            statistics: { enabled: true, actions: ['read'] },
            settings: { enabled: false, actions: [] }
        }
    };
    const permissions = rolePermissions[roleKey];
    if (permissions) {
        resources.value.forEach(resource => {
            const resourcePermission = permissions[resource.key];
            if (resourcePermission) {
                resource.enabled = resourcePermission.enabled;
                resource.actions.forEach(action => {
                    action.enabled = resourcePermission.actions.includes(action.key);
                });
            }
        });
    }
};
const handleResourceToggle = (resourceKey, enabled) => {
    const resource = resources.value.find(r => r.key === resourceKey);
    if (resource) {
        resource.enabled = enabled;
        if (!enabled) {
            // 如果禁用资源，则禁用所有操作
            resource.actions.forEach(action => {
                action.enabled = false;
            });
        }
    }
};
const handleActionToggle = (resourceKey, actionKey: any,  enabled: any) => {
    const resource = resources.value.find(r => r.key === resourceKey);
    if (resource) {
        const action = resource.actions.find(a => a.key === actionKey);
        if (action) {
            action.enabled = enabled;
        }
    }
};
const handleSubmit = async () => {
    try {
        loading.value = true;
        // 收集权限配置
        const permissions = resources.value.map(resource => ({
            resource: resource.key,
            enabled: resource.enabled,
            actions: resource.actions.filter(action => action.enabled).map(action => action.key)
        }));
        emit('submit', {
            role: props.role?.key,
            permissions
        });
    }
    catch (error) {
        ant_design_vue_1.message.error('保存失败');
    }
    finally {
        loading.value = false;
    }
};
const handleCancel = () => {
    emit('cancel');
};
const getUserAvatarColor = (email) => {
    const colors = ['#f56a00', '#7265e6', '#ffbf00', '#00a2ae', '#f56a00'];
    const index = email.charCodeAt(0) % colors.length;
    return colors[index];
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    visible: false,
    role: null
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['permission-group']} */ ;
// CSS variable injection 
// CSS variable injection end 
const __VLS_0 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.visible),
    title: "角色权限配置",
    width: (800),
    confirmLoading: (__VLS_ctx.loading),
}));
const __VLS_2 = __VLS_1({
    ...{ 'onOk': {} },
    ...{ 'onCancel': {} },
    open: (__VLS_ctx.visible),
    title: "角色权限配置",
    width: (800),
    confirmLoading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onOk: (__VLS_ctx.handleSubmit)
};
const __VLS_8 = {
    onCancel: (__VLS_ctx.handleCancel)
};
var __VLS_9 = {};
__VLS_3.slots.default;
if (__VLS_ctx.role) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "role-edit-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center space-x-4 mb-4" },
    });
    const __VLS_10 = ((__VLS_ctx.role.icon));
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
        ...{ class: (['text-4xl', __VLS_ctx.role.color]) },
    }));
    const __VLS_12 = __VLS_11({
        ...{ class: (['text-4xl', __VLS_ctx.role.color]) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ class: "text-xl font-semibold" },
    });
    (__VLS_ctx.role.name);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "text-gray-600" },
    });
    (__VLS_ctx.role.description);
    const __VLS_14 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
        gutter: (16),
    }));
    const __VLS_16 = __VLS_15({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    __VLS_17.slots.default;
    const __VLS_18 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
        span: (12),
    }));
    const __VLS_20 = __VLS_19({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_19));
    __VLS_21.slots.default;
    const __VLS_22 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_23 = __VLS_asFunctionalComponent(__VLS_22, new __VLS_22({
        title: "当前用户数",
        value: (__VLS_ctx.role.userCount),
        suffix: "人",
    }));
    const __VLS_24 = __VLS_23({
        title: "当前用户数",
        value: (__VLS_ctx.role.userCount),
        suffix: "人",
    }, ...__VLS_functionalComponentArgsRest(__VLS_23));
    var __VLS_21;
    const __VLS_26 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_27 = __VLS_asFunctionalComponent(__VLS_26, new __VLS_26({
        span: (12),
    }));
    const __VLS_28 = __VLS_27({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_27));
    __VLS_29.slots.default;
    const __VLS_30 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_31 = __VLS_asFunctionalComponent(__VLS_30, new __VLS_30({
        title: "权限数量",
        value: (__VLS_ctx.role.permissionCount),
        suffix: "项",
    }));
    const __VLS_32 = __VLS_31({
        title: "权限数量",
        value: (__VLS_ctx.role.permissionCount),
        suffix: "项",
    }, ...__VLS_functionalComponentArgsRest(__VLS_31));
    var __VLS_29;
    var __VLS_17;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "permissions-config" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "text-lg font-semibold mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "space-y-4" },
    });
    for (const [resource] of __VLS_getVForSourceType((__VLS_ctx.resources))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (resource.key),
            ...{ class: "permission-group" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center justify-between p-4 bg-gray-50 rounded-lg" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center space-x-3" },
        });
        const __VLS_34 = ((resource.icon));
        // @ts-ignore
        const __VLS_35 = __VLS_asFunctionalComponent(__VLS_34, new __VLS_34({
            ...{ class: (['text-xl', resource.color]) },
        }));
        const __VLS_36 = __VLS_35({
            ...{ class: (['text-xl', resource.color]) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_35));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({
            ...{ class: "font-medium" },
        });
        (resource.name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
            ...{ class: "text-sm text-gray-600" },
        });
        (resource.description);
        const __VLS_38 = {}.ASwitch;
        /** @type {[typeof __VLS_components.ASwitch, typeof __VLS_components.aSwitch, ]} */ ;
        // @ts-ignore
        const __VLS_39 = __VLS_asFunctionalComponent(__VLS_38, new __VLS_38({
            ...{ 'onChange': {} },
            checked: (resource.enabled),
        }));
        const __VLS_40 = __VLS_39({
            ...{ 'onChange': {} },
            checked: (resource.enabled),
        }, ...__VLS_functionalComponentArgsRest(__VLS_39));
        let __VLS_42;
        let __VLS_43;
        let __VLS_44;
        const __VLS_45 = {
            onChange: (...[$event]) => {
                if (!(__VLS_ctx.role))
                    return;
                __VLS_ctx.handleResourceToggle(resource.key, $event);
            }
        };
        var __VLS_41;
        if (resource.enabled) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "ml-8 mt-3 space-y-2" },
            });
            for (const [action] of __VLS_getVForSourceType((resource.actions))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (action.key),
                    ...{ class: "flex items-center justify-between" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "flex items-center space-x-2" },
                });
                const __VLS_46 = ((action.icon));
                // @ts-ignore
                const __VLS_47 = __VLS_asFunctionalComponent(__VLS_46, new __VLS_46({
                    ...{ class: "text-gray-500" },
                }));
                const __VLS_48 = __VLS_47({
                    ...{ class: "text-gray-500" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_47));
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "text-sm" },
                });
                (action.name);
                const __VLS_50 = {}.ATooltip;
                /** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
                // @ts-ignore
                const __VLS_51 = __VLS_asFunctionalComponent(__VLS_50, new __VLS_50({
                    title: (action.description),
                }));
                const __VLS_52 = __VLS_51({
                    title: (action.description),
                }, ...__VLS_functionalComponentArgsRest(__VLS_51));
                __VLS_53.slots.default;
                const __VLS_54 = {}.QuestionCircleOutlined;
                /** @type {[typeof __VLS_components.QuestionCircleOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_55 = __VLS_asFunctionalComponent(__VLS_54, new __VLS_54({
                    ...{ class: "text-gray-400 cursor-help" },
                }));
                const __VLS_56 = __VLS_55({
                    ...{ class: "text-gray-400 cursor-help" },
                }, ...__VLS_functionalComponentArgsRest(__VLS_55));
                var __VLS_53;
                const __VLS_58 = {}.ACheckbox;
                /** @type {[typeof __VLS_components.ACheckbox, typeof __VLS_components.aCheckbox, ]} */ ;
                // @ts-ignore
                const __VLS_59 = __VLS_asFunctionalComponent(__VLS_58, new __VLS_58({
                    ...{ 'onChange': {} },
                    checked: (action.enabled),
                }));
                const __VLS_60 = __VLS_59({
                    ...{ 'onChange': {} },
                    checked: (action.enabled),
                }, ...__VLS_functionalComponentArgsRest(__VLS_59));
                let __VLS_62;
                let __VLS_63;
                let __VLS_64;
                const __VLS_65 = {
                    onChange: (...[$event]) => {
                        if (!(__VLS_ctx.role))
                            return;
                        if (!(resource.enabled))
                            return;
                        __VLS_ctx.handleActionToggle(resource.key, action.key, $event);
                    }
                };
                var __VLS_61;
            }
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-6" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({
        ...{ class: "text-lg font-semibold mb-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "space-y-2 max-h-40 overflow-y-auto" },
    });
    for (const [user] of __VLS_getVForSourceType((__VLS_ctx.roleUsers))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (user.id),
            ...{ class: "flex items-center justify-between p-2 bg-gray-50 rounded" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex items-center space-x-3" },
        });
        const __VLS_66 = {}.AAvatar;
        /** @type {[typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, ]} */ ;
        // @ts-ignore
        const __VLS_67 = __VLS_asFunctionalComponent(__VLS_66, new __VLS_66({
            size: (32),
            ...{ style: ({ backgroundColor: __VLS_ctx.getUserAvatarColor(user.email) }) },
        }));
        const __VLS_68 = __VLS_67({
            size: (32),
            ...{ style: ({ backgroundColor: __VLS_ctx.getUserAvatarColor(user.email) }) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_67));
        __VLS_69.slots.default;
        (user.display_name?.charAt(0) || user.email?.charAt(0));
        var __VLS_69;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "font-medium text-sm" },
        });
        (user.display_name || user.email);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-xs text-gray-500" },
        });
        (user.department || '-');
        const __VLS_70 = {}.ABadge;
        /** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
        // @ts-ignore
        const __VLS_71 = __VLS_asFunctionalComponent(__VLS_70, new __VLS_70({
            status: (user.is_active ? 'success' : 'default'),
            text: (user.is_active ? '激活' : '停用'),
        }));
        const __VLS_72 = __VLS_71({
            status: (user.is_active ? 'success' : 'default'),
            text: (user.is_active ? '激活' : '停用'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_71));
    }
    if (__VLS_ctx.roleUsers.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "text-center py-4 text-gray-500" },
        });
    }
}
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['role-edit-content']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-6']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-4xl']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['permissions-config']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-4']} */ ;
/** @type {__VLS_StyleScopedClasses['permission-group']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-8']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-help']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['space-y-2']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-40']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-3']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            QuestionCircleOutlined: icons_vue_1.QuestionCircleOutlined,
            loading: loading,
            resources: resources,
            roleUsers: roleUsers,
            handleResourceToggle: handleResourceToggle,
            handleActionToggle: handleActionToggle,
            handleSubmit: handleSubmit,
            handleCancel: handleCancel,
            getUserAvatarColor: getUserAvatarColor,
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
