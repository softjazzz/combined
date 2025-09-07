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
const echarts = __importStar(require("echarts"));
import running_qc_service_1 from '../../lib/running-qc-service';
// 响应式数据
const loading = (0, vue_1.ref)(false);
const selectedDepartment = (0, vue_1.ref)('');
const analyzingPatients = (0, vue_1.ref)(: any[]);
const analysisModalVisible = (0, vue_1.ref)(false);
const currentAnalysisResult = (0, vue_1.ref)(null);
// 数据
const patients = (0, vue_1.ref)(: any[]);
const filteredPatients = (0, vue_1.ref)(: any[]);
const departments = (0, vue_1.ref)(: any[]);
const recentAlerts = (0, vue_1.ref)(: any[]);
// 统计数据
const statistics = (0, vue_1.reactive)({
    totalPatients: 0,
    highRiskPatients: 0,
    criticalPatients: 0,
    overduePatients: 0
});
// 图表引用
const riskChartRef = (0, vue_1.ref)();
const departmentChartRef = (0, vue_1.ref)();
// 表格列定义
const patientColumns = [
    {
        title: '患者姓名',
        dataIndex: 'patientName',
        key: 'patientName',
        width: 100
    },
    {
        title: '科室',
        dataIndex: 'department',
        key: 'department',
        width: 100
    },
    {
        title: '入院天数',
        key: 'daysSinceAdmission',
        width: 80
    },
    {
        title: '风险等级',
        key: 'riskLevel',
        width: 80
    },
    {
        title: '质控等级',
        key: 'grade',
        width: 80
    },
    {
        title: '主治医生',
        dataIndex: 'doctorName',
        key: 'doctorName',
        width: 100
    },
    {
        title: '操作',
        key: 'actions',
        width: 150
    }
];
// 组件挂载
(0, vue_1.onMounted)(async () => {
    await loadInpatients();
    initCharts();
    // 设置定时刷新
    setInterval(refreshPatients, 5 * 60 * 1000); // 每5分钟刷新
});
// 加载在院病人数据
const loadInpatients = async () => {
    loading.value = true;
    try {
        // 模拟数据，实际应该从API获取
        const mockPatients = [
            {
                id: '1',
                patientName: '张三',
                patientAge: 45,
                patientGender: 'M',
                department: '内一科',
                admissionDate: '2024-01-15T10:00:00Z',
                daysSinceAdmission: 3,
                riskLevel: 'medium',
                grade: '乙级',
                lastQCTime: '2024-01-18T09:00:00Z',
                nextCheckTime: '2024-01-18T21:00:00Z',
                doctorId: 'doctor1',
                doctorName: '李医生'
            },
            {
                id: '2',
                patientName: '李四',
                patientAge: 32,
                patientGender: 'F',
                department: '外三科',
                admissionDate: '2024-01-16T14:00:00Z',
                daysSinceAdmission: 2,
                riskLevel: 'high',
                grade: '丙级',
                lastQCTime: '2024-01-17T16:00:00Z',
                nextCheckTime: '2024-01-18T22:00:00Z',
                doctorId: 'doctor2',
                doctorName: '王医生'
            },
            {
                id: '3',
                patientName: '王五',
                patientAge: 58,
                patientGender: 'M',
                department: '内一科',
                admissionDate: '2024-01-17T08:00:00Z',
                daysSinceAdmission: 1,
                riskLevel: 'low',
                grade: '甲级',
                lastQCTime: '2024-01-18T10:00:00Z',
                nextCheckTime: '2024-01-19T10:00:00Z',
                doctorId: 'doctor1',
                doctorName: '李医生'
            }
        ];
        patients.value = mockPatients;
        filteredPatients.value = mockPatients;
        // 提取科室列表
        departments.value = [...new Set(mockPatients.map(p => p.department))];
        // 更新统计数据
        updateStatistics();
        // 加载提醒数据
        await loadRecentAlerts();
    }
    catch (error) {
        console.error('加载在院病人数据失败:', error);
        ant_design_vue_1.message.error('加载数据失败');
    }
    finally {
        loading.value = false;
    }
};
// 刷新患者数据
const refreshPatients = async () => {
    await loadInpatients();
    ant_design_vue_1.message.success('数据已刷新');
};
// 过滤患者
const filterPatients = () => {
    if (!selectedDepartment.value) {
        filteredPatients.value = patients.value;
    }
    else {
        filteredPatients.value = patients.value.filter(p => p.department === selectedDepartment.value);
    }
};
// 分析患者
const analyzePatient = async (patient) => {
    analyzingPatients.value.push(patient.id);
    try {
        const result = await running_qc_service_1.runningQCService.analyzeRunningRecord({
            recordId: `running-${patient.id}`,
            patientId: patient.id,
            content: `患者：${patient.patientName}，科室：${patient.department}，入院日期：${patient.admissionDate}`,
            department: patient.department,
            admissionDate: patient.admissionDate,
            currentDate: new Date().toISOString(),
            doctorId: patient.doctorId,
            analysisType: 'real-time'
        });
        currentAnalysisResult.value = result;
        analysisModalVisible.value = true;
        // 更新患者状态
        const patientIndex = patients.value.findIndex(p => p.id === patient.id);
        if (patientIndex !== -1) {
            patients.value[patientIndex].riskLevel = result.summary.riskLevel;
            patients.value[patientIndex].grade = result.summary.grade;
            patients.value[patientIndex].lastQCTime = result.analysisTime;
            patients.value[patientIndex].nextCheckTime = result.nextCheckTime;
        }
        ant_design_vue_1.message.success('质控分析完成');
    }
    catch (error) {
        console.error('质控分析失败:', error);
        ant_design_vue_1.message.error('质控分析失败');
    }
    finally {
        analyzingPatients.value = analyzingPatients.value.filter(id => id !== patient.id);
    }
};
// 查看详情
const viewDetails = (patient) => {
    // 跳转到患者详情页面
    console.log('查看患者详情:', patient);
};
// 加载近期提醒
const loadRecentAlerts = async () => {
    // 模拟提醒数据
    recentAlerts.value = [
        {
            id: '1',
            patientId: '2',
            patientName: '李四',
            level: 'high',
            message: '入院记录超时24小时未完成',
            time: '2024-01-18T10:30:00Z'
        },
        {
            id: '2',
            patientId: '1',
            patientName: '张三',
            level: 'medium',
            message: '首次病程记录需要完善',
            time: '2024-01-18T11:00:00Z'
        }
    ];
};
// 处理提醒
const handleAlert = (alert) => {
    console.log('处理提醒:', alert);
    // 实现提醒处理逻辑
};
// 更新统计数据
const updateStatistics = () => {
    statistics.totalPatients = patients.value.length;
    statistics.highRiskPatients = patients.value.filter(p => p.riskLevel === 'high' || p.riskLevel === 'critical').length;
    statistics.criticalPatients = patients.value.filter(p => p.riskLevel === 'critical').length;
    statistics.overduePatients = patients.value.filter(p => p.daysSinceAdmission > 7).length;
};
// 初始化图表
const initCharts = () => {
    // 风险分布图表
    if (riskChartRef.value) {
        const riskChart = echarts.init(riskChartRef.value);
        const riskData = [
            { name: '低风险', value: patients.value.filter(p => p.riskLevel === 'low').length },
            { name: '中风险', value: patients.value.filter(p => p.riskLevel === 'medium').length },
            { name: '高风险', value: patients.value.filter(p => p.riskLevel === 'high').length },
            { name: '严重风险', value: patients.value.filter(p => p.riskLevel === 'critical').length }
        ];
        riskChart.setOption({
            tooltip: { trigger: 'item' }, series: [{
                    type: 'pie', radius: '60%', data: riskData, itemStyle: {
                        color: (params) => {
                            const colors = ['#52c41a', '#faad14', '#ff7875', '#ff4d4f'];
                            return colors[params.dataIndex];
                        }
                    }
                }]
        });
    }
    // 科室分布图表
    if (departmentChartRef.value) {
        const deptChart = echarts.init(departmentChartRef.value);
        const deptData = departments.value.map(dept => ({
            name: dept,
            value: patients.value.filter(p => p.department === dept).length
        }));
        deptChart.setOption({
            tooltip: { trigger: 'item' },
            series: [{
                    type: 'pie',
                    radius: '60%',
                    data: deptData
                }]
        });
    }
};
// 辅助函数
const getRiskColor = (level) => {
    switch (level) {
        case 'low': return 'green';
        case 'medium': return 'orange';
        case 'high': return 'red';
        case 'critical': return 'red';
        default: return 'default';
    }
};
const getRiskText = (level) => {
    switch (level) {
        case 'low': return '低风险';
        case 'medium': return '中风险';
        case 'high': return '高风险';
        case 'critical': return '严重风险';
        default: return '未知';
    }
};
const getGradeColor = (grade) => {
    switch (grade) {
        case '甲级': return 'green';
        case '乙级': return 'orange';
        case '丙级': return 'red';
        default: return 'default';
    }
};
const getDaysColor = (days) => {
    if (days <= 3)
        return 'green';
    if (days <= 7)
        return 'orange';
    return 'red';
};
const getAlertColor = (level) => {
    switch (level) {
        case 'low': return 'default';
        case 'medium': return 'orange';
        case 'high': return 'red';
        case 'critical': return 'red';
        default: return 'default';
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "running-qc-dashboard" },
});
const __VLS_0 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    gutter: (24),
}));
const __VLS_2 = __VLS_1({
    gutter: (24),
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    span: (16),
}));
const __VLS_6 = __VLS_5({
    span: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    title: "在院病人运行质控",
    ...{ class: "mb-4" },
}));
const __VLS_10 = __VLS_9({
    title: "在院病人运行质控",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
{
    const { extra: __VLS_thisSlot } = __VLS_11.slots;
    const __VLS_12 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
    const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
    __VLS_15.slots.default;
    const __VLS_16 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.selectedDepartment),
        placeholder: "选择科室",
        ...{ style: {} },
    }));
    const __VLS_18 = __VLS_17({
        ...{ 'onChange': {} },
        value: (__VLS_ctx.selectedDepartment),
        placeholder: "选择科室",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    let __VLS_20;
    let __VLS_21;
    let __VLS_22;
    const __VLS_23 = {
        onChange: (__VLS_ctx.filterPatients)
    };
    __VLS_19.slots.default;
    const __VLS_24 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        value: "",
    }));
    const __VLS_26 = __VLS_25({
        value: "",
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_27.slots.default;
    var __VLS_27;
    for (const [dept] of __VLS_getVForSourceType((__VLS_ctx.departments))) {
        const __VLS_28 = {}.ASelectOption;
        /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
            key: (dept),
            value: (dept),
        }));
        const __VLS_30 = __VLS_29({
            key: (dept),
            value: (dept),
        }, ...__VLS_functionalComponentArgsRest(__VLS_29));
        __VLS_31.slots.default;
        (dept);
        var __VLS_31;
    }
    var __VLS_19;
    const __VLS_32 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_34 = __VLS_33({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    let __VLS_36;
    let __VLS_37;
    let __VLS_38;
    const __VLS_39 = {
        onClick: (__VLS_ctx.refreshPatients)
    };
    __VLS_35.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_35.slots;
        const __VLS_40 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({}));
        const __VLS_42 = __VLS_41({}, ...__VLS_functionalComponentArgsRest(__VLS_41));
    }
    var __VLS_35;
    var __VLS_15;
}
const __VLS_44 = {}.ATable;
/** @type {[typeof __VLS_components.ATable, typeof __VLS_components.aTable, typeof __VLS_components.ATable, typeof __VLS_components.aTable, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    columns: (__VLS_ctx.patientColumns),
    dataSource: (__VLS_ctx.filteredPatients),
    loading: (__VLS_ctx.loading),
    pagination: ({ pageSize: 10 }),
    rowKey: "id",
    size: "middle",
}));
const __VLS_46 = __VLS_45({
    columns: (__VLS_ctx.patientColumns),
    dataSource: (__VLS_ctx.filteredPatients),
    loading: (__VLS_ctx.loading),
    pagination: ({ pageSize: 10 }),
    rowKey: "id",
    size: "middle",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
{
    const { bodyCell: __VLS_thisSlot } = __VLS_47.slots;
    const [{ column, record }] = __VLS_getSlotParams(__VLS_thisSlot);
    if (column.key === 'riskLevel') {
        const __VLS_48 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
            color: (__VLS_ctx.getRiskColor(record.riskLevel)),
        }));
        const __VLS_50 = __VLS_49({
            color: (__VLS_ctx.getRiskColor(record.riskLevel)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_49));
        __VLS_51.slots.default;
        (__VLS_ctx.getRiskText(record.riskLevel));
        var __VLS_51;
    }
    if (column.key === 'grade') {
        const __VLS_52 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
            color: (__VLS_ctx.getGradeColor(record.grade)),
        }));
        const __VLS_54 = __VLS_53({
            color: (__VLS_ctx.getGradeColor(record.grade)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_53));
        __VLS_55.slots.default;
        (record.grade);
        var __VLS_55;
    }
    if (column.key === 'daysSinceAdmission') {
        const __VLS_56 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
            color: (__VLS_ctx.getDaysColor(record.daysSinceAdmission)),
        }));
        const __VLS_58 = __VLS_57({
            color: (__VLS_ctx.getDaysColor(record.daysSinceAdmission)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_57));
        __VLS_59.slots.default;
        (record.daysSinceAdmission);
        var __VLS_59;
    }
    if (column.key === 'actions') {
        const __VLS_60 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({}));
        const __VLS_62 = __VLS_61({}, ...__VLS_functionalComponentArgsRest(__VLS_61));
        __VLS_63.slots.default;
        const __VLS_64 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
            ...{ 'onClick': {} },
            type: "primary",
            size: "small",
            loading: (__VLS_ctx.analyzingPatients.includes(record.id)),
        }));
        const __VLS_66 = __VLS_65({
            ...{ 'onClick': {} },
            type: "primary",
            size: "small",
            loading: (__VLS_ctx.analyzingPatients.includes(record.id)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_65));
        let __VLS_68;
        let __VLS_69;
        let __VLS_70;
        const __VLS_71 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.analyzePatient(record);
            }
        };
        __VLS_67.slots.default;
        var __VLS_67;
        const __VLS_72 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_74 = __VLS_73({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        let __VLS_76;
        let __VLS_77;
        let __VLS_78;
        const __VLS_79 = {
            onClick: (...[$event]) => {
                if (!(column.key === 'actions'))
                    return;
                __VLS_ctx.viewDetails(record);
            }
        };
        __VLS_75.slots.default;
        var __VLS_75;
        var __VLS_63;
    }
}
var __VLS_47;
var __VLS_11;
var __VLS_7;
const __VLS_80 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
    span: (8),
}));
const __VLS_82 = __VLS_81({
    span: (8),
}, ...__VLS_functionalComponentArgsRest(__VLS_81));
__VLS_83.slots.default;
const __VLS_84 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    title: "实时统计",
    ...{ class: "mb-4" },
}));
const __VLS_86 = __VLS_85({
    title: "实时统计",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
const __VLS_88 = {}.ARow;
/** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
// @ts-ignore
const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
    gutter: (16),
}));
const __VLS_90 = __VLS_89({
    gutter: (16),
}, ...__VLS_functionalComponentArgsRest(__VLS_89));
__VLS_91.slots.default;
const __VLS_92 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    span: (12),
}));
const __VLS_94 = __VLS_93({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
const __VLS_96 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
    title: "在院病人",
    value: (__VLS_ctx.statistics.totalPatients),
    prefix: (__VLS_ctx.h(__VLS_ctx.UserOutlined)),
    ...{ style: {} },
}));
const __VLS_98 = __VLS_97({
    title: "在院病人",
    value: (__VLS_ctx.statistics.totalPatients),
    prefix: (__VLS_ctx.h(__VLS_ctx.UserOutlined)),
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_97));
var __VLS_95;
const __VLS_100 = {}.ACol;
/** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    span: (12),
}));
const __VLS_102 = __VLS_101({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
__VLS_103.slots.default;
const __VLS_104 = {}.AStatistic;
/** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    title: "高风险病人",
    value: (__VLS_ctx.statistics.highRiskPatients),
    prefix: (__VLS_ctx.h(__VLS_ctx.ExclamationCircleOutlined)),
    ...{ style: {} },
    valueStyle: ({ color: '#ff4d4f' }),
}));
const __VLS_106 = __VLS_105({
    title: "高风险病人",
    value: (__VLS_ctx.statistics.highRiskPatients),
    prefix: (__VLS_ctx.h(__VLS_ctx.ExclamationCircleOutlined)),
    ...{ style: {} },
    valueStyle: ({ color: '#ff4d4f' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
var __VLS_103;
var __VLS_91;
var __VLS_87;
const __VLS_108 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    title: "风险分布",
    ...{ class: "mb-4" },
}));
const __VLS_110 = __VLS_109({
    title: "风险分布",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "riskChartRef",
    ...{ style: {} },
});
/** @type {typeof __VLS_ctx.riskChartRef} */ ;
var __VLS_111;
const __VLS_112 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
    title: "科室分布",
    ...{ class: "mb-4" },
}));
const __VLS_114 = __VLS_113({
    title: "科室分布",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_113));
__VLS_115.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "departmentChartRef",
    ...{ style: {} },
});
/** @type {typeof __VLS_ctx.departmentChartRef} */ ;
var __VLS_115;
const __VLS_116 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
    title: "近期提醒",
    ...{ class: "mb-4" },
}));
const __VLS_118 = __VLS_117({
    title: "近期提醒",
    ...{ class: "mb-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_119.slots.default;
const __VLS_120 = {}.AList;
/** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
// @ts-ignore
const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
    dataSource: (__VLS_ctx.recentAlerts),
    size: "small",
    locale: ({ emptyText: '暂无提醒' }),
}));
const __VLS_122 = __VLS_121({
    dataSource: (__VLS_ctx.recentAlerts),
    size: "small",
    locale: ({ emptyText: '暂无提醒' }),
}, ...__VLS_functionalComponentArgsRest(__VLS_121));
__VLS_123.slots.default;
{
    const { renderItem: __VLS_thisSlot } = __VLS_123.slots;
    const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_124 = {}.AListItem;
    /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({}));
    const __VLS_126 = __VLS_125({}, ...__VLS_functionalComponentArgsRest(__VLS_125));
    __VLS_127.slots.default;
    const __VLS_128 = {}.AListItemMeta;
    /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({}));
    const __VLS_130 = __VLS_129({}, ...__VLS_functionalComponentArgsRest(__VLS_129));
    __VLS_131.slots.default;
    {
        const { title: __VLS_thisSlot } = __VLS_131.slots;
        const __VLS_132 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({}));
        const __VLS_134 = __VLS_133({}, ...__VLS_functionalComponentArgsRest(__VLS_133));
        __VLS_135.slots.default;
        const __VLS_136 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
            color: (__VLS_ctx.getAlertColor(item.level)),
        }));
        const __VLS_138 = __VLS_137({
            color: (__VLS_ctx.getAlertColor(item.level)),
        }, ...__VLS_functionalComponentArgsRest(__VLS_137));
        __VLS_139.slots.default;
        (item.level);
        var __VLS_139;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
        (item.patientName);
        var __VLS_135;
    }
    {
        const { description: __VLS_thisSlot } = __VLS_131.slots;
        (item.message);
    }
    var __VLS_131;
    {
        const { actions: __VLS_thisSlot } = __VLS_127.slots;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.a, __VLS_intrinsicElements.a)({
            ...{ onClick: (...[$event]) => {
                    __VLS_ctx.handleAlert(item);
                } },
        });
    }
    var __VLS_127;
}
var __VLS_123;
var __VLS_119;
var __VLS_83;
var __VLS_3;
const __VLS_140 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
    open: (__VLS_ctx.analysisModalVisible),
    title: "运行病历质控分析结果",
    width: "80%",
    footer: (null),
}));
const __VLS_142 = __VLS_141({
    open: (__VLS_ctx.analysisModalVisible),
    title: "运行病历质控分析结果",
    width: "80%",
    footer: (null),
}, ...__VLS_functionalComponentArgsRest(__VLS_141));
__VLS_143.slots.default;
if (__VLS_ctx.currentAnalysisResult) {
    const __VLS_144 = {}.RunningQcResult;
    /** @type {[typeof __VLS_components.RunningQcResult, typeof __VLS_components.runningQcResult, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        ...{ 'onClose': {} },
        result: (__VLS_ctx.currentAnalysisResult),
    }));
    const __VLS_146 = __VLS_145({
        ...{ 'onClose': {} },
        result: (__VLS_ctx.currentAnalysisResult),
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    let __VLS_148;
    let __VLS_149;
    let __VLS_150;
    const __VLS_151 = {
        onClose: (...[$event]) => {
            if (!(__VLS_ctx.currentAnalysisResult))
                return;
            __VLS_ctx.analysisModalVisible = false;
        }
    };
    var __VLS_147;
}
var __VLS_143;
/** @type {__VLS_StyleScopedClasses['running-qc-dashboard']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            h: vue_1.h,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            UserOutlined: icons_vue_1.UserOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            loading: loading,
            selectedDepartment: selectedDepartment,
            analyzingPatients: analyzingPatients,
            analysisModalVisible: analysisModalVisible,
            currentAnalysisResult: currentAnalysisResult,
            filteredPatients: filteredPatients,
            departments: departments,
            recentAlerts: recentAlerts,
            statistics: statistics,
            riskChartRef: riskChartRef,
            departmentChartRef: departmentChartRef,
            patientColumns: patientColumns,
            refreshPatients: refreshPatients,
            filterPatients: filterPatients,
            analyzePatient: analyzePatient,
            viewDetails: viewDetails,
            handleAlert: handleAlert,
            getRiskColor: getRiskColor,
            getRiskText: getRiskText,
            getGradeColor: getGradeColor,
            getDaysColor: getDaysColor,
            getAlertColor: getAlertColor,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
