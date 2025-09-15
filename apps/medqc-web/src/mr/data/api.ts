// API 配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

// 通用请求函数
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const fullUrl = `${API_BASE_URL}${url}`
  
  const defaultOptions: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      // 如果需要认证，可以在这里添加 Authorization header
      // 'Authorization': `Bearer ${getToken()}`
    },
    ...options
  }

  try {
    const response = await fetch(fullUrl, defaultOptions)
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    return await response.json()
  } catch (error) {
    console.error('API request failed:', error)
    throw error
  }
}

// 患者信息接口
export interface Patient {
  id: string
  record_name: string
  record_number: string
  patient_info: {
    name: string
    age: number
    gender: string
  }
  department: string
  status: string
  primary_diagnosis?: string
  secondary_diagnosis?: string[]
  major_surgery?: string
  raw_text?: string
  created_at: string
  updated_at: string
  document_count?: number
  classification_status?: string
  ai_confidence_score?: number
}

// 文档信息接口
export interface Document {
  id: string
  record_id: string
  category_id: string
  type_id: string
  title: string
  content: string
  summary?: string
  ai_classified: boolean
  classification_confidence: number
  manual_verified: boolean
  position_info: {
    startIndex?: number
    endIndex?: number
    startMarker?: string
    endMarker?: string
    fullContent?: string
  }
  sort_order: number
  status: string
  qc_status: string
  qc_score: number
  qc_issues: any[]
  metadata: {
    type_code: string
    content_hash: string
    extracted_at?: string
    category_code: string
    original_doc_id?: string
    extraction_method: string
  }
  created_at: string
  updated_at: string
  qc_last_analyzed?: string
  qc_analysis_version?: string
  content_hash: string
  content_preview: string
  type_info: {
    type_code: string
    type_name: string
  }
  category_code: string
}

// 文档分类响应接口
export interface DocumentsResponse {
  record_id: string
  total_documents: number
  categories: {
    category_id?: string
    category_code: string
    category_name: string
    category_description: string
    document_count: number
    documents: Document[]
  }[]
  classification_summary: Record<string, {
    name: string
    count: number
    types: Record<string, {
      name: string
      count: number
    }>
  }>
}

// 树节点接口
export interface TreeNode {
  key: string
  title: string
  isLeaf?: boolean
  children?: TreeNode[]
  aiScore?: number
  created_at?: string
  category?: string
  document?: Document
}

/**
 * 获取患者信息
 */
export async function fetchPatientById(id: string): Promise<Patient> {
  return request<Patient>(`/api/medical-records/${id}`)
}

/**
 * 获取文档列表
 */
export async function fetchDocumentsByRecord(id: string): Promise<DocumentsResponse> {
  return request<DocumentsResponse>(`/api/medical-records/${id}/documents`)
}

/**
 * 获取文档的完整内容
 */
export function getDocumentFullContent(document: Document, originalText?: string): string {
  // 1. 优先使用 position_info.fullContent
  if (document.position_info?.fullContent && document.position_info.fullContent.trim()) {
    return document.position_info.fullContent
  }

  // 2. 如果有原始文本和位置信息，从原始文本中提取
  if (originalText && document.position_info?.startIndex !== undefined && document.position_info?.endIndex !== undefined) {
    const { startIndex, endIndex } = document.position_info
    if (startIndex >= 0 && endIndex > startIndex && endIndex <= originalText.length) {
      return originalText.slice(startIndex, endIndex)
    }
  }

  // 3. 如果有原始文本，尝试通过文档标题来提取完整内容
  if (originalText && document.title) {
    const extractedContent = extractDocumentContentByTitle(originalText, document.title)
    if (extractedContent && extractedContent.length > document.content.length) {
      return extractedContent
    }
  }

  // 4. 兜底使用 content 字段（可能是摘要）
  return document.content || '暂无内容'
}

/**
 * 根据文档标题从原始文本中提取完整内容
 */
function extractDocumentContentByTitle(originalText: string, title: string): string {
  const titleIndex = originalText.indexOf(title)
  if (titleIndex === -1) {
    return ''
  }

  // 查找文档开始位置（标题所在行的开始）
  let startIndex = titleIndex
  while (startIndex > 0 && originalText[startIndex - 1] !== '\n') {
    startIndex--
  }

  // 查找文档结束位置（下一个文档标题或特定标记）
  const nextDocPatterns = [
    /\n\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}/,  // 日期时间格式
    /\n[=]{3,}.*[=]{3,}/,                  // 分页标记
    /\n\d+\.\s*[^\n]+记录/,                // 编号+记录类型
    /\n(孙治庆|张云海|王标|王飞|杜忠宜).*?(主治医师|主任医师|副主任医师)/,  // 医师姓名
    /\n(术前|术后|手术|CT|核磁|MRI|病理|出院).*?记录/,  // 其他文档类型
  ]

  let endIndex = originalText.length
  const searchText = originalText.slice(titleIndex + title.length)

  for (const pattern of nextDocPatterns) {
    const match = searchText.match(pattern)
    if (match && match.index !== undefined) {
      const potentialEnd = titleIndex + title.length + match.index
      if (potentialEnd > startIndex && potentialEnd < endIndex) {
        endIndex = potentialEnd
      }
    }
  }

  // 提取并清理内容
  let content = originalText.slice(startIndex, endIndex).trim()

  // 移除多余的空行
  content = content.replace(/\n\s*\n\s*\n/g, '\n\n')

  return content
}

// 分类代码到中文名称的映射
const CATEGORY_NAME_MAP: Record<string, string> = {
  'progress_note': '病程记录',
  'operation_record': '手术记录',
  'examination_report': '检查报告',
  'admission_record': '入院记录',
  'discharge_record': '出院记录',
  'nursing_document': '护理文书',
  'medical_order': '医嘱记录',
  'unknown': '其他文档'
}

/**
 * 获取分类的中文名称
 */
function getCategoryDisplayName(categoryCode: string, categoryName: string): string {
  // 优先使用映射表中的中文名称
  return CATEGORY_NAME_MAP[categoryCode] || categoryName || '未分类'
}

/**
 * 构建树形数据结构
 */
export function buildTreeData(documentsResponse: DocumentsResponse): TreeNode[] {
  if (!documentsResponse.categories || documentsResponse.categories.length === 0) {
    return []
  }

  return documentsResponse.categories.map(category => {
    const displayName = getCategoryDisplayName(category.category_code, category.category_name)

    const categoryNode: TreeNode = {
      key: `category-${category.category_code}`,
      title: `${displayName} (${category.document_count})`,
      isLeaf: false,
      children: category.documents.map(doc => ({
        key: doc.id,
        title: doc.title || doc.type_info?.type_name || '未命名文档',
        isLeaf: true,
        aiScore: doc.classification_confidence,
        created_at: doc.created_at,
        category: displayName,
        document: doc
      }))
    }

    return categoryNode
  })
}

/**
 * 从文档响应中提取扁平化的文档列表
 */
export function extractDocuments(documentsResponse: DocumentsResponse): Document[] {
  const documents: Document[] = []
  
  documentsResponse.categories.forEach(category => {
    documents.push(...category.documents)
  })
  
  return documents
}

/**
 * 根据文档ID查找文档
 */
export function findDocumentById(documentsResponse: DocumentsResponse, docId: string): Document | null {
  for (const category of documentsResponse.categories) {
    const doc = category.documents.find(d => d.id === docId)
    if (doc) return doc
  }
  return null
}

/**
 * 生成文档摘要（后备方案）
 */
export function generateSummary(content: string, maxLength: number = 200): string {
  if (!content) return ''
  
  const cleanContent = content
    .replace(/\n+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  
  if (cleanContent.length <= maxLength) {
    return cleanContent
  }
  
  return cleanContent.slice(0, maxLength) + '…'
}

/**
 * 转义HTML特殊字符
 */
export function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}

/**
 * 转义正则表达式特殊字符
 */
export function escapeRegExp(string: string): string {
  return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * 高亮搜索关键词
 */
export function highlightSearchKeyword(content: string, keyword: string): string {
  if (!keyword.trim()) return escapeHtml(content)
  
  const escapedContent = escapeHtml(content)
  const escapedKeyword = escapeRegExp(keyword)
  const regex = new RegExp(`(${escapedKeyword})`, 'gi')
  
  return escapedContent.replace(regex, '<mark>$1</mark>')
}

/**
 * 获取认证token（如果需要）
 */
function getToken(): string | null {
  // 从localStorage或其他地方获取token
  return localStorage.getItem('auth_token')
}

/**
 * 设置认证token
 */
export function setAuthToken(token: string): void {
  localStorage.setItem('auth_token', token)
}

/**
 * 清除认证token
 */
export function clearAuthToken(): void {
  localStorage.removeItem('auth_token')
}

/**
 * 更新医疗文档内容
 */
export async function updateDocument(documentId: string, content: string): Promise<void> {
  const token = getToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE_URL}/api/medical-documents/${documentId}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({
      content: content,
      updated_at: new Date().toISOString()
    })
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  const result = await response.json()
  if (!result.success) {
    throw new Error('更新文档失败')
  }
}

// 文档管理相关API
export interface DocumentType {
  id: string
  category_id: string
  category_code: string
  category_name: string
  type_code: string
  type_name: string
  description?: string
  sort_order: number
}

export interface DocumentCategory {
  category_id: string
  category_code: string
  category_name: string
  description?: string
  types: DocumentType[]
}

export interface CreateDocumentRequest {
  title: string
  content: string
  document_type: string
  category_code?: string
  type_code?: string
  summary?: string
}

export async function getDocumentTypes(): Promise<DocumentCategory[]> {
  const response = await fetch(`${API_BASE_URL}/api/document-types`)

  if (!response.ok) {
    const errorText = await response.text()
    throw new Error(`HTTP ${response.status}: ${errorText || 'Unknown error'}`)
  }

  const data = await response.json()
  return data.categories || []
}

export async function createDocument(recordId: string, request: CreateDocumentRequest): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/medical-records/${recordId}/documents`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(request)
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

export async function deleteDocument(documentId: string, hardDelete: boolean = false): Promise<any> {
  const url = `${API_BASE_URL}/api/medical-documents/${documentId}${hardDelete ? '?hard_delete=true' : ''}`

  const response = await fetch(url, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json'
    }
  })

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`)
  }

  return await response.json()
}

// 导出默认配置
export const config = {
  API_BASE_URL,
  DEFAULT_SUMMARY_LENGTH: 200,
  STORAGE_KEYS: {
    NAV_WIDTH: 'mr_nav_w',
    ASIDE_WIDTH: 'mr_aside_w',
    COLLAPSED_NAV: 'mr_collapsed_nav',
    COLLAPSED_ASIDE: 'mr_collapsed_aside',
    FONT_SIZE: 'mr_font_px',
    SUMMARY_MODE: 'mr_summary'
  }
}
