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
const MedicalDocumentResultModal_vue_1 = __importDefault(require("@/components/MedicalDocumentResultModal.vue"));
const router = (0, vue_router_1.useRouter)();
// 后端 API 配置（开发环境走同源代理，避免跨域与端口错配）
const API_BASE_URL = '';
// 响应式数据
const activeTab = (0, vue_1.ref)('text');
const fileList = (0, vue_1.ref)(: any[]);
const inputText = (0, vue_1.ref)('');
const parsing = (0, vue_1.ref)(false);
const saving = (0, vue_1.ref)(false);
const importing = (0, vue_1.ref)(false);
const parseResult = (0, vue_1.ref)(null);
const operationLog = (0, vue_1.ref)('');
const importResult = (0, vue_1.ref)(null);
const realtimeSubscription = (0, vue_1.ref)(null);
const showApiConfig = (0, vue_1.ref)(false);
const currentConfig = (0, vue_1.ref)(null);
// 后端可用性标记，用于避免跨域健康检查造成的报错
const backendAvailable = (0, vue_1.ref)(false);
// Modal相关状态
const showResultModal = (0, vue_1.ref)(false);
const modalData = (0, vue_1.ref)(null);
const modalOriginalText = (0, vue_1.ref)('');
function isCrossOrigin(url) {
    try {
        const u = new URL(url);
        const currentOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost: 3000';
        return u.origin !== currentOrigin;
    }
    catch {
        return true;
    }
}
// 批量文件管理
const uploadedFiles = (0, vue_1.ref)(: any[]);
const currentFileIndex = (0, vue_1.ref)(0);
const pdfScale = (0, vue_1.ref)(1);
const batchParsing = (0, vue_1.ref)(false);
const batchPaused = (0, vue_1.ref)(false);
const canPauseBatch = (0, vue_1.ref)(true);
const batchProgress = (0, vue_1.ref)({
    total: 0,
    completed: 0,
    currentFile: '',
    hasErrors: false
});
const parsingFileIndex = (0, vue_1.ref)(-1);
const llmAnalyzing = (0, vue_1.ref)(false);
// 计算属性
const currentFile = (0, vue_1.computed)(() => {
    return uploadedFiles.value[currentFileIndex.value] || null;
});
const batchProgressPercent = (0, vue_1.computed)(() => {
    if (batchProgress.value.total === 0)
        return 0;
    return Math.round((batchProgress.value.completed / batchProgress.value.total) * 100);
});
// 示例医疗文本
// 文本输入占位说明由 placeholder 提供，不再预填示例文本
const sampleText = '';
// 方法
const beforeUpload = (file) => {
    console.log('beforeUpload 被调用:', file.name, file.type, file.size);
    // 检查文件数量限制
    if (uploadedFiles.value.length >= 20) {
        ant_design_vue_1.message.error('最多只能上传20个文件');
        return false;
    }
    // 检查文件类型
    const validTypes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain'
    ];
    // 也检查文件扩展名，以防MIME类型不准确
    const fileName = file.name.toLowerCase();
    const validExtensions = ['.pdf', '.doc', '.docx', '.txt'];
    const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext));
    const isValidType = validTypes.includes(file.type) || hasValidExtension;
    if (!isValidType) {
        ant_design_vue_1.message.error(`文件 ${file.name} 格式不支持，只支持 PDF、Word、文本文件格式`);
        return false;
    }
    // 检查文件大小
    const isLt50M = file.size / 1024 / 1024 < 50;
    if (!isLt50M) {
        ant_design_vue_1.message.error(`文件 ${file.name} 大小超过限制，单文件不能超过 50MB`);
        return false;
    }
    console.log('文件验证通过，允许上传:', file.name);
    return false; // 返回false，阻止默认上传，使用custom-request处理
};
// 处理文件上传变化事件
const handleUploadChange = (info) => {
    console.log('handleUploadChange 被调用', info);
    const { fileList } = info;
    console.log('文件列表:', fileList);
    // 处理新添加的文件
    fileList.forEach((fileItem: any) => {
        const file = fileItem.originFileObj || fileItem;
        // 检查是否已经添加过这个文件
        const exists = uploadedFiles.value.some(existingFile => existingFile.name === file.name && existingFile.size === file.size);
        if (!exists && file) {
            console.log('添加新文件:', file.name);
            addFileToList(file);
        }
    });
};
// 添加文件到列表
const addFileToList = (file) => {
    try {
        console.log('处理文件:', file.name, file.type, file.size);
        // 创建文件对象
        const fileObj = {
            name: file.name,
            size: file.size,
            type: file.type,
            file: file,
            uploadTime: new Date().toLocaleString(),
            parsed: false,
            parsing: false,
            parseResult: null,
            error: null,
            previewUrl: null, // 用于PDF预览
            imported: false,
            importResult: null
        };
        // 为PDF文件创建预览URL
        if (file.type === 'application/pdf') {
            fileObj.previewUrl = URL.createObjectURL(file);
            console.log('创建PDF预览URL:', fileObj.previewUrl);
        }
        // 添加到文件列表
        uploadedFiles.value.push(fileObj);
        console.log('文件已添加到列表，当前文件数量:', uploadedFiles.value.length);
        // 自动选择新上传的文件
        currentFileIndex.value = uploadedFiles.value.length - 1;
        operationLog.value += `\n文件上传成功: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)}MB)`;
        ant_design_vue_1.message.success(`文件 ${file.name} 上传成功`, 2);
    }
    catch (error) {
        console.error('文件处理失败:', error);
        operationLog.value += `\n文件处理失败: ${error}`;
        ant_design_vue_1.message.error('文件处理失败');
    }
};
// 保留原有的handleFileUpload方法作为备用
const handleFileUpload = async (options) => {
    console.log('handleFileUpload 被调用', options);
    const { file } = options;
    addFileToList(file);
};
// 文件管理方法
const selectFile = (index) => {
    currentFileIndex.value = index;
    resetZoom();
    console.log('选择文件:', index, (uploadedFiles.value[index] && uploadedFiles.value[index].name));
};
const removeFile = (index) => {
    const file = uploadedFiles.value[index];
    // 清理预览URL
    if (file.previewUrl) {
        URL.revokeObjectURL(file.previewUrl);
    }
    uploadedFiles.value.splice(index, 1);
    // 调整当前选中的文件索引
    if (currentFileIndex.value >= uploadedFiles.value.length) {
        currentFileIndex.value = Math.max(0, uploadedFiles.value.length - 1);
    }
    operationLog.value += `\n删除文件: ${file.name}`;
    ant_design_vue_1.message.success(`删除文件: ${file.name}`);
};
const clearAllFiles = () => {
    // 清理所有预览URL
    uploadedFiles.value.forEach(file => {
        if (file.previewUrl) {
            URL.revokeObjectURL(file.previewUrl);
        }
    });
    uploadedFiles.value = [];
    currentFileIndex.value = 0;
    operationLog.value += '\n清空所有文件';
    ant_design_vue_1.message.success('已清空所有文件');
};
// 解析方法
const parseFile = async (index) => {
    const file = uploadedFiles.value[index];
    if (!file) {
        ant_design_vue_1.message.warning('文件不存在');
        return;
    }
    // 设置解析状态
    file.parsing = true;
    file.error = null;
    file.parsed = false;
    file.imported = false;
    operationLog.value += `\n开始解析文件: ${file.name}`;
    try {
        // 调用后端PDF解析API
        const formData = new FormData();
        formData.append('file', file.file);
        formData.append('options', '{}');
        const response = await fetch(`${API_BASE_URL}/api/parse-medical-file-public`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        const result = await response.json();
        if (result.success) {
            // 更新文件状态
            file.parsed = true;
            file.parseResult = result.data;
            operationLog.value += `\n解析完成: 成功`;
            operationLog.value += `\n解析方法: ${result.data.method}`;
            operationLog.value += `\n内容长度: ${(result.data && result.data.content ? result.data.content.length : 0) || 0} 字符`;
            ant_design_vue_1.message.success(`文件解析成功: ${file.name}`);
        }
        else {
            throw new Error(result.error || '解析失败');
        }
    }
    catch (error) {
        file.error = error.message || '解析失败';
        operationLog.value += `\n解析失败: ${error.message}`;
        ant_design_vue_1.message.error(`文件解析失败: ${file.name} - ${error.message}`);
    }
    finally {
        file.parsing = false;
    }
};
const parseCurrentFile = async () => {
    if (!currentFile.value) {
        ant_design_vue_1.message.warning('请先选择文件');
        return;
    }
    parsing.value = true;
    parsingFileIndex.value = currentFileIndex.value;
    operationLog.value += `\n开始解析文件: ${currentFile.value.name}`;
    try {
        // 调用后端PDF解析API
        const formData = new FormData();
        formData.append('file', currentFile.value.file);
        formData.append('options', '{}');
        const response = await fetch(`${API_BASE_URL}/api/parse-medical-file-public`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const result = await response.json();
        if (result.success) {
            // 更新文件状态
            currentFile.value.parsed = true;
            currentFile.value.parseResult = result.data;
            operationLog.value += `\n解析完成: 成功`;
            operationLog.value += `\n解析方法: ${result.data.method}`;
            operationLog.value += `\n内容长度: ${(result.data && result.data.content ? result.data.content.length : 0) || 0} 字符`;
            operationLog.value += `\n页数: ${result.data.pages || 1} 页`;
            ant_design_vue_1.message.success('文件解析成功');
        }
        else {
            throw new Error(result.error || '解析失败');
        }
    }
    catch (error) {
        currentFile.value.error = error.message || '解析失败';
        operationLog.value += `\n解析失败: ${error.message}`;
        ant_design_vue_1.message.error(`文件解析失败: ${error.message}`);
    }
    finally {
        parsing.value = false;
        parsingFileIndex.value = -1;
    }
};
// 批量解析方法（增强版）
const parseAllFiles = async () => {
    if (uploadedFiles.value.length === 0) {
        ant_design_vue_1.message.warning('请先上传文件');
        return;
    }
    batchParsing.value = true;
    batchPaused.value = false;
    batchProgress.value = {
        total: uploadedFiles.value.length,
        completed: 0,
        currentFile: '',
        hasErrors: false
    };
    operationLog.value += `\n开始批量解析 ${uploadedFiles.value.length} 个文件...`;
    try {
        let successCount = 0;
        let failCount = 0;
        for (let i = 0; i < uploadedFiles.value.length; i++) {
            // 检查是否被取消
            if (!batchParsing.value) {
                operationLog.value += '\n批量解析已取消';
                break;
            }
            // 检查是否暂停
            while (batchPaused.value && batchParsing.value) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            const file = uploadedFiles.value[i];
            // 跳过已解析的文件
            if (file.parsed) {
                operationLog.value += `\n跳过已解析文件: ${file.name}`;
                batchProgress.value.completed++;
                continue;
            }
            batchProgress.value.currentFile = file.name;
            operationLog.value += `\n正在解析: ${file.name} (${i + 1}/${uploadedFiles.value.length})`;
            try {
                await parseFile(i);
                if (file.parsed) {
                    successCount++;
                }
                else {
                    failCount++;
                    batchProgress.value.hasErrors = true;
                }
            }
            catch (error) {
                failCount++;
                batchProgress.value.hasErrors = true;
                operationLog.value += `\n解析失败: ${file.name} - ${error.message}`;
            }
            batchProgress.value.completed++;
            // 添加延迟避免请求过快
            if (i < uploadedFiles.value.length - 1 && batchParsing.value) {
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        }
        batchProgress.value.currentFile = '';
        operationLog.value += `\n批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`;
        if (successCount > 0) {
            ant_design_vue_1.message.success(`批量解析完成: 成功 ${successCount} 个，失败 ${failCount} 个`);
        }
        else {
            ant_design_vue_1.message.error('批量解析失败，请检查文件格式和网络连接');
        }
    }
    catch (error) {
        console.error('批量解析出错:', error);
        ant_design_vue_1.message.error('批量解析出错，请检查网络连接');
        operationLog.value += `\n批量解析出错: ${error}`;
    }
    finally {
        batchParsing.value = false;
        batchPaused.value = false;
    }
};
// 智能导入到数据库
const smartImportToDatabase = async () => {
    if (!currentFile.value || !currentFile.value.parseResult) {
        ant_design_vue_1.message.warning('请先解析文件');
        return;
    }
    importing.value = true;
    operationLog.value += '\n开始智能导入到数据库...';
    try {
        const parseResult = currentFile.value.parseResult;
        const medicalInfo = parseResult.medical_info || {};
        // 提取患者姓名（优先从医疗信息中获取，否则使用默认值）
        const patientName = medicalInfo.patient_name ||
            extractPatientNameFromContent(parseResult.content) ||
            '未知患者';
        const importData = {
            patient_name: patientName,
            content: parseResult.content,
            file_info: {
                filename: currentFile.value.name,
                size: currentFile.value.size,
                type: currentFile.value.type,
                pages: parseResult.pages
            },
            parse_result: {
                method: parseResult.method,
                medical_info: medicalInfo
            }
        };
        const response = await fetch(`${API_BASE_URL}/api/smart-import`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(importData)
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const result = await response.json();
        // 保存导入结果
        importResult.value = result;
        currentFile.value.imported = true;
        currentFile.value.importResult = result;
        operationLog.value += `\n导入成功！`;
        operationLog.value += `\n记录ID: ${result.id}`;
        operationLog.value += `\n病历编号: ${result.record_number}`;
        operationLog.value += `\n创建时间: ${new Date(result.created_at).toLocaleString()}`;
        ant_design_vue_1.message.success('智能导入成功！数据已保存到数据库');
    }
    catch (error) {
        operationLog.value += `\n导入失败: ${error.message}`;
        ant_design_vue_1.message.error(`智能导入失败: ${error.message}`);
    }
    finally {
        importing.value = false;
    }
};
// 从内容中提取患者姓名的辅助函数
const extractPatientNameFromContent = (content) => {
    if (!content)
        return null;
    // 简单的正则匹配患者姓名
    const patterns = [
        /患者[：:]\s*([^\s，,。.]{2,4})/,
        /姓名[：:]\s*([^\s，,。.]{2,4})/,
        /病人[：:]\s*([^\s，,。.]{2,4})/
    ];
    for (const pattern of patterns) {
        const match = content.match(pattern);
        if (match && match[1]) {
            return match[1].trim();
        }
    }
    return null;
};
// LLM精确解析
const showLLMAnalysis = async () => {
    if (!(currentFile.value && currentFile.value.parseResult && currentFile.value.parseResult.content)) {
        ant_design_vue_1.message.warning('请先解析文件获取文本内容');
        return;
    }
    llmAnalyzing.value = true;
    operationLog.value += `\n开始LLM精确解析: ${currentFile.value.name}`;
    try {
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        // 检查LLM配置
        if (!currentConfig.value) {
            ant_design_vue_1.message.warning('请先配置LLM API');
            showApiConfig.value = true;
            return;
        }
        // 使用当前配置初始化LLM服务
        await llmService.initialize(currentConfig.value);
        const result = await llmService.extractMedicalData(currentFile.value.parseResult.content, {
            extractDocuments: true,
            extractPatientInfo: true,
            extractDiagnosis: true
        });
        parseResult.value = result;
        operationLog.value += `\n LLM解析完成: ${result.success ? '成功' : '失败'}`;
        if (result.success) {
            // 显示解析结果Modal
            modalData.value = result.data;
            modalOriginalText.value = result.data?.content || currentFile.value.parseResult?.content || '';
            showResultModal.value = true;
            ant_design_vue_1.message.success('LLM精确解析成功');
        }
        else {
            ant_design_vue_1.message.error(`LLM解析失败: ${result.error}`);
        }
    }
    catch (error) {
        console.error('LLM解析失败:', error);
        operationLog.value += `\n LLM解析失败: ${error}`;
        ant_design_vue_1.message.error('LLM解析失败，请检查API配置');
    }
    finally {
        llmAnalyzing.value = false;
    }
};
// 文本解析方法
const parseText = async () => {
    if (!inputText.value.trim()) {
        ant_design_vue_1.message.warning('请输入文本内容');
        return;
    }
    parsing.value = true;
    operationLog.value += '\n开始解析文本...';
    try {
        // 创建一个临时文本文件进行解析
        const textBlob = new Blob([inputText.value], { type: 'text/plain' });
        const textFile = new File([textBlob], 'input_text.txt', { type: 'text/plain' });
        const formData = new FormData();
        formData.append('file', textFile);
        formData.append('options', '{}');
        const response = await fetch(`${API_BASE_URL}/api/parse-medical-file-public`, {
            method: 'POST',
            body: formData
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const result = await response.json();
        if (result.success) {
            parseResult.value = {
                success: true,
                data: result.data,
                content: result.data.content,
                method: result.data.method,
                medical_info: result.data.medical_info
            };
            operationLog.value += `\n解析完成: 成功`;
            operationLog.value += `\n解析方法: ${result.data.method}`;
            operationLog.value += `\n内容长度: ${(result.data && result.data.content ? result.data.content.length : 0) || 0} 字符`;
            // 显示解析结果Modal
            modalData.value = result.data;
            modalOriginalText.value = result.data.content || inputText.value;
            showResultModal.value = true;
            ant_design_vue_1.message.success('文本解析成功');
        }
        else {
            throw new Error(result.error || '解析失败');
        }
    }
    catch (error) {
        console.error('文本解析失败:', error);
        operationLog.value += `\n解析失败: ${error.message}`;
        ant_design_vue_1.message.error(`文本解析失败: ${error.message}`);
    }
    finally {
        parsing.value = false;
    }
};
// 智能导入文本解析结果
const smartImportTextResult = async () => {
    if (!(parseResult.value && parseResult.value.success)) {
        ant_design_vue_1.message.warning('请先解析文本');
        return;
    }
    importing.value = true;
    operationLog.value += '\n开始智能导入文本解析结果到数据库...';
    try {
        const data = parseResult.value.data;
        const medicalInfo = data.medical_info || {};
        // 提取患者姓名
        const patientName = medicalInfo.patient_name ||
            extractPatientNameFromContent(data.content) ||
            '文本导入患者';
        const importData = {
            patient_name: patientName,
            content: data.content,
            file_info: {
                filename: 'text_input.txt',
                size: (data.content ? data.content.length : 0),
                type: 'text/plain',
                pages: 1
            },
            parse_result: {
                method: data.method,
                medical_info: medicalInfo
            }
        };
        const response = await fetch(`${API_BASE_URL}/api/smart-import`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(importData)
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        const result = await response.json();
        // 保存导入结果
        importResult.value = result;
        operationLog.value += `\n导入成功！`;
        operationLog.value += `\n记录ID: ${result.id}`;
        operationLog.value += `\n病历编号: ${result.record_number}`;
        operationLog.value += `\n创建时间: ${new Date(result.created_at).toLocaleString()}`;
        ant_design_vue_1.message.success('智能导入成功！数据已保存到数据库');
    }
    catch (error) {
        operationLog.value += `\n导入失败: ${error.message}`;
        ant_design_vue_1.message.error(`智能导入失败: ${error.message}`);
    }
    finally {
        importing.value = false;
    }
};
const clearText = () => {
    inputText.value = '';
    parseResult.value = null;
    ant_design_vue_1.message.success('文本已清空');
};
// 测试函数
const testAddFile = () => {
    console.log('测试添加文件');
    const testFile = {
        name: 'test.pdf',
        size: 1024,
        type: 'application/pdf',
        file: null,
        uploadTime: new Date().toLocaleString(),
        parsed: false,
        parsing: false,
        parseResult: null,
        error: null,
        previewUrl: null,
        imported: false,
        importResult: null
    };
    uploadedFiles.value.push(testFile);
    console.log('测试文件已添加，当前数量:', uploadedFiles.value.length);
    ant_design_vue_1.message.success('测试文件已添加');
};
// 其他辅助方法
const exportResult = () => {
    if (!(parseResult.value && parseResult.value.success)) {
        ant_design_vue_1.message.warning('没有可导出的解析结果');
        return;
    }
    try {
        const dataStr = JSON.stringify(parseResult.value, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `medical_analysis_${new Date().getTime()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        ant_design_vue_1.message.success('解析结果已导出');
        operationLog.value += '\n解析结果已导出为JSON文件';
    }
    catch (error) {
        ant_design_vue_1.message.error('导出失败');
        operationLog.value += `\n导出失败: ${error}`;
    }
};
const clearLog = () => {
    operationLog.value = '';
    ant_design_vue_1.message.success('日志已清空');
};
const saveRecord = async () => {
    if (!(parseResult.value && parseResult.value.success)) {
        ant_design_vue_1.message.warning('没有可保存的解析结果');
        return;
    }
    saving.value = true;
    operationLog.value += '\n开始保存记录到数据库...';
    try {
        // 导入数据库服务
        const { supabaseMedicalRecordService } = await Promise.resolve().then(() => __importStar(require('@/services/supabaseMedicalRecordService')));
        // 准备保存的数据
        const recordData = Object.assign({}, parseResult.value.data, {
            source: 'smart_import',
            importedAt: new Date().toISOString(),
            originalText: (currentFile.value && currentFile.value.parseResult && currentFile.value.parseResult.content) ? currentFile.value.parseResult.content : inputText.value
        });
        // 保存到数据库
        const savedRecord = await supabaseMedicalRecordService.createRecord(recordData);
        ant_design_vue_1.message.success('记录保存成功');
        operationLog.value += `\n记录已保存到数据库，ID: ${savedRecord.id}`;
        // 可选：跳转到记录详情页
        // router.push(`/medical-records/${savedRecord.id}`)
    }
    catch (error) {
        console.error('保存失败:', error);
        ant_design_vue_1.message.error(`保存失败: ${error.message || error}`);
        operationLog.value += `\n保存失败: ${error.message || error}`;
    }
    finally {
        saving.value = false;
    }
};
const handleApiConfigUpdated = async (config) => {
    try {
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        const success = await llmService.loadConfigFromDatabase(config.config_name);
        if (success) {
            currentConfig.value = llmService.getCurrentConfig();
            ant_design_vue_1.message.success(`已切换到配置: ${config.config_name}`);
            showApiConfig.value = false;
            operationLog.value += `\n配置已更新: ${config.config_name}`;
        }
    }
    catch (error) {
        ant_design_vue_1.message.error('应用配置失败');
        operationLog.value += `\n配置更新失败: ${error}`;
    }
};
const handleCancel = () => {
    router.back();
};
// PDF缩放控制
const zoomIn = () => {
    if (pdfScale.value < 2) {
        pdfScale.value += 0.1;
    }
};
const zoomOut = () => {
    if (pdfScale.value > 0.5) {
        pdfScale.value -= 0.1;
    }
};
const resetZoom = () => {
    pdfScale.value = 1;
};
// 查看导入结果
const viewImportResult = () => {
    if (currentFile.value && currentFile.value.importResult) {
        importResult.value = currentFile.value.importResult;
        ant_design_vue_1.message.success('已显示导入结果');
    }
};
// 在数据库中查看记录
const viewInDatabase = () => {
    if (importResult.value && importResult.value.id) {
        // 跳转到医疗记录详情页面
        router.push(`/medical-records/${importResult.value.id}`);
    }
};
// 工具函数
const formatFileSize = (bytes) => {
    if (bytes === 0)
        return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};
// 获取置信度颜色
const getConfidenceColor = (confidence) => {
    if (confidence >= 0.8)
        return '#52c41a'; // 绿色
    if (confidence >= 0.6)
        return '#faad14'; // 橙色
    return '#ff4d4f'; // 红色
};
// 获取文档类型颜色
const getDocumentTypeColor = (type) => {
    const colorMap = {
        'admission_record': 'blue',
        'progress_note': 'green',
        'operation_record': 'red',
        'discharge_record': 'purple',
        'auxiliary_examination': 'orange',
        'informed_consent': 'cyan'
    };
    return colorMap[type] || 'default';
};
// 获取文档类型名称
const getDocumentTypeName = (type) => {
    const nameMap = {
        'admission_record': '入院记录',
        'progress_note': '病程记录',
        'operation_record': '手术记录',
        'discharge_record': '出院记录',
        'auxiliary_examination': '辅助检查',
        'informed_consent': '知情同意书'
    };
    return nameMap[type] || type;
};
// Supabase Realtime 监听
const setupRealtimeSubscription = () => {
    if (realtimeSubscription.value) {
        realtimeSubscription.value.unsubscribe();
    }
    realtimeSubscription.value = supabase
        .channel('medical_records_changes')
        .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'medical_records' }, (payload: any) => {
        console.log('新的医疗记录创建:', payload.new);
        operationLog.value += `\n实时更新: 新记录已创建 (ID: ${payload.new.id})`;
        ant_design_vue_1.message.info('检测到新的医疗记录创建');
    })
        .on('postgres_changes',  { event: 'UPDATE', schema: 'public', table: 'medical_records' }, (payload: any) => {
        console.log('医疗记录更新:', payload.new);
        operationLog.value += `\n实时更新: 记录已更新 (ID: ${payload.new.id})`;
    })
        .subscribe();
};
// 检查后端服务连接（跨域或不可达时静默降级）
const checkBackendConnection = async () => {
    try {
        // 如果 API_BASE_URL 跨域，直接跳过健康检查，避免 CORS 错误
        if (isCrossOrigin(API_BASE_URL)) {
            operationLog.value += `\n检测到跨域后端(${API_BASE_URL})，跳过健康检查，启用前端直连模式`;
            backendAvailable.value = false;
            return true;
        }
        const response = await fetch(`${API_BASE_URL}/api/v1/health`);
        if (response.ok) {
            const result = await response.json();
            operationLog.value += `\n后端服务连接正常: ${result.message || 'OK'}`;
            backendAvailable.value = true;
            return true;
        }
        else {
            throw new Error(`HTTP ${response.status}`);
        }
    }
    catch (error) {
        operationLog.value += `\n后端服务连接失败，已降级为直连模式: ${(error && error.message) || error}`;
        backendAvailable.value = false;
        // 不提示 warning，避免打扰用户
        return true;
    }
};
// 生命周期
(0, vue_1.onMounted)(async () => {
    console.log('SmartImportMedicalRecordNew 组件已挂载');
    operationLog.value = '系统初始化中...';
    // 设置示例文本
    inputText.value = sampleText;
    // 检查后端连接
    await checkBackendConnection();
    // 尝试加载默认配置
    try {
        const { llmService } = await Promise.resolve().then(() => __importStar(require('@/services/llmServiceNew')));
        const success = await llmService.loadConfigFromDatabase('default');
        if (success) {
            currentConfig.value = llmService.getCurrentConfig();
            operationLog.value += '\n已加载默认LLM配置';
        }
    }
    catch (error) {
        operationLog.value += `\n加载配置失败: ${error}`;
    }
    // 设置实时监听
    setupRealtimeSubscription();
    operationLog.value += '\n系统初始化完成';
});
// 组件卸载时清理资源
(0, vue_1.onUnmounted)(() => {
    console.log('SmartImportMedicalRecordNew 组件即将卸载');
    // 清理所有预览URL
    uploadedFiles.value.forEach(file => {
        if (file.previewUrl) {
            URL.revokeObjectURL(file.previewUrl);
        }
    });
    // 清理实时订阅
    if (realtimeSubscription.value) {
        realtimeSubscription.value.unsubscribe();
        realtimeSubscription.value = null;
    }
});
// Modal处理方法
const handleModalConfirm = async (data) => {
    // 用户点击"保存并跳转"按钮，直接保存并跳转
    operationLog.value += '\n用户选择保存并跳转到详情页面';
    await autoSaveAndRedirect(data);
};
const handleModalConfirmOnly = (data) => {
    // 用户点击"确认结果"按钮，只确认不跳转
    parseResult.value = {
        success: true,
        data: data,
        content: data.content,
        method: data.method || 'LLM解析',
        medical_info: data.medical_info || {}
    };
    // 切换到结果标签页，显示简化的结果信息
    activeTab.value = 'result';
    operationLog.value += '\n用户确认了解析结果';
    ant_design_vue_1.message.success('解析结果已确认，可以进行后续操作');
};
const handleModalExport = (data) => {
    try {
        const dataStr = JSON.stringify(data, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `medical_parse_result_${new Date().getTime()}.json`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        ant_design_vue_1.message.success('解析结果已导出');
        operationLog.value += '\n解析结果已导出为JSON文件';
    }
    catch (error) {
        ant_design_vue_1.message.error('导出失败');
        operationLog.value += `\n导出失败: ${error}`;
    }
};
// 自动保存并跳转方法
const autoSaveAndRedirect = async (data) => {
    try {
        saving.value = true;
        operationLog.value += '\n开始自动保存解析结果...';
        // 构建保存数据
        const saveData = {
            record_number: data.recordNumber || `AUTO_${Date.now()}`,
            patient_name: data.patientName || '未识别',
            patient_age: data.patientAge || null,
            patient_gender: data.patientGender || null,
            department: data.department || '未识别',
            primary_diagnosis: data.primaryDiagnosis || '未识别',
            secondary_diagnosis: data.secondaryDiagnosis || [],
            major_surgery: data.majorSurgery || '无',
            documents: data.documents || [],
            confidence: data.confidence || 0,
            content: data.content || '',
            method: data.method || 'LLM解析',
            created_at: new Date().toISOString()
        };
        const response = await fetch(`${API_BASE_URL}/api/medical-records`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(saveData)
        });
        if (!response.ok) {
            throw new Error(`保存失败: ${response.status}`);
        }
        const savedRecord = await response.json();
        operationLog.value += `\n保存成功，记录ID: ${savedRecord.id}`;
        ant_design_vue_1.message.success('解析结果已保存，正在跳转到详情页面...');
        // 延迟跳转，让用户看到成功消息
        setTimeout(() => {
            router.push(`/dashboard/medical-records/${savedRecord.id}`);
        }, 1500);
    }
    catch (error) {
        console.error('自动保存失败:', error);
        ant_design_vue_1.message.error(`自动保存失败: ${error.message}`);
        operationLog.value += `\n自动保存失败: ${error.message}`;
        // 保存失败时，切换到结果标签页让用户手动操作
        activeTab.value = 'result';
    }
    finally {
        saving.value = false;
    }
};
// 暂停/继续批量处理
const pauseBatchProcessing = () => {
    batchPaused.value = !batchPaused.value;
    if (batchPaused.value) {
        operationLog.value += '\n批量解析已暂停';
    }
    else {
        operationLog.value += '\n批量解析已继续';
    }
};
// 取消批量处理
const cancelBatchProcessing = () => {
    batchParsing.value = false;
    batchPaused.value = false;
    operationLog.value += '\n批量解析已取消';
    ant_design_vue_1.message.info('批量解析已取消');
};
// 跳转到高级批量导入页面
const showBatchImportView = () => {
    router.push('/dashboard/medical-records/batch-import');
};
// 这些方法已在前面定义，删除重复定义
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "min-h-screen p-4 md:p-6 bg-gradient-to-br from-blue-50 via-blue-50 to-indigo-100" },
});
const __VLS_0 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg hover:shadow-xl transition-all ring-1 ring-blue-100/70 border md:border-2 border-gray-200 max-w-7xl mx-auto" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "bg-white/90 backdrop-blur-sm rounded-2xl shadow-lg hover:shadow-xl transition-all ring-1 ring-blue-100/70 border md:border-2 border-gray-200 max-w-7xl mx-auto" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
{
    const { title: __VLS_thisSlot } = __VLS_3.slots;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center gap-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex items-center justify-center w-10 h-10 rounded-lg bg-blue-100 text-blue-600 ring-1 ring-blue-200" },
    });
    const __VLS_4 = {}.RobotOutlined;
    /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
    const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xl md:text-2xl font-extrabold text-gray-900 tracking-tight" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-xs md:text-sm text-gray-500 mt-0.5" },
    });
}
{
    const { extra: __VLS_thisSlot } = __VLS_3.slots;
    const __VLS_8 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
    const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
    __VLS_11.slots.default;
    const __VLS_12 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        ...{ 'onClick': {} },
        type: "default",
        ...{ class: "hover:shadow-sm" },
    }));
    const __VLS_14 = __VLS_13({
        ...{ 'onClick': {} },
        type: "default",
        ...{ class: "hover:shadow-sm" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    let __VLS_16;
    let __VLS_17;
    let __VLS_18;
    const __VLS_19 = {
        onClick: (...[$event]) => {
            __VLS_ctx.showApiConfig = true;
        }
    };
    __VLS_15.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_15.slots;
        const __VLS_20 = {}.SettingOutlined;
        /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
        const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
    }
    var __VLS_15;
    const __VLS_24 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        ...{ 'onClick': {} },
        type: "default",
        ...{ class: "hover:shadow-sm" },
    }));
    const __VLS_26 = __VLS_25({
        ...{ 'onClick': {} },
        type: "default",
        ...{ class: "hover:shadow-sm" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    let __VLS_28;
    let __VLS_29;
    let __VLS_30;
    const __VLS_31 = {
        onClick: (__VLS_ctx.handleCancel)
    };
    __VLS_27.slots.default;
    var __VLS_27;
    var __VLS_11;
}
if (__VLS_ctx.currentConfig) {
    const __VLS_32 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        message: (`当前LLM配置: ${__VLS_ctx.currentConfig.config_name}`),
        description: (`${(__VLS_ctx.currentConfig.provider && __VLS_ctx.currentConfig.provider.provider_name) || ''} - ${(__VLS_ctx.currentConfig.model && __VLS_ctx.currentConfig.model.model_name) || ''}`),
        type: "info",
        showIcon: true,
        ...{ class: "mb-4" },
    }));
    const __VLS_34 = __VLS_33({
        message: (`当前LLM配置: ${__VLS_ctx.currentConfig.config_name}`),
        description: (`${(__VLS_ctx.currentConfig.provider && __VLS_ctx.currentConfig.provider.provider_name) || ''} - ${(__VLS_ctx.currentConfig.model && __VLS_ctx.currentConfig.model.model_name) || ''}`),
        type: "info",
        showIcon: true,
        ...{ class: "mb-4" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
}
const __VLS_36 = {}.ATabs;
/** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
    ...{ class: "mt-4" },
}));
const __VLS_38 = __VLS_37({
    activeKey: (__VLS_ctx.activeTab),
    type: "card",
    ...{ class: "mt-4" },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
__VLS_39.slots.default;
const __VLS_40 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    key: "text",
    tab: "文本输入",
}));
const __VLS_42 = __VLS_41({
    key: "text",
    tab: "文本输入",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
__VLS_43.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-2xl p-2 md:p-3 bg-gradient-to-br from-blue-100/50 via-sky-100/40 to-indigo-100/50" },
});
const __VLS_44 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    size: "small",
    title: "直接输入医疗文本",
    ...{ class: "rounded-2xl shadow-md ring-1 ring-slate-200/70" },
}));
const __VLS_46 = __VLS_45({
    size: "small",
    title: "直接输入医疗文本",
    ...{ class: "rounded-2xl shadow-md ring-1 ring-slate-200/70" },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
__VLS_47.slots.default;
const __VLS_48 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    value: (__VLS_ctx.inputText),
    rows: (8),
    placeholder: "\u8bf7\u8f93\u5165\u533b\u7597\u8bb0\u5f55\u6587\u672c\uff0c\u4f8b\u5982\uff1a\u005c\u006e\u60a3\u8005\u59d3\u540d\uff0c\u6027\u522b\uff0c\u5e74\u9f84\uff0c\u4e3b\u8bc9\u002e\u002e\u002e\u005c\u006e\u73b0\u75c5\u53f2\uff1a\u002e\u002e\u002e\u005c\u006e\u65e2\u5f80\u53f2\uff1a\u002e\u002e\u002e\u005c\u006e\u5165\u9662\u8bca\u65ad\uff1a\u002e\u002e\u002e",
    ...{ class: "mb-3" },
}));
const __VLS_50 = __VLS_49({
    value: (__VLS_ctx.inputText),
    rows: (8),
    placeholder: "\u8bf7\u8f93\u5165\u533b\u7597\u8bb0\u5f55\u6587\u672c\uff0c\u4f8b\u5982\uff1a\u005c\u006e\u60a3\u8005\u59d3\u540d\uff0c\u6027\u522b\uff0c\u5e74\u9f84\uff0c\u4e3b\u8bc9\u002e\u002e\u002e\u005c\u006e\u73b0\u75c5\u53f2\uff1a\u002e\u002e\u002e\u005c\u006e\u65e2\u5f80\u53f2\uff1a\u002e\u002e\u002e\u005c\u006e\u5165\u9662\u8bca\u65ad\uff1a\u002e\u002e\u002e",
    ...{ class: "mb-3" },
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "flex items-center justify-between" },
});
const __VLS_52 = {}.ASpace;
/** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.parsing),
    type: "primary",
    size: "large",
}));
const __VLS_58 = __VLS_57({
    ...{ 'onClick': {} },
    loading: (__VLS_ctx.parsing),
    type: "primary",
    size: "large",
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
let __VLS_60;
let __VLS_61;
let __VLS_62;
const __VLS_63 = {
    onClick: (__VLS_ctx.parseText)
};
__VLS_59.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_59.slots;
    const __VLS_64 = {}.ThunderboltOutlined;
    /** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({}));
    const __VLS_66 = __VLS_65({}, ...__VLS_functionalComponentArgsRest(__VLS_65));
}
var __VLS_59;
const __VLS_68 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    ...{ 'onClick': {} },
    type: "default",
}));
const __VLS_70 = __VLS_69({
    ...{ 'onClick': {} },
    type: "default",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
let __VLS_72;
let __VLS_73;
let __VLS_74;
const __VLS_75 = {
    onClick: (__VLS_ctx.clearText)
};
__VLS_71.slots.default;
var __VLS_71;
var __VLS_55;
if (__VLS_ctx.parseResult && __VLS_ctx.parseResult.success) {
    const __VLS_76 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({}));
    const __VLS_78 = __VLS_77({}, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    const __VLS_80 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        color: "success",
    }));
    const __VLS_82 = __VLS_81({
        color: "success",
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    const __VLS_84 = {}.CheckCircleOutlined;
    /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
    const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
    var __VLS_83;
    const __VLS_88 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.importing),
        type: "primary",
        size: "large",
    }));
    const __VLS_90 = __VLS_89({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.importing),
        type: "primary",
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    let __VLS_92;
    let __VLS_93;
    let __VLS_94;
    const __VLS_95 = {
        onClick: (__VLS_ctx.smartImportTextResult)
    };
    __VLS_91.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_91.slots;
        const __VLS_96 = {}.DatabaseOutlined;
        /** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({}));
        const __VLS_98 = __VLS_97({}, ...__VLS_functionalComponentArgsRest(__VLS_97));
    }
    var __VLS_91;
    var __VLS_79;
}
var __VLS_47;
var __VLS_43;
const __VLS_100 = {}.ATabPane;
/** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    key: "file",
    tab: "文件上传",
}));
const __VLS_102 = __VLS_101({
    key: "file",
    tab: "文件上传",
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
__VLS_103.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "rounded-2xl p-2 md:p-3 bg-gradient-to-br from-blue-100/50 via-sky-100/40 to-indigo-100/50" },
});
const __VLS_104 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    size: "small",
    title: "上传医疗文档",
    ...{ class: "rounded-2xl shadow-md ring-1 ring-slate-200/70" },
}));
const __VLS_106 = __VLS_105({
    size: "small",
    title: "上传医疗文档",
    ...{ class: "rounded-2xl shadow-md ring-1 ring-slate-200/70" },
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
__VLS_107.slots.default;
const __VLS_108 = {}.AUploadDragger;
/** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    ...{ 'onChange': {} }, fileList: (: any[]),
    beforeUpload: (__VLS_ctx.beforeUpload),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
    showUploadList: (false),
    ...{ class: "mb-4 rounded-2xl border-2 border-dashed border-blue-300/70 bg-gradient-to-br from-white via-white to-blue-50/40 shadow-sm hover:shadow-md transition-all" },
}));
const __VLS_110 = __VLS_109({
    ...{ 'onChange': {} }, fileList: (: any[]),
    beforeUpload: (__VLS_ctx.beforeUpload),
    accept: ".pdf,.doc,.docx,.txt",
    multiple: (true),
    showUploadList: (false),
    ...{ class: "mb-4 rounded-2xl border-2 border-dashed border-blue-300/70 bg-gradient-to-br from-white via-white to-blue-50/40 shadow-sm hover:shadow-md transition-all" },
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
let __VLS_112;
let __VLS_113;
let __VLS_114;
const __VLS_115 = {
    onChange: (__VLS_ctx.handleUploadChange)
};
__VLS_111.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-drag-icon" },
});
const __VLS_116 = {}.InboxOutlined;
/** @type {[typeof __VLS_components.InboxOutlined, ]} */ ;
// @ts-ignore
const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "ant-upload-hint" },
});
var __VLS_111;
if (__VLS_ctx.uploadedFiles.length > 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-4 bg-blue-50/40 rounded-2xl p-4 border md:border-2 border-blue-300" },
    });
    const __VLS_120 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({}));
    const __VLS_122 = __VLS_121({}, ...__VLS_functionalComponentArgsRest(__VLS_121));
    __VLS_123.slots.default;
    (__VLS_ctx.uploadedFiles.length);
    var __VLS_123;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-3 text-center p-4 bg-white/95 rounded-xl border md:border-2 border-blue-300 hover:border-blue-400 shadow-md hover:shadow-lg transition-all" },
    });
    const __VLS_124 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
        size: "large",
    }));
    const __VLS_126 = __VLS_125({
        size: "large",
    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
    __VLS_127.slots.default;
    const __VLS_128 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_129 = __VLS_asFunctionalComponent(__VLS_128, new __VLS_128({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.batchParsing),
        type: "primary",
        size: "default",
    }));
    const __VLS_130 = __VLS_129({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.batchParsing),
        type: "primary",
        size: "default",
    }, ...__VLS_functionalComponentArgsRest(__VLS_129));
    let __VLS_132;
    let __VLS_133;
    let __VLS_134;
    const __VLS_135 = {
        onClick: (__VLS_ctx.parseAllFiles)
    };
    __VLS_131.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_131.slots;
        const __VLS_136 = {}.ThunderboltOutlined;
        /** @type {[typeof __VLS_components.ThunderboltOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({}));
        const __VLS_138 = __VLS_137({}, ...__VLS_functionalComponentArgsRest(__VLS_137));
    }
    (__VLS_ctx.batchParsing ? '解析中...' : '一键解析所有文件');
    var __VLS_131;
    if (__VLS_ctx.batchParsing) {
        const __VLS_140 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
            ...{ 'onClick': {} },
            disabled: (!__VLS_ctx.canPauseBatch),
        }));
        const __VLS_142 = __VLS_141({
            ...{ 'onClick': {} },
            disabled: (!__VLS_ctx.canPauseBatch),
        }, ...__VLS_functionalComponentArgsRest(__VLS_141));
        let __VLS_144;
        let __VLS_145;
        let __VLS_146;
        const __VLS_147 = {
            onClick: (__VLS_ctx.pauseBatchProcessing)
        };
        __VLS_143.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_143.slots;
            const __VLS_148 = {}.PauseCircleOutlined;
            /** @type {[typeof __VLS_components.PauseCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({}));
            const __VLS_150 = __VLS_149({}, ...__VLS_functionalComponentArgsRest(__VLS_149));
        }
        (__VLS_ctx.batchPaused ? '继续' : '暂停');
        var __VLS_143;
    }
    if (__VLS_ctx.batchParsing) {
        const __VLS_152 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
            ...{ 'onClick': {} },
            danger: true,
        }));
        const __VLS_154 = __VLS_153({
            ...{ 'onClick': {} },
            danger: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_153));
        let __VLS_156;
        let __VLS_157;
        let __VLS_158;
        const __VLS_159 = {
            onClick: (__VLS_ctx.cancelBatchProcessing)
        };
        __VLS_155.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_155.slots;
            const __VLS_160 = {}.StopOutlined;
            /** @type {[typeof __VLS_components.StopOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({}));
            const __VLS_162 = __VLS_161({}, ...__VLS_functionalComponentArgsRest(__VLS_161));
        }
        var __VLS_155;
    }
    const __VLS_164 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_165 = __VLS_asFunctionalComponent(__VLS_164, new __VLS_164({
        ...{ 'onClick': {} },
        type: "default",
        size: "default",
        danger: true,
    }));
    const __VLS_166 = __VLS_165({
        ...{ 'onClick': {} },
        type: "default",
        size: "default",
        danger: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_165));
    let __VLS_168;
    let __VLS_169;
    let __VLS_170;
    const __VLS_171 = {
        onClick: (__VLS_ctx.clearAllFiles)
    };
    __VLS_167.slots.default;
    var __VLS_167;
    const __VLS_172 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
        ...{ 'onClick': {} },
        type: "dashed",
    }));
    const __VLS_174 = __VLS_173({
        ...{ 'onClick': {} },
        type: "dashed",
    }, ...__VLS_functionalComponentArgsRest(__VLS_173));
    let __VLS_176;
    let __VLS_177;
    let __VLS_178;
    const __VLS_179 = {
        onClick: (__VLS_ctx.showBatchImportView)
    };
    __VLS_175.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_175.slots;
        const __VLS_180 = {}.AppstoreOutlined;
        /** @type {[typeof __VLS_components.AppstoreOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({}));
        const __VLS_182 = __VLS_181({}, ...__VLS_functionalComponentArgsRest(__VLS_181));
    }
    var __VLS_175;
    var __VLS_127;
    if (__VLS_ctx.batchParsing || __VLS_ctx.batchProgress.total > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mb-3 p-3 bg-blue-50/60 rounded-xl border border-blue-200" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "flex justify-between items-center mb-2" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-sm font-medium text-blue-800" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-xs text-blue-600" },
        });
        (__VLS_ctx.batchProgress.completed);
        (__VLS_ctx.batchProgress.total);
        (__VLS_ctx.batchProgress.currentFile ? `(正在处理: ${__VLS_ctx.batchProgress.currentFile})` : '');
        const __VLS_184 = {}.AProgress;
        /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
        // @ts-ignore
        const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({
            percent: (__VLS_ctx.batchProgressPercent),
            status: (__VLS_ctx.batchParsing ? 'active' : (__VLS_ctx.batchProgress.hasErrors ? 'exception' : 'success')),
            size: "small",
        }));
        const __VLS_186 = __VLS_185({
            percent: (__VLS_ctx.batchProgressPercent),
            status: (__VLS_ctx.batchParsing ? 'active' : (__VLS_ctx.batchProgress.hasErrors ? 'exception' : 'success')),
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_185));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-white rounded-xl p-3 border md:border-2 border-gray-300 hover:border-gray-400 shadow-sm mb-4" },
    });
    const __VLS_188 = {}.AList;
    /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        dataSource: (__VLS_ctx.uploadedFiles),
        size: "small",
        split: (false),
    }));
    const __VLS_190 = __VLS_189({
        dataSource: (__VLS_ctx.uploadedFiles),
        size: "small",
        split: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    __VLS_191.slots.default;
    {
        const { renderItem: __VLS_thisSlot } = __VLS_191.slots;
        const [{ item, index }] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_192 = {}.AListItem;
        /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
        // @ts-ignore
        const __VLS_193 = __VLS_asFunctionalComponent(__VLS_192, new __VLS_192({
            ...{ 'onClick': {} },
            ...{ class: ([
                    'cursor-pointer transition-transform rounded-xl px-3 py-2 mb-2 ui-card ui-card-muted hover:border-blue-400 hover:shadow-md hover:-translate-y-[1px] duration-200 ease-out',
                    __VLS_ctx.currentFileIndex === index ? 'ring-2 ring-blue-300 border-blue-500 bg-blue-50/60 shadow-md' : ''
                ]) },
        }));
        const __VLS_194 = __VLS_193({
            ...{ 'onClick': {} },
            ...{ class: ([
                    'cursor-pointer transition-transform rounded-xl px-3 py-2 mb-2 ui-card ui-card-muted hover:border-blue-400 hover:shadow-md hover:-translate-y-[1px] duration-200 ease-out',
                    __VLS_ctx.currentFileIndex === index ? 'ring-2 ring-blue-300 border-blue-500 bg-blue-50/60 shadow-md' : ''
                ]) },
        }, ...__VLS_functionalComponentArgsRest(__VLS_193));
        let __VLS_196;
        let __VLS_197;
        let __VLS_198;
        const __VLS_199 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.uploadedFiles.length > 0))
                    return;
                __VLS_ctx.selectFile(index);
            }
        };
        __VLS_195.slots.default;
        {
            const { actions: __VLS_thisSlot } = __VLS_195.slots;
            const __VLS_200 = {}.ADropdown;
            /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
            // @ts-ignore
            const __VLS_201 = __VLS_asFunctionalComponent(__VLS_200, new __VLS_200({}));
            const __VLS_202 = __VLS_201({}, ...__VLS_functionalComponentArgsRest(__VLS_201));
            __VLS_203.slots.default;
            const __VLS_204 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({
                size: "small",
                type: "text",
            }));
            const __VLS_206 = __VLS_205({
                size: "small",
                type: "text",
            }, ...__VLS_functionalComponentArgsRest(__VLS_205));
            __VLS_207.slots.default;
            const __VLS_208 = {}.MoreOutlined;
            /** @type {[typeof __VLS_components.MoreOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({}));
            const __VLS_210 = __VLS_209({}, ...__VLS_functionalComponentArgsRest(__VLS_209));
            var __VLS_207;
            {
                const { overlay: __VLS_thisSlot } = __VLS_203.slots;
                const __VLS_212 = {}.AMenu;
                /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
                // @ts-ignore
                const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({}));
                const __VLS_214 = __VLS_213({}, ...__VLS_functionalComponentArgsRest(__VLS_213));
                __VLS_215.slots.default;
                const __VLS_216 = {}.AMenuItem;
                /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
                // @ts-ignore
                const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({
                    ...{ 'onClick': {} },
                    danger: true,
                }));
                const __VLS_218 = __VLS_217({
                    ...{ 'onClick': {} },
                    danger: true,
                }, ...__VLS_functionalComponentArgsRest(__VLS_217));
                let __VLS_220;
                let __VLS_221;
                let __VLS_222;
                const __VLS_223 = {
                    onClick: (...[$event]) => {
                        if (!(__VLS_ctx.uploadedFiles.length > 0))
                            return;
                        __VLS_ctx.removeFile(index);
                    }
                };
                __VLS_219.slots.default;
                const __VLS_224 = {}.DeleteOutlined;
                /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({}));
                const __VLS_226 = __VLS_225({}, ...__VLS_functionalComponentArgsRest(__VLS_225));
                var __VLS_219;
                var __VLS_215;
            }
            var __VLS_203;
        }
        const __VLS_228 = {}.AListItemMeta;
        /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
        // @ts-ignore
        const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({}));
        const __VLS_230 = __VLS_229({}, ...__VLS_functionalComponentArgsRest(__VLS_229));
        __VLS_231.slots.default;
        {
            const { avatar: __VLS_thisSlot } = __VLS_231.slots;
            const __VLS_232 = {}.FileOutlined;
            /** @type {[typeof __VLS_components.FileOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({
                ...{ class: "text-blue-500 text-base" },
            }));
            const __VLS_234 = __VLS_233({
                ...{ class: "text-blue-500 text-base" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_233));
        }
        {
            const { title: __VLS_thisSlot } = __VLS_231.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "flex items-center justify-between w-full" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "font-medium text-slate-800 max-w-[300px] truncate" },
                title: (item.name),
            });
            (item.name);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "ml-3" },
            });
            if (item.parsing) {
                const __VLS_236 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({
                    color: "processing",
                    size: "small",
                }));
                const __VLS_238 = __VLS_237({
                    color: "processing",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_237));
                __VLS_239.slots.default;
                const __VLS_240 = {}.LoadingOutlined;
                /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({}));
                const __VLS_242 = __VLS_241({}, ...__VLS_functionalComponentArgsRest(__VLS_241));
                var __VLS_239;
            }
            else if (item.parsed) {
                const __VLS_244 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({
                    color: "success",
                    size: "small",
                }));
                const __VLS_246 = __VLS_245({
                    color: "success",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_245));
                __VLS_247.slots.default;
                const __VLS_248 = {}.CheckCircleOutlined;
                /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({}));
                const __VLS_250 = __VLS_249({}, ...__VLS_functionalComponentArgsRest(__VLS_249));
                var __VLS_247;
            }
            else if (item.error) {
                const __VLS_252 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({
                    color: "error",
                    size: "small",
                }));
                const __VLS_254 = __VLS_253({
                    color: "error",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_253));
                __VLS_255.slots.default;
                const __VLS_256 = {}.ExclamationCircleOutlined;
                /** @type {[typeof __VLS_components.ExclamationCircleOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({}));
                const __VLS_258 = __VLS_257({}, ...__VLS_functionalComponentArgsRest(__VLS_257));
                var __VLS_255;
            }
            else {
                const __VLS_260 = {}.ATag;
                /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
                // @ts-ignore
                const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
                    color: "default",
                    size: "small",
                }));
                const __VLS_262 = __VLS_261({
                    color: "default",
                    size: "small",
                }, ...__VLS_functionalComponentArgsRest(__VLS_261));
                __VLS_263.slots.default;
                var __VLS_263;
            }
        }
        {
            const { description: __VLS_thisSlot } = __VLS_231.slots;
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                ...{ class: "text-slate-500 text-xs" },
            });
            (__VLS_ctx.formatFileSize(item.size));
            (item.uploadTime);
        }
        var __VLS_231;
        var __VLS_195;
    }
    var __VLS_191;
}
var __VLS_107;
var __VLS_103;
var __VLS_39;
if (__VLS_ctx.currentFile && __VLS_ctx.currentFile.parsed && __VLS_ctx.currentFile.parseResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-4 border-t-2 border-blue-100/70 pt-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rounded-2xl p-2 md:p-3 bg-gradient-to-br from-sky-100/40 via-blue-100/30 to-indigo-100/40" },
    });
    const __VLS_264 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
        size: "small",
        title: "📋 解析内容预览",
        ...{ class: "rounded-2xl shadow-md ring-1 ring-slate-200/70" },
    }));
    const __VLS_266 = __VLS_265({
        size: "small",
        title: "📋 解析内容预览",
        ...{ class: "rounded-2xl shadow-md ring-1 ring-slate-200/70" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_265));
    __VLS_267.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_267.slots;
        const __VLS_268 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({}));
        const __VLS_270 = __VLS_269({}, ...__VLS_functionalComponentArgsRest(__VLS_269));
        __VLS_271.slots.default;
        if (__VLS_ctx.currentFile.imported) {
            const __VLS_272 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
                color: "success",
                ...{ class: "shadow-sm" },
            }));
            const __VLS_274 = __VLS_273({
                color: "success",
                ...{ class: "shadow-sm" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_273));
            __VLS_275.slots.default;
            const __VLS_276 = {}.CheckCircleOutlined;
            /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({}));
            const __VLS_278 = __VLS_277({}, ...__VLS_functionalComponentArgsRest(__VLS_277));
            var __VLS_275;
        }
        else {
            const __VLS_280 = {}.ATag;
            /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
            // @ts-ignore
            const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
                color: "geekblue",
                ...{ class: "shadow-sm" },
            }));
            const __VLS_282 = __VLS_281({
                color: "geekblue",
                ...{ class: "shadow-sm" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_281));
            __VLS_283.slots.default;
            const __VLS_284 = {}.CheckCircleOutlined;
            /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({}));
            const __VLS_286 = __VLS_285({}, ...__VLS_functionalComponentArgsRest(__VLS_285));
            var __VLS_283;
        }
        if (!__VLS_ctx.currentFile.imported) {
            const __VLS_288 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
                ...{ 'onClick': {} },
                size: "small",
                loading: (__VLS_ctx.importing),
                type: "primary",
                ...{ class: "hover:shadow" },
            }));
            const __VLS_290 = __VLS_289({
                ...{ 'onClick': {} },
                size: "small",
                loading: (__VLS_ctx.importing),
                type: "primary",
                ...{ class: "hover:shadow" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_289));
            let __VLS_292;
            let __VLS_293;
            let __VLS_294;
            const __VLS_295 = {
                onClick: (__VLS_ctx.smartImportToDatabase)
            };
            __VLS_291.slots.default;
            {
                const { icon: __VLS_thisSlot } = __VLS_291.slots;
                const __VLS_296 = {}.DatabaseOutlined;
                /** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({}));
                const __VLS_298 = __VLS_297({}, ...__VLS_functionalComponentArgsRest(__VLS_297));
            }
            var __VLS_291;
        }
        if (__VLS_ctx.currentFile.imported) {
            const __VLS_300 = {}.AButton;
            /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
            // @ts-ignore
            const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({
                ...{ 'onClick': {} },
                size: "small",
                type: "default",
                ...{ class: "hover:shadow" },
            }));
            const __VLS_302 = __VLS_301({
                ...{ 'onClick': {} },
                size: "small",
                type: "default",
                ...{ class: "hover:shadow" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_301));
            let __VLS_304;
            let __VLS_305;
            let __VLS_306;
            const __VLS_307 = {
                onClick: (__VLS_ctx.viewImportResult)
            };
            __VLS_303.slots.default;
            {
                const { icon: __VLS_thisSlot } = __VLS_303.slots;
                const __VLS_308 = {}.EyeOutlined;
                /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
                // @ts-ignore
                const __VLS_309 = __VLS_asFunctionalComponent(__VLS_308, new __VLS_308({}));
                const __VLS_310 = __VLS_309({}, ...__VLS_functionalComponentArgsRest(__VLS_309));
            }
            var __VLS_303;
        }
        var __VLS_271;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parse-stats mb-3 grid grid-cols-1 sm:grid-cols-2 gap-3" },
    });
    const __VLS_312 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_313 = __VLS_asFunctionalComponent(__VLS_312, new __VLS_312({
        gutter: (0),
        ...{ style: {} },
    }));
    const __VLS_314 = __VLS_313({
        gutter: (0),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_313));
    __VLS_315.slots.default;
    const __VLS_316 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
        xs: (12),
        sm: (12),
        md: (12),
        lg: (12),
    }));
    const __VLS_318 = __VLS_317({
        xs: (12),
        sm: (12),
        md: (12),
        lg: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_317));
    __VLS_319.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rounded-xl border border-slate-200 bg-white hover:shadow-sm transition p-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex flex-col gap-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-[13px] text-gray-500 font-medium" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-[15px] font-semibold text-gray-900 truncate" },
    });
    (((__VLS_ctx.currentFile.parseResult && __VLS_ctx.currentFile.parseResult.content ? __VLS_ctx.currentFile.parseResult.content.length : 0)).toLocaleString());
    var __VLS_319;
    const __VLS_320 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
        xs: (12),
        sm: (12),
        md: (12),
        lg: (12),
    }));
    const __VLS_322 = __VLS_321({
        xs: (12),
        sm: (12),
        md: (12),
        lg: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_321));
    __VLS_323.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rounded-xl border border-slate-200 bg-white hover:shadow-sm transition p-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "flex flex-col gap-1" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-[13px] text-gray-500 font-medium" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-[15px] font-semibold text-gray-900 truncate" },
    });
    (__VLS_ctx.currentFile.parseResult.pages || 1);
    var __VLS_323;
    var __VLS_315;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsed-content-display" },
    });
    const __VLS_324 = {}.ACollapse;
    /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
    // @ts-ignore
    const __VLS_325 = __VLS_asFunctionalComponent(__VLS_324, new __VLS_324({}));
    const __VLS_326 = __VLS_325({}, ...__VLS_functionalComponentArgsRest(__VLS_325));
    __VLS_327.slots.default;
    const __VLS_328 = {}.ACollapsePanel;
    /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
    // @ts-ignore
    const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
        key: "content",
        header: "📄 提取的文本内容",
        ...{ class: "border border-blue-200 rounded-xl" },
    }));
    const __VLS_330 = __VLS_329({
        key: "content",
        header: "📄 提取的文本内容",
        ...{ class: "border border-blue-200 rounded-xl" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_329));
    __VLS_331.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "max-h-96 overflow-y-auto bg-gray-50 border rounded p-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
        ...{ class: "content-text font-sans text-[13px] leading-6 text-gray-800 whitespace-pre-wrap break-words m-0" },
    });
    (__VLS_ctx.currentFile.parseResult.content || '无内容');
    var __VLS_331;
    if (__VLS_ctx.currentFile.type === 'application/pdf' && __VLS_ctx.currentFile.previewUrl) {
        const __VLS_332 = {}.ACollapsePanel;
        /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
        // @ts-ignore
        const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({
            key: "pdf",
            header: "📖 PDF原文预览",
            ...{ class: "border border-blue-200 rounded-xl" },
        }));
        const __VLS_334 = __VLS_333({
            key: "pdf",
            header: "📖 PDF原文预览",
            ...{ class: "border border-blue-200 rounded-xl" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_333));
        __VLS_335.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "bg-gray-50 p-4 rounded-md border" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mb-2 flex items-center justify-between p-3 rounded-xl border border-slate-200 bg-white shadow-sm" },
        });
        const __VLS_336 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({}));
        const __VLS_338 = __VLS_337({}, ...__VLS_functionalComponentArgsRest(__VLS_337));
        __VLS_339.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-sm text-gray-600 font-medium truncate max-w-[200px]" },
        });
        (__VLS_ctx.currentFile.name);
        const __VLS_340 = {}.ADivider;
        /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
        // @ts-ignore
        const __VLS_341 = __VLS_asFunctionalComponent(__VLS_340, new __VLS_340({
            type: "vertical",
        }));
        const __VLS_342 = __VLS_341({
            type: "vertical",
        }, ...__VLS_functionalComponentArgsRest(__VLS_341));
        const __VLS_344 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
            ...{ 'onClick': {} },
            size: "small",
            disabled: (__VLS_ctx.pdfScale <= 0.5),
        }));
        const __VLS_346 = __VLS_345({
            ...{ 'onClick': {} },
            size: "small",
            disabled: (__VLS_ctx.pdfScale <= 0.5),
        }, ...__VLS_functionalComponentArgsRest(__VLS_345));
        let __VLS_348;
        let __VLS_349;
        let __VLS_350;
        const __VLS_351 = {
            onClick: (__VLS_ctx.zoomOut)
        };
        __VLS_347.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_347.slots;
            const __VLS_352 = {}.ZoomOutOutlined;
            /** @type {[typeof __VLS_components.ZoomOutOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({}));
            const __VLS_354 = __VLS_353({}, ...__VLS_functionalComponentArgsRest(__VLS_353));
        }
        var __VLS_347;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "text-sm font-medium text-gray-800 min-w-10 text-center" },
        });
        (Math.round(__VLS_ctx.pdfScale * 100));
        const __VLS_356 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_357 = __VLS_asFunctionalComponent(__VLS_356, new __VLS_356({
            ...{ 'onClick': {} },
            size: "small",
            disabled: (__VLS_ctx.pdfScale >= 2),
        }));
        const __VLS_358 = __VLS_357({
            ...{ 'onClick': {} },
            size: "small",
            disabled: (__VLS_ctx.pdfScale >= 2),
        }, ...__VLS_functionalComponentArgsRest(__VLS_357));
        let __VLS_360;
        let __VLS_361;
        let __VLS_362;
        const __VLS_363 = {
            onClick: (__VLS_ctx.zoomIn)
        };
        __VLS_359.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_359.slots;
            const __VLS_364 = {}.ZoomInOutlined;
            /** @type {[typeof __VLS_components.ZoomInOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({}));
            const __VLS_366 = __VLS_365({}, ...__VLS_functionalComponentArgsRest(__VLS_365));
        }
        var __VLS_359;
        const __VLS_368 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_369 = __VLS_asFunctionalComponent(__VLS_368, new __VLS_368({
            ...{ 'onClick': {} },
            size: "small",
        }));
        const __VLS_370 = __VLS_369({
            ...{ 'onClick': {} },
            size: "small",
        }, ...__VLS_functionalComponentArgsRest(__VLS_369));
        let __VLS_372;
        let __VLS_373;
        let __VLS_374;
        const __VLS_375 = {
            onClick: (__VLS_ctx.resetZoom)
        };
        __VLS_371.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_371.slots;
            const __VLS_376 = {}.ReloadOutlined;
            /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_377 = __VLS_asFunctionalComponent(__VLS_376, new __VLS_376({}));
            const __VLS_378 = __VLS_377({}, ...__VLS_functionalComponentArgsRest(__VLS_377));
        }
        var __VLS_371;
        var __VLS_339;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mt-3 rounded-2xl overflow-hidden bg-gradient-to-br from-sky-100/30 via-blue-100/20 to-indigo-100/30" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.iframe, __VLS_intrinsicElements.iframe)({
            src: (__VLS_ctx.currentFile.previewUrl),
            ...{ style: ({ transform: `scale(${__VLS_ctx.pdfScale})`, transformOrigin: 'top left' }) },
            width: "100%",
            height: "500px",
            frameborder: "0",
        });
        var __VLS_335;
    }
    var __VLS_327;
    var __VLS_267;
}
if (__VLS_ctx.importResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-4" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rounded-2xl p-2 md:p-3 bg-gradient-to-br from-green-100/60 via-emerald-100/50 to-teal-100/60" },
    });
    const __VLS_380 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_381 = __VLS_asFunctionalComponent(__VLS_380, new __VLS_380({
        size: "small",
        title: "🎉 智能导入成功",
        ...{ class: "rounded-2xl shadow-md ring-1 ring-emerald-200/60" },
    }));
    const __VLS_382 = __VLS_381({
        size: "small",
        title: "🎉 智能导入成功",
        ...{ class: "rounded-2xl shadow-md ring-1 ring-emerald-200/60" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_381));
    __VLS_383.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_383.slots;
        const __VLS_384 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_385 = __VLS_asFunctionalComponent(__VLS_384, new __VLS_384({}));
        const __VLS_386 = __VLS_385({}, ...__VLS_functionalComponentArgsRest(__VLS_385));
        __VLS_387.slots.default;
        const __VLS_388 = {}.ATag;
        /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
        // @ts-ignore
        const __VLS_389 = __VLS_asFunctionalComponent(__VLS_388, new __VLS_388({
            color: "success",
        }));
        const __VLS_390 = __VLS_389({
            color: "success",
        }, ...__VLS_functionalComponentArgsRest(__VLS_389));
        __VLS_391.slots.default;
        const __VLS_392 = {}.CheckCircleOutlined;
        /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_393 = __VLS_asFunctionalComponent(__VLS_392, new __VLS_392({}));
        const __VLS_394 = __VLS_393({}, ...__VLS_functionalComponentArgsRest(__VLS_393));
        var __VLS_391;
        const __VLS_396 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_397 = __VLS_asFunctionalComponent(__VLS_396, new __VLS_396({
            ...{ 'onClick': {} },
            size: "small",
            type: "primary",
        }));
        const __VLS_398 = __VLS_397({
            ...{ 'onClick': {} },
            size: "small",
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_397));
        let __VLS_400;
        let __VLS_401;
        let __VLS_402;
        const __VLS_403 = {
            onClick: (__VLS_ctx.viewInDatabase)
        };
        __VLS_399.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_399.slots;
            const __VLS_404 = {}.EyeOutlined;
            /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_405 = __VLS_asFunctionalComponent(__VLS_404, new __VLS_404({}));
            const __VLS_406 = __VLS_405({}, ...__VLS_functionalComponentArgsRest(__VLS_405));
        }
        var __VLS_399;
        var __VLS_387;
    }
    const __VLS_408 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_409 = __VLS_asFunctionalComponent(__VLS_408, new __VLS_408({
        bordered: true,
        size: "small",
        column: (2),
    }));
    const __VLS_410 = __VLS_409({
        bordered: true,
        size: "small",
        column: (2),
    }, ...__VLS_functionalComponentArgsRest(__VLS_409));
    __VLS_411.slots.default;
    const __VLS_412 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_413 = __VLS_asFunctionalComponent(__VLS_412, new __VLS_412({
        label: "记录ID",
    }));
    const __VLS_414 = __VLS_413({
        label: "记录ID",
    }, ...__VLS_functionalComponentArgsRest(__VLS_413));
    __VLS_415.slots.default;
    const __VLS_416 = {}.ATypographyText;
    /** @type {[typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, ]} */ ;
    // @ts-ignore
    const __VLS_417 = __VLS_asFunctionalComponent(__VLS_416, new __VLS_416({
        copyable: true,
    }));
    const __VLS_418 = __VLS_417({
        copyable: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_417));
    __VLS_419.slots.default;
    (__VLS_ctx.importResult.id);
    var __VLS_419;
    var __VLS_415;
    const __VLS_420 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_421 = __VLS_asFunctionalComponent(__VLS_420, new __VLS_420({
        label: "病历编号",
    }));
    const __VLS_422 = __VLS_421({
        label: "病历编号",
    }, ...__VLS_functionalComponentArgsRest(__VLS_421));
    __VLS_423.slots.default;
    const __VLS_424 = {}.ATypographyText;
    /** @type {[typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, typeof __VLS_components.ATypographyText, typeof __VLS_components.aTypographyText, ]} */ ;
    // @ts-ignore
    const __VLS_425 = __VLS_asFunctionalComponent(__VLS_424, new __VLS_424({
        copyable: true,
    }));
    const __VLS_426 = __VLS_425({
        copyable: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_425));
    __VLS_427.slots.default;
    (__VLS_ctx.importResult.record_number);
    var __VLS_427;
    var __VLS_423;
    const __VLS_428 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_429 = __VLS_asFunctionalComponent(__VLS_428, new __VLS_428({
        label: "患者姓名",
    }));
    const __VLS_430 = __VLS_429({
        label: "患者姓名",
    }, ...__VLS_functionalComponentArgsRest(__VLS_429));
    __VLS_431.slots.default;
    (__VLS_ctx.importResult.patient_name);
    var __VLS_431;
    const __VLS_432 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_433 = __VLS_asFunctionalComponent(__VLS_432, new __VLS_432({
        label: "患者信息",
    }));
    const __VLS_434 = __VLS_433({
        label: "患者信息",
    }, ...__VLS_functionalComponentArgsRest(__VLS_433));
    __VLS_435.slots.default;
    (__VLS_ctx.importResult.patient_age);
    (__VLS_ctx.importResult.patient_gender);
    var __VLS_435;
    const __VLS_436 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_437 = __VLS_asFunctionalComponent(__VLS_436, new __VLS_436({
        label: "主要诊断",
    }));
    const __VLS_438 = __VLS_437({
        label: "主要诊断",
    }, ...__VLS_functionalComponentArgsRest(__VLS_437));
    __VLS_439.slots.default;
    (__VLS_ctx.importResult.diagnosis_primary || '未识别');
    var __VLS_439;
    const __VLS_440 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_441 = __VLS_asFunctionalComponent(__VLS_440, new __VLS_440({
        label: "状态",
    }));
    const __VLS_442 = __VLS_441({
        label: "状态",
    }, ...__VLS_functionalComponentArgsRest(__VLS_441));
    __VLS_443.slots.default;
    const __VLS_444 = {}.ATag;
    /** @type {[typeof __VLS_components.ATag, typeof __VLS_components.aTag, typeof __VLS_components.ATag, typeof __VLS_components.aTag, ]} */ ;
    // @ts-ignore
    const __VLS_445 = __VLS_asFunctionalComponent(__VLS_444, new __VLS_444({
        color: (__VLS_ctx.importResult.status === 'pending' ? 'processing' : 'success'),
    }));
    const __VLS_446 = __VLS_445({
        color: (__VLS_ctx.importResult.status === 'pending' ? 'processing' : 'success'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_445));
    __VLS_447.slots.default;
    (__VLS_ctx.importResult.status === 'pending' ? '待处理' : '已完成');
    var __VLS_447;
    var __VLS_443;
    const __VLS_448 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_449 = __VLS_asFunctionalComponent(__VLS_448, new __VLS_448({
        label: "创建时间",
        span: (2),
    }));
    const __VLS_450 = __VLS_449({
        label: "创建时间",
        span: (2),
    }, ...__VLS_functionalComponentArgsRest(__VLS_449));
    __VLS_451.slots.default;
    (new Date(__VLS_ctx.importResult.created_at).toLocaleString());
    var __VLS_451;
    var __VLS_411;
    var __VLS_383;
}
if (__VLS_ctx.parseResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "rounded-2xl p-2 md:p-3 bg-gradient-to-br from-emerald-100/60 via-green-100/50 to-teal-100/60" },
    });
    const __VLS_452 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_453 = __VLS_asFunctionalComponent(__VLS_452, new __VLS_452({
        size: "small",
        title: "解析结果概览",
        ...{ class: "rounded-2xl shadow-md ring-1 ring-emerald-200/60" },
    }));
    const __VLS_454 = __VLS_453({
        size: "small",
        title: "解析结果概览",
        ...{ class: "rounded-2xl shadow-md ring-1 ring-emerald-200/60" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_453));
    __VLS_455.slots.default;
    const __VLS_456 = {}.ADescriptions;
    /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_457 = __VLS_asFunctionalComponent(__VLS_456, new __VLS_456({
        bordered: true,
        size: "small",
        column: (2),
    }));
    const __VLS_458 = __VLS_457({
        bordered: true,
        size: "small",
        column: (2),
    }, ...__VLS_functionalComponentArgsRest(__VLS_457));
    __VLS_459.slots.default;
    const __VLS_460 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_461 = __VLS_asFunctionalComponent(__VLS_460, new __VLS_460({
        label: "患者姓名",
    }));
    const __VLS_462 = __VLS_461({
        label: "患者姓名",
    }, ...__VLS_functionalComponentArgsRest(__VLS_461));
    __VLS_463.slots.default;
    ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.patientName) || '未识别');
    var __VLS_463;
    const __VLS_464 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_465 = __VLS_asFunctionalComponent(__VLS_464, new __VLS_464({
        label: "科室",
    }));
    const __VLS_466 = __VLS_465({
        label: "科室",
    }, ...__VLS_functionalComponentArgsRest(__VLS_465));
    __VLS_467.slots.default;
    ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.department) || '未识别');
    var __VLS_467;
    const __VLS_468 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_469 = __VLS_asFunctionalComponent(__VLS_468, new __VLS_468({
        label: "主要诊断",
    }));
    const __VLS_470 = __VLS_469({
        label: "主要诊断",
    }, ...__VLS_functionalComponentArgsRest(__VLS_469));
    __VLS_471.slots.default;
    ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.primaryDiagnosis) || '未识别');
    var __VLS_471;
    const __VLS_472 = {}.ADescriptionsItem;
    /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_473 = __VLS_asFunctionalComponent(__VLS_472, new __VLS_472({
        label: "文书数量",
    }));
    const __VLS_474 = __VLS_473({
        label: "文书数量",
    }, ...__VLS_functionalComponentArgsRest(__VLS_473));
    __VLS_475.slots.default;
    ((__VLS_ctx.parseResult.data && __VLS_ctx.parseResult.data.documents && __VLS_ctx.parseResult.data.documents.length) || 0);
    var __VLS_475;
    var __VLS_459;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mt-4" },
    });
    const __VLS_476 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_477 = __VLS_asFunctionalComponent(__VLS_476, new __VLS_476({}));
    const __VLS_478 = __VLS_477({}, ...__VLS_functionalComponentArgsRest(__VLS_477));
    __VLS_479.slots.default;
    const __VLS_480 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_481 = __VLS_asFunctionalComponent(__VLS_480, new __VLS_480({
        ...{ 'onClick': {} },
        type: "primary",
        ghost: true,
    }));
    const __VLS_482 = __VLS_481({
        ...{ 'onClick': {} },
        type: "primary",
        ghost: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_481));
    let __VLS_484;
    let __VLS_485;
    let __VLS_486;
    const __VLS_487 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.parseResult))
                return;
            __VLS_ctx.showResultModal = true;
        }
    };
    __VLS_483.slots.default;
    const __VLS_488 = {}.EyeOutlined;
    /** @type {[typeof __VLS_components.EyeOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_489 = __VLS_asFunctionalComponent(__VLS_488, new __VLS_488({
        ...{ class: "mr-1" },
    }));
    const __VLS_490 = __VLS_489({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_489));
    var __VLS_483;
    const __VLS_492 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_493 = __VLS_asFunctionalComponent(__VLS_492, new __VLS_492({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.saving),
        type: "primary",
    }));
    const __VLS_494 = __VLS_493({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.saving),
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_493));
    let __VLS_496;
    let __VLS_497;
    let __VLS_498;
    const __VLS_499 = {
        onClick: (__VLS_ctx.saveRecord)
    };
    __VLS_495.slots.default;
    const __VLS_500 = {}.DatabaseOutlined;
    /** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_501 = __VLS_asFunctionalComponent(__VLS_500, new __VLS_500({
        ...{ class: "mr-1" },
    }));
    const __VLS_502 = __VLS_501({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_501));
    var __VLS_495;
    const __VLS_504 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_505 = __VLS_asFunctionalComponent(__VLS_504, new __VLS_504({
        ...{ 'onClick': {} },
        type: "default",
    }));
    const __VLS_506 = __VLS_505({
        ...{ 'onClick': {} },
        type: "default",
    }, ...__VLS_functionalComponentArgsRest(__VLS_505));
    let __VLS_508;
    let __VLS_509;
    let __VLS_510;
    const __VLS_511 = {
        onClick: (__VLS_ctx.exportResult)
    };
    __VLS_507.slots.default;
    var __VLS_507;
    var __VLS_479;
    var __VLS_455;
}
if (__VLS_ctx.operationLog) {
    const __VLS_512 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_513 = __VLS_asFunctionalComponent(__VLS_512, new __VLS_512({
        size: "small",
        title: "操作日志",
        ...{ class: "mb-4 bg-white rounded-2xl shadow-lg border md:border-2 border-gray-300 hover:border-gray-400" },
    }));
    const __VLS_514 = __VLS_513({
        size: "small",
        title: "操作日志",
        ...{ class: "mb-4 bg-white rounded-2xl shadow-lg border md:border-2 border-gray-300 hover:border-gray-400" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_513));
    __VLS_515.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "bg-gray-50 rounded p-3" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
        ...{ class: "bg-gray-900 text-white p-3 rounded max-h-52 overflow-y-auto font-mono text-xs leading-5 m-0" },
    });
    (__VLS_ctx.operationLog);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "text-right mt-2" },
    });
    const __VLS_516 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_517 = __VLS_asFunctionalComponent(__VLS_516, new __VLS_516({
        ...{ 'onClick': {} },
        size: "small",
        type: "link",
    }));
    const __VLS_518 = __VLS_517({
        ...{ 'onClick': {} },
        size: "small",
        type: "link",
    }, ...__VLS_functionalComponentArgsRest(__VLS_517));
    let __VLS_520;
    let __VLS_521;
    let __VLS_522;
    const __VLS_523 = {
        onClick: (__VLS_ctx.clearLog)
    };
    __VLS_519.slots.default;
    var __VLS_519;
    var __VLS_515;
}
var __VLS_3;
const __VLS_524 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_525 = __VLS_asFunctionalComponent(__VLS_524, new __VLS_524({
    open: (__VLS_ctx.showApiConfig),
    title: "大模型API配置",
    width: "1000px",
    footer: (null),
    destroyOnClose: (true),
}));
const __VLS_526 = __VLS_525({
    open: (__VLS_ctx.showApiConfig),
    title: "大模型API配置",
    width: "1000px",
    footer: (null),
    destroyOnClose: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_525));
__VLS_527.slots.default;
const __VLS_528 = {}.LLMApiConfigStudio;
/** @type {[typeof __VLS_components.LLMApiConfigStudio, ]} */ ;
// @ts-ignore
const __VLS_529 = __VLS_asFunctionalComponent(__VLS_528, new __VLS_528({
    ...{ 'onConfigUpdated': {} },
}));
const __VLS_530 = __VLS_529({
    ...{ 'onConfigUpdated': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_529));
let __VLS_532;
let __VLS_533;
let __VLS_534;
const __VLS_535 = {
    onConfigUpdated: (__VLS_ctx.handleApiConfigUpdated)
};
var __VLS_531;
var __VLS_527;
/** @type {[typeof MedicalDocumentResultModal, ]} */ ;
// @ts-ignore
const __VLS_536 = __VLS_asFunctionalComponent(MedicalDocumentResultModal_vue_1.default, new MedicalDocumentResultModal_vue_1.default({
    ...{ 'onConfirm': {} },
    ...{ 'onConfirmOnly': {} },
    ...{ 'onExport': {} },
    visible: (__VLS_ctx.showResultModal),
    data: (__VLS_ctx.modalData),
    originalText: (__VLS_ctx.modalOriginalText),
}));
const __VLS_537 = __VLS_536({
    ...{ 'onConfirm': {} },
    ...{ 'onConfirmOnly': {} },
    ...{ 'onExport': {} },
    visible: (__VLS_ctx.showResultModal),
    data: (__VLS_ctx.modalData),
    originalText: (__VLS_ctx.modalOriginalText),
}, ...__VLS_functionalComponentArgsRest(__VLS_536));
let __VLS_539;
let __VLS_540;
let __VLS_541;
const __VLS_542 = {
    onConfirm: (__VLS_ctx.handleModalConfirm)
};
const __VLS_543 = {
    onConfirmOnly: (__VLS_ctx.handleModalConfirmOnly)
};
const __VLS_544 = {
    onExport: (__VLS_ctx.handleModalExport)
};
var __VLS_538;
/** @type {__VLS_StyleScopedClasses['min-h-screen']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['md:p-6']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-50']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-100']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/90']} */ ;
/** @type {__VLS_StyleScopedClasses['backdrop-blur-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-blue-100/70']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['md:border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-200']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-7xl']} */ ;
/** @type {__VLS_StyleScopedClasses['mx-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-center']} */ ;
/** @type {__VLS_StyleScopedClasses['w-10']} */ ;
/** @type {__VLS_StyleScopedClasses['h-10']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-100']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['md:text-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['font-extrabold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['tracking-tight']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['md:text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-0.5']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-100/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-sky-100/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-100/50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-slate-200/70']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-blue-100/50']} */ ;
/** @type {__VLS_StyleScopedClasses['via-sky-100/40']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-100/50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-slate-200/70']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-dashed']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-300/70']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-white']} */ ;
/** @type {__VLS_StyleScopedClasses['via-white']} */ ;
/** @type {__VLS_StyleScopedClasses['to-blue-50/40']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-50/40']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['md:border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white/95']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['md:border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-all']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-blue-50/60']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-800']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-600']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['md:border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['cursor-pointer']} */ ;
/** @type {__VLS_StyleScopedClasses['transition-transform']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['px-3']} */ ;
/** @type {__VLS_StyleScopedClasses['py-2']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ui-card-muted']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-blue-400']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:-translate-y-[1px]']} */ ;
/** @type {__VLS_StyleScopedClasses['duration-200']} */ ;
/** @type {__VLS_StyleScopedClasses['ease-out']} */ ;
/** @type {__VLS_StyleScopedClasses['text-blue-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-base']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-800']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-[300px]']} */ ;
/** @type {__VLS_StyleScopedClasses['truncate']} */ ;
/** @type {__VLS_StyleScopedClasses['ml-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-slate-500']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['border-t-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-100/70']} */ ;
/** @type {__VLS_StyleScopedClasses['pt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-sky-100/40']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-100/30']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-100/40']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-slate-200/70']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow']} */ ;
/** @type {__VLS_StyleScopedClasses['parse-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['grid']} */ ;
/** @type {__VLS_StyleScopedClasses['grid-cols-1']} */ ;
/** @type {__VLS_StyleScopedClasses['sm:grid-cols-2']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['transition']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[13px]']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[15px]']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['truncate']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['transition']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['flex-col']} */ ;
/** @type {__VLS_StyleScopedClasses['gap-1']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[13px]']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[15px]']} */ ;
/** @type {__VLS_StyleScopedClasses['font-semibold']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['truncate']} */ ;
/** @type {__VLS_StyleScopedClasses['parsed-content-display']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-96']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['content-text']} */ ;
/** @type {__VLS_StyleScopedClasses['font-sans']} */ ;
/** @type {__VLS_StyleScopedClasses['text-[13px]']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-6']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['break-words']} */ ;
/** @type {__VLS_StyleScopedClasses['m-0']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-blue-200']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['p-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-md']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-2']} */ ;
/** @type {__VLS_StyleScopedClasses['flex']} */ ;
/** @type {__VLS_StyleScopedClasses['items-center']} */ ;
/** @type {__VLS_StyleScopedClasses['justify-between']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-xl']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['border-slate-200']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-600']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['truncate']} */ ;
/** @type {__VLS_StyleScopedClasses['max-w-[200px]']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['font-medium']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-800']} */ ;
/** @type {__VLS_StyleScopedClasses['min-w-10']} */ ;
/** @type {__VLS_StyleScopedClasses['text-center']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-hidden']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-sky-100/30']} */ ;
/** @type {__VLS_StyleScopedClasses['via-blue-100/20']} */ ;
/** @type {__VLS_StyleScopedClasses['to-indigo-100/30']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-green-100/60']} */ ;
/** @type {__VLS_StyleScopedClasses['via-emerald-100/50']} */ ;
/** @type {__VLS_StyleScopedClasses['to-teal-100/60']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-emerald-200/60']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['p-2']} */ ;
/** @type {__VLS_StyleScopedClasses['md:p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gradient-to-br']} */ ;
/** @type {__VLS_StyleScopedClasses['from-emerald-100/60']} */ ;
/** @type {__VLS_StyleScopedClasses['via-green-100/50']} */ ;
/** @type {__VLS_StyleScopedClasses['to-teal-100/60']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-md']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-1']} */ ;
/** @type {__VLS_StyleScopedClasses['ring-emerald-200/60']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-4']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-white']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded-2xl']} */ ;
/** @type {__VLS_StyleScopedClasses['shadow-lg']} */ ;
/** @type {__VLS_StyleScopedClasses['border']} */ ;
/** @type {__VLS_StyleScopedClasses['md:border-2']} */ ;
/** @type {__VLS_StyleScopedClasses['border-gray-300']} */ ;
/** @type {__VLS_StyleScopedClasses['hover:border-gray-400']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-50']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['bg-gray-900']} */ ;
/** @type {__VLS_StyleScopedClasses['text-white']} */ ;
/** @type {__VLS_StyleScopedClasses['p-3']} */ ;
/** @type {__VLS_StyleScopedClasses['rounded']} */ ;
/** @type {__VLS_StyleScopedClasses['max-h-52']} */ ;
/** @type {__VLS_StyleScopedClasses['overflow-y-auto']} */ ;
/** @type {__VLS_StyleScopedClasses['font-mono']} */ ;
/** @type {__VLS_StyleScopedClasses['text-xs']} */ ;
/** @type {__VLS_StyleScopedClasses['leading-5']} */ ;
/** @type {__VLS_StyleScopedClasses['m-0']} */ ;
/** @type {__VLS_StyleScopedClasses['text-right']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            InboxOutlined: icons_vue_1.InboxOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            ZoomInOutlined: icons_vue_1.ZoomInOutlined,
            ZoomOutOutlined: icons_vue_1.ZoomOutOutlined,
            ThunderboltOutlined: icons_vue_1.ThunderboltOutlined,
            FileOutlined: icons_vue_1.FileOutlined,
            RobotOutlined: icons_vue_1.RobotOutlined,
            LoadingOutlined: icons_vue_1.LoadingOutlined,
            MoreOutlined: icons_vue_1.MoreOutlined,
            DeleteOutlined: icons_vue_1.DeleteOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            ExclamationCircleOutlined: icons_vue_1.ExclamationCircleOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            EyeOutlined: icons_vue_1.EyeOutlined,
            PauseCircleOutlined: icons_vue_1.PauseCircleOutlined,
            StopOutlined: icons_vue_1.StopOutlined,
            AppstoreOutlined: icons_vue_1.AppstoreOutlined,
            MedicalDocumentResultModal: MedicalDocumentResultModal_vue_1.default,
            activeTab: activeTab,
            inputText: inputText,
            parsing: parsing,
            saving: saving,
            importing: importing,
            parseResult: parseResult,
            operationLog: operationLog,
            importResult: importResult,
            showApiConfig: showApiConfig,
            currentConfig: currentConfig,
            showResultModal: showResultModal,
            modalData: modalData,
            modalOriginalText: modalOriginalText,
            uploadedFiles: uploadedFiles,
            currentFileIndex: currentFileIndex,
            pdfScale: pdfScale,
            batchParsing: batchParsing,
            batchPaused: batchPaused,
            canPauseBatch: canPauseBatch,
            batchProgress: batchProgress,
            currentFile: currentFile,
            batchProgressPercent: batchProgressPercent,
            beforeUpload: beforeUpload,
            handleUploadChange: handleUploadChange,
            selectFile: selectFile,
            removeFile: removeFile,
            clearAllFiles: clearAllFiles,
            parseAllFiles: parseAllFiles,
            smartImportToDatabase: smartImportToDatabase,
            parseText: parseText,
            smartImportTextResult: smartImportTextResult,
            clearText: clearText,
            exportResult: exportResult,
            clearLog: clearLog,
            saveRecord: saveRecord,
            handleApiConfigUpdated: handleApiConfigUpdated,
            handleCancel: handleCancel,
            zoomIn: zoomIn,
            zoomOut: zoomOut,
            resetZoom: resetZoom,
            viewImportResult: viewImportResult,
            viewInDatabase: viewInDatabase,
            formatFileSize: formatFileSize,
            handleModalConfirm: handleModalConfirm,
            handleModalConfirmOnly: handleModalConfirmOnly,
            handleModalExport: handleModalExport,
            pauseBatchProcessing: pauseBatchProcessing,
            cancelBatchProcessing: cancelBatchProcessing,
            showBatchImportView: showBatchImportView,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */

