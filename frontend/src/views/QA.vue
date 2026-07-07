<template>
  <div class="qa-page">
    <!-- 对话区域 -->
    <div class="chat-area" ref="chatAreaRef">
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
                  v-html="renderMarkdown(msg.content)"
                ></div>
                <!-- 来源引用 -->
                <div v-if="msg.sources && msg.sources.length > 0" class="msg-sources">
                  <div class="sources-title">
                    <LinkOutlined /> 参考来源：
                  </div>
                  <div class="sources-list">
                    <a
                      v-for="(src, sidx) in msg.sources"
                      :key="sidx"
                      class="source-item"
                      @click="goKnowledge(src.knowledge_id)"
                    >
                      <a-tag color="blue">
                        {{ sidx + 1 }}. {{ src.title }}
                      </a-tag>
                    </a>
                  </div>
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
  BulbOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import MarkdownIt from 'markdown-it'
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

async function onSend(): Promise<void> {
  const q = inputQuestion.value.trim()
  if (!q || streaming.value) return

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
  flex-wrap: wrap;
  gap: 4px;
}

.source-item {
  cursor: pointer;
}

.msg-meta {
  margin-top: 8px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  display: flex;
  gap: 16px;
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
</style>
