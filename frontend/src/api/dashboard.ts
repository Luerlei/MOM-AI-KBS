import { get } from './request'
import type {
  DashboardStats,
  DashboardRecentQA,
  TokenStatsSummary,
  TokenStatsQuery,
  TokenTrendPoint,
  TokenDimensionStat,
  CallLog,
  ModelCallLog,
  PaginatedData
} from '@/types'

/**
 * 仪表盘统计
 */
export function getDashboardStats(timeRange?: string): Promise<DashboardStats> {
  return get<DashboardStats>('/dashboard/stats', timeRange ? { time_range: timeRange } : undefined)
}

/**
 * 最近问答
 */
export function getRecentQA(timeRange?: string): Promise<DashboardRecentQA[]> {
  return get<DashboardRecentQA[]>('/dashboard/recent-qa', timeRange ? { time_range: timeRange } : undefined)
}

/**
 * Token 统计汇总（包含趋势、分布、缓存，后端单接口返回全部）
 */
export function getTokenStatsSummary(
  params: TokenStatsQuery
): Promise<TokenStatsSummary> {
  return get<TokenStatsSummary>('/token-stats', params)
}

/**
 * 健康检查
 */
export function healthCheck(): Promise<{ status: string }> {
  return get<{ status: string }>('/health', undefined, { baseURL: '' })
}

/**
 * 将后端趋势数据项映射为前端类型（calls -> call_count）
 */
export function mapTrend(raw: Array<Record<string, unknown>>): TokenTrendPoint[] {
  return (raw || []).map((r) => ({
    date: String(r.date ?? ''),
    total_tokens: Number(r.total_tokens ?? 0),
    input_tokens: Number(r.input_tokens ?? 0),
    output_tokens: Number(r.output_tokens ?? 0),
    call_count: Number(r.calls ?? r.call_count ?? 0)
  }))
}

/**
 * 将后端按维度分布数据映射为前端类型
 */
export function mapDimension(
  raw: Array<Record<string, unknown>>,
  nameField: string
): TokenDimensionStat[] {
  return (raw || []).map((r) => ({
    name: String(r[nameField] ?? r.name ?? '未知'),
    total_tokens: Number(r.total_tokens ?? 0),
    call_count: Number(r.calls ?? r.call_count ?? 0)
  }))
}

/**
 * 获取调用日志列表
 */
export function getCallLogs(params: {
  time_range?: string
  start_date?: string
  end_date?: string
  skill_id?: number
  model_name?: string
  page?: number
  page_size?: number
}): Promise<PaginatedData<CallLog>> {
  return get<PaginatedData<CallLog>>('/token-stats/call-logs', params)
}

/**
 * 获取模型调用日志列表（基于 TokenUsage 表，所有模型调用）
 */
export function getModelCallLogs(params: {
  time_range?: string
  start_date?: string
  end_date?: string
  call_type?: string
  model_name?: string
  skill_id?: number
  page?: number
  page_size?: number
}): Promise<PaginatedData<ModelCallLog>> {
  return get<PaginatedData<ModelCallLog>>('/token-stats/model-call-logs', params)
}
