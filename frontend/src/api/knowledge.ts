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
export function uploadKnowledgeFiles(files: File[]): Promise<ApiResponse> {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
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
 * 获取下载附件的 URL
 */
export function getDownloadUrl(knowledgeId: number, docId: number): string {
  return `/api/knowledge/${knowledgeId}/documents/${docId}/download`
}
