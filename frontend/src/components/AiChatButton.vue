<template>
  <div class="ai-chat-float" @click="visible = true" title="AI 智能问答">
    <div class="chat-icon">
      <RobotOutlined />
    </div>
  </div>

  <a-modal
    v-model:open="visible"
    title="AI 智能问答"
    :footer="null"
    width="680px"
    :body-style="{ padding: 0, height: '520px', display: 'flex', flexDirection: 'column' }"
    @close="onClose"
  >
    <div class="chat-body" ref="chatBodyRef">
      <a-empty
        v-if="messages.length === 0"
        description="开始提问，探索您的知识库"
        class="empty-state"
      >
        <template #image>
          <MessageOutlined style="font-size: 48px; color: #d9d9d9" />
        </template>
      </a-empty>

      <div v-for="(msg, idx) in messages" :key="idx" class="msg-item">
        <div v-if="msg.role === 'user'" class="msg-user">
          <div class="msg-bubble user-bubble">{{ msg.content }}</div>
          <a-avatar style="background-color: #1677ff; flex-shrink: 0" :size="32">我</a-avatar>
        </div>
        <div v-else class="msg-ai">
          <a-avatar style="background-color: #52c41a; flex-shrink: 0" :size="32">AI</a-avatar>
          <div class="msg-bubble ai-bubble">
            <div
              class="msg-text markdown-body"
              :class="{ 'typing-cursor': msg.streaming }"
              v-html="renderMd(msg.content)"
            ></div>
            <div v-if="msg.sources && msg.sources.length > 0" class="msg-sources">
              <div class="sources-title"><LinkOutlined /> 参考来源：</div>
              <a-tag v-for="(src, sidx) in msg.sources" :key="sidx" color="blue" style="margin: 2px">
                {{ src.title }}
              </a-tag>
            </div>
            <div v-if="!msg.streaming && msg.skill_name" class="msg-meta">
              <ThunderboltOutlined /> {{ msg.skill_name }}
              <span v-if="msg.total_tokens"> · Token: {{ msg.total_tokens }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input">
      <a-input
        v-model:value="inputQuestion"
        placeholder="输入您的问题..."
        :disabled="streaming"
        @press-enter="onSend"
        size="large"
      >
        <template #suffix>
          <a-button
            type="primary"
            size="small"
            :loading="streaming"
            :disabled="!inputQuestion.trim()"
            @click="onSend"
          >
            {{ streaming ? '生成中' : '发送' }}
          </a-button>
        </template>
      </a-input>
      <div v-if="streaming" class="stop-bar">
        <a-button type="link" size="small" @click="stopStream">停止生成</a-button>
      </div>
    </div>
  </a-modal>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import {
  RobotOutlined,
  MessageOutlined,
  LinkOutlined,
  ThunderboltOutlined
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import MarkdownIt from 'markdown-it'
import { askQuestionStream } from '@/api/qa'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

interface Source {
  knowledge_id: number
  title: string
}

interface ChatMsg {
  role: 'user' | 'ai'
  content: string
  streaming?: boolean
  sources?: Source[]
  skill_name?: string
  total_tokens?: number
}

const visible = ref(false)
const messages = ref<ChatMsg[]>([])
const inputQuestion = ref('')
const streaming = ref(false)
const chatBodyRef = ref<HTMLDivElement | null>(null)
let abortCtrl: AbortController | null = null

function renderMd(text: string): string {
  return text ? md.render(text) : ''
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  if (chatBodyRef.value) {
    chatBodyRef.value.scrollTop = chatBodyRef.value.scrollHeight
  }
}

async function onSend(): Promise<void> {
  const q = inputQuestion.value.trim()
  if (!q || streaming.value) return

  messages.value.push({ role: 'user', content: q })
  const aiMsg: ChatMsg = { role: 'ai', content: '', streaming: true }
  messages.value.push(aiMsg)

  inputQuestion.value = ''
  streaming.value = true
  await scrollToBottom()

  abortCtrl = new AbortController()

  await askQuestionStream(q, {
    use_cache: true,
    signal: abortCtrl.signal,
    onMessage: (_chunk, fullText) => {
      aiMsg.content = fullText
      scrollToBottom()
    },
    onDone: (data) => {
      aiMsg.streaming = false
      if (data.sources) aiMsg.sources = data.sources as Source[]
      if (data.skill_name) aiMsg.skill_name = data.skill_name
      if (data.tokens) aiMsg.total_tokens = data.tokens
      streaming.value = false
    },
    onError: (err) => {
      aiMsg.streaming = false
      aiMsg.content = `抱歉，出错了：${err.message}`
      streaming.value = false
      message.error('问答请求失败')
    }
  })
}

function stopStream(): void {
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
  const last = messages.value[messages.value.length - 1]
  if (last?.role === 'ai') last.streaming = false
  streaming.value = false
}

function onClose(): void {
  if (streaming.value) stopStream()
}
</script>

<style scoped>
.ai-chat-float {
  position: fixed;
  bottom: 32px;
  right: 32px;
  z-index: 1000;
  cursor: pointer;
  transition: all 0.3s;
}

.ai-chat-float:hover {
  transform: scale(1.1);
}

.ai-chat-float:hover .chat-icon {
  box-shadow: 0 6px 20px rgba(22, 119, 255, 0.45);
}

.chat-icon {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1677ff, #4096ff);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 24px;
  box-shadow: 0 4px 14px rgba(22, 119, 255, 0.35);
  transition: box-shadow 0.3s;
}

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background: #fafafa;
}

.empty-state {
  padding-top: 80px;
}

.msg-item {
  margin-bottom: 12px;
}

.msg-user {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.msg-ai {
  display: flex;
  gap: 8px;
}

.msg-bubble {
  max-width: 80%;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
}

.user-bubble {
  background: #1677ff;
  color: #fff;
}

.ai-bubble {
  background: #fff;
  border: 1px solid #f0f0f0;
}

.msg-sources {
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #f0f0f0;
}

.sources-title {
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
  margin-bottom: 4px;
}

.msg-meta {
  margin-top: 6px;
  font-size: 12px;
  color: rgba(0, 0, 0, 0.45);
}

.typing-cursor::after {
  content: '▊';
  animation: blink 0.8s infinite;
  color: #1677ff;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.chat-input {
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
  background: #fff;
}

.stop-bar {
  text-align: center;
  margin-top: 4px;
}
</style>
