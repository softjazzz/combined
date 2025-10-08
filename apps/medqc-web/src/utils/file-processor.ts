/**
 * 文件处理工具函数
 * 支持多种文件格式的验证、转换和内容提取
 */

// 支持的文件类型配置
export const FILE_TYPES = {
  PDF: {
    extensions: ['pdf'],
    mimeTypes: ['application/pdf'],
    maxSize: 10 * 1024 * 1024, // 10MB
    icon: 'fas fa-file-pdf text-red-500',
    displayName: 'PDF'
  },
  WORD: {
    extensions: ['doc', 'docx'],
    mimeTypes: [
      'application/msword',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ],
    maxSize: 10 * 1024 * 1024, // 10MB
    icon: 'fas fa-file-word text-blue-500',
    displayName: 'Word'
  },
  TEXT: {
    extensions: ['txt'],
    mimeTypes: ['text/plain'],
    maxSize: 5 * 1024 * 1024, // 5MB
    icon: 'fas fa-file-alt text-gray-500',
    displayName: 'Text'
  }
} as const

// 文件验证结果接口
export interface FileValidationResult {
  isValid: boolean
  error?: string
  fileType?: keyof typeof FILE_TYPES
  warnings?: string[]
}

// 文件信息接口
export interface FileInfo {
  name: string
  size: number
  type: string
  extension: string
  lastModified: number
  isValid: boolean
  fileType?: keyof typeof FILE_TYPES
  error?: string
}

/**
 * 获取文件扩展名
 */
export function getFileExtension(fileName: string): string {
  const parts = fileName.split('.')
  return parts.length > 1 ? parts.pop()!.toLowerCase() : ''
}

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * 检测文件类型
 */
export function detectFileType(file: File): keyof typeof FILE_TYPES | null {
  const extension = getFileExtension(file.name)
  const mimeType = file.type.toLowerCase()

  for (const [type, config] of Object.entries(FILE_TYPES)) {
    if (config.extensions.includes(extension) || config.mimeTypes.includes(mimeType)) {
      return type as keyof typeof FILE_TYPES
    }
  }

  return null
}

/**
 * 验证单个文件
 */
export function validateFile(file: File, maxTotalSize?: number): FileValidationResult {
  const extension = getFileExtension(file.name)
  const fileType = detectFileType(file)
  const warnings: string[] = []

  // 检查文件类型
  if (!fileType) {
    return {
      isValid: false,
      error: `不支持的文件类型: .${extension}`
    }
  }

  const config = FILE_TYPES[fileType]

  // 检查文件大小
  if (file.size > config.maxSize) {
    return {
      isValid: false,
      error: `文件大小超过限制: ${formatFileSize(file.size)} > ${formatFileSize(config.maxSize)}`,
      fileType
    }
  }

  // 检查文件名长度
  if (file.name.length > 255) {
    warnings.push('文件名过长，可能会被截断')
  }

  // 检查文件名字符
  if (!/^[a-zA-Z0-9\u4e00-\u9fa5._\-\s()[\]]+$/.test(file.name)) {
    warnings.push('文件名包含特殊字符，建议使用字母、数字、中文和常见符号')
  }

  // 检查文件是否为空
  if (file.size === 0) {
    return {
      isValid: false,
      error: '文件为空',
      fileType
    }
  }

  // 检查总大小限制
  if (maxTotalSize && file.size > maxTotalSize) {
    return {
      isValid: false,
      error: `文件大小超过总限制: ${formatFileSize(file.size)} > ${formatFileSize(maxTotalSize)}`,
      fileType
    }
  }

  return {
    isValid: true,
    fileType,
    warnings: warnings.length > 0 ? warnings : undefined
  }
}

/**
 * 批量验证文件
 */
export function validateFiles(
  files: File[],
  options: {
    maxTotalSize?: number
    maxFileCount?: number
    allowDuplicates?: boolean
  } = {}
): {
  validFiles: File[]
  invalidFiles: Array<{ file: File; error: string }>
  warnings: string[]
  totalSize: number
} {
  const {
    maxTotalSize = 100 * 1024 * 1024, // 100MB
    maxFileCount = 100,
    allowDuplicates = false
  } = options

  const validFiles: File[] = []
  const invalidFiles: Array<{ file: File; error: string }> = []
  const warnings: string[] = []
  let totalSize = 0

  // 检查文件数量限制
  if (files.length > maxFileCount) {
    warnings.push(`文件数量超过限制: ${files.length} > ${maxFileCount}`)
  }

  // 用于检测重复文件
  const fileSignatures = new Set<string>()

  for (const file of files) {
    // 检查重复文件
    if (!allowDuplicates) {
      const signature = `${file.name}-${file.size}-${file.lastModified}`
      if (fileSignatures.has(signature)) {
        invalidFiles.push({ file, error: '重复文件' })
        continue
      }
      fileSignatures.add(signature)
    }

    // 验证单个文件
    const validation = validateFile(file, maxTotalSize - totalSize)
    
    if (validation.isValid) {
      validFiles.push(file)
      totalSize += file.size
      
      // 添加警告
      if (validation.warnings) {
        warnings.push(...validation.warnings.map(w => `${file.name}: ${w}`))
      }
    } else {
      invalidFiles.push({ file, error: validation.error! })
    }

    // 检查总大小限制
    if (totalSize > maxTotalSize) {
      warnings.push(`总文件大小超过限制: ${formatFileSize(totalSize)} > ${formatFileSize(maxTotalSize)}`)
      break
    }
  }

  return {
    validFiles,
    invalidFiles,
    warnings,
    totalSize
  }
}

/**
 * 获取文件信息
 */
export function getFileInfo(file: File): FileInfo {
  const extension = getFileExtension(file.name)
  const validation = validateFile(file)

  return {
    name: file.name,
    size: file.size,
    type: file.type,
    extension,
    lastModified: file.lastModified,
    isValid: validation.isValid,
    fileType: validation.fileType,
    error: validation.error
  }
}

/**
 * 获取文件图标类名
 */
export function getFileIcon(file: File | string): string {
  let fileType: keyof typeof FILE_TYPES | null

  if (typeof file === 'string') {
    // 如果传入的是文件名或扩展名
    const extension = file.includes('.') ? getFileExtension(file) : file.toLowerCase()
    for (const [type, config] of Object.entries(FILE_TYPES)) {
      if (config.extensions.includes(extension)) {
        fileType = type as keyof typeof FILE_TYPES
        break
      }
    }
  } else {
    fileType = detectFileType(file)
  }

  return fileType ? FILE_TYPES[fileType].icon : 'fas fa-file text-gray-400'
}

/**
 * 获取文件类型显示名称
 */
export function getFileTypeDisplayName(file: File | string): string {
  let fileType: keyof typeof FILE_TYPES | null

  if (typeof file === 'string') {
    const extension = file.includes('.') ? getFileExtension(file) : file.toLowerCase()
    for (const [type, config] of Object.entries(FILE_TYPES)) {
      if (config.extensions.includes(extension)) {
        fileType = type as keyof typeof FILE_TYPES
        break
      }
    }
  } else {
    fileType = detectFileType(file)
  }

  return fileType ? FILE_TYPES[fileType].displayName : '未知'
}

/**
 * 读取文本文件内容
 */
export function readTextFile(file: File): Promise<string> {
  return new Promise((resolve: unknown,  reject: unknown) => {
    const reader = new FileReader()
    
    reader.onload = (e) => {
      resolve(e.target?.result as string)
    }
    
    reader.onerror = () => {
      reject(new Error('文件读取失败'))
    }
    
    reader.readAsText(file, 'UTF-8')
  })
}

/**
 * 读取文件为ArrayBuffer
 */
export function readFileAsArrayBuffer(file: File): Promise<ArrayBuffer> {
  return new Promise((resolve: unknown,  reject: unknown) => {
    const reader = new FileReader()
    
    reader.onload = (e) => {
      resolve(e.target?.result as ArrayBuffer)
    }
    
    reader.onerror = () => {
      reject(new Error('文件读取失败'))
    }
    
    reader.readAsArrayBuffer(file)
  })
}

/**
 * 读取文件为Base64
 */
export function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve: unknown,  reject: unknown) => {
    const reader = new FileReader()
    
    reader.onload = (e) => {
      const result = e.target?.result as string
      // 移除data:xxx;base64,前缀
      const base64 = result.split(',')[1]
      resolve(base64)
    }
    
    reader.onerror = () => {
      reject(new Error('文件读取失败'))
    }
    
    reader.readAsDataURL(file)
  })
}

/**
 * 创建文件下载
 */
export function downloadFile(content: string | Blob, fileName: string, mimeType?: string) {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mimeType || 'text/plain' })
  const url = URL.createObjectURL(blob)
  
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  
  // 清理URL对象
  URL.revokeObjectURL(url)
}

/**
 * 压缩文件列表为ZIP（需要额外的库支持）
 */
export async function createZipFromFiles(files: File[], zipFileName: string): Promise<Blob> {
  // 这里需要使用JSZip库，暂时返回一个占位符
  // 实际实现需要安装并导入JSZip
  throw new Error('ZIP压缩功能需要JSZip库支持')
}

/**
 * 生成文件摘要信息
 */
export function generateFileSummary(files: File[]): {
  totalCount: number
  totalSize: number
  typeDistribution: Record<string, number>
  sizeDistribution: Record<string, number>
} {
  const typeDistribution: Record<string, number> = {}
  const sizeDistribution: Record<string, number> = {
    'small': 0,    // < 1MB
    'medium': 0,   // 1MB - 5MB
    'large': 0     // > 5MB
  }

  let totalSize = 0

  for (const file of files) {
    totalSize += file.size
    
    // 统计文件类型分布
    const fileType = getFileTypeDisplayName(file)
    typeDistribution[fileType] = (typeDistribution[fileType] || 0) + 1
    
    // 统计文件大小分布
    if (file.size < 1024 * 1024) {
      sizeDistribution.small++
    } else if (file.size < 5 * 1024 * 1024) {
      sizeDistribution.medium++
    } else {
      sizeDistribution.large++
    }
  }

  return {
    totalCount: files.length,
    totalSize,
    typeDistribution,
    sizeDistribution
  }
}
