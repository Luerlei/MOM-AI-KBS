import { get, post, put, del } from './request'
import type {
  Skill,
  SkillTemplate,
  SkillTestResult,
  SkillCategory,
  SkillFunction
} from '@/types'

/**
 * 获取 Skill 列表
 */
export function getSkillList(params?: {
  category?: SkillCategory
  function?: SkillFunction
  enabled?: boolean
}): Promise<Skill[]> {
  return get<Skill[]>('/skills', params)
}

/**
 * 获取 Skill 模板列表
 */
export function getSkillTemplates(): Promise<SkillTemplate[]> {
  return get<SkillTemplate[]>('/skills/templates')
}

/**
 * 获取 Skill 详情
 */
export function getSkillDetail(id: number): Promise<Skill> {
  return get<Skill>(`/skills/${id}`)
}

/**
 * 创建 Skill
 */
export function createSkill(
  data: Partial<Skill>
): Promise<Skill> {
  return post<Skill>('/skills', data)
}

/**
 * 从模板创建 Skill
 */
export function createSkillFromTemplate(templateId: string): Promise<Skill> {
  return post<Skill>('/skills/from-template', { template_id: templateId })
}

/**
 * 更新 Skill
 */
export function updateSkill(id: number, data: Partial<Skill>): Promise<Skill> {
  return put<Skill>(`/skills/${id}`, data)
}

/**
 * 删除 Skill
 */
export function deleteSkill(id: number): Promise<void> {
  return del<void>(`/skills/${id}`)
}

/**
 * 启用/禁用 Skill
 */
export function toggleSkill(id: number): Promise<Skill> {
  return put<Skill>(`/skills/${id}/toggle`)
}

/**
 * 测试 Skill 路由
 */
export function testSkill(id: number, question: string): Promise<SkillTestResult> {
  return post<SkillTestResult>(`/skills/${id}/test`, { question })
}
