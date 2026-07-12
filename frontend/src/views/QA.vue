<template>
  <div class="qa-page">
    <!-- 对话区域 -->
    <div class="chat-area" ref="chatAreaRef" @click="onChatClick">
      <div class="chat-inner">
        <a-empty
          v-if="messages.length === 0"
          description="开始提问，探索您的知识库"
          class="empty-state"
        >
          <template #image>
            <MessageOutlined style="font-size: 64px; color: #d9d9d9" />
          </template>
        </a-empty>

        <div v-for="(msg, idx) in messages" :key="idx" class="msg-item">
          <!-- 用户问题 -->
          <div v-if="msg.role === 'user'" class="msg-user">
            <div class="msg-bubble user-bubble">
              <div class="msg-text">{{ msg.content }}</div>
            </div>
            <a-avatar style="background-color: #1677ff; flex-shrink: 0">我</a-avatar>
          </div>
          <!-- AI 回答 -->
          <div v-else>
            <div class="msg-ai">
              <a-avatar style="background-color: #52c41a; flex-shrink: 0">AI</a-avatar>
              <div class="msg-bubble ai-bubble">
                <div
                  class="msg-text markdown-body"
                  :class="{ 'typing-cursor': msg.streaming }"
                  v-html="renderAnswer(msg.content, msg.sources)"
                ></div>
                <!-- 来源引用 -->
                <div v-if="msg.sources && msg.sources.length > 0" class="msg-sources">
                  <div class="sources-title">
                    <LinkOutlined /> 参考来源：
                  </div>
                  <div class="sources-list">
                    <div
                      v-for="(src, sidx) in msg.sources"
                      :key="sidx"
                      class="source-card"
                      @click="goKnowledge(src.knowledge_id)"
                    >
                      <div class="source-header">
                        <span class="source-num">{{ sidx + 1 }}</span>
                        <span class="source-title-text">{{ src.title }}</span>
                        <span v-if="src.score != null" class="source-score" :class="scoreClass(src.score)">
                          {{ (src.score * 100).toFixed(0) }}%
                        </span>
                      </div>
                      <div v-if="src.snippet" class="source-snippet">{{ src.snippet }}</div>
                    </div>
                  </div>
                </div>
                <!-- 降级模式提示 -->
                <div v-if="!msg.streaming && msg.degraded" class="msg-degraded">
                  <WarningOutlined /> 当前为降级模式（未配置 Embedding 模型），仅使用关键词检索，检索质量可能下降
                </div>
                <!-- 低置信度提示 -->
                <div v-if="!msg.streaming && msg.low_confidence && !msg.degraded" class="msg-low-confidence">
                  <WarningOutlined /> 以下回答基于低相关性资料，请谨慎参考
                </div>
                <!-- Skill & Token -->
                <div v-if="!msg.streaming" class="msg-meta">
                  <span v-if="msg.skill_name">
                    <ThunderboltOutlined /> {{ msg.skill_name }}
                  </span>
                  <span v-if="msg.total_tokens">
                    Token: {{ msg.total_tokens }}
                  </span>
                </div>
                <!-- 反馈 -->
                <div v-if="!msg.streaming && msg.history_id" class="msg-feedback">
                  <span class="feedback-label">这个回答对您有帮助吗？</span>
                  <a-space>
                    <a-button
                      size="small"
                      :type="msg.feedback === 'useful' ? 'primary' : 'default'"
                      @click="onFeedback(msg, 'useful')"
                    >
                      <LikeOutlined /> 有用
                    </a-button>
                    <a-button
                      size="small"
                      :type="msg.feedback === 'useless' ? 'primary' : 'default'"
                      danger
                      @click="onFeedback(msg, 'useless')"
                    >
                      <DislikeOutlined /> 无用
                    </a-button>
                  </a-space>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 推荐追问 -->
        <div v-if="suggestions.length > 0 && !streaming" class="suggestions">
          <div class="suggestions-title">
            <BulbOutlined /> 推荐追问：
          </div>
          <div class="suggestions-list">
            <a-tag
              v-for="(s, idx) in suggestions"
              :key="idx"
              color="orange"
              class="suggestion-item"
              @click="onSuggestionClick(s)"
            >
              {{ s }}
            </a-tag>
          </div>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <a-input-group compact class="input-group">
        <a-input
          v-model:value="inputQuestion"
          placeholder="输入您的问题..."
          :disabled="streaming"
          @press-enter="onSend"
          style="width: calc(100% - 100px)"
          size="large"
        />
        <a-button
          type="primary"
          size="large"
          :loading="streaming"
          :disabled="!inputQuestion.trim()"
          @click="onSend"
          style="width: 100px"
        >
          {{ streaming ? '生成中' : '发送' }}
        </a-button>
      </a-input-group>
      <div v-if="streaming" class="stop-tip">
        <a-button type="link" size="small" @click="stopStream">停止生成</a-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  MessageOutlined,
  LikeOutlined,
  DislikeOutlined,
  LinkOutlined,
  ThunderboltOutlined,
  BulbOutlined,
  WarningOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import { askQuestionStream, submitFeedback, getSuggestions } from '@/api/qa'
import type { QAReference } from '@/types'

const router = useRouter()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

interface ChatMessage {
  role: 'user' | 'ai'
  content: string
  streaming?: boolean
  history_id?: number
  sources?: QAReference[]
  skill_name?: string
  total_tokens?: number
  feedback?: 'useful' | 'useless' | null
  degraded?: boolean
  low_confidence?: boolean
}

const messages = ref<ChatMessage[]>([])
const inputQuestion = ref('')
const streaming = ref(false)
const suggestions = ref<string[]>([])
const chatAreaRef = ref<HTMLDivElement | null>(null)
let abortController: AbortController | null = null

function renderMarkdown(text: string): string {
  if (!text) return ''
  return md.render(text)
}

function renderAnswer(text: string, sources?: QAReference[]): string {
  if (!text) return ''
  let html = md.render(text)
  // 将 [1] [2] 等角标替换为可点击的徽标
  if (sources && sources.length > 0) {
    html = html.replace(/\[(\d+)\]/g, (match, numStr) => {
      const num = parseInt(numStr)
      if (num >= 1 && num <= sources.length) {
        const src = sources[num - 1]
        // 转义 title 中的特殊字符，防止 XSS 和 HTML 属性注入
        const safeTitle = escapeHtml(src.title || '')
        const safeKid = encodeURIComponent(String(src.knowledge_id || ''))
        return `<a class="cite-badge" data-kid="${safeKid}" title="${safeTitle}">[${num}]</a>`
      }
      return match
    })
  }
  // 统一过 DOMPurify，防止 LLM 输出中的潜在 XSS
  return DOMPurify.sanitize(html, {
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel', 'data-kid'],
  })
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function scoreClass(score: number): string {
  if (score >= 0.75) return 'score-high'
  if (score >= 0.5) return 'score-mid'
  return 'score-low'
}

async function onSend(): Promise<void> {
  const q = inputQuestion.value.trim()
  if (!q || streaming.value) return

  // 构建对话历史（排除当前问题，取最近 6 轮）
  const history = messages.value
    .filter((m) => m.content && !m.streaming)
    .slice(-6)
    .map((m) => ({
      role: m.role === 'ai' ? 'assistant' : 'user',
      content: m.content
    }))

  // 添加用户消息
  messages.value.push({ role: 'user', content: q })
  // 添加 AI 占位
  const aiMsg: ChatMessage = {
    role: 'ai',
    content: '',
    streaming: true,
    feedback: null
  }
  messages.value.push(aiMsg)

  inputQuestion.value = ''
  streaming.value = true
  suggestions.value = []
  await scrollToBottom()

  abortController = new AbortController()

  await askQuestionStream(q, {
    use_cache: true,
    history,
    signal: abortController.signal,
    onMessage: (_chunk, fullText) => {
      aiMsg.content = fullText
      scrollToBottom()
    },
    onDone: (data) => {
      aiMsg.streaming = false
      if (data.history_id) aiMsg.history_id = data.history_id
      if (data.sources) aiMsg.sources = data.sources as QAReference[]
      if (data.tokens) aiMsg.total_tokens = data.tokens
      if (data.degraded) aiMsg.degraded = true
      if (data.low_confidence) aiMsg.low_confidence = true
      streaming.value = false
      loadSuggestions(q)
    },
    onError: (err) => {
      aiMsg.streaming = false
      aiMsg.content = `抱歉，生成回答时出错：${err.message}`
      streaming.value = false
      message.error('问答请求失败')
    }
  })
}

function stopStream(): void {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'ai') {
    lastMsg.streaming = false
  }
  streaming.value = false
}

async function loadSuggestions(question: string): Promise<void> {
  try {
    suggestions.value = await getSuggestions(question)
  } catch {
    suggestions.value = []
  }
}

function onSuggestionClick(s: string): void {
  inputQuestion.value = s
  onSend()
}

async function onFeedback(msg: ChatMessage, feedback: 'useful' | 'useless'): Promise<void> {
  if (!msg.history_id) return
  try {
    await submitFeedback(msg.history_id, feedback)
    msg.feedback = feedback
    message.success('感谢您的反馈')
  } catch {
    // ignore
  }
}

function goKnowledge(id: number): void {
  router.push(`/knowledge/detail/${id}`)
}

function onChatClick(e: MouseEvent): void {
  const target = e.target as HTMLElement
  if (target.classList.contains('cite-badge')) {
    const kid = parseInt(target.getAttribute('data-kid') || '0')
    if (kid) goKnowledge(kid)
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (chatAreaRef.value) {
    chatAreaRef.value.scrollTop = chatAreaRef.value.scrollHeight
  }
}

onMounted(() => {
  scrollToBottom()
})
</script>

<style scoped>
.qa-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 56px - 56px - 48px);
  max-width: 1100px;
  margin: 0 auto;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fff;
  border-radius: 8px 8px 0 0;
  border: 1px solid #f0f0f0;
}

.chat-inner {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-state {
  margin-top: 80px;
}

.msg-item {
  width: 100%;
}

.msg-user {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.msg-ai {
  display: flex;
  gap: 12px;
}

.msg-bubble {
  max-width: 75%;
  padding: 12px 16px;
  border-radius: 8px;
  line-height: 1.6;
  word-break: break-word;
}

.user-bubble {
  background: #1677ff;
  color: #fff;
}

.ai-bubble {
  background: #f5f5f5;
  color: rgba(0, 0, 0, 0.85);
}

.msg-text {
  white-space: pre-wrap;
}

.msg-sources {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px dashed #d9d9d9;
}

.sources-title {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  margin-bottom: 4px;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.source-card {
  padding: 8px 10px;
  background: #fafafa;
  border: 1px solid #f0f0f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.source-card:hover {
  background: #f0f7ff;
  border-color: #91caff;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.source-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #1677ff;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.source-title-text {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.85);
  font-weight: 500;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-score {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 8px;
  flex-shrink: 0;
}

.score-high {
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.score-mid {
  background: #fff7e6;
  color: #fa8c16;
  border: 1px solid #ffd591;
}

.score-low {
  background: #fff2f0;
  color: #ff4d4f;
  border: 1px solid #ffccc7;
}

.source-snippet {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.55);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.msg-meta {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  display: flex;
  gap: 16px;
}

.msg-degraded {
  margin-top: 8px;
  padding: 6px 10px;
  font-size: 12px;
  color: #d46b08;
  background: #fff7e6;
  border: 1px solid #ffd591;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.msg-low-confidence {
  margin-top: 8px;
  padding: 6px 10px;
  font-size: 12px;
  color: #cf1322;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.msg-feedback {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed #d9d9d9;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.feedback-label {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
}

.suggestions {
  margin-top: 12px;
}

.suggestions-title {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.65);
  margin-bottom: 4px;
}

.suggestions-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.suggestion-item {
  cursor: pointer;
}

.suggestion-item:hover {
  opacity: 0.85;
}

.input-area {
  background: #fff;
  padding: 12px 16px;
  border-radius: 0 0 8px 8px;
  border: 1px solid #f0f0f0;
  border-top: none;
}

.input-group {
  display: flex;
}

.stop-tip {
  text-align: center;
  margin-top: 4px;
}

:deep(.ai-bubble .markdown-body) {
  font-size: 14px;
}

:deep(.ai-bubble .markdown-body code) {
  background: #e6e6e6;
  color: #d63384;
}

:deep(.ai-bubble .markdown-body pre) {
  background: #1f1f1f;
  color: #f0f0f0;
}

:deep(.ai-bubble .markdown-body .cite-badge) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  margin: 0 2px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  color: #1677ff;
  background: #e6f4ff;
  border: 1px solid #91caff;
  border-radius: 3px;
  cursor: pointer;
  text-decoration: none;
  vertical-align: super;
  transition: all 0.15s;
}

:deep(.ai-bubble .markdown-body .cite-badge:hover) {
  background: #1677ff;
  color: #fff;
}
</style>
