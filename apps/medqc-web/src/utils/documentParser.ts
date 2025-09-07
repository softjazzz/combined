/**
 * 前端文档解析工具
 * 支持Word、TXT文档的解析，PDF通过后端处理
 */

import mammoth from 'mammoth'

export interface ParseResult {
  success: boolean
  content: string
  error?: string
  metadata?: {
    pages?: number
    wordCount?: number
    fileType: string
    fileName: string
  }
}

export class DocumentParser {
  /**
   * 解析Word文档
   */
  static async parseWord(file: File): Promise<ParseResult> {
    try {
      console.log('开始解析Word文件:', file.name)
      
      const arrayBuffer = await file.arrayBuffer()
      const result = await mammoth.extractRawText({ arrayBuffer  })
      
      const content = result.value.trim()
      const wordCount = content.split(/\s+/).length
      
      console.log(`Word解析完成: ${wordCount}字`)
      
      return {
        success: true,
        content,
        metadata: {
          wordCount,
          fileType: 'Word',
          fileName: file.name
        }
      }
    } catch (error) {
      console.error('Word解析失败:', error)
      return {
        success: false,
        content: '',
        error: `Word文档解析失败: ${error instanceof Error ? error.message : '未知错误'}`,
        metadata: {
          fileType: 'Word',
          fileName: file.name
        }
      }
    }
  }

  /**
   * 解析TXT文档
   */
  static async parseTXT(file: File): Promise<ParseResult> {
    try {
      console.log('开始解析TXT文件:', file.name)
      
      const text = await file.text()
      const wordCount = text.trim().split(/\s+/).length
      
      console.log(`TXT解析完成: ${wordCount}字`)
      
      return {
        success: true,
        content: text,
        metadata: {
          wordCount,
          fileType: 'TXT',
          fileName: file.name
        }
      }
    } catch (error) {
      console.error('TXT解析失败:', error)
      return {
        success: false,
        content: '',
        error: `TXT文档解析失败: ${error instanceof Error ? error.message : '未知错误'}`,
        metadata: {
          fileType: 'TXT',
          fileName: file.name
        }
      }
    }
  }

  /**
   * PDF文件处理提示（实际解析在后端进行）
   */
  static async handlePDF(file: File): Promise<ParseResult> {
    console.log('PDF文件将通过后端解析:', file.name)
    
    return {
      success: true,
      content: `PDF文件: ${file.name}

📄 PDF文件已准备就绪！

系统将通过后端Python服务解析PDF内容，支持：
• PyMuPDF (fitz) - 高性能PDF文本提取
• pdfplumber - 备用解析方案
• 自动医疗信息识别

文件信息：
- 文件名: ${file.name}
- 文件大小: ${(file.size / 1024).toFixed(2)} KB
- 文件类型: PDF文档

💡 点击"开始AI解析"按钮，系统将自动上传PDF到后端进行处理。`,
      metadata: {
        fileType: 'PDF',
        fileName: file.name
      }
    }
  }

  /**
   * 根据文件类型自动选择解析方法
   */
  static async parseDocument(file: File): Promise<ParseResult> {
    const fileName = file.name.toLowerCase()
    const fileType = file.type.toLowerCase()
    
    try {
      // 根据文件扩展名和MIME类型判断文件类型
      if (fileName.endsWith('.pdf') || fileType.includes('pdf')) {
        return await this.handlePDF(file)
      } else if (
        fileName.endsWith('.docx') || 
        fileName.endsWith('.doc') || 
        fileType.includes('word') ||
        fileType.includes('document')
      ) {
        return await this.parseWord(file)
      } else if (
        fileName.endsWith('.txt') || 
        fileType.includes('text/plain')
      ) {
        return await this.parseTXT(file)
      } else {
        // 尝试作为文本文件处理
        console.log('未知文件类型，尝试作为文本文件处理:', fileName, fileType)
        return await this.parseTXT(file)
      }
    } catch (error) {
      console.error('文档解析失败:', error)
      return {
        success: false,
        content: '',
        error: `不支持的文件格式或解析失败: ${fileName}`,
        metadata: {
          fileType: 'Unknown',
          fileName: file.name
        }
      }
    }
  }

  /**
   * 检查文件类型是否支持
   */
  static isSupportedFileType(file: File): boolean {
    const fileName = file.name.toLowerCase()
    const fileType = file.type.toLowerCase()
    
    const supportedExtensions = ['.pdf', '.docx', '.doc', '.txt']
    const supportedMimeTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    
    const hasValidExtension = supportedExtensions.some(ext => fileName.endsWith(ext))
    const hasValidMimeType = supportedMimeTypes.some(mime => fileType.includes(mime))
    
    return hasValidExtension || hasValidMimeType
  }

  /**
   * 获取文件类型描述
   */
  static getFileTypeDescription(file: File): string {
    const fileName = file.name.toLowerCase()
    const fileType = file.type.toLowerCase()
    
    if (fileName.endsWith('.pdf') || fileType.includes('pdf')) {
      return 'PDF文档'
    } else if (fileName.endsWith('.docx') || fileName.endsWith('.doc') || fileType.includes('word')) {
      return 'Word文档'
    } else if (fileName.endsWith('.txt') || fileType.includes('text/plain')) {
      return '文本文档'
    } else {
      return '未知格式'
    }
  }

  /**
   * 检查是否为PDF文件
   */
  static isPDFFile(file: File): boolean {
    const fileName = file.name.toLowerCase()
    const fileType = file.type.toLowerCase()
    return fileName.endsWith('.pdf') || fileType.includes('pdf')
  }
}

export default DocumentParser