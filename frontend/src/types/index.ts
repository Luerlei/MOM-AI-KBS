/**
 * 统一API响应格式
 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

/**
 * 分页响应数据
 */
export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

/**
 * 知识内容类型
 */
export type ContentType = 'markdown' | 'text' | 'html'

/**
 * 知识状态
 */
export type KnowledgeStatus = 'draft' | 'published' | 'archived'

/**
 * 知识条目附件
 */
export interface KnowledgeDocument {
  id: number
  filename: string
  file_type: string
  file_size: number
}

/**
 * 知识条目
 */
export interface Knowledge {
  id: number
  title: string
  content: string
  content_type: ContentType
  category_id: number | null
  category_name?: string
  tag_ids: number[]
  tags?: Tag[]
  source_type?: string
  source_file?: string
  status?: KnowledgeStatus
  vector_indexed?: boolean
  documents?: KnowledgeDocument[]
  document_count?: number
  created_at: string
  updated_at: string
  created_by?: string
}

/**
 * 知识列表查询参数
 */
export interface KnowledgeQuery {
  page?: number
  page_size?: number
  category_id?: number
  tag_ids?: number[]
  keyword?: string
  status?: KnowledgeStatus
}

/**
 * 知识创建/更新请求
 */
export interface KnowledgeForm {
  title: string
  content: string
  content_type: ContentType
  category_id: number | null
  tag_ids: number[]
  status?: KnowledgeStatus
}

/**
 * 批量操作类型
 */
export type BatchAction = 'delete' | 'add_tags' | 'set_category' | 'remove_tags' | 'set_status'

/**
 * 批量操作请求
 */
export interface KnowledgeBatchRequest {
  ids: number[]
  action: BatchAction
  tag_ids?: number[]
  category_id?: number
  status?: KnowledgeStatus
}

/**
 * 分类
 */
export interface Category {
  id: number
  name: string
  description?: string
  parent_id: number | null
  sort_order?: number
  children?: Category[]
  knowledge_count?: number
  created_at?: string
}

/**
 * 标签
 */
export interface Tag {
  id: number
  name: string
  color?: string
  knowledge_count?: number
  created_at?: string
}

/**
 * Skill 模块维度（改为字符串，支持自定义分类）
 */
export type SkillCategory = string

/**
 * Skill 功能维度（改为字符串，支持自定义功能）
 */
export type SkillFunction = string

/**
 * Skill 触发模式
 */
export type TriggerMode = 'keyword' | 'regex' | 'semantic'

/**
 * Skill 配置
 */
export interface Skill {
  id: number
  name: string
  description: string
  category: SkillCategory
  function: SkillFunction
  trigger_keywords: string[]
  trigger_patterns: string[]
  trigger_mode?: TriggerMode
  knowledge_scope?: { category_ids?: number[]; tag_ids?: number[] }
  knowledge_categories?: number[]
  knowledge_tags?: number[]
  prompt_template: string
  enabled: boolean
  is_default?: boolean
  enable_query_rewrite?: boolean
  context_turns?: number
  created_at: string
  updated_at: string
}

/**
 * Skill 分类/功能选项（可自定义）
 */
export interface SkillOption {
  id: number
  type: 'category' | 'function'
  name: string
  description: string
  sort_order: number
  color: string
  created_at: string
}

/**
 * Skill 模板
 */
export interface SkillTemplate {
  id: string
  name: string
  description: string
  category: SkillCategory
  function: SkillFunction
  prompt_template: string
}

/**
 * Skill 测试各 Skill 得分明细
 */
export interface SkillTestScore {
  skill_id: number
  skill_name: string
  keyword_hits: number
  semantic_score: number
}

/**
 * Skill 测试结果
 */
export interface SkillTestResult {
  matched_skill: Skill | null
  match_type: string  // keyword / semantic / default
  score: number
  all_scores: SkillTestScore[]
}

/**
 * 模型类型
 */
export type ModelType = 'LLM' | 'Embedding' | 'Forecast' | 'Rerank' | 'OCR' | 'VLM'

/**
 * 模型配置
 */
export interface ModelConfig {
  id: number
  name: string
  type: ModelType
  api_url: string
  api_key_masked: string
  model_name: string
  is_active: boolean
  input_price: number
  output_price: number
  created_at: string
  updated_at: string
}

/**
 * 模型状态
 */
export interface ModelStatusItem {
  id: number | null
  name: string
  model_name: string
  source?: string
}

export interface ModelStatus {
  llm: ModelStatusItem | null
  embedding: ModelStatusItem | null
  forecast: ModelStatusItem | null
  rerank?: ModelStatusItem | null
  ocr?: ModelStatusItem | null
  vlm?: ModelStatusItem | null
}

/**
 * 模型测试结果
 */
export interface ModelTestResult {
  success: boolean
  message: string
  latency?: number
}

/**
 * 问答历史
 */
export interface QAHistory {
  id: number
  question: string
  answer: string
  skill_id?: number
  skill_name?: string
  sources?: QAReference[]
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  feedback?: 'useful' | 'useless' | null
  model_name?: string
  created_at: string
}

/**
 * 答案引用来源
 */
export interface QAReference {
  knowledge_id: number
  title: string
  score?: number
  snippet?: string
  chunk_id?: string
  page_number?: number
}

/**
 * 搜索结果
 */
export interface SearchResult {
  id: number
  knowledge_id: number
  title: string
  content: string
  snippet: string
  highlight?: string
  category_id?: number
  category_name?: string
  tags?: Tag[]
  tag_names?: string[]
  score?: number
  created_at?: string
}

/**
 * 搜索查询参数
 */
export interface SearchQuery {
  query: string
  category_id?: number
  tag_ids?: number[]
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}

/**
 * 搜索历史
 */
export interface SearchHistory {
  id: number
  query: string
  search_type: 'semantic' | 'keyword'
  result_count: number
  created_at: string
}

/**
 * Token 使用统计
 */
export interface TokenUsage {
  total_tokens: number
  input_tokens: number
  output_tokens: number
  call_count: number
}

/**
 * 缓存命中统计
 */
export interface CacheStats {
  total_qa: number
  cache_hits: number
  cache_hit_rate: number
  tokens_saved: number
}

/**
 * 单模型成本估算明细
 */
export interface CostEstimateItem {
  model_name: string
  input_tokens: number
  output_tokens: number
  cost: number
}

/**
 * Token 成本估算
 */
export interface CostEstimate {
  total_cost: number
  by_model: CostEstimateItem[]
}

/**
 * Token 统计完整汇总（包含趋势、分布、缓存、成本）
 */
export interface TokenStatsSummary {
  total_tokens: number
  input_tokens: number
  output_tokens: number
  call_count: number
  trend: TokenTrendPoint[]
  by_skill: TokenDimensionStat[]
  by_call_type: TokenDimensionStat[]
  cache_stats: CacheStats
  cost_estimate?: CostEstimate
}

/**
 * Token 统计查询参数
 */
export interface TokenStatsQuery {
  time_range: 'today' | 'week' | 'month' | 'custom'
  start_date?: string
  end_date?: string
  skill_id?: number
  model_name?: string
}

/**
 * Token 趋势数据点
 */
export interface TokenTrendPoint {
  date: string
  total_tokens: number
  input_tokens: number
  output_tokens: number
  call_count: number
}

/**
 * Token 按维度统计
 */
export interface TokenDimensionStat {
  name: string
  total_tokens: number
  call_count: number
}

/**
 * 仪表盘统计数据
 */
export interface DashboardStats {
  knowledge_count: number
  skill_count: number
  today_qa_count: number
  document_count: number
  model_count: number
}

/**
 * 调用日志条目
 */
export interface CallLog {
  id: number
  question: string
  skill_name: string
  model_name: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cache_hit: boolean
  created_at: string
}

/**
 * 模型调用日志（基于 TokenUsage 表，记录所有模型调用）
 */
export interface ModelCallLog {
  id: number
  call_type: string
  model_name: string
  skill_id: number | null
  skill_name: string
  qa_history_id: number | null
  question: string
  input_tokens: number
  output_tokens: number
  total_tokens: number
  duration_ms: number
  source: string
  created_at: string
}

/**
 * 仪表盘最近问答
 */
export interface DashboardRecentQA {
  id: number
  question: string
  answer: string
  skill_name?: string
  created_at: string
}

/**
 * 文件上传状态
 */
export interface UploadFileItem {
  uid: string
  name: string
  size: number
  status: 'pending' | 'uploading' | 'done' | 'error'
  percent?: number
  response?: unknown
  originFileObj?: File
}

/**
 * 数据频率
 */
export type DataFrequency = 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly' | 'hourly' | 'other'

/**
 * 时序数据点
 */
export interface TimeSeriesPoint {
  time: string
  value: number
  label?: string
}

/**
 * 数据集
 */
export interface Dataset {
  id: number
  name: string
  description: string
  frequency: DataFrequency
  unit: string
  point_count: number
  source: string
  source_file: string
  created_at: string
  updated_at: string
  series_data?: TimeSeriesPoint[]
}

/**
 * 数据集查询参数
 */
export interface DatasetQuery {
  keyword?: string
  frequency?: DataFrequency
  page?: number
  page_size?: number
}

/**
 * 数据集创建/更新请求
 */
export interface DatasetForm {
  name: string
  description?: string
  frequency?: DataFrequency
  unit?: string
  series_data?: TimeSeriesPoint[]
}

/**
 * 数据集预览统计
 */
export interface DatasetPreview {
  dataset: Dataset
  points: TimeSeriesPoint[]
  stats: {
    count: number
    min: number
    max: number
    avg: number
    first: number
    last: number
  }
}

/**
 * 导入结果
 */
export interface ImportResult {
  dataset: Dataset
  warnings: string[]
}

/**
 * 预测任务状态
 */
export type ForecastTaskStatus = 'pending' | 'running' | 'success' | 'failed'

/**
 * 预测任务
 */
export interface ForecastTask {
  id: number
  dataset_id: number
  model_config_id: number | null
  model_name: string
  horizon: number
  start_index: number | null
  status: ForecastTaskStatus
  error_message: string
  duration_ms: number
  created_at: string
  completed_at: string
}

/**
 * 预测结果
 */
export interface ForecastResult {
  id: number
  task_id: number
  dataset_id: number
  forecasts: number[]
  quantiles: Record<string, number[]>
  future_times: string[]
  actuals: number[]
  metrics: Record<string, number>
  model_name: string
  analysis: string
  created_at: string
}

/**
 * 预测执行请求
 */
export interface ForecastPredictRequest {
  dataset_id: number
  horizon: number
  quantiles?: number[]
  start_index?: number | null
  skip_analysis?: boolean
}

/**
 * 预测执行响应
 */
export interface ForecastPredictResponse {
  task: ForecastTask
  result: ForecastResult
}

/**
 * 交叉验证请求
 */
export interface CrossValidationRequest {
  dataset_id: number
  n_splits?: number
  horizon?: number
  strategy?: 'expanding' | 'sliding'
  skip_analysis?: boolean
}

/**
 * 交叉验证单次切分结果
 */
export interface CVSplitResult {
  split_idx: number
  start_index: number
  metrics: Record<string, number | object>
  duration_ms: number
  status: 'success' | 'failed'
  error?: string
}

/**
 * 交叉验证响应
 */
export interface CrossValidationResponse {
  splits: CVSplitResult[]
  avg_metrics: Record<string, number | object>
  std_metrics: Record<string, number | object>
  model_name: string
  strategy: string
  n_splits: number
  horizon: number
}

/**
 * 多模型对比单模型结果
 */
export interface ModelCompareItem {
  model_name: string
  model_config_id: number
  model_identifier: string
  metrics: Record<string, number | object>
  duration_ms: number
  status: 'success' | 'failed'
  error?: string
}

/**
 * 多模型对比响应
 */
export interface ModelCompareResponse {
  models: ModelCompareItem[]
  best_model: {
    model_name: string
    metric_name: string
    metric_value: number
    rmae: number
  } | null
  baselines: {
    naive_mae: number
    seasonal_naive_mae: number
    naive_forecasts: number[]
    seasonal_naive_forecasts: number[]
  }
  start_index: number
  actual_count: number
  horizon: number
}

/**
 * STL 季节性分解响应
 */
export interface DecompositionResponse {
  success: boolean
  message?: string
  times?: string[]
  original?: number[]
  trend?: number[]
  seasonal?: number[]
  residual?: number[]
  seasonal_strength?: number
  seasonal_amplitude?: number
  frequency?: string
  preprocess?: {
    missing_filled: number
    outliers_fixed: number
  }
}

/**
 * 统计模型预测请求
 */
export interface StatisticalForecastRequest {
  dataset_id: number
  horizon: number
  model_type: 'arima' | 'ets' | 'theta' | 'prophet'
  start_index?: number | null
  use_covariates?: boolean
}

/**
 * 协变量类型
 */
export type CovariateType = 'continuous' | 'binary' | 'categorical'

/**
 * 协变量来源类型
 */
export type CovariateSourceType = 'manual' | 'auto' | 'template'

/**
 * 协变量值点（时间-值对）
 */
export interface CovariateValuePoint {
  time: string
  value: number
}

/**
 * 数据集协变量（外生变量，用于 ARIMAX 等支持 exog 的模型）
 */
export interface Covariate {
  id: number
  dataset_id: number
  name: string
  code: string
  type: CovariateType
  source_type: CovariateSourceType
  values: CovariateValuePoint[]
  description: string
  created_at: string
  updated_at: string
}

/**
 * 协变量创建/更新请求
 */
export interface CovariateForm {
  name: string
  code: string
  type?: CovariateType
  source_type?: CovariateSourceType
  values?: CovariateValuePoint[]
  description?: string
}

/**
 * 协变量对齐预览（用于检查时间对齐效果）
 */
export interface CovariatePreview {
  columns: { title: string; key: string }[]
  rows: Record<string, string | number>[]
  covariate_count: number
  point_count: number
}

/**
 * 自动生成协变量响应
 */
export interface AutoGenerateCovariatesResult {
  generated: string[]
  skipped: string[]
  total: number
}

/**
 * 趋势统计数据
 */
export interface TrendStats {
  count: number
  min: number
  max: number
  avg: number
  first: number
  last: number
  trend_direction: 'up' | 'down' | 'flat'
  trend_strength: number
  growth_rate: number
  volatility: number
}

/**
 * 趋势分析聚合数据
 */
export interface TrendAnalysis {
  dataset: {
    id: number
    name: string
    description: string
    frequency: DataFrequency
    unit: string
    point_count: number
  }
  history: TimeSeriesPoint[]
  forecast: {
    forecasts: number[]
    quantiles: Record<string, number[]>
    future_times: string[]
    actuals: number[]
    metrics: Record<string, number>
    model_name: string
    duration_ms: number
    analysis: string
    task_id: number
    start_index: number | null
    horizon: number
    is_backtest: boolean
  } | null
  analysis: {
    stats: TrendStats
    summary: string
  }
}
