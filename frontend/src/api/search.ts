import { get } from './request'
import type { SearchResult, SearchHistory, SearchQuery, PaginatedData } from '@/types'

/**
 * 语义搜索
 */
export function semanticSearch(
  params: SearchQuery
): Promise<PaginatedData<SearchResult>> {
  return get<PaginatedData<SearchResult>>('/search/semantic', params)
}

/**
 * 关键词搜索
 */
export function keywordSearch(
  params: SearchQuery
): Promise<PaginatedData<SearchResult>> {
  return get<PaginatedData<SearchResult>>('/search/keyword', params)
}

/**
 * 搜索历史
 */
export function getSearchHistory(): Promise<SearchHistory[]> {
  return get<SearchHistory[]>('/search/history')
}
