import { get, post, put, del } from './request'
import type { ModelConfig, ModelStatus, ModelTestResult, ModelType } from '@/types'

/**
 * 获取模型配置列表
 */
export function getModelList(): Promise<ModelConfig[]> {
  return get<ModelConfig[]>('/models')
}

/**
 * 获取模型详情
 */
export function getModelDetail(id: number): Promise<ModelConfig> {
  return get<ModelConfig>(`/models/${id}`)
}

/**
 * 新增模型配置
 */
export function createModel(data: {
  name: string
  type: ModelType
  api_url: string
  api_key: string
  model_name: string
}): Promise<ModelConfig> {
  return post<ModelConfig>('/models', data)
}

/**
 * 更新模型配置
 */
export function updateModel(
  id: number,
  data: Partial<{
    name: string
    type: ModelType
    api_url: string
    api_key: string
    model_name: string
  }>
): Promise<ModelConfig> {
  return put<ModelConfig>(`/models/${id}`, data)
}

/**
 * 删除模型配置
 */
export function deleteModel(id: number): Promise<void> {
  return del<void>(`/models/${id}`)
}

/**
 * 启用模型
 */
export function activateModel(id: number): Promise<ModelConfig> {
  return put<ModelConfig>(`/models/${id}/activate`)
}

/**
 * 测试连通性
 */
export function testModel(id: number): Promise<ModelTestResult> {
  return post<ModelTestResult>(`/models/${id}/test`)
}

/**
 * 当前启用模型状态
 */
export function getModelStatus(): Promise<ModelStatus> {
  return get<ModelStatus>('/models/status')
}
