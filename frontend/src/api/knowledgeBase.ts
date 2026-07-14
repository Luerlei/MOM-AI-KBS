import { get, post, put, del, upload } from './request'
import type { KnowledgeBase, KnowledgeBaseForm, PaginatedData, Knowledge } from '@/types'

/**
 * 知识库列表
 */
export function getKnowledgeBaseList(params: {
  keyword?: string
  page?: number
  page_size?: number
}): Promise<PaginatedData<KnowledgeBase>> {
  return get<PaginatedData<KnowledgeBase>>('/knowledge-bases', params)
}

/**
 * 知识库详情
 */
export function getKnowledgeBaseDetail(id: number): Promise<KnowledgeBase> {
  return get<KnowledgeBase>(`/knowledge-bases/${id}`)
}

/**
 * 创建知识库
 */
export function createKnowledgeBase(data: KnowledgeBaseForm): Promise<KnowledgeBase> {
  return post<KnowledgeBase>('/knowledge-bases', data)
}

/**
 * 更新知识库
 */
export function updateKnowledgeBase(id: number, data: Partial<KnowledgeBaseForm>): Promise<KnowledgeBase> {
  return put<KnowledgeBase>(`/knowledge-bases/${id}`, data)
}

/**
 * 删除知识库
 */
export function deleteKnowledgeBase(id: number): Promise<void> {
  return del<void>(`/knowledge-bases/${id}`)
}

/**
 * 知识库下的资料列表
 */
export function getKnowledgeBaseDocuments(
  id: number,
  params: { page?: number; page_size?: number; parse_status?: string; keyword?: string }
): Promise<PaginatedData<Knowledge>> {
  return get<PaginatedData<Knowledge>>(`/knowledge-bases/${id}/documents`, params)
}

/**
 * 上传资料到知识库（支持文件夹）
 */
export function uploadToKnowledgeBase(
  id: number,
  files: File[],
  options: {
    category_id?: number
    tag_ids?: number[]
    auto_tag?: boolean
    parse_immediately?: boolean
  } = {}
): Promise<{ created: number; skipped_duplicate: string[]; failed: { filename: string; reason: string }[] }> {
  const formData = new FormData()
  for (const f of files) {
    formData.append('files', f)
  }
  if (options.category_id) formData.append('category_id', String(options.category_id))
  if (options.tag_ids?.length) formData.append('tag_ids', options.tag_ids.join(','))
  if (options.auto_tag) formData.append('auto_tag', 'true')
  if (options.parse_immediately !== undefined) {
    formData.append('parse_immediately', String(options.parse_immediately))
  }
  return upload<{ created: number; skipped_duplicate: string[]; failed: { filename: string; reason: string }[] }>(
    `/knowledge-bases/${id}/upload`,
    formData
  )
}

/**
 * 手动解析单个资料
 */
export function parseDocument(kbId: number, kid: number): Promise<void> {
  return post<void>(`/knowledge-bases/${kbId}/documents/${kid}/parse`)
}

/**
 * 批量解析所有待解析资料
 */
export function parseAllDocuments(kbId: number): Promise<{ total: number; success: number; failed: number }> {
  return post<{ total: number; success: number; failed: number }>(`/knowledge-bases/${kbId}/parse-all`)
}
