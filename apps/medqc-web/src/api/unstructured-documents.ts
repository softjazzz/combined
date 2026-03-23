/**
 * 非结构化医疗文档API
 * 用于处理复制粘贴的原始病历文本
 */

import { supabase, TABLES } from '@/lib/supabase'
import { ApiWrapper } from '@/utils/api-wrapper'
import type { ApiResponse } from '@/utils/api-wrapper'
import type { Database } from '@/types/database'

type UnstructuredDocument = Database['public']['Tables']['unstructured_medical_documents']['Row']
type CreateUnstructuredDocument =
  Database['public']['Tables']['unstructured_medical_documents']['Insert']
type UpdateUnstructuredDocument =
  Database['public']['Tables']['unstructured_medical_documents']['Update']

/**
 * 创建非结构化文档
 */
export async function createUnstructuredDocument(
  data: CreateUnstructuredDocument,
): Promise<ApiResponse<UnstructuredDocument>> {
  return ApiWrapper.query(async () => {
    const result = await supabase
      .from('unstructured_medical_documents')
      .insert(data)
      .select()
      .single()

    return result
  })
}

/**
 * 快速保存复制粘贴的病历文本
 */
export async function saveRawMedicalText(
  content: string,
  title?: string,
  category?: string,
): Promise<ApiResponse<UnstructuredDocument>> {
  const documentData: CreateUnstructuredDocument = {
    title: title || '粘贴的病历文档',
    document_type: 'copied_record',
    raw_content: content,
    source: 'copy_paste',
    category: category || '未分类',
    tags: ['原始文档', '待处理'],
    processing_status: 'pending',
    qc_status: 'not_analyzed',
    priority_level: 1,
  }

  return createUnstructuredDocument(documentData)
}

/**
 * 获取非结构化文档列表
 */
export async function getUnstructuredDocuments(options?: {
  document_type?: string
  processing_status?: string
  qc_status?: string
  category?: string
  limit?: number
  offset?: number
}): Promise<ApiResponse<UnstructuredDocument[]>> {
  return ApiWrapper.query(async () => {
    let query = supabase
      .from('unstructured_medical_documents')
      .select('*')
      .eq('is_deleted', false)
      .order('created_at', { ascending: false })

    // 应用筛选条件
    if (options?.document_type) {
      query = query.eq('document_type', options.document_type)
    }
    if (options?.processing_status) {
      query = query.eq('processing_status', options.processing_status)
    }
    if (options?.qc_status) {
      query = query.eq('qc_status', options.qc_status)
    }
    if (options?.category) {
      query = query.eq('category', options.category)
    }

    // 分页
    if (options?.limit) {
      query = query.limit(options.limit)
    }
    if (options?.offset) {
      query = query.range(options.offset, options.offset + (options.limit || 10) - 1)
    }

    const result = await query
    return result
  })
}

/**
 * 获取单个非结构化文档
 */
export async function getUnstructuredDocument(
  id: string,
): Promise<ApiResponse<UnstructuredDocument>> {
  return ApiWrapper.query(async () => {
    const result = await supabase
      .from('unstructured_medical_documents')
      .select('*')
      .eq('id', id)
      .eq('is_deleted', false)
      .single()

    return result
  })
}

/**
 * 更新非结构化文档
 */
export async function updateUnstructuredDocument(
  id: string,
  data: UpdateUnstructuredDocument,
): Promise<ApiResponse<UnstructuredDocument>> {
  return ApiWrapper.query(async () => {
    const result = await supabase
      .from('unstructured_medical_documents')
      .update(data)
      .eq('id', id)
      .select()
      .single()

    return result
  })
}

/**
 * 软删除非结构化文档
 */
export async function deleteUnstructuredDocument(id: string): Promise<ApiResponse<void>> {
  return ApiWrapper.query(async () => {
    const result = await supabase
      .from('unstructured_medical_documents')
      .update({
        is_deleted: true,
        deleted_at: new Date().toISOString(),
      })
      .eq('id', id)

    return { data: undefined, error: result.error }
  })
}

/**
 * 批量删除非结构化文档
 */
export async function batchDeleteUnstructuredDocuments(ids: string[]): Promise<ApiResponse<void>> {
  return ApiWrapper.query(async () => {
    const result = await supabase
      .from('unstructured_medical_documents')
      .update({
        is_deleted: true,
        deleted_at: new Date().toISOString(),
      })
      .in('id', ids)

    return { data: undefined, error: result.error }
  })
}

/**
 * 搜索非结构化文档
 */
export async function searchUnstructuredDocuments(
  searchTerm: string,
  options?: {
    limit?: number
    offset?: number
  },
): Promise<ApiResponse<UnstructuredDocument[]>> {
  return ApiWrapper.query(async () => {
    let query = supabase
      .from('unstructured_medical_documents')
      .select('*')
      .eq('is_deleted', false)
      .or(
        `title.ilike.%${searchTerm}%,raw_content.ilike.%${searchTerm}%,category.ilike.%${searchTerm}%`,
      )
      .order('created_at', { ascending: false })

    // 分页
    if (options?.limit) {
      query = query.limit(options.limit)
    }
    if (options?.offset) {
      query = query.range(options.offset, options.offset + (options.limit || 10) - 1)
    }

    const result = await query
    return result
  })
}

/**
 * 标记文档为已处理
 */
export async function markDocumentAsProcessed(
  id: string,
  structuredRecordId?: string,
  extractedData?: Record<string, unknown>,
): Promise<ApiResponse<UnstructuredDocument>> {
  const updateData: UpdateUnstructuredDocument = {
    processing_status: 'completed',
    processed_at: new Date().toISOString(),
  }

  if (structuredRecordId) {
    updateData.structured_record_id = structuredRecordId
  }

  if (extractedData) {
    updateData.extracted_data = extractedData
  }

  return updateUnstructuredDocument(id, updateData)
}

/**
 * 获取文档统计信息
 */
export async function getUnstructuredDocumentsStats(): Promise<
  ApiResponse<{
    total: number
    pending: number
    processing: number
    completed: number
    failed: number
    by_type: Record<string, number>
    by_category: Record<string, number>
  }>
> {
  return ApiWrapper.query(async () => {
    // 获取总数和状态统计
    const { data: statusStats, error: statusError } = await supabase
      .from('unstructured_medical_documents')
      .select('processing_status')
      .eq('is_deleted', false)

    if (statusError) {
      return { data: null, error: statusError }
    }

    // 获取类型统计
    const { data: typeStats, error: typeError } = await supabase
      .from('unstructured_medical_documents')
      .select('document_type')
      .eq('is_deleted', false)

    if (typeError) {
      return { data: null, error: typeError }
    }

    // 获取分类统计
    const { data: categoryStats, error: categoryError } = await supabase
      .from('unstructured_medical_documents')
      .select('category')
      .eq('is_deleted', false)

    if (categoryError) {
      return { data: null, error: categoryError }
    }

    // 统计处理
    const total = statusStats.length
    const pending = statusStats.filter((s) => s.processing_status === 'pending').length
    const processing = statusStats.filter((s) => s.processing_status === 'processing').length
    const completed = statusStats.filter((s) => s.processing_status === 'completed').length
    const failed = statusStats.filter((s) => s.processing_status === 'failed').length

    const by_type = typeStats.reduce(
      (acc, item) => {
        acc[item.document_type] = (acc[item.document_type] || 0) + 1
        return acc
      },
      {} as Record<string, number>,
    )

    const by_category = categoryStats.reduce(
      (acc, item) => {
        const category = item.category || '未分类'
        acc[category] = (acc[category] || 0) + 1
        return acc
      },
      {} as Record<string, number>,
    )

    return {
      data: {
        total,
        pending,
        processing,
        completed,
        failed,
        by_type,
        by_category,
      },
      error: null,
    }
  })
}
