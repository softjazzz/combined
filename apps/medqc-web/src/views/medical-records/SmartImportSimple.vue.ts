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
import vue_router_1 from 'vue-router';
import ant_design_vue_1 from 'ant-design-vue';
import icons_vue_1 from '@ant-design/icons-vue';
const LLMApiConfig_vue_1 = __importDefault(require("@/components/LLMApiConfig.vue"));
const router = (0, vue_router_1.useRouter)();
const showLLMConfig = (0, vue_1.ref)(false);
// 响应式数据
const activeTab = (0, vue_1.ref)('text');
const inputText = (0, vue_1.ref)('');
const parsing = (0, vue_1.ref)(false);
const importing = (0, vue_1.ref)(false);
const parseResult = (0, vue_1.ref)(null);
const operationLog = (0, vue_1.ref)('系统已就绪');
const uploadedFiles = (0, vue_1.ref)(: any[]);
const llmParsing = (0, vue_1.ref)(false);
const batchParsing = (0, vue_1.ref)(false);
const mergedResults = (0, vue_1.ref)(null); // 存储合并后的多文档结果
const activeDocumentTypes = (0, vue_1.ref)(: any[]); // 控制文档分类折叠面板
// 结果显示的兼容性处理
const displayPatientName = (0, vue_1.computed)(() => {
    if (!parseResult.value)
        return '未识别';
    const d = parseResult.value.data || {};
    return d.patientName || d.patient_name || (d.medical_info && d.medical_info.patientName) || '未识别';
});
const displayDepartment = (0, vue_1.computed)(() => {
    if (!parseResult.value)
        return '未识别';
    const d = parseResult.value.data || {};
    return d.department || (d.medical_info && d.medical_info.department) || '未识别';
});
const displayPrimaryDiagnosis = (0, vue_1.computed)(() => {
    if (!parseResult.value)
        return '未识别';
    const d = parseResult.value.data || {};
    return d.primaryDiagnosis || d.diagnosis_primary || (d.medical_info && (d.medical_info.primaryDiagnosis || (Array.isArray(d.medical_info.diagnosis) ? d.medical_info.diagnosis[0] : ''))) || '未识别';
});
// 解析成功后自动切换结果标签
(0, vue_1.watch)(parseResult: any,  (val: any) => {
    if (val && val.success) {
        activeTab.value = 'result';
    }
});
// 文本解析
const parseText = async () => {
    if (!inputText.value.trim()) {
        ant_design_vue_1.message.warning('请输入文本内容');
        return;
    }
    parsing.value = true;
    operationLog.value += '\n开始解析文本...';
    try {
        const response = await fetch('/api/parse-medical-text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: inputText.value })
        });
        if (!response.ok) {
            throw new Error('解析请求失败');
        }
        const result = await response.json();
        if (result.success) {
            parseResult.value = result;
            operationLog.value += '\n解析完成';
            ant_design_vue_1.message.success('文本解析成功');
            activeTab.value = 'result';
        }
        else {
            throw new Error(result.error || '解析失败');
        }
    }
    catch (error) {
        operationLog.value += '\n解析失败: ' + error.message;
        ant_design_vue_1.message.error('解析失败: ' + error.message);
    }
    finally {
        parsing.value = false;
    }
};
// 清空文本
const clearText = () => {
    inputText.value = '';
    parseResult.value = null;
    operationLog.value += '\n已清空文本';
};
// 删除文件
const removeFile = (index) => {
    const fileObj = uploadedFiles.value[index];
    if (!fileObj)
        return;
    if (fileObj.parsing) {
        ant_design_vue_1.message.warning('正在解析的文件无法删除');
        return;
    }
    uploadedFiles.value.splice(index, 1);
    operationLog.value += `\n已删除文件: ${fileObj.name}`;
};
// 文件上传前检查
const beforeUpload = (file) => {
    console.log(`[${new Date().toLocaleTimeString()}] beforeUpload 被调用: ${file.name}`);
    const isValidType = [
        'application/pdf',
        'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ].includes(file.type) ||
        file.name.match(/\.(pdf|txt|doc|docx)$/i);
    if (!isValidType) {
        ant_design_vue_1.message.error('只支持 PDF、Word、文本文件');
        return false;
    }
    // 检查文件大小 (10MB限制)
    if (file.size > 10 * 1024 * 1024) {
        ant_design_vue_1.message.error('文件大小不能超过10MB');
        return false;
    }
    console.log(`[${new Date().toLocaleTimeString()}] 文件验证通过: ${file.name}`);
    return false; // 阻止自动上传，我们手动处理
};
// 处理文件上传变化
const handleUploadChange = (info) => {
    console.log(`[${new Date().toLocaleTimeString()}] handleUploadChange 被调用, 文件数量: ${info.fileList.length}`);
    // 过滤出新添加的文件
    const newFiles = info.fileList.filter(fileItem => {
        const exists = uploadedFiles.value.some(existing => existing.name === fileItem.name && existing.size === fileItem.size);
        return !exists;
    });
    // 添加新文件到列表
    newFiles.forEach(fileItem => {
        const fileObj = {
            name: fileItem.name,
            size: fileItem.size,
            type: fileItem.type || 'application/pdf',
            file: fileItem.originFileObj || fileItem,
            parsing: false,
            parsed: false,
            uploadTime: new Date().toLocaleString()
        };
        uploadedFiles.value.push(fileObj);
        console.log(`[${new Date().toLocaleTimeString()}] 添加新文件: ${fileObj.name}`);
    });
    operationLog.value += `\n多文件上传完成已加载: ${newFiles.length} 个文件`;
};
// 格式化文件大小
const formatFileSize = (bytes) => {
    if (bytes === 0)
        return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};
// 批量解析所有文件
const parseAllFiles = async () => {
    if (uploadedFiles.value.length === 0) {
        ant_design_vue_1.message.warning('请先上传文件');
        return;
    }
    batchParsing.value = true;
    operationLog.value += `\n开始批量解析 ${uploadedFiles.value.length} 个文件...`;
    const allResults = [];
    let successCount = 0;
    let failCount = 0;
    try {
        for (let i = 0; i < uploadedFiles.value.length; i++) {
            const fileObj = uploadedFiles.value[i];
            if (!fileObj.parsed) {
                operationLog.value += `\n正在解析文件 ${i + 1}/${uploadedFiles.value.length}: ${fileObj.name}`;
                try {
                    await parseFileSilent(i); // 使用静默解析，不切换到结果页
                    if (fileObj.result && fileObj.result.success) {
                        // 为每个文档添加来源信息
                        const resultWithSource = {
                            ...fileObj.result,
                            sourceFile: fileObj.name,
                            sourceIndex: i,
                            documentType: classifyDocument(fileObj.name),
                            parseTime: new Date().toLocaleString()
                        };
                        allResults.push(resultWithSource);
                        successCount++;
                        operationLog.value += `\n✓ ${fileObj.name} 解析成功`;
                    }
                    else {
                        failCount++;
                        operationLog.value += `\n✗ ${fileObj.name} 解析失败`;
                    }
                }
                catch (error) {
                    failCount++;
                    operationLog.value += `\n✗ ${fileObj.name} 解析失败: ${error.message}`;
                }
                // 添加延迟避免请求过快
                await new Promise(resolve => setTimeout(resolve, 1000));
            }
            else {
                // 文件已解析，直接添加到结果中
                if (fileObj.result && fileObj.result.success) {
                    const resultWithSource = {
                        ...fileObj.result,
                        sourceFile: fileObj.name,
                        sourceIndex: i,
                        documentType: classifyDocument(fileObj.name),
                        parseTime: fileObj.parseTime || new Date().toLocaleString()
                    };
                    allResults.push(resultWithSource);
                    successCount++;
                }
            }
        }
        // 合并所有解析结果
        if (allResults.length > 0) {
            mergedResults.value = mergeMultipleResults(allResults);
            parseResult.value = mergedResults.value; // 设置为合并结果以便显示
            activeTab.value = 'result';
            operationLog.value += `\n批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`;
            ant_design_vue_1.message.success(`批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`);
        }
        else {
            ant_design_vue_1.message.warning('没有成功解析的文件');
            operationLog.value += `\n批量解析完成，但没有成功解析的文件`;
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('批量解析过程中出现错误');
        operationLog.value += `\n批量解析错误: ${error.message}`;
    }
    finally {
        batchParsing.value = false;
    }
};
// 清空所有文件
const clearAllFiles = () => {
    uploadedFiles.value = [];
    parseResult.value = null;
    mergedResults.value = null;
    operationLog.value += `\n已清空所有文件`;
    ant_design_vue_1.message.info('已清空所有文件');
};
// 文档类型分类
const classifyDocument = (fileName) => {
    const name = fileName.toLowerCase();
    if (name.includes('病程') || name.includes('病历'))
        return '病程记录';
    if (name.includes('手术') || name.includes('术后'))
        return '手术记录';
    if (name.includes('检查') || name.includes('检验'))
        return '检查报告';
    if (name.includes('诊断') || name.includes('诊疗'))
        return '诊断记录';
    if (name.includes('护理'))
        return '护理记录';
    if (name.includes('出院') || name.includes('小结'))
        return '出院记录';
    if (name.includes('入院'))
        return '入院记录';
    return '其他文档';
};
// 静默解析文件（不切换到结果页）
const parseFileSilent = async (index) => {
    const fileObj = uploadedFiles.value[index];
    if (!fileObj)
        return;
    fileObj.parsing = true;
    try {
        const formData = new FormData();
        formData.append('file', fileObj.file);
        formData.append('options', '{}');
        const response = await fetch('/api/parse-medical-file-public', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error('文件解析请求失败');
        }
        const result = await response.json();
        if (result.success) {
            fileObj.parsed = true;
            fileObj.result = result;
            fileObj.parseTime = new Date().toLocaleString();
            // 注意：这里不设置 parseResult.value，避免切换到结果页
        }
        else {
            throw new Error(result.error || '解析失败');
        }
    }
    finally {
        fileObj.parsing = false;
    }
};
// 合并多个解析结果
const mergeMultipleResults = (results) => {
    if (results.length === 0)
        return null;
    if (results.length === 1)
        return results[0];
    // 收集所有患者信息，取最完整的
    const allPatientNames = results.map(r => r.data?.patientName).filter(Boolean);
    const allDepartments = results.map(r => r.data?.department).filter(Boolean);
    const allDiagnoses = results.map(r => r.data?.primaryDiagnosis).filter(Boolean);
    // 按文档类型分组
    const documentsByType = {};
    const allDocuments = [];
    results.forEach((result, index) => {
        const docType = result.documentType;
        const sourceFile = result.sourceFile;
        if (!documentsByType[docType]) {
            documentsByType[docType] = [];
        }
        // 创建符合 ExtractedDocument 接口的文档对象
        const docInfo = {
            id: `doc_${index}`,
            type: mapDocumentType(docType), // 映射到标准文档类型
            title: `${sourceFile} - ${docType}`,
            content: result.data?.content || '',
            confidence: result.data?.confidence || 0.8,
            extractedAt: new Date().toISOString(),
            position: {
                startIndex: 0,
                endIndex: (result.data?.content || '').length,
                fullContent: result.data?.content || ''
            },
            metadata: {
                sourceFile: sourceFile,
                parseTime: result.parseTime,
                method: result.data?.method || '文件解析',
                pages: result.data?.pages || 1
            }
        };
        documentsByType[docType].push(docInfo);
        allDocuments.push(docInfo);
    });
    // 合并内容
    const mergedContent = results.map(r => {
        const content = r.data?.content || '';
        return `=== ${r.sourceFile} (${r.documentType}) ===\n${content}\n`;
    }).join('\n');
    return {
        success: true,
        data: {
            patientName: allPatientNames[0] || '未识别',
            department: allDepartments[0] || '未识别',
            primaryDiagnosis: allDiagnoses[0] || '未识别',
            content: mergedContent,
            method: '批量文件解析',
            pages: results.reduce((sum, r) => sum + (r.data?.pages || 1), 0),
            documents: allDocuments, // 符合 ExtractedDocument[] 格式
            documentsByType: documentsByType,
            sourceFiles: results.map(r => r.sourceFile),
            totalFiles: results.length,
            confidence: results.reduce((sum, r) => sum + (r.data?.confidence || 0.8), 0) / results.length
        },
        isMerged: true,
        mergeTime: new Date().toLocaleString()
    };
};
// 映射文档类型到标准类型
const mapDocumentType = (docType) => {
    const typeMapping = {
        '手术记录': 'operation_record',
        '入院记录': 'admission_record',
        '病程记录': 'progress_note',
        '出院记录': 'discharge_record',
        '检验报告': 'auxiliary_examination',
        '检查报告': 'auxiliary_examination',
        '知情同意书': 'informed_consent',
        '医嘱': 'medical_order',
        '护理记录': 'nursing_record'
    };
    return typeMapping[docType] || 'other';
};
// 查看单个文档结果
const showIndividualResults = () => {
    if (!parseResult.value?.isMerged)
        return;
    // 展开所有文档分类
    const types = Object.keys(parseResult.value.data.documentsByType || {});
    activeDocumentTypes.value = types;
    ant_design_vue_1.message.info('已展开所有文档分类，您可以查看每个文档的详细内容');
};
// 处理文件上传
const handleFileUpload = async (options) => {
    const { file } = options;
    const fileObj = {
        name: file.name,
        size: file.size,
        type: file.type,
        file: file,
        parsing: false,
        parsed: false,
        result: null
    };
    uploadedFiles.value.push(fileObj);
    operationLog.value += '\n文件已添加: ' + file.name;
    ant_design_vue_1.message.success('文件上传成功');
};
// 解析文件
const parseFile = async (index) => {
    const fileObj = uploadedFiles.value[index];
    if (!fileObj)
        return;
    fileObj.parsing = true;
    operationLog.value += '\n开始解析文件: ' + fileObj.name;
    try {
        const formData = new FormData();
        formData.append('file', fileObj.file);
        formData.append('options', '{}');
        const response = await fetch('/api/parse-medical-file-public', {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error('文件解析请求失败');
        }
        const result = await response.json();
        if (result.success) {
            fileObj.parsed = true;
            fileObj.result = result;
            parseResult.value = result;
            operationLog.value += '\n文件解析完成';
            ant_design_vue_1.message.success('文件解析成功');
            activeTab.value = 'result';
        }
        else {
            throw new Error(result.error || '解析失败');
        }
    }
    catch (error) {
        operationLog.value += '\n文件解析失败: ' + error.message;
        ant_design_vue_1.message.error('解析失败: ' + error.message);
    }
    finally {
        fileObj.parsing = false;
    }
};
// 导入数据库
const importToDatabase = async () => {
    if (!parseResult.value) {
        ant_design_vue_1.message.warning('没有可导入的数据');
        return;
    }
    importing.value = true;
    operationLog.value += '\n开始导入数据库...';
    try {
        const response = await fetch('/api/medical-records', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                patient_name: parseResult.value.data.patientName || '未知',
                department: parseResult.value.data.department || '未知',
                diagnosis_primary: parseResult.value.data.primaryDiagnosis || '未知',
                content: parseResult.value.data.content || '',
                source: 'smart_import'
            })
        });
        if (!response.ok) {
            throw new Error('导入请求失败');
        }
        const result = await response.json();
        operationLog.value += '\n导入成功，记录ID: ' + result.id;
        ant_design_vue_1.message.success('导入数据库成功');
    }
    catch (error) {
        operationLog.value += '\n导入失败: ' + error.message;
        ant_design_vue_1.message.error('导入失败: ' + error.message);
    }
    finally {
        importing.value = false;
    }
};
// 导出结果
const exportResult = () => {
    if (!parseResult.value) {
        ant_design_vue_1.message.warning('没有可导出的结果');
        return;
    }
    const dataStr = JSON.stringify(parseResult.value, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    // 接收LLM配置更新（可用于更新 llmService 的运行时配置）
    const onLLMConfigUpdated = (configData) => {
        operationLog.value += '\nLLM 配置已更新';
    };
    const url = URL.createObjectURL(dataBlob);
    if (typeof document !== 'undefined') {
        const link = document.createElement('a');
        link.href = url;
        link.download = 'parse_result_' + new Date().getTime() + '.json';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }
    URL.revokeObjectURL(url);
    operationLog.value += '\n结果已导出';
    ant_design_vue_1.message.success('结果导出成功');
};
// LLM 精准解析（复用 llmService）
const preciseLLMParse = async () => {
    if (!(parseResult.value && parseResult.value.data && parseResult.value.data.content)) {
        ant_design_vue_1.message.warning('请先完成基础解析，确保有可用的文本内容');
        return;
    }
    llmParsing.value = true;
    operationLog.value += '\n开始 LLM 精准解析...';
    try {
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        // 在使用前确保加载默认配置
        await llmService.loadConfigFromDatabase('default');
        // 直接复用 llmService 的文本抽取能力
        const result = await llmService.extractMedicalData(parseResult.value.data.content, {
            extractPatientInfo: true,
            extractDiagnosis: true,
            classifyDocuments: true,
            confidenceThreshold: 0.7
        });
        if (result && result.success) {
            // 合并结果，保留原始内容与来源方法
            const original = parseResult.value;
            const merged = {
                success: true,
                data: {
                    ...result.data,
                    content: original.data?.content || '',
                    method: 'LLM 精准解析',
                    // 保留多文档相关信息
                    ...(original.isMerged && {
                        sourceFiles: original.data?.sourceFiles,
                        totalFiles: original.data?.totalFiles,
                        documentsByType: original.data?.documentsByType
                    })
                },
                tokensUsed: result.tokensUsed,
                processingTime: result.processingTime,
                // 保留合并标识
                isMerged: original.isMerged,
                mergeTime: original.mergeTime
            };
            parseResult.value = merged;
            // 写入store并跳转到统一结果页
            const { useLLMParseStore } = await Promise.resolve().then(() => __importStar(require('@/stores/llmParse')));
            const store = useLLMParseStore();
            store.setResult(merged);
            await router.push('/dashboard/llm-result');
            ant_design_vue_1.message.success('LLM 精准解析成功');
            operationLog.value += '\nLLM 精准解析成功';
            activeTab.value = 'result';
        }
        else {
            throw new Error((result && result.error) || 'LLM 解析失败');
        }
    }
    catch (e) {
        console.error('LLM精准解析失败:', e);
        ant_design_vue_1.message.error('LLM精准解析失败: ' + (e.message || e));
        operationLog.value += '\nLLM精准解析失败: ' + (e.message || e);
    }
    finally {
        llmParsing.value = false;
    }
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['document-item']} */ ;
/** @type {__VLS_StyleScopedClasses['document-header']} */ ;
/** @type {__VLS_StyleScopedClasses['source-files']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "smart-import-container" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-left" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-right" },
});
const __VLS_0 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onClick': {} },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showLLMConfig = true;
    }
};
__VLS_3.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.SettingOutlined;
    /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
    const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
}
var __VLS_3;
const __VLS_12 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "import-tabs" },
}));
const __VLS_14 = __VLS_13({
    activeKey: (__VLS_ctx.activeTab),
    ...{ class: "import-tabs" },
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
const __VLS_16 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    key: "text",
    tab: "文本输入",
}));
const __VLS_18 = __VLS_17({
    key: "text",
    tab: "文本输入",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "text-input-section" },
});
const __VLS_20 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    value: (__VLS_ctx.inputText),
    placeholder: "请输入医疗记录文本...",
    rows: (8),
    ...{ class: "mb-3" },
}));
const __VLS_22 = __VLS_21({
    value: (__VLS_ctx.inputText),
    placeholder: "请输入医疗记录文本...",
    rows: (8),
    ...{ class: "mb-3" },
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "action-buttons" },
});
const __VLS_24 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.parsing),
}));
const __VLS_26 = __VLS_25({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.parsing),
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onClick: (__VLS_ctx.parseText)
};
__VLS_27.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_27.slots;
    const __VLS_32 = {}.ThunderboltOutlined;
    /** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({}));
    const __VLS_34 = __VLS_33({}, ...__VLS_functionalComponentArgsRest(__VLS_33));
}
var __VLS_27;
const __VLS_36 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onClick': {} },
}));
const __VLS_38 = __VLS_37({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onClick: (__VLS_ctx.clearText)
};
__VLS_39.slots.default;
var __VLS_39;
var __VLS_19;
const __VLS_44 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    key: "upload",
    tab: "文件上传",
}));
const __VLS_46 = __VLS_45({
    key: "upload",
    tab: "文件上传",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "upload-section" },
});
const __VLS_48 = {}.AUploadDragger;
/** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onChange': {} }, fileList: (: any[]),
    beforeUpload: (__VLS_ctx.beforeUpload),
    showUploadList: (false),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
}));
const __VLS_50 = __VLS_49({
    ...{ 'onChange': {} }, fileList: (: any[]),
    beforeUpload: (__VLS_ctx.beforeUpload),
    showUploadList: (false),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onChange: (__VLS_ctx.handleUploadChange)
};
__VLS_51.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-drag-icon" },
});
const __VLS_56 = {}.InboxOutlined;
/** @type {[typeof __VLS_components.InboxOutlined, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-hint" },
});
var __VLS_51;
if (__VLS_ctx.uploadedFiles.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-list" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "file-list-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    (__VLS_ctx.uploadedFiles.length);
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
        loading: (__VLS_ctx.batchParsing),
    }));
    const __VLS_66 = __VLS_65({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.batchParsing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    let __VLS_68;
    let __VLS_69;
    let __VLS_70;
    const __VLS_71 = {
        onClick: (__VLS_ctx.parseAllFiles)
    };
    __VLS_67.slots.default;
    var __VLS_67;
    const __VLS_72 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ 'onClick': {} },
        danger: true,
    }));
    const __VLS_74 = __VLS_73({
        ...{ 'onClick': {} },
        danger: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    let __VLS_76;
    let __VLS_77;
    let __VLS_78;
    const __VLS_79 = {
        onClick: (__VLS_ctx.clearAllFiles)
    };
    __VLS_75.slots.default;
    var __VLS_75;
    var __VLS_63;
    const __VLS_80 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        dataSource: (__VLS_ctx.uploadedFiles),
        size: "small",
    }));
    const __VLS_82 = __VLS_81({
        dataSource: (__VLS_ctx.uploadedFiles),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_83.slots;
        const [{ item, index }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_84 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
        const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
        __VLS_87.slots.default;
        {
            const { actions: __VLS_thisSlot } = __VLS_87.slots;
            const __VLS_88 = {}.ASpace;
            /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
            // @ts-ignore
            const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
            const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
            __VLS_91.slots.default;
            const __VLS_92 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
                ...{ 'onClick': {} },
                size: "small",
                loading: (item.parsing),
                disabled: (item.parsed),
            }));
            const __VLS_94 = __VLS_93({
                ...{ 'onClick': {} },
                size: "small",
                loading: (item.parsing),
                disabled: (item.parsed),
            }, ...__VLS_functionalComponentArgsRest(__VLS_93));
            let __VLS_96;
            let __VLS_97;
            let __VLS_98;
            const __VLS_99 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.uploadedFiles.length > 0))
                        return;
                    __VLS_ctx.parseFile(index);
                }
            };
            __VLS_95.slots.default;
            (item.parsed ? '已解析' : '解析');
            var __VLS_95;
            const __VLS_100 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
                ...{ 'onClick': {} },
                size: "small",
                danger: true,
            }));
            const __VLS_102 = __VLS_101({
                ...{ 'onClick': {} },
                size: "small",
                danger: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_101));
            let __VLS_104;
            let __VLS_105;
            let __VLS_106;
            const __VLS_107 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.uploadedFiles.length > 0))
                        return;
                    __VLS_ctx.removeFile(index);
                }
            };
            __VLS_103.slots.default;
            var __VLS_103;
            var __VLS_91;
        }
        const __VLS_108 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({}));
        const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
        __VLS_111.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_111.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-title" },
            });
            const __VLS_112 = {}.FileOutlined;
            /** @type {[typeof __VLS_components.FileOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
                ...{ class: "file-icon" },
            }));
            const __VLS_114 = __VLS_113({
                ...{ class: "file-icon" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_113));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.name);
            if (item.parsed) {
                const __VLS_116 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
                    color: "success",
                    size: "small",
                }));
                const __VLS_118 = __VLS_117({
                    color: "success",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_117));
                __VLS_119.slots.default;
                var __VLS_119;
            }
            else if (item.parsing) {
                const __VLS_120 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
                    color: "processing",
                    size: "small",
                }));
                const __VLS_122 = __VLS_121({
                    color: "processing",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_121));
                __VLS_123.slots.default;
                var __VLS_123;
            }
            else {
                const __VLS_124 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
                    color: "default",
                    size: "small",
                }));
                const __VLS_126 = __VLS_125({
                    color: "default",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_125));
                __VLS_127.slots.default;
                var __VLS_127;
            }
        }
        {
            const { description: __VLS_thisSlot } = __VLS_111.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "file-details" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (__VLS_ctx.formatFileSize(item.size));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            (item.type);
            if (item.uploadTime) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
                (item.uploadTime);
            }
        }
        var __VLS_111;
        var __VLS_87;
    }
    var __VLS_83;
}
var __VLS_47;
const __VLS_128 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
    key: "result",
    tab: "解析结果",
    disabled: (!__VLS_ctx.parseResult),
}));
const __VLS_130 = __VLS_129({
    key: "result",
    tab: "解析结果",
    disabled: (!__VLS_ctx.parseResult),
}, ...__VLS_functionalComponentArgsRest(__VLS_129));
__VLS_131.slots.default;
if (__VLS_ctx.parseResult && __VLS_ctx.parseResult.success) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-section" },
    });
    const __VLS_132 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        title: "解析结果概览",
        bordered: true,
    }));
    const __VLS_134 = __VLS_133({
        title: "解析结果概览",
        bordered: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    __VLS_135.slots.default;
    const __VLS_136 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
        label: "患者姓名",
    }));
    const __VLS_138 = __VLS_137({
        label: "患者姓名",
    }, ...__VLS_functionalComponentArgsRest(__VLS_137));
    __VLS_139.slots.default;
    (__VLS_ctx.displayPatientName);
    var __VLS_139;
    const __VLS_140 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
        label: "科室",
    }));
    const __VLS_142 = __VLS_141({
        label: "科室",
    }, ...__VLS_functionalComponentArgsRest(__VLS_141));
    __VLS_143.slots.default;
    (__VLS_ctx.displayDepartment);
    var __VLS_143;
    const __VLS_144 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
        label: "主要诊断",
    }));
    const __VLS_146 = __VLS_145({
        label: "主要诊断",
    }, ...__VLS_functionalComponentArgsRest(__VLS_145));
    __VLS_147.slots.default;
    (__VLS_ctx.displayPrimaryDiagnosis);
    var __VLS_147;
    const __VLS_148 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
        label: "解析方法",
    }));
    const __VLS_150 = __VLS_149({
        label: "解析方法",
    }, ...__VLS_functionalComponentArgsRest(__VLS_149));
    __VLS_151.slots.default;
    ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.method) || '未知');
    var __VLS_151;
    const __VLS_152 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
        label: "页数",
    }));
    const __VLS_154 = __VLS_153({
        label: "页数",
    }, ...__VLS_functionalComponentArgsRest(__VLS_153));
    __VLS_155.slots.default;
    ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.pages) || 1);
    var __VLS_155;
    if (__VLS_ctx.parseResult.isMerged) {
        const __VLS_156 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
            label: "文档数量",
        }));
        const __VLS_158 = __VLS_157({
            label: "文档数量",
        }, ...__VLS_functionalComponentArgsRest(__VLS_157));
        __VLS_159.slots.default;
        (__VLS_ctx.parseResult.data.totalFiles);
        var __VLS_159;
    }
    if (__VLS_ctx.parseResult.isMerged) {
        const __VLS_160 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
            label: "合并时间",
        }));
        const __VLS_162 = __VLS_161({
            label: "合并时间",
        }, ...__VLS_functionalComponentArgsRest(__VLS_161));
        __VLS_163.slots.default;
        (__VLS_ctx.parseResult.mergeTime);
        var __VLS_163;
    }
    var __VLS_135;
    if (__VLS_ctx.parseResult.isMerged && __VLS_ctx.parseResult.data.documentsByType) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "documents-by-type" },
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        const __VLS_164 = {}.ACollapse;
        /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
            activeKey: (__VLS_ctx.activeDocumentTypes),
            ghost: true,
        }));
        const __VLS_166 = __VLS_165({
            activeKey: (__VLS_ctx.activeDocumentTypes),
            ghost: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_165));
        __VLS_167.slots.default;
        for (const [docs, type] of __VLS_getVForSourceType((__VLS_ctx.parseResult.data.documentsByType))) {
            const __VLS_168 = {}.ACollapsePanel;
            /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
            // @ts-ignore
            const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({
                key: (type),
                header: (`${type} (${docs.length}个文档)`),
            }));
            const __VLS_170 = __VLS_169({
                key: (type),
                header: (`${type} (${docs.length}个文档)`),
            }, ...__VLS_functionalComponentArgsRest(__VLS_169));
            __VLS_171.slots.default;
            for (const [doc] of __VLS_getVForSourceType((docs))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (doc.id),
                    ...{ class: "document-item" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    ...{ class: "document-header" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({});
                (doc.title);
                const __VLS_172 = {}.ASpace;
                /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
                // @ts-ignore
                const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({}));
                const __VLS_174 = __VLS_173({}, ...__VLS_functionalComponentArgsRest(__VLS_173));
                __VLS_175.slots.default;
                const __VLS_176 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({
                    color: "blue",
                }));
                const __VLS_178 = __VLS_177({
                    color: "blue",
                }, ...__VLS_functionalComponentArgsRest(__VLS_177));
                __VLS_179.slots.default;
                (doc.type);
                var __VLS_179;
                const __VLS_180 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({
                    color: "green",
                }));
                const __VLS_182 = __VLS_181({
                    color: "green",
                }, ...__VLS_functionalComponentArgsRest(__VLS_181));
                __VLS_183.slots.default;
                (Math.round(doc.confidence * 100));
                var __VLS_183;
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "parse-time" },
                });
                (doc.parseTime);
                var __VLS_175;
                const __VLS_184 = {}.ATextarea;
                /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
                // @ts-ignore
                const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
                    value: (doc.content),
                    rows: (6),
                    readonly: true,
                    ...{ class: "document-content" },
                    ...{ style: {} },
                }));
                const __VLS_186 = __VLS_185({
                    value: (doc.content),
                    rows: (6),
                    readonly: true,
                    ...{ class: "document-content" },
                    ...{ style: {} },
                }, ...__VLS_functionalComponentArgsRest(__VLS_185));
            }
            var __VLS_171;
        }
        var __VLS_167;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "content-preview" },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    (__VLS_ctx.parseResult.isMerged ? '合并内容预览' : '内容预览');
    if (__VLS_ctx.parseResult.isMerged) {
        const __VLS_188 = {}.ATooltip;
        /** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
        // @ts-ignore
        const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
            title: "显示所有文档的合并内容",
        }));
        const __VLS_190 = __VLS_189({
            title: "显示所有文档的合并内容",
        }, ...__VLS_functionalComponentArgsRest(__VLS_189));
        __VLS_191.slots.default;
        const __VLS_192 = {}.InfoCircleOutlined;
        /** @type {[typeof __VLS_components.InfoCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
            ...{ style: {} },
        }));
        const __VLS_194 = __VLS_193({
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_193));
        var __VLS_191;
    }
    const __VLS_196 = {}.ATextarea;
    /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
        value: ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.content) || ''),
        rows: (12),
        readonly: true,
        ...{ class: "content-textarea" },
    }));
    const __VLS_198 = __VLS_197({
        value: ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.content) || ''),
        rows: (12),
        readonly: true,
        ...{ class: "content-textarea" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_197));
    if (__VLS_ctx.parseResult.isMerged && __VLS_ctx.parseResult.data.sourceFiles) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "source-files" },
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h5, __VLS_intrinsicElements.h5)({});
        const __VLS_200 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({
            wrap: true,
        }));
        const __VLS_202 = __VLS_201({
            wrap: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_201));
        __VLS_203.slots.default;
        for (const [file, index] of __VLS_getVForSourceType((__VLS_ctx.parseResult.data.sourceFiles))) {
            const __VLS_204 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
                key: (index),
                color: "processing",
            }));
            const __VLS_206 = __VLS_205({
                key: (index),
                color: "processing",
            }, ...__VLS_functionalComponentArgsRest(__VLS_205));
            __VLS_207.slots.default;
            (file);
            var __VLS_207;
        }
        var __VLS_203;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "result-actions" },
        ...{ style: {} },
    });
    const __VLS_208 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.importing),
    }));
    const __VLS_210 = __VLS_209({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.importing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
    let __VLS_212;
    let __VLS_213;
    let __VLS_214;
    const __VLS_215 = {
        onClick: (__VLS_ctx.importToDatabase)
    };
    __VLS_211.slots.default;
    (__VLS_ctx.parseResult.isMerged ? '批量导入数据库' : '导入数据库');
    var __VLS_211;
    const __VLS_216 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.llmParsing),
        type: "dashed",
    }));
    const __VLS_218 = __VLS_217({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.llmParsing),
        type: "dashed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_217));
    let __VLS_220;
    let __VLS_221;
    let __VLS_222;
    const __VLS_223 = {
        onClick: (__VLS_ctx.preciseLLMParse)
    };
    __VLS_219.slots.default;
    var __VLS_219;
    const __VLS_224 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({
        ...{ 'onClick': {} },
    }));
    const __VLS_226 = __VLS_225({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_225));
    let __VLS_228;
    let __VLS_229;
    let __VLS_230;
    const __VLS_231 = {
        onClick: (__VLS_ctx.exportResult)
    };
    __VLS_227.slots.default;
    (__VLS_ctx.parseResult.isMerged ? '导出合并结果' : '导出结果');
    var __VLS_227;
    if (__VLS_ctx.parseResult.isMerged) {
        const __VLS_232 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
            ...{ 'onClick': {} },
            type: "default",
        }));
        const __VLS_234 = __VLS_233({
            ...{ 'onClick': {} },
            type: "default",
        }, ...__VLS_functionalComponentArgsRest(__VLS_233));
        let __VLS_236;
        let __VLS_237;
        let __VLS_238;
        const __VLS_239 = {
            onClick: (__VLS_ctx.showIndividualResults)
        };
        __VLS_235.slots.default;
        var __VLS_235;
    }
}
var __VLS_131;
var __VLS_15;
const __VLS_240 = {}.ADrawer;
/** @type {[typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, typeof __VLS_components.ADrawer, typeof __VLS_components.aDrawer, ]} */ ;
// @ts-ignore
const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({
    open: (__VLS_ctx.showLLMConfig),
    title: "LLM 配置",
    width: "720px",
}));
const __VLS_242 = __VLS_241({
    open: (__VLS_ctx.showLLMConfig),
    title: "LLM 配置",
    width: "720px",
}, ...__VLS_functionalComponentArgsRest(__VLS_241));
__VLS_243.slots.default;
/** @type {[typeof LLMApiConfig, ]} */ ;
// @ts-ignore
const __VLS_244 = __VLS_asFunctionalComponent(LLMApiConfig_vue_1.default, new LLMApiConfig_vue_1.default({
    ...{ 'onConfigUpdated': {} },
}));
const __VLS_245 = __VLS_244({
    ...{ 'onConfigUpdated': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_244));
let __VLS_247;
let __VLS_248;
let __VLS_249;
const __VLS_250 = {
    onConfigUpdated: (__VLS_ctx.onLLMConfigUpdated)
};
var __VLS_246;
var __VLS_243;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "log-section" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
const __VLS_251 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_252 = __VLS_asFunctionalComponent(__VLS_251, new __VLS_251({
    value: (__VLS_ctx.operationLog),
    rows: (6),
    readonly: true,
    ...{ class: "log-textarea" },
}));
const __VLS_253 = __VLS_252({
    value: (__VLS_ctx.operationLog),
    rows: (6),
    readonly: true,
    ...{ class: "log-textarea" },
}, ...__VLS_functionalComponentArgsRest(__VLS_252));
/** @type {__VLS_StyleScopedClasses['smart-import-container']} */ ;
/** @type {__VLS_StyleScopedClasses['header-section']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['import-tabs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-input-section']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['action-buttons']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['file-list']} */ ;
/** @type {__VLS_StyleScopedClasses['file-list-header']} */ ;
/** @type {__VLS_StyleScopedClasses['file-title']} */ ;
/** @type {__VLS_StyleScopedClasses['file-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['file-details']} */ ;
/** @type {__VLS_StyleScopedClasses['result-section']} */ ;
/** @type {__VLS_StyleScopedClasses['documents-by-type']} */ ;
/** @type {__VLS_StyleScopedClasses['document-item']} */ ;
/** @type {__VLS_StyleScopedClasses['document-header']} */ ;
/** @type {__VLS_StyleScopedClasses['parse-time']} */ ;
/** @type {__VLS_StyleScopedClasses['document-content']} */ ;
/** @type {__VLS_StyleScopedClasses['content-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['content-textarea']} */ ;
/** @type {__VLS_StyleScopedClasses['source-files']} */ ;
/** @type {__VLS_StyleScopedClasses['result-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['log-section']} */ ;
/** @type {__VLS_StyleScopedClasses['log-textarea']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            InboxOutlined: icons_vue_1.InboxOutlined,
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            FileOutlined: icons_vue_1.FileOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            InfoCircleOutlined: icons_vue_1.InfoCircleOutlined,
            LLMApiConfig: LLMApiConfig_vue_1.default,
            showLLMConfig: showLLMConfig,
            activeTab: activeTab,
            inputText: inputText,
            parsing: parsing,
            importing: importing,
            parseResult: parseResult,
            operationLog: operationLog,
            uploadedFiles: uploadedFiles,
            llmParsing: llmParsing,
            batchParsing: batchParsing,
            activeDocumentTypes: activeDocumentTypes,
            displayPatientName: displayPatientName,
            displayDepartment: displayDepartment,
            displayPrimaryDiagnosis: displayPrimaryDiagnosis,
            parseText: parseText,
            clearText: clearText,
            removeFile: removeFile,
            beforeUpload: beforeUpload,
            handleUploadChange: handleUploadChange,
            formatFileSize: formatFileSize,
            parseAllFiles: parseAllFiles,
            clearAllFiles: clearAllFiles,
            showIndividualResults: showIndividualResults,
            parseFile: parseFile,
            importToDatabase: importToDatabase,
            exportResult: exportResult,
            preciseLLMParse: preciseLLMParse,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
