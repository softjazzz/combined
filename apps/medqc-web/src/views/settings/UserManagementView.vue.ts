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
const PermissionButton_vue_1 = __importDefault(require("@/components/auth/PermissionButton.vue"));
// 模拟用户数据
const users = (0, vue_1.ref)([
    {
        id: '1',
        email: 'admin@demo.com',
        display_name: '系统管理员',
        department: '信息科',
        roles: ['admin'],
        status: 'active',
        last_login: '2024-01-15 10:30:00',
        created_at: '2024-01-01 00:00:00'
    },
    {
        id: '2',
        email: 'qc@demo.com',
        display_name: '质控管理员',
        department: '质控科',
        roles: ['qc_manager'],
        status: 'active',
        last_login: '2024-01-15 09:15:00',
        created_at: '2024-01-02 00:00:00'
    },
    {
        id: '3',
        email: 'doctor@demo.com',
        display_name: '医务人员',
        department: '内科',
        roles: ['doctor'],
        status: 'active',
        last_login: '2024-01-15 08:45:00',
        created_at: '2024-01-03 00:00:00'
    }
]);
// 搜索和过滤
const searchForm = (0, vue_1.reactive)({
    keyword: '',
    department: '',
    role: '',
    status: ''
});
const loading = (0, vue_1.ref)(false);
const selectedRowKeys = (0, vue_1.ref)(: any[]);
// 过滤后的用户列表
const filteredUsers = (0, vue_1.computed)(() => {
    return users.value.filter(user => {
        const matchKeyword = !searchForm.keyword ||
            user.display_name.includes(searchForm.keyword) ||
            user.email.includes(searchForm.keyword);
        const matchDepartment = !searchForm.department || user.department === searchForm.department;
        const matchRole = !searchForm.role || user.roles.includes(searchForm.role);
        const matchStatus = !searchForm.status || user.status === searchForm.status;
        return matchKeyword && matchDepartment && matchRole && matchStatus;
    });
});
// 表格列定义
const columns = [
    { title: '用户信息',
        dataIndex: 'display_name',
        key: 'display_name',
        width: 200,
        customRender: ({ record   }) => ({
            children: [
                {
                    type: 'div',
                    props: { class: 'user-info' },
                    children: [
                        {
                            type: 'div',
                            props: { class: 'user-name' },
                            children: record.display_name
                        },
                        {
                            type: 'div',
                            props: { class: 'user-email' },
                            children: record.email
                        }
                    ]
                }
            ]
        })
    },
    {
        title: '科室',
        dataIndex: 'department',
        key: 'department',
        width: 120
    },
    { title: '角色',
        dataIndex: 'roles',
        key: 'roles',
        width: 150,
        customRender: ({ record   }) => record.roles.map(role => getRoleTag(role))
    },
    { title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        customRender: ({ record   }) => getStatusTag(record.status)
    },
    {
        title: '最后登录',
        dataIndex: 'last_login',
        key: 'last_login',
        width: 150
    },
    {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 150
    },
    {
        title: '操作',
        key: 'actions',
        width: 200,
        fixed: 'right'
    }
];
// 获取角色标签
const getRoleTag = (role) => {
    const roleConfig = {
        admin: { color: 'red', text: '管理员', icon: icons_vue_1.CrownOutlined },
        qc_manager: { color: 'blue', text: '质控管理员', icon: icons_vue_1.SafetyCertificateOutlined },
        qc_staff: { color: 'green', text: '质控人员', icon: icons_vue_1.SettingOutlined },
        doctor: { color: 'orange', text: '医务人员', icon: icons_vue_1.UserOutlined }
    };
    return roleConfig[role] || { color: 'default', text: role, icon: icons_vue_1.UserOutlined };
};
// 获取状态标签
const getStatusTag = (status) => {
    const statusConfig = {
        active: { color: 'success', text: '正常' },
        inactive: { color: 'default', text: '停用' },
        locked: { color: 'error', text: '锁定' }
    };
    return statusConfig[status] || { color: 'default', text: status };
};
// 新增用户
const showCreateModal = (0, vue_1.ref)(false);
const createForm = (0, vue_1.reactive)({ email: '',
    display_name: '',
    department: '',
    roles:  [],
    password: ''
});
const handleCreateUser = () => { showCreateModal.value = true;
    Object.assign(createForm, {
        email: '',
        display_name: '',
        department: '',
        roles:  [],
        password: ''
    });
};
const handleCreateSubmit = () => {
    // 模拟创建用户
    const newUser = {
        id: Date.now().toString(),
        email: createForm.email,
        display_name: createForm.display_name,
        department: createForm.department,
        roles: createForm.roles,
        status: 'active',
        created_at: new Date().toISOString()
    };
    users.value.unshift(newUser);
    showCreateModal.value = false;
    ant_design_vue_1.message.success('用户创建成功');
};
// 编辑用户
const showEditModal = (0, vue_1.ref)(false);
const editForm = (0, vue_1.reactive)({ id: '',
    email: '',
    display_name: '',
    department: '',
    roles:  [],
    status: 'active'
});
const handleEditUser = (user) => {
    showEditModal.value = true;
    Object.assign(editForm, {
        id: user.id,
        email: user.email,
        display_name: user.display_name,
        department: user.department,
        roles: [...user.roles],
        status: user.status
    });
};
const handleEditSubmit = () => {
    const userIndex = users.value.findIndex(u => u.id === editForm.id);
    if (userIndex !== -1) {
        users.value[userIndex] = {
            ...users.value[userIndex],
            email: editForm.email,
            display_name: editForm.display_name,
            department: editForm.department,
            roles: editForm.roles,
            status: editForm.status
        };
        showEditModal.value = false;
        ant_design_vue_1.message.success('用户更新成功');
    }
};
// 删除用户
const handleDeleteUser = (user) => {
    const userIndex = users.value.findIndex(u => u.id === user.id);
    if (userIndex !== -1) {
        users.value.splice(userIndex, 1);
        ant_design_vue_1.message.success('用户删除成功');
    }
};
// 批量删除
const handleBatchDelete = () => {
    if (selectedRowKeys.value.length === 0) {
        ant_design_vue_1.message.warning('请选择要删除的用户');
        return;
    }
    users.value = users.value.filter(user => !selectedRowKeys.value.includes(user.id));
    selectedRowKeys.value = [];
    ant_design_vue_1.message.success('批量删除成功');
};
// 重置密码
const handleResetPassword = (user) => {
    ant_design_vue_1.message.success(`已为用户 ${user.display_name} 重置密码`);
};
// 刷新数据
const handleRefresh = () => {
    loading.value = true;
    setTimeout(() => {
        loading.value = false;
        ant_design_vue_1.message.success('数据刷新成功');
    }, 1000);
};
// 搜索
const handleSearch = () => {
    // 搜索逻辑已在computed中实现
    ant_design_vue_1.message.success('搜索完成');
};
// 重置搜索
const handleResetSearch = () => {
    Object.assign(searchForm, {
        keyword: '',
        department: '',
        role: '',
        status: ''
    });
};
// 选择变化
const onSelectChange = (selectedKeys) => {
    selectedRowKeys.value = selectedKeys;
};
// 组件挂载
(0, vue_1.onMounted)(() => {
    // 初始化数据
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "user-management-view" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
const __VLS_0 = {}.UserOutlined;
/** @type {[typeof __VLS_components.UserOutlined, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "title-icon" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "title-icon" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "page-description" },
});
const __VLS_4 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ class: "search-card" },
    bordered: (false),
}));
const __VLS_6 = __VLS_5({
    ...{ class: "search-card" },
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    layout: "inline",
    model: (__VLS_ctx.searchForm),
}));
const __VLS_10 = __VLS_9({
    layout: "inline",
    model: (__VLS_ctx.searchForm),
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    label: "关键词",
}));
const __VLS_14 = __VLS_13({
    label: "关键词",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    value: (__VLS_ctx.searchForm.keyword),
    placeholder: "用户名或邮箱",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_18 = __VLS_17({
    value: (__VLS_ctx.searchForm.keyword),
    placeholder: "用户名或邮箱",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
{
    const { prefix: __VLS_thisSlot } = __VLS_19.slots;
    const __VLS_20 = {}.SearchOutlined;
    /** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
    const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
var __VLS_19;
var __VLS_15;
const __VLS_24 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    label: "科室",
}));
const __VLS_26 = __VLS_25({
    label: "科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
const __VLS_28 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    value: (__VLS_ctx.searchForm.department),
    placeholder: "请选择科室",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_30 = __VLS_29({
    value: (__VLS_ctx.searchForm.department),
    placeholder: "请选择科室",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    value: "信息科",
}));
const __VLS_34 = __VLS_33({
    value: "信息科",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
var __VLS_35;
const __VLS_36 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    value: "质控科",
}));
const __VLS_38 = __VLS_37({
    value: "质控科",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
var __VLS_39;
const __VLS_40 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    value: "内科",
}));
const __VLS_42 = __VLS_41({
    value: "内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
var __VLS_43;
const __VLS_44 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    value: "外科",
}));
const __VLS_46 = __VLS_45({
    value: "外科",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
var __VLS_47;
var __VLS_31;
var __VLS_27;
const __VLS_48 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    label: "角色",
}));
const __VLS_50 = __VLS_49({
    label: "角色",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_51.slots.default;
const __VLS_52 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    value: (__VLS_ctx.searchForm.role),
    placeholder: "请选择角色",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_54 = __VLS_53({
    value: (__VLS_ctx.searchForm.role),
    placeholder: "请选择角色",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    value: "admin",
}));
const __VLS_58 = __VLS_57({
    value: "admin",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
var __VLS_59;
const __VLS_60 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    value: "qc_manager",
}));
const __VLS_62 = __VLS_61({
    value: "qc_manager",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
var __VLS_63;
const __VLS_64 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    value: "qc_staff",
}));
const __VLS_66 = __VLS_65({
    value: "qc_staff",
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
__VLS_67.slots.default;
var __VLS_67;
const __VLS_68 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    value: "doctor",
}));
const __VLS_70 = __VLS_69({
    value: "doctor",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
var __VLS_71;
var __VLS_55;
var __VLS_51;
const __VLS_72 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
    label: "状态",
}));
const __VLS_74 = __VLS_73({
    label: "状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_73));
__VLS_75.slots.default;
const __VLS_76 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    value: (__VLS_ctx.searchForm.status),
    placeholder: "请选择状态",
    allowClear: true,
    ...{ style: {} },
}));
const __VLS_78 = __VLS_77({
    value: (__VLS_ctx.searchForm.status),
    placeholder: "请选择状态",
    allowClear: true,
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
const __VLS_80 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    value: "active",
}));
const __VLS_82 = __VLS_81({
    value: "active",
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
var __VLS_83;
const __VLS_84 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    value: "inactive",
}));
const __VLS_86 = __VLS_85({
    value: "inactive",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
var __VLS_87;
const __VLS_88 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    value: "locked",
}));
const __VLS_90 = __VLS_89({
    value: "locked",
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
var __VLS_91;
var __VLS_79;
var __VLS_75;
const __VLS_92 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({}));
const __VLS_94 = __VLS_93({}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
const __VLS_96 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    ...{ 'onClick': {} },
    type: "primary",
}));
const __VLS_98 = __VLS_97({
    ...{ 'onClick': {} },
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
let __VLS_100;
let __VLS_101;
let __VLS_102;
const __VLS_103 = {
    onClick: (__VLS_ctx.handleSearch)
};
__VLS_99.slots.default;
const __VLS_104 = {}.SearchOutlined;
/** @type {[typeof __VLS_components.SearchOutlined, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({}));
const __VLS_106 = __VLS_105({}, ...__VLS_functionalComponentArgsRest(__VLS_105));
var __VLS_99;
const __VLS_108 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    ...{ 'onClick': {} },
    ...{ style: {} },
}));
const __VLS_110 = __VLS_109({
    ...{ 'onClick': {} },
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
let __VLS_112;
let __VLS_113;
let __VLS_114;
const __VLS_115 = {
    onClick: (__VLS_ctx.handleResetSearch)
};
__VLS_111.slots.default;
var __VLS_111;
var __VLS_95;
var __VLS_11;
var __VLS_7;
const __VLS_116 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    ...{ class: "toolbar-card" },
    bordered: (false),
}));
const __VLS_118 = __VLS_117({
    ...{ class: "toolbar-card" },
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar-left" },
});
/** @type {[typeof PermissionButton, typeof PermissionButton, ]} */ ;
// @ts-ignore
const __VLS_120 = __VLS_asFunctionalComponent(PermissionButton_vue_1.default, new PermissionButton_vue_1.default({
    ...{ 'onClick': {} },
    resource: "users",
    action: "create",
    type: "primary",
}));
const __VLS_121 = __VLS_120({
    ...{ 'onClick': {} },
    resource: "users",
    action: "create",
    type: "primary",
}, ...__VLS_functionalComponentArgsRest(__VLS_120));
let __VLS_123;
let __VLS_124;
let __VLS_125;
const __VLS_126 = {
    onClick: (__VLS_ctx.handleCreateUser)
};
__VLS_122.slots.default;
const __VLS_127 = {}.PlusOutlined;
/** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
// @ts-ignore
const __VLS_128 = __VLS_asFunctionalComponent(__VLS_127, new __VLS_127({}));
const __VLS_129 = __VLS_128({}, ...__VLS_functionalComponentArgsRest(__VLS_128));
var __VLS_122;
/** @type {[typeof PermissionButton, typeof PermissionButton, ]} */ ;
// @ts-ignore
const __VLS_131 = __VLS_asFunctionalComponent(PermissionButton_vue_1.default, new PermissionButton_vue_1.default({
    ...{ 'onClick': {} },
    resource: "users",
    action: "delete",
    danger: true,
    disabled: (__VLS_ctx.selectedRowKeys.length === 0),
}));
const __VLS_132 = __VLS_131({
    ...{ 'onClick': {} },
    resource: "users",
    action: "delete",
    danger: true,
    disabled: (__VLS_ctx.selectedRowKeys.length === 0),
}, ...__VLS_functionalComponentArgsRest(__VLS_131));
let __VLS_134;
let __VLS_135;
let __VLS_136;
const __VLS_137 = {
    onClick: (__VLS_ctx.handleBatchDelete)
};
__VLS_133.slots.default;
const __VLS_138 = {}.DeleteOutlined;
/** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
// @ts-ignore
const __VLS_139 = __VLS_asFunctionalComponent(__VLS_138, new __VLS_138({}));
const __VLS_140 = __VLS_139({}, ...__VLS_functionalComponentArgsRest(__VLS_139));
var __VLS_133;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "toolbar-right" },
});
const __VLS_142 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_143 = __VLS_asFunctionalComponent(__VLS_142, new __VLS_142({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}));
const __VLS_144 = __VLS_143({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_143));
let __VLS_146;
let __VLS_147;
let __VLS_148;
const __VLS_149 = {
    onClick: (__VLS_ctx.handleRefresh)
};
__VLS_145.slots.default;
const __VLS_150 = {}.ReloadOutlined;
/** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
// @ts-ignore
const __VLS_151 = __VLS_asFunctionalComponent(__VLS_150, new __VLS_150({}));
const __VLS_152 = __VLS_151({}, ...__VLS_functionalComponentArgsRest(__VLS_151));
var __VLS_145;
var __VLS_119;
const __VLS_154 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_155 = __VLS_asFunctionalComponent(__VLS_154, new __VLS_154({
    bordered: (false),
}));
const __VLS_156 = __VLS_155({
    bordered: (false),
}, ...__VLS_functionalComponentArgsRest(__VLS_155));
__VLS_157.slots.default;
const __VLS_158 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_159 = __VLS_asFunctionalComponent(__VLS_158, new __VLS_158({
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.filteredUsers),
    loading: (__VLS_ctx.loading),
    pagination: ({
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: (total) => `共 ${total} 条记录`
    }),
    rowSelection: ({
        selectedRowKeys: __VLS_ctx.selectedRowKeys,
        onChange: __VLS_ctx.onSelectChange
    }),
    rowKey: "id",
    size: "middle",
}));
const __VLS_160 = __VLS_159({
    columns: (__VLS_ctx.columns),
    dataSource: (__VLS_ctx.filteredUsers),
    loading: (__VLS_ctx.loading),
    pagination: ({
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: (total) => `共 ${total} 条记录`
    }),
    rowSelection: ({
        selectedRowKeys: __VLS_ctx.selectedRowKeys,
        onChange: __VLS_ctx.onSelectChange
    }),
    rowKey: "id",
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_159));
__VLS_161.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_161.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'display_name') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "user-info" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "user-name" },
        });
        (record.display_name);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "user-email" },
        });
        (record.email);
    }
    else if (column.key === 'roles') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "role-tags" },
        });
        for (const [role] of __VLS_getVForSourceType((record.roles))) {
            const __VLS_162 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_163 = __VLS_asFunctionalComponent(__VLS_162, new __VLS_162({
                key: (role),
                color: (__VLS_ctx.getRoleTag(role).color),
                ...{ class: "role-tag" },
            }));
            const __VLS_164 = __VLS_163({
                key: (role),
                color: (__VLS_ctx.getRoleTag(role).color),
                ...{ class: "role-tag" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_163));
            __VLS_165.slots.default;
            const __VLS_166 = ((__VLS_ctx.getRoleTag(role).icon));
            // @ts-ignore
            const __VLS_167 = __VLS_asFunctionalComponent(__VLS_166, new __VLS_166({
                ...{ class: "role-icon" },
            }));
            const __VLS_168 = __VLS_167({
                ...{ class: "role-icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_167));
            (__VLS_ctx.getRoleTag(role).text);
            var __VLS_165;
        }
    }
    else if (column.key === 'status') {
        const __VLS_170 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_171 = __VLS_asFunctionalComponent(__VLS_170, new __VLS_170({
            color: (__VLS_ctx.getStatusTag(record.status).color),
        }));
        const __VLS_172 = __VLS_171({
            color: (__VLS_ctx.getStatusTag(record.status).color),
        }, ...__VLS_functionalComponentArgsRest(__VLS_171));
        __VLS_173.slots.default;
        (__VLS_ctx.getStatusTag(record.status).text);
        var __VLS_173;
    }
    else if (column.key === 'actions') {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "action-buttons" },
        });
        /** @type {[typeof PermissionButton, typeof PermissionButton, ]} */ ;
        // @ts-ignore
        const __VLS_174 = __VLS_asFunctionalComponent(PermissionButton_vue_1.default, new PermissionButton_vue_1.default({
            ...{ 'onClick': {} },
            resource: "users",
            action: "update",
            type: "link",
            size: "small",
        }));
        const __VLS_175 = __VLS_174({
            ...{ 'onClick': {} },
            resource: "users",
            action: "update",
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_174));
        let __VLS_177;
        let __VLS_178;
        let __VLS_179;
        const __VLS_180 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'display_name'))
                    return;
                if (!!(column.key === 'roles'))
                    return;
                if (!!(column.key === 'status'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.handleEditUser(record);
            }
        };
        __VLS_176.slots.default;
        const __VLS_181 = {}.EditOutlined;
        /** @type {[typeof __VLS_components.EditOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({}));
        const __VLS_183 = __VLS_182({}, ...__VLS_functionalComponentArgsRest(__VLS_182));
        var __VLS_176;
        /** @type {[typeof PermissionButton, typeof PermissionButton, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(PermissionButton_vue_1.default, new PermissionButton_vue_1.default({
            ...{ 'onClick': {} },
            resource: "users",
            action: "update",
            type: "link",
            size: "small",
        }));
        const __VLS_186 = __VLS_185({
            ...{ 'onClick': {} },
            resource: "users",
            action: "update",
            type: "link",
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
        let __VLS_188;
        let __VLS_189;
        let __VLS_190;
        const __VLS_191 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'display_name'))
                    return;
                if (!!(column.key === 'roles'))
                    return;
                if (!!(column.key === 'status'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.handleResetPassword(record);
            }
        };
        __VLS_187.slots.default;
        const __VLS_192 = {}.SettingOutlined;
        /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({}));
        const __VLS_194 = __VLS_193({}, ...__VLS_functionalComponentArgsRest(__VLS_193));
        var __VLS_187;
        /** @type {[typeof PermissionButton, typeof PermissionButton, ]} */ ;
        // @ts-ignore
        const __VLS_196 = __VLS_asFunctionalComponent(PermissionButton_vue_1.default, new PermissionButton_vue_1.default({
            ...{ 'onClick': {} },
            resource: "users",
            action: "delete",
            type: "link",
            size: "small",
            danger: true,
        }));
        const __VLS_197 = __VLS_196({
            ...{ 'onClick': {} },
            resource: "users",
            action: "delete",
            type: "link",
            size: "small",
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_196));
        let __VLS_199;
        let __VLS_200;
        let __VLS_201;
        const __VLS_202 = {
            onClick: (...[$event]) => {
                if (!!(column.key === 'display_name'))
                    return;
                if (!!(column.key === 'roles'))
                    return;
                if (!!(column.key === 'status'))
                    return;
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.handleDeleteUser(record);
            }
        };
        __VLS_198.slots.default;
        const __VLS_203 = {}.DeleteOutlined;
        /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_204 = __VLS_asFunctionalComponent(__VLS_203, new __VLS_203({}));
        const __VLS_205 = __VLS_204({}, ...__VLS_functionalComponentArgsRest(__VLS_204));
        var __VLS_198;
    }
}
var __VLS_161;
var __VLS_157;
const __VLS_207 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_208 = __VLS_asFunctionalComponent(__VLS_207, new __VLS_207({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showCreateModal),
    title: "新增用户",
    width: (600),
}));
const __VLS_209 = __VLS_208({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showCreateModal),
    title: "新增用户",
    width: (600),
}, ...__VLS_functionalComponentArgsRest(__VLS_208));
let __VLS_211;
let __VLS_212;
let __VLS_213;
const __VLS_214 = {
    onOk: (__VLS_ctx.handleCreateSubmit)
};
__VLS_210.slots.default;
const __VLS_215 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_216 = __VLS_asFunctionalComponent(__VLS_215, new __VLS_215({
    model: (__VLS_ctx.createForm),
    layout: "vertical",
}));
const __VLS_217 = __VLS_216({
    model: (__VLS_ctx.createForm),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_216));
__VLS_218.slots.default;
const __VLS_219 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_220 = __VLS_asFunctionalComponent(__VLS_219, new __VLS_219({
    label: "邮箱地址",
    required: true,
}));
const __VLS_221 = __VLS_220({
    label: "邮箱地址",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_220));
__VLS_222.slots.default;
const __VLS_223 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_224 = __VLS_asFunctionalComponent(__VLS_223, new __VLS_223({
    value: (__VLS_ctx.createForm.email),
    placeholder: "请输入邮箱地址",
}));
const __VLS_225 = __VLS_224({
    value: (__VLS_ctx.createForm.email),
    placeholder: "请输入邮箱地址",
}, ...__VLS_functionalComponentArgsRest(__VLS_224));
var __VLS_222;
const __VLS_227 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_228 = __VLS_asFunctionalComponent(__VLS_227, new __VLS_227({
    label: "显示名称",
    required: true,
}));
const __VLS_229 = __VLS_228({
    label: "显示名称",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_228));
__VLS_230.slots.default;
const __VLS_231 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_232 = __VLS_asFunctionalComponent(__VLS_231, new __VLS_231({
    value: (__VLS_ctx.createForm.display_name),
    placeholder: "请输入显示名称",
}));
const __VLS_233 = __VLS_232({
    value: (__VLS_ctx.createForm.display_name),
    placeholder: "请输入显示名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_232));
var __VLS_230;
const __VLS_235 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_236 = __VLS_asFunctionalComponent(__VLS_235, new __VLS_235({
    label: "所属科室",
    required: true,
}));
const __VLS_237 = __VLS_236({
    label: "所属科室",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_236));
__VLS_238.slots.default;
const __VLS_239 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_240 = __VLS_asFunctionalComponent(__VLS_239, new __VLS_239({
    value: (__VLS_ctx.createForm.department),
    placeholder: "请选择科室",
}));
const __VLS_241 = __VLS_240({
    value: (__VLS_ctx.createForm.department),
    placeholder: "请选择科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_240));
__VLS_242.slots.default;
const __VLS_243 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_244 = __VLS_asFunctionalComponent(__VLS_243, new __VLS_243({
    value: "信息科",
}));
const __VLS_245 = __VLS_244({
    value: "信息科",
}, ...__VLS_functionalComponentArgsRest(__VLS_244));
__VLS_246.slots.default;
var __VLS_246;
const __VLS_247 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_248 = __VLS_asFunctionalComponent(__VLS_247, new __VLS_247({
    value: "质控科",
}));
const __VLS_249 = __VLS_248({
    value: "质控科",
}, ...__VLS_functionalComponentArgsRest(__VLS_248));
__VLS_250.slots.default;
var __VLS_250;
const __VLS_251 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_252 = __VLS_asFunctionalComponent(__VLS_251, new __VLS_251({
    value: "内科",
}));
const __VLS_253 = __VLS_252({
    value: "内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_252));
__VLS_254.slots.default;
var __VLS_254;
const __VLS_255 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_256 = __VLS_asFunctionalComponent(__VLS_255, new __VLS_255({
    value: "外科",
}));
const __VLS_257 = __VLS_256({
    value: "外科",
}, ...__VLS_functionalComponentArgsRest(__VLS_256));
__VLS_258.slots.default;
var __VLS_258;
var __VLS_242;
var __VLS_238;
const __VLS_259 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_260 = __VLS_asFunctionalComponent(__VLS_259, new __VLS_259({
    label: "用户角色",
    required: true,
}));
const __VLS_261 = __VLS_260({
    label: "用户角色",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_260));
__VLS_262.slots.default;
const __VLS_263 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_264 = __VLS_asFunctionalComponent(__VLS_263, new __VLS_263({
    value: (__VLS_ctx.createForm.roles),
    mode: "multiple",
    placeholder: "请选择角色",
}));
const __VLS_265 = __VLS_264({
    value: (__VLS_ctx.createForm.roles),
    mode: "multiple",
    placeholder: "请选择角色",
}, ...__VLS_functionalComponentArgsRest(__VLS_264));
__VLS_266.slots.default;
const __VLS_267 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_268 = __VLS_asFunctionalComponent(__VLS_267, new __VLS_267({
    value: "admin",
}));
const __VLS_269 = __VLS_268({
    value: "admin",
}, ...__VLS_functionalComponentArgsRest(__VLS_268));
__VLS_270.slots.default;
var __VLS_270;
const __VLS_271 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_272 = __VLS_asFunctionalComponent(__VLS_271, new __VLS_271({
    value: "qc_manager",
}));
const __VLS_273 = __VLS_272({
    value: "qc_manager",
}, ...__VLS_functionalComponentArgsRest(__VLS_272));
__VLS_274.slots.default;
var __VLS_274;
const __VLS_275 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_276 = __VLS_asFunctionalComponent(__VLS_275, new __VLS_275({
    value: "qc_staff",
}));
const __VLS_277 = __VLS_276({
    value: "qc_staff",
}, ...__VLS_functionalComponentArgsRest(__VLS_276));
__VLS_278.slots.default;
var __VLS_278;
const __VLS_279 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_280 = __VLS_asFunctionalComponent(__VLS_279, new __VLS_279({
    value: "doctor",
}));
const __VLS_281 = __VLS_280({
    value: "doctor",
}, ...__VLS_functionalComponentArgsRest(__VLS_280));
__VLS_282.slots.default;
var __VLS_282;
var __VLS_266;
var __VLS_262;
const __VLS_283 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_284 = __VLS_asFunctionalComponent(__VLS_283, new __VLS_283({
    label: "初始密码",
    required: true,
}));
const __VLS_285 = __VLS_284({
    label: "初始密码",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_284));
__VLS_286.slots.default;
const __VLS_287 = {}.AInputPassword;
/** @type {[typeof __VLS_components.AInputPassword, typeof __VLS_components.aInputPassword, ]} */ ;
// @ts-ignore
const __VLS_288 = __VLS_asFunctionalComponent(__VLS_287, new __VLS_287({
    value: (__VLS_ctx.createForm.password),
    placeholder: "请输入初始密码",
}));
const __VLS_289 = __VLS_288({
    value: (__VLS_ctx.createForm.password),
    placeholder: "请输入初始密码",
}, ...__VLS_functionalComponentArgsRest(__VLS_288));
var __VLS_286;
var __VLS_218;
var __VLS_210;
const __VLS_291 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_292 = __VLS_asFunctionalComponent(__VLS_291, new __VLS_291({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showEditModal),
    title: "编辑用户",
    width: (600),
}));
const __VLS_293 = __VLS_292({
    ...{ 'onOk': {} },
    open: (__VLS_ctx.showEditModal),
    title: "编辑用户",
    width: (600),
}, ...__VLS_functionalComponentArgsRest(__VLS_292));
let __VLS_295;
let __VLS_296;
let __VLS_297;
const __VLS_298 = {
    onOk: (__VLS_ctx.handleEditSubmit)
};
__VLS_294.slots.default;
const __VLS_299 = {}.AForm;
/** @type {[typeof __VLS_components.AForm, typeof __VLS_components.aForm, typeof __VLS_components.AForm, typeof __VLS_components.aForm, ]} */ ;
// @ts-ignore
const __VLS_300 = __VLS_asFunctionalComponent(__VLS_299, new __VLS_299({
    model: (__VLS_ctx.editForm),
    layout: "vertical",
}));
const __VLS_301 = __VLS_300({
    model: (__VLS_ctx.editForm),
    layout: "vertical",
}, ...__VLS_functionalComponentArgsRest(__VLS_300));
__VLS_302.slots.default;
const __VLS_303 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_304 = __VLS_asFunctionalComponent(__VLS_303, new __VLS_303({
    label: "邮箱地址",
    required: true,
}));
const __VLS_305 = __VLS_304({
    label: "邮箱地址",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_304));
__VLS_306.slots.default;
const __VLS_307 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_308 = __VLS_asFunctionalComponent(__VLS_307, new __VLS_307({
    value: (__VLS_ctx.editForm.email),
    placeholder: "请输入邮箱地址",
}));
const __VLS_309 = __VLS_308({
    value: (__VLS_ctx.editForm.email),
    placeholder: "请输入邮箱地址",
}, ...__VLS_functionalComponentArgsRest(__VLS_308));
var __VLS_306;
const __VLS_311 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_312 = __VLS_asFunctionalComponent(__VLS_311, new __VLS_311({
    label: "显示名称",
    required: true,
}));
const __VLS_313 = __VLS_312({
    label: "显示名称",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_312));
__VLS_314.slots.default;
const __VLS_315 = {}.AInput;
/** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
// @ts-ignore
const __VLS_316 = __VLS_asFunctionalComponent(__VLS_315, new __VLS_315({
    value: (__VLS_ctx.editForm.display_name),
    placeholder: "请输入显示名称",
}));
const __VLS_317 = __VLS_316({
    value: (__VLS_ctx.editForm.display_name),
    placeholder: "请输入显示名称",
}, ...__VLS_functionalComponentArgsRest(__VLS_316));
var __VLS_314;
const __VLS_319 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_320 = __VLS_asFunctionalComponent(__VLS_319, new __VLS_319({
    label: "所属科室",
    required: true,
}));
const __VLS_321 = __VLS_320({
    label: "所属科室",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_320));
__VLS_322.slots.default;
const __VLS_323 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_324 = __VLS_asFunctionalComponent(__VLS_323, new __VLS_323({
    value: (__VLS_ctx.editForm.department),
    placeholder: "请选择科室",
}));
const __VLS_325 = __VLS_324({
    value: (__VLS_ctx.editForm.department),
    placeholder: "请选择科室",
}, ...__VLS_functionalComponentArgsRest(__VLS_324));
__VLS_326.slots.default;
const __VLS_327 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_328 = __VLS_asFunctionalComponent(__VLS_327, new __VLS_327({
    value: "信息科",
}));
const __VLS_329 = __VLS_328({
    value: "信息科",
}, ...__VLS_functionalComponentArgsRest(__VLS_328));
__VLS_330.slots.default;
var __VLS_330;
const __VLS_331 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_332 = __VLS_asFunctionalComponent(__VLS_331, new __VLS_331({
    value: "质控科",
}));
const __VLS_333 = __VLS_332({
    value: "质控科",
}, ...__VLS_functionalComponentArgsRest(__VLS_332));
__VLS_334.slots.default;
var __VLS_334;
const __VLS_335 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_336 = __VLS_asFunctionalComponent(__VLS_335, new __VLS_335({
    value: "内科",
}));
const __VLS_337 = __VLS_336({
    value: "内科",
}, ...__VLS_functionalComponentArgsRest(__VLS_336));
__VLS_338.slots.default;
var __VLS_338;
const __VLS_339 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_340 = __VLS_asFunctionalComponent(__VLS_339, new __VLS_339({
    value: "外科",
}));
const __VLS_341 = __VLS_340({
    value: "外科",
}, ...__VLS_functionalComponentArgsRest(__VLS_340));
__VLS_342.slots.default;
var __VLS_342;
var __VLS_326;
var __VLS_322;
const __VLS_343 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_344 = __VLS_asFunctionalComponent(__VLS_343, new __VLS_343({
    label: "用户角色",
    required: true,
}));
const __VLS_345 = __VLS_344({
    label: "用户角色",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_344));
__VLS_346.slots.default;
const __VLS_347 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_348 = __VLS_asFunctionalComponent(__VLS_347, new __VLS_347({
    value: (__VLS_ctx.editForm.roles),
    mode: "multiple",
    placeholder: "请选择角色",
}));
const __VLS_349 = __VLS_348({
    value: (__VLS_ctx.editForm.roles),
    mode: "multiple",
    placeholder: "请选择角色",
}, ...__VLS_functionalComponentArgsRest(__VLS_348));
__VLS_350.slots.default;
const __VLS_351 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_352 = __VLS_asFunctionalComponent(__VLS_351, new __VLS_351({
    value: "admin",
}));
const __VLS_353 = __VLS_352({
    value: "admin",
}, ...__VLS_functionalComponentArgsRest(__VLS_352));
__VLS_354.slots.default;
var __VLS_354;
const __VLS_355 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_356 = __VLS_asFunctionalComponent(__VLS_355, new __VLS_355({
    value: "qc_manager",
}));
const __VLS_357 = __VLS_356({
    value: "qc_manager",
}, ...__VLS_functionalComponentArgsRest(__VLS_356));
__VLS_358.slots.default;
var __VLS_358;
const __VLS_359 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_360 = __VLS_asFunctionalComponent(__VLS_359, new __VLS_359({
    value: "qc_staff",
}));
const __VLS_361 = __VLS_360({
    value: "qc_staff",
}, ...__VLS_functionalComponentArgsRest(__VLS_360));
__VLS_362.slots.default;
var __VLS_362;
const __VLS_363 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_364 = __VLS_asFunctionalComponent(__VLS_363, new __VLS_363({
    value: "doctor",
}));
const __VLS_365 = __VLS_364({
    value: "doctor",
}, ...__VLS_functionalComponentArgsRest(__VLS_364));
__VLS_366.slots.default;
var __VLS_366;
var __VLS_350;
var __VLS_346;
const __VLS_367 = {}.AFormItem;
/** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
// @ts-ignore
const __VLS_368 = __VLS_asFunctionalComponent(__VLS_367, new __VLS_367({
    label: "用户状态",
    required: true,
}));
const __VLS_369 = __VLS_368({
    label: "用户状态",
    required: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_368));
__VLS_370.slots.default;
const __VLS_371 = {}.ASelect;
/** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
// @ts-ignore
const __VLS_372 = __VLS_asFunctionalComponent(__VLS_371, new __VLS_371({
    value: (__VLS_ctx.editForm.status),
    placeholder: "请选择状态",
}));
const __VLS_373 = __VLS_372({
    value: (__VLS_ctx.editForm.status),
    placeholder: "请选择状态",
}, ...__VLS_functionalComponentArgsRest(__VLS_372));
__VLS_374.slots.default;
const __VLS_375 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_376 = __VLS_asFunctionalComponent(__VLS_375, new __VLS_375({
    value: "active",
}));
const __VLS_377 = __VLS_376({
    value: "active",
}, ...__VLS_functionalComponentArgsRest(__VLS_376));
__VLS_378.slots.default;
var __VLS_378;
const __VLS_379 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_380 = __VLS_asFunctionalComponent(__VLS_379, new __VLS_379({
    value: "inactive",
}));
const __VLS_381 = __VLS_380({
    value: "inactive",
}, ...__VLS_functionalComponentArgsRest(__VLS_380));
__VLS_382.slots.default;
var __VLS_382;
const __VLS_383 = {}.ASelectOption;
/** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
// @ts-ignore
const __VLS_384 = __VLS_asFunctionalComponent(__VLS_383, new __VLS_383({
    value: "locked",
}));
const __VLS_385 = __VLS_384({
    value: "locked",
}, ...__VLS_functionalComponentArgsRest(__VLS_384));
__VLS_386.slots.default;
var __VLS_386;
var __VLS_374;
var __VLS_370;
var __VLS_302;
var __VLS_294;
/** @type {__VLS_StyleScopedClasses['user-management-view']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['title-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['page-description']} */ ;
/** @type {__VLS_StyleScopedClasses['search-card']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-card']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-left']} */ ;
/** @type {__VLS_StyleScopedClasses['toolbar-right']} */ ;
/** @type {__VLS_StyleScopedClasses['user-info']} */ ;
/** @type {__VLS_StyleScopedClasses['user-name']} */ ;
/** @type {__VLS_StyleScopedClasses['user-email']} */ ;
/** @type {__VLS_StyleScopedClasses['role-tags']} */ ;
/** @type {__VLS_StyleScopedClasses['role-tag']} */ ;
/** @type {__VLS_StyleScopedClasses['role-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['action-buttons']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            UserOutlined: icons_vue_1.UserOutlined,
            PlusOutlined: icons_vue_1.PlusOutlined,
            EditOutlined: icons_vue_1.EditOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            SearchOutlined: icons_vue_1.SearchOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            PermissionButton: PermissionButton_vue_1.default,
            searchForm: searchForm,
            loading: loading,
            selectedRowKeys: selectedRowKeys,
            filteredUsers: filteredUsers,
            columns: columns,
            getRoleTag: getRoleTag,
            getStatusTag: getStatusTag,
            showCreateModal: showCreateModal,
            createForm: createForm,
            handleCreateUser: handleCreateUser,
            handleCreateSubmit: handleCreateSubmit,
            showEditModal: showEditModal,
            editForm: editForm,
            handleEditUser: handleEditUser,
            handleEditSubmit: handleEditSubmit,
            handleDeleteUser: handleDeleteUser,
            handleBatchDelete: handleBatchDelete,
            handleResetPassword: handleResetPassword,
            handleRefresh: handleRefresh,
            handleSearch: handleSearch,
            handleResetSearch: handleResetSearch,
            onSelectChange: onSelectChange,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
