<template>
  <div class="conversation-page">
    <!-- 左侧：会话列表 -->
    <div class="sidebar">
      <div class="sidebar-header">
        <a-button type="primary" block @click="openCreateModal">
          <PlusOutlined />新建会话
        </a-button>
      </div>
      <div class="sidebar-search">
        <a-input-search
          v-model:value="query.keyword"
          placeholder="搜索会话标题"
          allow-clear
          @search="onSearch"
        />
      </div>
      <a-spin :spinning="listLoading" wrapper-class-name="conv-spin">
        <div class="conv-list">
          <a-empty
            v-if="!listLoading && conversationList.length === 0"
            description="暂无会话"
            :image="simpleImage"
          />
          <div
            v-for="conv in conversationList"
            :key="conv.id"
            class="conv-item"
            :class="{ active: currentConversation?.id === conv.id }"
            @click="selectConversation(conv.id)"
          >
            <div class="conv-item-title">{{ conv.title }}</div>
            <div v-if="conv.knowledge_base_names && conv.knowledge_base_names.length > 0" class="conv-item-tags">
              <a-tag
                v-for="name in conv.knowledge_base_names"
                :key="name"
                color="blue"
                class="kb-tag"
              >
                {{ name }}
              </a-tag>
            </div>
            <div class="conv-item-meta">
              <span><MessageOutlined /> {{ conv.message_count }} 条</span>
              <span>{{ formatTime(conv.updated_at) }}</span>
            </div>
            <a-popconfirm
              title="确定删除此会话？相关消息将一并删除。"
              ok-text="删除"
              ok-type="danger"
              @confirm="handleDelete(conv.id)"
            >
              <a-button
                type="text"
                size="small"
                danger
                class="conv-delete-btn"
                @click.stop
              >
                <DeleteOutlined />
              </a-button>
            </a-popconfirm>
          </div>
        </div>
      </a-spin>
    </div>

    <!-- 右侧：聊天区域 -->
    <div class="chat-panel">
      <template v-if="currentConversation">
        <!-- 顶部 -->
        <div class="chat-header">
          <div class="chat-header-info">
            <div class="chat-title">{{ currentConversation.title }}</div>
            <div v-if="currentConversation.knowledge_base_names?.length" class="chat-kbs">
              <a-tag
                v-for="name in currentConversation.knowledge_base_names"
                :key="name"
                color="blue"
              >
                {{ name }}
              </a-tag>
            </div>
          </div>
          <a-popconfirm
            title="确定清空当前会话的所有消息？"
            ok-text="清空"
            ok-type="danger"
            @confirm="handleClearMessages"
          >
            <a-button danger size="small" :disabled="streaming || messages.length === 0">
              <ClearOutlined />清空消息
            </a-button>
          </a-popconfirm>
        </div>

        <!-- 消息列表 -->
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
              <!-- 用户消息 -->
              <div v-if="msg.role === 'user'" class="msg-user">
                <div class="msg-bubble user-bubble">
                  <div class="msg-text">{{ msg.content }}</div>
                </div>
                <a-avatar style="background-color: #1677ff; flex-shrink: 0">我</a-avatar>
              </div>
              <!-- AI 消息 -->
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
                            <span v-if="src.page_number && src.page_number > 0" class="source-page">
                              <FilePdfOutlined /> 第 {{ src.page_number }} 页
                            </span>
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
                  </div>
                </div>
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
              v-if="!streaming"
              type="primary"
              size="large"
              :disabled="!inputQuestion.trim()"
              @click="onSend"
              style="width: 100px"
            >
              发送
            </a-button>
            <a-button
              v-else
              type="primary"
              danger
              size="large"
              @click="stopStream"
              style="width: 100px"
            >
              停止
            </a-button>
          </a-input-group>
        </div>
      </template>

      <!-- 空状态 -->
      <div v-else class="no-conversation">
        <a-empty description="请选择或创建会话">
          <template #image>
            <MessageOutlined style="font-size: 64px; color: #d9d9d9" />
          </template>
        </a-empty>
      </div>
    </div>

    <!-- 新建会话弹窗 -->
    <a-modal
      v-model:open="formVisible"
      title="新建会话"
      :confirm-loading="submitting"
      width="560px"
      @ok="handleCreate"
    >
      <a-form layout="vertical">
        <a-form-item label="标题" required>
          <a-input
            v-model:value="form.title"
            placeholder="请输入会话标题"
            :maxlength="100"
          />
        </a-form-item>
        <a-form-item label="描述">
          <a-textarea
            v-model:value="form.description"
            placeholder="请输入描述（可选）"
            :rows="2"
            :maxlength="500"
          />
        </a-form-item>
        <a-form-item label="关联知识库">
          <a-select
            v-model:value="form.knowledge_base_ids"
            mode="multiple"
            placeholder="选择关联的知识库（可多选）"
            :loading="kbLoading"
            :field-names="{ label: 'name', value: 'id' }"
            allow-clear
          >
            <a-select-option
              v-for="kb in knowledgeBaseList"
              :key="kb.id"
              :value="kb.id"
            >
              {{ kb.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  PlusOutlined,
  DeleteOutlined,
  ClearOutlined,
  MessageOutlined,
  LinkOutlined,
  WarningOutlined,
  FilePdfOutlined
} from '@ant-design/icons-vue'
import { message, Empty as AEmpty } from 'ant-design-vue'
import dayjs from 'dayjs'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import {
  getConversationList,
  getConversationDetail,
  createConversation,
  deleteConversation,
  clearConversationMessages,
  askInConversation
} from '@/api/conversation'
import { getKnowledgeBaseList } from '@/api/knowledgeBase'
import type {
  Conversation,
  ConversationDetail,
  ConversationMessage,
  ConversationForm,
  QAReference,
  KnowledgeBase
} from '@/types'

const router = useRouter()
const md = new MarkdownIt({ html: false, linkify: true, breaks: true })
const simpleImage = AEmpty.PRESENTED_IMAGE_SIMPLE

interface DisplayMessage extends ConversationMessage {
  streaming?: boolean
  degraded?: boolean
  low_confidence?: boolean
}

const conversationList = ref<Conversation[]>([])
const currentConversation = ref<ConversationDetail | null>(null)
const messages = ref<DisplayMessage[]>([])
const inputQuestion = ref('')
const streaming = ref(false)
const listLoading = ref(false)
const chatAreaRef = ref<HTMLDivElement | null>(null)
let abortController: AbortController | null = null

const query = ref({ keyword: '', page: 1, page_size: 50 })

// 新建会话
const formVisible = ref(false)
const submitting = ref(false)
const kbLoading = ref(false)
const knowledgeBaseList = ref<KnowledgeBase[]>([])
const form = ref<{ title: string; description: string; knowledge_base_ids: number[] }>({
  title: '',
  description: '',
  knowledge_base_ids: []
})

function formatTime(time: string): string {
  return dayjs(time).format('YYYY-MM-DD HH:mm')
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
        const safeTitle = escapeHtml(src.title || '')
        const safeKid = encodeURIComponent(String(src.knowledge_id || ''))
        return `<a class="cite-badge" data-kid="${safeKid}" title="${safeTitle}">[${num}]</a>`
      }
      return match
    })
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_ATTR: ['href', 'src', 'alt', 'title', 'class', 'target', 'rel', 'data-kid']
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

async function loadConversationList(): Promise<void> {
  listLoading.value = true
  try {
    const res = await getConversationList({
      keyword: query.value.keyword || undefined,
      page: query.value.page,
      page_size: query.value.page_size
    })
    conversationList.value = res.items || []
  } catch {
    // ignore
  } finally {
    listLoading.value = false
  }
}

async function loadKnowledgeBases(): Promise<void> {
  kbLoading.value = true
  try {
    const res = await getKnowledgeBaseList({ page: 1, page_size: 200 })
    knowledgeBaseList.value = res.items || []
  } catch {
    knowledgeBaseList.value = []
  } finally {
    kbLoading.value = false
  }
}

function onSearch(): void {
  query.value.page = 1
  loadConversationList()
}

async function selectConversation(id: number): Promise<void> {
  if (streaming.value) {
    message.warning('请等待当前生成完成')
    return
  }
  if (currentConversation.value?.id === id) return
  try {
    const detail = await getConversationDetail(id)
    currentConversation.value = detail
    messages.value = (detail.messages || []).map((m) => ({ ...m }))
    await scrollToBottom()
  } catch {
    message.error('加载会话详情失败')
  }
}

function openCreateModal(): void {
  form.value = { title: '', description: '', knowledge_base_ids: [] }
  formVisible.value = true
  if (knowledgeBaseList.value.length === 0) {
    loadKnowledgeBases()
  }
}

async function handleCreate(): Promise<void> {
  if (!form.value.title.trim()) {
    message.warning('请输入会话标题')
    return
  }
  submitting.value = true
  try {
    const payload: ConversationForm = {
      title: form.value.title.trim(),
      description: form.value.description?.trim() || undefined,
      knowledge_base_ids: form.value.knowledge_base_ids
    }
    const conv = await createConversation(payload)
    message.success('创建成功')
    formVisible.value = false
    await loadConversationList()
    await selectConversation(conv.id)
  } catch {
    // ignore
  } finally {
    submitting.value = false
  }
}

async function handleDelete(id: number): Promise<void> {
  try {
    await deleteConversation(id)
    message.success('删除成功')
    if (currentConversation.value?.id === id) {
      currentConversation.value = null
      messages.value = []
    }
    loadConversationList()
  } catch {
    // ignore
  }
}

async function handleClearMessages(): Promise<void> {
  if (!currentConversation.value) return
  try {
    await clearConversationMessages(currentConversation.value.id)
    message.success('已清空消息')
    messages.value = []
    currentConversation.value.message_count = 0
    loadConversationList()
  } catch {
    // ignore
  }
}

async function onSend(): Promise<void> {
  const q = inputQuestion.value.trim()
  if (!q || streaming.value || !currentConversation.value) return

  const convId = currentConversation.value.id

  // 用户消息
  messages.value.push({
    id: 0,
    conversation_id: convId,
    role: 'user',
    content: q,
    sources: [],
    token_input: 0,
    token_output: 0,
    duration_ms: 0,
    created_at: new Date().toISOString()
  })

  // AI 占位
  const aiMsg: DisplayMessage = {
    id: 0,
    conversation_id: convId,
    role: 'assistant',
    content: '',
    sources: [],
    token_input: 0,
    token_output: 0,
    duration_ms: 0,
    created_at: new Date().toISOString(),
    streaming: true
  }
  messages.value.push(aiMsg)

  inputQuestion.value = ''
  streaming.value = true
  await scrollToBottom()

  abortController = new AbortController()

  await askInConversation(convId, q, {
    signal: abortController.signal,
    onSources: (sources, degraded, low_confidence) => {
      aiMsg.sources = sources as QAReference[]
      if (degraded) aiMsg.degraded = true
      if (low_confidence) aiMsg.low_confidence = true
    },
    onMessage: (_chunk, fullText) => {
      aiMsg.content = fullText
      scrollToBottom()
    },
    onDone: () => {
      aiMsg.streaming = false
      streaming.value = false
      // 完成后刷新消息列表，获取最终持久化状态
      refreshMessages()
    },
    onError: (err) => {
      aiMsg.streaming = false
      aiMsg.content = `抱歉，生成回答时出错：${err.message}`
      streaming.value = false
      message.error('问答请求失败')
    }
  })
}

async function refreshMessages(): Promise<void> {
  if (!currentConversation.value) return
  try {
    const detail = await getConversationDetail(currentConversation.value.id)
    currentConversation.value = detail
    messages.value = (detail.messages || []).map((m) => ({ ...m }))
    loadConversationList()
  } catch {
    // ignore
  }
}

function stopStream(): void {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg && lastMsg.role === 'assistant') {
    lastMsg.streaming = false
  }
  streaming.value = false
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
  loadConversationList()
  loadKnowledgeBases()
})
</script>

<style scoped>
.conversation-page {
  display: flex;
  height: calc(100vh - 56px - 56px - 48px);
  gap: 16px;
}

/* 左侧会话列表 */
.sidebar {
  width: 280px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.sidebar-search {
  padding: 8px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.conv-list {
  padding: 8px;
  overflow-y: auto;
}

.conv-item {
  position: relative;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  margin-bottom: 4px;
}

.conv-item:hover {
  background: #f5f5f5;
}

.conv-item.active {
  background: #e6f4ff;
}

.conv-item-title {
  font-size: 14px;
  font-weight: 500;
  color: rgba(0, 0, 0, 0.85);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 24px;
}

.conv-item-tags {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.kb-tag {
  font-size: 11px;
  margin: 0;
  padding: 0 4px;
  line-height: 16px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-item-meta {
  margin-top: 6px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: rgba(0, 0, 0, 0.45);
}

.conv-item-meta span {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.conv-delete-btn {
  position: absolute;
  top: 6px;
  right: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.conv-item:hover .conv-delete-btn {
  opacity: 1;
}

/* 右侧聊天区域 */
.chat-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #fff;
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
  min-width: 0;
}

.chat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #f0f0f0;
  gap: 12px;
}

.chat-header-info {
  flex: 1;
  min-width: 0;
}

.chat-title {
  font-size: 16px;
  font-weight: 600;
  color: rgba(0, 0, 0, 0.88);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-kbs {
  margin-top: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
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

.source-page {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 11px;
  color: #722ed1;
  background: #f9f0ff;
  border: 1px solid #d3adf7;
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

.input-area {
  padding: 12px 16px;
  border-top: 1px solid #f0f0f0;
}

.input-group {
  display: flex;
}

.no-conversation {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
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

:deep(.conv-spin) {
  height: 100%;
  display: block;
}

:deep(.conv-spin .ant-spin-container) {
  height: 100%;
}

@media (max-width: 768px) {
  .conversation-page {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    max-height: 240px;
  }
}
</style>
