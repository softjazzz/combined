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
import vue_router_1 from 'vue-router';
import auth_1 from '@/stores/auth';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
// 路由和状态管理
const router = (0, vue_router_1.useRouter)();
const route = (0, vue_router_1.useRoute)();
const authStore = (0, auth_1.useAuthStore)();
// 响应式数据
const sidebarOpen = (0, vue_1.ref)(false);
const selectedKeys = (0, vue_1.ref)(: any[]);
const openKeys = (0, vue_1.ref)(: any[]);
const notificationCount = (0, vue_1.ref)(3);
// 计算属性
const currentUser = (0, vue_1.computed)(() => authStore.user);
const isAdmin = (0, vue_1.computed)(() => authStore.user?.role === 'admin');
// 方法
const toggleSidebar = () => {
    sidebarOpen.value = !sidebarOpen.value;
};
const closeSidebar = () => {
    sidebarOpen.value = false;
};
const navigateTo = (path) => {
    router.push(path);
    closeSidebar();
};
const goToProfile = () => {
    router.push('/profile');
};
const goToSettings = () => {
    router.push('/settings');
};
const handleLogout = async () => {
    try {
        await authStore.signOut();
        ant_design_vue_1.message.success('已安全退出');
        router.push('/auth/login');
    }
    catch (error) {
        ant_design_vue_1.message.error('退出失败');
    }
};
// 根据当前路由设置菜单选中状态
const updateMenuState = () => {
    const path = route.path;
    if (path.includes('/dashboard')) {
        selectedKeys.value = ['dashboard'];
        openKeys.value = [];
    }
    else if (path.includes('/audit-tasks')) {
        selectedKeys.value = ['audit-tasks'];
        openKeys.value = ['qc-management'];
    }
    else if (path.includes('/ai-assistance')) {
        selectedKeys.value = ['ai-assistance'];
        openKeys.value = ['qc-management'];
    }
    else if (path.includes('/batch-audit')) {
        selectedKeys.value = ['batch-audit'];
        openKeys.value = ['qc-management'];
    }
    else if (path.includes('/rules/work-rules')) {
        selectedKeys.value = ['work-rules'];
        openKeys.value = ['rules'];
    }
    else if (path.includes('/rules/enhanced-rules')) {
        selectedKeys.value = ['enhanced-rules'];
        openKeys.value = ['rules'];
    }
    else if (path.includes('/department-config')) {
        selectedKeys.value = ['department-config'];
        openKeys.value = ['rules'];
    }
    else if (path.includes('/reports')) {
        selectedKeys.value = ['qc-reports'];
        openKeys.value = ['analytics'];
    }
    else if (path.includes('/statistics')) {
        selectedKeys.value = ['statistics'];
        openKeys.value = ['analytics'];
    }
    else if (path.includes('/admin/users')) {
        selectedKeys.value = ['user-management'];
        openKeys.value = ['system'];
    }
    else if (path.includes('/admin/settings')) {
        selectedKeys.value = ['system-settings'];
        openKeys.value = ['system'];
    }
    else if (path.includes('/admin/logs')) {
        selectedKeys.value = ['logs'];
        openKeys.value = ['system'];
    }
};
// 生命周期
(0, vue_1.onMounted)(() => {
    updateMenuState();
});
// 监听路由变化
(0, vue_1.watch)(route, () => {
    updateMenuState();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['ant-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-menu-item-selected']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-menu-submenu-title']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-menu-submenu-title']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "min-h-screen bg-gray-50" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({
    ...{ class: "bg-white shadow-sm border-b border-gray-200 fixed w-full top-0 z-50" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "px-6 py-4" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.toggleSidebar) },
    ...{ class: "lg:hidden p-2 rounded-lg text-gray-600 hover:bg-gray-100 mr-3" },
});
const __VLS_0 = {}.MenuOutlined;
/** @type {[typeof __VLS_components.MenuOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "text-lg" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center mr-3" },
});
const __VLS_4 = {}.MedicineBoxOutlined;
/** @type {[typeof __VLS_components.MedicineBoxOutlined, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "text-white text-sm" },
}));
const __VLS_6 = __VLS_5({
    ...{ class: "text-white text-sm" },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "text-lg font-semibold text-gray-900" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "text-xs text-gray-500 hidden sm:block" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center space-x-4" },
});
const __VLS_8 = {}.ABadge;
/** @type {[typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, typeof __VLS_components.ABadge, typeof __VLS_components.aBadge, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    count: (__VLS_ctx.notificationCount),
    offset: ([10, 0]),
}));
const __VLS_10 = __VLS_9({
    count: (__VLS_ctx.notificationCount),
    offset: ([10, 0]),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ class: "p-2 text-gray-600 hover:bg-gray-100 rounded-lg" },
});
const __VLS_12 = {}.BellOutlined;
/** @type {[typeof __VLS_components.BellOutlined, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ class: "text-lg" },
}));
const __VLS_14 = __VLS_13({
    ...{ class: "text-lg" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
var __VLS_11;
const __VLS_16 = {}.ADropdown;
/** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    placement: "bottomRight",
}));
const __VLS_18 = __VLS_17({
    placement: "bottomRight",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ class: "flex items-center space-x-2 p-2 text-gray-700 hover:bg-gray-100 rounded-lg" },
});
const __VLS_20 = {}.AAvatar;
/** @type {[typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, typeof __VLS_components.AAvatar, typeof __VLS_components.aAvatar, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    size: (32),
    src: (__VLS_ctx.currentUser?.avatar),
}));
const __VLS_22 = __VLS_21({
    size: (32),
    src: (__VLS_ctx.currentUser?.avatar),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_23.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_23.slots;
    const __VLS_24 = {}.UserOutlined;
    /** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
    const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
}
var __VLS_23;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "hidden sm:block text-left" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-sm font-medium" },
});
(__VLS_ctx.currentUser?.name || '用户');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-xs text-gray-500" },
});
(__VLS_ctx.currentUser?.role || '医务人员');
const __VLS_28 = {}.DownOutlined;
/** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ class: "text-xs text-gray-400" },
}));
const __VLS_30 = __VLS_29({
    ...{ class: "text-xs text-gray-400" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
{
    const { overlay: __VLS_thisSlot } = __VLS_19.slots;
    const __VLS_32 = {}.AMenu;
    /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
    const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_35.slots.default;
    const __VLS_36 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        ...{ 'onClick': {} },
        key: "profile",
    }));
    const __VLS_38 = __VLS_37({
        ...{ 'onClick': {} },
        key: "profile",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    let __VLS_40;
    let __VLS_41;
    let __VLS_42;
    const __VLS_43 = {
        onClick: (__VLS_ctx.goToProfile)
    };
    __VLS_39.slots.default;
    const __VLS_44 = {}.UserOutlined;
    /** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        ...{ class: "mr-2" },
    }));
    const __VLS_46 = __VLS_45({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    var __VLS_39;
    const __VLS_48 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ 'onClick': {} },
        key: "settings",
    }));
    const __VLS_50 = __VLS_49({
        ...{ 'onClick': {} },
        key: "settings",
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    let __VLS_52;
    let __VLS_53;
    let __VLS_54;
    const __VLS_55 = {
        onClick: (__VLS_ctx.goToSettings)
    };
    __VLS_51.slots.default;
    const __VLS_56 = {}.SettingOutlined;
    /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        ...{ class: "mr-2" },
    }));
    const __VLS_58 = __VLS_57({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    var __VLS_51;
    const __VLS_60 = {}.AMenuDivider;
    /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({}));
    const __VLS_62 = __VLS_61({}, ...__VLS_functionalComponentArgsRest(__VLS_61));
    const __VLS_64 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        ...{ 'onClick': {} },
        key: "logout",
    }));
    const __VLS_66 = __VLS_65({
        ...{ 'onClick': {} },
        key: "logout",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    let __VLS_68;
    let __VLS_69;
    let __VLS_70;
    const __VLS_71 = {
        onClick: (__VLS_ctx.handleLogout)
    };
    __VLS_67.slots.default;
    const __VLS_72 = {}.LogoutOutlined;
    /** @type {[typeof __VLS_components.LogoutOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ class: "mr-2" },
    }));
    const __VLS_74 = __VLS_73({
        ...{ class: "mr-2" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    var __VLS_67;
    var __VLS_35;
}
var __VLS_19;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex pt-16" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
    ...{ class: ([
            'fixed lg:static inset-y-0 left-0 z-40 w-64 bg-white shadow-sm border-r border-gray-200 transform transition-transform duration-300 ease-in-out pt-16 lg:pt-0',
            __VLS_ctx.sidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        ]) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.nav, __VLS_intrinsicElements.nav)({
    ...{ class: "h-full overflow-y-auto py-6" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "px-4" },
});
const __VLS_76 = {}.AMenu;
/** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    selectedKeys: (__VLS_ctx.selectedKeys),
    openKeys: (__VLS_ctx.openKeys),
    mode: "inline",
    inlineCollapsed: (false),
    ...{ class: "border-none" },
}));
const __VLS_78 = __VLS_77({
    selectedKeys: (__VLS_ctx.selectedKeys),
    openKeys: (__VLS_ctx.openKeys),
    mode: "inline",
    inlineCollapsed: (false),
    ...{ class: "border-none" },
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
const __VLS_80 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    ...{ 'onClick': {} },
    key: "dashboard",
}));
const __VLS_82 = __VLS_81({
    ...{ 'onClick': {} },
    key: "dashboard",
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
let __VLS_84;
let __VLS_85;
let __VLS_86;
const __VLS_87 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/dashboard');
    }
};
__VLS_83.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_83.slots;
    const __VLS_88 = {}.DashboardOutlined;
    /** @type {[typeof __VLS_components.DashboardOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        ...{ class: "text-gray-600" },
    }));
    const __VLS_90 = __VLS_89({
        ...{ class: "text-gray-600" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-700" },
});
var __VLS_83;
const __VLS_92 = {}.ASubMenu;
/** @type {[typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    key: "qc-management",
}));
const __VLS_94 = __VLS_93({
    key: "qc-management",
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_95.slots;
    const __VLS_96 = {}.SafetyCertificateOutlined;
    /** @type {[typeof __VLS_components.SafetyCertificateOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        ...{ class: "text-gray-600" },
    }));
    const __VLS_98 = __VLS_97({
        ...{ class: "text-gray-600" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
}
{
    const { title: __VLS_thisSlot } = __VLS_95.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-700" },
    });
}
const __VLS_100 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    ...{ 'onClick': {} },
    key: "audit-tasks",
}));
const __VLS_102 = __VLS_101({
    ...{ 'onClick': {} },
    key: "audit-tasks",
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
let __VLS_104;
let __VLS_105;
let __VLS_106;
const __VLS_107 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/audit-tasks');
    }
};
__VLS_103.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_103;
const __VLS_108 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    ...{ 'onClick': {} },
    key: "ai-assistance",
}));
const __VLS_110 = __VLS_109({
    ...{ 'onClick': {} },
    key: "ai-assistance",
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
let __VLS_112;
let __VLS_113;
let __VLS_114;
const __VLS_115 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/ai-assistance');
    }
};
__VLS_111.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_111;
const __VLS_116 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    ...{ 'onClick': {} },
    key: "batch-audit",
}));
const __VLS_118 = __VLS_117({
    ...{ 'onClick': {} },
    key: "batch-audit",
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
let __VLS_120;
let __VLS_121;
let __VLS_122;
const __VLS_123 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/batch-audit');
    }
};
__VLS_119.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_119;
var __VLS_95;
const __VLS_124 = {}.ASubMenu;
/** @type {[typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    key: "rules",
}));
const __VLS_126 = __VLS_125({
    key: "rules",
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
__VLS_127.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_127.slots;
    const __VLS_128 = {}.SettingOutlined;
    /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        ...{ class: "text-gray-600" },
    }));
    const __VLS_130 = __VLS_129({
        ...{ class: "text-gray-600" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
}
{
    const { title: __VLS_thisSlot } = __VLS_127.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-700" },
    });
}
const __VLS_132 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
    ...{ 'onClick': {} },
    key: "work-rules",
}));
const __VLS_134 = __VLS_133({
    ...{ 'onClick': {} },
    key: "work-rules",
}, ...__VLS_functionalComponentArgsRest(__VLS_133));
let __VLS_136;
let __VLS_137;
let __VLS_138;
const __VLS_139 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/rules/work-rules');
    }
};
__VLS_135.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_135;
const __VLS_140 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    ...{ 'onClick': {} },
    key: "enhanced-rules",
}));
const __VLS_142 = __VLS_141({
    ...{ 'onClick': {} },
    key: "enhanced-rules",
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
let __VLS_144;
let __VLS_145;
let __VLS_146;
const __VLS_147 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/rules/enhanced-rules');
    }
};
__VLS_143.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_143;
const __VLS_148 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
    ...{ 'onClick': {} },
    key: "department-config",
}));
const __VLS_150 = __VLS_149({
    ...{ 'onClick': {} },
    key: "department-config",
}, ...__VLS_functionalComponentArgsRest(__VLS_149));
let __VLS_152;
let __VLS_153;
let __VLS_154;
const __VLS_155 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/department-config');
    }
};
__VLS_151.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_151;
var __VLS_127;
const __VLS_156 = {}.ASubMenu;
/** @type {[typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, ]} */ ;
// @ts-ignore
const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
    key: "analytics",
}));
const __VLS_158 = __VLS_157({
    key: "analytics",
}, ...__VLS_functionalComponentArgsRest(__VLS_157));
__VLS_159.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_159.slots;
    const __VLS_160 = {}.BarChartOutlined;
    /** @type {[typeof __VLS_components.BarChartOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        ...{ class: "text-gray-600" },
    }));
    const __VLS_162 = __VLS_161({
        ...{ class: "text-gray-600" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
}
{
    const { title: __VLS_thisSlot } = __VLS_159.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-700" },
    });
}
const __VLS_164 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
    ...{ 'onClick': {} },
    key: "qc-reports",
}));
const __VLS_166 = __VLS_165({
    ...{ 'onClick': {} },
    key: "qc-reports",
}, ...__VLS_functionalComponentArgsRest(__VLS_165));
let __VLS_168;
let __VLS_169;
let __VLS_170;
const __VLS_171 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/reports/qc-reports');
    }
};
__VLS_167.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_167;
const __VLS_172 = {}.AMenuItem;
/** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
// @ts-ignore
const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
    ...{ 'onClick': {} },
    key: "statistics",
}));
const __VLS_174 = __VLS_173({
    ...{ 'onClick': {} },
    key: "statistics",
}, ...__VLS_functionalComponentArgsRest(__VLS_173));
let __VLS_176;
let __VLS_177;
let __VLS_178;
const __VLS_179 = {
    onClick: (...[$event]) => {
        __VLS_ctx.navigateTo('/statistics');
    }
};
__VLS_175.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "text-gray-600" },
});
var __VLS_175;
var __VLS_159;
if (__VLS_ctx.isAdmin) {
    const __VLS_180 = {}.ASubMenu;
    /** @type {[typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, typeof __VLS_components.ASubMenu, typeof __VLS_components.aSubMenu, ]} */ ;
    // @ts-ignore
    const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
        key: "system",
    }));
    const __VLS_182 = __VLS_181({
        key: "system",
    }, ...__VLS_functionalComponentArgsRest(__VLS_181));
    __VLS_183.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_183.slots;
        const __VLS_184 = {}.ControlOutlined;
        /** @type {[typeof __VLS_components.ControlOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
            ...{ class: "text-gray-600" },
        }));
        const __VLS_186 = __VLS_185({
            ...{ class: "text-gray-600" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    }
    {
        const { title: __VLS_thisSlot } = __VLS_183.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-gray-700" },
        });
    }
    const __VLS_188 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        ...{ 'onClick': {} },
        key: "user-management",
    }));
    const __VLS_190 = __VLS_189({
        ...{ 'onClick': {} },
        key: "user-management",
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    let __VLS_192;
    let __VLS_193;
    let __VLS_194;
    const __VLS_195 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.isAdmin))
                return;
            __VLS_ctx.navigateTo('/admin/users');
        }
    };
    __VLS_191.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-600" },
    });
    var __VLS_191;
    const __VLS_196 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
        ...{ 'onClick': {} },
        key: "system-settings",
    }));
    const __VLS_198 = __VLS_197({
        ...{ 'onClick': {} },
        key: "system-settings",
    }, ...__VLS_functionalComponentArgsRest(__VLS_197));
    let __VLS_200;
    let __VLS_201;
    let __VLS_202;
    const __VLS_203 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.isAdmin))
                return;
            __VLS_ctx.navigateTo('/admin/settings');
        }
    };
    __VLS_199.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-600" },
    });
    var __VLS_199;
    const __VLS_204 = {}.AMenuItem;
    /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
    // @ts-ignore
    const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
        ...{ 'onClick': {} },
        key: "logs",
    }));
    const __VLS_206 = __VLS_205({
        ...{ 'onClick': {} },
        key: "logs",
    }, ...__VLS_functionalComponentArgsRest(__VLS_205));
    let __VLS_208;
    let __VLS_209;
    let __VLS_210;
    const __VLS_211 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.isAdmin))
                return;
            __VLS_ctx.navigateTo('/admin/logs');
        }
    };
    __VLS_207.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-gray-600" },
    });
    var __VLS_207;
    var __VLS_183;
}
var __VLS_79;
if (__VLS_ctx.sidebarOpen) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ onClick: (__VLS_ctx.closeSidebar) },
        ...{ class: "fixed inset-0 z-30 bg-black bg-opacity-50 lg:hidden" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.main, __VLS_intrinsicElements.main)({
    ...{ class: "flex-1 lg:ml-0" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "p-6" },
});
const __VLS_212 = {}.RouterView;
/** @type {[typeof __VLS_components.RouterView, typeof __VLS_components.routerView, ]} */ ;
// @ts-ignore
const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({}));
const __VLS_214 = __VLS_213({}, ...__VLS_functionalComponentArgsRest(__VLS_213));
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-b']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['top-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-50']} */ ;
/** @type {__VLS_StyleScopedClasses['px-6']} */ ;
/** @type {__VLS_StyleScopedClasses['py-4']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-8']} */ ;
/** @type {__VLS_StyleScopedClasses['h-8']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['sm:block']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-4']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['text-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['space-x-2']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:bg-gray-100']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['sm:block']} */ ;
/** @type {__VLS_StyleScopedClasses['text-left']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-16']} */ ;
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:static']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-y-0']} */ ;
/** @type {__VLS_StyleScopedClasses['left-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-40']} */ ;
/** @type {__VLS_StyleScopedClasses['w-64']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['border-r']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['transform']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-transform']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-300']} */ ;
/** @type {__VLS_StyleScopedClasses['ease-in-out']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-16']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:pt-0']} */ ;
/** @type {__VLS_StyleScopedClasses['h-full']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['py-6']} */ ;
/** @type {__VLS_StyleScopedClasses['px-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-none']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-700']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['fixed']} */ ;
/** @type {__VLS_StyleScopedClasses['inset-0']} */ ;
/** @type {__VLS_StyleScopedClasses['z-30']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-black']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-opacity-50']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-1']} */ ;
/** @type {__VLS_StyleScopedClasses['lg:ml-0']} */ ;
/** @type {__VLS_StyleScopedClasses['p-6']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            MenuOutlined: icons_vue_1.MenuOutlined,
            MedicineBoxOutlined: icons_vue_1.MedicineBoxOutlined,
            BellOutlined: icons_vue_1.BellOutlined,
            UserOutlined: icons_vue_1.UserOutlined,
            DownOutlined: icons_vue_1.DownOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            LogoutOutlined: icons_vue_1.LogoutOutlined,
            DashboardOutlined: icons_vue_1.DashboardOutlined,
            SafetyCertificateOutlined: icons_vue_1.SafetyCertificateOutlined,
            BarChartOutlined: icons_vue_1.BarChartOutlined,
            ControlOutlined: icons_vue_1.ControlOutlined,
            sidebarOpen: sidebarOpen,
            selectedKeys: selectedKeys,
            openKeys: openKeys,
            notificationCount: notificationCount,
            currentUser: currentUser,
            isAdmin: isAdmin,
            toggleSidebar: toggleSidebar,
            closeSidebar: closeSidebar,
            navigateTo: navigateTo,
            goToProfile: goToProfile,
            goToSettings: goToSettings,
            handleLogout: handleLogout,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
