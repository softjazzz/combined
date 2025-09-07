/**
 * 批量上传模拟器
 * 当数据库表不存在时使用本地存储模拟批量处理功能
 */

import { ref } from 'vue'
import { createMedicalRecord } from '@/api/medical-records'

// 批量上传文件接口
interface UploadFile {
  name: string
  size: number
  type: string
  file: File
  status: 'pending' | 'uploading' | 'success' | 'error'
  error?: string
  id?: string
}

// 批量上传选项
interface BatchUploadOptions {
  onProgress?: (progress: number) => void
  onFileComplete?: (index: number, success: boolean, error?: string) => void
  onBatchComplete?: (results: BatchUploadResult[]) => void
  batchSize?: number
  maxRetries?: number
}

// 批量上传结果
interface BatchUploadResult {
  file: UploadFile
  success: boolean
  recordId?: string
  error?: string
}

export function useBatchUploadMock() {
  const isUploading = ref(false)
  const uploadProgress = ref(0)

  /**
   * 文件内容提取
   */
  const extractFileContent = async (file: File): Promise<string> => {
    return new Promise((resolve: any,  reject: any) => {
      const reader = new FileReader()
      
      reader.onload = (e) => {
        const content = e.target?.result as string
        
        // 根据文件类型处理内容
        if (file.type.includes('text')) {
          resolve(content)
        } else if (file.type.includes('pdf')) {
          resolve(`PDF文件: ${file.name}\n\n[PDF内容需要后端处理]`)
        } else if (file.type.includes('doc')) {
          resolve(`Word文件: ${file.name}\n\n[Word内容需要后端处理]`)
        } else {
          resolve(content || `文件: ${file.name}`)
        }
      }
      
      reader.onerror = () => {
        reject(new Error('文件读取失败'))
      }
      
      // 根据文件类型选择读取方式
      if (file.type.includes('text')) {
        reader.readAsText(file, 'UTF-8')
      } else {
        reader.readAsArrayBuffer(file)
      }
    })
  }

  /**
   * 处理单个文件上传
   */
  const processSingleFile = async (
    file: UploadFile,
    index: number
  ): Promise<BatchUploadResult> => {
    try {
      // 更新文件状态为上传中
      file.status = 'uploading'

      // 1. 提取文件内容
      const content = await extractFileContent(file.file)

      // 2. 创建病案记录
      const recordData = {
        patient_name: `批量导入患者-${index + 1}`,
        patient_age: 50,
        patient_gender: 'U' as const,
        department: '批量导入',
        admission_date: new Date().toISOString().split('T')[0],
        record_type: 'inpatient' as const,
        content: content,
        file_name: file.name,
        file_size: file.file.size,
        status: 'pending' as const
      }

      const response = await createMedicalRecord(recordData)
      
      if (!response.success || !response.data) {
        throw new Error(response.error || '创建病案记录失败')
      }

      // 更新文件状态为成功
      file.status = 'success'
      file.id = response.data.id

      return {
        file,
        success: true,
        recordId: response.data.id
      }
    } catch (error) {
      // 更新文件状态为失败
      file.status = 'error'
      file.error = error instanceof Error ? error.message : '未知错误'

      return {
        file,
        success: false,
        error: file.error
      }
    }
  }

  /**
   * 批量上传文件（模拟版本）
   */
  const uploadBatch = async (
    files: UploadFile[],
    options: BatchUploadOptions = {}
  ): Promise<BatchUploadResult[]> => {
    const {
      onProgress,
      onFileComplete,
      onBatchComplete,
      batchSize = 5
    } = options

    if (files.length === 0) {
      return []
    }

    isUploading.value = true
    uploadProgress.value = 0

    try {
      console.log('🚀 开始批量上传（模拟模式）:', files.length, '个文件')

      const results: BatchUploadResult[] = []
      let processedCount = 0

      // 分批处理文件
      for (let i = 0; i < files.length; i += batchSize) {
        const batch = files.slice(i, i + batchSize)
        
        // 并行处理当前批次的文件
        const batchPromises = batch.map((file, batchIndex) => 
          processSingleFile(file, i + batchIndex)
        )

        const batchResults = await Promise.all(batchPromises)
        results.push(...batchResults)

        // 更新进度
        processedCount += batch.length
        const progress = Math.round((processedCount / files.length) * 100)
        uploadProgress.value = progress

        // 调用进度回调
        onProgress?.(progress)

        // 调用文件完成回调
        batchResults.forEach((result, batchIndex) => {
          onFileComplete?.(i + batchIndex, result.success, result.error)
        })

        // 短暂延迟，模拟处理时间
        if (i + batchSize < files.length) {
          await new Promise(resolve => setTimeout(resolve, 500))
        }
      }

      // 调用批量完成回调
      onBatchComplete?.(results)

      const successCount = results.filter(r => r.success).length
      const failedCount = results.filter(r => !r.success).length
      
      console.log('✅ 批量上传完成（模拟模式）:', {
        total: files.length,
        success: successCount,
        failed: failedCount
      })

      return results
    } catch (error) {
      console.error('❌ 批量上传失败:', error)
      throw error
    } finally {
      isUploading.value = false
    }
  }

  return {
    isUploading,
    uploadProgress,
    uploadBatch
  }
}
