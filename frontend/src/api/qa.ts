import { get, post, del } from './request'
import type { QAHistory, PaginatedData } from '@/types'

/**
 * 智能问答（SSE流式）
 * 由于需要POST，使用 fetch + ReadableStream
 */
export async function askQuestionStream(
  question: string,
  options: {
    use_cache?: boolean
    history?: { role: string; content: string }[]
    onMessage?: (chunk: string, fullText: string) => void
    onDone?: (data: { history_id?: number; sources?: unknown[]; tokens?: number; skill_name?: string; degraded?: boolean; low_confidence?: boolean }) => void
    onError?: (error: Error) => void
    signal?: AbortSignal
  } = {}
): Promise<void> {
  const { use_cache = true, history, onMessage, onDone, onError, signal } = options

  try {
    const response = await fetch('/api/qa/ask', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream'
      },
      body: JSON.stringify({ question, use_cache, history: history || [] }),
      signal
    })

    if (!response.ok) {
      throw new Error(`请求失败: ${response.status}`)
    }

    if (!response.body) {
      throw new Error('响应体为空')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let fullText = ''
    const metaData: { history_id?: number; sources?: unknown[]; tokens?: number; skill_name?: string; degraded?: boolean; low_confidence?: boolean } = {}

    while (true) {
      const { done, value } = await reader.read()
      if (done) {
        break
      }
      buffer += decoder.decode(value, { stream: true })

      // 按 SSE 事件分割（双换行）
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue

        // 处理 data: 前缀
        if (trimmed.startsWith('data:')) {
          const dataStr = trimmed.slice(5).trim()
          if (!dataStr || dataStr === '[DONE]') {
            continue
          }
          try {
            const data = JSON.parse(dataStr)
            // 不同的事件结构兼容
            if (data.type === 'token' || data.type === 'delta' || data.token) {
              const chunk = data.token || data.content || data.delta || ''
              if (chunk) {
                fullText += chunk
                onMessage?.(chunk, fullText)
              }
            } else if (data.type === 'meta' || data.type === 'done') {
              if (data.history_id !== undefined) metaData.history_id = data.history_id
              if (data.sources) metaData.sources = data.sources
              if (data.total_tokens !== undefined) metaData.tokens = data.total_tokens
              if (data.token_input !== undefined && data.token_output !== undefined) {
                metaData.tokens = (data.token_input || 0) + (data.token_output || 0)
              }
              if (data.skill_name) metaData.skill_name = data.skill_name
              if (data.degraded !== undefined) metaData.degraded = data.degraded
              if (data.low_confidence !== undefined) metaData.low_confidence = data.low_confidence
              if (data.content) {
                fullText += data.content
                onMessage?.(data.content, fullText)
              }
            } else if (typeof data === 'string') {
              fullText += data
              onMessage?.(data, fullText)
            } else if (data.content) {
              fullText += data.content
              onMessage?.(data.content, fullText)
            }
          } catch {
            // 非 JSON，作为纯文本处理
            fullText += dataStr
            onMessage?.(dataStr, fullText)
          }
        } else if (trimmed.startsWith('event:')) {
          // 事件类型标记，忽略
          continue
        }
      }
    }

    onDone?.(metaData)
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      return
    }
    onError?.(error as Error)
  }
}

/**
 * 答案反馈
 */
export function submitFeedback(
  historyId: number,
  feedback: 'useful' | 'useless'
): Promise<void> {
  return post<void>('/qa/feedback', { history_id: historyId, feedback })
}

/**
 * 追问推荐
 */
export function getSuggestions(question: string): Promise<string[]> {
  return get<string[]>('/qa/suggestions', { question })
}

/**
 * 问答历史
 */
export function getQAHistory(params: {
  page?: number
  page_size?: number
  keyword?: string
}): Promise<PaginatedData<QAHistory>> {
  return get<PaginatedData<QAHistory>>('/qa/history', params)
}

/**
 * 历史详情
 */
export function getQAHistoryDetail(id: number): Promise<QAHistory> {
  return get<QAHistory>(`/qa/history/${id}`)
}

/**
 * 删除历史
 */
export function deleteQAHistory(id: number): Promise<void> {
  return del<void>(`/qa/history/${id}`)
}
