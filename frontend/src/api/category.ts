import { get, post, put, del } from './request'
import type { Category, Tag } from '@/types'

/* ==================== 分类 API ==================== */

/**
 * 获取分类树
 */
export function getCategoryTree(): Promise<Category[]> {
  return get<Category[]>('/categories')
}

/**
 * 创建分类
 */
export function createCategory(data: {
  name: string
  description?: string
  parent_id?: number | null
}): Promise<Category> {
  return post<Category>('/categories', data)
}

/**
 * 更新分类
 */
export function updateCategory(
  id: number,
  data: Partial<{ name: string; description: string; parent_id: number | null }>
): Promise<Category> {
  return put<Category>(`/categories/${id}`, data)
}

/**
 * 删除分类
 */
export function deleteCategory(id: number): Promise<void> {
  return del<void>(`/categories/${id}`)
}

/* ==================== 标签 API ==================== */

/**
 * 获取标签列表
 */
export function getTagList(): Promise<Tag[]> {
  return get<Tag[]>('/tags')
}

/**
 * 创建标签
 */
export function createTag(data: { name: string; color?: string }): Promise<Tag> {
  return post<Tag>('/tags', data)
}

/**
 * 删除标签
 */
export function deleteTag(id: number): Promise<void> {
  return del<void>(`/tags/${id}`)
}
