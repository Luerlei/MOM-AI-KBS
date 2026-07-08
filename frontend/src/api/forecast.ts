import { get, post } from './request'
import type {
  ForecastPredictRequest,
  ForecastPredictResponse,
  ForecastTask,
  TrendAnalysis,
  PaginatedData,
} from '@/types'

/**
 * 执行预测
 */
export function runForecast(data: ForecastPredictRequest): Promise<ForecastPredictResponse> {
  return post<ForecastPredictResponse>('/forecast/predict', data, { timeout: 300000 })
}

/**
 * 预测任务历史
 */
export function getForecastTasks(
  datasetId?: number,
  page: number = 1,
  pageSize: number = 20
): Promise<PaginatedData<ForecastTask>> {
  return get<PaginatedData<ForecastTask>>('/forecast/tasks', {
    dataset_id: datasetId,
    page,
    page_size: pageSize,
  })
}

/**
 * 获取数据集最新预测结果
 */
export function getLatestForecastResult(datasetId: number): Promise<{ task: ForecastTask; result: any } | null> {
  return get<any>(`/forecast/results/${datasetId}`)
}

/**
 * 获取趋势分析聚合数据
 */
export function getTrendAnalysis(datasetId: number): Promise<TrendAnalysis> {
  return get<TrendAnalysis>(`/forecast/trend/${datasetId}`)
}

/**
 * 导出预测结果 URL
 */
export function exportForecastResultUrl(
  taskId: number,
  format: 'excel' | 'csv' = 'excel'
): string {
  return `/api/forecast/export/${taskId}?format=${format}`
}
