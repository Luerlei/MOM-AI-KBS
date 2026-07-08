import { get, post, put, del, upload } from './request'
import type { Dataset, DatasetQuery, DatasetForm, DatasetPreview, ImportResult, PaginatedData } from '@/types'

/**
 * 数据集列表
 */
export function getDatasetList(params: DatasetQuery): Promise<PaginatedData<Dataset>> {
  return get<PaginatedData<Dataset>>('/datasets', params)
}

/**
 * 数据集详情
 */
export function getDatasetDetail(id: number): Promise<Dataset> {
  return get<Dataset>(`/datasets/${id}`)
}

/**
 * 预览数据集
 */
export function previewDataset(id: number, limit: number = 50): Promise<DatasetPreview> {
  return get<DatasetPreview>(`/datasets/${id}/preview`, { limit })
}

/**
 * 创建数据集
 */
export function createDataset(data: DatasetForm): Promise<Dataset> {
  return post<Dataset>('/datasets', data)
}

/**
 * 更新数据集
 */
export function updateDataset(id: number, data: Partial<DatasetForm>): Promise<Dataset> {
  return put<Dataset>(`/datasets/${id}`, data)
}

/**
 * 删除数据集
 */
export function deleteDataset(id: number): Promise<void> {
  return del<void>(`/datasets/${id}`)
}

/**
 * 导入数据集（Excel/CSV）
 */
export function importDataset(
  file: File,
  options: { name?: string; frequency?: string; unit?: string; description?: string }
): Promise<ImportResult> {
  const formData = new FormData()
  formData.append('file', file)
  if (options.name) formData.append('name', options.name)
  if (options.frequency) formData.append('frequency', options.frequency)
  if (options.unit) formData.append('unit', options.unit)
  if (options.description) formData.append('description', options.description)
  return upload<ImportResult>('/datasets/import', formData, { timeout: 60000 })
}

/**
 * 下载模板
 */
export function downloadTemplateUrl(format: 'excel' | 'csv' = 'excel'): string {
  return `/api/datasets/template?format=${format}`
}

/**
 * 导出数据集
 */
export function exportDatasetUrl(
  id: number,
  format: 'excel' | 'csv' = 'excel',
  withForecast: boolean = false
): string {
  return `/api/datasets/${id}/export?format=${format}&with_forecast=${withForecast}`
}
