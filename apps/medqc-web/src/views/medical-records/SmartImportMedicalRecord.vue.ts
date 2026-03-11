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
const LLMApiConfigDatabase_vue_1 = __importDefault(require("@/components/LLMApiConfigDatabase.vue"));
import llmServiceNew_1 from '@/services/llmServiceNew';
import supabaseMedicalRecordService_1 from '@/services/supabaseMedicalRecordService';
import documentParser_1 from '@/utils/documentParser';
const MedicalDocumentTree_vue_1 = __importDefault(require("@/components/MedicalDocumentTree.vue"));
import documentTypeUtils_1 from '@/utils/documentTypeUtils';
const router = (0, vue_router_1.useRouter)();
// 响应式数据
const currentStep = (0, vue_1.ref)(0);
const inputMethod = (0, vue_1.ref)('paste');
const inputText = (0, vue_1.ref)('');
const uploadFileList = (0, vue_1.ref)(: any[]);
const batchFileList = (0, vue_1.ref)(: any[]);
const uploadedContent = (0, vue_1.ref)('');
const uploadedFile = (0, vue_1.ref)(null);
const isParsingFile = (0, vue_1.ref)(false);
const batchFiles = (0, vue_1.ref)(: any[]);
const processing = (0, vue_1.ref)(false);
const parsing = (0, vue_1.ref)(false);
const importing = (0, vue_1.ref)(false);
const parsingProgress = (0, vue_1.ref)(0);
const parsingStep = (0, vue_1.ref)(0);
const reviewTab = (0, vue_1.ref)('basic');
const importedCount = (0, vue_1.ref)(0);
const importedDocumentsCount = (0, vue_1.ref)(0);
const showApiConfig = (0, vue_1.ref)(false);
// 用于目录展开时显示原文
const originalFullText = (0, vue_1.ref)('');
// 调试用的数据
const debugSelectedFile = (0, vue_1.ref)(null);
// 抽取的数据
const extractedData = (0, vue_1.reactive)({
    recordNumber: '',
    patientName: '',
    department: '',
    primaryDiagnosis: '',
    majorSurgery: '',
    documents: []
});
// 计算属性
const canProceedToNext = (0, vue_1.computed)(() => {
    if (inputMethod.value === 'paste') {
        return inputText.value.trim().length > 100;
    }
    else if (inputMethod.value === 'upload') {
        return uploadedContent.value.length > 0;
    }
    else if (inputMethod.value === 'batch') {
        return batchFiles.value.length > 0;
    }
    return false;
});
const extractedFieldsCount = (0, vue_1.computed)(() => {
    let count = 0;
    if (extractedData.patientName)
        count++;
    if (extractedData.department)
        count++;
    if (extractedData.primaryDiagnosis)
        count++;
    if (extractedData.majorSurgery)
        count++;
    count += (extractedData.documents ? extractedData.documents.length : 0);
    return count;
});
const averageConfidence = (0, vue_1.computed)(() => {
    // 模拟计算平均置信度
    return 89;
});
// 获取分组的文书类型选项
const documentTypeOptions = (0, vue_1.computed)(() => {
    return (0, documentTypeUtils_1.getGroupedDocumentTypeOptions)();
});
// 生命周期
(0, vue_1.onMounted)(async () => {
    generateRecordNumber();
    // 尝试从数据库加载默认配置
    try {
        const success = await llmServiceNew_1.llmService.loadConfigFromDatabase('default');
        if (success) {
            console.log('已加载默认LLM配置');
        }
        else {
            console.log('未找到默认配置，使用内置配置');
            loadAndApplyApiConfig(); // 回退到原有的配置加载方式
        }
    }
    catch (error) {
        console.error('加载数据库配置失败，使用内置配置:', error);
        loadAndApplyApiConfig();
    }
    // 监听全局配置更新事件
    window.addEventListener('llm-config-updated', handleGlobalConfigUpdate);
});
(0, vue_1.onUnmounted)(() => {
    // 清理事件监听器
    window.removeEventListener('llm-config-updated', handleGlobalConfigUpdate);
});
// 方法定义
const generateRecordNumber = () => {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
    extractedData.recordNumber = `MR${year}${month}${day}${random}`;
};
const handleInputMethodChange = (key) => {
    inputMethod.value = key;
    // 清空其他输入方式的数据
    if (key !== 'paste')
        inputText.value = '';
    if (key !== 'upload') {
        uploadFileList.value = [];
        uploadedContent.value = '';
    }
    if (key !== 'batch') {
        batchFileList.value = [];
        batchFiles.value = [];
    }
};
const beforeUpload = (file) => {
    console.log('beforeUpload 被调用:', file.name, file.type, file.size);
    // 验证文件类型
    const isValidType = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'].includes(file.type);
    if (!isValidType) {
        ant_design_vue_1.message.error('只支持 PDF、Word、文本文件格式');
        return false;
    }
    // 验证文件大小
    const isLt10M = file.size / 1024 / 1024 < 10;
    if (!isLt10M) {
        ant_design_vue_1.message.error('文件大小不能超过 10MB');
        return false;
    }
    console.log('文件验证通过');
    return false; // 阻止自动上传，使用 @change 事件处理
};
const beforeBatchUpload = () => {
    return false; // 阻止自动上传
};
const handleFileUpload = async (info) => {
    console.log('🔥 handleFileUpload 被调用了！', info);
    const file = (info.fileList[0] && info.fileList[0].originFileObj);
    console.log('📁 提取的文件对象:', file);
    if (file) {
        // 防止重复处理
        if (isParsingFile.value) {
            console.log('正在解析中，忽略重复请求');
            return;
        }
        // 保存文件对象供后续处理
        uploadedFile.value = file;
        // 检查文件类型是否支持
        const allowedTypes = ['text/plain', 'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
        const allowedExtensions = ['.txt', '.pdf', '.doc', '.docx'];
        const isValidType = allowedTypes.includes(file.type) || allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
        if (!isValidType) {
            ant_design_vue_1.message.error(`不支持的文件格式: ${file.name}`);
            uploadedContent.value = `不支持的文件类型: ${file.name}

请上传以下格式的文件：
- .txt (纯文本文件)
- .pdf (PDF文档)
- .doc/.docx (Word文档)`;
            return;
        }
        // 检查文件大小 (10MB限制)
        if (file.size > 10 * 1024 * 1024) {
            ant_design_vue_1.message.error('文件大小不能超过10MB');
            return;
        }
        const fileTypeDesc = getFileTypeDescription(file);
        // 开始解析
        isParsingFile.value = true;
        uploadedContent.value = `📄 正在解析文件: ${file.name}
文件大小: ${formatFileSize(file.size)}
文件类型: ${fileTypeDesc}

⏳ 正在处理中，请稍候...`;
        try {
            console.log('开始处理文件:', file.name, '类型:', file.type, '大小:', file.size);
            if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
                // PDF文件通过后端API解析
                console.log('调用PDF解析函数');
                await parsePDFFile(file);
            }
            else if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')) {
                // 文本文件直接读取
                await parseTextFile(file);
            }
            else {
                // 其他文件类型使用原有的DocumentParser
                const parseResult = await documentParser_1.DocumentParser.parseDocument(file);
                if (parseResult.success) {
                    uploadedContent.value = parseResult.content;
                    const metadata = parseResult.metadata;
                    let successMsg = `${fileTypeDesc}解析成功！`;
                    if (metadata && metadata.pages) {
                        successMsg += ` 共${metadata.pages}页`;
                    }
                    if (metadata && metadata.wordCount) {
                        successMsg += ` ${metadata.wordCount}字`;
                    }
                    ant_design_vue_1.message.success(successMsg);
                }
                else {
                    throw new Error(parseResult.error);
                }
            }
        }
        catch (error) {
            console.error('文档解析异常:', error);
            let errorMessage = error instanceof Error ? error.message : '未知错误';
            // 特殊处理网络错误
            if (error instanceof TypeError && error.message.includes('NetworkError')) {
                errorMessage = '网络连接失败，请检查网络连接';
            }
            else if (error instanceof DOMException && error.name === 'AbortError') {
                errorMessage = '请求超时，请重试';
            }
            else if (error instanceof TypeError && error.message.includes('fetch')) {
                errorMessage = '无法连接到服务器，请检查服务是否正常运行';
            }
            uploadedContent.value = `【解析失败】

【文件信息】
- 文件名: ${file.name}
- 文件大小: ${formatFileSize(file.size)}
- 文件类型: ${getFileTypeDescription(file)}

【错误详情】
${errorMessage}

【解决建议】
${getErrorSuggestions(errorMessage)}

【请尝试】
1. 重新上传文件
2. 检查文件是否损坏
3. 尝试其他格式的文件
4. 联系技术支持`;
            ant_design_vue_1.message.error(`文档解析失败: ${errorMessage}`);
        }
        finally {
            isParsingFile.value = false;
        }
    }
};
const handleBatchUpload = (info) => {
    // 模拟批量文件处理
    batchFiles.value = [
        { name: '患者张三病历.txt', size: 15420, type: 'text/plain' },
        { name: '患者李四病历.doc', size: 23680, type: 'application/msword' },
        { name: '患者王五病历.txt', size: 18950, type: 'text/plain' }
    ];
};
// 备用文件选择处理
const handleDebugFileSelect = (event) => {
    const target = event.target;
    const file = (target.files && target.files[0]);
    if (file) {
        console.log('📁 备用上传：选择了文件', file.name, file.type, file.size);
        // 检查文件类型
        const allowedTypes = ['text/plain', 'application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
        const allowedExtensions = ['.txt', '.pdf', '.doc', '.docx'];
        const isValidType = allowedTypes.includes(file.type) || allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
        if (!isValidType) {
            ant_design_vue_1.message.error(`不支持的文件格式: ${file.name}`);
            return;
        }
        // 检查文件大小 (10MB限制)
        if (file.size > 10 * 1024 * 1024) {
            ant_design_vue_1.message.error('文件大小不能超过10MB');
            return;
        }
        debugSelectedFile.value = file;
        uploadedFile.value = file; // 同步到主要的文件变量
        ant_design_vue_1.message.success(`已选择文件: ${file.name}`);
    }
};
// 备用文件解析
const handleDebugParsePDF = async () => {
    if (!debugSelectedFile.value) {
        ant_design_vue_1.message.error('请先选择一个文件');
        return;
    }
    console.log('📁 备用上传：开始解析文件', debugSelectedFile.value.name);
    try {
        isParsingFile.value = true;
        const fileTypeDesc = getFileTypeDescription(debugSelectedFile.value);
        uploadedContent.value = `📁 备用上传：正在解析文件

📄 文件信息:
- 文件名: ${debugSelectedFile.value.name}
- 文件大小: ${formatFileSize(debugSelectedFile.value.size)}
- 文件类型: ${fileTypeDesc}

⏳ 正在处理中，请稍候...`;
        // 根据文件类型选择解析方法
        if (debugSelectedFile.value.type === 'application/pdf' || debugSelectedFile.value.name.toLowerCase().endsWith('.pdf')) {
            await parsePDFFile(debugSelectedFile.value);
        }
        else if (debugSelectedFile.value.type === 'text/plain' || debugSelectedFile.value.name.toLowerCase().endsWith('.txt')) {
            await parseTextFile(debugSelectedFile.value);
        }
        else {
            // 其他文件类型使用DocumentParser
            const parseResult = await documentParser_1.DocumentParser.parseDocument(debugSelectedFile.value);
            if (parseResult.success) {
                uploadedContent.value = parseResult.content;
                ant_design_vue_1.message.success(`${fileTypeDesc}解析成功！`);
            }
            else {
                throw new Error(parseResult.error);
            }
        }
        ant_design_vue_1.message.success('文件解析完成！');
    }
    catch (error) {
        console.error('备用上传解析失败:', error);
        let errorMessage = error instanceof Error ? error.message : '未知错误';
        uploadedContent.value = `【解析失败】

【文件信息】
- 文件名: ${debugSelectedFile.value.name}
- 文件大小: ${formatFileSize(debugSelectedFile.value.size)}
- 文件类型: ${getFileTypeDescription(debugSelectedFile.value)}

【错误详情】
${errorMessage}

【解决建议】
${getErrorSuggestions(errorMessage)}

【请尝试】
1. 重新选择文件
2. 检查文件是否损坏
3. 尝试其他格式的文件`;
        ant_design_vue_1.message.error(`文件解析失败: ${errorMessage}`);
    }
    finally {
        isParsingFile.value = false;
    }
};
const formatFileSize = (bytes) => {
    if (bytes === 0)
        return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};
// 获取文件类型描述
const getFileTypeDescription = (file) => {
    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
        return 'PDF文档';
    }
    else if (file.type === 'text/plain' || file.name.toLowerCase().endsWith('.txt')) {
        return '文本文件';
    }
    else if (file.type.includes('msword') || file.name.toLowerCase().endsWith('.doc') || file.name.toLowerCase().endsWith('.docx')) {
        return 'Word文档';
    }
    return '文档';
};
// 获取错误建议
const getErrorSuggestions = (errorMessage) => {
    if (errorMessage.includes('用户未登录')) {
        return '请刷新页面重新登录后再试';
    }
    else if (errorMessage.includes('Not authenticated') || errorMessage.includes('401') || errorMessage.includes('403')) {
        return '认证失败，请检查登录状态或刷新页面重新登录';
    }
    else if (errorMessage.includes('网络连接失败') || errorMessage.includes('NetworkError')) {
        return '网络连接问题，请检查网络连接状态，确保前后端服务都在运行';
    }
    else if (errorMessage.includes('请求超时') || errorMessage.includes('timeout') || errorMessage.includes('AbortError')) {
        return '请求处理时间过长，可能是文件过大或服务器繁忙，请稍后重试';
    }
    else if (errorMessage.includes('无法连接到服务器') || errorMessage.includes('fetch')) {
        return '服务器连接失败，请确认后端服务正在运行，或联系技术支持';
    }
    else if (errorMessage.includes('网络') || errorMessage.includes('Network')) {
        return '网络连接问题，请检查网络连接后重试';
    }
    else if (errorMessage.includes('文件格式') || errorMessage.includes('format')) {
        return '文件格式不支持，请确保上传的是有效的PDF、Word或文本文件';
    }
    else if (errorMessage.includes('文件大小') || errorMessage.includes('size')) {
        return '文件过大，请上传小于10MB的文件';
    }
    else if (errorMessage.includes('解析失败') || errorMessage.includes('parse')) {
        return '文件内容解析失败，可能是文件损坏或格式异常';
    }
    else {
        return '遇到未知错误，建议重试或联系技术支持';
    }
};
// 解析PDF文件
const parsePDFFile = async (file) => {
    console.log('PDF解析函数开始，文件:', file.name, '大小:', file.size);
    try {
        // 使用ApiService来处理请求，确保token管理一致性
        const formData = new FormData();
        formData.append('file', file);
        formData.append('options', JSON.stringify({}));
        console.log('FormData创建完成，文件已添加');
        // PDF解析不需要API token，只需要用户已登录即可
        // 创建AbortController来处理请求取消
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60秒超时
        // 尝试直接调用后端，如果代理有问题的话
        const apiUrl = window.location.hostname === 'localhost'
            ? 'http://localhost:8001/api/parse-medical-file'
            : '/api/parse-medical-file';
        console.log('调用API:', apiUrl);
        console.log('发送请求...');
        const response = await fetch(apiUrl, {
            method: 'POST',
            body: formData,
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        console.log('收到响应:', response.status, response.statusText);
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }
        const result = await response.json();
        if (result.success && result.data) {
            const data = result.data;
            const content = data.content || '';
            const method = data.method || '未知方法';
            const pages = data.pages || 0;
            const medicalInfo = data.medical_info || {};
            // 构建显示内容
            let displayContent = `✅ PDF文档解析成功！

📄 文件信息:
- 文件名: ${file.name}
- 文件大小: ${formatFileSize(file.size)}
- 页数: ${pages}页
- 解析方法: ${method}
- 内容长度: ${content.length}字符

`;
            // 如果提取到医疗信息，显示它们
            if (Object.keys(medicalInfo).some(key => medicalInfo[key])) {
                displayContent += `🏥 自动提取的医疗信息:
`;
                Object.entries(medicalInfo).forEach(([key,  value]) => {
                    if (value) {
                        const keyMap = {
                            'patient_name': '患者姓名',
                            'patient_age': '年龄',
                            'patient_gender': '性别',
                            'department': '科室',
                            'diagnosis': '诊断',
                            'vital_signs': '生命体征'
                        };
                        displayContent += `- ${keyMap[key] || key}: ${Array.isArray(value) ? value.join(', ') : value}
`;
                    }
                });
                displayContent += `
`;
            }
            else {
                displayContent += `ℹ️ 未检测到结构化医疗信息，请在下方查看完整文档内容

`;
            }
            displayContent += `📝 文档内容预览:
${content.length > 2000 ? content.substring(0, 2000) + '\n\n...(内容已截断，完整内容将在AI解析时使用)' : content}

💡 提示: 您现在可以点击"开始AI解析"按钮，让系统智能提取病历信息！`;
            uploadedContent.value = displayContent;
            ant_design_vue_1.message.success(`PDF文件解析成功！共${pages}页，内容长度${content.length}字符`);
        }
        else {
            throw new Error(result.error || 'PDF解析失败');
        }
    }
    catch (error) {
        console.error('PDF解析失败:', error);
        throw error;
    }
};
// 解析文本文件
const parseTextFile = async (file) => {
    return new Promise((resolve: any,  reject: any) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const content = (e.target && e.target.result);
                uploadedContent.value = content;
                ant_design_vue_1.message.success(`文本文件读取成功！内容长度${content.length}字符`);
                resolve(content);
            }
            catch (error) {
                reject(error);
            }
        };
        reader.onerror = () => {
            reject(new Error('文件读取失败'));
        };
        reader.readAsText(file, 'UTF-8');
    });
};
const handleStartParsing = async () => {
    processing.value = true;
    parsing.value = true;
    currentStep.value = 1;
    parsingProgress.value = 0;
    parsingStep.value = 0;
    try {
        // 获取输入内容
        let textToParse = '';
        let fileToProcess = null;
        let inputMethodUsed = 'paste';
        if (inputMethod.value === 'paste') {
            textToParse = inputText.value;
            inputMethodUsed = 'paste';
        }
        else if (inputMethod.value === 'upload') {
            inputMethodUsed = 'upload';
            // 检查是否为PDF文件，需要通过后端处理
            if (uploadedFile.value && documentParser_1.DocumentParser.isPDFFile(uploadedFile.value)) {
                fileToProcess = uploadedFile.value;
                console.log('准备通过后端处理PDF文件:', fileToProcess.name);
            }
            else {
                // 其他文件类型直接使用已解析的内容
                textToParse = uploadedContent.value;
            }
        }
        else if (inputMethod.value === 'batch') {
            // 批量处理暂时使用第一个文件的内容作为示例
            textToParse = '患者张三，男，65岁，因"头晕、头痛3天"入院...';
            inputMethodUsed = 'batch';
        }
        // 验证输入
        if (!textToParse.trim() && !fileToProcess) {
            throw new Error('没有可解析的文本内容或文件');
        }
        // 显示解析进度
        await simulateAIParsing();
        // 确保在使用前加载默认配置（用户级优先，回退全局）
        await llmServiceNew_1.llmService.loadConfigFromDatabase('default');
        // 调用LLM服务进行解析
        let parseResult;
        if (fileToProcess) {
            // 处理PDF文件 - 通过后端API
            console.log('通过后端API解析PDF文件:', fileToProcess.name);
            parseResult = await llmServiceNew_1.llmService.parseMedicalFileViaBackend(fileToProcess, {
                extractPatientInfo: true,
                extractDiagnosis: true,
                extractSurgeryInfo: true,
                classifyDocuments: true,
                confidenceThreshold: 0.7
            });
        }
        else {
            // 处理文本内容
            console.log('开始AI解析文本内容，长度:', textToParse.length);
            parseResult = await llmServiceNew_1.llmService.parseMedicalText(textToParse, {
                extractPatientInfo: true,
                extractDiagnosis: true,
                extractSurgeryInfo: true,
                classifyDocuments: true,
                confidenceThreshold: 0.7
            });
        }
        if (!parseResult.success || !parseResult.data) {
            throw new Error(parseResult.error || 'AI解析失败');
        }
        // 保存原始全文，供目录视图展开时使用
        originalFullText.value = parseResult.data.content || '';
        // 更新解析结果（用于当前页小结展示）
        const data = parseResult.data;
        Object.assign(extractedData, {
            patientName: data.patientName || '',
            department: data.department || '',
            primaryDiagnosis: data.primaryDiagnosis || '',
            majorSurgery: data.majorSurgery || '',
            documents: (data.documents ? data.documents.map(doc => ({
                id: doc.id,
                type: doc.type,
                title: doc.title,
                content: doc.content,
                confidence: doc.confidence
            })) : [])
        });
        // 写入全局store与session，并跳转到结果页
        const { useLLMParseStore } = await Promise.resolve().then(() => __importStar(require('@/stores/llmParse')));
        const store = useLLMParseStore();
        store.setResult(parseResult);
        await router.push('/dashboard/llm-result');
        // 成本提示：显示本次解析的 token 用量与节省估算（结果页里也会展示）
        const tokensUsed = parseResult.tokensUsed || 0;
        if (tokensUsed > 0) {
            const baselineTokens = (parseResult.data?.content ? Math.round(parseResult.data.content.length / 4) : Math.round((textToParse || '').length / 4)) + 1000;
            const saved = Math.max(0, baselineTokens - tokensUsed);
            const savedPct = baselineTokens > 0 ? Math.round((saved / baselineTokens) * 100) : 0;
            ant_design_vue_1.message.info(`本次LLM用量≈${tokensUsed} tokens，较旧方案预计节省≈${savedPct}%`, 6);
        }
        ant_design_vue_1.message.success('AI解析完成！');
    }
    catch (error) {
        console.error('AI解析失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '解析失败，请重试');
        currentStep.value = 0;
    }
    finally {
        processing.value = false;
        parsing.value = false;
    }
};
const simulateAIParsing = async () => {
    const steps = [
        { step: 1, progress: 25, delay: 1000 },
        { step: 2, progress: 50, delay: 1500 },
        { step: 3, progress: 75, delay: 2000 },
        { step: 4, progress: 100, delay: 1000 }
    ];
    for (const { step, progress, delay } of steps) {
        parsingStep.value = step;
        parsingProgress.value = progress;
        await new Promise(resolve => setTimeout(resolve, delay));
    }
};
const handleBackToInput = () => {
    currentStep.value = 0;
};
const handleReparse = async () => {
    await handleStartParsing();
};
const handleConfirmImport = async () => {
    importing.value = true;
    try {
        // 获取原始文本
        let rawText = '';
        let inputMethodUsed = 'paste';
        if (inputMethod.value === 'paste') {
            rawText = inputText.value;
            inputMethodUsed = 'paste';
        }
        else if (inputMethod.value === 'upload') {
            rawText = uploadedContent.value;
            inputMethodUsed = 'upload';
        }
        else if (inputMethod.value === 'batch') {
            rawText = '批量导入的病历文本内容...';
            inputMethodUsed = 'batch';
        }
        // 构建ExtractedMedicalData对象
        const extractedMedicalData = {
            recordNumber: extractedData.recordNumber,
            patientName: extractedData.patientName,
            patientAge: extractedData.patientAge,
            patientGender: extractedData.patientGender,
            department: extractedData.department,
            primaryDiagnosis: extractedData.primaryDiagnosis,
            secondaryDiagnosis: extractedData.secondaryDiagnosis,
            majorSurgery: extractedData.majorSurgery,
            documents: (extractedData.documents ? extractedData.documents.map((doc, idx) => ({
                id: doc.id,
                type: doc.type,
                title: doc.title,
                content: doc.content,
                confidence: doc.confidence,
                extractedAt: new Date(),
                position: doc.position
            })) : []),
            confidence: averageConfidence.value
        };
        // 保存到Supabase数据库（测试表）
        const savedRecord = await supabaseMedicalRecordService_1.supabaseMedicalRecordService.saveAIExtractionResult(extractedMedicalData, rawText, inputMethodUsed, 2500, 1250);
        // 同步写入医疗文书表
        try {
            const { createDocumentsBatch } = await Promise.resolve().then(() => __importStar(require('@/services/medicalDocumentApi')));
            const baseText = originalFullText.value || rawText || '';
            const batch = (extractedMedicalData.documents || : any[]).map((d, idx: any) => {
                const pos = d.position || {};
                const si = pos.startIndex;
                const ei = pos.endIndex;
                let full = '';
                if (typeof si === 'number' && typeof ei === 'number' && ei > si && ei <= baseText.length) {
                    full = baseText.slice(si, ei);
                }
                else if (pos.startMarker) {
                    const startIdx = baseText.indexOf(pos.startMarker);
                    if (startIdx >= 0) {
                        if (pos.endMarker) {
                            const after = baseText.indexOf(pos.endMarker, startIdx + String(pos.startMarker).length);
                            if (after > startIdx)
                                full = baseText.slice(startIdx, after);
                        }
                        if (!full)
                            full = baseText.slice(startIdx, Math.min(baseText.length, startIdx + 4000));
                    }
                }
                if (!full)
                    full = d.content || '';
                return {
                    record_id: savedRecord.id,
                    document_type: d.type,
                    title: d.title || '',
                    content: full,
                    summary: d.content || '',
                    ai_classified: true,
                    ai_confidence_score: d.confidence || 0,
                    position: d.position || undefined,
                    sort_order: idx,
                    status: 'active'
                };
            });
            if (batch.length)
                await createDocumentsBatch(batch);
        }
        catch (e) {
            console.warn('写入医疗文书表失败（不中断流程）:', e);
        }
        importedCount.value = 1;
        importedDocumentsCount.value = (extractedData.documents ? extractedData.documents.length : 0);
        // 保存记录ID用于后续查看
        localStorage.setItem('lastImportedRecordId', savedRecord.id);
        currentStep.value = 3;
        ant_design_vue_1.message.success('病历导入成功！');
    }
    catch (error) {
        console.error('导入失败:', error);
        ant_design_vue_1.message.error(error instanceof Error ? error.message : '导入失败，请重试');
    }
    finally {
        importing.value = false;
    }
};
const handleViewImported = () => {
    const recordId = localStorage.getItem('lastImportedRecordId');
    if (recordId) {
        router.push(`/dashboard/medical-records/edit/${recordId}`);
    }
    else {
        router.push('/dashboard/medical-records');
    }
};
const handleImportAnother = () => {
    // 重置所有状态
    currentStep.value = 0;
    inputText.value = '';
    uploadFileList.value = [];
    uploadedContent.value = '';
    batchFiles.value = [];
    Object.assign(extractedData, {
        recordNumber: '',
        patientName: '',
        department: '',
        primaryDiagnosis: '',
        majorSurgery: '',
        documents: []
    });
    generateRecordNumber();
};
const handleBackToList = () => {
    router.push('/dashboard/medical-records');
};
// 读取并应用API配置（兼容旧版本）
const loadAndApplyApiConfig = async () => {
    try {
        // 首先尝试从数据库加载默认配置
        const success = await llmServiceNew_1.llmService.loadConfigFromDatabase('default');
        if (success) {
            console.log('已从数据库加载默认配置');
            return;
        }
        // 如果数据库没有配置，尝试从localStorage加载（向后兼容）
        const savedConfig = localStorage.getItem('llm-api-config');
        console.log('尝试从localStorage加载API配置:', savedConfig);
        if (savedConfig) {
            const configData = JSON.parse(savedConfig);
            console.log('解析的配置数据:', configData);
            // 使用基本配置（不依赖ENHANCED_LLM_API_CONFIGS）
            llmServiceNew_1.llmService.updateConfig({
                apiEndpoint: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
                apiKey: configData.apiKey || '',
                model: configData.selectedModel || 'qwen-plus'
            });
            console.log('已加载并应用localStorage配置:', {
                model: configData.selectedModel,
                hasApiKey: !!configData.apiKey
            });
        }
        else {
            console.log('未找到保存的API配置，使用默认配置');
            console.log('当前localStorage中的所有key:', Object.keys(localStorage));
        }
    }
    catch (error) {
        console.error('加载API配置失败:', error);
    }
};
// API配置更新处理
const handleApiConfigUpdated = async (config) => {
    console.log('API配置已更新:', config);
    try {
        // 从数据库加载配置到llmService实例
        const success = await llmServiceNew_1.llmService.loadConfigFromDatabase(config.config_name);
        if (success) {
            ant_design_vue_1.message.success(`已切换到配置: ${config.config_name}`);
            showApiConfig.value = false;
        }
        else {
            ant_design_vue_1.message.error('加载配置失败');
        }
    }
    catch (error) {
        console.error('应用API配置失败:', error);
        ant_design_vue_1.message.error('应用配置失败');
    }
};
// 处理全局配置更新事件
const handleGlobalConfigUpdate = async (event) => {
    const configData = event.detail;
    console.log('收到全局配置更新事件:', configData);
    try {
        // 从数据库重新加载配置
        const success = await llmServiceNew_1.llmService.loadConfigFromDatabase('default');
        if (success) {
            console.log('已应用全局配置更新');
        }
    }
    catch (error) {
        console.error('应用全局配置更新失败:', error);
    }
};
const handleCancel = () => {
    router.back();
};
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['steps-card']} */ ;
/** @type {__VLS_StyleScopedClasses['step-card']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-card-body']} */ ;
/** @type {__VLS_StyleScopedClasses['step-card']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['textarea-container']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input-data-count']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['uploaded-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-status']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-status']} */ ;
/** @type {__VLS_StyleScopedClasses['parsed-content']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-content']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-content']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-step']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-step']} */ ;
/** @type {__VLS_StyleScopedClasses['document-header']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-breakdown']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-item']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-breadcrumb']} */ ;
/** @type {__VLS_StyleScopedClasses['selected-file-info']} */ ;
/** @type {__VLS_StyleScopedClasses['selected-file-info']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-container" },
});
const __VLS_0 = {}.ABreadcrumb;
/** @type {[typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, typeof __VLS_components.ABreadcrumb, typeof __VLS_components.aBreadcrumb, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "breadcrumb" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "breadcrumb" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({}));
const __VLS_6 = __VLS_5({}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.RouterLink;
/** @type {[typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, typeof __VLS_components.RouterLink, typeof __VLS_components.routerLink, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    to: "/dashboard/medical-records",
}));
const __VLS_10 = __VLS_9({
    to: "/dashboard/medical-records",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
var __VLS_11;
var __VLS_7;
const __VLS_12 = {}.ABreadcrumbItem;
/** @type {[typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, typeof __VLS_components.ABreadcrumbItem, typeof __VLS_components.aBreadcrumbItem, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
__VLS_15.slots.default;
var __VLS_15;
var __VLS_3;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-text" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-description" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-actions" },
});
const __VLS_16 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    ...{ 'onClick': {} },
    type: "text",
}));
const __VLS_18 = __VLS_17({
    ...{ 'onClick': {} },
    type: "text",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
let __VLS_20;
let __VLS_21;
let __VLS_22;
const __VLS_23 = {
    onClick: (...[$event]) => {
        __VLS_ctx.showApiConfig = true;
    }
};
__VLS_19.slots.default;
{
    const { icon: __VLS_thisSlot } = __VLS_19.slots;
    const __VLS_24 = {}.SettingOutlined;
    /** @type {[typeof __VLS_components.SettingOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({}));
    const __VLS_26 = __VLS_25({}, ...__VLS_functionalComponentArgsRest(__VLS_25));
}
var __VLS_19;
const __VLS_28 = {}.ACard;
/** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ class: "steps-card" },
}));
const __VLS_30 = __VLS_29({
    ...{ class: "steps-card" },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
__VLS_31.slots.default;
const __VLS_32 = {}.ASteps;
/** @type {[typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, typeof __VLS_components.ASteps, typeof __VLS_components.aSteps, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    current: (__VLS_ctx.currentStep),
    size: "small",
}));
const __VLS_34 = __VLS_33({
    current: (__VLS_ctx.currentStep),
    size: "small",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    title: "输入病历文本",
    description: "粘贴或上传病历内容",
}));
const __VLS_38 = __VLS_37({
    title: "输入病历文本",
    description: "粘贴或上传病历内容",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
const __VLS_40 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    title: "AI智能解析",
    description: "自动抽取结构化信息",
}));
const __VLS_42 = __VLS_41({
    title: "AI智能解析",
    description: "自动抽取结构化信息",
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
const __VLS_44 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    title: "确认和修正",
    description: "检查并修正解析结果",
}));
const __VLS_46 = __VLS_45({
    title: "确认和修正",
    description: "检查并修正解析结果",
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
const __VLS_48 = {}.AStep;
/** @type {[typeof __VLS_components.AStep, typeof __VLS_components.aStep, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    title: "完成导入",
    description: "保存到病历系统",
}));
const __VLS_50 = __VLS_49({
    title: "完成导入",
    description: "保存到病历系统",
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
var __VLS_35;
var __VLS_31;
if (__VLS_ctx.currentStep === 0) {
    const __VLS_52 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        title: "步骤1: 输入病历文本",
        ...{ class: "step-card" },
    }));
    const __VLS_54 = __VLS_53({
        title: "步骤1: 输入病历文本",
        ...{ class: "step-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    const __VLS_56 = {}.ATabs;
    /** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        ...{ 'onChange': {} },
        activeKey: (__VLS_ctx.inputMethod),
    }));
    const __VLS_58 = __VLS_57({
        ...{ 'onChange': {} },
        activeKey: (__VLS_ctx.inputMethod),
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    let __VLS_60;
    let __VLS_61;
    let __VLS_62;
    const __VLS_63 = {
        onChange: (__VLS_ctx.handleInputMethodChange)
    };
    __VLS_59.slots.default;
    const __VLS_64 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        key: "paste",
        tab: "文本粘贴",
    }));
    const __VLS_66 = __VLS_65({
        key: "paste",
        tab: "文本粘贴",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "input-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "textarea-container" },
    });
    const __VLS_68 = {}.ATextarea;
    /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
    // @ts-ignore
    const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
        value: (__VLS_ctx.inputText),
        placeholder: "请粘贴完整的病历文本内容，包括入院记录、病程记录、出院小结等...",
        rows: (8),
        maxLength: (50000),
        showCount: true,
        ...{ class: "enhanced-text-input" },
        autoSize: ({ minRows: 8, maxRows: 20 }),
    }));
    const __VLS_70 = __VLS_69({
        value: (__VLS_ctx.inputText),
        placeholder: "请粘贴完整的病历文本内容，包括入院记录、病程记录、出院小结等...",
        rows: (8),
        maxLength: (50000),
        showCount: true,
        ...{ class: "enhanced-text-input" },
        autoSize: ({ minRows: 8, maxRows: 20 }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_69));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "input-tips" },
    });
    const __VLS_72 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        message: "输入提示",
        description: "请粘贴包含患者基本信息、入院记录、病程记录、出院记录等完整病历内容的文本。AI将自动识别和分类不同的文书类型。",
        type: "info",
        showIcon: true,
    }));
    const __VLS_74 = __VLS_73({
        message: "输入提示",
        description: "请粘贴包含患者基本信息、入院记录、病程记录、出院记录等完整病历内容的文本。AI将自动识别和分类不同的文书类型。",
        type: "info",
        showIcon: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    var __VLS_67;
    const __VLS_76 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
        key: "upload",
        tab: "文件上传",
    }));
    const __VLS_78 = __VLS_77({
        key: "upload",
        tab: "文件上传",
    }, ...__VLS_functionalComponentArgsRest(__VLS_77));
    __VLS_79.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "upload-section" },
    });
    const __VLS_80 = {}.AUploadDragger;
    /** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        ...{ 'onChange': {} },
        fileList: (__VLS_ctx.uploadFileList),
        beforeUpload: (__VLS_ctx.beforeUpload),
        accept: ".txt,.doc,.docx,.pdf",
        multiple: (false),
        showUploadList: (false),
        fileList: ([]),
    }));
    const __VLS_82 = __VLS_81({
        ...{ 'onChange': {} },
        fileList: (__VLS_ctx.uploadFileList),
        beforeUpload: (__VLS_ctx.beforeUpload),
        accept: ".txt,.doc,.docx,.pdf",
        multiple: (false),
        showUploadList: (false),
        fileList: ([]),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    let __VLS_84;
    let __VLS_85;
    let __VLS_86;
    const __VLS_87 = {
        onChange: (__VLS_ctx.handleFileUpload)
    };
    __VLS_83.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-drag-icon" },
    });
    const __VLS_88 = {}.InboxOutlined;
    /** @type {[typeof __VLS_components.InboxOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
    const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-hint" },
    });
    var __VLS_83;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alternative-upload-section mt-4" },
    });
    const __VLS_92 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({}));
    const __VLS_94 = __VLS_93({}, ...__VLS_functionalComponentArgsRest(__VLS_93));
    __VLS_95.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "text-sm text-gray-500" },
    });
    const __VLS_96 = {}.FileTextOutlined;
    /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        ...{ class: "mr-1" },
    }));
    const __VLS_98 = __VLS_97({
        ...{ class: "mr-1" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    var __VLS_95;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "alternative-upload-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mb-3" },
    });
    const __VLS_100 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
        message: "如果上方的拖拽上传遇到问题，可以使用下面的备用方式",
        type: "info",
        showIcon: true,
        closable: (false),
        ...{ class: "text-sm" },
    }));
    const __VLS_102 = __VLS_101({
        message: "如果上方的拖拽上传遇到问题，可以使用下面的备用方式",
        type: "info",
        showIcon: true,
        closable: (false),
        ...{ class: "text-sm" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_101));
    const __VLS_104 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
        direction: "vertical",
        ...{ class: "w-full" },
    }));
    const __VLS_106 = __VLS_105({
        direction: "vertical",
        ...{ class: "w-full" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_105));
    __VLS_107.slots.default;
    const __VLS_108 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({}));
    const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
    __VLS_111.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
        ...{ onChange: (__VLS_ctx.handleDebugFileSelect) },
        ref: "debugFileInput",
        type: "file",
        accept: ".pdf,.txt,.doc,.docx",
        ...{ style: {} },
    });
    /** @type {typeof __VLS_ctx.debugFileInput} */ ;
    const __VLS_112 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
        ...{ 'onClick': {} },
        type: "default",
        loading: (__VLS_ctx.isParsingFile),
        disabled: (__VLS_ctx.isParsingFile),
    }));
    const __VLS_114 = __VLS_113({
        ...{ 'onClick': {} },
        type: "default",
        loading: (__VLS_ctx.isParsingFile),
        disabled: (__VLS_ctx.isParsingFile),
    }, ...__VLS_functionalComponentArgsRest(__VLS_113));
    let __VLS_116;
    let __VLS_117;
    let __VLS_118;
    const __VLS_119 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.currentStep === 0))
                return;
            __VLS_ctx.$refs.debugFileInput && __VLS_ctx.$refs.debugFileInput.click();
        }
    };
    __VLS_115.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_115.slots;
        const __VLS_120 = {}.FileTextOutlined;
        /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({}));
        const __VLS_122 = __VLS_121({}, ...__VLS_functionalComponentArgsRest(__VLS_121));
    }
    var __VLS_115;
    if (__VLS_ctx.debugSelectedFile) {
        const __VLS_124 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
            ...{ 'onClick': {} },
            type: "primary",
            loading: (__VLS_ctx.isParsingFile),
            disabled: (__VLS_ctx.isParsingFile),
        }));
        const __VLS_126 = __VLS_125({
            ...{ 'onClick': {} },
            type: "primary",
            loading: (__VLS_ctx.isParsingFile),
            disabled: (__VLS_ctx.isParsingFile),
        }, ...__VLS_functionalComponentArgsRest(__VLS_125));
        let __VLS_128;
        let __VLS_129;
        let __VLS_130;
        const __VLS_131 = {
            onClick: (__VLS_ctx.handleDebugParsePDF)
        };
        __VLS_127.slots.default;
        {
            const { icon: __VLS_thisSlot } = __VLS_127.slots;
            const __VLS_132 = {}.RobotOutlined;
            /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({}));
            const __VLS_134 = __VLS_133({}, ...__VLS_functionalComponentArgsRest(__VLS_133));
        }
        var __VLS_127;
    }
    var __VLS_111;
    if (__VLS_ctx.debugSelectedFile) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "selected-file-info" },
        });
        const __VLS_136 = {}.ADescriptions;
        /** @type {[typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, typeof __VLS_components.ADescriptions, typeof __VLS_components.aDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
            size: "small",
            column: (1),
            bordered: true,
        }));
        const __VLS_138 = __VLS_137({
            size: "small",
            column: (1),
            bordered: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_137));
        __VLS_139.slots.default;
        const __VLS_140 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_141 = __VLS_asFunctionalComponent(__VLS_140, new __VLS_140({
            label: "文件名",
        }));
        const __VLS_142 = __VLS_141({
            label: "文件名",
        }, ...__VLS_functionalComponentArgsRest(__VLS_141));
        __VLS_143.slots.default;
        (__VLS_ctx.debugSelectedFile.name);
        var __VLS_143;
        const __VLS_144 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({
            label: "文件大小",
        }));
        const __VLS_146 = __VLS_145({
            label: "文件大小",
        }, ...__VLS_functionalComponentArgsRest(__VLS_145));
        __VLS_147.slots.default;
        (__VLS_ctx.formatFileSize(__VLS_ctx.debugSelectedFile.size));
        var __VLS_147;
        const __VLS_148 = {}.ADescriptionsItem;
        /** @type {[typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, typeof __VLS_components.ADescriptionsItem, typeof __VLS_components.aDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({
            label: "文件类型",
        }));
        const __VLS_150 = __VLS_149({
            label: "文件类型",
        }, ...__VLS_functionalComponentArgsRest(__VLS_149));
        __VLS_151.slots.default;
        (__VLS_ctx.getFileTypeDescription(__VLS_ctx.debugSelectedFile));
        var __VLS_151;
        var __VLS_139;
    }
    var __VLS_107;
    if (__VLS_ctx.uploadedContent || __VLS_ctx.isParsingFile) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "uploaded-preview" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "content-preview-enhanced" },
        });
        if (__VLS_ctx.isParsingFile) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "parsing-status" },
            });
            const __VLS_152 = {}.ASpin;
            /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
            // @ts-ignore
            const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
                size: "large",
            }));
            const __VLS_154 = __VLS_153({
                size: "large",
            }, ...__VLS_functionalComponentArgsRest(__VLS_153));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "text-sm text-gray-500 mt-2" },
            });
        }
        else {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "parsed-content" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.pre, __VLS_intrinsicElements.pre)({
                ...{ class: "whitespace-pre-wrap" },
            });
            (__VLS_ctx.uploadedContent);
        }
    }
    var __VLS_79;
    const __VLS_156 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_157 = __VLS_asFunctionalComponent(__VLS_156, new __VLS_156({
        key: "batch",
        tab: "批量导入",
    }));
    const __VLS_158 = __VLS_157({
        key: "batch",
        tab: "批量导入",
    }, ...__VLS_functionalComponentArgsRest(__VLS_157));
    __VLS_159.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "batch-section" },
    });
    const __VLS_160 = {}.AUploadDragger;
    /** @type {[typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, typeof __VLS_components.AUploadDragger, typeof __VLS_components.aUploadDragger, ]} */ ;
    // @ts-ignore
    const __VLS_161 = __VLS_asFunctionalComponent(__VLS_160, new __VLS_160({
        ...{ 'onChange': {} },
        fileList: (__VLS_ctx.batchFileList),
        beforeUpload: (__VLS_ctx.beforeBatchUpload),
        accept: ".zip,.rar",
        multiple: (false),
    }));
    const __VLS_162 = __VLS_161({
        ...{ 'onChange': {} },
        fileList: (__VLS_ctx.batchFileList),
        beforeUpload: (__VLS_ctx.beforeBatchUpload),
        accept: ".zip,.rar",
        multiple: (false),
    }, ...__VLS_functionalComponentArgsRest(__VLS_161));
    let __VLS_164;
    let __VLS_165;
    let __VLS_166;
    const __VLS_167 = {
        onChange: (__VLS_ctx.handleBatchUpload)
    };
    __VLS_163.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-drag-icon" },
    });
    const __VLS_168 = {}.FolderOpenOutlined;
    /** @type {[typeof __VLS_components.FolderOpenOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_169 = __VLS_asFunctionalComponent(__VLS_168, new __VLS_168({}));
    const __VLS_170 = __VLS_169({}, ...__VLS_functionalComponentArgsRest(__VLS_169));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-text" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "ant-upload-hint" },
    });
    var __VLS_163;
    if (__VLS_ctx.batchFiles.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "batch-preview" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
        (__VLS_ctx.batchFiles.length);
        const __VLS_172 = {}.AList;
        /** @type {[typeof __VLS_components.AList, typeof __VLS_components.aList, typeof __VLS_components.AList, typeof __VLS_components.aList, ]} */ ;
        // @ts-ignore
        const __VLS_173 = __VLS_asFunctionalComponent(__VLS_172, new __VLS_172({
            size: "small",
            dataSource: (__VLS_ctx.batchFiles),
        }));
        const __VLS_174 = __VLS_173({
            size: "small",
            dataSource: (__VLS_ctx.batchFiles),
        }, ...__VLS_functionalComponentArgsRest(__VLS_173));
        __VLS_175.slots.default;
        {
            const { renderItem: __VLS_thisSlot } = __VLS_175.slots;
            const [{ item }] = __VLS_getSlotParams(__VLS_thisSlot);
            const __VLS_176 = {}.AListItem;
            /** @type {[typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, typeof __VLS_components.AListItem, typeof __VLS_components.aListItem, ]} */ ;
            // @ts-ignore
            const __VLS_177 = __VLS_asFunctionalComponent(__VLS_176, new __VLS_176({}));
            const __VLS_178 = __VLS_177({}, ...__VLS_functionalComponentArgsRest(__VLS_177));
            __VLS_179.slots.default;
            const __VLS_180 = {}.AListItemMeta;
            /** @type {[typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, typeof __VLS_components.AListItemMeta, typeof __VLS_components.aListItemMeta, ]} */ ;
            // @ts-ignore
            const __VLS_181 = __VLS_asFunctionalComponent(__VLS_180, new __VLS_180({}));
            const __VLS_182 = __VLS_181({}, ...__VLS_functionalComponentArgsRest(__VLS_181));
            __VLS_183.slots.default;
            {
                const { title: __VLS_thisSlot } = __VLS_183.slots;
                (item.name);
            }
            {
                const { description: __VLS_thisSlot } = __VLS_183.slots;
                (__VLS_ctx.formatFileSize(item.size));
                (item.type);
            }
            var __VLS_183;
            var __VLS_179;
        }
        var __VLS_175;
    }
    var __VLS_159;
    var __VLS_59;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "step-actions" },
    });
    const __VLS_184 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_185 = __VLS_asFunctionalComponent(__VLS_184, new __VLS_184({}));
    const __VLS_186 = __VLS_185({}, ...__VLS_functionalComponentArgsRest(__VLS_185));
    __VLS_187.slots.default;
    const __VLS_188 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_189 = __VLS_asFunctionalComponent(__VLS_188, new __VLS_188({
        ...{ 'onClick': {} },
    }));
    const __VLS_190 = __VLS_189({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_189));
    let __VLS_192;
    let __VLS_193;
    let __VLS_194;
    const __VLS_195 = {
        onClick: (__VLS_ctx.handleCancel)
    };
    __VLS_191.slots.default;
    var __VLS_191;
    const __VLS_196 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_197 = __VLS_asFunctionalComponent(__VLS_196, new __VLS_196({
        ...{ 'onClick': {} },
        type: "primary",
        disabled: (!__VLS_ctx.canProceedToNext),
        loading: (__VLS_ctx.processing),
    }));
    const __VLS_198 = __VLS_197({
        ...{ 'onClick': {} },
        type: "primary",
        disabled: (!__VLS_ctx.canProceedToNext),
        loading: (__VLS_ctx.processing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_197));
    let __VLS_200;
    let __VLS_201;
    let __VLS_202;
    const __VLS_203 = {
        onClick: (__VLS_ctx.handleStartParsing)
    };
    __VLS_199.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_199.slots;
        const __VLS_204 = {}.RobotOutlined;
        /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_205 = __VLS_asFunctionalComponent(__VLS_204, new __VLS_204({}));
        const __VLS_206 = __VLS_205({}, ...__VLS_functionalComponentArgsRest(__VLS_205));
    }
    var __VLS_199;
    var __VLS_187;
    var __VLS_55;
}
if (__VLS_ctx.currentStep === 1) {
    const __VLS_208 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_209 = __VLS_asFunctionalComponent(__VLS_208, new __VLS_208({
        title: "步骤2: AI智能解析",
        ...{ class: "step-card" },
    }));
    const __VLS_210 = __VLS_209({
        title: "步骤2: AI智能解析",
        ...{ class: "step-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_209));
    __VLS_211.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-progress" },
    });
    const __VLS_212 = {}.ASpin;
    /** @type {[typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, typeof __VLS_components.ASpin, typeof __VLS_components.aSpin, ]} */ ;
    // @ts-ignore
    const __VLS_213 = __VLS_asFunctionalComponent(__VLS_212, new __VLS_212({
        size: "large",
        spinning: (__VLS_ctx.parsing),
    }));
    const __VLS_214 = __VLS_213({
        size: "large",
        spinning: (__VLS_ctx.parsing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_213));
    __VLS_215.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-content" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-icon" },
    });
    const __VLS_216 = {}.RobotOutlined;
    /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_217 = __VLS_asFunctionalComponent(__VLS_216, new __VLS_216({}));
    const __VLS_218 = __VLS_217({}, ...__VLS_functionalComponentArgsRest(__VLS_217));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    const __VLS_220 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_221 = __VLS_asFunctionalComponent(__VLS_220, new __VLS_220({
        percent: (__VLS_ctx.parsingProgress),
        status: (__VLS_ctx.parsing ? 'active' : 'success'),
        showInfo: (true),
    }));
    const __VLS_222 = __VLS_221({
        percent: (__VLS_ctx.parsingProgress),
        status: (__VLS_ctx.parsing ? 'active' : 'success'),
        showInfo: (true),
    }, ...__VLS_functionalComponentArgsRest(__VLS_221));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-steps" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-step" },
        ...{ class: ({ active: __VLS_ctx.parsingStep >= 1, completed: __VLS_ctx.parsingStep > 1 }) },
    });
    if (__VLS_ctx.parsingStep > 1) {
        const __VLS_224 = {}.CheckCircleOutlined;
        /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_225 = __VLS_asFunctionalComponent(__VLS_224, new __VLS_224({}));
        const __VLS_226 = __VLS_225({}, ...__VLS_functionalComponentArgsRest(__VLS_225));
    }
    else if (__VLS_ctx.parsingStep === 1) {
        const __VLS_228 = {}.LoadingOutlined;
        /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_229 = __VLS_asFunctionalComponent(__VLS_228, new __VLS_228({}));
        const __VLS_230 = __VLS_229({}, ...__VLS_functionalComponentArgsRest(__VLS_229));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-step" },
        ...{ class: ({ active: __VLS_ctx.parsingStep >= 2, completed: __VLS_ctx.parsingStep > 2 }) },
    });
    if (__VLS_ctx.parsingStep > 2) {
        const __VLS_232 = {}.CheckCircleOutlined;
        /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_233 = __VLS_asFunctionalComponent(__VLS_232, new __VLS_232({}));
        const __VLS_234 = __VLS_233({}, ...__VLS_functionalComponentArgsRest(__VLS_233));
    }
    else if (__VLS_ctx.parsingStep === 2) {
        const __VLS_236 = {}.LoadingOutlined;
        /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_237 = __VLS_asFunctionalComponent(__VLS_236, new __VLS_236({}));
        const __VLS_238 = __VLS_237({}, ...__VLS_functionalComponentArgsRest(__VLS_237));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-step" },
        ...{ class: ({ active: __VLS_ctx.parsingStep >= 3, completed: __VLS_ctx.parsingStep > 3 }) },
    });
    if (__VLS_ctx.parsingStep > 3) {
        const __VLS_240 = {}.CheckCircleOutlined;
        /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_241 = __VLS_asFunctionalComponent(__VLS_240, new __VLS_240({}));
        const __VLS_242 = __VLS_241({}, ...__VLS_functionalComponentArgsRest(__VLS_241));
    }
    else if (__VLS_ctx.parsingStep === 3) {
        const __VLS_244 = {}.LoadingOutlined;
        /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_245 = __VLS_asFunctionalComponent(__VLS_244, new __VLS_244({}));
        const __VLS_246 = __VLS_245({}, ...__VLS_functionalComponentArgsRest(__VLS_245));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-step" },
        ...{ class: ({ active: __VLS_ctx.parsingStep >= 4, completed: __VLS_ctx.parsingStep > 4 }) },
    });
    if (__VLS_ctx.parsingStep > 4) {
        const __VLS_248 = {}.CheckCircleOutlined;
        /** @type {[typeof __VLS_components.CheckCircleOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_249 = __VLS_asFunctionalComponent(__VLS_248, new __VLS_248({}));
        const __VLS_250 = __VLS_249({}, ...__VLS_functionalComponentArgsRest(__VLS_249));
    }
    else if (__VLS_ctx.parsingStep === 4) {
        const __VLS_252 = {}.LoadingOutlined;
        /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_253 = __VLS_asFunctionalComponent(__VLS_252, new __VLS_252({}));
        const __VLS_254 = __VLS_253({}, ...__VLS_functionalComponentArgsRest(__VLS_253));
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    var __VLS_215;
    var __VLS_211;
}
if (__VLS_ctx.currentStep === 2) {
    const __VLS_256 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_257 = __VLS_asFunctionalComponent(__VLS_256, new __VLS_256({
        title: "步骤3: 确认和修正解析结果",
        ...{ class: "step-card" },
    }));
    const __VLS_258 = __VLS_257({
        title: "步骤3: 确认和修正解析结果",
        ...{ class: "step-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_257));
    __VLS_259.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "review-section" },
    });
    const __VLS_260 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_261 = __VLS_asFunctionalComponent(__VLS_260, new __VLS_260({
        message: "AI解析完成",
        description: (`成功解析出 ${((__VLS_ctx.extractedData && __VLS_ctx.extractedData.documents) ? __VLS_ctx.extractedData.documents.length : 0)} 个文书，请仔细检查并修正以下信息`),
        type: "success",
        showIcon: true,
        ...{ class: "review-alert" },
    }));
    const __VLS_262 = __VLS_261({
        message: "AI解析完成",
        description: (`成功解析出 ${((__VLS_ctx.extractedData && __VLS_ctx.extractedData.documents) ? __VLS_ctx.extractedData.documents.length : 0)} 个文书，请仔细检查并修正以下信息`),
        type: "success",
        showIcon: true,
        ...{ class: "review-alert" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_261));
    const __VLS_264 = {}.ATabs;
    /** @type {[typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, typeof __VLS_components.ATabs, typeof __VLS_components.aTabs, ]} */ ;
    // @ts-ignore
    const __VLS_265 = __VLS_asFunctionalComponent(__VLS_264, new __VLS_264({
        activeKey: (__VLS_ctx.reviewTab),
    }));
    const __VLS_266 = __VLS_265({
        activeKey: (__VLS_ctx.reviewTab),
    }, ...__VLS_functionalComponentArgsRest(__VLS_265));
    __VLS_267.slots.default;
    const __VLS_268 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_269 = __VLS_asFunctionalComponent(__VLS_268, new __VLS_268({
        key: "basic",
        tab: "基本信息",
    }));
    const __VLS_270 = __VLS_269({
        key: "basic",
        tab: "基本信息",
    }, ...__VLS_functionalComponentArgsRest(__VLS_269));
    __VLS_271.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "review-form" },
    });
    const __VLS_272 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_273 = __VLS_asFunctionalComponent(__VLS_272, new __VLS_272({
        gutter: (16),
    }));
    const __VLS_274 = __VLS_273({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_273));
    __VLS_275.slots.default;
    const __VLS_276 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_277 = __VLS_asFunctionalComponent(__VLS_276, new __VLS_276({
        span: (12),
    }));
    const __VLS_278 = __VLS_277({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_277));
    __VLS_279.slots.default;
    const __VLS_280 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_281 = __VLS_asFunctionalComponent(__VLS_280, new __VLS_280({
        label: "病历编号",
    }));
    const __VLS_282 = __VLS_281({
        label: "病历编号",
    }, ...__VLS_functionalComponentArgsRest(__VLS_281));
    __VLS_283.slots.default;
    const __VLS_284 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_285 = __VLS_asFunctionalComponent(__VLS_284, new __VLS_284({
        value: (__VLS_ctx.extractedData.recordNumber),
        placeholder: "自动生成",
        disabled: true,
    }));
    const __VLS_286 = __VLS_285({
        value: (__VLS_ctx.extractedData.recordNumber),
        placeholder: "自动生成",
        disabled: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_285));
    var __VLS_283;
    var __VLS_279;
    const __VLS_288 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_289 = __VLS_asFunctionalComponent(__VLS_288, new __VLS_288({
        span: (12),
    }));
    const __VLS_290 = __VLS_289({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_289));
    __VLS_291.slots.default;
    const __VLS_292 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_293 = __VLS_asFunctionalComponent(__VLS_292, new __VLS_292({
        label: "患者姓名",
    }));
    const __VLS_294 = __VLS_293({
        label: "患者姓名",
    }, ...__VLS_functionalComponentArgsRest(__VLS_293));
    __VLS_295.slots.default;
    const __VLS_296 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_297 = __VLS_asFunctionalComponent(__VLS_296, new __VLS_296({
        value: (__VLS_ctx.extractedData.patientName),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.patientName }) },
    }));
    const __VLS_298 = __VLS_297({
        value: (__VLS_ctx.extractedData.patientName),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.patientName }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_297));
    if (__VLS_ctx.extractedData.patientName) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "ai-confidence" },
        });
        const __VLS_300 = {}.RobotOutlined;
        /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_301 = __VLS_asFunctionalComponent(__VLS_300, new __VLS_300({}));
        const __VLS_302 = __VLS_301({}, ...__VLS_functionalComponentArgsRest(__VLS_301));
    }
    var __VLS_295;
    var __VLS_291;
    var __VLS_275;
    const __VLS_304 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_305 = __VLS_asFunctionalComponent(__VLS_304, new __VLS_304({
        gutter: (16),
    }));
    const __VLS_306 = __VLS_305({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_305));
    __VLS_307.slots.default;
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
        label: "出院科室",
    }));
    const __VLS_314 = __VLS_313({
        label: "出院科室",
    }, ...__VLS_functionalComponentArgsRest(__VLS_313));
    __VLS_315.slots.default;
    const __VLS_316 = {}.ASelect;
    /** @type {[typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, typeof __VLS_components.ASelect, typeof __VLS_components.aSelect, ]} */ ;
    // @ts-ignore
    const __VLS_317 = __VLS_asFunctionalComponent(__VLS_316, new __VLS_316({
        value: (__VLS_ctx.extractedData.department),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.department }) },
    }));
    const __VLS_318 = __VLS_317({
        value: (__VLS_ctx.extractedData.department),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.department }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_317));
    __VLS_319.slots.default;
    const __VLS_320 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_321 = __VLS_asFunctionalComponent(__VLS_320, new __VLS_320({
        value: "内科",
    }));
    const __VLS_322 = __VLS_321({
        value: "内科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_321));
    __VLS_323.slots.default;
    var __VLS_323;
    const __VLS_324 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_325 = __VLS_asFunctionalComponent(__VLS_324, new __VLS_324({
        value: "外科",
    }));
    const __VLS_326 = __VLS_325({
        value: "外科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_325));
    __VLS_327.slots.default;
    var __VLS_327;
    const __VLS_328 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_329 = __VLS_asFunctionalComponent(__VLS_328, new __VLS_328({
        value: "妇产科",
    }));
    const __VLS_330 = __VLS_329({
        value: "妇产科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_329));
    __VLS_331.slots.default;
    var __VLS_331;
    const __VLS_332 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_333 = __VLS_asFunctionalComponent(__VLS_332, new __VLS_332({
        value: "儿科",
    }));
    const __VLS_334 = __VLS_333({
        value: "儿科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_333));
    __VLS_335.slots.default;
    var __VLS_335;
    const __VLS_336 = {}.ASelectOption;
    /** @type {[typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, typeof __VLS_components.ASelectOption, typeof __VLS_components.aSelectOption, ]} */ ;
    // @ts-ignore
    const __VLS_337 = __VLS_asFunctionalComponent(__VLS_336, new __VLS_336({
        value: "急诊科",
    }));
    const __VLS_338 = __VLS_337({
        value: "急诊科",
    }, ...__VLS_functionalComponentArgsRest(__VLS_337));
    __VLS_339.slots.default;
    var __VLS_339;
    var __VLS_319;
    if (__VLS_ctx.extractedData.department) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "ai-confidence" },
        });
        const __VLS_340 = {}.RobotOutlined;
        /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_341 = __VLS_asFunctionalComponent(__VLS_340, new __VLS_340({}));
        const __VLS_342 = __VLS_341({}, ...__VLS_functionalComponentArgsRest(__VLS_341));
    }
    var __VLS_315;
    var __VLS_311;
    const __VLS_344 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_345 = __VLS_asFunctionalComponent(__VLS_344, new __VLS_344({
        span: (12),
    }));
    const __VLS_346 = __VLS_345({
        span: (12),
    }, ...__VLS_functionalComponentArgsRest(__VLS_345));
    __VLS_347.slots.default;
    const __VLS_348 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_349 = __VLS_asFunctionalComponent(__VLS_348, new __VLS_348({
        label: "主诊断",
    }));
    const __VLS_350 = __VLS_349({
        label: "主诊断",
    }, ...__VLS_functionalComponentArgsRest(__VLS_349));
    __VLS_351.slots.default;
    const __VLS_352 = {}.AInput;
    /** @type {[typeof __VLS_components.AInput, typeof __VLS_components.aInput, ]} */ ;
    // @ts-ignore
    const __VLS_353 = __VLS_asFunctionalComponent(__VLS_352, new __VLS_352({
        value: (__VLS_ctx.extractedData.primaryDiagnosis),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.primaryDiagnosis }) },
    }));
    const __VLS_354 = __VLS_353({
        value: (__VLS_ctx.extractedData.primaryDiagnosis),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.primaryDiagnosis }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_353));
    if (__VLS_ctx.extractedData.primaryDiagnosis) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "ai-confidence" },
        });
        const __VLS_356 = {}.RobotOutlined;
        /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_357 = __VLS_asFunctionalComponent(__VLS_356, new __VLS_356({}));
        const __VLS_358 = __VLS_357({}, ...__VLS_functionalComponentArgsRest(__VLS_357));
    }
    var __VLS_351;
    var __VLS_347;
    var __VLS_307;
    const __VLS_360 = {}.AFormItem;
    /** @type {[typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, typeof __VLS_components.AFormItem, typeof __VLS_components.aFormItem, ]} */ ;
    // @ts-ignore
    const __VLS_361 = __VLS_asFunctionalComponent(__VLS_360, new __VLS_360({
        label: "主要手术及操作",
    }));
    const __VLS_362 = __VLS_361({
        label: "主要手术及操作",
    }, ...__VLS_functionalComponentArgsRest(__VLS_361));
    __VLS_363.slots.default;
    const __VLS_364 = {}.ATextarea;
    /** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
    // @ts-ignore
    const __VLS_365 = __VLS_asFunctionalComponent(__VLS_364, new __VLS_364({
        value: (__VLS_ctx.extractedData.majorSurgery),
        rows: (3),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.majorSurgery }) },
    }));
    const __VLS_366 = __VLS_365({
        value: (__VLS_ctx.extractedData.majorSurgery),
        rows: (3),
        ...{ class: ({ 'ai-extracted': __VLS_ctx.extractedData.majorSurgery }) },
    }, ...__VLS_functionalComponentArgsRest(__VLS_365));
    if (__VLS_ctx.extractedData.majorSurgery) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "ai-confidence" },
        });
        const __VLS_368 = {}.RobotOutlined;
        /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_369 = __VLS_asFunctionalComponent(__VLS_368, new __VLS_368({}));
        const __VLS_370 = __VLS_369({}, ...__VLS_functionalComponentArgsRest(__VLS_369));
    }
    var __VLS_363;
    var __VLS_271;
    const __VLS_372 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_373 = __VLS_asFunctionalComponent(__VLS_372, new __VLS_372({
        key: "documents",
        tab: "文书目录",
    }));
    const __VLS_374 = __VLS_373({
        key: "documents",
        tab: "文书目录",
    }, ...__VLS_functionalComponentArgsRest(__VLS_373));
    __VLS_375.slots.default;
    /** @type {[typeof MedicalDocumentTree, ]} */ ;
    // @ts-ignore
    const __VLS_376 = __VLS_asFunctionalComponent(MedicalDocumentTree_vue_1.default, new MedicalDocumentTree_vue_1.default({
        documents: (__VLS_ctx.extractedData.documents || []),
        originalText: (__VLS_ctx.originalFullText),
    }));
    const __VLS_377 = __VLS_376({
        documents: (__VLS_ctx.extractedData.documents || []),
        originalText: (__VLS_ctx.originalFullText),
    }, ...__VLS_functionalComponentArgsRest(__VLS_376));
    var __VLS_375;
    const __VLS_379 = {}.ATabPane;
    /** @type {[typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, typeof __VLS_components.ATabPane, typeof __VLS_components.aTabPane, ]} */ ;
    // @ts-ignore
    const __VLS_380 = __VLS_asFunctionalComponent(__VLS_379, new __VLS_379({
        key: "stats",
        tab: "解析统计",
    }));
    const __VLS_381 = __VLS_380({
        key: "stats",
        tab: "解析统计",
    }, ...__VLS_functionalComponentArgsRest(__VLS_380));
    __VLS_382.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "parsing-stats" },
    });
    const __VLS_383 = {}.ARow;
    /** @type {[typeof __VLS_components.ARow, typeof __VLS_components.aRow, typeof __VLS_components.ARow, typeof __VLS_components.aRow, ]} */ ;
    // @ts-ignore
    const __VLS_384 = __VLS_asFunctionalComponent(__VLS_383, new __VLS_383({
        gutter: (16),
    }));
    const __VLS_385 = __VLS_384({
        gutter: (16),
    }, ...__VLS_functionalComponentArgsRest(__VLS_384));
    __VLS_386.slots.default;
    const __VLS_387 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_388 = __VLS_asFunctionalComponent(__VLS_387, new __VLS_387({
        span: (8),
    }));
    const __VLS_389 = __VLS_388({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_388));
    __VLS_390.slots.default;
    const __VLS_391 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_392 = __VLS_asFunctionalComponent(__VLS_391, new __VLS_391({
        title: "识别文书数量",
        value: ((__VLS_ctx.extractedData.documents ? __VLS_ctx.extractedData.documents.length : 0)),
        valueStyle: ({ color: '#1890ff' }),
    }));
    const __VLS_393 = __VLS_392({
        title: "识别文书数量",
        value: ((__VLS_ctx.extractedData.documents ? __VLS_ctx.extractedData.documents.length : 0)),
        valueStyle: ({ color: '#1890ff' }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_392));
    __VLS_394.slots.default;
    {
        const { prefix: __VLS_thisSlot } = __VLS_394.slots;
        const __VLS_395 = {}.FileTextOutlined;
        /** @type {[typeof __VLS_components.FileTextOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_396 = __VLS_asFunctionalComponent(__VLS_395, new __VLS_395({}));
        const __VLS_397 = __VLS_396({}, ...__VLS_functionalComponentArgsRest(__VLS_396));
    }
    var __VLS_394;
    var __VLS_390;
    const __VLS_399 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_400 = __VLS_asFunctionalComponent(__VLS_399, new __VLS_399({
        span: (8),
    }));
    const __VLS_401 = __VLS_400({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_400));
    __VLS_402.slots.default;
    const __VLS_403 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_404 = __VLS_asFunctionalComponent(__VLS_403, new __VLS_403({
        title: "抽取字段数量",
        value: (__VLS_ctx.extractedFieldsCount),
        valueStyle: ({ color: '#52c41a' }),
    }));
    const __VLS_405 = __VLS_404({
        title: "抽取字段数量",
        value: (__VLS_ctx.extractedFieldsCount),
        valueStyle: ({ color: '#52c41a' }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_404));
    __VLS_406.slots.default;
    {
        const { prefix: __VLS_thisSlot } = __VLS_406.slots;
        const __VLS_407 = {}.DatabaseOutlined;
        /** @type {[typeof __VLS_components.DatabaseOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_408 = __VLS_asFunctionalComponent(__VLS_407, new __VLS_407({}));
        const __VLS_409 = __VLS_408({}, ...__VLS_functionalComponentArgsRest(__VLS_408));
    }
    var __VLS_406;
    var __VLS_402;
    const __VLS_411 = {}.ACol;
    /** @type {[typeof __VLS_components.ACol, typeof __VLS_components.aCol, typeof __VLS_components.ACol, typeof __VLS_components.aCol, ]} */ ;
    // @ts-ignore
    const __VLS_412 = __VLS_asFunctionalComponent(__VLS_411, new __VLS_411({
        span: (8),
    }));
    const __VLS_413 = __VLS_412({
        span: (8),
    }, ...__VLS_functionalComponentArgsRest(__VLS_412));
    __VLS_414.slots.default;
    const __VLS_415 = {}.AStatistic;
    /** @type {[typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, typeof __VLS_components.AStatistic, typeof __VLS_components.aStatistic, ]} */ ;
    // @ts-ignore
    const __VLS_416 = __VLS_asFunctionalComponent(__VLS_415, new __VLS_415({
        title: "平均置信度",
        value: (__VLS_ctx.averageConfidence),
        suffix: "%",
        valueStyle: ({ color: '#722ed1' }),
    }));
    const __VLS_417 = __VLS_416({
        title: "平均置信度",
        value: (__VLS_ctx.averageConfidence),
        suffix: "%",
        valueStyle: ({ color: '#722ed1' }),
    }, ...__VLS_functionalComponentArgsRest(__VLS_416));
    __VLS_418.slots.default;
    {
        const { prefix: __VLS_thisSlot } = __VLS_418.slots;
        const __VLS_419 = {}.TrophyOutlined;
        /** @type {[typeof __VLS_components.TrophyOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_420 = __VLS_asFunctionalComponent(__VLS_419, new __VLS_419({}));
        const __VLS_421 = __VLS_420({}, ...__VLS_functionalComponentArgsRest(__VLS_420));
    }
    var __VLS_418;
    var __VLS_414;
    var __VLS_386;
    const __VLS_423 = {}.ADivider;
    /** @type {[typeof __VLS_components.ADivider, typeof __VLS_components.aDivider, ]} */ ;
    // @ts-ignore
    const __VLS_424 = __VLS_asFunctionalComponent(__VLS_423, new __VLS_423({}));
    const __VLS_425 = __VLS_424({}, ...__VLS_functionalComponentArgsRest(__VLS_424));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "confidence-breakdown" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "confidence-items" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "confidence-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_427 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_428 = __VLS_asFunctionalComponent(__VLS_427, new __VLS_427({
        percent: (95),
        size: "small",
    }));
    const __VLS_429 = __VLS_428({
        percent: (95),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_428));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "confidence-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_431 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_432 = __VLS_asFunctionalComponent(__VLS_431, new __VLS_431({
        percent: (92),
        size: "small",
    }));
    const __VLS_433 = __VLS_432({
        percent: (92),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_432));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "confidence-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_435 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_436 = __VLS_asFunctionalComponent(__VLS_435, new __VLS_435({
        percent: (88),
        size: "small",
    }));
    const __VLS_437 = __VLS_436({
        percent: (88),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_436));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "confidence-item" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    const __VLS_439 = {}.AProgress;
    /** @type {[typeof __VLS_components.AProgress, typeof __VLS_components.aProgress, ]} */ ;
    // @ts-ignore
    const __VLS_440 = __VLS_asFunctionalComponent(__VLS_439, new __VLS_439({
        percent: (85),
        size: "small",
    }));
    const __VLS_441 = __VLS_440({
        percent: (85),
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_440));
    var __VLS_382;
    var __VLS_267;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "step-actions" },
    });
    const __VLS_443 = {}.ASpace;
    /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
    // @ts-ignore
    const __VLS_444 = __VLS_asFunctionalComponent(__VLS_443, new __VLS_443({}));
    const __VLS_445 = __VLS_444({}, ...__VLS_functionalComponentArgsRest(__VLS_444));
    __VLS_446.slots.default;
    const __VLS_447 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_448 = __VLS_asFunctionalComponent(__VLS_447, new __VLS_447({
        ...{ 'onClick': {} },
    }));
    const __VLS_449 = __VLS_448({
        ...{ 'onClick': {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_448));
    let __VLS_451;
    let __VLS_452;
    let __VLS_453;
    const __VLS_454 = {
        onClick: (__VLS_ctx.handleBackToInput)
    };
    __VLS_450.slots.default;
    var __VLS_450;
    const __VLS_455 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_456 = __VLS_asFunctionalComponent(__VLS_455, new __VLS_455({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.parsing),
    }));
    const __VLS_457 = __VLS_456({
        ...{ 'onClick': {} },
        loading: (__VLS_ctx.parsing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_456));
    let __VLS_459;
    let __VLS_460;
    let __VLS_461;
    const __VLS_462 = {
        onClick: (__VLS_ctx.handleReparse)
    };
    __VLS_458.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_458.slots;
        const __VLS_463 = {}.ReloadOutlined;
        /** @type {[typeof __VLS_components.ReloadOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_464 = __VLS_asFunctionalComponent(__VLS_463, new __VLS_463({}));
        const __VLS_465 = __VLS_464({}, ...__VLS_functionalComponentArgsRest(__VLS_464));
    }
    var __VLS_458;
    const __VLS_467 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_468 = __VLS_asFunctionalComponent(__VLS_467, new __VLS_467({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.importing),
    }));
    const __VLS_469 = __VLS_468({
        ...{ 'onClick': {} },
        type: "primary",
        loading: (__VLS_ctx.importing),
    }, ...__VLS_functionalComponentArgsRest(__VLS_468));
    let __VLS_471;
    let __VLS_472;
    let __VLS_473;
    const __VLS_474 = {
        onClick: (__VLS_ctx.handleConfirmImport)
    };
    __VLS_470.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_470.slots;
        const __VLS_475 = {}.CheckOutlined;
        /** @type {[typeof __VLS_components.CheckOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_476 = __VLS_asFunctionalComponent(__VLS_475, new __VLS_475({}));
        const __VLS_477 = __VLS_476({}, ...__VLS_functionalComponentArgsRest(__VLS_476));
    }
    var __VLS_470;
    var __VLS_446;
    var __VLS_259;
}
if (__VLS_ctx.currentStep === 3) {
    const __VLS_479 = {}.ACard;
    /** @type {[typeof __VLS_components.ACard, typeof __VLS_components.aCard, typeof __VLS_components.ACard, typeof __VLS_components.aCard, ]} */ ;
    // @ts-ignore
    const __VLS_480 = __VLS_asFunctionalComponent(__VLS_479, new __VLS_479({
        title: "导入完成",
        ...{ class: "step-card" },
    }));
    const __VLS_481 = __VLS_480({
        title: "导入完成",
        ...{ class: "step-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_480));
    __VLS_482.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "success-section" },
    });
    const __VLS_483 = {}.AResult;
    /** @type {[typeof __VLS_components.AResult, typeof __VLS_components.aResult, typeof __VLS_components.AResult, typeof __VLS_components.aResult, ]} */ ;
    // @ts-ignore
    const __VLS_484 = __VLS_asFunctionalComponent(__VLS_483, new __VLS_483({
        status: "success",
        title: "病历导入成功！",
        subTitle: (`成功导入 ${__VLS_ctx.importedCount} 条病历记录，包含 ${__VLS_ctx.importedDocumentsCount} 个文书`),
    }));
    const __VLS_485 = __VLS_484({
        status: "success",
        title: "病历导入成功！",
        subTitle: (`成功导入 ${__VLS_ctx.importedCount} 条病历记录，包含 ${__VLS_ctx.importedDocumentsCount} 个文书`),
    }, ...__VLS_functionalComponentArgsRest(__VLS_484));
    __VLS_486.slots.default;
    {
        const { extra: __VLS_thisSlot } = __VLS_486.slots;
        const __VLS_487 = {}.ASpace;
        /** @type {[typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, typeof __VLS_components.ASpace, typeof __VLS_components.aSpace, ]} */ ;
        // @ts-ignore
        const __VLS_488 = __VLS_asFunctionalComponent(__VLS_487, new __VLS_487({}));
        const __VLS_489 = __VLS_488({}, ...__VLS_functionalComponentArgsRest(__VLS_488));
        __VLS_490.slots.default;
        const __VLS_491 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_492 = __VLS_asFunctionalComponent(__VLS_491, new __VLS_491({
            ...{ 'onClick': {} },
            type: "primary",
        }));
        const __VLS_493 = __VLS_492({
            ...{ 'onClick': {} },
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_492));
        let __VLS_495;
        let __VLS_496;
        let __VLS_497;
        const __VLS_498 = {
            onClick: (__VLS_ctx.handleViewImported)
        };
        __VLS_494.slots.default;
        var __VLS_494;
        const __VLS_499 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_500 = __VLS_asFunctionalComponent(__VLS_499, new __VLS_499({
            ...{ 'onClick': {} },
        }));
        const __VLS_501 = __VLS_500({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_500));
        let __VLS_503;
        let __VLS_504;
        let __VLS_505;
        const __VLS_506 = {
            onClick: (__VLS_ctx.handleImportAnother)
        };
        __VLS_502.slots.default;
        var __VLS_502;
        const __VLS_507 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_508 = __VLS_asFunctionalComponent(__VLS_507, new __VLS_507({
            ...{ 'onClick': {} },
        }));
        const __VLS_509 = __VLS_508({
            ...{ 'onClick': {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_508));
        let __VLS_511;
        let __VLS_512;
        let __VLS_513;
        const __VLS_514 = {
            onClick: (__VLS_ctx.handleBackToList)
        };
        __VLS_510.slots.default;
        var __VLS_510;
        var __VLS_490;
    }
    var __VLS_486;
    var __VLS_482;
}
const __VLS_515 = {}.AModal;
/** @type {[typeof __VLS_components.AModal, typeof __VLS_components.aModal, typeof __VLS_components.AModal, typeof __VLS_components.aModal, ]} */ ;
// @ts-ignore
const __VLS_516 = __VLS_asFunctionalComponent(__VLS_515, new __VLS_515({
    open: (__VLS_ctx.showApiConfig),
    title: "大模型API配置",
    width: "1000px",
    footer: (null),
    destroyOnClose: (true),
}));
const __VLS_517 = __VLS_516({
    open: (__VLS_ctx.showApiConfig),
    title: "大模型API配置",
    width: "1000px",
    footer: (null),
    destroyOnClose: (true),
}, ...__VLS_functionalComponentArgsRest(__VLS_516));
__VLS_518.slots.default;
/** @type {[typeof LLMApiConfigDatabase, ]} */ ;
// @ts-ignore
const __VLS_519 = __VLS_asFunctionalComponent(LLMApiConfigDatabase_vue_1.default, new LLMApiConfigDatabase_vue_1.default({
    ...{ 'onConfigUpdated': {} },
}));
const __VLS_520 = __VLS_519({
    ...{ 'onConfigUpdated': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_519));
let __VLS_522;
let __VLS_523;
let __VLS_524;
const __VLS_525 = {
    onConfigUpdated: (__VLS_ctx.handleApiConfigUpdated)
};
var __VLS_521;
var __VLS_518;
/** @type {__VLS_StyleScopedClasses['page-container']} */ ;
/** @type {__VLS_StyleScopedClasses['breadcrumb']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-content']} */ ;
/** @type {__VLS_StyleScopedClasses['header-text']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['page-description']} */ ;
/** @type {__VLS_StyleScopedClasses['header-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['steps-card']} */ ;
/** @type {__VLS_StyleScopedClasses['step-card']} */ ;
/** @type {__VLS_StyleScopedClasses['input-section']} */ ;
/** @type {__VLS_StyleScopedClasses['textarea-container']} */ ;
/** @type {__VLS_StyleScopedClasses['enhanced-text-input']} */ ;
/** @type {__VLS_StyleScopedClasses['input-tips']} */ ;
/** @type {__VLS_StyleScopedClasses['upload-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['alternative-upload-section']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-4']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mr-1']} */ ;
/** @type {__VLS_StyleScopedClasses['alternative-upload-content']} */ ;
/** @type {__VLS_StyleScopedClasses['mb-3']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['w-full']} */ ;
/** @type {__VLS_StyleScopedClasses['selected-file-info']} */ ;
/** @type {__VLS_StyleScopedClasses['uploaded-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['content-preview-enhanced']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-status']} */ ;
/** @type {__VLS_StyleScopedClasses['text-sm']} */ ;
/** @type {__VLS_StyleScopedClasses['text-gray-500']} */ ;
/** @type {__VLS_StyleScopedClasses['mt-2']} */ ;
/** @type {__VLS_StyleScopedClasses['parsed-content']} */ ;
/** @type {__VLS_StyleScopedClasses['whitespace-pre-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-section']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-drag-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-text']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-upload-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['batch-preview']} */ ;
/** @type {__VLS_StyleScopedClasses['step-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['step-card']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-section']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-progress']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-content']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-steps']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-step']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['completed']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-step']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['completed']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-step']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['completed']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-step']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['completed']} */ ;
/** @type {__VLS_StyleScopedClasses['step-card']} */ ;
/** @type {__VLS_StyleScopedClasses['review-section']} */ ;
/** @type {__VLS_StyleScopedClasses['review-alert']} */ ;
/** @type {__VLS_StyleScopedClasses['review-form']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-extracted']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-confidence']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-extracted']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-confidence']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-extracted']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-confidence']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-extracted']} */ ;
/** @type {__VLS_StyleScopedClasses['ai-confidence']} */ ;
/** @type {__VLS_StyleScopedClasses['parsing-stats']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-breakdown']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-items']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-item']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-item']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-item']} */ ;
/** @type {__VLS_StyleScopedClasses['confidence-item']} */ ;
/** @type {__VLS_StyleScopedClasses['step-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['step-card']} */ ;
/** @type {__VLS_StyleScopedClasses['success-section']} */ ;
var __VLS_dollars;
const __VLS_self = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {
            InboxOutlined: icons_vue_1.InboxOutlined,
            FolderOpenOutlined: icons_vue_1.FolderOpenOutlined,
            RobotOutlined: icons_vue_1.RobotOutlined,
            CheckCircleOutlined: icons_vue_1.CheckCircleOutlined,
            LoadingOutlined: icons_vue_1.LoadingOutlined,
            FileTextOutlined: icons_vue_1.FileTextOutlined,
            DatabaseOutlined: icons_vue_1.DatabaseOutlined,
            TrophyOutlined: icons_vue_1.TrophyOutlined,
            ReloadOutlined: icons_vue_1.ReloadOutlined,
            CheckOutlined: icons_vue_1.CheckOutlined,
            SettingOutlined: icons_vue_1.SettingOutlined,
            LLMApiConfigDatabase: LLMApiConfigDatabase_vue_1.default,
            MedicalDocumentTree: MedicalDocumentTree_vue_1.default,
            currentStep: currentStep,
            inputMethod: inputMethod,
            inputText: inputText,
            uploadFileList: uploadFileList,
            batchFileList: batchFileList,
            uploadedContent: uploadedContent,
            isParsingFile: isParsingFile,
            batchFiles: batchFiles,
            processing: processing,
            parsing: parsing,
            importing: importing,
            parsingProgress: parsingProgress,
            parsingStep: parsingStep,
            reviewTab: reviewTab,
            importedCount: importedCount,
            importedDocumentsCount: importedDocumentsCount,
            showApiConfig: showApiConfig,
            originalFullText: originalFullText,
            debugSelectedFile: debugSelectedFile,
            extractedData: extractedData,
            canProceedToNext: canProceedToNext,
            extractedFieldsCount: extractedFieldsCount,
            averageConfidence: averageConfidence,
            handleInputMethodChange: handleInputMethodChange,
            beforeUpload: beforeUpload,
            beforeBatchUpload: beforeBatchUpload,
            handleFileUpload: handleFileUpload,
            handleBatchUpload: handleBatchUpload,
            handleDebugFileSelect: handleDebugFileSelect,
            handleDebugParsePDF: handleDebugParsePDF,
            formatFileSize: formatFileSize,
            getFileTypeDescription: getFileTypeDescription,
            handleStartParsing: handleStartParsing,
            handleBackToInput: handleBackToInput,
            handleReparse: handleReparse,
            handleConfirmImport: handleConfirmImport,
            handleViewImported: handleViewImported,
            handleImportAnother: handleImportAnother,
            handleBackToList: handleBackToList,
            handleApiConfigUpdated: handleApiConfigUpdated,
            handleCancel: handleCancel,
        };
    },
});
export const default = (await Promise.resolve().then(() => __importStar(require('vue')))).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */

