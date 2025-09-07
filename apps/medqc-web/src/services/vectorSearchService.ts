/**
 * 向量搜索服务
 * 提供基于语义的中文医疗文档搜索功能
 */

import { supabase } from '@/lib/supabase'
import type { Database } from '@/types/database'

// 搜索结果类型
export interface VectorSearchResult {
  record_id: string
  record_number: string
  patient_name: string
  diagnosis_primary: string
  content_snippet: string
  similarity_score: number
  content_type: string
  section_name?: string
}

// 混合搜索结果类型
export interface HybridSearchResult extends VectorSearchResult {
  combined_score: number
  vector_score: number
  keyword_score: number
}

// 相似病例结果类型
export interface SimilarCaseResult {
  record_id: string
  record_number: string
  patient_name: string
  diagnosis_primary: string
  similarity_score: number
  common_keywords: string[]
}

// 搜索统计类型
export interface SearchStatistics {
  total_searches: number
  unique_users: number
  avg_results_per_search: number
  avg_search_time_ms: number
  popular_queries: string[]
}

export class VectorSearchService {
  /**
   * 语义搜索医疗记录
   */
  static async semanticSearch(
    query: string,
    options: {
      similarityThreshold?: number
      maxResults?: number
      contentTypes?: string[]
      userId?: string
    } = {}
  ): Promise<VectorSearchResult[]> {
    try {
      const {
        similarityThreshold = 0.7,
        maxResults = 10,
        contentTypes = ['full_content', 'diagnosis', 'summary'],
        userId
      } = options

      // 首先需要生成查询向量（这里需要调用后端API）
      const queryEmbedding = await this.generateQueryEmbedding(query)

      // 执行语义搜索
      const { data, error } = await supabase.rpc('semantic_search_medical_records', {
        query_embedding: queryEmbedding,
        similarity_threshold: similarityThreshold,
        max_results: maxResults,
        content_types: contentTypes
      })

      if (error) {
        throw new Error(`语义搜索失败: ${error.message}`)
      }

      // 记录搜索历史
      if (userId) {
        await this.logSearchHistory(userId, query, 'semantic', data?.length || 0)
      }

      return data || []
    } catch (error) {
      console.error('语义搜索错误:', error)
      throw error
    }
  }

  /**
   * 混合搜索（向量 + 关键词）
   */
  static async hybridSearch(
    query: string,
    options: {
      vectorWeight?: number
      keywordWeight?: number
      maxResults?: number
      userId?: string
    } = {}
  ): Promise<HybridSearchResult[]> {
    try {
      const {
        vectorWeight = 0.7,
        keywordWeight = 0.3,
        maxResults = 10,
        userId
      } = options

      // 生成查询向量
      const queryEmbedding = await this.generateQueryEmbedding(query)

      // 执行混合搜索
      const { data, error } = await supabase.rpc('hybrid_search_medical_records', {
        query_embedding: queryEmbedding,
        search_keywords: query,
        vector_weight: vectorWeight,
        keyword_weight: keywordWeight,
        max_results: maxResults
      })

      if (error) {
        throw new Error(`混合搜索失败: ${error.message}`)
      }

      // 记录搜索历史
      if (userId) {
        await this.logSearchHistory(userId, query, 'hybrid', data?.length || 0)
      }

      return data || []
    } catch (error) {
      console.error('混合搜索错误:', error)
      throw error
    }
  }

  /**
   * 查找相似病例
   */
  static async findSimilarCases(
    recordId: string,
    options: {
      similarityThreshold?: number
      maxResults?: number
    } = {}
  ): Promise<SimilarCaseResult[]> {
    try {
      const {
        similarityThreshold = 0.8,
        maxResults = 5
      } = options

      const { data, error } = await supabase.rpc('find_similar_cases', {
        source_record_id: recordId,
        similarity_threshold: similarityThreshold,
        max_results: maxResults
      })

      if (error) {
        throw new Error(`查找相似病例失败: ${error.message}`)
      }

      return data || []
    } catch (error) {
      console.error('查找相似病例错误:', error)
      throw error
    }
  }

  /**
   * 生成查询向量（调用后端API）
   */
  private static async generateQueryEmbedding(query: string): Promise<number[]> {
    try {
      // 这里需要调用后端API来生成向量
      // 因为前端无法直接调用 OpenAI API（安全考虑）
      const response = await fetch('/api/generate-embedding', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ text: query })
      })

      if (!response.ok) {
        throw new Error(`生成向量失败: ${response.statusText}`)
      }

      const result = await response.json()
      return result.embedding
    } catch (error) {
      console.error('生成查询向量错误:', error)
      throw error
    }
  }

  /**
   * 记录搜索历史
   */
  private static async logSearchHistory(
    userId: string,
    query: string,
    searchType: string,
    resultsCount: number
  ): Promise<void> {
    try {
      const startTime = Date.now()
      
      await supabase.rpc('log_vector_search', {
        p_user_id: userId,
        p_search_query: query,
        p_search_type: searchType,
        p_results_count: resultsCount,
        p_search_time_ms: Date.now() - startTime
      })
    } catch (error) {
      console.warn('记录搜索历史失败:', error)
    }
  }

  /**
   * 获取搜索统计
   */
  static async getSearchStatistics(daysBack: number = 30): Promise<SearchStatistics | null> {
    try {
      const { data, error } = await supabase.rpc('get_search_statistics', {
        days_back: daysBack
      })

      if (error) {
        throw new Error(`获取搜索统计失败: ${error.message}`)
      }

      return data?.[0] || null
    } catch (error) {
      console.error('获取搜索统计错误:', error)
      return null
    }
  }

  /**
   * 智能搜索建议
   */
  static async getSearchSuggestions(query: string): Promise<string[]> {
    try {
      // 基于历史搜索和相似度提供建议
      const { data, error } = await supabase
        .from('vector_search_history')
        .select('search_query')
        .ilike('search_query', `%${query}%`)
        .limit(5)

      if (error) {
        console.warn('获取搜索建议失败:', error)
        return []
      }

      return data?.map(item => item.search_query) || []
    } catch (error) {
      console.error('获取搜索建议错误:', error)
      return []
    }
  }

  /**
   * 批量创建文档向量（管理员功能）
   */
  static async batchCreateEmbeddings(records: Array<{
    record_id: string
    content: string
    content_type?: string
    section_name?: string
  }>): Promise<string[]> {
    try {
      // 调用后端API进行批量处理
      const response = await fetch('/api/batch-create-embeddings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ records   })
      })

      if (!response.ok) {
        throw new Error(`批量创建向量失败: ${response.statusText}`)
      }

      const result = await response.json()
      return result.embedding_ids || []
    } catch (error) {
      console.error('批量创建向量错误:', error)
      throw error
    }
  }

  /**
   * 清理孤立的向量数据
   */
  static async cleanupOrphanedEmbeddings(): Promise<number> {
    try {
      const { data, error } = await supabase.rpc('cleanup_orphaned_embeddings')

      if (error) {
        throw new Error(`清理向量数据失败: ${error.message}`)
      }

      return data || 0
    } catch (error) {
      console.error('清理向量数据错误:', error)
      return 0
    }
  }
}

// 搜索工具函数
export const searchUtils = {
  /**
   * 高亮搜索关键词
   */
  highlightKeywords(text: string, keywords: string): string {
    if (!keywords.trim()) return text
    
    const keywordList = keywords.split(/\s+/).filter(k => k.length > 0)
    let highlightedText = text
    
    keywordList.forEach(keyword => {
      const regex = new RegExp(`(${keyword})`, 'gi')
      highlightedText = highlightedText.replace(regex, '<mark>$1</mark>')
    })
    
    return highlightedText
  },

  /**
   * 格式化相似度分数
   */
  formatSimilarityScore(score: number): string {
    return `${(score * 100).toFixed(1)}%`
  },

  /**
   * 获取搜索结果摘要
   */
  getSearchSummary(results: VectorSearchResult[], query: string): string {
    if (results.length === 0) {
      return `未找到与"${query}"相关的医疗记录`
    }
    
    const avgScore = results.reduce((sum, r) => sum + r.similarity_score, 0) / results.length
    return `找到 ${results.length} 条相关记录，平均相似度 ${this.formatSimilarityScore(avgScore)}`
  }
}
