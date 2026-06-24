/**
 * 文件上传组合式函数
 * 处理文件上传、验证和进度监控
 */
import { ref, computed, readonly } from 'vue'
import type { FileUploadConfig, UploadProgress } from '../types/medical-records'

export function useFileUpload(config?: Partial<FileUploadConfig>) {
  // 默认配置
  const defaultConfig: FileUploadConfig = {
    maxSize: 10 * 1024 * 1024, // 10MB
    allowedTypes: [
      'text/plain',
      'application/pdf',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'image/jpeg',
      'image/png'
    ],
    maxFiles: 1
  }

  const uploadConfig = { ...defaultConfig, ...config }

  // 响应式状态
  const files = ref<File[]>([])
  const uploadProgress = ref<UploadProgress>({ loaded: 0, total: 0, percentage: 0 })
  const isUploading = ref(false)
  const error = ref<string | null>(null)

  // 计算属性
  const hasFiles = computed(() => files.value.length > 0)
  const canAddMoreFiles = computed(() => files.value.length < uploadConfig.maxFiles)

  /**
   * 验证文件
   */
  const validateFile = (file: File): boolean => {
    error.value = null

    // 检查文件大小
    if (file.size > uploadConfig.maxSize) {
      error.value = `文件大小不能超过 ${formatFileSize(uploadConfig.maxSize)}`
      return false
    }

    // 检查文件类型
    if (!uploadConfig.allowedTypes.includes(file.type)) {
      error.value = `不支持的文件类型: ${file.type}`
      return false
    }

    return true
  }

  /**
   * 添加文件
   */
  const addFiles = (newFiles: File[]) => {
    for (const file of newFiles) {
      if (!canAddMoreFiles.value) {
        error.value = `最多只能上传 ${uploadConfig.maxFiles} 个文件`
        break
      }

      if (validateFile(file)) {
        files.value.push(file)
      } else {
        break
      }
    }
  }

  /**
   * 移除文件
   */
  const removeFile = (index: number) => {
    files.value.splice(index, 1)
    error.value = null
  }

  /**
   * 清空文件
   */
  const clearFiles = () => {
    files.value = []
    error.value = null
    uploadProgress.value = { loaded: 0, total: 0, percentage: 0 }
  }

  /**
   * 上传文件到Supabase Storage
   */
  const uploadToStorage = async (file: File, bucket: string, path: string): Promise<string> => {
    // TODO: 实现Supabase Storage上传
    // 这里先模拟上传过程
    isUploading.value = true
    
    try {
      // 模拟上传进度
      for (let i = 0; i <= 100; i += 10) {
        uploadProgress.value = {
          loaded: (file.size * i) / 100,
          total: file.size,
          percentage: i
        }
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      // 返回模拟的文件URL
      return `${bucket}/${path}/${file.name}`
    } finally {
      isUploading.value = false
    }
  }

  /**
   * 格式化文件大小
   */
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes'
    
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  /**
   * 获取文件图标
   */
  const getFileIcon = (file: File): string => {
    const type = file.type.toLowerCase()
    
    if (type.includes('pdf')) return 'file-pdf'
    if (type.includes('word') || type.includes('document')) return 'file-word'
    if (type.includes('image')) return 'file-image'
    if (type.includes('text')) return 'file-text'
    
    return 'file'
  }

  return {
    // 状态
    files: readonly(files),
    uploadProgress: readonly(uploadProgress),
    isUploading: readonly(isUploading),
    error: readonly(error),
    
    // 计算属性
    hasFiles,
    canAddMoreFiles,
    
    // 方法
    addFiles,
    removeFile,
    clearFiles,
    uploadToStorage,
    formatFileSize,
    getFileIcon,
    validateFile
  }
} 