import { ref } from 'vue'
import { supabase, TABLES } from '@/lib/backend-store'
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
  onProgress?: (_progress: number) => void
  onFileComplete?: (_index: number, _success: boolean, _error?: string) => void
  onBatchComplete?: (_results: BatchUploadResult[]) => void
  batchSize?: number // 每批处理的文件数量
  maxRetries?: number // 最大重试次数
}

// 批量上传结果
interface BatchUploadResult {
  file: UploadFile
  success: boolean
  recordId?: string
  error?: string
}

// 批量处理任务状态
interface BatchTask {
  id: string
  user_id: string
  task_type: 'upload' | 'analysis' | 'export'
  status: 'pending' | 'processing' | 'completed' | 'failed'
  total_items: number
  processed_items: number
  failed_items: number
  progress_percentage: number
  error_details?: Record<string, unknown>
  created_at: string
  started_at?: string
  completed_at?: string
}

export function useBatchUpload() {
  const isUploading = ref(false)
  const uploadProgress = ref(0)
  const currentBatch = ref<BatchTask | null>(null)

  /**
   * 文件内容提取
   */
  const extractFileContent = async (file: File): Promise<string> => {
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader()

      reader.onload = (e) => {
        const content = e.target?.result as string

        // 根据文件类型处理内容
        if (file.type.includes('text')) {
          resolve(content)
        } else if (file.type.includes('pdf')) {
          // PDF文件需要特殊处理，这里先返回文件名作为占位符
          resolve(`PDF文件: ${file.name}\n\n[PDF内容需要后端处理]`)
        } else if (file.type.includes('doc')) {
          // Word文件需要特殊处理
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
   * 上传单个文件到Supabase Storage
   */
  const uploadFileToStorage = async (file: File): Promise<string> => {
    const fileName = `${Date.now()}-${file.name}`
    const filePath = `medical-records/${fileName}`

    const { error } = await supabase.storage.from('medical-files').upload(filePath, file, {
      cacheControl: '3600',
      upsert: false,
    })

    if (error) {
      throw new Error(`文件上传失败: ${error.message}`)
    }

    // 获取公共URL
    const { data: urlData } = supabase.storage.from('medical-files').getPublicUrl(filePath)

    return urlData.publicUrl
  }

  /**
   * 创建批量处理任务
   */
  const createBatchTask = async (
    taskType: 'upload' | 'analysis' | 'export',
    totalItems: number,
  ): Promise<string> => {
    const { data: userData } = await supabase.auth.getUser()
    if (!userData.user) {
      throw new Error('用户未登录')
    }

    const { data, error } = await supabase
      .from(TABLES.BATCH_PROCESSING_TASKS)
      .insert({
        user_id: userData.user.id,
        task_type: taskType,
        total_items: totalItems,
        status: 'pending',
      })
      .select()
      .single()

    if (error) {
      throw new Error(`创建批量任务失败: ${error.message}`)
    }

    return data.id
  }

  /**
   * 更新批量处理任务状态
   */
  const updateBatchTask = async (taskId: string, updates: Partial<BatchTask>): Promise<void> => {
    const { error } = await supabase
      .from(TABLES.BATCH_PROCESSING_TASKS)
      .update(updates)
      .eq('id', taskId)

    if (error) {
      console.error('更新批量任务状态失败:', error)
    }
  }

  /**
   * 处理单个文件上传
   */
  const processSingleFile = async (file: UploadFile, index: number): Promise<BatchUploadResult> => {
    try {
      // 更新文件状态为上传中
      file.status = 'uploading'

      // 1. 提取文件内容
      const content = await extractFileContent(file.file)

      // 2. 上传文件到存储
      let fileUrl: string | null = null
      try {
        fileUrl = await uploadFileToStorage(file.file)
      } catch (error) {
        console.warn('文件存储上传失败，继续处理:', error)
      }

      // 3. 创建病案记录
      const recordData = {
        patient_name: `批量导入患者 ${index + 1}`,
        patient_age: 50, // 默认年龄
        patient_gender: 'U' as const, // 未知性别
        department: '批量导入',
        admission_date: new Date().toISOString().split('T')[0],
        record_type: 'inpatient' as const,
        content: content,
        file_url: fileUrl,
        file_name: file.name,
        file_size: file.file.size,
        status: 'pending' as const,
      }

      const response = await createMedicalRecord(recordData)

      if (!response.success || !response.data) {
        const errorMessage =
          typeof response.error === 'string' ? response.error : response.error?.message
        throw new Error(errorMessage || '创建病案记录失败')
      }

      // 更新文件状态为成功
      file.status = 'success'
      file.id = response.data.id

      return {
        file,
        success: true,
        recordId: response.data.id,
      }
    } catch (error) {
      // 更新文件状态为失败
      file.status = 'error'
      file.error = error instanceof Error ? error.message : '未知错误'

      return {
        file,
        success: false,
        error: file.error,
      }
    }
  }

  /**
   * 批量上传文件
   */
  const uploadBatch = async (
    files: UploadFile[],
    options: BatchUploadOptions = {},
  ): Promise<BatchUploadResult[]> => {
    const {
      onProgress,
      onFileComplete,
      onBatchComplete,
      batchSize = 5, // 每批处理5个文件
    } = options

    if (files.length === 0) {
      return []
    }

    isUploading.value = true
    uploadProgress.value = 0

    try {
      // 创建批量处理任务
      const taskId = await createBatchTask('upload', files.length)

      // 更新任务状态为处理中
      await updateBatchTask(taskId, {
        status: 'processing',
        started_at: new Date().toISOString(),
      })

      const results: BatchUploadResult[] = []
      let processedCount = 0

      // 分批处理文件
      for (let i = 0; i < files.length; i += batchSize) {
        const batch = files.slice(i, i + batchSize)

        // 并行处理当前批次的文件
        const batchPromises = batch.map((file, batchIndex) =>
          processSingleFile(file, i + batchIndex),
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

        // 更新批量任务进度
        const failedCount = results.filter((r) => !r.success).length

        await updateBatchTask(taskId, {
          processed_items: processedCount,
          failed_items: failedCount,
          progress_percentage: progress,
        })

        // 短暂延迟，避免过于频繁的请求
        if (i + batchSize < files.length) {
          await new Promise((resolve) => setTimeout(resolve, 100))
        }
      }

      // 完成批量任务
      const failedCount = results.filter((r) => !r.success).length

      await updateBatchTask(taskId, {
        status: failedCount === 0 ? 'completed' : 'failed',
        completed_at: new Date().toISOString(),
        processed_items: files.length,
        failed_items: failedCount,
        progress_percentage: 100,
      })

      // 调用批量完成回调
      onBatchComplete?.(results)

      return results
    } catch (error) {
      console.error('批量上传失败:', error)
      throw error
    } finally {
      isUploading.value = false
    }
  }

  /**
   * 监听批量任务状态变化
   */
  const subscribeToBatchTask = (taskId: string, callback: (_task: BatchTask) => void) => {
    const subscription = supabase
      .channel(`batch_task_${taskId}`)
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: TABLES.BATCH_PROCESSING_TASKS,
          filter: `id=eq.${taskId}`,
        },
        (payload: unknown) => {
          if (typeof payload === 'object' && payload && 'new' in payload) {
            callback((payload as { new: BatchTask }).new)
          }
        },
      )
      .subscribe()

    return subscription
  }

  /**
   * 获取用户的批量任务列表
   */
  const getUserBatchTasks = async (limit = 10) => {
    const { data: userData } = await supabase.auth.getUser()
    if (!userData.user) {
      throw new Error('用户未登录')
    }

    const { data, error } = await supabase
      .from(TABLES.BATCH_PROCESSING_TASKS)
      .select('*')
      .eq('user_id', userData.user.id)
      .order('created_at', { ascending: false })
      .limit(limit)

    if (error) {
      throw new Error(`获取批量任务失败: ${error.message}`)
    }

    return data as BatchTask[]
  }

  return {
    isUploading,
    uploadProgress,
    currentBatch,
    uploadBatch,
    subscribeToBatchTask,
    getUserBatchTasks,
    createBatchTask,
    updateBatchTask,
  }
}
