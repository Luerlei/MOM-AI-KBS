import { get, post, put, del, upload } from './request'
import type {
  Knowledge,
  KnowledgeQuery,
  KnowledgeForm,
  KnowledgeBatchRequest,
  PaginatedData,
  ApiResponse
} from '@/types'

/**
 * 获取知识列表（分页）
 */
export function getKnowledgeList(
  params: KnowledgeQuery
): Promise<PaginatedData<Knowledge>> {
  return get<PaginatedData<Knowledge>>('/knowledge', params)
}

/**
 * 获取知识详情
 */
export function getKnowledgeDetail(id: number): Promise<Knowledge> {
  return get<Knowledge>(`/knowledge/${id}`)
}

/**
 * 创建知识
 */
export function createKnowledge(data: KnowledgeForm): Promise<Knowledge> {
  return post<Knowledge>('/knowledge', data)
}

/**
 * 更新知识
 */
export function updateKnowledge(id: number, data: KnowledgeForm): Promise<Knowledge> {
  return put<Knowledge>(`/knowledge/${id}`, data)
}

/**
 * 删除知识
 */
export function deleteKnowledge(id: number): Promise<void> {
  return del<void>(`/knowledge/${id}`)
}

/**
 * 批量上传文件
 */
export function uploadKnowledgeFiles(
  files: File[],
  options?: { category_id?: number | null; tag_ids?: number[]; auto_tag?: boolean }
): Promise<ApiResponse> {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
  if (options?.category_id) {
    formData.append('category_id', String(options.category_id))
  }
  if (options?.tag_ids?.length) {
    formData.append('tag_ids', options.tag_ids.join(','))
  }
  if (options?.auto_tag) {
    formData.append('auto_tag', 'true')
  }
  return upload<ApiResponse>('/knowledge/upload', formData)
}

/**
 * 批量操作
 */
export function batchOperateKnowledge(
  data: KnowledgeBatchRequest
): Promise<{ success_count: number; failed_count: number }> {
  return post<{ success_count: number; failed_count: number }>('/knowledge/batch', data)
}

/**
 * 获取相关内容
 */
export function getRelatedKnowledge(id: number): Promise<Knowledge[]> {
  return get<Knowledge[]>(`/knowledge/${id}/related`)
}

/**
 * 知识分块信息
 */
export interface KnowledgeChunk {
  id: string
  chunk_index: number
  document: string
  char_count: number
  metadata: Record<string, unknown>
  _hit?: boolean
  _score?: number
}

/**
 * 获取知识的向量分块列表（chunk 级别视图）
 */
export function getKnowledgeChunks(id: number): Promise<{ chunks: KnowledgeChunk[]; total: number }> {
  return get<{ chunks: KnowledgeChunk[]; total: number }>(`/knowledge/${id}/chunks`)
}

/**
 * chunk 检索测试：输入 query，返回命中的 chunk 及得分
 */
export function testChunkRetrieval(id: number, query: string, topK: number = 5): Promise<{ hits: Array<{ id: string; chunk_index: number; score: number; document: string }>; total: number }> {
  return post<{ hits: Array<{ id: string; chunk_index: number; score: number; document: string }>; total: number }>(`/knowledge/${id}/test-retrieval`, { query, top_k: topK })
}

/**
 * 重建单条知识的向量索引
 */
export function rebuildSingleIndex(id: number): Promise<{ success: boolean }> {
  return post<{ success: boolean }>(`/knowledge/${id}/rebuild-index`, {})
}

/**
 * 获取下载附件的 URL
 */
export function getDownloadUrl(knowledgeId: number, docId: number): string {
  return `/api/knowledge/${knowledgeId}/documents/${docId}/download`
}
