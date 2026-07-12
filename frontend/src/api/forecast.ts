import { get, post } from './request'
import type {
  ForecastPredictRequest,
  ForecastPredictResponse,
  ForecastTask,
  TrendAnalysis,
  PaginatedData,
  CrossValidationRequest,
  CrossValidationResponse,
  ModelCompareResponse,
  DecompositionResponse,
  StatisticalForecastRequest,
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
 * 按 task_id 获取特定预测任务结果（用于历史任务查看）
 */
export function getForecastResultByTask(taskId: number): Promise<{ task: ForecastTask; result: any }> {
  return get<any>(`/forecast/result/${taskId}`)
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

/**
 * 交叉验证（多次回测取平均）
 */
export function runCrossValidation(data: CrossValidationRequest): Promise<CrossValidationResponse> {
  return post<CrossValidationResponse>('/forecast/cross-validation', data, { timeout: 600000 })
}

/**
 * 多模型对比回测
 */
export function compareModels(data: {
  dataset_id: number
  horizon?: number
  start_index?: number | null
}): Promise<ModelCompareResponse> {
  return post<ModelCompareResponse>('/forecast/compare-models', data, { timeout: 600000 })
}

/**
 * STL 季节性分解
 */
export function getDecomposition(datasetId: number): Promise<DecompositionResponse> {
  return get<DecompositionResponse>(`/forecast/decomposition/${datasetId}`)
}

/**
 * 统计模型预测（ARIMA/ETS/Theta/Prophet）
 */
export function runStatisticalForecast(data: StatisticalForecastRequest): Promise<ForecastPredictResponse> {
  return post<ForecastPredictResponse>('/forecast/statistical-forecast', data, { timeout: 120000 })
}

/**
 * 自动模型选择（B1）
 */
export function autoSelectModel(data: {
  dataset_id: number
  horizon?: number
  n_splits?: number
  strategy?: string
}): Promise<any> {
  return post<any>('/forecast/auto-select', data, { timeout: 600000 })
}

/**
 * 集成预测（B2）
 */
export function ensembleForecast(data: {
  dataset_id: number
  horizon: number
  start_index?: number | null
  models?: string[]
  strategy?: 'weighted_avg' | 'median' | 'simple_avg'
}): Promise<any> {
  return post<any>('/forecast/ensemble', data, { timeout: 300000 })
}

/**
 * 高级特征工程（B3）
 */
export function getAdvancedFeatures(datasetId: number): Promise<any> {
  return get<any>(`/forecast/features/${datasetId}`)
}

/**
 * 统计异常检测（B4）
 */
export function detectAnomalies(data: {
  dataset_id: number
  method?: 'stl_residual' | 'isolation_forest' | 'change_point'
  contamination?: number
}): Promise<any> {
  return post<any>('/forecast/anomaly-detection', data)
}

/**
 * 超参优化（B5）
 */
export function optimizeParams(data: {
  dataset_id: number
  model_type: 'ets' | 'arima' | 'prophet' | 'theta'
  horizon?: number
  n_trials?: number
}): Promise<any> {
  return post<any>('/forecast/optimize-params', data, { timeout: 300000 })
}
