import { get, post, put, del } from './request'
import type { SkillOption } from '@/types'

/**
 * 获取分类/功能选项列表
 * @param type category=模块维度, function=功能维度
 */
export function getSkillOptions(type: 'category' | 'function'): Promise<SkillOption[]> {
  return get<SkillOption[]>('/skill-options', { type })
}

/**
 * 创建选项
 */
export function createSkillOption(data: {
  type: 'category' | 'function'
  name: string
  description?: string
  sort_order?: number
  color?: string
}): Promise<SkillOption> {
  return post<SkillOption>('/skill-options', data)
}

/**
 * 更新选项
 */
export function updateSkillOption(
  id: number,
  data: Partial<{ name: string; description: string; sort_order: number; color: string }>
): Promise<SkillOption> {
  return put<SkillOption>(`/skill-options/${id}`, data)
}

/**
 * 删除选项
 */
export function deleteSkillOption(id: number): Promise<void> {
  return del<void>(`/skill-options/${id}`)
}
