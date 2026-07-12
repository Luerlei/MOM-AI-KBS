import { get, post, put, del } from './request'
import type { Covariate, CovariateForm, CovariatePreview, AutoGenerateCovariatesResult } from '@/types'

/**
 * 列出数据集的协变量
 */
export function listCovariates(datasetId: number): Promise<Covariate[]> {
  return get<Covariate[]>(`/datasets/${datasetId}/covariates`)
}

/**
 * 新增协变量
 */
export function createCovariate(datasetId: number, data: CovariateForm): Promise<Covariate> {
  return post<Covariate>(`/datasets/${datasetId}/covariates`, data)
}

/**
 * 修改协变量
 */
export function updateCovariate(covariateId: number, data: Partial<CovariateForm>): Promise<Covariate> {
  return put<Covariate>(`/covariates/${covariateId}`, data)
}

/**
 * 删除协变量
 */
export function deleteCovariate(covariateId: number): Promise<void> {
  return del<void>(`/covariates/${covariateId}`)
}

/**
 * 自动生成协变量（基于数据集频率生成 trend/节假日/周末/周期编码等）
 */
export function autoGenerateCovariates(datasetId: number, skipExisting: boolean = true): Promise<AutoGenerateCovariatesResult> {
  return post(`/datasets/${datasetId}/covariates/auto-generate`, { skip_existing: skipExisting })
}

/**
 * 预览协变量对齐后的矩阵（用于检查时间对齐效果）
 */
export function previewCovariates(datasetId: number): Promise<CovariatePreview> {
  return get<CovariatePreview>(`/datasets/${datasetId}/covariates/preview`)
}

/**
 * 获取数据集的未来时间标签（用于协变量未来值录入辅助）
 */
export function getFutureTimes(datasetId: number, horizon: number = 6): Promise<{ future_times: string[]; frequency: string }> {
  return get(`/datasets/${datasetId}/covariates/future-times`, { horizon })
}
