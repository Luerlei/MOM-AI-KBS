import { get, post, put, del } from './request'
import type { Conversation, ConversationForm, ConversationDetail, PaginatedData } from '@/types'

/**
 * 会话列表
 */
export function getConversationList(params: {
  keyword?: string
  page?: number
  page_size?: number
}): Promise<PaginatedData<Conversation>> {
  return get<PaginatedData<Conversation>>('/conversations', params)
}

/**
 * 会话详情（含消息历史）
 */
export function getConversationDetail(id: number): Promise<ConversationDetail> {
  return get<ConversationDetail>(`/conversations/${id}`)
}

/**
 * 创建会话
 */
export function createConversation(data: ConversationForm): Promise<Conversation> {
  return post<Conversation>('/conversations', data)
}

/**
 * 更新会话
 */
export function updateConversation(id: number, data: Partial<ConversationForm>): Promise<Conversation> {
  return put<Conversation>(`/conversations/${id}`, data)
}

/**
 * 删除会话
 */
export function deleteConversation(id: number): Promise<void> {
  return del<void>(`/conversations/${id}`)
}

/**
 * 清空会话消息
 */
export function clearConversationMessages(id: number): Promise<void> {
  return del<void>(`/conversations/${id}/messages`)
}

/**
 * 会话内流式问答（SSE）
 */
export async function askInConversation(
  conversationId: number,
  question: string,
  options: {
    history_turns?: number
    onSources?: (sources: unknown[], degraded: boolean, low_confidence: boolean) => void
    onMessage?: (chunk: string, fullText: string) => void
    onDone?: (data: { answer?: string; sources?: unknown[]; token_input?: number; token_output?: number; model?: string; degraded?: boolean; low_confidence?: boolean }) => void
    onError?: (error: Error) => void
    signal?: AbortSignal
  } = {}
): Promise<void> {
  const { history_turns = 6, onSources, onMessage, onDone, onError, signal } = options

  try {
    const response = await fetch(`/api/conversations/${conversationId}/ask`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({ question, history_turns }),
      signal,
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

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || !trimmed.startsWith('data:')) continue
        const dataStr = trimmed.slice(5).trim()
        if (!dataStr || dataStr === '[DONE]') continue
        try {
          const data = JSON.parse(dataStr)
          if (data.type === 'sources') {
            onSources?.(data.sources || [], data.degraded || false, data.low_confidence || false)
          } else if (data.type === 'chunk') {
            const chunk = data.content || ''
            if (chunk) {
              fullText += chunk
              onMessage?.(chunk, fullText)
            }
          } else if (data.type === 'done') {
            onDone?.({
              answer: data.answer || fullText,
              sources: data.sources || [],
              token_input: data.token_input || 0,
              token_output: data.token_output || 0,
              model: data.model || '',
              degraded: data.degraded || false,
              low_confidence: data.low_confidence || false,
            })
          } else if (data.type === 'error') {
            onError?.(new Error(data.message || '未知错误'))
          }
        } catch {
          // 非 JSON，跳过
        }
      }
    }
  } catch (error) {
    if ((error as Error).name === 'AbortError') return
    onError?.(error as Error)
  }
}
