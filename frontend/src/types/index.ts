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
}

/**
 * 批量操作类型
 */
export type BatchAction = 'delete' | 'add_tags' | 'set_category' | 'remove_tags'

/**
 * 批量操作请求
 */
export interface KnowledgeBatchRequest {
  ids: number[]
  action: BatchAction
  tag_ids?: number[]
  category_id?: number
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
 * Skill 测试结果
 */
export interface SkillTestResult {
  matched: boolean
  skill_id?: number
  skill_name?: string
  confidence?: number
  reason?: string
}

/**
 * 模型类型
 */
export type ModelType = 'LLM' | 'Embedding'

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
}

/**
 * 搜索结果
 */
export interface SearchResult {
  id: number
  title: string
  content: string
  snippet: string
  highlight?: string
  category_id?: number
  category_name?: string
  tags?: Tag[]
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
 * Token 统计完整汇总（包含趋势、分布、缓存）
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
